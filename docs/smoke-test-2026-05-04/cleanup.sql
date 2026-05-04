-- ============================================================================
-- QuillMD smoke-test cleanup — 2026-05-04
-- ----------------------------------------------------------------------------
-- Run this AFTER PR review to remove all qa-smoke-* test artifacts from prod.
--
-- Order matters: visits before patients (FK), patients before user, user last.
-- All entities are scoped to the qa-smoke synthetic doctor user(s) so this
-- can NOT touch any real clinical data.
--
-- Usage:
--   docker compose exec -T postgres psql -U meddoc -d meddoc -f cleanup.sql
-- ============================================================================

BEGIN;

-- 1) Snapshot what will be deleted (for audit trail).
\echo '== Smoke-test users to be deleted:'
SELECT id, email, name, "createdAt"
FROM users
WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
ORDER BY "createdAt" DESC;

\echo '== Smoke-test patients (cross-reference):'
SELECT p.id, p.name, p."dateOfBirth", p."createdAt", u.email AS doctor
FROM patients p
JOIN users u ON u.id = p."userId"
WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
ORDER BY p."createdAt" DESC;

\echo '== Smoke-test visits:'
SELECT v.id, v.status, v."inputMode", v."createdAt", u.email AS doctor
FROM transcribe_visits v
JOIN users u ON u.id = v."userId"
WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
ORDER BY v."createdAt" DESC;

-- 2) Cascade delete from leaf to root.
DELETE FROM ai_calls WHERE "visitId" IN (
  SELECT v.id FROM transcribe_visits v
  JOIN users u ON u.id = v."userId"
  WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM audit_logs WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM session_logs WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM api_usage_events WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM api_usage_logs WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM doctor_edit_patterns WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM transcribe_visits WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM transcribe_md_patients WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM patients WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM accounts WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM sessions WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM auth_tokens WHERE email LIKE 'qa-smoke-%@quillmd-test.local';

DELETE FROM user_sessions WHERE "userId" IN (
  SELECT id FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
);

DELETE FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local';

-- 3) Verify nothing remains.
\echo '== Post-cleanup verification (all should be 0):'
SELECT
  (SELECT COUNT(*) FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local') AS users_remaining,
  (SELECT COUNT(*) FROM patients p JOIN users u ON u.id = p."userId" WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local') AS patients_remaining,
  (SELECT COUNT(*) FROM transcribe_visits v JOIN users u ON u.id = v."userId" WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local') AS visits_remaining;

COMMIT;

\echo '== Cleanup complete.'
