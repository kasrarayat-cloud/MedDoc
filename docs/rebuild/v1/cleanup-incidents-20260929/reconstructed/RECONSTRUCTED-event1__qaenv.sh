# Source me. Sets the QA test environment without printing the password.
export TMPDIR=/tmp
export DJANGO_SETTINGS_MODULE=quillmd.settings
export QUILLMD_SECRET_KEY=synthetic-sonnet5-campaign-offline-tests-only-0000000000000
export QUILLMD_DB_HOST=127.0.0.1
export QUILLMD_DB_PORT=55731
export QUILLMD_DB_USER=quillmd_qa
export QUILLMD_DB_NAME=quillmd_qa_sonnet5
QUILLMD_DB_PASSWORD="$(cat /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password)"
export QUILLMD_DB_PASSWORD
export QUILLMD_AI_MODE=fixture
export QUILLMD_ADMIN_SITE=0
export QUILLMD_HTTPS=0
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
PY=/opt/meddoc-pro/.worktrees/v1-sonnet5-campaign/rebuild/.venv/bin/python
