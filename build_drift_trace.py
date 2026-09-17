#!/usr/bin/env python3
"""Builds the Drift Trace dashboard: an HTML page tracing every golden
entry through all four pipeline stages (Layer 2 checks, the AI's raw
read, rule enforcement, the text-match validator) against golden.

Reads eval_output/results-dashboard-full.jsonl (produced by
run_dashboard_eval.py). Self-contained - the template lives in this file,
not in any scratch/session-specific artifact, so this keeps working next
time someone runs it.

Usage:
    python3 run_dashboard_eval.py   # regenerate the underlying eval data
    python3 build_drift_trace.py    # regenerate eval_output/drift-trace.html

Then republish eval_output/drift-trace.html to the existing Drift Trace
artifact (same URL) so the shared link reflects the new run. That publish
step has to happen from a Claude Code session - there's no script for it.
"""
import html
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent
DATA = PROJ / "eval_output" / "results-dashboard-full.jsonl"
OUT = PROJ / "eval_output" / "drift-trace.html"

STATUS_CLASS = {"Code complete": "complete", "Tested": "complete", "Pending": "pending", "Flagged": "flagged", "ERROR": "flagged"}

RULE_LABELS = {
    "sweeping_claim_check": "rule 9",
    "overclaim_check": "rule 14",
    "ui_copy_removal_check": "rule 15",
    "unexplained_deletions": "rule 11",
}

