# Session state — resume here

**Canonical resume file.** Updated at the end of each session. The dated
`docs/session-handoff-YYYY-MM-DD.md` files are frozen per-session snapshots;
this one is the living pointer.

---

## Resuming from

### Session 9 (2026-09-17) — eval-v10, Drift Trace dashboard, repo-wide consistency pass, LinkedIn write-up

**Resume point:** everything from this session is merged to `main` and
pushed (`f5c5751`), matching `origin/main`. No open branch, nothing
pending. If continuing the eval work, start with the open decision below
(what, if anything, to do about the validator's word-distance bug and the
entry-22 gap). If continuing the portfolio/LinkedIn thread, the post is
drafted and ready to post, and a private "Status-Drift-Agent Talking
Points" Claude Doc exists as a FAQ companion (not in this repo,
deliberately, per the user's instruction).

**What happened, in order:**
1. Resolved session 8's open decision: ran the full 23-entry eval fresh
   (new script, `run_dashboard_eval.py`) instead of trusting the stale
   2026-09-09 `results.jsonl`, with 3 independent runs on the 6
   historically-variable entries (01, 03, 06, 09, 15, 17) to separate
   genuine misses from one-off model wording.
2. Added `raw_status`/`raw_narrative` capture to `generate_status_update`
   (`prompt_contract_layer.py`) — the AI's answer before rule enforcement
   had never been recorded anywhere before this; now every eval run
   captures it automatically (flows through `run_golden_eval.py`'s
   existing whole-dict write to `results.jsonl`, no other change needed).
3. **Real finding, `docs/eval-v10-findings.md`:** 21/23. Entry 03's raw AI
   answer was correct (`Code complete`) in all 3 runs, but
   `status_consistency_validator` flipped it to `Pending` in 2 of 3 —
   traced to the exact mechanism (a quote mark around `'tested'` broke a
   verification-word set-membership check in one run; a one-word-too-far
   distance missed it in another). Concluded this is a meaning-judgment
   problem being approximated by word-distance over freely-generated
   text, not fixable by widening a threshold — documented as open rather
   than patched. Confirmed one-directional/safe:
   `validate_status` can only ever move a status *toward* `Pending`,
   never fabricate `Code complete` or clear a `Flagged`. Entry 22
   (synthetic, unverifiable "QA verified" claim) also failed — a
   distinct gap, no check built for it; confirmed persistent (also failed
   at session 6's rule-9-confirmation run, a 3-way split with no
   majority).
