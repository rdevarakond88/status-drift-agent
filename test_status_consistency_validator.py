#!/usr/bin/env python3
"""Permanent unit tests for status_consistency_validator.validate_status().

Pure text-matching checks. No AI call, no pipeline, no network, no golden
set. Runs in well under a second.

Purpose: confirm the validator itself is sound in isolation BEFORE spending
23 model calls on the full golden-set pipeline eval. If this file fails,
the validator is broken and there is no point running the pipeline yet.

    python3 test_status_consistency_validator.py

Exit 0 = all pass. Exit 1 = one or more failures.

Two groups, matching how the validator is supposed to behave:

  NEVER_TRIGGER  - narrative + incoming status where validate_status must
                   leave the status untouched and report no matched
                   phrases. Includes the real regression that broke
                   case 04 ("code-complete but not yet tested"), the
                   negation-guard cases, and the follow-up boilerplate.

  MUST_TRIGGER   - narrative + a non-"Pending" incoming status where
                   validate_status must rewrite the status to "Pending"
                   and report at least the expected trigger phrase.

Add a case here whenever a real narrative slips through wrong, so the
fix stays fixed.

Verification-context carve-out (added after cases 01 and 06 broke the
same way case 04 had): a trigger phrase with a verification word
("tested", "QA", "verification", "review", "device", ...) within ~5 words
on either side is a routine pending-verification mention, not genuine
incompleteness, and must NOT trigger. The exact real sentences that broke
are pinned below as CASE_01_/CASE_04_/CASE_06_NARRATIVE_AS_GENERATED.
"""

import sys

from prompt_contract_layer import FOLLOW_UP_QUESTION
from status_consistency_validator import validate_status


# The exact case 04 narrative as generated in the eval run that regressed
# (eval_output/results.jsonl, golden_file 04.json). Before the fix, the
# bare "not yet" trigger matched "not yet tested" in the fourth sentence
# and flipped a correct "Code complete" to "Pending". It must not.
CASE_04_NARRATIVE_AS_GENERATED = (
    "This commit adds a new mockup screen that lets a doctor look up a patient by "
    "mobile number as the starting point for requesting cross-provider access to that "
    "patient's records, and it covers three visual states: an idle number-entry screen, "
    "a 'found' screen showing the patient's details with a request-consent button, and "
    "a 'not found' screen offering to register the patient or try again. The new screen "
    "is wired into the app's navigation as expected, and a small developer-only shortcut "
    "was added to the existing patient-search screen so this new screen is easy to reach "
    "for review; the diff supports both of these claims. This work is tracked under story "
    "D7, so no guessing was needed to attribute it. The commit message is upfront that "
    "this is a mockup using hardcoded sample data rather than a real backend lookup, and "
    "neither the message nor the diff claims that any testing, automated or on-device, "
    "has actually been performed, so this should be treated as code-complete but not yet "
    "tested; the project's own tracking notes agree, listing the next step as a "
    "persona-based design review rather than further coding or testing. This commit is "
    "bundled into a larger pull request whose overall description mentions broader device "
    "verification, but that description reflects everything included in that pull request "
    "as of when it was merged, not this specific mockup screen, so it is not being "
    "treated as a conflicting claim here. Follow-up for the developer: when/how will this "
    "be tested, and what's the ETA?"
)


# The exact case 01 narrative from the last eval run (eval_output/results.jsonl,
# golden_file 01.json). "outstanding" matched in "that verification is still
# outstanding" and flipped a correct "Code complete" to "Pending". The word
# "verification" sits 4 words before the match, so the verification-context
# carve-out must now suppress it.
CASE_01_NARRATIVE_AS_GENERATED = (
    "This commit does exactly what its message says: it removes a hardcoded web "
    "address in the authentication file (src/api/auth.ts) that pointed at the retired "
    "Render.com server, and instead pulls in the shared API_BASE_URL setting from the "
    "app's central API client. The diff confirms all four sign-in-related functions "
    "named in the message (send one-time passcode, verify passcode, verify patient "
    "passcode, and refresh access token) were updated to use that shared value, so "
    "login traffic should now follow whatever address the demo startup script "
    "configures (the cloudflared tunnel). The only other changed file is the project's "
    "session tracking document, which is a routine status-log update and not unrelated "
    "content. The change is self-contained and internally consistent with its claim, so "
    "it reads as code complete. It is not marked as tested: the commit message does not "
    "claim any testing was run, and the updated tracking document explicitly routes the "
    "next step to a device tester to confirm one-time-passcode login actually works on "
    "a phone, so that verification is still outstanding. The commit is attributed to "
    "story D1, which matches. The pull request that later bundled this work describes "
    "end-to-end device verification, but per the rules that reflects the combined state "
    "at merge time and does not contradict this single commit still needing its own "
    "on-device check; I only read the message and diff and did not run anything myself. "
    "Follow-up for the developer: when/how will this be tested, and what's the ETA?"
)


