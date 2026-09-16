#!/usr/bin/env python3
"""Permanent unit tests for prompt_contract_layer.parse_model_output()'s
JSON-repair pass. No AI, no pipeline, no network.

The 7 cases below are the EXACT raw text `claude -p` returned for 7 real
historical calls that failed strict json.loads, pulled directly from
Claude Code's own session logs
(~/.claude/projects/-home-rdeva-status-translation-agent/*.jsonl,
2026-08-25 through 2026-09-13 - 489 total `claude -p` calls, 480 clean,
1 with no response, these 7 malformed). Not reconstructed, not
paraphrased - the literal bytes the model produced.

    python3 test_parse_model_output.py

Exit 0 = all pass. Exit 1 = one or more failures.

The repair pass handles exactly 4 evidenced malformations - not a general
JSON fixer, see prompt_contract_layer.py's own comment for the full
rationale:
  1. an unescaped literal " inside the narrative, quoting a short phrase
     inline, which prematurely closes the JSON string (3 of the 7 cases)
  2. a trailing comma right before the closing brace (2 of the 7 cases)
  3. a Unicode curly/smart quote used as the closing string delimiter
     instead of a straight ASCII quote (1 of the 7 cases)
  4. extra content after a complete, valid JSON object - either trailing
     prose, or (case 5's variant) an extra simple key-value pair inside
     the object itself (1 of the 7 cases)

A note on a mistake corrected before this was built: an earlier read of
two of these cases, by eyeballing a repr()'d preview, misidentified an
invalid `\\'` escape sequence as the problem. Direct inspection of the raw
bytes (not a repr preview) showed no such backslash ever appears - both
of those cases are plain instances of malformation #2. There is no `\\'`
handling here because it was never a real, evidenced failure mode.
"""

import sys

from prompt_contract_layer import parse_model_output

# expected status: 'Flagged'
CASE_UNESCAPED_QUOTE_1 = '{"status": "Flagged", "narrative": "This commit adds a five-phase hook-based governance system to the medrecord project\'s Claude agent tooling, intended to enforce agent declarations, file-ownership rules, and add session-start context plus an audit trail for traceability, and the diff does line up with that description for the new files added. However, it also deletes the previous agent-declaration script (check-agent-declared.sh) entirely without the commit message ever mentioning that removal, which is a traceability gap worth a developer\'s eyes even though the replacement script (agent-gate.sh) appears to cover the same job. No story or ticket was attached to this commit, but since it\'s a self-contained infrastructure/governance change with a clear purpose in its own message and files, that\'s not itself a problem. On testing: nothing in this commit\'s message or diff claims any of this new hook logic was actually run and verified, and the related pull request\'s own test plan lists reviewing these hook files as a still-open checklist item and explicitly scopes its "verified end-to-end on device" claim to the backend/network changes, not to this governance system, so I have no basis to say this was tested — I only read the message and diff, I did not execute anything myself. Given the unexplained file deletion, this should be flagged for a quick developer check before being considered fully wrapped up."}'

# expected status: 'Code complete'
CASE_UNESCAPED_QUOTE_2 = '{"status": "Code complete", "narrative": "This is a project-management (PM) commit that closes governance backlog item #3, which concerned two conflicting sources of truth for deciding which agent should run next. Rather than writing new code, the commit describes considering two possible fixes and rejecting both after inspection, then replaying the original incident against the existing check logic in a scratch test outside the real project files, along with four additional edge cases, and reports that everything behaved correctly as-is. The diff itself only updates a project-state documentation file and two log/registry files, consistent with the message\'s claim that no code change was made, so there is nothing in the diff that contradicts what the commit says. This commit does not touch any application code, so no testing claim applies here, and it also isn\'t tied to a specific product story, but its purpose is self-contained and clearly explained by its own message and diff (a governance/process decision), so no story attribution was needed. Since the diff supports the message\'s claims and there are no unexplained file deletions, unrelated bundled content, sweeping unverified claims, or feature overclaims, this is best classified as code complete, with the caveat that "complete" here means the review and documentation update are done, not that any application code was written or tested.", "status_final_note": null}'

# expected status: 'Flagged'
CASE_UNESCAPED_QUOTE_3 = '{"status": "Flagged", "narrative": "This infra commit adds a five-phase hook system meant to govern which AI agent can declare a session and edit which files, plus logging and trace-lookup tooling to reconstruct what happened during a session; the diff backs up the described phases (agent declaration gate, file-ownership gate, infra-session scoping, session-start context injection, workflow-report processing, and a trace query script), and no product story was attached to this commit, but that looks fine on its own since the work is a self-contained internal tooling change rather than a feature tied to a user-facing story. The main issue is that this commit deletes an existing file, check-agent-declared.sh (an older version of the agent gate), entirely, and the commit message never mentions this removal, which is a routine traceability gap worth a developer confirming was intentional. Separately, the new code\'s own comments flag that parts of this system are not yet confirmed working — one hook notes its context-injection behavior has a known issue in some versions and needs manual verification, and another notes it won\'t actually fire under the project\'s current session setup — so this should be treated as code that looks complete but has not been shown to work end-to-end; a related pull request\'s claim of having verified things "end-to-end on device" describes the state of that larger, bundled pull request at merge time (which also included separate backend/networking work), not a specific confirmation that this hook system itself was tested, so it doesn\'t resolve that open question."}'

