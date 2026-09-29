#!/bin/bash
# usage: run.sh <test-db-name> <manage.py test args...>
set -u
S=/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/rr2verify
export VERIFY_TEST_DB="$1"; shift
export TMPDIR=/tmp
export DJANGO_SETTINGS_MODULE=verify_settings
export QUILLMD_SECRET_KEY="synthetic-verify-$(date +%s%N)"
export QUILLMD_DB_USER=quillmd_qa QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731
export QUILLMD_DB_NAME=quillmd_qa_rr2_verify_base
export QUILLMD_STATE_DIR="$S/state"
QUILLMD_DB_PASSWORD="$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)"; export QUILLMD_DB_PASSWORD
unset QUILLMD_ENV_MANAGED ANTHROPIC_API_KEY OPENAI_API_KEY
cd "$S/rebuild"
exec /opt/meddoc-pro/.worktrees/v1-residuals/rebuild/.venv/bin/python -B manage.py test "$@" --noinput
