# Agent 02 — Authentication & Session Security · Summary

## Severity counts
**P0: 2 · P1: 4 · P2: 3 · P3: 2 · Total: 11**

## Top 3 findings
1. **P0-001** — `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local` is *active in production* (`.env:76`, `docker-compose.yml:468`). The matcher itself withstands every adversarial input from the brief — uppercase normalizes correctly, lookalike-I and null-byte and double-`@` variants all fall through to `attacker.com`, and the denylist defends the gmail-misconfig footgun. The defect is purely that the bypass exists in prod at all: anyone signing up with `*@quillmd-test.local` skips the verification email and gets a fully-provisioned `DOCTOR` + `TRANSCRIBE_MD` account with no enforced trial expiry → unbounded API-cost farming + audit-log noise + brand risk.
2. **P0-002** — `.env.backup` and `.env.local` on the VPS are mode `0755`, readable by every local UNIX account (`ubuntu`, `tester`, `cortex` exist on the box). They carry the live `AUTH_SECRET`, `DB_PASSWORD`, OpenAI/Anthropic/Deepgram keys. AUTH_SECRET exposure permits forging JWE session cookies for any user including SUPER_ADMIN.
3. **P1-001** — `signupAction` (`auth.ts:325-340`) returns a UI-distinct "account exists, sign in instead" message; lone enumeration hole — login/forgot-password/resend-verification/change-email are all anti-enumerated correctly.

## Other findings
- **P1-002** Lockout-DoS via 5-attempt-lock + IP-only rate-limit (`nextauth.ts:138`)
- **P1-003** Rate-limit Map is in-memory per replica (resets every restart, KI-4)
- **P1-004** NextAuth pinned to `5.0.0-beta.31` for prod launch
- **P2-001** No HIBP / max-length / specials in password policy
- **P2-002** Verify-email + confirm-email use GET; corporate link-scanners eat single-use tokens
- **P2-003** No `trusted_proxies` declaration in Caddy
- **P3-001** Stale `NEXTAUTH_URL=http://5.231.107.93:3001` in `.env` (overridden by compose, but config-drift landmine)
- **P3-002** `isEmailDeliveryEnabled()` used inconsistently + auto-confirm log line includes full email

## Coverage
Read every `apps/transcribe-md/src/actions/auth*.ts`, `apps/transcribe-md/src/lib/{nextauth,auth,auth.config,auth-tokens,rate-limit,email-auto-confirm,email-enabled,constants,email}.ts`, `packages/auth/src/{index,user-session}.ts`, all six `/api/auth/*` route handlers, change-password + change-email + admin/users/[id]/reset-password, every login/signup/forgot/reset/check-email page + form, `Caddyfile` + `docker-compose.yml` + `.env*`, `next.config.ts`, root `layout.tsx`. Verified prod cookies via `curl /api/auth/csrf` (`__Host-` and `__Secure-` prefixes present, `Secure; SameSite=Lax`).

## Positives
1. Anti-enumeration via `DUMMY_PASSWORD_HASH` timing equalizers across login & nextauth authorize (`auth.ts:25, 170-175, 247-249`, `nextauth.ts:39, 130`).
2. Single-session enforcement with delete-then-create transaction semantics + Phase-6 lifecycle gates (`user-session.ts:57-71, 108-133`).
3. Textbook one-time AuthToken design — 32-byte CSPRNG raw, SHA-256 hash storage, atomic `updateMany WHERE usedAt IS NULL`, prior-token invalidation, generic null-on-failure (`auth-tokens.ts`).

## Cross-domain hooks
- **Agent 01/07** (secrets/infra): P0-002 + P2-003 (Caddy `trusted_proxies`)
- **Agent 03** (API): P1-003 Redis-backed rate-limit migration
- **Agent 05** (HIPAA): P0-001, P0-002 audit-poisoning + AUTH_SECRET-leak as breach-disclosure forcing functions
- **Agent 11** (email): P3-002, P2-002 GET-prefetch token consumption
- **Agent 12** (runbooks): P3-001 stale NEXTAUTH_URL cleanup + CI `find -not -perm 600` env-perm assertion
