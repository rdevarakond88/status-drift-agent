#!/usr/bin/env python3
"""One-off harness: builds fetch-layer-shaped records for all 23 golden-set
entries (pulling 19 of them from a private production repo's real commit
history via fetch_layer's own commit-reading code; hand-building the four
synthetic entries, which have no real commit to pull), runs each through
prompt_contract_layer, and writes results next to the golden answers for
comparison.

The 19 real entries were built and reviewed against a private repo not
included here. Only the golden-set descriptions and eval results are
public, not that repo's code. Point EVAL_TARGET_REPO at a local clone of
your own target repo to reproduce this harness.
"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fetch_layer import (  # noqa: E402
    get_commit_record,
    get_repo_slug,
    compute_touches_app_code,
    detect_sweeping_claims,
)
from prompt_contract_layer import generate_status_update  # noqa: E402
from status_consistency_validator import validate_status  # noqa: E402

REPO = Path(os.environ.get("EVAL_TARGET_REPO", "/path/to/target-repo"))
GOLDEN_DIR = SCRIPT_DIR / "golden-set"
RESULTS_PATH = SCRIPT_DIR / "eval_output" / "results.jsonl"

# golden filename -> real commit sha (branch used for the fetch-layer record)
REAL_COMMITS = {
    "01.json": ("fee9cd5", "dev"),
    "02.json": ("6a19a8f", "dev"),
    "03.json": ("5572d95", "dev"),
    "04.json": ("56af773", "dev"),
    "05.json": ("6f43663", "dev"),
    "06.json": ("802e444", "dev"),
    "07.json": ("52fb363", "dev"),
    "08.json": ("24ef723", "dev"),
    "09.json": ("ce67468", "dev"),
    "10.json": ("af0360e", "dev"),
    "11.json": ("9cfe9eb", "dev"),
    "12.json": ("aa4f769", "dev"),
    "13.json": ("2dab6c7", "dev"),
    "14.json": ("cb66d392", "main"),  # PR #6 merge commit: the whole bundle as one diff
    "15.json": ("6aa36a6", "main"),
    "16.json": ("91b2e6e", "dev"),
    "17.json": ("afce46a", "dev"),
    "18.json": ("a84d816", "dev"),
    "19.json": ("b3383fa", "dev"),
}


def synthetic_record(commit_id, branch, commit_message, files_changed, full_diff):
    return {
        "commit_id": commit_id,
        "branch": branch,
        "author": "synthetic <n/a>",
        "authored_at": None,
        "is_merge_commit": False,
        "commit_message": commit_message,
        "files_changed": files_changed,
        "full_diff": full_diff,
        "pr_metadata": [],
        "touches_app_code": compute_touches_app_code(files_changed),
        "sweeping_claim_check": _synthetic_sweeping_claim_check(commit_message),
    }


def _synthetic_sweeping_claim_check(commit_message):
    # Synthetic entries have no real repo tree to grep, so detection-only:
    # keyword matches are reported, but nothing gets verified against a repo.
    matched_keywords, _claimed_texts = detect_sweeping_claims(commit_message)
    return {
        "detected": bool(matched_keywords),
        "keywords_matched": matched_keywords,
        "verifications": [],
    }


SYNTHETIC_RECORDS = {
    "20.json": synthetic_record(
        "synthetic-001", "quick-fix", "fix bug",
        ["src/utils/retryHelper.ts", "src/config/limits.ts"],
        """diff --git a/src/utils/retryHelper.ts b/src/utils/retryHelper.ts
