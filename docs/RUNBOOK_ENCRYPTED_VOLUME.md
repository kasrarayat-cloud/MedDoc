# Runbook — Encrypted Postgres Data Volume (LUKS-on-loop-file)

*HIPAA h8 — encryption at rest for PHI in postgres. Current procedure
for the Zap Hosting deployment. Supersedes the Hetzner-managed-volume
approach in `docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md`.*

---

## 0. Overview

The postgres service's data directory is bind-mounted from
`/var/lib/meddoc-postgres-data` on the host. That host directory is
the mount point of an ext4 filesystem inside a LUKS2 container backed
by a sparse 50 GB loop file at `/var/lib/meddoc-postgres-encrypted.img`.
The LUKS key file lives at `/etc/meddoc/postgres-volume.key`
(0400, root:root) and is referenced by the systemd unit
`meddoc-postgres-volume.service`, which opens + mounts the device on
boot ordered `Before=docker.service`.

This runbook covers:

1. Pre-flight checks
2. Migration of the existing `pgdata` named volume → encrypted bind mount
3. Smoke test
4. Rollback
5. Key rotation
6. HIPAA audit-trail entry

**Estimated maintenance window: 30–60 minutes** (10 min setup +
data rsync + 5 min smoke test + 10 min slack for unexpected issues).
Practice on staging first.

---

## 1. Pre-flight checks

Run all of these BEFORE the maintenance window. Abort if any fail.

```bash
# 1.1 — Confirm current free disk on /var/lib (need ≥ 60 GB headroom:
#        50 GB for the encrypted image + working room for rsync).
df -h /var/lib

# 1.2 — Confirm postgres is currently healthy.
docker compose -f /opt/meddoc-pro/docker-compose.yml ps postgres
docker compose -f /opt/meddoc-pro/docker-compose.yml exec -T postgres \
  pg_isready -U meddoc -d meddoc

# 1.3 — Confirm a recent backup exists AND verify it restores into a
#       throwaway container. The h16 backup sidecar drops dumps into
#       /var/lib/docker/volumes/meddoc-pro_postgres_backups (path may
#       vary — check your h16 setup). Pick the most recent and verify:
ls -lht /var/lib/docker/volumes/*postgres*backup*/_data/ | head -5

# Pick the newest .sql.gz, then:
LATEST=$(ls -1t /var/lib/docker/volumes/*postgres*backup*/_data/*.sql.gz | head -1)
echo "verifying: $LATEST"
gunzip -t "$LATEST" && echo "gzip integrity OK"

# 1.4 — Confirm cryptsetup is installed on the host.
cryptsetup --version

# 1.5 — Capture row counts BEFORE migration so you can diff after.
docker compose -f /opt/meddoc-pro/docker-compose.yml exec -T postgres \
  psql -U meddoc -d meddoc -c "
    SELECT 'users' AS t, COUNT(*) FROM users
    UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
    UNION ALL SELECT 'transcribe_visits', COUNT(*) FROM transcribe_visits;
  " | tee /root/h8-pre-migration-rowcounts-$(date -u +%Y%m%d-%H%M%S).txt
```

---

## 2. Maintenance window

Announce a 60-minute window. Set status page if applicable.

### 2.1 Take a fresh dump (extra safety on top of nightly h16 backup)

```bash
docker compose -f /opt/meddoc-pro/docker-compose.yml exec -T postgres \
  pg_dump -U meddoc -Fc meddoc > /root/pre-h8-migration-$(date -u +%Y%m%d-%H%M%S).dump
ls -lh /root/pre-h8-migration-*.dump
```

### 2.2 Stop postgres (and anything that depends on it)

```bash
cd /opt/meddoc-pro
docker compose stop transcribe-md transcribe-md-worker marketing
docker compose stop postgres
```

Verify nothing in the compose stack still expects postgres to be up:

```bash
docker compose ps
```

### 2.3 Provision the encrypted volume

```bash
sudo bash /opt/meddoc-pro/infra/setup-encrypted-volume.sh
```

The script is idempotent — re-run it if it fails partway. It prints a
summary at the end with the key file location.

**IMMEDIATELY ESCROW THE KEY FILE off-host:**

```bash
# Example — encrypt with your team's GPG key and store in vault.
sudo cat /etc/meddoc/postgres-volume.key | gpg --encrypt --armor -r ops@example.com \
  > postgres-volume.key.asc
# Upload postgres-volume.key.asc to the secrets vault. Verify upload.
# Then SHRED the local copy:
shred -u postgres-volume.key.asc
```

