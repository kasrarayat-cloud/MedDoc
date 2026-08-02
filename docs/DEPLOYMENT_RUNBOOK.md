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
git fetch origin main && git log HEAD..origin/main --oneline   # review what's landing
git merge --ff-only origin/main
bash scripts/deploy-prod.sh
```

**Use the script.** The prose version of this section failed silently on
2026-07-28 and the script exists so it cannot fail that way again. It does, in
order: backup → **build db-migrate** → migrate → **assert** → build worker →
build app → recreate → health.

### 2.1 Why db-migrate is rebuilt every time

`docker compose run --rm db-migrate` runs whatever image was **last built**.
`db-migrate` builds from the app Dockerfile, so a deploy that rebuilds only
`transcribe-md` and `transcribe-md-worker` leaves it stale.

That happened. It printed:

```
79 migrations found in prisma/migrations
No pending migrations to apply.
```

and exited **0**. The repo had eighty. The image physically did not contain the
new migration directory, so there was nothing for it to find. A clean exit code,
a reassuring message, and nothing done.

**"No pending migrations to apply" from a stale image is indistinguishable from
success.** Never read it as proof.

### 2.2 Why the assertion exists on top of that

Rebuilding is a step a person can forget; this section used to say "rebuild
changed services" and list only the app services. The assertion cannot be
forgotten, because it aborts the deploy before anything is recreated:

```bash
bash scripts/assert-migrations-applied.sh   # 0 = all applied · 1 = UNAPPLIED · 2 = off-host
```

It compares the repo's migration directories against `_prisma_migrations` and
knows nothing about how migrate was invoked — which is the point.

It is **directional**: it fails only when a repo migration is *not applied*. An
applied row with no directory is a baseline (`0000_init`, 2026-04-12,
`applied_steps_count=0`, present in prod and QA) or a since-removed migration,
and is reported for information. Count equality would false-alarm on that
baseline forever, and a guard that cries wolf gets switched off.

### 2.3 The log is a file, never a pipe into `tail`

`scripts/deploy-prod.sh` tees the full transcript to
`docs/deploy-logs/deploy-<UTC>.log` (gitignored — retained on disk, not
versioned). The first attempt at the failed deploy was run as
`deploy.sh | tail -50`, which discarded the backup and migration output: exactly
the two sections that would have shown the no-op. **The record of a deploy must
outlive the terminal.**

### 2.4 Manual equivalent, if you must

```bash
BACKUP=/opt/meddoc-pro/backups/pre_deploy_$(date -u +%Y%m%d_%H%M%S).sql.gz
docker compose exec -T postgres pg_dump -U meddoc -d meddoc --no-owner --no-acl | gzip > "$BACKUP"
docker compose build db-migrate          # <-- NOT optional
docker compose run --rm db-migrate
bash scripts/assert-migrations-applied.sh || exit 1
docker compose build transcribe-md-worker
docker compose build transcribe-md
docker compose up -d transcribe-md transcribe-md-worker
```

Rebuild `meddoc-pro` / `marketing` only if they changed. `packages/shared` must be
in `Dockerfile.worker` — the worker imports from it.

**Zero-downtime tip**: `docker compose up -d` replaces containers one-by-one.
In-flight HTTP requests drop (there's no blue/green today). For the worker,
BullMQ's lock means in-flight jobs finish on the old container before the new one
picks up; a restart mid-job triggers BullMQ retry.

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

### 3.1 Tagged image rollbacks

⚠️ **CORRECTED 2026-08-02.** This section used to open "Every promotion tags the
outgoing images before recreating". **Nothing does that.** `scripts/deploy-prod.sh`
has no tagging step — its only `tag` match is an unrelated comment on line 81 —
and §2.4's manual equivalent has none either. So the tags below exist because
somebody typed the command by hand, and a promotion that forgets leaves no
rollback target at all. The sentence described a guarantee the deploy path does
not provide, which is the most expensive kind of documentation error: it reads
as reassurance and is discovered during an incident.

**Tagging is a MANUAL PRE-STEP. Do it BEFORE `deploy-prod.sh`, not after — once
the build finishes, `:latest` is the new image and the outgoing one is
untagged.**

```bash
# Run this FIRST, before deploy-prod.sh. <slug> names what is being changed.
D=$(date -u +%Y%m%d)
docker tag meddoc-pro-transcribe-md:latest        meddoc-pro-transcribe-md:pre-<slug>-$D
docker tag meddoc-pro-transcribe-md-worker:latest meddoc-pro-transcribe-md-worker:pre-<slug>-$D
docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}' | grep "pre-<slug>-$D"   # record these IDs in the table
```

| Tag | What it restores | Notes |
|---|---|---|
| `:pre-readonlypaper-20260728` | the review page BEFORE it became read-only paper | app `4719eef70099` / worker `09ea62317b44` |
| `:pre-emrehome-20260728` | the review page BEFORE the E/M level row returned to the gate stack | app `bc2bd303740f` / worker `10eb2d4baec1` |
| `:pre-rounds-20260802` | the app BEFORE the Rounds skin went live — **and before C1-d…C2-b, see §3.3** | app `cfa6df5520f6` / worker `d391ddb62cff` / gotenberg `4bd4489d15b7` (the stock `gotenberg/gotenberg:8`) |

Four further families exist on the host and were never recorded here:
`:pre-exportguard-20260728`, `:pre-lanedelete-20260727`, `:pre-auditonly-20260727`
and `:pre-verifierfix-20260727`. **`:pre-verifierfix-20260727` is UNPAIRED — the
worker image exists and the app image does not**, so restoring it would leave app
and worker on mismatched builds. Treat it as unusable.

**The no-rebuild restore path** (seconds, versus ~10 minutes for a rebuild). It
existed only inside old QA reports; it belongs here:

```bash
docker tag meddoc-pro-transcribe-md:pre-<slug>-<date>        meddoc-pro-transcribe-md:latest
docker tag meddoc-pro-transcribe-md-worker:pre-<slug>-<date> meddoc-pro-transcribe-md-worker:latest
docker compose -f /opt/meddoc-pro/docker-compose.yml up -d --no-deps --force-recreate \
  transcribe-md transcribe-md-worker
