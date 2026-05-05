---
id: A02-P3-001
severity: P3
title: Stale NEXTAUTH_URL=http://5.231.107.93:3001 lingers in /opt/meddoc-pro/.env — hidden by docker-compose env precedence
domain: Auth & session security
files:
  - .env:24
  - docker-compose.yml:434
---

## Issue

`/opt/meddoc-pro/.env` line 24 carries:
```
NEXTAUTH_URL=http://5.231.107.93:3001
```

This is a holdover from MODE A (pre-T-M19, IP+plaintext). At runtime
it's invisible because the docker-compose `environment:` block on the
`transcribe-md` service overrides via:
```yaml
AUTH_URL: ${TRANSCRIBE_MD_AUTH_URL:-http://5.231.107.93:9020}
NEXTAUTH_URL: ${TRANSCRIBE_MD_AUTH_URL:-http://5.231.107.93:9020}
```
…and the host `.env` sets `TRANSCRIBE_MD_AUTH_URL=https://app.quillmd.com`,
so the live container's resolved env is correctly:
```
AUTH_URL=https://app.quillmd.com
NEXTAUTH_URL=https://app.quillmd.com
```
(verified via `docker exec meddoc-pro-transcribe-md-1 printenv`).

Cookie posture confirmed clean — production responses carry
`__Host-authjs.csrf-token; Secure; SameSite=Lax` and
`__Secure-authjs.callback-url; Secure; SameSite=Lax`, which are
the secure-flag prefixes only emitted when `useSecureCookies`
resolves to `true` in `@auth/core/src/lib/utils/cookie.ts:60`.

The risk is configuration drift: if a future ops task uses
`source .env && ...` outside docker-compose (a debug script, a
migration runner that pulls env from `.env`, a one-off
`docker run` without the compose file), the stale `NEXTAUTH_URL`
silently switches secure-cookie detection off, regresses
cookie attributes, and would not be caught by the existing
smoke harness which only checks via `https://app.quillmd.com`.

## Evidence

`/opt/meddoc-pro/.env:23-25`:
```
AUTH_USE_MOCK=false
NEXTAUTH_URL=http://5.231.107.93:3001
RESEND_API_KEY=re_...
```

`/opt/meddoc-pro/docker-compose.yml:434-435`:
```yaml
AUTH_URL: ${TRANSCRIBE_MD_AUTH_URL:-http://5.231.107.93:9020}
NEXTAUTH_URL: ${TRANSCRIBE_MD_AUTH_URL:-http://5.231.107.93:9020}
```

`@auth/core/src/lib/init.ts:109` is what would flip if the env
ever leaked through unchanged:
```ts
config.useSecureCookies ?? url.protocol === "https:"
```
Where `url` flows from `req.url` after `reqWithEnvURL(req)` in
`next-auth/src/lib/env.ts:7`, and `reqWithEnvURL` rewrites the
request origin to whatever `AUTH_URL` / `NEXTAUTH_URL` say. With
the plaintext-IP override, `url.protocol === "http:"` →
`useSecureCookies = false` → cookies emitted without `Secure` and
without `__Secure-` / `__Host-` prefixes.

## Risk

Low today (the docker-compose path is canonical and overrides),
but config drift in the runbook makes it a latent landmine. A
future "let me run a one-off migration via `node` outside the
compose stack" workflow could regress production cookie security
without anything else changing.

## Recommended fix

Remove the stale line:

```diff
- NEXTAUTH_URL=http://5.231.107.93:3001
+ # NEXTAUTH_URL is set per-service in docker-compose.yml from TRANSCRIBE_MD_AUTH_URL
+ # — do not also set it here, otherwise out-of-compose tooling would pick up the
+ # stale value and break secure-cookie detection.
```

Same review pass on `.env.backup` (which still contains the same
stale value) once it's chmod-fixed under finding A02-P0-002.
