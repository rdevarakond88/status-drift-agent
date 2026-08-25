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
  in v1). This run the model actually got the status right on its own
  (Flagged, for a real unexplained deletion inside that commit that
  unexplained_deletions also caught) - and then the validator's negated
  "not a gap needing **follow-up**" match dragged it down to Pending
  anyway, replacing one wrong answer with a different wrong answer.

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

## Two new catches, not previously flagged at all

Two entries that matched cleanly in v1 turned up genuinely new, real
findings this round, unrelated to anything in the original 9 disagreements:

- **Case 11**: unexplained_deletions correctly caught a real, previously
  unflagged issue. This commit deletes an old hook script
  (`check-agent-declared.sh`, confirmed via `git show`) and never mentions
  the removal anywhere in its message. The golden label (Code complete)
  predates this feature and doesn't account for it. The model's new
  "Flagged" answer looks like the more defensible one; the golden label is
  arguably the one that needs updating, similar to case 14.
- **Case 15**: unexplained_deletions also fired here for a real deletion
  inside that commit's diff (unrelated to the original dead-URL mismatch
  the golden label was written around). It's a second, independent
  confirmation the feature works on real repo history, though the
  Status Consistency Validator's negation-blindness (above) then dragged
  this one's final status to the wrong answer anyway.

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
