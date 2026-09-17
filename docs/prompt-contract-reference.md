# Prompt Contract — Full Reference (Verified Against Source Code)

*The complete, current rulebook the AI follows — pulled directly from prompt_contract_layer.py's SYSTEM_PROMPT and enforce_deterministic_rules, not reconstructed from memory. 15 numbered rules total. Use this to refresh your memory instead of asking what a rule says.*

---

## The most important finding in this document — read this first

**Updated 2026-09-17 (Run 10):** rule 9 moved from unenforced to code-enforced (`bc4db67`, 2026-09-13) since this section was first written — the finding below described 9/12/13 as unenforced, but only **12 and 13** still are.

**Not every rule that SAYS "status must be Flagged/Pending" actually enforces that in code.** Two rules (12, 13) still use the exact same imperative language as four others (9, 11, 14, 15) — but only 9, 11, 14, and 15 have a real code-level safety net behind them. Rules 12 and 13 rely entirely on the AI choosing to comply, every single time.

**This used to directly explain the project's most persistent instability, and no longer does.** Entry 13's old coin-flip between Pending and Flagged existed because rule 9 (sweeping-claim → Flagged) could fire on the same commit as rule 13 (partial-completion → Pending) with no stated precedence, and neither was code-enforced. Rule 9 becoming code-enforced didn't just close entry 15 — it also closed entry 13's instability in practice, because the fix is correctly gated on `claim_holds: False` (a claim actually disproved), not on `detected` alone. Entry 13's own sweeping-claim mention is `detected` but holds up (`claim_holds: True`), so rule 9 correctly never fires on it, and the two rules stopped colliding. Confirmed stable across Run 9 and Run 10 (`docs/eval-history.md`). Rule 13 itself is still not code-enforced — this is a resolved *symptom*, not a resolved *rule*.

**The pattern to remember: a rule with "status must be X" in its wording is not the same as a rule that's guaranteed to produce X.** Only the code-enforced ones are guarantees. Rules 12 and 13 are the two rules left in that gap — worth watching if either one ever causes a real miss the way 9 did.

---

## All 15 rules, in order

| # | Enforcement | Originating entry |
|---|---|---|
| 1 | AI judgment + reject-only validation gate | Foundational (status vocabulary) |
| 2 | Both — AI judgment on Tested-vs-Code-complete; code hard-override for the `touches_app_code` half | Entry 17 |
| 3 | AI judgment only | Foundational — recurring driver behind entries 01, 03, 14 |
| 4 | Code only (AI told to ignore it) | Not entry-driven — mechanism for the standard follow-up question |
| 5 | AI judgment only | Foundational |
| 6 | AI judgment only | Synthetic entry 20 |
| 7 | AI judgment only (output format) | Not entry-driven |
| 8 | AI judgment only | Synthetic entry 22 |
| 9 | Both — code hard-override, added `bc4db67` (2026-09-13), gated on `claim_holds: False` | Entry 15 (closed for real at Run 9) and, as a side effect, entry 13's instability |
| 10 | AI judgment only | Entries 01 and 03 |
| 11 | Both — code hard-override | Entry 19; retroactively also fixed entry 11's golden label |
| **12** | **AI judgment only — NOT code-enforced, despite "status must be Flagged"** | Entry 12 |
| **13** | **AI judgment only — NOT code-enforced, despite "status must be Pending"** | Entry 13 — no longer unstable in practice (see above), but still not a code guarantee |
| 14 | Both — code hard-override | Entry 14 |
| 15 | Both — code hard-override | Entry 09 |

**Bolded rows are the two remaining unenforced-but-imperative rules** — the project's remaining real risk area, now that rule 9 has moved out of this category.

---

## Rule-by-rule detail

### Rule 1 — Status vocabulary
*"Status must be exactly one of: 'Code complete', 'Tested', 'Pending', 'Flagged'. Never any other word, never a vague synonym like 'done'."*
**Enforcement:** the code doesn't correct a bad answer — it rejects it outright (`parse_model_output` raises an error if the model returns anything outside the four allowed words).

