#!/bin/bash
# Usage: run-tests.sh <label>...   (runs from the worktree's rebuild/, one run at a time, keepdb)
set -u
HERE=/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/pyenv
cd /opt/meddoc-pro/.worktrees/v1-residuals/rebuild
export TMPDIR=/tmp
export PYTHONPATH="$HERE"
export DJANGO_SETTINGS_MODULE=resid2_settings
export QUILLMD_SECRET_KEY=synthetic-resid2-test-only-key-no-external-access
export QUILLMD_DB_NAME=quillmd_qa_resid2_main
export QUILLMD_DB_USER=quillmd_qa
export QUILLMD_DB_PASSWORD="$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)"
export QUILLMD_DB_HOST=127.0.0.1
export QUILLMD_DB_PORT=55731
export QUILLMD_AI_MODE=fixture
export QUILLMD_ADMIN_SITE=0
export QUILLMD_HTTPS=0
exec .venv/bin/python -B manage.py test --noinput --keepdb --parallel 1 "$@"
