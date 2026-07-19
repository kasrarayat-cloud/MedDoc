-- Template Twin production release/control plane v1.
--
-- Additive and default-off. This migration creates only empty release-control
-- tables and enforcement functions. It does not authorize a human, create a
-- release, enable the global gate, enable a practice, or mutate clinical data.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RELEASE_CREATED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RELEASE_FROZEN';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RELEASE_APPROVAL_RECORDED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_ACTIVATED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_RELEASE_REVOKED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLOUT_GUARDRAIL_REVOKED';

-- Installation is permitted only from an already revoked production posture.
-- Do not silently convert an older synthetic/staging enablement into a GA
-- release. Operations must use the audited revocation path before migration.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
      AND (
        "enabled" = TRUE
        OR "rollbackFenceState" <> 'OPEN'
        OR "rollbackOperationId" IS NOT NULL
      )
  ) OR EXISTS (
    SELECT 1 FROM "practices" WHERE "templateTwinEnabled" = TRUE
  ) THEN
    RAISE EXCEPTION 'Template Twin production control plane requires a disabled, open-fence rollout baseline';
  END IF;
END;
$$;

CREATE TABLE "template_twin_release_candidates" (
  "id" UUID NOT NULL,
  "identityVersion" VARCHAR(64) NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "sourceCommitSha" CHAR(40) NOT NULL,
  "baseCommitSha" CHAR(40) NOT NULL,
  "appImageDigest" VARCHAR(71) NOT NULL,
  "workerImageDigest" VARCHAR(71) NOT NULL,
  "migratorImageDigest" VARCHAR(71) NOT NULL,
  "testCensusEvidenceSha256" CHAR(64) NOT NULL,
  "independentReviewEvidenceSha256" CHAR(64) NOT NULL,
  "securityEvidenceSha256" CHAR(64) NOT NULL,
  "migrationRestoreEvidenceSha256" CHAR(64) NOT NULL,
  "officeWordEvidenceSha256" CHAR(64) NOT NULL,
  "guardrailPolicySha256" CHAR(64) NOT NULL,
  "authorizedPracticeManifestSha256" CHAR(64) NOT NULL,
  "guardrailPolicy" JSONB NOT NULL,
  "status" VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
  "generation" BIGINT NOT NULL DEFAULT 1,
  "createdById" TEXT NOT NULL,
  "frozenById" TEXT,
  "frozenAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_candidates_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_identity_key" UNIQUE ("releaseIdentitySha256"),
  CONSTRAINT "template_twin_release_identity_version" CHECK (
    "identityVersion" = 'template-twin-production-release-v1'
  ),
  CONSTRAINT "template_twin_release_identity_sha" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "testCensusEvidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "independentReviewEvidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "securityEvidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "migrationRestoreEvidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "officeWordEvidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "guardrailPolicySha256" ~ '^[0-9a-f]{64}$'
    AND "authorizedPracticeManifestSha256" ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT "template_twin_release_commit_sha" CHECK (
    "sourceCommitSha" ~ '^[0-9a-f]{40}$'
    AND "baseCommitSha" ~ '^[0-9a-f]{40}$'
  ),
  CONSTRAINT "template_twin_release_image_digest" CHECK (
    "appImageDigest" ~ '^sha256:[0-9a-f]{64}$'
    AND "workerImageDigest" ~ '^sha256:[0-9a-f]{64}$'
    AND "migratorImageDigest" ~ '^sha256:[0-9a-f]{64}$'
  ),
  CONSTRAINT "template_twin_release_status" CHECK (
    "status" IN (
      'DRAFT', 'FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100',
      'REJECTED', 'REVOKED'
    )
  ),
  CONSTRAINT "template_twin_release_generation_positive" CHECK (
    "generation" > 0
  ),
  CONSTRAINT "template_twin_release_freeze_shape" CHECK (
    ("status" = 'DRAFT' AND "frozenById" IS NULL AND "frozenAt" IS NULL)
    OR
    ("status" <> 'DRAFT' AND "frozenById" IS NOT NULL AND "frozenAt" IS NOT NULL)
  )
);

CREATE INDEX "template_twin_release_candidates_status_created_idx"
  ON "template_twin_release_candidates"("status", "createdAt");

CREATE UNIQUE INDEX "template_twin_one_live_release_key"
  ON "template_twin_release_candidates" ((TRUE))
  WHERE "status" IN ('DRAFT', 'FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100');

CREATE TABLE "template_twin_release_authorities" (
  "id" UUID NOT NULL,
  "userId" TEXT NOT NULL,
  "discipline" VARCHAR(32) NOT NULL,
  "sourceRef" VARCHAR(160) NOT NULL,
  "effectiveAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "revokedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_authorities_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_authority_discipline" CHECK (
    "discipline" IN ('DESKTOP_WORD', 'CLINICAL_SAFETY', 'PRIVACY_LEGAL', 'OPERATIONS')
  ),
  CONSTRAINT "template_twin_release_authority_source" CHECK (
    "sourceRef" ~ '^[A-Za-z0-9][A-Za-z0-9._:/ -]{2,159}$'
  ),
  CONSTRAINT "template_twin_release_authority_dates" CHECK (
    "revokedAt" IS NULL OR "revokedAt" >= "effectiveAt"
  )
);

CREATE UNIQUE INDEX "template_twin_one_active_release_authority_key"
  ON "template_twin_release_authorities"("userId", "discipline")
  WHERE "revokedAt" IS NULL;
CREATE INDEX "template_twin_release_authorities_user_discipline_idx"
  ON "template_twin_release_authorities"("userId", "discipline", "revokedAt");

