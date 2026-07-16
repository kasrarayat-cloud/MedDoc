-- Template Twin deterministic placeholder intent + static practice assets.
-- Additive first-deployment migration. No existing row is rewritten.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STATIC_ASSET_APPROVED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STATIC_ASSET_REJECTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STATIC_ASSET_REVOKED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STATIC_ASSET_USED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_FIELD_INTENT_RECORDED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_CUSTOM_EXAMPLE_EXECUTED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_CUSTOM_EXAMPLE_ACKNOWLEDGED';

ALTER TABLE "template_twin_compiled_versions"
  ADD COLUMN "latestTestFieldIntentsSha256" CHAR(64),
  ADD CONSTRAINT "template_twin_compiled_field_intents_sha256_hex" CHECK (
    "latestTestFieldIntentsSha256" IS NULL
    OR "latestTestFieldIntentsSha256" ~ '^[a-f0-9]{64}$'
  ) NOT VALID;

ALTER TABLE "template_twin_certifications"
  ADD COLUMN "approvedFieldIntentsSha256" CHAR(64),
  ADD COLUMN "approvedCustomExampleProofSha256" CHAR(64),
  ADD CONSTRAINT "template_twin_cert_field_intents_sha256_hex" CHECK (
    "approvedFieldIntentsSha256" IS NULL
    OR "approvedFieldIntentsSha256" ~ '^[a-f0-9]{64}$'
  ) NOT VALID,
  ADD CONSTRAINT "template_twin_cert_custom_example_proof_sha256_hex" CHECK (
    "approvedCustomExampleProofSha256" IS NULL
    OR "approvedCustomExampleProofSha256" ~ '^[a-f0-9]{64}$'
  ) NOT VALID;

ALTER TABLE "template_twin_fill_manifests"
  ADD COLUMN "fieldIntentsSha256" CHAR(64),
  ADD CONSTRAINT "template_twin_fill_field_intents_sha256_hex" CHECK (
    "fieldIntentsSha256" IS NULL
    OR "fieldIntentsSha256" ~ '^[a-f0-9]{64}$'
  ) NOT VALID;

