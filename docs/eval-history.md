# Eval Run History — Living Record (Verified Against Git History)

*One place to see every eval run, why it happened, and what it found. All data below was pulled directly from git commits and results files by Claude Code — not reconstructed from memory. Use this to refresh your memory before talking about this project.*

---

## Read this first — naming caveats

The labels "v1" through "v6" are informal, assigned after the fact in various findings docs — not consistent, official version numbers. A few important corrections to hold onto:

- **There is exactly one "v4," and it's the 20/23 self-consistency run.** There is no separate "v4 (18/23)" or "v4.1" — that confusion came from an earlier session. The 18/23 run some prior conversation called "v4" is actually a *different* run (commit `ac2708c`), informally "v3 post 'not yet' fix."
- **Three separate runs all scored 18/23**, with three different sets of failures each time (`6ec2f71`, `37856c1`, `ac2708c`). Easy to conflate — they are not the same run.
- **A methodology break exists between run 5 and run 6.** Runs 1–5 are single-pass (one AI call per entry). Runs 6–8 use self-consistency checking (3 calls + majority vote on historically unstable entries). **Pass rates are not directly comparable across that line** — a 20/23 self-consistency result is not the same kind of measurement as an 18/23 single-pass result.
- **The golden set itself changed 4 times mid-history** (entries 14, 11, 03, 09 each had their label corrected at different points). A "miss" on an early run isn't necessarily the same disagreement as a later "miss" on the same entry number, since what counts as correct sometimes moved.

---

## All 10 runs, at a glance

| # | Label | Commit | Date | Pass rate | Methodology |
|---|---|---|---|---|---|
| 1 | "v1" (baseline) | de9687d | 2026-08-25 | 14/23 | single-run |
| 2 | "v2" (first re-run) | 9c90b7e | 2026-08-25 | 14/23 | single-run |
| 3 | "v2.1" (second re-run) | 6ec2f71 | 2026-08-25 | 18/23 | single-run |
| 4 | "v3" | 37856c1 | 2026-08-26 | 18/23 | single-run |
| 5 | "v3 post 'not yet' fix" | ac2708c | 2026-08-27 | 18/23 | single-run |
| 6 | "v4" (the only v4) | d9c0219 | 2026-09-09 | 20/23 | self-consistency |
| 7 | "v5" | db6c7da | 2026-09-09 | 22/23 | self-consistency |
| 8 | "v6" | 3e20099 | 2026-09-10 | 21/23 | self-consistency |
| 9 | rule-9 confirmation | 961b61d | 2026-09-13 | 21/23 | self-consistency |
| 10 | "v10" (Drift Trace dashboard) | d1811f0 | 2026-09-17 | 21/23 | self-consistency (3x on 01/03/06/09/15/17) |

---

## Run 1 — de9687d · 14/23 · "v1" (baseline)

**Changed going in:** first eval of prompt contract v1 (no fixes yet) against the 23-entry golden set.

**Failed (9):** 01, 02, 03, 12, 13, 14, 15, 17, 19

**Why:** 01/14 — the AI caught real contradictions the golden set didn't account for (defensible AI, wrong golden). 02 — no rule existed for "commit done, feature not usable yet." 03 — claim-vs-claim conflict, "not yet tested" not yet properly separated. 12/13/19 — genuine gaps (bundling hygiene, partial-completion, missing co-author trailer). 15 — the discrepancy lives in a file the diff didn't touch (architectural limit, unsolved to this day). 17 — "Tested" was undefined for a commit with no app code.

**Rules 3 and 8 (never invent, never fake confidence) held 100% across all 23**, including every disagreement — the single most important finding of this run.

---

## Run 2 — 9c90b7e · 14/23 · "v2, first re-run"

**Changed going in:** five contract changes — `touches_app_code` hard-block on "Tested," sweeping-claim repo verification, PR-metadata merge-time labeling, the Status Consistency Validator added as its own stage, unexplained-deletion flagging. Plus golden entry 14 corrected Code complete → Flagged.

**Failed (9):** 04, 11, 12, 13, 14, 15, 17, 18, 22

**Why:** headline flat, but composition shifted — 01/02/03/19 fixed by the five changes. New problems on 17/18: the validator was negation-blind, flipping "no outstanding work" to Pending. 04 — model variance on "follow-up review step" phrasing. 14 — variance on a complex bundled commit. 12/22 — bundling-hygiene and unverifiable-"QA verified" gaps, untouched this round. 11 — golden set still mislabeled (fixed next run).

---

## Run 3 — 6ec2f71 · 18/23 · "v2.1"

**Changed going in:** validator negation-blindness fixed (widened to an 8-word lookback); golden entry 11 corrected Code complete → Flagged.

