# Golden-set disagreements: review notes

Of the 23 golden-set entries, 14 matched the generated status exactly and 9
did not. This is a first-pass human review of all 9 disagreements: which
ones are real defects in the agent's output, which ones expose a gap in the
prompt contract itself, and which ones are architectural limits worth
knowing about rather than bugs to fix.

Status values referenced below: `Code complete`, `Tested`, `Pending`,
`Flagged`.

## Summary

| # | Golden | Generated | Verdict |
|---|--------|-----------|---------|
| 01 | Code complete | Flagged | Defensible. Agent caught a real contradiction the golden label didn't account for |
| 02 | Pending | Code complete | Contract gap. No rule for "this piece is done but the feature isn't usable yet" |
| 03 | Pending | Flagged | Same contract gap as 01/14. Conflicting claims vs. "not yet tested" aren't clearly separated |
| 12 | Flagged | Code complete | Genuine miss. Agent didn't catch an unrelated-content bundling issue it caught elsewhere |
| 13 | Pending | Code complete | Genuine miss. Agent named the open items, then still called it complete |
| 14 | Code complete | Flagged | Defensible. A real wording mismatch, but arguably shouldn't sink a 28-commit release's whole status |
| 15 | Flagged | Code complete | Architectural limit. The discrepancy lived in a file this commit's diff didn't touch |
| 17 | Code complete | Tested | Definitional gap. "Tested" isn't defined for a commit with no application code in it |
| 19 | Flagged | Code complete | Genuine miss. Agent had no signal to notice a missing convention (absent co-author trailer) |

Net: 2 clear misses, 1 clear contract gap that shows up twice, 1 architecture
limit, 1 definitional gap, and 2 cases where the agent's answer is arguably
better-reasoned than the golden label.

## By case

### 01: Code complete vs. Flagged
The golden label treats this as a small, clean fix. The agent flagged it
instead, because the commit's own tracking notes say on-device verification
is still outstanding, while a pull request bundling this commit claims it
was "verified end-to-end on device." That's a real contradiction between two
sources describing the same commit, not a hallucinated concern. The prompt
contract's flagging rule is written around diff-vs-claim mismatches, not
claim-vs-claim mismatches, so this is arguably the agent extending the rule
correctly rather than misapplying it. Leaning toward: the golden label
should be revisited, or the contract should explicitly say how to handle
conflicting claims across sources.

### 02: Pending vs. Code complete
The commit itself (a backend infrastructure change) is complete and was
verified on its own terms. But the feature it's part of isn't usable
end-to-end until a second, separate piece of front-end work lands, which
the commit message itself says is still queued. The golden label rolls this
up to `Pending` for the overall capability; the agent scored only the
commit in front of it and landed on `Code complete`. The contract has no
rule instructing the model to look past "is this commit's own scope done"
toward "is the capability this enables actually usable yet." This is the
clearest reusable finding in this batch.

### 03: Pending vs. Flagged
Same underlying pattern as 01: commit says testing is still outstanding,
a bundled PR claims it's already verified end-to-end. The agent again
escalated to `Flagged` for the contradiction; the golden label chose
`Pending` to describe the literal state (device test not done yet). Both
are defensible reads of the same facts. This is really the same open
question as 01: when sources disagree, is that a `Pending` (the safer claim
hasn't been met yet) or a `Flagged` (someone needs to resolve which claim is
true)? The contract should pick one and say so explicitly.

### 12: Flagged vs. Code complete
The code fix is genuinely fine; golden agrees. The reason golden flags it
is hygiene: the commit bundles an unrelated draft write-up into the same
change as the code fix. The agent didn't surface that at all, even though
it caught a near-identical bundling concern in case 14 (a 28-commit release
worth flagging as reducing traceability). This is a real inconsistency in
the agent's own behavior, not a contract ambiguity. It should have caught
this one too.

### 13: Pending vs. Code complete
The agent's narrative is actually correct on the facts: it names two items
closed in this commit and two items explicitly left open for a human
decision. Then it still assigns `Code complete` because no application code
needed testing. This is the same gap as case 02. The contract doesn't
connect "some sub-items are still open" to "overall status should reflect
that," and here it's a clean miss rather than a defensible read: the agent's
own narrative contradicts its own status label.

### 14: Code complete vs. Flagged
This is a 28-commit bundled release. Golden calls it `Code complete` overall
and treats the bundling itself as a traceability note, not a blocker. The
agent flagged it because one specific claim in the PR description ("resend
was added") doesn't match the diff (resend already existed; only the cooldown
timer changed). That's a real, verifiable mismatch, and rule 3 of the contract
says exactly this should be flagged. The open question is proportionality:
should one inaccurate word in a PR description covering 28 commits flag the
whole release, or should it be called out as a footnote while the overall
status stays `Code complete`? Current contract doesn't distinguish "flag the
whole thing" from "flag one claim within it."

### 15: Flagged vs. Code complete
Golden's flag depends on a fact that isn't in this commit's diff at all: the
"no longer appears anywhere in src/api/" claim is false because of a
reference left behind in a third file. But that third file was changed by
an earlier commit, not this one. This commit is a merge/tracking commit,
and the agent's narrative correctly notes it doesn't contain the actual code
diff being described. The agent didn't miss this due to bad reasoning; it
never had visibility into it. This is a structural limit of scoring one
commit's diff at a time: some verification claims are about repo-wide
state, not the current diff. Worth flagging as a known boundary of the
current design rather than something to "fix" in the prompt.

### 17: Code complete vs. Tested
No application code changed in this commit; it's a closed-as-verified
investigation (an existing behavior was checked against several scenarios
and found to already be correct). Golden calls this `Code complete` on the
reasoning that `Tested` only applies when there's code to test. The agent
called it `Tested` because the commit's entire content is a testing/
verification action that concluded successfully. Both readings are internally
consistent. The contract's definition of `Tested` (rule 2) is written for
"code shipped and testing confirmed," and doesn't say what to do when the
entire unit of work is a test/investigation with no code attached to it.

### 19: Flagged vs. Code complete
Golden's flag rests on a convention, not on anything explicit in this
commit: every other commit in this history carries an agent co-author
trailer, and this one doesn't, implying it was made outside the normal
process. The agent had no explicit signal telling it to check for this
trailer and treat its absence as suspicious. It read the diff (a clean,
total deletion) and the commit message (a stated revert) and reasonably
concluded the change was clean and intentional. This is a real miss, but a
data/instruction gap rather than a reasoning failure: the model wasn't told
this convention exists or matters.

## Takeaways for the next contract revision

1. Add an explicit rule for partial/split completion: when a commit is
   internally complete but the capability it's part of still depends on
   other unfinished work, status should reflect the capability, not just
   the commit's own scope (cases 02, 13).
2. Decide, in writing, how to handle conflicting claims across sources
   (commit notes vs. bundled PR description): does that produce `Pending`
   or `Flagged`? Right now the model is inconsistent because the contract
   is silent (cases 01, 03, 14).
3. Define what `Tested` means for a commit that contains no application
   code: is a verification/investigation commit eligible for `Tested`, or
   is that status reserved for code (case 17)?
4. Bundling-hygiene flagging (case 12 vs. 14) needs to be applied
   consistently. Right now it's present in the contract's spirit but not
   reliably triggered.
5. Document as a known limitation, not a bug: single-commit-diff scoring
   cannot catch claims about repo-wide state that live outside the current
   diff (case 15). A future version might need multi-commit or working-tree
   context to close this gap.
