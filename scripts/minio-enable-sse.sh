#!/usr/bin/env bash
# scripts/minio-enable-sse.sh — Round 3 PR-C
# ============================================================================
# Closes Round 3 audit A05-P0-001 (MinIO has no SSE on the audio bucket).
#
# Enables MinIO server-side encryption (SSE-S3) on the transcribe-md-audio
# bucket. Idempotent — re-running is safe; `mc encrypt set sse-s3` overwrites
# the same configuration.
#
# WHAT THIS DOES (and doesn't)
# ----------------------------
# DOES: encrypts every object PUT into the bucket from now on with a
#       MinIO-managed key. GETs decrypt transparently.
# DOES NOT: re-encrypt objects already on disk before this script ran.
#       (See "RE-ENCRYPT EXISTING OBJECTS" section at the bottom.)
#
# This is SSE-S3, NOT SSE-KMS. SSE-S3 is the simpler-but-still-HIPAA-OK
# choice — keys are managed by MinIO itself rather than an external KMS
# service. SSE-KMS is overkill for a single-tenant pre-pilot; revisit
# when we move to multi-tenant or a HIPAA-eligible-cloud BAA mandates
# customer-managed keys.
#
# WHAT THIS DOESN'T COVER (Phase 6.3 follow-up)
# ---------------------------------------------
# /var/lib/docker volume that backs MinIO storage lives on the unencrypted
# root filesystem (/dev/sda2, no LUKS). Full-disk encryption of the MinIO
# data directory requires the same migration shape Phase 6.1 applied to
# Postgres: move /var/lib/docker/volumes/meddoc-pro_minio under
# /mnt/pgdata-encrypted (or new /mnt/minio-encrypted volume). That's
# Phase 6.3 / post-pilot scope; SSE-S3 here is the pre-pilot minimum.
#
# WHAT THIS DOESN'T COVER (re-encrypt-in-place gap)
# -------------------------------------------------
# SSE-S3 only encrypts NEW PUTs. Existing objects stay unencrypted on
# disk until rewritten. To rewrite all existing objects:
#   mc cp --recursive --md-preserve --enc-s3=local/transcribe-md-audio \
#     local/transcribe-md-audio/ /tmp/sse-rewrite/ \
#     && mc cp --recursive --md-preserve --enc-s3=local/transcribe-md-audio \
#         /tmp/sse-rewrite/ local/transcribe-md-audio/
# Pre-pilot we have <100 audio files; post-pilot run on next maint window.
#
# REQUIREMENTS
# ------------
# - mc (MinIO client) installed on PATH
# - MINIO_ROOT_USER + MINIO_ROOT_PASSWORD set in env (NOT on argv —
#   visible in /proc/*/cmdline)
#
# EXIT CODES
# ----------
# 0  : SSE configured + verified
# 1  : missing prereqs
# 2  : `mc encrypt set` failed
# 3  : `mc encrypt info` returned a status other than enabled

set -euo pipefail

ALIAS="${MINIO_ALIAS:-local}"
ENDPOINT="${MINIO_ENDPOINT:-http://127.0.0.1:9000}"
BUCKET="${TRANSCRIBE_MD_MINIO_BUCKET:-transcribe-md-audio}"

if ! command -v mc >/dev/null 2>&1; then
  echo "[minio-enable-sse] ERROR: mc (MinIO client) not on PATH." >&2
  echo "  Install: curl -sL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc" >&2
  exit 1
fi

if [ -z "${MINIO_ROOT_USER:-}" ] || [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
  echo "[minio-enable-sse] ERROR: MINIO_ROOT_USER + MINIO_ROOT_PASSWORD must be set in env." >&2
  echo "  Source the operator's .env first: 'set -a && . /opt/meddoc-pro/.env && set +a'" >&2
  exit 1
fi

echo "[minio-enable-sse] configuring mc alias '$ALIAS' -> $ENDPOINT"
mc alias set "$ALIAS" "$ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1

if ! mc ls "$ALIAS/$BUCKET" >/dev/null 2>&1; then
  echo "[minio-enable-sse] ERROR: bucket '$ALIAS/$BUCKET' does not exist." >&2
  echo "  transcribe-md-worker creates it on first start; verify it's healthy." >&2
  exit 1
fi

echo "[minio-enable-sse] setting SSE-S3 on '$ALIAS/$BUCKET'"
if ! mc encrypt set sse-s3 "$ALIAS/$BUCKET"; then
  echo "[minio-enable-sse] ERROR: 'mc encrypt set sse-s3' failed." >&2
  exit 2
fi

echo "[minio-enable-sse] verifying with 'mc encrypt info'"
INFO=$(mc encrypt info "$ALIAS/$BUCKET" 2>&1)
echo "$INFO"

if ! echo "$INFO" | grep -qiE "(enabled|sse-s3|AES256)"; then
  echo "[minio-enable-sse] ERROR: encryption did not appear to take effect:" >&2
  echo "$INFO" >&2
  exit 3
fi

echo "[minio-enable-sse] OK - SSE-S3 active on $ALIAS/$BUCKET."
echo
echo "[minio-enable-sse] Reminder: existing objects (PUT before this run)"
echo "                   are NOT re-encrypted. Run the one-shot rewrite"
echo "                   sweep documented in this script's header on the"
echo "                   next maintenance window."
