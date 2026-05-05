---
id: A01-P0-002
severity: P0
title: "OpenAI key documented as leaked + must-rotate is still live in 5 on-disk locations and 2 Docker images"
domain: Credential & secret hygiene
files:
  - docs/LAUNCH_CHECKLIST.md:90-118
  - .env:20
  - .env.backup:20
  - apps/meddoc-pro/.env:20
  - apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env:20
---

## Issue
`docs/LAUNCH_CHECKLIST.md` §6 states:

> **Status:** open security debt. Key was exposed in a dev log / commit / screen-share (root cause TBD below). Must rotate before production use.

and lists, as an **open** checkbox: "Log into OpenAI dashboard → API Keys → Delete the leaked key".

The key string flagged for rotation is `sk-proj-<REDACTED>...`. That same prefix is currently live (verified by trufflehog detector + by inspection) in **every** of these locations:

| Path | Mode | OpenAI key | Anthropic key | Deepgram key |
|---|---|---|---|---|
| `/opt/meddoc-pro/.env` | 640 | `sk-proj-<REDACTED>...` | `sk-ant-api03-<REDACTED>...` | `<REDACTED-DEEPGRAM>...` |
| `/opt/meddoc-pro/.env.backup` | **755** | same | same | same |
| `/opt/meddoc-pro/.env.local` | **755** | (not set) | same | (not set) |
| `/opt/meddoc-pro/apps/meddoc-pro/.env` | **777** | same | same | same |
| `/opt/meddoc-pro/apps/meddoc-pro/.env.local` | **777** | (not set) | same | (not set) |
| `/opt/meddoc-pro/apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env` | 755 | same | same | same |
| `/opt/meddoc-pro/tests/automated/.env.test` | 600 | (not present) | (not present) | (not present) — but contains live `RESEND_API_KEY=<REDACTED-LIVE-RESEND>` |

`apps/meddoc-pro/.env` and `apps/meddoc-pro/.env.local` are **mode 0777** (world-writable), with the live Anthropic + OpenAI keys readable by any local user. `.env.backup` and `.env.local` at the repo root are mode 0755 (world-readable).

Trufflehog filesystem scan output (excerpt, `/tmp/trufflehog-fs.jsonl`):
```
[Anthropic] verified=True | /opt/meddoc-pro/.env | raw=sk-ant-api03-<REDACTED>...
[Anthropic] verified=True | /opt/meddoc-pro/.env.backup | raw=sk-ant-api03-<REDACTED>...
[Anthropic] verified=True | /opt/meddoc-pro/.env.local | raw=sk-ant-api03-<REDACTED>...
[Anthropic] verified=True | /opt/meddoc-pro/apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env
[OpenAI]    verified=True | /opt/meddoc-pro/.env.backup | raw=sk-proj-<REDACTED>...
[Deepgram]  verified=True | /opt/meddoc-pro/.env | raw=<REDACTED-DEEPGRAM>...
[Deepgram]  verified=True | /opt/meddoc-pro/.env.backup
```
("Verified=True" = trufflehog hit the live provider API and the key is accepted.)

Either:
1. The "rotation" never happened — the key in `.env` IS the leaked key, in production. Or
2. The rotation happened but the leaked copy was not purged from `.env.backup` and `.next/standalone/.../.env`, leaving an attacker-discoverable copy of the old key on the box.

Either branch is P0.

## Evidence

`docs/LAUNCH_CHECKLIST.md:90-95`:
```
## 6. `OPENAI_API_KEY` rotation (leaked during development)

**Status:** open security debt. Key was exposed in a dev log / commit / screen-share
(root cause TBD below). Must rotate before production use.
```
…with the rotation steps as **un-checked** boxes (`- [ ]`) — see lines 96-118 of the same file.

`/opt/meddoc-pro/.env:20`:
```
OPENAI_API_KEY=sk-proj-<REDACTED-LIVE-KEY-MATCHES-LAUNCH_CHECKLIST.md-§6>
```
(Trufflehog verified `Verified=true` against OpenAI on 2026-05-04; key prefix `sk-proj-<REDACTED>…` matches the value documented as "must rotate" in `LAUNCH_CHECKLIST.md §6`. Full value omitted from this report deliberately.)
`/opt/meddoc-pro/.env.backup:20` carries the **identical** value, mode 0755 (world-readable).

`stat` summary:
```
640 .env
755 .env.backup            <-- world-readable, contains live keys
755 .env.local             <-- world-readable, contains live Anthropic key
777 apps/meddoc-pro/.env   <-- world-writable + readable
777 apps/meddoc-pro/.env.local <-- world-writable + readable
755 apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env
600 tests/automated/.env.test
```

Cross-reference: `docs/T-M15-AUDIT-REPORT.md` (Apr 2026) documented this rotation gap and `LAUNCH_CHECKLIST.md` (Apr 21, 2026) tracked it as a launch-gate blocker. Today is **2026-05-04**; the boxes are still unchecked and the key is still live + extant in seven locations.

## Risk
1. **Any process running as `claude` or any user** on the VPS reads `apps/meddoc-pro/.env` (mode 0777) and walks away with the OpenAI/Anthropic/Deepgram keys.
2. The **same** key prefix in `.env.backup` means even if `.env` gets rotated, `.env.backup` keeps a usable copy of either the leaked or new key — defeating rotation.
3. The `apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env` exists because Next.js's `output: 'standalone'` build copies tracing-discovered dotfiles into the standalone bundle. The decommissioned `apps/meddoc-pro` should not be retaining build artefacts at all (out-of-scope app per AGENT 01 brief), and certainly not ones with live keys.
4. Pre-pilot launch with this pattern means the first PHI-bearing visit hits a key any local actor or stale image-puller can use — invalidating any BAA position with Anthropic / OpenAI / Deepgram.

## Recommended fix
1. Treat all five secrets present in any of these files as **compromised**: rotate ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPGRAM_API_KEY, RESEND_API_KEY, AUTH_SECRET, DB_PASSWORD, MINIO_ROOT_PASSWORD, SCRIBE_SERVICE_TOKEN — the full set in `.env`.
2. Delete `.env.backup`, `.env.local` (root), `apps/meddoc-pro/.env`, `apps/meddoc-pro/.env.local`, and `apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env`. The decommissioned `apps/meddoc-pro` should not have a populated env file or a `.next/standalone` directory at all — wipe `apps/meddoc-pro/.next/` entirely.
3. Set `chmod 600 /opt/meddoc-pro/.env` and verify ownership is `claude:claude` (or restrict further to a dedicated service user). Document in `ROTATION_RUNBOOK.md` that the post-rotation file mode MUST be 600.
4. Tick the LAUNCH_CHECKLIST §6 boxes only after billing data has been pulled for the leaked-key window per the runbook's own §6 instructions.
5. Add `.env.backup` and `.env.local` to a pre-launch grep gate (CI step) — if either ever appears with non-placeholder values, fail the deploy.
