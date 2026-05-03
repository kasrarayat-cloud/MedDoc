# INF-01 — `.env.example` is wildly out of sync with reality

**Severity:** P2 (developer experience, not security)
**File:** `/opt/meddoc-pro/.env.example`

## What

`.env.example` defines **3 vars** (only the BACKBLAZE_* trio for
offsite backup). The actual `.env` on production has **27+ vars**
spanning every service, and `.env.production.example` (the canonical
deploy template) has **59 vars**.

A new contributor cloning the repo and running `cp .env.example .env`
would get a fully-broken local dev environment (no DATABASE_URL, no
AUTH_SECRET, no API keys for Anthropic/Deepgram/etc.).

## Why it matters

- Onboarding friction. Every new contributor wastes time figuring
  out which env vars to set, where to look, what's secret vs not.
- The `.env.production.example` exists but isn't discovered by
  default — the convention is `.env.example`.
- README likely references the wrong file (not verified).

## Proposed remediation

Replace `.env.example` with a copy of `.env.production.example`
that has all 59 vars listed with empty / placeholder values + a
header comment pointing dev contributors at the right secrets
to acquire.

```bash
cp .env.production.example .env.example
# then edit to ensure all values are blank / 'CHANGE_ME_*' /
# 'http://localhost:...' for dev defaults
```

This is mostly a copy + scrub-secrets-from-the-copy operation.

## Effort
- ~10 min (copy + sanitize)
- 0 production impact (host `.env` unchanged)

## Risk to fix
LOW. The file affects onboarding only.

## Status
Plan-only per audit rule (P2 stays plan-only). Could also be done
in the cleanup PR if Kasra approves bumping it from P2 → P3 — but
strictly the rule says no.
