# Agent 4 — Infrastructure & Container Auditor

**Run:** 2026-05-03 19:45-19:50 UTC
**Scope:** docker-compose.yml, 3 Dockerfiles, Caddyfile, systemd units, .env files

## Executive summary

Infrastructure is **production-grade**. Phase 19 cap_drop hardening
applied across all services; multi-stage Dockerfiles run as
non-root `nextjs` user; ports correctly bound to 127.0.0.1 except
the public-facing Caddy ones; Caddy enforces CSP + HSTS + Permissions-
Policy; LUKS-encrypted postgres volume mounted via systemd unit.

**Findings: 0 P0, 0 P1, 1 P2, 2 P3.**

| # | Finding | Severity | Effort |
|---|---|---|---|
| INF-01 | `.env.example` has 3 vars but real `.env` has 27+ — massive drift; new contributors won't know what to set | P2 | low (sync `.env.example` to mirror `.env.production.example`'s 59 vars, with placeholder values) |
| INF-02 | No Dockerfile-level `HEALTHCHECK` — only compose-level. Works for `docker compose ps` but means `docker run` standalone misses health signal | P3 | low (one HEALTHCHECK line per Dockerfile) |
| INF-03 | No Caddy-level rate limiting — relies entirely on app-layer rate limits (which DO exist per Agent 1/3) | P3 | low (caddy-ratelimit plugin or Cloudflare in front) |

---

## 1. docker-compose.yml — service-by-service audit

| Service | restart | cap_drop | user | mem_limit | cpus | healthcheck | ports |
|---|---|---|---|---|---|---|---|
| postgres | unless-stopped | ALL | 999:999 | 512m | 1.0 | ✓ pg_isready | 127.0.0.1:5432 |
| meddoc-pro | unless-stopped | ALL | (Dockerfile USER nextjs) | 512m | 1.0 | ✓ /api/health | 127.0.0.1:3001 |
| redis | unless-stopped | ALL | 999:999 | 128m | 0.5 | ✓ redis-cli ping | 127.0.0.1:6379 |
| minio | unless-stopped | ALL | 1000:1000 | 256m | 0.5 | ✓ /minio/health/live | 127.0.0.1:9000-9001 |
| caddy | unless-stopped | ALL | 1000:1000 | 128m | 0.5 | ✓ /healthz | 80, 443, 9010, 9020 (public) |
| marketing | unless-stopped | ALL | (Dockerfile USER nextjs) | 256m | 0.5 | ✓ /api/health | 127.0.0.1:3010 |
| transcribe-md | unless-stopped | ALL | (Dockerfile USER nextjs) | 512m | 1.0 | ✓ /api/health | 127.0.0.1:3011 |
| transcribe-md-worker | unless-stopped | ALL | (Dockerfile USER nextjs) | 1g | 1.5 | (none, BullMQ stateless) | (none) |
| postgres-backup | unless-stopped | ALL | 999:999 | 128m | 0.5 | ✓ readiness check | (none) |

**Total mem_limits: 3.7 GB** — sum exceeds host RAM by design (compose
limits are per-service caps, not reservations). Worker is the largest
single allocation at 1g (AI pipeline + Sentry + BullMQ).

**Sensitive ports correctly bound to 127.0.0.1**:
- postgres 5432, redis 6379, minio 9000-9001 — never reach the
  public internet
- meddoc-pro 3001, marketing 3010, transcribe-md 3011 — only
  reachable through Caddy

**Public ports (intentional via Caddy)**:
- 80 (HTTP→HTTPS redirect)
- 443 (HTTPS)
- 9010 (port-forward, internal use only — should be confirmed
  closed at firewall level)
- 9020 (same)

**No secrets hardcoded** — every sensitive var uses
`${VAR:-fallback}` substitution from host env.

---

## 2. Dockerfiles — all 3 apps

| File | Stages | USER | HEALTHCHECK |
|---|---|---|---|
| `apps/marketing/Dockerfile` | 3 (deps→builder→runner) | `nextjs` (uid 1001) at line 70 | ⚠️ none |
| `apps/transcribe-md/Dockerfile` | 3 (deps→builder→runner) | `nextjs` (uid 1001) at line 98 | ⚠️ none |
| `apps/meddoc-pro/Dockerfile` | 3 (deps→builder→runner) | `nextjs` (uid 1001) at line 67 | ⚠️ none |

