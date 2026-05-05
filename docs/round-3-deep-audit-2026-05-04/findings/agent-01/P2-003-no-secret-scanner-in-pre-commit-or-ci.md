---
id: A01-P2-003
severity: P2
title: "No automated secret scanner in pre-commit hooks or CI despite documented obligation"
domain: Credential & secret hygiene
files:
  - .github/workflows/test.yml
  - .github/workflows/a11y.yml
  - .github/workflows/nightly-tests.yml
  - docs/LAUNCH_CHECKLIST.md:115
---

## Issue
`docs/LAUNCH_CHECKLIST.md:115` (under the unchecked "OPENAI_API_KEY rotation" section) lists as a launch-gate item:

> - [ ] Add the key pattern (`sk-proj-[A-Za-z0-9]{40,}`) to a pre-commit secret-scanner (git-secrets, detect-secrets, gitleaks) — pick one and install on the repo

This is **un-checked** as of 2026-05-04. There is no `.pre-commit-config.yaml`, no Husky `pre-commit` script that runs a scanner, and no CI step that runs `gitleaks`, `trufflehog`, or `detect-secrets`.

Given the documented prior incident (3 GitHub PATs + 1 OpenAI key exposed), shipping pre-pilot without any scanner is a regression hazard.

## Evidence
- `find /opt/meddoc-pro -name '.pre-commit-config*' -o -name '.husky' 2>&1`: no results.
- `package.json` scripts (root): no `pre-commit` / `husky` setup; `gitleaks` / `trufflehog` / `detect-secrets` not in `devDependencies`.
- `.github/workflows/`: only `test.yml`, `a11y.yml`, `nightly-tests.yml`. None invoke a secret scanner. (`grep -rE 'gitleaks|trufflehog|detect-secrets' .github/`: 0 hits.)
- The host has `trufflehog` installed at `/usr/local/bin/trufflehog`, but that's a dev-machine convenience, not a repo-policy gate.

## Risk
1. The next contributor pasting a key into a commit goes undetected until production logs blow up. The previous incident was discovered because a key got revoked in flight, not because of a tooling gate.
2. PR review alone is insufficient for high-entropy strings — humans miss them, and large diffs pile up `package-lock.json` lines that hide additions.
3. Any of the placeholders being silently replaced with real values (e.g. `.env.production.example` getting populated by a sloppy edit) would not get caught.

## Recommended fix
1. Add a `.github/workflows/secrets.yml` that runs `gitleaks detect --source . --redact` on every PR and on push to `main`, failing on any non-zero exit.
2. Install `husky` + a `pre-commit` hook that runs `gitleaks protect --staged` on the developer's machine.
3. Tick the LAUNCH_CHECKLIST §6 box once both are merged and tested with a known-bad fixture (a deliberate fake `sk-ant-` line in a throwaway commit, then verify the gate blocks it).
4. Pin the `gitleaks` config to the exact patterns from `docs/ROTATION_RUNBOOK.md` so the scanner knows which key prefixes are in scope.
