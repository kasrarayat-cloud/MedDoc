-- Durable provider-execution boundary for visit automation.
--
-- Additive only: historical visits and layer rows receive no execution row
-- and are never inferred successful. New work reserves one row before a
-- provider invocation and can reuse a committed result after projection
-- contention without invoking the provider again.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE TYPE "VisitAutomationProviderExecutionStatus" AS ENUM (
  'RESERVED', 'IN_FLIGHT', 'SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME'
);

CREATE UNIQUE INDEX "visit_automation_layer_tenant_identity_key"
  ON "visit_automation_layers"("id", "manifestId", "practiceId", "visitId");

CREATE TABLE "visit_automation_provider_executions" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "manifestId" TEXT NOT NULL,
  "automationLayerId" TEXT NOT NULL,
  "stagingAdmissionId" TEXT,
  "stagingRunId" TEXT,
  "inputSha256" CHAR(64) NOT NULL,
  "provider" VARCHAR(40) NOT NULL,
  "providerMode" VARCHAR(40) NOT NULL,
  "model" VARCHAR(100) NOT NULL,
  "operationVersion" VARCHAR(80) NOT NULL,
  "idempotencyKey" CHAR(64) NOT NULL,
  "status" "VisitAutomationProviderExecutionStatus" NOT NULL DEFAULT 'RESERVED',
  "invocationCount" INTEGER NOT NULL DEFAULT 0,
  "resultPayload" JSONB,
  "resultSha256" CHAR(64),
  "resultVersion" VARCHAR(80),
  "failureCode" VARCHAR(80),
  "reservedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "invokedAt" TIMESTAMPTZ(6),
  "completedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "visit_automation_provider_executions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "visit_automation_provider_execution_hash_check" CHECK (
    "inputSha256" ~ '^[a-f0-9]{64}$'
    AND "idempotencyKey" ~ '^[a-f0-9]{64}$'
    AND ("resultSha256" IS NULL OR "resultSha256" ~ '^[a-f0-9]{64}$')
  ),
  CONSTRAINT "visit_automation_provider_execution_code_check" CHECK (
    "provider" ~ '^[a-z0-9_-]{1,40}$'
    AND "providerMode" IN ('LIVE', 'DETERMINISTIC_MOCK', 'SYNTHETIC_QA')
    AND "model" ~ '^[A-Za-z0-9._:-]{1,100}$'
    AND "operationVersion" ~ '^[A-Za-z0-9._:-]{1,80}$'
    AND ("failureCode" IS NULL OR "failureCode" ~ '^[A-Z0-9_]{1,80}$')
  ),
  CONSTRAINT "visit_automation_provider_execution_staging_pair_check" CHECK (
    ("stagingAdmissionId" IS NULL) = ("stagingRunId" IS NULL)
  ),
  CONSTRAINT "visit_automation_provider_execution_payload_limit_check" CHECK (
    "resultPayload" IS NULL OR octet_length("resultPayload"::text) <= 1048576
  ),
  CONSTRAINT "visit_automation_provider_execution_state_shape_check" CHECK (
    ("status" = 'RESERVED'
      AND "invocationCount" = 0
      AND "invokedAt" IS NULL AND "completedAt" IS NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NULL)
    OR
    ("status" = 'IN_FLIGHT'
      AND "invocationCount" = 1
      AND "invokedAt" IS NOT NULL AND "completedAt" IS NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NULL)
    OR
    ("status" = 'SUCCEEDED'
      AND "invocationCount" = 1
      AND "invokedAt" IS NOT NULL AND "completedAt" IS NOT NULL
      AND "resultPayload" IS NOT NULL AND "resultSha256" IS NOT NULL
      AND "resultVersion" IS NOT NULL AND "failureCode" IS NULL)
    OR
    ("status" IN ('FAILED', 'UNKNOWN_OUTCOME')
      AND "invocationCount" <= 1
      AND "completedAt" IS NOT NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NOT NULL)
  ),
  CONSTRAINT "visit_automation_provider_execution_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_provider_execution_visit_fkey"
    FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_provider_execution_manifest_fkey"
    FOREIGN KEY ("manifestId", "practiceId", "visitId")
    REFERENCES "visit_automation_manifests"("id", "practiceId", "visitId")
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_provider_execution_layer_fkey"
    FOREIGN KEY ("automationLayerId", "manifestId", "practiceId", "visitId")
    REFERENCES "visit_automation_layers"("id", "manifestId", "practiceId", "visitId")
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_provider_execution_admission_fkey"
    FOREIGN KEY ("stagingAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "visit_automation_provider_execution_run_fkey"
    FOREIGN KEY ("stagingRunId") REFERENCES "template_twin_synthetic_qa_runs"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "visit_automation_provider_execution_layer_key"
  ON "visit_automation_provider_executions"(
    "automationLayerId", "manifestId", "practiceId", "visitId"
  );
CREATE UNIQUE INDEX "visit_automation_provider_execution_idempotency_key"
  ON "visit_automation_provider_executions"("idempotencyKey");
CREATE INDEX "visit_automation_provider_execution_tenant_status_idx"
  ON "visit_automation_provider_executions"("practiceId", "visitId", "status");
CREATE INDEX "visit_automation_provider_execution_manifest_status_idx"
  ON "visit_automation_provider_executions"("manifestId", "status");
CREATE INDEX "visit_automation_provider_execution_run_status_idx"
  ON "visit_automation_provider_executions"("stagingRunId", "status");

CREATE OR REPLACE FUNCTION visit_automation_provider_execution_assert_lineage()
RETURNS trigger AS $$
DECLARE
  layer_row RECORD;
  run_row RECORD;
BEGIN
  SELECT
    l."manifestId", l."practiceId", l."visitId", l."inputSha256",
    m."stagingAdmissionId", m."stagingRunId"
  INTO layer_row
  FROM "visit_automation_layers" l
  JOIN "visit_automation_manifests" m ON m."id" = l."manifestId"
  WHERE l."id" = NEW."automationLayerId";

  IF layer_row IS NULL
    OR layer_row."manifestId" <> NEW."manifestId"
    OR layer_row."practiceId" <> NEW."practiceId"
    OR layer_row."visitId" <> NEW."visitId"
    OR layer_row."inputSha256" <> NEW."inputSha256"
    OR layer_row."stagingAdmissionId" IS DISTINCT FROM NEW."stagingAdmissionId"
    OR layer_row."stagingRunId" IS DISTINCT FROM NEW."stagingRunId" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_LINEAGE_MISMATCH'
      USING ERRCODE = '23514';
  END IF;

  IF NEW."stagingRunId" IS NULL THEN
    IF NEW."providerMode" = 'SYNTHETIC_QA' THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_MODE_MISMATCH'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    SELECT r."practiceId", r."visitId", r."admissionId", a."phase"
    INTO run_row
    FROM "template_twin_synthetic_qa_runs" r
    JOIN "template_twin_synthetic_qa_admissions" a ON a."id" = r."admissionId"
    WHERE r."id" = NEW."stagingRunId"
      AND a."id" = NEW."stagingAdmissionId";
    IF run_row IS NULL
      OR run_row."practiceId" <> NEW."practiceId"
      OR run_row."visitId" <> NEW."visitId"
      OR run_row."admissionId" <> NEW."stagingAdmissionId"
      OR NOT (
        run_row."phase" = 'PROCESSING'
        OR (
          NEW."status" IN ('FAILED', 'UNKNOWN_OUTCOME')
          AND run_row."phase" IN ('FAILED', 'REVOKED')
        )
      )
      OR NEW."providerMode" <> 'SYNTHETIC_QA' THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_STAGING_MISMATCH'
        USING ERRCODE = '23514';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_provider_execution_lineage_guard
BEFORE INSERT OR UPDATE ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION visit_automation_provider_execution_assert_lineage();

CREATE OR REPLACE FUNCTION visit_automation_provider_execution_guard_transition()
RETURNS trigger AS $$
BEGIN
  IF OLD."practiceId" <> NEW."practiceId"
    OR OLD."visitId" <> NEW."visitId"
    OR OLD."manifestId" <> NEW."manifestId"
    OR OLD."automationLayerId" <> NEW."automationLayerId"
    OR OLD."stagingAdmissionId" IS DISTINCT FROM NEW."stagingAdmissionId"
    OR OLD."stagingRunId" IS DISTINCT FROM NEW."stagingRunId"
    OR OLD."inputSha256" <> NEW."inputSha256"
    OR OLD."provider" <> NEW."provider"
    OR OLD."providerMode" <> NEW."providerMode"
    OR OLD."model" <> NEW."model"
    OR OLD."operationVersion" <> NEW."operationVersion"
    OR OLD."idempotencyKey" <> NEW."idempotencyKey"
    OR OLD."reservedAt" <> NEW."reservedAt" THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_IDENTITY_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;

  IF OLD."status" IN ('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME') THEN
    IF NEW IS DISTINCT FROM OLD THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE'
        USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  IF NOT (
    (OLD."status" = 'RESERVED' AND NEW."status" IN ('IN_FLIGHT', 'FAILED'))
    OR
    (OLD."status" = 'IN_FLIGHT' AND NEW."status" IN ('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME'))
  ) THEN
    RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_TRANSITION_INVALID'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_provider_execution_transition_guard
BEFORE UPDATE ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION visit_automation_provider_execution_guard_transition();

COMMENT ON TABLE "visit_automation_provider_executions" IS
  'Private provider-result ledger; no historical rows are inferred and no payload may enter audit metadata.';

COMMIT;