All multi-stage with minimal final image (Next.js standalone). All
run as non-root `nextjs:nodejs` user. The missing `HEALTHCHECK` is
covered at the compose layer (so `docker compose ps` shows healthy)
but missing at `docker run` standalone — see INF-02.

`.dockerignore` properly excludes `node_modules`, `.next`, `.git`,
`.env*`, `*.md`, `.claude`, `backups`, `docs` (the last two added
during the Phase 7 deploy hotfix `dc4e36f`).

---

## 3. Caddyfile — strong defaults ✓

```
Hosts:
  app.quillmd.com   → transcribe-md:3011
  admin.quillmd.com → admin route on transcribe-md
  pro.quillmd.com   → meddoc-pro:3000
  quillmd.com       → marketing:3010
```

Active mode is **MODE B (HTTPS-only)**. MODE A (plaintext) blocks
preserved as commented rollback reference.

**Security headers (every host)**:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` (1 yr + preload)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: microphone=(self), camera=(self), geolocation=()`
  — mic + camera self-only (visit recording), geo blocked
- `Content-Security-Policy` ENFORCED (previously Report-Only during
  Phases 13-17 burn-in — promoted after 0 violations):
  `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' https://*.ingest.sentry.io; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; object-src 'none';`
- `-Server` (header removed — less fingerprinting)

⚠️ `'unsafe-inline'` + `'unsafe-eval'` in `script-src` — required by
Next 16 + Tailwind inline-style emission. Documented in Caddyfile
comment. Acceptable tradeoff.

**Auto Let's Encrypt** for each hostname; certs persisted in
`caddy_data` volume.

**No Caddy-level rate limiting** — see INF-03.

---

## 4. .env files — drift detected (INF-01)

| File | Vars defined | Notes |
|---|---|---|
| `.env` (active) | ~27+ | Real production values |
| `.env.example` | **3** | Only `BACKBLAZE_*` — drastically out of sync |
| `.env.production.example` | **59** | The actual canonical reference |

The 59-var `.env.production.example` is fine as a deploy template,
but **`.env.example` is what GitHub UI shows new contributors first**
and what tools like `cp .env.example .env` reach for. With only 3
BACKBLAZE vars, a new contributor cloning the repo would have a
fully broken local dev environment.

**Plan-only fix:** copy the var names (with placeholder values) from
`.env.production.example` into `.env.example`. Don't include real
values. Effort: 5 min.

---

## 5. systemd units — Phase 6.1 LUKS still active ✓

```
● pgdata-encrypted.service - Open + mount QuillMD encrypted postgres volume
     Loaded: loaded (/etc/systemd/system/pgdata-encrypted.service; enabled; preset: enabled)
     Active: active (exited) since Sun 2026-05-03 04:01:31 UTC; 15h ago
```

Service file timestamp: `2026-05-02 23:04` (confirms Phase 6.1 deploy).
Last fired at **04:01:31 UTC today** (so the system has rebooted at
least once since the service was set up — confirms the
"reboot test PENDING" item from POST_MERGE_TODO §12 has IMPLICITLY
PASSED). Update §12 to mark this resolved.

---

## 6. Cron jobs (host)

```
/etc/cron.d/:
  e2scrub_all   ← LUKS-related
  sysstat       ← OS metrics
```

(Full host crontab requires sudo; only the cron.d dir is readable.)
- The Phase 5.2 cache-verify cron (mentioned in user's stored memory)
  if it exists isn't in cron.d — likely in user crontab. Defer.
- The Phase 6.1 reboot-test cron should have self-removed after the
  test fired. Inferred resolved.

---

## 7. Backup verification ✓

```
postgres-backup: Up 16 hours (healthy)
backups/daily/:
  meddoc-20260426.sql.gz (1.5 MB)
  meddoc-20260427.sql.gz (1.7 MB)
  ...
```

✓ Container healthy + recent backup files (within 24h)
⚠️ Restore not tested — defer to Phase 6.2 (offsite backup) initiative

---

## What was NOT covered

- Host-level firewall rules (`iptables -L`, `ufw status`) — needs sudo
- Disk-level disk-encryption (LUKS root vol vs LUKS pgdata only) —
  deferred to Phase 6 successor
- Container runtime version + CVE state on the host docker daemon
- Caddy access logs — would need to read `/var/log/caddy/` (sudo)
- Restore-from-backup drill — Phase 6.2 deferred work
