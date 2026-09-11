#!/usr/bin/env python3
"""Permanent unit tests for the fetch-layer sweeping-claim check.

No AI, no pipeline, no golden set. The hermetic cases build throwaway git
repos in a temp dir so they run anywhere in well under a second. One gated
case re-checks the real golden entry 13 (commit 2dab6c7 - "corrected ...
entirely" about a stale 'Six Agents' header) against EVAL_TARGET_REPO when
it is set.

    python3 test_sweeping_claim_check.py

Exit 0 = all pass. Exit 1 = one or more failures.

What the check must do:
  - a sweeping-absence claim ("X no longer appears anywhere") where X is
    genuinely gone from the tree -> claim_holds True
  - a sweeping claim where X still sits in a PRE-EXISTING file the commit
    never touched -> claim_holds False, still_found_at names that file
  - a sweeping claim where the ONLY remaining hit is on a line THIS COMMIT
    ITSELF just added (a log/changelog line describing the fix it made)
    -> claim_holds True: the commit explaining its own fix is not a
    leftover problem (golden entry 13)
  - a hit on a pre-existing (context / unchanged) line still counts
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fetch_layer import (
    build_sweeping_claim_check,
    claims_from_added_prose,
    detect_sweeping_claims,
)


# -- hermetic git repo helpers ----------------------------------------------

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _init_repo(tmp):
    repo = Path(tempfile.mkdtemp(dir=tmp))
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(repo, files, message):
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


# A doc whose heading is stale: says "Six Agents" over a table of eight.
DOC_STALE = """\
# Project

## The Six Agents

| # | Agent |
|---|-------|
| 1 | PM |
| 2 | Builder |
| 3 | Persona Critic |
| 4 | Security |
| 5 | QA |
| 6 | Device Tester |
| 7 | Backend |
| 8 | Integration Tester |

Each agent has a defined role.
"""

DOC_FIXED = DOC_STALE.replace("## The Six Agents", "## The Eight Agents")

# A separate tracking log. In the "self-describing fix" case the commit
# ADDS a line here that names the old text as the thing it changed.
LOG_BEFORE = """\
# Change log

- 2026-07-10: registered Integration Tester agent
- 2026-07-11: registered Backend agent
"""

LOG_AFTER_SELFDESCRIBING = LOG_BEFORE + (
    "- 2026-07-13: fixed stale heading - changed \"Six Agents\" to "
    "\"Eight Agents\" in the project doc\n"
)

# A pre-existing file the commit never touches, which genuinely still
# carries the old text.
OTHER_FILE_WITH_STALE = """\
# Onboarding notes

See "The Six Agents" section of the project doc for role definitions.
"""

SWEEPING_MSG = (
    'Fix stale governance heading\n\n'
    'The "Six Agents" heading was wrong against a table of eight; corrected '
    'it entirely so the doc no longer contradicts itself.'
)

# -- entry-15 shape: the sweeping claim is in the commit's OWN added prose,
#    not the commit message. A merge whose auto-generated message says
#    nothing sweeping, but which appends a "Last Updated" note asserting a
#    dead URL is gone from a directory - while it still sits in a file the
#    merge never touched.

API_WITH_DEAD_URL = """\
const BASE_URL = 'https://dead-api.example.com/v1';
export function client() { return fetch(BASE_URL); }
"""
API_CLEAN = """\
import { API_BASE_URL } from './config';
export function client() { return fetch(API_BASE_URL); }
"""

# A pre-existing doc that also mentions the dead URL, in a cert-pinning
# comment. The entry-15 commit never touches this file.
PINNING_DOC = """\
# TLS pinning notes

The cert chain was issued for dead-api.example.com; pin the intermediate
so a swapped leaf still validates.
"""

STATUS_BEFORE = """\
# Status

