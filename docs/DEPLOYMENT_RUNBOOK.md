# Deployment Runbook

Operational procedures for deploying, updating, rolling back, and recovering `/opt/meddoc-pro`.

Target host: Ubuntu 24 LTS, single VPS, ≥2 GB RAM, ≥40 GB disk. All procedures assume root or a sudo-enabled user.

---

## 1. First-time deploy on a fresh VPS

### 1.1 Host prep

```bash
# SSH in as root (or via your chosen cloud-init user) and create a deploy user.
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
rsync -a ~/.ssh/ /home/deploy/.ssh/ && chown -R deploy:deploy /home/deploy/.ssh

# From now on, log in as `deploy` and use sudo.

# Base packages
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git rsync

# Docker Engine + Compose plugin (official repo)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add deploy user to docker group so compose doesn't need sudo
sudo usermod -aG docker deploy
newgrp docker      # re-read group membership without logout

# Verify
docker compose version
```

### 1.2 Clone the repo

```bash
sudo mkdir -p /opt/meddoc-pro
sudo chown deploy:deploy /opt/meddoc-pro
cd /opt
git clone https://github.com/kasrarayat-cloud/MedDoc.git meddoc-pro
cd meddoc-pro
```

### 1.3 Configure environment

```bash
cp .env.production.example .env
$EDITOR .env
```

Fill in every value marked **[REQUIRED]**. Minimum set for a launch-ready deploy:

- `DB_PASSWORD`, `DATABASE_URL` (keep shape, sub in password)
- `AUTH_SECRET` — `openssl rand -base64 32`
- `PUBLIC_URL`, `AUTH_URL`, `TRANSCRIBE_MD_AUTH_URL`, `MARKETING_URL`, `NEXT_PUBLIC_*_URL` (all 4 set)
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`

Everything else has a safe default. Leave `RESEND_API_KEY=` blank to disable email delivery until your Resend domain is verified.

### 1.4 Bring up the stack

```bash
# Pull base images first (reduces parallel network pressure during up)
docker compose pull postgres redis minio caddy

# Start infrastructure services
docker compose up -d postgres redis minio caddy

# Wait for postgres healthy
until docker compose exec postgres pg_isready -U meddoc; do sleep 1; done

# Run migrations
docker compose run --rm db-migrate

# Build app images (ONE service at a time — the 2 GB VPS OOM-kills
# parallel builds).
docker compose build marketing
docker compose build meddoc-pro
docker compose build transcribe-md
docker compose build transcribe-md-worker

# Start the rest
docker compose up -d marketing meddoc-pro transcribe-md transcribe-md-worker
```

### 1.5 Verify

```bash
# All 8 containers Up
docker compose ps --format 'table {{.Name}}\t{{.Status}}'

# Regression port matrix (expected codes in parens)
curl -sS -o /dev/null -w "port 80:   %{http_code}\n" http://localhost:80/    # 200
curl -sS -o /dev/null -w "port 9010: %{http_code}\n" http://localhost:9010/  # 200
curl -sS -o /dev/null -w "port 9020: %{http_code}\n" http://localhost:9020/  # 307 → /login

# Worker queue is clean
docker compose exec redis redis-cli LLEN "bull:transcribe-md:wait"      # 0
docker compose exec redis redis-cli LLEN "bull:transcribe-md:active"    # 0
docker compose exec redis redis-cli LLEN "bull:transcribe-md:failed"    # 0

# pgvector extension present
docker compose exec postgres psql -U meddoc -d meddoc -c "\dx vector"

# T-M16.3: /api/health checks + docker healthcheck status
curl -sS http://localhost:3001/api/health | head -c 500  # meddoc-pro
curl -sS http://localhost:3011/api/health | head -c 500  # transcribe-md
#   Both should return JSON with { "status": "healthy", ... } and HTTP 200.
#   Docker healthchecks run every 30s; `docker compose ps` shows
#   (healthy) once they converge.
```

### 1.6 Smoke test (mock mode, no real AI calls)

```bash
# Temporarily flip MOCK_AI_CALLS for the smoke test
docker compose exec transcribe-md-worker env | grep MOCK_AI_CALLS
# If not "true", edit .env → MOCK_AI_CALLS=true →
# docker compose up -d --force-recreate transcribe-md transcribe-md-worker

cd apps/transcribe-md
npx playwright test --project=chromium
# All 4 scenarios should pass.

