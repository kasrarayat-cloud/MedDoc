BEGIN;

SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

-- A fill's direct identity was frozen in v4. Its physician ownership is
-- transitive through transcribe_visits.userId -> users.practiceId, so protect
-- that reverse lineage as well. The migration lock makes validation and
-- trigger installation atomic: unsafe existing rows fail closed, and no
-- concurrent ownership write can enter between the census and the guards.
LOCK TABLE
  "template_twin_fill_manifests",
  "transcribe_visits",
  "users"
IN SHARE ROW EXCLUSIVE MODE;

DO $template_twin_existing_fill_owner_lineage_validation_v5$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_fill_manifests" fill
    JOIN "transcribe_visits" visit ON visit."id" = fill."visitId"
    LEFT JOIN "users" physician ON physician."id" = visit."userId"
    WHERE physician."practiceId" IS NULL
       OR physician."practiceId" <> fill."practiceId"
  ) THEN
    RAISE EXCEPTION 'Existing Template Twin fill physician tenant lineage mismatch';
  END IF;
END;
$template_twin_existing_fill_owner_lineage_validation_v5$;

-- New fill creation and reverse visit/user ownership changes share this gate.
-- READ COMMITTED is required so a trigger that waited for the gate validates
-- the ownership committed by the preceding transaction, not an old snapshot.
CREATE OR REPLACE FUNCTION template_twin_assert_fill_visit_owner_lineage_v5()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE physician_practice TEXT;
BEGIN
  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_fill_visit_owner_lineage_v5', 0)
  );

  SELECT physician."practiceId" INTO physician_practice
  FROM "transcribe_visits" visit
  JOIN "users" physician ON physician."id" = visit."userId"
  WHERE visit."id" = NEW."visitId";

  IF physician_practice IS NULL
     OR physician_practice <> NEW."practiceId" THEN
    RAISE EXCEPTION 'Template Twin fill physician tenant lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aaa_template_twin_fill_visit_owner_lineage_v5
BEFORE INSERT ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_fill_visit_owner_lineage_v5();

-- Once a fill exists, the visit cannot be reassigned to any other physician,
-- including another physician in the same practice. A reassignment would
-- change the owner of immutable clinical evidence without changing its fill
-- identity or preserving an explicit reviewed migration lineage.
CREATE OR REPLACE FUNCTION template_twin_guard_visit_fill_owner_lineage_v5()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."userId" IS NOT DISTINCT FROM OLD."userId" THEN
    RETURN NEW;
  END IF;

  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_fill_visit_owner_lineage_v5', 0)
  );

  IF EXISTS (
    SELECT 1
    FROM "template_twin_fill_manifests" fill
    WHERE fill."visitId" = OLD."id"
  ) THEN
    RAISE EXCEPTION 'Template Twin visit physician ownership is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aaa_template_twin_visit_fill_owner_lineage_v5
BEFORE UPDATE OF "userId" ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_visit_fill_owner_lineage_v5();

-- Changing a physician's practice also changes every visit's derived tenant.
-- Historical fills keep their original practice and must never silently
-- follow that reassignment. A separate reviewed migration workflow is needed.
CREATE OR REPLACE FUNCTION template_twin_guard_physician_fill_practice_v5()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."practiceId" IS NOT DISTINCT FROM OLD."practiceId" THEN
    RETURN NEW;
  END IF;

  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_fill_visit_owner_lineage_v5', 0)
  );

  IF EXISTS (
    SELECT 1
    FROM "transcribe_visits" visit
    JOIN "template_twin_fill_manifests" fill
      ON fill."visitId" = visit."id"
    WHERE visit."userId" = OLD."id"
  ) THEN
    RAISE EXCEPTION 'Template Twin physician practice ownership is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aaa_template_twin_physician_fill_practice_v5
BEFORE UPDATE OF "practiceId" ON "users"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_physician_fill_practice_v5();

-- The fill primary key owns review, audit, and object-ledger references. Do
-- not let ON UPDATE CASCADE rewrite that immutable evidence identity.
CREATE OR REPLACE FUNCTION template_twin_guard_fill_primary_identity_v5()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD."id" IS DISTINCT FROM NEW."id" THEN
    RAISE EXCEPTION 'Template Twin fill primary identity is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aaa_template_twin_fill_primary_identity_v5
BEFORE UPDATE OF "id" ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_fill_primary_identity_v5();

COMMIT;
