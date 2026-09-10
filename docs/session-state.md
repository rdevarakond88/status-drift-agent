# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `rule15-ui-copy-removal`, branched off `eval-v5-overclaim-verification`
  (`db6c7da`), itself off `main` (`6e7051e`). Two unmerged branches stacked:
    - `eval-v5-overclaim-verification` — v5 eval writeup, README pass rate,
      entry 03 label, refreshed selfconsistency output. No code change.
    - `rule15-ui-copy-removal` — NEW deterministic check + rule 15 (this
      session). All 3 unit suites green. **Full eval held** pending the
      entry 09 golden-label decision (open decision 2).
- **Last session:** 2026-09-09/10 (session 3) — built rule 15
  (deterministic undisclosed-UI-copy-removal check + `Flagged` override),
  flipped golden entry 09 → `Flagged` (architect-confirmed), ran the v6
  self-consistency eval. **21/23**, misses 13 + 15. Rule 15 works
  perfectly (09 now 3/3 `Flagged` deterministically, zero false
  positives); entry 13 regressed on its own long-standing rule 3/9-vs-13
  coin-flip, unrelated to rule 15. See `docs/eval-v6-findings.md`.

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
| Rule 15 — undisclosed UI-copy removal check (`build_ui_copy_removal_check` + prompt wiring + override) | DONE — committed `55f483a`. 3 unit suites green (validator 20, overclaim 14, ui-copy-removal 22). Sweep: fires on entry 09 only. |
| Golden entry 09 label | FLIPPED — `Code complete` → `Flagged`, committed `fcd8b83` (architect-confirmed). |
| v6 self-consistency eval | DONE — **21/23**, misses 13 + 15. `docs/eval-v6-findings.md`. |
| Merge `eval-v5-overclaim-verification` to `main` | **NOT DONE** — see open decision 1 |
| Merge `rule15-ui-copy-removal` to `main` | **NOT DONE** — after decision 1 (+ optionally decision 2) |

## Open decisions for next session (in priority order)

1. **Merge both stacked branches into `main` and push.** Order:
   `eval-v5-overclaim-verification` first (docs + entry 03 label + eval
   output, no code), then `rule15-ui-copy-removal` (rule 15 code + tests +
   entry 09 label + v6 findings). Same `--no-ff` + push pattern as the last
   merge. Whether to hold `rule15-*` for a 13 fix first is a judgment call —
   rule 15 itself is clean and regression-free; only the headline number
   moved (22→21) because of independent 13 variance.

2. **Case 13 — precedence gap is now non-deferrable if 22+/23 is the goal.**
   Deferred since `eval-v3-findings.md`; v6 forces it. `sweeping_claim_check`
   fires on 13 ("Six Agents" still in `docs/project-state.md`, inside the
   commit's own audit-log prose → `claim_holds: false`), pulling the model
   to `Flagged` under rule 9; rule 13 (open sub-items #8/#9) pulls to
   `Pending`; no precedence stated → ~coin-flip (v4 2/3 Pending, v5 3/3
   Pending, v6 2/3 Flagged). Options in `eval-v6-findings.md`: (a) state a
   precedence (rule 13 wins when the "mismatch" is a sweeping-claim hit on
   the commit's own tracking-log text); (b) tighten `sweeping_claim_check`
   to ignore hits inside the diff's own added log lines; (c) review whether
   `Pending` is the right golden for 13.

3. **Raise `call_claude`'s default `claude -p` timeout (120 → 180 s).**
   Entry 13's 33 KB diff (largest in the set) timed out run 1 of the v6
   eval; had to re-run it 3× at `timeout=300`. One-line fix in
   `prompt_contract_layer.py`; not done this session (out of the rule-15
   ask).

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
python3 test_status_consistency_validator.py                                    # validator unit suite, 20 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py          # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_ui_copy_removal_check.py    # ui-copy-removal unit suite, 22 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest
```