### Rule 2 — Tested vs. Code complete
*"Use 'Tested' only if the commit message or diff explicitly confirms that necessary testing was actually performed and passed — not queued, not routed to a tester, not partially covered while a required step is still outstanding. In every other case where the code looks complete, default to 'Code complete.' Note: touches_app_code is enforced separately in code — if false, 'Tested' isn't available regardless of what you decide here."*
**Enforcement:** the Tested-vs-Code-complete judgment itself is still up to the AI. The `touches_app_code` half is a hard code override.
**History check — has this wording ever changed?** No. Verified against git history: the decision logic is byte-identical to the very first version (v1, commit `25a198a`). Two edits happened since, both purely cosmetic (an em-dash-removal pass, and one sentence appended pointing at the new code override) — the actual criteria for when "Tested" applies has never been rewritten.

### Rule 3 — Claim-vs-diff comparison
*"Compare every claim in the commit message and PR description against the actual diff. If a claim isn't supported (overstates scope, claims unverified testing), state the mismatch as a plain fact — never guess why. When a real mismatch exists, set status to Flagged."*
**Enforcement:** AI judgment only. This is the foundational rule behind entries 01, 03, and 14's original catches.

### Rule 4 — Follow-up question
The AI is explicitly told to ignore this rule number — it's a placeholder. **Fully code-driven:** the follow-up question ("when/how will this be tested, and what's the ETA?") gets appended automatically to any "Code complete" narrative that doesn't already have one.

### Rule 5 — No invented completion percentages
*"Do not estimate a percent-complete number based on diff size or impression. No acceptance-criteria data is supplied in this run, so completion can't be computed — don't attempt it."*
**Enforcement:** AI judgment only.

### Rule 6 — Unattributed commits
*"If a commit can't be matched to a story, don't guess. If the commit is self-evidently a process/governance/docs action, it's fine to classify status normally and just note no story was needed. If the purpose genuinely can't be determined, status must be Flagged, and the narrative must say this needs human input — never fabricate a plausible purpose."*
**Enforcement:** AI judgment only. Test case: synthetic entry 20 (the "fix bug," no-context commit).

### Rule 7 — Output format
*"One plain paragraph, standup tone, readable by both technical and non-technical people. No code syntax, no undefined jargon."*
**Enforcement:** AI judgment only.

### Rule 8 — No false confidence
*"Never phrase anything as if you personally verified, ran, or confirmed something you didn't actually check — you only read a diff and a message, you didn't execute anything. Hedge honestly."*
**Enforcement:** AI judgment only. Test case: synthetic entry 22 (the bare "QA verified" claim).

### Rule 9 — Sweeping-claim verification
*"When a commit makes a sweeping claim ('anywhere,' 'everywhere,' 'no longer exists') about specific text, a repo search has already been run — this is verified fact, not something to re-check. If the search shows the claim doesn't hold (`claim_holds: false`), treat that as a real mismatch under rule 3."*
**Enforcement:** Both — code hard-override, added `bc4db67` (2026-09-13). Gated specifically on `claim_holds: False` — an actual disproved claim — not on `detected` alone, so a sweeping claim that's detected but still holds up (entry 13's "Six Agents" mention) correctly doesn't force anything. Closed entry 15 for real: first pass in 9 runs at Run 9, 3/3 stable at Run 10 (`docs/eval-history.md`).

### Rule 10 — PR-timing separation
*"A PR's description describes the aggregate, final state as of merge time — not this individual commit's own point in time. Don't treat a PR-level claim as contradicting a narrower or earlier claim inside this commit purely because they differ. This isn't license to ignore PR claims entirely — if the PR's own claim doesn't hold up against the code, that's still a rule-3 mismatch."*
**Enforcement:** AI judgment only. Fixed entries 01 and 03's false PR-timing contradictions.

### Rule 11 — Unexplained whole-file deletions
*"If a commit deletes a file entirely and doesn't name it in the message, status must be Flagged — routine traceability gap, not a sign of anything serious. Same calm, unalarmed tone as any other flag."*
**Enforcement:** Both — code hard-override. Fixed entry 19; also retroactively caught the real gap that got entry 11's golden label corrected.

### Rule 12 — Bundling hygiene ⚠️ unenforced
*"If a diff bundles unrelated content (a code fix plus a standalone article, write-up, or something meant to be read outside the codebase), flag it — even if it covers the same bug. Routine engineering docs (test files, changelog notes, tracking-log updates) don't count as unrelated."*
**Enforcement:** AI judgment only, despite "status must be Flagged." Fixed entry 12's original miss, but with no code guarantee behind it.