If `/etc/meddoc/postgres-volume.key` is ever lost, the encrypted volume
is unrecoverable.

### 2.4 Copy existing pgdata into the new encrypted mount

The named volume `pgdata` lives under
`/var/lib/docker/volumes/meddoc-pro_pgdata/_data`. Confirm the path
once before rsync:

```bash
docker volume inspect meddoc-pro_pgdata --format '{{ .Mountpoint }}'
PGDATA_SRC=$(docker volume inspect meddoc-pro_pgdata --format '{{ .Mountpoint }}')
echo "source: $PGDATA_SRC"
```

Now copy. `-aHAX` preserves perms, hardlinks, ACLs, and xattrs.
`--numeric-ids` keeps uid 999 intact across the copy.

```bash
sudo rsync -aHAX --numeric-ids --info=progress2 \
  "$PGDATA_SRC"/ /var/lib/meddoc-postgres-data/
sudo chown -R 999:999 /var/lib/meddoc-postgres-data
```

Sanity-check that the contents look like a postgres data dir:

```bash
ls /var/lib/meddoc-postgres-data | head
# Should include: PG_VERSION, base, global, pg_wal, postgresql.conf, ...
sudo cat /var/lib/meddoc-postgres-data/PG_VERSION
# Should print: 16
```

### 2.5 Bring postgres back up on the encrypted volume

The bind mount in `docker-compose.yml` is already pointed at
`/var/lib/meddoc-postgres-data` on this branch — once it's merged and
deployed, just:

```bash
cd /opt/meddoc-pro
docker compose up -d postgres
docker compose logs --tail=80 postgres
docker compose exec -T postgres pg_isready -U meddoc -d meddoc
```

### 2.6 Bring app services back up

```bash
docker compose up -d transcribe-md transcribe-md-worker marketing
docker compose ps
```

---

## 3. Smoke test

```bash
# 3.1 — Row counts match pre-migration capture.
docker compose -f /opt/meddoc-pro/docker-compose.yml exec -T postgres \
  psql -U meddoc -d meddoc -c "
    SELECT 'users' AS t, COUNT(*) FROM users
    UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs
    UNION ALL SELECT 'transcribe_visits', COUNT(*) FROM transcribe_visits;
  "
# diff against /root/h8-pre-migration-rowcounts-*.txt — must be identical.

# 3.2 — HTTP smoke (post-deploy regression matrix from MEMORY.md).
curl -fsS -o /dev/null -w 'caddy:%{http_code}\n'   http://127.0.0.1/
curl -fsS -o /dev/null -w 'patient:%{http_code}\n' http://127.0.0.1:9020/
curl -fsS -o /dev/null -w 'cli:%{http_code}\n'    http://127.0.0.1:9010/

# 3.3 — Confirm the data is actually on the encrypted device.
mount | grep meddoc-postgres-data
lsblk -f /dev/mapper/meddoc-postgres-encrypted

# 3.4 — Confirm the LUKS header is intact.
sudo cryptsetup luksDump /var/lib/meddoc-postgres-encrypted.img | head -20
```

If anything fails the smoke test, **rollback** (§4).

---

## 4. Rollback

If postgres won't start, a smoke test fails, or row counts don't
match — restore the original named volume.

```bash
cd /opt/meddoc-pro
docker compose stop transcribe-md transcribe-md-worker marketing postgres

# Revert docker-compose.yml on this host so postgres uses the
# original named volume again. Easiest path: check out the previous
# version of the file from git on the host.
git -C /opt/meddoc-pro diff HEAD docker-compose.yml | head -20  # confirm the bind-mount change is the diff
git -C /opt/meddoc-pro checkout HEAD~1 -- docker-compose.yml    # adjust to the right commit if needed

docker compose up -d postgres
docker compose exec -T postgres pg_isready -U meddoc -d meddoc
docker compose up -d transcribe-md transcribe-md-worker marketing
```

If the original `pgdata` volume was somehow corrupted, restore from
the dump captured in §2.1:

```bash
docker compose stop transcribe-md transcribe-md-worker marketing
docker compose exec -T postgres dropdb -U meddoc meddoc
docker compose exec -T postgres createdb -U meddoc meddoc
cat /root/pre-h8-migration-*.dump \
  | docker compose exec -T postgres pg_restore -U meddoc -d meddoc -Fc
```