# The exact case 06 narrative from the last eval run (eval_output/results.jsonl,
# golden_file 06.json). "still needs" matched in "still needs a visual QA pass"
# and flipped a correct "Code complete" to "Pending". "QA" sits 3 words after
# the match, so the verification-context carve-out must now suppress it.
CASE_06_NARRATIVE_AS_GENERATED = (
    "This commit adjusts the visual styling of the error and \"not found\" states on "
    "the doctor's consent lookup screen so they look less alarming: instead of a "
    "red-tinted fill, the affected elements now use a plain white/surface background "
    "with a red border and red text, and the \"not found\" card's border is made "
    "slightly thicker while its warning icon switches from a solid red circle to an "
    "outlined one with red text. The changes in the diff line up with what the commit "
    "message describes, and the work is limited to that one screen file with no other "
    "scope. This is tied to story D7, which was correctly attributed from the commit "
    "message. There is no indication in the message or the diff that this change was "
    "actually run or visually checked on a device or simulator, so testing cannot be "
    "assumed from the data provided; the pull request it later merged under states "
    "device verification was done at the PR level, but that speaks to the bundle at "
    "merge time rather than this individual styling commit. No files were deleted and "
    "no unrelated material is bundled in, so treating this as finished code that still "
    "needs a visual QA pass is the right read. Follow-up for the developer: when/how "
    "will this be tested, and what's the ETA?"
)


# (name, incoming_status, narrative)
NEVER_TRIGGER = [
    (
        "case_04_exact_as_generated",
        "Code complete",
        CASE_04_NARRATIVE_AS_GENERATED,
    ),
    (
        # Real sentence that broke: "outstanding" next to "verification".
        "case_01_exact_as_generated",
        "Code complete",
        CASE_01_NARRATIVE_AS_GENERATED,
    ),
    (
        # Real sentence that broke: "still needs" next to "QA".
        "case_06_exact_as_generated",
        "Code complete",
        CASE_06_NARRATIVE_AS_GENERATED,
    ),
    (
        # "still outstanding" with a verification word right beside it: a
        # pending device/verification step, which rule 2 keeps at "Code
        # complete". Must be suppressed by the verification-context carve-out.
        "still_outstanding_with_verification_context",
        "Code complete",
        "The implementation is done and the diff is self-consistent; the on-device "
        "testing is still outstanding and is routed to a device tester.",
    ),
    (
        # "still needs" + "QA": a pending QA pass, not unfinished work.
        "still_needs_qa_pass",
        "Code complete",
        "The styling change is complete and matches the commit message; it still needs "
        "a QA pass on a real screen before it ships.",
    ),
    (
        "bare_not_yet_tested_sentence",
        "Code complete",
        "This should be treated as code-complete but not yet tested.",
    ),
    (
        "rule_2_untested_mockup",
        "Code complete",
        "A single self-contained mockup; nothing in the message or diff claims testing "
        "was done, so it is not yet tested but still reads as code complete.",
    ),
    (
        "no_outstanding_work",
        "Code complete",
        "There is no outstanding work on this change; the diff matches every claim.",
    ),
    (
        "nothing_left_to_do_here",
        "Code complete",
        "Nothing left to do here. The fix is in and consistent with the commit message.",
    ),
    (
        "not_a_gap_needing_follow_up",
        "Code complete",
        "The message does not name the deleted file, but that is not a gap needing "
        "follow-up given the diff is otherwise self-explanatory.",
    ),
    (
        "negated_not_yet_complete_constructed",
        "Code complete",
        # Constructed: exercises the negation guard against the new
        # "not yet complete" trigger. "nothing" sits inside the lookback
        # window, so the match is suppressed.
        "Every sub-task named in the commit is closed; this leaves nothing that is "
        "not yet complete.",
    ),
    (
        "follow_up_boilerplate_only",
        "Code complete",
        # The Rule-4 follow-up question is appended to every Code-complete
        # result. Its own "Follow-up" wording is stripped before matching
        # and must not, by itself, trigger a correction.
        "Everything in the diff matches the commit's stated claims." + FOLLOW_UP_QUESTION,
    ),
    (
        "already_pending_is_left_alone",
        # A trigger phrase is present, but the incoming status is already
        # "Pending", so there is nothing to correct: validate_status
        # returns the status unchanged with an empty matched list.
        "Pending",
        "The front-end header change still needs to happen before this is usable.",
    ),
]


