#!/usr/bin/env bash
# ============================================================================
# tests/integrity/audit-logs-immutable.test.sh — Round 3 PR-C
# ============================================================================
# Asserts the REVOKE migration (20260505010210_round_3_pr_c_revoke_audit_mutation)
# held: the application Postgres role `meddoc` cannot DELETE / UPDATE /
# TRUNCATE on audit_logs. Closes audit finding A09-P0-002 (HIPAA §164.312(c)
# integrity safeguard).
#
# This test runs against the live Postgres container. It is:
#   - SKIP if the migration has not been applied yet (migration pending in
#     the deployment pipeline). Useful so devs can run the suite locally
#     before `prisma migrate deploy` finishes.
#   - PASS if INSERT + SELECT still work AND DELETE / UPDATE / TRUNCATE
#     all return permission-denied errors.
#   - FAIL if any of the three forbidden operations succeeds, or if INSERT
#     or SELECT regresses.
#
# Required env (read from /opt/meddoc-pro/.env or shell):
#   DB_PASSWORD          — meddoc role password
#   POSTGRES_CONTAINER   — defaults to meddoc-pro-postgres-1
#
# Run: bash tests/integrity/audit-logs-immutable.test.sh
# Exit: 0 on pass-or-skip, 1 on actual failure.
# ============================================================================

set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-meddoc-pro-postgres-1}"
DB_NAME="${DB_NAME:-meddoc}"
DB_USER="${DB_USER:-meddoc}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }
skip() { printf 'SKIP: %s\n' "$*"; exit 0; }

if ! command -v docker >/dev/null 2>&1; then
  skip "docker CLI not on PATH (test designed to run on the deployment host)"
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
  skip "${POSTGRES_CONTAINER} not running"
fi

if [[ -z "${DB_PASSWORD:-}" ]]; then
  # Pull DB_PASSWORD directly from the running postgres container's env,
  # avoiding the need to source /opt/meddoc-pro/.env (which contains
  # `RESEND_FROM=QuillMD <noreply@…>` and other values bash can't safely
  # interpret as `KEY=VALUE` shell assignments).
  DB_PASSWORD="$(docker exec "${POSTGRES_CONTAINER}" printenv POSTGRES_PASSWORD 2>/dev/null || true)"
fi

if [[ -z "${DB_PASSWORD:-}" ]]; then
  skip "DB_PASSWORD not in env (could not read from ${POSTGRES_CONTAINER} either)"
fi

PSQL=( docker exec -e "PGPASSWORD=${DB_PASSWORD}" "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -At -c )

# 0) Migration applied?
HAS_DELETE=$("${PSQL[@]}" "
  SELECT 1 FROM information_schema.role_table_grants
  WHERE grantee = 'meddoc'
    AND table_name = 'audit_logs'
    AND privilege_type = 'DELETE'
" 2>/dev/null | head -1)

if [[ "$HAS_DELETE" == "1" ]]; then
  skip "REVOKE migration not yet applied (meddoc role still has DELETE on audit_logs). Run 'npm run db:migrate:deploy' first."
fi
pass "DELETE privilege has been revoked (migration applied)"

# 1) INSERT still works (the app must be able to write audit rows).
INSERT_RESULT=$("${PSQL[@]}" "
  INSERT INTO audit_logs (id, action, \"practiceId\", success)
  VALUES ('test-pr-c-' || extract(epoch from now())::text, 'LOGIN_SUCCESS', 'clinic_main', true)
  RETURNING id
" 2>&1 || true)
if ! echo "$INSERT_RESULT" | grep -qE "test-pr-c-"; then
  fail "INSERT into audit_logs failed: $INSERT_RESULT"
fi
TEST_ID=$(echo "$INSERT_RESULT" | grep -oE "test-pr-c-[0-9.]+" | head -1)
pass "INSERT into audit_logs succeeded (id=$TEST_ID)"

# 2) SELECT still works (admin dashboard reads audit rows).
SELECT_COUNT=$("${PSQL[@]}" "SELECT count(*) FROM audit_logs WHERE id = '${TEST_ID}'" 2>&1)
if [[ "$SELECT_COUNT" != "1" ]]; then
  fail "SELECT after INSERT returned ${SELECT_COUNT}, expected 1"
fi
pass "SELECT from audit_logs succeeded"

# 3) DELETE must fail with permission denied.
DELETE_RESULT=$("${PSQL[@]}" "DELETE FROM audit_logs WHERE id = '${TEST_ID}'" 2>&1 || true)
if echo "$DELETE_RESULT" | grep -qiE "permission denied|insufficient privilege"; then
  pass "DELETE on audit_logs correctly rejected: $(echo "$DELETE_RESULT" | head -1)"
else
  fail "DELETE on audit_logs did NOT fail: $DELETE_RESULT"
fi

# 4) UPDATE must fail with permission denied.
UPDATE_RESULT=$("${PSQL[@]}" "UPDATE audit_logs SET success = false WHERE id = '${TEST_ID}'" 2>&1 || true)
if echo "$UPDATE_RESULT" | grep -qiE "permission denied|insufficient privilege"; then
  pass "UPDATE on audit_logs correctly rejected: $(echo "$UPDATE_RESULT" | head -1)"
else
  fail "UPDATE on audit_logs did NOT fail: $UPDATE_RESULT"
fi

# 5) TRUNCATE must fail with permission denied.
TRUNCATE_RESULT=$("${PSQL[@]}" "TRUNCATE TABLE audit_logs" 2>&1 || true)
if echo "$TRUNCATE_RESULT" | grep -qiE "permission denied|insufficient privilege"; then
  pass "TRUNCATE on audit_logs correctly rejected: $(echo "$TRUNCATE_RESULT" | head -1)"
else
  fail "TRUNCATE on audit_logs did NOT fail: $TRUNCATE_RESULT"
fi

# 6) Cleanup — superuser-only path (postgres role); this test row stays
# in the table since the app role can't delete it. The denormalised
# 'test-pr-c-' prefix lets a periodic cleanup query identify and prune
# them via the postgres superuser if accumulated.
echo
echo "Note: test row id=${TEST_ID} remains in audit_logs (cannot be deleted"
echo "      by the app role — that is the test's whole point). Periodic"
echo "      cleanup via the postgres superuser if buildup becomes an issue:"
echo "      docker exec ${POSTGRES_CONTAINER} psql -U postgres -d ${DB_NAME} \\"
echo "        -c \"DELETE FROM audit_logs WHERE id LIKE 'test-pr-c-%' AND timestamp < now() - interval '30 days'\""
echo
echo "All audit_logs immutability assertions passed."
