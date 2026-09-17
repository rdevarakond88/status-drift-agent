# status-drift-agent

Status updates on a project tracker say what someone *believes* happened.
The commit history says what the code *actually* did. Those two things
drift apart constantly: a "Tested" that was really just a smoke check, a
PR description claiming a fix was verified when the commit's own notes say
it wasn't, a "fixed all edge cases" that only handles one of them. Nobody
catches the drift until it causes a real problem downstream.

This is a small tool that reads real commit history and tries to catch that
drift automatically: does the story a commit (or PR) tells about itself
actually match what its diff shows?

It's an active, iterative build, not a finished product. The eval results
in this repo (`eval_output/`, `docs/disagreements.md`) are an honest
snapshot of where it currently gets things right and where it doesn't,
including cases where the tool's answer turned out to be more defensible
than my own hand-labeled "correct" answer.

## The pipeline

Four stages, currently split across three files:

1. **Fetch** (`fetch_layer.py`): deterministic, no AI involved. Pulls new
   commits off a branch since the last checkpoint, attaches PR metadata
   (labeled as describing state at PR merge time, not this commit's own
   point in time), attributes each commit to a story/ticket ID if one can
   be found in the message, branch name, or PR text, computes whether the
   diff touches any real source file at all, checks the commit message
   against a fixed list of sweeping-claim keywords and verifies any
   quoted claim against the actual repo tree, and flags file deletions the
   message never explains. Writes everything out as JSONL. Checkpointed so
   re-runs only process what's new.
2. **AI** (`prompt_contract_layer.py`): takes one fetch-layer record and
   asks a model to compare the commit's own claims (message, diff, PR
   description) against what the diff actually shows, and produce a status
   plus a plain-language narrative. This is the only stage that's genuinely
   AI judgment; everything else is deterministic.
3. **Rule enforcement** (`enforce_deterministic_rules`, also
   `prompt_contract_layer.py`): forces the model's answer to `Flagged` in
   four specific cases where the fetch layer already has a verified,
   checkable fact rather than trusting the model to weigh it on its own:
   an unexplained file deletion (rule 11), a verified overclaim — a
   message says a feature was "added" but git history shows it already
   existed (rule 14), an undisclosed removal of on-screen text (rule 15),
   or a sweeping claim ("no longer appears anywhere") that a repo-wide
   search has actually disproved (rule 9 — gated on the claim failing,
   not merely being present, so a claim that holds up under the same
   search is left alone). Also enforces the non-override parts of the
   contract: status must be one of exactly four allowed values, a locked
   follow-up question gets appended whenever status is "Code complete,"
   "Tested" is hard-blocked when the diff never touched app code, and
   malformed model output is rejected outright. Returns the model's
   answer both before and after this stage runs (`raw_status` /
   `raw_narrative` vs. the final `status` / `narrative`), so it's possible
   to tell whether a rule actually changed anything or the model already
   agreed with it — see the Drift Trace dashboard below.
4. **Status Consistency Validator** (`status_consistency_validator.py`):
   a separate, AI-free pass over the model's own generated paragraph.
   Scans it for a fixed list of "still outstanding" phrases and
   auto-corrects the status word to "Pending" when one is present but the
   status word doesn't already say so. Two carve-outs suppress a match:
   a negation word in the few words right before it ("no outstanding
   work"), or a verification word (`tested`, `QA`, `verification`,
   `review`, `device`, ...) within a few words on either side — because
   "verification is still outstanding" / "still needs a QA pass" is a
   routine pending-check that rule 2 keeps at "Code complete", not
   genuinely unfinished work. Pure text matching, no model call, no real
   grammar beyond those two checks.

`run_golden_eval.py` is the harness that runs a hand-labeled golden set
through the full pipeline and diffs the result against the expected answer.

## Golden set and eval results

The golden set (`golden-set/`, 23 entries) is 19 real commits plus 4
hand-constructed synthetic ones designed to probe specific failure modes:
a commit with no usable metadata, an overclaimed fix, boilerplate QA
language, an AI-authored commit with a claim the diff doesn't support.

The 19 real entries were built and evaluated against commit history from a
separate, private production repository, not included here. This repo
ships only the golden-set descriptions and the eval output (status and
narrative), never that repo's source code or diffs. Screen names, third-party
service names, and internal branded UI copy have also been generalized in
the golden set and eval narratives, since they're specific enough to
identify the private codebase even without exposing its code directly.

