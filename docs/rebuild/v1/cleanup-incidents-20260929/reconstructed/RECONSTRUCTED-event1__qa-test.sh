#!/usr/bin/env bash
# Run Django tests for the campaign worktree against the synthetic QA server. Usage: qa-test.sh <dbname> <labels...>
set -euo pipefail
WT=/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign
test ! -e "$WT/rebuild/.env" || { echo "rebuild/.env exists: refusing" >&2; exit 3; }
DB="$1"; shift
case "$DB" in quillmd_qa_*) ;; *) echo "not a QA name" >&2; exit 3;; esac
PW_FILE=/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password
cd "$WT/rebuild"
export TMPDIR=/tmp DJANGO_SETTINGS_MODULE=quillmd.settings QUILLMD_SECRET_KEY=synthetic-offline-test-secret-key-000000000000 \
  QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 QUILLMD_DB_USER=quillmd_qa QUILLMD_DB_NAME="$DB"
QUILLMD_DB_PASSWORD="$(cat "$PW_FILE")"; export QUILLMD_DB_PASSWORD
exec /opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild/.venv/bin/python -B manage.py test --noinput "$@"
