# Eval v2: five contract changes, golden-set correction, re-run findings

Five changes went into the pipeline (touches_app_code hard block, sweeping-claim
repo verification, PR merge-time labeling, the Status Consistency Validator,
unexplained-deletion flagging), plus a correction to golden-set entry 14. This
is an honest account of what the re-run against all 23 golden-set entries
actually showed, not just the headline number.

## Pass rate

**14/23**, unchanged from the v1 run. The number is flat, but which 14 match
is substantially different: some targeted disagreements got fixed, and the
run surfaced new problems, some caused by this round's changes and some by
plain model variance run to run.

## The 7 entries asked about specifically

| Entry | Golden | Generated | Match | Why |
|---|---|---|---|---|
| 01 | Code complete | Code complete | **Yes** | PR merge-time labeling (change 3) worked as intended: the model no longer treats the PR's aggregate "verified end-to-end" claim as contradicting this earlier commit's own state. |
| 02 | Pending | Pending | **Yes** | The model's own narrative said the front-end half "still needs" to land; the Status Consistency Validator (change 4) correctly caught that and corrected to Pending. |
| 03 | Pending | Pending | **Yes** | Same mechanism as 01: no more false contradiction between this commit's "not yet device-tested" note and the bundling PR's aggregate claim. |
| 13 | Pending | Flagged | **No** | Different disagreement than before, not fixed. See below. |
| 14 | Flagged | Code complete | **No** | Regressed. The golden label is now correct (updated this round), but this specific re-run of the model didn't independently catch the OTP-claim mismatch it caught on the original run. See below. |
| 17 | Code complete | Pending | **No** | New disagreement, not the same as before. The touches_app_code block did stop it from saying "Tested" (that part worked), but the Status Consistency Validator then mis-fired. See below. |
| 19 | Flagged | Flagged | **Yes** | unexplained_deletions (change 5) caught exactly the case it was built for: the deleted screen file is never named in the commit message. |

**4 of 7 now match (01, 02, 03, 19). 3 still don't (13, 14, 17), for three different reasons below.**

## Root cause: the Status Consistency Validator is negation-blind

This is the most consequential finding. Three previously-correct entries
(04, 17, 18) flipped from matching to not matching, and one already-wrong
entry (15) flipped to a different wrong answer, all for the same reason:
the validator does fixed substring matching with no understanding of
negation. It was asked for as "pure text matching, no AI," and that's
exactly what it does, but the consequence showed up immediately:

- Case 17's model narrative ends with "...no **outstanding** code work."
  The word is there, but negated. The validator doesn't know that and
  flips a correct "Code complete" to "Pending".
- Case 18 ends with "...no indication of any problems needing
  **follow-up**." Same pattern, correct answer flipped to wrong.
- Case 04's narrative organically mentions a project-notes file that
  "point[s] to a **follow-up** review step" - a routine, harmless note, not
  a sign this commit itself is incomplete. Flipped from correct to wrong.
- Case 15 already didn't match (golden Flagged, model said Code complete
  in v1). This run the model got the status right on its own (Flagged),
  though for a claim that turned out to be fabricated, not a real
  unexplained_deletions catch: see the correction below. The validator's
  negated "not a gap needing **follow-up**" match then dragged it down to
  Pending anyway, replacing one wrong answer with a different wrong one.

This isn't a bug in the implementation; it's the direct, predictable result
of a fixed-keyword matcher with no negation handling, which is what was
asked for. Worth deciding explicitly: keep it as a blunt instrument (accept
these false positives as the cost of catching real ones like case 02), or
add a narrow negation guard (e.g. skip a match if "no", "not", "nothing",
or "n't" appears within a few words before it). I did not make that call
unilaterally since it changes behavior beyond what was specified.

## Root cause: case 14 didn't reproduce

The original golden-set correction for entry 14 was based on the model
correctly catching a real mismatch on the original run: the PR claimed OTP
resend was "added," but the diff only lowered an already-existing cooldown
timer. That reasoning doesn't require any of this round's five changes to
work; it depends entirely on rule 3 (compare claims to diff) from the
original contract.

