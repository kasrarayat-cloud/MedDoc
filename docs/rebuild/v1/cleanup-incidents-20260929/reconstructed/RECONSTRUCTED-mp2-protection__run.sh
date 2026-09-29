#!/bin/bash
S=/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/mp2-protection
cd $S/rebuild
export TMPDIR=/tmp PYTHONPATH=$S/guard QUILLMD_SECRET_KEY=refutation-scratch-only QUILLMD_DB_USER=quillmd_qa QUILLMD_DB_PORT=55731 QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_NAME=quillmd_qa_mp2_protection QUILLMD_STATE_DIR=$S/state
export QUILLMD_DB_PASSWORD="$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)"
exec /opt/meddoc-pro/.worktrees/v1-mapping-partial/rebuild/.venv/bin/python -B "$@"