HEAD = """<title>Drift Trace</title>
<style>
  :root{
    --bg:#f6f8f6; --surface:#ffffff; --surface-2:#eef2ef; --border:#dbe3dd;
    --text:#101a15; --muted:#5b6d64; --faint:#8a9a91;
    --accent:#1f8f78; --accent-soft:#e3f3ee;
    --complete:#2f9e5b; --complete-soft:#e5f6ea;
    --pending:#b8801f; --pending-soft:#faf0dc;
    --flagged:#c9503f; --flagged-soft:#fbe8e4;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    --sans: 'Sora', system-ui, -apple-system, sans-serif;
    --match:#2f9e5b; --mismatch:#c9503f;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#0d1210; --surface:#131a17; --surface-2:#182019; --border:#263029;
      --text:#e7ede9; --muted:#8ea296; --faint:#5e6f67;
      --accent:#5fd0b8; --accent-soft:#16302a;
      --complete:#5cc584; --complete-soft:#122a1c;
      --pending:#e0b25a; --pending-soft:#2e2413;
      --flagged:#ea7565; --flagged-soft:#2e1815;
    }
  }
  :root[data-theme="dark"]{
    --bg:#0d1210; --surface:#131a17; --surface-2:#182019; --border:#263029;
    --text:#e7ede9; --muted:#8ea296; --faint:#5e6f67;
    --accent:#5fd0b8; --accent-soft:#16302a;
    --complete:#5cc584; --complete-soft:#122a1c;
    --pending:#e0b25a; --pending-soft:#2e2413;
    --flagged:#ea7565; --flagged-soft:#2e1815;
  }
  * { box-sizing: border-box; }
  body{ background: var(--bg); color: var(--text); font-family: var(--sans); padding-inline: 16px; padding-block: 28px 60px; line-height: 1.5; }
  .wrap{ max-width: 920px; margin: 0 auto; }
  .eyebrow{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); margin: 0 0 8px; }
  h1{ font-size: clamp(26px, 5vw, 34px); margin: 0 0 6px; letter-spacing: -0.01em; text-wrap: balance; }
  .sub{ color: var(--muted); font-size: 14.5px; max-width: 66ch; margin: 0 0 22px; }
  .banner{ background: var(--accent-soft); border: 1px solid var(--accent); border-radius: 10px; padding: 14px 16px; font-size: 13px; color: var(--text); margin-bottom: 20px; }
  .scoreboard{ display:flex; gap: 18px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid color-mix(in srgb, var(--accent) 35%, transparent); }
  .score-item{ font-family: var(--mono); font-size: 12px; }
  .score-num{ font-size: 16px; font-weight: 700; color: var(--complete); font-variant-numeric: tabular-nums; }
  .section-label{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); margin: 0 0 10px; padding-top: 4px; }
  .sha{ font-family: var(--mono); font-size: 12px; color: var(--muted); margin: 0 0 4px; }
  .summary{ font-size: 14.5px; margin: 0; color: var(--text); }
  .verdicts{ display:flex; align-items:center; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
  .pill{ font-family: var(--mono); font-size: 11px; font-weight: 600; letter-spacing: 0.02em; padding: 4px 10px; border-radius: 999px; white-space: nowrap; }
  .pill.complete{ background: var(--complete-soft); color: var(--complete); }
  .pill.pending{ background: var(--pending-soft); color: var(--pending); }
  .pill.flagged{ background: var(--flagged-soft); color: var(--flagged); }
  .arrow{ color: var(--faint); font-size: 13px; }
  .verdict-tag{ font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; padding: 4px 8px; border-radius: 6px; font-weight: 700; }
  .verdict-tag.match{ color: var(--match); background: color-mix(in srgb, var(--match) 14%, transparent); }
  .verdict-tag.mismatch{ color: var(--mismatch); background: color-mix(in srgb, var(--mismatch) 14%, transparent); }
  .verdict-tag.same{ color: var(--faint); background: var(--surface-2); }
  .stages{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; background: var(--border); }
  @media (max-width: 640px){ .stages{ grid-template-columns: 1fr; } }
  .stage{ background: var(--surface); padding: 14px 16px; min-width: 0; }
  .stage-title{ font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--faint); margin: 0 0 10px; display: flex; align-items: center; gap: 6px; }
  .stage-num{ display:inline-flex; align-items:center; justify-content:center; width: 16px; height: 16px; border-radius: 50%; background: var(--surface-2); color: var(--faint); font-size: 9px; }
  .chip-row{ display:flex; flex-direction: column; gap: 6px; }
  .chip{ display:flex; align-items: baseline; gap: 7px; font-size: 12.5px; padding: 6px 8px; border-radius: 7px; background: var(--surface-2); }
  .chip.fired{ background: var(--pending-soft); }
  .chip.fired.hard{ background: var(--flagged-soft); }
  .chip-dot{ width: 6px; height: 6px; border-radius: 50%; background: var(--faint); flex-shrink: 0; margin-top: 3px; }
  .chip.fired .chip-dot{ background: var(--pending); }
  .chip.fired.hard .chip-dot{ background: var(--flagged); }
  .chip-name{ font-family: var(--mono); color: var(--text); font-size: 12px; }
  .chip-note{ color: var(--muted); font-size: 11.5px; }
  details.narrative{ font-size: 12.5px; color: var(--muted); }
  details.narrative summary{ cursor: pointer; font-family: var(--mono); font-size: 11px; color: var(--accent); letter-spacing: 0.02em; list-style: none; }
  details.narrative summary::-webkit-details-marker{ display:none; }
  details.narrative summary::before{ content: "\\25B8 "; }
  details.narrative[open] summary::before{ content: "\\25BE "; }
  details.narrative p{ margin: 8px 0 0; line-height: 1.55; }
  .rule-flow{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom: 10px; }
  .no-fire{ font-size: 12.5px; color: var(--muted); font-style: italic; }
  .matched{ font-family: var(--mono); font-size: 11px; color: var(--pending); background: var(--pending-soft); padding: 2px 7px; border-radius: 6px; display:inline-block; margin-top: 6px; }
  .note{ font-size: 12px; color: var(--muted); margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border); }
  .note b{ color: var(--text); }
  .note.watch{ border-top-color: color-mix(in srgb, var(--pending) 40%, transparent); }
  code.k{ font-family: var(--mono); background: var(--surface-2); padding: 1px 4px; border-radius: 4px; font-size: 11px; }
  footer{ margin-top: 30px; font-size: 12px; color: var(--faint); font-family: var(--mono); }
  .entry{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; margin-bottom: 10px; overflow: hidden; }
  .entry > summary{ cursor: pointer; list-style: none; padding: 14px 18px; }
  .entry > summary::-webkit-details-marker{ display:none; }
  .entry > summary::before{ content: "\\25B8"; color: var(--faint); display:inline-block; width: 14px; }
  .entry[open] > summary::before{ content: "\\25BE"; }
  .entry-head{ display:inline-flex; width: calc(100% - 16px); flex-wrap: wrap; gap: 10px 16px; align-items: flex-start; justify-content: space-between; }
  .entry-head-left{ min-width: 0; flex: 1 1 320px; }
  .entry .stages{ border-top: 1px solid var(--border); }
  .entry .note, .entry > .note{ margin: 10px 18px 4px; }
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
"""