On this re-run, on a 28-commit bundled merge, the model's narrative doesn't
mention that specific claim at all, and lands on "Code complete." This is
model variance, not a regression caused by the five changes; nothing new
suppresses that check. But it's worth flagging plainly: the golden-set
correction is right (the earlier catch was real and verifiable by hand),
and the model doesn't reliably reproduce it run to run on a case this
complex. A single eval run's "pass" on a hard case isn't a guarantee the
next run passes too.

## Root cause: case 13's disagreement changed shape

v1: golden Pending, model said Code complete despite naming the open items
in its own narrative (a clean self-contradiction).
v2: golden Pending, model said Flagged, because it independently checked a
"Six Agents" -> "Eight Agents" wording-fix claim against the current repo
and found the stale phrase still exists elsewhere (in an unrelated file
quoting the old heading for audit purposes, a false-positive of the
sweeping-claim-style check the model appears to be applying on its own
initiative, not something change 2 triggered mechanically since no
sweeping keyword from the fixed list matched this commit's message).

None of the five changes directly address the actual documented gap here
(disagreements.md's original finding: "no rule for partial/split
completion" - two of four items still open should roll up to Pending).
That gap is still open; this round didn't attempt to close it.

## One new catch, confirmed and corrected; one claim that turned out false

- **Case 11**: unexplained_deletions correctly caught a real, previously
  unflagged issue. This commit deletes an old hook script
  (`check-agent-declared.sh`, confirmed via `git show --name-status`) and
  the commit message is title-only with no body, never mentioning the
  removal. The golden label (Code complete) predated this feature and
  didn't account for it. Golden-set entry 11 has been corrected to
  Flagged, same process as entry 14.
- **Case 15, corrected**: an earlier version of this document claimed
  unexplained_deletions had also fired here, on a "second, independent"
  deletion inside that commit's diff. That was wrong, and it's worth
  saying plainly why: I read the model's own narrative ("this commit's
  message doesn't explain why it also deletes historical content") and
  reported it as a confirmed finding without checking it against the
  actual diff first. `git show --name-status` on this commit shows two
  modified files and zero deletions. unexplained_deletions itself computed
  an empty list for this record, exactly correctly; the model asserted a
  deletion that never happened, and I passed that assertion along
  uncritically instead of verifying it. That's precisely the failure mode
  this whole project exists to catch, and it slipped through the review of
  this project's own eval output. Entry 15's golden status is unaffected
  (it was already Flagged, for the real "no longer appears" mismatch it
  was written around), so no golden-set correction was needed there, but
  the false claim itself is worth recording: a "Flagged" status can still
  carry a partly-fabricated justification underneath it, and status-only
  comparison against a golden label won't catch that. Verifying the
  reasoning, not just the status word, is a real gap in how this eval
  harness checks itself.

## What worked cleanly, no caveats

- **touches_app_code hard block**: did its job everywhere it applied.
  Case 12, a real source-code fix (a shell script) with an actual
  described verification step, correctly stayed eligible for "Tested"
  since it does touch real source; case 17 and 13, docs/log-only commits,
  correctly never got "Tested" as an option.
- **PR merge-time labeling**: cases 01, 03, and 08 all show the model
  explicitly reasoning about "this commit's own point in time" versus
  "the PR's combined state at merge time" in its own words, unprompted by
  anything except the new contract rule.
- **Sweeping-claim verification**: didn't fire on any of these 23 (the
  one real-world case it was built for lives in a diff's log content, not
  the commit message itself, which is outside what was asked for), but
  the detection and repo-grep mechanics were unit-tested independently and
  work correctly.

## Also worth noting

One run hit a transient JSON-parsing failure on the model's raw output
(case 11's first attempt). A retry succeeded. Not something the five
changes caused directly, but a reminder that a single eval pass includes
some amount of raw API/parsing flakiness on top of genuine reasoning
variance, separate from the negation-blindness and model-variance issues
above.
