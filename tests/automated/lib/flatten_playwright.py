#!/usr/bin/env python3
"""Flatten Playwright's native JSON reporter output into the shape
run-all.sh expects — {suite, pass, fail, warn, skip, results[]}.

Usage:
    python3 flatten_playwright.py reports/playwright-latest.json

Outputs one JSON object on stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def walk(suites: list, results: list) -> None:
    for s in suites:
        for spec in s.get("specs", []):
            for t in spec.get("tests", []):
                # Each "test" has a list of "results" (per-retry), plus
                # a top-level "status" that captures the outcome even
                # when the results array is empty (happens for skips).
                rs = t.get("results", []) or []
                last = rs[-1] if rs else {}
                raw_status = last.get("status") or t.get("status") or "unknown"
                mapped = {
                    "passed": "pass",
                    "expected": "pass",
                    "failed": "fail",
                    "timedOut": "fail",
                    "unexpected": "fail",
                    "skipped": "skip",
                    "interrupted": "fail",
                    "flaky": "warn",
                }.get(raw_status, "warn")
                name = f"{spec.get('title','?')} — {t.get('projectName','?')}"
                details = ""
                if mapped == "fail":
                    err = last.get("error", {}) or {}
                    details = (err.get("message", "") or "").split("\n")[0][:400]
                results.append(
                    {
                        "name": name,
                        "status": mapped,
                        "durationMs": int(last.get("duration", 0) or 0),
                        "details": details,
                    }
                )
        walk(s.get("suites", []), results)


def main() -> int:
    path = Path(sys.argv[1])
    data = json.loads(path.read_text())
    results: list[dict] = []
    walk(data.get("suites", []), results)

    counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print(
        json.dumps(
            {
                "suite": "e2e",
                **counts,
                "results": results,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
