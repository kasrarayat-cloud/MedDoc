#!/usr/bin/env bash
# Runs named tests of mp2verify against the rebuild tree given as $1 (default: the worktree).
set -uo pipefail
S=/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/mp2-verify
TREE=${TREE:-/opt/meddoc-pro/.worktrees/v1-mapping-partial/rebuild}
mkdir -p "$S/state"
cd "$TREE"
env -i PATH=/usr/bin:/bin HOME="$S" TMPDIR=/tmp LANG=C.UTF-8 \
  QUILLMD_SECRET_KEY=synthetic-mp2-verify-not-a-secret-000000000000 \
  QUILLMD_DB_PASSWORD=unused-simpletestcase-only QUILLMD_DB_NAME=quillmd_qa_mp2_verify QUILLMD_DB_USER=quillmd_qa \
  QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 QUILLMD_STATE_DIR="$S/state" \
  PYTHONPATH="$S${EXTRA_PYTHONPATH:+:$EXTRA_PYTHONPATH}" \
  /opt/meddoc-pro/.worktrees/v1-mapping-partial/rebuild/.venv/bin/python -B manage.py test "$@" --verbosity 1
