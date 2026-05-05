#!/usr/bin/env bash
# ============================================================================
# postgres-backup-local POST_BACKUP_COMMAND — DEPRECATED (Round 3 PR-C)
# ============================================================================
#
# This script previously mirrored /backups/last/ to an S3-compatible offsite
# bucket via `mc mirror` IF the REMOTE_BACKUP_S3_* env vars were populated.
# Round 3 audit (A05-P0-003) flagged this path as a plaintext offsite leg:
# the dumps were uploaded as gzip-only, with no age encryption, one env
# edit away from active.
#
# The Phase 6.2 host-cron script `scripts/postgres-offsite-cron.sh` (PR #110)
# is now the canonical encrypted offsite leg. It:
#   1. Reads the freshly-rotated dump from /opt/meddoc-pro/backups/last/
#   2. Encrypts with age using /etc/meddoc/offsite-backup-public.age
#      (with PR-C fingerprint validation — see infra/backup-offsite-sync.sh)
#   3. Uploads to Backblaze B2 via rclone
#
# This sidecar postscript is now a no-op so even an accidental
# REMOTE_BACKUP_S3_* env-var leak cannot cause unencrypted PHI to ship
# offsite. The local /backups/last/ rotation continues to work via the
# postgres-backup-local image's own cron — only the secondary push
# from this sidecar is removed.
#
# DO NOT re-introduce a mirror call here. The defense-in-depth model is:
# encryption happens BEFORE bytes leave the host, in a script the operator
# can audit, with an age-keypair the private half of which never lives on
# the VPS. mc mirror cannot offer that.
#
# Closes Round 3 PR-C audit fix #5 (Postgres backup encryption gap).

set -euo pipefail

echo "[postscript] no-op (Round 3 PR-C: encrypted offsite leg moved to host cron — see scripts/postgres-offsite-cron.sh)" >&2
exit 0
