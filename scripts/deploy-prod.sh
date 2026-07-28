#!/usr/bin/env bash
# ============================================================================
# Rolling deploy of the transcribe-md app + worker to production.
# ----------------------------------------------------------------------------
# This exists because the runbook's prose version failed silently on 2026-07-28.
# The three things it encodes, each bought with a real incident:
#
#   1. db-migrate is ALWAYS rebuilt, alongside the app services.
#      `docker compose run --rm db-migrate` runs whatever image was last built.
#      A deploy that rebuilt only the app services ran migrate from a stale
#      image, which printed "79 migrations found / No pending migrations to
#      apply" and exited 0 — while the repo had eighty. Nothing was applied and
#      nothing said so.
#
#   2. The migration state is ASSERTED after migrating, not assumed.
#      Rebuilding is a step someone can forget. The assertion cannot be
#      forgotten, because it aborts the deploy. It compares the repo against
#      the database and knows nothing about how migrate was invoked.
#
#   3. The full log is written to a FILE, never piped through `tail`.
#      The first attempt was run as `deploy.sh | tail -50`, which discarded the
#      backup and migration output — the two lines that would have shown the
#      no-op. The record of a deploy must outlive the terminal.
#
# Ingress note: host nginx owns 80/443. Nothing here touches Caddy or nginx.
#
# Usage:  bash scripts/deploy-prod.sh [--skip-backup]
# Exit:   0 = deployed · non-zero = aborted (nothing recreated)
# ============================================================================
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="docs/deploy-logs"
mkdir -p "$LOG_DIR" backups
LOG="$LOG_DIR/deploy-$TS.log"

# Everything from here is teed to the log. `tee` (not a pipe into tail) so the
# operator still sees it live AND the record survives.
exec > >(tee -a "$LOG") 2>&1

echo "=== deploy $TS ==="
echo "commit: $(git log --oneline -1)"
echo "branch: $(git branch --show-current)"
echo "log:    $LOG"
echo

if [ "${1:-}" != "--skip-backup" ]; then
  echo "=== 1. pre-deploy backup ==="
  BACKUP="backups/pre_deploy_${TS}.sql.gz"
  docker compose exec -T postgres pg_dump -U meddoc -d meddoc --no-owner --no-acl | gzip > "$BACKUP"
  ls -lh "$BACKUP"
  echo
fi

echo "=== 2. build db-migrate (UNCONDITIONAL — see the header) ==="
docker compose build db-migrate
echo

echo "=== 3. apply migrations ==="
docker compose run --rm db-migrate
echo

echo "=== 4. ASSERT the migrations actually landed ==="
# The backstop. A stale-image no-op exits 0 with a reassuring message, so the
# exit code of step 3 proves nothing on its own.
if ! bash scripts/assert-migrations-applied.sh; then
  echo
  echo "🔴 ABORTING THE DEPLOY — the database is not where the repo says it should be."
  echo "   Nothing has been rebuilt or recreated; production is untouched."
  exit 1
fi
echo

echo "=== 5. build app + worker (sequential — this VPS cannot parallel-build) ==="
docker compose build transcribe-md-worker
docker compose build transcribe-md
echo

echo "=== 6. recreate ==="
docker compose up -d transcribe-md transcribe-md-worker
echo

echo "=== 7. settle, then health ==="
sleep 30
docker compose ps --format '{{.Service}}\t{{.State}}\t{{.Status}}' | grep -E 'transcribe-md'
echo "app /api/health: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://app.quillmd.com/api/health)"
echo
echo "=== deploy complete — full log at $LOG ==="
