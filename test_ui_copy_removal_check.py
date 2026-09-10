#!/usr/bin/env python3
"""Permanent unit tests for the fetch-layer user-facing-copy removal check.

No AI, no pipeline, no golden set. The hermetic cases build throwaway git
repos in a temp dir so they run anywhere in well under a second. Two gated
cases re-check real golden entries against EVAL_TARGET_REPO when it is set:
entry 09 (ce67468, must flag) and entry 08 (24ef723, must NOT flag - the
message discloses the removal and the line is relocated).

    python3 test_ui_copy_removal_check.py

Exit 0 = all pass. Exit 1 = one or more failures.

What the check must do:
  - a UI component that loses a line of on-screen text, with a commit
    message that never mentions removing anything, MUST flag (as a plain
    fact naming the file and the exact text)
  - the same removal, with a commit message that DOES disclose it
    ("Remove the old hint..."), must NOT flag
  - removed code / comments / styles / imports / renamed identifiers must
    NOT flag
  - text that is relocated (removed here, re-added there in the same diff)
    must NOT flag
  - visible text removed from a non-UI file (.ts, .py, ...) must NOT flag
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fetch_layer import (
    build_ui_copy_removal_check,
    _is_visible_prose,
    _removed_visible_text,
    _REMOVAL_DISCLOSURE_RE,
)
from prompt_contract_layer import build_user_prompt, enforce_deterministic_rules


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


def _diff(repo, sha):
    return subprocess.run(
        ["git", "-C", str(repo), "show", "--format=", "-p", sha],
        capture_output=True, text=True,
    ).stdout


HINT_LINE = "An SMS will be sent to the patient's registered number for verification."

SCREEN_WITH_HINT = """\
import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

export function ConsentLookupScreen() {
  const [lookupState, setLookupState] = useState('idle');
  return (
    <View>
      <TouchableOpacity accessibilityLabel="Request access to patient records">
        <Text>Request Access</Text>
      </TouchableOpacity>
      {lookupState === 'found' && (
        <Text style={styles.hint}>
          %s
        </Text>
      )}
    </View>
  );
}
""" % HINT_LINE

SCREEN_WITH_TOOLTIP = """\
import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

export function ConsentLookupScreen() {
  const [lookupState, setLookupState] = useState('idle');
  const [showTooltip, setShowTooltip] = useState(false);
  return (
    <View>
      <TouchableOpacity accessibilityLabel="Request access to patient records">
        <Text>Request Access</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setShowTooltip(v => !v)}>
        <Text>i</Text>
      </TouchableOpacity>
      {showTooltip && (
        <View style={styles.tooltip}>
          <Text>Tapping Request Access texts the patient a six digit code.</Text>
        </View>
      )}
    </View>
  );
}
"""

# Same as SCREEN_WITH_TOOLTIP but the old hint line is kept, just moved
# lower in the tree (relocation, not removal).
SCREEN_HINT_RELOCATED = SCREEN_WITH_TOOLTIP.replace(
    "      {showTooltip && (",
    "      <Text style={styles.hint}>\n        %s\n      </Text>\n      {showTooltip && (" % HINT_LINE,
)

SCREEN_INTERNAL_ONLY = """\
import React, { useState } from 'react';
import { View, Text } from 'react-native';

// D9 ConsentRequest would launch here
const MAX_ATTEMPTS = 3;

export function ConsentLookupScreen() {
  const [lookupState, setLookupState] = useState('idle');
  return (
    <View>
      <Text style={styles.hint}>
        %s
      </Text>
    </View>
  );
}
""" % HINT_LINE

SCREEN_INTERNAL_REMOVED = """\
import React, { useState } from 'react';
import { View, Text } from 'react-native';

