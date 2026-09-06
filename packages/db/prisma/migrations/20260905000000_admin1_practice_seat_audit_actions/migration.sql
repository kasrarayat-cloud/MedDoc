-- ADMIN-1 — the practice-administration audit vocabulary. Three values, one act.
--
-- ⚠️ POSTGRES HAS NO `ALTER TYPE … DROP VALUE`. Every line below is permanent.
-- `IF NOT EXISTS` keeps the migration idempotent so a partial application cannot
-- wedge a deploy half-way through a three-statement change.
--
--   PRACTICE_SEAT_INVITED    an OWNER minted a seat invite — practice + role
--   PRACTICE_ROLE_CHANGED    a member's practiceRole moved, old -> new
--   PRACTICE_ADMIN_REFUSED   the administration guard refused a caller
--
-- ⚠️ WHY NOT REUSE `USER_ROLE_CHANGED`. That value is written by the
-- meddoc-pro system-admin app for the SYSTEM role (`actions.ts:353`), which is a
-- DIFFERENT AXIS from the practice role. This row's own scope note names
-- axis-conflation as the mistake that produced the 48-surface misreading; one
-- label covering both would make a practice demotion and a super-admin grant
-- indistinguishable in an append-only trail.
--
-- ⚠️ AND THE REFUSAL GETS ITS OWN LABEL BECAUSE A GATE NOTHING RECORDS IS ONE
-- PATH AWAY FROM NOT EXISTING — the sign route's own reasoning
-- (`SIGN_BLOCKED_ROLE_NOT_PERMITTED`), applied to the surface that hands out
-- seats.
--
-- 153 -> 156.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_SEAT_INVITED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ROLE_CHANGED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ADMIN_REFUSED';
