# Eval v8: sweeping-claim trigger also scans the commit's own added prose

Closes the last golden-set miss (entry 15), again in the **fetch layer**.
The v7 sweeping-claim check only scanned the *commit message* for
sweeping-claim language before running its repo-wide verification search.
Entry 15's overclaim is not in the message — it is in a "Last Updated"
note the commit adds to `docs/project-state.md`. v8 extends the trigger
scan to the commit's own newly-added prose lines; the verification logic
is unchanged (repo-wide, still excluding the commit's own added lines per
the v7 / entry-13 fix).

Same self-consistency methodology as v4–v7.

## What changed since v7

**`build_sweeping_claim_check` (fetch layer).**

1. `_added_line_numbers_by_path` is refactored into `_commit_diff_added`,
   which parses the commit's diff once and returns both `{path: {added
   line numbers}}` (the v7 exclusion set) **and** the text of every added
   line in a human-prose file (`.md/.rst/.txt/.adoc/...` —
   `_CLAIM_SOURCE_EXTENSIONS`). Machine logs (`.jsonl/.json`), code, and
   config are excluded: their added lines are data, not a status claim,
   and entry 15's commit also appends 20 lines of captured shell output to
   a `.jsonl` log.
2. New `claims_from_added_prose(prose_lines)` — deliberately narrower than
   the message scan, because added prose was not written as a claim to a
   reviewer:
   - only **absence-claim phrasing** counts (`_ABSENCE_CLAIM_RE`: "no
     longer appears/exists", "nowhere in", "gone/removed/stripped from").
     The scope intensifiers in `SWEEPING_CLAIM_KEYWORDS` ("entirely",
     "anywhere", "completely") do **not** — "deferring entirely to
     `` `infra-session-gate.sh` ``" in entry 13's own added prose is not a
     claim that that file is gone.
   - the claimed token must sit **just before** the phrase (its subject)
   - the token must look like a domain or dotted filename (contains `.`,
     no spaces) — a bare word like `` `main` `` greps to noise
   - backtick delimiters are read as well as quotes (added prose writes
     `` `code` `` far more than `'quoted'`)
3. `build_sweeping_claim_check` now fires `detected: True` when *either*
   the message *or* an added-prose absence-claim is found; every claimed
   text (from both sources) goes through `verify_claim_against_repo`
   unchanged.

**Prompt rule 9** — one clause added: the check may now be fed by "a
status/verification claim in the commit's own newly-added diff lines",
and the verification "excludes the commit's own newly-added lines". No
change to the operative instruction (a `claim_holds: false` verification
is a rule-3 mismatch).

`test_sweeping_claim_check.py`: **15 → 20** AI-free cases. New: 4 pure
`claims_from_added_prose` cases; hermetic E (entry-15 shape — claim in an
added status line, token still in an untouched doc → detected,
`claim_holds` false), F (scope intensifier in added prose + plain message
→ **not** detected — the entry-13-in-reverse guard), G (plain message, no
added-prose claim → silent); gated real entry-15 regression against
`6aa36a6`.

Blast-radius check: across the 19 real entries, `sweeping_claim_check`
now fires on **13 and 15 only** (was 13 only). Entries 01, 03, 06 —
`_commit_diff_added` sees their added `.md` prose but `claims_from_added_prose`
returns nothing; their `sweeping_claim_check` payload is unchanged.

## Full 23-entry table

| entry | golden | runs (post-validator) | vs golden |
|---|---|---|---|
| 01 | Code complete | Code complete ×3 | match |
| 02 | Pending | Pending | match |
| 03 | Code complete | Code complete / Pending / Code complete | match (majority; +4/4 CC on re-check) |
| 04 | Code complete | Code complete ×3 | match |
| 05 | Code complete | Code complete | match |
| 06 | Code complete | Code complete ×3 | match |
| 07 | Code complete | Code complete | match |
| 08 | Code complete | Code complete | match |
| 09 | Flagged | Flagged ×3 | match (deterministic — rule 15) |
| 10 | Code complete | Code complete | match |
| 11 | Flagged | Flagged | match |
| 12 | Flagged | Flagged | match |
| 13 | Pending | Pending ×3 | match |
| 14 | Flagged | Flagged ×3 | match (deterministic — rule 14) |
| 15 | **Flagged** | **Flagged ×1 (+4/4 on re-check = 5/5)** | **match** — was Code complete in v7 |
| 16 | Code complete | Code complete | match |
| 17 | Code complete | Code complete | match |
| 18 | Code complete | Code complete | match |
| 19 | Flagged | Flagged | match |
| 20 | Flagged | Flagged | match |
| 21 | Flagged | Flagged | match |
| 22 | Flagged | Flagged ×3 | match |
| 23 | Flagged | Flagged | match |

### Headline

**23/23 on majority vote.** No remaining misses. All-runs-correct 22/23
(entry 03 had one run drift `Code complete → Pending`; a 4-run re-check
returned `Code complete` ×4 — model noise, `sweeping_claim_check` does not
fire on 03).

| run | score (majority) | misses |
|---|---|---|
| v4 | 20/23 | 03, 09, 15 |
| v5 | 22/23 | 15 |
| v6 | 21/23 | 13, 15 |
| v7 (sweeping ignores own added lines) | 22/23 | 15 |
| **v8 (sweeping also scans own added prose)** | **23/23** | **—** |

## Entry 15 — resolved

The merge `6aa36a6` ("Merge PR #7 dev → main") carries a plain message with
no sweeping language. Its added `docs/project-state.md` "Last Updated"
note says:

> Post-merge confirmed via `git grep` that `` `onrender.com` `` no longer
> appears in `` `main` ``'s `` `src/api/` ``.

`claims_from_added_prose` extracts `onrender.com` (backticked token
immediately before "no longer appears"; has a `.`, no spaces).
`verify_claim_against_repo` greps the tree as of `6aa36a6`, minus the
commit's own added lines: **51 hits**, including `src/api/pinnedFetch.ts`
lines 6 and 16 — the certificate-pinning comment the golden's
`correct_agent_response` calls out. `claim_holds: false`.

Result: **5/5 `Flagged`** (1 in the v8 run + a 4-run re-check). The
substance of the merge is fine (`auth.ts`/`apiClient.ts` are clean); the
commit's own verification claim overstates its scope, which is exactly
what `Flagged` is for here.

## Entry 13 — no regression

Entry 13's added prose contains "deferring **entirely** to
`` `infra-session-gate.sh` ``" and "corrected it **entirely**" — scope
intensifiers, not absence claims. `_ABSENCE_CLAIM_RE` does not match them,
so `claims_from_added_prose` returns nothing and entry 13 still detects
only via its message keyword, with `claim_holds: true` (v7 fix intact).
**3/3 `Pending`.** Hermetic case F locks this in.

## Still open

- **Eval robustness** — the freeze-`prompt_contract_layer`-outputs option
  to isolate the validator stage from model variance is still not taken.
  Entry 03's one-run wobble is the current reminder that single-run
  entries carry no stability signal.
- **Synthetic entries (20–23)** build their `sweeping_claim_check` via
  `run_golden_eval._synthetic_sweeping_claim_check`, which scans only the
  message (no repo tree to grep, no diff object). None of the four
  synthetic diffs contain absence-claim prose, so this is not a gap
  today, but the two code paths have now diverged by one capability.
