-- Template Twin safe-alpha audit gates v1
-- Additive/fail-closed migration. Existing Template Twin prototype rows are
-- not rewritten; application signing rejects rows without new provenance.

-- Prisma does not implicitly make every PostgreSQL migration atomic. Hold a
-- write-blocking lock across validation and trigger installation so no
-- concurrent source, template-owner, or compiled-lineage write can enter the
-- gap and become grandfathered. These locks are released only by the COMMIT at
-- the end of this file.
BEGIN;
LOCK TABLE
  "template_twin_compiled_versions",
  "template_twin_source_artifacts",
  "note_templates",
  "users"
IN SHARE ROW EXCLUSIVE MODE;

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_FIELD_TEST_WAIVED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_DEACTIVATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RETIRED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLED_BACK';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_SAFETY_GATE_BLOCKED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_OBJECT_RECONCILED';

CREATE TYPE "TemplateTwinObjectLedgerState" AS ENUM (
  'INTENT', 'WRITTEN_UNCLAIMED', 'CLAIMED', 'RETAINED',
  'PURGE_PENDING', 'PURGED', 'FAILED'
);
CREATE TYPE "TemplateTwinAuditOutboxStatus" AS ENUM (
  'PENDING', 'PROCESSING', 'DELIVERED', 'FAILED'
);

ALTER TABLE "practices"
  ADD COLUMN "templateTwinEnabled" BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE "note_templates"
  ADD COLUMN "versionDescription" TEXT;

ALTER TABLE "template_twin_source_artifacts"
  ADD COLUMN "privacyScanEvidence" JSONB,
  ADD COLUMN "objectVersionId" TEXT,
  ADD COLUMN "objectEtag" TEXT;

ALTER TABLE "template_twin_source_artifacts"
  ADD CONSTRAINT "template_twin_accepted_source_privacy_evidence" CHECK (
    "validationStatus" <> 'accepted'
    OR (
      "privacyScanEvidence" IS NOT NULL
      AND "objectKey" IS NOT NULL
      AND "objectVersionId" IS NOT NULL
      AND "objectEtag" IS NOT NULL
      AND char_length(btrim("objectVersionId")) > 0
      AND char_length(btrim("objectEtag")) > 0
      AND "privacyScanEvidence"->>'profileVersion' = 'template-twin-source-phi-safe-alpha-v1'
      AND "privacyScanEvidence"->>'approvedStaticAssetPolicySha256' ~ '^[a-f0-9]{64}$'
      AND "privacyScanEvidence"->>'approvedStaticAssetUsageSha256' ~ '^[a-f0-9]{64}$'
    )
  ) NOT VALID;

ALTER TABLE "template_twin_certifications"
  ADD COLUMN "sourcePrivacyScanEvidenceSha256" CHAR(64),
  ADD COLUMN "testOutputVersionId" TEXT,
  ADD COLUMN "testOutputEtag" TEXT,
  ADD CONSTRAINT "template_twin_cert_source_privacy_sha256_hex" CHECK (
    "sourcePrivacyScanEvidenceSha256" IS NULL
    OR "sourcePrivacyScanEvidenceSha256" ~ '^[a-f0-9]{64}$'
  ),
  ADD CONSTRAINT "template_twin_cert_output_provider_identity" CHECK (
    ("testOutputVersionId" IS NULL AND "testOutputEtag" IS NULL)
    OR ("testOutputVersionId" IS NOT NULL
      AND "testOutputEtag" IS NOT NULL
      AND char_length(btrim("testOutputVersionId")) > 0
      AND char_length(btrim("testOutputEtag")) > 0)
  );

ALTER TABLE "template_twin_compiled_versions"
  ADD COLUMN "latestTestOutputVersionId" TEXT,
  ADD COLUMN "latestTestOutputEtag" TEXT,
  ADD CONSTRAINT "template_twin_compiled_test_output_tuple" CHECK (
    ("latestTestOutputObjectKey" IS NULL
      AND "latestTestOutputVersionId" IS NULL
      AND "latestTestOutputEtag" IS NULL)
    OR ("latestTestOutputObjectKey" IS NOT NULL
      AND "latestTestOutputVersionId" IS NOT NULL
      AND "latestTestOutputEtag" IS NOT NULL
      AND char_length(btrim("latestTestOutputVersionId")) > 0
      AND char_length(btrim("latestTestOutputEtag")) > 0)
  ) NOT VALID;

