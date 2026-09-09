#!/usr/bin/env python3
"""Permanent unit tests for the fetch-layer overclaim check.

No AI, no pipeline, no golden set. The hermetic cases build throwaway git
repos in a temp dir so they run anywhere in well under a second. One
gated case re-checks the real golden entry 14 (PR #6's "OTP resend added
to both login screens" claim) against EVAL_TARGET_REPO when it is set.

    python3 test_overclaim_check.py

Exit 0 = all pass. Exit 1 = one or more failures.

What the check must do:
  - a message that claims X was "added" to a file where X is GENUINELY
    new must NOT flag
  - a message that claims X was "added" to a file where X was already
    there in force, and the commit barely touches it, MUST flag, as a
    plain fact naming the commit X has existed since
  - a claim with no resolvable "added to <file>" location is recorded but
    not flagged either way
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fetch_layer import build_overclaim_check, detect_creation_claims
from prompt_contract_layer import (
    FOLLOW_UP_QUESTION,
    build_user_prompt,
    enforce_deterministic_rules,
)


# ── hermetic git repo helpers ──────────────────────────────────────────

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


# A login screen that already has a full resend feature.
LOGIN_WITH_RESEND = """\
import React, { useState } from 'react';
const RESEND_SECONDS = 45;
export function LoginScreen() {
  const [resendSeconds, setResendSeconds] = useState(RESEND_SECONDS);
  const [canResend, setCanResend] = useState(false);
  const startResendCountdown = () => { setCanResend(false); };
  const handleResend = async () => { startResendCountdown(); };
  return (
    <View>
      {canResend
        ? <Button accessibilityLabel="Resend OTP" onPress={handleResend}>Resend OTP</Button>
        : <Text>Resend in {resendSeconds}s</Text>}
    </View>
  );
}
"""

LOGIN_NO_RESEND = """\
import React, { useState } from 'react';
export function LoginScreen() {
  const [code, setCode] = useState('');
  return (<View><TextInput value={code} onChangeText={setCode} /></View>);
}
"""

LOGIN_WITH_RESEND_30 = LOGIN_WITH_RESEND.replace("RESEND_SECONDS = 45", "RESEND_SECONDS = 30")


# Verbatim shape of the real PR #6 body (golden entry 14). The "added"
# claim is the OTP-resend bullet; the diff for the two login screens only
# lowers an existing 45s cooldown to 30s. The claim is joined to its
# subject by " — ", which must not be read as a clause boundary.
PR6_BODY = """\
## Summary

- **P3 + P5 wired to real API** — both screens were on mock data in main; demo switcher buttons removed
- **Integration bugs fixed** — BUG-IT-1, BUG-IT-2, BUG-IT-3, BUG-IT-4; 6/7 scenarios PASS
- **OTP resend (30s cooldown)** — added to D1 (LoginScreen) and P1 (PatientLoginScreen); pre-pilot requirement
- **Backend mobile immutability guard** — PATCH /patient/profile returns HTTP 400 MOBILE_IMMUTABLE

## Test plan