# Don't forget to flip MOCK_AI_CALLS back to false and recreate.
```

---

## 2. Rolling update (existing deploy)

```bash
cd /opt/meddoc-pro

# 1. Backup first (1 minute, minimal downtime)
BACKUP=/opt/meddoc-pro/backups/pre_deploy_$(date -u +%Y%m%d_%H%M%S).sql.gz
docker compose exec -T postgres pg_dump -U meddoc -d meddoc --no-owner --no-acl | gzip > "$BACKUP"

# 2. Pull latest
git fetch origin main
git log HEAD..origin/main --oneline      # review what's landing
git merge --ff-only origin/main

# 3. If migrations are present
ls packages/db/prisma/migrations/        # check for new dirs
docker compose run --rm db-migrate        # Prisma will apply + log diff

# 4. Rebuild changed services (sequential — VPS can't parallel-build)
#    Identify which services are affected by the diff, then:
docker compose build transcribe-md-worker
docker compose build transcribe-md
# (meddoc-pro, marketing only if they changed)

# 5. Recreate
docker compose up -d transcribe-md transcribe-md-worker

# 6. Verify (see §1.5)
```

**Zero-downtime tip**: `docker compose up -d` replaces containers one-by-one. In-flight HTTP requests drop (there's no bluegreen/rolling deploy today). For the worker, BullMQ's lock means in-flight jobs finish on the old container before the new one picks up; a restart mid-job triggers BullMQ retry.

---

## 3. Rollback

Reverting a bad deploy:

```bash
cd /opt/meddoc-pro
git log --oneline -10                     # find the last-known-good commit
git reset --hard <good-sha>               # or `git revert <bad-sha>` for a forward-only history

# If the bad deploy shipped a migration, roll it back BEFORE rebuilding.
# Prisma has no automatic down-migration — you either:
#   (a) write the inverse SQL manually and run it via psql, OR
#   (b) restore from the pre-deploy pg_dump (see §4).
# (a) is preferred for small schema diffs; (b) for anything touching data.

# Rebuild affected images from the reset SHA (sequential)
docker compose build <service>
docker compose up -d <service>

# Verify (see §1.5)
```

---

## 4. Restore from backup

```bash
# Pick a backup. Current convention: backups/pre_<label>_<date>.sql.gz
ls -lh /opt/meddoc-pro/backups/

# Stop apps (keep postgres running)
docker compose stop transcribe-md transcribe-md-worker meddoc-pro marketing caddy

# Drop and recreate the database (DESTRUCTIVE — do NOT skip the backup step)
docker compose exec -T postgres psql -U meddoc -d postgres -c "DROP DATABASE meddoc;"
docker compose exec -T postgres psql -U meddoc -d postgres -c "CREATE DATABASE meddoc OWNER meddoc;"

# Restore
gunzip -c /opt/meddoc-pro/backups/pre_<label>_<date>.sql.gz | \
  docker compose exec -T postgres psql -U meddoc -d meddoc

# If pgvector was missing from the dump (older backups), re-enable:
docker compose exec postgres psql -U meddoc -d meddoc -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Restart apps
docker compose start caddy marketing meddoc-pro transcribe-md transcribe-md-worker

# Verify (see §1.5)
```

MinIO objects are NOT in the pg_dump — audio lives in the bucket and is cascaded to `null` references if visits are lost. Use `mc mirror` or restic for MinIO-specific backups (future work).

---

## 5. Common failure modes

### 5.1 `502 Bad Gateway` on port 80

Caddy can't reach the meddoc-pro container. Usually: the app container is down or still booting.

```bash
docker compose logs --tail 50 meddoc-pro
docker compose restart caddy meddoc-pro
```

### 5.2 Pipeline stuck — visit shows "transcribing" forever

```bash
# Queue depth
docker compose exec redis redis-cli LLEN "bull:transcribe-md:active"
docker compose exec redis redis-cli LLEN "bull:transcribe-md:failed"

# Worker logs
docker compose logs --tail 100 transcribe-md-worker