ALTER TABLE "template_twin_fill_manifests"
  ADD COLUMN "soapVersion" INTEGER,
  ADD COLUMN "soapSha256" CHAR(64),
  ADD COLUMN "outputVersionId" TEXT,
  ADD COLUMN "outputEtag" TEXT,
  ADD COLUMN "reviewedById" TEXT,
  ADD COLUMN "reviewedManifestVersion" INTEGER,
  ADD COLUMN "reviewedManifestSha256" CHAR(64);

ALTER TABLE "template_twin_fill_manifests"
  ADD CONSTRAINT "template_twin_fill_soap_sha256_hex" CHECK (
    "soapSha256" IS NULL OR "soapSha256" ~ '^[a-f0-9]{64}$'
  ),
  ADD CONSTRAINT "template_twin_fill_verified_requires_soap_provenance" CHECK (
    "status" NOT IN ('VERIFIED', 'SIGNED')
    OR ("soapVersion" IS NOT NULL AND "soapVersion" >= 1 AND "soapSha256" IS NOT NULL)
  ) NOT VALID,
  ADD CONSTRAINT "template_twin_fill_review_tuple" CHECK (
    ("reviewedAt" IS NULL AND "reviewedById" IS NULL
      AND "reviewedManifestVersion" IS NULL AND "reviewedManifestSha256" IS NULL)
    OR
    ("reviewedAt" IS NOT NULL AND "reviewedById" IS NOT NULL
      AND "reviewedManifestVersion" IS NOT NULL AND "reviewedManifestVersion" >= 1
      AND "reviewedManifestSha256" ~ '^[a-f0-9]{64}$')
  ) NOT VALID,
  ADD CONSTRAINT "template_twin_fill_review_current_manifest" CHECK (
    "reviewedAt" IS NULL
    OR ("reviewedManifestVersion" = "manifestVersion"
      AND "reviewedManifestSha256" = "manifestSha256")
  ) NOT VALID,
  ADD CONSTRAINT "template_twin_fill_reviewer_fkey" FOREIGN KEY ("reviewedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE NOT VALID;

CREATE INDEX "template_twin_fill_reviewedById_reviewedAt_idx"
  ON "template_twin_fill_manifests"("reviewedById", "reviewedAt");

CREATE TABLE "template_twin_field_test_waivers" (
  "id" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "fieldDefinitionId" TEXT NOT NULL,
  "fieldId" TEXT NOT NULL,
  "mappingsSha256" CHAR(64) NOT NULL,
  "waivedById" TEXT NOT NULL,
  "reason" TEXT NOT NULL,
  "waivedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_field_test_waivers_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_waiver_mapping_sha256_hex" CHECK (
    "mappingsSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_waiver_reason_nonempty" CHECK (
    char_length(btrim("reason")) BETWEEN 8 AND 1000
  ),
  CONSTRAINT "template_twin_waiver_compiled_fkey" FOREIGN KEY ("compiledVersionId")
    REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_waiver_field_fkey" FOREIGN KEY ("fieldDefinitionId")
    REFERENCES "template_twin_field_definitions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_waiver_physician_fkey" FOREIGN KEY ("waivedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_waiver_compiled_field_mapping_key"
  ON "template_twin_field_test_waivers"("compiledVersionId", "fieldId", "mappingsSha256");
CREATE INDEX "template_twin_waiver_fieldDefinitionId_waivedAt_idx"
  ON "template_twin_field_test_waivers"("fieldDefinitionId", "waivedAt");
CREATE INDEX "template_twin_waiver_waivedById_waivedAt_idx"
  ON "template_twin_field_test_waivers"("waivedById", "waivedAt");

CREATE TABLE "template_twin_object_ledgers" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "objectKey" TEXT NOT NULL,
  "objectVersionId" TEXT,
  "objectEtag" TEXT,
  "sha256" CHAR(64) NOT NULL,
  "sizeBytes" INTEGER NOT NULL,
  "kind" TEXT NOT NULL,
  "state" "TemplateTwinObjectLedgerState" NOT NULL DEFAULT 'INTENT',
  "claimType" TEXT,
  "claimId" TEXT,
  "attemptCount" INTEGER NOT NULL DEFAULT 0,
  "nextAttemptAt" TIMESTAMPTZ(6),
  "retentionUntil" TIMESTAMPTZ(6),
  "lastErrorCode" TEXT,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_object_ledgers_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_object_practice_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_object_sha256_hex" CHECK ("sha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_object_size_positive" CHECK ("sizeBytes" > 0),
  CONSTRAINT "template_twin_object_kind" CHECK ("kind" IN ('source', 'output')),
  CONSTRAINT "template_twin_object_provider_identity" CHECK (
    ("state" = 'INTENT' AND "objectVersionId" IS NULL AND "objectEtag" IS NULL)
    OR ("state" <> 'INTENT'
      AND "objectVersionId" IS NOT NULL
      AND "objectEtag" IS NOT NULL
      AND char_length(btrim("objectVersionId")) > 0
      AND char_length(btrim("objectEtag")) > 0)
  ),
  CONSTRAINT "template_twin_object_claim_pair" CHECK (
    ("claimType" IS NULL AND "claimId" IS NULL)
    OR ("claimType" IS NOT NULL AND "claimId" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_object_attempts_nonnegative" CHECK ("attemptCount" >= 0)
);
CREATE UNIQUE INDEX "template_twin_object_ledgers_objectKey_key"
  ON "template_twin_object_ledgers"("objectKey");
CREATE INDEX "template_twin_object_practice_state_nextAttemptAt_idx"
  ON "template_twin_object_ledgers"("practiceId", "state", "nextAttemptAt");
CREATE INDEX "template_twin_object_claimType_claimId_idx"
  ON "template_twin_object_ledgers"("claimType", "claimId");

CREATE TABLE "template_twin_audit_outbox" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "actorId" TEXT,
  "actorEmailSnapshot" TEXT,
  "ipAddress" INET,
  "userAgent" TEXT,
  "eventKey" TEXT NOT NULL,
  "action" "AuditAction" NOT NULL,
  "targetId" TEXT,
  "targetType" TEXT,
  "metadata" JSONB,
  "status" "TemplateTwinAuditOutboxStatus" NOT NULL DEFAULT 'PENDING',
  "attemptCount" INTEGER NOT NULL DEFAULT 0,
  "availableAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deliveredAt" TIMESTAMPTZ(6),
  "lastErrorCode" TEXT,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_audit_outbox_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_outbox_practice_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_outbox_actor_fkey" FOREIGN KEY ("actorId")
    REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT "template_twin_outbox_attempts_nonnegative" CHECK ("attemptCount" >= 0),
  CONSTRAINT "template_twin_outbox_delivery_state" CHECK (
    ("status" = 'DELIVERED' AND "deliveredAt" IS NOT NULL)
    OR ("status" <> 'DELIVERED' AND "deliveredAt" IS NULL)
  )
);
CREATE UNIQUE INDEX "template_twin_audit_outbox_eventKey_key"
  ON "template_twin_audit_outbox"("eventKey");
CREATE INDEX "template_twin_outbox_status_availableAt_idx"
  ON "template_twin_audit_outbox"("status", "availableAt");
CREATE INDEX "template_twin_outbox_practice_createdAt_idx"
  ON "template_twin_audit_outbox"("practiceId", "createdAt");

-- A compiled version may only join a tenant-owned source to a NoteTemplate
-- owned by a physician in that same tenant. Fail the migration if a prototype
-- row already violates the invariant; do not silently grandfather unsafe
-- lineage and then rely on application filtering.
DO $template_twin_existing_compiled_tenant_validation$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    LEFT JOIN "users" owner ON owner."id" = n."doctorId"
    WHERE owner."practiceId" IS NULL
       OR owner."practiceId" <> s."practiceId"
  ) THEN
    RAISE EXCEPTION 'Existing Template Twin compiled tenant lineage mismatch';
  END IF;
END;
$template_twin_existing_compiled_tenant_validation$;

CREATE OR REPLACE FUNCTION template_twin_require_read_committed_lineage() RETURNS void AS $$
BEGIN
  -- The advisory gate below depends on a post-wait fresh snapshot. PostgreSQL
  -- REPEATABLE READ and SERIALIZABLE retain a transaction snapshot, so a
  -- waiting trigger could otherwise validate stale ownership. Fail closed for
  -- those isolation levels. All application paths that create compiled
  -- lineage explicitly use READ COMMITTED; callers at another level must retry
  -- the lineage mutation in a dedicated READ COMMITTED transaction.
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION USING
      ERRCODE = '40001',
      MESSAGE = 'Template Twin tenant lineage writes require READ COMMITTED isolation';
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION template_twin_assert_compiled_tenant_consistency() RETURNS trigger AS $$
DECLARE source_practice TEXT;
DECLARE template_owner_id TEXT;
DECLARE template_owner_practice TEXT;
BEGIN
  -- Cross-table trigger checks need an explicit lock protocol: under READ
  -- COMMITTED, unlocked checks can both validate pre-change rows and then
  -- commit a cross-tenant lineage. Take the same transaction-scoped advisory
  -- gate in all three lineage triggers before reading NoteTemplate and User.
  -- Do not combine the gate with row locks: an updater may already own its
  -- target row before its BEFORE trigger waits, which would invert gate/row
  -- order against compilation and create a deadlock.
  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_compiled_owner_lineage_v1', 0)
  );
  SELECT n."doctorId" INTO template_owner_id
    FROM "note_templates" n
    WHERE n."id" = NEW."noteTemplateId";
  SELECT owner."practiceId" INTO template_owner_practice
    FROM "users" owner
    WHERE owner."id" = template_owner_id;
  SELECT s."practiceId" INTO source_practice
    FROM "template_twin_source_artifacts" s
    WHERE s."id" = NEW."sourceArtifactId";

  IF source_practice IS NULL
     OR template_owner_practice IS NULL
     OR source_practice <> template_owner_practice THEN
    RAISE EXCEPTION 'Template Twin compiled tenant lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_compiled_tenant_consistency
  BEFORE INSERT OR UPDATE OF "sourceArtifactId", "noteTemplateId"
  ON "template_twin_compiled_versions"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_compiled_tenant_consistency();

-- Preserve the invariant when ownership metadata changes after compilation.
CREATE OR REPLACE FUNCTION template_twin_assert_note_template_owner_consistency() RETURNS trigger AS $$
DECLARE template_owner_practice TEXT;
BEGIN
  IF NEW."doctorId" IS NOT DISTINCT FROM OLD."doctorId" THEN
    RETURN NEW;
  END IF;

  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_compiled_owner_lineage_v1', 0)
  );
  IF NOT EXISTS (
       SELECT 1 FROM "template_twin_compiled_versions" c
       WHERE c."noteTemplateId" = OLD."id"
     ) THEN
    RETURN NEW;
  END IF;

  -- Re-read the prospective owner only after the shared lineage gate. A
  -- concurrent compilation or practice reassignment must commit or roll back
  -- before this check can continue.
  SELECT owner."practiceId" INTO template_owner_practice
    FROM "users" owner
    WHERE owner."id" = NEW."doctorId";
  IF template_owner_practice IS NULL OR EXISTS (
    SELECT 1
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    WHERE c."noteTemplateId" = OLD."id"
      AND s."practiceId" <> template_owner_practice
  ) THEN
    RAISE EXCEPTION 'Template Twin NoteTemplate owner tenant mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_note_template_owner_consistency
  BEFORE UPDATE OF "doctorId" ON "note_templates"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_note_template_owner_consistency();

CREATE OR REPLACE FUNCTION template_twin_assert_owner_practice_consistency() RETURNS trigger AS $$
BEGIN
  IF NEW."practiceId" IS NOT DISTINCT FROM OLD."practiceId" THEN
    RETURN NEW;
  END IF;

  -- Serialize before checking compiled rows. In particular, do not rely on a
  -- User-row lock wait: PostgreSQL can invoke this BEFORE trigger before the
  -- physical row update reaches that wait.
  PERFORM template_twin_require_read_committed_lineage();
  PERFORM pg_advisory_xact_lock(
    hashtextextended('template_twin_compiled_owner_lineage_v1', 0)
  );
  IF EXISTS (
    SELECT 1
    FROM "note_templates" n
    JOIN "template_twin_compiled_versions" c ON c."noteTemplateId" = n."id"
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    WHERE n."doctorId" = OLD."id"
      AND s."practiceId" <> NEW."practiceId"
  ) THEN
    RAISE EXCEPTION 'Template Twin owner practice reassignment mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_owner_practice_consistency
  BEFORE UPDATE OF "practiceId" ON "users"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_owner_practice_consistency();

CREATE OR REPLACE FUNCTION template_twin_assert_waiver_lineage() RETURNS trigger AS $$
DECLARE field_compilation TEXT;
DECLARE field_identifier TEXT;
DECLARE physician_practice TEXT;
DECLARE source_practice TEXT;
DECLARE template_owner_practice TEXT;
BEGIN
  SELECT f."compiledVersionId", f."fieldId"
    INTO field_compilation, field_identifier
    FROM "template_twin_field_definitions" f
    WHERE f."id" = NEW."fieldDefinitionId";
  IF field_compilation IS NULL
     OR field_compilation <> NEW."compiledVersionId"
     OR field_identifier <> NEW."fieldId" THEN
    RAISE EXCEPTION 'Template Twin waiver field lineage mismatch';
  END IF;

  SELECT u."practiceId" INTO physician_practice
    FROM "users" u WHERE u."id" = NEW."waivedById" AND u."role" = 'DOCTOR' AND u."isActive" = true;
  SELECT s."practiceId", owner."practiceId"
    INTO source_practice, template_owner_practice
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    LEFT JOIN "users" owner ON owner."id" = n."doctorId"
    WHERE c."id" = NEW."compiledVersionId";
  IF physician_practice IS NULL
     OR template_owner_practice IS NULL
     OR source_practice <> template_owner_practice
     OR physician_practice <> source_practice THEN
    RAISE EXCEPTION 'Template Twin waiver physician tenant mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_waiver_lineage_insert
  BEFORE INSERT ON "template_twin_field_test_waivers"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_waiver_lineage();

CREATE OR REPLACE FUNCTION template_twin_waivers_immutable_after_certification() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin field test waivers are append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_waiver_no_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_field_test_waivers"
  FOR EACH ROW EXECUTE FUNCTION template_twin_waivers_immutable_after_certification();

CREATE OR REPLACE FUNCTION template_twin_assert_certification_provider_identity() RETURNS trigger AS $$
DECLARE source_practice TEXT;
DECLARE certifier_practice TEXT;
DECLARE compiled_key TEXT;
DECLARE compiled_version_id TEXT;
DECLARE compiled_etag TEXT;
DECLARE compiled_sha256 TEXT;
DECLARE template_owner_practice TEXT;
BEGIN
  SELECT s."practiceId", owner."practiceId", c."latestTestOutputObjectKey",
         c."latestTestOutputVersionId", c."latestTestOutputEtag",
         c."latestTestOutputSha256"
    INTO source_practice, template_owner_practice, compiled_key,
         compiled_version_id, compiled_etag, compiled_sha256
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    LEFT JOIN "users" owner ON owner."id" = n."doctorId"
    WHERE c."id" = NEW."compiledVersionId";
  SELECT u."practiceId" INTO certifier_practice
    FROM "users" u
    WHERE u."id" = NEW."certifiedById"
      AND u."role" = 'DOCTOR'
      AND u."isActive" = true;
  IF source_practice IS NULL OR template_owner_practice IS NULL
     OR source_practice <> template_owner_practice
     OR certifier_practice IS NULL
     OR certifier_practice <> source_practice
     OR NEW."testOutputObjectKey" <> compiled_key
     OR NEW."testOutputVersionId" IS NULL
     OR NEW."testOutputVersionId" <> compiled_version_id
     OR NEW."testOutputEtag" IS NULL
     OR NEW."testOutputEtag" <> compiled_etag
     OR NEW."testOutputSha256" <> compiled_sha256 THEN
    RAISE EXCEPTION 'Template Twin certification provider identity mismatch';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM "template_twin_object_ledgers" l
    WHERE l."objectKey" = NEW."testOutputObjectKey"
      AND l."practiceId" = source_practice
      AND l."objectVersionId" = NEW."testOutputVersionId"
      AND l."objectEtag" = NEW."testOutputEtag"
      AND l."sha256" = NEW."testOutputSha256"
      AND l."kind" = 'output'
      AND l."state" = 'CLAIMED'
      AND l."claimType" = 'compiled_test_output'
      AND l."claimId" = NEW."compiledVersionId"
  ) THEN
    RAISE EXCEPTION 'Template Twin certification output ledger mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_certification_provider_identity
  BEFORE INSERT ON "template_twin_certifications"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_certification_provider_identity();

