#!/usr/bin/env bash
# Usage: run.sh <worktree-rebuild-dir> <manage.py args...>
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
rebuild=$1; shift
export TMPDIR=/tmp
export PYTHONPATH="$here${EXTRA_PYTHONPATH:+:$EXTRA_PYTHONPATH}"
export DJANGO_SETTINGS_MODULE=resid_settings
export QUILLMD_SECRET_KEY=synthetic-residuals-only-key-no-external-access-20260929
QUILLMD_DB_PASSWORD=$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)
export QUILLMD_DB_PASSWORD
export QUILLMD_DB_NAME=quillmd_qa_resid_base QUILLMD_DB_USER=quillmd_qa QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731
export QUILLMD_AI_MODE=fixture QUILLMD_ADMIN_SITE=0 QUILLMD_HTTPS=0
export QUILLMD_STATE_DIR="$here/../state"
unset QUILLMD_ENV_MANAGED
cd "$rebuild"
exec /opt/meddoc-pro/.worktrees/v1-residuals/rebuild/.venv/bin/python -B manage.py "$@"