def chip(name, state, note):
    cls = "chip"
    if state == "hard":
        cls += " fired hard"
    elif state == "fired":
        cls += " fired"
    return f'<div class="{cls}"><span class="chip-dot"></span><span class="chip-name">{name}</span><span class="chip-note">{html.escape(note)}</span></div>'


def check_chips(checks):
    sc = checks.get("sweeping_claim_check") or {}
    sc_hard = any(v.get("claim_holds") is False for v in sc.get("verifications", []))
    sc_detected = sc.get("detected")
    oc_detected = (checks.get("overclaim_check") or {}).get("detected")
    uc_detected = (checks.get("ui_copy_removal_check") or {}).get("detected")
    ud = checks.get("unexplained_deletions") or []

    out = []
    if sc_hard:
        out.append(chip("sweeping_claim_check", "hard", "fired — claim fails"))
    elif sc_detected:
        out.append(chip("sweeping_claim_check", "fired", "fired — claim holds"))
    else:
        out.append(chip("sweeping_claim_check", "clean", "clean"))
    out.append(chip("overclaim_check", "hard" if oc_detected else "clean", "fired — verified false" if oc_detected else "clean"))
    out.append(chip("ui_copy_removal_check", "hard" if uc_detected else "clean", "fired — undisclosed removal" if uc_detected else "clean"))
    out.append(chip("unexplained_deletions", "hard" if ud else "clean", f"fired — {len(ud)} file(s)" if ud else "none"))

    armed = []
    if sc_hard:
        armed.append("sweeping_claim_check")
    if oc_detected:
        armed.append("overclaim_check")
    if uc_detected:
        armed.append("ui_copy_removal_check")
    if ud:
        armed.append("unexplained_deletions")
    return "".join(out), armed


def pill(status):
    return f'<span class="pill {STATUS_CLASS.get(status, "pending")}">{html.escape(status)}</span>'


