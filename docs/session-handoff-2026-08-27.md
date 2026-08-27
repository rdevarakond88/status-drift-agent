# Session handoff — 2026-08-27

Pick up here in a fresh session. This captures exactly what was done, what
the state is, and what's undecided.

---

## What this session was asked to do

1. **Fix the trigger phrase list in the Status Consistency Validator.**
   Remove bare `"not yet"` (it matched rule-2's required "not yet tested"
   phrasing and wrongly flipped `Code complete` → `Pending`). Replace with
   more specific phrasings that only signal genuine incompleteness:
   `"not yet complete"`, `"not yet done"`, `"not yet finished"`.

2. **Build a permanent unit-test suite for the validator**, separate from
   the 23-entry pipeline eval. Hand-written sentences, pure text matching,
   no AI call. Two groups: sentences that must NEVER trigger a status
   change, and sentences that MUST.

3. Run the unit suite standalone and confirm it passes **before** running
   the full 23-entry pipeline eval. Report both results separately.

Scope decision made mid-session (user chose "minimal"): the case-13
"logged for a person to decide later" / waiting-on-a-human pattern is
**not** added as a new trigger phrase. Case 13 was never a validator
catch — its `Pending` golden label comes from prompt-contract rule 13,
not the validator. That pattern lives in the unit suite as documented
NEVER_TRIGGER behavior only.

---

## What was done — all COMPLETE, NOT COMMITTED

### Change 1: `status_consistency_validator.py`
`OUTSTANDING_PHRASES` is now:
```
"still needs", "not yet complete", "not yet done", "not yet finished",
"follow-up", "outstanding", "handed off"
```
`"not yet"` removed. Docstring + inline comment explain the carve-out and
point at the test file. **No other logic touched** (negation guard,
lookback window, FOLLOW_UP strip all unchanged).

### Change 2: `test_status_consistency_validator.py` (NEW)
Permanent unit suite. `python3 test_status_consistency_validator.py`,
exit 0/1, ~0.1s, no AI. 16 cases:

- **9 NEVER_TRIGGER**: exact case-04 regressed narrative; bare "not yet
  tested"; rule-2 untested mockup; "no outstanding work" (negation guard);
  "nothing left to do here"; "not a gap needing follow-up" (negation
  guard); constructed negated "not yet complete"; FOLLOW_UP boilerplate
  alone; trigger phrase against an already-`Pending` status (no-op).
- **7 MUST_TRIGGER**: "still needs to happen"; "one outstanding … step";
  "handed off to another agent"; "not yet complete"; "not yet done"; "not
  yet finished"; a trigger against `Flagged` input.

**Result: 16/16 PASS.**

### Change 3: `score_golden_eval.py` (NEW)
There was no automated scorer. This compares
`eval_output/results.jsonl` against each golden entry's
`verified_status` and prints a per-entry table + headline N/23.
`python3 score_golden_eval.py [results.jsonl]`.

### Artifacts
- `eval_output/results-prefix-baseline.jsonl` — the pre-fix results,
  saved before re-running. Baseline score **18/23**, misses = 04, 13, 14,
  15, 22. Case 04's miss was `Code complete` → `Pending` via `['not yet']`
  (the regression this session fixed).
- `eval_output/run-postfix.log` — stderr/progress log of the post-fix
  pipeline run.
- `eval_output/results.jsonl` — **overwritten** with the post-fix run.

---

## Pipeline eval result (post-fix)

**18/23 — same headline as baseline, different composition, and NOISY.**

| | misses |
|---|---|
| baseline (pre-fix) | 04, 13, 14, 15, 22 |
| post-fix | 01, 03, 06, 09, 15 |

- Newly passing: 04, 13, 14, 22 — Newly failing: 01, 03, 06, 09 — net 0.
- **Only case 04's change is attributable to the fix.** 13/14/22 (now
  pass) and 03/09 (now fail) are model run-to-run variance — narrative
  wording changed between runs, no code caused it. 8 of 23 entries flipped
  pass/fail state between two runs of near-identical code (~35% churn).
  **The eval at 1 run/entry cannot certify "nothing else broke" — noise >
  effect.**

### Real finding: cases 01 and 06 broke on the SAME bug class, different words

| case | phrase in model narrative | validator did | correct answer |
|---|---|---|---|
| 01 | "that verification is still **outstanding**" | `Code complete`→`Pending` | `Code complete` (means "still needs a device test" — rule 2) |
| 06 | "finished code that **still needs** a visual QA pass" | `Code complete`→`Pending` | `Code complete` (means "still needs QA" — rule 2) |

`"outstanding"` and `"still needs"` have the **identical flaw `"not yet"`
had**: they match pending-*verification* language, which rule 2 keeps at
`Code complete`. Substring matching can't separate "still needs to happen"
(work incomplete — SHOULD trigger, unit suite asserts it) from "still
needs a QA pass" (verification pending — should NOT). Case 03 was
previously passing only because this same false positive corrected it to
the right answer by luck.

---

## Open decisions for next session (NOT started)

1. **Commit the work.** Nothing is committed. Files: `M
   status_consistency_validator.py`, `M eval_output/results.jsonl`, new
   `test_status_consistency_validator.py`, `score_golden_eval.py`,
   `eval_output/results-prefix-baseline.jsonl`,
   `eval_output/run-postfix.log`, `docs/session-handoff-2026-08-27.md`.
   Currently on `main` — branch first.

2. **Decide whether `"outstanding"` and `"still needs"` get a rule-2-aware
   carve-out** (a verification-context exception, the way the negation
   guard is an exception), or whether the false positives on cases 01/06
   are acceptable. This is the same question `eval-v3-findings.md` raised
   about `"not yet"` and it now has two more instances.

3. **Eval noise.** To get real signal on pipeline regressions: either run
   the eval 3–5× per entry and majority-vote, or freeze the model outputs
   (`prompt_contract_layer` stage) and re-run only the validator stage so
   the validator's effect is isolated from model variance.

4. **Update `README.md` / write `docs/eval-v4-findings.md`** once the
   above are decided — the README still says "18/23 … Fixed: … a
   text-matcher that was flipping correct answers to wrong ones on negated
   phrases" and does not yet mention the `not yet` fix or the
   outstanding/still-needs finding.

---

## How to re-run things

```bash
cd /home/rdeva/status-translation-agent

# unit suite (fast, no AI)
python3 test_status_consistency_validator.py

# full pipeline eval (23x `claude -p` subprocess calls, ~10-20 min)
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py

# score whatever is in eval_output/results.jsonl
python3 score_golden_eval.py
# or score the saved baseline
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl
```

Key facts a fresh session needs:
- Eval target repo = `/home/rdeva/medrecord` (the "private production
  repo" the golden set was built against; all 19 real shas resolve there).
- Model call = `claude -p` subprocess (see `prompt_contract_layer.call_claude`).
- Golden files use the key `verified_status`.
- Pipeline order: `fetch_layer` → `prompt_contract_layer.generate_status_update`
  (the only AI step) → `status_consistency_validator.validate_status`.
