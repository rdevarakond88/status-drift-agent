#!/usr/bin/env python3
"""Self-consistency eval run.

- Entries 01,03,04,06,09,13,14,22: run the AI pipeline 3x each (fresh
  `claude -p` subprocess calls; independent, nothing cached).
- Entry 15 + every other entry: run once.

Writes eval_output/results-selfconsistency.jsonl with one row per golden
file, each row carrying every run's raw model status, post-validator
status, matched phrases, and narrative.
"""
import json
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ))

# EVAL_TARGET_REPO must be set by the caller (a local clone of the target
# repo the 19 real golden shas resolve against), same as run_golden_eval.py.

from run_golden_eval import build_record  # noqa: E402
from prompt_contract_layer import generate_status_update  # noqa: E402
from status_consistency_validator import validate_status  # noqa: E402

GOLDEN_DIR = PROJ / "golden-set"
OUT = PROJ / "eval_output" / "results-selfconsistency.jsonl"

MULTI = {"01.json", "03.json", "04.json", "06.json", "09.json", "13.json", "14.json", "22.json"}


def one_run(record):
    output = generate_status_update(record)
    original_status = output["status"]
    corrected_status, matched = validate_status(original_status, output["narrative"])
    return {
        "model_status": original_status,
        "validated_status": corrected_status if matched else original_status,
        "matched_phrases": matched,
        "narrative": output["narrative"],
    }


def main():
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    OUT.parent.mkdir(exist_ok=True)
    rows = []
    for gf in golden_files:
        golden = json.loads(gf.read_text())
        n = 3 if gf.name in MULTI else 1
        runs = []
        for i in range(n):
            print(f"[{gf.name}] run {i+1}/{n} building+calling model...", file=sys.stderr, flush=True)
            record = build_record(gf.name)
            try:
                r = one_run(record)
            except Exception as e:
                r = {"model_status": "ERROR", "validated_status": "ERROR",
                     "matched_phrases": [], "narrative": f"{type(e).__name__}: {e}"}
            runs.append(r)
            print(f"[{gf.name}] run {i+1} -> model={r['model_status']} validated={r['validated_status']} {r['matched_phrases']}",
                  file=sys.stderr, flush=True)
            time.sleep(1)
        rows.append({
            "golden_file": gf.name,
            "commit_id": golden.get("commit_id", ""),
            "verified_status": golden["verified_status"],
            "n_runs": n,
            "runs": runs,
        })
        with OUT.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    print(f"\nWrote {len(rows)} rows to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
