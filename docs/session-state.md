# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `fix-sweeping-claim-own-lines` (session 4, 2026-09-10),
  committed, **not merged, not pushed** — awaiting architect review.
  Prior state: `main` @ `86ed931`, both session-3 branches merged and
  pushed. Do the merge decision first (see Open decisions).
- **Last session:** 2026-09-10 (session 4) — fixed the entry-13 false
  positive in `build_sweeping_claim_check` (fetch layer, not the prompt):
  the repo grep for stale text a sweeping claim says is gone was counting
  hits on lines the commit itself just added (a changelog line describing
  its own fix). New `_added_line_numbers_by_path` parses the commit's own
  diff; hits on added lines no longer count. `test_sweeping_claim_check.py`
  added (9 AI-free cases + gated real entry-13 regression). All 4 unit
  suites green. v7 self-consistency eval: **22/23** (only miss: 15).
  Entry 13 now **6/6 `Pending`** (3 in the eval + 3 targeted re-check) —
  was a documented coin-flip since v3. Entries 01/06 showed 2/3 in the
  eval run but 3/3 `Code complete` on targeted re-check — model noise, not
  this change (neither triggers the sweeping-claim check). See
  `docs/eval-v7-findings.md`.

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
| Merge `eval-v5-overclaim-verification` to `main` | DONE — `--no-ff` merge `2bcffcd`, pushed |
| Merge `rule15-ui-copy-removal` to `main` | DONE — `--no-ff` merge `ad65497`, pushed |
| `call_claude` timeout 120 → 180 s | DONE — `86ed931` on `main`, pushed |
| Case 13 fix — `sweeping_claim_check` ignores the commit's own added lines | DONE — session 4, branch `fix-sweeping-claim-own-lines`, committed. `test_sweeping_claim_check.py` added. v7 eval **22/23**, entry 13 6/6 `Pending`. NOT merged/pushed. |

## Open decisions for next session (in priority order)

1. **Merge `fix-sweeping-claim-own-lines` to `main`.** Session 4's entry-13
   fix. `--no-ff` merge + push, same as the session-3 branches, once the
   architect has reviewed. This was option (b) from `eval-v6-findings.md`;
   options (a) prompt-contract precedence and (c) relabel entry 13 were
   not needed — the ambiguity was a fetch-layer artifact. Details in
   `docs/eval-v7-findings.md`.

2. **Case 15 — now the sole miss.** Unchanged long-standing miss: sweeping
   claim lives in diff/log content, not the commit message, so
   `detect_sweeping_claims` never sees it. Closing it means reading claims
   out of added diff content (real false-positive risk) or accepting
   22/23 as this golden set's ceiling.

3. **Eval cost.** The self-consistency run is 39 `claude -p` calls.
   Cheaper alternative not yet taken: freeze `prompt_contract_layer`
   outputs and re-run only the validator stage to isolate its effect from
   model variance.

4. **Entries 01/06 variance.** Both drifted 1/3 to `Pending` in the v7 run
   (3/3 `Code complete` on re-check). Persistent low-grade noise on the
   "open sub-items → is it done?" boundary. Not blocking; note if it
   worsens.

## Re-run commands (for reference — a session can just run these)

```bash
cd /home/rdeva/status-translation-agent
python3 test_status_consistency_validator.py                                    # validator unit suite, 20 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py          # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_ui_copy_removal_check.py    # ui-copy-removal unit suite, 22 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_sweeping_claim_check.py     # sweeping-claim unit suite, 9 cases + entry-13 regression, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest
```