- [ ] D1: OTP resend button appears after 30s
- [ ] P1: OTP resend button appears after 30s
"""


# ── pure detect_creation_claims cases (no git) ─────────────────────────

def _check_detect():
    failures = []

    # 1. no cue word anywhere -> no claims
    claims = detect_creation_claims(
        "Refactored auth module for performance; all existing tests pass, no behavioral change."
    )
    if claims:
        failures.append(f"[detect] no-cue message produced claims: {claims}")
    else:
        print("  ok   detect        no-cue message -> no claims")

    # 2. "<subject> added to <location>" -> resend in subject, LoginScreen in location
    claims = detect_creation_claims(
        "- **OTP resend (30s cooldown)** — added to D1 (LoginScreen) and P1 (PatientLoginScreen)"
    )
    ok = (
        len(claims) == 1
        and "resend" in claims[0]["subject_terms"]
        and any("loginscreen" in t for t in claims[0]["location_terms"])
        and "resend" not in claims[0]["location_terms"]
    )
    if not ok:
        failures.append(f"[detect] 'added to' form parsed wrong: {claims}")
    else:
        print("  ok   detect        '<subject> added to <location>' splits correctly")

    # 3. generic subject word ("entry point") must not become a term
    claims = detect_creation_claims("Dev __DEV__ entry point added to D2 PatientSearch.")
    subj = claims[0]["subject_terms"] if claims else None
    if subj is None or "point" in subj or "entry" in subj:
        failures.append(f"[detect] generic subject leaked a term: {claims}")
    else:
        print(f"  ok   detect        generic subject 'entry point' -> no term ({subj})")

    return failures


# ── build_overclaim_check hermetic cases ──────────────────────────────

def _check_overclaim(tmp):
    failures = []

    # A. term genuinely new in the file this commit -> must NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/LoginScreen.tsx": LOGIN_NO_RESEND, "README.md": "app"},
            "[D1] Login screen scaffold")
    sha = _commit(repo, {"src/screens/LoginScreen.tsx": LOGIN_WITH_RESEND},
                  "OTP resend button added to LoginScreen; pre-pilot requirement")
    res = build_overclaim_check(repo, sha, "OTP resend button added to LoginScreen", [])
    if res["detected"]:
        failures.append(f"[overclaim] genuinely-new resend was flagged: {res['overclaims']}")
    else:
        print("  ok   overclaim     genuinely-new feature -> not flagged")

    # B. term already present in force, commit barely touches it -> MUST flag
    repo = _init_repo(tmp)
    c1 = _commit(repo, {"src/screens/LoginScreen.tsx": LOGIN_WITH_RESEND, "README.md": "app"},
                 "[D1] Login screen with resend + WhatsApp fallback")
    sha = _commit(repo, {"src/screens/LoginScreen.tsx": LOGIN_WITH_RESEND_30},
                  "OTP resend (30s cooldown) - added to LoginScreen; pre-pilot requirement")
    res = build_overclaim_check(
        repo, sha, "OTP resend (30s cooldown) - added to LoginScreen; pre-pilot requirement", []
    )
    oc = res["overclaims"]
    ok = (
        res["detected"]
        and any(o["term"] == "resend" for o in oc)
        and any(o["existed_since"] and o["existed_since"].startswith(c1[:7]) for o in oc)
        and any("src/screens/LoginScreen.tsx" in o["location_files"] for o in oc)
    )
    if not ok:
        failures.append(f"[overclaim] pre-existing resend NOT flagged as expected: {res}")
    else:
        print(f"  ok   overclaim     pre-existing feature -> flagged, since {oc[0]['existed_since']!r}")

    # C. claim with no resolvable location file -> recorded, not flagged
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/LoginScreen.tsx": LOGIN_NO_RESEND, "README.md": "app"}, "scaffold")
    sha = _commit(repo, {"CHANGELOG.md": "- did stuff"}, "Introduced a metrics dashboard for ops")
    res = build_overclaim_check(repo, sha, "Introduced a metrics dashboard for ops", [])
    if res["detected"]:
        failures.append(f"[overclaim] unlocatable claim was flagged: {res}")
    elif not res["claims_checked"]:
        failures.append(f"[overclaim] unlocatable claim was not even recorded: {res}")
    else:
        print("  ok   overclaim     claim with no location file -> recorded, not flagged")

    # D. the overclaim is read from PR metadata, not just the commit message
    repo = _init_repo(tmp)
    c1 = _commit(
        repo,
        {
            "src/screens/doctor/LoginScreen.tsx": LOGIN_WITH_RESEND,
            "src/screens/patient/PatientLoginScreen.tsx": LOGIN_WITH_RESEND,
            "README.md": "app",
        },
        "[D1/P1] Login screens with resend",
    )
    sha = _commit(
        repo,
        {
            "src/screens/doctor/LoginScreen.tsx": LOGIN_WITH_RESEND_30,
            "src/screens/patient/PatientLoginScreen.tsx": LOGIN_WITH_RESEND_30,
        },
        "Merge PR #6 - Pre-pilot fixes",
    )
    res = build_overclaim_check(
        repo, sha, "Merge PR #6 - Pre-pilot fixes",
        [{"title": "Pre-pilot fixes", "description": PR6_BODY}],
    )
    ok = (
        res["detected"]
        and any(o["term"] == "resend" for o in res["overclaims"])
        and any(
            {"src/screens/doctor/LoginScreen.tsx", "src/screens/patient/PatientLoginScreen.tsx"}
            <= set(o["location_files"])
            for o in res["overclaims"]
        )
    )
    if not ok:
        failures.append(f"[overclaim] PR-body claim not caught: {res}")
    else:
        print("  ok   overclaim     'added' claim in PR body (not commit msg) -> flagged")

    return failures


# ── real golden entry 14, gated on EVAL_TARGET_REPO ───────────────────

REAL_MERGE_SHA = "cb66d392"
REAL_MERGE_MESSAGE = (
    "Merge PR #6 - Pre-pilot fixes: OTP resend, real API wiring, integration bugs, mobile guard\n\n"
    "Pre-pilot fixes - OTP resend, real API wiring, integration bugs, mobile guard"
)


def _check_real_entry_14():
    repo = os.environ.get("EVAL_TARGET_REPO")
    if not repo or not Path(repo, ".git").exists():
        print("  skip REGRESSION    entry 14 (set EVAL_TARGET_REPO=/home/rdeva/medrecord to run)")
        return []
    repo = Path(repo)
    try:
        subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", REAL_MERGE_SHA],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"  skip REGRESSION    entry 14 ({REAL_MERGE_SHA} not in {repo})")
        return []

    res = build_overclaim_check(
        repo, REAL_MERGE_SHA, REAL_MERGE_MESSAGE,
        [{"title": "Pre-pilot fixes - OTP resend, real API wiring, integration bugs, mobile guard",
          "description": PR6_BODY}],
    )
    failures = []
    resend_oc = [o for o in res["overclaims"] if o["term"] == "resend"]
    ok = (
        res["detected"]
        and resend_oc
        and any(
            "LoginScreen" in " ".join(o["location_files"])
            and "PatientLoginScreen" in " ".join(o["location_files"])
            for o in resend_oc
        )
        and all(o["existed_since"] for o in resend_oc)
    )
    if not ok:
        failures.append(f"[REGRESSION entry 14] not caught deterministically: {res}")
    else:
        o = resend_oc[0]
        print(f"  ok   REGRESSION     entry 14: 'resend' claimed added, was already "
              f"{o['occurrences_before']}x in both login screens, since {o['existed_since']!r}")
    return failures


# ── prompt-contract wiring: the code-level Flagged override ────────────

def _record(overclaim_check=None, **extra):
    r = {
        "commit_id": "test",
        "commit_message": "x",
        "files_changed": ["src/a.ts"],
        "full_diff": "",
        "pr_metadata": [],
        "story_attribution": {"status": "unattributed", "story_id": None, "matched_in": None},
        "touches_app_code": True,
        "unexplained_deletions": [],
    }
    if overclaim_check is not None:
        r["overclaim_check"] = overclaim_check
    r.update(extra)
    return r


_DETECTED_OC = {
    "detected": True,
    "prior_ref": "f7936ee",
    "claims_checked": [],
    "overclaims": [{
        "claim": "OTP resend added to LoginScreen",
        "term": "resend",
        "location_files": ["src/screens/doctor/LoginScreen.tsx"],
        "occurrences_before": 88,
        "occurrences_after": 91,
        "existed_since": "12969c8 Doctor Visit Flow",
        "plain_fact": "Claim says 'resend' was added, but 'resend' already appears 88x ... since 12969c8.",
    }],
}
_NOT_CHECKABLE_OC = {
    "detected": False,
    "prior_ref": "f7936ee",
    "claims_checked": [{"clause": "added a dashboard", "subject_terms": ["dashboard"],
                        "location_files": [], "result": "not_checkable"}],
    "overclaims": [],
}


def _check_contract_override():
    failures = []

    # detected=True -> status forced to Flagged, whatever the model said
    for model_status in ("Code complete", "Tested", "Pending"):
        status, _ = enforce_deterministic_rules(model_status, "The commit does X.", _record(_DETECTED_OC))
        if status != "Flagged":
            failures.append(f"[override] detected overclaim + model {model_status!r} -> {status!r}, expected 'Flagged'")
    if not failures:
        print("  ok   override      detected overclaim forces Flagged over Code complete / Tested / Pending")

    # detected=True + model already Flagged -> still Flagged, no error
    status, _ = enforce_deterministic_rules("Flagged", "Already flagged.", _record(_DETECTED_OC))
    if status != "Flagged":
        failures.append(f"[override] detected overclaim + model 'Flagged' -> {status!r}")
    else:
        print("  ok   override      detected overclaim + model already Flagged -> Flagged")

    # not_checkable -> no effect: Code complete stays Code complete
    status, _ = enforce_deterministic_rules("Code complete", "The commit does X.", _record(_NOT_CHECKABLE_OC))
    if status != "Code complete":
        failures.append(f"[override] not_checkable overclaim changed status to {status!r}")
    else:
        print("  ok   override      not_checkable overclaim -> status unaffected")

    # overclaim_check absent entirely -> no effect (behaves exactly as before)
    status, _ = enforce_deterministic_rules("Code complete", "The commit does X.", _record())
    if status != "Code complete":
        failures.append(f"[override] absent overclaim_check changed status to {status!r}")
    else:
        print("  ok   override      absent overclaim_check -> status unaffected")

    # the plain_fact actually reaches the model payload
    payload = json.loads(build_user_prompt(_record(_DETECTED_OC)))
    oc = payload.get("overclaim_check", {})
    if not (oc.get("detected") and oc["overclaims"][0]["plain_fact"] and oc["overclaims"][0]["existed_since"]):
        failures.append(f"[override] plain_fact / existed_since not in prompt payload: {oc}")
    else:
        print("  ok   override      detected/existed_since/plain_fact passed into the prompt payload")

    # a not-detected overclaim_check is slimmed to just {detected: false} in the payload
    payload = json.loads(build_user_prompt(_record(_NOT_CHECKABLE_OC)))
    if payload.get("overclaim_check") != {"detected": False}:
        failures.append(f"[override] not-detected overclaim_check not slimmed in payload: {payload.get('overclaim_check')}")
    else:
        print("  ok   override      not-detected overclaim_check slimmed to {detected: false} in payload")

    return failures


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        failures = (
            _check_detect()
            + _check_overclaim(tmp)
            + _check_contract_override()
            + _check_real_entry_14()
        )
    print()
    if failures:
        print(f"FAIL - {len(failures)} overclaim-check test(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS - all overclaim-check tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
