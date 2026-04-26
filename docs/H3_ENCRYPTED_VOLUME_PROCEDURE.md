# H3 — Hetzner managed encrypted volume migration procedure

*Phase 13. The procedure for closing `h8-h3-pilot-followup`.*

This document is the runbook. Follow it on a planned maintenance window
(estimated ~30-45 min downtime). All steps either need root on the host
or Hetzner Cloud Console / API access — neither available to the
in-VPS automation, so this is a documented hand-off rather than an
auto-runnable script.

---

## A. Pre-flight (do these first, in order)

```bash
# 1. Take a fresh full backup outside the volume that's about to move.
docker exec meddoc-pro-postgres-1 pg_dump -U meddoc -Fc meddoc > /root/pre-h3-migration-$(date -u +%Y%m%d-%H%M%S).dump
ls -lh /root/pre-h3-migration-*.dump

# 2. Snapshot via Hetzner Cloud Console:
#    Servers → meddoc-pro → Snapshots → Create snapshot
#    Label: "pre-h3-encrypted-volume-migration"
#    This is the safety net. If anything below goes wrong, restore
#    the entire VPS from this snapshot.

# 3. Capture current state for diff comparison post-migration
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT 'users' AS t, COUNT(*) FROM users
  UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
  UNION ALL SELECT 'transcribe_visits', COUNT(*) FROM transcribe_visits
  UNION ALL SELECT 'api_usage_events', COUNT(*) FROM api_usage_events
  UNION ALL SELECT 'hipaa_findings', COUNT(*) FROM hipaa_findings;
" > /root/pre-h3-rowcounts.txt
cat /root/pre-h3-rowcounts.txt
```

## B. Provision the encrypted volume (Hetzner Cloud Console / hcloud CLI)

**Option 1 — Hetzner Cloud Console (UI)**

1. Log into https://console.hetzner.cloud
2. Select the `meddoc-pro` project
3. Volumes → Create Volume
4. Settings:
   - Location: same data center as the VPS (e.g. `nbg1`)
   - Name: `meddoc-encrypted`
   - Size: **50 GB** (current postgres ~150MB + minio ~160MB + audit-log growth headroom for first year of pilot)
   - Format: `ext4`
   - **Encryption: enabled** (Hetzner-managed LUKS, key held by Hetzner, unlocked at boot)
   - Server: attach to `meddoc-pro` VPS
   - Mount automatically: yes (mount path `/mnt/encrypted`)
5. Wait for "Mounted" status (~30s)

**Option 2 — hcloud CLI** (install first: `apt install hcloud-cli`)

```bash
hcloud volume create \
  --name meddoc-encrypted \
  --size 50 \
  --location nbg1 \
  --format ext4 \
  --automount \
  --server meddoc-pro

# Verify mount
lsblk -o NAME,FSTYPE,LABEL,MOUNTPOINT,SIZE
mount | grep encrypted
```

After provisioning, `lsblk` should show the new volume mounted at
`/mnt/encrypted`. Hetzner-managed encryption uses LUKS under the
hood; the key is held by Hetzner and unlocked at boot. Acceptable
for HIPAA Safe Harbor per the published Hetzner attestation.

## C. Migrate data to the encrypted volume

```bash
# Stop everything that writes to postgres or minio
cd /opt/meddoc-pro
docker compose stop transcribe-md transcribe-md-worker meddoc-pro marketing minio
docker compose stop postgres-backup postgres

# rsync postgres data dir
sudo rsync -aHAXxv --info=progress2 \
  /var/lib/docker/volumes/meddoc-pro_postgres_data/_data/ \
  /mnt/encrypted/postgres-data/

# rsync minio data dir
sudo rsync -aHAXxv --info=progress2 \
  /var/lib/docker/volumes/meddoc-pro_minio_data/_data/ \
  /mnt/encrypted/minio-data/

# Verify size matches
du -sh /var/lib/docker/volumes/meddoc-pro_postgres_data/_data/ \
       /mnt/encrypted/postgres-data/
du -sh /var/lib/docker/volumes/meddoc-pro_minio_data/_data/ \
       /mnt/encrypted/minio-data/

# Preserve uid/gid (postgres expects 999, minio 1000)
sudo chown -R 999:999 /mnt/encrypted/postgres-data
sudo chown -R 1000:1000 /mnt/encrypted/minio-data
```

## D. Update docker-compose.yml volume bindings

Replace the current named-volume entries at the bottom of
`docker-compose.yml`:

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/encrypted/postgres-data
  minio_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/encrypted/minio-data
  # caddy_data, redis_data, caddy_config — KEEP AS-IS
  # (those are state, not PHI; encrypted-at-rest scope is just
  # postgres + minio for the pilot launch)
