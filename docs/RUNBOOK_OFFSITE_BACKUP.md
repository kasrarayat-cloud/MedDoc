# Runbook — Encrypted Offsite Backup (Backblaze B2 + age)

*Closes HIPAA finding **h16** — geographically-distinct offsite backup copy
with at-rest encryption.*

This runbook covers the **encrypted** offsite backup path (Backblaze B2
with `age` client-side encryption). It is independent of, and complementary
to, the unencrypted Hetzner Object Storage mirror documented in
`docs/H16_OFFSITE_BACKUP_PROCEDURE.md`. Operators may run either, both, or
replace one with the other.

| Aspect | This runbook (B2 + age) | H16_OFFSITE_BACKUP_PROCEDURE.md (Hetzner) |
|---|---|---|
| Provider | Backblaze B2 | Hetzner Object Storage |
| Encryption | Client-side (age) before upload | Bucket-level only (provider-managed) |
| BAA required | **Yes — sign with Backblaze** | Hetzner has no HIPAA BAA |
| Use when | HIPAA-bound deployments (US, covered entity) | EU operational mirror, cost-floor only |

For HIPAA-bound deployments, **use this path**. The unencrypted mirror is
fine for operational redundancy on non-PHI workloads.

---

## A. One-time setup

### A.1 Sign a BAA with Backblaze

1. Email `compliance@backblaze.com` from a deployment-owner address (the
   one associated with the B2 account that will hold the bucket).
2. Reference your Backblaze account ID and the bucket name you intend to
   use (e.g. `meddoc-offsite-backups-prod`).
3. Wait for the countersigned BAA. **Do not populate credentials before
   the BAA is in your inbox** — uploading PHI to a non-BAA-covered bucket
   is itself a HIPAA breach even if the data is encrypted at rest.
4. File the countersigned BAA in your compliance binder. Audit-tracker
   reviewers will ask for the date.

### A.2 Create the B2 bucket