### Rule 13 — Partial completion → Pending ⚠️ unenforced
*"If a commit frames its content as multiple sub-items, and at least one is explicitly still open, the overall status must be Pending — even if everything else is done. One open sub-item is enough; don't average toward the majority. This is different from a single item just awaiting one verification step (which stays Code complete under rules 1-2)."*
**Enforcement:** AI judgment only, despite "status must be Pending." **Used to be exactly why entry 13 was unstable** — rule 9 could fire on the same commit with no stated precedence, and neither was code-enforced. Rule 9 becoming code-enforced (correctly gated on `claim_holds: False`) means it no longer fires on entry 13 at all, so the collision stopped happening — entry 13 has been stable, plain `Pending`, across Runs 9 and 10. Rule 13 itself is still not code-enforced; this is a resolved symptom, not a resolved rule, and worth revisiting if a future commit exposes the gap differently.

### Rule 14 — Deterministic overclaim detection
*"When a commit claims something was 'added'/'introduced'/'new,' this has already been checked against real git history in code. If detected, the named thing already existed — state the plain fact in your own words, calm tone, status Flagged."*
**Enforcement:** Both — code hard-override. Closes entry 14's silent-miss risk for good.

### Rule 15 — Undisclosed UI-copy removal
*"When a commit removes on-screen text (a label, hint, or message) without the commit message mentioning any removal, this has already been determined in code. State plainly which text was removed and that the message doesn't mention it — calm tone, the removal may well be intentional, just not disclosed. Doesn't apply to removed code, comments, styles, or imports — and it's distinct from rule 11's whole-file case."*
**Enforcement:** Both — code hard-override. Closes entry 09's free-floating instability for good.

---

## The third enforcement stage — outside this file entirely

There's one more layer that isn't part of the prompt contract at all: **`status_consistency_validator.py`**, a pure text-matcher that runs *after* the AI has already produced its answer. It doesn't read any rule numbers — it just scans the AI's own finished paragraph for phrases like "still outstanding" or "not yet complete," and flips the status word if it contradicts what the paragraph itself says. See `eval-v2-findings.md` for its negation-blindness history, continued in `eval-v3-findings.md` and `eval-v4-findings.md`.

**Full pipeline, three distinct enforcement mechanisms:**
1. **SYSTEM_PROMPT rules** — instructions given to the AI before it answers (all 15 rules)
2. **`enforce_deterministic_rules`** — code that runs immediately after, hard-overriding the status for rules 2 (partial), 4, 9, 11, 14, 15. Also returns the model's answer both before and after this stage (`raw_status`/`raw_narrative` vs. the final `status`/`narrative`), added Run 10 — the first point in the pipeline where it's possible to tell whether a rule actually changed anything or the model already agreed with it.
3. **`status_consistency_validator`** — a separate, later pass that checks the AI's paragraph against itself, independent of rule numbers entirely

---

## What this document changes about your remaining priority list

This used to say entry 13's fix was making rule 9 code-enforced — **that's done** (`bc4db67`), and it closed both entry 15 and entry 13's instability. The remaining gap in this specific file is narrower now: rules 12 and 13 are still AI-judgment-only, worth revisiting only if either one causes a real, reproducible miss the way rule 9's absence did.

The project's actual open findings right now live in `eval-v10-findings.md`, not in this rulebook — they're not prompt-contract gaps at all. Entry 03 is a bug in `status_consistency_validator.py` (the third enforcement stage, outside this file — see above), and entry 22 is a claim type (an unverifiable "QA verified") that none of the existing rules or checks are built to catch, which would need a new rule 16-style check, not a fix to an existing one.

---

## Related documents

- `golden-set-reference.md` — the 23 entries these rules are tested against
- `eval-history.md` — all 10 real eval runs, verified against git history
- `eval-v2-findings.md` — the separate, third enforcement stage's own history (negation-blindness arc; continued in `eval-v3-findings.md`, `eval-v4-findings.md`)
- `eval-v10-findings.md` — the third enforcement stage's current open bug (validator verification-context carve-out unreliable by construction) and the unrelated entry-22 gap
- `session-state.md` — current status and open decisions