CREATE OR REPLACE FUNCTION template_twin_assert_fill_tenant_consistency() RETURNS trigger AS $$
DECLARE source_practice TEXT;
DECLARE visit_practice TEXT;
DECLARE compiled_template TEXT;
DECLARE compiled_template_version INTEGER;
DECLARE template_owner_practice TEXT;
DECLARE output_key_parts TEXT[];
DECLARE reviewer_practice TEXT;
BEGIN
  SELECT s."practiceId", owner."practiceId", c."noteTemplateId", n."version"
    INTO source_practice, template_owner_practice, compiled_template,
         compiled_template_version
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    LEFT JOIN "users" owner ON owner."id" = n."doctorId"
    WHERE c."id" = NEW."compiledVersionId";
  SELECT u."practiceId" INTO visit_practice
    FROM "transcribe_visits" v
    JOIN "users" u ON u."id" = v."userId"
    WHERE v."id" = NEW."visitId";

  IF source_practice IS NULL OR template_owner_practice IS NULL
     OR source_practice <> template_owner_practice
     OR visit_practice IS NULL
     OR NEW."practiceId" <> source_practice
     OR NEW."practiceId" <> visit_practice
     OR NEW."noteTemplateId" <> compiled_template
     OR NEW."noteTemplateVersion" <> compiled_template_version THEN
    RAISE EXCEPTION 'Template Twin fill tenant or lineage mismatch';
  END IF;
  IF NEW."reviewedById" IS NOT NULL THEN
    SELECT u."practiceId" INTO reviewer_practice
      FROM "users" u
      WHERE u."id" = NEW."reviewedById"
        AND u."role" = 'DOCTOR'
        AND u."isActive" = true;
    IF reviewer_practice IS NULL OR reviewer_practice <> NEW."practiceId" THEN
      RAISE EXCEPTION 'Template Twin fill reviewer tenant mismatch';
    END IF;
  END IF;
  IF NEW."outputObjectKey" IS NULL THEN
    IF NEW."outputVersionId" IS NOT NULL
       OR NEW."outputEtag" IS NOT NULL
       OR NEW."outputSha256" IS NOT NULL
       OR NEW."outputMimeType" IS NOT NULL
       OR NEW."outputSizeBytes" IS NOT NULL
       OR NEW."staticContentSha256" IS NOT NULL
       OR NEW."roundTripVerified" THEN
      RAISE EXCEPTION 'Template Twin fill output tuple mismatch';
    END IF;
  ELSE
    IF char_length(btrim(NEW."outputVersionId")) = 0
       OR char_length(btrim(NEW."outputEtag")) = 0
       OR NEW."outputVersionId" IS NULL
       OR NEW."outputEtag" IS NULL
       OR NEW."outputSha256" IS NULL
       OR NEW."outputMimeType" <> 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
       OR NEW."outputSizeBytes" IS NULL OR NEW."outputSizeBytes" <= 0
       OR NEW."staticContentSha256" IS NULL
       OR NOT NEW."roundTripVerified" THEN
      RAISE EXCEPTION 'Template Twin fill output tuple mismatch';
    END IF;

    output_key_parts := string_to_array(NEW."outputObjectKey", '/');
    IF array_length(output_key_parts, 1) <> 8
       OR output_key_parts[1] <> 'practices'
       OR output_key_parts[2] <> NEW."practiceId"
       OR output_key_parts[3] <> 'template-twin'
       OR output_key_parts[4] <> 'outputs'
       OR output_key_parts[5] <> NEW."visitId" THEN
      RAISE EXCEPTION 'Template Twin output key tenant lineage mismatch';
    END IF;
    IF output_key_parts[6] <> NEW."manifestSha256" THEN
      RAISE EXCEPTION 'Template Twin output key manifest hash mismatch';
    END IF;
    IF output_key_parts[8] <> (NEW."outputSha256" || '.docx') THEN
      RAISE EXCEPTION 'Template Twin output key content hash mismatch';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_fill_tenant_consistency
  BEFORE INSERT OR UPDATE ON "template_twin_fill_manifests"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_fill_tenant_consistency();

