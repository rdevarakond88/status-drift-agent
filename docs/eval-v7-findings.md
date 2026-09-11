# Eval v7: sweeping-claim check ignores the commit's own added lines

Closes the entry-13 precedence gap that v3–v6 deferred, by fixing it in the
**fetch layer** (deterministic) rather than adding a precedence rule to the
prompt contract. Same self-consistency methodology as v4/v5/v6:
`run_selfconsistency_eval.py` — 3 runs on the 8 flip-history entries (01,
03, 04, 06, 09, 13, 14, 22), 1 run on the other 15.

## What changed since v6

**`build_sweeping_claim_check` / `verify_claim_against_repo` (fetch layer).**
The sweeping-claim check greps the repo tree as of the commit for the
literal text a sweeping claim says is gone (e.g. `"Six Agents"`). It was
counting *every* hit as a leftover — including hits on lines the commit
itself had just written.

New: `_added_line_numbers_by_path(repo, sha)` parses the commit's own
unified diff (first-parent for merges) into `{path: {new-side line numbers
added}}`. A `git grep -n <sha>` hit at `path:lineno` is now dropped from
`still_found_at` when that line is one the commit added. Only pre-existing
content — text the commit did not just write — counts toward
`claim_holds`.

`test_sweeping_claim_check.py`: 9 AI-free cases (2 `detect_sweeping_claims`,
4 hermetic `build_sweeping_claim_check`, 1 gated real entry-13 regression;
counts include sub-assertions). Core cases:

- self-describing fix — commit fixes a stale heading *and*, in the same
  diff, adds a changelog line naming the old text as what it changed →
  `claim_holds: true` (the only remaining hit is the commit's own new line)
- genuine leftover — old text also sits in a separate **pre-existing** file
  the commit never touches → `claim_holds: false`, `still_found_at` names
  only that file (unchanged behavior)
- hit on a pre-existing **context** line (commit edits the file but not
  that line) → still counts; the exclusion is added-lines-only

False-positive / blast-radius check before the run: across all 19 real +
4 synthetic entries, `sweeping_claim_check` fires (`detected: true`) on
**entry 13 only**. Entries 01 and 06 do not trigger it — their fetch-layer
payload is byte-identical before and after this change.

## Full 23-entry table

| entry | golden | runs (post-validator) | outcome | vs golden |
|---|---|---|---|---|
| 01 | Code complete | Pending / Code complete / Code complete | 2/3 | match (majority) — see note |
| 02 | Pending | Pending | — | match |
| 03 | Code complete | Code complete ×3 | 3/3 | match |
| 04 | Code complete | Code complete ×3 | 3/3 | match |
| 05 | Code complete | Code complete | — | match |
| 06 | Code complete | Code complete / Pending / Code complete | 2/3 | match (majority) — see note |
| 07 | Code complete | Code complete | — | match |
| 08 | Code complete | Code complete | — | match |
| 09 | Flagged | Flagged ×3 | 3/3 | match (deterministic — rule 15) |
| 10 | Code complete | Code complete | — | match |
| 11 | Flagged | Flagged | — | match |
| 12 | Flagged | Flagged | — | match |
| 13 | **Pending** | **Pending ×3** | **3/3** | **match** — was 2/3 Flagged in v6 |
| 14 | Flagged | Flagged ×3 | 3/3 | match (deterministic — rule 14) |
| 15 | Flagged | Code complete | — | **miss** |
| 16 | Code complete | Code complete | — | match |
| 17 | Code complete | Code complete | — | match |
| 18 | Code complete | Code complete | — | match |
| 19 | Flagged | Flagged | — | match |
| 20 | Flagged | Flagged | — | match |
| 21 | Flagged | Flagged | — | match |
| 22 | Flagged | Flagged ×3 | 3/3 | match |
| 23 | Flagged | Flagged | — | match |

### Headline

**22/23** on majority vote. Only miss: **15**.

| run | score | misses |
|---|---|---|
| v4 (verification carve-out, self-consistency) | 20/23 | 03, 09, 15 |
| v5 (overclaim check + carve-out, merged) | 22/23 | 15 |
| v6 (rule 15 + entry 09 relabel) | 21/23 | 13, 15 |
| **v7 (sweeping-claim ignores own added lines)** | **22/23** | **15** |

## Entry 13 — resolved, deterministically

v6 diagnosis was correct: `sweeping_claim_check` was firing a false
`claim_holds: false` on entry 13. The message quotes `"Six Agents"` with
"entirely"; a repo grep as of `2dab6c7` still finds `"Six Agents"` at
`docs/project-state.md:83` and `:86` — but **both are lines `2dab6c7`
itself adds**: a governance-backlog row (`| 10 | ... header changed to
'## The Eight Agents' |`) and a "Last Session" note, each describing the
fix the commit just made. With those excluded, `still_found_at` is empty
and `claim_holds` is `true` — the commit did clean up the stale header
everywhere it was actually stale.

That removes the rule-3/9 "mismatch" that had been pulling the model to
`Flagged`. Rule 13 (open sub-items #8/#9 awaiting a human decision) is now
uncontested → `Pending`, the golden.

Result: **6/6 `Pending`** across two independent reads (3 in the v7
self-consistency run + a 3-run targeted re-check). Entry 13 went from a
documented ~coin-flip (v4 2/3 P, v5 3/3 P, v6 2/3 F) to stable-correct.

This is option (b) from the v6 "still open" list. Option (a) — a
precedence rule in the prompt contract — was not taken: the ambiguity was
a fetch-layer artifact, not a genuine judgment the model needed guidance
on. Option (c) — relabel entry 13 — not needed; `Pending` stands.

## Entries 01 and 06 — model noise, not this change

The v7 self-consistency run showed 01 and 06 each at 2/3 (one run drifting
`Code complete → Pending`), where v6 had both 3/3. Neither commit triggers
the sweeping-claim check, so this change cannot have touched them. A 3-run
targeted re-check returned **`Code complete` ×3 for both** — the single
`Pending` in the main run was `claude -p` sampling variance on the usual
"open sub-items → is it really done?" boundary. Both are in the
flip-history MULTI set for exactly this reason.

## Still open

- **Entry 15 — unchanged, now the sole miss.** The sweeping claim lives in
  the diff / log content, not the commit message, so
  `detect_sweeping_claims` never sees it. Closing it means either reading
  claims out of added diff content (large scope increase, false-positive
  risk) or accepting 22/23 as the ceiling for this golden set.
- **Eval cost / robustness** — the v7 run was 39 `claude -p` calls (8×3
  multi + 15 single), plus 9 in the 01/06/13 targeted re-check. No runs
  timed out this time; the 120→180 s bump from `86ed931` held on entry
  13's 33 KB diff. The freeze-`prompt_contract_layer`-outputs option to
  isolate the validator stage from model variance is still not taken.
