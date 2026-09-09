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

# Extensions treated as "real source" for touches_app_code. Anything else
# (markdown, JSON/YAML/log files, etc) counts as docs/logs/config, not app code.
APP_CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".rb", ".java", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".php",
    ".css", ".scss", ".less", ".html", ".vue",
    ".m", ".mm", ".sh", ".bash", ".sql",
}


def compute_touches_app_code(files_changed):
    """True if any changed file is a real source file, False if the diff
    only touches docs/logs/config."""
    return any(Path(f).suffix.lower() in APP_CODE_EXTENSIONS for f in files_changed)


# Fixed trigger list: commit-message language that claims something holds
# across the whole codebase, not just in the lines the diff shows.
SWEEPING_CLAIM_KEYWORDS = [
    "anywhere",
    "everywhere",
    "no longer exists",
    "no longer appears",
    "completely",
    "entirely",
    "nowhere",
    "all instances",
]

# A sweeping claim is only checkable if the message also quotes the
# specific text being claimed absent (a URL, an error string, etc).
QUOTED_TEXT_PATTERN = re.compile(r"['\"]([^'\"]{3,120})['\"]")


def detect_sweeping_claims(commit_message):
    lowered = commit_message.lower()
    matched_keywords = [kw for kw in SWEEPING_CLAIM_KEYWORDS if kw in lowered]
    claimed_texts = QUOTED_TEXT_PATTERN.findall(commit_message) if matched_keywords else []
    return matched_keywords, claimed_texts


def verify_claim_against_repo(repo, sha, claimed_text):
    """Greps the repo tree as of sha (not just this commit's diff) for the
    literal claimed text, so a claim about the whole codebase gets checked
    against the whole codebase, not just what the diff happens to show."""
    result = subprocess.run(
        ["git", "-C", str(repo), "grep", "-n", "-F", claimed_text, sha],
        capture_output=True, text=True,
    )
    still_found_at = [line for line in result.stdout.splitlines() if line]
    return {
        "claimed_text": claimed_text,
        "still_found_at": still_found_at,
        "claim_holds": len(still_found_at) == 0,
    }


def build_sweeping_claim_check(repo, sha, commit_message):
    matched_keywords, claimed_texts = detect_sweeping_claims(commit_message)
    if not matched_keywords:
        return {"detected": False, "keywords_matched": [], "verifications": []}
    verifications = [verify_claim_against_repo(repo, sha, text) for text in claimed_texts]
    return {
        "detected": True,
        "keywords_matched": matched_keywords,
        "verifications": verifications,
    }


# ── Overclaim check ─────────────────────────────────────────────────────
#
# A commit or PR message that says a feature was "added" / "introduced" /
# is "new" is making a checkable factual claim: the named thing did not
# exist before this commit. When the message also names WHERE it went (a
# screen, a component, a file), that resolves to real files and git
# history answers the question directly, no model judgment.
#
# Flag condition: the named thing was already present in force in those
# files at the parent commit, and this commit barely changed how much of
# it is there. That is "it was already there, nothing was added" - a
# verified overclaim, handed to the model as a plain fact rather than
# something it has to reason its way to (see golden entry 14: PR #6's body
# says an OTP resend button was "added to" both login screens; the diff
# only lowers an existing 45s cooldown to 30s).
#
# This is a heuristic, not a proof:
#   - it leans on a stop-word list to tell a feature name ("resend") from
#     a generic word ("entry point"); the list will need tuning
#   - it only fires when a location term resolves to a file, so a claim
#     with no "added to <place>" is recorded but not checked
#   - the frequency guard is what keeps genuinely-new work from flagging:
#     if the term was absent before, occurrences_before is 0 and nothing
#     fires

CREATION_CLAIM_CUES = ("added", "adds", "introduced", "introduces", "created", "creates")

_CLAIM_LOCATION_PREPS = ("to", "in", "into", "onto", "for", "within", "under", "beside", "alongside")

