-- B-017: exact-owner execution boundary for every Template Twin provider call.
--
-- Additive only. Historical artifacts remain nullable and are classified as
-- LEGACY_UNOWNED by application gates. Every artifact inserted after this
-- migration must carry a canonical receipt whose referenced executions are
-- exact, terminal, tenant-bound successes. A provider outcome that may have
-- escaped is terminal UNKNOWN_OUTCOME and can never be replayed.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE "template_twin_provider_executions" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "actorUserId" TEXT NOT NULL,
  "visitId" TEXT,
  "scope" VARCHAR(40) NOT NULL,
  "operation" VARCHAR(80) NOT NULL,
  "logicalAttempt" INTEGER NOT NULL,
  "subjectId" VARCHAR(200) NOT NULL,
  "subjectSha256" CHAR(64) NOT NULL,
  "sourceArtifactId" TEXT,
  "compiledVersionId" TEXT,
  "noteTemplateId" TEXT,
  "noteTemplateVersion" INTEGER,
  "sourceLineageId" TEXT,
  "sourceLineageVersion" INTEGER,
  "sourceSha256" CHAR(64),
  "inputSha256" CHAR(64) NOT NULL,
  "provider" VARCHAR(40) NOT NULL,
  "providerMode" VARCHAR(40) NOT NULL,
  "model" VARCHAR(100) NOT NULL,
  "operationVersion" VARCHAR(80) NOT NULL,
  "providerConfigurationSha256" CHAR(64) NOT NULL,
  "runtimeIdentitySha256" CHAR(64) NOT NULL,
  "ownershipKey" CHAR(64) NOT NULL,
  "idempotencyKey" CHAR(64) NOT NULL,
  "pinnedGlobalRolloutGeneration" BIGINT NOT NULL,
  "pinnedPracticeRolloutGeneration" BIGINT NOT NULL,
  "releaseId" UUID,
  "releaseIdentitySha256" CHAR(64),
  "runtimeManifestSha256" CHAR(64),
  "runtimeInstanceId" VARCHAR(128),
  "status" "VisitAutomationProviderExecutionStatus" NOT NULL DEFAULT 'RESERVED',
  "invocationCount" INTEGER NOT NULL DEFAULT 0,
  "claimId" CHAR(64),
  "claimedAt" TIMESTAMPTZ(6),
  "resultPayload" JSONB,
  "resultSha256" CHAR(64),
  "resultVersion" VARCHAR(80),
  "failureCode" VARCHAR(80),
  "reservedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "invokedAt" TIMESTAMPTZ(6),
  "completedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_provider_executions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_provider_execution_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_execution_actor_fkey"
    FOREIGN KEY ("actorUserId") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_execution_visit_fkey"
    FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_execution_hash_check" CHECK (
    "subjectSha256" ~ '^[0-9a-f]{64}$'
    AND "inputSha256" ~ '^[0-9a-f]{64}$'
    AND "providerConfigurationSha256" ~ '^[0-9a-f]{64}$'
    AND "runtimeIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "ownershipKey" ~ '^[0-9a-f]{64}$'
    AND "idempotencyKey" ~ '^[0-9a-f]{64}$'
    AND ("sourceSha256" IS NULL OR "sourceSha256" ~ '^[0-9a-f]{64}$')
    AND ("releaseIdentitySha256" IS NULL OR "releaseIdentitySha256" ~ '^[0-9a-f]{64}$')
    AND ("runtimeManifestSha256" IS NULL OR "runtimeManifestSha256" ~ '^[0-9a-f]{64}$')
    AND ("claimId" IS NULL OR "claimId" ~ '^[0-9a-f]{64}$')
    AND ("resultSha256" IS NULL OR "resultSha256" ~ '^[0-9a-f]{64}$')
  ),
  CONSTRAINT "template_twin_provider_execution_code_check" CHECK (
    "scope" IN ('SOURCE_INTAKE', 'VISIT_PIPELINE', 'STATIC_ASSET',
      'CUSTOM_EXAMPLE', 'SYNTHETIC_EVIDENCE')
    AND "operation" IN (
      'SOURCE_PHI_SCAN', 'SOURCE_SEMANTIC_MAPPING',
      'STATIC_ASSET_PRIVACY_SCAN', 'SYNTHETIC_EVIDENCE_EXTRACTION',
      'CUSTOM_EXAMPLE_EXTRACTION', 'CUSTOM_CONCEPT_EXTRACTION',
      'L1_TRANSCRIBE', 'L1B_TRANSCRIBE', 'L2_SPEAKER_ROLES',
      'L3_EXTRACT_ENTITIES', 'L4_GENERATE_SOAP', 'L4_ANCHOR_VERIFY',
      'L5_SELF_CRITIQUE', 'L6_POLISH', 'L6_FIDELITY_VERIFY'
    )
    AND "provider" ~ '^[a-z0-9_-]{1,40}$'
    AND "providerMode" IN ('LIVE', 'DETERMINISTIC_MOCK', 'SYNTHETIC_QA')
    AND "model" ~ '^[A-Za-z0-9._:/-]{1,100}$'
    AND "operationVersion" ~ '^[A-Za-z0-9._:-]{1,80}$'
    AND "subjectId" ~ '^[A-Za-z0-9._:/-]{1,200}$'
    AND ("sourceLineageId" IS NULL OR "sourceLineageId" ~ '^[A-Za-z0-9._:/-]{1,200}$')
    AND ("runtimeInstanceId" IS NULL OR "runtimeInstanceId" ~ '^[A-Za-z0-9._:-]{1,128}$')
    AND ("failureCode" IS NULL OR "failureCode" ~ '^[A-Z0-9_]{1,80}$')
    AND "logicalAttempt" BETWEEN 1 AND 1000
    AND "pinnedGlobalRolloutGeneration" > 0
    AND "pinnedPracticeRolloutGeneration" > 0
  ),
  CONSTRAINT "template_twin_provider_execution_scope_operation_check" CHECK (
    ("scope" = 'SOURCE_INTAKE' AND "operation" IN
      ('SOURCE_PHI_SCAN', 'SOURCE_SEMANTIC_MAPPING'))
    OR ("scope" = 'STATIC_ASSET' AND "operation" = 'STATIC_ASSET_PRIVACY_SCAN')
    OR ("scope" = 'CUSTOM_EXAMPLE' AND "operation" = 'CUSTOM_EXAMPLE_EXTRACTION')
    OR ("scope" = 'SYNTHETIC_EVIDENCE' AND "operation" = 'SYNTHETIC_EVIDENCE_EXTRACTION')
    OR ("scope" = 'VISIT_PIPELINE' AND "operation" IN (
      'CUSTOM_CONCEPT_EXTRACTION', 'L1_TRANSCRIBE', 'L1B_TRANSCRIBE',
      'L2_SPEAKER_ROLES', 'L3_EXTRACT_ENTITIES', 'L4_GENERATE_SOAP',
      'L4_ANCHOR_VERIFY', 'L5_SELF_CRITIQUE', 'L6_POLISH',
      'L6_FIDELITY_VERIFY'
    ))
  ),
  CONSTRAINT "template_twin_provider_execution_subject_shape_check" CHECK (
    (("sourceLineageId" IS NULL) = ("sourceLineageVersion" IS NULL))
    AND (("sourceLineageId" IS NULL) = ("sourceSha256" IS NULL))
    AND ("sourceLineageVersion" IS NULL OR "sourceLineageVersion" > 0)
    AND (
      ("scope" IN ('SOURCE_INTAKE', 'VISIT_PIPELINE', 'CUSTOM_EXAMPLE')
        AND "sourceArtifactId" IS NOT NULL
        AND "compiledVersionId" IS NOT NULL
        AND "noteTemplateId" IS NOT NULL
        AND "noteTemplateVersion" IS NOT NULL
        AND "sourceLineageId" IS NOT NULL)
      OR
      ("scope" = 'STATIC_ASSET'
        AND "sourceArtifactId" IS NULL
        AND "compiledVersionId" IS NULL
        AND "noteTemplateId" IS NULL
        AND "noteTemplateVersion" IS NULL
        AND "sourceLineageId" IS NULL)
      OR
      ("scope" = 'SYNTHETIC_EVIDENCE' AND (
        ("sourceArtifactId" IS NULL AND "compiledVersionId" IS NULL
          AND "noteTemplateId" IS NULL AND "noteTemplateVersion" IS NULL
          AND "sourceLineageId" IS NULL)
        OR
        ("sourceArtifactId" IS NOT NULL AND "compiledVersionId" IS NOT NULL
          AND "noteTemplateId" IS NOT NULL
          AND "noteTemplateVersion" IS NOT NULL
          AND "sourceLineageId" IS NOT NULL)
      ))
    )
    AND ("noteTemplateVersion" IS NULL OR "noteTemplateVersion" > 0)
    AND ("scope" <> 'VISIT_PIPELINE' OR "visitId" IS NOT NULL)
    AND ("visitId" IS NULL OR "scope" IN
      ('VISIT_PIPELINE', 'SYNTHETIC_EVIDENCE'))
  ),
  CONSTRAINT "template_twin_provider_execution_release_shape_check" CHECK (
    (("releaseId" IS NULL) = ("releaseIdentitySha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeManifestSha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeInstanceId" IS NULL))
    AND ("providerMode" <> 'LIVE' OR "releaseId" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_provider_execution_payload_limit_check" CHECK (
    "resultPayload" IS NULL
    OR octet_length("resultPayload"::TEXT) <= 8388608
  ),
  CONSTRAINT "template_twin_provider_execution_state_shape_check" CHECK (
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
      AND (("invocationCount" = 0 AND "claimId" IS NULL
        AND "claimedAt" IS NULL AND "invokedAt" IS NULL)
        OR ("invocationCount" = 1 AND "claimId" IS NOT NULL
        AND "claimedAt" IS NOT NULL AND "invokedAt" IS NOT NULL))
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
  )
);