# (name, incoming_status, narrative, expected_phrase_substring)
MUST_TRIGGER = [
    (
        "still_needs_to_happen",  # the phrasing pattern from case 02's catch
        "Code complete",
        "The backend tunnel swap is done and curl-verified, but the corresponding "
        "front-end header change still needs to happen before the switch is usable "
        "end to end.",
        "still needs",
    ),
    (
        # "outstanding work" with NO verification word nearby: the work
        # itself is unfinished, so this must still flip to "Pending".
        # (Replaces an earlier "one outstanding verification step remains"
        # case -- that phrasing literally describes a pending verification
        # step, which rule 2 keeps at "Code complete", so it belonged in
        # NEVER_TRIGGER, not here.)
        "outstanding_work_no_verification_context",
        "Code complete",
        "The happy path is implemented, but there is still significant outstanding "
        "work on the error-handling branch before this is usable.",
        "outstanding",
    ),
    (
        "handed_off_to_another_agent",  # case 02's other real catch phrase
        "Code complete",
        "The backend half landed here; the matching front-end change is being handed "
        "off to another agent for a future work session.",
        "handed off",
    ),
    (
        "not_yet_complete_new_trigger",
        "Code complete",
        "The screen is wired into navigation, but the data layer behind it is not yet "
        "complete.",
        "not yet complete",
    ),
    (
        "not_yet_done_new_trigger",
        "Code complete",
        "The backend endpoint is in; the matching app-side call is not yet done.",
        "not yet done",
    ),
    (
        "not_yet_finished_new_trigger",
        "Code complete",
        "Migration scripts are written and reviewed, but the rollout is not yet "
        "finished.",
        "not yet finished",
    ),
    (
        "trigger_overrides_flagged_too",
        # The correction is not limited to "Code complete" input: any
        # non-"Pending" status with an unresolved-work phrase becomes
        # "Pending".
        "Flagged",
        "One claim does not hold up against the diff, and separately the app-side "
        "change is being handed off to another agent.",
        "handed off",
    ),
]


def _run():
    failures = []

    for name, status_in, narrative in NEVER_TRIGGER:
        status_out, matched = validate_status(status_in, narrative)
        if status_out != status_in or matched:
            failures.append(
                f"[NEVER_TRIGGER] {name}: expected ({status_in!r}, []) "
                f"got ({status_out!r}, {matched!r})"
            )
        else:
            print(f"  ok   NEVER_TRIGGER  {name}")

    for name, status_in, narrative, expected_phrase in MUST_TRIGGER:
        status_out, matched = validate_status(status_in, narrative)
        if status_out != "Pending" or expected_phrase not in matched:
            failures.append(
                f"[MUST_TRIGGER] {name}: expected ('Pending', [... {expected_phrase!r} ...]) "
                f"got ({status_out!r}, {matched!r})"
            )
        else:
            print(f"  ok   MUST_TRIGGER   {name}  (matched {matched})")

    total = len(NEVER_TRIGGER) + len(MUST_TRIGGER)
    print()
    if failures:
        print(f"FAIL — {len(failures)} of {total} validator unit tests failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS — all {total} validator unit tests passed "
          f"({len(NEVER_TRIGGER)} never-trigger, {len(MUST_TRIGGER)} must-trigger).")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
