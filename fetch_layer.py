#!/usr/bin/env python3
"""Layer 1 of status-translation-agent: deterministic commit fetch, no AI calls.

Usage:
    python3 fetch_layer.py --repo /path/to/repo --branch dev
    python3 fetch_layer.py --repo /path/to/repo --branch main

Checkpoint file: checkpoints.json (next to this script, or --checkpoint-file).
Output: one JSON object per new commit, written as JSONL to output/<branch>__<run_timestamp>.jsonl
and echoed to stdout.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT_FILE = SCRIPT_DIR / "checkpoints.json"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"
STORY_PATTERN = re.compile(r"\b([DP]\d{1,2})\b")


def run_git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def resolve_ref(repo, branch):
    for candidate in (f"origin/{branch}", branch):
        try:
            sha = run_git(repo, "rev-parse", candidate).strip()
            return candidate, sha
        except RuntimeError:
            continue
    raise RuntimeError(f"could not resolve branch '{branch}' as origin/{branch} or {branch}")


def load_checkpoints(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_checkpoints(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def get_repo_slug(repo):
    url = run_git(repo, "remote", "get-url", "origin").strip()
    # handles both git@github.com:owner/repo.git and https://github.com/owner/repo.git
    match = re.search(r"[:/]([^/:]+/[^/]+?)(\.git)?$", url)
    if not match:
        raise RuntimeError(f"could not parse owner/repo from remote url: {url}")
    return match.group(1)


def get_new_commit_shas(repo, since_sha, ref):
    out = run_git(repo, "rev-list", "--reverse", f"{since_sha}..{ref}")
    return [line for line in out.splitlines() if line]


def get_pr_metadata(repo_slug, sha):
    result = subprocess.run(
        ["gh", "api", f"repos/{repo_slug}/commits/{sha}/pulls"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    prs = json.loads(result.stdout)
    return [
        {"number": pr["number"], "title": pr["title"], "description": pr.get("body") or ""}
        for pr in prs
    ]


def attribute_story(commit_message, branch, prs):
    checks = [("commit_message", commit_message), ("branch_name", branch)]
    for pr in prs:
        checks.append((f"pr_{pr['number']}_title", pr["title"]))
        checks.append((f"pr_{pr['number']}_description", pr["description"]))

    for source, text in checks:
        match = STORY_PATTERN.search(text or "")
        if match:
            return {"status": "matched", "story_id": match.group(1), "matched_in": source}

    return {"status": "unattributed", "story_id": None, "matched_in": None}


def get_commit_record(repo, sha, branch, repo_slug):
    subject = run_git(repo, "log", "-1", "--format=%s", sha).strip()
    body = run_git(repo, "log", "-1", "--format=%b", sha).strip()
    author = run_git(repo, "log", "-1", "--format=%an <%ae>", sha).strip()
    authored_at = run_git(repo, "log", "-1", "--format=%aI", sha).strip()
    parents = run_git(repo, "log", "-1", "--format=%P", sha).strip().split()
    is_merge = len(parents) > 1

    files_changed = [
        line for line in run_git(repo, "show", "--name-only", "--format=", sha).splitlines() if line
    ]

    diff_args = ["show", "--format=", "-p"]
    if is_merge:
        diff_args = ["show", "--first-parent", "--format=", "-p"]
    full_diff = run_git(repo, *diff_args, sha)

    prs = get_pr_metadata(repo_slug, sha)
    commit_message = (subject + "\n\n" + body).strip() if body else subject

    return {
        "commit_id": sha,
        "branch": branch,
        "author": author,
        "authored_at": authored_at,
        "is_merge_commit": is_merge,
        "commit_message": commit_message,
        "files_changed": files_changed,
        "full_diff": full_diff,
        "pr_metadata": prs,
        "story_attribution": attribute_story(commit_message, branch, prs),
    }


def main():
    parser = argparse.ArgumentParser(description="Deterministic commit fetch layer")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--checkpoint-file", default=str(DEFAULT_CHECKPOINT_FILE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    checkpoint_path = Path(args.checkpoint_file)
    output_dir = Path(args.output_dir)
    branch = args.branch

    run_git(repo, "fetch", "origin")
    ref, head_sha = resolve_ref(repo, branch)

    checkpoints = load_checkpoints(checkpoint_path)
    entry = checkpoints.get(branch)

    if entry is None:
        checkpoints[branch] = {
            "last_sha": head_sha,
            "last_run_utc": datetime.now(timezone.utc).isoformat(),
            "stories": {},
        }
        save_checkpoints(checkpoint_path, checkpoints)
        print(f"No checkpoint existed for branch '{branch}' — initialized at current HEAD "
              f"({head_sha[:7]}, via {ref}). No commits processed this run.")
        return

    last_sha = entry["last_sha"]

    if last_sha == head_sha:
        print("No change since last update")
        return

    new_shas = get_new_commit_shas(repo, last_sha, ref)

    if not new_shas:
        print(f"WARNING: checkpoint SHA {last_sha[:7]} is not an ancestor of {ref} "
              f"({head_sha[:7]}) — branch history may have been rewritten (rebase/force-push). "
              f"Checkpoint NOT advanced. Manual review recommended.")
        sys.exit(1)

    repo_slug = get_repo_slug(repo)
    records = [get_commit_record(repo, sha, branch, repo_slug) for sha in new_shas]

    output_dir.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_branch = re.sub(r"[^\w.-]", "_", branch)
    out_path = output_dir / f"{safe_branch}__{run_ts}.jsonl"
    with out_path.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    for record in records:
        print(json.dumps(record))

    entry["last_sha"] = new_shas[-1]
    entry["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    stories = entry.setdefault("stories", {})
    for record in records:
        story_id = record["story_attribution"]["story_id"] or "unattributed"
        stories[story_id] = {
            "last_sha": record["commit_id"],
            "last_seen_utc": datetime.now(timezone.utc).isoformat(),
        }
    save_checkpoints(checkpoint_path, checkpoints)


if __name__ == "__main__":
    main()