# Generic words that are never, on their own, the name of a newly-created
# feature. Without this, "entry point added to X" would try to verify the
# word "point".
_CLAIM_GENERIC_TERMS = {
    "point", "entry", "page", "item", "view", "list", "field", "value", "state", "flow",
    "step", "part", "area", "note", "line", "text", "icon", "card", "row", "tab", "link",
    "menu", "form", "mode", "type", "name", "code", "data", "file", "path", "call", "hook",
    "util", "guard", "rule", "check", "test", "spec", "docs", "logs", "url", "key", "button",
    "screen", "screens", "feature", "features", "support", "requirement", "handler", "helper",
    "method", "option", "config", "setup", "change", "update", "version", "number", "status",
    "action", "banner", "label", "modal", "toast", "badge", "input", "output", "layout",
    "style", "block", "group", "panel", "route", "stub", "shim", "flag", "cooldown",
    "patient", "doctor", "user", "admin", "login", "logout", "backend", "frontend", "server",
    "client", "endpoint", "database", "table", "column", "schema", "model", "record", "token",
    "session", "request", "response", "error", "warning", "message", "string", "object",
    "array", "function", "class", "module", "package", "library", "component", "wrapper",
    "service", "worker", "queue", "cache", "store", "context", "provider", "reducer",
    "selector", "effect", "event", "state", "props", "state", "logic", "wiring", "fixes",
    "both", "real", "demo", "mock", "pilot", "prelaunch", "gate",
}

_CLAIM_IDENT_RE = re.compile(r"\b[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+\b|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b")
_CLAIM_PATH_RE = re.compile(
    r"\b[\w./-]+\.(?:ts|tsx|js|jsx|mjs|cjs|py|go|rb|java|kt|swift|c|cpp|h|hpp|rs|php|css|scss|less|html|vue|sql|sh)\b"
)
_CLAIM_BACKTICK_RE = re.compile(r"`([^`]{2,60})`")
_CLAIM_WORD_RE = re.compile(r"[A-Za-z][A-Za-z-]{3,}")
_CLAIM_MD_STRIP_RE = re.compile(r"[*_`#>\[\]]")
# Split on line breaks, semicolons, and sentence boundaries only. A dash is
# NOT a boundary: markdown bullets write the claim as "- **X** — added to Y",
# where the dash joins the subject to its predicate (golden entry 14).
_CLAIM_CLAUSE_SPLIT_RE = re.compile(r"[\n;]|(?<=[a-z])\.\s+")

# Flag when the term was already present in force before the commit
# (>= _OVERCLAIM_MIN_PRIOR occurrences in the named files) and the commit
# does not come close to introducing it: net new occurrences stay under
# _OVERCLAIM_MAX_ADDED, or under half of what was already there. A real
# "added from scratch" starts from 0 before and fails _OVERCLAIM_MIN_PRIOR;
# an already-shipped feature that a diff only tweaks (entry 14: 88 -> 91
# incidental mentions while lowering a cooldown) clears both.
_OVERCLAIM_MIN_PRIOR = 3
_OVERCLAIM_MAX_ADDED = 3


def _looks_like_overclaim(before, after):
    if before < _OVERCLAIM_MIN_PRIOR:
        return False
    return (after - before) <= max(_OVERCLAIM_MAX_ADDED, 0.5 * before)


def _claim_terms(span):
    """(identifier-like terms, all terms) found in a text span. Identifiers
    keep their case (used to resolve file names); everything is lowercased
    for the term list."""
    idents, terms = [], set()
    stripped = _CLAIM_MD_STRIP_RE.sub(" ", span)
    for m in _CLAIM_BACKTICK_RE.finditer(span):
        terms.add(m.group(1).strip().lower())
    for m in _CLAIM_PATH_RE.finditer(stripped):
        tok = m.group(0)
        idents.append(tok)
        terms.add(tok.lower())
    for m in _CLAIM_IDENT_RE.finditer(stripped):
        tok = m.group(0)
        idents.append(tok)
        terms.add(tok.lower())
    for m in _CLAIM_WORD_RE.finditer(stripped):
        w = m.group(0).lower()
        if w not in _CLAIM_GENERIC_TERMS and w not in CREATION_CLAIM_CUES and w != "new":
            terms.add(w)
    return idents, sorted(terms)


def _split_claim_clause(clause):
    """Return (subject_text, location_text) for a clause that contains a
    creation cue, or None if it has none."""
    low = clause.lower()
    cue_match = None
    for cue in CREATION_CLAIM_CUES:
        m = re.search(r"\b" + re.escape(cue) + r"\b", low)
        if m and (cue_match is None or m.start() < cue_match.start()):
            cue_match = m
    if cue_match:
        before, after = clause[:cue_match.start()], clause[cue_match.end():]
        prep = re.match(r"\s+(" + "|".join(_CLAIM_LOCATION_PREPS) + r")\b", after, re.I)
        if prep:
            # "<subject> added to <location>"
            return before, after[prep.end():]
        # "added <subject> [to <location>]"
        parts = re.split(r"\b(?:" + "|".join(_CLAIM_LOCATION_PREPS) + r")\b", after, maxsplit=1)
        return parts[0], (parts[1] if len(parts) > 1 else "")
    m = re.search(r"\bnew\b", low)
    if m:
        after = clause[m.end():]
        parts = re.split(r"\b(?:" + "|".join(_CLAIM_LOCATION_PREPS) + r")\b", after, maxsplit=1)
        return parts[0], (parts[1] if len(parts) > 1 else "")
    return None