```

Never *rebuild* `:latest` to stage a rollback. Note the distinction the old
wording blurred: this path **retags onto** `:latest`, which is fine and is how
compose finds the image; what is forbidden is *building* a rollback into
`:latest`, because then the thing you rolled back from no longer exists.

### 3.2 KNOWN CONSTRAINT — a flag rollback of `NEXT_PUBLIC_REVIEW_DOC_VIEW`
### leaves E/M confirm-only, with no override control

**Decided 2026-07-28. Accepted. Do not "fix" it by rebuilding the retired
control.**

Setting `NEXT_PUBLIC_REVIEW_DOC_VIEW=false` and rebuilding returns the legacy
tabbed review view. On that surface there is **no way for a doctor to set a
documentation level** — they can still see the level and still confirm a change,
but not disagree with one.

Why: the level override now lives only in the gate stack (`<EmLevelCard>`), which
is part of the read-only paper. The legacy `BillingCardC3` dropdown and the
coding rail's were retired in the same change, because `POST /em-score/override`
requires a reason and neither surface had anywhere to collect one — they would
have returned 400 on every use. A control that looks live and cannot work is
worse than an absent one, and inventing a rationale to satisfy the route would
put words in an audit row that no doctor said.

**This is acceptable for an emergency rollback window.** The gate does not
weaken: the confirm-before-sign path and the server-side refusal in
`POST /api/visits/[id]/sign` are untouched by the flag, so nothing unreviewed can
be signed. What is lost is one capability, temporarily.

**Revisit only if a rollback has to live longer than an incident.** In that case
the fix is to give `BillingCardC3` its own required-reason step — not to restore
a reasonless caller. Rolling back the IMAGE (`:pre-emrehome-20260728`, §3.1)
restores the old dropdown too and does not have this constraint; prefer it when
the concern is the E/M surface specifically rather than the whole review page.

### 3.3 KNOWN CONSTRAINT — the Rounds rollback is NOT flag-shaped, and it
### carries five other items back with it

**Decided 2026-08-02. Accepted. Do not "fix" it by re-adding a flag branch.**

`NEXT_PUBLIC_SKIN_ROUNDS=true` went live on 2026-08-02 (relay item F). Two
things about rolling it back are not what the flag's name suggests.

**First: the flag path is a REBUILD, not a restart.** `NEXT_PUBLIC_*` is inlined
into the client *and* server bundle at `docker compose build`. Setting the value
false in `.env` and recreating the container changes nothing — the old value is
already compiled in. The flag path costs a full app rebuild (~10 minutes). And
after the old-skin retirement it stops working entirely, because there is no
longer an OFF branch to fall back to.

**Second, and the part to actually plan around: production had not been deployed
since 2026-07-29.** The running image predated **C1-d, C1-e, C1-f, C1-g, C2-a and
C2-b**, all of which shipped dark behind the flag and all of which this deploy
carried to production alongside it. So `:pre-rounds-20260802` is not "the same
app minus a skin" — it is the app as of 2026-07-29.

Rolling the image back therefore also reverts:

- **the A4/US-Letter export fix (C2-b), which is flag-INDEPENDENT.** Before it,
  `docx-generator.ts` declared no page properties and Word used the library's
  default A4 while the PDF drew US Letter — so the doctor read an A4 page on
  screen and downloaded a Letter one. A rollback reinstates that split page for
  every doctor, including any who never see Rounds.
- the converter: `meddoc-pro-gotenberg:fonts` back to stock `gotenberg/gotenberg:8`,
  which has neither Charter nor Inter Tight installed and silently substitutes
  Noto Serif in every preview.
- C1-d…C2-a's contrast fixes on the auth, settings and templates surfaces.

**PREFER THE IMAGE ROLLBACK ANYWAY** — it is seconds and it is the only path
that still exists after retirement. Just know it is a six-item revert, not a
one-flag revert, and say so in the incident note.

**The rollback line, verbatim:**

```bash
docker tag meddoc-pro-transcribe-md:pre-rounds-20260802        meddoc-pro-transcribe-md:latest
docker tag meddoc-pro-transcribe-md-worker:pre-rounds-20260802 meddoc-pro-transcribe-md-worker:latest
docker tag meddoc-pro-gotenberg:pre-rounds-20260802            meddoc-pro-gotenberg:fonts
docker compose -f /opt/meddoc-pro/docker-compose.yml up -d --no-deps --force-recreate \
  transcribe-md transcribe-md-worker gotenberg
