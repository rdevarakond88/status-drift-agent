#!/usr/bin/env python3
"""Data generation for the Drift Trace dashboard (see build_drift_trace.py).

For every golden entry: build the record once (fetch-layer checks are
deterministic, no need to recompute per run), then run the AI pipeline
(generate_status_update + validate_status) once, or 3x for entries with
a history of flipping run-to-run across past sessions (see
docs/eval-v*-findings.md) so a dashboard reader can tell a genuine miss
from one-off model wording. Update VARIANCE_ENTRIES if a different entry
starts showing that pattern.

Writes eval_output/results-dashboard-full.jsonl, one row per golden file,
capturing raw AI status/narrative, post-rule status/narrative, and
post-validator status/matched-phrases for every run.

Usage:
    EVAL_TARGET_REPO=/path/to/target/repo python3 run_dashboard_eval.py
"""
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ))

from run_golden_eval import build_record  # noqa: E402
from prompt_contract_layer import generate_status_update  # noqa: E402
from status_consistency_validator import validate_status  # noqa: E402

GOLDEN_DIR = PROJ / "golden-set"
OUT = PROJ / "eval_output" / "results-dashboard-full.jsonl"

VARIANCE_ENTRIES = {"01.json", "03.json", "06.json", "09.json", "15.json", "17.json"}
CHECK_KEYS = ["sweeping_claim_check", "overclaim_check", "ui_copy_removal_check", "unexplained_deletions"]


def one_run(record):
    output = generate_status_update(record)
    corrected, matched = validate_status(output["status"], output["narrative"])
    return {
        "raw_status": output["raw_status"],
        "raw_narrative": output["raw_narrative"],
        "rule_status": output["status"],
        "rule_narrative": output["narrative"],
        "validator_status": corrected if matched else output["status"],
        "matched_phrases": matched,
    }


def main():
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    OUT.parent.mkdir(exist_ok=True)
    rows = []
    for gf in golden_files:
        golden = json.loads(gf.read_text())
        print(f"[{gf.name}] building record...", file=sys.stderr, flush=True)
        record = build_record(gf.name)
        checks = {k: record.get(k) for k in CHECK_KEYS}

        n = 3 if gf.name in VARIANCE_ENTRIES else 1
        runs = []
        for i in range(n):
            print(f"[{gf.name}] run {i + 1}/{n} calling model...", file=sys.stderr, flush=True)
            try:
                r = one_run(record)
            except Exception as e:
                r = {"raw_status": "ERROR", "raw_narrative": f"{type(e).__name__}: {e}",
                     "rule_status": "ERROR", "rule_narrative": "", "validator_status": "ERROR",
                     "matched_phrases": []}
            runs.append(r)
            print(f"[{gf.name}] run {i + 1}/{n} -> raw={r['raw_status']} rule={r['rule_status']} validator={r['validator_status']}",
                  file=sys.stderr, flush=True)

        rows.append({"golden_file": gf.name, "golden": golden, "checks": checks, "runs": runs})

    with OUT.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nWrote {len(rows)} entries to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
