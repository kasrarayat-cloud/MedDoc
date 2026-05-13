# Security Audit — transcribe-md
**Date:** 2026-05-13 15:23 UTC
**Auditor:** Claude (Opus 4.7 1M)
**Trigger:** Pilot doctor IT/compliance review gate. P0 ship tonight; P1/P2 documented for follow-up.
**Method:** Attack-surface inventory across 68 API routes + 8 server actions + auth/cookie config + Sentry + worker + Caddy/docker-compose, then probe across 10 threat categories via 4 parallel agent passes. Spot-check of every flagged finding before commitment.

---

## Section A — Executive Summary

| Severity | Count | Disposition |
|---|---|---|
| **P0** (exploitable; ship now) | **1** | Worker error → DLQ persists unscrubbed PHI |
| **P1** (real risk; queue follow-up) | **11** | Documented in §C; not blocking pilot pending the P0 fix |
| **P2** (hardening; document only) | **9** | Documented; review at the next milestone |

**Pilot-readiness verdict: YELLOW → GREEN after P0 ships.**

The fundamentals are intact:
- 59/68 API routes auth-gated (the 9 unauth routes are 6 auth-bootstrap endpoints, 1 status alias, 1 health probe, 1 client-error sink — verified legitimate).
- 100% server-action input validation via Zod; `practiceId` always sourced from session, never client.
- DB-level `REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM meddoc` enforced (migration `20260505010210_round_3_pr_c_revoke_audit_mutation`) — audit-log tampering blocked at PostgreSQL ACL.
- Login rate-limited (10/h IP), bcrypt timing-equalized (DUMMY_PASSWORD_HASH on every branch), account lockout after 5 fails / 15 min.
- MFA secret never returned post-enrollment; recovery codes SHA-256-hashed at rest; `/api/mfa/disable` requires password + (TOTP OR recovery).
- Password reset: opaque token, 1h TTL, single-use, generic response; ALL sessions revoked on success.
- TruffleHog `--only-verified` runs diff-scan on every PR + main push; HSTS `max-age=31536000; includeSubDomains; preload` enforced; HTTP→HTTPS via Caddy; CSP enforced (no longer report-only); Postgres/Redis/MinIO bound to 127.0.0.1; MinIO bucket private.
- No `dangerouslySetInnerHTML` anywhere in `apps/transcribe-md/src`. SOAP rendered through React text nodes (auto-escaped).
- No raw-string SQL injection paths; every `$queryRaw` uses tagged-template-literal syntax; two `$queryRawUnsafe` calls in `users-data.ts:159,163` use positional `$N` parameters with whitelisted constants — safe.

The P0 finding is a PHI-in-DLQ-storage path that surfaces when the worker fails its retry budget on a real visit. The fix is a 2-line `redactPhi()` wrap. PR shipping in §D.

---

## Section B — Attack Surface Inventory

### API routes (68 total)

| Category | Count | Auth posture |
|---|---|---|
| `/api/admin/*` (SUPER_ADMIN only) | 27 | All wrapped by `adminApi()` helper — 404-on-not-admin, audit-row on every access, 12h session-freshness check |
| `/api/auth/*` (auth bootstrap) | 7 | 6 legitimately unauth (signup, signin, password-reset, email-verify, forgot-password, NextAuth catch-all); 1 (`reset-password` POST) gated by token |
| `/api/mfa/*` | 3 | All require an authenticated session via `auth()` |
| `/api/settings/*` | 4 | All session-gated |
| `/api/patients/*` | 4 | Session + practice-scoped on every handler |
| `/api/visits/[id]/*` | 19 | Session + visit-owner-check (`visit.userId === userId` → 404 on mismatch) on every handler |
| `/api/health`, `/api/client-errors` | 2 | Public by design (health probe; client-side error sink) |

### Server actions (8 files)

All 8 wrapped in `'use server'`. All input validated via Zod schemas. `practiceId` always sourced from `session.user.practiceId`, never trusted from client. CSRF mitigated by Next 16 server-action implicit origin check.

### Public-facing pages