CREATE UNIQUE INDEX "template_twin_provider_execution_ownership_key"
  ON "template_twin_provider_executions"("ownershipKey");
CREATE UNIQUE INDEX "template_twin_provider_execution_idempotency_key"
  ON "template_twin_provider_executions"("idempotencyKey");
CREATE UNIQUE INDEX "template_twin_provider_execution_claim_key"
  ON "template_twin_provider_executions"("claimId");
CREATE INDEX "template_twin_provider_execution_tenant_visit_status_idx"
  ON "template_twin_provider_executions"("practiceId", "visitId", "status");
CREATE INDEX "template_twin_provider_execution_lineage_status_idx"
  ON "template_twin_provider_executions"(
    "sourceLineageId", "sourceLineageVersion", "status"
  );
CREATE INDEX "template_twin_provider_execution_artifact_status_idx"
  ON "template_twin_provider_executions"(
    "sourceArtifactId", "compiledVersionId", "status"
  );

CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  expected_runtime CHAR(64);
  expected_owner CHAR(64);
  expected_idempotency CHAR(64);
BEGIN
  expected_runtime := encode(digest(concat_ws('|',
    'template-twin-provider-runtime-v1', NEW."providerMode",
    NEW."pinnedGlobalRolloutGeneration"::TEXT,
    NEW."pinnedPracticeRolloutGeneration"::TEXT,
    COALESCE(NEW."releaseId"::TEXT, '-'),
    COALESCE(NEW."releaseIdentitySha256", '-'),
    COALESCE(NEW."runtimeManifestSha256", '-'),
    COALESCE(NEW."runtimeInstanceId", '-')
  ), 'sha256'), 'hex');
  expected_owner := encode(digest(concat_ws('|',
    'template-twin-provider-ownership-v1', NEW."practiceId",
    NEW."actorUserId", NEW."scope",
    NEW."subjectId", NEW."subjectSha256", NEW."logicalAttempt"::TEXT,
    NEW."operation", NEW."inputSha256",
    COALESCE(NEW."visitId", '-'), COALESCE(NEW."sourceArtifactId", '-'),
    COALESCE(NEW."compiledVersionId", '-'), COALESCE(NEW."noteTemplateId", '-'),
    COALESCE(NEW."noteTemplateVersion"::TEXT, '-'),
    COALESCE(NEW."sourceLineageId", '-'),
    COALESCE(NEW."sourceLineageVersion"::TEXT, '-'),
    COALESCE(NEW."sourceSha256", '-')
  ), 'sha256'), 'hex');
  expected_idempotency := encode(digest(concat_ws('|',
    'template-twin-provider-idempotency-v1', expected_owner,
    NEW."provider", NEW."providerMode", NEW."model",
    NEW."operationVersion", NEW."providerConfigurationSha256",
    expected_runtime
  ), 'sha256'), 'hex');
  IF NEW."runtimeIdentitySha256" <> expected_runtime
    OR NEW."ownershipKey" <> expected_owner
    OR NEW."idempotencyKey" <> expected_idempotency THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_IDENTITY_INVALID'
      USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'INSERT' AND NEW."status" <> 'RESERVED' THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_MUST_RESERVE_FIRST'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM "users" actor
    WHERE actor."id" = NEW."actorUserId"
      AND actor."practiceId" = NEW."practiceId"
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
      AND (
        (NEW."scope" = 'STATIC_ASSET'
          AND actor."role" IN ('ADMIN'::"UserRole", 'SUPER_ADMIN'::"UserRole"))
        OR
        (NEW."scope" <> 'STATIC_ASSET'
          AND actor."role" = 'DOCTOR'::"UserRole")
      )
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_ACTOR_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;

  IF NEW."visitId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "transcribe_visits" visit
    JOIN "users" owner ON owner."id" = visit."userId"
    WHERE visit."id" = NEW."visitId"
      AND owner."id" = NEW."actorUserId"
      AND owner."practiceId" = NEW."practiceId"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_VISIT_TENANT_MISMATCH'
      USING ERRCODE = '42501';
  END IF;

  IF NEW."scope" = 'SOURCE_INTAKE' AND (
    EXISTS (SELECT 1 FROM "template_twin_source_artifacts"
      WHERE "id" = NEW."sourceArtifactId")
    OR EXISTS (SELECT 1 FROM "template_twin_compiled_versions"
      WHERE "id" = NEW."compiledVersionId")
    OR EXISTS (SELECT 1 FROM "note_templates"
      WHERE "id" = NEW."noteTemplateId")
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLANNED_ARTIFACT_COLLISION'
      USING ERRCODE = '23505';
  END IF;

  IF (
    NEW."scope" IN ('VISIT_PIPELINE', 'CUSTOM_EXAMPLE')
    OR (NEW."scope" = 'SYNTHETIC_EVIDENCE'
      AND NEW."compiledVersionId" IS NOT NULL)
  ) AND NOT EXISTS (
    SELECT 1
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN "note_templates" template
      ON template."id" = compiled."noteTemplateId"
    JOIN "users" template_owner ON template_owner."id" = template."doctorId"
    WHERE compiled."id" = NEW."compiledVersionId"
      AND compiled."sourceArtifactId" = NEW."sourceArtifactId"
      AND compiled."noteTemplateId" = NEW."noteTemplateId"
      AND source."practiceId" = NEW."practiceId"
      AND source."lineageId" = NEW."sourceLineageId"
      AND source."lineageVersion" = NEW."sourceLineageVersion"
      AND source."sha256" = NEW."sourceSha256"
      AND template."version" = NEW."noteTemplateVersion"
      AND template_owner."practiceId" = NEW."practiceId"
      AND (NEW."scope" <> 'VISIT_PIPELINE' OR EXISTS (
        SELECT 1 FROM "transcribe_visits" visit
        WHERE visit."id" = NEW."visitId"
          AND visit."noteTemplateId" = NEW."noteTemplateId"
          AND visit."noteTemplateVersion" = NEW."noteTemplateVersion"
      ))
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_ARTIFACT_LINEAGE_MISMATCH'
      USING ERRCODE = '42501';
  END IF;

  IF TG_OP = 'UPDATE' AND ROW(
    NEW."practiceId", NEW."actorUserId", NEW."visitId", NEW."scope", NEW."operation",
    NEW."logicalAttempt", NEW."subjectId", NEW."subjectSha256",
    NEW."sourceArtifactId", NEW."compiledVersionId", NEW."noteTemplateId",
    NEW."noteTemplateVersion",
    NEW."sourceLineageId", NEW."sourceLineageVersion", NEW."sourceSha256",
    NEW."inputSha256", NEW."provider", NEW."providerMode", NEW."model",
    NEW."operationVersion", NEW."providerConfigurationSha256",
    NEW."runtimeIdentitySha256", NEW."ownershipKey", NEW."idempotencyKey",
    NEW."pinnedGlobalRolloutGeneration",
    NEW."pinnedPracticeRolloutGeneration", NEW."releaseId",
    NEW."releaseIdentitySha256", NEW."runtimeManifestSha256",
    NEW."runtimeInstanceId", NEW."reservedAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."actorUserId", OLD."visitId", OLD."scope", OLD."operation",
    OLD."logicalAttempt", OLD."subjectId", OLD."subjectSha256",
    OLD."sourceArtifactId", OLD."compiledVersionId", OLD."noteTemplateId",
    OLD."noteTemplateVersion",
    OLD."sourceLineageId", OLD."sourceLineageVersion", OLD."sourceSha256",
    OLD."inputSha256", OLD."provider", OLD."providerMode", OLD."model",
    OLD."operationVersion", OLD."providerConfigurationSha256",
    OLD."runtimeIdentitySha256", OLD."ownershipKey", OLD."idempotencyKey",
    OLD."pinnedGlobalRolloutGeneration",
    OLD."pinnedPracticeRolloutGeneration", OLD."releaseId",
    OLD."releaseIdentitySha256", OLD."runtimeManifestSha256",
    OLD."runtimeInstanceId", OLD."reservedAt", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_IDENTITY_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_transition()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW."status" = 'SUCCEEDED' AND (
    NEW."resultVersion" <> 'template-twin-provider-result-v1'
    OR NEW."resultSha256" <> encode(public.digest(
      public.template_twin_canonical_json(NEW."resultPayload"), 'sha256'
    ), 'hex')
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RESULT_INVALID'
      USING ERRCODE = '23514';
  END IF;
  IF OLD."status" IN ('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME') THEN
    IF NEW IS DISTINCT FROM OLD THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE'
        USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD."status" = 'RESERVED' AND NEW."status" = 'IN_FLIGHT' THEN
    IF OLD."claimId" IS NOT NULL OR OLD."claimedAt" IS NOT NULL
      OR NEW."claimId" IS NULL OR NEW."claimedAt" IS NULL THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF OLD."status" = 'RESERVED' AND NEW."status" = 'FAILED' THEN
    IF NEW."claimId" IS DISTINCT FROM OLD."claimId"
      OR NEW."claimedAt" IS DISTINCT FROM OLD."claimedAt" THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF OLD."status" = 'IN_FLIGHT'
    AND NEW."status" IN ('SUCCEEDED', 'FAILED', 'UNKNOWN_OUTCOME') THEN
    IF OLD."claimId" IS NULL OR OLD."claimedAt" IS NULL
      OR NEW."claimId" IS DISTINCT FROM OLD."claimId"
      OR NEW."claimedAt" IS DISTINCT FROM OLD."claimedAt" THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_CLAIM_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_TRANSITION_INVALID'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

-- Defense in depth for a LIVE claim. The application also takes the rollout
-- lock immediately before the CAS. This trigger independently proves that
-- the exact release, practice, rollout epochs, runtime instance, and complete
-- replica barrier are still current inside the same database transaction.
CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_live_claim()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW."providerMode" <> 'LIVE' OR NEW."status" <> 'IN_FLIGHT'
    OR (TG_OP = 'UPDATE' AND OLD."status" = 'IN_FLIGHT') THEN
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM public."template_twin_release_candidates" candidate
    JOIN public."template_twin_release_practices" manifest
      ON manifest."releaseId" = candidate."id"
     AND manifest."releaseIdentitySha256" = candidate."releaseIdentitySha256"
    JOIN public."template_twin_release_runtime_requirements" runtime
      ON runtime."releaseId" = candidate."id"
     AND runtime."releaseIdentitySha256" = candidate."releaseIdentitySha256"
    JOIN public."template_twin_rollout_controls" global_control
      ON global_control."id" = 'global'
    JOIN public."practices" practice
      ON practice."id" = manifest."practiceId"
    WHERE candidate."id" = NEW."releaseId"
      AND candidate."releaseIdentitySha256" = NEW."releaseIdentitySha256"
      AND candidate."runtimeManifestSha256" = NEW."runtimeManifestSha256"
      AND candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
      AND manifest."practiceId" = NEW."practiceId"
      AND runtime."instanceId" = NEW."runtimeInstanceId"
      AND global_control."enabled" = TRUE
      AND global_control."rollbackFenceState" = 'OPEN'
      AND global_control."generation" = NEW."pinnedGlobalRolloutGeneration"
      AND practice."isActive" = TRUE
      AND practice."templateTwinEnabled" = TRUE
      AND practice."templateTwinRolloutGeneration" =
        NEW."pinnedPracticeRolloutGeneration"
      AND public.template_twin_release_approvals_are_current(
        candidate."id", candidate."releaseIdentitySha256"
      )
      AND public.template_twin_release_runtime_ready(
        candidate."id", candidate."releaseIdentitySha256"
      )
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RUNTIME_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_provider_execution_10_identity_guard
BEFORE INSERT OR UPDATE ON "template_twin_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_provider_execution_guard_identity();
CREATE TRIGGER template_twin_provider_execution_20_transition_guard
BEFORE UPDATE ON "template_twin_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_provider_execution_guard_transition();
CREATE TRIGGER template_twin_provider_execution_30_live_claim_guard
BEFORE INSERT OR UPDATE ON "template_twin_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_provider_execution_guard_live_claim();

ALTER TABLE "template_twin_source_artifacts"
  ADD COLUMN "providerOwnershipEvidence" JSONB,
  ADD COLUMN "providerOwnershipSha256" CHAR(64);
ALTER TABLE "template_twin_compiled_versions"
  ADD COLUMN "providerOwnershipEvidence" JSONB,
  ADD COLUMN "providerOwnershipSha256" CHAR(64);
ALTER TABLE "template_twin_fill_manifests"
  ADD COLUMN "providerOwnershipEvidence" JSONB,
  ADD COLUMN "providerOwnershipSha256" CHAR(64);
ALTER TABLE "template_twin_static_assets"
  ADD COLUMN "providerOwnershipEvidence" JSONB,
  ADD COLUMN "providerOwnershipSha256" CHAR(64);
ALTER TABLE "template_twin_custom_example_executions"
  ADD COLUMN "providerOwnershipEvidence" JSONB,
  ADD COLUMN "providerOwnershipSha256" CHAR(64);

ALTER TABLE "template_twin_source_artifacts"
  ADD CONSTRAINT "template_twin_source_provider_ownership_pair_check" CHECK (
    ("providerOwnershipEvidence" IS NULL) = ("providerOwnershipSha256" IS NULL)
    AND ("providerOwnershipSha256" IS NULL
      OR "providerOwnershipSha256" ~ '^[0-9a-f]{64}$')
    AND ("providerOwnershipEvidence" IS NULL
      OR octet_length("providerOwnershipEvidence"::TEXT) <= 131072)
  );
ALTER TABLE "template_twin_compiled_versions"
  ADD CONSTRAINT "template_twin_compiled_provider_ownership_pair_check" CHECK (
    ("providerOwnershipEvidence" IS NULL) = ("providerOwnershipSha256" IS NULL)
    AND ("providerOwnershipSha256" IS NULL
      OR "providerOwnershipSha256" ~ '^[0-9a-f]{64}$')
    AND ("providerOwnershipEvidence" IS NULL
      OR octet_length("providerOwnershipEvidence"::TEXT) <= 131072)
  );
ALTER TABLE "template_twin_fill_manifests"
  ADD CONSTRAINT "template_twin_fill_provider_ownership_pair_check" CHECK (
    ("providerOwnershipEvidence" IS NULL) = ("providerOwnershipSha256" IS NULL)
    AND ("providerOwnershipSha256" IS NULL
      OR "providerOwnershipSha256" ~ '^[0-9a-f]{64}$')
    AND ("providerOwnershipEvidence" IS NULL
      OR octet_length("providerOwnershipEvidence"::TEXT) <= 131072)
  );
ALTER TABLE "template_twin_static_assets"
  ADD CONSTRAINT "template_twin_static_asset_provider_ownership_pair_check" CHECK (
    ("providerOwnershipEvidence" IS NULL) = ("providerOwnershipSha256" IS NULL)
    AND ("providerOwnershipSha256" IS NULL
      OR "providerOwnershipSha256" ~ '^[0-9a-f]{64}$')
    AND ("providerOwnershipEvidence" IS NULL
      OR octet_length("providerOwnershipEvidence"::TEXT) <= 131072)
  );
ALTER TABLE "template_twin_custom_example_executions"
  ADD CONSTRAINT "template_twin_custom_example_provider_ownership_pair_check" CHECK (
    ("providerOwnershipEvidence" IS NULL) = ("providerOwnershipSha256" IS NULL)
    AND ("providerOwnershipSha256" IS NULL
      OR "providerOwnershipSha256" ~ '^[0-9a-f]{64}$')
    AND ("providerOwnershipEvidence" IS NULL
      OR octet_length("providerOwnershipEvidence"::TEXT) <= 131072)
  );

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_is_valid(
  expected_practice_id TEXT,
  expected_subject_id TEXT,
  expected_subject_sha256 TEXT,
  expected_visit_id TEXT,
  expected_source_artifact_id TEXT,
  expected_compiled_version_id TEXT,
  expected_note_template_id TEXT,
  evidence JSONB,
  evidence_sha256 CHAR(64)
) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
  SELECT evidence IS NOT NULL
    AND evidence_sha256 IS NOT NULL
    AND jsonb_typeof(evidence) = 'object'
    AND evidence->>'contractVersion' =
      'template-twin-provider-ownership-receipt-v1'
    AND evidence->>'practiceId' = expected_practice_id
    AND evidence->>'subjectId' = expected_subject_id
    AND evidence->>'subjectSha256' ~ '^[0-9a-f]{64}$'
    AND (expected_subject_sha256 IS NULL
      OR evidence->>'subjectSha256' = expected_subject_sha256)
    AND (evidence->>'visitId') IS NOT DISTINCT FROM expected_visit_id
    AND (evidence->>'sourceArtifactId') IS NOT DISTINCT FROM
      expected_source_artifact_id
    AND (evidence->>'compiledVersionId') IS NOT DISTINCT FROM
      expected_compiled_version_id
    AND (evidence->>'noteTemplateId') IS NOT DISTINCT FROM
      expected_note_template_id
    AND jsonb_typeof(evidence->'executions') = 'array'
    AND jsonb_array_length(evidence->'executions') BETWEEN 1 AND 64
    AND evidence_sha256 = encode(digest(
      public.template_twin_canonical_json(evidence), 'sha256'
    ), 'hex')
    AND jsonb_array_length(evidence->'executions') = (
      SELECT count(DISTINCT item->>'executionId')
      FROM jsonb_array_elements(evidence->'executions') item
    )
    AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(evidence->'executions') item
      WHERE jsonb_typeof(item) <> 'object'
        OR item->>'executionId' IS NULL
        OR item->>'operation' IS NULL
        OR item->>'resultSha256' !~ '^[0-9a-f]{64}$'
        OR NOT EXISTS (
          SELECT 1 FROM public."template_twin_provider_executions" execution
          WHERE execution."id" = item->>'executionId'
            AND execution."practiceId" = expected_practice_id
            AND execution."subjectId" = expected_subject_id
            AND execution."subjectSha256" = evidence->>'subjectSha256'
            AND execution."visitId" IS NOT DISTINCT FROM expected_visit_id
            AND (expected_source_artifact_id IS NULL OR
              execution."sourceArtifactId" = expected_source_artifact_id)
            AND (expected_compiled_version_id IS NULL OR
              execution."compiledVersionId" = expected_compiled_version_id)
            AND (expected_note_template_id IS NULL OR
              execution."noteTemplateId" = expected_note_template_id)
            AND execution."operation" = item->>'operation'
            AND execution."status" = 'SUCCEEDED'
            AND execution."resultSha256" = item->>'resultSha256'
            AND execution."resultVersion" =
              'template-twin-provider-result-v1'
        )
    );
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_has_operation(
  evidence JSONB, expected_operation TEXT
) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM jsonb_array_elements(evidence->'executions') item
    WHERE item->>'operation' = expected_operation
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_provider_owned_artifact()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  source_row RECORD;
  input_mode TEXT;
BEGIN
  IF TG_OP = 'UPDATE' AND OLD."providerOwnershipSha256" IS NOT NULL
    AND ROW(NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256")
      IS DISTINCT FROM
      ROW(OLD."providerOwnershipEvidence", OLD."providerOwnershipSha256") THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RECEIPT_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD."providerOwnershipSha256" IS NULL
    AND NEW."providerOwnershipSha256" IS NOT NULL THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_LEGACY_PROVIDER_RECEIPT_CANNOT_ATTACH'
      USING ERRCODE = '23514';
  END IF;
  IF NEW."providerOwnershipEvidence" IS NULL
    OR NEW."providerOwnershipSha256" IS NULL THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RECEIPT_REQUIRED'
      USING ERRCODE = '23514';
  END IF;

  IF TG_TABLE_NAME = 'template_twin_source_artifacts' THEN
    IF NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."id", NEW."sha256", NULL,
      NEW."id", NULL, NULL,
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'SOURCE_PHI_SCAN'
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_SOURCE_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_compiled_versions' THEN
    SELECT source."practiceId", source."sha256" INTO source_row
    FROM "template_twin_source_artifacts" source
    WHERE source."id" = NEW."sourceArtifactId";
    IF NOT FOUND OR NOT public.template_twin_provider_receipt_is_valid(
      source_row."practiceId", NEW."sourceArtifactId", source_row."sha256", NULL,
      NEW."sourceArtifactId", NEW."id", NEW."noteTemplateId",
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'SOURCE_PHI_SCAN'
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'SOURCE_SEMANTIC_MAPPING'
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_COMPILED_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_fill_manifests' THEN
    SELECT source."id" AS "sourceArtifactId", visit."inputMode"
      INTO source_row
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN "transcribe_visits" visit ON visit."id" = NEW."visitId"
    WHERE compiled."id" = NEW."compiledVersionId"
      AND source."practiceId" = NEW."practiceId";
    IF NOT FOUND OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."visitId", NULL, NEW."visitId",
      source_row."sourceArtifactId", NEW."compiledVersionId",
      NEW."noteTemplateId", NEW."providerOwnershipEvidence",
      NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'L3_EXTRACT_ENTITIES'
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'L4_GENERATE_SOAP'
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'L5_SELF_CRITIQUE'
    ) OR (source_row."inputMode" = 'audio_upload' AND (
      NOT public.template_twin_provider_receipt_has_operation(
        NEW."providerOwnershipEvidence", 'L1_TRANSCRIBE')
      OR NOT public.template_twin_provider_receipt_has_operation(
        NEW."providerOwnershipEvidence", 'L2_SPEAKER_ROLES')
    )) OR (source_row."inputMode" = 'voice_dictation' AND
      NOT public.template_twin_provider_receipt_has_operation(
        NEW."providerOwnershipEvidence", 'L1B_TRANSCRIBE')
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_FILL_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_static_assets' THEN
    IF NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."id", NEW."sha256", NULL,
      NULL, NULL, NULL,
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'STATIC_ASSET_PRIVACY_SCAN'
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_custom_example_executions' THEN
    SELECT source."id" AS "sourceArtifactId", source."practiceId",
      compiled."noteTemplateId" INTO source_row
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    WHERE compiled."id" = NEW."compiledVersionId"
      AND source."practiceId" = NEW."practiceId";
    IF NOT FOUND OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."id", NEW."exampleEvidenceSha256", NULL,
      source_row."sourceArtifactId",
      NEW."compiledVersionId", source_row."noteTemplateId",
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_has_operation(
      NEW."providerOwnershipEvidence", 'CUSTOM_EXAMPLE_EXTRACTION'
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_CUSTOM_EXAMPLE_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_source_provider_receipt_guard
BEFORE INSERT OR UPDATE OF "providerOwnershipEvidence", "providerOwnershipSha256"
ON "template_twin_source_artifacts"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_owned_artifact();
CREATE TRIGGER template_twin_compiled_provider_receipt_guard
BEFORE INSERT OR UPDATE OF "providerOwnershipEvidence", "providerOwnershipSha256"
ON "template_twin_compiled_versions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_owned_artifact();
CREATE TRIGGER template_twin_fill_provider_receipt_guard
BEFORE INSERT OR UPDATE OF "providerOwnershipEvidence", "providerOwnershipSha256"
ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_owned_artifact();
CREATE TRIGGER template_twin_static_asset_provider_receipt_guard
BEFORE INSERT OR UPDATE OF "providerOwnershipEvidence", "providerOwnershipSha256"
ON "template_twin_static_assets"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_owned_artifact();
CREATE TRIGGER template_twin_custom_example_provider_receipt_guard
BEFORE INSERT OR UPDATE OF "providerOwnershipEvidence", "providerOwnershipSha256"
ON "template_twin_custom_example_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_owned_artifact();

REVOKE ALL ON FUNCTION template_twin_provider_execution_guard_live_claim()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_is_valid(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, CHAR(64)
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_has_operation(JSONB, TEXT)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_is_valid(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, CHAR(64)
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_has_operation(JSONB, TEXT)
  TO quillmd_runtime;
GRANT SELECT, INSERT ON "template_twin_provider_executions"
  TO quillmd_runtime;
GRANT UPDATE (
  "status", "invocationCount", "claimId", "claimedAt", "resultPayload",
  "resultSha256", "resultVersion", "failureCode", "invokedAt",
  "completedAt", "updatedAt"
) ON "template_twin_provider_executions" TO quillmd_runtime;
REVOKE DELETE, TRUNCATE ON "template_twin_provider_executions"
  FROM quillmd_runtime;

COMMENT ON TABLE "template_twin_provider_executions" IS
  'Private exact-owner ledger. resultPayload and claimId are prohibited from clients, logs, audit metadata, and screenshots.';
COMMENT ON COLUMN "template_twin_provider_executions"."claimId" IS
  'Server-only one-owner CAS token; never emit to logs, audits, or clients.';
COMMENT ON COLUMN "template_twin_provider_executions"."resultPayload" IS
  'Private provider result retained only for no-egress replay after projection contention.';

COMMIT;