# expected status: 'Flagged'
CASE_TRAILING_COMMA_1 = '{"status": "Flagged", "narrative": "This commit (story D7) adds a small info icon with a toggleable tooltip next to the \'Request Access\' button on the doctor consent lookup screen, explaining that tapping the button sends an SMS verification code to the patient; the button itself keeps its full width and the icon sits in its own tap target, and the diff looks consistent with what the commit message describes for that part of the change. However, the same diff also deletes an existing on-screen hint that used to read \\"An SMS will be sent to the patient\'s registered number for verification,\\" and the commit message doesn\'t mention removing or replacing anything — it\'s framed purely as an addition. That\'s a routine traceability gap worth a developer\'s eyes rather than a sign of a real problem (the same information may simply have moved into the new tooltip card), but it should be called out and confirmed rather than left unstated. No testing is claimed or evidenced in the message or diff, so this couldn\'t be marked as tested regardless; the unexplained text removal is the reason this is being flagged rather than marked simply code complete.", }'

# expected status: 'Code complete'
CASE_TRAILING_COMMA_2 = '{"status": "Code complete", "narrative": "This commit is attributed to story D7 and adds a loading state to the mock Consent Lookup screen: after entering 10 digits, the doctor now taps a new \\"Look Up Patient\\" button, which shows a spinner card for about 1.2 seconds (a simulated delay, not a real network call) before the screen resolves to a found or not-found result; the number keypad locks while the spinner is showing, and the input box gets a dashed blue border during that wait. Comparing the commit message to the diff, every behavior it describes is actually present in the code, and the change stays consistent with this screen\'s existing pattern of being a mockup with no real backend calls, so there\'s no scope mismatch to flag here. The associated pull request covers a much larger, unrelated set of backend and governance work, but per how these commits are meant to be read, that PR\'s testing claims describe the overall PR at merge time and aren\'t a claim about this specific UI mockup commit, so it isn\'t treated as a contradiction. The commit message doesn\'t state that this new loading behavior was actually tried out or verified, so even though the code looks internally consistent and complete, it\'s marked Code complete rather than Tested.", }'

# expected status: 'Tested'
CASE_CURLY_QUOTE = '{"status": "Tested", "narrative": "This commit updates the patient Profile screen\'s styling — adjusting the header\'s vertical padding, background color, and title font size — to match a design spec, and the commit message states that QA has verified the change. The diff itself is limited to these style values, which lines up with the message\'s description of a design-spec update, and there\'s no mismatch between what\'s claimed and what the diff actually shows. No story or ticket is attached to this commit, but since it\'s a small, self-contained visual styling change with a clear purpose, that\'s not a problem worth flagging on its own. Based on the explicit statement in the commit message that QA verified the change, this is being marked as tested, though that reflects the commit\'s own stated claim rather than any independent confirmation on my part.”}'

# expected status: 'Flagged'
CASE_EXTRA_TRAILING_CONTENT = '{"status": "Flagged", "narrative": "This commit reverts an earlier change (referenced as P9, \\"Upcoming Appointments — static mockup\\") and, as expected of a revert, deletes the file src/screens/patient/PatientAppointmentsScreen.tsx entirely, which the diff confirms matches the commit\'s stated intent. However, this is flagged as a routine traceability gap because the commit message does not explicitly name the file being removed, so the deletion isn\'t self-documenting from the message text alone even though it lines up with what a revert of that mockup would be expected to do. A story reference (P9) is attached to this commit, so no story attribution is missing here. Since this change only touches a UI screen file and there is no mention or evidence of testing being performed, this should be treated as code complete rather than tested, and a developer should take a quick look to confirm the deleted file is the correct and only intended removal.", "PLACEHOLDER": ""}\n\nWait, I need to output only the JSON object per the format. Let me correct that.\n\n{"status": "Flagged", "narrative": "This commit reverts an earlier change referenced as story P9, \\"Upcoming Appointments — static mockup,\\" and the diff shows exactly one file, src/screens/patient/PatientAppointmentsScreen.tsx, being deleted in full, which is consistent with reverting a screen that was previously added. This is flagged because that deleted file is not explicitly named in the commit message itself (the message only references the commit hash being reverted), so on its own the message doesn\'t spell out which file is being removed, even though the deletion is consistent with a revert of the appointments mockup work tied to story P9. A story reference is present here, so there is no missing attribution to call out. Because this change only touches a UI screen file and there is no mention of any testing being performed or passed, it should be marked as code complete rather than tested, and it would be worth a quick developer check to confirm this is the intended and only file removed by the revert.'

