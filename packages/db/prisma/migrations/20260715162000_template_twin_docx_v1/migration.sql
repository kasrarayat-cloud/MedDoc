-- Template Twin — Structure-Preserving DOCX v1
-- Additive schema only. This migration does not touch existing clinical data
-- beyond assigning every existing NoteTemplate row its own lineage root.

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_SOURCE_UPLOADED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_COMPILED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_QUARANTINED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_MAPPING_UPDATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_CERTIFIED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ACTIVATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_SYNTHETIC_TESTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_FIELD_REVIEWED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_SIGN_BLOCKED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RENDER_VERIFIED';

CREATE TYPE "TemplateTwinCertificationStatus" AS ENUM (
  'RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED', 'CERTIFIED', 'QUARANTINED'
);
CREATE TYPE "TemplateTwinDetectionStatus" AS ENUM (
  'RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED', 'CERTIFIED'
);
CREATE TYPE "TemplateTwinResolutionStatus" AS ENUM (
  'SUPPORTED', 'EXPLICITLY_DENIED', 'NOT_MENTIONED', 'AMBIGUOUS', 'CONFLICT',
  'NEEDS_CLINICIAN_INPUT', 'APPROVED_PRACTICE_DEFAULT'
);
CREATE TYPE "TemplateTwinFillStatus" AS ENUM (
  'RESOLVING', 'NEEDS_REVIEW', 'VERIFIED', 'SIGNED', 'FAILED'
);

ALTER TABLE "note_templates"
  ADD COLUMN "lineageId" TEXT,
  ADD COLUMN "parentVersionId" TEXT,
  ADD COLUMN "templateKind" TEXT NOT NULL DEFAULT 'structured';

UPDATE "note_templates" SET "lineageId" = "id" WHERE "lineageId" IS NULL;
ALTER TABLE "note_templates" ALTER COLUMN "lineageId" SET NOT NULL;

CREATE UNIQUE INDEX "note_templates_lineageId_version_key"
  ON "note_templates"("lineageId", "version");
CREATE INDEX "note_templates_doctorId_templateKind_status_idx"
  ON "note_templates"("doctorId", "templateKind", "status");

CREATE TABLE "template_twin_source_artifacts" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "createdById" TEXT,
  "lineageId" TEXT NOT NULL,
  "lineageVersion" INTEGER NOT NULL,
  "objectKey" TEXT,
  "sha256" CHAR(64) NOT NULL,
  "mimeType" TEXT NOT NULL,
  "sizeBytes" INTEGER NOT NULL,
  "validationStatus" TEXT NOT NULL DEFAULT 'accepted',
  "rejectionCodes" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_source_artifacts_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_source_size_positive" CHECK ("sizeBytes" > 0),
  CONSTRAINT "template_twin_source_sha256_hex" CHECK ("sha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_source_status" CHECK ("validationStatus" IN ('accepted', 'quarantined')),
  CONSTRAINT "template_twin_source_object_state" CHECK (
    ("validationStatus" = 'accepted' AND "objectKey" IS NOT NULL)
    OR ("validationStatus" = 'quarantined' AND "objectKey" IS NULL)
  )
);

CREATE UNIQUE INDEX "template_twin_source_artifacts_objectKey_key"
  ON "template_twin_source_artifacts"("objectKey");
CREATE INDEX "template_twin_source_artifacts_practiceId_createdAt_idx"
  ON "template_twin_source_artifacts"("practiceId", "createdAt");
CREATE INDEX "template_twin_source_artifacts_lineageId_lineageVersion_idx"
  ON "template_twin_source_artifacts"("lineageId", "lineageVersion");
CREATE INDEX "template_twin_source_artifacts_sha256_idx"
  ON "template_twin_source_artifacts"("sha256");