In the B2 console (https://secure.backblaze.com/b2_buckets.htm):

1. **Create a Bucket**
2. Settings:
   - **Bucket Name**: `meddoc-offsite-backups-prod`
     (must match `BACKBLAZE_BUCKET` in `.env`)
   - **Files in Bucket are**: Private
   - **Default Encryption**: SSE-B2 (AES-256, server-side) — this is
     defence-in-depth on top of our client-side `age` encryption
   - **Object Lock**: **OFF** (object lock incompatibility with our
     30-day retention policy; bucket lifecycle handles deletion)
3. After creation, open **Lifecycle Rules** for the bucket:
   - Add rule: **Keep only the last 30 days of versions**
     - "Keep only the most recent version" → unchecked
     - "Hide files older than" → 30 days
     - "Delete files older than" → 35 days (5-day grace after hide)

The script also prunes locally; the bucket-level rule is belt-and-braces
for the case where the script's prune step fails or the credentials lose
delete capability.

### A.3 Create an Application Key

In **App Keys** (https://secure.backblaze.com/app_keys.htm):

1. **Add a New Application Key**
2. Settings:
   - **Name**: `meddoc-offsite-backup-writer`
   - **Allow access to Bucket(s)**: select `meddoc-offsite-backups-prod`
     (NOT "All buckets" — the key must be scoped)
   - **Type of Access**: **Read and Write**
   - **Allow List All Bucket Names**: **Yes** (the script's `b2 ls`
     prune step needs this)
   - **File name prefix**: leave blank (script uses date-based prefixes)
   - **Duration**: leave blank (no expiry — rotate on schedule, not by TTL)
3. Click **Create**. The next page shows:
   - **keyID** → goes into `BACKBLAZE_KEY_ID`
   - **applicationKey** → goes into `BACKBLAZE_APPLICATION_KEY`
4. **Copy both NOW** — `applicationKey` is shown exactly once and is
   unrecoverable if you click away.

### A.4 Install B2 CLI + age on the VPS

The postgres-backup container's image (prodrigestivill/postgres-backup-local)
ships neither tool. Two options:

**Option 1 (recommended) — install in a derived image.** Add a Dockerfile
that extends the upstream and installs `age` + `b2`. Out of scope for this
runbook; track in `docs/POST_MERGE_TODO.md`.

**Option 2 (operator's choice for the immediate landing) — install on the
host and bind-mount.** The compose file already mounts `/var/log/meddoc`
and `/etc/meddoc`; you can also bind-mount `/usr/local/bin` if the host
has the binaries. This is host-coupled and not preferred long-term.

For the BAA-pending phase, the script's safe-state behaviour (exit 78 when
tools are missing) means landing it without either install path is OK —
the local pg_dump still runs.

### A.5 Generate the age keypair

The script generates the keypair automatically on first run, but a safer
flow is to generate it **OFFLINE** on a clean workstation, then copy only
the public key onto the VPS. The private key never touches the production
host:

```bash
# On an offline machine (e.g. air-gapped laptop)
age-keygen -o offsite-backup-private.age
# This writes:
#   offsite-backup-private.age (mode 600)
# and prints "Public key: age1..." to stderr — record it.

# Extract just the public key into a separate file
grep '^# public key:' offsite-backup-private.age | sed 's/^# public key: //' \
  > offsite-backup-public.age

# Copy ONLY the public key to the VPS:
scp offsite-backup-public.age root@<vps>:/etc/meddoc/offsite-backup-public.age

# On the VPS:
chmod 0444 /etc/meddoc/offsite-backup-public.age

# Archive the private key in your offline secret store (1Password Vault,
# physical safe, etc). Do NOT copy it to the VPS — restoration will pull
# it from offline storage when needed.
```

If the operator skips this and lets the script generate the keypair on
the VPS itself, the private key sits at `/etc/meddoc/offsite-backup-private.age`
chmod 0400 root-owned. That's still secure against anything short of a
host-level compromise, but the air-gap option is better.

### A.6 Populate `.env`

```bash
ssh root@<vps>
cd /opt/meddoc-pro

# Append to existing .env (mode 600). DO NOT replace .env wholesale.
cat >> .env <<'EOF'

# h16-offsite-backup (encrypted variant) — added <YYYY-MM-DD>
BACKBLAZE_KEY_ID=<keyID from A.3>
BACKBLAZE_APPLICATION_KEY=<applicationKey from A.3>
BACKBLAZE_BUCKET=meddoc-offsite-backups-prod
EOF

# Verify mode
chmod 600 .env
ls -la .env  # → -rw------- 1 root root ...
```

### A.7 Wire the script into the postgres-backup container

The compose file already bind-mounts `infra/backup-offsite-sync.sh` to
`/scripts/backup-offsite-sync.sh:ro`. To have it run after every pg_dump,
chain it from the existing postscript:

Edit `infra/postgres-backup/postscript.sh` and append:

```bash
# h16-offsite-backup (encrypted) — chained after the unencrypted mirror
if [[ -x /scripts/backup-offsite-sync.sh ]]; then
  /scripts/backup-offsite-sync.sh || {
    rc=$?
    if [[ $rc -eq 78 ]]; then
      echo "[postscript] backup-offsite-sync.sh skipped (config not ready)" >&2
    else
      echo "[postscript] backup-offsite-sync.sh failed with code $rc" >&2
      # Do NOT exit non-zero here — local backup already succeeded; the
      # encrypted offsite leg is best-effort.
    fi
  }
fi
```

(This wiring is intentionally NOT done in the h16 branch — it's an
operator decision because of the install-tools-first prerequisite. Track
the postscript chaining as a follow-up after A.4 lands.)

### A.8 Restart the sidecar

```bash
docker compose up -d --force-recreate postgres-backup
docker logs --tail 20 meddoc-pro-postgres-backup-1
```

---

## B. First-run verification

### B.1 Trigger a manual backup

```bash
docker exec meddoc-pro-postgres-backup-1 sh -c '/backup.sh'
```

### B.2 Watch the offsite sync

```bash
tail -f /var/log/meddoc/offsite-backup.log
```

Expected sequence (each line prefixed `[<UTC ISO timestamp>]`):

```
INFO: backup-offsite-sync.sh starting
INFO: latest dump: /backups/last/meddoc-<dow>.sql.gz
INFO: authorizing B2 CLI
INFO: encrypting /backups/last/meddoc-<dow>.sql.gz (NNNN bytes, sha256=abc123def...)
INFO: encrypted blob is MMMM bytes; uploading to b2://meddoc-offsite-backups-prod/meddoc-pro/2026/04/30/meddoc-thu.sql.gz.age
INFO: upload complete: b2://meddoc-offsite-backups-prod/meddoc-pro/2026/04/30/meddoc-thu.sql.gz.age
INFO: pruning blobs older than 30 days from b2://meddoc-offsite-backups-prod/meddoc-pro/
INFO: backup-offsite-sync.sh completed successfully
```

If you see `ERROR: required env var BACKBLAZE_KEY_ID is not set`, the
`.env` write didn't reach the container. Re-do A.6 + A.8.

If you see `ERROR: required tool 'age' is not on PATH`, complete A.4.

### B.3 Verify in the B2 console

1. Go to https://secure.backblaze.com/b2_buckets.htm
2. Open `meddoc-offsite-backups-prod` → Browse Files
3. Drill into `meddoc-pro/<YYYY>/<MM>/<DD>/`
4. You should see one `meddoc-<dow>.sql.gz.age` blob.

Click the blob → check the **File Info** tab. You should see:

| Key | Value |
|---|---|
| sha256 | `<64 hex chars>` |
| dump_filename | `meddoc-<dow>.sql.gz` |
| dump_size | `<bytes>` |
| source_hostname | `<your VPS FQDN>` |
| uploaded_at | `<ISO 8601 UTC>` |

### B.4 Record evidence

Append to `audit-evidence/h16/`:

```
date:        <YYYY-MM-DD>
operator:    <name>
local dump:  <path + size + sha256>
b2 blob:     b2://meddoc-offsite-backups-prod/meddoc-pro/<path>
b2 size:     <bytes after age encryption>
b2 sha256:   <from File Info panel>
```

This is the evidence reviewers will ask for at the next compliance audit.

---

## C. Restoration procedure

**Run this drill at least once per quarter** to verify the offsite copy
is actually restorable.

### C.1 Retrieve the private key

```bash
# From your offline secret store (1Password Vault, physical safe, etc).
# Copy to a temp location on a workstation that will perform the restore.
# DO NOT copy back to the production VPS — restoration happens on a
# separate host so you don't conflate "does the offsite copy work" with
# "is the production VPS healthy".
cp <secret-store-extract>/offsite-backup-private.age /tmp/restore-private.age
chmod 0400 /tmp/restore-private.age
```

### C.2 Authenticate the B2 CLI on the restore host

```bash
b2 account authorize <BACKBLAZE_KEY_ID> <BACKBLAZE_APPLICATION_KEY>
```

(For restoration you can use a read-only key scoped to the same bucket;
write capability is not required.)

### C.3 Pick the blob to restore

```bash
b2 ls --recursive --json meddoc-offsite-backups-prod meddoc-pro/ \
  | jq -r '.[] | "\(.uploadTimestamp) \(.fileName) \(.contentLength)"' \
  | sort -nr \
  | head -n 10
```

Pick the most recent `*.sql.gz.age`. Save its `fileName`.

### C.4 Download

```bash
b2 file download \
  --threads 4 \
  b2://meddoc-offsite-backups-prod/<fileName> \
  /tmp/restore.sql.gz.age
```

### C.5 Verify the sha256 matches B2's file-info tag

```bash
b2 file info b2://meddoc-offsite-backups-prod/<fileName> | grep sha256
sha256sum /tmp/restore.sql.gz.age   # should match the encrypted-blob sha
                                     # NOT the dump_sha256 file-info value
                                     # (that one is the pre-encryption sha,
                                     # verify it after decryption below)
```

### C.6 Decrypt with age

```bash
age --decrypt --identity /tmp/restore-private.age --output /tmp/restore.sql.gz \
  /tmp/restore.sql.gz.age

# Verify pre-encryption sha matches
sha256sum /tmp/restore.sql.gz
# Compare to the dump_sha256 value from `b2 file info` — must match exactly.
```

### C.7 Restore into ephemeral postgres

```bash
docker run -d --name pg-restore-test \
  -e POSTGRES_USER=meddoc -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=meddoc -p 15434:5432 \
  pgvector/pgvector:pg16

# Wait for postgres ready
sleep 8

gunzip -c /tmp/restore.sql.gz \
  | docker exec -i pg-restore-test psql -U meddoc -d meddoc

# Smoke test row counts vs production reference values
docker exec pg-restore-test psql -U meddoc -d meddoc -c "
SELECT 'users' AS t, COUNT(*) FROM users
UNION ALL SELECT 'transcribe_visits', COUNT(*) FROM transcribe_visits
UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;
"
```

Row counts should match the local-restore drill in
`docs/H16_OFFSITE_BACKUP_PROCEDURE.md` Section F (within ±1 row, since
the offsite copy is up to 24h behind the live DB).

### C.8 Tear down

```bash
docker stop pg-restore-test && docker rm pg-restore-test
shred -u /tmp/restore.sql.gz /tmp/restore.sql.gz.age /tmp/restore-private.age
```

`shred` (not `rm`) ensures the decrypted PHI dump and the private key are
unrecoverable from the workstation's free space.

---

## D. Key custody

This is the load-bearing part of the procedure. **If the age private key
is lost, every encrypted blob in B2 becomes permanently unrecoverable.**
That is by design — the alternative (storing the private key with the
encrypted data) defeats the purpose of client-side encryption.

### D.1 Where the private key lives

| Copy | Location | Access | Purpose |
|---|---|---|---|
| Primary | Offline secret store (1Password Business Vault, encrypted USB in safe, or HSM) | Deployment owner + 1 backup approver | Restoration |
| Secondary | `/etc/meddoc/offsite-backup-private.age` on the VPS, mode 0400, root-owned | Root SSH on the VPS | Convenience for emergency in-place restore |
| Tertiary | Printed/cold-storage paper backup in a fireproof safe | Compliance officer | Catastrophic recovery — last resort |

The secondary copy is optional but recommended. If the VPS is compromised
the attacker has access to the primary B2 credentials anyway, so co-locating
the private key with them doesn't materially increase exposure (the VPS
already holds plaintext PHI in /var/lib/postgres). The defence is against
B2 compromise + leaked credentials *without* host compromise — that's
exactly the scenario where the private key, archived offline, saves you.

### D.2 Who has access

Document explicitly. Suggested template (fill in for your org):

```
Primary holders:
  - <name>, <role>, <contact>           ← deployment owner
  - <name>, <role>, <contact>           ← backup approver

Tertiary (paper) holders:
  - <name>, <role>                       ← compliance officer

Last reviewed: <YYYY-MM-DD>
Next review:   <YYYY-MM-DD + 6 months>
```

File this with the BAA in your compliance binder.

### D.3 What happens if the key is lost

**Catastrophic.** The encrypted blobs in B2 become opaque, undecryptable,
and effectively useless. You can still restore from:

1. The local pg_dump retention (`/opt/meddoc-pro/backups/` — 7 daily, 4
   weekly, 6 monthly).
2. The unencrypted Hetzner mirror if it's also configured (per
   `docs/H16_OFFSITE_BACKUP_PROCEDURE.md`).
