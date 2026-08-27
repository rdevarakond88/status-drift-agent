#!/usr/bin/env python3
"""Score eval_output/results.jsonl against the golden set on status match.

No AI. Compares each entry's generated status to golden verified_status
and prints a per-entry table plus the headline N/23.

    python3 score_golden_eval.py [results.jsonl]
"""
import json
import sys
from pathlib import Path

RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "eval_output" / "results.jsonl"


def main():
    rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()]
    match = 0
    print(f"{'file':<10} {'commit':<16} {'golden':<14} {'generated':<14} {'':<4} correction")
    print("-" * 78)
    for r in rows:
        gf = r["golden_file"]
        golden = r["golden"]["verified_status"]
        gen = r["generated"]["status"]
        commit = r["golden"].get("commit_id", "")
        corr = r["generated"].get("consistency_correction")
        corr_str = ""
        if corr:
            corr_str = f'{corr["original_status"]} -> Pending via {corr["matched_phrases"]}'
        ok = golden == gen
        match += ok
        print(f"{gf:<10} {commit:<16} {golden:<14} {gen:<14} {'ok' if ok else 'MISS':<4} {corr_str}")
    print("-" * 78)
    print(f"{match}/{len(rows)} match on status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