```

Then bring services back:

```bash
docker compose up -d
until docker inspect meddoc-pro-postgres-1 --format '{{.State.Health.Status}}' | grep -q healthy; do sleep 3; done
until docker inspect meddoc-pro-minio-1 --format '{{.State.Health.Status}}' | grep -q healthy; do sleep 3; done
```

## E. Verify

```bash
# Data integrity — row counts must match the pre-migration snapshot
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT 'users' AS t, COUNT(*) FROM users
  UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
  UNION ALL SELECT 'transcribe_visits', COUNT(*) FROM transcribe_visits
  UNION ALL SELECT 'api_usage_events', COUNT(*) FROM api_usage_events
  UNION ALL SELECT 'hipaa_findings', COUNT(*) FROM hipaa_findings;
" > /root/post-h3-rowcounts.txt
diff /root/pre-h3-rowcounts.txt /root/post-h3-rowcounts.txt
# Expected: zero diff

# MinIO bucket — content intact
docker exec meddoc-pro-minio-1 mc alias set local http://127.0.0.1:9000 \
  $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD
docker exec meddoc-pro-minio-1 mc ls local/transcribe-md-audio | head -5

# Encryption proof
mount | grep encrypted
lsblk -o NAME,FSTYPE,MOUNTPOINT,SIZE
cryptsetup status $(mount | grep '/mnt/encrypted' | awk '{print $1}') | head -10

# Production smoke
for h in app pro admin; do
  curl -sk -o /dev/null -w "$h.quillmd.com csrf=%{http_code} time=%{time_total}s\n" \
    --resolve $h.quillmd.com:443:127.0.0.1 \
    https://$h.quillmd.com/api/auth/csrf
done

# Test suites
node /tmp/admin-audit.mjs 2>&1 | tail -5
node /tmp/test-flows.mjs 2>&1 | tail -5
```

## F. Resolve the finding via the dashboard

After everything is green, mark `h8-h3-pilot-followup` resolved with
a note that includes the encryption-status output:

```bash
rm -f /tmp/qa-cookies.txt
CSRF=$(curl -sk -c /tmp/qa-cookies.txt --resolve admin.quillmd.com:443:127.0.0.1 \
  https://admin.quillmd.com/api/auth/csrf | jq -r '.csrfToken')
curl -sk -b /tmp/qa-cookies.txt -c /tmp/qa-cookies.txt -X POST \
  --resolve admin.quillmd.com:443:127.0.0.1 \
  -d "csrfToken=$CSRF&email=qa-audit@quillmd.local&password=QaTestPassword2024!&callbackUrl=/admin&redirect=false" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -o /dev/null https://admin.quillmd.com/api/auth/callback/credentials

ENCRYPTION_PROOF=$(cryptsetup status $(mount | grep '/mnt/encrypted' | awk '{print $1}') | head -10 | tr '\n' ' ')
curl -sk -b /tmp/qa-cookies.txt -X POST --resolve admin.quillmd.com:443:127.0.0.1 \
  -H "Content-Type: application/json" \
  -d "{\"note\":\"Migrated postgres + minio data volumes to Hetzner managed encrypted volume at /mnt/encrypted. Encryption proof: $ENCRYPTION_PROOF\"}" \
  https://admin.quillmd.com/api/admin/hipaa/h8-h3-pilot-followup/resolve
```

## G. Rollback (if any step in C/D/E fails)

```bash
# 1. Revert docker-compose.yml volumes section to the original
#    named-volume form
git checkout HEAD~1 -- docker-compose.yml

# 2. Bring services back on the original volumes
docker compose up -d

# 3. If postgres data corrupted somehow, restore from
#    /root/pre-h3-migration-*.dump:
docker exec meddoc-pro-postgres-1 psql -U meddoc -d postgres \
  -c "DROP DATABASE meddoc;"
docker exec meddoc-pro-postgres-1 psql -U meddoc -d postgres \
  -c "CREATE DATABASE meddoc;"
docker exec -i meddoc-pro-postgres-1 pg_restore -U meddoc -d meddoc \
  < /root/pre-h3-migration-<timestamp>.dump
```

## H. Cost note

A 50GB Hetzner managed encrypted volume is roughly €2.50/month
(Apr 2026 pricing). For pilot scale (5 doctors × ~30 visits/day ×
audio + transcripts), this is ample headroom for the first 6
months. Re-evaluate sizing before expanding past pilot.
