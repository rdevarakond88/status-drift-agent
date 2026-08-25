#!/usr/bin/env python3
"""Layer 2 of status-translation-agent: turns a fetch-layer commit record into
a plain-language status update via an actual AI call. Enforces the locked
rules deterministically wherever the rule is mechanical (allowed status
values, the Code-complete follow-up question, completion-% suppression);
leaves only the judgment calls (claim-vs-diff comparison, tone, story-context
reasoning) to the model.
"""

import json
import re
import subprocess
import sys

ALLOWED_STATUSES = {"Code complete", "Tested", "Pending", "Flagged"}

FOLLOW_UP_QUESTION = (
    " Follow-up for the developer: when/how will this be tested, and what's the ETA?"
)

SYSTEM_PROMPT = """You translate a single raw git commit's structured data into a plain-language status update for a project-tracking tool. Follow these rules exactly: they are locked, non-negotiable constraints:

1. status must be exactly one of: "Code complete", "Tested", "Pending", "Flagged". Never any other word, never a vague synonym like "done".
2. Use "Tested" only if the commit message or diff explicitly confirms that necessary testing was actually performed and passed, not queued, not routed to a tester, not partially covered by an automated smoke check while a required verification step (e.g. on-device testing) is still explicitly outstanding. In every other case where the code itself looks complete and consistent with its claim, default to "Code complete". Note: touches_app_code is provided and enforced separately in code; if it's false, "Tested" is not an available answer regardless of what you decide here, so don't bother reasoning toward it for a docs/logs/config-only commit.
3. Compare every claim in the commit message and (if present) the PR title/description against the actual diff. If a claim is not supported by the diff (overstates scope, claims a fix the diff doesn't show, claims verification that isn't evidenced), state the mismatch as a plain fact. Do not guess or invent a reason why the mismatch exists. When a real mismatch exists, set status to "Flagged".
4. (Handled automatically outside your output: ignore this rule, do not add anything about it yourself.)
5. Do not estimate or output a percent-complete number based on diff size or your own impression. No acceptance-criteria data is being supplied to you in this run, so completion cannot be computed; do not attempt it or mention a percentage.
6. If story_attribution.status is "unattributed": do not guess or invent a story/issue. If the commit's own message, diff, and files changed make its purpose and completeness clear on their own, e.g. a self-contained process, documentation, or governance action that plainly isn't tied to a product story, it is fine to classify status normally (Code complete / Pending / etc.) and just state plainly that no story was attributed and none was needed. If instead the commit's purpose genuinely cannot be determined from the message, diff, and files changed (e.g. a generic message like "fix bug" with no other context), status must be "Flagged", and the narrative must say this needs developer/TPM input to identify both the intent and the story; do not fabricate a plausible-sounding purpose.
7. Output exactly one paragraph in the "narrative" field: plain language, standup tone, understandable by both a technical and a non-technical reader. No code syntax dumped into the paragraph, no jargon left undefined.
8. Never phrase anything as if you personally verified, ran, or confirmed something you did not actually check from the given data (e.g. do not say "I confirmed this works end-to-end", you only read a diff and a message, you did not execute anything). Hedge honestly wherever the data doesn't support a confident claim.
9. sweeping_claim_check is provided when the commit message uses sweeping language ("anywhere", "everywhere", "no longer exists", "completely", etc) about a specific quoted piece of text. When detected is true, its verifications list already contains the result of actually searching the repository for that text: this is verified fact, not something for you to infer or re-check from the diff alone. If any verification shows claim_holds as false (the text is still found somewhere, listed in still_found_at), treat that as a real, evidenced mismatch under rule 3 and reflect it plainly in the narrative and status. If verifications is empty (nothing quoted to check, or nothing matched), sweeping_claim_check gives you nothing extra to act on.

You will be given: the commit message, the full diff, the list of files changed, PR metadata if any (treat PR title/description as another claim to check against the diff, not as verified fact), a story_attribution object already computed upstream (you must not override or re-derive story_id yourself), and a sweeping_claim_check object (see rule 9).

Respond with ONLY a JSON object, no markdown fences, no extra text, in exactly this shape:
{"status": "<one of the four values>", "narrative": "<one paragraph>"}
"""


def build_user_prompt(record):
    payload = {
        "commit_message": record["commit_message"],
        "files_changed": record["files_changed"],
        "full_diff": record["full_diff"],
        "pr_metadata": record.get("pr_metadata", []),
        "story_attribution": record["story_attribution"],
        "is_merge_commit": record.get("is_merge_commit", False),
        "touches_app_code": record.get("touches_app_code", True),
        "sweeping_claim_check": record.get(
            "sweeping_claim_check", {"detected": False, "keywords_matched": [], "verifications": []}
        ),
    }
    return json.dumps(payload)


def call_claude(system_prompt, user_prompt, timeout=120):
    result = subprocess.run(
        ["claude", "-p", "--system-prompt", system_prompt],
        input=user_prompt, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed: {result.stderr.strip()}")
    return result.stdout.strip()


def parse_model_output(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    parsed = json.loads(text)
    if "status" not in parsed or "narrative" not in parsed:
        raise ValueError(f"model output missing required keys: {parsed}")
    if parsed["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"model returned an out-of-contract status: {parsed['status']!r}")
    return parsed


def generate_status_update(record):
    user_prompt = build_user_prompt(record)
    raw = call_claude(SYSTEM_PROMPT, user_prompt)
    parsed = parse_model_output(raw)

    narrative = parsed["narrative"]
    status = parsed["status"]

    # Hard block: "Tested" is not an available answer for a commit that
    # doesn't touch any real source file, no matter what the model (or the
    # commit message) claims.
    if status == "Tested" and not record.get("touches_app_code", True):
        status = "Code complete"

    # Rule 4, enforced in code rather than trusted to the model.
    if status == "Code complete" and FOLLOW_UP_QUESTION.strip() not in narrative:
        narrative = narrative.rstrip() + FOLLOW_UP_QUESTION

    return {
        "commit_id": record["commit_id"],
        "status": status,
        "narrative": narrative,
        "completion": "can't compute completion",
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        result = generate_status_update(record)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
