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
3. **Validator** (also `prompt_contract_layer.py`): enforces the
   mechanical parts of the contract in code rather than trusting the model
   to self-police. Status must be one of exactly four allowed values, a
   locked follow-up question gets appended whenever status is "Code
   complete," "Tested" is hard-blocked when the diff never touched app
   code, and malformed model output is rejected outright.
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

Current result: **22 of 23** golden entries match exactly on status, 1
doesn't (`docs/eval-v5-findings.md`). That run used self-consistency
checking — 3 runs and a majority vote on the 8 entries with a history of
flipping run-to-run, 1 run on the rest — rather than a single run per
entry, since earlier rounds showed run-to-run model variance larger than
the changes being measured. It's up from an original 14/23
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

Still open, and documented rather than papered over: one sweeping claim
(15) lives in diff/log content rather than the commit message, outside
what the current sweeping-claim check reaches; entry 09 is a genuine
run-to-run model instability (3/3 `Flagged` in v4, 2/3 `Code complete` in
v5, no code change between) over whether a diff's silent line removal is a
say-vs-do mismatch — the golden label question there is unresolved; case
13 passes only via majority vote and is genuinely unstable run-to-run
because rules 3 and 13 can both fire on it with no stated precedence.

## Status

Working end-to-end on a real commit history, with a growing golden set and
an honest eval loop, not a packaged tool. Expect the prompt contract, the
allowed status values, and the fetch layer's story-attribution heuristics
to keep changing as more disagreements get reviewed.
