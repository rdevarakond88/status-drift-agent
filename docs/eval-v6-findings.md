# Eval v6: rule 15 (undisclosed UI-copy removal) + entry 09 relabel

Measures the rule-15 deterministic check for an undisclosed removal of
user-visible on-screen text, plus the golden-label correction it forces on
entry 09. Same self-consistency methodology as v4/v5:
`run_selfconsistency_eval.py` — 3 runs + majority vote on the 8 flip-history
entries (01, 03, 04, 06, 09, 13, 14, 22), 1 run on the other 15.

## What changed since v5

1. **Rule 15 + `build_ui_copy_removal_check`** (fetch layer) — deterministic
   diff parse: a removed JSX text node / visible prose line in a
   `.tsx/.jsx/.vue/.svelte` file, where the commit message (or, for a merge,
   the PR body) discloses no removal, and the text is not relocated
   elsewhere in the same diff. Code-level `Flagged` override in
   `enforce_deterministic_rules`, same pattern as rules 11 and 14.
   `test_ui_copy_removal_check.py`: 22 AI-free cases.
2. **Golden entry 09 (`ce67468`) relabelled** `Code complete` → `Flagged`.
   Its diff silently removes the always-visible hint line
   *"An SMS will be sent to the patient's registered number for
   verification."* while the message says only "Add info icon…". The
   architect confirmed `Flagged` is the intended answer for undisclosed
   removal of user-facing copy; `correct_agent_response` rewritten in the
   same plain-flag tone as entries 11/12/19.

False-positive sweep before the run: rule 15 fires on **entry 09 only**
across all 19 real + 4 synthetic entries.

## Full 23-entry table

| entry | golden | runs (post-validator) | outcome | vs golden |
|---|---|---|---|---|
| 01 | Code complete | Code complete ×3 | 3/3 | match |
| 02 | Pending | Pending | — | match |
| 03 | Code complete | Code complete ×3 | 3/3 | match |
| 04 | Code complete | Code complete ×3 | 3/3 | match |
| 05 | Code complete | Code complete | — | match |
| 06 | Code complete | Code complete ×3 | 3/3 | match |
| 07 | Code complete | Code complete | — | match |
| 08 | Code complete | Code complete | — | match |
| 09 | **Flagged** | **Flagged ×3** | **3/3** | **match (deterministic — rule 15)** |
| 10 | Code complete | Code complete | — | match |
| 11 | Flagged | Flagged | — | match |
| 12 | Flagged | Flagged | — | match |
| 13 | Pending | Flagged / Flagged / Pending | 2/3 Flagged | **miss** |
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

**21/23.** Misses: **13, 15**.

| run | score | misses |
|---|---|---|
| v4 (verification carve-out, self-consistency) | 20/23 | 03, 09, 15 |
| v5 (overclaim check + carve-out, merged) | 22/23 | 15 |
| **v6 (rule 15 + entry 09 relabel)** | **21/23** | **13, 15** |

## Entry 09 — resolved, deterministically

3/3 `Flagged`, and it is the code override doing it, not model agreement:

- `build_record('09.json')` → `ui_copy_removal_check.detected` is **True**
  (fetch layer, no AI), one removal:
  `src/screens/doctor/ConsentLookupScreen.tsx` /
  *"An SMS will be sent to the patient's registered number for
  verification."*
- `enforce_deterministic_rules` fed a wrong model status returns `Flagged`
  for `Code complete` / `Tested` / `Pending`.

This closes the v4/v5 free-float on entry 09 (v4: 3/3 Flagged; v5: 2/3 Code
complete — both by luck of the sampling). It is now fixed by construction.

## Entry 13 — regressed on variance, NOT caused by rule 15

v5 had entry 13 at 3/3 `Pending`; v6 is 2/3 `Flagged` (majority `Flagged`,
golden `Pending`). Rule 15 is not involved: `ui_copy_removal_check.detected`
is `False` for entry 13 (its diff touches only `.md`/`.json`/`.jsonl`; no
on-screen copy).

The real cause is the **rule 3/9 vs rule 13 precedence gap**, open and
documented since `eval-v3-findings.md`:

- `sweeping_claim_check` fires on entry 13 — the message uses "entirely" and
  quotes `"Six Agents"`; a repo grep as of the commit still finds
  `"Six Agents"` in `docs/project-state.md` (inside audit-log prose
  describing the fix, not as a live stale header), so `claim_holds` is
  `false`. Rule 9 tells the model to treat that as a real mismatch →
  `Flagged`.
- Rule 13 tells the model that open sub-items #8/#9 (awaiting a human
  decision) make the whole commit `Pending`.
- The contract states no precedence between them, so the model splits.

Entry 13's history across every run: v3 diagnosed the gap; v4 was 2/3
`Pending` (1 `Flagged`); v5 was 3/3 `Pending` (the outlier); v6 is 2/3
`Flagged`. Its true state is a ~coin-flip. v5's 22/23 was carried by the
lucky side of that flip.

### Note: the original run 1 for entry 13 was a `claude -p` timeout

`run_selfconsistency_eval.py` run 1 returned `TimeoutExpired` — entry 13's
diff is 33 KB (the largest in the set) and `call_claude`'s default timeout
is 120 s. Entry 13 was re-run 3× at `timeout=300` to get a clean
3-sample read (`Flagged` / `Flagged` / `Pending`); `results-selfconsistency.jsonl`
row 13 was patched with that read. **Recommendation:** raise
`call_claude`'s default timeout (120 → 180 s) so the largest diffs don't
drop runs.

## Still open

- **Entry 13 — the precedence gap is now non-deferrable if 22+/23 is the
  goal.** Options: (a) state a precedence in the contract (rule 13 wins
  when the "mismatch" is a sweeping-claim hit on text that lives in the
  commit's own audit-log/tracking prose rather than in live UI or code);
  (b) tighten `sweeping_claim_check` so a hit inside the diff's own added
  tracking-log lines doesn't count; (c) review whether `Pending` is even
  the right golden for 13. Deferred 3 rounds; v6 forces the question.
- **Entry 15 — unchanged.** Sweeping claim lives in diff/log content, not
  the commit message.
- **Eval cost / robustness** — 39 calls; raise the `claude -p` timeout
  (above); the freeze-`prompt_contract_layer` option to isolate stages
  from model variance still not taken.