export function ConsentLookupScreen() {
  const [status, setStatus] = useState('idle');
  return (
    <View>
      <Text style={styles.hint}>
        %s
      </Text>
    </View>
  );
}
""" % HINT_LINE

HELPER_WITH_STRING = '''\
export function verificationHint(): string {
  return "An SMS will be sent to the patient's registered number for verification.";
}
'''

HELPER_STRING_CHANGED = '''\
export function verificationHint(): string {
  return "We text the patient a code.";
}
'''


# ── pure helper cases (no git) ────────────────────────────────────────

def _check_helpers():
    failures = []

    if _is_visible_prose(HINT_LINE) is not True:
        failures.append(f"[prose] real hint line not recognized as prose: {HINT_LINE!r}")
    else:
        print("  ok   prose         real on-screen hint line -> visible prose")

    for codey in (
        "const MAX_ATTEMPTS = 3;",
        "backgroundColor: Colors.errorLight,",
        "import { View, Text } from 'react-native';",
        "// D9 ConsentRequest would launch here",
        "<Text style={styles.hint}>",
        "type LookupState = 'idle' | 'found';",
        "'code' in err &&",
        "'status' in err",
        "setLookupState(mobile === MOCK_PATIENT.mobile ? 'found' : 'not_found');",
    ):
        if _is_visible_prose(codey.strip()):
            failures.append(f"[prose] code line misread as prose: {codey!r}")
    if not failures:
        print("  ok   prose         code / style / import / comment / operator lines -> not prose")

    # apostrophe inside a word must NOT trip the quote-delimiter guard
    if _is_visible_prose("An SMS is sent to the patient's registered number.") is not True:
        failures.append("[prose] apostrophe-in-word wrongly rejected")
    else:
        print("  ok   prose         apostrophe inside a word -> still visible prose")

    if _removed_visible_text("      <Text>Session expired, please sign in again.</Text>") is None:
        failures.append("[removed] inline JSX text node not extracted")
    else:
        print("  ok   removed       inline <Text>...</Text> node -> extracted")

    if _removed_visible_text("  const isAtMax = digits.length === 10;") is not None:
        failures.append("[removed] code line returned text")
    else:
        print("  ok   removed       code line -> None")

    for msg, should_match in [
        ("Add info icon with inline tooltip next to Request Access button", False),
        ("Remove CTA from inside the found card", True),
        ("Replace inline hint with a tooltip", True),
        ("Consolidate the two hint lines into one", True),
        ("Drop the legacy SMS notice", True),
        ("Show last visit date under patient name", False),
    ]:
        got = bool(_REMOVAL_DISCLOSURE_RE.search(msg))
        if got != should_match:
            failures.append(f"[disclosure] {msg!r} -> {got}, expected {should_match}")
    if not failures:
        print("  ok   disclosure    removal-cue detection matches expectations")

    return failures


# ── build_ui_copy_removal_check hermetic cases ────────────────────────

def _check_removal(tmp):
    failures = []

    # A. on-screen text removed, message never mentions removing -> MUST flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_HINT, "README.md": "app"},
            "[D7] Consent lookup screen with SMS hint")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_TOOLTIP},
                  "[D7] Add info icon with inline tooltip next to Request Access button")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Add info icon with inline tooltip next to Request Access button",
        [],     # no PR metadata
        False,  # not a merge commit
        [],     # no deleted files
    )
    ok = (
        res["detected"]
        and len(res["removals"]) == 1
        and res["removals"][0]["file"] == "src/screens/ConsentLookupScreen.tsx"
        and "An SMS will be sent" in res["removals"][0]["text"]
        and "does not mention removing" in res["removals"][0]["plain_fact"]
    )
    if not ok:
        failures.append(f"[removal] undisclosed on-screen text removal NOT flagged: {res}")
    else:
        print("  ok   removal       undisclosed on-screen text removal -> flagged")

    # B. same removal, message DOES disclose it -> MUST NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_HINT, "README.md": "app"},
            "[D7] Consent lookup screen with SMS hint")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_TOOLTIP},
                  "[D7] Replace the always-on SMS hint with a tap-to-open info tooltip")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Replace the always-on SMS hint with a tap-to-open info tooltip",
        [],
        False,
        [],
    )
    if res["detected"] or not res["disclosed"]:
        failures.append(f"[removal] disclosed removal was flagged: {res}")
    else:
        print("  ok   removal       removal disclosed in message -> not flagged")

    # B2. MERGE commit: terse message, but the PR body discloses the removal -> MUST NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_HINT, "README.md": "app"},
            "[D7] Consent lookup screen with SMS hint")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_TOOLTIP},
                  "Merge PR #12 - consent lookup polish")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "Merge PR #12 - consent lookup polish",
        [{"title": "Consent lookup polish",
          "description": "- info icon + tooltip added\n- always-on SMS hint line removed (now in the tooltip)"}],
        True,   # merge commit -> disclosure is read from the PR body
        [],
    )
    if res["detected"] or not res["disclosed"]:
        failures.append(f"[removal] merge-commit removal disclosed in PR body was flagged: {res}")
    else:
        print("  ok   removal       merge commit: removal disclosed in PR body -> not flagged")

    # B3. NON-merge commit: PR body mentions a removal but the commit's own
    # message does not -> STILL FIRES. A non-merge commit must disclose its own
    # removals in its own message; a bundling PR body is not consulted (it
    # almost always says "removed" about something unrelated).
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_HINT, "README.md": "app"},
            "[D7] Consent lookup screen with SMS hint")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_TOOLTIP},
                  "[D7] Add info icon with inline tooltip")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Add info icon with inline tooltip",
        [{"title": "Sprint 7", "description": "lots of things; some dead code removed elsewhere"}],
        False,  # non-merge -> PR body NOT consulted for disclosure
        [],
    )
    if not res["detected"]:
        failures.append(f"[removal] non-merge commit relied on PR body for disclosure: {res}")
    else:
        print("  ok   removal       non-merge commit: PR body not consulted for disclosure -> fires")

    # C. only internal / non-visible code removed -> MUST NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_INTERNAL_ONLY, "README.md": "app"},
            "[D7] Consent lookup screen")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_INTERNAL_REMOVED},
                  "[D7] Drop unused MAX_ATTEMPTS constant and stale comment; rename lookupState")
    # message has a disclosure cue too, so also drop it to isolate the code guard
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Tidy up the consent lookup screen internals",
        [],
        False,
        [],
    )
    if res["detected"]:
        failures.append(f"[removal] internal-only removal was flagged: {res}")
    else:
        print("  ok   removal       only code/comment/import removed -> not flagged")

    # D. text relocated (removed here, re-added elsewhere in the diff) -> MUST NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_WITH_HINT, "README.md": "app"},
            "[D7] Consent lookup screen with SMS hint")
    sha = _commit(repo, {"src/screens/ConsentLookupScreen.tsx": SCREEN_HINT_RELOCATED},
                  "[D7] Add info icon and reflow the request-access area")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Add info icon and reflow the request-access area",
        [],
        False,
        [],
    )
    if res["detected"]:
        failures.append(f"[removal] relocated (not removed) text was flagged: {res}")
    else:
        print("  ok   removal       text relocated within the diff -> not flagged")

    # E. visible-looking text removed from a NON-UI file -> MUST NOT flag
    repo = _init_repo(tmp)
    _commit(repo, {"src/lib/verificationHint.ts": HELPER_WITH_STRING, "README.md": "app"},
            "[D7] Add verification hint helper")
    sha = _commit(repo, {"src/lib/verificationHint.ts": HELPER_STRING_CHANGED},
                  "[D7] Shorten the verification hint copy")
    res = build_ui_copy_removal_check(
        _diff(repo, sha),
        "[D7] Shorten the verification hint copy",
        [],
        False,
        [],
    )
    if res["detected"]:
        failures.append(f"[removal] non-UI-file text change was flagged: {res}")
    else:
        print("  ok   removal       text removed from a .ts (non-UI) file -> not flagged")

    return failures


# ── prompt-contract wiring: the code-level Flagged override ────────────

def _record(ui_copy_removal_check=None, **extra):
    r = {
        "commit_id": "test",
        "commit_message": "x",
        "files_changed": ["src/a.tsx"],
        "full_diff": "",
        "pr_metadata": [],
        "story_attribution": {"status": "unattributed", "story_id": None, "matched_in": None},
        "touches_app_code": True,
        "unexplained_deletions": [],
    }
    if ui_copy_removal_check is not None:
        r["ui_copy_removal_check"] = ui_copy_removal_check
    r.update(extra)
    return r


_DETECTED_UC = {
    "detected": True,
    "disclosed": False,
    "removals": [{
        "file": "src/screens/doctor/ConsentLookupScreen.tsx",
        "text": HINT_LINE,
        "plain_fact": (
            f"This commit removes a line of user-visible text from "
            f"src/screens/doctor/ConsentLookupScreen.tsx ({HINT_LINE!r}), and the "
            f"commit message does not mention removing or replacing anything."
        ),
    }],
}
_DISCLOSED_UC = {"detected": False, "disclosed": True, "removals": []}


def _check_contract_override():
    failures = []

    for model_status in ("Code complete", "Tested", "Pending"):
        status, _ = enforce_deterministic_rules(model_status, "The commit does X.", _record(_DETECTED_UC))
        if status != "Flagged":
            failures.append(f"[override] detected removal + model {model_status!r} -> {status!r}, expected 'Flagged'")
    if not failures:
        print("  ok   override      detected removal forces Flagged over Code complete / Tested / Pending")

    status, _ = enforce_deterministic_rules("Flagged", "Already flagged.", _record(_DETECTED_UC))
    if status != "Flagged":
        failures.append(f"[override] detected removal + model 'Flagged' -> {status!r}")
    else:
        print("  ok   override      detected removal + model already Flagged -> Flagged")

    status, _ = enforce_deterministic_rules("Code complete", "The commit does X.", _record(_DISCLOSED_UC))
    if status != "Code complete":
        failures.append(f"[override] disclosed (not detected) removal changed status to {status!r}")
    else:
        print("  ok   override      disclosed removal -> status unaffected")

    status, _ = enforce_deterministic_rules("Code complete", "The commit does X.", _record())
    if status != "Code complete":
        failures.append(f"[override] absent ui_copy_removal_check changed status to {status!r}")
    else:
        print("  ok   override      absent ui_copy_removal_check -> status unaffected")

    payload = json.loads(build_user_prompt(_record(_DETECTED_UC)))
    uc = payload.get("ui_copy_removal_check", {})
    if not (uc.get("detected") and uc["removals"][0]["plain_fact"] and uc["removals"][0]["text"]):
        failures.append(f"[override] plain_fact / text not in prompt payload: {uc}")
    else:
        print("  ok   override      file/text/plain_fact passed into the prompt payload")

    payload = json.loads(build_user_prompt(_record(_DISCLOSED_UC)))
    if payload.get("ui_copy_removal_check") != {"detected": False}:
        failures.append(f"[override] not-detected ui_copy_removal_check not slimmed: {payload.get('ui_copy_removal_check')}")
    else:
        print("  ok   override      not-detected ui_copy_removal_check slimmed to {detected: false}")

    return failures


# ── real golden entries, gated on EVAL_TARGET_REPO ────────────────────

def _real_repo():
    repo = os.environ.get("EVAL_TARGET_REPO")
    if not repo or not Path(repo, ".git").exists():
        return None
    return Path(repo)


def _real_show(repo, sha, first_parent=False):
    args = ["git", "-C", str(repo), "show", "--format=", "-p", sha]
    if first_parent:
        args.insert(4, "--first-parent")
    diff = subprocess.run(args, capture_output=True, text=True).stdout
    msg = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B", sha],
        capture_output=True, text=True,
    ).stdout.strip()
    return diff, msg


# PR #6 body (golden entry 14) - the "demo switcher buttons removed" phrase is
# the disclosure the terse merge commit message itself does not carry.
_PR6_BODY = (
    "- **P3 + P5 wired to real API** - both screens were on mock data in main; "
    "demo switcher buttons removed; device-verified 4/4 PASS\n"
    "- **OTP resend (30s cooldown)** - added to D1 and P1\n"
)


def _check_real_entries():
    repo = _real_repo()
    if repo is None:
        print("  skip REGRESSION    entries 09 / 08 / 14 (set EVAL_TARGET_REPO=/home/rdeva/medrecord to run)")
        return []
    failures = []

    # entry 09 (ce67468): "Add info icon..." - silently drops the SMS hint line. MUST flag.
    diff, msg = _real_show(repo, "ce67468")
    res = build_ui_copy_removal_check(diff, msg, [], False, [])
    ok = (
        res["detected"]
        and any(r["file"].endswith("ConsentLookupScreen.tsx") for r in res["removals"])
        and any("An SMS will be sent" in r["text"] for r in res["removals"])
    )
    if not ok:
        failures.append(f"[REGRESSION entry 09] undisclosed hint removal not caught: {res}")
    else:
        print("  ok   REGRESSION     entry 09: undisclosed removal of the SMS hint line -> flagged")

    # entry 08 (24ef723): commit message says "Removed CTA from inside the found
    # card" AND the hint line is re-added lower down. MUST NOT flag.
    diff, msg = _real_show(repo, "24ef723")
    res = build_ui_copy_removal_check(diff, msg, [], False, [])
    if res["detected"]:
        failures.append(f"[REGRESSION entry 08] disclosed + relocated removal was flagged: {res}")
    else:
        print("  ok   REGRESSION     entry 08: removal disclosed in message + relocated -> not flagged")

    # entry 14 (cb66d392, PR #6 merge): terse merge message, but the diff drops
    # demo-scaffolding <Text> nodes ("Demo states - mockup only", "Mock auth ...").
    # PR #6's body says "demo switcher buttons removed" -> disclosed -> MUST NOT flag.
    diff, msg = _real_show(repo, "cb66d392", first_parent=True)
    fired_without_pr = build_ui_copy_removal_check(diff, msg, [], True, [])["detected"]
    res = build_ui_copy_removal_check(
        diff, msg, [{"title": "Pre-pilot fixes", "description": _PR6_BODY}], True, [])
    if res["detected"]:
        failures.append(f"[REGRESSION entry 14] removal disclosed in PR #6 body was flagged: {res}")
    elif not fired_without_pr:
        print("  warn REGRESSION     entry 14: no demo-text removal seen even without the PR body "
              "(diff shape changed?) - PR-disclosure path not exercised")
    else:
        print("  ok   REGRESSION     entry 14: demo-text removal disclosed in PR #6 body -> not flagged")

    return failures


def _run():
    with tempfile.TemporaryDirectory() as tmp:
        failures = (
            _check_helpers()
            + _check_removal(tmp)
            + _check_contract_override()
            + _check_real_entries()
        )
    print()
    if failures:
        print(f"FAIL - {len(failures)} ui-copy-removal-check test(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS - all ui-copy-removal-check tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run())