REAL_CASES = [
    ("unescaped_quote_1", CASE_UNESCAPED_QUOTE_1, "Flagged"),
    ("unescaped_quote_2_plus_extra_key", CASE_UNESCAPED_QUOTE_2, "Code complete"),
    ("unescaped_quote_3", CASE_UNESCAPED_QUOTE_3, "Flagged"),
    ("trailing_comma_1", CASE_TRAILING_COMMA_1, "Flagged"),
    ("trailing_comma_2", CASE_TRAILING_COMMA_2, "Code complete"),
    ("curly_quote", CASE_CURLY_QUOTE, "Tested"),
    ("extra_trailing_content", CASE_EXTRA_TRAILING_CONTENT, "Flagged"),
]


def _check_real_cases():
    failures = []
    for name, raw, expected_status in REAL_CASES:
        try:
            import json
            json.loads(raw)
            failures.append(f"[repro] {name}: plain json.loads unexpectedly succeeded - "
                             f"this case no longer reproduces the original failure")
            continue
        except Exception:
            pass  # confirmed still a real repro of the historical failure

        try:
            result = parse_model_output(raw)
        except Exception as e:
            failures.append(f"[repair] {name}: still fails -> {type(e).__name__}: {e}")
            continue
        if result["status"] != expected_status:
            failures.append(
                f"[repair] {name}: status {result['status']!r}, expected {expected_status!r}"
            )
            continue
        if not result["narrative"] or len(result["narrative"]) < 50:
            failures.append(f"[repair] {name}: narrative missing or suspiciously short: {result['narrative']!r}")
            continue
        print(f"  ok   real-case    {name} -> {result['status']!r} ({len(result['narrative'])} chars)")
    return failures


def _check_clean_json_unaffected():
    failures = []
    clean_cases = [
        ('{"status": "Code complete", "narrative": "A plain, well-formed response."}', "Code complete"),
        ('```json\n{"status": "Flagged", "narrative": "Fenced response, unaffected."}\n```', "Flagged"),
        # a narrative that legitimately quotes something WITH correct escaping must
        # still work - the repair pass must not be the only path that handles quotes.
        ('{"status": "Pending", "narrative": "The message says \\"done\\" but the diff disagrees."}', "Pending"),
        # curly quotes used correctly, INSIDE an otherwise well-formed string, must
        # survive untouched - the repair pass only engages after json.loads fails.
        ('{"status": "Code complete", "narrative": "The doc calls this “feature complete” already."}', "Code complete"),
    ]
    for raw, expected_status in clean_cases:
        result = parse_model_output(raw)
        if result["status"] != expected_status:
            failures.append(f"[clean] {raw[:40]}...: status {result['status']!r}, expected {expected_status!r}")
    if not failures:
        print("  ok   clean         well-formed / fenced / correctly-escaped / stylistic-curly-quote inputs unaffected")
    return failures


def _check_curly_quote_not_applied_when_already_valid():
    # A narrative that correctly uses a curly quote stylistically (not as a
    # delimiter) must come through byte-for-byte unchanged - the repair pass
    # must never even run when json.loads already succeeds.
    raw = '{"status": "Code complete", "narrative": "She called it “done” in the PR."}'
    result = parse_model_output(raw)
    if "“" not in result["narrative"] or "”" not in result["narrative"]:
        return [f"[clean] curly quote used correctly was altered: {result['narrative']!r}"]
    print("  ok   clean         curly quote used correctly inside an already-valid string -> untouched")
    return []


def _check_unrecoverable_garbage_still_raises():
    # Something outside all four evidenced patterns must NOT be silently
    # papered over - the repair pass returns None and parse_model_output
    # must re-raise the original error, not fabricate a result.
    failures = []
    garbage_cases = [
        "not json at all, just prose",
        '{"status": "Flagged"',  # missing narrative key entirely, truncated
        '{"totally_wrong_key": "x"}',  # valid JSON, wrong schema
    ]
    for raw in garbage_cases:
        try:
            result = parse_model_output(raw)
            failures.append(f"[garbage] {raw[:40]!r} unexpectedly parsed as {result!r} instead of raising")
        except Exception:
            pass  # expected
    if not failures:
        print("  ok   garbage       unrecoverable / out-of-schema input still raises, not silently guessed")
    return failures


def _run():
    failures = (
        _check_real_cases()
        + _check_clean_json_unaffected()
        + _check_curly_quote_not_applied_when_already_valid()
        + _check_unrecoverable_garbage_still_raises()
    )
    print()
    if failures:
        print(f"FAIL - {len(failures)} parse_model_output test(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS - all parse_model_output tests passed ({len(REAL_CASES)} real historical cases + clean/garbage guards).")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