3. Any out-of-band manual backup taken before the key loss event.

**Lost-key recovery procedure**:

1. Generate a new keypair (per A.5).
2. Update `/etc/meddoc/offsite-backup-public.age` on the VPS.
3. Wait for the next backup cycle — going forward, blobs are encrypted to
   the new key.
4. **Manually delete every blob in B2 encrypted to the lost key** (they
   are dead weight; the bucket lifecycle rule will catch them in 30 days
   anyway, but explicit deletion clears space sooner).
5. Treat all data lost in the gap (oldest unencrypted backup → first
   re-keyed backup) as IRRECOVERABLE OFFSITE. Local copies still cover
   their retention windows.
6. File an incident report. This is a near-miss compliance event even
   though no PHI was leaked — the **offsite recoverability** posture
   degraded, which is itself a reportable risk.

### D.4 Disaster scenario walk-through

> Q: VPS is destroyed (cloud account deleted, hardware total loss). What's the recovery path?
>
> 1. Spin up a fresh VPS, install docker compose.
> 2. Restore from the most recent `meddoc-offsite-backups-prod/meddoc-pro/<latest>/` blob using the **offline-archived** private key (D.1 primary).
> 3. Bring up the new compose stack pointing at the restored DB.
> 4. **Outcome**: at most 24h of data loss (the offsite mirror runs daily). Acceptable per Phase 16 BCP.

