-- Template Twin authenticated synthetic staging admission.
--
-- Additive and bounded: this creates one empty table, supporting indexes, and
-- small guard triggers. It does not rewrite transcribe_visits, note_templates,
-- or any existing clinical row. Both product rollout gates remain default-off.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_RUN_CREATED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_RUN_RETRIED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_SOAP_EDITED';

CREATE TABLE "template_twin_synthetic_qa_runs" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "doctorId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "noteTemplateId" TEXT NOT NULL,
  "noteTemplateVersion" INTEGER NOT NULL,
  "requestSha256" CHAR(64) NOT NULL,
  "payloadSha256" CHAR(64) NOT NULL,
  "mode" TEXT NOT NULL,
  "fixtureVersion" TEXT NOT NULL,
  "pinnedGlobalRolloutGeneration" BIGINT NOT NULL,
  "pinnedPracticeRolloutGeneration" BIGINT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'PENDING_ENQUEUE',
  "attempt" INTEGER NOT NULL DEFAULT 0,
  "enqueuedAt" TIMESTAMPTZ(6),
  "lastRetriedAt" TIMESTAMPTZ(6),
  "workerClaimId" VARCHAR(64),
  "workerClaimedAt" TIMESTAMPTZ(6),
  "workerHeartbeatAt" TIMESTAMPTZ(6),
  "workerLeaseExpiresAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_synthetic_qa_runs_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_qa_visit_unique" UNIQUE ("visitId"),
  CONSTRAINT "template_twin_qa_request_unique"
    UNIQUE ("practiceId", "doctorId", "requestSha256"),
  CONSTRAINT "template_twin_qa_request_sha256_hex"
    CHECK ("requestSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_payload_sha256_hex"
    CHECK ("payloadSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_mode"
    CHECK ("mode" IN ('typed', 'mock_voice')),
  CONSTRAINT "template_twin_qa_fixture_version"
    CHECK (char_length(btrim("fixtureVersion")) BETWEEN 3 AND 80),
  CONSTRAINT "template_twin_qa_template_version_positive"
    CHECK ("noteTemplateVersion" > 0),
  CONSTRAINT "template_twin_qa_rollout_generations_positive" CHECK (
    "pinnedGlobalRolloutGeneration" > 0
    AND "pinnedPracticeRolloutGeneration" > 0
  ),
  CONSTRAINT "template_twin_qa_attempt_nonnegative"
    CHECK ("attempt" >= 0),
  CONSTRAINT "template_twin_qa_worker_claim_shape" CHECK (
    (
      "workerClaimId" IS NULL
      AND "workerClaimedAt" IS NULL
      AND "workerHeartbeatAt" IS NULL
      AND "workerLeaseExpiresAt" IS NULL
    )
    OR
    (
      "workerClaimId" ~ '^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$'
      AND "workerClaimedAt" IS NOT NULL
      AND "workerHeartbeatAt" IS NOT NULL
      AND "workerLeaseExpiresAt" > "workerHeartbeatAt"
      AND "workerHeartbeatAt" >= "workerClaimedAt"
    )
  ),
  CONSTRAINT "template_twin_qa_queue_state" CHECK (
    ("status" = 'PENDING_ENQUEUE' AND "enqueuedAt" IS NULL
      AND "workerClaimId" IS NULL)
    OR
    ("status" = 'ENQUEUE_FAILED' AND "attempt" > 0 AND "enqueuedAt" IS NULL
      AND "workerClaimId" IS NULL)
    OR
    ("status" = 'ENQUEUED' AND "attempt" > 0 AND "enqueuedAt" IS NOT NULL
      AND "workerClaimId" IS NULL)
    OR
    ("status" IN ('PROCESSING', 'PROCESSING_FAILED', 'COMPLETED')
      AND "attempt" > 0 AND "enqueuedAt" IS NOT NULL
      AND "workerClaimId" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_qa_practice_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_doctor_fkey" FOREIGN KEY ("doctorId")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_visit_fkey" FOREIGN KEY ("visitId")
    REFERENCES "transcribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_template_fkey" FOREIGN KEY ("noteTemplateId")
    REFERENCES "note_templates"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "template_twin_qa_practice_created_idx"
  ON "template_twin_synthetic_qa_runs"("practiceId", "createdAt");
CREATE INDEX "template_twin_qa_doctor_status_idx"
  ON "template_twin_synthetic_qa_runs"("doctorId", "status");
CREATE INDEX "template_twin_qa_template_version_idx"
  ON "template_twin_synthetic_qa_runs"("noteTemplateId", "noteTemplateVersion");

-- Database backstop for application-layer tenant/lineage checks. The run must
-- point at a visit owned by the same doctor, that visit must already pin the
-- exact immutable template version, and the compiled source must belong to the
-- same practice. No document text or encounter evidence is inspected here.
CREATE FUNCTION template_twin_assert_synthetic_qa_run_lineage()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "users" u
    JOIN "transcribe_visits" v
      ON v."id" = NEW."visitId"
     AND v."userId" = u."id"
    JOIN "transcribe_md_patients" patient
      ON patient."id" = v."patientId"
      AND patient."practiceId" = NEW."practiceId"
      AND patient."name" = 'Template Twin Synthetic QA'
      AND patient."externalId" = 'SYNTHETIC-QA-ONLY'
      AND patient."dateOfBirth" IS NULL
      AND patient."mrn" IS NULL
      AND patient."insurance" IS NULL
      AND patient."problemList" IS NULL
      AND patient."weightKg" IS NULL
      AND patient."allergies" = ARRAY[]::TEXT[]
      AND patient."deletedAt" IS NULL
    JOIN "note_templates" nt
      ON nt."id" = NEW."noteTemplateId"
     AND nt."doctorId" = u."id"
    JOIN "template_twin_compiled_versions" cv
      ON cv."noteTemplateId" = nt."id"
    JOIN "template_twin_source_artifacts" source
      ON source."id" = cv."sourceArtifactId"
    JOIN "template_twin_certifications" certification
      ON certification."compiledVersionId" = cv."id"
    WHERE u."id" = NEW."doctorId"
      AND u."practiceId" = NEW."practiceId"
      AND u."role" = 'DOCTOR'
      AND u."isActive" = true
      AND nt."templateKind" = 'template_twin_docx'
      AND nt."status" = 'active'
      AND nt."version" = NEW."noteTemplateVersion"
      AND cv."certificationStatus" = 'CERTIFIED'
      AND source."practiceId" = NEW."practiceId"
      AND source."validationStatus" = 'accepted'
      AND source."sha256" = '9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4'
      AND source."sizeBytes" = 4686
      AND v."noteTemplateId" = NEW."noteTemplateId"
      AND v."noteTemplateVersion" = NEW."noteTemplateVersion"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA tenant or lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_synthetic_qa_run_lineage_guard
BEFORE INSERT OR UPDATE OF
  "practiceId", "doctorId", "visitId", "noteTemplateId", "noteTemplateVersion"
ON "template_twin_synthetic_qa_runs"
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_synthetic_qa_run_lineage();

-- Admission identity is immutable. Queue state may advance only through the
-- reviewed state machine, and attempt is monotonic with a maximum increment of
-- one. This prevents a service-role update from rewriting evidence hashes or
-- rollout generations after a disable/re-enable epoch.
CREATE FUNCTION template_twin_guard_synthetic_qa_run_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF ROW(
    NEW."practiceId", NEW."doctorId", NEW."visitId", NEW."noteTemplateId",
    NEW."noteTemplateVersion", NEW."requestSha256", NEW."payloadSha256",
    NEW."mode", NEW."fixtureVersion", NEW."pinnedGlobalRolloutGeneration",
    NEW."pinnedPracticeRolloutGeneration", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."doctorId", OLD."visitId", OLD."noteTemplateId",
    OLD."noteTemplateVersion", OLD."requestSha256", OLD."payloadSha256",
    OLD."mode", OLD."fixtureVersion", OLD."pinnedGlobalRolloutGeneration",
    OLD."pinnedPracticeRolloutGeneration", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission identity is immutable';
  END IF;

  IF NEW."attempt" < OLD."attempt" OR NEW."attempt" > OLD."attempt" + 1 THEN
    RAISE EXCEPTION 'Template Twin synthetic QA attempt is not monotonic';
  END IF;

  IF NOT (
    (NEW."status" = OLD."status" AND NEW."attempt" = OLD."attempt")
    OR (OLD."status" = 'PENDING_ENQUEUE' AND NEW."status" = 'ENQUEUED'
        AND NEW."attempt" = 1)
    OR (OLD."status" = 'ENQUEUED' AND NEW."status" IN ('PROCESSING', 'ENQUEUE_FAILED')
        AND NEW."attempt" = OLD."attempt")
    OR (OLD."status" = 'ENQUEUED' AND NEW."status" = 'ENQUEUED'
        AND NEW."attempt" = OLD."attempt" + 1)
    OR (OLD."status" = 'PROCESSING' AND NEW."status" IN ('COMPLETED', 'PROCESSING_FAILED')
        AND NEW."attempt" = OLD."attempt")
    OR (OLD."status" IN ('ENQUEUE_FAILED', 'PROCESSING_FAILED', 'COMPLETED')
        AND NEW."status" = 'ENQUEUED'
        AND NEW."attempt" = OLD."attempt" + 1)
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA queue transition is invalid';
  END IF;

  IF OLD."status" = 'PROCESSING' AND NEW."status" = 'PROCESSING' THEN
    IF NEW."workerClaimId" = OLD."workerClaimId" THEN
      IF NEW."workerClaimedAt" IS DISTINCT FROM OLD."workerClaimedAt"
        OR NEW."workerHeartbeatAt" < OLD."workerHeartbeatAt"
        OR NEW."workerLeaseExpiresAt" <= OLD."workerLeaseExpiresAt"
      THEN
        RAISE EXCEPTION 'Template Twin synthetic QA worker heartbeat is invalid';
      END IF;
    -- CURRENT_TIMESTAMP is fixed at transaction start. A reclaim transaction
    -- may wait behind the old owner until after the lease expires, so compare
    -- against wall time at the post-lock trigger execution point.
    ELSIF OLD."workerLeaseExpiresAt" > clock_timestamp() THEN
      RAISE EXCEPTION 'Template Twin synthetic QA worker lease is still active';
    END IF;
  ELSIF NEW."status" IN ('PROCESSING_FAILED', 'COMPLETED') THEN
    IF NEW."workerClaimId" IS DISTINCT FROM OLD."workerClaimId"
      OR NEW."workerClaimedAt" IS DISTINCT FROM OLD."workerClaimedAt"
      OR NEW."workerHeartbeatAt" IS DISTINCT FROM OLD."workerHeartbeatAt"
      OR NEW."workerLeaseExpiresAt" IS DISTINCT FROM OLD."workerLeaseExpiresAt"
    THEN
      RAISE EXCEPTION 'Template Twin synthetic QA terminal worker claim changed';
    END IF;
  ELSIF NEW."status" = 'ENQUEUED' AND (
    NEW."workerClaimId" IS NOT NULL
    OR NEW."workerClaimedAt" IS NOT NULL
    OR NEW."workerHeartbeatAt" IS NOT NULL
    OR NEW."workerLeaseExpiresAt" IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA enqueued attempt has a worker claim';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_synthetic_qa_run_transition_guard
BEFORE UPDATE ON "template_twin_synthetic_qa_runs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_qa_run_transition();

-- Once a QA run exists, its visit may not be reassigned to another owner or
-- template behind the immutable admission record.
CREATE FUNCTION template_twin_guard_synthetic_qa_visit_pin()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_runs" run
    WHERE run."visitId" = OLD."id"
      AND (
        run."doctorId" <> NEW."userId"
        OR OLD."patientId" IS DISTINCT FROM NEW."patientId"
        OR run."noteTemplateId" <> NEW."noteTemplateId"
        OR run."noteTemplateVersion" <> NEW."noteTemplateVersion"
        OR OLD."patientName" IS DISTINCT FROM NEW."patientName"
        OR OLD."inputMode" IS DISTINCT FROM NEW."inputMode"
        OR OLD."rawTextInput" IS DISTINCT FROM NEW."rawTextInput"
        OR OLD."dictationAudioKey" IS DISTINCT FROM NEW."dictationAudioKey"
        OR OLD."audioMimeType" IS DISTINCT FROM NEW."audioMimeType"
        OR OLD."audioSizeBytes" IS DISTINCT FROM NEW."audioSizeBytes"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA visit provenance is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_synthetic_qa_visit_pin_guard
BEFORE UPDATE OF
  "userId", "patientId", "patientName", "inputMode", "rawTextInput",
  "dictationAudioKey", "audioMimeType", "audioSizeBytes",
  "noteTemplateId", "noteTemplateVersion"
ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_qa_visit_pin();

-- The deterministic QA patient is not a real chart. Once referenced by a QA
-- run, its tenant and all clinical identity fields remain fixed. Normal
-- patients are unaffected.
CREATE FUNCTION template_twin_guard_synthetic_qa_patient()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_runs" run
    JOIN "transcribe_visits" visit ON visit."id" = run."visitId"
    WHERE visit."patientId" = OLD."id"
  ) THEN
    IF TG_OP = 'DELETE' THEN
      RAISE EXCEPTION 'Template Twin synthetic QA patient cannot be deleted';
    END IF;
    IF ROW(
      NEW."practiceId", NEW."name", NEW."dateOfBirth", NEW."externalId",
      NEW."mrn", NEW."insurance", NEW."problemList", NEW."weightKg",
      NEW."allergies", NEW."deletedAt"
    ) IS DISTINCT FROM ROW(
      OLD."practiceId", OLD."name", OLD."dateOfBirth", OLD."externalId",
      OLD."mrn", OLD."insurance", OLD."problemList", OLD."weightKg",
      OLD."allergies", OLD."deletedAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin synthetic QA patient is immutable';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_synthetic_qa_patient_guard
BEFORE UPDATE OR DELETE ON "transcribe_md_patients"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_qa_patient();

COMMIT;
