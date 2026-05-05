---
id: A07-P1-004
title: Postgres .sql.gz dumps under /opt/meddoc-pro/backups are world-readable
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The `postgres-backup` sidecar writes its rotated dumps to
`/opt/meddoc-pro/backups/{daily,last,weekly,monthly}/`. Inside the
container the user is `999:999` (postgres uid by symmetry); on the host
those numeric IDs map to `dnsmasq:systemd-journal`. The container writes
files with default umask, producing **mode 0644** — world-readable. Any
user on the host (including the `claude` user — see A07-P1-003 for the
docker-equivalence issue, but this is *additionally* readable by
non-docker users) can `cat` a dump containing the entire `meddoc`
database in plaintext.

The migration subdir (mode 0750, dnsmasq:systemd-journal) is correctly
restricted.

## Evidence

```
$ ls -la /opt/meddoc-pro/backups/daily/
drwxr-xr-x 2 dnsmasq systemd-journal    4096 May  4 00:00 .
-rw-r--r-- 1 dnsmasq systemd-journal 1682802 Apr 27 00:00 meddoc-20260427.sql.gz
-rw-r--r-- 1 dnsmasq systemd-journal 1840305 Apr 29 00:00 meddoc-20260429.sql.gz
-rw-r--r-- 2 dnsmasq systemd-journal 1841422 Apr 30 00:00 meddoc-20260430.sql.gz
-rw-r--r-- 1 dnsmasq systemd-journal 1842834 May  1 00:00 meddoc-20260501.sql.gz
-rw-r--r-- 1 dnsmasq systemd-journal 2072581 May  2 00:00 meddoc-20260502.sql.gz
-rw-r--r-- 2 dnsmasq systemd-journal 2076237 May  3 00:00 meddoc-20260503.sql.gz
-rw-r--r-- 4 dnsmasq systemd-journal 2172968 May  4 00:00 meddoc-20260504.sql.gz

$ stat -c '%a %U:%G' /opt/meddoc-pro/backups/daily
755 dnsmasq:systemd-journal     # parent dir is also o+rx
```

The same posture exists in `/opt/meddoc-pro/backups/{last,weekly,monthly}`.

The local pg_dump is **NOT** encrypted. Phase 6.2's age-encryption only
applies to the offsite copy uploaded to Backblaze B2. Local dumps on the
VPS itself are plaintext gzipped SQL.

## Risk

- HIPAA §164.312(c) "Integrity" + §164.312(a)(2)(iv) "Encryption and
  Decryption" — local PHI-bearing dumps without confidentiality controls
  beyond filesystem permissions, and the filesystem permissions
  themselves do not enforce confidentiality.
- The backups dir is the largest single PHI surface on the host. With
  6+ months of `BACKUP_KEEP_MONTHS=6`, 4 weeks of `BACKUP_KEEP_WEEKS=4`,
  and 7 days of `BACKUP_KEEP_DAYS=7`, there are at minimum 17 plaintext
  copies of the production DB readable to every user on the host at any
  given moment.
- Combines with A07-P0-001 / A07-P0-003 (every shared-host risk vector
  has an immediate access path to PHI).

## Recommended fix

Two layers, applied together:

1. **Restrict the host directory.** In compose, add the `umask` option
   to the postgres-backup environment (the upstream
   prodrigestivill/postgres-backup-local image supports `BACKUP_UMASK`
   or similar — confirm in the image docs); or set up an inotify watcher
   that chmods 0600 on creation; or simplest, change ownership of
   `/opt/meddoc-pro/backups` to `999:999` and `chmod 0700` so non-postgres
   uids cannot enter the directory at all. This requires that no non-
   container reader currently expects to walk the dir. Update Phase 6.2
   cron scripts if any of them assume world-read.

2. **Encrypt local dumps too.** Phase 6.2 already wires the age public
   key onto the host at `/etc/meddoc/offsite-backup-public.age`. Modify
   `infra/postgres-backup/postscript.sh` (currently runs `mc mirror`
   plaintext) and the Phase 6.2 host cron to age-encrypt the dump
   *before* writing the on-disk copy that lives in `/opt/meddoc-pro/
   backups/last/`. Restore drill (`scripts/restore-drill.sh`) already
   handles age-encrypted blobs — restore from local would need the
   offline private key, which is the intended posture (defence in depth,
   not convenience).

Verify post-fix: `find /opt/meddoc-pro/backups -type f -perm /o+r` should
return zero files containing `.sql.gz`.
