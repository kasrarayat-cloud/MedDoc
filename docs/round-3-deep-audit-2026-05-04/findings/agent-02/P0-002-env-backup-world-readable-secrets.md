---
id: A02-P0-002
severity: P0
title: .env.backup and .env.local are world-readable on the VPS — leaks AUTH_SECRET, DB password, OpenAI/Anthropic/Deepgram keys to every local user
domain: Auth & session security
files:
  - .env.backup
  - .env.local
---

## Issue

`.env.backup` and `.env.local` on the production host carry the live
`AUTH_SECRET` plus every paid-API key (OpenAI, Anthropic, Deepgram,
Resend) and the postgres `DB_PASSWORD`, but their filesystem
permissions are `0755` — readable by every local UNIX user. The host
has at least four non-root accounts (`ubuntu`, `claude`, `tester`,
`cortex` per `/etc/passwd`), and any of them can `cat` these files
without elevation.

`.env` itself is `0640` (root-of-the-app group only), so the secrets
are protected on the canonical path; the leak is purely the two
backup/local copies.

## Evidence

```
$ ls -la /opt/meddoc-pro/.env*
-rw-r-----  ... .env                        # 640 — fine
-rwxr-xr-x  ... .env.backup                 # 755 — leak
-rwxr-xr-x  ... .env.local                  # 755 — leak
-rw-rw-r--  ... .env.example                # placeholder, no secrets
-rw-r-----  ... .env.phase-6.2.template     # 640
-rw-rw-r--  ... .env.production.example     # placeholder, no secrets
```

```
$ awk -F: '$3 >= 1000 && $3 < 60000 {print $1, $3}' /etc/passwd
ubuntu 1001
claude 1000
tester 1002
cortex 1003
```

`.env.backup` contents (key names listed; live values **deliberately omitted**
from this report — Trufflehog verified live on 2026-05-04):
```
AUTH_SECRET=<REDACTED-LIVE-base64-44>
OPENAI_API_KEY=<REDACTED-LIVE-MATCHES-LAUNCH_CHECKLIST.md-§6>
ANTHROPIC_API_KEY=<REDACTED-LIVE>
DEEPGRAM_API_KEY=<REDACTED-LIVE-40-hex>
DB_PASSWORD=<REDACTED-LIVE>
MINIO_ROOT_PASSWORD=<REDACTED-LIVE>
```

The `AUTH_SECRET` exposure is the highest-impact one: holding it lets
anyone with shell access on the VPS forge JWE-encrypted session
cookies for any user (the JWT payload includes `id`, `role`,
`practiceId`, `sessionId` per `packages/auth/src/index.ts:348`). The
`UserSession` row check (`packages/auth/src/user-session.ts:84`)
gates on the `sessionId` claim, but the attacker can simply mint a
JWT carrying a sessionId they observe from a real signed-in user
(or replay an admin's recent value).

## Risk

- **Account takeover at the platform-admin tier** by any local user
  who can read the AUTH_SECRET. The SUPER_ADMIN role bypasses every
  tenant scope (`packages/auth/src/index.ts:283`) and reaches every
  practice's PHI.
- **Direct DB access** via `DB_PASSWORD` to the postgres container
  (port 5432 is published to localhost, see `docker-compose.yml`).
- **Six-figure paid-API spend** by exfiltrating the OpenAI/Anthropic/
  Deepgram keys.

## Recommended fix

```
chmod 600 /opt/meddoc-pro/.env.backup
chmod 600 /opt/meddoc-pro/.env.local
chown root:root /opt/meddoc-pro/.env*   # or the service user, with strict mode
```

Followed by **rotating every secret in those files** since they have
been world-readable for an unknown duration. Specifically:

1. Rotate `AUTH_SECRET` (re-issue: `openssl rand -base64 32`); the
   shared `authConfig` already supports a multi-secret rolling
   migration via `AUTH_SECRET_1/2/3` per `@auth/core` env handling
   (`node_modules/@auth/core/src/lib/utils/env.ts:38`).
2. Rotate Postgres password, regenerate every API key at the
   provider console, update `.env`, recreate the affected containers.
3. Add a CI / pre-deploy assertion that `find /opt/meddoc-pro -name
   '.env*' -not -name '*.example' -not -perm 600` returns zero rows.
