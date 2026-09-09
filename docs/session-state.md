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
- **Last session:** 2026-09-09 (session 3) — built rule 15: deterministic
  detection of an undisclosed removal of user-visible on-screen text, with
  a code-level `Flagged` override. Fires on exactly one golden entry (09).

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
| Rule 15 — undisclosed UI-copy removal check (`build_ui_copy_removal_check` + prompt wiring + override) | DONE (uncommitted at time of writing) — 3 unit suites green (validator 20, overclaim 14, ui-copy-removal 22). False-positive sweep: fires on entry 09 only. |
| Merge `eval-v5-overclaim-verification` to `main` | **NOT DONE** — see open decision 1 |
| Merge `rule15-ui-copy-removal` to `main` | **NOT DONE** — after decisions 1 + 2 |
| Full 23-entry eval measuring rule 15 | **HELD** — waiting on the entry 09 golden-label decision so 09 + 13 confirm together |

## Open decisions for next session (in priority order)

1. **Merge `eval-v5-overclaim-verification` into `main` and push.** Branch
   holds only docs + the entry 03 label + refreshed eval output — no code
   change. Same `--no-ff` + push pattern as the last merge. Then rebase /
   merge `rule15-ui-copy-removal` on top.

2. **Entry 09 golden label — the rule 15 build forces the decision.** Rule
   15 now makes entry 09 deterministically `Flagged` (its diff silently
   removes the visible SMS-hint line; commit message says only "Add info
   icon…"). Entry 09's golden is currently `Code complete`, so **the new
   rule guarantees a miss on 09 until the golden flips to `Flagged`**. The
   user's instruction was "flag it" for undisclosed removal of user-facing
   copy, which implies `Flagged` is the intended answer for 09. Recommended:
   flip `golden-set/09.json` `verified_status` → `Flagged` and rewrite
   `correct_agent_response` (same move as entry 03 this session). Needs the
   architect's explicit confirmation before the held eval runs.

3. **Case 13 — NOT addressed by rule 15.** Its diff touches only
   `.md`/`.json`/`.jsonl`; no on-screen copy, so rule 15 correctly does not
   fire. 13 is 3/3 `Pending` in v5 (matches golden). Its latent instability
   is the rule 3 vs rule 13 precedence gap (contract states no precedence),
   diagnosed in `eval-v3-findings.md`, still unresolved — separate work.

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
