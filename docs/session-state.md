# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

- **Branch:** `validator-not-yet-fix` (off `main`). **Pushed** to
  `origin/validator-not-yet-fix`, HEAD `c36a518` as of 2026-09-09.
- **Last session:** 2026-09-09 — verification-context carve-out (v4 eval),
  then the deterministic overclaim check (fetch layer + prompt contract).

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
| Full 23-entry eval since `10e5af6`/`c36a518` landed | **NOT RUN** — batched/pending (see open decision 2) |
| Push branch | DONE — `origin/validator-not-yet-fix` @ `c36a518` |
| Merge to `main` | NOT DONE — waiting on user |

## Open decisions for next session (in priority order)

1. **Merge `validator-not-yet-fix` → `main`?** Branch is pushed, HEAD
   `c36a518`. `main` is still at `37856c1`. Nothing merged yet. Six
   commits ahead: `ac2708c`, `0d094f2`, `433410f`, `d9c0219`, `10e5af6`,
   `c36a518`.

2. **Whether/when to run the next full 23-entry eval.** Not re-run since
   the two overclaim-check commits (`10e5af6`, `c36a518`) landed. Rule 14
   now force-flags a detected overclaim, so entry 14 should move to
   `Flagged` deterministically; effect on the other 22 is unmeasured.
   Decide: run the full self-consistency eval (39 `claude -p` calls), a
   1×/entry run, or hold for more batched changes first.

3. **Entry 09's say-vs-do flag — accepted judgment call, not a bug.**
   Across the v4 self-consistency run the model flagged 09 3/3 (message
   says it only adds an info icon/tooltip; the diff also silently removes
   an existing inline SMS-hint line). Golden wants `Code complete`. This
   is a defensible rule-3 read, not a validator or overclaim-check
   failure — left as-is. Revisit only if the golden label itself is
   reviewed (same as the 03/11/14 label-review question).

4. **Case 13 rule precedence.** Passes now only via majority vote (2/3),
   genuinely unstable because rule 3 and rule 13 can both fire on it and
   the contract states no precedence. Diagnosed in `eval-v3-findings.md`,
   still unresolved.

5. **Case 15.** Unchanged long-standing miss — sweeping claim lives in
   diff/log content, not the commit message, outside the sweeping-claim
   check's reach.

6. **Eval cost.** The v4 self-consistency run was 39 `claude -p` calls.
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
