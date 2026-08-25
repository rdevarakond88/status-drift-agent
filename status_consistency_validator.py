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

Usage:
    python3 prompt_contract_layer.py < records.jsonl | python3 status_consistency_validator.py
"""

import json
import sys

from prompt_contract_layer import FOLLOW_UP_QUESTION

OUTSTANDING_PHRASES = [
    "still needs",
    "not yet",
    "follow-up",
    "outstanding",
    "handed off",
]


def validate_status(status, narrative):
    """Returns (possibly-corrected status, phrases that triggered the correction)."""
    scan_text = narrative.replace(FOLLOW_UP_QUESTION.strip(), "").lower()
    matched = [phrase for phrase in OUTSTANDING_PHRASES if phrase in scan_text]
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
