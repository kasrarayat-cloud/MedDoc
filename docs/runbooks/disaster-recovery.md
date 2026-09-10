# Disaster recovery runbook

**Purpose:** documented procedure for restoring service after major data-loss events. Operationalizes HIPAA §164.308(a)(7) (contingency plan) requirements.

**Owner:** Kasra. **Last reviewed:** 2026-05-05.

This is the page operator opens when something is *gone*, not just *broken*. For "broken" → see `incident-response.md`. For "Postgres role won't connect" → `postgres-recovery.md`.

---

## §1 — Recovery objectives

| Metric | Pre-pilot target | Post-launch target |
|---|---|---|
| **RTO** (recovery time) | < 4 hours | < 1 hour |
| **RPO** (recovery point) | < 24 hours (daily backup) | < 1 hour (continuous backup, Phase 7+) |
| **Drill cadence** | Once before pilot launch | Quarterly |

The pre-pilot targets are what's achievable today with Phase 6.1 daily local backups + Phase 6.2 (in-flight) encrypted offsite. Post-launch targets require continuous backup (e.g., WAL archiving) which is Phase 7 scope.

---

## §2 — Backup inventory

What we currently have, where it lives, and what it covers:

| Backup | Source | Destination | Frequency | Retention | Encryption | Phase | Status |
|---|---|---|---|---|---|---|---|
| Postgres logical dump | `meddoc` DB | `/opt/meddoc-pro/backups/last/` (host volume) | Daily (postgres-backup sidecar) | 30 days | gzip; LUKS-at-rest via Phase 6.1 | 6.1 | ✅ Active |
| Postgres encrypted offsite | `/opt/meddoc-pro/backups/last/` | Backblaze B2 via age-encryption | Daily (host cron) | 30 days B2 lifecycle | age (asymmetric, private key offline) | 6.2 | 🟡 Scripts shipped (PR #110); activation pending Backblaze BAA + bucket creation |
| MinIO encrypted offsite | `transcribe-md-audio` bucket | Backblaze B2 via age-encryption + tar | Daily (host cron) | 30 days B2 lifecycle | age | 6.2 | 🟡 Same as Postgres path; same activation gate |
| Source code | `main` branch | GitHub | On every push | Forever | TLS in transit; GitHub at-rest | N/A | ✅ Active |
| Secrets | `/opt/meddoc-pro/.env` | Operator's Bitwarden | Per rotation | Bitwarden retention | Bitwarden vault encryption | N/A | ✅ Active per Round 3 PR-A |
| Public/private offsite-backup keypair | `age-keygen` on offline laptop | Bitwarden + fireproof safe (paper backup) | One-time at Phase 6.2 setup | Forever | At-rest in Bitwarden | 6.2 | 🟡 Pending Phase 6.2 activation |

### What's NOT backed up (and why)

- **Redis** — ephemeral session state + BullMQ queue. Re-derivable from Postgres on restart. Losing Redis = brief queue replay; not a recovery scenario.
- **Container images** — rebuilt from source. GitHub holds the truth.
- **`/var/log/*`** — captured by Sentry where it matters; rest is operational only.

---

## §3 — Recovery scenarios

### A. Single container down (90% of incidents — should never reach this runbook)

```bash
docker compose up -d --force-recreate <service>
docker compose ps
```

If health doesn't return within 60s, see `incident-response.md` §3.

### B. Postgres data volume corrupted

Symptoms: postgres container restart-loops; `psql` returns "could not access status of transaction" or "invalid page in block".

**RTO target:** ~30 min (local restore)

```bash
# 1. Stop the cluster
docker compose stop postgres transcribe-md transcribe-md-worker marketing

# 2. Identify the most recent good backup
ls -la /opt/meddoc-pro/backups/last/
# postgres-backup sidecar leaves files like:
#   meddoc-2026-05-05T03:00:00.sql.gz
#   meddoc-2026-05-04T03:00:00.sql.gz
# (latest = most recent successful daily run)

# 3. Move the corrupted volume aside (don't delete; forensics)
mv /var/lib/docker/volumes/meddoc-pro_pgdata /var/lib/docker/volumes/meddoc-pro_pgdata.corrupt-$(date +%Y%m%d)

# 4. Start postgres with empty data dir (re-runs init script)
docker compose up -d postgres
sleep 15
docker compose ps postgres   # confirm "healthy"

# 5. Restore from the backup
LATEST=$(ls -t /opt/meddoc-pro/backups/last/meddoc-*.sql.gz | head -1)
gunzip -c "$LATEST" \
  | docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc

# 6. Re-apply pending migrations (in case backup pre-dates them)
cd /opt/meddoc-pro
docker run --rm \
  --network meddoc-pro_default \
  -v /opt/meddoc-pro/packages/db/prisma/migrations:/app/packages/db/prisma/migrations:ro \
  -v /opt/meddoc-pro/packages/db/prisma/schema.prisma:/app/packages/db/prisma/schema.prisma:ro \
  -e "DATABASE_URL=postgresql://meddoc:$(grep '^DB_PASSWORD=' .env | cut -d= -f2-)@postgres:5432/meddoc?schema=public" \
  -w /app/packages/db meddoc-pro-db-migrate \
  /app/node_modules/.bin/prisma migrate deploy

# 7. Restart app tier
docker compose up -d transcribe-md transcribe-md-worker marketing

# 8. Verify
docker compose ps
curl -sI https://app.quillmd.com
```

**Data loss:** anything written between the last backup and the corruption (up to ~24 hours pre-pilot). Document in incident post-mortem.

### C. MinIO bucket corrupted / lost

Symptoms: audio playback returns 5xx; `docker exec minio mc ls local/transcribe-md-audio` errors.

**RTO target:** depends on Phase 6.2 status.

**Phase 6.2 NOT yet active** (current state):
- Local restore is not possible (no MinIO local backup; volume IS the only copy)
- Pre-pilot acceptable because no live PHI yet
- Post-pilot blocker — Phase 6.2 must activate before pilot

**Phase 6.2 active** (target state):
```bash
# 1. Stop services that read MinIO
docker compose stop transcribe-md transcribe-md-worker

# 2. Pull the most recent encrypted MinIO backup from B2
b2 file download b2://meddoc-offsite-backups/<latest-minio-archive>.tar.age \
  /tmp/minio-restore.tar.age

# 3. Decrypt with the offline private key
age --decrypt --identity /tmp/offline-private.age \
  /tmp/minio-restore.tar.age > /tmp/minio-restore.tar
# (Bring the offline private key in via 1Password export onto a one-shot
# USB stick. Do NOT leave it on the VPS after restore.)

# 4. Recreate the bucket + restore objects
docker exec meddoc-pro-minio-1 mc mb local/transcribe-md-audio
docker cp /tmp/minio-restore.tar meddoc-pro-minio-1:/tmp/
docker exec meddoc-pro-minio-1 sh -c '
  cd /tmp && tar xf minio-restore.tar
  mc cp --recursive transcribe-md-audio/* local/transcribe-md-audio/
'

# 5. Wipe the temporary plaintext
shred -u /tmp/minio-restore.tar /tmp/minio-restore.tar.age
docker exec meddoc-pro-minio-1 rm -f /tmp/minio-restore.tar

# 6. Restart app tier
docker compose up -d transcribe-md transcribe-md-worker
```

### D. Full VPS lost

Symptoms: ssh to host returns nothing; Zap Hosting dashboard shows server unreachable.

**RTO target:** ~3 hours pre-pilot (depends on B2 + Bitwarden access). Phase 7 multi-region target: < 1 hour.

**Phase 6.2 NOT yet active:** **DATA LOSS UP TO LAST DAILY BACKUP** (the local pg_dump is on the same host; if the host is gone, so is the backup). Pre-pilot acceptable; post-pilot blocker.

**Phase 6.2 active** (target state):
```bash
# 1. Provision new VPS (Zap Hosting, same Ubuntu version)
#    Note the new public IP

# 2. Update DNS (Cloudflare or registrar)
#    app.quillmd.com → new IP
#    quillmd.com → new IP

# 3. Install Docker + docker-compose on the new host

# 4. Clone the repo
git clone https://github.com/kasrarayat-cloud/MedDoc.git /opt/meddoc-pro
cd /opt/meddoc-pro

# 5. Restore .env from Bitwarden
# (manual paste into /opt/meddoc-pro/.env, mode 600, owner claude:claude)

# 6. Restore Postgres from the most recent encrypted B2 archive
b2 file download b2://meddoc-offsite-backups/<latest-pg>.sql.gz.age /tmp/pg.sql.gz.age
age --decrypt --identity /tmp/offline-private.age /tmp/pg.sql.gz.age \
  | gunzip > /tmp/pg.sql

# 7. Bring up postgres alone, restore
docker compose up -d postgres
sleep 15
docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc < /tmp/pg.sql

# 8. Restore MinIO (per scenario C, steps 2-5)

# 9. Bring up the rest
docker compose up -d

# 10. Smoke + reset operator-facing creds (some may have been in
#     post-rotation state per ROTATION_RUNBOOK.md)
curl -sI https://app.quillmd.com
```

**Data loss:** anything since the last successful B2 upload (typically < 24 hours).

### E. DNS hijack / domain compromise

Symptoms: `dig app.quillmd.com` returns wrong IP; certificate errors in browser; user reports phishing-like login page.

```bash
# 1. Contact registrar IMMEDIATELY (lock the domain)

# 2. Rotate every DNS record affected (A, AAAA, MX, TXT)

# 3. Pull updated DNS from registrar console

# 4. Document attack vector for post-mortem (was an admin account
#    compromised? Did MFA fail? Was social engineering involved?)

# 5. If TLS certs were issued under attacker control:
#    - Revoke via the cert provider (e.g., Let's Encrypt)
#    - Re-issue under new auth flow
#    - Consider CAA record locking
```

This is rare but high-impact. Post-pilot: enable registrar-level 2FA + DNSSEC + CAA records.

### F. Region / Zap Hosting outage

Symptoms: Zap Hosting status page shows region down; ssh fails; DNS resolves but no response.

**Pre-pilot:** wait for region to come back up. RTO is whatever Zap takes (historically <4 hours for them).

**Phase 7 multi-region plan** (deferred): cold standby in a secondary host (e.g., Hetzner). Manual failover via DNS update. RTO target ~30 min once we own the standby playbook.

### G. Backblaze B2 compromised / unavailable

Symptoms: B2 console shows breach notification or service is down for an extended period.

- The backups themselves are age-encrypted. Even if Backblaze leaks the bucket contents, attackers cannot decrypt without the offline private key. **No PHI exposure.**
- For active operations: rotate B2 credentials, switch to a secondary destination if needed.
- The age private key never lives on the VPS, so there is no operational way for an attacker who compromised the VPS to decrypt the offsite copies.

---

## §4 — Drill schedule

### Pre-pilot drill (mandatory before launch)

Once Phase 6.2 is activated:

1. Provision a throwaway VPS (Zap Hosting, smallest tier)
2. Run scenario D end-to-end against the throwaway
3. Time the wall-clock from "host is fresh Ubuntu" to "https://app.quillmd.com on new IP returns 307"
4. Document RTO actual; if > 4 hours, identify what slowed it down
5. Tear down throwaway
6. Add the actual RTO to this runbook's §1 table

### Quarterly drill (post-pilot)

Once team grows beyond single-engineer:

- Q1: Postgres restore drill (scenario B)
- Q2: MinIO restore drill (scenario C)
- Q3: Full VPS rebuild drill (scenario D)
- Q4: Tabletop incident (scenario E or F — discussion-only)

Each drill produces a `docs/drills/<YYYY-Q#>-<scenario>.md` post-mortem.

---

## §5 — When backups themselves are the suspect

If you see `audit_logs` entries for `EXPORTED_AUDIT_LOG` from unexpected times, or B2 bucket showing access from unexpected IPs:

1. Do NOT restore from a potentially-compromised backup blindly. The attacker may have planted backdoor entries.
2. Pick a backup from a date EARLIER than any suspicious activity.
3. Restore to a throwaway environment first; diff against current production for unexpected rows.
4. Only restore to production after diff is clean.

This is paranoid but cheap. Saves a SEV-1 from becoming a SEV-0.

---

## §6 — References

- `docs/runbooks/incident-response.md` — for "broken" rather than "gone" scenarios
- `docs/runbooks/postgres-recovery.md` — for Postgres-role-level issues
- `docs/runbooks/edge-security.md` — for sshd/UFW/fail2ban operator runbook
- `docs/RUNBOOK_OFFSITE_BACKUP.md` — Phase 6.2 activation steps + key custody
- `docs/COMPLIANCE_REGISTER.md` — subprocessor BAA matrix
- `docs/POST_MERGE_TODO.md §22` — Phase 6.2 status
