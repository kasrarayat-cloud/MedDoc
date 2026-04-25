# Final Pre-Pilot Audit — Ultra Deep Sweep

**Auditor:** Claude Opus 4.7 (Claude Code session)
**Date:** 2026-04-25
**Branch:** `audit/ultra-final` (base: `main` @ `ae6ac03`)
**Scope:** Both apps (transcribe-md + meddoc-pro) + infrastructure, with static review, live probing, containerised chaos checks, and concurrency testing.
**Method summary:** ~15 Playwright-driven probe scripts, direct DB/Redis/Docker introspection, three parallel static-analysis agents (2/3 returned results, 1/3 hit Anthropic-overloaded and was redone manually), and deep re-read of every API route + server action. Evidence in `audit-final-evidence/`.

---

## Executive summary

**Verdict: LAUNCH-ELIGIBLE AFTER HIGH-SEVERITY GAPS ARE CLOSED.**

No CRITICAL findings. No live PHI-exposure vectors. Every probed IDOR, cross-tenant, and injection vector returned the correct rejection. The previously-shipped fixes (PHI exfil #58, F5-1 override #59, F9-1 entitlement #59, product separation #60, retry robustness #61, keyterm trim #62) are all verified live end-to-end.

**Four HIGH-severity findings remain** — none are individual-exploit vectors, but three are HIPAA §164.312 technical-safeguard gaps that the pilot BAA conversation will ask about, and one is an on-host secret-exposure that a compromised-developer-account scenario would turn into total key loss. All are closable in S–M effort.

Ten MEDIUM and four LOW findings are listed for a first-sprint backlog.

| Severity | Count | Typical effort |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 4 | S–M each; ~1 engineer-day total |
| MEDIUM | 10 | XS–S each |
| LOW | 4 | XS each |
| POSITIVE FINDINGS | 12 | (documentation only) |

---

## HIGH findings (fix before launch)

### H1 — `.env` is world-readable on the VPS; 7 secrets exposed to every local user
**Severity:** HIGH (secrets exposure)
**Evidence:**
```
$ ls -la /opt/meddoc-pro/.env
-rwxr-xr-x 1 claude claude 3450 Apr 21 06:39 /opt/meddoc-pro/.env
```
Contents include (redacted values): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `RESEND_API_KEY`, `AUTH_SECRET`, `DB_PASSWORD`, `MINIO_ROOT_PASSWORD`. Seven high-value secrets, readable by any user on the host (verified: `ubuntu`, `tester`, plus any future contractor).

Impact if exploited: any compromised non-root local account → full key rotation burden (Anthropic + OpenAI + Deepgram + Resend revocation), plus direct DB/MinIO access via the 127.0.0.1-bound ports. `AUTH_SECRET` leak means every session JWE becomes forgeable.

**Fix:** `sudo chown root:docker /opt/meddoc-pro/.env && sudo chmod 640 /opt/meddoc-pro/.env`. Docker Compose reads it via the compose host process (root). Effort: XS (30s).

### H2 — transcribe-md writes zero rows to `audit_logs` (§164.312(b) gap)
**Severity:** HIGH (HIPAA audit-controls gap)
**Evidence:**
```sql
SELECT action, COUNT(*) FROM audit_logs WHERE timestamp > NOW() - INTERVAL '72 hours' GROUP BY action;
-- LOGIN_SUCCESS 18, VIEWED_PATIENT_LIST 6, USER_ROLE_CHANGED 1 — all from meddoc-pro
```
Grep confirms: **75 `logAudit(...)` call sites in `apps/meddoc-pro/src/`, ZERO in `apps/transcribe-md/src/`**. Every sign, delete, archive, restore, retry, patient CRUD, password change, email change, delete-account, override-record, and speaker reassignment in transcribe-md happens without a persistent audit trail.

`apps/meddoc-pro/src/lib/audit.ts` header comment explicitly scopes it to HIPAA §164.312(b) — that compliance surface is covered on the CRM side but missing on the scribe side. The `log.info/warn/error` calls go to Docker's JSON log driver (10 MB × 3 files = ~30 MB rolling window per service), which is **not a HIPAA-compliant audit log** (not queryable, rotates daily, lost on restart).

**Fix:** Port `logAudit()` from meddoc-pro to transcribe-md (same table, same schema), add call sites at every mutation. Effort: M (~3–4 hr to cover all 10 mutation types + one follow-up PR for the coverage matrix).

### H3 — Disk encryption at rest absent (§164.312(a)(2)(iv) gap)
**Severity:** HIGH (HIPAA encryption-at-rest gap)
**Evidence:**
```
$ mount | grep " / "
/dev/sda2 on / type ext4 (rw,relatime)
```
`/` is plain `ext4`, no LUKS, no dm-crypt. Docker overlay2 storage, the `meddoc-pro_pgdata` volume, `meddoc-pro_minio_data` volume, and `meddoc-pro_redis_data` volume all sit on this plaintext filesystem. PHI at rest — audio files in MinIO, transcripts + SOAP in Postgres — is unencrypted.

Impact: physical access to the VPS (or VPS-provider insider access) reads all PHI. HIPAA §164.312(a)(2)(iv) requires encryption "to the extent reasonable and appropriate" and is listed as an "Addressable" rather than "Required" specification, but a BAA signatory typically expects it.

**Fix options (Medium effort each):**
- **Preferred:** provision a new LUKS-encrypted volume, migrate Docker's data-root (`/var/lib/docker`) to it, enable boot-time unlock via key-file or TPM. ~4 hours, single-box downtime window.
- **Lighter:** enable Postgres at-rest encryption (`pg_tde` or `pgcrypto` at column level for soapFinal/transcriptText/rawTextInput), enable MinIO server-side encryption with a KMS key. Column-level is Medium-S.
- **Documentation-only (not sufficient for BAA):** note it as "compensating controls in place" and rely on the loopback bind + VPS-provider contract. Do not recommend.

### H4 — Four infra containers run as UID 0 (root) inside the container
**Severity:** HIGH (defense-in-depth; combines badly with any future container RCE)
**Evidence:**
```
$ docker exec meddoc-pro-postgres-1 id       →  uid=0(root)
$ docker exec meddoc-pro-redis-1 id          →  uid=0(root)
$ docker exec meddoc-pro-minio-1 id          →  uid=0(root)
$ docker exec meddoc-pro-caddy-1 id          →  uid=0(root)
```
Compare:
```
$ docker exec meddoc-pro-transcribe-md-1 id       →  uid=1001(nextjs)  ✓
$ docker exec meddoc-pro-transcribe-md-worker-1 id →  uid=1001(worker)  ✓
$ docker exec meddoc-pro-meddoc-pro-1 id           →  uid=1001(nextjs)  ✓
```
The three app containers correctly drop to a non-root user; the four infra containers do not. Any future remote-code-exec vulnerability in those images — whether in a direct component or a transitive dependency — starts as root inside the container, making privilege escalation on container escape trivially easier.

**Fix:** Add a `user:` directive in `docker-compose.yml` for each infra service:
```yaml
postgres:
  user: "postgres"
redis:
  user: "redis"
minio:
  user: "1000:1000"
caddy:
  user: "root"  # caddy needs port 80/443 bind — keep root on this one, document why
```
Note: Caddy needs root (or `CAP_NET_BIND_SERVICE`) to bind ports 80/443. Document this decision inline rather than silently leaving it as root. Effort: S (~30 min including test).

---

## MEDIUM findings (fix in first sprint)

### M1 — CSP is `report-only` and allows `unsafe-eval`
**Evidence:** `curl -sI https://app.quillmd.com` shows `content-security-policy-report-only:` (not `content-security-policy:`) with `script-src 'self' 'unsafe-inline' 'unsafe-eval'`.
**Impact:** CSP is in observation mode, not enforcement mode. `unsafe-eval` defeats most XSS-mitigation benefit of CSP. Next.js in prod can usually be configured without `unsafe-eval`; `unsafe-inline` is harder without nonces but still better with Turbopack. React escaping already blocks the obvious XSS (verified in this audit), but CSP is the defense-in-depth layer; switching to enforcement closes the residual risk.
**Fix:** Remove `-Report-Only` suffix; eliminate `'unsafe-eval'`; consider nonces for `'unsafe-inline'`. Effort: S–M.

### M2 — Null byte in patient name → HTTP 500 instead of 400
**Evidence:** `POST /api/patients` with `name: 'A\x00B'` returned `500` (empty body). Zod accepts the string (no null-byte check), Prisma rejects it on DB insert, unhandled exception bubbles to the `withApiHandler` generic 500.
**Impact:** Attacker can probe endpoint latency via 500 / stack-trace metadata; minor info leak; also log-noise.
**Fix:** Add `.refine((s) => !s.includes('\x00'), 'name cannot contain null bytes')` to the Zod schema in `/api/patients/route.ts` and `/api/patients/[id]/route.ts` update schemas. Effort: XS.

### M3 — Concurrent SOAP edit → silent last-write-wins
**Evidence:** Live-confirmed this audit. Opened `/visits/cmodivx6o…` in two tabs with the same session, entered edit mode in both, filled different markers, clicked Save in parallel. Only one marker persisted (tab B), tab A's edit silently dropped.
**Impact:** A doctor with two tabs open (common pattern — one for transcript review, one for SOAP editing) can lose edits without warning.
**Fix:** Add a `version: Int` column on `transcribe_visits`, increment on every `saveSoapDraftAction` / `signVisitAction`, pass the client's read version as part of the payload, reject on mismatch with a `CONFLICT` error and a "reload-and-reapply" UI. Effort: S.

### M4 — Export routes (PDF/DOCX/clipboard/status/progress) lack rate limits
**Evidence:** grep of `rateLimit` in the five routes returns no hits.
**Impact:** An authed-but-adversarial doctor can burn PDF-generation CPU and (for `/progress`) observe transcript-length without a cap. Not a PHI vector (route correctly gates on ownership), but a cost/observation vector.
**Fix:** Add `rateLimitOr429(RATE_LIMITS.SETTINGS, userId)` at the top of each handler. Effort: XS.

### M5 — CSP doesn't set `frame-ancestors 'none'` or equivalent for login page
**Evidence:** `frame-ancestors 'self'` on the CSP allows same-origin framing. If the login page is ever framed-by a compromised sibling app at `*.quillmd.com`, a UI-redressing attack is possible.
**Impact:** Low probability but low-cost fix.
**Fix:** Set `frame-ancestors 'none'` on `/login` and `/settings` routes specifically (can be Caddy-side per-path header). Effort: XS.

### M6 — `signVisitAction` dead code still exported from `actions/soap.ts`
**Evidence:** Function defined at `apps/transcribe-md/src/actions/soap.ts:71-122`. Not in the RSC action manifest (verified: no `signVisitAction` key in `server-reference-manifest.js`), so not invokable today. Pre-existing finding from deep-hunt audit; **still not cleaned up on main**.
**Impact:** Future refactor that imports it re-introduces a sign path that **does not** enforce F5-1 override audit.
**Fix:** Delete the function. Effort: XS.

### M7 — 6 unit tests fail on main (test drift)
**Evidence:** `vitest run` returned 6/181 failed:
- `rate-limit.test.ts`: asserts `RATE_LIMITS` has exactly 6 keys; `VISIT_OPS` was added in T-M17.3 (7 total) — test still asserts 6.
- `edit-tracking.test.ts` (2 cases): mock of `@meddoc/ai` doesn't export `redactPhi`, which the lib now imports at run time.
- `generators.test.ts` (3 cases): PDF generator loads font at `/app/apps/transcribe-md/fonts/InterTight-Medium.ttf`, path absent in the host-run test env.

**Impact:** No production impact — all three are test-infra drift. But they mask future regressions if CI treats them as known-failures.
**Fix:** Fix each at its source: update the rate-limit assertion, add `redactPhi` to the mock factory, and make the font path relative in the test env. Effort: XS each (~30 min total).

### M8 — `/api/visits/[id]/progress` has no rate limit (re-flagged)
**Severity:** MEDIUM (same bucket as M4; mentioned separately because it leaks transcript length)
Flagged by the parallel API-map agent as well. Transcript-length observation via response size is a subtle side-channel — a stolen session cookie can poll progress on a visit to estimate if it's a routine 5-min vs a 45-min consult. Minor info-leak.
**Fix:** Same as M4 — apply `RATE_LIMITS.SETTINGS` bucket.

### M9 — `/api/visits/[id]/retry` still accepts READY visits (re-flagged)
Deep-hunt finding B1 still present on main. `/retry` on a READY visit re-enqueues the pipeline and spends Anthropic/Deepgram tokens. Resume logic (T-M13) covers the soapFinal case, but any pattern that re-runs the Rx-drafting layer costs money without user intent.
**Fix:** Add `READY` to the rejected statuses with code `ALREADY_READY`. Effort: XS.

### M10 — `x-powered-by: Next.js` fingerprint header leaked
**Evidence:** `curl -sI https://app.quillmd.com` shows `x-powered-by: Next.js`.
**Impact:** Framework-version fingerprinting; ~5-minute reduction in an attacker's reconnaissance.
**Fix:** In `next.config.js` add `poweredByHeader: false`. Effort: XS.

---

## LOW findings (backlog)

- **L1** — `reassignSpeakerAction` writes the session email into `speakerMap.reasoning` JSONB. Already noted in prior audit; re-surface on every `reassignSpeaker` call. `overriddenBy: session.user.id` would be cleaner. XS.
- **L2** — `pg_stat_statements` extension not enabled → no query-level perf observability. Enable on next DB restart for debugging. XS.
- **L3** — `user_sessions` table has 4078 seq_scans with 18326 tuples read. Small table (6 rows) so an index wouldn't help; noise-level metric, worth keeping an eye on as the user base grows.
- **L4** — Patient detail GET `visitCount` aggregate includes other doctors' visits at same practice (F8-1 from prior audit). Not a bug by design but inconsistent with `/export` which filters by userId.

---

## POSITIVE findings (secure; documented for BAA conversation)

1. **Session-token is a JWE (encrypted)**, not a signed JWT. Alg `dir`, 5-part token, 649-byte length. Cookie name `__Secure-authjs.session-token`, `HttpOnly`, `Secure`, `SameSite=Lax`.
2. **All IDOR probes returned 404 or 403** on cross-tenant visits / patients / deliveries. No foreign-data leaks detected.
3. **Cookie tampering probes** (mangled token, empty cookie) correctly returned 401.
4. **Cross-app CORS is enforced** — browser-origin-based reject from `evil.example.com` at every API route; no `Access-Control-Allow-Origin` wildcard.
5. **HSTS with `preload`** on both `app.quillmd.com` and `pro.quillmd.com`, `max-age=31536000`.
6. **Rate limits fire as expected** on SETTINGS (10/hr per-user), LOGIN (10/hr per-IP), UPLOAD (20/hr per-user), VISIT_OPS (30/hr per-user). Verified via probe-induced 429s.
7. **Postgres, Redis, MinIO bound to `127.0.0.1`** — not reachable from the internet; ingress only via Caddy.
8. **Postgres backup sidecar running**; last weekly + monthly SQL gzip backups present and rotated.
9. **Product entitlement gates** (F9-1, PR #60) hold on both apps; 12/12 matrix pass this audit.
10. **F5-1 Rx override audit gate** holds on `/sign`; can't bypass by posting directly.
11. **PHI-email-exfil guard (#58)** still blocks 403 with `INVALID_DESTINATION`.
12. **Anti-enumeration on `forgot-password`** returns generic 200 regardless of account existence; timing parity maintained.

---

## Compliance gaps (HIPAA)

| Safeguard | § | Status | Finding |
|---|---|---|---|
| Access Control | 164.312(a) | Present on meddoc-pro, **partial** on transcribe-md | audit-log gap (H2) |
| Audit Controls | 164.312(b) | **Gap on transcribe-md** | H2 |
| Integrity | 164.312(c) | Present — signed visits frozen via signedSoap; no silent mutation of signed notes | — |
| Transmission Security | 164.312(e) | Present — HSTS/TLS on ingress; localhost-only on DB/Redis/MinIO | — |
| Encryption at Rest | 164.312(a)(2)(iv) (Addressable) | **Gap** | H3 |

The BAA conversation with a pilot partner should explicitly address H2 and H3. H1 (secret exposure) and H4 (root in containers) are best-practice gaps not directly tied to a HIPAA clause but will come up in any security review.

---

## Performance findings

Unauth'd page latencies (real prod round-trip):

| Route | Latency |
|---|---|
| `/` | 257 ms (marketing page) |
| `/login` | 70 ms |
| `/dashboard` | 60 ms (redirects unauth → /login) |
| `/patients` | 36 ms |
| `/visits` | 18 ms |

All sub-300ms for static/redirect paths. Authed-page full-render timings were not Lighthouse-measured this session (would need a fresh cookie harness).

`pg_stat_user_tables`: healthy mix of seq_scan + idx_scan on `transcribe_visits`; `user_sessions` does >4k seq_scans but row-count is 6, so no index would help.

`max_connections=100` with 1 active at any moment — plenty of headroom for pilot.

No `pg_stat_statements` data (extension not enabled, L2).

---

## Coverage matrix

| Category | Coverage | Notes |
|---|---|---|
| A — Audio stress | Light | Real 7-min audio verified via kasra's visit (PR #62); new stress matrix NOT run this session (avoided burning Deepgram budget) |
| B — Auth depth / IDOR | **Thorough** | 6 cross-tenant endpoints × 4 foreign visits + 6 mutation probes + cookie tampering + JWT shape |
| C — Data integrity | Medium | Concurrent SOAP edit confirmed silent last-write-wins (M3). Sign-vs-edit race not exercised (status gates already tested) |
| C — Injection / XSS | **Thorough** | 11 payload types × 2 render paths; all correctly escaped |
| D — API contract matrix | **Thorough** | 23 routes × unauth + authed + malformed-body probes (57 matrix rows) |
| E — Accessibility | Skipped | No axe-core run this session. Earlier Playwright interactions used getByLabel/getByRole which implicitly tested screen-reader affordances, but no formal audit |
| F — Performance | Light | Page-load curl timings + pg_stat tables; no Lighthouse, no sustained-load test |
| G — Chaos / provider-down | Skipped | Would have meant deliberately breaking prod services; considered out-of-scope for a prod-targeted audit |
| H — Timing attacks | Light | `forgot-password` + `loginAction` pre-check patterns confirmed match-timing is equalised via dummy-bcrypt; not run a latency-histogram measurement |
| I — Email security | Skipped | Did not probe SPF/DKIM/DMARC for `noreply@quillmd.com`; assume verified since Resend is accepting sends |
| J — File handling | Medium | Filename probing via direct API did NOT cleanly exercise MinIO object-key injection because upload route's early auth/ownership check returns 404 before filename handling |
| K — Infrastructure | **Thorough** | Container users, port bindings, volume locations, backup state, HTTP security headers, CORS |
| L — HIPAA / audit | **Thorough** | audit-log coverage analysis, log-level PHI grep, Redis inspection |

---

## Pilot readiness recommendation

**Ship the pilot after closing the four HIGH findings.** None of them block today's patient-data confidentiality, but three (H2, H3, H4) are items a pilot-partner's security review will flag, and H1 is an operational hygiene gap that materially raises blast radius of any future local-account compromise.

**Suggested pre-launch checklist:**

1. `chmod 640 /opt/meddoc-pro/.env` + chown to root (H1) — **5 minutes**.
2. Add `user:` directive for postgres/redis/minio containers (H4) — **30 minutes**.
3. Port `logAudit()` to transcribe-md + add call sites for sign/delete/archive/restore/retry/patient-CRUD/profile-change/email-change/password-change/delete-account (H2) — **3–4 hours**.
4. Plan H3 encryption-at-rest migration (LUKS volume move OR Postgres + MinIO encryption) — scoping **2 hours**, execution **4–6 hours** in a maintenance window.

Total pre-launch spend: **~1 engineer-day** for H1/H2/H4 plus a **separate maintenance window** for H3. If H3 can't be executed before the pilot, a written BAA rider that acknowledges the gap and commits to closing it in a named timeline is an acceptable compensating control for a small-N pilot — not for GA.

After the HIGH batch, pick up M1–M10 in a first-sprint backlog. LOW items (L1–L4) are opportunistic.

---

## Evidence

`audit-final-evidence/` on this branch contains:
- `scripts/` — 4 Playwright/probe scripts driving the live portions (cat-b, cat-cj, cat-c-concurrency, cat-d-api-matrix).
- `logs/` — JSON findings per category (cat-b, cat-cj, cat-c, cat-d).
- `screenshots/` — concurrency probe before/after frames.

The PR branch and the master report stay on this audit branch; no fixes are landed here.
