-- Template Twin raw-quarantine admission v1
-- Additive and fail-closed: existing source rows remain readable but cannot
-- satisfy the new GA certification admission receipt until re-admitted.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_MALWARE_SCANNED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_METADATA_MINIMIZED';

ALTER TABLE "template_twin_object_ledgers"
  DROP CONSTRAINT "template_twin_object_kind",
  ADD CONSTRAINT "template_twin_object_kind"
    CHECK ("kind" IN ('source', 'output', 'quarantine'));

CREATE TABLE "template_twin_quarantine_artifacts" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "createdById" TEXT,
  "lineageId" TEXT NOT NULL,
  "lineageVersion" INTEGER NOT NULL,
  "intakeMode" TEXT NOT NULL,
  "objectKey" TEXT NOT NULL,
  "objectVersionId" TEXT NOT NULL,
  "objectEtag" TEXT NOT NULL,
  "sha256" CHAR(64) NOT NULL,
  "mimeType" TEXT NOT NULL,
  "sizeBytes" INTEGER NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'QUARANTINED',
  "malwareScanEvidence" JSONB,
  "metadataMinimizationEvidence" JSONB,
  "rejectionCodes" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "scannedAt" TIMESTAMPTZ(6),
  "admittedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_quarantine_artifacts_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_quarantine_lineage_version_positive" CHECK ("lineageVersion" > 0),
  CONSTRAINT "template_twin_quarantine_size_positive" CHECK ("sizeBytes" > 0),
  CONSTRAINT "template_twin_quarantine_sha256_hex" CHECK ("sha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_quarantine_provider_identity" CHECK (
    char_length(btrim("objectVersionId")) > 0
    AND char_length(btrim("objectEtag")) > 0
  ),
  CONSTRAINT "template_twin_quarantine_mode" CHECK (
    "intakeMode" IN ('NATIVE_TEMPLATE', 'COMPLETED_EXAMPLE')
  ),
  CONSTRAINT "template_twin_quarantine_status" CHECK (
    "status" IN ('QUARANTINED', 'MALWARE_CLEAN', 'REJECTED', 'ADMITTED')
  ),
  CONSTRAINT "template_twin_quarantine_state_evidence" CHECK (
    ("status" = 'QUARANTINED' AND "admittedAt" IS NULL)
    OR ("status" = 'MALWARE_CLEAN'
      AND "malwareScanEvidence"->>'verdict' = 'clean'
      AND "scannedAt" IS NOT NULL
      AND "admittedAt" IS NULL
      AND cardinality("rejectionCodes") = 0)
    OR ("status" = 'REJECTED'
      AND cardinality("rejectionCodes") > 0
      AND "admittedAt" IS NULL)
    OR ("status" = 'ADMITTED'
      AND "malwareScanEvidence"->>'verdict' = 'clean'
      AND "metadataMinimizationEvidence" IS NOT NULL
      AND "scannedAt" IS NOT NULL
      AND "admittedAt" IS NOT NULL
      AND cardinality("rejectionCodes") = 0)
  ),
  CONSTRAINT "template_twin_quarantine_malware_receipt" CHECK (
    "malwareScanEvidence" IS NULL
    OR (
      "malwareScanEvidence"->>'profileVersion' = 'template-twin-clamd-instream-v1'
      AND "malwareScanEvidence"->>'scanner' = 'clamav-clamd'
      AND "malwareScanEvidence"->>'transport' = 'unix-domain-socket'
      AND "malwareScanEvidence"->>'sourceSha256' = "sha256"
      AND ("malwareScanEvidence"->>'sourceSizeBytes')::INTEGER = "sizeBytes"
      AND "malwareScanEvidence"->>'attestationSha256' ~ '^[a-f0-9]{64}$'
      AND "malwareScanEvidence"->>'verdict' IN ('clean', 'infected')
    )
  ),
  CONSTRAINT "template_twin_quarantine_metadata_receipt" CHECK (
    "metadataMinimizationEvidence" IS NULL
    OR (
      "metadataMinimizationEvidence"->>'profileVersion' = 'template-twin-docx-metadata-minimization-v1'
      AND "metadataMinimizationEvidence"->>'originalSha256' = "sha256"
      AND "metadataMinimizationEvidence"->>'minimizedSha256' ~ '^[a-f0-9]{64}$'
    )
  )
);