CREATE TABLE "template_twin_compiled_versions" (
  "id" TEXT NOT NULL,
  "sourceArtifactId" TEXT NOT NULL,
  "noteTemplateId" TEXT NOT NULL,
  "compilerVersion" TEXT NOT NULL,
  "irSchemaVersion" INTEGER NOT NULL,
  "compiledAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "compiledDocumentIr" JSONB NOT NULL,
  "unsupportedElements" JSONB NOT NULL,
  "structureSha256" CHAR(64) NOT NULL,
  "staticContentSha256" CHAR(64) NOT NULL,
  "certificationStatus" "TemplateTwinCertificationStatus" NOT NULL DEFAULT 'NEEDS_CONFIRMATION',
  "blockingUnsupportedCount" INTEGER NOT NULL DEFAULT 0,
  "latestSyntheticTestManifest" JSONB,
  "latestTestMappingsSha256" CHAR(64),
  "latestTestOutputObjectKey" TEXT,
  "latestTestOutputSha256" CHAR(64),
  "latestTestStaticContentSha256" CHAR(64),
  "latestTestRoundTrip" JSONB,
  "latestTestVerifiedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_compiled_versions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_compiled_hashes_hex" CHECK (
    "structureSha256" ~ '^[a-f0-9]{64}$'
    AND "staticContentSha256" ~ '^[a-f0-9]{64}$'
    AND ("latestTestMappingsSha256" IS NULL OR "latestTestMappingsSha256" ~ '^[a-f0-9]{64}$')
    AND ("latestTestOutputSha256" IS NULL OR "latestTestOutputSha256" ~ '^[a-f0-9]{64}$')
    AND ("latestTestStaticContentSha256" IS NULL OR "latestTestStaticContentSha256" ~ '^[a-f0-9]{64}$')
  ),
  CONSTRAINT "template_twin_compiled_test_state" CHECK (
    ("latestTestVerifiedAt" IS NULL
      AND "latestSyntheticTestManifest" IS NULL
      AND "latestTestMappingsSha256" IS NULL
      AND "latestTestOutputObjectKey" IS NULL
      AND "latestTestOutputSha256" IS NULL
      AND "latestTestStaticContentSha256" IS NULL
      AND "latestTestRoundTrip" IS NULL)
    OR
    ("latestTestVerifiedAt" IS NOT NULL
      AND "latestSyntheticTestManifest" IS NOT NULL
      AND "latestTestMappingsSha256" IS NOT NULL
      AND "latestTestOutputObjectKey" IS NOT NULL
      AND "latestTestOutputSha256" IS NOT NULL
      AND "latestTestStaticContentSha256" IS NOT NULL
      AND "latestTestRoundTrip" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_compiled_counts_nonnegative" CHECK ("blockingUnsupportedCount" >= 0)
);

CREATE UNIQUE INDEX "template_twin_compiled_versions_noteTemplateId_key"
  ON "template_twin_compiled_versions"("noteTemplateId");
CREATE UNIQUE INDEX "template_twin_compiled_versions_latestTestOutputObjectKey_key"
  ON "template_twin_compiled_versions"("latestTestOutputObjectKey");
CREATE UNIQUE INDEX "template_twin_compiled_source_compiler_key"
  ON "template_twin_compiled_versions"("sourceArtifactId", "compilerVersion");
CREATE INDEX "template_twin_compiled_status_compiledAt_idx"
  ON "template_twin_compiled_versions"("certificationStatus", "compiledAt");

CREATE TABLE "template_twin_field_definitions" (
  "id" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "fieldId" TEXT NOT NULL,
  "displayOrder" INTEGER NOT NULL,
  "originalLabel" TEXT NOT NULL,
  "fieldKind" TEXT NOT NULL,
  "allowedOptions" JSONB,
  "rendererBinding" JSONB NOT NULL,
  "detectionStatus" "TemplateTwinDetectionStatus" NOT NULL,
  "clinicallyMaterial" BOOLEAN NOT NULL DEFAULT true,
  "criticality" TEXT NOT NULL DEFAULT 'routine',
  "required" BOOLEAN NOT NULL DEFAULT false,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_field_definitions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_field_display_order_nonnegative" CHECK ("displayOrder" >= 0)
);

CREATE UNIQUE INDEX "template_twin_field_compiledVersionId_fieldId_key"
  ON "template_twin_field_definitions"("compiledVersionId", "fieldId");
CREATE INDEX "template_twin_field_compiledVersionId_displayOrder_idx"
  ON "template_twin_field_definitions"("compiledVersionId", "displayOrder");
CREATE INDEX "template_twin_field_compiledVersionId_detectionStatus_idx"
  ON "template_twin_field_definitions"("compiledVersionId", "detectionStatus");

CREATE TABLE "template_twin_semantic_mappings" (
  "id" TEXT NOT NULL,
  "fieldDefinitionId" TEXT NOT NULL,
  "clinicalConcept" TEXT,
  "expectedDataType" TEXT NOT NULL,
  "polarityBehavior" TEXT NOT NULL,
  "temporality" TEXT,
  "laterality" TEXT,
  "unitPolicy" TEXT,
  "approvedSynonyms" JSONB NOT NULL,
  "required" BOOLEAN NOT NULL DEFAULT false,
  "blankPolicy" TEXT NOT NULL,
  "unknownPolicy" TEXT NOT NULL,
  "practiceDefault" TEXT,
  "mappingStatus" "TemplateTwinDetectionStatus" NOT NULL DEFAULT 'NEEDS_CONFIRMATION',
  "proposedByModel" TEXT,
  "approvedById" TEXT,
  "approvedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_semantic_mappings_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "template_twin_semantic_mappings_fieldDefinitionId_key"
  ON "template_twin_semantic_mappings"("fieldDefinitionId");
CREATE INDEX "template_twin_semantic_mappings_status_updatedAt_idx"
  ON "template_twin_semantic_mappings"("mappingStatus", "updatedAt");

CREATE TABLE "template_twin_certifications" (
  "id" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "certifiedById" TEXT NOT NULL,
  "compiledStructureSha256" CHAR(64) NOT NULL,
  "approvedMappingsSha256" CHAR(64) NOT NULL,
  "syntheticTestManifest" JSONB NOT NULL,
  "testOutputObjectKey" TEXT NOT NULL,
  "testOutputSha256" CHAR(64) NOT NULL,
  "certifiedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_certifications_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_certification_hashes_hex" CHECK (
    "compiledStructureSha256" ~ '^[a-f0-9]{64}$'
    AND "approvedMappingsSha256" ~ '^[a-f0-9]{64}$'
    AND "testOutputSha256" ~ '^[a-f0-9]{64}$'
  )
);

CREATE UNIQUE INDEX "template_twin_certifications_compiledVersionId_key"
  ON "template_twin_certifications"("compiledVersionId");
CREATE UNIQUE INDEX "template_twin_certifications_testOutputObjectKey_key"
  ON "template_twin_certifications"("testOutputObjectKey");
CREATE INDEX "template_twin_certifications_certifiedById_certifiedAt_idx"
  ON "template_twin_certifications"("certifiedById", "certifiedAt");

CREATE TABLE "template_twin_fill_manifests" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "noteTemplateId" TEXT NOT NULL,
  "noteTemplateVersion" INTEGER NOT NULL,
  "compilerVersion" TEXT NOT NULL,
  "resolverVersion" TEXT NOT NULL,
  "resolverModelVersion" TEXT,
  "rendererVersion" TEXT NOT NULL,
  "status" "TemplateTwinFillStatus" NOT NULL DEFAULT 'RESOLVING',
  "fillManifest" JSONB NOT NULL,
  "manifestVersion" INTEGER NOT NULL DEFAULT 1,
  "manifestSha256" CHAR(64) NOT NULL,
  "factSetSha256" CHAR(64) NOT NULL,
  "validationResult" JSONB NOT NULL,
  "filledCount" INTEGER NOT NULL DEFAULT 0,
  "needsReviewCount" INTEGER NOT NULL DEFAULT 0,
  "notMentionedCount" INTEGER NOT NULL DEFAULT 0,
  "conflictCount" INTEGER NOT NULL DEFAULT 0,
  "criticalUnresolvedCount" INTEGER NOT NULL DEFAULT 0,
  "outputObjectKey" TEXT,
  "outputSha256" CHAR(64),
  "outputMimeType" TEXT,
  "outputSizeBytes" INTEGER,
  "staticContentSha256" CHAR(64),
  "roundTripVerified" BOOLEAN NOT NULL DEFAULT false,
  "roundTripVerification" JSONB,
  "reviewedAt" TIMESTAMPTZ(6),
  "signedDecisionAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_fill_manifests_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_fill_hashes_hex" CHECK (
    "manifestSha256" ~ '^[a-f0-9]{64}$'
    AND "factSetSha256" ~ '^[a-f0-9]{64}$'
    AND ("outputSha256" IS NULL OR "outputSha256" ~ '^[a-f0-9]{64}$')
    AND ("staticContentSha256" IS NULL OR "staticContentSha256" ~ '^[a-f0-9]{64}$')
  ),
  CONSTRAINT "template_twin_fill_counts_nonnegative" CHECK (
    "filledCount" >= 0 AND "needsReviewCount" >= 0
    AND "notMentionedCount" >= 0 AND "conflictCount" >= 0
    AND "criticalUnresolvedCount" >= 0
  )
);

CREATE UNIQUE INDEX "template_twin_fill_manifests_visitId_key"
  ON "template_twin_fill_manifests"("visitId");
CREATE UNIQUE INDEX "template_twin_fill_manifests_outputObjectKey_key"
  ON "template_twin_fill_manifests"("outputObjectKey");
CREATE INDEX "template_twin_fill_practice_status_updatedAt_idx"
  ON "template_twin_fill_manifests"("practiceId", "status", "updatedAt");
CREATE INDEX "template_twin_fill_compiledVersionId_status_idx"
  ON "template_twin_fill_manifests"("compiledVersionId", "status");
CREATE INDEX "template_twin_fill_status_criticalUnresolvedCount_idx"
  ON "template_twin_fill_manifests"("status", "criticalUnresolvedCount");

CREATE TABLE "template_twin_review_decisions" (
  "id" TEXT NOT NULL,
  "fillManifestId" TEXT NOT NULL,
  "fieldId" TEXT NOT NULL,
  "fieldDefinitionId" TEXT NOT NULL,
  "resolutionStatus" "TemplateTwinResolutionStatus" NOT NULL,
  "decisionKind" TEXT NOT NULL,
  "previousValue" JSONB,
  "correctedValue" JSONB,
  "sourceFactIds" JSONB NOT NULL,
  "reasonCode" TEXT,
  "createMappingRule" BOOLEAN NOT NULL DEFAULT false,
  "expectedManifestVersion" INTEGER NOT NULL,
  "reviewerId" TEXT,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_review_decisions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "template_twin_review_fillManifestId_fieldId_createdAt_idx"
  ON "template_twin_review_decisions"("fillManifestId", "fieldId", "createdAt");
CREATE INDEX "template_twin_review_fieldDefinitionId_createdAt_idx"
  ON "template_twin_review_decisions"("fieldDefinitionId", "createdAt");
CREATE INDEX "template_twin_review_reviewerId_createdAt_idx"
  ON "template_twin_review_decisions"("reviewerId", "createdAt");

ALTER TABLE "template_twin_source_artifacts"
  ADD CONSTRAINT "template_twin_source_practice_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_source_createdBy_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "template_twin_compiled_versions"
  ADD CONSTRAINT "template_twin_compiled_source_fkey" FOREIGN KEY ("sourceArtifactId") REFERENCES "template_twin_source_artifacts"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_compiled_noteTemplate_fkey" FOREIGN KEY ("noteTemplateId") REFERENCES "note_templates"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "template_twin_field_definitions"
  ADD CONSTRAINT "template_twin_field_compiled_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_semantic_mappings"
  ADD CONSTRAINT "template_twin_mapping_field_fkey" FOREIGN KEY ("fieldDefinitionId") REFERENCES "template_twin_field_definitions"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_mapping_approver_fkey" FOREIGN KEY ("approvedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "template_twin_certifications"
  ADD CONSTRAINT "template_twin_certification_compiled_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_certification_certifier_fkey" FOREIGN KEY ("certifiedById") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "template_twin_fill_manifests"
  ADD CONSTRAINT "template_twin_fill_practice_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_fill_visit_fkey" FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_fill_compiled_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "template_twin_review_decisions"
  ADD CONSTRAINT "template_twin_review_fill_fkey" FOREIGN KEY ("fillManifestId") REFERENCES "template_twin_fill_manifests"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_review_field_fkey" FOREIGN KEY ("fieldDefinitionId") REFERENCES "template_twin_field_definitions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_review_reviewer_fkey" FOREIGN KEY ("reviewerId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Source packages and certifications are append-only. Certified compiler,
-- field, and mapping rows become immutable. A signed fill manifest is frozen.
CREATE OR REPLACE FUNCTION template_twin_source_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin source artifacts are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_source_no_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_source_artifacts"
  FOR EACH ROW EXECUTE FUNCTION template_twin_source_immutable();

CREATE OR REPLACE FUNCTION template_twin_certification_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin certifications are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_certification_no_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_certifications"
  FOR EACH ROW EXECUTE FUNCTION template_twin_certification_immutable();

CREATE OR REPLACE FUNCTION template_twin_compiled_guard() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM "template_twin_certifications" c WHERE c."compiledVersionId" = OLD."id") THEN
    RAISE EXCEPTION 'Certified Template Twin compilations are immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_compiled_guard_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_compiled_versions"
  FOR EACH ROW EXECUTE FUNCTION template_twin_compiled_guard();

CREATE OR REPLACE FUNCTION template_twin_field_guard() RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_certifications" c
    WHERE c."compiledVersionId" = OLD."compiledVersionId"
  ) THEN
    RAISE EXCEPTION 'Certified Template Twin fields are immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_field_guard_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_field_definitions"
  FOR EACH ROW EXECUTE FUNCTION template_twin_field_guard();

CREATE OR REPLACE FUNCTION template_twin_mapping_guard() RETURNS trigger AS $$
DECLARE compilation_id TEXT;
BEGIN
  SELECT f."compiledVersionId" INTO compilation_id
  FROM "template_twin_field_definitions" f
  WHERE f."id" = OLD."fieldDefinitionId";
  IF EXISTS (
    SELECT 1 FROM "template_twin_certifications" c
    WHERE c."compiledVersionId" = compilation_id
  ) THEN
    RAISE EXCEPTION 'Certified Template Twin mappings are immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_mapping_guard_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_semantic_mappings"
  FOR EACH ROW EXECUTE FUNCTION template_twin_mapping_guard();

CREATE OR REPLACE FUNCTION template_twin_signed_fill_guard() RETURNS trigger AS $$
BEGIN
  IF OLD."signedDecisionAt" IS NOT NULL THEN
    RAISE EXCEPTION 'Signed Template Twin fill manifests are immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_signed_fill_guard_update_delete
  BEFORE UPDATE OR DELETE ON "template_twin_fill_manifests"
  FOR EACH ROW EXECUTE FUNCTION template_twin_signed_fill_guard();