```

No rebuild, no `.env` edit, no compose edit. **Verify it landed** the same way
the flip was verified — on the bytes, not the env:

```bash
docker exec meddoc-pro-transcribe-md-1 sh -c \
  'D=/app/apps/transcribe-md/.next;
   echo "rounds: $(grep -rl qm-rounds- $D | wc -l)  (0 = rolled back)";
   echo "control: $(grep -rl qm-lin- $D | wc -l)  (non-zero = the grep works)"'
```

⚠️ **The gotenberg line is stable only until the next deploy.** `deploy-prod.sh`
step 5b rebuilds the converter from `docker/gotenberg-fonts.Dockerfile` and
retags `:fonts`, so a converter rollback is undone by the next promotion. That
is correct — the fonts image is the intended steady state — but do not assume a
retag survives a deploy.

**Migrations are not a concern for this one:** the deploy applied none (83 in
repo, 83 recorded, before and after), so the image rollback needs no schema work.

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

## 5.6 TLS — the renewal timer is not the thing that can break

Host nginx owns 80/443 and terminates TLS with the Let's Encrypt cert at
`/etc/letsencrypt/live/quillmd.com/fullchain.pem`. Caddy sits behind it on
`127.0.0.1:8443` with its own internal certs and is not involved.

**`certbot.timer` renewing successfully is not enough.** nginx reads the cert
file once at start and holds it in memory. A renewed file on disk that nginx
never re-reads is not a renewed certificate — the site keeps serving the old one
until it expires, while every renewal check reports success.

This was the real state on 2026-07-28: the timer was active and a dry run
succeeded, but `/etc/letsencrypt/renewal-hooks/deploy/` was **empty**. Fixed by
installing:

```sh
# /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh   (chmod +x)
#!/bin/sh
set -e
nginx -t && systemctl reload nginx
```

Verify it, from the host:

```bash
ls -l /etc/letsencrypt/renewal-hooks/deploy/          # must be non-empty
certbot renew --dry-run --cert-name quillmd.com
/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh  # graceful, no downtime
echo | openssl s_client -servername quillmd.com -connect quillmd.com:443 \
  2>/dev/null | openssl x509 -noout -enddate