CREATE TABLE "template_twin_release_practices" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "practiceId" TEXT NOT NULL,
  "practiceSlugSnapshot" VARCHAR(160) NOT NULL,
  "physicianCountSnapshot" INTEGER NOT NULL,
  "cohortRank" INTEGER NOT NULL,
  "cohortHashSha256" CHAR(64) NOT NULL,
  "isCanary" BOOLEAN NOT NULL DEFAULT false,
  "activationStage" VARCHAR(24) NOT NULL,
  "activationStageOrdinal" INTEGER NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_practices_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_practice_key" UNIQUE ("releaseId", "practiceId"),
  CONSTRAINT "template_twin_release_cohort_rank_key" UNIQUE ("releaseId", "cohortRank"),
  CONSTRAINT "template_twin_release_practice_sha" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "cohortHashSha256" ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT "template_twin_release_practice_counts" CHECK (
    "physicianCountSnapshot" >= 0 AND "cohortRank" > 0
  ),
  CONSTRAINT "template_twin_release_practice_stage" CHECK (
    ("activationStage" = 'CANARY' AND "activationStageOrdinal" = 1)
    OR ("activationStage" = 'PERCENT_10' AND "activationStageOrdinal" = 2)
    OR ("activationStage" = 'PERCENT_25' AND "activationStageOrdinal" = 3)
    OR ("activationStage" = 'PERCENT_50' AND "activationStageOrdinal" = 4)
    OR ("activationStage" = 'PERCENT_100' AND "activationStageOrdinal" = 5)
  ),
  CONSTRAINT "template_twin_release_canary_stage" CHECK (
    NOT "isCanary" OR "activationStage" = 'CANARY'
  )
);

CREATE INDEX "template_twin_release_practices_stage_rank_idx"
  ON "template_twin_release_practices"("releaseId", "activationStageOrdinal", "cohortRank");

CREATE TABLE "template_twin_release_approval_decisions" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "discipline" VARCHAR(32) NOT NULL,
  "decision" VARCHAR(16) NOT NULL,
  "evidenceSha256" CHAR(64) NOT NULL,
  "confirmation" VARCHAR(160) NOT NULL,
  "actorId" TEXT NOT NULL,
  "actorEmailSnapshot" TEXT,
  "actorSessionSha256" CHAR(64) NOT NULL,
  "authorityAssignmentId" UUID NOT NULL,
  "auditOutboxEventKey" TEXT NOT NULL,
  "decidedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_approval_decisions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_approval_audit_key" UNIQUE ("auditOutboxEventKey"),
  CONSTRAINT "template_twin_release_approval_discipline" CHECK (
    "discipline" IN ('DESKTOP_WORD', 'CLINICAL_SAFETY', 'PRIVACY_LEGAL', 'OPERATIONS')
  ),
  CONSTRAINT "template_twin_release_approval_decision" CHECK (
    "decision" IN ('APPROVE', 'REJECT', 'REVOKE')
  ),
  CONSTRAINT "template_twin_release_approval_sha" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "evidenceSha256" ~ '^[0-9a-f]{64}$'
    AND "actorSessionSha256" ~ '^[0-9a-f]{64}$'
  )
);

CREATE INDEX "template_twin_release_approval_release_discipline_idx"
  ON "template_twin_release_approval_decisions"("releaseId", "discipline", "decidedAt");
CREATE INDEX "template_twin_release_approval_actor_idx"
  ON "template_twin_release_approval_decisions"("actorId", "decidedAt");

