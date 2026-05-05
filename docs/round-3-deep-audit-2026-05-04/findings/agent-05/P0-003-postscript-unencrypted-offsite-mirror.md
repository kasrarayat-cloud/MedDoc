---
id: A05-P0-003
title: postgres-backup postscript.sh ships PLAINTEXT pg_dumps to remote S3 if env set
domain: HIPAA-technical-safeguards
severity: P0
agent: 05
---

## Issue

`infra/postgres-backup/postscript.sh` (the `POST_BACKUP_COMMAND` wired
into the postgres-backup sidecar via `docker-compose.yml:547`) mirrors
`/backups/last/` to a remote S3 bucket using `mc mirror`. The path is
plaintext: there is no encryption layer between the SQL dump and the
remote bucket.

```bash
# postscript.sh:66-70
"$MC_BIN" mirror --quiet --overwrite \
  --exclude ".mc-*" \
  /backups/last/ \
  "remote/${BUCKET}/${PREFIX}last/" \
  >/dev/null
```

The script gates on `REMOTE_BACKUP_S3_*` env vars: if all four are set
(endpoint/bucket/access/secret), the offsite push runs; if any is
missing, the script no-ops silently. The encrypted-offsite path
(`infra/backup-offsite-sync.sh` → Backblaze B2 with age) is a SEPARATE
script; the two are independent.

If an operator sets `REMOTE_BACKUP_S3_*` to mirror to e.g. Hetzner
Object Storage (`docs/H16_OFFSITE_BACKUP_PROCEDURE.md` documents this
flow), every PHI row goes to that bucket as plaintext gzip — the only
"protection" is the bucket ACL.

Currently `.env` does not set `REMOTE_BACKUP_*` (verified — grep
returns nothing), so the path is dormant. But the script is wired, the
runbook documents activation, and a single env edit flips it on.

## Evidence

- `/opt/meddoc-pro/infra/postgres-backup/postscript.sh` lines 32-72 —
  no `age`, no `gpg`, no SSE, no client-side encryption anywhere in the
  pipeline.
- `/opt/meddoc-pro/docker-compose.yml:547` wires it as
  `POST_BACKUP_COMMAND`.
- `/opt/meddoc-pro/docs/H16_OFFSITE_BACKUP_PROCEDURE.md` is referenced
  as the activation runbook for this path; it pre-dates the encrypted
  variant in `infra/backup-offsite-sync.sh`.

## Risk

- §164.312(e)(1) — Transmission security: PHI in motion to a third
  party must be encrypted (TLS gives transport encryption, but the
  blob itself is unencrypted; whoever holds the bucket — or the
  remote-backup vendor's storage provider, or any future credential
  leak — has full plaintext PHI).
- §164.312(a)(2)(iv) — Encryption & decryption: the data at rest in
  the offsite bucket is unencrypted at the application layer. Vendor-
  side SSE may or may not be configured; the script doesn't enforce
  it.

## Recommended fix

1. **Deprecate `postscript.sh` as a PHI-shipping path.** Rename to
   `postscript.sh.unsafe` or delete entirely now that the encrypted
   variant `backup-offsite-sync.sh` exists and is wired to Phase 6.2.
2. **If the unencrypted path is retained for an operations-only target
   (e.g. an internal Hetzner mirror covered by a host-level BAA),
   rename the env vars to `REMOTE_BACKUP_HETZNER_*` and add a
   defense-in-depth check** that refuses to run unless
   `BACKBLAZE_*` is ALSO configured (so the encrypted path always
   exists alongside).
3. **Add a startup banner / log line** at sidecar boot showing which
   offsite paths are active, so an operator can see "Plaintext: ON,
   Encrypted: OFF" and react.

This is P0 because the activation surface is one env-var change and
the documentation actively encourages flipping it on.
