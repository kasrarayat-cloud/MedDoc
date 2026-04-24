#!/usr/bin/env python3
"""Render the aggregated JSON report into HTML using template.html.

Usage:
    python3 render_report.py <input.json> <template.html> <output.html>

Placeholders in the template:
    {{TITLE}}       — report title (ISO timestamp)
    {{SUMMARY}}     — inline summary counts
    {{SUITES_HTML}} — rendered suite sections
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path


STATUS_COLORS = {
    "pass": "#16a34a",
    "fail": "#dc2626",
    "warn": "#d97706",
    "skip": "#6b7280",
}


def status_pill(status: str) -> str:
    color = STATUS_COLORS.get(status, "#6b7280")
    return (
        f'<span class="pill" style="background:{color}22;color:{color};'
        f'border:1px solid {color}66">{html.escape(status.upper())}</span>'
    )


def render_suite(s: dict) -> str:
    rows = []
    for r in s.get("results", []):
        details = html.escape(r.get("details") or "")
        rows.append(
            "<tr>"
            f'<td>{status_pill(r.get("status","warn"))}</td>'
            f'<td class="name">{html.escape(r.get("name","?"))}</td>'
            f'<td class="num">{int(r.get("durationMs",0))}ms</td>'
            f'<td class="details">{details}</td>'
            "</tr>"
        )
    summary = (
        f'{s.get("pass",0)} pass · {s.get("fail",0)} fail · '
        f'{s.get("skip",0)} skip · {s.get("warn",0)} warn'
    )
    status_cls = "ok" if s.get("fail", 0) == 0 else "err"
    return (
        f'<section class="suite {status_cls}">'
        f'<header><h2>{html.escape(s.get("suite","?"))}</h2>'
        f'<span class="summary">{summary}</span></header>'
        '<table><thead><tr><th>Status</th><th>Test</th>'
        "<th>Duration</th><th>Details</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table>'
        "</section>"
    )


def main() -> int:
    inp, tpl, out = (Path(p) for p in sys.argv[1:4])
    data = json.loads(inp.read_text())
    template = tpl.read_text()

    total = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for s in data.get("suites", []):
        for k in total:
            total[k] += int(s.get(k, 0))

    title = f"MedDoc automated tests — {data.get('generatedAt','')}"
    summary = (
        f'<strong>{total["pass"]} pass</strong> · '
        f'<strong style="color:#dc2626">{total["fail"]} fail</strong> · '
        f'{total["skip"]} skip · {total["warn"]} warn'
    )
    suites_html = "\n".join(render_suite(s) for s in data.get("suites", []))

    rendered = (
        template.replace("{{TITLE}}", html.escape(title))
        .replace("{{SUMMARY}}", summary)
        .replace("{{SUITES_HTML}}", suites_html)
    )
    out.write_text(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
