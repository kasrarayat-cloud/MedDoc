#!/bin/bash
# Runs the ops campaign tests under Django's test runner on the QA server (test DB test_<NAME>). Never prints the password.
set -u
WT=/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild
NAME="${TEST_DB_NAME:-quillmd_qa_repair}"
case "$NAME" in quillmd_qa_sonnet5) echo "refusing the live database name" >&2; exit 2;; quillmd_qa_*) ;; *) echo "not a QA name" >&2; exit 2;; esac
STATE=$(mktemp -d /tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/state-XXXXXX)
trap 'rm -rf "$STATE"' EXIT
cd "$WT"
PW="$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)"
env -i PATH=/usr/bin:/bin HOME="$HOME" LANG=C.UTF-8 TMPDIR=/tmp \
  DJANGO_SETTINGS_MODULE=quillmd.settings QUILLMD_SECRET_KEY=offline-test-secret-key-not-used-anywhere-000000 \
  QUILLMD_DB_NAME="$NAME" QUILLMD_DB_USER=quillmd_qa QUILLMD_DB_PASSWORD="$PW" QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 \
  QUILLMD_STATE_DIR="$STATE" \
  "$WT/.venv/bin/python" -B manage.py test --noinput "$@"
