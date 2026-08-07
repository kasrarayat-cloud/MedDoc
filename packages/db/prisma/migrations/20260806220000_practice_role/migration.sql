-- ===========================================================================
-- T6 — PracticeRole on the User↔practice edge.
-- ---------------------------------------------------------------------------
-- RULING, 2026-08-06 (docs/foundation/RULINGS.md):
--
--   TWO AXES, NEW FIELD. The practice role is a NEW enum
--   `PracticeRole { OWNER, CLINICIAN, TECH }` on `users`, never values added to
--   `UserRole`. The legacy enum conflates a CLINICAL distinction (DOCTOR/STAFF)
--   with a PLATFORM-PRIVILEGE one (ADMIN/SUPER_ADMIN) and cannot express
--   ownership of a practice at all. `UserRole` survives as the legacy platform
--   axis, marked do-not-extend.
--
-- ⚠️ THE DERIVATION IS STRUCTURAL, NOT THE LEGACY LABEL.
--
--   sole member of their practice  →  OWNER
--
-- The old `role` column is NOT consulted. A user is not a practice OWNER because
-- somebody once typed DOCTOR; they are an OWNER because they are structurally
-- alone in their practice and there is nobody else it could be.
--
-- ⚠️⚠️ THE RULING'S PREMISE DOES NOT HOLD, AND THIS IS THE DEVIATION.
--
-- The ruling reads: "every active user today is the sole member of their
-- personal practice, so all become OWNER of their own practice regardless of old
-- role." MEASURED ON PRODUCTION 2026-08-06, that is not true:
--
--     active users .............................. 196
--     sole member of their practice ............. 178
--     in a MULTI-MEMBER practice ................  18   ← the premise misses these
--     active with no practice ...................   0
--
--   Main Clinic 11 · QA Audit Practice 5 · Test Clinic B 2
--
-- Taken literally, those 18 would derive NULL and then trip the constraint at
-- the bottom of this file — the migration would abort. Correct behaviour for the
-- guard; useless as a migration.
--
-- SO THIS FILE APPLIES A STATED RULE FOR THEM: multi-member practices also get
-- OWNER, for every member. Three reasons, in order of weight:
--
--   1. **A migration must not DOWNGRADE anybody.** Today every member of a
--      practice can do everything in it — there is no role gate yet. Deriving
--      CLINICIAN or TECH for someone would remove a capability they currently
--      have, based on a hierarchy nobody has stated. OWNER preserves exactly
--      today's behaviour, which is the only defensible default.
--   2. **Any alternative is a guess.** "Earliest member owns it" is an
--      invention; the schema records no designation, so there is nothing to
--      derive from. The ruling's own principle — derive from STRUCTURE — has no
--      structure to read here.
--   3. **Nothing is at stake in these three.** They hold ZERO visits and ZERO
--      patients between them (measured, with a positive control against the two
--      practices that DO hold data: Solo—kasra 24, Solo—Kash 2). Whatever these
--      rows say, no clinical record is governed by it.
--
-- Real CLINICIAN/TECH assignments arrive ONLY via T8 invites carrying a role.
-- This migration mints OWNER and nothing else, and the counts below are printed
-- so the split is visible in the deploy log rather than inferred afterwards.
--
-- ⚠️ ABORTS BEFORE THE CONSTRAINT if any active member is left underivable —
-- T3's shape. A partially-backfilled column that then takes a constraint is a
-- migration that half-ran and reported success.
-- ===========================================================================

CREATE TYPE "PracticeRole" AS ENUM ('OWNER', 'CLINICIAN', 'TECH');

ALTER TABLE "users" ADD COLUMN "practiceRole" "PracticeRole";

-- Report the split BEFORE writing, so the deploy log records what was found
-- rather than only what was done.
DO $$
DECLARE
  sole_n   int;
  multi_n  int;
  nopr_n   int;
BEGIN
  SELECT count(*) INTO sole_n FROM users u
   WHERE u."isActive" AND u."practiceId" IS NOT NULL
     AND (SELECT count(*) FROM users x WHERE x."practiceId" = u."practiceId") = 1;
  SELECT count(*) INTO multi_n FROM users u
   WHERE u."isActive" AND u."practiceId" IS NOT NULL
     AND (SELECT count(*) FROM users x WHERE x."practiceId" = u."practiceId") > 1;
  SELECT count(*) INTO nopr_n FROM users u
   WHERE u."isActive" AND u."practiceId" IS NULL;

  RAISE NOTICE '[practiceRole] active sole-member=% multi-member=% no-practice=%',
    sole_n, multi_n, nopr_n;

  IF multi_n > 0 THEN
    RAISE NOTICE '[practiceRole] % active users are in MULTI-MEMBER practices and take OWNER by the stated rule (no downgrade in a migration). See this file''s header.', multi_n;
  END IF;
END $$;

-- The backfill. Every ACTIVE user WITH a practice becomes OWNER of it.
-- Deactivated rows and practice-less rows are deliberately left NULL.
UPDATE "users"
   SET "practiceRole" = 'OWNER'
 WHERE "isActive" = true
   AND "practiceId" IS NOT NULL;

-- ⚠️ ABORT ON ANY UNDERIVABLE ROW, BEFORE THE CONSTRAINT EXISTS.
DO $$
DECLARE
  missing int;
BEGIN
  SELECT count(*) INTO missing
    FROM users
   WHERE "isActive" = true
     AND "practiceId" IS NOT NULL
     AND "practiceRole" IS NULL;

  IF missing > 0 THEN
    RAISE EXCEPTION
      '[practiceRole] % active users with a practice have no practiceRole. The constraint below would fail and the column would be half-backfilled. Refusing.', missing;
  END IF;
END $$;

-- ⚠️ THE INVARIANT, ENFORCED BY THE DATABASE RATHER THAN BY CONVENTION.
-- An ACTIVE user who belongs to a practice MUST have a role in it. The two NULL
-- cases are stated positively rather than left as an absence:
--   * deactivated  — no role in a practice they can no longer enter
--   * no practice  — nothing to have a role in
ALTER TABLE "users"
  ADD CONSTRAINT "users_active_member_has_practice_role"
  CHECK (
    "isActive" = false
    OR "practiceId" IS NULL
    OR "practiceRole" IS NOT NULL
  );

-- Roles are read on every practice-scoped action; the sign gate reads one per
-- request. Declared in schema.prisma in this same commit — a raw index that the
-- schema does not know about is drift (AGENTS.md).
CREATE INDEX "users_practiceId_practiceRole_idx"
  ON "users" ("practiceId", "practiceRole");
