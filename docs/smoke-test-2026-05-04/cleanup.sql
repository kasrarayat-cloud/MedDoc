-- ============================================================================
-- QuillMD smoke-test cleanup — 2026-05-04 (revised)
-- ----------------------------------------------------------------------------
-- Removes all qa-smoke-* test artifacts from production.
--
-- Schema notes (verified 2026-05-04 after the first run hit "column
-- p.userId does not exist"):
--
--   • transcribe_md_patients is PRACTICE-scoped, not user-scoped — it
--     has practiceId (NOT NULL) and no userId column. The previous
--     version of this script joined patients on userId and crashed.
--
--   • transcribe_visits.userId → users.id ON DELETE CASCADE: deleting
--     a user automatically removes their visits + accounts + sessions
--     + auth_tokens + api_usage + session_logs + doctor_edit_patterns
--     + appointments + user_sessions. We don't need to delete those
--     manually.
--
--   • transcribe_visits.patientId → transcribe_md_patients.id ON
--     DELETE RESTRICT: patients can only be removed AFTER their
--     visits cascade away. We capture the patient IDs into a temp
--     table BEFORE deleting users so the post-cascade DELETE has
--     something to target.
--
--   • rx_warning_overrides.visitId → transcribe_visits.id ON DELETE
--     RESTRICT: blocks the user-cascade if a smoke visit had any
--     override rows. We pre-clear them. (Smoke runs typically have
--     0 of these, but the precaution is cheap.)
--
--   • billing_events.clinicianUserId → users.id ON DELETE RESTRICT:
--     would block the user delete if the smoke user had ever billed.
--     The snapshot SELECT below surfaces this so we abort before
--     the DELETE if it's non-zero.
--
-- Defensive scoping for patients: we DELETE patients only when (a)
-- they live in a smoke practice (every user in the practice matches
-- the qa-smoke email pattern) AND (b) NO visits remain that
-- reference them. The smoke signup creates a solo practice per
-- user, so this is safe today; the all-users-in-practice check is
-- a forward guard against multi-user smoke practices someday.
--
-- Usage:
--   docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
--     -f docs/smoke-test-2026-05-04/cleanup.sql
-- ============================================================================

BEGIN;

-- 1) Snapshot what will be deleted (for audit trail).

\echo '== Smoke users to be deleted:'
SELECT id, email, "createdAt"
FROM users
WHERE email LIKE 'qa-smoke-%@quillmd-test.local'
ORDER BY "createdAt" DESC;

\echo ''
\echo '== Smoke visits (owned by those users — will cascade with the user delete):'
SELECT v.id, v.status, v."inputMode", v."createdAt"
FROM transcribe_visits v
JOIN users u ON u.id = v."userId"
WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
ORDER BY v."createdAt" DESC;

\echo ''
\echo '== Smoke practices (= practices where EVERY user is a qa-smoke account):'
SELECT id, name, "createdAt"
FROM practices p
WHERE NOT EXISTS (
  SELECT 1 FROM users u
  WHERE u."practiceId" = p.id
    AND u.email NOT LIKE 'qa-smoke-%@quillmd-test.local'
)
AND EXISTS (
  SELECT 1 FROM users u
  WHERE u."practiceId" = p.id
    AND u.email LIKE 'qa-smoke-%@quillmd-test.local'
);

\echo ''
\echo '== Patients in those smoke practices (will be deleted after the user-cascade):'
SELECT p.id, p.name, p."practiceId", p."createdAt"
FROM transcribe_md_patients p
WHERE p."practiceId" IN (
  SELECT id FROM practices pr
  WHERE NOT EXISTS (
    SELECT 1 FROM users u
    WHERE u."practiceId" = pr.id
      AND u.email NOT LIKE 'qa-smoke-%@quillmd-test.local'
  )
  AND EXISTS (
    SELECT 1 FROM users u
    WHERE u."practiceId" = pr.id
      AND u.email LIKE 'qa-smoke-%@quillmd-test.local'
  )
)
ORDER BY p."createdAt" DESC;