CREATE TABLE "template_twin_release_checkpoints" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "stage" VARCHAR(24) NOT NULL,
  "ordinal" INTEGER NOT NULL,
  "targetPercent" INTEGER NOT NULL,
  "targetPhysicianCount" INTEGER NOT NULL,
  "assignedPhysicianCount" INTEGER NOT NULL,
  "status" VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  "minimumBakeSeconds" INTEGER NOT NULL,
  "activatedPhysicianCount" INTEGER,
  "passedPhysicianCount" INTEGER,
  "activatedAt" TIMESTAMPTZ(6),
  "earliestPassAt" TIMESTAMPTZ(6),
  "passedAt" TIMESTAMPTZ(6),
  "revokedAt" TIMESTAMPTZ(6),
  "activatedById" TEXT,
  "passedById" TEXT,
  "activationOutboxEventKey" TEXT,
  "passOutboxEventKey" TEXT,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_checkpoints_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_checkpoint_stage_key" UNIQUE ("releaseId", "stage"),
  CONSTRAINT "template_twin_release_checkpoint_ordinal_key" UNIQUE ("releaseId", "ordinal"),
  CONSTRAINT "template_twin_release_checkpoint_activation_audit_key" UNIQUE ("activationOutboxEventKey"),
  CONSTRAINT "template_twin_release_checkpoint_pass_audit_key" UNIQUE ("passOutboxEventKey"),
  CONSTRAINT "template_twin_release_checkpoint_sha" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT "template_twin_release_checkpoint_stage" CHECK (
    ("stage" = 'CANARY' AND "ordinal" = 1 AND "targetPercent" = 0)
    OR ("stage" = 'PERCENT_10' AND "ordinal" = 2 AND "targetPercent" = 10)
    OR ("stage" = 'PERCENT_25' AND "ordinal" = 3 AND "targetPercent" = 25)
    OR ("stage" = 'PERCENT_50' AND "ordinal" = 4 AND "targetPercent" = 50)
    OR ("stage" = 'PERCENT_100' AND "ordinal" = 5 AND "targetPercent" = 100)
  ),
  CONSTRAINT "template_twin_release_checkpoint_counts" CHECK (
    "targetPhysicianCount" >= 0
    AND "assignedPhysicianCount" >= 0
    AND "minimumBakeSeconds" > 0
    AND ("activatedPhysicianCount" IS NULL OR "activatedPhysicianCount" >= 0)
    AND ("passedPhysicianCount" IS NULL OR "passedPhysicianCount" >= 0)
  ),
  CONSTRAINT "template_twin_release_checkpoint_status" CHECK (
    "status" IN ('PENDING', 'ACTIVE', 'PASSED', 'FAILED', 'REVOKED')
  ),
  CONSTRAINT "template_twin_release_checkpoint_state_shape" CHECK (
    ("status" = 'PENDING'
      AND "activatedAt" IS NULL AND "earliestPassAt" IS NULL
      AND "activatedById" IS NULL AND "activatedPhysicianCount" IS NULL
      AND "passedAt" IS NULL AND "passedById" IS NULL
      AND "passedPhysicianCount" IS NULL AND "revokedAt" IS NULL
      AND "activationOutboxEventKey" IS NULL AND "passOutboxEventKey" IS NULL)
    OR
    ("status" = 'ACTIVE'
      AND "activatedAt" IS NOT NULL AND "earliestPassAt" IS NOT NULL
      AND "activatedById" IS NOT NULL AND "activatedPhysicianCount" IS NOT NULL
      AND "passedAt" IS NULL AND "passedById" IS NULL
      AND "passedPhysicianCount" IS NULL AND "revokedAt" IS NULL
      AND "activationOutboxEventKey" IS NOT NULL AND "passOutboxEventKey" IS NULL)
    OR
    ("status" = 'PASSED'
      AND "activatedAt" IS NOT NULL AND "earliestPassAt" IS NOT NULL
      AND "activatedById" IS NOT NULL AND "activatedPhysicianCount" IS NOT NULL
      AND "passedAt" IS NOT NULL AND "passedById" IS NOT NULL
      AND "passedPhysicianCount" IS NOT NULL AND "revokedAt" IS NULL
      AND "activationOutboxEventKey" IS NOT NULL AND "passOutboxEventKey" IS NOT NULL)
    OR
    ("status" IN ('FAILED', 'REVOKED')
      AND "activatedAt" IS NOT NULL AND "earliestPassAt" IS NOT NULL
      AND "activatedById" IS NOT NULL AND "activatedPhysicianCount" IS NOT NULL
      AND "passedAt" IS NULL AND "passedById" IS NULL
      AND "passedPhysicianCount" IS NULL AND "revokedAt" IS NOT NULL
      AND "activationOutboxEventKey" IS NOT NULL AND "passOutboxEventKey" IS NULL)
  )
);

CREATE INDEX "template_twin_release_checkpoints_status_idx"
  ON "template_twin_release_checkpoints"("releaseId", "status", "ordinal");

CREATE TABLE "template_twin_release_metric_snapshots" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "checkpointId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "policySha256" CHAR(64) NOT NULL,
  "schemaVersion" VARCHAR(64) NOT NULL,
  "sampleCount" INTEGER NOT NULL,
  "observationStartedAt" TIMESTAMPTZ(6) NOT NULL,
  "observationEndedAt" TIMESTAMPTZ(6) NOT NULL,
  "metrics" JSONB NOT NULL,
  "canonicalSha256" CHAR(64) NOT NULL,
  "evaluation" VARCHAR(24) NOT NULL,
  "missingMetrics" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  "breachedMetrics" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  "blockingReasons" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  "recordedById" TEXT,
  "criticalOutboxEventKey" TEXT,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_release_metric_snapshots_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_metric_canonical_key" UNIQUE ("canonicalSha256"),
  CONSTRAINT "template_twin_release_metric_critical_audit_key" UNIQUE ("criticalOutboxEventKey"),
  CONSTRAINT "template_twin_release_metric_sha" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "policySha256" ~ '^[0-9a-f]{64}$'
    AND "canonicalSha256" ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT "template_twin_release_metric_counts" CHECK (
    "sampleCount" >= 0 AND "observationEndedAt" > "observationStartedAt"
  ),
  CONSTRAINT "template_twin_release_metric_evaluation" CHECK (
    "evaluation" IN ('PASS', 'BLOCK', 'CRITICAL_REVOKE')
  ),
  CONSTRAINT "template_twin_release_metric_critical_shape" CHECK (
    ("evaluation" = 'CRITICAL_REVOKE' AND "criticalOutboxEventKey" IS NOT NULL)
    OR ("evaluation" <> 'CRITICAL_REVOKE' AND "criticalOutboxEventKey" IS NULL)
  )
);

CREATE INDEX "template_twin_release_metric_checkpoint_idx"
  ON "template_twin_release_metric_snapshots"("checkpointId", "createdAt");
CREATE INDEX "template_twin_release_metric_evaluation_idx"
  ON "template_twin_release_metric_snapshots"("releaseId", "evaluation", "createdAt");

-- Short-lived, transaction-bound capability receipts. A random nonce is
-- issued only by the validating SECURITY DEFINER function. A nonce cannot be
-- replayed in another backend or transaction and expires after five minutes.
CREATE TABLE "template_twin_release_capabilities" (
  "nonce" UUID NOT NULL,
  "transactionId" BIGINT NOT NULL,
  "backendPid" INTEGER NOT NULL,
  "releaseId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "checkpointId" UUID NOT NULL,
  "stageOrdinal" INTEGER NOT NULL,
  "releaseGeneration" BIGINT NOT NULL,
  "expectedGlobalGeneration" BIGINT NOT NULL,
  "issuedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_release_capabilities_pkey" PRIMARY KEY ("nonce"),
  CONSTRAINT "template_twin_release_capability_expiry" CHECK ("expiresAt" > "issuedAt")
);

