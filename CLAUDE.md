# status-drift-agent — Claude Code instructions

## Start of every session — do this first, without being asked

1. Read `docs/session-state.md` (if absent, read the newest
   `docs/session-handoff-*.md`). It is the authoritative snapshot of where
   work left off: what was done, current git state, and the open decisions.
2. Read the **Open decisions for next session** section and continue from
   there. Do not ask the user to re-explain the project or the last
   session — the snapshot is the context.
3. State a one-line "resuming from: <branch> — next: <the first open
   decision>" so the user can confirm or redirect.

At session end, update `docs/session-state.md` (or add a new dated
`docs/session-handoff-YYYY-MM-DD.md` and repoint this file) so the next
session resumes cleanly.

## What this project is

A tool that reads real git commit history and flags drift between what a
commit *says* it did and what its diff *actually* shows. Pipeline:
`fetch_layer.py` (deterministic) → `prompt_contract_layer.py`
(`generate_status_update` — the only AI step, calls `claude -p`) →
`status_consistency_validator.py` (pure text-match, no AI).

`run_golden_eval.py` runs a 23-entry hand-labeled golden set through the
full pipeline; `score_golden_eval.py` scores `eval_output/results.jsonl`
against each golden entry's `verified_status`.

## Key facts

- Eval target repo: `EVAL_TARGET_REPO=/home/rdeva/medrecord` (the private
  repo the golden set was built against; all 19 real commit shas resolve
  there). Set it when running `run_golden_eval.py`.
- The full pipeline eval spends 23 `claude -p` subprocess calls (~10–20
  min). The unit suite (`test_status_consistency_validator.py`) is
  AI-free and runs in ~0.1s — always run it first.
- Golden files (`golden-set/*.json`) use the key `verified_status`.
- Findings docs live in `docs/` (`disagreements.md`, `eval-v2-findings.md`,
  `eval-v3-findings.md`, …). Add the next one rather than rewriting old.

## Working style (from /home/rdeva/CLAUDE.md)

The user is the architect and directs execution; Claude executes. Show the
plan before doing. Plain English, define terms. Lean implementations, no
over-engineering. Challenge wrong assumptions. Don't expand scope beyond
what was asked — this repo's own history repeatedly notes changes that
were *not* made unilaterally because they went past the ask.

## End of every session

- Commit changed work to the current feature branch (not `main` directly —
  branch first if on `main`).
- State explicitly if a push was skipped and why.
- Update `docs/session-state.md` with the new resume point.
