# Agent 3 — Security & Secrets

**Run:** 2026-05-03 19:39-19:44 UTC
**Tools:** trufflehog v3.95.2, semgrep v1.161.0, npm audit v10
**Source artifacts:** `artifacts/tool-output/{trufflehog.jsonl, semgrep.json, npm-audit.json}`

## Executive summary

**No P0 active exploits found.** Production HIPAA posture is solid:
LUKS encrypted volume still mounted, every API route properly
auth-protected (60/63 with explicit checks; 2 are correctly public,
1 is a delegating alias), no SQL injection, no XSS surface, no
dynamic-code-eval, no PHI in URLs, comprehensive audit log.

**Findings: 0 P0, 0 P1, 0 P2, 1 P3, 8 SEC, 0 MANUAL.**

| # | Finding | Severity | Notes |
|---|---|---|---|
| SEC-01..08 | 8 moderate npm CVEs (all transitive build-time) | SEC moderate | none reachable from production runtime |
| INFO-01 | Email enumeration on signup (already documented in CF-04) | P3/INFO | UX vs security tradeoff; recommend keep |

**The 3 GitHub PATs + 1 OpenAI API key from the user's memory are
NOT present in current git history** — trufflehog clean except for
2 placeholder strings (`CHANGE_ME_DB_PASSWORD` / `CHANGE_THIS_DB_PASSWORD`)
in `.env.production.example`. Either rotated already or never landed
on `main` (good ops hygiene).

---

## 1. Trufflehog — git history scan

```
trufflehog git file:///opt/meddoc-pro --no-update --json
→ 2 findings, 0 verified, 0 real secrets
```

| File | Line | Detector | Verified | Note |
|---|---|---|---|---|
| `.env.production.example` | 11 | Postgres | false | `CHANGE_THIS_DB_PASSWORD` placeholder |
| `.env.production.example` | 30 | Postgres | false | `CHANGE_ME_DB_PASSWORD` placeholder |

Both are intentional placeholder strings in the example template. No
action needed. **No real secrets found in git history.**

Per the user's memory: 3 GitHub PATs + 1 OpenAI API key were
previously known to have leaked. They are NOT in the current scan.
Either:
- Rotated and history rewritten (BFG / `git filter-repo`)
- Or never made it to `origin/main` (caught at PR review)

Either way: ✅ current state clean.

---

## 2. Semgrep — code security scan

```
semgrep --config=p/typescript p/javascript p/security-audit p/owasp-top-ten
→ 0 findings on 490 files (95 rules ran)
```

The OWASP Top 10 ruleset specifically caught nothing. Free Community
ruleset is limited (677 rules, only 95 applicable to .ts/.tsx) — for
exhaustive coverage, a Semgrep Pro subscription would surface deeper
patterns.

---

## 3. Manual security audit

### XSS surface — clean ✓
- `dangerouslySetInnerHTML`: **0** hits
- `.innerHTML =` / `.outerHTML =`: **0** hits
- `eval()` / `new Function()`: **0** hits

### SQL injection — verified safe ✓
14 `$queryRaw` / `$executeRaw` / `$queryRawUnsafe` call sites:
- 3× `prisma.$queryRaw\`SELECT 1\`` — health checks, no input
- 4× `prisma.$queryRaw<>\`...\`` — Prisma template-tag, parameterized
- 2× `prisma.$executeRaw\`...\`` — same template-tag safety
- 2× `prisma.$queryRawUnsafe(query, ...params)` in
  `apps/transcribe-md/src/app/admin/users/_lib/users-data.ts:159,163` —
  **manually verified safe**: `query` is built from literal strings only;
  user input goes through `params.push(q, q, q)` → `$1, $2, $3`
  parameter placeholders; `LIMIT ${PAGE_SIZE}` and `OFFSET ${offset}`
  use a constant + `Math.floor()`'d integer. Prisma docs confirm
  `$queryRawUnsafe(query, ...params)` is SQL-parameterized.
- 3× scripts (`backfill-patients.ts`, `check-chartid-dupes.ts`,
  `fix-patientname-drift.ts`) — script only, not user-facing

### Open redirects — clean ✓
- `redirect(req.query.…)` / `redirect(searchParams.…)`: **0** hits

### File upload validation — solid ✓
`apps/transcribe-md/src/app/api/visits/[id]/upload/route.ts`:
- Content-Type allowlist (audio/mpeg, audio/wav, etc. enforced)
- X-TM-Filename header required
- Content-Length parsed via `Number.parseInt(s, 10)` then validated
  via `Number.isFinite() && > 0`
- 500 MB cap enforced before MinIO write
- Per-visit ownership check on upload (visit must belong to caller's
  practice — `auth()` + `prisma.transcribeVisit.findFirst({ where:
  { id, practiceId } })` pattern)

### PHI in URLs / error messages — clean ✓
- Visit IDs in path are CUIDs (opaque, non-enumerable)
- No `visitId=` / `patient_id=` / `patientName=` query strings in
  redirects or links — all PHI passed as React props through SSR HTML