def render_entry(row):
    gf = row["golden_file"]
    golden = row["golden"]
    runs = row["runs"]
    r0 = runs[0]
    golden_status = golden["verified_status"]
    final_status = r0["validator_status"]
    is_match = golden_status == final_status
    n_runs = len(runs)

    chips_html, armed = check_chips(row["checks"])

    changed = r0["raw_status"] != r0["rule_status"]
    if not armed:
        rule_note = "No override rule armed this run — none of the four checks fired."
    elif changed:
        names = ", ".join(f"{RULE_LABELS[a]} ({a})" for a in armed)
        rule_note = f"Armed: {names}. Forced the status from {r0['raw_status']} to {r0['rule_status']}."
    else:
        names = ", ".join(f"{RULE_LABELS[a]} ({a})" for a in armed)
        rule_note = f"Armed: {names}. The model already said {r0['rule_status']} on its own — confirms, doesn't change anything."

    fired_runs = [(i, r) for i, r in enumerate(runs) if r["matched_phrases"]]
    if not fired_runs:
        validator_html = '<p class="no-fire">did not fire' + (f' in any of {n_runs} runs' if n_runs > 1 else '') + '</p>'
    else:
        parts = []
        for i, r in fired_runs:
            phrases = ", ".join(f'&quot;{html.escape(p)}&quot;' for p in r["matched_phrases"])
            parts.append(
                f'<div class="rule-flow">{pill(r["rule_status"])}<span class="arrow">&rarr;</span>{pill(r["validator_status"])}'
                f'<span class="matched" style="margin-top:0">{phrases}</span></div>'
            )
        prefix = f'<p class="no-fire" style="font-style:normal;color:var(--muted);margin-bottom:8px;">fired in {len(fired_runs)} of {n_runs} runs:</p>' if n_runs > 1 else ""
        validator_html = prefix + "".join(parts)

    variance_tag = ""
    run_summary = ""
    if n_runs > 1:
        finals = [r["validator_status"] for r in runs]
        stable = len(set(finals)) == 1
        variance_tag = f'<span class="verdict-tag {"match" if stable else "mismatch"}">{n_runs}&times; run &middot; {"stable" if stable else "flips"}</span>'
        run_summary = f'<p class="note" style="border-top:none;padding-top:0;margin-top:2px;">Raw AI answer across {n_runs} independent runs: {", ".join(r["raw_status"] for r in runs)}. Final: {", ".join(finals)}.</p>'

    return f"""
  <details class="entry">
    <summary>
      <div class="entry-head">
        <div class="entry-head-left">
          <p class="sha">{html.escape(golden['commit_id'])} &middot; golden/{gf.replace('.json','')}</p>
          <p class="summary">{html.escape(golden['plain_english_summary'])}</p>
        </div>
        <div class="verdicts">
          {pill(golden_status)}<span class="arrow">&rarr;</span>{pill(final_status)}
          <span class="verdict-tag {'match' if is_match else 'mismatch'}">{'match' if is_match else 'mismatch'}</span>
          {variance_tag}
        </div>
      </div>
    </summary>
    <div class="stages">
      <div class="stage">
        <p class="stage-title"><span class="stage-num">1</span>Layer 2 checks</p>
        <div class="chip-row">{chips_html}</div>
      </div>
      <div class="stage">
        <p class="stage-title"><span class="stage-num">2</span>AI raw read</p>
        {pill(r0['raw_status'])}
        <details class="narrative">
          <summary>full narrative{' (run 1)' if n_runs > 1 else ''}</summary>
          <p>{html.escape(r0['raw_narrative'])}</p>
        </details>
      </div>
      <div class="stage">
        <p class="stage-title"><span class="stage-num">3</span>Rule enforcement</p>
        <div class="rule-flow">{pill(r0['rule_status'])}<span class="verdict-tag same">{'override' if changed else 'no override'}</span></div>
        <p class="note">{html.escape(rule_note)}</p>
      </div>
      <div class="stage">
        <p class="stage-title"><span class="stage-num">4</span>Validator</p>
        {validator_html}
      </div>
    </div>
    {run_summary}
  </details>"""


def main():
    rows = sorted((json.loads(line) for line in DATA.open()), key=lambda r: r["golden_file"])
    match = sum(1 for r in rows if r["golden"]["verified_status"] == r["runs"][0]["validator_status"])
    total_runs = sum(len(r["runs"]) for r in rows)
    validator_fires = sum(1 for r in rows for run in r["runs"] if run["matched_phrases"])
    variance_entries = [r["golden_file"] for r in rows if len({run["validator_status"] for run in r["runs"]}) > 1]

    entries_html = "\n".join(render_entry(r) for r in rows)

    body = f"""<div class="wrap">
  <p class="eyebrow">status-drift-agent &middot; pipeline trace</p>
  <h1>Drift Trace</h1>
  <p class="sub">All {len(rows)} golden-set entries, four stages each: the deterministic checks that feed the model, the model's own raw read, the code-level rule enforcement that can override it, and the text-match validator that runs last. Click any row to expand its full trace.</p>

  <div class="banner">
    <b>Generated by build_drift_trace.py from eval_output/results-dashboard-full.jsonl.</b> Regenerate both with <code class="k">run_dashboard_eval.py</code> + <code class="k">build_drift_trace.py</code> whenever the pipeline changes, then republish this file to keep the shared link current.
    <div class="scoreboard">
      <span class="score-item"><span class="score-num">{match} / {len(rows)}</span> match golden</span>
      <span class="score-item"><span class="score-num">{total_runs}</span> total model calls</span>
      <span class="score-item"><span class="score-num">{validator_fires} / {total_runs}</span> validator fired</span>
      <span class="score-item"><span class="score-num">{len(variance_entries)}</span> entries unstable across runs</span>
    </div>
  </div>

{entries_html}

  <footer>eval_output/results-dashboard-full.jsonl &middot; regenerate with run_dashboard_eval.py + build_drift_trace.py</footer>
</div>"""

    OUT.write_text(HEAD + body)
    print(f"match={match}/{len(rows)} total_runs={total_runs} validator_fires={validator_fires} variance={variance_entries}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