# If the worker is wedged, bounce it. BullMQ's lock will release after
# job-timeout seconds (default 15 min) and the retry will kick in.
docker compose restart transcribe-md-worker
```

### 5.3 Postgres OOM-kill on host

Symptom: `docker compose ps` shows postgres in `Restarting` state, meddoc-pro + transcribe-md error out on DB queries. `dmesg | grep oom` shows the kill.

```bash
free -h                                    # check available + swap
docker stats --no-stream                   # which container is the hog
docker compose down transcribe-md-worker   # largest memory footprint
free -h                                    # confirm headroom is back
docker compose up -d transcribe-md-worker  # bring it back with fresh allocation
```

Resource-limit ceilings landed in T-M16.4; see §7 for the
per-service table. If a specific container keeps OOM-killing,
bump its `mem_limit` in `docker-compose.yml` and recreate.

### 5.4 Disk full

Fast triage — see §9 for the full monthly cleanup workflow:

```bash
df -h /                             # confirm 95%+
docker system df                    # ~30 GB in build cache is typical
make prune-docker                   # interactive confirm + prune (T-M16.4)
# or, without the Makefile wrapper:
docker system prune -a --volumes --filter "until=720h" -f
```

Don't cron-schedule prune — image deletion can take out rollback
candidates. Keep it manual + monthly. Full playbook in §9.

### 5.5 MinIO bucket disappeared

```bash
# Recreate bucket (worker bootstraps the bucket on start, but manual is OK)
docker compose exec minio mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
docker compose exec minio mc mb local/transcribe-md-audio
```

Restart the worker so it rediscovers the bucket via its client cache.

---

## 6. Observability — Sentry + external uptime monitor

T-M16.3 wired Sentry into both apps + the transcribe-md worker, and
added a `/api/health` probe to both apps. Neither is useful without
the operator configuring two small pieces:

### 6.1 Sentry DSNs

At https://sentry.io, create two projects (one per app) and copy
their DSNs into `.env`:

```bash
# Server-side Sentry DSNs — empty strings = Sentry no-ops (safe default)
SENTRY_DSN_MEDDOC_PRO=https://<key>@o<org>.ingest.sentry.io/<project>
SENTRY_DSN_TRANSCRIBE_MD=https://<key>@o<org>.ingest.sentry.io/<project>

# Browser-side DSNs. Must mirror the server values. MUST start with
# NEXT_PUBLIC_ because the Next bundler embeds them at build time.
NEXT_PUBLIC_SENTRY_DSN_MEDDOC_PRO=<same-as-above>
NEXT_PUBLIC_SENTRY_DSN_TRANSCRIBE_MD=<same-as-above>

# Optional: tag events by environment and release.
SENTRY_ENVIRONMENT=production
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=<short-sha>
NEXT_PUBLIC_SENTRY_RELEASE=<short-sha>
```

Changing Sentry env vars requires a full rebuild for the client
bundle to pick them up (NEXT_PUBLIC_* is a build-time embed). The
server side picks them up on container recreate.

```bash
docker compose build meddoc-pro transcribe-md transcribe-md-worker
docker compose up -d --force-recreate meddoc-pro transcribe-md \
  transcribe-md-worker
```

Sentry's own beforeSend hook scrubs PHI via
`redactPhi` from `@meddoc/ai` before emission, so even if an error
message accidentally carries a transcript snippet the >20-word
collapser masks it as `[REDACTED:Nw]`.

Worker errors are captured with `{ visitId, layer }` tags so ops can
filter Sentry issues by failure point. The capture happens BEFORE
the BullMQ re-throw, so retry semantics are preserved.

### 6.2 External uptime monitor

Docker's built-in healthchecks restart containers but don't tell
anyone. Point a third-party monitor at `/api/health` on each app so
a multi-container failure (e.g. postgres down → both apps unhealthy)
sends a pager.

Recommended providers (pick one, free tier is enough):
- **UptimeRobot** — 50 monitors free, 5-minute intervals.
- **Better Stack** — richer incident timeline, also free tier.
- **Hetzner Cloud Monitor** (if you're already on Hetzner) — no
  extra account needed.

Configure two monitors per deployment:

| Name | URL | Expected |
|------|-----|----------|
| meddoc-pro health | `http://<host>:80/api/health` | 200 + JSON with `"status": "healthy"` |
| transcribe-md health | `http://<host>:9020/api/health` | 200 + JSON with `"status": "healthy"` |

Both endpoints return `503 { "status": "unhealthy", ... }` when any
required dependency (postgres for meddoc-pro; postgres + redis +
minio for transcribe-md) is down. Status-code monitoring catches
503; `status == "healthy"` body checking catches a 200-with-failed-
checks edge case.

