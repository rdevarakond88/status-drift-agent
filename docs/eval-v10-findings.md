# Eval v10: the validator's "is this a real problem" check is unreliable by construction

Built while assembling the full 23-entry Drift Trace dashboard (2026-09-17).
Not a fetch-layer or golden-set change — this documents a validator finding
surfaced by running all 23 entries fresh, with the 6 entries known to have
historical variance (01, 03, 06, 09, 15, 17) run 3x independently each to
separate real misses from one-off model-sampling noise.

## What happened

21/23 matched golden. Two misses, unrelated to each other:

- **Entry 22** (synthetic): commit claims "QA verified" with no test files
  changed and no CI run linked. None of the four deterministic checks
  (`sweeping_claim_check`, `overclaim_check`, `ui_copy_removal_check`,
  `unexplained_deletions`) are built to catch an unverifiable process
  claim like this — they catch absence claims, prior-existence claims,
  and undisclosed removals, not "trust me, QA passed." The model took the
  claim at face value and returned `Tested`. A real, distinct gap with no
  check built for it yet. Not investigated further this session.

- **Entry 03**: the model's raw answer was `Code complete` in all 3
  independent runs — correct, matches golden. `status_consistency_validator`
  downgraded it to `Pending` in **2 of the 3 runs**, on the trigger words
  "outstanding" / "handed off" appearing in the model's own explanation
  that on-device testing hadn't happened yet — an already-disclosed,
  expected next step per rule 2, not a contradiction. Same failure shape
  as golden entry 01's earlier miss (2026-09-09 snapshot, also triggered
  by "outstanding").

## Why entry 03 flipped 2 of 3 times: traced, not guessed

Ran `_is_negated` / `_is_verification_context` / `_is_hedged_alternative`
directly against all three runs' real narratives rather than eyeballing
word counts. Exact result:

- **Run A (wrongly downgraded):** "handed off" had no verification word
  (`tested`, `device`, etc.) within the 5-word window on either side in
  that run's sentence, so nothing suppressed it. "outstanding" sat right
  next to the word "tested" — but the model wrote it as `'tested'` with
  quote marks, and `WORD_PATTERN` (`[a-z']+`) tokenizes the quoted form
  as `'tested'`, not `tested`. `VERIFICATION_WORDS` only contains the bare
  word, so the set-membership check silently missed it. The carve-out
  didn't decide this case was different — it just failed to recognize
  the word because of a quote mark.
- **Run B (wrongly downgraded):** "outstanding" sat 7 words from the
  nearest verification word ("device"), one word past the 5-word
  `VERIFICATION_CONTEXT_WINDOW_WORDS` limit.
- **Run C (correct):** both trigger words happened to land within the
  window of a verification word in that run's specific phrasing
  ("verification step is still openly outstanding," "handed off to
  whoever does that device testing"), so both were correctly suppressed.

All three runs describe the exact same fact (code done, device test
still pending). The only thing that differed was how many words the
model happened to put between two ideas, and whether it quoted one word.

## Why this isn't a "widen the window" fix

This carve-out (and the negation and hedge-alternative carve-outs next to
it) is trying to answer a meaning-based question — does this sentence
report genuine incomplete work, or name a routine, already-expected
pending-verification step — using literal word-distance and exact-string
matching over freshly-generated prose. That's structurally different from
the other three checks: `sweeping_claim_check` / `overclaim_check` /
`ui_copy_removal_check` each check an objective, mechanical fact against
the repo (does this text still exist, did this already exist before, was
this line removed) — a grep/diff question with one correct answer. This
validator's job is a judgment call about intent, and intent has no
word-distance signature to approximate. Widening 5 to 8 (as the negation
window already was, once, per its own code comment) would catch this
session's specific miss and leave the next differently-worded one
uncaught — the model writes a new sentence every call, in effectively
unlimited phrasings, and the carve-out is a fixed, hand-tuned list
chasing all of them. Three separate carve-outs already exist in this
file (negation, verification-context, hedge-alternative), each added in
response to one specific sentence that slipped through. This session
found a fourth gap in an existing one.

## Not as bad as it sounds: the failure is one-directional

`validate_status` can only ever correct a status *to* `"Pending"` — the
code path is `if matched and status != "Pending": return "Pending",
matched`, otherwise the status passes through unchanged. It can never
produce `"Code complete"` or clear a `"Flagged"`. So this specific bug
class can only make the pipeline *more* cautious than the model's own
read (an unnecessary "still needs follow-up" flag shown to the user),
never less. It cannot cause the pipeline to silently present something as
done when it isn't. The failure is visible and safe-direction, not
misleading.

## Open decision for next session

Not fixed. Two live, reproduced instances now (entry 01 historically,
entry 03 this session) of the same shape. Worth deciding whether this
class of judgment — "does the narrative's meaning match its claimed
status" — should be asked of the model itself (a self-consistency check,
new AI call, new cost, different failure modes) rather than continuing to
patch individual word-distance carve-outs, or left as a documented,
known, safe-direction soft spot. No decision made; flagging for the
architect to weigh cost vs. accuracy on this specific tradeoff.