def detect_creation_claims(text):
    """Clauses of `text` that claim something was newly created, each split
    into the thing claimed new and where it was said to go. Pure text, no
    git."""
    claims = []
    for raw in _CLAIM_CLAUSE_SPLIT_RE.split(text or ""):
        clause = re.sub(r"\s+", " ", raw.replace("*", "")).strip(" \t-•")
        if not clause:
            continue
        split = _split_claim_clause(clause)
        if split is None:
            continue
        subject_text, location_text = split
        _, subject_terms = _claim_terms(subject_text)
        loc_idents, location_terms = _claim_terms(location_text)
        # a term that shows up on both sides is ambiguous - drop from subject
        subject_terms = [t for t in subject_terms if t not in set(location_terms)]
        claims.append({
            "clause": clause,
            "subject_terms": subject_terms,
            "location_terms": location_terms,
            "location_idents": loc_idents,
        })
    return claims


def _resolve_location_files(repo, ref, location_idents):
    if not location_idents:
        return []
    try:
        tree = run_git(repo, "ls-tree", "-r", "--name-only", ref).splitlines()
    except RuntimeError:
        return []
    matched = []
    for ident in location_idents:
        key = ident.lower().rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if len(key) < 4:
            continue
        for f in tree:
            if key in f.lower() and f not in matched:
                matched.append(f)
    return matched


