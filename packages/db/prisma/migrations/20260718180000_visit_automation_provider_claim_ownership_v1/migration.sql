-- One-owner compare-and-set internal concurrency token for provider execution.
--
-- Additive migration 77. Existing terminal executions keep their recorded
-- outcome and receive a deterministic legacy ownership marker. Existing
-- IN_FLIGHT rows are conservatively made UNKNOWN_OUTCOME: deployment cannot
-- prove whether their provider returned, so they must never be replayed.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- The old triggers predate the claim columns. Suspend them only inside this
-- transaction while rows are conservatively normalized, then recreate them
-- before commit. A failure rolls back the entire migration and both triggers.
DROP TRIGGER IF EXISTS visit_automation_provider_execution_transition_guard
  ON "visit_automation_provider_executions";
DROP TRIGGER IF EXISTS visit_automation_provider_execution_lineage_guard
  ON "visit_automation_provider_executions";

ALTER TABLE "visit_automation_provider_executions"
  ADD COLUMN "claimId" CHAR(64),
  ADD COLUMN "claimedAt" TIMESTAMPTZ(6);

-- md5 is a built-in PostgreSQL function. These legacy markers are not bearer
-- tokens and are never returned by the application; they only let the new
-- immutable state constraint describe executions created before migration 77.
UPDATE "visit_automation_provider_executions"
SET "claimId" = md5('template-twin-provider-claim-legacy-a:' || "id")
      || md5('template-twin-provider-claim-legacy-b:' || "id"),
    "claimedAt" = COALESCE("invokedAt", "reservedAt"),
    "status" = 'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus",
    "failureCode" = 'PROVIDER_OUTCOME_AMBIGUOUS',
    "completedAt" = COALESCE("completedAt", clock_timestamp()),
    "updatedAt" = clock_timestamp()
WHERE "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus";

UPDATE "visit_automation_provider_executions"
SET "claimId" = md5('template-twin-provider-claim-legacy-a:' || "id")
      || md5('template-twin-provider-claim-legacy-b:' || "id"),
    "claimedAt" = COALESCE("invokedAt", "reservedAt"),
    "updatedAt" = clock_timestamp()
WHERE "claimId" IS NULL
  AND (
    "status" IN (
      'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
      'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus"
    )
    OR (
      "status" = 'FAILED'::"VisitAutomationProviderExecutionStatus"
      AND "invocationCount" = 1
    )
  );

CREATE UNIQUE INDEX "visit_automation_provider_execution_claim_key"
  ON "visit_automation_provider_executions"("claimId");

ALTER TABLE "visit_automation_provider_executions"
  ADD CONSTRAINT "visit_automation_provider_execution_claim_hash_check"
    CHECK ("claimId" IS NULL OR "claimId" ~ '^[a-f0-9]{64}$'),
  DROP CONSTRAINT "visit_automation_provider_execution_state_shape_check",
  ADD CONSTRAINT "visit_automation_provider_execution_state_shape_check" CHECK (
    ("status" = 'RESERVED'
      AND "invocationCount" = 0
      AND "claimId" IS NULL AND "claimedAt" IS NULL
      AND "invokedAt" IS NULL AND "completedAt" IS NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NULL)
    OR
    ("status" = 'IN_FLIGHT'
      AND "invocationCount" = 1
      AND "claimId" IS NOT NULL AND "claimedAt" IS NOT NULL
      AND "invokedAt" IS NOT NULL AND "completedAt" IS NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NULL)
    OR
    ("status" = 'SUCCEEDED'
      AND "invocationCount" = 1
      AND "claimId" IS NOT NULL AND "claimedAt" IS NOT NULL
      AND "invokedAt" IS NOT NULL AND "completedAt" IS NOT NULL
      AND "resultPayload" IS NOT NULL AND "resultSha256" IS NOT NULL
      AND "resultVersion" IS NOT NULL AND "failureCode" IS NULL)
    OR
    ("status" = 'FAILED'
      AND "invocationCount" IN (0, 1)
      AND (
        ("invocationCount" = 0 AND "claimId" IS NULL
          AND "claimedAt" IS NULL AND "invokedAt" IS NULL)
        OR
        ("invocationCount" = 1 AND "claimId" IS NOT NULL
          AND "claimedAt" IS NOT NULL AND "invokedAt" IS NOT NULL)
      )
      AND "completedAt" IS NOT NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NOT NULL)
    OR
    ("status" = 'UNKNOWN_OUTCOME'
      AND "invocationCount" = 1
      AND "claimId" IS NOT NULL AND "claimedAt" IS NOT NULL
      AND "invokedAt" IS NOT NULL AND "completedAt" IS NOT NULL
      AND "resultPayload" IS NULL AND "resultSha256" IS NULL
      AND "resultVersion" IS NULL AND "failureCode" IS NOT NULL)
  );

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

  IF OLD."status" = 'RESERVED' AND NEW."status" = 'IN_FLIGHT' THEN
    IF OLD."claimId" IS NOT NULL OR OLD."claimedAt" IS NOT NULL
      OR NEW."claimId" IS NULL OR NEW."claimedAt" IS NULL THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF OLD."status" = 'RESERVED' AND NEW."status" = 'FAILED' THEN
    IF NEW."claimId" IS DISTINCT FROM OLD."claimId"
      OR NEW."claimedAt" IS DISTINCT FROM OLD."claimedAt" THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF OLD."status" = 'IN_FLIGHT'
    AND NEW."status" IN ('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME') THEN
    IF OLD."claimId" IS NULL OR OLD."claimedAt" IS NULL
      OR NEW."claimId" IS DISTINCT FROM OLD."claimId"
      OR NEW."claimedAt" IS DISTINCT FROM OLD."claimedAt" THEN
      RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    RAISE EXCEPTION 'VISIT_AUTOMATION_PROVIDER_EXECUTION_TRANSITION_INVALID'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER visit_automation_provider_execution_lineage_guard
BEFORE INSERT OR UPDATE ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION visit_automation_provider_execution_assert_lineage();

CREATE TRIGGER visit_automation_provider_execution_transition_guard
BEFORE UPDATE ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION visit_automation_provider_execution_guard_transition();

COMMENT ON COLUMN "visit_automation_provider_executions"."claimId" IS
  'Server-only provider ownership concurrency token; prohibited from logs, audits, and client responses.';
COMMENT ON COLUMN "visit_automation_provider_executions"."claimedAt" IS
  'Timestamp of the sole RESERVED-to-IN_FLIGHT compare-and-set claim.';

COMMIT;
