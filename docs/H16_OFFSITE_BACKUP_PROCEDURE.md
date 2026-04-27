# H16 — Offsite backup runbook

*Closes h16-offsite-backup once Hetzner Object Storage credentials are
in place on the VPS.*

The Phase 16 deep audit flagged that postgres backups live at
`/opt/meddoc-pro/backups` on the same VPS as postgres. If the VPS is
destroyed (cloud-instance loss, hardware failure, account compromise)
both DB and backups are gone.

This procedure adds a daily mirror of `/backups/last/` to S3-compatible
offsite storage. Local backup behaviour is unchanged.

---

## A. Provision the bucket (Hetzner Console)

1. https://console.hetzner.cloud → `meddoc-pro` project
2. **Object Storage → Create**
3. Settings:
   - Location: same data centre as the VPS (`nbg1` typical)
   - Name: `meddoc-backup-prod`
   - Public access: **disabled**
   - Versioning: **enabled** (recommended — protects against ransomware
     overwriting the live backup file)
4. After creation, **Tokens → Generate** and save:
   - Access Key
   - Secret Key
   - Endpoint URL — usually `https://<region>.your-objectstorage.com`

Cost: ~€1/month for 10 GB at Hetzner's current pricing. The pilot DB
backup is ~1.5 MB/day, so you'll never approach 10 GB in the first six
months.

Alternatives that work the same way (script is endpoint-agnostic): AWS
S3, Backblaze B2, Wasabi, Cloudflare R2, MinIO-on-another-host.

## B. Wire credentials into `.env`

```bash
ssh root@meddoc-pro
cd /opt/meddoc-pro

cat >> .env <<'EOF'

# h16-offsite-backup — Hetzner Object Storage push
REMOTE_BACKUP_S3_ENDPOINT=https://nbg1.your-objectstorage.com
REMOTE_BACKUP_S3_BUCKET=meddoc-backup-prod
REMOTE_BACKUP_S3_ACCESS_KEY=<paste from console>
REMOTE_BACKUP_S3_SECRET_KEY=<paste from console>
REMOTE_BACKUP_S3_REGION=nbg1
EOF

# Lock down
chmod 600 .env
```

## C. Restart the backup sidecar so it picks up the new env

```bash
docker compose up -d --no-deps postgres-backup
docker logs --tail 20 meddoc-pro-postgres-backup-1
```

The container only consumes the env at start; restart is required.

## D. Trigger a backup + verify

```bash
# Force a backup right now (the schedule is daily; don't wait).
docker exec meddoc-pro-postgres-backup-1 sh -c '/backup.sh'

# Watch the postscript run — first invocation downloads mc to
# /backups/.mc-bin (cached after that), then mirrors.
docker logs --tail 50 meddoc-pro-postgres-backup-1 | grep postscript
```

Expected log lines:

```
[postscript] downloading mc...
[postscript] offsite mirror complete: https://nbg1.your-objectstorage.com/meddoc-backup-prod/last/
```

If you see `[postscript] REMOTE_BACKUP_* not set — skipping offsite
push.` instead, one or more env vars didn't reach the container.
Re-check the `.env` write and re-run `docker compose up -d --no-deps
postgres-backup`.

## E. Confirm in the bucket

```bash
# From your laptop — use mc, AWS CLI, or the Hetzner console UI.
mc alias set meddoc \
  https://nbg1.your-objectstorage.com \
  $REMOTE_BACKUP_S3_ACCESS_KEY $REMOTE_BACKUP_S3_SECRET_KEY
mc ls meddoc/meddoc-backup-prod/last/
```

You should see today's `meddoc-<date>-000000.sql.gz` and the
`meddoc-latest.sql.gz` symlink target.

## F. Restore drill from offsite

```bash
# Pull the offsite copy
mc cp meddoc/meddoc-backup-prod/last/meddoc-latest.sql.gz /tmp/offsite-restore.sql.gz

# Restore into ephemeral pg
docker run -d --name pg-offsite-restore \
  -e POSTGRES_USER=meddoc -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=meddoc -p 15434:5432 pgvector/pgvector:pg16
sleep 8
gunzip -c /tmp/offsite-restore.sql.gz | \
  docker exec -i pg-offsite-restore psql -U meddoc -d meddoc
docker exec pg-offsite-restore psql -U meddoc -d meddoc -c \
  "SELECT 'users' AS t, COUNT(*) FROM users
   UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;"
docker stop pg-offsite-restore && docker rm pg-offsite-restore
rm /tmp/offsite-restore.sql.gz
```

Row counts should match the local restore drill from
`docs/PHASE_16_DEEP_AUDIT_RESULTS.md` Section E.

## G. Resolve the finding

Once `D` and `E` succeed and Section F restore drill row-counts match,
mark `h16-offsite-backup` resolved:

```bash
rm -f /tmp/qa-cookies.txt
CSRF=$(curl -sk -c /tmp/qa-cookies.txt --resolve admin.quillmd.com:443:127.0.0.1 \
  https://admin.quillmd.com/api/auth/csrf | jq -r '.csrfToken')
curl -sk -b /tmp/qa-cookies.txt -c /tmp/qa-cookies.txt -X POST \
  --resolve admin.quillmd.com:443:127.0.0.1 \
  -d "csrfToken=$CSRF&email=qa-audit@quillmd.local&password=QaTestPassword2024!&callbackUrl=/admin&redirect=false" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -o /dev/null https://admin.quillmd.com/api/auth/callback/credentials

curl -sk -b /tmp/qa-cookies.txt -X POST --resolve admin.quillmd.com:443:127.0.0.1 \
  -H "Content-Type: application/json" \
  -d '{"note":"Hetzner Object Storage offsite mirror live; first push verified at <date>; restore drill from offsite verified row counts match."}' \
  https://admin.quillmd.com/api/admin/hipaa/h16-offsite-backup/resolve
```

## H. Operational notes

- The `mc` binary is cached at `/backups/.mc-bin` on first run. If
  Hetzner changes the URL or the binary signature breaks, delete the
  file and the next backup will re-download.
- The `mc mirror` runs with `--overwrite` — newer local copies replace
  the offsite version. With versioning enabled at the bucket, prior
  versions are still accessible via the Hetzner console.
- A network outage during the postscript will exit non-zero. The local
  backup still succeeds; only the offsite push is missed for that day.
  The next day's run picks up where this one left off (mirror is
  idempotent).
- If the VPS itself is compromised, the bucket credentials in `.env`
  are also compromised — the attacker could delete remote backups. With
  versioning enabled, deletes are recoverable for the bucket's
  retention window. Consider a separate read-only audit account that
  only your laptop holds for periodic out-of-band verification.
