# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `eval-v5-overclaim-verification`, branched off `main`
  (`6e7051e`). Holds the v5 eval writeup, README pass-rate update, entry 03
  label correction, and the refreshed selfconsistency results. Not yet
  merged, not pushed. `validator-not-yet-fix` is still kept for reference.
- **Last session:** 2026-09-09 (session 2) — ran the full v5 self-consistency
  eval measuring the merged overclaim check + verification carve-out;
  corrected golden entry 03's label. Result **22/23** (only miss: 15).

## Status of the work

| Item | State |
|---|---|
| Rules 12/13 in prompt contract | DONE — committed `6352660` (earlier session) |
| Drop bare `"not yet"` trigger + original 16-case unit suite | DONE — committed `ac2708c` (earlier session) |
| General verification-word carve-out + 20-case unit suite | DONE — committed `433410f`, **20/20 pass**, AI-free |
| Self-consistency eval run (3× on 8 unstable entries, 1× rest) | RUN — **20/23**; misses 03, 09, 15; see `docs/eval-v4-findings.md` |
| Docs: `eval-v4-findings.md`, README | DONE — committed `d9c0219` |
| Overclaim check — fetch-layer detection (`build_overclaim_check`) + 8 unit cases | DONE — committed `10e5af6`; false-positive sweep clean (fires on entry 14 only) |
| Overclaim check — prompt-contract wiring (payload field, `enforce_deterministic_rules`, rule 14) + 6 more unit cases | DONE — committed `c36a518`, **14/14 pass**, AI-free |
| Full 23-entry eval since `10e5af6`/`c36a518` landed | DONE — v5 self-consistency run, **22/23**, `docs/eval-v5-findings.md` |
| Entry 14 deterministic `Flagged` via rule 14 | CONFIRMED — 3/3 Flagged; `overclaim_check.detected` True deterministically, `enforce_deterministic_rules` forces Flagged for any model status |
| Golden entry 03 label | CORRECTED — `Pending` → `Code complete`, `correct_agent_response` rewritten to match 01/04–08/10 |
| Merge `eval-v5-overclaim-verification` to `main` | **NOT DONE** — see open decision 1 |

## Open decisions for next session (in priority order)

1. **Merge `eval-v5-overclaim-verification` into `main` and push.** Branch
   holds only docs + the entry 03 label + refreshed eval output — no code
   change. Same `--no-ff` + push pattern as the last merge.

2. **Entry 09 — genuine run-to-run instability, not resolved.** v4: 3/3
   `Flagged`. v5: 2/3 `Code complete` (now "passes" by majority), with no
   code change on its path between the two runs. The model alternately
   reads the diff's silent removal of an inline SMS-hint line as a rule 3
   say-vs-do mismatch or as within scope of "add an info icon". Passing now
   is luck, not a fix. Decide whether the golden label is right and/or
   whether rule 3 needs tightening. (Was framed as "accepted judgment
   call" after v4 — v5 shows it's actually unstable.)

3. **Case 13 rule precedence.** Passes now only via majority vote (2/3),
   genuinely unstable because rule 3 and rule 13 can both fire on it and
   the contract states no precedence. Diagnosed in `eval-v3-findings.md`,
   still unresolved.

4. **Case 15.** Unchanged long-standing miss — sweeping claim lives in
   diff/log content, not the commit message, outside the sweeping-claim
   check's reach.

5. **Eval cost.** The v4 self-consistency run was 39 `claude -p` calls.
   Cheaper alternative not yet taken: freeze `prompt_contract_layer`
   outputs and re-run only the validator stage to isolate its effect from
   model variance.

## Re-run commands (for reference — a session can just run these)

```bash
cd /home/rdeva/status-translation-agent
python3 test_status_consistency_validator.py                              # validator unit suite, 20 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py    # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest
```
