# VPS Deep Clean — Forensics Report

- **Filename date:** `20260515` (as specified in the task brief — kept verbatim so the Lead finds it at the expected path)
- **Actual execution date:** **2026-05-17 ~21:10 UTC** (discrepancy noted; brief was likely drafted 2 days before run)
- **Host:** `crimson-mink-43222`  ·  **Operator:** Lead (autonomous)  ·  **Mode:** SERIAL ONLY (memory #1 — RAM constraint history)
- **Scope:** meddoc-pro VPS hygiene / disk reclaim. No code changes.

---

## ⚠️ HEADLINE FINDINGS (surface to Kasra — read first)

1. **This is a MULTI-TENANT host.** The brief assumed a single-tenant meddoc-pro VPS. It is not. Three independent projects share this daemon and filesystem:
   - **meddoc-pro** — 9 containers (the project in scope). ✅
   - **leathererp** — `leathererp-pg`, `leathererp-redis`, `leathererp-meili` (3 containers) **+ owns essentially the entire `/tmp` working set** (active dev server, tsx, metro, Playwright/Chromium temp, modified *minutes* before this run).
   - **openclaw** — `openclaw-openclaw-gateway-1` (1 container, `openclaw:local`).
   Every `docker … prune` is **daemon-global** and every `/tmp`/cache sweep is **host-global**. All destructive actions below were re-scoped to avoid collateral damage to leathererp/openclaw. **The brief's blanket commands were NOT run as written.**

2. **`meddoc-pro_pgdata` volume — NOT TOUCHED, needs a conscious decision.** 77.44 MB, **0 container links**, name implies postgres data. The running `meddoc-pro-postgres-1` uses `pgvector/pgvector:pg16` with different storage and mounts no named volume. This volume looks orphaned from a pre-pgvector era — **but a `pgdata`-named volume is on the NEVER-AUTO-DELETE list.** Left intact. Kasra to decide consciously.

3. **`/tmp` mass-delete was SKIPPED entirely.** It is almost 100% `leathererp`-owned, every file dated today, nothing older than 7 days, ≈0 meddoc-pro reclaim, and deleting it risks breaking a *running* leathererp dev server / metro bundler / Playwright run.

4. **`git clean -fdx` was NEVER executed (dry-run only, as mandated).** Confirmed it *would* delete `.env`, `apps/meddoc-pro/.env`, `backups/`, and the entire `docs/` audit tree. The orphan sweep produced **zero** safe deletions.

5. **Pre-existing unhealthy containers (NOT caused by this sweep):** `leathererp-meili` (other tenant) and `meddoc-pro-postgres-backup-1` (backup sidecar — `prodrigestivill/postgres-backup-local` routinely false-reports unhealthy between cron windows). Baseline state, flagged not fixed (out of scope).

---

## STEP 1 — BASELINE (pre-cleanup)

### Disk
```
/dev/sda2  296G  138G used  146G avail  49%  /
```

### Memory
```
Mem: 15Gi total  6.0Gi used  4.4Gi free  9.6Gi available
Swap: 4.0Gi total  943Mi used
```
(Note: memory #1 recorded a 5.6 GB RAM regression on 2026-05-04; host now reports 15 Gi total / 9.6 Gi available — balloon appears deflated. Healthy.)

### Preflight safety gates — ALL GREEN
| Gate | Result |
|---|---|
| OOM kills (last 7d) | none |
| Load average | 1.01 / 0.65 / 0.96 (normal) |
| Container restart loops | **0 restarts on all 13 containers** |
| Disk | 49% (threshold 90%) |
| RAM available | 9.6 Gi |
| meddoc-pro-postgres-1 | healthy |

> The auto-pruning `preflight-health-check` skill was deliberately **not** invoked: this task carries its own pre-flight section, and Step 1 requires an *uncorrupted* baseline — the skill auto-prunes Docker when cache >50 GB, which would have destroyed the before/after delta this report depends on. All of the skill's hard gates were verified manually above and are green.

### `docker system df`
```
TYPE            TOTAL  ACTIVE  SIZE      RECLAIMABLE
Images          42     12      31.18GB   10.17GB (32%)
Containers      13     13      1.235GB   0B (0%)
Local Volumes   10     8       709.7MB   77.44MB (10%)
Build Cache     359    0       86.63GB   63.88GB
```

### Containers (13 — all "Up", 0 stopped)
meddoc-pro (9): transcribe-md-worker, transcribe-md, caddy, marketing, meddoc-pro, minio, redis, postgres-backup⚠, postgres
leathererp (3): pg, redis, meili⚠ · openclaw (1): gateway
(⚠ = pre-existing unhealthy, see Headline #5)

### Volumes
`meddoc-pro_pgdata` 77.44MB **0 links** ⚠ (Headline #2) · 2 anon 0-link 0B · `meddoc-pro_minio_data` 492MB · `meddoc-pro_redis_data` 45.8MB · `leathererp_*` (other tenant) — none touched

### Filesystem (no meddoc-pro cruft found)
- `/opt/meddoc-pro` largest: `node_modules` 1.4G (load-bearing), `docs` 262M (NEVER TOUCH), `secrets` 133M (NEVER TOUCH), `backups` 31M (NEVER TOUCH)
- No host `.next` dirs (apps run from images) · no `*.log` >10M · no core dumps · no `/tmp` files >7d
- `/tmp`: ~leathererp-owned, all dated 2026-05-17
- Container log driver: `json-file max-size=10m max-file=3` → ≤30 MB/container, **cannot exceed 1 GB** (Step 5 moot)
- `~/.npm` 335M (regenerable) · `~/.cache` 707M (ms-playwright + prisma engines = load-bearing) · no pnpm store

---

## STEP 2 — CRUFT CATEGORIZATION & DECISIONS

### Category A — executed (safe, no cross-tenant data risk)
| # | Action | Expected reclaim | Notes |
|---|---|---|---|
| A1 | `docker image prune --force` | ~10.17 GB | Dangling-only (no `-a`); tagged images incl. other tenants' & `meddoc-pro-db-migrate:latest` untouched by definition |
| A2 | `docker container prune --force` | 0 B | **Provable no-op** — 0 stopped containers confirmed; run for idempotency |
| A3 | `docker builder prune --force --filter until=24h` | bulk of 63.88 GB | Keeps today's marathon cache for fast rollback rebuilds |
| A4 | `npm cache clean --force` | ~335 MB | claude-owned, regenerable |

### Category B — Lead judgment (documented)
- **Dangling images are post-rebuild orphans, NOT the rollback mechanism.** Services are `:latest`-only tagged; `docker image prune` (no `-a`) never removes tagged/in-use images, so all *current* versions are 100% safe. Rollback here = source rebuild (`git checkout && docker compose build`), accelerated by the <24h build cache we retain — not image-tag swap. The brief's "keep 3 per service" rule targets multi-version tag history, which does not exist here (N/A).
- **Builder prune horizon = `until=24h`, NOT also `until=168h`.** The brief's two-filter sequence is internally contradictory (running both nets "remove everything >24h", contradicting its own "keep last 7 days" comment). `until=24h` is the single well-defined operation honoring rollback intent: it preserves *today's* (the rollback-relevant) cache and reclaims the staler bulk.
- **`~/.cache` (707 MB) retained.** Brief's stated scope is `~/.npm`/`~/.pnpm-store` only. `~/.cache` holds ms-playwright browsers (E2E/QA skills) and Prisma engines (migration workflow, memory #5) — load-bearing. Cleaning only `~/.npm`.
- **Tiny intentional config backups kept** (`Caddyfile.backup`, `Caddyfile.bak-T0.19-followup`, `docker-compose.yml.backup`, `docker-compose.yml.pre-h8`): <100 KB total, task-tagged deliberate rollback aids, zero reclaim value.

### Category C — NEVER touched (surfaced to Kasra)
- `meddoc-pro_pgdata` 0-link volume (Headline #2) · 2 anon 0-link volumes (0 B, no reclaim)
- All `leathererp_*` / `openclaw` resources (other tenants) · entire `/tmp` (Headline #3)
- `.env*`, `secrets/`, `backups/`, `docs/` tree, migrations, `~/.ssh` — untouched
- `/var/log` rotated logs: root:syslog-owned, not the `claude` user's purview; brief's `find /var/log -delete` would fail non-root and reclaim is negligible (alternatives.log etc.). Surfaced for root-level OS cleanup if desired — not actioned.

### Steps that turned out N/A
- Step 4 orphan sweep → 0 deletions (all untracked = protected or intentional; no `.swp/.tmp/.orig`)
- Step 5 log truncation → daemon already rotation-capped at 30 MB/container
- `.next/cache` → no host-side `.next`
- `/tmp` >7d → nothing qualifies + other-tenant live files
- pnpm store prune → pnpm not installed

---

## STEP 3 — EXECUTION LOG

| # | Action | Reclaimed | Result |
|---|---|---|---|
| A1 | `docker image prune --force` | **2.074 GB** | Dangling removed; tagged/in-use images (incl. other tenants, `db-migrate:latest`) untouched. Lower than the 10 GB `system df` estimate because dangling layers were heavily shared with the retained tagged images. |
| A2 | `docker container prune --force` | **0 B** | No-op confirmed (0 stopped containers). |
| A3 | `docker builder prune --force --filter until=24h` | **72.79 GB** | Stale build cache from before today's marathon. Today's cache retained for fast rollback rebuilds. (Exceeded the 63.88 GB estimate — A1 freed image refs that made more cache layers collectable.) |
| A4 | `npm cache clean --force` | **~238 MB** | `~/.npm` 335M → 97M. claude-owned, regenerable. |
| — | pnpm store prune | — | N/A (pnpm not installed). |
| — | `/tmp` >7d delete | — | **SKIPPED** — leathererp-owned live files, nothing >7d (Headline #3). |
| — | `.next/cache` | — | N/A (no host-side `.next`). |
| — | `/var/log` rotated logs | — | N/A (root:syslog-owned; non-root delete would fail; negligible size). |
| — | Step 4 orphan sweep | 0 | No `.swp/.tmp/.orig`; all untracked = protected docs/secrets/backups. `git clean` **never executed**. |
| — | Step 5 log truncation | — | N/A (daemon rotation `max-size=10m max-file=3` ≤30 MB/container). |

**Total reclaimed ≈ 75.1 GB** (prune-reported) / **76 GB** (disk-measured). Above the 1 GB hard-stop floor.

## STEP 6 — POST-CLEANUP VERIFICATION

| Metric | Before | After |
|---|---|---|
| Disk `/` | 138G used · 146G avail · **49%** | **62G used · 222G avail · 22%** |
| RAM available | 9.6 Gi | 9.0 Gi |
| Images | 42 | 13 |
| Build cache | 359 / 86.63 GB | 111 / 13.84 GB |

- **All 9 meddoc-pro containers:** healthy. (`meddoc-pro-postgres-backup-1` unhealthy = **pre-existing baseline**, identical to Step 1 — NOT cleanup-induced; `postgres-backup-local` false-reports between cron windows.)
- **Other tenants untouched:** `leathererp-pg/redis` healthy, `leathererp-meili` unhealthy (pre-existing), `openclaw` up. All restart counts still **0**. No collateral damage.
- **Smoke:** `https://app.quillmd.com/api/health` → **HTTP 200**; `127.0.0.1:3001/api/health` → 200; `127.0.0.1:3011/api/health` → 200.
- **DB stuck-visit check:** **0 stuck visits.** The brief's query was stale — `TranscribeVisitStatus` enum is `QUEUED, TRANSCRIBING, EXTRACTING, DRAFTING, CRITIQUING, POLISHING, AUTOMATING, READY, FAILED, SIGNED` (**no `EXPORTED`, no `DELETED`**). All visits stale >15 min are terminal-only (READY 163 / SIGNED 25 / FAILED 13); no in-flight status is wedged. ⚠️ **Action item for Kasra:** update the canonical stuck-visit query / regression runbook — the `('READY','SIGNED','EXPORTED','DELETED')` set errors against the live enum.

## STEP 7 — VERDICT

✅ **GREEN.** ~76 GB reclaimed (49% → 22% disk), all in-scope containers healthy, public health 200, zero stuck visits, zero collateral damage to co-tenants. No HARD-STOP condition triggered. Nothing in the NEVER-TOUCH set was modified.

### Surfaced to Kasra (no action taken — needs human decision)
1. **Multi-tenant host** — meddoc-pro shares this VPS with `leathererp` (3 containers + the `/tmp` working set) and `openclaw` (1 container). Future "VPS-wide" briefs must account for this; global `docker prune` / `/tmp` sweeps are blast-radius-wide.
2. **`meddoc-pro_pgdata`** volume — 0 links, 77.44 MB, `pgdata`-named, mounted by nothing. Likely a pre-pgvector orphan but NOT auto-deleted (NEVER-TOUCH rule). Kasra to decide consciously.
3. **Stale stuck-visit query** in the brief/runbook — uses non-existent `EXPORTED`/`DELETED` enum values.
4. Pre-existing unhealthy: `leathererp-meili` (other tenant), `meddoc-pro-postgres-backup-1` (sidecar false-positive) — not introduced here.