def _grep_count(repo, ref, term, files):
    result = subprocess.run(
        ["git", "-C", str(repo), "grep", "-i", "-I", "-F", "-c", term, ref, "--", *files],
        capture_output=True, text=True,
    )
    total = 0
    for line in result.stdout.splitlines():
        try:
            total += int(line.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            pass
    return total


def _introduced_commit(repo, ref, term, files):
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-i", "-S", term, "--oneline", "--reverse", ref, "--", *files],
        capture_output=True, text=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return lines[0] if lines else None


def build_overclaim_check(repo, sha, commit_message, prs):
    empty = {"detected": False, "prior_ref": None, "claims_checked": [], "overclaims": []}
    try:
        prior_ref = run_git(repo, "rev-parse", "--verify", f"{sha}^").strip()
    except RuntimeError:
        return empty  # root commit, nothing before it

    sources = [commit_message]
    for pr in prs or []:
        sources.append(pr.get("title", ""))
        sources.append(pr.get("description", ""))

    claims = []
    for src in sources:
        claims.extend(detect_creation_claims(src))
    if not claims:
        return {**empty, "prior_ref": prior_ref}

    claims_checked, overclaims = [], []
    for claim in claims:
        loc_files = _resolve_location_files(repo, prior_ref, claim["location_idents"])
        entry = {
            "clause": claim["clause"],
            "subject_terms": claim["subject_terms"],
            "location_files": loc_files,
        }
        if not loc_files or not claim["subject_terms"]:
            entry["result"] = "not_checkable"
            claims_checked.append(entry)
            continue
        term_results = []
        for term in claim["subject_terms"]:
            before = _grep_count(repo, prior_ref, term, loc_files)
            after = _grep_count(repo, sha, term, loc_files)
            is_overclaim = _looks_like_overclaim(before, after)
            term_results.append({"term": term, "before": before, "after": after, "overclaim": is_overclaim})
            if is_overclaim:
                since = _introduced_commit(repo, prior_ref, term, loc_files)
                overclaims.append({
                    "claim": claim["clause"],
                    "term": term,
                    "location_files": loc_files,
                    "occurrences_before": before,
                    "occurrences_after": after,
                    "existed_since": since,
                    "plain_fact": (
                        f"Claim says {term!r} was added ({claim['clause']!r}), but {term!r} "
                        f"already appears {before}x in {', '.join(loc_files)} before this commit"
                        + (f" (present since {since})" if since else "")
                        + f", and this commit leaves it at {after}x - it was not newly added here."
                    ),
                })
        entry["result"] = "checked"
        entry["term_results"] = term_results
        claims_checked.append(entry)

    return {
        "detected": bool(overclaims),
        "prior_ref": prior_ref,
        "claims_checked": claims_checked,
        "overclaims": overclaims,
    }


# ── User-facing copy removal check ─────────────────────────────────────
#
# A commit whose message frames its work purely as an addition or a change
# ("Add info icon with inline tooltip") but whose diff also quietly deletes
# a line of text a real user would have seen on screen is making an
# undisclosed change to the product. This is NOT the whole-file-deletion
# case (find_unexplained_deletions, rule 11) and NOT a claim-vs-diff
# mismatch the model has to reason toward - it is a plain, diff-level fact:
# a visible string is gone and the message never says anything was removed.
#
# See golden entry 09 (ce67468): message says "Add info icon with inline
# tooltip"; the diff also removes the always-visible hint line "An SMS will
# be sent to the patient's registered number for verification." that showed
# once a patient was found. Detection here is deterministic; the model was
# free-floating between Code complete and Flagged on exactly this call.
#
# Scoped deliberately narrow - it must NOT fire on:
#   - removed code, comments, styles, imports, renamed identifiers
#     (handled by the code-punctuation / comment / ALL-CAPS guards)
#   - text in non-UI files (only .tsx/.jsx/.vue/.svelte count)
#   - text that is relocated, not removed (same string re-added in the diff)
#   - whole-file deletions (already covered by rule 11)
#   - any commit whose message DOES disclose a removal/replacement

UI_COMPONENT_EXTENSIONS = {".tsx", ".jsx", ".vue", ".svelte"}

# Commit-message language that discloses something was taken out or swapped.
# If any of these is present, this check stays silent - the removal is not
# "undisclosed" and it is not this check's job to judge whether the
# disclosure is adequate (that is an ordinary rule 3 claim-vs-diff call).
_REMOVAL_DISCLOSURE_RE = re.compile(
    r"\b(remove[sd]?|removing|delet(?:e[sd]?|ing)|replac(?:e[sd]?|ing)|"
    r"consolidat(?:e[sd]?|ing|ion)|strip(?:s|ped|ping)?|reloca(?:te[sd]?|ting|tion)|"
    r"moved|drop(?:s|ped|ping)?|no longer)\b",
    re.I,
)

# Characters that mean a line is code, not a bare on-screen text node.
_CODEISH_CHARS = set("<>{}()[]:;=,/`\"\\|")
_PROSE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
# An inline JSX text node: >Some visible words<  (no braces/tags inside)
_JSX_TEXT_NODE_RE = re.compile(r">\s*([A-Za-z][^<>{}]*?)\s*<")


def _is_visible_prose(text):
    """True if `text` reads as on-screen copy: at least three word-tokens,
    contains a space, not a comment/directive, not an ALL-CAPS constant,
    and almost entirely letters + spaces + light sentence punctuation."""
    if not text or text.startswith(("//", "/*", "*", "#", "import", "export", "@", "-")):
        return False
    if " " not in text:
        return False
    if len(_PROSE_WORD_RE.findall(text)) < 3:
        return False
    if text.replace(" ", "").isupper():
        return False
    # assignment, union type, JSX expression, logical operator, or a code
    # namespace reference
    if re.search(r"[=|]|&&|\b(?:Colors|styles|theme|StyleSheet|props|React)\.", text):
        return False
    # a quote used as a string delimiter (`'code' in err`) rather than an
    # apostrophe inside a word (`patient's`): a quote next to whitespace or
    # a line boundary.
    if re.search(r"(?:^|\s)['\"`]|['\"`](?:\s|$)", text):
        return False
    # a JS/TS object-property line ("backgroundColor: Colors.x,") - identifier
    # then colon then value, ending in a structural char. Real prose that
    # happens to use a colon ("Note: an SMS will be sent.") ends in sentence
    # punctuation instead, so it is not caught here.
    if re.match(r"^['\"]?[A-Za-z_$][\w$]*['\"]?:\s", text) and text.rstrip()[-1:] in ",{[":
        return False
    good = sum(c.isalpha() or c.isspace() or c in ".,'’!?:;-—" for c in text)
    return good / len(text) >= 0.9


def _removed_visible_text(raw_line):
    """The on-screen text a removed diff line deletes, or None. Handles a
    bare text-node line ("  An SMS will be sent...") and an inline node
    ("<Text>Session expired</Text>")."""
    s = raw_line.strip()
    if not s:
        return None
    m = _JSX_TEXT_NODE_RE.search(s)
    if m:
        cand = m.group(1).strip()
        return cand if _is_visible_prose(cand) else None
    if _CODEISH_CHARS & set(s):
        return None
    return s if _is_visible_prose(s) else None


def _iter_removed_lines(full_diff):
    """(file_path, line_without_minus) for every real removal line in a
    unified diff. Tracks the current file from the `+++ b/...` header."""
    path = None
    for line in (full_diff or "").splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            if p == "/dev/null":
                path = None
            elif p.startswith(("a/", "b/")):
                path = p[2:]
            else:
                path = p
        elif line.startswith("---"):
            continue
        elif line.startswith("-"):
            yield path, line[1:]


def _normalize_text(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _added_text_blob(full_diff):
    added = []
    for line in (full_diff or "").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return _normalize_text(" ".join(added))


def build_ui_copy_removal_check(full_diff, commit_message, prs, is_merge, deleted_files):
    """Deterministic: does this diff delete a line of user-visible text from
    a UI component file while the commit message discloses no removal?

    Disclosure is read from the commit message for an ordinary commit. For a
    MERGE commit the message is auto-generated boilerplate, so the PR
    title/description is the unit that describes what the merge does (rule
    10) and disclosure is read from there instead - golden entry 14: the
    merge message is terse, but PR #6's body says "demo switcher buttons
    removed". A big PR body almost always says "removed" about something, so
    it is deliberately NOT consulted for non-merge commits, where a removal
    the commit itself makes should be disclosed in the commit's own message.
    """
    if is_merge:
        disclosure_text = "\n".join(
            f"{pr.get('title', '')}\n{pr.get('description', '')}" for pr in (prs or [])
        )
    else:
        disclosure_text = commit_message or ""
    if _REMOVAL_DISCLOSURE_RE.search(disclosure_text):
        return {"detected": False, "disclosed": True, "removals": []}

    skip = set(deleted_files or [])
    added_blob = _added_text_blob(full_diff)
    removals, seen = [], set()
    for path, raw in _iter_removed_lines(full_diff):
        if not path or path in skip:
            continue
        if Path(path).suffix.lower() not in UI_COMPONENT_EXTENSIONS:
            continue
        text = _removed_visible_text(raw)
        if not text:
            continue
        norm = _normalize_text(text)
        if norm in added_blob:  # relocated within the same diff, not removed
            continue
        key = (path, norm)
        if key in seen:
            continue
        seen.add(key)
        removals.append({
            "file": path,
            "text": text,
            "plain_fact": (
                f"This commit removes a line of user-visible text from {path} "
                f"({text!r}), and the commit message does not mention removing "
                f"or replacing anything."
            ),
        })

    return {"detected": bool(removals), "disclosed": False, "removals": removals}


def get_deleted_files(repo, sha, is_merge):
    """Fully-deleted files in this commit's diff, using the same scope
    (first-parent for merges) as the full diff itself."""
    args = ["show", "--first-parent", "--format=", "--name-status", sha] if is_merge \
        else ["show", "--format=", "--name-status", sha]
    out = run_git(repo, *args)
    deleted = []
    for line in out.splitlines():
        if line.startswith("D\t"):
            deleted.append(line.split("\t", 1)[1])
    return deleted


def find_unexplained_deletions(deleted_files, commit_message):
    """Deleted files whose name is never referenced anywhere in the commit
    message. Without even naming the file, the message can't be explaining
    why it's gone."""
    lowered_message = commit_message.lower()
    unexplained = []
    for f in deleted_files:
        name = Path(f).name.lower()
        stem = Path(f).stem.lower()
        if name in lowered_message or stem in lowered_message:
            continue
        unexplained.append(f)
    return unexplained


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
        {
            "number": pr["number"],
            "title": pr["title"],
            "description": pr.get("body") or "",
            # A PR's title/description describe the aggregate state of the
            # whole PR as of merge time, not this individual commit's own
            # point in time. Kept explicit so it doesn't get read as if it
            # describes this commit specifically.
            "describes_state_as_of": "PR merge time, not this individual commit's own point in time",
        }
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
    deleted_files = get_deleted_files(repo, sha, is_merge)

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
        "touches_app_code": compute_touches_app_code(files_changed),
        "sweeping_claim_check": build_sweeping_claim_check(repo, sha, commit_message),
        "overclaim_check": build_overclaim_check(repo, sha, commit_message, prs),
        "unexplained_deletions": find_unexplained_deletions(deleted_files, commit_message),
        "ui_copy_removal_check": build_ui_copy_removal_check(
            full_diff, commit_message, prs, is_merge, deleted_files
        ),
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
        print(f"No checkpoint existed for branch '{branch}': initialized at current HEAD "
              f"({head_sha[:7]}, via {ref}). No commits processed this run.")
        return

    last_sha = entry["last_sha"]

    if last_sha == head_sha:
        print("No change since last update")
        return

    new_shas = get_new_commit_shas(repo, last_sha, ref)

    if not new_shas:
        print(f"WARNING: checkpoint SHA {last_sha[:7]} is not an ancestor of {ref} "
              f"({head_sha[:7]}). Branch history may have been rewritten (rebase/force-push). "
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