4. Built `run_dashboard_eval.py` + `build_drift_trace.py` (checked in,
   fully self-contained — the earlier scratchpad version depended on
   reading another scratchpad file that wouldn't exist next session),
   generating `eval_output/drift-trace.html`: a 4-stage trace (Layer 2
   checks → AI raw read → rule enforcement → validator) for all 23
   entries. Published as a Claude Artifact, shared publicly by the user
   via its own share menu, linked from the README.
5. **README overhaul**: the eval-results section was still describing
   entries 13 and 15 as open problems from `eval-v6` — both had been
   closed since rule 9 landed (session 6, `bc4db67`), pre-dating this
   session but never reflected in the README. Replaced with the current,
   real state (21/23, entries 03 and 22 open), documented rules
   9/11/14/15 in the pipeline description (previously not mentioned at
   all despite being the most interesting deterministic logic in the
   project), added an Observability section explaining the
   Langfuse-vs-Drift-Trace split (call-level cost/prompt visibility vs.
   pipeline-decision visibility — deliberately not overlapping).
6. Merged `eval-summary-line` → `main` `--no-ff` (`f5c5751`), pushed. All
   5 unit suites green throughout, checked again post-merge.
7. **User asked for a whole-repo consistency check — this surfaced real,
   pre-existing staleness, not just this session's own gaps:**
   - `docs/eval-history.md` stopped at Run 8 (2026-09-10). Added Run 9
     (the rule-9 confirmation run, `961b61d`, previously undocumented in
     this file even though the commit existed) and Run 10 (this
     session), with full entry-by-entry table updates and a corrected
     "where things stand" section (13 and 15 moved to closed; 03 and 22
     are the real open items now).
   - `docs/prompt-contract-reference.md` was written before rule 9
     existed — it stated rule 9 was AI-judgment-only and named it as the
     direct cause of entry 13's instability. Corrected throughout: rule 9
     is code-enforced (`bc4db67`), and entry 13's instability resolved as
     a side effect of that fix's correct gating (`claim_holds: False`,
     not `detected` alone) rather than being fixed directly — rule 13
     itself is still not code-enforced.
   - `docs/golden-set-reference.md` had **five wrong status values**,
     found by diffing every row against the actual `golden-set/*.json`
     files rather than trusting the doc's own prose: entry 3 (said
     `Pending`, actually `Code complete` — stale since the `eval-v5`
     relabel), entries 11 and 14 (both said `Code complete`, actually
     `Flagged` — stale since golden-label corrections that predate this
     project's session-tracking entirely), entry 12 (said `Code
     complete`, actually `Flagged`), entry 16 (said a non-canonical "No
     app behavior changed" instead of `Code complete`). All fixed. This
     is the one that most directly validates doing the check — this repo
     had been citing wrong "correct answers" from its own answer key for
     an unknown number of sessions before anyone noticed.
8. LinkedIn post drafted and refined with the user via the
   `linkedin-content-mentor` skill: corrected an early framing that would
   have overstated technical depth (kept it at evaluation-design/judgment
   altitude, not implementation detail, per the user's non-developer
   identity guardrails), and corrected a misattribution — the user
   follows Hamel Husain and Shreya Shankar's public writing/podcasts on
   AI evals, not their paid Maven course, verified against their actual
   published work (the "who validates the validators" parallel to entry
   03's finding is genuine, checked against Shreya Shankar's real paper,
   not assumed). Final post covers both open issues (03 and 22). A
   private Claude Doc ("Status-Drift-Agent Talking Points") was created
   as a FAQ/talking-points companion — deliberately not checked into this
   repo, per the user's instruction.

**Where things actually stand, cleanly, as of this session's end:**
- `main` @ `f5c5751`, pushed, matches `origin/main`. Working tree clean.
- All 5 AI-free unit suites green.
- The golden-set answer key, eval history, and prompt-contract reference
  docs are now verified accurate against source (git commits and the
  actual `golden-set/*.json` files) — not just internally consistent with
  each other, which is the check that was skipped before and let the
  golden-set-reference errors survive undetected.
- Two real, open pipeline issues remain, both documented rather than
  quietly patched: entry 03 (validator word-distance bug,
  `docs/eval-v10-findings.md`) and entry 22 (unverifiable-claim gap, no
  check built yet).

---

### Session 8 (2026-09-16) — Langfuse validator-visibility assessment + eval summary line

**Resume point:** picking this back up fresh tomorrow. Nothing merged to
`main` this session. Start with the open decision below (fresh eval run
vs. existing `results.jsonl` for a portfolio dashboard) before building
anything.

**What happened:** user asked whether `status_consistency_validator.py`'s
decision (fired / matched phrase / pre- and post-validator status) should
be made visible in Langfuse, since only the AI-call step is traced today
and the validator step runs after it as a black box. Investigated the
actual call path (`call_claude`'s `trace_id` is generated and consumed
entirely inside `_trace_live_call` and never returned to
`generate_status_update` or its callers) and the actual usage pattern
(`run_golden_eval.py` calls `validate_status` directly after
`generate_status_update`, outside any traced scope). Conclusion given to
the user: skip Langfuse instrumentation for now — entry 13's
rule-9-vs-13 precedence gap is the real open priority, not this; nesting
a span or patching the trace output both require threading `trace_id`
out of `call_claude`, which is real plumbing, not a toggle; and the data
already exists locally — `run_golden_eval.py` already writes
`consistency_correction` (`original_status`, `matched_phrases`) into
`eval_output/results.jsonl`, and `score_golden_eval.py` already prints it
per row.

**Small change made:** `score_golden_eval.py` now also prints an
end-of-run summary block — how many entries the validator corrected and
which ones — on top of the existing per-row correction column. Committed
on branch `eval-summary-line` (`28203f3`), **not merged to `main`, not
pushed** (small WIP branch, user asked to wind down before deciding next
steps).

**Where it turned:** the user's actual goal is broader than eval
convenience — they want this captured in a way that keeps the portfolio
story complete (per this repo's "Positioning" objective in
`/home/rdeva/CLAUDE.md`), not just a terminal print. Landed on wanting an
HTML dashboard (viewable like Langfuse's UI) showing the full pipeline:
the Layer 2 checks that fed the AI, the AI's raw answer, and the Layer 3
validator's before/after decision. Not yet built.

**Open decision to resolve first, tomorrow:** before building that
dashboard, decide whether to (a) re-run the full golden eval fresh
(~10–20 min, 23 `claude -p` calls) so the dashboard reflects current
pipeline behavior, or (b) build it against the `eval_output/results.jsonl`
already on disk, which has not been confirmed current against the latest
validator/rule fixes (e.g. it's unclear whether it postdates the entry-13
rule-9 override). Leaning towards (a) for something meant to represent
real, current work, but this is the user's call to make first.

---

### Session 7 (2026-09-16) — Langfuse tracing, all 4 parts done

**Resume point:** nothing blocking. The Langfuse task from this session
(stand up self-hosted Langfuse, backfill historical traces, join to
golden-set, wire up live tracing) is fully complete, verified, committed
on branch `langfuse-tracing`, merged `--no-ff` to `main`. See "Status of
the work" below for the one-line-per-item summary and the "Open
decisions" list for what's actually still open (unrelated leftovers from
sessions 4–6, unchanged by this session).

**What got built:**
- **`langfuse/`** (gitignored) — cloned `langfuse/langfuse`, running via
  `docker compose up -d`. `langfuse/.env` (gitignored) holds
  auto-provisioned org/project/API keys (`LANGFUSE_INIT_*` env vars —
  no browser signup needed). `docker-compose.override.yml`: (1) remaps
  Postgres to host port 5433 (`127.0.0.1:5432` was already taken by a
  native Postgres 16 service used by other projects — untouched), (2)
  sets `LANGFUSE_MIGRATION_V4_WRITE_MODE=dual` on `langfuse-web` and
  `langfuse-worker` — v4 defaults to OTLP-only ingestion and rejects the
  classic `trace-create`/`generation-create` batch API needed for
  backdated historical timestamps; the error message names this exact
  fix. UI: `http://localhost:3000`, login in `langfuse/.env`.
- **`langfuse_client.py`** — stdlib-only (`urllib`, no SDK/`requests`
  dependency) credential loading + batch-push helper, shared by the
  backfill script and live tracing. Chose the classic ingestion API over
  the v4 Python SDK deliberately: the SDK is OTEL-based and ties
  observation `start_time` to wall-clock "now," which can't backdate
  historical traces; the classic API's `timestamp`/`startTime`/`endTime`
  fields can.
- **`import_historical_traces.py`** — parses all 489 `sdk-cli`-entrypoint
  session log files in
  `~/.claude/projects/-home-rdeva-status-translation-agent/*.jsonl`,
  classifies each (`clean` / `json-repaired` / `json-parse-failure` /
  `no-response` / `connectivity-ping`), joins to `golden-set/*.json` by
  resolving each entry's `commit_id` via `git log -1 --format=%B` in
  `EVAL_TARGET_REPO` and matching against the session log's
  `commit_message` text (handles the one PR-level entry, `golden-set/14.json`,
  whose `commit_id` is a label like `"PR-6 (merge cb66d392)"`, not a bare
  SHA — extracts the SHA via regex before resolving), and pushes
  trace-create/generation-create events. `--limit N` for a sample,
  `--all` for the full run, `--dry-run` to preview without pushing.
  Classification breakdown matches commit `bdcecd9`'s documented numbers
  exactly: 480 clean / 7 json-repaired / 1 no-response / 1
  connectivity-ping. Golden-set join: 413/489 confident, 0 uncertain, 76
  unmatched (real `claude -p` calls that weren't against a golden-set
  commit).
- **Ran the pilot (20 records), then the full 489-trace backfill.**
  Verified directly against ClickHouse (`uniqExact(id)` — not raw
  `count()`, which briefly over-counts by the pilot's 20 duplicate rows
  until ReplacingMergeTree background-merges them, harmless): **489
  distinct traces, 488 distinct generations** (489 − 1 no-response).
  Historical timestamps confirmed correct (e.g. `2026-09-09`, not
  import-time "now").
- **Live tracing wired into `prompt_contract_layer.call_claude`.**
  `claude -p` now runs with `--output-format json`; `call_claude` unwraps
  `envelope["result"]` and returns it exactly as before (same contract,
  verified byte-identical), so no caller changed. The envelope carries
  usage/model/session_id/cost but not the thinking block or `requestId`
  — those are read back from the session log Claude Code itself writes
  at `<session_id>.jsonl` immediately after the call (same directory as
  the historical import reads). Tracing is best-effort only: silently
  skipped when `langfuse_client.load_credentials()` finds no
  credentials, never raises or blocks the pipeline on a push failure
  (wrapped, 5s timeout, warns to stderr and moves on). Verified with a
  real smoke-test call — trace landed with full metadata.
- **Refactored `import_historical_traces.py` onto `langfuse_client.py`**,
  dropping its `requests` dependency — both scripts now run under plain
  system `python3`, no venv needed. (`.venv-langfuse/`, gitignored, was
  built to develop against before this refactor; harmless to keep or
  delete, no longer required.)
- Committed on branch `langfuse-tracing` (`248be54`), merged `--no-ff` to
  `main`, pushed.

**Known noise, not a bug:** three `json-parse-failure`-classified session
log files exist from this session's own manual probing of
`--output-format json`'s shape (throwaway prompts like "reply with
exactly: OK") — correctly classified (they're not `{status, narrative}`
JSON), but not real pipeline data. They were created *after* the 489-file
backfill ran, so the imported historical data is unaffected. If
`import_historical_traces.py --all` is ever re-run, it will now also
pick up these 3 (and any other manual test calls made in the meantime)
as `none`-golden-matched `json-parse-failure` entries — harmless (they
land in the same place a real anomalous call would), just not
meaningful. No action taken; noting so it isn't mistaken for a
regression later.

---

### Session 6 (2026-09-13 → 2026-09-16) — since session 5

- **`docs/golden-set-reference.md` entry-9 row fixed** (`55046f8`,
  pushed): was still showing `Code complete`, stale since before the
  entry-09 relabel. Now `Flagged` with a short note, matching entries
  12/14/17/19's style.
- **Rule-9 genuine Tier-1 hard override built** (`bc4db67` →
  `--no-ff` merge `b1e8e77`, pushed): `enforce_deterministic_rules` now
  forces `Flagged` when `sweeping_claim_check` has a verification with
  `claim_holds: False` — gated on that, NOT on `detected` alone (entry
  13 is `detected: True` with every verification holding and must not
  be overridden — proven with a deliberately-wrong-model-status test,
  same method as rules 11/14/15's originals). Eval-confirmed: entry 15
  `Flagged`, entry 13 `Pending`, unaffected.
- **`/home/rdeva/medrecord` (a *separate* git repo, `dev` branch)** —
  fixed the actual root cause behind golden entry 15 / the repeat-flag
  on unseen commit `687ea28`: removed the stale `onrender.com` reference
  from `src/api/pinnedFetch.ts`'s cert-pinning comment (comment-only,
  no functional code touched). Committed `3150d74`, **pushed to
  `origin/dev`**. `grep -rn onrender src/api/` now empty in that repo.
- **Tier-2 → Tier-1 feasibility assessment** for entries 01/02/04/06/17/18
  — see "not written to any doc" note above.
- **Trace-data inventory** (repo `eval_output/` vs. Claude Code's own
  session logs) — see "Facts already gathered" above. This directly led
  to today's Langfuse ask.
- **JSON-parsing robustness fix** (`bdcecd9` → `--no-ff` merge `f25acc5`,
  **pushed**): `parse_model_output` now repairs 4 evidenced malformations
  (unescaped internal quote in narrative, trailing comma before `}`,
  Unicode curly quote as closing delimiter, extra trailing content after
  a complete object) found by direct inspection of the 7 real failures
  above. Only engages when plain `json.loads` already failed — zero
  behavior change verified against the full 480-clean-response set, not
  sampled. New `test_parse_model_output.py` (7 real cases pinned
  verbatim + clean/garbage guards), all 5 unit suites green. **Correction
  logged in that commit's own message:** an earlier claim of an invalid
  `\'` escape in 2 of the 7 cases was wrong — a `repr()` preview artifact,
  not a real byte in the data; both are plain trailing-comma cases.
- **`main` @ `f25acc5`, pushed, `origin/main` confirmed up to date** as
  of the end of this block. `git status` was clean before the Langfuse
  task started.

---

### Earlier sessions (4–5, 2026-09-10/11) — sweeping-claim + validator fixes

- **Entry-13 fix** (`3fbc5c9`): sweeping-claim repo grep no longer counts
  hits on lines the commit itself just added. Entry 13 now reliably
  `Pending`. `docs/eval-v7-findings.md`.
- **Entry-15 fix** (`b1ebe9d`): trigger scan also reads the commit's own
  added prose (absence-claim phrasing only), not just the message. Entry
  15 → correct data, though not yet code-*enforced* until session 6's
  rule-9 override above. `docs/eval-v8-findings.md`.
- **Validator hedge-downgrade fix** (`5770ecd`): a hedge like "...or
  something that still needs cleanup" no longer wrongly downgrades an
  already-`Flagged` status. `docs/eval-v9-findings.md`.
- All three merged `--no-ff` into `main` and pushed during session 5.
  All 4 unit suites (as of then) green throughout.

## Status of the work

| Item | State |
|---|---|
| Rules 12/13 in prompt contract | DONE — committed `6352660` (earlier session) |
| Drop bare `"not yet"` trigger + original 16-case unit suite | DONE — committed `ac2708c` (earlier session) |
| General verification-word carve-out + 20-case unit suite | DONE — committed `433410f`, **20/20 pass**, AI-free |
| Self-consistency eval run (3× on 8 unstable entries, 1× rest) | RUN — **20/23**; misses 03, 09, 15; see `docs/eval-v4-findings.md` |
| Docs: `eval-v4-findings.md`, README | DONE — committed `d9c0219` |
| Overclaim check — fetch-layer detection (`build_overclaim_check`) + 8 unit cases | DONE — committed `10e5af6`; false-positive sweep clean (fires on entry 14 only) |
| Overclaim check — prompt-contract wiring (payload field, `enforce_deterministic_rules`, rule 14) + 6 more unit cases | DONE — committed `c36a518`, **14/14 pass**, AI-free |
| Full 23-entry eval since `10e5af6`/`c36a518` landed | DONE — v5 self-consistency run, **22/23**, `docs/eval-v5-findings.md` |
| Entry 14 deterministic `Flagged` via rule 14 | CONFIRMED — 3/3 Flagged; `overclaim_check.detected` True deterministically, `enforce_deterministic_rules` forces Flagged for any model status |
| Golden entry 03 label | CORRECTED — `Pending` → `Code complete`, `correct_agent_response` rewritten to match 01/04–08/10 |
| Rule 15 — undisclosed UI-copy removal check (`build_ui_copy_removal_check` + prompt wiring + override) | DONE — committed `55f483a`. 3 unit suites green (validator 20, overclaim 14, ui-copy-removal 22). Sweep: fires on entry 09 only. |
| Golden entry 09 label | FLIPPED — `Code complete` → `Flagged`, committed `fcd8b83` (architect-confirmed). |
| v6 self-consistency eval | DONE — **21/23**, misses 13 + 15. `docs/eval-v6-findings.md`. |
| Merge `eval-v5-overclaim-verification` to `main` | DONE — `--no-ff` merge `2bcffcd`, pushed |
| Merge `rule15-ui-copy-removal` to `main` | DONE — `--no-ff` merge `ad65497`, pushed |
| `call_claude` timeout 120 → 180 s | DONE — `86ed931` on `main`, pushed |
| Case 13 fix — `sweeping_claim_check` ignores the commit's own added lines | DONE — `3fbc5c9`, merged to `main` `b200807`, pushed. Entry 13 6/6 `Pending` across sessions 4 and 5. |
| Case 15 fix — sweeping trigger also scans the commit's own added prose (absence-claim phrasing only) + rule-9 clause | DONE — `b1ebe9d`, merged to `main` `b200807`, pushed. Entry 15 `Flagged` consistently once the validator fix (below) landed. |
| Validator fix — `Flagged` no longer downgraded by a hedge ("or ... still needs") that isn't a separate unfinished task | DONE — `5770ecd`, merged to `main` `799451f`, pushed. `test_status_consistency_validator.py` 17/8 cases (`trigger_overrides_flagged_too` guard unchanged). Found and fixed while verifying the sweeping-claim merge; see session-5 note above. |
| `docs/golden-set-reference.md` entry-9 stale row | DONE — `55046f8`, pushed. Was showing `Code complete`, corrected to `Flagged`. |
| Rule-9 genuine Tier-1 hard override (`claim_holds: False` → forced `Flagged`) | DONE — `bc4db67` → merge `b1e8e77`, pushed. Entry 15 now code-enforced, not just AI-judgment. Gated on `claim_holds`, not `detected` alone — verified entry 13 unaffected via deliberately-wrong-status test. |
| `medrecord` repo — removed stale `onrender.com` from `pinnedFetch.ts` comment | DONE — `3150d74` on `medrecord`'s `dev` branch, pushed to `origin/dev`. Separate repo from this one. |
| Tier-2 → Tier-1 feasibility assessment (entries 01/02/04/06/17/18) | DONE, analysis only, nothing built (per instruction) — **not written to a doc**, only in conversation. See "not written to any doc" note above if needed again. |
| Trace-data inventory (repo files vs. Claude Code's own session logs) | DONE — **not written to a doc**, only in conversation; key facts captured above under "Facts already gathered." |
| JSON-parsing robustness fix (`parse_model_output` repair pass) | DONE — `bdcecd9` → merge `f25acc5`, pushed. `test_parse_model_output.py` new (7 real cases + guards). All 5 unit suites green. |
| Langfuse self-hosted setup (4-part task: backfill 489 historical traces, live tracing wiring) | DONE — see session 7 above. Committed `248be54` on `langfuse-tracing`, merged `--no-ff` to `main`, pushed. All 5 unit suites still green (tracing is opt-in/best-effort, no test touches `call_claude`). |
| `raw_status`/`raw_narrative` capture in `generate_status_update` | DONE — session 9, `1d92067`. Additive, all existing callers unaffected (dict-key access). |
| Full 23-entry eval, session 9 ("v10") | DONE — **21/23**, misses 03 + 22, `docs/eval-v10-findings.md`. 6 variance-prone entries run 3x each. |
| Rule-9 fix confirmed to also close entry 13's instability | CONFIRMED — session 9, via `docs/eval-history.md` Run 9/10 data. Not a new fix; a side effect of `bc4db67`'s correct `claim_holds` gating. |
| `run_dashboard_eval.py` + `build_drift_trace.py` (Drift Trace dashboard, checked in) | DONE — session 9, `c4a512d`. Self-contained, no scratchpad dependency. Public artifact link in README. |
| README overhaul (current eval state, rules 9/11/14/15 documented, Observability section) | DONE — session 9, `10233cb`. |
| `docs/eval-history.md`, `docs/prompt-contract-reference.md`, `docs/golden-set-reference.md` corrected against source | DONE — session 9, prompted by a user-requested whole-repo consistency check. Golden-set-reference had 5 wrong status values (entries 3, 11, 12, 14, 16) — found by diffing against `golden-set/*.json` directly, not by trusting the doc. |
| `eval-summary-line` branch merged to `main` | DONE — `--no-ff` merge `f5c5751`, pushed. All 5 unit suites green pre- and post-merge. |
| LinkedIn post + "Status-Drift-Agent Talking Points" Claude Doc | DONE — session 9. Post drafted, refined (technical-depth framing, corrected a course-completion misattribution), covers both entry 03 and entry 22. Doc is a private FAQ companion, intentionally not in this repo. |

## Open decisions for next session (in priority order)

**Current, as of session 9 (2026-09-17) — replaces the list below, which is now either resolved or superseded; kept underneath for history, not as live priorities.**

1. **Entry 03 — the validator's word-distance bug (`docs/eval-v10-findings.md`).** Real, reproduced twice on identical input, precisely diagnosed (a quote mark and a one-word distance issue, two different runs, same root cause). Decision needed: leave documented as a known, safe (one-directional) soft spot, or build a model-based self-consistency check to replace `status_consistency_validator`'s word-matching (new AI call, new cost, new failure modes to characterize). Not decided — this is a real cost-vs-accuracy call for the architect, not a quick fix.

2. **Entry 22 — unverifiable-claim gap.** No check exists for a "trust me, QA passed"-style claim with zero evidence. Confirmed persistent across two separate runs (session 6's rule-9-confirmation run, and this session's) — not a fluke. Would need a new check in the fetch layer (rule-16-shaped), not a fix to an existing one. Not started.

3. **Portfolio thread, if picking that back up:** the LinkedIn post is drafted and ready to post as-is. The Talking Points Claude Doc is live and has one open comment thread (asking the user to confirm whether the "my role" section's phrasing sounds like their actual voice). The user separately mentioned a Notion page ("Medrecord AI") and a GitHub Pages portfolio site (`rdevarakond88.github.io`) as existing destinations — nothing done toward either yet; no decision made on whether this project should feed them too.

<details>
<summary>Superseded list from sessions 4–8 (kept for history only — see item above for current priorities)</summary>

1. **Entry 12 — a second, still-open negation-window gap.** Same class of
   bug as the hedge fix but different: `"doesn't"` sat 9 words before the
   `"follow-up"` trigger it was negating (`"...doesn't need to be treated
   as a gap needing follow-up"`), one word past `NEGATION_LOOKBACK_WORDS`
   (8). Hit once in the session-5 eval, cleared 4/4 on re-check — rare,
   not reproduced on demand, not fixed (deliberately, to avoid open-ended
   validator patching). Widening the lookback is the likely fix if it
   recurs; watch for it rather than pre-emptively tuning.

2. **Entry 17 — model split on an unrelated diff detail, not the golden
   set's fault.** Alternated `Code complete` (4/4 on one re-check) and
   `Flagged` (2/2 on a later one) across independent samples. The
   `Flagged` reasoning is about a real, separate observation (an
   ownership-registry line the diff adds with no mention in the commit
   message) — not caused by anything changed in session 5
   (`sweeping_claim_check.detected` confirmed `False` on this commit).
   Session 6's Tier-2 assessment looked at this in more depth: a naive
   "unexplained file touch" hard override would fire on 16 of 19 real
   golden entries without a maintained allowlist — not a clean fix.
   Worth a look if it keeps splitting; not a quick win either way.

3. **`claude -p` JSON-parse failures — the root cause is now understood
   and fixed** (session 6, `bdcecd9`). What was called "transient
   flakiness" in session 5 is actually 7 specific, categorized
   malformations, now repaired in `parse_model_output`. Superseded by
   the fix above; kept here only as a pointer in case the fix needs
   revisiting.

3b. **The one live "model temporarily unavailable" tool error hit in
   session 5** was a different, harness-level thing (a Bash-tool
   classifier timeout), unrelated to the `claude -p` JSON issue above.
   No action taken; note if it recurs.

4. **Eval cost / robustness.** The self-consistency run is 39 `claude -p`
   calls, run three times this session alone (~115 calls) chasing a clean
   confirmation number that inherent model variance on single-run entries
   makes unlikely in any one run. Cheaper alternative not yet taken:
   freeze `prompt_contract_layer` outputs and re-run only the validator
   stage to isolate its effect from model sampling variance.

5. **Entries 01/03/06 variance.** Low-grade `Code complete ↔ Pending`
   noise on the "open sub-items → is it done?" boundary; stable across
   sessions 4–5's re-checks. Not blocking; note if it worsens.

6. **Synthetic entries (20–23)** get `sweeping_claim_check` from
   `run_golden_eval._synthetic_sweeping_claim_check`, which scans only the
   message. Not a gap today (no synthetic diff has absence-claim prose),
   but the two code paths have diverged by one capability. **Still true
   as of session 9** — not touched.

</details>

## Re-run commands (for reference — a session can just run these)

```bash
cd /home/rdeva/status-translation-agent
python3 test_status_consistency_validator.py                                    # validator unit suite, 23 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_overclaim_check.py          # overclaim-check unit suite, 14 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_ui_copy_removal_check.py    # ui-copy-removal unit suite, 22 cases, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 test_sweeping_claim_check.py     # sweeping-claim unit suite, 20 cases + entry 13 & 15 regressions, fast
python3 test_parse_model_output.py                                              # JSON-repair unit suite, 7 real historical cases + guards, fast
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_golden_eval.py         # full eval, 1x/entry, ~10-20 min
python3 score_golden_eval.py                                              # score results.jsonl
python3 score_golden_eval.py eval_output/results-prefix-baseline.jsonl    # score the pre-fix baseline
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_selfconsistency_eval.py  # 3x on unstable entries, 1x rest

# Langfuse (needs the local stack running: `cd langfuse && docker compose up -d`)
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 import_historical_traces.py --dry-run  # preview, no push
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 import_historical_traces.py --all      # re-run full backfill (idempotent - trace id = session log filename)

# Drift Trace dashboard (public artifact linked from the README) - regenerate
# whenever pipeline behavior changes, so the shared link doesn't go stale.
# Republishing to the existing artifact URL is a manual Claude Code step
# (Artifact tool, action publish, same url) - no script does that part.
EVAL_TARGET_REPO=/home/rdeva/medrecord python3 run_dashboard_eval.py   # ~35 claude -p calls, ~20-35 min
python3 build_drift_trace.py                                          # -> eval_output/drift-trace.html
```
