---
id: A05-P2-001
title: Production LUKS-encrypted Postgres volume is 1 GB (script default 50 GB) — exhaustion risk pre-pilot
domain: HIPAA-technical-safeguards
severity: P2
agent: 05
---

## Issue

`infra/setup-encrypted-volume.sh:39` defaults `IMG_SIZE_GB=50`, but
production was provisioned with `IMG_SIZE_GB=1`:

- `losetup -l` → `/dev/loop0  /opt/meddoc-pro/secrets/pgdata.luks`
- `df -h /mnt/pgdata-encrypted` → `/dev/mapper/pg-encrypted  974M
  74M  835M  9% /mnt/pgdata-encrypted`
- `ls -la /opt/meddoc-pro/secrets/pgdata.luks` → 1 073 741 824 bytes
  (exactly 1 GB).

Currently 9% used (74 M / 974 M). At today's data-growth pattern
(low) the volume is fine, but a pilot with even modest visit volume
will fill it within weeks. Postgres data + WAL + indexes for a single
practice doing 30 visits/day with full audio metadata + transcripts
+ AuditLog accumulation will push past 1 GB in 4–6 weeks.

When the volume fills:
- Postgres write failures (cascading worker job failures, audit
  failures, sign failures).
- HIPAA requirement compromised: audit logs MUST be persistable —
  if the table can't accept INSERTs, every write event silently
  drops the audit row (the `try {} catch {}` pattern in
  `lib/audit.ts:185-194` swallows the error).

The script also ships a path mismatch: defaults are
`IMG_PATH=/var/lib/meddoc-postgres-encrypted.img`, `MOUNT_POINT=
/var/lib/meddoc-postgres-data`, `MAPPER_NAME=meddoc-postgres-
encrypted`. Production uses `IMG_PATH=/opt/meddoc-pro/secrets/
pgdata.luks`, `MOUNT_POINT=/mnt/pgdata-encrypted`, `MAPPER_NAME=
pg-encrypted`. Operator-side runbook divergence — re-running the
script with default env will create a SECOND volume rather than
re-using the existing one.

## Evidence

- `losetup -l`, `df -h /mnt/pgdata-encrypted`, `ls -la /opt/meddoc-
  pro/secrets/pgdata.luks` all run in the audit session.
- `infra/setup-encrypted-volume.sh:36-40` — IMG_SIZE_GB defaults to
  50.
- `docker-compose.yml:60-61` — `volumes: -
  /mnt/pgdata-encrypted:/var/lib/postgresql/data`.

## Risk

- §164.312(b) — Audit controls: silent audit-write failures during a
  full-disk event break the audit chain.
- Operational: pilot launch + first burst of visits + disk-full
  cascade is a high-probability incident.

## Recommended fix

1. **Resize the loop file.** Standard sequence (maintenance window):
   ```bash
   systemctl stop docker
   cryptsetup close pg-encrypted
   truncate -s 50G /opt/meddoc-pro/secrets/pgdata.luks
   cryptsetup luksResize ...
   resize2fs /dev/mapper/pg-encrypted
   ```
2. **Reconcile the script defaults with production paths.** Update
   `infra/setup-encrypted-volume.sh` so its defaults match what's
   running, OR document the override env vars at the top of the
   script + in the runbook so re-runs land in the right place.
3. **Add disk-usage monitoring** to `/api/health` (the health route
   already does cleanup_crons[] checks per T-M18.2 A13). Alert at
   >70% on the encrypted volume so an operator gets warning before
   write failures begin.

P2 (not P1) because the fail mode is operational rather than direct
PHI exposure — but the cascading audit-row-loss path makes it borderline P1.
