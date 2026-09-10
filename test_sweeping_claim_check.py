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

from fetch_layer import build_sweeping_claim_check, detect_sweeping_claims


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


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        failures = (
            _check_detect()
            + _check_sweeping(tmp)
            + _check_real_entry_13()
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
