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

Long-term: set `mem_limit` per service in `docker-compose.yml` (T-M15 finding H9). Tentative limits: worker 1 Gi, app 512 Mi, postgres 512 Mi.

### 5.4 Disk full

```bash
df -h /                             # confirm 95%+
docker system df                    # usually 30+ GB in build cache
docker system prune -af --volumes   # DESTRUCTIVE — removes ALL unused
                                    # images, networks, volumes, build cache
```

Scheduled cleanup: add to crontab once a month (`0 4 1 * * docker system prune -af`). Never prune while a build is in flight.

### 5.5 MinIO bucket disappeared

```bash
# Recreate bucket (worker bootstraps the bucket on start, but manual is OK)
docker compose exec minio mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
docker compose exec minio mc mb local/transcribe-md-audio
```

Restart the worker so it rediscovers the bucket via its client cache.

---

## 6. Post-deploy checklist

After any change hits main:

- [ ] `docker compose ps` shows 8/8 Up.
- [ ] Port 80 / 9010 / 9020 respond (regression matrix).
- [ ] `docker compose logs --tail 20 transcribe-md-worker` shows booting → listening on queue.
- [ ] `doctor_edit_patterns` count >0 after a real sign (or confirm legacy skip log if testing with a pre-T-M14.1 visit).
- [ ] `AiCall` rows appearing with expected `purpose` tags and nonzero cost.
- [ ] If you changed `.env`: confirm `docker compose exec <service> printenv VAR_NAME` matches, container was recreated (not just restarted).