```

⚠️ **Trap.** There is no sudo on this box, so the root path is
`docker run --pid=host -v /:/host` (see AGENTS.md). Running `certbot renew
--dry-run` that way **without `--network host`** fails on DNS resolution and
looks exactly like a renewal failure. Always pass `--network host`.

⚠️ `--dry-run` does not execute deploy hooks. Run the hook script directly to
prove it works.

---

## 5.7 Encryption at rest — the two encrypted volumes

Both PHI stores sit on LUKS-encrypted loop-backed volumes, unlocked at boot by a
systemd unit ordered `Before=docker.service`.

| Store | Backing file | Mapper | Mount | Size |
|---|---|---|---|---|
| Postgres (structured PHI) | `secrets/pgdata.luks` | `pg-encrypted` | `/mnt/pgdata-encrypted` | 1 GiB |
| MinIO (patient AUDIO) | `secrets/miniodata.luks` | `minio-encrypted` | `/mnt/miniodata-encrypted`**`/data`** | 20 GiB |

**MinIO binds the `data` SUBDIRECTORY, not the mountpoint.** That is not
cosmetic — it is the fail-closed guard, and §5.7.1 is why.

### Why MinIO got its own volume rather than sharing Postgres's

The pg volume had 828 MB free and the audio was 1.2 MB, so it *fitted*. It was
still the wrong home. Audio grows at roughly a visit's length in megabytes; at a
five-doctor pilot that is a few hundred MB a day, which exhausts 828 MB in about
two days — **and a full shared volume takes the database down with it.** Letting
audio growth starve Postgres is a worse failure than the disk cost of a second
volume.

20 GiB is ~2 months at pilot volume, against a 90-day retention sweep, and leaves
60 GB+ free on the host.

### 5.7.1 ⚠️ The migration did NOT complete on the day it was declared complete

**2026-07-29, ~01:20–05:50 UTC. MinIO wrote patient-audio-bucket data to the
UNENCRYPTED root filesystem for about four hours while every artefact in this
repository said it was on LUKS.**

Nothing was misconfigured in the usual sense. Each layer was correct in
isolation:

- `docker-compose.yml` bound `minio_data` to `/mnt/miniodata-encrypted` ✅
- `miniodata-encrypted.service` existed and was **enabled** ✅
- `secrets/miniodata.luks` existed, the mapping opened, `mkfs.ext4` ran ✅
- this runbook said "encryption at rest" ✅

**The unit was never STARTED.** `enabled` schedules a unit for the next boot; it
does not run it now. So nothing was mounted at `/mnt/miniodata-encrypted` — and

> **a mountpoint directory exists whether or not anything is mounted on it.**

The bind therefore resolved to a plain directory on `/dev/sda2`. Docker created
it, MinIO wrote into it, the health check went green, and `df` against the path
reported the root filesystem's free space, which looks entirely normal. There
was no error to find because nothing was in an error state.

**Why the setup step left no trace.** The one-shot that opened and formatted the
volume was run as `docker run --privileged --pid=host -v /:/host … chroot /host`
— the documented root-via-docker path. It hung, was never noticed, and sat there
for four hours as a stray container. It had in fact *done its work* (the mapping
and the ext4 both existed); it simply never returned to run the `mount`.

> **`--pid=host` is not enough for device-mapper work. You need `--ipc=host`.**
>
> libdevmapper synchronises with udev through **SysV semaphores**. `docker run`
> gives the container its own IPC namespace, so `cryptsetup` waits on a cookie
> that host udev signals in a *different* namespace. The dm operation completes;
> the process blocks forever afterwards. Both the original `open` and a later
> `close` hung this way and had to be killed — each after finishing its actual
> work, which is what makes it so easy to misread.
>
> Better still: **do not run `cryptsetup` in a container at all.** Use
> `systemctl start miniodata-encrypted` — systemd runs it as a host process,
> with host IPC, and it returns in seconds.

**The fix, and the guard.** The compose `device` now points at
`/mnt/miniodata-encrypted/data`, a directory that exists **only on the encrypted
filesystem**. Docker's local bind driver does not create a missing `driver_opts`
device (compose's short-form `- /host/path:/ctr` syntax *does* — which is how
this class of bug is normally introduced), so:

| encrypted mount | result |
|---|---|
| present | `…/data` exists → MinIO starts |
| **absent** | path missing → **docker refuses → MinIO FAILS CLOSED** |

Negative-controlled 2026-07-29: with the unit stopped,
`docker compose up -d minio` fails with
`failed to mount local volume: mount /mnt/miniodata-encrypted/data: no such file
or directory`, and the container never runs.

**Never "fix" a failed MinIO start by creating that directory by hand.** A
`mkdir -p /mnt/miniodata-encrypted/data` while the volume is unmounted lands on
the plaintext filesystem and silently converts a loud refusal back into the
four-hour failure above. `scripts/check-minio-encrypted-mount.sh` asserts
against exactly that.

### ⚠️ ROLLBACK — written before the migration, and CORRECTED during it

**Correction, recorded rather than quietly fixed.** This section originally said
the pre-migration directory was "left in place, untouched" and that the migration
deleted nothing. That stopped being true mid-procedure: the named volume already
existed pointing at the old path, and it has to be **recreated** to pick up new
`driver_opts` — which means `docker volume rm meddoc-pro_minio_data`, which
deletes the original `_data`. The copy-not-move was real; the volume recreate
undid it.

**So the rollback is the TARBALL**, taken before the stop window:
`backups/pre_minio_move_<UTC>.data.tgz`. It is not a lesser rollback — it is a
frozen, MinIO-stopped copy — but it must be restored rather than simply
re-pointed at, and pretending otherwise would send whoever needs it looking for
a directory that no longer exists.

Note also that after the switch `/var/lib/docker/volumes/meddoc-pro_minio_data/_data`
still appears to hold the data. It does: it is now a **bind mount of
`/mnt/miniodata-encrypted`** — the same directory seen through two paths, not a
second copy. Do not read its presence as an intact rollback.

To go back:

```bash
cd /opt/meddoc-pro
docker compose stop minio