Alert routing: email the operator on any 503 for >5 minutes. Page on
repeated fails in a 30-minute window.

Once TLS is live, switch monitor URLs to `https://` and enable
TLS-expiry monitoring on the same checks (most providers include
this for free).

### 6.3 Worker liveness (gap)

The transcribe-md worker is a BullMQ consumer with no HTTP endpoint,
so it has no docker healthcheck and doesn't appear in `/api/health`.
Today's signals:
- Sentry captures any pipeline throw via `captureWorkerException` in
  `apps/transcribe-md/src/worker-sentry.ts`.
- `docker compose ps` shows `Up <duration>` based on process lifecycle.
- BullMQ's `failed` queue depth grows if jobs are failing:
  `docker compose exec redis redis-cli LLEN "bull:transcribe-md:failed"`.

A dedicated worker-liveness probe is a future milestone; until then
the "completed jobs per hour == 0 for 1+ hour" heuristic is a good
proxy for "worker stuck".

## 7. Host memory baseline (T-M16.4 diagnosis)

The T-M15 audit flagged swap usage at 1.9 GB on a 1.8 GB-RAM host;
the T-M16.4 re-audit confirmed 2.0 GB swap on the same physical box
after an hour of dev work. Digging into `ps aux --sort=-rss` showed
**our app containers are not the culprit** — they total ~285 MB
across all eight Docker services. The top userspace consumers:

| Process | RSS | Nature |
|---------|-----|--------|
| `dockerd` | 504 MB | Docker daemon — aggregates all container-process memory |
| Dev-session tooling (Claude agent, etc.) | ~390 MB | Ephemeral; vanishes when the dev session ends |
| `next-server` × 4 | ~150 MB | Next.js runtime processes across the 3 apps |
| Unrelated co-located projects (openclaw, meilisearch, ai-deal-hunter) | ~70 MB | Shared VPS tenants outside this repo |
| Linux + systemd + containerd + multipathd + journald | ~150 MB | OS baseline |

**No Postgres tuning is warranted** — postgres is at 6 MiB resident.
**No app-side memory refactor is warranted** — the apps are light.
The pressure is a combination of dockerd overhead, this VPS hosting
other projects, and the dev session itself.

**What we did instead (T-M16.4 Commit 1)**: compose `mem_limit` +
`cpus` on every service as protective ceilings (see
`docker-compose.yml`). These limits protect against a future
runaway container OOM-killing postgres, not against current-state
swap pressure. Current values:

| Service | mem_limit | cpus |
|---------|-----------|------|
| postgres | 512 MB | 1.0 |
| redis | 128 MB | 0.5 |
| minio | 256 MB | 0.5 |
| caddy | 128 MB | 0.5 |
| marketing | 256 MB | 0.5 |
| meddoc-pro | 512 MB | 1.0 |
| transcribe-md | 512 MB | 1.0 |
| transcribe-md-worker | 1024 MB | 1.5 |

Sum of `mem_limit` across services (≈ 3.3 GB) exceeds physical RAM
(1.8 GB) on purpose — limits are ceilings, not reservations. They
only fire when a container actually hits them.

**Future note**: if memory pressure starts causing observable
problems (slow API latency, worker OOM-kills, PDF renders failing)
post-pilot, **upgrade the VPS to 4 GB RAM** rather than trying to
squeeze the apps further. At 4 GB + the current co-located-tenant
mix, we'd have ~2 GB of real headroom for traffic spikes.

## 8. Automated DB backups (T-M16.4)

A `postgres-backup` sidecar container runs pg_dump against the
meddoc DB on a `@daily` cron schedule and writes rotated gzipped
dumps to `/opt/meddoc-pro/backups/`. Retention policy:

- 7 daily backups
- 4 weekly backups
- 6 monthly backups
- 1 always-latest copy (`last/`)

Total disk budget at current DB size (~68 MB compressed) is well
under 2 GB even with the full rotation in place.

### 8.1 Verify the service is running

```bash
docker compose ps postgres-backup
# Should show "Up (healthy)" once the HEALTHCHECK_PORT probe converges.
```

### 8.2 Trigger a one-off backup on demand

The image exposes the internal script at `/backup.sh`:

```bash
docker compose exec postgres-backup /backup.sh
ls -lht /opt/meddoc-pro/backups/daily/ | head
```

Use this before risky operations (schema changes, data migrations).