CREATE OR REPLACE FUNCTION template_twin_assert_review_lineage_consistency() RETURNS trigger AS $$
DECLARE fill_compilation TEXT;
DECLARE field_compilation TEXT;
DECLARE expected_field_id TEXT;
BEGIN
  SELECT "compiledVersionId" INTO fill_compilation
    FROM "template_twin_fill_manifests" WHERE "id" = NEW."fillManifestId";
  SELECT "compiledVersionId", "fieldId" INTO field_compilation, expected_field_id
    FROM "template_twin_field_definitions" WHERE "id" = NEW."fieldDefinitionId";
  IF fill_compilation IS NULL OR field_compilation IS NULL
     OR fill_compilation <> field_compilation OR NEW."fieldId" <> expected_field_id THEN
    RAISE EXCEPTION 'Template Twin review field lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_review_lineage_consistency
  BEFORE INSERT OR UPDATE ON "template_twin_review_decisions"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_review_lineage_consistency();

CREATE OR REPLACE FUNCTION template_twin_assert_object_ledger_tenant() RETURNS trigger AS $$
DECLARE owner_practice TEXT;
DECLARE owner_key TEXT;
DECLARE owner_sha256 TEXT;
DECLARE owner_size_bytes INTEGER;
DECLARE owner_version_id TEXT;
DECLARE owner_etag TEXT;
BEGIN
  IF NEW."objectKey" NOT LIKE ('practices/' || NEW."practiceId" || '/template-twin/%') THEN
    RAISE EXCEPTION 'Template Twin object ledger tenant key mismatch';
  END IF;
  IF NEW."claimType" = 'fill_manifest' THEN
    SELECT f."practiceId", f."outputObjectKey", f."outputSha256", f."outputSizeBytes",
           f."outputVersionId", f."outputEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_fill_manifests" f WHERE f."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'source_artifact' THEN
    SELECT s."practiceId", s."objectKey", s."sha256", s."sizeBytes",
           s."objectVersionId", s."objectEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_source_artifacts" s WHERE s."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'compiled_test_output' THEN
    SELECT s."practiceId", c."latestTestOutputObjectKey",
           c."latestTestOutputSha256", NULL,
           c."latestTestOutputVersionId", c."latestTestOutputEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_compiled_versions" c
      JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
      WHERE c."id" = NEW."claimId";
  ELSIF NEW."claimType" IS NOT NULL THEN
    RAISE EXCEPTION 'Template Twin object ledger claim type is unsupported';
  END IF;
  IF NEW."claimType" IS NOT NULL
     AND (owner_practice IS NULL OR owner_practice <> NEW."practiceId" OR owner_key <> NEW."objectKey") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim lineage mismatch';
  END IF;
  IF NEW."claimType" IS NOT NULL
     AND (NEW."state" <> 'CLAIMED'
       OR owner_version_id IS NULL OR owner_version_id <> NEW."objectVersionId"
       OR owner_etag IS NULL OR owner_etag <> NEW."objectEtag") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim provider identity mismatch';
  END IF;
  IF NEW."claimType" = 'source_artifact'
     AND (NEW."kind" <> 'source'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin source object ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" = 'compiled_test_output'
     AND (NEW."kind" <> 'output'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256") THEN
    RAISE EXCEPTION 'Template Twin synthetic output ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" = 'fill_manifest'
     AND (NEW."kind" <> 'output'
       OR NEW."state" <> 'CLAIMED'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" IS NULL AND EXISTS (
    SELECT 1 FROM "template_twin_fill_manifests" f
    WHERE f."outputObjectKey" = NEW."objectKey"
  ) THEN
    RAISE EXCEPTION 'Template Twin object ledger claim ownership missing';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_object_ledger_tenant_consistency
  BEFORE INSERT OR UPDATE ON "template_twin_object_ledgers"
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_object_ledger_tenant();

-- A fill is written before its pre-storage ledger is claimed in the same
-- serializable transaction. Defer this reverse ownership assertion to commit
-- so the only durable state is an exact key/hash/size claim owned by the fill.
CREATE OR REPLACE FUNCTION template_twin_assert_fill_output_ledger() RETURNS trigger AS $$
BEGIN
  IF NEW."outputObjectKey" IS NULL THEN
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM "template_twin_object_ledgers" l
    WHERE l."objectKey" = NEW."outputObjectKey"
      AND l."practiceId" = NEW."practiceId"
      AND l."sha256" = NEW."outputSha256"
      AND l."sizeBytes" = NEW."outputSizeBytes"
      AND l."objectVersionId" = NEW."outputVersionId"
      AND l."objectEtag" = NEW."outputEtag"
      AND l."kind" = 'output'
      AND l."state" = 'CLAIMED'
      AND l."claimType" = 'fill_manifest'
      AND l."claimId" = NEW."id"
  ) THEN
    RAISE EXCEPTION 'Template Twin fill output ledger ownership mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER template_twin_fill_output_ledger_consistency
  AFTER INSERT OR UPDATE ON "template_twin_fill_manifests"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_fill_output_ledger();

COMMIT;