# 1. Point the compose volume back at the docker-managed directory:
#    in docker-compose.yml, restore
#        minio_data:
#          driver: local            # (no driver_opts)
#    i.e. delete the driver_opts block that binds /mnt/miniodata-encrypted.

# 2. The named volume must be recreated to drop the bind, and its content
#    restored from the tarball — the original directory is gone.
docker compose rm -sf minio && docker volume rm meddoc-pro_minio_data
docker compose up -d --no-deps minio          # recreates an empty local volume
docker compose stop minio
docker run --rm -v meddoc-pro_minio_data:/d -v /opt/meddoc-pro/backups:/b alpine \
  sh -c 'tar xzf /b/pre_minio_move_<UTC>.data.tgz -C /d'
docker compose start minio

# 3. Verify object count matches the pre-migration figure recorded in
#    docs/deploy-logs/ for the migration run.
docker exec meddoc-pro-minio-1 sh -c \
  'export MC_CONFIG_DIR=/tmp/mc; mc alias set local http://127.0.0.1:9000 \
   "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc ls --recursive local/ | wc -l'
```

The encrypted volume can then be left mounted and empty, or torn down with
`systemctl stop miniodata-encrypted` + removing the unit and
`secrets/miniodata.luks`.

**Keep the tarball until a pilot's worth of traffic has run clean on the
encrypted volume.** It is the rollback, and it is the only one.

### Verifying the posture

```bash
bash scripts/check-minio-encrypted-mount.sh   # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-pg-encrypted-mount.sh      # READ-ONLY. same, for the cluster
```

It asks the only question that cannot be answered wrongly by a correct-looking
config: **what device backs the directory MinIO is writing into, right now?** It
reads `findmnt` against the *live container's* resolved volume path, plus four
supporting conditions (mount source is the dm device, `data/` present on the
encrypted fs and absent from the underlying one, unit enabled). Negative-controlled
in both directions on 2026-07-29.

⚠️ **The recipe that used to live here could not have caught the four-hour
plaintext window, and is kept below only to say why:**

```bash
lsblk -o NAME,TYPE,MOUNTPOINT | grep crypt          # ← says the volume EXISTS
docker inspect … --format '{{range .Mounts}} {{.Source}}{{end}}'
```

`docker inspect .Source` returns
`/var/lib/docker/volumes/meddoc-pro_minio_data/_data` — a path under
`/var/lib/docker`, **the same string whether that path is a bind onto dm-crypt or
a plain directory on `/dev/sda2`.** It describes docker's bookkeeping, not the
kernel's mount table. And `lsblk` showed `minio-encrypted` present with a blank
MOUNTPOINT, which reads as reassuring at a glance and is in fact the signature of
the bug.

Two distinct things have now gone wrong here, and both need checking:

1. **The volume exists but no container is on it** (MinIO, for months).
2. **A container is bound to the path but nothing is mounted there** (MinIO, for
   four hours on 2026-07-29) — strictly worse, because the config *reads* fixed.

### 5.7.2 Postgres carried the same exposure — closed 2026-07-29

Postgres used compose's short-form `- /mnt/pgdata-encrypted:/var/lib/postgresql/data`,
which **auto-creates the host path**. Its version of the failure is worse than
MinIO's:

> unmounted `/mnt/pgdata-encrypted` → docker creates an empty dir on `/dev/sda2`
> → the image finds no `PG_VERSION` → **`initdb` runs** → a brand-new empty
> cluster starts, **healthy**, on plaintext storage → the app connects to an
> empty database while the real cluster sits unmounted underneath, untouched
> and invisible.

`pg_isready` returns fine. The health check goes green. It is a silent, total,
apparently-successful data outage.

**The fix was a remap, not a data move.** The cluster already lived at
`/mnt/pgdata-encrypted/pgdata`; the volume now binds *that subdirectory* — which
exists only on the encrypted filesystem — and `PGDATA` became the mount root
instead of a subdir of it. Same physical directory, one level deeper. Nothing
was copied.

```yaml
# volumes:
pgdata_encrypted:
  driver: local
  driver_opts: { type: none, o: bind, device: /mnt/pgdata-encrypted/pgdata }