CREATE TABLE "template_twin_field_intent_decisions" (
  "id" TEXT NOT NULL,
  "fieldDefinitionId" TEXT NOT NULL,
  "version" INTEGER NOT NULL,
  "intentKind" TEXT NOT NULL,
  "supportedConcept" TEXT,
  "customConceptId" TEXT,
  "customSpec" JSONB,
  "customSpecSha256" CHAR(64),
  "reason" TEXT,
  "decidedById" TEXT NOT NULL,
  "decidedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_field_intent_decisions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_field_intent_one_decision_per_version" CHECK ("version" = 1),
  CONSTRAINT "template_twin_field_intent_kind" CHECK (
    "intentKind" IN ('UNRESOLVED', 'SUPPORTED_CONCEPT', 'STATIC', 'CUSTOM_CONCEPT')
  ),
  CONSTRAINT "template_twin_field_intent_custom_sha256_hex" CHECK (
    "customSpecSha256" IS NULL OR "customSpecSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_field_intent_shape" CHECK (
    ("intentKind" IN ('UNRESOLVED', 'STATIC')
      AND "supportedConcept" IS NULL
      AND "customConceptId" IS NULL
      AND "customSpec" IS NULL
      AND "customSpecSha256" IS NULL)
    OR
    ("intentKind" = 'SUPPORTED_CONCEPT'
      AND char_length(btrim("supportedConcept")) BETWEEN 1 AND 160
      AND "customConceptId" IS NULL
      AND "customSpec" IS NULL
      AND "customSpecSha256" IS NULL)
    OR
    ("intentKind" = 'CUSTOM_CONCEPT'
      AND "supportedConcept" IS NULL
      AND char_length(btrim("customConceptId")) BETWEEN 8 AND 160
      AND "customSpec" IS NOT NULL
      AND "customSpecSha256" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_field_intent_reason_length" CHECK (
    "reason" IS NULL OR char_length(btrim("reason")) BETWEEN 3 AND 1000
  ),
  CONSTRAINT "template_twin_field_intent_decisions_fieldDefinitionId_fkey" FOREIGN KEY ("fieldDefinitionId")
    REFERENCES "template_twin_field_definitions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_field_intent_decisions_decidedById_fkey" FOREIGN KEY ("decidedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_field_intent_decisions_fieldDefinitionId_key"
  ON "template_twin_field_intent_decisions"("fieldDefinitionId");
CREATE INDEX "template_twin_field_intent_decisions_fieldDefinitionId_deci_idx"
  ON "template_twin_field_intent_decisions"("fieldDefinitionId", "decidedAt");
CREATE INDEX "template_twin_field_intent_decisions_decidedById_decidedAt_idx"
  ON "template_twin_field_intent_decisions"("decidedById", "decidedAt");

CREATE TABLE "template_twin_custom_example_executions" (
  "id" TEXT NOT NULL,
  "batchId" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "fieldDefinitionId" TEXT NOT NULL,
  "fieldIntentDecisionId" TEXT NOT NULL,
  "fieldId" TEXT NOT NULL,
  "conceptId" TEXT NOT NULL,
  "exampleKind" TEXT NOT NULL,
  "exampleId" TEXT NOT NULL,
  "exampleDefinitionSha256" CHAR(64) NOT NULL,
  "exampleEvidenceSha256" CHAR(64) NOT NULL,
  "specificationSha256" CHAR(64) NOT NULL,
  "specificationSetSha256" CHAR(64) NOT NULL,
  "mappingsSha256" CHAR(64) NOT NULL,
  "fieldIntentsSha256" CHAR(64) NOT NULL,
  "contractVersion" TEXT NOT NULL,
  "extractionSchemaSha256" CHAR(64) NOT NULL,
  "extractorVersion" TEXT NOT NULL,
  "extractionSchemaVersion" TEXT NOT NULL,
  "provider" TEXT NOT NULL,
  "providerSha256" CHAR(64) NOT NULL,
  "model" TEXT NOT NULL,
  "modelSha256" CHAR(64) NOT NULL,
  "resultStatus" TEXT NOT NULL,
  "resultValue" JSONB NOT NULL,
  "resultFactCount" INTEGER NOT NULL,
  "resultSummary" JSONB NOT NULL,
  "resultSha256" CHAR(64) NOT NULL,
  "passed" BOOLEAN NOT NULL,
  "failureCode" TEXT,
  "executedById" TEXT NOT NULL,
  "executedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "acknowledgedById" TEXT,
  "acknowledgedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_custom_example_executions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_custom_example_kind" CHECK (
    "exampleKind" IN ('POSITIVE', 'NEGATIVE', 'AMBIGUITY')
  ),
  CONSTRAINT "template_twin_custom_example_result_fact_count" CHECK (
    "resultFactCount" >= 0
  ),
  CONSTRAINT "template_twin_custom_example_ack_shape" CHECK (
    ("acknowledgedById" IS NULL AND "acknowledgedAt" IS NULL)
    OR ("acknowledgedById" IS NOT NULL AND "acknowledgedAt" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_custom_example_sha256_hex" CHECK (
    "exampleDefinitionSha256" ~ '^[a-f0-9]{64}$'
    AND "exampleEvidenceSha256" ~ '^[a-f0-9]{64}$'
    AND "specificationSha256" ~ '^[a-f0-9]{64}$'
    AND "specificationSetSha256" ~ '^[a-f0-9]{64}$'
    AND "mappingsSha256" ~ '^[a-f0-9]{64}$'
    AND "fieldIntentsSha256" ~ '^[a-f0-9]{64}$'
    AND "extractionSchemaSha256" ~ '^[a-f0-9]{64}$'
    AND "providerSha256" ~ '^[a-f0-9]{64}$'
    AND "modelSha256" ~ '^[a-f0-9]{64}$'
    AND "resultSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_custom_example_practiceId_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_custom_example_compiledVersionId_fkey" FOREIGN KEY ("compiledVersionId")
    REFERENCES "template_twin_compiled_versions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_custom_example_fieldDefinitionId_fkey" FOREIGN KEY ("fieldDefinitionId")
    REFERENCES "template_twin_field_definitions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_custom_example_fieldIntentDecisionId_fkey" FOREIGN KEY ("fieldIntentDecisionId")
    REFERENCES "template_twin_field_intent_decisions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_custom_example_executedById_fkey" FOREIGN KEY ("executedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_custom_example_acknowledgedById_fkey" FOREIGN KEY ("acknowledgedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_custom_example_batch_field_kind_id_key"
  ON "template_twin_custom_example_executions"("batchId", "fieldId", "exampleKind", "exampleId");
CREATE INDEX "template_twin_custom_example_compiled_executed_idx"
  ON "template_twin_custom_example_executions"("compiledVersionId", "executedAt");
CREATE INDEX "template_twin_custom_example_intent_executed_idx"
  ON "template_twin_custom_example_executions"("fieldIntentDecisionId", "executedAt");
CREATE INDEX "template_twin_custom_example_practice_executed_idx"
  ON "template_twin_custom_example_executions"("practiceId", "executedAt");

CREATE TABLE "template_twin_static_assets" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "sha256" CHAR(64) NOT NULL,
  "mimeType" TEXT NOT NULL,
  "width" INTEGER NOT NULL,
  "height" INTEGER NOT NULL,
  "sizeBytes" INTEGER NOT NULL,
  "scannerVersion" TEXT NOT NULL,
  "ocrEngineVersion" TEXT NOT NULL,
  "ocrTextSha256" CHAR(64) NOT NULL,
  "metadataEvidenceSha256" CHAR(64) NOT NULL,
  "privacyEvidenceSha256" CHAR(64) NOT NULL,
  "privacyScanProvider" TEXT NOT NULL,
  "privacyScanModel" TEXT NOT NULL,
  "inspectionEvidenceSha256" CHAR(64) NOT NULL,
  "inspectionEvidence" JSONB NOT NULL,
  "createdById" TEXT NOT NULL,
  "currentStatus" TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
  "currentDecisionVersion" INTEGER NOT NULL DEFAULT 0,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_static_assets_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_static_asset_sha256_hex" CHECK ("sha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_static_asset_evidence_sha256_hex" CHECK (
    "ocrTextSha256" ~ '^[a-f0-9]{64}$'
    AND "metadataEvidenceSha256" ~ '^[a-f0-9]{64}$'
    AND "privacyEvidenceSha256" ~ '^[a-f0-9]{64}$'
    AND "inspectionEvidenceSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_static_asset_safe_png" CHECK ("mimeType" = 'image/png'),
  CONSTRAINT "template_twin_static_asset_privacy_scanner" CHECK (
    "privacyScanProvider" = 'anthropic'
    AND char_length(btrim("privacyScanModel")) BETWEEN 1 AND 120
  ),
  CONSTRAINT "template_twin_static_asset_dimensions" CHECK (
    "width" BETWEEN 1 AND 4096
    AND "height" BETWEEN 1 AND 4096
    AND "width"::BIGINT * "height"::BIGINT <= 16777216
  ),
  CONSTRAINT "template_twin_static_asset_size" CHECK ("sizeBytes" BETWEEN 1 AND 5242880),
  CONSTRAINT "template_twin_static_asset_status" CHECK (
    "currentStatus" IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED', 'REVOKED')
  ),
  CONSTRAINT "template_twin_static_asset_decision_version" CHECK (
    ("currentStatus" = 'PENDING_REVIEW' AND "currentDecisionVersion" = 0)
    OR ("currentStatus" <> 'PENDING_REVIEW' AND "currentDecisionVersion" >= 1)
  ),
  CONSTRAINT "template_twin_static_assets_practiceId_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_static_assets_createdById_fkey" FOREIGN KEY ("createdById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_static_assets_practiceId_sha256_key"
  ON "template_twin_static_assets"("practiceId", "sha256");
CREATE INDEX "template_twin_static_assets_practiceId_currentStatus_update_idx"
  ON "template_twin_static_assets"("practiceId", "currentStatus", "updatedAt");

CREATE TABLE "template_twin_static_asset_review_receipts" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "reviewedById" TEXT NOT NULL,
  "tokenSha256" CHAR(64) NOT NULL,
  "assetSha256" CHAR(64) NOT NULL,
  "inspectionEvidenceSha256" CHAR(64) NOT NULL,
  "scannerVersion" TEXT NOT NULL,
  "ocrEngineVersion" TEXT NOT NULL,
  "privacyEvidenceSha256" CHAR(64) NOT NULL,
  "globalRolloutGeneration" BIGINT NOT NULL,
  "practiceRolloutGeneration" BIGINT NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  "consumedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_static_asset_review_receipts_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_static_asset_review_receipt_hashes" CHECK (
    "tokenSha256" ~ '^[a-f0-9]{64}$'
    AND "assetSha256" ~ '^[a-f0-9]{64}$'
    AND "inspectionEvidenceSha256" ~ '^[a-f0-9]{64}$'
    AND "privacyEvidenceSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_static_asset_review_receipt_generations" CHECK (
    "globalRolloutGeneration" >= 1 AND "practiceRolloutGeneration" >= 1
  ),
  CONSTRAINT "template_twin_static_asset_review_receipt_window" CHECK (
    "expiresAt" > "createdAt"
    AND ("consumedAt" IS NULL OR "consumedAt" >= "createdAt")
  ),
  CONSTRAINT "template_twin_static_asset_review_receipts_practiceId_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_static_asset_review_receipts_reviewedById_fkey" FOREIGN KEY ("reviewedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_static_asset_review_receipts_tokenSha256_key"
  ON "template_twin_static_asset_review_receipts"("tokenSha256");
CREATE INDEX "tt_static_asset_receipt_practice_reviewer_expiry_idx"
  ON "template_twin_static_asset_review_receipts"("practiceId", "reviewedById", "expiresAt");
CREATE INDEX "tt_static_asset_receipt_unconsumed_expiry_idx"
  ON "template_twin_static_asset_review_receipts"("expiresAt") WHERE "consumedAt" IS NULL;

CREATE TABLE "template_twin_static_asset_decisions" (
  "id" TEXT NOT NULL,
  "assetId" TEXT NOT NULL,
  "version" INTEGER NOT NULL,
  "decision" TEXT NOT NULL,
  "reason" TEXT NOT NULL,
  "attestedReusableBlankAsset" BOOLEAN NOT NULL DEFAULT false,
  "inspectionEvidenceSha256" CHAR(64) NOT NULL,
  "reviewReceiptId" TEXT,
  "auditEventKey" TEXT NOT NULL,
  "decidedById" TEXT NOT NULL,
  "decidedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_static_asset_decisions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_static_asset_decision_version_positive" CHECK ("version" >= 1),
  CONSTRAINT "template_twin_static_asset_decision_kind" CHECK (
    "decision" IN ('APPROVED', 'REJECTED', 'REVOKED')
  ),
  CONSTRAINT "template_twin_static_asset_approval_attestation" CHECK (
    ("decision" = 'APPROVED' AND "attestedReusableBlankAsset" = true AND "reviewReceiptId" IS NOT NULL)
    OR ("decision" <> 'APPROVED' AND "attestedReusableBlankAsset" = false AND "reviewReceiptId" IS NULL)
  ),
  CONSTRAINT "template_twin_static_asset_decision_reason" CHECK (
    char_length(btrim("reason")) BETWEEN 8 AND 1000
  ),
  CONSTRAINT "template_twin_static_asset_decision_evidence_sha256" CHECK (
    "inspectionEvidenceSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_static_asset_decisions_assetId_fkey" FOREIGN KEY ("assetId")
    REFERENCES "template_twin_static_assets"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_static_asset_decisions_decidedById_fkey" FOREIGN KEY ("decidedById")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_static_asset_decisions_reviewReceiptId_fkey" FOREIGN KEY ("reviewReceiptId")
    REFERENCES "template_twin_static_asset_review_receipts"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_static_asset_decisions_auditEventKey_fkey" FOREIGN KEY ("auditEventKey")
    REFERENCES "template_twin_audit_outbox"("eventKey") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "template_twin_static_asset_decisions_assetId_version_key"
  ON "template_twin_static_asset_decisions"("assetId", "version");
CREATE INDEX "template_twin_static_asset_decisions_assetId_decidedAt_idx"
  ON "template_twin_static_asset_decisions"("assetId", "decidedAt");
CREATE INDEX "template_twin_static_asset_decisions_decidedById_decidedAt_idx"
  ON "template_twin_static_asset_decisions"("decidedById", "decidedAt");
CREATE UNIQUE INDEX "template_twin_static_asset_decisions_reviewReceiptId_key"
  ON "template_twin_static_asset_decisions"("reviewReceiptId");
CREATE UNIQUE INDEX "template_twin_static_asset_decisions_auditEventKey_key"
  ON "template_twin_static_asset_decisions"("auditEventKey");

CREATE OR REPLACE FUNCTION template_twin_assert_field_intent_append_only()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  physician_valid BOOLEAN;
BEGIN
  IF NEW."version" <> 1 OR EXISTS (
    SELECT 1
    FROM "template_twin_field_intent_decisions" d
    WHERE d."fieldDefinitionId" = NEW."fieldDefinitionId"
  ) THEN
    RAISE EXCEPTION 'TT_FIELD_INTENT_NEW_TEMPLATE_VERSION_REQUIRED' USING ERRCODE = '23514';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM "template_twin_field_definitions" f
    JOIN "template_twin_compiled_versions" c ON c."id" = f."compiledVersionId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    WHERE f."id" = NEW."fieldDefinitionId"
      AND (
        n."status" <> 'draft'
        OR c."certificationStatus" NOT IN ('RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED')
        OR EXISTS (
          SELECT 1
          FROM "template_twin_certifications" cert
          WHERE cert."compiledVersionId" = c."id"
        )
      )
  ) THEN
    RAISE EXCEPTION 'TT_FIELD_INTENT_NEW_TEMPLATE_VERSION_REQUIRED' USING ERRCODE = '23514';
  END IF;
  SELECT EXISTS (
    SELECT 1
    FROM "template_twin_field_definitions" f
    JOIN "template_twin_compiled_versions" c ON c."id" = f."compiledVersionId"
    JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
    JOIN "note_templates" n ON n."id" = c."noteTemplateId"
    JOIN "users" u ON u."id" = NEW."decidedById"
    WHERE f."id" = NEW."fieldDefinitionId"
      AND n."doctorId" = NEW."decidedById"
      AND u."practiceId" = s."practiceId"
      AND u."role" = 'DOCTOR'
      AND u."isActive" = true
      AND n."status" = 'draft'
      AND c."certificationStatus" IN ('RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED')
      AND NOT EXISTS (
        SELECT 1
        FROM "template_twin_certifications" cert
        WHERE cert."compiledVersionId" = c."id"
      )
  ) INTO physician_valid;
  IF NOT physician_valid THEN
    RAISE EXCEPTION 'TT_FIELD_INTENT_PHYSICIAN_TENANT_INVALID' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_field_intent_history_guard"
BEFORE INSERT ON "template_twin_field_intent_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_field_intent_append_only();

CREATE OR REPLACE FUNCTION template_twin_reject_append_only_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'TEMPLATE_TWIN_APPEND_ONLY_RECORD' USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER "template_twin_field_intent_immutable"
BEFORE UPDATE OR DELETE ON "template_twin_field_intent_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_append_only_mutation();

CREATE OR REPLACE FUNCTION template_twin_guard_custom_example_execution()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW."acknowledgedById" IS NOT NULL OR NEW."acknowledgedAt" IS NOT NULL THEN
      RAISE EXCEPTION 'TT_CUSTOM_EXAMPLE_ACK_MUST_BE_SEPARATE' USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
      SELECT 1
      FROM "template_twin_field_definitions" f
      JOIN "template_twin_compiled_versions" c ON c."id" = f."compiledVersionId"
      JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
      JOIN "note_templates" n ON n."id" = c."noteTemplateId"
      JOIN "template_twin_field_intent_decisions" d
        ON d."id" = NEW."fieldIntentDecisionId"
       AND d."fieldDefinitionId" = f."id"
      JOIN "users" u ON u."id" = NEW."executedById"
      WHERE f."id" = NEW."fieldDefinitionId"
        AND f."compiledVersionId" = NEW."compiledVersionId"
        AND f."fieldId" = NEW."fieldId"
        AND d."intentKind" = 'CUSTOM_CONCEPT'
        AND d."customConceptId" = NEW."conceptId"
        AND s."practiceId" = NEW."practiceId"
        AND n."doctorId" = NEW."executedById"
        AND n."status" = 'draft'
        AND c."certificationStatus" IN ('RECOGNIZED', 'NEEDS_CONFIRMATION', 'UNSUPPORTED')
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_certifications" cert
          WHERE cert."compiledVersionId" = c."id"
        )
        AND u."practiceId" = NEW."practiceId"
        AND u."role" = 'DOCTOR'
        AND u."isActive" = true
    ) THEN
      RAISE EXCEPTION 'TT_CUSTOM_EXAMPLE_PHYSICIAN_TENANT_INVALID' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_CUSTOM_EXAMPLE_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  IF (to_jsonb(NEW) - 'acknowledgedById' - 'acknowledgedAt') IS DISTINCT FROM
     (to_jsonb(OLD) - 'acknowledgedById' - 'acknowledgedAt')
     OR OLD."acknowledgedAt" IS NOT NULL
     OR NEW."acknowledgedAt" IS NULL
     OR NEW."acknowledgedById" <> OLD."executedById"
  THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_CUSTOM_EXAMPLE_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_custom_example_execution_guard"
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_custom_example_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_custom_example_execution();

CREATE OR REPLACE FUNCTION template_twin_require_custom_example_proof()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  has_custom_fields BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM "template_twin_field_definitions" f
    JOIN "template_twin_field_intent_decisions" d
      ON d."fieldDefinitionId" = f."id"
    WHERE f."compiledVersionId" = NEW."compiledVersionId"
      AND d."intentKind" = 'CUSTOM_CONCEPT'
  ) INTO has_custom_fields;
  IF has_custom_fields AND NEW."approvedCustomExampleProofSha256" IS NULL THEN
    RAISE EXCEPTION 'TT_CUSTOM_EXAMPLE_PROOF_REQUIRED' USING ERRCODE = '23514';
  END IF;
  IF NOT has_custom_fields AND NEW."approvedCustomExampleProofSha256" IS NOT NULL THEN
    RAISE EXCEPTION 'TT_CUSTOM_EXAMPLE_PROOF_UNEXPECTED' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_certification_custom_example_proof_guard"
BEFORE INSERT ON "template_twin_certifications"
FOR EACH ROW EXECUTE FUNCTION template_twin_require_custom_example_proof();

CREATE OR REPLACE FUNCTION template_twin_guard_static_asset_identity()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  IF ROW(
    NEW."practiceId", NEW."sha256", NEW."mimeType", NEW."width", NEW."height",
    NEW."sizeBytes", NEW."scannerVersion", NEW."ocrEngineVersion",
    NEW."ocrTextSha256", NEW."metadataEvidenceSha256", NEW."privacyEvidenceSha256",
    NEW."privacyScanProvider", NEW."privacyScanModel", NEW."inspectionEvidenceSha256",
    NEW."inspectionEvidence", NEW."createdById", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."sha256", OLD."mimeType", OLD."width", OLD."height",
    OLD."sizeBytes", OLD."scannerVersion", OLD."ocrEngineVersion",
    OLD."ocrTextSha256", OLD."metadataEvidenceSha256", OLD."privacyEvidenceSha256",
    OLD."privacyScanProvider", OLD."privacyScanModel", OLD."inspectionEvidenceSha256",
    OLD."inspectionEvidence", OLD."createdById", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  IF pg_trigger_depth() < 2 AND ROW(
    NEW."currentStatus", NEW."currentDecisionVersion", NEW."updatedAt"
  ) IS DISTINCT FROM ROW(
    OLD."currentStatus", OLD."currentDecisionVersion", OLD."updatedAt"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_SUMMARY_MANAGED' USING ERRCODE = '55000';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_static_asset_identity_immutable"
BEFORE UPDATE OR DELETE ON "template_twin_static_assets"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_static_asset_identity();

CREATE OR REPLACE FUNCTION template_twin_validate_static_asset_creator()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM "users" u
    WHERE u."id" = NEW."createdById"
      AND u."practiceId" = NEW."practiceId"
      AND u."role" IN ('ADMIN', 'SUPER_ADMIN')
      AND u."isActive" = true
  ) THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_ADMIN_TENANT_INVALID' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_static_asset_creator_tenant_guard"
BEFORE INSERT ON "template_twin_static_assets"
FOR EACH ROW EXECUTE FUNCTION template_twin_validate_static_asset_creator();

CREATE OR REPLACE FUNCTION template_twin_guard_static_asset_review_receipt()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  global_enabled BOOLEAN;
  global_generation BIGINT;
  practice_enabled BOOLEAN;
  practice_generation BIGINT;
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW."consumedAt" IS NOT NULL
       OR NEW."createdAt" > CURRENT_TIMESTAMP
       OR NEW."expiresAt" <= CURRENT_TIMESTAMP
       OR NEW."expiresAt" > CURRENT_TIMESTAMP + INTERVAL '15 minutes'
    THEN
      RAISE EXCEPTION 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID' USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM "users" u
      WHERE u."id" = NEW."reviewedById"
        AND u."practiceId" = NEW."practiceId"
        AND u."role" IN ('ADMIN', 'SUPER_ADMIN')
        AND u."isActive" = true
    ) THEN
      RAISE EXCEPTION 'TT_STATIC_ASSET_ADMIN_TENANT_INVALID' USING ERRCODE = '23514';
    END IF;
    SELECT "enabled", "generation"
      INTO global_enabled, global_generation
      FROM "template_twin_rollout_controls"
      WHERE "id" = 'global'
      FOR SHARE;
    SELECT "templateTwinEnabled", "templateTwinRolloutGeneration"
      INTO practice_enabled, practice_generation
      FROM "practices"
      WHERE "id" = NEW."practiceId"
      FOR SHARE;
    IF NOT FOUND OR global_enabled IS DISTINCT FROM true
       OR practice_enabled IS DISTINCT FROM true
       OR NEW."globalRolloutGeneration" <> global_generation
       OR NEW."practiceRolloutGeneration" <> practice_generation
    THEN
      RAISE EXCEPTION 'TT_STATIC_ASSET_ROLLOUT_STALE' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_REVIEW_RECEIPT_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  IF ROW(
    NEW."practiceId", NEW."reviewedById", NEW."tokenSha256", NEW."assetSha256",
    NEW."inspectionEvidenceSha256", NEW."scannerVersion", NEW."ocrEngineVersion",
    NEW."privacyEvidenceSha256", NEW."globalRolloutGeneration",
    NEW."practiceRolloutGeneration", NEW."createdAt", NEW."expiresAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."reviewedById", OLD."tokenSha256", OLD."assetSha256",
    OLD."inspectionEvidenceSha256", OLD."scannerVersion", OLD."ocrEngineVersion",
    OLD."privacyEvidenceSha256", OLD."globalRolloutGeneration",
    OLD."practiceRolloutGeneration", OLD."createdAt", OLD."expiresAt"
  ) OR OLD."consumedAt" IS NOT NULL
    OR NEW."consumedAt" IS NULL
    OR OLD."expiresAt" <= CURRENT_TIMESTAMP
    OR NEW."consumedAt" IS DISTINCT FROM CURRENT_TIMESTAMP
    OR NEW."consumedAt" > OLD."expiresAt"
  THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_REVIEW_RECEIPT_IMMUTABLE' USING ERRCODE = '55000';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_static_asset_review_receipt_guard"
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_static_asset_review_receipts"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_static_asset_review_receipt();

CREATE OR REPLACE FUNCTION template_twin_apply_static_asset_decision()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  global_enabled BOOLEAN;
  global_generation BIGINT;
  practice_enabled BOOLEAN;
  practice_generation BIGINT;
  asset_status TEXT;
  asset_version INTEGER;
  asset_practice_id TEXT;
  asset_sha256 CHAR(64);
  asset_scanner_version TEXT;
  asset_ocr_engine_version TEXT;
  asset_privacy_evidence_sha256 CHAR(64);
  asset_inspection_evidence_sha256 CHAR(64);
  receipt_practice_id TEXT;
  receipt_reviewed_by_id TEXT;
  receipt_asset_sha256 CHAR(64);
  receipt_inspection_evidence_sha256 CHAR(64);
  receipt_scanner_version TEXT;
  receipt_ocr_engine_version TEXT;
  receipt_privacy_evidence_sha256 CHAR(64);
  receipt_global_generation BIGINT;
  receipt_practice_generation BIGINT;
  receipt_expires_at TIMESTAMPTZ;
  receipt_consumed_at TIMESTAMPTZ;
  expected_audit_action TEXT;
  expected_audit_event_key TEXT;
BEGIN
  SELECT "practiceId" INTO asset_practice_id
    FROM "template_twin_static_assets" WHERE "id" = NEW."assetId";
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_DECISION_CONFLICT' USING ERRCODE = '23503';
  END IF;

  -- Load-bearing lock order: global rollout, practice rollout, receipt, asset.
  SELECT "enabled", "generation" INTO global_enabled, global_generation
    FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
    FOR UPDATE;
  SELECT "templateTwinEnabled", "templateTwinRolloutGeneration"
    INTO practice_enabled, practice_generation
    FROM "practices"
    WHERE "id" = asset_practice_id
    FOR UPDATE;
  IF NOT FOUND OR global_enabled IS DISTINCT FROM true
     OR practice_enabled IS DISTINCT FROM true
  THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_ROLLOUT_STALE' USING ERRCODE = '23514';
  END IF;

  CASE NEW."decision"
    WHEN 'APPROVED' THEN
      expected_audit_action := 'TEMPLATE_TWIN_STATIC_ASSET_APPROVED';
      expected_audit_event_key := 'template-twin:static-asset-approved:' || NEW."id";
    WHEN 'REJECTED' THEN
      expected_audit_action := 'TEMPLATE_TWIN_STATIC_ASSET_REJECTED';
      expected_audit_event_key := 'template-twin:static-asset-rejected:' || NEW."id";
    WHEN 'REVOKED' THEN
      expected_audit_action := 'TEMPLATE_TWIN_STATIC_ASSET_REVOKED';
      expected_audit_event_key := 'template-twin:static-asset-revoked:' || NEW."id";
    ELSE
      RAISE EXCEPTION 'TT_STATIC_ASSET_DECISION_CONFLICT' USING ERRCODE = '23514';
  END CASE;
  IF NEW."auditEventKey" IS DISTINCT FROM expected_audit_event_key OR NOT EXISTS (
    SELECT 1
    FROM "template_twin_audit_outbox" outbox
    WHERE outbox."eventKey" = NEW."auditEventKey"
      AND outbox."practiceId" = asset_practice_id
      AND outbox."actorId" = NEW."decidedById"
      AND outbox."action"::text = expected_audit_action
      AND outbox."targetType" = 'TemplateTwinStaticAsset'
      AND outbox."targetId" = NEW."assetId"
      AND outbox."metadata"->>'decisionId' = NEW."id"
      AND outbox."status" = 'PENDING'
      AND outbox."attemptCount" = 0
      AND outbox."deliveredAt" IS NULL
  ) THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID' USING ERRCODE = '23514';
  END IF;

  IF NEW."decision" = 'APPROVED' THEN
    SELECT receipt."practiceId", receipt."reviewedById", receipt."assetSha256",
           receipt."inspectionEvidenceSha256", receipt."scannerVersion",
           receipt."ocrEngineVersion", receipt."privacyEvidenceSha256",
           receipt."globalRolloutGeneration", receipt."practiceRolloutGeneration",
           receipt."expiresAt", receipt."consumedAt"
      INTO receipt_practice_id, receipt_reviewed_by_id, receipt_asset_sha256,
           receipt_inspection_evidence_sha256, receipt_scanner_version,
           receipt_ocr_engine_version, receipt_privacy_evidence_sha256,
           receipt_global_generation, receipt_practice_generation,
           receipt_expires_at, receipt_consumed_at
      FROM "template_twin_static_asset_review_receipts" receipt
      WHERE receipt."id" = NEW."reviewReceiptId"
      FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID' USING ERRCODE = '23514';
    END IF;
  END IF;

  SELECT "currentStatus", "currentDecisionVersion", "practiceId", "sha256",
         "scannerVersion", "ocrEngineVersion", "privacyEvidenceSha256",
         "inspectionEvidenceSha256"
    INTO asset_status, asset_version, asset_practice_id, asset_sha256,
         asset_scanner_version, asset_ocr_engine_version,
         asset_privacy_evidence_sha256, asset_inspection_evidence_sha256
    FROM "template_twin_static_assets"
    WHERE "id" = NEW."assetId"
    FOR UPDATE;
  IF NOT FOUND OR NEW."version" <> asset_version + 1 THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_DECISION_CONFLICT' USING ERRCODE = '40001';
  END IF;
  IF NEW."inspectionEvidenceSha256" <> asset_inspection_evidence_sha256 THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_EVIDENCE_MISMATCH' USING ERRCODE = '23514';
  END IF;
  IF NEW."decision" = 'APPROVED' AND (
    receipt_practice_id IS DISTINCT FROM asset_practice_id
    OR receipt_reviewed_by_id IS DISTINCT FROM NEW."decidedById"
    OR receipt_asset_sha256 IS DISTINCT FROM asset_sha256
    OR receipt_inspection_evidence_sha256 IS DISTINCT FROM asset_inspection_evidence_sha256
    OR receipt_inspection_evidence_sha256 IS DISTINCT FROM NEW."inspectionEvidenceSha256"
    OR receipt_scanner_version IS DISTINCT FROM asset_scanner_version
    OR receipt_ocr_engine_version IS DISTINCT FROM asset_ocr_engine_version
    OR receipt_privacy_evidence_sha256 IS DISTINCT FROM asset_privacy_evidence_sha256
    OR receipt_global_generation IS DISTINCT FROM global_generation
    OR receipt_practice_generation IS DISTINCT FROM practice_generation
    OR receipt_consumed_at IS NULL
    OR receipt_consumed_at > receipt_expires_at
    OR receipt_consumed_at > NEW."decidedAt"
  ) THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID' USING ERRCODE = '23514';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM "users" u
    WHERE u."id" = NEW."decidedById"
      AND u."practiceId" = asset_practice_id
      AND u."role" IN ('ADMIN', 'SUPER_ADMIN')
      AND u."isActive" = true
  ) THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_ADMIN_TENANT_INVALID' USING ERRCODE = '23514';
  END IF;
  IF NEW."decision" = 'REVOKED' AND asset_status <> 'APPROVED' THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_NOT_APPROVED' USING ERRCODE = '23514';
  END IF;
  IF NEW."decision" = 'REJECTED' AND asset_status <> 'PENDING_REVIEW' THEN
    RAISE EXCEPTION 'TT_STATIC_ASSET_DECISION_CONFLICT' USING ERRCODE = '23514';
  END IF;
  UPDATE "template_twin_static_assets"
    SET "currentStatus" = NEW."decision",
        "currentDecisionVersion" = NEW."version",
        "updatedAt" = NEW."decidedAt"
    WHERE "id" = NEW."assetId";
  RETURN NEW;
END;
$$;

CREATE TRIGGER "template_twin_static_asset_decision_applies"
BEFORE INSERT ON "template_twin_static_asset_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_apply_static_asset_decision();

CREATE TRIGGER "template_twin_static_asset_decision_immutable"
BEFORE UPDATE OR DELETE ON "template_twin_static_asset_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_append_only_mutation();

COMMIT;
