# Eval v2: five contract changes, golden-set correction, re-run findings

Five changes went into the pipeline (touches_app_code hard block, sweeping-claim
repo verification, PR merge-time labeling, the Status Consistency Validator,
unexplained-deletion flagging), plus a correction to golden-set entry 14.
A follow-up round then fixed the Status Consistency Validator's
negation-blindness and corrected golden-set entry 11. This is an honest
account of what re-running against all 23 golden-set entries actually
showed at each step, not just the headline numbers.

## Pass rate

First re-run (the five changes only): **14/23**, unchanged from v1 in
headline number, but which 14 matched was substantially different: some
targeted disagreements got fixed, and the run surfaced new problems, some
caused by this round's changes and some by plain model variance run to run.

Second re-run, after fixing the Status Consistency Validator's
negation-blindness and correcting golden-set entry 11 (see below):
**18/23**. Confirmed directly against this run's actual output:

| Entry | Status | Notes |
|---|---|---|
| 04 | Code complete, matches | Not fixed by the negation guard itself (see below); this run's model output simply didn't repeat the ambiguous "follow-up review step" phrasing that caused it to flip last time. Model variance, not the fix. |
| 15 | Code complete, still mismatched (golden Flagged) | The negation fix did its job (no more false "Pending" flip), but the model's own judgment this run also doesn't independently verify the underlying claim the golden label is about. See the correction below: an earlier version of this document wrongly credited unexplained_deletions with catching something here. |
| 17 | Code complete, matches | Negation guard correctly suppressed "no outstanding code work." |
| 18 | Code complete, matches | Negation guard correctly suppressed "no indication of any problems needing follow-up," which needed the widened 8-word lookback (the original 4-5 word suggestion would have missed it: "no" sits 6 words back). |

Case 04 is worth being precise about: the negation fix does not fix it,
because there was never a negation to detect there. Its "follow-up" mention
("point to a follow-up review step") is a harmless, non-negated aside, a
different false-positive shape than 15/17/18. It happened to come out
correct on this run because the model didn't use that phrasing this time,
which is model variance, not something this fix addresses. If that
phrasing comes back on a future run, this entry would mis-flag again.

## The 7 entries asked about specifically

This table is as of the **first** re-run (five changes only, before the
negation fix). It's kept as-is for the historical record; see "Pass rate"
above for what changed after the negation fix and the entry-11 correction.

| Entry | Golden | Generated | Match | Why |
|---|---|---|---|---|
| 01 | Code complete | Code complete | **Yes** | PR merge-time labeling (change 3) worked as intended: the model no longer treats the PR's aggregate "verified end-to-end" claim as contradicting this earlier commit's own state. |
| 02 | Pending | Pending | **Yes** | The model's own narrative said the front-end half "still needs" to land; the Status Consistency Validator (change 4) correctly caught that and corrected to Pending. |
| 03 | Pending | Pending | **Yes** | Same mechanism as 01: no more false contradiction between this commit's "not yet device-tested" note and the bundling PR's aggregate claim. |
| 13 | Pending | Flagged | **No** | Different disagreement than before, not fixed. See below. Still unfixed after the negation fix too; logged as an open item in disagreements.md rather than addressed. |
| 14 | Flagged | Code complete | **No** | Regressed. The golden label is now correct (updated this round), but this specific re-run of the model didn't independently catch the OTP-claim mismatch it caught on the original run. See below. Still doesn't reproduce reliably as of the second re-run either. |
| 17 | Code complete | Pending | **No at this point** | The touches_app_code block did stop it from saying "Tested" (that part worked), but the Status Consistency Validator then mis-fired on negated "outstanding." **Fixed by the negation guard**: matches as of the second re-run. |
| 19 | Flagged | Flagged | **Yes** | unexplained_deletions (change 5) caught exactly the case it was built for: the deleted screen file is never named in the commit message. |

First re-run: 4 of 7 matched (01, 02, 03, 19). After the negation fix:
**5 of 7 match (01, 02, 03, 17, 19). 13 and 14 remain open**, for the
reasons in the sections below (13: a policy gap, not yet an AI-facing
rule; 14: model variance on a complex bundled commit, not a systemic
issue caused by any of the five changes).

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

## Still open, untouched by this round

Two entries mismatch consistently across both re-runs, for reasons none of
the five changes or the negation fix targeted:

- **Case 12** (golden Flagged, generated Tested): the code fix and its
  testing claim both hold up, so "Tested" is a defensible read on its own
  terms. What golden actually flags is a bundling-hygiene issue, an
  unrelated draft write-up bundled into the same commit as the code fix.
  Nothing in this round addresses bundling hygiene (disagreements.md
  takeaway 4, still open).
- **Case 22** (golden Flagged, generated Tested): a synthetic entry
  designed to test whether the model treats a bare "QA verified" claim in
  a commit message as credible with no corroborating evidence (no test
  files changed, no CI run). It shouldn't; rule 3 asks for exactly this
  kind of skepticism. Both re-runs call it "Tested" anyway. Worth a closer
  look in a future session: whether the touches_app_code/sweeping-claim/
  unexplained-deletions additions are diluting the model's adherence to
  the original unverifiable-claim skepticism rule, or whether this is
  independent variance.

## Also worth noting

One run hit a transient JSON-parsing failure on the model's raw output
(case 11's first attempt). A retry succeeded. Not something the five
changes caused directly, but a reminder that a single eval pass includes
some amount of raw API/parsing flakiness on top of genuine reasoning
variance, separate from the negation-blindness and model-variance issues
above.