**Last Updated:** 2026-05-30 (initial deploy).
"""
# The commit adds this line - a status note that makes the sweeping claim.
STATUS_AFTER = STATUS_BEFORE + (
    "\n**Last Updated:** 2026-08-03 (merged the fix. Post-merge confirmed via "
    "`git grep` that `dead-api.example.com` no longer appears in `main`'s "
    "`src/api/`.)\n"
)
# Same shape, but a pure scope-intensifier in the added prose - NOT a claim
# that anything is absent. This is the entry-13 regression guard: "entirely"
# next to a backticked filename must not be read as "that file is gone".
STATUS_AFTER_INTENSIFIER = STATUS_BEFORE + (
    "\n**Last Updated:** 2026-08-03 (merged the fix. The API client now "
    "defers entirely to `src/api/config.ts` for the base URL.)\n"
)

MERGE_MSG_PLAIN = "Merge branch 'fix/dead-url' into main"


# -- pure detect_sweeping_claims cases (no git) ----------------------------

def _check_detect():
    failures = []

    # 1. no sweeping keyword -> nothing detected, no quoted text pulled
    kw, texts = detect_sweeping_claims(
        'Renamed the "Six Agents" heading to "Eight Agents".'
    )
    if kw or texts:
        failures.append(f"[detect] non-sweeping message matched: {kw} {texts}")
    else:
        print("  ok   detect        no sweeping keyword -> nothing detected")

    # 2. sweeping keyword + quoted text -> both surfaced
    kw, texts = detect_sweeping_claims(SWEEPING_MSG)
    if "entirely" not in kw or "Six Agents" not in texts:
        failures.append(f"[detect] sweeping message parsed wrong: {kw} {texts}")
    else:
        print("  ok   detect        sweeping keyword + quoted text -> both surfaced")

    return failures


# -- pure claims_from_added_prose cases (no git) -------------------------

def _check_added_prose():
    failures = []

    # 1. entry-15 phrasing: distinctive token just before an absence phrase
    claimed, phrases = claims_from_added_prose([
        "Post-merge confirmed via `git grep` that `dead-api.example.com` "
        "no longer appears in `main`'s `src/api/`."
    ])
    if claimed != ["dead-api.example.com"] or "no longer appears" not in phrases:
        failures.append(f"[prose] entry-15 phrasing not extracted: {claimed} {phrases}")
    else:
        print("  ok   prose         '`x.y` no longer appears' -> claims ['x.y']")

    # 2. scope intensifier, NOT an absence claim -> nothing (entry-13 guard)
    claimed, _ = claims_from_added_prose([
        "The gate now defers entirely to `infra-session-gate.sh` for path checks.",
        "Corrected the `Six Agents` header completely.",
    ])
    if claimed:
        failures.append(f"[prose] scope intensifier wrongly treated as absence claim: {claimed}")
    else:
        print("  ok   prose         'defers entirely to `x.sh`' -> no claim (intensifier)")

    # 3. absence phrase but only a bare word before it -> nothing (greps to noise)
    claimed, _ = claims_from_added_prose([
        "The `main` branch reference no longer appears in the routing table.",
    ])
    if claimed:
        failures.append(f"[prose] bare-word token wrongly kept: {claimed}")
    else:
        print("  ok   prose         bare word before absence phrase -> no claim")

    # 4. machine-log / non-prose content is never passed here in practice,
    #    but a line with no quoted token must be a no-op
    claimed, phrases = claims_from_added_prose([
        "the onrender.com url no longer appears in src/api after the merge",
    ])
    if claimed or phrases:
        failures.append(f"[prose] unquoted token wrongly extracted: {claimed} {phrases}")
    else:
        print("  ok   prose         absence phrase with no quoted token -> no claim")

    return failures


# -- build_sweeping_claim_check hermetic cases ----------------------------

def _check_sweeping(tmp):
    failures = []

    # A. genuinely gone: old text removed, nothing else carries it -> holds
    repo = _init_repo(tmp)
    _commit(repo, {"docs/project.md": DOC_STALE, "README.md": "app"}, "seed")
    sha = _commit(repo, {"docs/project.md": DOC_FIXED}, SWEEPING_MSG)
    res = build_sweeping_claim_check(repo, sha, SWEEPING_MSG)
    v = res["verifications"][0]
    if not (res["detected"] and v["claim_holds"] and not v["still_found_at"]):
        failures.append(f"[sweeping] genuinely-gone text not holding: {res}")
    else:
        print("  ok   sweeping      old text fully gone -> claim_holds True")

    # B. THE ENTRY-13 CASE: the commit fixes the heading AND, in the same
    #    diff, adds a log line that names the old text as what it changed.
    #    The only remaining hit is that self-describing line -> must hold.
    repo = _init_repo(tmp)
    _commit(
        repo,
        {"docs/project.md": DOC_STALE, "docs/changelog.md": LOG_BEFORE, "README.md": "app"},
        "seed",
    )
    sha = _commit(
        repo,
        {"docs/project.md": DOC_FIXED, "docs/changelog.md": LOG_AFTER_SELFDESCRIBING},
        SWEEPING_MSG,
    )
    res = build_sweeping_claim_check(repo, sha, SWEEPING_MSG)
    v = res["verifications"][0]
    if not (res["detected"] and v["claim_holds"] and not v["still_found_at"]):
        failures.append(
            f"[sweeping] self-describing fix (entry 13 shape) wrongly flagged "
            f"its own new log line as a leftover: {res}"
        )
    else:
        print("  ok   sweeping      self-describing fix (entry 13) -> own new "
              "log line not counted, claim_holds True")

    # C. genuine leftover: old text also sits in a SEPARATE pre-existing file
    #    the commit never touches -> must still be flagged, same as before.
    repo = _init_repo(tmp)
    _commit(
        repo,
        {
            "docs/project.md": DOC_STALE,
            "docs/changelog.md": LOG_BEFORE,
            "docs/onboarding.md": OTHER_FILE_WITH_STALE,
            "README.md": "app",
        },
        "seed",
    )
    sha = _commit(
        repo,
        {"docs/project.md": DOC_FIXED, "docs/changelog.md": LOG_AFTER_SELFDESCRIBING},
        SWEEPING_MSG,
    )
    res = build_sweeping_claim_check(repo, sha, SWEEPING_MSG)
    v = res["verifications"][0]
    hit_files = {h.split(":", 2)[1] for h in v["still_found_at"]}
    if not (res["detected"] and not v["claim_holds"] and hit_files == {"docs/onboarding.md"}):
        failures.append(
            f"[sweeping] genuine leftover in an untouched pre-existing file "
            f"was not flagged (or the self-describing line leaked in): {res}"
        )
    else:
        print("  ok   sweeping      leftover in untouched pre-existing file -> "
              "claim_holds False, names only that file")

    # D. a hit on a PRE-EXISTING context line (commit changes the file but
    #    not that line) still counts - the exclusion is added-lines-only.
    repo = _init_repo(tmp)
    _commit(
        repo,
        {"docs/project.md": DOC_STALE, "README.md": "app"},
        "seed",
    )
    # touch the file (append a trailing line) WITHOUT fixing the heading
    sha = _commit(
        repo,
        {"docs/project.md": DOC_STALE + "\nAppended note, heading left stale.\n"},
        SWEEPING_MSG,
    )
    res = build_sweeping_claim_check(repo, sha, SWEEPING_MSG)
    v = res["verifications"][0]
    hit_lines = {h.split(":", 2)[1] for h in v["still_found_at"]}
    if not (not v["claim_holds"] and "3" in {h.split(":", 3)[2] for h in v["still_found_at"]}):
        failures.append(
            f"[sweeping] pre-existing (unchanged) line carrying the old text "
            f"was wrongly excluded: {res}"
        )
    else:
        print("  ok   sweeping      hit on an unchanged pre-existing line -> "
              "still counts, claim_holds False")

    # E. THE ENTRY-15 CASE: the sweeping claim is in a line THIS COMMIT ADDS
    #    to a status doc, not in the (plain) commit message. The claimed URL
    #    is cleaned from src/api/ but still lives in a pinning-notes doc the
    #    commit never touches -> must be detected AND claim_holds False.
    repo = _init_repo(tmp)
    _commit(
        repo,
        {
            "src/api/client.ts": API_WITH_DEAD_URL,
            "docs/tls-pinning.md": PINNING_DOC,
            "docs/status.md": STATUS_BEFORE,
            "README.md": "app",
        },
        "seed",
    )
    sha = _commit(
        repo,
        {"src/api/client.ts": API_CLEAN, "docs/status.md": STATUS_AFTER},
        MERGE_MSG_PLAIN,
    )
    res = build_sweeping_claim_check(repo, sha, MERGE_MSG_PLAIN)
    ok = res["detected"] and "no longer appears" in res["keywords_matched"]
    v = next((x for x in res["verifications"] if x["claimed_text"] == "dead-api.example.com"), None)
    hit_files = {h.split(":", 2)[1] for h in v["still_found_at"]} if v else set()
    if not (ok and v and not v["claim_holds"] and hit_files == {"docs/tls-pinning.md"}):
        failures.append(
            f"[sweeping] entry-15 shape (claim in the commit's own added status "
            f"line, not the message) not detected/verified: {res}"
        )
    else:
        print("  ok   sweeping      entry 15: claim in commit's OWN added status "
              "line -> detected, still in an untouched doc -> claim_holds False")

    # F. NO REGRESSION: same shape, but the added prose is a scope
    #    intensifier ("defers entirely to `src/api/config.ts`"), not an
    #    absence claim, and the message says nothing sweeping -> not detected.
    repo = _init_repo(tmp)
    _commit(
        repo,
        {"src/api/client.ts": API_WITH_DEAD_URL, "docs/status.md": STATUS_BEFORE, "README.md": "app"},
        "seed",
    )
    sha = _commit(
        repo,
        {"src/api/client.ts": API_CLEAN, "docs/status.md": STATUS_AFTER_INTENSIFIER},
        MERGE_MSG_PLAIN,
    )
    res = build_sweeping_claim_check(repo, sha, MERGE_MSG_PLAIN)
    if res["detected"]:
        failures.append(
            f"[sweeping] scope intensifier in added prose wrongly triggered "
            f"the check (entry-13-in-reverse regression): {res}"
        )
    else:
        print("  ok   sweeping      intensifier in added prose + plain message "
              "-> not detected")

    # G. NO REGRESSION: a plain commit message and no claim-bearing added
    #    prose at all -> the check stays silent, exactly as before this path.
    repo = _init_repo(tmp)
    _commit(repo, {"src/api/client.ts": API_WITH_DEAD_URL, "README.md": "app"}, "seed")
    sha = _commit(repo, {"src/api/client.ts": API_CLEAN}, MERGE_MSG_PLAIN)
    res = build_sweeping_claim_check(repo, sha, MERGE_MSG_PLAIN)
    if res != {"detected": False, "keywords_matched": [], "verifications": []}:
        failures.append(f"[sweeping] plain commit, no sweeping claim anywhere -> not silent: {res}")
    else:
        print("  ok   sweeping      plain message + no claim in added prose -> silent")

    return failures


# -- real golden entry 13, gated on EVAL_TARGET_REPO ---------------------

REAL_SHA = "2dab6c7"
REAL_MESSAGE = (
    "[PM] Full governance audit: close #7, #10; correct wrong #6 claim; log #8, #9\n\n"
    "Cross-referenced all 7 agents/*.md spec files against the live ownership\n"
    "registry and hook scripts. Found and fixed two real bugs: Builder Agent\n"
    "was excluded from reviews/ despite its own spec requiring build notes go\n"
    "there (#7); CLAUDE.md's \"Six Agents\" header was stale against a table of\n"
    "eight (#10) - corrected it entirely.\n"
)


def _check_real_entry_13():
    repo = os.environ.get("EVAL_TARGET_REPO")
    if not repo or not Path(repo, ".git").exists():
        print("  skip REGRESSION    entry 13 (set EVAL_TARGET_REPO=/home/rdeva/medrecord to run)")
        return []
    repo = Path(repo)
    try:
        subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", REAL_SHA],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"  skip REGRESSION    entry 13 ({REAL_SHA} not in {repo})")
        return []

    # Use the commit's real message so the keyword/quoted-text detection is
    # exercised end to end against the real diff.
    real_msg = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s%n%n%b", REAL_SHA],
        capture_output=True, text=True,
    ).stdout.strip()
    res = build_sweeping_claim_check(repo, REAL_SHA, real_msg)
    failures = []
    if not res["detected"]:
        failures.append(f"[REGRESSION entry 13] sweeping claim no longer detected at all: {res}")
        return failures
    v = next((x for x in res["verifications"] if x["claimed_text"] == "Six Agents"), None)
    if v is None:
        failures.append(f"[REGRESSION entry 13] 'Six Agents' claim not extracted: {res}")
    elif not v["claim_holds"] or v["still_found_at"]:
        failures.append(
            f"[REGRESSION entry 13] still flagging the commit's own new log lines "
            f"as a leftover: {v['still_found_at']}"
        )
    else:
        print("  ok   REGRESSION     entry 13: 'Six Agents' only remains on lines "
              "2dab6c7 itself added -> claim_holds True")
    return failures


def _check_real_entry_15():
    repo = os.environ.get("EVAL_TARGET_REPO")
    if not repo or not Path(repo, ".git").exists():
        print("  skip REGRESSION    entry 15 (set EVAL_TARGET_REPO=/home/rdeva/medrecord to run)")
        return []
    repo = Path(repo)
    sha = "6aa36a6"
    try:
        subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", sha],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"  skip REGRESSION    entry 15 ({sha} not in {repo})")
        return []

    real_msg = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s%n%n%b", sha],
        capture_output=True, text=True,
    ).stdout.strip()
    res = build_sweeping_claim_check(repo, sha, real_msg)
    failures = []
    # The commit message itself has no sweeping language - detection here
    # can only come from the "Last Updated" note the commit adds to
    # docs/project-state.md.
    if detect_sweeping_claims(real_msg)[0]:
        print("  note REGRESSION    entry 15 message now has sweeping language; test assumption stale")
    v = next((x for x in res["verifications"] if x["claimed_text"] == "onrender.com"), None)
    if not res["detected"] or v is None:
        failures.append(f"[REGRESSION entry 15] claim in the added status note not detected: {res}")
    elif v["claim_holds"]:
        failures.append(
            f"[REGRESSION entry 15] 'onrender.com' claimed gone from src/api/ but "
            f"verification says it holds - should still be found in src/api/pinnedFetch.ts: {v}"
        )
    elif not any("src/api/pinnedFetch.ts" in h for h in v["still_found_at"]):
        failures.append(
            f"[REGRESSION entry 15] claim_holds False but pinnedFetch.ts (the "
            f"golden's cited leftover) is not in still_found_at: {v['still_found_at'][:5]}"
        )
    else:
        print("  ok   REGRESSION     entry 15: claim from the commit's own added "
              "status note -> detected, still in src/api/pinnedFetch.ts -> claim_holds False")
    return failures


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        failures = (
            _check_detect()
            + _check_added_prose()
            + _check_sweeping(tmp)
            + _check_real_entry_13()
            + _check_real_entry_15()
        )
    print()
    if failures:
        print(f"FAIL - {len(failures)} sweeping-claim-check test(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS - all sweeping-claim-check tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
