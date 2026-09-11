# Eval v9: merge verification + a third validator fix

Not a new fetch-layer change. This documents merging `fix-sweeping-claim-own-lines`
(the v7/v8 entry-13 and entry-15 fixes) into `main`, the validator bug that
verification surfaced, and the resulting three post-merge eval runs.

## Sequence

1. Merged `fix-sweeping-claim-own-lines` (`3fbc5c9`, `b1ebe9d`) into `main`
   `--no-ff` (`b200807`).
2. **Run 1** (post-merge, pre-validator-fix): entry 15's model output was
   correctly `Flagged`, but `status_consistency_validator` downgraded it
   to `Pending` — the narrative's closing hedge, *"...are expected
   leftover comments or something that **still needs** cleanup"*, matched
   the `"still needs"` trigger. `validate_status` had no way to tell a
   hedge about the same already-flagged issue apart from a genuinely
   separate unfinished task (the pre-existing `trigger_overrides_flagged_too`
   test: *"...and separately the app-side change is being handed off to
   another agent"*, which correctly does still flip `Flagged → Pending`).
   Also hit an unrelated `JSONDecodeError` on entry 22 (transient
   `claude -p` output truncation).
3. Fixed with a third, narrow carve-out — `_is_hedged_alternative`: a
   trigger phrase immediately after "or" (3-word lookback) is suppressed.
   Branch `fix-flagged-hedge-downgrade` (`5770ecd`), merged `--no-ff`
   (`799451f`). `test_status_consistency_validator.py`: 15→17
   `NEVER_TRIGGER` / 7→8 `MUST_TRIGGER` (23 total). The existing
   `trigger_overrides_flagged_too` case — Flagged should still downgrade
   for a genuinely separate unfinished task — passes unchanged.
4. **Run 2** (post-validator-fix): entry 15 correct (`Flagged`, no
   correction). Two new single-run anomalies: entry 12 (`Flagged→Pending`,
   a *different*, still-open negation-window gap — `"doesn't"` sat 9
   words before `"follow-up"`, one past the 8-word lookback) and entry 17
   (`ERROR`, another `JSONDecodeError`). Targeted re-check: both cleared
   4/4 correct.
5. **Run 3** (final, for the record): entry 15 correct again; entry 13
   correct 3/3. New noise on entries 02, 09, 11, 17, 22 — a mix of
   single-run misses and more `JSONDecodeError`s. Targeted re-check of
   02/11/17: 02 and 11 cleared instantly; **17 came back `Flagged` again**
   (2/2 across two separate checks, vs. 4/4 `Code complete` earlier).
   Confirmed `sweeping_claim_check.detected` is `False` for entry 17's
   commit (`afce46a`) — nothing changed this session is involved. The
   model's `Flagged` narrative is about a real, separate diff detail (an
   undisclosed ownership-registry addition), which it reads differently
   run to run. Not resolved; logged as an open item rather than chased
   further.

## What this confirms

- **Entry 13**: `Pending` in every sample across all three runs plus
  targeted checks (6+ observations this session, on top of 6/6 last
  session).
- **Entry 15**: `Flagged` in every sample once the validator fix landed
  (model itself was always `Flagged`, 5/5, even before the validator fix —
  the bug was purely in the correction pass).
- **Nothing else that moved is attributable to this session's code.**
  Verified per-entry: `sweeping_claim_check.detected` is `False` for
  every entry that showed noise (02, 09, 11, 12, 17, 22) except 13 and 15.
  The three anomaly classes are: (a) a second, distinct validator
  negation-window gap (entry 12, not fixed this session), (b) genuine
  model-sampling variance on a commit with a real ambiguous detail (entry
  17), (c) transient `claude -p` infra flakiness (`JSONDecodeError` on
  09, 11, 22 across the three runs) — consistent with a live "model
  temporarily unavailable" tool error hit mid-session.

## Why no single clean 23/23 run is reported

Three full 39-call runs (~115 `claude -p` calls) were spent this session
chasing one. Given the above — a second known validator gap, real
model-sampling variance on at least one entry, and observed infra
flakiness — a single perfectly clean run is not a reliable signal either
way; the entries that matter to this session's actual changes (13, 15)
were the stable ones throughout. Pushed on that basis rather than
continuing to re-roll.
