-- Durable visit-automation completion proof.
--
-- This is an additive, bounded migration: it creates empty tables, metadata,
-- and triggers only. It deliberately does not scan or update historical
-- transcribe_visits. A historical visit with no manifest is LEGACY_UNKNOWN
-- and must be reprocessed before a new READY/SIGNED/export claim.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VISIT_AUTOMATION_COMPLETED';

CREATE TYPE "VisitAutomationManifestStatus" AS ENUM (
  'PENDING', 'RUNNING', 'INCOMPLETE', 'COMPLETE', 'FAILED'
);

CREATE TYPE "VisitAutomationLayerStatus" AS ENUM (
  'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'NOT_APPLICABLE'
);

CREATE TYPE "VisitAutomationLayerRequirement" AS ENUM (
  'REQUIRED', 'OPTIONAL', 'NOT_APPLICABLE'
);

CREATE TABLE "visit_automation_manifests" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "stagingAdmissionId" TEXT,
  "stagingRunId" TEXT,
  "soapVersion" INTEGER NOT NULL,
  "soapSha256" CHAR(64) NOT NULL,
  "sourceVersion" VARCHAR(80) NOT NULL,
  "sourceSha256" CHAR(64) NOT NULL,
  "policyVersion" VARCHAR(80) NOT NULL,
  "manifestVersion" INTEGER NOT NULL DEFAULT 1,
  "status" "VisitAutomationManifestStatus" NOT NULL DEFAULT 'PENDING',
  "attemptCount" INTEGER NOT NULL DEFAULT 1,
  "pinnedGlobalRolloutGeneration" BIGINT,
  "pinnedPracticeRolloutGeneration" BIGINT,
  "startedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "visit_automation_manifests_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "visit_automation_manifest_attempt_check"
    CHECK ("attemptCount" > 0 AND "manifestVersion" > 0),
  CONSTRAINT "visit_automation_manifest_hash_check"
    CHECK (
      "soapSha256" ~ '^[a-f0-9]{64}$'
      AND "sourceSha256" ~ '^[a-f0-9]{64}$'
    ),
  CONSTRAINT "visit_automation_manifest_staging_pair_check"
    CHECK (("stagingAdmissionId" IS NULL) = ("stagingRunId" IS NULL)),
  CONSTRAINT "visit_automation_manifest_rollout_pair_check"
    CHECK (
      ("stagingRunId" IS NULL
        AND "pinnedGlobalRolloutGeneration" IS NULL
        AND "pinnedPracticeRolloutGeneration" IS NULL)
      OR
      ("stagingRunId" IS NOT NULL
        AND "pinnedGlobalRolloutGeneration" IS NOT NULL
        AND "pinnedPracticeRolloutGeneration" IS NOT NULL)
    ),
  CONSTRAINT "visit_automation_manifest_completion_time_check"
    CHECK (
      ("status" IN ('PENDING', 'RUNNING') AND "completedAt" IS NULL)
      OR
      ("status" IN ('INCOMPLETE', 'COMPLETE', 'FAILED') AND "completedAt" IS NOT NULL)
    ),
  CONSTRAINT "visit_automation_manifest_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_manifest_visit_fkey"
    FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_manifest_admission_fkey"
    FOREIGN KEY ("stagingAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_manifest_run_fkey"
    FOREIGN KEY ("stagingRunId") REFERENCES "template_twin_synthetic_qa_runs"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "visit_automation_manifest_visit_key"
  ON "visit_automation_manifests"("visitId");
CREATE UNIQUE INDEX "visit_automation_manifest_admission_key"
  ON "visit_automation_manifests"("stagingAdmissionId");
CREATE UNIQUE INDEX "visit_automation_manifest_run_key"
  ON "visit_automation_manifests"("stagingRunId");
CREATE UNIQUE INDEX "visit_automation_manifest_tenant_identity_key"
  ON "visit_automation_manifests"("id", "practiceId", "visitId");
CREATE INDEX "visit_automation_manifest_practice_status_idx"
  ON "visit_automation_manifests"("practiceId", "status", "updatedAt");
CREATE INDEX "visit_automation_manifest_run_status_idx"
  ON "visit_automation_manifests"("stagingRunId", "status");

CREATE TABLE "visit_automation_layers" (
  "id" TEXT NOT NULL,
  "manifestId" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "layerId" VARCHAR(80) NOT NULL,
  "layerVersion" VARCHAR(80) NOT NULL,
  "requirement" "VisitAutomationLayerRequirement" NOT NULL,
  "status" "VisitAutomationLayerStatus" NOT NULL DEFAULT 'PENDING',
  "attemptCount" INTEGER NOT NULL DEFAULT 0,
  "inputSha256" CHAR(64) NOT NULL,
  "outputSha256" CHAR(64),
  "failureCode" VARCHAR(80),
  "idempotencyKey" CHAR(64) NOT NULL,
  "startedAt" TIMESTAMPTZ(6),
  "completedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "visit_automation_layers_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "visit_automation_layer_attempt_check" CHECK ("attemptCount" >= 0),
  CONSTRAINT "visit_automation_layer_hash_check"
    CHECK (
      "inputSha256" ~ '^[a-f0-9]{64}$'
      AND ("outputSha256" IS NULL OR "outputSha256" ~ '^[a-f0-9]{64}$')
      AND "idempotencyKey" ~ '^[a-f0-9]{64}$'
    ),
  CONSTRAINT "visit_automation_layer_failure_code_check"
    CHECK (
      "failureCode" IS NULL
      OR "failureCode" ~ '^[A-Z0-9_]{1,80}$'
    ),
  CONSTRAINT "visit_automation_layer_not_applicable_check"
    CHECK (
      ("requirement" = 'NOT_APPLICABLE' AND "status" = 'NOT_APPLICABLE')
      OR
      ("requirement" <> 'NOT_APPLICABLE' AND "status" <> 'NOT_APPLICABLE')
    ),
  CONSTRAINT "visit_automation_layer_terminal_shape_check"
    CHECK (
      ("status" = 'PENDING'
        AND "outputSha256" IS NULL AND "failureCode" IS NULL
        AND "startedAt" IS NULL AND "completedAt" IS NULL)
      OR
      ("status" = 'RUNNING'
        AND "attemptCount" > 0 AND "outputSha256" IS NULL
        AND "failureCode" IS NULL AND "startedAt" IS NOT NULL
        AND "completedAt" IS NULL)
      OR
      ("status" = 'SUCCEEDED'
        AND "attemptCount" > 0 AND "outputSha256" IS NOT NULL
        AND "failureCode" IS NULL AND "startedAt" IS NOT NULL
        AND "completedAt" IS NOT NULL)
      OR
      ("status" = 'FAILED'
        AND "attemptCount" > 0 AND "outputSha256" IS NULL
        AND "failureCode" IS NOT NULL AND "startedAt" IS NOT NULL
        AND "completedAt" IS NOT NULL)
      OR
      ("status" = 'NOT_APPLICABLE'
        AND "attemptCount" = 0 AND "outputSha256" IS NULL
        AND "failureCode" IS NULL AND "startedAt" IS NULL
        AND "completedAt" IS NOT NULL)
    ),
  CONSTRAINT "visit_automation_layer_manifest_tenant_fkey"
    FOREIGN KEY ("manifestId", "practiceId", "visitId")
    REFERENCES "visit_automation_manifests"("id", "practiceId", "visitId")
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "visit_automation_layer_idempotency_key"
  ON "visit_automation_layers"("idempotencyKey");
CREATE UNIQUE INDEX "visit_automation_layer_manifest_layer_key"
  ON "visit_automation_layers"("manifestId", "layerId");
CREATE INDEX "visit_automation_layer_tenant_visit_status_idx"
  ON "visit_automation_layers"("practiceId", "visitId", "status");
CREATE INDEX "visit_automation_layer_completion_idx"
  ON "visit_automation_layers"("manifestId", "requirement", "status");

CREATE OR REPLACE FUNCTION visit_automation_assert_manifest_lineage()
RETURNS trigger AS $$
DECLARE
  visit_practice_id TEXT;
  visit_user_id TEXT;
  run_row RECORD;
BEGIN
  SELECT u."practiceId", v."userId"
  INTO visit_practice_id, visit_user_id
  FROM "transcribe_visits" v
  JOIN "users" u ON u."id" = v."userId"
  WHERE v."id" = NEW."visitId";

  IF visit_practice_id IS NULL
    OR visit_practice_id <> NEW."practiceId" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_TENANT_MISMATCH' USING ERRCODE = '23514';
  END IF;

  IF NEW."stagingRunId" IS NOT NULL THEN
    SELECT
      r."practiceId", r."doctorId", r."visitId", r."admissionId",
      r."pinnedGlobalRolloutGeneration", r."pinnedPracticeRolloutGeneration",
      a."practiceId" AS admission_practice_id,
      a."actorId" AS admission_actor_id,
      a."visitId" AS admission_visit_id
    INTO run_row
    FROM "template_twin_synthetic_qa_runs" r
    JOIN "template_twin_synthetic_qa_admissions" a
      ON a."id" = r."admissionId"
    WHERE r."id" = NEW."stagingRunId"
      AND a."id" = NEW."stagingAdmissionId";

    IF run_row IS NULL
      OR run_row."practiceId" <> NEW."practiceId"
      OR run_row.admission_practice_id <> NEW."practiceId"
      OR run_row."doctorId" <> visit_user_id
      OR run_row.admission_actor_id <> visit_user_id
      OR run_row."visitId" <> NEW."visitId"
      OR run_row.admission_visit_id <> NEW."visitId"
      OR run_row."admissionId" <> NEW."stagingAdmissionId"
      OR run_row."pinnedGlobalRolloutGeneration" <> NEW."pinnedGlobalRolloutGeneration"
      OR run_row."pinnedPracticeRolloutGeneration" <> NEW."pinnedPracticeRolloutGeneration" THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_STAGING_LINEAGE_MISMATCH'
        USING ERRCODE = '23514';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_manifest_lineage_guard
BEFORE INSERT OR UPDATE ON "visit_automation_manifests"
FOR EACH ROW EXECUTE FUNCTION visit_automation_assert_manifest_lineage();

CREATE OR REPLACE FUNCTION visit_automation_guard_manifest_transition()
RETURNS trigger AS $$
DECLARE
  binding_changed BOOLEAN;
  complete_reprocess BOOLEAN;
BEGIN
  IF OLD."practiceId" <> NEW."practiceId"
    OR OLD."visitId" <> NEW."visitId"
    OR OLD."stagingAdmissionId" IS DISTINCT FROM NEW."stagingAdmissionId"
    OR OLD."stagingRunId" IS DISTINCT FROM NEW."stagingRunId"
    OR OLD."pinnedGlobalRolloutGeneration" IS DISTINCT FROM NEW."pinnedGlobalRolloutGeneration"
    OR OLD."pinnedPracticeRolloutGeneration" IS DISTINCT FROM NEW."pinnedPracticeRolloutGeneration" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_LINEAGE_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;

  binding_changed :=
    OLD."soapVersion" IS DISTINCT FROM NEW."soapVersion"
    OR OLD."soapSha256" IS DISTINCT FROM NEW."soapSha256"
    OR OLD."sourceVersion" IS DISTINCT FROM NEW."sourceVersion"
    OR OLD."sourceSha256" IS DISTINCT FROM NEW."sourceSha256"
    OR OLD."policyVersion" IS DISTINCT FROM NEW."policyVersion";

  complete_reprocess :=
    OLD."status" = 'COMPLETE'
    AND NEW."status" = 'RUNNING'
    AND NEW."manifestVersion" = OLD."manifestVersion" + 1
    AND NEW."completedAt" IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = OLD."id"
    )
    AND EXISTS (
      SELECT 1
      FROM "transcribe_visits" visit
      WHERE visit."id" = NEW."visitId"
        AND visit."status" = 'AUTOMATING'
        AND visit."signedAt" IS NULL
        AND visit."soapVersion" = NEW."soapVersion"
    );

  IF OLD."status" = 'COMPLETE' AND NOT complete_reprocess THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_COMPLETE_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;

  IF binding_changed AND (
    NEW."status" <> 'RUNNING'
    OR NEW."manifestVersion" <> OLD."manifestVersion" + 1
    OR NEW."completedAt" IS NOT NULL
    OR EXISTS (
      SELECT 1 FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = OLD."id"
    )
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_REBIND_INVALID'
      USING ERRCODE = '23514';
  END IF;

  IF NOT binding_changed
    AND NOT complete_reprocess
    AND NEW."manifestVersion" <> OLD."manifestVersion" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_VERSION_INVALID'
      USING ERRCODE = '23514';
  END IF;

  IF NEW."attemptCount" < OLD."attemptCount" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_ATTEMPT_INVALID'
      USING ERRCODE = '23514';
  END IF;

  IF OLD."status" IS DISTINCT FROM NEW."status" AND NOT (
    (OLD."status" = 'PENDING' AND NEW."status" IN ('RUNNING', 'FAILED'))
    OR (OLD."status" = 'RUNNING' AND NEW."status" IN ('INCOMPLETE', 'COMPLETE', 'FAILED'))
    OR (OLD."status" = 'INCOMPLETE' AND NEW."status" IN ('RUNNING', 'FAILED'))
    OR (OLD."status" = 'FAILED' AND NEW."status" = 'RUNNING')
    OR (OLD."status" = 'COMPLETE' AND complete_reprocess)
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_MANIFEST_TRANSITION_INVALID'
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_manifest_transition_guard
BEFORE UPDATE ON "visit_automation_manifests"
FOR EACH ROW EXECUTE FUNCTION visit_automation_guard_manifest_transition();

CREATE OR REPLACE FUNCTION visit_automation_guard_layer_transition()
RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "visit_automation_manifests" manifest
    WHERE manifest."id" = OLD."manifestId"
      AND manifest."status" = 'COMPLETE'
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_COMPLETE_LAYER_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;

  IF OLD."manifestId" <> NEW."manifestId"
    OR OLD."practiceId" <> NEW."practiceId"
    OR OLD."visitId" <> NEW."visitId"
    OR OLD."layerId" <> NEW."layerId"
    OR OLD."layerVersion" <> NEW."layerVersion"
    OR OLD."requirement" <> NEW."requirement"
    OR OLD."inputSha256" <> NEW."inputSha256"
    OR OLD."idempotencyKey" <> NEW."idempotencyKey" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_LAYER_IDENTITY_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;

  IF OLD."status" = NEW."status" AND (
    OLD."attemptCount" IS DISTINCT FROM NEW."attemptCount"
    OR OLD."outputSha256" IS DISTINCT FROM NEW."outputSha256"
    OR OLD."failureCode" IS DISTINCT FROM NEW."failureCode"
    OR OLD."startedAt" IS DISTINCT FROM NEW."startedAt"
    OR OLD."completedAt" IS DISTINCT FROM NEW."completedAt"
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_LAYER_RESULT_IMMUTABLE'
      USING ERRCODE = '23514';
  ELSIF OLD."status" = NEW."status" THEN
    RETURN NEW;
  END IF;
  IF NOT (
    (OLD."status" = 'PENDING' AND NEW."status" IN ('RUNNING', 'FAILED'))
    OR (OLD."status" = 'RUNNING' AND NEW."status" IN ('SUCCEEDED', 'FAILED'))
    OR (OLD."status" = 'FAILED' AND NEW."status" = 'RUNNING')
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_LAYER_TRANSITION_INVALID'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_layer_transition_guard
BEFORE UPDATE ON "visit_automation_layers"
FOR EACH ROW EXECUTE FUNCTION visit_automation_guard_layer_transition();

CREATE OR REPLACE FUNCTION visit_automation_guard_manifest_completion()
RETURNS trigger AS $$
BEGIN
  IF NEW."status" = 'COMPLETE' AND (
    (SELECT COUNT(*) FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = NEW."id") <> 6
    OR
    (SELECT COUNT(DISTINCT layer."layerId")
      FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = NEW."id") <> 6
    OR EXISTS (
      SELECT 1
      FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = NEW."id"
        AND NOT (
          (layer."layerId" = 'icd_coding' AND layer."layerVersion" = 'l7a-v1')
          OR (layer."layerId" = 'cpt_coding' AND layer."layerVersion" = 'l7b-v1')
          OR (layer."layerId" = 'rx_drafting' AND layer."layerVersion" = 'l7c-v1')
          OR (layer."layerId" = 'referrals' AND layer."layerVersion" = 'l7d-v1')
          OR (layer."layerId" = 'patient_summary' AND layer."layerVersion" = 'l7e-v1')
          OR (layer."layerId" = 'em_mdm_prewarm' AND layer."layerVersion" = 'em-mdm-prewarm-v1')
        )
    )
    OR EXISTS (
      SELECT 1
      FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = NEW."id"
        AND layer."status" IN ('PENDING', 'RUNNING')
    )
    OR EXISTS (
      SELECT 1
      FROM "visit_automation_layers" layer
      WHERE layer."manifestId" = NEW."id"
        AND layer."requirement" = 'REQUIRED'
        AND layer."status" <> 'SUCCEEDED'
    )
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_manifest_completion_guard
BEFORE INSERT OR UPDATE ON "visit_automation_manifests"
FOR EACH ROW EXECUTE FUNCTION visit_automation_guard_manifest_completion();

CREATE OR REPLACE FUNCTION visit_automation_guard_visit_terminal_state()
RETURNS trigger AS $$
DECLARE
  manifest_row RECORD;
BEGIN
  IF NEW."status" IN ('READY', 'SIGNED')
    AND (TG_OP = 'INSERT' OR OLD."status" IS DISTINCT FROM NEW."status") THEN
    SELECT "status", "soapVersion"
    INTO manifest_row
    FROM "visit_automation_manifests"
    WHERE "visitId" = NEW."id";
    IF manifest_row IS NULL
      OR manifest_row."status" <> 'COMPLETE'
      OR manifest_row."soapVersion" <> NEW."soapVersion" THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROOF_REQUIRED'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_terminal_state_guard
BEFORE INSERT OR UPDATE ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION visit_automation_guard_visit_terminal_state();

COMMIT;