CREATE UNIQUE INDEX "template_twin_quarantine_artifacts_objectKey_key"
  ON "template_twin_quarantine_artifacts"("objectKey");
CREATE INDEX "template_twin_quarantine_practice_created_idx"
  ON "template_twin_quarantine_artifacts"("practiceId", "createdAt");
CREATE INDEX "template_twin_quarantine_lineage_version_idx"
  ON "template_twin_quarantine_artifacts"("lineageId", "lineageVersion");
CREATE INDEX "template_twin_quarantine_sha256_idx"
  ON "template_twin_quarantine_artifacts"("sha256");
CREATE INDEX "template_twin_quarantine_practice_status_created_idx"
  ON "template_twin_quarantine_artifacts"("practiceId", "status", "createdAt");

ALTER TABLE "template_twin_quarantine_artifacts"
  ADD CONSTRAINT "template_twin_quarantine_practice_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_quarantine_creator_fkey"
  FOREIGN KEY ("createdById") REFERENCES "users"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "template_twin_source_artifacts"
  ADD COLUMN "quarantineArtifactId" TEXT;
CREATE UNIQUE INDEX "template_twin_source_quarantineArtifactId_key"
  ON "template_twin_source_artifacts"("quarantineArtifactId");
ALTER TABLE "template_twin_source_artifacts"
  ADD CONSTRAINT "template_twin_source_quarantine_fkey"
  FOREIGN KEY ("quarantineArtifactId")
  REFERENCES "template_twin_quarantine_artifacts"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE OR REPLACE FUNCTION template_twin_quarantine_immutable_identity() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin quarantine artifacts are append-only';
  END IF;
  IF OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR OLD."createdById" IS DISTINCT FROM NEW."createdById"
     OR OLD."lineageId" IS DISTINCT FROM NEW."lineageId"
     OR OLD."lineageVersion" IS DISTINCT FROM NEW."lineageVersion"
     OR OLD."intakeMode" IS DISTINCT FROM NEW."intakeMode"
     OR OLD."objectKey" IS DISTINCT FROM NEW."objectKey"
     OR OLD."objectVersionId" IS DISTINCT FROM NEW."objectVersionId"
     OR OLD."objectEtag" IS DISTINCT FROM NEW."objectEtag"
     OR OLD."sha256" IS DISTINCT FROM NEW."sha256"
     OR OLD."mimeType" IS DISTINCT FROM NEW."mimeType"
     OR OLD."sizeBytes" IS DISTINCT FROM NEW."sizeBytes"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt" THEN
    RAISE EXCEPTION 'Template Twin quarantine identity is immutable';
  END IF;
  IF OLD."status" IN ('REJECTED', 'ADMITTED') AND OLD IS DISTINCT FROM NEW THEN
    RAISE EXCEPTION 'Template Twin quarantine terminal state is immutable';
  END IF;
  IF NOT (
    OLD."status" = NEW."status"
    OR (OLD."status" = 'QUARANTINED' AND NEW."status" IN ('MALWARE_CLEAN', 'REJECTED'))
    OR (OLD."status" = 'MALWARE_CLEAN' AND NEW."status" IN ('ADMITTED', 'REJECTED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin quarantine state transition is invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_twin_quarantine_immutable_identity_guard
  BEFORE UPDATE OR DELETE ON "template_twin_quarantine_artifacts"
  FOR EACH ROW EXECUTE FUNCTION template_twin_quarantine_immutable_identity();

CREATE OR REPLACE FUNCTION template_twin_assert_quarantine_ledger() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM "template_twin_object_ledgers" l
    WHERE l."objectKey" = NEW."objectKey"
      AND l."practiceId" = NEW."practiceId"
      AND l."objectVersionId" = NEW."objectVersionId"
      AND l."objectEtag" = NEW."objectEtag"
      AND l."sha256" = NEW."sha256"
      AND l."sizeBytes" = NEW."sizeBytes"
      AND l."kind" = 'quarantine'
      AND l."state" = 'CLAIMED'
      AND l."claimType" = 'quarantine_artifact'
      AND l."claimId" = NEW."id"
  ) THEN
    RAISE EXCEPTION 'Template Twin quarantine object ledger ownership mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER template_twin_quarantine_ledger_consistency
  AFTER INSERT OR UPDATE ON "template_twin_quarantine_artifacts"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_quarantine_ledger();

-- Replace the ledger tenant function with the same accepted behavior plus the
-- new raw-quarantine claim type. Existing fill/source/test-output checks remain
-- byte-for-byte equivalent.
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
  ELSIF NEW."claimType" = 'quarantine_artifact' THEN
    SELECT q."practiceId", q."objectKey", q."sha256", q."sizeBytes",
           q."objectVersionId", q."objectEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_quarantine_artifacts" q WHERE q."id" = NEW."claimId";
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
  IF NEW."claimType" = 'quarantine_artifact'
     AND (NEW."kind" <> 'quarantine'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin quarantine object ledger claim integrity mismatch';
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

CREATE OR REPLACE FUNCTION template_twin_assert_quarantine_admission() RETURNS trigger AS $$
DECLARE source_practice TEXT;
DECLARE source_lineage TEXT;
DECLARE source_sha256 TEXT;
BEGIN
  IF NEW."status" <> 'ADMITTED' THEN
    RETURN NEW;
  END IF;
  SELECT s."practiceId", s."lineageId", s."sha256"
    INTO source_practice, source_lineage, source_sha256
    FROM "template_twin_source_artifacts" s
    WHERE s."quarantineArtifactId" = NEW."id"
      AND s."validationStatus" = 'accepted';
  IF source_practice IS NULL
     OR source_practice <> NEW."practiceId"
     OR source_lineage <> NEW."lineageId"
     OR source_sha256 <> NEW."metadataMinimizationEvidence"->>'minimizedSha256' THEN
    RAISE EXCEPTION 'Template Twin quarantine admission lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER template_twin_quarantine_admission_consistency
  AFTER INSERT OR UPDATE ON "template_twin_quarantine_artifacts"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_quarantine_admission();

CREATE OR REPLACE FUNCTION template_twin_assert_source_quarantine() RETURNS trigger AS $$
DECLARE quarantine_practice TEXT;
DECLARE quarantine_lineage TEXT;
DECLARE quarantine_status TEXT;
DECLARE minimized_sha256 TEXT;
BEGIN
  IF NEW."quarantineArtifactId" IS NULL THEN
    RETURN NEW;
  END IF;
  SELECT q."practiceId", q."lineageId", q."status",
         q."metadataMinimizationEvidence"->>'minimizedSha256'
    INTO quarantine_practice, quarantine_lineage, quarantine_status,
         minimized_sha256
    FROM "template_twin_quarantine_artifacts" q
    WHERE q."id" = NEW."quarantineArtifactId";
  IF quarantine_practice IS NULL
     OR quarantine_practice <> NEW."practiceId"
     OR quarantine_lineage <> NEW."lineageId"
     OR quarantine_status <> 'ADMITTED'
     OR minimized_sha256 <> NEW."sha256"
     OR NEW."validationStatus" <> 'accepted' THEN
    RAISE EXCEPTION 'Template Twin source quarantine admission mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER template_twin_source_quarantine_consistency
  AFTER INSERT OR UPDATE
  ON "template_twin_source_artifacts"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_source_quarantine();

-- Certification is a second, independent fail-closed boundary. The deferred
-- source/quarantine consistency triggers protect admission transactions, while
-- this existing BEFORE INSERT trigger is replaced so direct SQL cannot certify
-- a pre-GA source or bypass the clean-malware and minimized-source binding.
CREATE OR REPLACE FUNCTION template_twin_assert_certification_provider_identity() RETURNS trigger AS $$
DECLARE source_practice TEXT;
DECLARE source_lineage TEXT;
DECLARE source_sha256 TEXT;
DECLARE source_quarantine_id TEXT;
DECLARE certifier_practice TEXT;
DECLARE compiled_key TEXT;
DECLARE compiled_version_id TEXT;
DECLARE compiled_etag TEXT;
DECLARE compiled_sha256 TEXT;
DECLARE template_owner_practice TEXT;
DECLARE quarantine_practice TEXT;
DECLARE quarantine_lineage TEXT;
DECLARE quarantine_mode TEXT;
DECLARE quarantine_sha256 TEXT;
DECLARE quarantine_size_bytes INTEGER;
DECLARE quarantine_status TEXT;
DECLARE quarantine_malware JSONB;
DECLARE quarantine_metadata JSONB;
DECLARE quarantine_rejection_codes TEXT[];
DECLARE quarantine_scanned_at TIMESTAMPTZ;
DECLARE quarantine_admitted_at TIMESTAMPTZ;
BEGIN
  SELECT s."practiceId", s."lineageId", s."sha256", s."quarantineArtifactId",
         owner."practiceId", c."latestTestOutputObjectKey",
         c."latestTestOutputVersionId", c."latestTestOutputEtag",
         c."latestTestOutputSha256",
         q."practiceId", q."lineageId", q."intakeMode", q."sha256",
         q."sizeBytes", q."status", q."malwareScanEvidence",
         q."metadataMinimizationEvidence", q."rejectionCodes",
         q."scannedAt", q."admittedAt"
    INTO source_practice, source_lineage, source_sha256,
         source_quarantine_id, template_owner_practice, compiled_key,
         compiled_version_id, compiled_etag, compiled_sha256,
         quarantine_practice, quarantine_lineage, quarantine_mode,
         quarantine_sha256, quarantine_size_bytes, quarantine_status,
         quarantine_malware, quarantine_metadata, quarantine_rejection_codes,
         quarantine_scanned_at, quarantine_admitted_at
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    LEFT JOIN "users" owner ON owner."id" = n."doctorId"
    LEFT JOIN "template_twin_quarantine_artifacts" q
      ON q."id" = s."quarantineArtifactId"
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
  IF source_quarantine_id IS NULL
     OR quarantine_practice IS NULL
     OR quarantine_practice <> source_practice
     OR quarantine_lineage IS DISTINCT FROM source_lineage
     OR quarantine_mode IS DISTINCT FROM 'NATIVE_TEMPLATE'
     OR quarantine_status IS DISTINCT FROM 'ADMITTED'
     OR quarantine_scanned_at IS NULL
     OR quarantine_admitted_at IS NULL
     OR cardinality(quarantine_rejection_codes) <> 0
     OR quarantine_malware IS NULL
     OR quarantine_malware->>'profileVersion' IS DISTINCT FROM 'template-twin-clamd-instream-v1'
     OR quarantine_malware->>'scanner' IS DISTINCT FROM 'clamav-clamd'
     OR quarantine_malware->>'transport' IS DISTINCT FROM 'unix-domain-socket'
     OR quarantine_malware->>'verdict' IS DISTINCT FROM 'clean'
     OR quarantine_malware->>'sourceSha256' IS DISTINCT FROM quarantine_sha256
     OR quarantine_malware->>'sourceSizeBytes' IS DISTINCT FROM quarantine_size_bytes::TEXT
     OR COALESCE(quarantine_malware->>'engineVersion', '') = ''
     OR COALESCE(quarantine_malware->>'signatureVersion', '') !~ '^[0-9]+$'
     OR COALESCE(quarantine_malware->>'attestationSha256', '') !~ '^[a-f0-9]{64}$'
     OR quarantine_malware->>'threatNameSha256' IS NOT NULL
     OR quarantine_metadata IS NULL
     OR quarantine_metadata->>'profileVersion' IS DISTINCT FROM 'template-twin-docx-metadata-minimization-v1'
     OR quarantine_metadata->>'originalSha256' IS DISTINCT FROM quarantine_sha256
     OR quarantine_metadata->>'minimizedSha256' IS DISTINCT FROM source_sha256
     OR quarantine_metadata->>'zipEntryTimestampsNormalized' IS DISTINCT FROM 'true' THEN
    RAISE EXCEPTION 'Template Twin certification quarantine admission mismatch';
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
