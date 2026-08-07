-- ===========================================================================
-- T7 — the remaining clinical tables gain `practiceId`.
-- ---------------------------------------------------------------------------
-- Nine tables. Every derivation is STRUCTURAL and stated here, and every
-- backfill ABORTS before its constraint if any row is left underivable — T3's
-- shape, because a partially-backfilled column that then takes a constraint is
-- a migration that half-ran and reported success.
--
-- MEASURED ON PRODUCTION 2026-08-07, before writing a line:
--
--     visit_deliveries ..................  62 rows   → visit.practiceId
--     doctor_edit_patterns ..............  16 rows   → visit.practiceId
--     note_templates ....................   6 rows   → doctor.practiceId (2 platform-global)
--     rx_warning_overrides ..............   0 rows   → visit.practiceId
--     account_deletions .................   0 rows   → user.practiceId
--     template_twin_compiled_versions ...   0 rows   → source_artifacts.practiceId
--     template_twin_certifications ......   0 rows   → compiled_versions → …
--     template_twin_field_definitions ...   0 rows   → compiled_versions → …
--     template_twin_semantic_mappings ...   0 rows   → field_definitions → …
--
-- ⚠️ THE TWIN CHAIN HAS ONE ROOT, AND THAT IS WHY IT IS SAFE TO DO AT ONCE.
-- `template_twin_source_artifacts` ALREADY carries `practiceId`. Every other
-- twin table reaches it through exactly one FK path, so there is no table whose
-- tenant is ambiguous and none that needs a second source of truth.
--
-- ⚠️ ZERO-ROW TABLES ARE CONSTRAINED NOW, NOT LATER (DISCOVERY §B.3). A table
-- with no rows is the cheapest possible moment to make a bad row
-- unrepresentable — the constraint costs nothing to add and the first row that
-- would have violated it never gets written.
--
-- ⚠️ note_templates TAKES A BICONDITIONAL, RULED 2026-08-07 (RULINGS.md, SPEC
-- §1.5). See its section below — it is the one table here whose column stays
-- nullable, and the reason is recorded rather than inferable from the DDL.
-- ===========================================================================

-- ── 1. visit_deliveries — 62 rows, derives from the visit ──────────────────
ALTER TABLE "visit_deliveries" ADD COLUMN "practiceId" TEXT;

UPDATE "visit_deliveries" d
   SET "practiceId" = v."practiceId"
  FROM "transcribe_visits" v
 WHERE v.id = d."visitId";

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM visit_deliveries WHERE "practiceId" IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION '[t7] % visit_deliveries rows have no derivable practice. Refusing to SET NOT NULL on a half-backfilled column.', n;
  END IF;
  RAISE NOTICE '[t7] visit_deliveries backfilled';
END $$;

ALTER TABLE "visit_deliveries" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "visit_deliveries" ADD CONSTRAINT "visit_deliveries_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX "visit_deliveries_practiceId_idx" ON "visit_deliveries" ("practiceId");

-- ── 2. doctor_edit_patterns — 16 rows, derives from the visit ──────────────
-- ⚠️ FROM THE VISIT, NOT THE DOCTOR, and the distinction is T3's ruling again:
-- the CHART owns the note, so a locum's edit pattern files under the chart's
-- practice rather than the editor's. This table also stores `originalSoap` and
-- `editedSoap` as full text — it is the one that leaks whole notes.
ALTER TABLE "doctor_edit_patterns" ADD COLUMN "practiceId" TEXT;

UPDATE "doctor_edit_patterns" p
   SET "practiceId" = v."practiceId"
  FROM "transcribe_visits" v
 WHERE v.id = p."visitId";

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM doctor_edit_patterns WHERE "practiceId" IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION '[t7] % doctor_edit_patterns rows have no derivable practice.', n;
  END IF;
  RAISE NOTICE '[t7] doctor_edit_patterns backfilled';
END $$;

ALTER TABLE "doctor_edit_patterns" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "doctor_edit_patterns" ADD CONSTRAINT "doctor_edit_patterns_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX "doctor_edit_patterns_practiceId_idx" ON "doctor_edit_patterns" ("practiceId");

-- ── 3. rx_warning_overrides — 0 rows, derives from the visit ───────────────
ALTER TABLE "rx_warning_overrides" ADD COLUMN "practiceId" TEXT;

UPDATE "rx_warning_overrides" o
   SET "practiceId" = v."practiceId"
  FROM "transcribe_visits" v
 WHERE v.id = o."visitId";

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM rx_warning_overrides WHERE "practiceId" IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION '[t7] % rx_warning_overrides rows have no derivable practice.', n;
  END IF;
END $$;

ALTER TABLE "rx_warning_overrides" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "rx_warning_overrides" ADD CONSTRAINT "rx_warning_overrides_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX "rx_warning_overrides_practiceId_idx" ON "rx_warning_overrides" ("practiceId");

-- ── 4. account_deletions — 0 rows, derives from the user ───────────────────
-- ⚠️ NULLABLE ON PURPOSE, AND FOR THE SAME REASON AS audit_logs (S4c): a
-- deletion record must outlive the account it describes, and `users.practiceId`
-- is gone once the row is. The column records the practice AT DELETION TIME;
-- it is not a live FK to something that must still exist.
ALTER TABLE "account_deletions" ADD COLUMN "practiceId" TEXT;

UPDATE "account_deletions" a
   SET "practiceId" = u."practiceId"
  FROM "users" u
 WHERE u.id = a."userId";

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM account_deletions
   WHERE "practiceId" IS NULL
     AND EXISTS (SELECT 1 FROM users u WHERE u.id = "userId" AND u."practiceId" IS NOT NULL);
  IF n > 0 THEN
    RAISE EXCEPTION '[t7] % account_deletions rows failed to derive a practice their user still has.', n;
  END IF;