**Failed (5):** 12, 13, 14, 15, 22

**Why:** 17/18 recovered thanks to the negation guard. 12 still a bundling gap. 13's partial-completion issue still not an AI-facing rule. 14 — variance. 15 — scope limit. 22 — unverifiable-claim skepticism not holding.

---

## Run 4 — 37856c1 · 18/23 · "v3"

**Changed going in:** prompt-contract rules 12 (bundling hygiene) and 13 (partial completion → Pending) added.

**Failed (5):** 04, 13, 14, 15, 22

**Why — "one fix, one new miss, net flat":** rule 12 fixed case 12 (first real match). Case 04 regressed for an unrelated, pre-existing reason (validator flipping "not yet tested" on a legitimate rule-2 case). Rule 13's reasoning fired correctly on case 13, but the model still escalated to Flagged, because rule 3 and rule 13 both apply with no stated precedence between them — still open, still unresolved as of the latest run. 14/15/22 unchanged.

---

## Run 5 — ac2708c · 18/23 · "v3 post 'not yet' fix"

**Changed going in:** removed the bare "not yet" trigger from the validator (it was matching rule 2's legitimate "not yet tested"); added the first permanent, 16-case AI-free unit-test suite for the validator — a new concept for this project.

**Failed (5):** 01, 03, 06, 09, 15

**Why — genuinely noisy, not a real regression:** 04/13/14/22 newly passing, 01/03/06/09 newly failing, net zero change in the headline. 01 and 06 broke on the exact same bug class as "not yet," just different words ("still outstanding," "still needs a QA pass") flipping Code complete → Pending. Roughly 35% of entries churned pass/fail state between this run and the last, attributed to model run-to-run variance — proof a flat headline number can hide real change underneath. 15 remains the persistent scope-limit case.

---

## Run 6 — d9c0219 · 20/23 · "v4" (the only v4)

**Changed going in:** the "not yet" patch generalized into a phrase-agnostic verification-word carve-out in the validator (any trigger phrase near a verification word like tested/QA/device gets suppressed); 20-case unit suite. **First self-consistency run** — 3 runs + majority vote on entries 01/03/04/06/09/13/14/22, single-run on the rest.

**Failed (3):** 03, 09, 15

**Why:** the carve-out demonstrably removed 01 and 06 from the miss list — verified directly by re-checking the real generated sentences with and without the fix. 13/14/22 recovered via majority vote (they were genuinely 2/3 unstable, not fixed by any specific change). 03 and 09 are now understood as **stable, 3/3 model-vs-golden-label disagreements** — not validator errors, not run-to-run noise. 15 unchanged.

---

## Run 7 — db6c7da · 22/23 · "v5"

**Changed going in:** deterministic overclaim check — fetch-layer detection of "added"/"introduced" claims against real git history, wired into the prompt contract as a code-level Flagged override (rule 14). Golden entry 03 relabelled Pending → Code complete in this same commit (the golden answer itself was inconsistent with 7 similar entries).

**Failed (1):** 15

**Why:** 03 now matches — the model was already saying "Code complete" 3/3 all along; only the golden label was wrong. Entry 14 now hits 3/3 Flagged, and verified deterministic (the override was tested by feeding it a deliberately wrong model status and confirming it still forced Flagged every time). **Entry 09 flipped to passing by luck of the sampling (2/3 Code complete), not by any fix** — flagged honestly as unresolved instability, not a resolved case. 15 remains the only real, unaddressed gap.

---

## Run 8 — 3e20099 · 21/23 · "v6"

**Changed going in:** deterministic rule 15 — flags undisclosed removal of user-facing, on-screen copy (extends the existing whole-file-deletion rule to cover removed text *within* a file). Golden entry 09 relabelled Code complete → Flagged, matching the newly-correct, deterministic behavior.

**Failed (2):** 13, 15

**Why:** entry 09 now hits 3/3 Flagged deterministically — the multi-run free-float that plagued it since run 5 is permanently closed. A false-positive sweep confirmed the new rule fires on entry 09 only, zero regressions elsewhere. **Entry 13 fell to the wrong side of its long-standing coin-flip this run** (2/3 Flagged) — not caused by rule 15, which correctly doesn't fire on entry 13 at all (its diff is governance docs, not UI copy). The real cause remains rule 9 (sweeping-claim check) vs. rule 13 (partial completion) having no stated precedence — traced this run to a more precise root cause: the sweeping-claim check fires on a stale phrase quoted *inside the commit's own audit-log prose*, not a live stale reference. Entry 13's history across self-consistency runs: 2/3 Pending (run 6) → 3/3 Pending, the lucky outlier (run 7) → 2/3 Flagged (run 8). Genuinely unresolved, not newly broken.

---

## Run 9 — 961b61d · 21/23 · rule-9 confirmation

**Changed going in:** rule-9 hard override added (`bc4db67`) — forces `Flagged` when `sweeping_claim_check` finds a verified-false claim, gated on `claim_holds: False` specifically, not on `detected` alone.

**Failed (2):** 05, 22

**Why:** **entry 15 passes for the first time in 9 runs** — `Flagged`, matching golden, and this time it's a real code-level fix, not luck: the override forces it regardless of what the model says on its own. Entry 13 held 3/3 `Pending`, confirming it's unaffected by the new override (correctly gated on `claim_holds`, not `detected`). Entry 05 failed on an infra error (`ERROR`, transient `claude -p` issue that week), not a real regression. Entry 22 split three ways across its 3 runs (`Tested`, `Code complete`, `Flagged`) — no majority, genuinely unstable, unrelated to this change (`sweeping_claim_check.detected` confirmed `False`).

---

## Run 10 — d1811f0 · 21/23 · "v10" (Drift Trace dashboard)

**Changed going in:** nothing to the pipeline itself — this run built `run_dashboard_eval.py` / `build_drift_trace.py` (the Drift Trace dashboard) and, in the course of building it, added `raw_status`/`raw_narrative` capture to `generate_status_update` so the model's answer *before* rule enforcement is visible for the first time. 6 entries with a history of instability (01, 03, 06, 09, 15, 17) run 3x independently each; the rest once.

**Failed (2):** 03, 22

**Why:** **entry 15 confirmed stable, 3/3 `Flagged`** — the rule-9 fix from Run 9 holds. Entry 13 back to a clean, single-run `Pending` — the rule-9-vs-rule-13 precedence gap that plagued runs 6–8 has not recurred since rule 9 was gated correctly. **Entry 03 is a newly-diagnosed, different problem, not a repeat of any earlier miss on this entry**: the model's raw answer was `Code complete` (correct) in all 3 runs, but `status_consistency_validator` flipped it to `Pending` in 2 of 3 — traced to the exact mechanism (a quote mark broke a verification-word match in one run; a one-word-too-far distance missed it in another). See `docs/eval-v10-findings.md` for the full trace. **Entry 22 fails again**, third time now (also unstable at Run 9) — an unverifiable "QA verified" claim with no test evidence, which none of the four deterministic checks are built to catch. Two consecutive runs (9 and 10) confirm this is a real, persistent gap, not one-off noise.

---

## Why multi-run checking for unstable entries — the real term, and why it's legitimate

**The technique:** for entries with a track record of flip-flopping, run the same commit through the AI 3 times instead of once, and take the majority answer. If there's no majority (e.g. 3 different answers), treat that as a signal the commit is genuinely too ambiguous for automation — route it for mandatory human review instead of trusting any single pass.

**The real name for this: "self-consistency checking."** This is not something improvised for this project — it's a recognized, standard technique for evaluating LLM-based systems, used in real production settings.

**Where it's actually used in enterprise practice:**
- High-stakes classification (fraud detection, content moderation, medical triage support) — often requires agreement across multiple samples above a threshold before auto-acting
- AI-assisted code review and compliance tools — same pattern: inconsistency escalates to a human instead of being auto-resolved
- Regulated/audited domains (healthcare, finance) — inconsistency between repeated runs is treated as a real signal worth investigating, not noise to ignore

**What it actually fixes, precisely — worth being accurate about this distinction:** it does NOT make the model itself more consistent. Nothing fully solves that. What it does is tell you *where* to trust a single answer and *where* not to — so a human gets pulled in exactly on the cases that need it, instead of on everything.

**Why applied selectively, not to all 23 entries:** it costs more compute — running "everything 3-5 times, always" doesn't scale and isn't necessary. Entries with zero history of flip-flopping don't need it; entries that have already shown instability do.

---

## Entry-by-entry table — pass/fail across all 10 real runs

P = Pass, F = Fail. Runs 6–10 use self-consistency (majority vote); runs 1–5 are single-pass — see the methodology caveat above before comparing across that line.

| # | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | F | P | P | P | F | P | P | P | P | P | R5: same bug class as "not yet," different word ("still outstanding"). Fixed by the R6 verification carve-out, verified directly. 3/3 stable at R10. |
| 02 | F | P | P | P | P | P | P | P | P | P | R1: no rule existed yet for "still needs to happen" → Pending. |
| 03 | F | P | P | P | F | F | P | P | P | F | Corrected at R7 (golden label was wrong, not the model). **New, different failure at R10**: the validator's own text-match bug, not a repeat of the golden-label issue — see `eval-v10-findings.md`. |
| 04 | P | F | P | F | P | P | P | P | P | P | Regressed twice (R2, R4) for two different validator reasons, both since fixed. |
| 05 | P | P | P | P | P | P | P | P | F | P | R9's fail was a transient `claude -p` infra error (`ERROR`), not a real regression — passed cleanly at R10. |
| 06 | P | P | P | P | F | P | P | P | P | P | Same bug class as 01, fixed same way at R6. 3/3 stable at R10. |
| 07 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 08 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 09 | P | P | P | P | F | F | P (luck) | P (fixed) | P | P | R7's pass was NOT a fix — sampling luck. R8's rule-15 override made it reliable; 3/3 stable at R9 and R10. |
| 10 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 11 | P | F | P | P | P | P | P | P | P | P | Golden label corrected before R3; model had already found a real gap. |
| 12 | F | F | F | P | P | P | P | P | P | P | First real fix landed at R4 (bundling-hygiene rule); stable since. |
| 13 | F | F | F | F | P | P | P | F | P | P | R8's fail was the rule-9-vs-rule-13 precedence gap. **Not recurred since** — 3/3 Pending at R9, clean Pending at R10, both after rule 9 landed correctly gated on `claim_holds`. |
| 14 | F | F | F | F | P | P | P | P | P | P | Fully closed at R7 — deterministic override, verified even against a deliberately wrong model status. |
| 15 | F | F | F | F | F | F | F | F | P | P | **Closed for real at R9** — the rule-9 hard override (`bc4db67`) forces `Flagged` regardless of the model's own answer. 3/3 stable at R10. First pass in 9 runs, and it's a verified fix, not luck. |
| 16 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 17 | F | F | P | P | P | P | P | P | P | P | Fixed by the negation guard at R3. 3/3 stable at R10. |
| 18 | P | F | P | P | P | P | P | P | P | P | Negation-guard casualty at R2, recovered R3. |
| 19 | F | P | P | P | P | P | P | P | P | P | Fixed by the unexplained-deletion rule at R2. |
| 20 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 21 | P | P | P | P | P | P | P | P | P | P | Always stable. |
| 22 | P | F | F | F | P | P | P | P | F | F | Recovered at R5 by chance, not a targeted fix — and it shows: **failed again at R9 (3-way split) and R10**. Genuinely unresolved: an unverifiable "QA verified" claim with no test evidence, which no current check catches. |
| 23 | P | P | P | P | P | P | P | P | P | P | Always stable. |

---

## Where things stand as of Run 10 (the latest)

**Genuinely, permanently closed:** 01, 02, 04, 05, 06, 09, 11, 12, 13, 14, 15, 17, 18, 19, 23 — each has either always been stable, or was closed by a real, verified deterministic fix (not luck). **15 and 13 moved into this list at R9/R10** — the rule-9 override (`bc4db67`) closed 15 for real (first pass in 9 runs) and the same fix's correct gating means 13 hasn't recurred since.

**Still open, real work remaining:**
- **Entry 03** — a newly-diagnosed problem, unrelated to its earlier (already-fixed) golden-label issue. `status_consistency_validator`'s verification-context carve-out is a word-distance heuristic over freely-generated text, and it's unreliable by construction — traced exactly why in `docs/eval-v10-findings.md`. Confirmed one-directional (can only push toward `Pending`, never fabricate `Code complete`), so it's a visible, safe-direction soft spot, not a silent one.
- **Entry 22** — passed R5–R8 by chance (never a targeted fix), then failed the last two runs checked (R9, R10). An unverifiable "QA verified" claim with zero test evidence attached — none of the four deterministic checks are built to catch this claim type. A distinct gap from entry 03, not the same root cause.

**Legend — what the bracketed words mean when they show up in narrative sections above:**
- **Fail (regressed)** — passed on the run before, fails now. Something made it worse.
- **Fail (new reason)** — failed before and still fails, but the underlying cause changed.
- **Pass (fixed)** — passes because of a real, verified, deterministic fix. Trust it.
- **Pass (variance / luck)** — passes this run only because the AI happened to phrase things a certain way. Could flip back with zero code changes. **The single most important distinction in this whole table.**

---

## Related documents

- `eval-v2-findings.md` — the arc of the Status Consistency Validator's negation-blindness breaks and how each was fixed (continued in `eval-v3-findings.md`, `eval-v4-findings.md`)
- `eval-v10-findings.md` — Run 10's headline finding: the validator's verification-context carve-out is unreliable by construction, traced against the real narratives
- `golden-set-reference.md` — the 23 entries themselves
- `prompt-contract-reference.md` — the full, current 15-rule reference, including the code-enforcement-gap finding
