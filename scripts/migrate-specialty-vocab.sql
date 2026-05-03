-- =============================================================================
-- One-time data migration: normalize specialty vocab to the shared catalog
-- (P2-002 fix). Run AFTER the code that introduces the new vocab is deployed.
-- =============================================================================
--
-- Why
--   Pre-fix, two columns held two different vocabs:
--     users.specialty           — lowercase short ids ('cardiology', 'pain',
--                                  'ortho', 'primary', 'pulmonology',
--                                  'ophthalmology').
--     transcribe_visits.specialty — display names ('Cardiology', 'Orthopedics',
--                                  'Primary Care / Family Medicine', 'Internal
--                                  Medicine').
--   The shared catalog (packages/shared/src/specialties.ts) ships a single
--   canonical id list. New writes already use those ids; this script
--   normalizes the legacy rows in place so downstream queries (analytics,
--   audit trails, billing reports) can rely on the column carrying a
--   single enum value.
--
-- Pre-flight (read-only audit at the time this script was written)
--   users.specialty:
--     NULL          | 36
--     cardiology    |  1
--   transcribe_visits.specialty:
--     Orthopedics                    | 26
--     Cardiology                     | 22
--     Primary Care / Family Medicine |  3
--     Internal Medicine              |  2
--
--   Total rows touched: 53 transcribe_visits rows, 0 users rows
--   ('cardiology' is already canonical).
--
-- Idempotency
--   Each UPDATE is gated on the legacy value, so re-running the script is a
--   no-op once the rows are normalized.
--
-- Rollback
--   Display names → ids is a one-way mapping for the rows where the legacy
--   value already matched a real specialty (e.g. 'Cardiology' → 'cardiology').
--   For 'Internal Medicine' (specialty dropped in this fix) we map to
--   'primary-care' which loses information — if rollback is needed, restore
--   from a pre-migration logical backup. /opt/meddoc-pro/backups/ contains a
--   nightly dump per the postgres-backup sidecar.
-- =============================================================================

BEGIN;

-- transcribe_visits.specialty — display name → canonical id ---------------

UPDATE transcribe_visits SET specialty = 'cardiology'
  WHERE specialty = 'Cardiology';

UPDATE transcribe_visits SET specialty = 'orthopedics'
  WHERE specialty = 'Orthopedics';

UPDATE transcribe_visits SET specialty = 'primary-care'
  WHERE specialty IN ('Primary Care / Family Medicine', 'Internal Medicine');

-- users.specialty — short id → canonical id (no rows currently affected,
-- left here for completeness so a re-run after a write to the legacy vocab
-- still normalizes correctly). -------------------------------------------

UPDATE users SET specialty = 'pain-management'  WHERE specialty = 'pain';
UPDATE users SET specialty = 'orthopedics'      WHERE specialty = 'ortho';
UPDATE users SET specialty = 'primary-care'     WHERE specialty = 'primary';
UPDATE users SET specialty = NULL               WHERE specialty IN ('pulmonology', 'ophthalmology', 'internal-medicine', 'ob-gyn');

-- Audit ------------------------------------------------------------------
-- Confirm zero non-canonical rows remain. If either query returns >0 rows,
-- the catalog or this script is out of sync — abort.
DO $$
DECLARE
  bad_visits INT;
  bad_users INT;
BEGIN
  SELECT COUNT(*) INTO bad_visits
    FROM transcribe_visits
    WHERE specialty IS NOT NULL
      AND specialty NOT IN (
        'unspecified','primary-care','cardiology','psychiatry','pediatrics',
        'dermatology','orthopedics','urgent-care','pain-management'
      );
  SELECT COUNT(*) INTO bad_users
    FROM users
    WHERE specialty IS NOT NULL
      AND specialty NOT IN (
        'unspecified','primary-care','cardiology','psychiatry','pediatrics',
        'dermatology','orthopedics','urgent-care','pain-management'
      );
  IF bad_visits > 0 OR bad_users > 0 THEN
    RAISE EXCEPTION 'Specialty migration left % visit + % user row(s) outside the canonical catalog', bad_visits, bad_users;
  END IF;
END $$;

COMMIT;