Zero public pages with PHI access. Public surface: `/`, `/signin`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email`, `/privacy`, `/terms`, `/hipaa`, `/security`, `/contact`. All others gated by `requireSession()` or 404-on-not-admin layout (admin section).

### File upload endpoints

- `/api/visits/[id]/upload` — 100 MB cap, MIME allowlist, magic-byte sniffing, filename sanitization
- `/api/visits/[id]/dictation/upload` — 100 MB cap, MIME allowlist, **but NO magic-byte sniffing** (P1-D below)

### Multi-tenant boundaries

`TranscribeMdPatient` rows scope to `practiceId`. Every patient handler does `patient.practiceId !== session.user.practiceId → 404`. `TranscribeVisit` rows scope to `userId` (solo-product). The cross-practice scope rule is documented in `/api/patients/[id]/export/route.ts:78-94`: the export query filters `userId: userId` even for shared-practice patients — only the caller's own visits appear. Verified.

### External secrets surface

- `.env.production.example`: all placeholders (`CHANGE_ME_*`, `REPLACE_ME`)
- `.env.example`: dev placeholders only
- Hardcoded keys in source: none (verified `grep -rE "sk-ant-|sk-proj-|nv-api-|ghp_|AKIA*"` clean outside `sk-test-fixture` in a unit test)
- AUTH_SECRET: hard-fails at container start in production if unset (gated on `NEXT_PHASE !== 'phase-production-build'`)
- GitHub Actions secrets: every workflow uses `pull_request` (not `pull_request_target`); no fork-secret exposure

---

## Section C — Findings per Threat Category

### Authentication & Session Management

- **P1-A — Reset-password emits no `PASSWORD_CHANGED` audit row.**
  - **File:** `apps/transcribe-md/src/app/api/auth/reset-password/route.ts:91-110`
  - **Risk:** HIPAA §164.312(b) requires logging credential-material changes regardless of trigger. `change-password` emits the row (line 132 of that file); `reset-password` does not. Forensics around stolen-account recovery is exactly the case the audit is for.
  - **Fix:** add `logAudit({ action: 'PASSWORD_CHANGED', userId: consumed.userId, metadata: { via: 'reset_token' } })` after the transaction.
  - **PoC:** `request reset → click email link → set new password → SELECT * FROM audit_logs WHERE action='PASSWORD_CHANGED' AND "userId"=<id>` returns 0 rows.

- **P1-H — Cookie hardening dropped when `AUTH_COOKIE_DOMAIN` unset.**
  - **File:** `packages/auth/src/index.ts:121-139` + `.env:74`
  - **Risk:** The entire `cookies.sessionToken.options` block is gated on `cookieDomain` being truthy. In production today `AUTH_COOKIE_DOMAIN=` (empty), so the explicit `httpOnly: true`, `sameSite: 'lax'`, `secure: ...` flags are skipped and the app inherits NextAuth defaults. Auth.js v5 picks sensible defaults in production but a future `NODE_ENV=development` flip with `AUTH_COOKIE_DOMAIN` still empty would silently drop the `__Secure-` prefix path.
  - **Fix:** always emit the options block (`httpOnly: true`, `sameSite: 'lax'`, `secure: NODE_ENV==='production'`, `path: '/'`); conditionally add `domain` only when `cookieDomain` is set.

- **P1-J — `verify-enrollment` doesn't rotate existing JWTs after MFA enable.**
  - **File:** `apps/transcribe-md/src/app/api/mfa/verify-enrollment/route.ts:97-113`
  - **Risk:** Other open tabs/devices keep their pre-MFA session. Best practice on factor enrollment is to revoke siblings (mirror `reset-password`'s `userSession.deleteMany`). Undermines the assumption that "MFA-enabled" sessions all went through an MFA challenge.
  - **Fix:** after flipping `mfaEnabled=true`, run `prisma.userSession.deleteMany({ where: { userId, NOT: { sessionId: currentSession.sessionId } } })`.

- **P1-K — GET-mutates on `verify-email` + `confirm-email`.**
  - **File:** `apps/transcribe-md/src/app/api/auth/verify-email/route.ts:43` + `apps/transcribe-md/src/app/api/auth/confirm-email/route.ts:51`
  - **Risk:** GET writes `users.emailVerified = now()` (verify-email) and `users.email = newAddress` (confirm-email). Acknowledged in the code as deliberate so the email link is clickable. Mitigated by the high-entropy, single-use, time-limited token in the query string. Residual risk: a Referer-leaking malicious page could exfiltrate the token if the user clicks the link while logged into something else.
  - **Fix:** keep the link-clickable GET but bounce through an HTML interstitial that submits POST. Two-line redirect change.

### Authorization (IDOR + Privilege Escalation)

- **P1-E — Four admin-lifecycle routes missing self-action guard.**
  - **Files:** `force-logout/route.ts:19`, `reset-password/route.ts:25`, `unsuspend/route.ts:18`, `grant-admin/route.ts:22`
  - **Risk:** Sibling routes (`revoke-admin`, `suspend`, `soft-delete`) have a 3-line `if (id === ctx.session.user.id) return 400` guard. These four don't. **Real risk**: a single-SUPER_ADMIN tenant fat-fingers `force-logout` on their own id, gets logged out, no other SUPER_ADMIN to unlock — DB-level intervention required.
  - **Fix:** copy the 3-line guard from `revoke-admin/route.ts:30-32` into the four routes. ~12 LOC, single PR.
  - **PoC:** `curl -X POST $HOST/api/admin/users/$MY_ID/force-logout` → 200 OK, next admin call returns 404.

### CSRF Protection

Clean for server actions (Next 16 implicit origin check). One residual:

- **P2 — sameSite=lax + no Origin check on `/api/**`.**
  - **Files:** `packages/auth/src/index.ts:131` + `apps/transcribe-md/src/lib/api-error.ts`
  - **Risk:** Top-level cross-site POST (`<form method=POST action="/api/...">`) is permitted by `sameSite: 'lax'`. NextAuth v5 server actions have implicit Origin check; plain `/api/**` route handlers do not. Defense-in-depth gap, not exploitable today (no GET-equivalent of mutating endpoints; SOP blocks cross-origin XHR).
  - **Fix:** add Origin/Referer check inside `withApiHandler` that 403s mismatched hosts.

### Input Validation

- **P1-D — Dictation upload missing magic-byte sniff.**
  - **File:** `apps/transcribe-md/src/app/api/visits/[id]/dictation/upload/route.ts:112-120`
  - **Risk:** The sibling bulk-upload route has `sniffAudioMagicBytes` + `magicBytesMatchClaimedMime` (added in Round 3 PR-J). Dictation route was not updated and trusts the client's `Content-Type`. **PoC:** send a `.exe` with `Content-Type: audio/webm` — bytes land in MinIO, Deepgram fails downstream, worker pulls attacker-controlled bytes (not RCE, but byte exfiltration to MinIO + processing pipeline of arbitrary content).
  - **Fix:** lift the buffer-then-sniff block from `upload/route.ts` into `dictation/upload/route.ts`. Object key is server-built (line 131) so no traversal risk.

- **P3 — Path-param IDs unvalidated as CUIDs.** Routes like `/api/visits/[id]` accept any string. `prisma.findUnique({where:{id}})` returns null on any string and the owner check returns 404, so not exploitable. Hardening only: add `z.string().cuid()` upfront for cleaner 400s.

### PII / PHI Leakage

**P0-A — DLQ persists unscrubbed `err.message` indefinitely.**
- **File:** `apps/transcribe-md/src/worker.ts:1395-1400`
- **Risk:** Worker `on('failed')` handler enqueues to DLQ with `lastError: err instanceof Error ? err.message : String(err)`. **No `redactPhi()` wrap.** DLQ entries are durable, reviewed via `/admin/queues`. Prisma errors and Anthropic 400 bodies routinely quote prompt fragments — a worker fault on a `soapFinal` write leaves the patient's note text in DLQ storage. Worker.ts already uses `redactPhi` in 5 other places (lines 954, 1021, 1041, 1050, 1423) — this site is an inconsistency, not a missing-helper.
- **Fix:** wrap in `redactPhi()` symmetric to the file's other err.message sites. Two lines.
- **PoC:** seed a Prisma write that fails after attempt 3 (e.g., 100KB+ string into a varchar column); the DLQ payload's `lastError` will contain the column value (PHI).
- **Severity rationale:** durable storage of PHI in a non-PHI-classified table is a §164.502 minimum-necessary violation in HIPAA terms. Even if eventually purged, retention beyond purpose is a documented gap.

P1 findings on PHI scrub posture (cheap to bundle with the P0 fix in the same PR):

- **P1-F-1 — Worker `on('failed')` stdout (1373-1376):** logs raw `err`, including stack. Anthropic SDK / Prisma stacks can include prompt fragments.
- **P1-F-2 — DLQ-enqueue-catch stdout (1402-1405):** logs raw `dlqErr`. Lower likelihood (Redis errors don't carry PHI) but inconsistent.
- **P1-F-3 — em-judge prewarm error (787-790):** raw `err` to stdout; the judge prompt embeds `soapFinalForFanout` (SOAP body), so a 400 echoes prompt fragments.
- **P1-F-4 — cleanup-worker `failed` (1209-1213):** raw `err` to stdout; cleanup ops don't typically carry PHI but inconsistent.
- **P1-F-5 — heartbeat write error (1331-1336):** raw `err` to stdout; fs errors low PHI but inconsistent.
- **P1-G — `/api/client-errors` route (`message`/`url` unredacted):** stack IS redacted (line 86) but `message`, `digest`, and `url` are logged raw. The file's header calls this a "design choice" / "fix at source" — but Next.js render errors stringify props (PHI risk).
- **P1-B — Sentry `beforeSend` doesn't scrub `request.data` / `query_string` / `contexts` / `user.email`.** Sentry Next.js integration auto-attaches request data on errors. A failed `POST /api/visits/[id]/text` would include the dictated text in `event.request.data`.
- **P1-C — `GET /api/patients?search=<name>` puts patient names in URL** → Caddy access logs (unscrubbed), browser history, Referer header on outbound clicks, Sentry request URL. Auth-gated, but URL surface is well outside the redactPhi posture. **Fix:** convert to POST with body, or strip access-log query strings at the Caddy layer.

P2 PHI/audit-adjacent (document only):

- **P2 — `ai_calls.errorDetails` persists model output on SCHEMA_FAIL / JSON_PARSE_FAIL.** Intentional per the design trail (T-M17.1); flag for the audit-log retention policy ledger — these rows should age out on the same calendar as `TranscribeVisit`.

### Secrets Management

- **P2 — Misleading comment in `.env.production.example:38`.** Comment "If unset, the code falls back to a literal dev string — treat as CRITICAL" reads like prod will silently sign with a dev key. The actual code (`packages/auth/src/index.ts:106-115`) hard-fails in production via thrown Error. Rewrite the comment.

Otherwise clean.

### Rate Limiting Coverage

PR #238 (today) refreshed the catalog. Patient CRUD, visit ops, login, signup, signup-email-verification, settings all covered with clinical-reality multi-window thresholds. Two narrow gaps:

- **P2 — `force-logout` admin route has no rate limit + no required `reason` field.** An admin-account compromise lets an attacker rapidly log every user out before their token can be revoked. Add `RATE_LIMITS.ADMIN_OPS` + required `reason` field on POST body. Same hardening already present on `suspend/route.ts`.
- **P2 — `/api/patients/[id]/export` still uses `SETTINGS` (10/h).** A clinician bulk-exporting 11+ patients would hit it. Add `PATIENT_EXPORT` preset OR raise the bucket.

### HTTPS / Transport

- **P1-I — Ports 9010/9020 published on `0.0.0.0` with no active listener.**
  - **File:** `docker-compose.yml:276,278` + `Caddyfile` MODE A blocks commented
  - **Risk:** `docker-compose.yml` publishes `"9010:9010"` and `"9020:9020"` (no `127.0.0.1:` prefix). The Caddyfile MODE A blocks for these ports are commented out, so today external TCP SYN gets `Connection reset`. **But**: if anyone re-uncomments MODE A (the file invites it as rollback), the app instantly serves over plaintext HTTP on those ports — bypassing HSTS for first-time visitors and undoing the MODE B `Strict-Transport-Security` posture.
  - **Fix:** prefix the publishes with `127.0.0.1:` so they're loopback-only, OR remove them outright if they have no live route.

- **P2 — CSP allows `'unsafe-inline'` + `'unsafe-eval'`.** CSP is enforced (not report-only) but `script-src` includes both unsafe values — required by Next 16 + Tailwind historically. Modern Next supports nonces. Track migration to nonce-based CSP and drop the two unsafe values.

### MCP / External integrations

No third-party callbacks present. No webhook surfaces. Clean.

### Audit-Log Integrity (HIPAA §164.312(b))

DB-level `REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM meddoc` enforced via migration `20260505010210_round_3_pr_c_revoke_audit_mutation`. No application code paths mutate the table. Coverage spot-check: `VIEWED_PATIENT_LIST`, `VISIT_DELETED`, `ACCOUNT_DELETED`, `PASSWORD_CHANGED` (change-password only — see P1-A), `MFA_*`, `VIEWED_VISIT` all present. The PR #236 worker-context `auth()` swallow is intact (logAudit's two-pronged fix).

P2 hardening idea: audit.ts:196-200 swallows `auth()` failure to `null`. Combined with the worker path passing `null` userId, an attacker who finds a way to invoke a privileged action via a non-session-bearing surface produces a sentinel-practiceId row with `userId=null`. Add a structured warning when both session AND `input.userId` are absent so the case is detectable in log review.

### IDOR Probe — Clean

All visit handlers verify `visit.userId === userId` (404 on mismatch) after `findUnique({where:{id}})`. Patient routes gate on `patient.practiceId !== session.user.practiceId` → 404. Admin routes gate on `Product.SUPER_ADMIN` in user products[] (re-checked from DB, not from JWT, so stale-JWT-after-revocation is blocked). MinIO bucket is private; no presigned URLs anywhere; all audio reads route through `/dictation/audio` and `/api/visits/[id]/upload` GET path with full ownership check. **One P2 hardening** noted: MinIO keys include a 13-digit `Date.now()` timestamp — guessable but harmless today because the bucket is private. Add 8 hex bytes of `crypto.randomBytes` to the key for future-proofing.

---

## Section D — Pilot-Readiness Verdict

**YELLOW → GREEN after P0 ships.** The fundamentals (auth-gating, multi-tenant isolation, audit-log integrity, transport security, secrets management, input validation, rate limiting) are intact. The one P0 finding is a 2-line redactPhi wrap that has been a known pattern in the file for 5 prior sites — the new line just inherits the same fix.

P1 findings should be triaged into a follow-up sprint; none of them are pilot-blocking by themselves, but the P1-E admin-self-action quartet is the next-most-load-bearing one and warrants a quick follow-up PR.

### Recommended PR sequence

1. **TONIGHT (P0):** `fix(worker): scrub PHI from DLQ + error-handler stdout` — single PR. Wraps line 1395 (DLQ `lastError`) + 5 console.error sites in `worker.ts` in `redactPhi()`. ~10 LOC across 1 file. **Ships in §3 below.**
2. **Next session (P1 bundle 1):** admin-self-action guards on 4 routes. ~12 LOC, single PR.
3. **Next session (P1 bundle 2):** reset-password audit row + verify-enrollment session revocation + cookie config always-emit.
4. **Next session (P1 bundle 3):** Sentry `beforeSend` request-data scrub + client-errors message/url scrub + GET `/api/patients?search` → POST.
5. **Next session (P1 bundle 4):** dictation upload magic-byte sniff + GET-mutates email link interstitial + docker-compose port loopback prefix.
6. **Next milestone (P2 bundle):** sameSite check refinement, CSP nonce migration, MinIO key randomness, force-logout rate-limit, ai_calls retention.

### Findings ledger

| ID | Severity | File | One-line description |
|---|---|---|---|
| P0-A | P0 | worker.ts:1395 | DLQ persists unscrubbed err.message → PHI durable in DLQ |
| P1-A | P1 | reset-password/route.ts:91-110 | No `PASSWORD_CHANGED` audit row |
| P1-B | P1 | sentry.server.config.ts:32 | beforeSend doesn't scrub request.data |
| P1-C | P1 | /api/patients?search=<name> | Patient names in GET URL → access logs |
| P1-D | P1 | dictation/upload/route.ts:112 | Missing magic-byte sniff |
| P1-E | P1 | force-logout + 3 sibling admin routes | Missing self-action guard |
| P1-F | P1 | worker.ts:1373/1402/1209/1331/787 | Raw err to stdout bypasses redactPhi |
| P1-G | P1 | client-errors/route.ts | message/url unredacted |
| P1-H | P1 | packages/auth/src/index.ts:121 | Cookie hardening gated on AUTH_COOKIE_DOMAIN |
| P1-I | P1 | docker-compose.yml:276,278 | 0.0.0.0 publish without listener (re-uncomment foot-gun) |
| P1-J | P1 | verify-enrollment/route.ts:97 | No JWT rotation on MFA enable |
| P1-K | P1 | verify-email + confirm-email GET | GET-mutates (token-mitigated; harden to POST interstitial) |
| P2-1 | P2 | minio.ts:204 | Audio object keys partially guessable |
| P2-2 | P2 | force-logout/route.ts | No rate limit + no reason field |
| P2-3 | P2 | api-error.ts | No Origin/Referer check on /api/** |
| P2-4 | P2 | sensitive forms | No anti-double-submit idempotency key |
| P2-5 | P2 | ai_calls.errorDetails | Persists model output on SCHEMA_FAIL |
| P2-6 | P2 | .env.production.example:38 | Misleading comment |
| P2-7 | P2 | Caddyfile CSP | unsafe-inline + unsafe-eval |
| P2-8 | P2 | audit.ts:196 | Silent fall-through to null userId |
| P2-9 | P2 | /api/patients/[id]/export | Still on SETTINGS (10/h) |
| P3 | P3 | Path-param IDs | Unvalidated as CUIDs |

**Total: 1 P0 / 11 P1 / 9 P2 / 1 P3.**