index 1a2b3c4..5d6e7f8 100644
--- a/src/utils/retryHelper.ts
+++ b/src/utils/retryHelper.ts
@@ -12,7 +12,7 @@ export function withRetry<T>(fn: () => Promise<T>): Promise<T> {
-  const MAX_ATTEMPTS = 3;
+  const MAX_ATTEMPTS = 5;
   let attempt = 0;
diff --git a/src/config/limits.ts b/src/config/limits.ts
index 9a8b7c6..3d2e1f0 100644
--- a/src/config/limits.ts
+++ b/src/config/limits.ts
@@ -4,5 +4,5 @@ export const LIMITS = {
-  MAX_ITEMS: 50,
+  MAX_ITEMS: 100,
 };
""",
    ),
    "21.json": synthetic_record(
        "synthetic-002", "dev", "Fixed the sync bug, all edge cases handled now.",
        ["src/sync/syncWorker.ts"],
        """diff --git a/src/sync/syncWorker.ts b/src/sync/syncWorker.ts
index 2b3c4d5..6e7f8a9 100644
--- a/src/sync/syncWorker.ts
+++ b/src/sync/syncWorker.ts
@@ -40,10 +40,18 @@ async function processQueueItem(item: QueueItem) {
-  const response = await pinnedFetch(url, { method: 'POST', body });
-  if (!response.ok) {
-    item.status = 'failed';
-    return;
-  }
+  let response;
+  try {
+    response = await pinnedFetch(url, { method: 'POST', body });
+  } catch (err) {
+    // dropped-connection retry: one retry after a short backoff
+    await sleep(1500);
+    response = await pinnedFetch(url, { method: 'POST', body });
+  }
+  if (!response.ok) {
+    item.status = 'failed';
+    return;
+  }
   item.status = 'synced';
 }

 // offline-queue draining (device regains connectivity): unchanged, see drainOfflineQueue()
""",
    ),
    "22.json": synthetic_record(
        "synthetic-003", "dev", "Updated component per design spec, QA verified.",
        ["src/screens/patient/ProfileScreen.tsx"],
        """diff --git a/src/screens/patient/ProfileScreen.tsx b/src/screens/patient/ProfileScreen.tsx
index 4c5d6e7..8f9a0b1 100644
--- a/src/screens/patient/ProfileScreen.tsx
+++ b/src/screens/patient/ProfileScreen.tsx
@@ -88,8 +88,8 @@ const styles = StyleSheet.create({
   header: {
-    paddingVertical: 12,
-    backgroundColor: Colors.surface,
+    paddingVertical: 20,
+    backgroundColor: Colors.primaryBlueLight,
   },
   headerTitle: {
-    fontSize: 18,
+    fontSize: 22,
   },
""",
    ),
    "23.json": synthetic_record(
        "synthetic-004", "dev",
        "Refactored auth module for performance; all existing tests pass, no behavioral change.\n\n"
        "Co-Authored-By: Codex <noreply@openai.com>",
        ["backend/src/middleware/authorize.ts"],
        """diff --git a/backend/src/middleware/authorize.ts b/backend/src/middleware/authorize.ts
index 5e6f7a8..9b0c1d2 100644
--- a/backend/src/middleware/authorize.ts
+++ b/backend/src/middleware/authorize.ts
@@ -21,7 +21,7 @@ export function authorize(req: Request, res: Response, next: NextFunction) {
   const role = req.user?.role;
-  if (role === 'doctor' && resourceOwnerId === req.user.id) {
+  if (role === 'doctor' || resourceOwnerId === req.user.id) {
     return next();
   }
   return res.status(403).json({ error: 'FORBIDDEN' });
""",
    ),
}


def attribute_story(commit_message, branch):
    from fetch_layer import attribute_story as fetch_attribute
    return fetch_attribute(commit_message, branch, [])


def build_record(filename):
    if filename in REAL_COMMITS:
        sha, branch = REAL_COMMITS[filename]
        repo_slug = get_repo_slug(REPO)
        return get_commit_record(REPO, sha, branch, repo_slug)
    record = SYNTHETIC_RECORDS[filename]
    record["story_attribution"] = attribute_story(record["commit_message"], record["branch"])
    return record


def main():
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    RESULTS_PATH.parent.mkdir(exist_ok=True)

    results = []
    for gf in golden_files:
        golden = json.loads(gf.read_text())
        print(f"[{gf.name}] building record for {golden['commit_id']}...", file=sys.stderr)
        record = build_record(gf.name)
        print(f"[{gf.name}] calling model...", file=sys.stderr)
        try:
            output = generate_status_update(record)
            original_status = output["status"]
            corrected_status, matched = validate_status(original_status, output["narrative"])
            if matched:
                output["status"] = corrected_status
                output["consistency_correction"] = {
                    "original_status": original_status,
                    "matched_phrases": matched,
                }
        except Exception as e:
            output = {"commit_id": golden["commit_id"], "status": "ERROR", "narrative": str(e), "completion": None}
        results.append({"golden_file": gf.name, "golden": golden, "generated": output})
        print(f"[{gf.name}] -> {output['status']}", file=sys.stderr)

    with RESULTS_PATH.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote {len(results)} results to {RESULTS_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