> Q: The B2 bucket is deleted by an attacker who got the credentials. What's the recovery path?
>
> 1. The local `/opt/meddoc-pro/backups/` retention covers 7 daily, 4 weekly, 6 monthly snapshots.
> 2. Rotate the B2 application key (revoke compromised key, create new one).
> 3. Trigger a fresh full backup cycle to repopulate the offsite mirror.
> 4. **Outcome**: zero data loss as long as the local volume is intact.

> Q: Both the VPS AND the B2 bucket are gone (correlated compromise: stolen .env). What's the recovery path?
>
> 1. Most recent backup = whatever's in the **paper** tertiary copy + Hetzner mirror if configured + monthly tape (if you maintain one).
> 2. Acceptable RPO degrades to "last quarter" without a third independent off-host copy.
> 3. **This scenario is the reason cold-storage paper backups exist.** Don't skip D.1 tertiary.

---

## E. Rotation

### E.1 Cadence

Rotate the age keypair **every 12 months** or immediately on any of these
triggers:

- Suspected compromise of `/etc/meddoc/offsite-backup-private.age` on the VPS
- Departure of any employee who held a copy of the private key
- VPS root-credential rotation (the script's safe-state means re-keying
  alongside SSH key rotation is cheap)
- Annual compliance review identifies the key as overdue

