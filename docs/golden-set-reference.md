# Golden Set — Full Reference (All 23 Entries)

*Plain-language version of the 23 saved answer-key entries. Use this to refresh your memory instead of asking what was decided — everything here is already final and saved.*

---

## Clean, single-purpose commits (1–10) — straightforward, no disagreements in eval

| # | What happened | Status |
|---|---|---|
| 1 | Fixed login pointing to a dead server address | Code complete |
| 2 | Swapped demo tunnel service; front-end follow-up still needed | Pending |
| 3 | Fixed tunnel warning page; not yet tested on a real device | Pending |
| 4 | Built new doctor screen for cross-provider consent lookup | Code complete |
| 5 | Added loading spinner to patient lookup | Code complete |
| 6 | Softened "patient not found" error card styling | Code complete |
| 7 | Added last-visit date to patient card | Code complete |
| 8 | Made Request Access button always visible, greyed out until match | Code complete |
| 9 | Added info icon explaining SMS consent process | Code complete |
| 10 | Updated placeholder sample names | Code complete |

## Verified against real code (11–19) — required checking the actual diff, not just the message

| # | What happened | Status | Note |
|---|---|---|---|
| 11 | Reworked hook governance into 5 phases, undocumented but verified via diff | Code complete | |
| 12 | Fixed startup deadlock; bundled an unrelated draft article | Code complete | Hygiene issue flagged separately, not a code problem |
| 13 | Governance audit — 2 items closed, 2 still open | Pending | |
| 14 | Bundled release (OTP resend, API wiring, bug fixes) | Code complete | Eval found the model actually caught a real overclaim here — see `eval-history.md` |
| 16 | Documentation-only log entry | No app behavior changed | |
| 17 | Investigated a suspected bug, no code changed | Code complete | Eval revealed a genuine rule-wording gap — see `eval-history.md` |
| 18 | Reverted a prior fix after its assumption proved wrong | Code complete | |
| 19 | Removed a screen entirely, no reason given | Flagged | Missing AI-signature line + no stated reason — see `eval-history.md` |

## Discrepancy found in the repo's own history

| # | What happened | Status |
|---|---|---|
| 15 | Merge commit claims "no references remain" — two actually do, in an untouched file | Flagged |

## Constructed edge cases (not real MedRecord commits — built to test specific failure modes)

| # | What it tests | Status |
|---|---|---|
| 20 (synthetic-001) | Zero usable metadata — junk message, junk branch, no story link | Flagged |
| 21 (synthetic-002) | Optimistic self-reporting — claims "all edge cases handled," diff shows only one | Flagged |
| 22 (synthetic-003) | Unverifiable claim — "QA verified" with no test files or CI run to back it up | Flagged |
| 23 (synthetic-004) | AI-authored commit claims "no behavioral change" — diff shows a real logic change | Flagged |

---

## Where to look next

- **What the eval run found when the AI was tested against these 23** → see `eval-history.md`
- **The rules the AI follows when generating its own answer** → see `prompt-contract-reference.md`
- **The fetch script itself** → see `fetch_layer.py` (heavily commented) in the repo root
- **Current status and open decisions** → see `session-state.md`