### 8.3 Filename patterns

Two patterns coexist in `/opt/meddoc-pro/backups/`:

- `<prefix>-meddoc-<date>.sql.gz` — written by the automated service,
  where `<prefix>` is one of `daily`, `weekly`, `monthly`, `last`.
  Landing in the matching subdirectory (`backups/daily/`, etc.).
- `pre_<label>_<timestamp>.sql.gz` — historical manual dumps taken
  before risky milestone deploys (T-M14.1, T-M16.2). These remain
  for posterity; the automated service does not touch them.

Both are regular pg_dump gzipped output. §4 restore procedure works
for either — just point the `gunzip -c` path at whichever file you
want to restore.

### 8.4 Off-host mirror (operator task, DEFERRED)

These backups are useless against VPS loss if they live only on the
VPS. Before real customer data lands, configure an off-host mirror:

```bash
# Example: rsync to a second VPS every 6 hours (add to host crontab).
0 */6 * * * rsync -aq --delete /opt/meddoc-pro/backups/ \
  backups@other-vps:/opt/meddoc-backups/
```

Alternatives: restic to a cheap object-storage bucket (B2, R2),
borg to a dedicated backup VPS, or a provider-native snapshot
schedule if Hetzner / whoever has one. Pick one; document the
restore chain; don't skip this step before onboarding PHI.

### 8.5 Restoring from an automated backup

Same as §4, just point at the automated file:

```bash
gunzip -c /opt/meddoc-pro/backups/last/meddoc-latest.sql.gz \
  | docker compose exec -T postgres psql -U meddoc -d meddoc
```

## 9. Monthly docker cleanup (T-M16.4)

Build cache + stale images accumulate faster than you'd think on
this single-VPS deploy. Rebuilding apps a few times a week pushes
the 99 GB root filesystem past 80% in a couple of weeks. Ops task:
**run the prune once a month on a day you're NOT about to roll back
to a previous image**.

### 9.1 What the prune removes

```bash
docker system prune -a --volumes --filter "until=720h" -f
```

- `-a` — untagged AND unused tagged images
- `--volumes` — dangling volumes (none of our named volumes qualify
  — `pgdata`, `redis_data`, `minio_data`, `caddy_data`, `caddy_config`
  are attached to active services and are safe)
- `--filter "until=720h"` — only objects untouched for >30 days.
  This is the safety rail — yesterday's fallback image stays put.
- `-f` — no confirmation prompt (use `make prune-docker` for an
  interactive confirmation instead)

Typical reclaim at the point it's worth running: **~25-35 GB**.

### 9.2 Wrapper

```bash
make prune-docker        # interactive; prompts before deleting
make prune-docker-dry    # shows what would go, deletes nothing
```

### 9.3 Scheduling

**Do NOT add this to cron.** Image deletion can take out a rollback
target you wanted to keep around. The monthly cadence is a calendar
reminder for ops, not an automated job.

Guidance:
- Only run after a successful deploy has been stable for ≥1 week.
- Don't run during / right before a build — prune races with the
  build's temporary image tags.
- After `make prune-docker`, re-check `df -h /` and `docker system
  df`. Expected: root fs drops 20-30%, `Reclaimable` columns near 0.

### 9.4 When to NOT prune (even on schedule)

- A new milestone just shipped → you might want to roll back to the
  previous image if a regression surfaces.
- Active incident → don't introduce more variables.
- Disk is already under 50% full → not worth the risk.

## 10. Post-deploy checklist

After any change hits main:

- [ ] `docker compose ps` shows 8/8 Up, app containers `(healthy)`.
- [ ] Port 80 / 9010 / 9020 respond (regression matrix).
- [ ] `/api/health` on both apps returns `{"status":"healthy"}` + 200.
- [ ] `docker compose logs --tail 20 transcribe-md-worker` shows booting → listening on queue.
- [ ] `doctor_edit_patterns` count >0 after a real sign (or confirm legacy skip log if testing with a pre-T-M14.1 visit).
- [ ] `AiCall` rows appearing with expected `purpose` tags and nonzero cost.
- [ ] If you changed `.env`: confirm `docker compose exec <service> printenv VAR_NAME` matches, container was recreated (not just restarted).
- [ ] Sentry dashboard shows the test-deploy release tag (if `SENTRY_RELEASE` was bumped).
- [ ] External uptime monitor reports both health endpoints green.