CREATE INDEX "template_twin_release_capability_expiry_idx"
  ON "template_twin_release_capabilities"("expiresAt");

-- Capability receipts are an immutable security ledger. The issuer inserts a
-- fresh receipt; no caller may retarget, refresh, or delete it for replay.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE
  ON "template_twin_release_capabilities" FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_reject_release_capability_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin release capability receipts are immutable';
END;
$$;

CREATE TRIGGER template_twin_release_capability_update_delete_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_capabilities"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_release_capability_mutation();
CREATE TRIGGER template_twin_release_capability_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_capabilities"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_capability_mutation();

ALTER TABLE "template_twin_release_candidates"
  ADD CONSTRAINT "template_twin_release_creator_fkey"
  FOREIGN KEY ("createdById") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_finalizer_fkey"
  FOREIGN KEY ("frozenById") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_authorities"
  ADD CONSTRAINT "template_twin_release_authority_user_fkey"
  FOREIGN KEY ("userId") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_practices"
  ADD CONSTRAINT "template_twin_release_practice_release_fkey"
  FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_practice_practice_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_approval_decisions"
  ADD CONSTRAINT "template_twin_release_approval_release_fkey"
  FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_approval_actor_fkey"
  FOREIGN KEY ("actorId") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_approval_authority_fkey"
  FOREIGN KEY ("authorityAssignmentId") REFERENCES "template_twin_release_authorities"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_approval_audit_fkey"
  FOREIGN KEY ("auditOutboxEventKey") REFERENCES "template_twin_audit_outbox"("eventKey")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_checkpoints"
  ADD CONSTRAINT "template_twin_release_checkpoint_release_fkey"
  FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_checkpoint_activator_fkey"
  FOREIGN KEY ("activatedById") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_checkpoint_passer_fkey"
  FOREIGN KEY ("passedById") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_checkpoint_activation_audit_fkey"
  FOREIGN KEY ("activationOutboxEventKey") REFERENCES "template_twin_audit_outbox"("eventKey")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_checkpoint_pass_audit_fkey"
  FOREIGN KEY ("passOutboxEventKey") REFERENCES "template_twin_audit_outbox"("eventKey")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_metric_snapshots"
  ADD CONSTRAINT "template_twin_release_metric_release_fkey"
  FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_metric_checkpoint_fkey"
  FOREIGN KEY ("checkpointId") REFERENCES "template_twin_release_checkpoints"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_metric_recorder_fkey"
  FOREIGN KEY ("recordedById") REFERENCES "users"("id")
  ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_metric_critical_audit_fkey"
  FOREIGN KEY ("criticalOutboxEventKey") REFERENCES "template_twin_audit_outbox"("eventKey")
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE "template_twin_release_capabilities"
  ADD CONSTRAINT "template_twin_release_capability_release_fkey"
  FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
  ON DELETE CASCADE ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_capability_checkpoint_fkey"
  FOREIGN KEY ("checkpointId") REFERENCES "template_twin_release_checkpoints"("id")
  ON DELETE CASCADE ON UPDATE RESTRICT;

-- One lock order covers rollback, approval, release state, and exposure.
CREATE OR REPLACE FUNCTION template_twin_lock_release_control_statement()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);
  RETURN NULL;
END;
$$;

CREATE TRIGGER aaa_template_twin_release_candidate_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_candidates"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();
CREATE TRIGGER aaa_template_twin_release_authority_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_authorities"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();
CREATE TRIGGER aaa_template_twin_release_practice_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_practices"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();
CREATE TRIGGER aaa_template_twin_release_approval_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_approval_decisions"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();
CREATE TRIGGER aaa_template_twin_release_checkpoint_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_checkpoints"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();
CREATE TRIGGER aaa_template_twin_release_metric_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_release_metric_snapshots"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_release_control_statement();

