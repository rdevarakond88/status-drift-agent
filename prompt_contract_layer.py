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
10. Each entry in pr_metadata carries describes_state_as_of: "PR merge time, not this individual commit's own point in time." A PR's title/description describe the aggregate, final state of everything the PR bundles, as of when it was merged, not the state of this one commit at the moment it was authored. Do not treat a PR-level claim (e.g. "verified end-to-end", "no further testing needed") as contradicting a narrower or earlier claim inside this commit's own message or diff purely because they differ: by merge time, other commits in the same PR may have completed what this one commit alone had not yet done. This is not license to ignore PR claims: if the PR's own claim doesn't hold up against what the actual code shows, that is still a mismatch under rule 3. It only means a difference in scope or timing between "this commit" and "the whole PR at merge" is not, by itself, a contradiction to flag.
11. unexplained_deletions lists any file this commit deletes entirely that isn't named anywhere in the commit message. If it's non-empty, status must be "Flagged" (this is enforced separately in code as a safety net, but write the narrative as if it's your own judgment call). Say plainly which file(s) were removed without the message explaining why. Use the same plain, unalarmed tone as any other flagged item: this is a routine traceability gap worth a developer's eyes, not a sign of anything more serious, so don't editorialize about intent or motive you don't have evidence for.
12. If the diff bundles clearly unrelated content types together (for example, a code fix alongside an unrelated document, article, or write-up that is not part of implementing that fix), flag it. Being about the same underlying issue does not by itself make something "part of implementing the fix": a full write-up, postmortem article, or blog-style post explaining the incident for an audience beyond the immediate fix (a LinkedIn draft, a shareable article, anything written to be published or read outside this codebase) still counts as unrelated content bundled in, even when it covers the exact same bug the rest of the diff fixes. That is different from the routine engineering documentation this repository's commits normally carry alongside a fix: a test file, a short changelog-style note, or the routine tracking-log/status-doc updates. Only that narrower, routine kind is exempt; a standalone article or write-up is not, regardless of topic overlap. When rule 12 applies, status must be "Flagged", same plain, unalarmed tone as any other flagged item, not an elevated concern: work something like "this commit bundles unrelated content; consider splitting for traceability" into the paragraph.
13. If the commit's own message or diff frames its content as multiple distinct sub-items (for example, a list of things closed or fixed versus things left open), and at least one of those sub-items is explicitly still open, unresolved, or waiting on a human decision, the overall status must be "Pending", even if every other sub-item is complete. Do not average toward the majority state: one explicitly-open sub-item is enough to make the whole commit Pending. This is different from rules 1 to 2's ordinary "not yet tested" case: a single self-contained piece of work that just hasn't been tested yet is still "Code complete", not "Pending", under those rules. Rule 13 only applies when the commit itself frames its own content as several separate items with different completion states, not to a single item awaiting one verification step.
14. overclaim_check is provided when a commit or PR message claims a feature was "added", "introduced", or is "new", and that claim has already been checked against the repository's git history in code, not by you. When detected is true, the named thing already existed before this commit: each entry in overclaims carries a plain_fact string ("Claim says X was added ... but X already appears ... present since commit Y ... it was not newly added here"). This is verified fact, not something for you to re-check against the diff, soften, or explain away. State the plain_fact plainly in the narrative in your own words (what was claimed as added, and the commit it has actually existed since), using the same unalarmed tone as any other flagged item, and set status to "Flagged" (this is also enforced separately in code as a safety net). When detected is false or overclaim_check is absent, it gives you nothing to act on.
15. ui_copy_removal_check is provided when this commit's diff removes a line of text a user would have seen on screen (visible copy inside a UI component - a label, hint, message, or other on-screen text) while the commit message does not mention removing or replacing anything. This has already been determined from the diff in code, not by you. When detected is true, each entry in removals carries the file and the exact text removed, plus a plain_fact string. This is verified fact, not something for you to re-check against the diff, soften, or explain away. State plainly in the narrative which on-screen text was removed and that the commit message frames the work only as an addition or a change, not a removal. Use the same plain, unalarmed tone as any other flagged item: this is a routine traceability gap worth a developer's eyes - the removal may well be intentional (for instance the same information moved into a new element), it simply is not called out - so do not editorialize about intent you cannot see. Set status to "Flagged" (this is also enforced separately in code as a safety net). This rule is specifically about content a user sees on screen; it does not apply to removed code, comments, styles, imports, or renamed identifiers, and it is not the whole-file-deletion case in rule 11. When detected is false or ui_copy_removal_check is absent, it gives you nothing to act on.

You will be given: the commit message, the full diff, the list of files changed, PR metadata if any (treat PR title/description as another claim to check against the diff, not as verified fact; see rule 10 for how to weigh it against this commit's own narrower state), a story_attribution object already computed upstream (you must not override or re-derive story_id yourself), a sweeping_claim_check object (see rule 9), an unexplained_deletions list (see rule 11), an overclaim_check object (see rule 14), and a ui_copy_removal_check object (see rule 15).

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
        "unexplained_deletions": record.get("unexplained_deletions", []),
        "overclaim_check": _overclaim_for_prompt(record),
        "ui_copy_removal_check": _ui_copy_removal_for_prompt(record),
    }
    return json.dumps(payload)


def _overclaim_for_prompt(record):
    """Slim overclaim_check down to what the model needs: whether a
    verified overclaim was found and, if so, the plain facts. The full
    claims_checked breakdown stays in the fetch-layer record, out of the
    prompt."""
    oc = record.get("overclaim_check") or {}
    if not oc.get("detected"):
        return {"detected": False}
    return {
        "detected": True,
        "overclaims": [
            {
                "term": o.get("term"),
                "existed_since": o.get("existed_since"),
                "plain_fact": o.get("plain_fact"),
            }
            for o in oc.get("overclaims", [])
        ],
    }


def _ui_copy_removal_for_prompt(record):
    """Slim ui_copy_removal_check to what the model needs: whether an
    undisclosed on-screen-text removal was found and, if so, the file and
    the exact text. The full record keeps the rest."""
    uc = record.get("ui_copy_removal_check") or {}
    if not uc.get("detected"):
        return {"detected": False}
    return {
        "detected": True,
        "removals": [
            {"file": r.get("file"), "text": r.get("text"), "plain_fact": r.get("plain_fact")}
            for r in uc.get("removals", [])
        ],
    }


def call_claude(system_prompt, user_prompt, timeout=180):
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


def enforce_deterministic_rules(status, narrative, record):
    """Code-level contract enforcement applied to the model's raw output.
    These are the mechanical rules that are not left to the model's
    judgement. Pure, no AI, no network - unit-testable on its own.
    """
    # Hard block: "Tested" is not an available answer for a commit that
    # doesn't touch any real source file, no matter what the model (or the
    # commit message) claims.
    if status == "Tested" and not record.get("touches_app_code", True):
        status = "Code complete"

    # Rule 11 safety net: an unnamed, unexplained file deletion is always
    # Flagged, whether or not the model caught it on its own.
    if record.get("unexplained_deletions") and status != "Flagged":
        status = "Flagged"

    # Rule 14 safety net: a verified overclaim (message says a feature was
    # "added" but git history shows it already existed) is always Flagged.
    # The plain fact is in overclaim_check.overclaims[].plain_fact and the
    # model is told to state it; this override just guarantees the status.
    overclaim_check = record.get("overclaim_check") or {}
    if overclaim_check.get("detected") and status != "Flagged":
        status = "Flagged"

    # Rule 15 safety net: an undisclosed removal of user-visible on-screen
    # text (message never says anything was removed) is always Flagged.
    ui_copy_removal_check = record.get("ui_copy_removal_check") or {}
    if ui_copy_removal_check.get("detected") and status != "Flagged":
        status = "Flagged"

    # Rule 4, enforced in code rather than trusted to the model.
    if status == "Code complete" and FOLLOW_UP_QUESTION.strip() not in narrative:
        narrative = narrative.rstrip() + FOLLOW_UP_QUESTION

    return status, narrative


def generate_status_update(record):
    user_prompt = build_user_prompt(record)
    raw = call_claude(SYSTEM_PROMPT, user_prompt)
    parsed = parse_model_output(raw)

    status, narrative = enforce_deterministic_rules(parsed["status"], parsed["narrative"], record)

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
