#!/usr/bin/env python3
"""A pure text-matching pass over the AI's own generated paragraph, no AI
calls. Runs after prompt_contract_layer produces a {status, narrative}
pair and auto-corrects the status word to "Pending" when the narrative
admits something is still unresolved but the status word doesn't already
say so.

The scan strips prompt_contract_layer's fixed Code-complete follow-up
question before matching. That question ("Follow-up for the developer:
when/how will this be tested...") gets appended to every single "Code
complete" result as a matter of routine, so its own wording ("Follow-up")
would otherwise match the trigger list on every code-complete item and
make "Pending" swallow "Code complete" entirely. What's being scanned is
the AI's own paragraph, not code-injected boilerplate asked of every item
alike.

A trigger phrase preceded by a negation word within a short lookback
window ("no outstanding work", "not a gap needing follow-up") is not a
sign that something is unresolved: it's the AI saying the opposite. Those
matches are suppressed rather than counted. This is still pure text
matching, no understanding of grammar beyond "is there a negation word
somewhere in the last few words before this match."

A trigger phrase sitting next to a verification word ("tested", "QA",
"verification", "review", "device", ...) is the second carve-out. Every
trigger phrase has the same two senses: "not yet complete" / "still
outstanding" / "still needs" can each mean the *work itself* is unfinished
(genuine incompleteness -> flip to Pending) OR that a routine
pending-verification step is outstanding ("not yet tested", "verification
is still outstanding", "still needs a QA pass"), which rule 2 keeps at
"Code complete". Substring matching can't tell the two apart, so when any
trigger phrase has a verification word within a few words on either side,
the match is suppressed. This replaces the old approach of hand-patching
each trigger phrase (bare "not yet" was dropped, then "outstanding" and
"still needs" collided the same way); the rule is phrase-agnostic and
covers future trigger phrases too.

A trigger phrase sitting inside the second branch of an "X or Y"
alternative, immediately after "or", is the third carve-out (golden entry
15: "...are expected leftover comments or something that still needs
cleanup" - the AI hedging about whether a couple of pinning-comment
mentions matter, not reporting a second, separate unfinished task; the
narrative's real, Flagged-worthy issue is stated earlier in the same
paragraph and must not be swallowed by this incidental hedge). This is
deliberately a short, close-range lookback: it must not suppress a
genuinely separate second issue like "...and separately the app-side
change is being handed off to another agent", which still needs to flip a
"Flagged" commit's status to "Pending" per rule 13's spirit (see
test case trigger_overrides_flagged_too).

The trigger list deliberately excludes bare "not yet": under rule 2 the
model is expected to describe an untested mockup as "code-complete but not
yet tested", and that phrasing must NOT be flipped to "Pending". Only the
more specific "not yet complete / done / finished" phrasings, which speak
to the work itself rather than a pending verification step, are triggers.
Regression coverage for this lives in test_status_consistency_validator.py.

Usage:
    python3 prompt_contract_layer.py < records.jsonl | python3 status_consistency_validator.py
"""

import json
import re
import sys

from prompt_contract_layer import FOLLOW_UP_QUESTION

OUTSTANDING_PHRASES = [
    "still needs",
    # "not yet" on its own is deliberately NOT here: it matches "not yet
    # tested", which is rule 2's contractually-expected way of describing a
    # mockup or unverified change that should still read as "Code complete",
    # not "Pending". Only the phrasings below signal genuine incompleteness
    # of the work itself, not a pending verification step.
    "not yet complete",
    "not yet done",
    "not yet finished",
    "follow-up",
    "outstanding",
    "handed off",
]

NEGATION_WORDS = {"no", "not", "nothing", "without", "never"}

