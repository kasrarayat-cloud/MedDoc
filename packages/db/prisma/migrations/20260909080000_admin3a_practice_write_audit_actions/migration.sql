-- ADMIN-3a — THE `Practice` WRITE PATH GETS ITS AUDIT VOCABULARY.
--
-- ⚠️ THE FINDING THIS ANSWERS: there is NO write path to a `Practice` row
-- anywhere in the product. `practice.update|practices.update` over apps/ and
-- packages/ = 0 call sites, against a positive control of 15+ `user.update`.
--
-- FOUR FILED ROWS AND ONE STANDING RULING WAIT ON THAT SINGLE MISSING VERB:
--   · ADMIN-3  needs somebody to SET a specialty
--   · ADMIN-6  needs somebody to ARCHIVE a practice
--   · ADMIN-2a needs somebody to CHANGE A SLUG (195 of 199 are machine-generated)
--   · ruling #226 has been blocked since 2026-09-07, and says why in its own
--     words: "NO ADMIN PATH WRITES A PRACTICE ROW … and there is no
--     PRACTICE_ARCHIVED among the 156 AuditAction values."
--
-- Each was filed as though it owned the problem. This migration and the verb
-- beside it are the floor under all four.
--
-- ⚠️ PERMANENTLY IRREVERSIBLE. Postgres has no `ALTER TYPE … DROP VALUE`. Once
-- applied these three values exist for the life of the database, which is why
-- they are declared in §2.5 BEFORE the act and why the list is exactly three.
--
-- 156 -> 159.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_UPDATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ARCHIVED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_RESTORED';
