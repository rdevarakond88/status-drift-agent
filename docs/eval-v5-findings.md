# Eval v5: measuring the overclaim-check fix and the verification-word carve-out, merged

This run measures everything that landed on `main` on 2026-09-09 and had
not yet been run through a full eval:

1. The **verification-context carve-out** in
   `status_consistency_validator.py` (commit `433410f`) — a phrase-agnostic
   suppression rule so trigger words like `outstanding` / `still needs` /
   `not yet` don't flip `Code complete` → `Pending` when they refer to a
   routine pending-verification step (rule 2) rather than unfinished work.
2. The **deterministic overclaim check** — fetch-layer detection
   (`build_overclaim_check`, `10e5af6`) plus prompt-contract wiring and the
   rule 14 code-level override (`c36a518`). When a commit/PR message claims
   a feature was "added" but git history shows it already existed, rule 14
   forces status to `Flagged` regardless of what the model returns.

Plus one golden-set label correction (entry 03, see below).

Methodology is unchanged from v4: `run_selfconsistency_eval.py` — 3 runs
and a majority vote on the 8 entries with a flip history (01, 03, 04, 06,
09, 13, 14, 22), 1 run on the other 15. 39 `claude -p` calls, 0 errors.
Output in `eval_output/results-selfconsistency.jsonl`.

## Golden-set label correction: entry 03

Entry 03 (`5572d95`, tunnel-service interstitial bypassed by one header on
the shared network function) was labeled `verified_status: "Pending"`. The
commit's code is complete and consistent with its claim; only on-device
testing is outstanding. That is the exact situation entries 01, 04–08 and
10 all label `Code complete` — code done, a verification/device-test step
not yet confirmed is a rule 2 pending-verification step, not unfinished
work. Entry 03 was corrected to `Code complete` (and its
`correct_agent_response` rewritten to match) so the golden set is
self-consistent. The model had returned `Code complete` 3/3 on this entry
in v4; it was only a "miss" because of the label.

## Full 23-entry table

| entry | golden | runs (post-validator) | outcome | vs golden |
|---|---|---|---|---|
| 01 | Code complete | Code complete ×3 | 3/3 Code complete | match |
| 02 | Pending | Pending | Pending | match |
| 03 | Code complete | Code complete ×3 | 3/3 Code complete | match |
| 04 | Code complete | Code complete ×3 | 3/3 Code complete | match |
| 05 | Code complete | Code complete | Code complete | match |
| 06 | Code complete | Code complete ×3 | 3/3 Code complete | match |
| 07 | Code complete | Code complete | Code complete | match |
| 08 | Code complete | Code complete | Code complete | match |
| 09 | Code complete | Code complete / Flagged / Code complete | 2/3 Code complete | match (unstable — see below) |
| 10 | Code complete | Code complete | Code complete | match |
| 11 | Flagged | Flagged | Flagged | match |
| 12 | Flagged | Flagged | Flagged | match |
| 13 | Pending | Pending ×3 | 3/3 Pending | match |
| 14 | Flagged | Flagged ×3 | 3/3 Flagged | match (deterministic — rule 14) |
| 15 | Flagged | Code complete | Code complete | **miss** |
| 16 | Code complete | Code complete | Code complete | match |
| 17 | Code complete | Code complete | Code complete | match |
| 18 | Code complete | Code complete | Code complete | match |
| 19 | Flagged | Flagged | Flagged | match |
| 20 | Flagged | Flagged | Flagged | match |
| 21 | Flagged | Flagged | Flagged | match |
| 22 | Flagged | Flagged ×3 | 3/3 Flagged | match |
| 23 | Flagged | Flagged | Flagged | match |

The validator (`validate_status`) did not fire on any run this round —
`matched_phrases` empty on all 39. Every outcome above is either raw model
behavior or a prompt-contract code override.

### Headline

**22/23.** Only miss: **15**.

| run | score | misses |
|---|---|---|
| v2.1 / v3 baseline | 18/23 | 04, 13, 14, 15, 22 |
| v4 (verification carve-out, self-consistency) | 20/23 | 03, 09, 15 |
| **v5 (overclaim check + carve-out, merged)** | **22/23** | **15** |

## Entry 14 — now deterministic, 3/3 not 2/3

v4 had entry 14 at 2/3 Flagged (one run returned `Code complete`). This is
the entry the overclaim check was built for: PR #6's message claims OTP
`resend` was "added to D1 and P1", but `resend` was already present 88× in
both login screens since `12969c8` and this commit only takes it 88 → 91.

Verified the override is what guarantees the result, not model luck:

- `build_record('14.json')` → `overclaim_check.detected` is **True**
  deterministically (fetch layer, no AI). The `overclaim-check` unit suite
  (`test_overclaim_check.py`, 14 cases) pins this, and a prior
  false-positive sweep confirmed it fires on entry 14 only.
- `enforce_deterministic_rules(status, ..., record)` fed a deliberately
  wrong model status returns `Flagged` for every input
  (`Code complete` → `Flagged`, `Tested` → `Flagged`, `Pending` →
  `Flagged`).

So entry 14 is `Flagged` on all 3 runs because the code forces it, and
would stay `Flagged` even if the model regressed further. This is the
intended behavior for a code-level override: 3/3, not a majority vote.

## Still open

- **Entry 15** — unchanged long-standing miss. The sweeping claim
  ("no longer appears anywhere") lives in diff/log content, not the commit
  message, so the sweeping-claim check doesn't reach it. Not touched by
  anything in this round.
- **Entry 09** — passes this round at 2/3 `Code complete`, but it was 3/3
  `Flagged` in v4 with no code change on its path in between. This is
  genuine run-to-run model instability, not a fix. The model alternately
  reads the diff's silent removal of an inline SMS-hint line as a rule 3
  say-vs-do mismatch (→ Flagged) or as within scope of "add an info icon"
  (→ Code complete). It "matches" now only by majority. The underlying
  say-vs-do question and whether the golden label is right are both still
  open (session-state open decision 2).
- **Entry 13** — 3/3 `Pending` this round (was 2/3 in v4). More stable, but
  the rule 3 vs rule 13 precedence gap in the contract that makes it
  swingy is still unresolved (session-state open decision 3).
- **Eval cost** — still 39 calls. The freeze-`prompt_contract_layer`-and-
  re-run-only-the-validator option to isolate validator effect from model
  variance has not been taken.