### E.2 Procedure

```bash
# 1. Generate a new keypair OFFLINE (per A.5).
age-keygen -o offsite-backup-private-2027.age
grep '^# public key:' offsite-backup-private-2027.age \
  | sed 's/^# public key: //' > offsite-backup-public-2027.age

# 2. Archive the OLD private key in an "offsite-backup-private-archive"
#    folder of your secret store. Label it with the date range it covers.
#    Old encrypted blobs in B2 remain decryptable WITH THE OLD KEY ONLY.
#    Keep this archive forever — you may need to restore from a 6-month-old
#    blob a year after rotation.

# 3. Replace the public key on the VPS:
scp offsite-backup-public-2027.age \
    root@<vps>:/etc/meddoc/offsite-backup-public.age
ssh root@<vps> chmod 0444 /etc/meddoc/offsite-backup-public.age

# 4. (Optional) Replace the secondary private key on the VPS too:
scp offsite-backup-private-2027.age \
    root@<vps>:/etc/meddoc/offsite-backup-private.age
ssh root@<vps> chmod 0400 /etc/meddoc/offsite-backup-private.age

# 5. Restart the postgres-backup container so the script picks up the
#    new public key on its next run:
ssh root@<vps> 'cd /opt/meddoc-pro && docker compose up -d --force-recreate postgres-backup'

# 6. Trigger a manual backup (per B.1) and verify the new blob decrypts
#    with the new private key (per C.6).

# 7. Run the C.* restoration drill end-to-end with the OLD private key
#    against an OLD blob to confirm the archive is still good.
```

### E.3 Archive longevity

The archive of historical private keys is **load-bearing for HIPAA's 6-year
retention rule**. PHI must be retrievable for 6 years from the date of
service. If you rotate annually, that means up to 6 historical keys must
be archived and recoverable at any time.

**Test this annually.** A key archive that nobody can find is the same as
no archive at all. Add to the quarterly drill checklist:
"Decrypt one blob from each historical key era; confirm row counts."

---

## F. Operational notes

- The script writes its log to `/var/log/meddoc/offsite-backup.log`. The
  log self-rotates: oldest lines trimmed to keep the file under 10,000 lines.
- A failed offsite push does **NOT** fail the local pg_dump. The local
  dump path is the priority; offsite is best-effort.
- `b2` CLI v4 syntax is required (`b2 file upload`, `b2 file download`,
  `b2 account authorize`). Older v3 syntax (`b2 upload-file`) is not
  compatible with the script.
- If `python3` is missing from the postgres-backup image, the prune step
  silently skips and bucket lifecycle rules (A.2) are the only retention
  enforcement. Add `python3` to the image if you want the script-driven
  prune to work.
- The script tags each upload with sha256 / filename / size / hostname /
  uploaded_at. These are the audit-trail evidence reviewers will ask for.
- Cost estimate: 1.5 MB encrypted dump × 30 days = ~45 MB stored at
  $0.005/GB/month → effectively zero. Bandwidth: ~45 MB upload/month
  (Backblaze egress is what costs; restoration drills will dominate the
  bandwidth bill).

---

## G. Resolution checklist

Once setup, first-run verification, and a successful restore drill are
all done:

- [ ] BAA with Backblaze countersigned and filed
- [ ] Bucket created with lifecycle rules (A.2)
- [ ] Application key created, scoped to the single bucket (A.3)
- [ ] `age` + `b2` CLI installed (A.4)
- [ ] Age keypair generated; private key archived offline (A.5, D.1)
- [ ] `.env` populated and chmod 600 (A.6)
- [ ] `postscript.sh` chained to call the new script (A.7) — operator decision
- [ ] Container restarted and first manual backup verified (B.1, B.2, B.3)
- [ ] First-run evidence recorded (B.4)
- [ ] Restoration drill completed end-to-end (C.*)
- [ ] Key custody documented with named holders (D.2)
- [ ] Calendar reminder set for next quarterly drill
- [ ] Calendar reminder set for next annual key rotation (E.1)

After all checked, mark `h16` as **Mitigated** in
`docs/HIPAA_COMPLIANCE.md` and resolve the matching admin/hipaa finding.
