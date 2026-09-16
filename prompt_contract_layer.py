#!/usr/bin/env python3
"""Layer 2 of status-translation-agent: turns a fetch-layer commit record into
a plain-language status update via an actual AI call. Enforces the locked
rules deterministically wherever the rule is mechanical (allowed status
values, the Code-complete follow-up question, completion-% suppression);
leaves only the judgment calls (claim-vs-diff comparison, tone, story-context
reasoning) to the model.
"""

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import langfuse_client

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
9. sweeping_claim_check is provided when the commit message — or a status/verification claim in the commit's own newly-added diff lines (e.g. a "Last Updated" note or tracking-log entry the commit writes) — uses sweeping language ("anywhere", "everywhere", "no longer exists", "no longer appears", "completely", etc) about a specific quoted piece of text. When detected is true, its verifications list already contains the result of actually searching the repository for that text (excluding the commit's own newly-added lines, so the commit describing its own fix is not counted against it): this is verified fact, not something for you to infer or re-check from the diff alone. If any verification shows claim_holds as false (the text is still found somewhere, listed in still_found_at), treat that as a real, evidenced mismatch under rule 3 and reflect it plainly in the narrative and status - status must be "Flagged" (this is also enforced separately in code as a safety net, but write the narrative as if it's your own judgment call). If verifications is empty (nothing quoted to check, or nothing matched), sweeping_claim_check gives you nothing extra to act on.
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
    start_iso = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(
        ["claude", "-p", "--system-prompt", system_prompt, "--output-format", "json"],
        input=user_prompt, capture_output=True, text=True, timeout=timeout,
    )
    end_iso = datetime.now(timezone.utc).isoformat()

    if result.returncode != 0:
        error = result.stderr.strip()
        _trace_live_call(system_prompt, user_prompt, start_iso, end_iso, None, None, error)
        raise RuntimeError(f"claude -p failed: {error}")

    # --output-format json wraps the model's raw {status, narrative} text in
    # an envelope carrying usage/model/session_id - unwrap it, but return
    # exactly the same raw text call_claude always returned so callers
    # (parse_model_output) are unaffected. Requested only so live tracing can
    # capture the same usage/model/request-id richness the historical import
    # pulled from Claude Code's own session logs.
    try:
        envelope = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        _trace_live_call(system_prompt, user_prompt, start_iso, end_iso, None, None,
                          f"claude -p --output-format json returned non-JSON stdout: {e}")
        raise RuntimeError(
            f"claude -p --output-format json returned non-JSON stdout: {result.stdout[:200]!r}"
        ) from e
    output_text = envelope.get("result", "").strip()
    _trace_live_call(system_prompt, user_prompt, start_iso, end_iso, envelope, output_text, None)
    return output_text


# ── JSON-parsing robustness ─────────────────────────────────────────────
#
# The model's raw {status, narrative} output occasionally fails strict
# json.loads. This is NOT a general JSON fixer - it repairs exactly four
# malformations found by direct inspection of 7 real historical claude -p
# outputs (session logs, 2026-08-25 through 2026-09-13, out of 489 total
# calls): the model believes it produced valid output every time
# (stop_reason: end_turn on all 7), it's a formatting slip, not a cutoff.
#
#   1. a Unicode curly/smart quote ("Tested", ' vs "Tested", ') used as a
#      string delimiter instead of a straight ASCII quote (1 case)
#   2. a trailing comma right before the closing brace: ..."}, }" (2 cases)
#   3. an unescaped literal " inside the narrative text - quoting a short
#      phrase inline ("...its \"verified end-to-end\" claim...") without
#      escaping it - which prematurely closes the JSON string (3 cases)
#   4. extra content after a complete, valid JSON object: the model kept
#      talking (or added a stray extra key) after the real "}" (1 case)
#
# Anything outside these four patterns is left alone; parse_model_output
# re-raises the original json.loads error rather than guessing further.

_CURLY_QUOTE_TABLE = str.maketrans({
    "“": '"', "”": '"',  # “ ”
    "‘": "'", "’": "'",  # ‘ ’
})

# The four allowed status words, used both to validate and - for the
# repair path - to locate the status value without needing the rest of
# the object to be well-formed.
_STATUS_VALUE_RE = re.compile(
    r'"status"\s*:\s*"(' + "|".join(re.escape(s) for s in
        ("Code complete", "Tested", "Pending", "Flagged")) + r')"'
)
_NARRATIVE_START_RE = re.compile(r'"narrative"\s*:\s*"')
# The real closing delimiter: a '"', then either the closing '}' straight
# away, or a stray trailing comma (malformation #2) before it, or - seen in
# one real case combining #3 with an extra stray key - one or more extra
# simple "key": value pairs before it. Anchored to the END of the text.
# Anchoring to the end - not the first quote found after "narrative": " -
# is what lets this skip past an unescaped internal quote used earlier as
# inline content (malformation #3): that quote is never immediately
# followed by this whole tail pattern through end-of-string, only the real
# closing one is.
_TRAILING_SIMPLE_PAIR = r',\s*"[^"\\]*"\s*:\s*(?:"[^"\\]*"|null|true|false|-?\d+(?:\.\d+)?)'
_NARRATIVE_END_RE = re.compile(r'"(?:' + _TRAILING_SIMPLE_PAIR + r')*\s*,?\s*\}\s*\Z')


def _repair_model_json(text):
    """Best-effort repair for the four evidenced malformations above.
    Returns a clean JSON string on success, or None if the text doesn't
    match any of them - never raises, never fabricates a result."""
    t = text.translate(_CURLY_QUOTE_TABLE)  # malformation #1

    # Cheap path first: maybe normalizing quotes was enough, or the object
    # itself is already well-formed and the problem is purely extra
    # trailing content after it (malformation #4) - raw_decode parses one
    # complete value from the start and ignores anything left over.
    try:
        obj, _end = json.JSONDecoder().raw_decode(t)
        if isinstance(obj, dict) and "status" in obj and "narrative" in obj:
            return json.dumps(obj)
    except json.JSONDecodeError:
        pass

    # Malformations #2 / #3: re-extract status and narrative directly by
    # locating their boundaries in the text, rather than trying to patch
    # the string in place - the stray delimiter itself makes position-based
    # patching unreliable. Re-serializing the extracted narrative with
    # json.dumps() correctly (re-)escapes anything inside it; nothing here
    # depends on the original internal escaping being correct.
    m_status = _STATUS_VALUE_RE.search(t)
    m_start = _NARRATIVE_START_RE.search(t)
    if not (m_status and m_start):
        return None
    m_end = _NARRATIVE_END_RE.search(t)
    if not m_end or m_end.start() < m_start.end():
        return None
    narrative = t[m_start.end():m_end.start()]
    return json.dumps({"status": m_status.group(1), "narrative": narrative})


def parse_model_output(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        repaired = _repair_model_json(text)
        if repaired is None:
            raise e
        parsed = json.loads(repaired)
    if "status" not in parsed or "narrative" not in parsed:
        raise ValueError(f"model output missing required keys: {parsed}")
    if parsed["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"model returned an out-of-contract status: {parsed['status']!r}")
    return parsed


# ── live Langfuse tracing ────────────────────────────────────────────────
#
# Best-effort only: a Langfuse push never raises and never blocks the
# pipeline - if the local Langfuse stack isn't running, or credentials
# aren't configured (langfuse_client.load_credentials() returns None),
# tracing is silently skipped. See docs/session-state.md for the historical
# backfill this mirrors (import_historical_traces.py).

_SESSION_LOG_DIR = os.path.expanduser(
    "~/.claude/projects/-home-rdeva-status-translation-agent"
)


def _classify_raw_output(text):
    if not text:
        return "no-response"
    try:
        json.loads(text)
        return "clean"
    except json.JSONDecodeError:
        pass
    try:
        parse_model_output(text)
        return "json-repaired"
    except Exception:
        return "json-parse-failure"


def _read_thinking_and_request_id(session_id):
    """claude -p's --output-format json envelope carries usage/model but not
    the thinking block or requestId - those only live in the session log
    Claude Code itself writes for the call, named exactly <session_id>.jsonl
    in this project's own log directory. Best-effort: returns (None, None)
    if the file isn't there or doesn't parse."""
    path = os.path.join(_SESSION_LOG_DIR, f"{session_id}.jsonl")
    if not os.path.exists(path):
        return None, None
    assistant_records = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "assistant":
                    assistant_records.append(d)
    except OSError:
        return None, None
    if not assistant_records:
        return None, None
    last_request_id = assistant_records[-1].get("requestId")
    group = [a for a in assistant_records if a.get("requestId") == last_request_id]
    thinking = "\n".join(
        b.get("thinking", "")
        for a in group
        for b in a.get("message", {}).get("content", [])
        if b.get("type") == "thinking"
    )
    return thinking, last_request_id


def _trace_live_call(system_prompt, user_prompt, start_iso, end_iso, envelope, output_text, error):
    creds = langfuse_client.load_credentials()
    if creds is None:
        return

    try:
        trace_input = json.loads(user_prompt)
    except (json.JSONDecodeError, TypeError):
        trace_input = user_prompt

    parse_class = "error" if error else _classify_raw_output(output_text)
    session_id = envelope.get("session_id") if envelope else None
    thinking_text, request_id = _read_thinking_and_request_id(session_id) if session_id else (None, None)

    metadata = {
        "session_id": session_id,
        "request_id": request_id,
        "stop_reason": envelope.get("stop_reason") if envelope else None,
        "total_cost_usd": envelope.get("total_cost_usd") if envelope else None,
        "parse_class": parse_class,
        "error": error,
    }

    trace_id = str(uuid.uuid4())
    events = [{
        "id": str(uuid.uuid4()),
        "type": "trace-create",
        "timestamp": start_iso,
        "body": {
            "id": trace_id,
            "timestamp": start_iso,
            "name": "generate_status_update",
            "input": trace_input,
            "output": output_text,
            "metadata": metadata,
            "tags": ["live", f"parse:{parse_class}"],
        },
    }]

    usage = envelope.get("usage") if envelope else None
    events.append({
        "id": str(uuid.uuid4()),
        "type": "generation-create",
        "timestamp": start_iso,
        "body": {
            "id": f"{trace_id}-gen",
            "traceId": trace_id,
            "name": "call_claude",
            "startTime": start_iso,
            "endTime": end_iso,
            "model": "claude-sonnet-5",
            "input": {"system_prompt": system_prompt, "user_prompt": trace_input},
            "output": output_text,
            "usageDetails": langfuse_client.usage_details(usage),
            "metadata": {**metadata, "thinking": thinking_text},
            "level": "ERROR" if error else "DEFAULT",
            "statusMessage": error or parse_class,
        },
    })

    try:
        langfuse_client.push_batch(events, creds, timeout=5)
    except Exception as e:
        print(f"[langfuse] live trace push failed (non-fatal): {e}", file=sys.stderr)


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

    # Rule 9 safety net: a sweeping claim that a repo-wide search has
    # already, verifiably disproved is always Flagged. `detected` alone
    # is not enough to fire this - unlike overclaim_check/ui_copy_removal_check,
    # a sweeping claim can be detected and still hold (golden entry 13:
    # "Six Agents" is checked and comes back claim_holds True, correctly
    # not Flagged). Only an actual claim_holds: False verification - the
    # text is still found somewhere, per still_found_at - is the verified
    # fact this overrides on.
    sweeping_claim_check = record.get("sweeping_claim_check") or {}
    if (
        any(v.get("claim_holds") is False for v in sweeping_claim_check.get("verifications", []))
        and status != "Flagged"
    ):
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
