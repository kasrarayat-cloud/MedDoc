"""Render the offline Corti adapter output as a private, inert HTML preview.

This is deliberately not imported by the application or a provider client. It
reads saved JSON and writes a standalone file; it has no network dependencies.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "quillmd-corti-replay-v1"


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _json(value: Any) -> str:
    return _escape(json.dumps(value, ensure_ascii=False, indent=2))


def _value(value: Any) -> str:
    return _escape(value) if value is not None and value != "" else "Not available"


def _list(items: list[Any]) -> str:
    return "<ul>" + "".join(f"<li>{_escape(item)}</li>" for item in items) + "</ul>"


def _diagnostic_counts(diagnostics: dict[str, Any]) -> tuple[str, str]:
    """Count arrays only, without normalizing away malformed raw diagnostics."""
    candidates = diagnostics.get("candidates", [])
    candidate_count = str(len(candidates)) if isinstance(candidates, list) else "Unavailable (malformed collection)"
    groups = diagnostics.get("alternatives", [])
    if not isinstance(groups, list):
        return candidate_count, "Unavailable (malformed collection)"
    count = 0
    malformed = False
    for group in groups:
        alternatives = group.get("alternatives") if isinstance(group, dict) else None
        if isinstance(alternatives, list):
            count += len(alternatives)
        else:
            malformed = True
    alternative_count = f"{count} countable; malformed collection present" if malformed else str(count)
    return candidate_count, alternative_count


def _evidence(item: dict[str, Any]) -> str:
    spans = item.get("evidence", [])
    if not spans:
        return '<p class="warning-text">No supporting evidence was returned.</p>'
    rendered = []
    for span in spans:
        valid = span.get("status") == "valid"
        rendered.append(
            '<div class="evidence">'
            f'<blockquote>{_escape(span.get("text", ""))}</blockquote>'
            '<p class="small muted">'
            f'{"Exact source match" if valid else "Evidence could not be verified"}'
            f' · Context {_value(span.get("context_index"))}'
            f' · Characters {_value(span.get("start"))}–{_value(span.get("end"))}'
            '</p>'
            + (f'<p class="small warning-text">{_escape(span["reason"])}</p>'
               if span.get("reason") else "")
            + '</div>'
        )
    return "".join(rendered)


def _terminology(item: dict[str, Any]) -> str:
    term = item.get("terminology", {})
    verified = term.get("status") == "verified"
    label = "Dated terminology verified" if verified else "Terminology unverified"
    result = (
        f'<span class="badge {"neutral" if verified else "warning"}">{label}</span>'
        f'<p class="small">Status: {_value(term.get("status"))}</p>'
    )
    if term.get("description") is not None:
        result += (
            '<p class="small"><strong>Reference description</strong><br>'
            f'{_escape(term["description"])}</p>'
        )
    if term.get("description_matches") is False:
        result += '<p class="warning-text small">Provider description differs from the dated reference.</p>'
    result += (
        '<dl class="small">'
        f'<dt>Release</dt><dd>{_value(term.get("version"))}</dd>'
        f'<dt>Effective from</dt><dd>{_value(term.get("effective_from"))}</dd>'
        f'<dt>Effective until</dt><dd>{_value(term.get("effective_until"))}</dd>'
        f'<dt>Source</dt><dd>{_value(term.get("source"))}</dd>'
        '</dl>'
    )
    if term.get("reason"):
        result += f'<p class="small warning-text">{_escape(term["reason"])}</p>'
    return result


def _row(item: dict[str, Any]) -> str:
    system = item.get("system", "Unknown system")
    system_label = "ICD-10-CM outpatient" if system == "icd10cm-outpatient" else str(system).upper()
    issues = item.get("issues", [])
    return (
        '<tr>'
        '<td class="proposal">'
        f'<span class="small muted">{_escape(system_label)}</span>'
        f'<h3 class="code">{_escape(item.get("code", "Unknown code"))}</h3>'
        '<span class="badge warning">Not approved</span>'
        '<p class="small"><strong>Original provider description</strong><br>'
        f'{_value(item.get("provider_display"))}</p>'
        '<p class="small muted">Provider-selected proposal. Clinical applicability requires clinician review.</p>'
        + (f'<div class="issue-list small">{_list(issues)}</div>' if issues else "")
        + '</td><td class="support">'
        f'<p class="small"><strong>Evidence: {_value(item.get("evidence_status"))}</strong></p>'
        + _evidence(item)
        + '<p class="small muted">Quoted documentation is retained evidence, not independent confirmation of clinical applicability.</p>'
        '</td><td class="reference">'
        + _terminology(item)
        + '</td></tr>'
    )


CSS = """
:root { --canvas:#f4f6f2; --ink:#23382d; --muted:#566951; --line:#d9e1d5;
  --accent:#173e2f; --warning:#785516; --warning-bg:#fcf5e6;
  --danger:#a42c2c; --danger-bg:#fff0ee; font-family:"Segoe UI",system-ui,sans-serif;
  color:var(--ink); font-size:15px; line-height:1.5; }
