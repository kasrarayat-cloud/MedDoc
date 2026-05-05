---
id: A05-P0-002
title: Local pg_dump backups in /opt/meddoc-pro/backups — gzipped plaintext on unencrypted root disk
domain: HIPAA-technical-safeguards
severity: P0
agent: 05
---

## Issue

The postgres-backup sidecar writes daily/weekly/monthly `*.sql.gz`
dumps into `/opt/meddoc-pro/backups/` (host bind mount per
`docker-compose.yml:563-564`). Inspection:

- `/opt/meddoc-pro/backups/daily/meddoc-20260427.sql.gz` … through
  `meddoc-20260503.sql.gz` (~2 MB each).
- `/opt/meddoc-pro/backups/last/`, `monthly/`, plus loose
  `pre_t_m14_*.sql.gz`, `pre_t_m16_2_*.sql.gz`,
  `db-pre-app-redesign-20260422.sql.gz`.
- `file` confirms: gzip-compressed plain SQL.

These files contain every `audit_logs`, `users`, `transcribe_visits`,
`transcribe_md_patients` row including transcript text, SOAP notes,
patient demographics, MRNs, etc. They are:

1. **Unencrypted** (gzip is compression, not encryption).
2. **Stored on `/dev/sda2` (root disk, ext4, no LUKS)** — same disk
   that hosts the running app.
3. World-readable except `migration/` (mode `drwxr-x---`); ownership
   `dnsmasq:systemd-journal` is unusual but does not enforce HIPAA
   access control. `db-pre-app-redesign-20260422.sql.gz` is mode 664.

The matching finding h8 in `docs/HIPAA_COMPLIANCE.md` only addresses
the live `/var/lib/postgresql/data` directory (which IS on the
LUKS-mounted `/mnt/pgdata-encrypted`). It is silent on the bind-mounted
backup directory.

## Evidence

- `ls -la /opt/meddoc-pro/backups/` (mtime 2026-04 onwards; most recent
  `meddoc-20260503.sql.gz` 2 MB).
- `df /opt/meddoc-pro/backups → /dev/sda2 (root, unencrypted)`.
- `/opt/meddoc-pro/docker-compose.yml:563-564` —
  `volumes: - ./backups:/backups`.
- `/opt/meddoc-pro/infra/postgres-backup/postscript.sh` ships the dumps
  to a remote S3 bucket if `REMOTE_BACKUP_S3_*` env is set — also
  without encryption (see adjacent finding A05-P0-003).

## Risk

- §164.312(a)(2)(iv): PHI at rest must be encrypted. Daily backups
  contain a complete copy of every PHI-bearing row; physical-disk
  compromise of the VPS = full breach.
- Backups are the highest-value target for an attacker because they
  are pre-aggregated and easy to exfiltrate in a single file.

## Recommended fix

1. **Move the backup directory onto the encrypted LUKS mount.** Either
   bind `/mnt/pgdata-encrypted/backups:/backups` in compose, or expand
   the LUKS volume so it can host both pgdata and backups. Until then
   the encryption-at-rest mitigation is incomplete.

2. **Encrypt the dumps client-side BEFORE writing to disk.** Pipe
   `pg_dump | gzip | age -r $PUBLIC_KEY` via a custom prescript so the
   `*.sql.gz.age` file is what hits `/backups/last/`. The
   `infra/backup-offsite-sync.sh` already encrypts before B2 upload,
   but the encryption step needs to happen pre-disk-write, not just
   pre-network.

3. **Tighten directory perms** to mode `0700`, ownership `postgres-
   backup` user only. Fix the `dnsmasq:systemd-journal` ownership —
   that's a host-config artifact and surprising in this context.

4. **Add row to `HIPAA_COMPLIANCE.md`** for backup encryption-at-rest
   distinct from the live-database row. Today the matrix implies h8
   covers everything; it doesn't.