After rollback, leave the encrypted image + mount in place but
unmounted — investigate the failure offline before re-attempting.

---

## 5. Key rotation

Rotate the LUKS key **every 12 months** OR **immediately after any
privileged-staff turnover** (anyone with root on the host or access
to the secrets vault).

LUKS2 supports up to 32 key slots. Rotation = add the new key to a
free slot, verify it works, then kill the old slot — never leave the
volume unprotected during the swap.

```bash
# 5.1 — Generate the new key (4 KB random, same posture as original).
sudo install -m 0400 /dev/null /etc/meddoc/postgres-volume.key.new
sudo dd if=/dev/urandom of=/etc/meddoc/postgres-volume.key.new \
  bs=4096 count=1 status=none
sudo chmod 0400 /etc/meddoc/postgres-volume.key.new

# 5.2 — Add it to a new slot (LUKS prompts for an existing key to
#       authorize the addition; pass the current key file).
sudo cryptsetup luksAddKey \
  --key-file /etc/meddoc/postgres-volume.key \
  /var/lib/meddoc-postgres-encrypted.img \
  /etc/meddoc/postgres-volume.key.new

# 5.3 — Verify the new key actually opens the device.
sudo cryptsetup luksOpen --test-passphrase \
  --key-file /etc/meddoc/postgres-volume.key.new \
  /var/lib/meddoc-postgres-encrypted.img \
  && echo "new key OK"

# 5.4 — Identify the slot the OLD key occupies.
sudo cryptsetup luksDump /var/lib/meddoc-postgres-encrypted.img \
  | grep -E 'Keyslot|^[[:space:]]+[0-9]+:'

# 5.5 — Kill the OLD slot. Authorize with the NEW key (so we don't
#       accidentally lock ourselves out if something is wrong).
#       Replace <N> with the old slot number from §5.4 (typically 0
#       for the first-ever rotation).
sudo cryptsetup luksKillSlot \
  --key-file /etc/meddoc/postgres-volume.key.new \
  /var/lib/meddoc-postgres-encrypted.img <N>

# 5.6 — Promote the new key file. Update the systemd unit reference
#       only if you changed the path; the default unit reads the
#       canonical path so a same-path swap is fine.
sudo mv /etc/meddoc/postgres-volume.key /etc/meddoc/postgres-volume.key.OLD
sudo mv /etc/meddoc/postgres-volume.key.new /etc/meddoc/postgres-volume.key

# 5.7 — Re-escrow the new key off-host. Then shred the OLD copies.
sudo shred -u /etc/meddoc/postgres-volume.key.OLD

# 5.8 — Confirm boot persistence by reloading the unit (does NOT
#       touch the running mount).
sudo systemctl daemon-reload
sudo systemctl status meddoc-postgres-volume.service
```

Log the rotation in the HIPAA audit trail (§6).

---

## 6. HIPAA documentation

Append an entry to your audit log AT MIGRATION time and AT EACH KEY
ROTATION. Suggested format (CSV in `/var/log/meddoc/hipaa-audit.log`,
or whatever your audit-trail mechanism is):

```
2026-04-30T14:00:00Z, h8-encrypt-at-rest, MIGRATE, operator=<name>, sha256(key)=<hex>, image=/var/lib/meddoc-postgres-encrypted.img
2027-04-30T14:00:00Z, h8-encrypt-at-rest, ROTATE,  operator=<name>, sha256(key)=<hex>, slot_killed=0
```

Capture `sha256` of the key file (NOT the key itself) so you can
later prove which key was active at a given point in time without
exposing the key:

```bash
sudo sha256sum /etc/meddoc/postgres-volume.key
```

Update `docs/HIPAA_COMPLIANCE.md` to flip the h8 row from
`Mitigated (pending operator migration)` to
`Mitigated (migrated YYYY-MM-DD)` once §3 passes.

---

## 7. References

- Original task spec: HIPAA finding **h8** (Phase 3 Wave 1).
- Superseded predecessor: `docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md`.
- Related: `docs/H16_OFFSITE_BACKUP_PROCEDURE.md` (offsite encrypted
  backups — the other half of "encryption at rest").
- HIPAA Security Rule §164.312(a)(2)(iv) — encryption and decryption.