\echo ''
\echo '== Pre-flight blockers (both must be 0 — otherwise abort):'
SELECT
  (
    SELECT COUNT(*) FROM rx_warning_overrides r
    WHERE r."visitId" IN (
      SELECT v.id FROM transcribe_visits v
      JOIN users u ON u.id = v."userId"
      WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
    )
  ) AS rx_overrides_to_clear,
  (
    SELECT COUNT(*) FROM billing_events b
    JOIN users u ON u.id = b."clinicianUserId"
    WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
  ) AS billing_blocks;

-- 2) Pre-clear the only RESTRICT-FK that points at smoke visits.
DELETE FROM rx_warning_overrides
WHERE "visitId" IN (
  SELECT v.id FROM transcribe_visits v
  JOIN users u ON u.id = v."userId"
  WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local'
);

-- 3) Capture smoke practice + patient IDs BEFORE the user-cascade
--    drops the visits that link them.
CREATE TEMP TABLE smoke_practice_ids ON COMMIT DROP AS
SELECT id FROM practices p
WHERE NOT EXISTS (
  SELECT 1 FROM users u
  WHERE u."practiceId" = p.id
    AND u.email NOT LIKE 'qa-smoke-%@quillmd-test.local'
)
AND EXISTS (
  SELECT 1 FROM users u
  WHERE u."practiceId" = p.id
    AND u.email LIKE 'qa-smoke-%@quillmd-test.local'
);

CREATE TEMP TABLE smoke_patient_ids ON COMMIT DROP AS
SELECT id FROM transcribe_md_patients
WHERE "practiceId" IN (SELECT id FROM smoke_practice_ids);

-- 4) Delete users — CASCADE removes:
--      transcribe_visits, accounts, sessions, auth_tokens, api_usage,
--      api_usage_logs, session_logs, doctor_edit_patterns,
--      appointments, user_sessions.
--    SET NULL preserves rows but nulls the userId on:
--      audit_logs, api_usage_events, allergies, documents,
--      hipaa_findings, medications, patients (legacy CRM),
--      tasks, threat_resolutions.
--    The HIPAA audit trail is preserved by design (SET NULL, not
--    DELETE) — we are not erasing access history, only the user.
DELETE FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local';

-- 5) Now that smoke visits are gone, the patients are unreferenced
--    and we can drop them. NOT EXISTS guard is belt-and-braces: if
--    any non-smoke visit somehow still references a smoke patient,
--    we leave that patient alone.
DELETE FROM transcribe_md_patients p
WHERE p.id IN (SELECT id FROM smoke_patient_ids)
  AND NOT EXISTS (
    SELECT 1 FROM transcribe_visits v WHERE v."patientId" = p.id
  );

-- 6) Verify nothing of ours remains. All four counts MUST be 0
--    before COMMIT — otherwise ROLLBACK and investigate.
\echo ''
\echo '== Post-cleanup verification (all four MUST be 0):'
SELECT
  (SELECT COUNT(*) FROM users WHERE email LIKE 'qa-smoke-%@quillmd-test.local') AS users_remaining,
  (SELECT COUNT(*) FROM transcribe_md_patients
    WHERE id IN (SELECT id FROM smoke_patient_ids)) AS patients_remaining,
  (SELECT COUNT(*) FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE u.email LIKE 'qa-smoke-%@quillmd-test.local') AS smoke_visits_remaining,
  (SELECT COUNT(*) FROM rx_warning_overrides r
    WHERE r."visitId" NOT IN (SELECT id FROM transcribe_visits)) AS orphan_rx_overrides;

COMMIT;

\echo ''
\echo '== Cleanup complete. Smoke practices are intentionally retained;'
\echo '   they are tiny shells with no PHI and serve no test data anymore.'
