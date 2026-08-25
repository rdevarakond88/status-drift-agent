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

Three stages, currently split across two files:

1. **Fetch** (`fetch_layer.py`): deterministic, no AI involved. Pulls new
   commits off a branch since the last checkpoint, attaches PR metadata,
   attributes each commit to a story/ticket ID if one can be found in the
   message, branch name, or PR text, and writes everything out as JSONL.
   Checkpointed so re-runs only process what's new.
2. **AI** (`prompt_contract_layer.py`): takes one fetch-layer record and
   asks a model to compare the commit's own claims (message, diff, PR
   description) against what the diff actually shows, and produce a status
   plus a plain-language narrative. This is the only stage that's genuinely
   AI judgment; everything else is deterministic.
3. **Validator** (also `prompt_contract_layer.py`): enforces the
   mechanical parts of the contract in code rather than trusting the model
   to self-police. Status must be one of exactly four allowed values, a
   locked follow-up question gets appended whenever status is "Code
   complete," and malformed model output is rejected outright.

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

Current result: 14 of 23 golden entries match exactly on status, 9 don't.
`docs/disagreements.md` reviews every one of those 9 by hand. Some are
real misses in the agent's output, some expose a genuine gap in the prompt
contract (no rule yet for "this commit is done but the feature it's part
of still isn't usable"), and at least two are cases where the agent's
answer is arguably better-reasoned than my own hand-written golden label.

## Status

Working end-to-end on a real commit history, with a growing golden set and
an honest eval loop, not a packaged tool. Expect the prompt contract, the
allowed status values, and the fetch layer's story-attribution heuristics
to keep changing as more disagreements get reviewed.