CREATE OR REPLACE FUNCTION template_twin_guard_release_candidate_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release history cannot be deleted';
  END IF;

  IF ROW(
    NEW."id", NEW."identityVersion", NEW."releaseIdentitySha256",
    NEW."sourceCommitSha", NEW."baseCommitSha", NEW."appImageDigest",
    NEW."workerImageDigest", NEW."migratorImageDigest",
    NEW."testCensusEvidenceSha256", NEW."independentReviewEvidenceSha256",
    NEW."securityEvidenceSha256", NEW."migrationRestoreEvidenceSha256",
    NEW."officeWordEvidenceSha256", NEW."guardrailPolicySha256",
    NEW."authorizedPracticeManifestSha256", NEW."guardrailPolicy",
    NEW."createdById", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."identityVersion", OLD."releaseIdentitySha256",
    OLD."sourceCommitSha", OLD."baseCommitSha", OLD."appImageDigest",
    OLD."workerImageDigest", OLD."migratorImageDigest",
    OLD."testCensusEvidenceSha256", OLD."independentReviewEvidenceSha256",
    OLD."securityEvidenceSha256", OLD."migrationRestoreEvidenceSha256",
    OLD."officeWordEvidenceSha256", OLD."guardrailPolicySha256",
    OLD."authorizedPracticeManifestSha256", OLD."guardrailPolicy",
    OLD."createdById", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin release identity is immutable';
  END IF;

  IF NEW."generation" <> OLD."generation" + 1 THEN
    RAISE EXCEPTION 'Template Twin release transition must advance one generation';
  END IF;

  IF NOT (
    (OLD."status" = 'DRAFT' AND NEW."status" = 'FROZEN')
    OR (OLD."status" = 'FROZEN' AND NEW."status" IN ('FROZEN', 'APPROVED', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'APPROVED' AND NEW."status" IN ('APPROVED', 'ROLLING_OUT', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'ROLLING_OUT' AND NEW."status" IN ('ROLLING_OUT', 'STABLE_100', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'STABLE_100' AND NEW."status" IN ('REJECTED', 'REVOKED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin release state transition is invalid';
  END IF;

  IF OLD."status" = 'DRAFT' THEN
    IF NEW."status" <> 'FROZEN' OR NEW."frozenById" IS NULL OR NEW."frozenAt" IS NULL THEN
      RAISE EXCEPTION 'Template Twin release freeze evidence is incomplete';
    END IF;
  ELSIF ROW(NEW."frozenById", NEW."frozenAt") IS DISTINCT FROM
            ROW(OLD."frozenById", OLD."frozenAt") THEN
    RAISE EXCEPTION 'Template Twin release finalizer identity is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_candidate_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_candidates"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_candidate_history();

CREATE OR REPLACE FUNCTION template_twin_guard_release_authority_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release authority history cannot be deleted';
  END IF;
  IF ROW(
    NEW."id", NEW."userId", NEW."discipline", NEW."sourceRef",
    NEW."effectiveAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."userId", OLD."discipline", OLD."sourceRef",
    OLD."effectiveAt", OLD."createdAt"
  ) OR OLD."revokedAt" IS NOT NULL OR NEW."revokedAt" IS NULL THEN
    RAISE EXCEPTION 'Template Twin release authority may only be revoked once';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM "template_twin_release_candidates" candidate
    JOIN "template_twin_release_approval_decisions" decision
      ON decision."releaseId" = candidate."id"
    WHERE candidate."status" IN ('APPROVED', 'ROLLING_OUT', 'STABLE_100')
      AND decision."authorityAssignmentId" = OLD."id"
      AND decision."id" = (
        SELECT latest."id"
        FROM "template_twin_release_approval_decisions" latest
        WHERE latest."releaseId" = candidate."id"
          AND latest."discipline" = decision."discipline"
        ORDER BY latest."decidedAt" DESC, latest."id" DESC
        LIMIT 1
      )
  ) THEN
    RAISE EXCEPTION 'Revoke the active Template Twin release before revoking its human authority';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_authority_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_authorities"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_authority_history();

CREATE OR REPLACE FUNCTION template_twin_reject_release_row_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin release evidence is append-only';
END;
$$;

CREATE TRIGGER template_twin_release_practice_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_release_row_mutation();
CREATE TRIGGER template_twin_release_approval_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_approval_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_release_row_mutation();
CREATE TRIGGER template_twin_release_metric_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_metric_snapshots"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_release_row_mutation();

CREATE OR REPLACE FUNCTION template_twin_guard_release_approval_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  release_creator TEXT;
  release_finalizer TEXT;
  release_identity CHAR(64);
  release_state TEXT;
BEGIN
  SELECT "createdById", "frozenById", "releaseIdentitySha256", "status"
    INTO release_creator, release_finalizer, release_identity, release_state
  FROM "template_twin_release_candidates"
  WHERE "id" = NEW."releaseId";
  IF NOT FOUND OR release_state NOT IN ('FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100') THEN
    RAISE EXCEPTION 'Template Twin release is not open for a human decision';
  END IF;
  IF NEW."releaseIdentitySha256" <> release_identity THEN
    RAISE EXCEPTION 'Template Twin approval identity does not match the release';
  END IF;
  IF NEW."actorId" = release_creator OR NEW."actorId" = release_finalizer THEN
    RAISE EXCEPTION 'Template Twin release creator/finalizer cannot approve the release';
  END IF;
  IF release_state IN ('ROLLING_OUT', 'STABLE_100') AND NEW."decision" = 'APPROVE' THEN
    RAISE EXCEPTION 'Template Twin approvals cannot be refreshed after rollout begins';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM "template_twin_release_authorities" authority
    WHERE authority."id" = NEW."authorityAssignmentId"
      AND authority."userId" = NEW."actorId"
      AND authority."discipline" = NEW."discipline"
      AND authority."effectiveAt" <= NEW."decidedAt"
      AND authority."revokedAt" IS NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin human authority is missing or revoked';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_approval_insert_guard
BEFORE INSERT ON "template_twin_release_approval_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_approval_insert();

CREATE OR REPLACE FUNCTION template_twin_guard_release_checkpoint_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin checkpoint history cannot be deleted';
  END IF;
  IF ROW(
    NEW."id", NEW."releaseId", NEW."releaseIdentitySha256", NEW."stage",
    NEW."ordinal", NEW."targetPercent", NEW."targetPhysicianCount",
    NEW."assignedPhysicianCount", NEW."minimumBakeSeconds", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."releaseId", OLD."releaseIdentitySha256", OLD."stage",
    OLD."ordinal", OLD."targetPercent", OLD."targetPhysicianCount",
    OLD."assignedPhysicianCount", OLD."minimumBakeSeconds", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint identity is immutable';
  END IF;
  IF NOT (
    (OLD."status" = 'PENDING' AND NEW."status" = 'ACTIVE')
    OR (OLD."status" = 'ACTIVE' AND NEW."status" IN ('PASSED', 'FAILED', 'REVOKED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint state transition is invalid';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_checkpoint_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_checkpoints"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_checkpoint_history();

CREATE OR REPLACE FUNCTION template_twin_guard_release_child_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  expected_identity CHAR(64);
  expected_policy CHAR(64);
  checkpoint_release UUID;
BEGIN
  SELECT "releaseIdentitySha256", "guardrailPolicySha256"
    INTO expected_identity, expected_policy
  FROM "template_twin_release_candidates"
  WHERE "id" = NEW."releaseId";
  IF NOT FOUND OR NEW."releaseIdentitySha256" <> expected_identity THEN
    RAISE EXCEPTION 'Template Twin release child identity mismatch';
  END IF;
  IF TG_TABLE_NAME = 'template_twin_release_metric_snapshots' THEN
    SELECT "releaseId" INTO checkpoint_release
    FROM "template_twin_release_checkpoints"
    WHERE "id" = NEW."checkpointId";
    IF NOT FOUND OR checkpoint_release <> NEW."releaseId"
      OR NEW."policySha256" <> expected_policy THEN
      RAISE EXCEPTION 'Template Twin metric release/policy identity mismatch';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_practice_identity_guard
BEFORE INSERT ON "template_twin_release_practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_child_identity();
CREATE TRIGGER template_twin_release_checkpoint_identity_guard
BEFORE INSERT ON "template_twin_release_checkpoints"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_child_identity();
CREATE TRIGGER template_twin_release_metric_identity_guard
BEFORE INSERT ON "template_twin_release_metric_snapshots"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_child_identity();

CREATE OR REPLACE FUNCTION template_twin_reject_release_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin release evidence cannot be truncated';
END;
$$;

CREATE TRIGGER template_twin_release_candidate_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_candidates"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();
CREATE TRIGGER template_twin_release_authority_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_authorities"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();
CREATE TRIGGER template_twin_release_practice_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_practices"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();
CREATE TRIGGER template_twin_release_approval_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_approval_decisions"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();
CREATE TRIGGER template_twin_release_checkpoint_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_checkpoints"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();
CREATE TRIGGER template_twin_release_metric_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_metric_snapshots"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();

CREATE OR REPLACE FUNCTION template_twin_release_approvals_are_current(
  candidate_id UUID,
  candidate_identity CHAR(64)
)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
  WITH latest AS (
    SELECT DISTINCT ON (decision."discipline")
      decision."discipline", decision."decision",
      decision."authorityAssignmentId", decision."actorId"
    FROM "template_twin_release_approval_decisions" decision
    WHERE decision."releaseId" = candidate_id
      AND decision."releaseIdentitySha256" = candidate_identity
    ORDER BY decision."discipline", decision."decidedAt" DESC, decision."id" DESC
  )
  SELECT COUNT(*) = 4 AND BOOL_AND(
    latest."decision" = 'APPROVE'
    AND EXISTS (
      SELECT 1 FROM "template_twin_release_authorities" authority
      WHERE authority."id" = latest."authorityAssignmentId"
        AND authority."userId" = latest."actorId"
        AND authority."discipline" = latest."discipline"
        AND authority."revokedAt" IS NULL
    )
  )
  FROM latest;
$$;

CREATE OR REPLACE FUNCTION template_twin_issue_release_capability(
  candidate_id UUID,
  candidate_identity CHAR(64),
  active_checkpoint_id UUID,
  expected_release_generation BIGINT,
  expected_global_generation BIGINT
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  capability_nonce UUID := gen_random_uuid();
  stage_ordinal INTEGER;
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);

  SELECT checkpoint."ordinal" INTO stage_ordinal
  FROM public."template_twin_release_candidates" candidate
  JOIN public."template_twin_release_checkpoints" checkpoint
    ON checkpoint."releaseId" = candidate."id"
  WHERE candidate."id" = candidate_id
    AND candidate."releaseIdentitySha256" = candidate_identity
    AND candidate."status" = 'ROLLING_OUT'
    AND candidate."generation" = expected_release_generation
    AND checkpoint."id" = active_checkpoint_id
    AND checkpoint."releaseIdentitySha256" = candidate_identity
    AND checkpoint."status" = 'ACTIVE';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin release capability identity is stale';
  END IF;

  IF NOT public.template_twin_release_approvals_are_current(
    candidate_id, candidate_identity
  ) THEN
    RAISE EXCEPTION 'Template Twin release approvals are incomplete or stale';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public."template_twin_rollout_controls"
    WHERE "id" = 'global'
      AND "generation" = expected_global_generation
      AND "rollbackFenceState" = 'OPEN'
      AND "rollbackOperationId" IS NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin global rollout identity is stale or fenced';
  END IF;

  INSERT INTO public."template_twin_release_capabilities" (
    "nonce", "transactionId", "backendPid", "releaseId",
    "releaseIdentitySha256", "checkpointId", "stageOrdinal",
    "releaseGeneration", "expectedGlobalGeneration", "expiresAt"
  ) VALUES (
    capability_nonce, txid_current(), pg_backend_pid(), candidate_id,
    candidate_identity, active_checkpoint_id, stage_ordinal,
    expected_release_generation, expected_global_generation,
    clock_timestamp() + INTERVAL '5 minutes'
  );
  PERFORM set_config(
    'meddoc.template_twin_release_capability', capability_nonce::TEXT, TRUE
  );
  RETURN capability_nonce;
END;
$$;

REVOKE ALL ON FUNCTION template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_require_release_capability(
  requested_scope TEXT,
  requested_practice_id TEXT DEFAULT NULL
)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  configured_nonce TEXT;
  capability RECORD;
BEGIN
  configured_nonce := current_setting(
    'meddoc.template_twin_release_capability', TRUE
  );
  IF configured_nonce IS NULL OR configured_nonce !~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  THEN
    RAISE EXCEPTION 'Template Twin production enablement requires an active release capability';
  END IF;

  SELECT cap.* INTO capability
  FROM "template_twin_release_capabilities" cap
  JOIN "template_twin_release_candidates" candidate
    ON candidate."id" = cap."releaseId"
   AND candidate."releaseIdentitySha256" = cap."releaseIdentitySha256"
   AND candidate."generation" = cap."releaseGeneration"
   AND candidate."status" = 'ROLLING_OUT'
  JOIN "template_twin_release_checkpoints" checkpoint
    ON checkpoint."id" = cap."checkpointId"
   AND checkpoint."releaseId" = cap."releaseId"
   AND checkpoint."releaseIdentitySha256" = cap."releaseIdentitySha256"
   AND checkpoint."ordinal" = cap."stageOrdinal"
   AND checkpoint."status" = 'ACTIVE'
  WHERE cap."nonce" = configured_nonce::UUID
    AND cap."transactionId" = txid_current()
    AND cap."backendPid" = pg_backend_pid()
    AND cap."expiresAt" > clock_timestamp();
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin production enablement capability is forged or stale';
  END IF;

  IF requested_scope = 'global' THEN
    IF NOT EXISTS (
      SELECT 1 FROM "template_twin_rollout_controls"
      WHERE "id" = 'global'
        AND "generation" = capability."expectedGlobalGeneration"
        AND "rollbackFenceState" = 'OPEN'
    ) THEN
      RAISE EXCEPTION 'Template Twin global capability generation is stale';
    END IF;
  ELSIF requested_scope = 'practice' THEN
    IF requested_practice_id IS NULL OR NOT EXISTS (
      SELECT 1 FROM "template_twin_release_practices" manifest
      JOIN "template_twin_rollout_controls" control ON control."id" = 'global'
      WHERE manifest."releaseId" = capability."releaseId"
        AND manifest."releaseIdentitySha256" = capability."releaseIdentitySha256"
        AND manifest."practiceId" = requested_practice_id
        AND manifest."activationStageOrdinal" <= capability."stageOrdinal"
        AND control."enabled" = TRUE
        AND control."generation" = capability."expectedGlobalGeneration" + 1
        AND control."rollbackFenceState" = 'OPEN'
    ) THEN
      RAISE EXCEPTION 'Template Twin practice is outside the active release capability';
    END IF;
  ELSE
    RAISE EXCEPTION 'Template Twin release capability scope is invalid';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_global_release_enable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."enabled" = TRUE
    AND (OLD."enabled" = FALSE OR NEW."generation" IS DISTINCT FROM OLD."generation")
  THEN
    PERFORM template_twin_require_release_capability('global', NULL);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aab_template_twin_global_release_capability_guard
BEFORE UPDATE OF "enabled", "generation" ON "template_twin_rollout_controls"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_global_release_enable();

CREATE OR REPLACE FUNCTION template_twin_guard_practice_release_enable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateTwinEnabled" = TRUE AND OLD."templateTwinEnabled" = FALSE THEN
    PERFORM template_twin_require_release_capability('practice', NEW."id");
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aab_template_twin_practice_release_capability_guard
BEFORE UPDATE OF "templateTwinEnabled" ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_practice_release_enable();

-- Release event identity and delivered receipts are immutable just like the
-- rollback event family. Event keys contain identifiers/hashes only.
CREATE OR REPLACE FUNCTION template_twin_is_release_audit_identity(event_key TEXT)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
  SELECT event_key ~ '^template-twin:release:[0-9a-fA-F-]{36}:';
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_release_outbox_history()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  relevant BOOLEAN;
BEGIN
  relevant := CASE TG_OP
    WHEN 'INSERT' THEN template_twin_is_release_audit_identity(NEW."eventKey")
    WHEN 'DELETE' THEN template_twin_is_release_audit_identity(OLD."eventKey")
    ELSE template_twin_is_release_audit_identity(OLD."eventKey")
      OR template_twin_is_release_audit_identity(NEW."eventKey")
  END;
  IF NOT relevant THEN
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release audit outbox evidence cannot be deleted';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF ROW(
      NEW."id", NEW."practiceId", NEW."actorId", NEW."actorEmailSnapshot",
      NEW."eventKey", NEW."action", NEW."targetId", NEW."targetType",
      NEW."metadata", NEW."createdAt"
    ) IS DISTINCT FROM ROW(
      OLD."id", OLD."practiceId", OLD."actorId", OLD."actorEmailSnapshot",
      OLD."eventKey", OLD."action", OLD."targetId", OLD."targetType",
      OLD."metadata", OLD."createdAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin release audit identity is immutable';
    END IF;
    IF OLD."status" = 'DELIVERED' AND ROW(
      NEW."status", NEW."attemptCount", NEW."availableAt", NEW."deliveredAt",
      NEW."lastErrorCode", NEW."updatedAt"
    ) IS DISTINCT FROM ROW(
      OLD."status", OLD."attemptCount", OLD."availableAt", OLD."deliveredAt",
      OLD."lastErrorCode", OLD."updatedAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin delivered release receipt is immutable';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_release_outbox_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_audit_outbox"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_outbox_history();

CREATE OR REPLACE FUNCTION template_twin_guard_release_audit_log_history()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  relevant BOOLEAN;
BEGIN
  relevant := CASE TG_OP
    WHEN 'INSERT' THEN template_twin_is_release_audit_identity(NEW."templateTwinOutboxEventKey")
    WHEN 'DELETE' THEN template_twin_is_release_audit_identity(OLD."templateTwinOutboxEventKey")
    ELSE template_twin_is_release_audit_identity(OLD."templateTwinOutboxEventKey")
      OR template_twin_is_release_audit_identity(NEW."templateTwinOutboxEventKey")
  END;
  IF relevant AND TG_OP IN ('UPDATE', 'DELETE') THEN
    RAISE EXCEPTION 'Template Twin release audit receipt is immutable';
  END IF;
  RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

CREATE TRIGGER template_twin_release_audit_log_history_guard
BEFORE UPDATE OR DELETE ON "audit_logs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_audit_log_history();

CREATE OR REPLACE FUNCTION template_twin_assert_release_audit_delivery()
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_audit_outbox" outbox
    WHERE template_twin_is_release_audit_identity(outbox."eventKey")
      AND outbox."status" = 'DELIVERED'
      AND (
        outbox."deliveredAt" IS NULL
        OR NOT EXISTS (
          SELECT 1 FROM "audit_logs" log
          WHERE log."templateTwinOutboxEventKey" = outbox."eventKey"
            AND log."action" = outbox."action"
            AND log."targetType" = outbox."targetType"
            AND log."targetId" = outbox."targetId"
            AND log."practiceId" = outbox."practiceId"
            AND log."userId" IS NOT DISTINCT FROM outbox."actorId"
            AND log."success" = TRUE AND log."errorCode" IS NULL
        )
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin delivered release audit receipt is missing';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_check_release_audit_delivery()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM template_twin_assert_release_audit_delivery();
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER template_twin_release_outbox_delivery_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_audit_outbox"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_check_release_audit_delivery();
CREATE CONSTRAINT TRIGGER template_twin_release_audit_log_delivery_guard
AFTER INSERT OR UPDATE OR DELETE ON "audit_logs"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_check_release_audit_delivery();

CREATE OR REPLACE FUNCTION template_twin_assert_release_control_coupling()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_release_practices" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_approval_decisions" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_metric_snapshots" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
      OR child."policySha256" <> candidate."guardrailPolicySha256"
  ) THEN
    RAISE EXCEPTION 'Template Twin release child evidence identity mismatch';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE NOT EXISTS (
      SELECT 1 FROM "template_twin_audit_outbox" outbox
      WHERE outbox."eventKey" = 'template-twin:release:' || candidate."id"::TEXT || ':created'
        AND outbox."action"::TEXT = 'TEMPLATE_TWIN_RELEASE_CREATED'
        AND outbox."targetType" = 'TemplateTwinReleaseCandidate'
        AND outbox."targetId" = candidate."id"::TEXT
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin release creation audit evidence is missing';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE candidate."status" <> 'DRAFT'
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = 'template-twin:release:' || candidate."id"::TEXT || ':frozen'
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_RELEASE_FROZEN'
          AND outbox."targetId" = candidate."id"::TEXT
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin release freeze audit evidence is missing';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE candidate."status" IN ('APPROVED', 'ROLLING_OUT', 'STABLE_100')
      AND NOT template_twin_release_approvals_are_current(
        candidate."id", candidate."releaseIdentitySha256"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin current human approvals are incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" IN ('ACTIVE', 'PASSED', 'FAILED', 'REVOKED')
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = checkpoint."activationOutboxEventKey"
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_ACTIVATED'
          AND outbox."targetId" = checkpoint."id"::TEXT
      )
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" = 'PASSED'
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = checkpoint."passOutboxEventKey"
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED'
          AND outbox."targetId" = checkpoint."id"::TEXT
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint audit evidence is incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" = 'ACTIVE'
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_checkpoints" prior
        WHERE prior."releaseId" = checkpoint."releaseId"
          AND prior."ordinal" < checkpoint."ordinal"
          AND prior."status" <> 'PASSED'
      )
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE (
      SELECT COUNT(*) FROM "template_twin_release_checkpoints" checkpoint
      WHERE checkpoint."releaseId" = candidate."id"
        AND checkpoint."stage" IN ('CANARY', 'PERCENT_10', 'PERCENT_25', 'PERCENT_50', 'PERCENT_100')
    ) <> 5
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint rail is incomplete or out of order';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls" control
    WHERE control."id" = 'global' AND control."enabled" = TRUE
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_release_candidates" candidate
        WHERE candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
      )
  ) OR EXISTS (
    SELECT 1 FROM "practices" practice
    WHERE practice."templateTwinEnabled" = TRUE
      AND NOT EXISTS (
        SELECT 1
        FROM "template_twin_release_practices" manifest
        JOIN "template_twin_release_candidates" candidate
          ON candidate."id" = manifest."releaseId"
        WHERE manifest."practiceId" = practice."id"
          AND candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
          AND manifest."activationStageOrdinal" <= COALESCE((
            SELECT MAX(checkpoint."ordinal")
            FROM "template_twin_release_checkpoints" checkpoint
            WHERE checkpoint."releaseId" = candidate."id"
              AND checkpoint."status" IN ('ACTIVE', 'PASSED')
          ), 0)
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin persisted exposure is outside the release checkpoint';
  END IF;
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER template_twin_release_candidate_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_candidates"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_practice_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_practices"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_approval_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_approval_decisions"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_checkpoint_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_checkpoints"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_metric_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_metric_snapshots"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_global_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_rollout_controls"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_practice_flag_coupling_guard
AFTER UPDATE OF "templateTwinEnabled" ON "practices"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();

COMMIT;