END $$;

CREATE INDEX "account_deletions_practiceId_idx" ON "account_deletions" ("practiceId");

-- ── 5-8. the Template Twin chain — all 0 rows, one root ────────────────────
ALTER TABLE "template_twin_compiled_versions" ADD COLUMN "practiceId" TEXT;
UPDATE "template_twin_compiled_versions" c
   SET "practiceId" = s."practiceId"
  FROM "template_twin_source_artifacts" s
 WHERE s.id = c."sourceArtifactId";

ALTER TABLE "template_twin_field_definitions" ADD COLUMN "practiceId" TEXT;
UPDATE "template_twin_field_definitions" f
   SET "practiceId" = c."practiceId"
  FROM "template_twin_compiled_versions" c
 WHERE c.id = f."compiledVersionId";

ALTER TABLE "template_twin_certifications" ADD COLUMN "practiceId" TEXT;
UPDATE "template_twin_certifications" t
   SET "practiceId" = c."practiceId"
  FROM "template_twin_compiled_versions" c
 WHERE c.id = t."compiledVersionId";

ALTER TABLE "template_twin_semantic_mappings" ADD COLUMN "practiceId" TEXT;
UPDATE "template_twin_semantic_mappings" m
   SET "practiceId" = f."practiceId"
  FROM "template_twin_field_definitions" f
 WHERE f.id = m."fieldDefinitionId";

DO $$
DECLARE n int; tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['template_twin_compiled_versions','template_twin_field_definitions',
                             'template_twin_certifications','template_twin_semantic_mappings'] LOOP
    EXECUTE format('SELECT count(*) FROM %I WHERE "practiceId" IS NULL', tbl) INTO n;
    IF n > 0 THEN
      RAISE EXCEPTION '[t7] % rows in % have no derivable practice.', n, tbl;
    END IF;
  END LOOP;
  RAISE NOTICE '[t7] twin chain backfilled from source_artifacts';
END $$;

ALTER TABLE "template_twin_compiled_versions" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "template_twin_field_definitions" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "template_twin_certifications" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "template_twin_semantic_mappings" ALTER COLUMN "practiceId" SET NOT NULL;

ALTER TABLE "template_twin_compiled_versions" ADD CONSTRAINT "twin_compiled_versions_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "template_twin_field_definitions" ADD CONSTRAINT "twin_field_definitions_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "template_twin_certifications" ADD CONSTRAINT "twin_certifications_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "template_twin_semantic_mappings" ADD CONSTRAINT "twin_semantic_mappings_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE INDEX "twin_compiled_versions_practiceId_idx" ON "template_twin_compiled_versions" ("practiceId");
CREATE INDEX "twin_field_definitions_practiceId_idx" ON "template_twin_field_definitions" ("practiceId");
CREATE INDEX "twin_certifications_practiceId_idx" ON "template_twin_certifications" ("practiceId");
CREATE INDEX "twin_semantic_mappings_practiceId_idx" ON "template_twin_semantic_mappings" ("practiceId");

-- ── 9. note_templates — the BICONDITIONAL, ruled 2026-08-07 ────────────────
-- ⚠️ THIS IS THE ONE TABLE WHOSE COLUMN STAYS NULLABLE, AND THE RULE IS AN IFF:
--
--     (doctorId IS NULL     AND practiceId IS NULL)
--  OR (doctorId IS NOT NULL AND practiceId IS NOT NULL)
--
-- A template has a practice IF AND ONLY IF it has a doctor.
--
--   FORWARD  closes the derivation gap: a doctor-owned template always has a
--            practice to derive from, so it must carry one.
--   REVERSE  is the half that is easy to omit and worth stating: it forbids an
--            ORPHANED TENANCY CLAIM on platform content — a row asserting it
--            belongs to a practice while belonging to nobody.
--
-- The sentinel-practice alternative was REJECTED (RULINGS.md): an invented
-- tenant that every practice-scoped query must learn to ignore is the
-- hand-kept-list failure mode expressed in schema.
--
-- Production 2026-08-07: 6 rows — 4 doctor-owned, 2 platform-global.
ALTER TABLE "note_templates" ADD COLUMN "practiceId" TEXT;

UPDATE "note_templates" t
   SET "practiceId" = u."practiceId"
  FROM "users" u
 WHERE u.id = t."doctorId";

DO $$
DECLARE bad int; global int;
BEGIN
  -- A doctor-owned template that failed to derive is a real failure.
  SELECT count(*) INTO bad FROM note_templates
   WHERE "doctorId" IS NOT NULL AND "practiceId" IS NULL;
  IF bad > 0 THEN
    RAISE EXCEPTION '[t7] % doctor-owned note_templates failed to derive a practice.', bad;
  END IF;
  -- A platform-global template with a practice would violate the reverse half.
  SELECT count(*) INTO global FROM note_templates
   WHERE "doctorId" IS NULL AND "practiceId" IS NOT NULL;
  IF global > 0 THEN
    RAISE EXCEPTION '[t7] % platform-global note_templates acquired a practice — the biconditional would refuse them.', global;
  END IF;
  SELECT count(*) INTO global FROM note_templates WHERE "doctorId" IS NULL;
  RAISE NOTICE '[t7] note_templates backfilled; % platform-global rows carved out', global;
END $$;

ALTER TABLE "note_templates"
  ADD CONSTRAINT "note_templates_practice_iff_doctor"
  CHECK (
    ("doctorId" IS NULL AND "practiceId" IS NULL)
    OR ("doctorId" IS NOT NULL AND "practiceId" IS NOT NULL)
  );

ALTER TABLE "note_templates" ADD CONSTRAINT "note_templates_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX "note_templates_practiceId_idx" ON "note_templates" ("practiceId");
