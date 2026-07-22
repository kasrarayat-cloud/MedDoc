-- Template Twin native-DOCX — ADDITIVE-ONLY migration (2026-07-22).
-- Adds 7 template_twin_* tables, 4 TemplateTwin* enums, and 10 TEMPLATE_TWIN_*
-- AuditAction values. ZERO ALTER/DROP on any existing table (note_templates,
-- users, practices, transcribe_visits, audit_logs stay byte-identical). Version-
-- forking lineage lives entirely in template_twin_source_artifacts.lineageId.
-- Safe on a live DB; the feature is dormant unless NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX=true.
--
-- ROLLBACK (reversible): DROP TABLE the 7 template_twin_* tables (CASCADE) and
-- DROP TYPE the 4 TemplateTwin* enums. The 10 additive AuditAction enum values
-- remain (PostgreSQL cannot drop enum values without recreating the type); they
-- are inert when unused. No existing data is touched by apply or rollback.

-- CreateEnum
CREATE TYPE "TemplateTwinCertificationStatus" AS ENUM ('RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED', 'CERTIFIED', 'QUARANTINED');

-- CreateEnum
CREATE TYPE "TemplateTwinDetectionStatus" AS ENUM ('RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED', 'CERTIFIED');

-- CreateEnum
CREATE TYPE "TemplateTwinResolutionStatus" AS ENUM ('SUPPORTED', 'EXPLICITLY_DENIED', 'NOT_MENTIONED', 'AMBIGUOUS', 'CONFLICT', 'NEEDS_CLINICIAN_INPUT', 'APPROVED_PRACTICE_DEFAULT');

-- CreateEnum
CREATE TYPE "TemplateTwinFillStatus" AS ENUM ('RESOLVING', 'NEEDS_REVIEW', 'VERIFIED', 'SIGNED', 'FAILED');

-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_SOURCE_UPLOADED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_COMPILED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_QUARANTINED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_MAPPING_UPDATED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_CERTIFIED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_ACTIVATED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_SYNTHETIC_TESTED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_FIELD_REVIEWED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_SIGN_BLOCKED';
ALTER TYPE "AuditAction" ADD VALUE 'TEMPLATE_TWIN_RENDER_VERIFIED';

-- CreateTable
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
    "rejectionCodes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "template_twin_source_artifacts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
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

    CONSTRAINT "template_twin_compiled_versions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
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

    CONSTRAINT "template_twin_field_definitions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
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

-- CreateTable
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

    CONSTRAINT "template_twin_certifications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
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

    CONSTRAINT "template_twin_fill_manifests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
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

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_source_artifacts_objectKey_key" ON "template_twin_source_artifacts"("objectKey");

-- CreateIndex
CREATE INDEX "template_twin_source_artifacts_practiceId_createdAt_idx" ON "template_twin_source_artifacts"("practiceId", "createdAt");

-- CreateIndex
CREATE INDEX "template_twin_source_artifacts_lineageId_lineageVersion_idx" ON "template_twin_source_artifacts"("lineageId", "lineageVersion");

-- CreateIndex
CREATE INDEX "template_twin_source_artifacts_sha256_idx" ON "template_twin_source_artifacts"("sha256");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_compiled_versions_noteTemplateId_key" ON "template_twin_compiled_versions"("noteTemplateId");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_compiled_versions_latestTestOutputObjectKey_key" ON "template_twin_compiled_versions"("latestTestOutputObjectKey");

-- CreateIndex
CREATE INDEX "template_twin_compiled_versions_sourceArtifactId_compilerVe_idx" ON "template_twin_compiled_versions"("sourceArtifactId", "compilerVersion");

-- CreateIndex
CREATE INDEX "template_twin_compiled_versions_certificationStatus_compile_idx" ON "template_twin_compiled_versions"("certificationStatus", "compiledAt");

-- CreateIndex
CREATE INDEX "template_twin_field_definitions_compiledVersionId_displayOr_idx" ON "template_twin_field_definitions"("compiledVersionId", "displayOrder");

-- CreateIndex
CREATE INDEX "template_twin_field_definitions_compiledVersionId_detection_idx" ON "template_twin_field_definitions"("compiledVersionId", "detectionStatus");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_field_definitions_compiledVersionId_fieldId_key" ON "template_twin_field_definitions"("compiledVersionId", "fieldId");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_semantic_mappings_fieldDefinitionId_key" ON "template_twin_semantic_mappings"("fieldDefinitionId");

