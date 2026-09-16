#!/usr/bin/env python3
"""Extract historical `claude -p` calls from this project's own Claude Code
session logs (~/.claude/projects/-home-rdeva-status-translation-agent/*.jsonl)
and import them into Langfuse as traces with their real historical
timestamps, joined to golden-set entries where possible.

Each `sdk-cli`-entrypoint session log file is exactly one
`prompt_contract_layer.call_claude` invocation:
  - a `type: "user"` record: timestamp + the exact `build_user_prompt(record)`
    JSON string sent as stdin.
  - a `type: "attachment"` record with `attachment.type == "prompt_snapshot"`:
    the full system prompt.
  - one or more `type: "assistant"` records sharing a requestId: timestamp,
    model, usage, stop_reason, effort, and content blocks (thinking + the
    final {status, narrative} text block).

Uses the classic Langfuse batch ingestion API (POST /api/public/ingestion)
directly rather than the v4 Python SDK, because the SDK is OTEL-based and
ties observation start_time to wall-clock "now" - the ingestion API's
trace-create/generation-create events accept explicit historical
timestamp/startTime/endTime fields, which is required here.

Usage:
    python3 import_historical_traces.py --limit 20      # pilot sample
    python3 import_historical_traces.py --all            # all 489
    python3 import_historical_traces.py --limit 20 --dry-run
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import langfuse_client
from prompt_contract_layer import parse_model_output

SESSION_LOG_DIR = os.path.expanduser(
    "~/.claude/projects/-home-rdeva-status-translation-agent"
)
GOLDEN_SET_DIR = os.path.join(os.path.dirname(__file__), "golden-set")
DEFAULT_EVAL_TARGET_REPO = os.environ.get("EVAL_TARGET_REPO", "/home/rdeva/medrecord")




# ── session-log parsing ─────────────────────────────────────────────────

def parse_session_file(path):
    """Returns None if this file isn't an sdk-cli claude -p call. Otherwise
    a dict with the raw pieces needed to build a trace."""
    entrypoint = None
    user_record = None
    system_prompt = None
    assistant_records = []

    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entrypoint is None and "entrypoint" in d:
                entrypoint = d["entrypoint"]
            t = d.get("type")
            if t == "user" and user_record is None:
                user_record = d
            elif (
                t == "attachment"
                and d.get("attachment", {}).get("type") == "prompt_snapshot"
                and system_prompt is None
            ):
                sp = d["attachment"].get("systemPrompt")
                system_prompt = sp[0] if isinstance(sp, list) else sp
            elif t == "assistant":
                assistant_records.append(d)

    if entrypoint != "sdk-cli" or user_record is None:
        return None

    # Keep only the assistant records sharing the requestId of the LAST one
    # (guards against retries within a single file; in practice there's one
    # requestId shared by a thinking-block record and a text-block record).
    group = []
    if assistant_records:
        last_request_id = assistant_records[-1].get("requestId")
        group = [a for a in assistant_records if a.get("requestId") == last_request_id]

    blocks = []
    for a in group:
        blocks.extend(a.get("message", {}).get("content", []))

    thinking_text = "\n".join(
        b.get("thinking", "") for b in blocks if b.get("type") == "thinking"
    )
    text_blocks = [b for b in blocks if b.get("type") == "text"]
    final_text = text_blocks[-1]["text"] if text_blocks else None

    return {
        "path": path,
        "file_uuid": Path(path).stem,
        "user_timestamp": user_record.get("timestamp"),
        "user_content": user_record.get("message", {}).get("content"),
        "system_prompt": system_prompt,
        "group": group,
        "thinking_text": thinking_text,
        "final_text": final_text,
        "last_assistant_timestamp": group[-1]["timestamp"] if group else None,
        "model": group[0]["message"].get("model") if group else None,
        "stop_reason": group[-1]["message"].get("stop_reason") if group else None,
        "effort": group[-1].get("effort") if group else None,
        "request_id": group[-1].get("requestId") if group else None,
        "usage": group[-1]["message"].get("usage") if group else None,
    }


def classify(record):
    """Returns one of: no-response, connectivity-ping, json-parse-failure,
    json-repaired, clean."""
    if record["final_text"] is None:
        return "no-response"

    try:
        payload = json.loads(record["user_content"])
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict) and set(payload.keys()) == {"ping"}:
        return "connectivity-ping"

    text = record["final_text"].strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        json.loads(text)
        return "clean"
    except json.JSONDecodeError:
        pass

    try:
        parse_model_output(record["final_text"])
        return "json-repaired"
    except Exception:
        return "json-parse-failure"


# ── golden-set join ─────────────────────────────────────────────────────

def build_golden_index(eval_target_repo):
    """Maps full commit message text -> golden entry, for every golden-set
    entry with a real (non-synthetic) commit_id, resolved via `git log` in
    the eval target repo. Also keeps a subject-line-only index for uncertain
    matches."""
    by_message = {}
    by_subject = {}
    for path in sorted(glob.glob(os.path.join(GOLDEN_SET_DIR, "*.json"))):
        entry = json.load(open(path))
        commit_id = entry["commit_id"]
        if commit_id.startswith("synthetic-"):
            continue
        # PR-level entries look like "PR-6 (merge cb66d392)" - resolve the
        # actual merge commit's sha for the git lookup, not the label.
        sha_match = re.search(r"[0-9a-f]{7,40}", commit_id)
        git_ref = sha_match.group(0) if sha_match else commit_id
        result = subprocess.run(
            ["git", "-C", eval_target_repo, "log", "-1", "--format=%B", git_ref],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  warning: could not resolve {commit_id} ({path}): {result.stderr.strip()}", file=sys.stderr)
            continue
        message = result.stdout.rstrip("\n")
        entry["_golden_file"] = os.path.basename(path)
        by_message[message] = entry
        by_subject[message.splitlines()[0]] = entry
    return by_message, by_subject


def join_golden(record, by_message, by_subject):
    try:
        payload = json.loads(record["user_content"])
        commit_message = payload.get("commit_message")
    except (json.JSONDecodeError, TypeError):
        commit_message = None
    if not commit_message:
        return None, "none"
    if commit_message in by_message:
        return by_message[commit_message], "confident"
    subject = commit_message.splitlines()[0]
    if subject in by_subject:
        return by_subject[subject], "uncertain"
    return None, "none"


# ── pilot selection ─────────────────────────────────────────────────────

def select_pilot(all_records, limit):
    by_class = {}
    for r in all_records:
        by_class.setdefault(r["_class"], []).append(r)

    selected = []
    # Always include every edge case we know about, up to what exists.
    for cls in ("json-parse-failure", "no-response", "connectivity-ping", "json-repaired"):
        selected.extend(by_class.get(cls, []))

    remaining = limit - len(selected)
    if remaining > 0:
        clean = sorted(by_class.get("clean", []), key=lambda r: r["user_timestamp"])
        if clean:
            step = max(1, len(clean) // remaining)
            for i in range(0, len(clean), step):
                if remaining <= 0:
                    break
                selected.append(clean[i])
                remaining -= 1
    return selected[:limit] if limit else selected


# ── Langfuse ingestion ──────────────────────────────────────────────────

def build_events(record, golden_entry, match_kind):
    trace_id = record["file_uuid"]
    obs_id = f"{trace_id}-gen"
    tags = ["sdk-cli", f"parse:{record['_class']}", f"golden-match:{match_kind}"]
    if golden_entry:
        tags.append(f"golden:{golden_entry['_golden_file']}")

    try:
        payload = json.loads(record["user_content"])
        commit_message = payload.get("commit_message")
    except (json.JSONDecodeError, TypeError):
        payload = record["user_content"]
        commit_message = None

    metadata = {
        "file": os.path.basename(record["path"]),
        "request_id": record["request_id"],
        "stop_reason": record["stop_reason"],
        "effort": record["effort"],
        "parse_class": record["_class"],
        "golden_match": match_kind,
    }
    if golden_entry:
        metadata["golden_commit_id"] = golden_entry["commit_id"]
        metadata["golden_verified_status"] = golden_entry["verified_status"]

    trace_event = {
        "id": str(uuid.uuid4()),
        "type": "trace-create",
        "timestamp": record["user_timestamp"],
        "body": {
            "id": trace_id,
            "timestamp": record["user_timestamp"],
            "name": "generate_status_update",
            "input": payload,
            "output": record["final_text"],
            "metadata": metadata,
            "tags": tags,
        },
    }

    if record["last_assistant_timestamp"] is None:
        return [trace_event]

    generation_event = {
        "id": str(uuid.uuid4()),
        "type": "generation-create",
        "timestamp": record["user_timestamp"],
        "body": {
            "id": obs_id,
            "traceId": trace_id,
            "name": "call_claude",
            "startTime": record["user_timestamp"],
            "endTime": record["last_assistant_timestamp"],
            "model": record["model"],
            "input": {
                "system_prompt": record["system_prompt"],
                "user_prompt": commit_message and payload or record["user_content"],
            },
            "output": record["final_text"],
            "usageDetails": langfuse_client.usage_details(record["usage"]),
            "metadata": {
                **metadata,
                "thinking": record["thinking_text"],
            },
            "level": "ERROR" if record["_class"] == "json-parse-failure" else "DEFAULT",
            "statusMessage": record["_class"],
        },
    }
    return [trace_event, generation_event]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="pilot sample size (ignored with --all)")
    ap.add_argument("--all", action="store_true", help="import all 489 sdk-cli files, not just a pilot sample")
    ap.add_argument("--dry-run", action="store_true", help="classify and join only, print summary, push nothing")
    ap.add_argument("--eval-target-repo", default=DEFAULT_EVAL_TARGET_REPO)
    args = ap.parse_args()

    print(f"Scanning {SESSION_LOG_DIR} ...")
    all_files = sorted(glob.glob(os.path.join(SESSION_LOG_DIR, "*.jsonl")))
    records = []
    for path in all_files:
        r = parse_session_file(path)
        if r is None:
            continue
        r["_class"] = classify(r)
        records.append(r)
    print(f"  {len(records)} sdk-cli claude -p call files parsed")

    by_class_count = {}
    for r in records:
        by_class_count[r["_class"]] = by_class_count.get(r["_class"], 0) + 1
    print(f"  breakdown: {by_class_count}")

    print(f"Resolving golden-set commit messages via {args.eval_target_repo} ...")
    by_message, by_subject = build_golden_index(args.eval_target_repo)
    print(f"  {len(by_message)} real golden entries resolved")

    if args.all:
        selected = records
    else:
        selected = select_pilot(records, args.limit)
    print(f"Selected {len(selected)} records to import")

    match_counts = {"confident": 0, "uncertain": 0, "none": 0}
    all_events = []
    for r in selected:
        golden_entry, match_kind = join_golden(r, by_message, by_subject)
        match_counts[match_kind] += 1
        tag = f"[{r['_class']:>18}] [{match_kind:>9}]"
        golden_note = f" -> {golden_entry['_golden_file']}" if golden_entry else ""
        print(f"  {tag} {os.path.basename(r['path'])}{golden_note}")
        all_events.extend(build_events(r, golden_entry, match_kind))

    print(f"Golden-set join: {match_counts}")
    print(f"Built {len(all_events)} ingestion events "
          f"({len([e for e in all_events if e['type']=='trace-create'])} traces, "
          f"{len([e for e in all_events if e['type']=='generation-create'])} generations)")

    if args.dry_run:
        print("Dry run - nothing pushed.")
        return

    creds = langfuse_client.load_credentials()
    if creds is None:
        sys.exit(f"No Langfuse credentials found (checked LANGFUSE_PUBLIC_KEY/"
                  f"LANGFUSE_SECRET_KEY env vars and {langfuse_client._ENV_FILE}).")
    print(f"Pushing to {creds['host']} ...")
    # Batch in chunks to keep request bodies reasonable (full diffs can be large).
    CHUNK = 20
    for i in range(0, len(all_events), CHUNK):
        chunk = all_events[i:i + CHUNK]
        result = langfuse_client.push_batch(chunk, creds, timeout=30)
        errors = result.get("errors", [])
        if errors:
            print(f"  chunk {i}-{i+len(chunk)}: {len(errors)} errors: {errors[:3]}")
        else:
            print(f"  chunk {i}-{i+len(chunk)}: ok ({len(result.get('successes', []))} accepted)")

    print("Done.")


if __name__ == "__main__":
    main()