```

Verified 2026-07-29: fresh `pg_dump` taken to `backups/` and **proven restorable**
(schema-only into a throwaway — 38 tables, matching live) *before* the change;
row-count fingerprint identical across it (`audit_logs=9084 note_templates=6
patients=0 practices=196 transcribe_visits=23 users=195`); container data dir
resolves to `/dev/mapper/pg-encrypted[/pgdata]`; app healthy with a real
Postgres query through its own pool.

**Negative-controlled without touching prod data** — a throwaway compose project
replicating the volume definition, run both ways: device missing → docker
refuses and the container never runs; device present → it runs (proving the
refusal was the guard, not a syntax error).

`scripts/check-pg-encrypted-mount.sh` asserts it, including a condition MinIO's
sibling does not need: **`PG_VERSION` must be present**, because an
initdb-on-plaintext incident produces a perfectly healthy Postgres and "is it
running" therefore proves nothing.

### 5.7.3 The 10 legacy objects with no SSE-S3 — ACCEPTED, do not rewrite them

**Decided 2026-07-29. This is a recorded decision, not an open finding. Do not
re-flag it in audits, and do not "fix" it with a rewrite sweep.**

There are **two independent encryption layers** over the object store, and
conflating them is what makes this look like a hole:

| Layer | What it protects against | Covers these 10 objects? |
|---|---|---|
| **LUKS** (`/dev/mapper/minio-encrypted`) | the disk, the backing file, the host being seized or the volume being copied | **YES — all of them, unconditionally** |
| **SSE-S3** (MinIO per-object) | an attacker who already has a live authenticated path into MinIO's own data dir | no, only objects PUT after it was enabled |

`scripts/minio-enable-sse.sh` has always said it: **SSE-S3 encrypts only NEW
PUTs.** Objects written before it was switched on stay plaintext *at the object
layer* — while still sitting inside the LUKS mapping like everything else.

**What the ten actually are.** Verified against live prod on 2026-07-29 by
listing every object in every bucket and reading `X-Amz-Server-Side-Encryption`
per object — not by reading a prior report:

- `transcribe-md-audio` — **0 objects.** The patient-audio bucket is empty, so
  none of this touches audio. **It has never held one** — corrected 2026-07-29;
  the parenthetical that stood here blamed the emptiness on the §5.7.1
  re-migration, which is false and in the worst possible direction. PR #456's own
  commit message records *"the audio bucket was empty, so no patient audio was
  among the moved objects"*, its sha256 manifest **matched 33/33 before and
  after**, and all 23 prod visits carry `audioKey` = 0 / `dictationAudioKey` = 0.
  The re-migration was a verified copy that deleted nothing.

  Worth naming why one clause mattered enough to fix: it sat inside a **"do not
  re-flag it"** block, so it was written to be trusted and not re-derived — and
  it attributed a phantom loss of patient audio to the encryption work. A future
  auditor reading only this section would have found documentary evidence that
  the LUKS migration destroyed clinical data. **A cause is a claim; state it only
  when it is checked.** The fact ("0 objects") was verified; the reason for it
  was assumed, and rode along inside the verified sentence.
- `transcribe-md-template-artifacts` — 10 objects, **all ten `NONE`**:

| Count | Path | What it is |
|---|---|---|
| 5 | `pdf-native/<templateId>/canvas.pdf` | **byte-identical to each other** (one etag, 55900 B). One blank PDF form re-uploaded five times — the "active template id rotates per upload" behaviour. None of the five template ids still exists in `note_templates`; they are orphans of deleted templates |
| 2 | `template-twin/sources/**.docx` | **byte-identical to each other** (one etag, 52884 B). A *source* is an uploaded template — a BLANK form by definition |
| 3 | `template-twin/outputs/**.docx` | three distinct FILLED documents |

**The honest part: three of the ten are filled documents.** They are not
non-PHI because they are blank — they are not blank. They are non-PHI because
of **who owns them**: every one of the five `template-twin` objects sits under
practice `cmrzqiafm0000pd87qtubsj56`, which resolves to *"QuillMD Smoke Test
Practice (synthetic)"*, owner `smoke-doctor@smoke.quillmd.invalid` — the
sanctioned synthetic account, from the 2026-07-26 twin GA run. Two of the three
even carry a `synthetic_` path segment; the third
(`outputs/cms18cnct00010iqt6zfwnz31/`) has no matching row in
`transcribe_visits` at all, which is the FK-cascade-on-reseed behaviour AGENTS.md
already records.

Resolve ownership by practice, **not** by trusting a `synthetic_` filename. A
filename is a claim; a practice row is a fact.

**Why accepted rather than rewritten.** Rewriting an object to pick up SSE-S3 is
a read-then-PUT — a real mutation of the store, with real ways to go wrong — and
it would buy a second encryption layer over five copies of a blank form, a blank
template uploaded twice, and three synthetic smoke outputs that are already
under LUKS. The risk of the sweep exceeds the risk it removes.

**What would reverse this ruling.** Exactly one thing: an object with `NONE`
that belongs to a **real** doctor's practice. Then it is not a legacy artifact,
it is PHI at rest missing a layer, and it gets moved — not left. Re-check with:

```bash
# every object, with its SSE state; anything NONE, resolve its practice id
docker exec meddoc-pro-minio-1 sh -lc '
  mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1
  mc stat --recursive --json local/transcribe-md-template-artifacts'
```

Both buckets have `Auto encryption 'sse-s3' is enabled`, so **everything written
from here on is covered at both layers.** This is a closed tail, not a growing
one.

### 5.7.4 The standing post-reboot proof — it runs itself, on every boot

Added here 2026-07-29. The unit and script had been live since PR #457 and were
cited from the Rounds ledger as *"Runbook §5.7.1–5.7.2"* — **sections that never
mentioned them.** A production safety mechanism documented only in a project
ledger is documented for the wrong reader.

**What it is.** `quillmd-postreboot-proof.service` (enabled, `After=docker.service`,
90 s settle) runs `scripts/verify-post-reboot.sh` on **every** boot, writes
`/var/log/quillmd-postreboot-proof.<UTC>.log` plus a `.latest.log` symlink, and
does **not** swallow the exit code — a bad proof shows up in `systemctl --failed`.
It therefore also covers the **unplanned** hypervisor resets this host is known
for, the ones nobody is awake for.

**Why it has to record itself.** Claude Code runs *on this host*, so a reboot
kills the session that would otherwise verify it. The proof cannot be both
triggered and observed from inside a session.

```bash
cat /var/log/quillmd-postreboot-proof.latest.log     # expect a trailing exit=0
systemctl --failed                                   # expect empty
bash scripts/verify-post-reboot.sh                   # re-runnable at any time
bash scripts/test-verify-post-reboot.sh              # negative controls for the above
```

**What it asserts**, in order: both LUKS units started **at boot** (not by hand) ·
both mappings open · both mounts live on their dm devices · Postgres and MinIO
healthy **on those devices** · both fail-closed guards intact · prod stack
complete · `quillmd.com` 200 · co-tenants up · and the two known reboot side
effects surfaced rather than discovered.

**§1 is the load-bearing one, and the only one immune to a stale artefact.** It
compares each unit's `ActiveEnterTimestamp` against boot time (120 s grace)
rather than asking "is it active", so it fails on a hand start and on a
no-reboot alike — and it stays valid however long afterwards you re-run it. When
this script and a written claim disagree, **the script wins**.

**Read the container sections with their history in mind.** §4 and §6 reported
success on states that needed action until 2026-07-29 — §4 printed *"every
meddoc-pro container is up"* against **zero** containers and could not see an
`unhealthy` one; §6 printed *"QA stack: 1 container(s) up"* with five of six
down. Both now derive the expected service set from the compose files and name
what is missing, and `scripts/test-verify-post-reboot.sh` pins that they can
still go red. If you change either section, run that harness — it fails 7/7
against the pre-fix script, which is the only reason to believe it works.

**The two side effects are expected, not faults:** the QA stack does not
self-restart (only `gotenberg` is `unless-stopped`; the other five are
`restart: "no"`) — bring it back with
`docker compose -f docker-compose.qa.yml up -d` and **then** re-run
`scripts/check-qa-mock-posture.sh`, which reads live containers and means nothing
while they are down. And a reboot **clears `/tmp`**, so an empty `/tmp` after a
boot is never evidence that the previous session reaped its scratch.

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