-- CreateIndex
CREATE INDEX "template_twin_semantic_mappings_mappingStatus_updatedAt_idx" ON "template_twin_semantic_mappings"("mappingStatus", "updatedAt");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_certifications_compiledVersionId_key" ON "template_twin_certifications"("compiledVersionId");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_certifications_testOutputObjectKey_key" ON "template_twin_certifications"("testOutputObjectKey");

-- CreateIndex
CREATE INDEX "template_twin_certifications_certifiedById_certifiedAt_idx" ON "template_twin_certifications"("certifiedById", "certifiedAt");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_fill_manifests_visitId_key" ON "template_twin_fill_manifests"("visitId");

-- CreateIndex
CREATE UNIQUE INDEX "template_twin_fill_manifests_outputObjectKey_key" ON "template_twin_fill_manifests"("outputObjectKey");

-- CreateIndex
CREATE INDEX "template_twin_fill_manifests_practiceId_status_updatedAt_idx" ON "template_twin_fill_manifests"("practiceId", "status", "updatedAt");

-- CreateIndex
CREATE INDEX "template_twin_fill_manifests_compiledVersionId_status_idx" ON "template_twin_fill_manifests"("compiledVersionId", "status");

-- CreateIndex
CREATE INDEX "template_twin_fill_manifests_status_criticalUnresolvedCount_idx" ON "template_twin_fill_manifests"("status", "criticalUnresolvedCount");

-- CreateIndex
CREATE INDEX "template_twin_review_decisions_fillManifestId_fieldId_creat_idx" ON "template_twin_review_decisions"("fillManifestId", "fieldId", "createdAt");

-- CreateIndex
CREATE INDEX "template_twin_review_decisions_fieldDefinitionId_createdAt_idx" ON "template_twin_review_decisions"("fieldDefinitionId", "createdAt");

-- CreateIndex
CREATE INDEX "template_twin_review_decisions_reviewerId_createdAt_idx" ON "template_twin_review_decisions"("reviewerId", "createdAt");

-- AddForeignKey
ALTER TABLE "template_twin_source_artifacts" ADD CONSTRAINT "template_twin_source_artifacts_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_source_artifacts" ADD CONSTRAINT "template_twin_source_artifacts_createdById_fkey" FOREIGN KEY ("createdById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_compiled_versions" ADD CONSTRAINT "template_twin_compiled_versions_sourceArtifactId_fkey" FOREIGN KEY ("sourceArtifactId") REFERENCES "template_twin_source_artifacts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_compiled_versions" ADD CONSTRAINT "template_twin_compiled_versions_noteTemplateId_fkey" FOREIGN KEY ("noteTemplateId") REFERENCES "note_templates"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_field_definitions" ADD CONSTRAINT "template_twin_field_definitions_compiledVersionId_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_semantic_mappings" ADD CONSTRAINT "template_twin_semantic_mappings_fieldDefinitionId_fkey" FOREIGN KEY ("fieldDefinitionId") REFERENCES "template_twin_field_definitions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_semantic_mappings" ADD CONSTRAINT "template_twin_semantic_mappings_approvedById_fkey" FOREIGN KEY ("approvedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_certifications" ADD CONSTRAINT "template_twin_certifications_compiledVersionId_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_certifications" ADD CONSTRAINT "template_twin_certifications_certifiedById_fkey" FOREIGN KEY ("certifiedById") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_fill_manifests" ADD CONSTRAINT "template_twin_fill_manifests_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_fill_manifests" ADD CONSTRAINT "template_twin_fill_manifests_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_fill_manifests" ADD CONSTRAINT "template_twin_fill_manifests_compiledVersionId_fkey" FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_review_decisions" ADD CONSTRAINT "template_twin_review_decisions_fillManifestId_fkey" FOREIGN KEY ("fillManifestId") REFERENCES "template_twin_fill_manifests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_review_decisions" ADD CONSTRAINT "template_twin_review_decisions_fieldDefinitionId_fkey" FOREIGN KEY ("fieldDefinitionId") REFERENCES "template_twin_field_definitions"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "template_twin_review_decisions" ADD CONSTRAINT "template_twin_review_decisions_reviewerId_fkey" FOREIGN KEY ("reviewerId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