Current result (`docs/eval-v10-findings.md`, 2026-09-17): **21 of 23**
golden entries match exactly on status. That run used 3 independent runs
on the 6 entries with a history of flipping run-to-run (01, 03, 06, 09,
15, 17), 1 run on the rest, specifically so a mismatch can be labeled a
genuine miss instead of one lucky/unlucky sample. Every full trace —
which of the four fetch-layer checks fired, the model's raw answer before
rule enforcement, whether a rule changed it, and whether the validator
did — is browsable in the **[Drift Trace dashboard](https://claude.ai/artifact/1VKJvjMPu99P18CWC6ujgX)**
(generated 2026-09-17; regenerate with `run_dashboard_eval.py` +
`build_drift_trace.py`, see `docs/session-state.md`).

It's up from an original 14/23
(`docs/disagreements.md`) after several rounds of changes documented in
`docs/eval-v2-findings.md` and `docs/eval-v3-findings.md`: a hard block on
claiming "Tested" for docs/logs/config-only commits, verifying sweeping
claims ("no longer appears anywhere") against the actual repo instead of
just the diff, labeling PR metadata as describing state at merge time
rather than any one commit's own point in time, a text-matching pass that
catches when the model's own paragraph admits something is still
unresolved but the status word doesn't say so, flagging file deletions the
commit message never explains, and two corrections to golden-set entries
(11, 14) where the agent's original answer turned out more defensible than
the hand-written golden label.

Fixed since then: bundling-hygiene and partial-completion rules (12, 13)
added to the prompt contract; the false contradictions between a commit's
own "not yet tested" note and a bundling PR's aggregate claim; and a
text-matcher that was flipping correct answers to wrong ones — first on
negated phrases like "no outstanding work", then on "not yet tested" and
its cousins ("verification is still outstanding", "still needs a QA
pass"), which turned out to be the same bug wearing three different
phrases. The `not yet` patch and then a general verification-context
carve-out (`docs/eval-v3-findings.md`, `docs/eval-v4-findings.md`) fixed
that class; a permanent 20-case AI-free unit suite
(`test_status_consistency_validator.py`) pins the exact real sentences
that broke. Most recently (`docs/eval-v5-findings.md`): a deterministic
overclaim check — when a message claims a feature was "added" but git
history shows it already existed, the fetch layer detects it and a
code-level rule forces `Flagged` regardless of the model's answer, pinned
by a 14-case AI-free suite (`test_overclaim_check.py`); and entry 03's
golden label corrected from `Pending` to `Code complete` to match how the
other code-done/verification-pending entries (01, 04–08, 10) are labeled.
Then (`docs/eval-v6-findings.md`): a second deterministic check, rule 15 —
when a commit's diff removes a line of on-screen text a user would have
seen (a label, hint, or message inside a UI component) and neither the
commit message nor, for a merge, the PR body mentions removing anything,
the fetch layer detects it from the diff and a code-level rule forces
`Flagged`, pinned by a 22-case AI-free suite
(`test_ui_copy_removal_check.py`); and entry 09's golden label corrected
from `Code complete` to `Flagged` to match.

Since v6: the sweeping-claim trigger was taught to also scan a commit's
own added prose, not just its message, and a third deterministic check,
rule 9, forces `Flagged` when a sweeping claim is actually verified false
against the repo (gated on the claim failing, not merely being present —
entry 13's "Six Agents" claim is detected but holds up, and stays
`Pending` correctly). That closed the entry-15 gap for real, in code, not
just by relabeling — entry 15 has been `Flagged` 6/6 across the sessions
since, and entry 13 stable (`Pending`, matching golden) across this
session's full run plus every prior repeat check.

Still open, per `docs/eval-v10-findings.md`: **entry 03** — the model's
raw answer is correct (`Code complete`) in every run, but
`status_consistency_validator`'s "is this a real problem or a routine
pending-verification mention" check is a hand-written word-distance
heuristic over freely-generated prose, and it flipped a correct answer to
`Pending` in 2 of 3 independent runs on wording that meant the same thing
each time. Traced to the exact mechanism (a quote mark around one word
broke a set-membership check in one run; a one-word-too-far distance
missed it in another) — not fixed, because widening the distance
threshold would catch this specific phrasing and miss the next one; this
class of judgment probably needs the model to self-check rather than a
fixed rule. The failure is one-directional and safe: this validator can
only ever push a status toward `Pending`, never fabricate `Code complete`
or silently clear a `Flagged`, so it produces visible over-caution, not a
misleading result. Separately, **entry 22** (synthetic) — a commit claims
"QA verified" with no test files or CI run linked; none of the four
deterministic checks are built to catch an unverifiable process claim
like that, so the model took it at face value. A distinct, real gap with
no check built for it yet.

## Observability

Every real `claude -p` call in this pipeline is traced to a self-hosted
[Langfuse](https://github.com/langfuse/langfuse) instance: 489 historical
calls were backfilled from this repo's own session logs with their
original timestamps, and every live call since is traced automatically
(best-effort — tracing failures never block the pipeline). That covers
cost, latency, and the exact prompt/response for the AI step, but it has
no visibility into the fetch-layer checks, rule enforcement, or the
validator, since those aren't AI calls. The Drift Trace dashboard above
covers the other side: not what a call cost, but why the pipeline landed
on a given answer across all four stages. The two are meant to be
complementary, not overlapping — the dashboard is for "why did we get
this status," Langfuse is for "how much did this cost and what exactly
did the model see."

## Status

Working end-to-end on a real commit history, with a growing golden set and
an honest eval loop, not a packaged tool. Expect the prompt contract, the
allowed status values, and the fetch layer's story-attribution heuristics
to keep changing as more disagreements get reviewed.
