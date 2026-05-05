---
id: A01-P3-001
severity: P3
title: "Prior trufflehog scan artefact committed in docs/deep-audit-2026-05-03 — placeholders only, but principle violation"
domain: Credential & secret hygiene
files:
  - docs/deep-audit-2026-05-03/artifacts/tool-output/trufflehog.jsonl
---

## Issue
`docs/deep-audit-2026-05-03/artifacts/tool-output/trufflehog.jsonl` contains six committed lines that re-print the strings the scanner detected. In this case all six are placeholders (`postgresql://meddoc:CHANGE_ME_DB_PASSWORD@postgres:5432`, etc.) — so no live secret is in the file — but the **practice** of committing the raw scanner output is risky.

If the next time this artefact pattern fires it captures a real key (e.g. someone runs the scan after temporarily populating `.env.production.example` for a test), the live key would land in git history.

## Evidence
`docs/deep-audit-2026-05-03/artifacts/tool-output/trufflehog.jsonl` (representative line, redacted):
```
{"DetectorName":"Postgres", ..., "Raw":"postgresql://meddoc:CHANGE_THIS_DB_PASSWORD@postgres:5432", ...}
```

trufflehog itself flagged this artefact during today's scan (Detector=Postgres, Verified=False) — see /tmp/trufflehog-full.jsonl from this audit run.

## Risk
- Pattern liability: any future audit that doesn't redact before committing the scanner artifact leaks secrets.
- The current six lines are placeholders, but the precedent is that "scanner output goes in the repo unmodified".

## Recommended fix
1. Add a CI step (after `gitleaks` from P2-003) that fails if `**/trufflehog*.json*` or similar artefacts contain anything non-redacted. Or better, gitignore the path entirely.
2. Update the audit-process doc (whichever file in `docs/deep-audit-2026-05-03/` describes the workflow) to specify `--redact` flag and a strip pass before committing.
3. Add `*.trufflehog.json*` and similar globs to `.gitignore` defensively.