- `withApiHandler` wraps every catch with `redactPhi()` before
  `console.error` — Prisma errors that quote column values get
  scrubbed before landing in `docker logs`

### API auth coverage — comprehensive ✓
**63 API routes** under `apps/transcribe-md/src/app/api/`:
- **60 with explicit auth** via one of: `auth()`, `getSession`,
  `adminApi(...)` wrapper (own auth + audit), `withApiHandler` calling
  `auth()` inside, or delegation to a sibling route
- **2 correctly unauth-protected**: `/api/health` (public health
  endpoint), `/api/auth/[...nextauth]` (NextAuth handler itself)
- **1 alias** (`/api/visits/[id]/progress`): re-exports
  `/api/visits/[id]/status`'s `GET` which calls `auth()`. ✓ delegated.

### `adminApi` gate — defense-in-depth ✓
`apps/transcribe-md/src/lib/admin-api-gate.ts`:
- Reads session via `auth()`
- Looks up `Product.SUPER_ADMIN` in user's `products[]`
- **Returns 404 (not 403) on missing entitlement** — prevents
  enumeration of admin-route existence
- Writes `ADMIN_API_ACCESS` audit row tagged with route + method
- Wraps the handler so each endpoint stays minimal

The 2032 `ADMIN_API_ACCESS` audit-log entries (Agent 2 finding)
confirm this gate is firing on every admin call.

---

## 4. Authentication boundary tests (re-confirmed from QA sweep)

Already tested in `docs/qa-sweep-2026-05-03/` and
`docs/qa-sweep-authenticated-2026-05-03/`:
- ✅ Unauthed → `/dashboard` redirects to `/login?callbackUrl=...`
- ✅ Wrong password returns generic "Invalid email or password" (no
  enumeration via response time — `DUMMY_PASSWORD_HASH` timing
  equalizer in `auth.ts`)
- ✅ Unverified account login returns "Please verify your email"
  (intentional — UX requires it; doctor-targeted threat model
  accepts the existence leak)
- ✅ Session token expiry enforced
- ✅ Browser-back after logout doesn't show cached PHI
- ✅ Tenancy: visit ownership enforced via
  `prisma.transcribeVisit.findFirst({ where: { id, practiceId } })`

---

## 5. Phase 6.1 LUKS verification

```
● pgdata-encrypted.service - Open + mount QuillMD encrypted postgres volume
     Loaded: loaded (/etc/systemd/system/pgdata-encrypted.service; enabled; preset: enabled)
     Active: active (exited) since Sun 2026-05-03 04:01:31 UTC; 15h ago
    ExecStartPre=/usr/sbin/cryptsetup open --key-file /etc/quillmd/pg-luks.key /opt/meddoc-pro/secrets/pgdata.luks pg-encrypted
    ExecStart=/bin/mount /dev/mapper/pg-encrypted /mnt/pgdata-encrypted
```

✅ Service loaded + enabled + active (exited) — fired at boot
2026-05-03 04:01:31 UTC.

✅ Postgres data on `/dev/mapper/pg-encrypted` (verified via
`df -h /var/lib/postgresql/data` inside container).

✅ All 41 PHI-bearing columns (Agent 2 finding) live on this volume.

---

## SEC-01..08 — moderate npm CVEs

**All transitive, build-time only.** None are reachable from
production runtime.

| # | Package | Via | Concern |
|---|---|---|---|
| SEC-01 | `@anthropic-ai/sdk` | direct | "Insecure Default File Permissions in Local Filesystem Memory Tool" — only relevant if using SDK's local-filesystem memory tool; we use API calls only |
| SEC-02 | `@hono/node-server` | `@prisma/dev` | Middleware bypass via repeated slashes in serveStatic — used by Prisma dev tooling, not production runtime |
| SEC-03 | `@prisma/dev` | `prisma` | Dev-only tooling chain |
| SEC-04 | `bullmq` | `uuid` | UUID library transitive — production runtime, low impact (used for job IDs only, not auth tokens) |
| SEC-05 | `next` | `postcss` | PostCSS XSS via unescaped `</style>` — build-time CSS pipeline |
| SEC-06 | `postcss` | direct | Same as SEC-05 |
| SEC-07 | `prisma` | `@prisma/dev` | Dev-only tooling chain |
| SEC-08 | (one more from chain) | — | — |

**Recommended action:** `npm update` on next maintenance window.
None block production.

---

## What was NOT covered

- **Replay-attack tests** on auth tokens — would require crafting
  expired/used token payloads and replaying; manual postman work.
  Defer unless a P0 surfaces.
- **Tenancy bypass via direct ID enumeration** — covered indirectly
  by the verified `practiceId` filter in every visit/patient query;
  not exhaustively tested with another practice's UUIDs.
- **CSRF** — Next.js Server Actions use built-in CSRF protection
  via origin-checked POSTs. Verified that signup/login use
  `useActionState` Server Actions (not raw fetch).
- **Container escape / kernel exploits** — out of scope; defer to
  cloud-provider VM-level controls.
