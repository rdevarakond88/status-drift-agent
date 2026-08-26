# Eval v3: bundling-hygiene and partial-completion rules

Two new prompt-contract rules went in this round, targeting golden-set
entries 12 (bundling hygiene) and 13 (partial completion). This documents
what actually happened on re-run, not just the headline number.

## Pass rate

**18/23**, the same headline number as v2.1, but not because nothing
changed: rule 12 fixed case 12 (a real fix), while case 04 newly regressed
for an unrelated, pre-existing reason (see below). One fix, one new miss,
net flat.

## Rule 12 (bundling hygiene): worked, after a false start

First draft's carve-out for "routine documentation alongside a fix" was
too permissive. A smoke test before the full run showed the model
exempting a file literally named `linkedin-article-hook-governance-
deadlock.md` from the flag, reasoning it was "part of explaining this fix"
since it covered the same bug. Tightened the rule to make clear that a
standalone write-up meant for an audience outside the codebase (an
article, a blog-style post) doesn't get exempted by topic overlap alone,
distinct from the actually-routine stuff (test files, changelog notes,
tracking-log updates). Re-tested and re-ran: the model now explicitly
calls out the bundled article and flags it, matching golden. Case 12 now
matches for the first time across all runs.

## Rule 13 (partial completion): reasoning fired, verdict didn't land where expected

This is the more interesting result. The model's narrative for case 13
explicitly invokes the rule in its own words: "the commit's own tracking
notes explicitly list several items ... as still open and waiting on a
human decision, which by itself would normally hold this at a
not-yet-finished state rather than a clean 'done.'" That's rule 13 working
exactly as intended, in isolation.

But the final status is "Flagged," not "Pending." The same narrative also
independently re-verifies an unrelated claim on its own initiative (that a
stale "Six Agents" header was fully corrected) and finds a residual
mention of the old phrase elsewhere in the same tracking document, in a
historical section describing the old finding, not a live claim. This is
the same self-initiated verification behavior already documented for this
entry in the v2 findings (a check the model runs on its own, not driven by
sweeping_claim_check, since "Six Agents" isn't in the fixed keyword list).
The model then treats that finding as a rule-3 mismatch and escalates past
Pending straight to Flagged, since nothing in the contract says which of
the two should win when both apply to the same commit.

Case 13 still doesn't match golden (which wants Pending). Not fixed, but
diagnosed precisely: rules 3 and 13 can both fire on the same commit, and
there's no stated precedence between them. Adding rule-precedence guidance
wasn't part of what was asked for this round, so it wasn't added
unilaterally; noting it here as a follow-up worth deciding explicitly
rather than guessing.

## New regression: case 04, unrelated to rules 12/13

Case 04 flipped from matching (Code complete) to not matching (Pending).
The model's own raw status was correctly "Code complete": its narrative
says plainly "this should be treated as code-complete but not yet tested,"
which is exactly rule 2's default case (a single self-contained mockup,
nothing claims testing was done, no reason to escalate). Rule 13 doesn't
apply here; there's no multi-item framing in this commit.

The regression happened downstream, in the Status Consistency Validator.
"not yet" is one of its five fixed trigger phrases, and "not yet tested"
is an extremely common, contractually-intentional phrase under rule 2 (it
is the standard way the model is expected to describe a mockup or
unverified change that should still read as Code complete, not Pending).
The validator has no way to distinguish "not yet tested, therefore
Pending" from "not yet tested, and that's fine, still Code complete under
rule 2" - it just matches the substring. This is a pre-existing gap in the
validator's fixed phrase list, not something rules 12 or 13 introduced; it
simply hadn't been triggered by this specific phrasing on a matching entry
before. Worth deciding in a future round: either drop "not yet" from the
trigger list (rule 2 already covers plain not-yet-tested cases
correctly), or add a rule-2-aware exception the way the negation guard
does. Not fixed here since it wasn't part of what this round asked for.

## Confirmed unaffected: cases 02 and 17

Both were specifically flagged as at-risk given their shape (02 is a
real, legitimate Pending case; 17 was the touches_app_code test case).
Both still match after this round:

- **02**: still Pending, still correct. The Status Consistency Validator
  caught different trigger phrases this run ("outstanding", "handed off")
  than the last run ("still needs"), model phrasing varies, but the
  outcome held.
- **17**: still Code complete, still correct. No multi-item framing in
  this commit for rule 13 to misfire on, and touches_app_code correctly
  keeps "Tested" off the table.

## Still open, unrelated to this round

Cases 14, 15, and 22 remain mismatched for the same reasons documented in
`docs/eval-v2-findings.md`: model variance on case 14's complex bundled
commit, sweeping-claim verification's scope limit on case 15 (the claim
lives in diff/log content, not the commit message), and rule 3's
skepticism toward an unverifiable "QA verified" claim not holding on case
22. None of this round's changes targeted any of the three.
