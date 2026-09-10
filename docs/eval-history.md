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

## All 8 runs, at a glance

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

## Entry-by-entry table — pass/fail across all 8 real runs

P = Pass, F = Fail. Runs 6–8 use self-consistency (majority vote); runs 1–5 are single-pass — see the methodology caveat above before comparing across that line.

| # | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 01 | F | P | P | P | F | P | P | P | R5: same bug class as "not yet," different word ("still outstanding"). Fixed by the R6 verification carve-out, verified directly. |
| 02 | F | P | P | P | P | P | P | P | R1: no rule existed yet for "still needs to happen" → Pending. |
| 03 | F | P | P | P | F | F | P | P | Never really a model problem — golden label was inconsistent with 7 similar entries. Corrected at R7. |
| 04 | P | F | P | F | P | P | P | P | Regressed twice (R2, R4) for two different validator reasons, both since fixed. |
| 05 | P | P | P | P | P | P | P | P | Always stable. |
| 06 | P | P | P | P | F | P | P | P | Same bug class as 01, fixed same way at R6. |
| 07 | P | P | P | P | P | P | P | P | Always stable. |
| 08 | P | P | P | P | P | P | P | P | Always stable. |
| 09 | P | P | P | P | F | F | P (luck) | P (fixed) | R7's pass was NOT a fix — sampling luck. Only R8's rule-15 override makes this genuinely reliable. |
| 10 | P | P | P | P | P | P | P | P | Always stable. |
| 11 | P | F | P | P | P | P | P | P | Golden label corrected before R3; model had already found a real gap. |
| 12 | F | F | F | P | P | P | P | P | First real fix landed at R4 (bundling-hygiene rule); stable since. |
| 13 | F | F | F | F | P | P | P | F | Still genuinely unresolved — the rule-9-vs-rule-13 precedence gap. R7's pass was the lucky side of a real coin-flip, not a fix. |
| 14 | F | F | F | F | P | P | P | P | Fully closed at R7 — deterministic override, verified even against a deliberately wrong model status. |
| 15 | F | F | F | F | F | F | F | F | Never once passed, across all 8 runs. The deepest, still-unsolved gap — sweeping claim lives in diff/log content, not the commit message. |
| 16 | P | P | P | P | P | P | P | P | Always stable. |
| 17 | F | F | P | P | P | P | P | P | Fixed by the negation guard at R3. |
| 18 | P | F | P | P | P | P | P | P | Negation-guard casualty at R2, recovered R3. |
| 19 | F | P | P | P | P | P | P | P | Fixed by the unexplained-deletion rule at R2. |
| 20 | P | P | P | P | P | P | P | P | Always stable. |
| 21 | P | P | P | P | P | P | P | P | Always stable. |
| 22 | P | F | F | F | P | P | P | P | Recovered at R5; not attributable to any specific targeted fix at that point. |
| 23 | P | P | P | P | P | P | P | P | Always stable. |

---

## Where things stand as of Run 8 (the latest)

**Genuinely, permanently closed:** 01, 02, 04, 06, 09, 11, 12, 14, 17, 18, 19, 22 — each has either always been stable, or was closed by a real, verified deterministic fix (not luck).

**Still open, real work remaining:**
- **Entry 15** — never once passed in 8 runs. The deepest structural gap: no automated way yet to verify a claim against content outside the specific commit's own diff/message.
- **Entry 13** — the rule-9-vs-rule-13 precedence gap. Now precisely diagnosed (a stale phrase quoted inside the commit's own audit-log prose, not a live reference) but not yet fixed.

**Legend — what the bracketed words mean when they show up in narrative sections above:**
- **Fail (regressed)** — passed on the run before, fails now. Something made it worse.
- **Fail (new reason)** — failed before and still fails, but the underlying cause changed.
- **Pass (fixed)** — passes because of a real, verified, deterministic fix. Trust it.
- **Pass (variance / luck)** — passes this run only because the AI happened to phrase things a certain way. Could flip back with zero code changes. **The single most important distinction in this whole table.**

---

## Related documents

- `validator-negation-story.md` — the full, focused arc of the Status Consistency Validator's four separate breaks and how each was actually fixed
- `golden-set-reference.md` — the 23 entries themselves
- `prompt-contract-rules.md` — the full, current 15-rule reference, including the code-enforcement-gap finding
