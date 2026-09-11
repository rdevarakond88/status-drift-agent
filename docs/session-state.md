# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `main` @ `799451f`. `fix-sweeping-claim-own-lines` (`3fbc5c9`,
  `b1ebe9d`) and `fix-flagged-hedge-downgrade` (`5770ecd`) both merged
  `--no-ff` into `main` on 2026-09-11 and **pushed**. Both branches kept
  for reference, not deleted. `origin/main` confirmed up to date.
- **Last session (session 5, 2026-09-11):** merged the two session-4
  sweeping-claim fixes into `main`, and along the way found + fixed a
  third, related bug in the validator.
    1. **Merge `fix-sweeping-claim-own-lines`** (`3fbc5c9` entry-13 fix,
       `b1ebe9d` entry-15 fix — see prior entry below for detail).
       `--no-ff`, both commits visible in history.
    2. **Post-merge verification surfaced a real validator bug on entry
       15**: the model correctly reasoned to `Flagged` (exactly what the
       entry-15 fix is for), but its narrative's closing hedge — *"...are
       expected leftover comments or something that **still needs**
       cleanup"* — matched `status_consistency_validator`'s `"still
       needs"` trigger and silently downgraded `Flagged → Pending`.
       Pre-existing gap (the validator never distinguished a hedge about
       the *same* flagged issue from a genuinely separate unfinished
       task like `trigger_overrides_flagged_too`'s "...and separately the
       app-side change is being handed off"). Fixed with a third,
       narrow carve-out (`_is_hedged_alternative`, 3-word lookback for a
       trigger phrase right after "or"). `test_status_consistency_validator.py`
       15→17 / 7→8 cases; the `trigger_overrides_flagged_too` guard still
       passes unchanged. Branch `fix-flagged-hedge-downgrade` (`5770ecd`),
       merged `--no-ff`.
    3. **Combined eval, run three times post-merge** (39 `claude -p`
       calls each): entries **13 and 15 — the two things this session's
       code actually changes — were stable and correct across all three
       runs and every targeted re-check** (13: `Pending` every time; 15:
       `Flagged` every time once the validator fix landed). Other entries
       showed run-to-run noise **confirmed unrelated** to anything changed
       this session (checked `sweeping_claim_check.detected` is `False`
       on each): entry 12 hit a *different*, still-open negation-window
       gap once (4/4 correct on re-check); entry 17 alternated
       `Code complete`/`Flagged` across samples — a real narrative split
       on whether an unrelated ownership-registry line the diff adds
       deserves a flag, not caused by today's changes; entry 22 repeated
       its long-standing historical instability; multiple runs hit a raw
       `claude -p` `JSONDecodeError` (09, 11, 22) — transient infra
       flakiness, matches a live "model temporarily unavailable" tool
       error hit mid-session. See open decisions below for what's still
       worth a look.
  All 4 unit suites green throughout (validator, overclaim, ui-copy-removal,
  sweeping-claim).

- **Earlier, session 4 (2026-09-10)** — two related fixes to
  `build_sweeping_claim_check`, both fetch-layer:
    1. **Entry-13 fix**: the repo grep for stale text a sweeping claim says
       is gone was counting hits on lines the commit itself just added (a
       changelog line describing its own fix). `_commit_diff_added` parses
       the commit's diff; hits on its own added lines no longer count. v7
       eval **22/23** (only miss: 15). Entry 13: **6/6 `Pending`** (was a
       coin-flip since v3). `docs/eval-v7-findings.md`.
    2. **Entry-15 fix**: the trigger scan only checked the commit
       *message* for sweeping language. Entry 15's overclaim is in a "Last
       Updated" note the commit *adds* to `docs/project-state.md`. New
       `claims_from_added_prose` scans added prose lines from doc files
       for **absence-claim** phrasing only ("no longer appears") + a
       distinctive adjacent token; verification unchanged. One-clause edit
       to prompt rule 9. v8 eval **23/23 majority** (no misses). Entry 15:
       **5/5 `Flagged`**. Entry 13 unaffected (scope intensifiers like
       "deferring entirely to `x.sh`" in its added prose are not absence
       claims). `docs/eval-v8-findings.md`.

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
| Case 13 fix — `sweeping_claim_check` ignores the commit's own added lines | DONE — `3fbc5c9`, merged to `main` `b200807`, pushed. Entry 13 6/6 `Pending` across sessions 4 and 5. |
| Case 15 fix — sweeping trigger also scans the commit's own added prose (absence-claim phrasing only) + rule-9 clause | DONE — `b1ebe9d`, merged to `main` `b200807`, pushed. Entry 15 `Flagged` consistently once the validator fix (below) landed. |
| Validator fix — `Flagged` no longer downgraded by a hedge ("or ... still needs") that isn't a separate unfinished task | DONE — `5770ecd`, merged to `main` `799451f`, pushed. `test_status_consistency_validator.py` 17/8 cases (`trigger_overrides_flagged_too` guard unchanged). Found and fixed while verifying the sweeping-claim merge; see session-5 note above. |

## Open decisions for next session (in priority order)

1. **Entry 12 — a second, still-open negation-window gap.** Same class of
   bug as the hedge fix but different: `"doesn't"` sat 9 words before the
   `"follow-up"` trigger it was negating (`"...doesn't need to be treated
   as a gap needing follow-up"`), one word past `NEGATION_LOOKBACK_WORDS`
   (8). Hit once in the session-5 eval, cleared 4/4 on re-check — rare,
   not reproduced on demand, not fixed this session (deliberately, to
   avoid open-ended validator patching). Widening the lookback is the
   likely fix if it recurs; watch for it rather than pre-emptively tuning.

2. **Entry 17 — model split on an unrelated diff detail, not the golden
   set's fault.** Alternated `Code complete` (4/4 on one re-check) and
   `Flagged` (2/2 on a later one) across independent samples. The
   `Flagged` reasoning is about a real, separate observation (an
   ownership-registry line the diff adds with no mention in the commit
   message) — not caused by anything changed this session
   (`sweeping_claim_check.detected` confirmed `False` on this commit).
   Worth a look if it keeps splitting: either the golden label needs a
   second look, or this is a legitimately close call the model is
   entitled to see differently run to run.

3. **`claude -p` flakiness observed this session.** Multiple raw
   `JSONDecodeError`s (truncated/malformed JSON) across different runs
   and entries (09, 11, 22), plus one live "model temporarily unavailable"
   tool error mid-session. Not a code regression — infra/availability
   noise. No action taken; note if it becomes the norm rather than the
   exception.

4. **Eval cost / robustness.** The self-consistency run is 39 `claude -p`
   calls, run three times this session alone (~115 calls) chasing a clean
   confirmation number that inherent model variance on single-run entries
   makes unlikely in any one run. Cheaper alternative not yet taken:
   freeze `prompt_contract_layer` outputs and re-run only the validator
   stage to isolate its effect from model sampling variance.

5. **Entries 01/03/06 variance.** Low-grade `Code complete ↔ Pending`
   noise on the "open sub-items → is it done?" boundary; stable across
   sessions 4–5's re-checks. Not blocking; note if it worsens.

6. **Synthetic entries (20–23)** get `sweeping_claim_check` from
   `run_golden_eval._synthetic_sweeping_claim_check`, which scans only the
   message. Not a gap today (no synthetic diff has absence-claim prose),
   but the two code paths have diverged by one capability.

## Re-run commands (for reference — a session can just run these)

```bash
cd /home/rdeva/status-translation-agent
python3 test_status_consistency_validator.py                                    # validator unit suite, 23 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py          # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_ui_copy_removal_check.py    # ui-copy-removal unit suite, 22 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_sweeping_claim_check.py     # sweeping-claim unit suite, 20 cases + entry 13 & 15 regressions, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest
```