* { box-sizing:border-box; } body { margin:0; background:var(--canvas); }
a { color:var(--accent); } h1,h2,h3,p { margin-top:0; }
h1,h2,h3 { text-wrap:balance; } h1 { font-size:2rem; line-height:1.2; letter-spacing:-.04em; }
h2 { font-size:1.2rem; } h3 { font-size:1rem; }
p { margin-bottom:14px; } .small { font-size:.85rem; } .muted { color:var(--muted); }
.topbar { padding:18px max(24px,calc((100vw - 1320px)/2)); background:#fbfcf9;
  border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.brand { font-weight:700; font-size:1.2rem; letter-spacing:-.03em; }
.eyebrow { color:var(--muted); text-transform:uppercase; font-size:.74rem; letter-spacing:.09em; }
main { max-width:1368px; margin:0 auto; padding:28px 24px 60px; }
.replay-heading { display:flex; justify-content:space-between; align-items:start; gap:22px; }
.replay-heading p { max-width:75ch; }
.notice { border:1px solid var(--line); border-radius:12px; padding:16px 20px; margin:20px 0; overflow-wrap:anywhere; }
.notice p:last-child { margin-bottom:0; } .failure { color:var(--danger); background:var(--danger-bg); border-color:#e9c4bd; }
.warning { color:var(--warning); background:var(--warning-bg); border-color:#e5c98f!important; }
.warning-text { color:var(--warning); } .badge { display:inline-block; padding:3px 7px; font-size:.75rem;
  border:1px solid var(--line); border-radius:4px; font-weight:600; }
.neutral { background:var(--canvas); color:var(--ink); }
.summary { display:grid; grid-template-columns:1fr 1fr 2fr; gap:22px; padding:20px 0; }
.summary p { margin-bottom:0; } .summary strong { display:block; font-size:.85rem; }
.table-wrap { background:white; border:1px solid var(--line); border-radius:12px; overflow:hidden; }
table { border-collapse:collapse; width:100%; table-layout:fixed; }
caption { text-align:left; padding:20px; font-size:1.15rem; font-weight:650; }
th { text-align:left; background:#eef2eb; color:var(--muted); font-size:.8rem; padding:12px 20px; }
td { vertical-align:top; padding:22px 20px; border-top:1px solid var(--line); overflow-wrap:anywhere; }
.proposal { width:27%; } .support { width:43%; } .reference { width:30%; }
.code { font:650 1.45rem ui-monospace,Consolas,monospace; margin:5px 0 10px; }
.proposal > .badge { margin-bottom:16px; } .evidence { margin-bottom:14px; }
blockquote { margin:0 0 6px; border-left:3px solid #b4c2ac; padding-left:12px; font-size:.9rem; white-space:pre-wrap; }
.evidence p { margin-bottom:0; } dl { margin:12px 0; } dt { font-weight:600; } dd { margin:0 0 7px; overflow-wrap:anywhere; }
li + li { margin-top:7px; } ul { padding-left:20px; } .issue-list { color:var(--warning); }
details { background:white; border:1px solid var(--line); border-radius:12px; margin-top:22px; padding:16px 20px; }
summary { color:var(--accent); cursor:pointer; font-weight:600; min-height:28px; }
summary:focus-visible,a:focus-visible { outline:3px solid var(--accent); outline-offset:4px; }
details[open] summary { margin-bottom:18px; } details details { background:var(--canvas); }
pre { font: .8rem/1.5 ui-monospace,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; }
.note { white-space:pre-wrap; max-width:100ch; } .hash { font-family:ui-monospace,Consolas,monospace; overflow-wrap:anywhere; }
.footer { border-top:1px solid var(--line); padding-top:20px; margin-top:28px; }
.skip { position:absolute; left:24px; top:-90px; background:white; padding:10px; }
.skip:focus { top:10px; }
@media(max-width:800px) { .replay-heading { display:block; } .summary { grid-template-columns:1fr 1fr; }
  .summary > :last-child { grid-column:1/-1; } table,tbody,tr,td { display:block; width:100%; }
  thead { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
  tr + tr { border-top:3px solid var(--line); } td { border-top:0; padding:14px 20px; }
  td.proposal,td.support,td.reference { width:100%; } td.reference { background:#f9fbf7; }
  td.support:before { content:"Evidence from the synthetic note"; display:block; font-size:.9rem; font-weight:650; margin-bottom:14px; }
  td.reference:before { content:"Terminology for the service date"; display:block; font-size:.9rem; font-weight:650; margin-bottom:14px; }
}
@media(max-width:420px) { main { padding:24px 14px 40px; } h1 { font-size:1.6rem; } .summary { grid-template-columns:1fr; } }
@media print { body { background:white; } details { break-inside:avoid; } .skip { display:none; } }
"""


def render_preview(result: dict[str, Any], request: dict[str, Any]) -> str:
    """Render only adapter proposals in the main table; diagnostics stay inert.

    Reject a different schema or execution mode. All dynamic text, including
    source strings and full diagnostic JSON, is escaped as text, never markup.
    The historic FAIL is a fixed property of this preview, not an inferred test
    verdict; this renderer cannot reclassify the original trial.
    """
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported offline adapter schema")
    if result.get("mode") != "offline_replay":
        raise ValueError("Preview accepts offline replay results only")
    if result.get("dashboard_activation_allowed") is not False:
        raise ValueError("This preview requires dashboard activation to remain disabled")
    selections = result.get("proposed_selections", [])
    if not isinstance(selections, list):
        raise ValueError("Adapter proposed_selections must be a list")
    if any(item.get("approved") is not False or item.get("selectable") is not False for item in selections):
        raise ValueError("Replay proposals must remain unapproved and non-selectable")
    rows = "".join(_row(item) for item in selections)
    if not rows:
        rows = '<tr><td colspan="3">No provider-selected proposals are available.</td></tr>'
    diagnostics = result.get("diagnostics", {})
    candidate_count, alternative_count = _diagnostic_counts(diagnostics)
    blockers = result.get("blockers", [])
    contexts = request.get("context", [])
    note = "\n\n".join(str(context.get("text", "")) for context in contexts if context.get("type") == "text")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>QuillMD — Synthetic Corti replay</title><style>{CSS}</style></head>
<body><a class="skip" href="#main">Skip to replay</a>
<header class="topbar"><span class="brand">QuillMD</span><span class="small">Private offline preview · No live connection</span></header>
<main id="main"><div class="replay-heading"><div><p class="eyebrow">Corti integration preparation</p>
<h1>Synthetic replay — not live</h1>
<p>Provider-selected code proposals from the retained synthetic response. Every proposal remains unapproved and requires clinician review.</p></div>
<span class="badge warning">Dashboard activation blocked</span></div>
<section class="notice failure" aria-labelledby="original-verdict"><h2 id="original-verdict">Original response quality: FAIL</h2>
<p>The original trial verdict is preserved. Correct selected code identifiers do not resolve the description defect or unsupported unselected material.</p>
<p class="small">Recorded verdict: {_value(result.get("original_verdict"))}</p></section>
<div class="summary"><p><strong>Date of service</strong>{_value(result.get("service_date"))}</p>
<p><strong>Provider-selected proposals</strong>{len(selections)} · 0 approved</p>
<p><strong>Review boundary</strong>Evidence matching and dated terminology checks do not establish clinical applicability or reimbursement.</p></div>
<div class="table-wrap"><table><caption>Proposed clinician display</caption>
<thead><tr><th class="proposal" scope="col">Provider-selected proposal</th><th class="support" scope="col">Evidence from the synthetic note</th><th class="reference" scope="col">Terminology for the service date</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<section class="notice warning" aria-labelledby="blockers"><h2 id="blockers">What still prevents activation</h2>
{_list(blockers) if blockers else '<p>Single-response replay validation does not establish production readiness. Activation remains disabled.</p>'}
</section>
<details><summary>Original synthetic note</summary><p class="note">{_escape(note)}</p></details>
<details id="diagnostics"><summary>Unselected diagnostics · {candidate_count} candidates · {alternative_count} nested alternatives</summary>
<p>Unselected and unverified provider material. These records are retained for investigation only; they are not proposed selections, supported codes, or approvals.</p>
<details><summary>Unselected candidates</summary><pre>{_json(diagnostics.get("candidates", []))}</pre></details>
<details><summary>Nested alternatives — unselected</summary><pre>{_json(diagnostics.get("alternatives", []))}</pre></details>
<details><summary>Rejected selected records</summary><pre>{_json(diagnostics.get("rejected_selected", []))}</pre></details>
<details><summary>Complete retained provider response</summary><pre>{_json(diagnostics.get("provider_response", {}))}</pre></details>
</details>
<footer class="footer small muted"><p>Replay source SHA-256: <span class="hash">{_value(result.get("source_response_sha256"))}</span></p>
<p>Private static artifact. No provider requests, selection controls, approval actions, or clinical writes are available. This preview does not change the clinical document, Word export, existing ICD workflow, or live provider.</p></footer>
</main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    request = json.loads(args.request.read_text(encoding="utf-8"))
    rendered = render_preview(result, request)
    # O_EXCL prevents overwriting the original evidence or an earlier preview.
    # Mode 0600 makes the artifact private even under a permissive caller umask.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(rendered)


if __name__ == "__main__":
    main()
