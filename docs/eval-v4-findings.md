# Eval v4: the "not yet" bug was a pattern, not a phrase — and a self-consistency-checked run

Two things this round:

1. Generalized the `not yet` fix into a phrase-agnostic carve-out, after
   the same bug showed up again in two more trigger phrases.
2. Ran the golden set with self-consistency checking on the entries with a
   track record of flipping run-to-run, instead of one run per entry.

## The bug was never about the words "not yet"

v3 dropped bare `"not yet"` from the validator's trigger list because it
matched `"not yet tested"` — rule 2's contractually-expected way of
describing an untested-but-complete mockup — and wrongly flipped `Code
complete` → `Pending` (case 04).

The v3 post-fix pipeline run then broke cases 01 and 06 the *exact same
way*, with different words:

| case | phrase in model narrative | validator did | correct answer |
|---|---|---|---|
| 01 | "that verification is still **outstanding**" | `Code complete` → `Pending` | `Code complete` (means "still needs a device test" — rule 2) |
| 06 | "finished code that **still needs** a visual QA pass" | `Code complete` → `Pending` | `Code complete` (means "still needs QA" — rule 2) |

`"outstanding"`, `"still needs"`, and `"not yet"` all have the same two
senses: the *work itself* is unfinished (should trigger) vs. a routine
*pending-verification step* is outstanding (rule 2 keeps at `Code
complete`). Substring matching can't tell them apart. Patching one phrase
at a time just moves the bug to the next phrase.

## The fix: a verification-context carve-out

`status_consistency_validator.py` now has a second suppression rule
alongside the negation guard. A shared list of verification words —
`tested, testing, QA, verification, verified, review, device` — and if any
of them sits within 5 words on either side of *any* trigger phrase
(current or future), the match is suppressed. Bidirectional because the
real collisions land both ways: `"still needs a visual QA pass"` (word
after) and `"verification is still outstanding"` (word before).

Window is 5 words: wide enough for `"verification is still outstanding"`
(4 words back) and `"still needs a visual QA pass"` (3 forward), tight
enough that an unrelated `"...done and curl-verified, but ... still needs
to happen"` (the `verified` token is 8 words back) still correctly
triggers.

Unit suite grew 16 → 20 cases. The four new cases are the exact real
sentences that broke (`case_01_/case_06_narrative_as_generated` pinned
verbatim) plus `still outstanding` + verification context (must not
trigger), `still needs QA` (must not trigger), and `outstanding work`
with no verification context (must still trigger). One old MUST_TRIGGER
case — `"one outstanding verification step remains"` — was moved to
NEVER_TRIGGER, because that phrasing literally *is* a pending-verification
mention and rule 2 keeps it at `Code complete`; it had encoded the old
wrong behavior. All 20 pass, AI-free, ~0.1s.

## Self-consistency run

Instead of one run per entry (v2/v3 showed ~35% of entries flip pass/fail
between two runs of near-identical code — noise larger than the effect
being measured), this run does:

- **3 runs each** for the 8 entries with a flip history: 01, 03, 04, 06,
  09, 13, 14, 22. Majority of 3 is the result. All 3 disagreeing = "no
  consensus, needs human review" rather than a pass/fail.
- **1 run** for entry 15 and the 14 entries that have passed every run so
  far.

39 model calls, 0 errors. Harness: `run_selfconsistency_eval.py`, output
in `eval_output/results-selfconsistency.jsonl` (every run's raw model
status, post-validator status, matched phrases, and narrative).

### Multi-run entries

| entry | golden | run 1 | run 2 | run 3 | outcome | vs golden |
|---|---|---|---|---|---|---|
| 01 | Code complete | Code complete | Code complete | Code complete | 3/3 Code complete | match |
| 03 | Pending | Code complete | Code complete | Code complete | 3/3 Code complete | **miss** |
| 04 | Code complete | Code complete | Code complete | Code complete | 3/3 Code complete | match |
| 06 | Code complete | Code complete | Code complete | Code complete | 3/3 Code complete | match |
| 09 | Code complete | Flagged | Flagged | Flagged | 3/3 Flagged | **miss** |
| 13 | Pending | Flagged | Pending | Pending | 2/3 Pending | match |
| 14 | Flagged | Code complete | Flagged | Flagged | 2/3 Flagged | match |
| 22 | Flagged | Flagged | Flagged | Flagged | 3/3 Flagged | match |

No entry hit "all 3 disagree". The validator did not fire on any of these
24 runs — 03/09/13/14 outcomes are pure model behavior.

### Single-run entries

14/15 pass. Only miss is **15** (golden `Flagged`, got `Code complete`) —
the same long-standing sweeping-claim scope-limit miss from v2.

### Headline

**20/23.** Misses: 03, 09, 15.

| run | score | misses |
|---|---|---|
| v2.1 / v3 baseline | 18/23 | 04, 13, 14, 15, 22 |
| v3 post "not yet" fix (1×) | 18/23 | 01, 03, 06, 09, 15 |
| **v4 (verification carve-out, self-consistency)** | **20/23** | **03, 09, 15** |

01 and 06 gone from the miss list. 13/14/22 recovered — 13 and 14 needed
the majority vote (genuinely 2/3 unstable). 03 and 09 were already misses
in v3; they are stable (3/3) model-vs-golden-label disagreements, not
regressions and not validator errors.

## Are 01 and 06 actually fixed, or passing by luck?

Re-ran `validate_status` on all six real narratives with and without the
carve-out:

**Case 01 — fixed, and the carve-out is demonstrably why.**
- Run 1: *"the necessary on-device **testing** is still explicitly
  **outstanding**"* — `outstanding` is present. Without the carve-out →
  `Pending`. With it → `testing` is 4 words before → suppressed.
- Run 3: *"lists on-device otp login **verification** as the
  still-**outstanding** next step"* — same, `verification` in window →
  suppressed.
- Run 2: model didn't use the word.
- Without the fix: runs 1 and 3 → `Pending`, majority `Pending` → **miss**.
  With the fix: 3/3 `Code complete`. The carve-out carried 2 of 3 runs.

**Case 06 — passing 3/3, but the carve-out wasn't exercised this run.**
- All 3 runs phrased it as *"simply code-complete"* / *"code-complete
  rather than tested"* with no trigger phrase at all (only the stripped
  `follow-up` boilerplate). The model's own output was clean, so the
  validator had nothing to suppress.
- Not luck — the underlying judgment was right all 3 times — but the
  safety net wasn't independently re-demonstrated here. The exact sentence
  that broke 06 last round is pinned in the unit suite and the carve-out
  does suppress it, so a recurrence is covered.

## Still open

- **Cases 03, 09**: stable model disagreements with the golden label.
  Neither involves the validator. 03: model reads a change as a single
  self-contained `Code complete`, golden wants `Pending`. 09: model finds
  a claim mismatch and escalates to `Flagged`, golden says `Code
  complete`. Worth reviewing whether the golden labels or the model are
  right — same kind of review that corrected entries 11 and 14 earlier.
- **Case 15**: unchanged. Sweeping claim lives in diff/log content, not
  the commit message, outside the sweeping-claim check's reach.
- **Case 13**: passes now via majority vote but is genuinely 2/3 unstable
  (rule 3 vs rule 13 precedence, diagnosed in v3, still not resolved in
  the contract).
- **Eval cost**: the self-consistency run is 39 calls. Full 3× on all 23
  would be 69. A cheaper option not taken this round: freeze the
  `prompt_contract_layer` outputs and re-run only the validator stage to
  isolate its effect from model variance entirely.