# Words that mark a routine pending-verification step rather than the work
# itself being unfinished. A trigger phrase with one of these within a few
# words on either side is a "not yet tested" / "verification is still
# outstanding" / "still needs a QA pass" situation, which rule 2 keeps at
# "Code complete". Matched against the lowercased narrative, tokenised the
# same way as the negation scan ("QA" -> "qa", "curl-verified" -> ["curl",
# "verified"]).
VERIFICATION_WORDS = {
    "tested",
    "testing",
    "qa",
    "verification",
    "verified",
    "review",
    "device",
}

# How many words immediately before a match to scan for a negation word.
# 5 catches "not a gap needing follow-up" (4 words back) but misses "no
# indication of any problems needing follow-up" (6 words back); widened
# to 8 to cover realistic hedged phrasing without scanning the whole
# sentence.
NEGATION_LOOKBACK_WORDS = 8

# How many words on EACH side of a trigger match to scan for a
# verification word. 5 catches "verification is still outstanding" (4 words
# back) and "still needs a visual QA pass" (3 words forward) without
# reaching an unrelated "curl-verified" 8 words back in a genuine
# "still needs to happen" sentence.
VERIFICATION_CONTEXT_WINDOW_WORDS = 5

# A third carve-out, same shape as the negation guard: a trigger phrase
# sitting inside the SECOND branch of an "X or Y" alternative is the AI
# presenting a hedge, not asserting Y is true. "...are expected leftover
# comments or something that still needs cleanup" is the AI wondering
# whether a couple of pinning-comment mentions matter, not reporting a
# second, separate piece of unfinished work - unlike, say, "...and
# separately the app-side change is being handed off to another agent",
# which names a real second task and must still trigger. A short lookback
# (3 catches "or something that still needs", the closest real case seen;
# wider risks swallowing a genuine "...done, but X, or is that actually
# still outstanding" report) keeps this narrow to the "or" sitting right
# next to the hedge, not anywhere earlier in the sentence.
HEDGE_WORDS = {"or"}
HEDGE_LOOKBACK_WORDS = 3

WORD_PATTERN = re.compile(r"[a-z']+")


def _is_negated(scan_text, match_start):
    preceding_words = WORD_PATTERN.findall(scan_text[:match_start])
    window = preceding_words[-NEGATION_LOOKBACK_WORDS:]
    return any(w in NEGATION_WORDS or w.endswith("n't") for w in window)


def _is_verification_context(scan_text, match_start, match_end):
    before = WORD_PATTERN.findall(scan_text[:match_start])[-VERIFICATION_CONTEXT_WINDOW_WORDS:]
    after = WORD_PATTERN.findall(scan_text[match_end:])[:VERIFICATION_CONTEXT_WINDOW_WORDS]
    return any(w in VERIFICATION_WORDS for w in before + after)


def _is_hedged_alternative(scan_text, match_start):
    preceding_words = WORD_PATTERN.findall(scan_text[:match_start])
    window = preceding_words[-HEDGE_LOOKBACK_WORDS:]
    return any(w in HEDGE_WORDS for w in window)


def validate_status(status, narrative):
    """Returns (possibly-corrected status, phrases that triggered the correction)."""
    scan_text = narrative.replace(FOLLOW_UP_QUESTION.strip(), "").lower()
    matched = []
    for phrase in OUTSTANDING_PHRASES:
        start = 0
        while True:
            idx = scan_text.find(phrase, start)
            if idx == -1:
                break
            end = idx + len(phrase)
            if (
                not _is_negated(scan_text, idx)
                and not _is_verification_context(scan_text, idx, end)
                and not _is_hedged_alternative(scan_text, idx)
            ):
                matched.append(phrase)
                break
            start = end
    if matched and status != "Pending":
        return "Pending", matched
    return status, []


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        original_status = record["status"]
        corrected_status, matched = validate_status(original_status, record["narrative"])
        if matched:
            record["status"] = corrected_status
            record["consistency_correction"] = {
                "original_status": original_status,
                "matched_phrases": matched,
            }
        print(json.dumps(record))


if __name__ == "__main__":
    main()
