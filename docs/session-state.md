# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `fix-sweeping-claim-own-lines` (session 4, 2026-09-10), two
  commits, **not merged, not pushed** — awaiting architect review.
  Prior state: `main` @ `86ed931`, both session-3 branches merged and
  pushed. Do the merge decision first (see Open decisions).
- **Last session:** 2026-09-10 (session 4) — two related fixes to
  `build_sweeping_claim_check`, both fetch-layer:
    1. **Entry-13 fix** (commit 1): the repo grep for stale text a sweeping
       claim says is gone was counting hits on lines the commit itself just
       added (a changelog line describing its own fix). `_commit_diff_added`
       parses the commit's diff; hits on its own added lines no longer
       count. v7 eval **22/23** (only miss: 15). Entry 13: **6/6 `Pending`**
       (was a coin-flip since v3). `docs/eval-v7-findings.md`.
    2. **Entry-15 fix** (commit 2): the trigger scan only checked the
       commit *message* for sweeping language. Entry 15's overclaim is in a
       "Last Updated" note the commit *adds* to `docs/project-state.md`.
       New `claims_from_added_prose` scans added prose lines from doc files
       for **absence-claim** phrasing only ("no longer appears") + a
       distinctive adjacent token; verification unchanged. One-clause edit
       to prompt rule 9. v8 eval **23/23 majority** (no misses). Entry 15:
       **5/5 `Flagged`**. Entry 13 unaffected (scope intensifiers like
       "deferring entirely to `x.sh`" in its added prose are not absence
       claims). `docs/eval-v8-findings.md`.
  `test_sweeping_claim_check.py`: 20 AI-free cases + gated real 13 & 15
  regressions. All 4 unit suites green. Entry 03 had a 1-run wobble in the
  v8 run (4/4 `Code complete` on re-check — noise, doesn't trigger the
  check).

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
| Case 13 fix — `sweeping_claim_check` ignores the commit's own added lines | DONE — session 4 commit 1 on `fix-sweeping-claim-own-lines`. v7 eval **22/23**, entry 13 6/6 `Pending`. NOT merged/pushed. |
| Case 15 fix — sweeping trigger also scans the commit's own added prose (absence-claim phrasing only) + rule-9 clause | DONE — session 4 commit 2 on `fix-sweeping-claim-own-lines`. `test_sweeping_claim_check.py` now 20 cases. v8 eval **23/23 majority**, entry 15 5/5 `Flagged`, entry 13 unaffected. NOT merged/pushed. |

## Open decisions for next session (in priority order)

1. **Merge `fix-sweeping-claim-own-lines` to `main`.** Two commits: the
   entry-13 fix (option (b) from `eval-v6-findings.md`) and the entry-15
   fix. `--no-ff` merge + push, same as the session-3 branches, once the
   architect has reviewed. Details in `docs/eval-v7-findings.md` and
   `docs/eval-v8-findings.md`. This branch takes the golden set from
   22/23 to **23/23** (majority vote), no known misses.

2. **Eval cost / robustness.** The self-consistency run is 39 `claude -p`
   calls. Cheaper alternative not yet taken: freeze `prompt_contract_layer`
   outputs and re-run only the validator stage. Entry 03's v8 one-run
   wobble is the reminder that the 15 single-run entries carry no
   stability signal.

3. **Entries 01/03/06 variance.** Low-grade `Code complete ↔ Pending`
   noise on the "open sub-items → is it done?" boundary; each returned to
   a clean sweep on targeted re-check. Not blocking; note if it worsens.

4. **Synthetic entries (20–23)** get `sweeping_claim_check` from
   `run_golden_eval._synthetic_sweeping_claim_check`, which scans only the
   message. Not a gap today (no synthetic diff has absence-claim prose),
   but the two code paths have diverged by one capability.

## Re-run commands (for reference — a session can just run these)

```bash
cd /home/rdeva/status-translation-agent
python3 test_status_consistency_validator.py                                    # validator unit suite, 20 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py          # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_ui_copy_removal_check.py    # ui-copy-removal unit suite, 22 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_sweeping_claim_check.py     # sweeping-claim unit suite, 20 cases + entry 13 & 15 regressions, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest
```
