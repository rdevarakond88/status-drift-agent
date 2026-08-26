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

Usage:
    python3 prompt_contract_layer.py < records.jsonl | python3 status_consistency_validator.py
"""

import json
import re
import sys

from prompt_contract_layer import FOLLOW_UP_QUESTION

OUTSTANDING_PHRASES = [
    "still needs",
    "not yet",
    "follow-up",
    "outstanding",
    "handed off",
]

NEGATION_WORDS = {"no", "not", "nothing", "without", "never"}

# How many words immediately before a match to scan for a negation word.
# 5 catches "not a gap needing follow-up" (4 words back) but misses "no
# indication of any problems needing follow-up" (6 words back); widened
# to 8 to cover realistic hedged phrasing without scanning the whole
# sentence.
NEGATION_LOOKBACK_WORDS = 8

WORD_PATTERN = re.compile(r"[a-z']+")


def _is_negated(scan_text, match_start):
    preceding_words = WORD_PATTERN.findall(scan_text[:match_start])
    window = preceding_words[-NEGATION_LOOKBACK_WORDS:]
    return any(w in NEGATION_WORDS or w.endswith("n't") for w in window)


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
            if not _is_negated(scan_text, idx):
                matched.append(phrase)
                break
            start = idx + len(phrase)
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
