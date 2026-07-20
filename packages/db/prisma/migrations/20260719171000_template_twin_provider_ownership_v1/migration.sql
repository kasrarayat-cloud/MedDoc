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

-- AUTH-16: one pre-certification mock-voice capability. Audio bytes remain
-- ephemeral; the immutable digest/size/MIME/object identity and a real
-- reserved synthetic visit are committed before the mock provider boundary.
ALTER TABLE "template_twin_synthetic_qa_admissions"
  ADD COLUMN "preCertificationVoiceEvidence" BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN "audioSha256" CHAR(64),
  ADD COLUMN "audioSizeBytes" INTEGER,
  ADD COLUMN "audioMimeType" VARCHAR(80),
  ADD COLUMN "audioObjectKey" VARCHAR(500);

ALTER TABLE "template_twin_synthetic_qa_admissions"
  ADD CONSTRAINT "template_twin_qa_admission_voice_evidence_shape" CHECK (
    (
      "preCertificationVoiceEvidence" = FALSE
      AND "audioSha256" IS NULL
      AND "audioSizeBytes" IS NULL
      AND "audioMimeType" IS NULL
      AND "audioObjectKey" IS NULL
    ) OR (
      "preCertificationVoiceEvidence" = TRUE
      AND "purpose" = 'VISIT'
      AND "providerMode" = 'SYNTHETIC_MOCK_VOICE'
      AND "parentAdmissionId" IS NOT NULL
      AND "payloadSha256" IS NOT NULL
      AND "attempt" = 1
      AND "audioSha256" ~ '^[0-9a-f]{64}$'
      AND "audioSizeBytes" > 0
      AND "audioMimeType" ~ '^audio/[a-z0-9.+-]{1,60}$'
      AND length("audioObjectKey") BETWEEN 1 AND 500
      AND "certificationId" IS NULL
      AND "mappingSha256" IS NULL
      AND "certifiedAt" IS NULL
      AND "phase" IN (
        'ADMITTED', 'SOURCE_VERIFIED', 'TEMPLATE_LINKED', 'VISIT_LINKED',
        'FAILED', 'REVOKED'
      )
    )
  );

ALTER TABLE "template_twin_synthetic_qa_admissions"
  DROP CONSTRAINT "template_twin_qa_admission_phase_evidence";
ALTER TABLE "template_twin_synthetic_qa_admissions"
  ADD CONSTRAINT "template_twin_qa_admission_phase_evidence" CHECK (
    ("phase" IN ('ADMITTED', 'FAILED', 'REVOKED') OR "sourceArtifactId" IS NOT NULL)
    AND (
      "phase" NOT IN (
        'TEMPLATE_LINKED', 'CERTIFIED', 'VISIT_LINKED', 'PROCESSING',
        'REVIEW_READY', 'SIGNED'
      ) OR (
        "noteTemplateId" IS NOT NULL
        AND "noteTemplateVersion" IS NOT NULL
        AND "templateLinkedAt" IS NOT NULL
      )
    )
    AND (
      "phase" NOT IN ('CERTIFIED', 'VISIT_LINKED', 'PROCESSING', 'REVIEW_READY', 'SIGNED')
      OR (
        "preCertificationVoiceEvidence" = TRUE
        AND "phase" = 'VISIT_LINKED'
        AND "certificationId" IS NULL
        AND "mappingSha256" IS NULL
        AND "certifiedAt" IS NULL
      )
      OR (
        "preCertificationVoiceEvidence" = FALSE
        AND "certificationId" IS NOT NULL
        AND "mappingSha256" IS NOT NULL
        AND "certifiedAt" IS NOT NULL
      )
    )
    AND (
      "phase" NOT IN ('VISIT_LINKED', 'PROCESSING', 'REVIEW_READY', 'SIGNED')
      OR ("visitId" IS NOT NULL AND "visitLinkedAt" IS NOT NULL)
    )
    AND (("phase" = 'FAILED') = ("failedAt" IS NOT NULL AND "failureCode" IS NOT NULL))
    AND (("phase" = 'REVOKED') = ("revokedAt" IS NOT NULL))
    AND (("phase" = 'SIGNED') = ("consumedAt" IS NOT NULL))
  );

CREATE OR REPLACE FUNCTION template_twin_assert_synthetic_qa_admission_lineage()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF NEW."sourceSha256" <> '9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4'
    OR NEW."sourceSizeBytes" <> 4686 THEN
    RAISE EXCEPTION 'Template Twin synthetic QA source is not allowlisted';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM "users" actor
    WHERE actor."id" = NEW."actorId"
      AND actor."practiceId" = NEW."practiceId"
      AND actor."role" = 'DOCTOR'
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission actor mismatch';
  END IF;
  IF NEW."parentAdmissionId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "template_twin_synthetic_qa_admissions" parent
    WHERE parent."id" = NEW."parentAdmissionId"
      AND parent."practiceId" = NEW."practiceId"
      AND parent."actorId" = NEW."actorId"
      AND parent."purpose" = 'UPLOAD'
      AND parent."providerMode" = 'SYNTHETIC_LIFECYCLE'
      AND parent."sourceSha256" = NEW."sourceSha256"
      AND parent."sourceSizeBytes" = NEW."sourceSizeBytes"
      AND parent."fixtureVersion" = NEW."fixtureVersion"
      AND parent."pinnedGlobalRolloutGeneration" = NEW."pinnedGlobalRolloutGeneration"
      AND parent."pinnedPracticeRolloutGeneration" = NEW."pinnedPracticeRolloutGeneration"
      AND parent."attempt" = 1
      AND parent."failedAt" IS NULL
      AND parent."revokedAt" IS NULL
      AND parent."consumedAt" IS NULL
      AND parent."expiresAt" > clock_timestamp()
      AND parent."noteTemplateId" IS NOT DISTINCT FROM NEW."noteTemplateId"
      AND parent."noteTemplateVersion" IS NOT DISTINCT FROM NEW."noteTemplateVersion"
      AND parent."sourceArtifactId" IS NOT DISTINCT FROM NEW."sourceArtifactId"
      AND (
        (
          NEW."preCertificationVoiceEvidence" = TRUE
          AND parent."phase" = 'TEMPLATE_LINKED'
          AND parent."certificationId" IS NULL
          AND parent."mappingSha256" IS NULL
          AND parent."visitId" IS NULL
          AND parent."preCertificationVoiceEvidence" = FALSE
          AND NEW."certificationId" IS NULL
          AND NEW."mappingSha256" IS NULL
          AND NEW."attempt" = 1
        ) OR (
          NEW."preCertificationVoiceEvidence" = FALSE
          AND parent."phase" = 'CERTIFIED'
          AND parent."certificationId" IS NOT DISTINCT FROM NEW."certificationId"
          AND parent."mappingSha256" IS NOT DISTINCT FROM NEW."mappingSha256"
        )
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA parent admission mismatch';
  END IF;
  IF NEW."sourceArtifactId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "template_twin_source_artifacts" source
    WHERE source."id" = NEW."sourceArtifactId"
      AND source."practiceId" = NEW."practiceId"
      AND source."sha256" = NEW."sourceSha256"
      AND source."sizeBytes" = NEW."sourceSizeBytes"
      AND source."validationStatus" = 'accepted'
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA source lineage mismatch';
  END IF;
  IF NEW."noteTemplateId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "note_templates" template
    JOIN "template_twin_compiled_versions" compiled
      ON compiled."noteTemplateId" = template."id"
    WHERE template."id" = NEW."noteTemplateId"
      AND template."doctorId" = NEW."actorId"
      AND template."version" = NEW."noteTemplateVersion"
      AND template."templateKind" = 'template_twin_docx'
      AND compiled."sourceArtifactId" = NEW."sourceArtifactId"
      AND (
        NEW."preCertificationVoiceEvidence" = FALSE
        OR compiled."certificationStatus" <> 'CERTIFIED'
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA template lineage mismatch';
  END IF;
  IF NEW."certificationId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "template_twin_certifications" certification
    JOIN "template_twin_compiled_versions" compiled
      ON compiled."id" = certification."compiledVersionId"
    WHERE certification."id" = NEW."certificationId"
      AND compiled."noteTemplateId" = NEW."noteTemplateId"
      AND certification."approvedMappingsSha256" = NEW."mappingSha256"
      AND compiled."certificationStatus" = 'CERTIFIED'
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA certification lineage mismatch';
  END IF;
  IF NEW."visitId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient ON patient."id" = visit."patientId"
    WHERE visit."id" = NEW."visitId"
      AND visit."userId" = NEW."actorId"
      AND visit."noteTemplateId" = NEW."noteTemplateId"
      AND visit."noteTemplateVersion" = NEW."noteTemplateVersion"
      AND patient."practiceId" = NEW."practiceId"
      AND patient."name" = 'Template Twin Synthetic QA'
      AND patient."externalId" = 'SYNTHETIC-QA-ONLY'
      AND patient."deletedAt" IS NULL
      AND (
        NEW."preCertificationVoiceEvidence" = FALSE
        OR (
          visit."inputMode" = 'audio_upload'
          AND visit."status" = 'QUEUED'
          AND visit."audioKey" = NEW."audioObjectKey"
          AND visit."audioMimeType" = NEW."audioMimeType"
          AND visit."audioSizeBytes" = NEW."audioSizeBytes"
          AND visit."audioUploadedAt" IS NOT NULL
          AND visit."dictationAudioKey" IS NULL
          AND visit."rawTextInput" IS NULL
          AND visit."deletedAt" IS NULL
          AND visit."archivedAt" IS NULL
          AND visit."signedAt" IS NULL
        )
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA visit lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_synthetic_qa_admission_transition()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW."phase" <> 'ADMITTED' THEN
      RAISE EXCEPTION 'Template Twin synthetic QA admission must start ADMITTED';
    END IF;
    RETURN NEW;
  END IF;
  IF ROW(
    NEW."practiceId", NEW."actorId", NEW."parentAdmissionId",
    NEW."sourceSha256", NEW."sourceSizeBytes", NEW."fixtureVersion",
    NEW."providerMode", NEW."purpose", NEW."requestSha256",
    NEW."payloadSha256", NEW."pinnedGlobalRolloutGeneration",
    NEW."pinnedPracticeRolloutGeneration", NEW."createdAt", NEW."expiresAt",
    NEW."preCertificationVoiceEvidence", NEW."audioSha256",
    NEW."audioSizeBytes", NEW."audioMimeType", NEW."audioObjectKey"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."actorId", OLD."parentAdmissionId",
    OLD."sourceSha256", OLD."sourceSizeBytes", OLD."fixtureVersion",
    OLD."providerMode", OLD."purpose", OLD."requestSha256",
    OLD."payloadSha256", OLD."pinnedGlobalRolloutGeneration",
    OLD."pinnedPracticeRolloutGeneration", OLD."createdAt", OLD."expiresAt",
    OLD."preCertificationVoiceEvidence", OLD."audioSha256",
    OLD."audioSizeBytes", OLD."audioMimeType", OLD."audioObjectKey"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission identity is immutable';
  END IF;
  IF (OLD."sourceArtifactId" IS NOT NULL AND NEW."sourceArtifactId" IS DISTINCT FROM OLD."sourceArtifactId")
    OR (OLD."noteTemplateId" IS NOT NULL AND NEW."noteTemplateId" IS DISTINCT FROM OLD."noteTemplateId")
    OR (OLD."noteTemplateVersion" IS NOT NULL AND NEW."noteTemplateVersion" IS DISTINCT FROM OLD."noteTemplateVersion")
    OR (OLD."certificationId" IS NOT NULL AND NEW."certificationId" IS DISTINCT FROM OLD."certificationId")
    OR (OLD."mappingSha256" IS NOT NULL AND NEW."mappingSha256" IS DISTINCT FROM OLD."mappingSha256")
    OR (OLD."visitId" IS NOT NULL AND NEW."visitId" IS DISTINCT FROM OLD."visitId") THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission binding is immutable';
  END IF;
  IF NEW."preCertificationVoiceEvidence" = TRUE AND NEW."attempt" <> 1 THEN
    RAISE EXCEPTION 'Template Twin synthetic voice attempt is immutable';
  END IF;
  IF NEW."attempt" < OLD."attempt" OR NEW."attempt" > OLD."attempt" + 1 THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission attempt is not monotonic';
  END IF;
  IF NOT (
    (NEW."phase" = OLD."phase" AND NEW."attempt" = OLD."attempt")
    OR (OLD."phase" = 'ADMITTED' AND NEW."phase" = 'SOURCE_VERIFIED')
    OR (OLD."phase" = 'SOURCE_VERIFIED' AND NEW."phase" = 'TEMPLATE_LINKED')
    OR (OLD."phase" = 'TEMPLATE_LINKED' AND NEW."phase" = 'CERTIFIED'
      AND NEW."preCertificationVoiceEvidence" = FALSE)
    OR (OLD."phase" = 'TEMPLATE_LINKED' AND NEW."phase" = 'VISIT_LINKED'
      AND NEW."preCertificationVoiceEvidence" = TRUE)
    OR (OLD."phase" = 'CERTIFIED' AND NEW."phase" = 'VISIT_LINKED')
    OR (OLD."phase" = 'VISIT_LINKED' AND NEW."phase" = 'PROCESSING'
      AND NEW."preCertificationVoiceEvidence" = FALSE)
    OR (OLD."phase" = 'PROCESSING' AND NEW."phase" = 'REVIEW_READY')
    OR (OLD."phase" = 'REVIEW_READY' AND NEW."phase" = 'SIGNED')
    OR (OLD."phase" = 'REVIEW_READY' AND NEW."phase" = 'VISIT_LINKED'
      AND NEW."attempt" = OLD."attempt" + 1)
    OR (OLD."phase" NOT IN ('SIGNED', 'FAILED', 'REVOKED')
      AND NEW."phase" IN ('FAILED', 'REVOKED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission transition is invalid';
  END IF;
  IF OLD."phase" IN ('SIGNED', 'FAILED', 'REVOKED') THEN
    RAISE EXCEPTION 'Template Twin synthetic QA terminal admission is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE FUNCTION template_twin_guard_pre_cert_voice_admission_removal()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF TG_OP = 'TRUNCATE' THEN
    RAISE EXCEPTION 'Template Twin synthetic voice admission is immutable';
  END IF;
  IF OLD."preCertificationVoiceEvidence" = TRUE THEN
    RAISE EXCEPTION 'Template Twin synthetic voice admission is immutable';
  END IF;
  RETURN OLD;
END;
$$;
CREATE TRIGGER template_twin_pre_cert_voice_admission_delete_guard
BEFORE DELETE ON "template_twin_synthetic_qa_admissions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_pre_cert_voice_admission_removal();
CREATE TRIGGER template_twin_pre_cert_voice_admission_truncate_guard
BEFORE TRUNCATE ON "template_twin_synthetic_qa_admissions"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_guard_pre_cert_voice_admission_removal();

CREATE FUNCTION template_twin_guard_pre_cert_voice_visit()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF TG_OP = 'TRUNCATE' THEN
    RAISE EXCEPTION 'Template Twin synthetic voice visit is immutable';
  END IF;
  IF EXISTS (
    SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
    WHERE admission."visitId" = OLD."id"
      AND admission."preCertificationVoiceEvidence" = TRUE
  ) THEN
    IF TG_OP = 'DELETE' OR NEW IS DISTINCT FROM OLD THEN
      RAISE EXCEPTION 'Template Twin synthetic voice visit is immutable';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER template_twin_pre_cert_voice_visit_update_delete_guard
BEFORE UPDATE OR DELETE ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_pre_cert_voice_visit();
CREATE TRIGGER template_twin_pre_cert_voice_visit_truncate_guard
BEFORE TRUNCATE ON "transcribe_visits"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_guard_pre_cert_voice_visit();

-- The original staging guard recognizes patients through a synthetic QA run.
-- Pre-certification voice evidence deliberately has no run, so extend that
-- same immutable identity fence to patients referenced by its admission.
CREATE OR REPLACE FUNCTION template_twin_guard_synthetic_qa_patient()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_runs" run
    JOIN "transcribe_visits" visit ON visit."id" = run."visitId"
    WHERE visit."patientId" = OLD."id"
  ) OR EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_admissions" admission
    JOIN "transcribe_visits" visit ON visit."id" = admission."visitId"
    WHERE visit."patientId" = OLD."id"
      AND admission."preCertificationVoiceEvidence" = TRUE
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

CREATE FUNCTION template_twin_guard_synthetic_qa_patient_truncate()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin synthetic QA patient is immutable';
END;
$$;
CREATE TRIGGER template_twin_synthetic_qa_patient_truncate_guard
BEFORE TRUNCATE ON "transcribe_md_patients"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_guard_synthetic_qa_patient_truncate();

CREATE TABLE "template_twin_provider_executions" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "actorUserId" TEXT NOT NULL,
  "visitId" TEXT,
  "visitInputMode" VARCHAR(40),
  "scope" VARCHAR(40) NOT NULL,
  "operation" VARCHAR(80) NOT NULL,
  "operationInstance" VARCHAR(120) NOT NULL,
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
  "syntheticAdmissionId" TEXT,
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
  CONSTRAINT "template_twin_provider_execution_synthetic_admission_fkey"
    FOREIGN KEY ("syntheticAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id")
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
      'STATIC_ASSET_PRIVACY_SCAN', 'SYNTHETIC_EVIDENCE_PRIVACY_SCAN',
      'SYNTHETIC_EVIDENCE_TRANSCRIPTION', 'SYNTHETIC_EVIDENCE_EXTRACTION',
      'CUSTOM_EXAMPLE_EXTRACTION', 'CUSTOM_CONCEPT_EXTRACTION',
      'L1_TRANSCRIBE', 'L1B_TRANSCRIBE', 'L2_SPEAKER_ROLES',
      'L3_EXTRACT_ENTITIES', 'L4_GENERATE_SOAP', 'L4_ANCHOR_VERIFY',
      'L5_SELF_CRITIQUE', 'L6_POLISH', 'L6_FIDELITY_VERIFY'
    )
    AND "provider" ~ '^[a-z0-9_-]{1,40}$'
    AND "providerMode" IN ('LIVE', 'DETERMINISTIC_MOCK', 'SYNTHETIC_QA')
    AND "model" ~ '^[A-Za-z0-9._:/-]{1,100}$'
    AND "operationVersion" ~ '^[A-Za-z0-9._:-]{1,80}$'
    AND "operationInstance" ~ '^[a-z0-9][a-z0-9._:-]{0,119}$'
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
    OR ("scope" = 'SYNTHETIC_EVIDENCE' AND "operation" IN (
      'SYNTHETIC_EVIDENCE_PRIVACY_SCAN',
      'SYNTHETIC_EVIDENCE_TRANSCRIPTION',
      'SYNTHETIC_EVIDENCE_EXTRACTION'
    ))
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
    AND ("scope" NOT IN ('SOURCE_INTAKE', 'CUSTOM_EXAMPLE', 'STATIC_ASSET')
      OR "visitId" IS NULL)
    AND ("visitId" IS NULL OR "scope" IN
      ('VISIT_PIPELINE', 'SYNTHETIC_EVIDENCE'))
    AND (("visitId" IS NULL) = ("visitInputMode" IS NULL))
    AND ("visitInputMode" IS NULL
      OR "visitInputMode" IN
        ('audio_upload', 'voice_dictation', 'text_notes'))
  ),
  CONSTRAINT "template_twin_provider_execution_release_shape_check" CHECK (
    (("releaseId" IS NULL) = ("releaseIdentitySha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeManifestSha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeInstanceId" IS NULL))
    AND ("providerMode" <> 'LIVE' OR "releaseId" IS NOT NULL)
    AND (("providerMode" = 'SYNTHETIC_QA') =
      ("syntheticAdmissionId" IS NOT NULL))
  ),
  CONSTRAINT "template_twin_provider_execution_synthetic_voice_shape_check" CHECK (
    (
      "operation" = 'SYNTHETIC_EVIDENCE_TRANSCRIPTION'
      AND "scope" = 'SYNTHETIC_EVIDENCE'
      AND "providerMode" = 'SYNTHETIC_QA'
      AND "syntheticAdmissionId" IS NOT NULL
      AND "visitId" IS NOT NULL
      AND "visitInputMode" = 'audio_upload'
      AND "logicalAttempt" = 1
      AND "operationInstance" = 'primary'
    ) OR "operation" <> 'SYNTHETIC_EVIDENCE_TRANSCRIPTION'
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
CREATE INDEX "template_twin_provider_execution_synthetic_admission_idx"
  ON "template_twin_provider_executions"("syntheticAdmissionId", "status");

-- Durable, independently authorized records for deterministic provider-plan
-- branches. These are not provider executions and can never carry a result;
-- receipt validation joins them for every NOT_APPLICABLE plan entry so caller
-- JSON alone cannot invent an omitted call.
CREATE TABLE "template_twin_provider_plan_decisions" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "actorUserId" TEXT NOT NULL,
  "visitId" TEXT NOT NULL,
  "visitInputMode" VARCHAR(40) NOT NULL,
  "scope" VARCHAR(40) NOT NULL,
  "operation" VARCHAR(80) NOT NULL,
  "operationInstance" VARCHAR(120) NOT NULL,
  "logicalAttempt" INTEGER NOT NULL,
  "subjectId" VARCHAR(200) NOT NULL,
  "subjectSha256" CHAR(64) NOT NULL,
  "sourceArtifactId" TEXT NOT NULL,
  "compiledVersionId" TEXT NOT NULL,
  "noteTemplateId" TEXT NOT NULL,
  "noteTemplateVersion" INTEGER NOT NULL,
  "sourceLineageId" TEXT NOT NULL,
  "sourceLineageVersion" INTEGER NOT NULL,
  "sourceSha256" CHAR(64) NOT NULL,
  "providerMode" VARCHAR(40) NOT NULL,
  "pinnedGlobalRolloutGeneration" BIGINT NOT NULL,
  "pinnedPracticeRolloutGeneration" BIGINT NOT NULL,
  "releaseId" UUID,
  "releaseIdentitySha256" CHAR(64),
  "runtimeManifestSha256" CHAR(64),
  "runtimeInstanceId" VARCHAR(128),
  "runtimeIdentitySha256" CHAR(64) NOT NULL,
  "syntheticAdmissionId" TEXT,
  "reasonCode" VARCHAR(80) NOT NULL,
  "ownershipKey" CHAR(64) NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_provider_plan_decisions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_provider_plan_decision_owner_key" UNIQUE ("ownershipKey"),
  CONSTRAINT "template_twin_provider_plan_decision_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_plan_decision_actor_fkey"
    FOREIGN KEY ("actorUserId") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_plan_decision_visit_fkey"
    FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_plan_decision_admission_fkey"
    FOREIGN KEY ("syntheticAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_provider_plan_decision_shape_check" CHECK (
    "scope" = 'VISIT_PIPELINE'
    AND "operation" IN (
      'CUSTOM_CONCEPT_EXTRACTION', 'L1_TRANSCRIBE', 'L1B_TRANSCRIBE',
      'L2_SPEAKER_ROLES', 'L4_ANCHOR_VERIFY', 'L6_POLISH',
      'L6_FIDELITY_VERIFY'
    )
    AND "operationInstance" ~ '^[a-z0-9][a-z0-9._:-]{0,119}$'
    AND "logicalAttempt" BETWEEN 1 AND 1000
    AND "subjectId" ~ '^[A-Za-z0-9._:/-]{1,200}$'
    AND "subjectSha256" ~ '^[0-9a-f]{64}$'
    AND "sourceLineageId" ~ '^[A-Za-z0-9._:/-]{1,200}$'
    AND "sourceLineageVersion" > 0
    AND "sourceSha256" ~ '^[0-9a-f]{64}$'
    AND "noteTemplateVersion" > 0
    AND "visitInputMode" IN
      ('audio_upload', 'voice_dictation', 'text_notes')
    AND "providerMode" IN ('LIVE', 'SYNTHETIC_QA')
    AND "pinnedGlobalRolloutGeneration" > 0
    AND "pinnedPracticeRolloutGeneration" > 0
    AND "runtimeIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "ownershipKey" ~ '^[0-9a-f]{64}$'
    AND ("releaseIdentitySha256" IS NULL
      OR "releaseIdentitySha256" ~ '^[0-9a-f]{64}$')
    AND ("runtimeManifestSha256" IS NULL
      OR "runtimeManifestSha256" ~ '^[0-9a-f]{64}$')
    AND (("releaseId" IS NULL) = ("releaseIdentitySha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeManifestSha256" IS NULL))
    AND (("releaseId" IS NULL) = ("runtimeInstanceId" IS NULL))
    AND (
      ("providerMode" = 'LIVE'
        AND "releaseId" IS NOT NULL
        AND "syntheticAdmissionId" IS NULL)
      OR
      ("providerMode" = 'SYNTHETIC_QA'
        AND "releaseId" IS NULL
        AND "syntheticAdmissionId" IS NOT NULL)
    )
    AND (
      ("operation" = 'CUSTOM_CONCEPT_EXTRACTION'
        AND "operationInstance" ~ '^spec-set-[0-9a-f]{48}$'
        AND "reasonCode" = 'NO_CERTIFIED_CUSTOM_SPECIFICATIONS')
      OR ("operation" = 'L1_TRANSCRIBE' AND (
        ("visitInputMode" = 'voice_dictation'
          AND "reasonCode" = 'INPUT_MODE_DICTATION')
        OR ("visitInputMode" = 'text_notes'
          AND "reasonCode" = 'INPUT_MODE_TEXT')
      ))
      OR ("operation" = 'L1B_TRANSCRIBE' AND (
        ("visitInputMode" = 'audio_upload'
          AND "reasonCode" = 'INPUT_MODE_CONVERSATION')
        OR ("visitInputMode" = 'text_notes'
          AND "reasonCode" = 'INPUT_MODE_TEXT')
      ))
      OR ("operation" = 'L2_SPEAKER_ROLES' AND (
        ("visitInputMode" = 'voice_dictation'
          AND "reasonCode" = 'INPUT_MODE_DICTATION')
        OR ("visitInputMode" = 'text_notes'
          AND "reasonCode" = 'INPUT_MODE_TEXT')
      ))
      OR ("operation" = 'L4_ANCHOR_VERIFY'
        AND "operationInstance" IN
          ('ensemble-pass-1', 'ensemble-pass-2', 'ensemble-pass-3')
        AND "reasonCode" IN (
          'EVIDENCE_ANCHORS_DISABLED', 'NO_ANCHORED_CLAIMS',
          'DETERMINISTIC_ANCHOR_MOCK'
        ))
      OR ("operation" = 'L6_POLISH'
        AND "operationInstance" = 'primary'
        AND "reasonCode" = 'NO_FIXABLE_CRITIQUE_WORK')
      OR ("operation" = 'L6_FIDELITY_VERIFY'
        AND "operationInstance" = 'primary'
        AND "reasonCode" IN
          ('POLISH_NOT_EXECUTED', 'EMPTY_POLISH_OUTPUT'))
    )
  )
);
CREATE INDEX "template_twin_provider_plan_decision_context_idx"
  ON "template_twin_provider_plan_decisions"(
    "practiceId", "visitId", "logicalAttempt", "operation"
  );
CREATE INDEX "template_twin_provider_plan_decision_admission_idx"
  ON "template_twin_provider_plan_decisions"("syntheticAdmissionId");

CREATE OR REPLACE FUNCTION template_twin_provider_plan_decision_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  expected_runtime CHAR(64);
  expected_owner CHAR(64);
BEGIN
  IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;
  expected_runtime := encode(public.digest(concat_ws('|',
    'template-twin-provider-runtime-v1', NEW."providerMode",
    NEW."pinnedGlobalRolloutGeneration"::TEXT,
    NEW."pinnedPracticeRolloutGeneration"::TEXT,
    COALESCE(NEW."releaseId"::TEXT, '-'),
    COALESCE(NEW."releaseIdentitySha256", '-'),
    COALESCE(NEW."runtimeManifestSha256", '-'),
    COALESCE(NEW."runtimeInstanceId", '-')
  ), 'sha256'), 'hex');
  expected_owner := encode(public.digest(concat_ws('|',
    'template-twin-provider-plan-decision-v1', NEW."practiceId",
    NEW."actorUserId", NEW."visitId", NEW."visitInputMode", NEW."scope",
    NEW."logicalAttempt"::TEXT, NEW."subjectId", NEW."subjectSha256",
    NEW."sourceArtifactId", NEW."compiledVersionId", NEW."noteTemplateId",
    NEW."noteTemplateVersion"::TEXT, NEW."sourceLineageId",
    NEW."sourceLineageVersion"::TEXT, NEW."sourceSha256",
    NEW."providerMode", NEW."operation", NEW."operationInstance",
    NEW."pinnedGlobalRolloutGeneration"::TEXT,
    NEW."pinnedPracticeRolloutGeneration"::TEXT,
    COALESCE(NEW."releaseId"::TEXT, '-'),
    COALESCE(NEW."releaseIdentitySha256", '-'),
    COALESCE(NEW."runtimeManifestSha256", '-'),
    COALESCE(NEW."runtimeInstanceId", '-'), NEW."runtimeIdentitySha256",
    COALESCE(NEW."syntheticAdmissionId", '-')
  ), 'sha256'), 'hex');
  IF NEW."runtimeIdentitySha256" <> expected_runtime
    OR NEW."ownershipKey" <> expected_owner THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IDENTITY_INVALID'
      USING ERRCODE = '23514';
  END IF;
  PERFORM 1
    FROM "users" actor
    WHERE actor."id" = NEW."actorUserId"
      AND actor."practiceId" = NEW."practiceId"
      AND actor."role" = 'DOCTOR'::"UserRole"
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    FOR SHARE OF actor;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_ACTOR_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;
  PERFORM 1
    FROM "transcribe_visits" visit
    WHERE visit."id" = NEW."visitId"
      AND visit."userId" = NEW."actorUserId"
      AND visit."inputMode" = NEW."visitInputMode"
      AND visit."deletedAt" IS NULL
      AND visit."archivedAt" IS NULL
      AND visit."noteTemplateId" = NEW."noteTemplateId"
      AND visit."noteTemplateVersion" = NEW."noteTemplateVersion"
    FOR SHARE OF visit;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_VISIT_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;
  PERFORM 1
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN "note_templates" template
      ON template."id" = compiled."noteTemplateId"
    WHERE compiled."id" = NEW."compiledVersionId"
      AND compiled."sourceArtifactId" = NEW."sourceArtifactId"
      AND compiled."noteTemplateId" = NEW."noteTemplateId"
      AND source."practiceId" = NEW."practiceId"
      AND source."lineageId" = NEW."sourceLineageId"
      AND source."lineageVersion" = NEW."sourceLineageVersion"
      AND source."sha256" = NEW."sourceSha256"
      AND source."validationStatus" = 'accepted'
      AND template."doctorId" = NEW."actorUserId"
      AND template."version" = NEW."noteTemplateVersion"
      AND template."templateKind" = 'template_twin_docx'
      AND compiled."certificationStatus" = 'CERTIFIED'
    FOR SHARE OF compiled, source, template;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_LINEAGE_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;
  IF NEW."providerMode" = 'LIVE' THEN
    IF NOT public.template_twin_live_provider_compilation_is_valid(
      NEW."compiledVersionId", NEW."actorUserId"
    ) OR NOT EXISTS (
      SELECT 1
      FROM "template_twin_certifications" certification
      WHERE certification."compiledVersionId" = NEW."compiledVersionId"
        AND certification."certifiedById" = NEW."actorUserId"
        AND certification."providerAuthorizationMode" = 'LIVE'
        AND certification."providerAuthorizationAdmissionId" IS NULL
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_COMPILATION_NOT_AUTHORIZED'
        USING ERRCODE = '42501';
    END IF;
    PERFORM 1
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
      AND global_control."generation" =
        NEW."pinnedGlobalRolloutGeneration"
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
    FOR SHARE OF candidate, manifest, runtime, global_control, practice;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED'
        USING ERRCODE = '42501';
    END IF;
  ELSIF NEW."providerMode" = 'SYNTHETIC_QA' THEN
    PERFORM 1
    FROM "template_twin_synthetic_qa_admissions" admission
    WHERE admission."id" = NEW."syntheticAdmissionId"
      AND admission."practiceId" = NEW."practiceId"
      AND admission."actorId" = NEW."actorUserId"
      AND admission."purpose" = 'VISIT'
      AND admission."providerMode" IN
        ('SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE')
      AND admission."preCertificationVoiceEvidence" = FALSE
      AND admission."phase" IN
        ('CERTIFIED', 'VISIT_LINKED', 'PROCESSING', 'REVIEW_READY')
      AND admission."visitId" = NEW."visitId"
      AND admission."sourceArtifactId" = NEW."sourceArtifactId"
      AND admission."noteTemplateId" = NEW."noteTemplateId"
      AND admission."noteTemplateVersion" = NEW."noteTemplateVersion"
      AND admission."pinnedGlobalRolloutGeneration" =
        NEW."pinnedGlobalRolloutGeneration"
      AND admission."pinnedPracticeRolloutGeneration" =
        NEW."pinnedPracticeRolloutGeneration"
      AND admission."failedAt" IS NULL
      AND admission."revokedAt" IS NULL
      AND admission."expiresAt" > CURRENT_TIMESTAMP
      AND admission."parentAdmissionId" IS NOT NULL
      AND public.template_twin_staging_provider_compilation_is_valid(
        NEW."compiledVersionId", NEW."actorUserId",
        admission."parentAdmissionId"
      )
      AND EXISTS (
        SELECT 1
        FROM "template_twin_certifications" certification
        WHERE certification."compiledVersionId" = NEW."compiledVersionId"
          AND certification."certifiedById" = NEW."actorUserId"
          AND certification."providerAuthorizationMode" = 'SYNTHETIC_QA'
          AND certification."providerAuthorizationAdmissionId" =
            admission."parentAdmissionId"
      )
    FOR SHARE OF admission;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_ADMISSION_NOT_AUTHORIZED'
        USING ERRCODE = '42501';
    END IF;
  ELSE
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_PLAN_MODE_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER template_twin_provider_plan_decision_guard_trigger
BEFORE INSERT OR UPDATE OR DELETE
ON "template_twin_provider_plan_decisions"
FOR EACH ROW EXECUTE FUNCTION template_twin_provider_plan_decision_guard();
CREATE TRIGGER template_twin_provider_plan_decision_truncate_guard_trigger
BEFORE TRUNCATE ON "template_twin_provider_plan_decisions"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_provider_plan_decision_guard();

CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_identity()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  expected_runtime CHAR(64);
  expected_owner CHAR(64);
  expected_idempotency CHAR(64);
  authority_failure_transition BOOLEAN := FALSE;
BEGIN
  authority_failure_transition := TG_OP = 'UPDATE' AND (
    (OLD."status" = 'RESERVED' AND NEW."status" = 'FAILED'
      AND NEW."failureCode" = 'AUTHORITY_REVOKED_BEFORE_PROVIDER')
    OR (OLD."status" = 'IN_FLIGHT' AND NEW."status" = 'FAILED'
      AND NEW."failureCode" = 'AUTHORITY_REVOKED_AFTER_PROVIDER')
    OR (OLD."status" = 'IN_FLIGHT' AND NEW."status" = 'UNKNOWN_OUTCOME'
      AND NEW."failureCode" IN (
        'PROVIDER_OUTCOME_UNKNOWN', 'PROVIDER_OUTCOME_AMBIGUOUS',
        'RESULT_COMMIT_AMBIGUOUS', 'AUTHORITY_REVOKED_AFTER_PROVIDER'
      ))
  );
  expected_runtime := encode(public.digest(concat_ws('|',
    'template-twin-provider-runtime-v1', NEW."providerMode",
    NEW."pinnedGlobalRolloutGeneration"::TEXT,
    NEW."pinnedPracticeRolloutGeneration"::TEXT,
    COALESCE(NEW."releaseId"::TEXT, '-'),
    COALESCE(NEW."releaseIdentitySha256", '-'),
    COALESCE(NEW."runtimeManifestSha256", '-'),
    COALESCE(NEW."runtimeInstanceId", '-')
  ), 'sha256'), 'hex');
  expected_owner := encode(public.digest(concat_ws('|',
    'template-twin-provider-ownership-v2', NEW."practiceId",
    NEW."scope", NEW."subjectId", NEW."logicalAttempt"::TEXT,
    NEW."operation", NEW."operationInstance"
  ), 'sha256'), 'hex');
  expected_idempotency := encode(public.digest(concat_ws('|',
    'template-twin-provider-idempotency-v2', expected_owner,
    NEW."actorUserId", NEW."subjectSha256", NEW."inputSha256",
    NEW."provider", NEW."providerMode", NEW."model",
    NEW."operationVersion", NEW."providerConfigurationSha256",
    expected_runtime,
    COALESCE(NEW."visitId", '-'), COALESCE(NEW."visitInputMode", '-'),
    COALESCE(NEW."sourceArtifactId", '-'),
    COALESCE(NEW."compiledVersionId", '-'), COALESCE(NEW."noteTemplateId", '-'),
    COALESCE(NEW."noteTemplateVersion"::TEXT, '-'),
    COALESCE(NEW."sourceLineageId", '-'),
    COALESCE(NEW."sourceLineageVersion"::TEXT, '-'),
    COALESCE(NEW."sourceSha256", '-'),
    COALESCE(NEW."syntheticAdmissionId", '-')
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

  IF NOT authority_failure_transition AND NOT EXISTS (
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

  IF NOT authority_failure_transition
    AND NEW."providerMode" = 'SYNTHETIC_QA' AND NOT EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_admissions" admission
    LEFT JOIN "template_twin_synthetic_qa_admissions" parent
      ON parent."id" = admission."parentAdmissionId"
    LEFT JOIN "transcribe_visits" synthetic_visit
      ON synthetic_visit."id" = admission."visitId"
    LEFT JOIN "transcribe_md_patients" synthetic_patient
      ON synthetic_patient."id" = synthetic_visit."patientId"
    LEFT JOIN "template_twin_compiled_versions" synthetic_compiled
      ON synthetic_compiled."id" = NEW."compiledVersionId"
    LEFT JOIN "template_twin_source_artifacts" synthetic_source
      ON synthetic_source."id" = synthetic_compiled."sourceArtifactId"
    LEFT JOIN "note_templates" synthetic_template
      ON synthetic_template."id" = synthetic_compiled."noteTemplateId"
    WHERE admission."id" = NEW."syntheticAdmissionId"
      AND admission."practiceId" = NEW."practiceId"
      AND admission."actorId" = NEW."actorUserId"
      AND admission."revokedAt" IS NULL
      AND admission."failedAt" IS NULL
      AND admission."expiresAt" > CURRENT_TIMESTAMP
      AND admission."pinnedGlobalRolloutGeneration" =
        NEW."pinnedGlobalRolloutGeneration"
      AND admission."pinnedPracticeRolloutGeneration" =
        NEW."pinnedPracticeRolloutGeneration"
      AND (
        (
          admission."preCertificationVoiceEvidence" = TRUE
          AND NEW."scope" = 'SYNTHETIC_EVIDENCE'
          AND NEW."operation" = 'SYNTHETIC_EVIDENCE_TRANSCRIPTION'
          AND NEW."operationInstance" = 'primary'
          AND NEW."logicalAttempt" = 1
          AND NEW."subjectId" = admission."id"
          AND NEW."visitId" = admission."visitId"
          AND NEW."visitInputMode" = 'audio_upload'
          AND admission."purpose" = 'VISIT'
          AND admission."providerMode" = 'SYNTHETIC_MOCK_VOICE'
          AND admission."phase" = 'VISIT_LINKED'
          AND admission."attempt" = 1
          AND admission."certificationId" IS NULL
          AND admission."mappingSha256" IS NULL
          AND admission."consumedAt" IS NULL
          AND admission."sourceArtifactId" = NEW."sourceArtifactId"
          AND admission."noteTemplateId" = NEW."noteTemplateId"
          AND admission."noteTemplateVersion" = NEW."noteTemplateVersion"
          AND admission."audioSha256" ~ '^[0-9a-f]{64}$'
          AND admission."audioSizeBytes" > 0
          AND admission."audioMimeType" = synthetic_visit."audioMimeType"
          AND admission."audioSizeBytes" = synthetic_visit."audioSizeBytes"
          AND admission."audioObjectKey" = synthetic_visit."audioKey"
          AND parent."practiceId" = admission."practiceId"
          AND parent."actorId" = admission."actorId"
          AND parent."purpose" = 'UPLOAD'
          AND parent."providerMode" = 'SYNTHETIC_LIFECYCLE'
          AND parent."preCertificationVoiceEvidence" = FALSE
          AND parent."phase" = 'TEMPLATE_LINKED'
          AND parent."sourceArtifactId" = admission."sourceArtifactId"
          AND parent."noteTemplateId" = admission."noteTemplateId"
          AND parent."noteTemplateVersion" = admission."noteTemplateVersion"
          AND parent."certificationId" IS NULL
          AND parent."mappingSha256" IS NULL
          AND parent."visitId" IS NULL
          AND parent."failedAt" IS NULL
          AND parent."revokedAt" IS NULL
          AND parent."consumedAt" IS NULL
          AND parent."expiresAt" > CURRENT_TIMESTAMP
          AND parent."pinnedGlobalRolloutGeneration" =
            admission."pinnedGlobalRolloutGeneration"
          AND parent."pinnedPracticeRolloutGeneration" =
            admission."pinnedPracticeRolloutGeneration"
          AND synthetic_visit."userId" = admission."actorId"
          AND synthetic_visit."inputMode" = 'audio_upload'
          AND synthetic_visit."status" = 'QUEUED'
          AND synthetic_visit."noteTemplateId" = admission."noteTemplateId"
          AND synthetic_visit."noteTemplateVersion" =
            admission."noteTemplateVersion"
          AND synthetic_visit."rawTextInput" IS NULL
          AND synthetic_visit."dictationAudioKey" IS NULL
          AND synthetic_visit."deletedAt" IS NULL
          AND synthetic_visit."archivedAt" IS NULL
          AND synthetic_visit."signedAt" IS NULL
          AND synthetic_patient."practiceId" = admission."practiceId"
          AND synthetic_patient."name" = 'Template Twin Synthetic QA'
          AND synthetic_patient."externalId" = 'SYNTHETIC-QA-ONLY'
          AND synthetic_patient."dateOfBirth" IS NULL
          AND synthetic_patient."mrn" IS NULL
          AND synthetic_patient."insurance" IS NULL
          AND synthetic_patient."problemList" IS NULL
          AND synthetic_patient."weightKg" IS NULL
          AND cardinality(synthetic_patient."allergies") = 0
          AND synthetic_patient."deletedAt" IS NULL
          AND synthetic_compiled."sourceArtifactId" = NEW."sourceArtifactId"
          AND synthetic_compiled."noteTemplateId" = NEW."noteTemplateId"
          AND synthetic_compiled."certificationStatus" <> 'CERTIFIED'
          AND synthetic_source."practiceId" = NEW."practiceId"
          AND synthetic_source."validationStatus" = 'accepted'
          AND synthetic_source."lineageId" = NEW."sourceLineageId"
          AND synthetic_source."lineageVersion" = NEW."sourceLineageVersion"
          AND synthetic_source."sha256" = NEW."sourceSha256"
          AND synthetic_template."doctorId" = NEW."actorUserId"
          AND synthetic_template."version" = NEW."noteTemplateVersion"
          AND synthetic_template."templateKind" = 'template_twin_docx'
          AND NEW."subjectSha256" = encode(public.digest(
            public.template_twin_canonical_json(jsonb_build_object(
              'contractVersion', 'template-twin-synthetic-voice-subject-v1',
              'admissionId', admission."id",
              'parentAdmissionId', parent."id",
              'practiceId', admission."practiceId",
              'actorUserId', admission."actorId",
              'visitId', admission."visitId",
              'inputMode', 'audio_upload',
              'audioSha256', admission."audioSha256",
              'audioSizeBytes', admission."audioSizeBytes",
              'audioMimeType', admission."audioMimeType",
              'audioObjectKey', admission."audioObjectKey",
              'sourceArtifactId', admission."sourceArtifactId",
              'compiledVersionId', synthetic_compiled."id",
              'noteTemplateId', admission."noteTemplateId",
              'noteTemplateVersion', admission."noteTemplateVersion",
              'sourceLineageId', synthetic_source."lineageId",
              'sourceLineageVersion', synthetic_source."lineageVersion",
              'sourceSha256', synthetic_source."sha256",
              'logicalAttempt', 1
            )), 'sha256'
          ), 'hex')
        ) OR (
          NEW."operation" <> 'SYNTHETIC_EVIDENCE_TRANSCRIPTION'
          AND admission."preCertificationVoiceEvidence" = FALSE
          AND (NEW."visitId" IS NULL OR admission."visitId" = NEW."visitId")
          AND (
            (NEW."scope" = 'SOURCE_INTAKE'
              AND admission."purpose" = 'UPLOAD'
              AND admission."providerMode" = 'SYNTHETIC_LIFECYCLE'
              AND admission."phase" = 'ADMITTED'
              AND admission."visitId" IS NULL
              AND admission."fixtureVersion" =
                'template-twin-staging-safe-docx/1.0.0')
            OR
            (NEW."scope" <> 'SOURCE_INTAKE'
              AND admission."purpose" = 'VISIT'
              AND admission."providerMode" IN
                ('SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE')
              AND admission."phase" IN
                ('CERTIFIED', 'VISIT_LINKED', 'PROCESSING', 'REVIEW_READY'))
          )
          AND (admission."sourceArtifactId" IS NULL
            OR admission."sourceArtifactId" = NEW."sourceArtifactId")
          AND (admission."noteTemplateId" IS NULL
            OR admission."noteTemplateId" = NEW."noteTemplateId")
          AND (admission."noteTemplateVersion" IS NULL
            OR admission."noteTemplateVersion" = NEW."noteTemplateVersion")
        )
      )
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID'
      USING ERRCODE = '42501';
  END IF;

  IF NOT authority_failure_transition
    AND NEW."visitId" IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM "transcribe_visits" visit
    JOIN "users" owner ON owner."id" = visit."userId"
    WHERE visit."id" = NEW."visitId"
      AND owner."id" = NEW."actorUserId"
      AND owner."practiceId" = NEW."practiceId"
      AND visit."inputMode" = NEW."visitInputMode"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_VISIT_TENANT_MISMATCH'
      USING ERRCODE = '42501';
  END IF;

  IF NOT authority_failure_transition AND NEW."scope" = 'SOURCE_INTAKE' AND (
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

  IF NOT authority_failure_transition AND (
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
      AND source."validationStatus" = 'accepted'
      AND template."doctorId" = NEW."actorUserId"
      AND template."version" = NEW."noteTemplateVersion"
      AND template."templateKind" = 'template_twin_docx'
      AND template_owner."practiceId" = NEW."practiceId"
      AND (NEW."scope" <> 'VISIT_PIPELINE'
        OR compiled."certificationStatus" = 'CERTIFIED')
      AND (NEW."scope" <> 'VISIT_PIPELINE' OR EXISTS (
        SELECT 1 FROM "transcribe_visits" visit
        WHERE visit."id" = NEW."visitId"
          AND visit."noteTemplateId" = NEW."noteTemplateId"
          AND visit."noteTemplateVersion" = NEW."noteTemplateVersion"
          AND visit."inputMode" = NEW."visitInputMode"
      ))
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_ARTIFACT_LINEAGE_MISMATCH'
      USING ERRCODE = '42501';
  END IF;

  IF NOT authority_failure_transition AND NEW."scope" = 'VISIT_PIPELINE'
    AND NOT EXISTS (
      SELECT 1
      FROM "template_twin_compiled_versions" compiled
      JOIN "template_twin_certifications" certification
        ON certification."compiledVersionId" = compiled."id"
      LEFT JOIN "template_twin_synthetic_qa_admissions" admission
        ON admission."id" = NEW."syntheticAdmissionId"
      WHERE compiled."id" = NEW."compiledVersionId"
        AND compiled."certificationStatus" = 'CERTIFIED'
        AND certification."certifiedById" = NEW."actorUserId"
        AND (
          (
            NEW."providerMode" = 'LIVE'
            AND certification."providerAuthorizationMode" = 'LIVE'
            AND certification."providerAuthorizationAdmissionId" IS NULL
            AND public.template_twin_live_provider_compilation_is_valid(
              NEW."compiledVersionId", NEW."actorUserId"
            )
          ) OR (
            NEW."providerMode" = 'SYNTHETIC_QA'
            AND admission."preCertificationVoiceEvidence" = FALSE
            AND admission."parentAdmissionId" IS NOT NULL
            AND certification."providerAuthorizationMode" = 'SYNTHETIC_QA'
            AND certification."providerAuthorizationAdmissionId" =
              admission."parentAdmissionId"
            AND public.template_twin_staging_provider_compilation_is_valid(
              NEW."compiledVersionId", NEW."actorUserId",
              admission."parentAdmissionId"
            )
          )
        )
    ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_COMPILATION_NOT_AUTHORIZED'
      USING ERRCODE = '42501';
  END IF;

  IF TG_OP = 'UPDATE' AND ROW(
    NEW."practiceId", NEW."actorUserId", NEW."visitId", NEW."visitInputMode",
    NEW."scope", NEW."operation",
    NEW."operationInstance",
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
    NEW."runtimeInstanceId", NEW."syntheticAdmissionId",
    NEW."reservedAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."actorUserId", OLD."visitId", OLD."visitInputMode",
    OLD."scope", OLD."operation",
    OLD."operationInstance",
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
    OLD."runtimeInstanceId", OLD."syntheticAdmissionId",
    OLD."reservedAt", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_IDENTITY_IMMUTABLE'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_transition()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
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
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE'
      USING ERRCODE = '23514';
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
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF NEW."providerMode" <> 'LIVE'
    OR NEW."status" NOT IN ('IN_FLIGHT', 'SUCCEEDED')
    OR (TG_OP = 'UPDATE' AND OLD."status" = NEW."status") THEN
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

CREATE OR REPLACE FUNCTION template_twin_provider_execution_guard_remove()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_EXECUTION_IMMUTABLE'
    USING ERRCODE = '23514';
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
CREATE TRIGGER template_twin_provider_execution_40_delete_guard
BEFORE DELETE ON "template_twin_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_provider_execution_guard_remove();
CREATE TRIGGER template_twin_provider_execution_50_truncate_guard
BEFORE TRUNCATE ON "template_twin_provider_executions"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_provider_execution_guard_remove();

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
ALTER TABLE "template_twin_custom_example_executions"
  ADD CONSTRAINT "template_twin_custom_example_unowned_failure_shape_check"
  CHECK (
    "providerOwnershipEvidence" IS NOT NULL
    OR (
      "passed" = FALSE
      AND "resultStatus" = 'extraction_rejected'
      AND "resultFactCount" = 0
      AND "failureCode" IS NOT NULL
      AND "failureCode" ~ '^[A-Z0-9_]{1,160}$'
      AND "resultValue" = '{"value":null,"unit":null}'::JSONB
      AND "resultSummary"->>'targetPresent' = 'false'
      AND "resultSummary"->>'extractionRejected' = 'true'
    )
  ) NOT VALID;

ALTER TABLE "template_twin_certifications"
  ADD COLUMN "providerAuthorizationMode" VARCHAR(24) NOT NULL
    DEFAULT 'LEGACY_UNKNOWN',
  ADD COLUMN "providerAuthorizationAdmissionId" TEXT,
  ADD CONSTRAINT "template_twin_certification_provider_authorization_shape"
    CHECK (
      ("providerAuthorizationMode" IN ('LIVE', 'LEGACY_UNKNOWN')
        AND "providerAuthorizationAdmissionId" IS NULL)
      OR
      ("providerAuthorizationMode" = 'SYNTHETIC_QA'
        AND "providerAuthorizationAdmissionId" IS NOT NULL)
    ),
  ADD CONSTRAINT "template_twin_certification_provider_admission_fkey"
    FOREIGN KEY ("providerAuthorizationAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;
CREATE INDEX "template_twin_certification_provider_admission_idx"
  ON "template_twin_certifications"("providerAuthorizationAdmissionId");

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_is_valid(
  expected_practice_id TEXT,
  expected_actor_id TEXT,
  expected_scope TEXT,
  expected_provider_mode TEXT,
  expected_synthetic_admission_id TEXT,
  expected_subject_id TEXT,
  expected_subject_sha256 TEXT,
  expected_visit_id TEXT,
  expected_visit_input_mode TEXT,
  expected_source_artifact_id TEXT,
  expected_compiled_version_id TEXT,
  expected_note_template_id TEXT,
  expected_note_template_version INTEGER,
  expected_logical_attempt INTEGER,
  expected_source_lineage_id TEXT,
  expected_source_lineage_version INTEGER,
  expected_source_sha256 TEXT,
  evidence JSONB,
  evidence_sha256 CHAR(64)
) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT evidence IS NOT NULL
    AND evidence_sha256 IS NOT NULL
    AND jsonb_typeof(evidence) = 'object'
    AND octet_length(evidence::TEXT) <= 131072
    AND (SELECT count(*) FROM jsonb_object_keys(evidence)) = 28
    AND evidence ?& ARRAY[
      'contractVersion', 'scope', 'practiceId', 'actorUserId', 'subjectId',
      'subjectSha256', 'visitId', 'sourceArtifactId', 'compiledVersionId',
      'noteTemplateId', 'noteTemplateVersion', 'visitInputMode',
      'logicalAttempt', 'sourceLineageId', 'sourceLineageVersion',
      'sourceSha256', 'providerMode', 'pinnedGlobalRolloutGeneration',
      'pinnedPracticeRolloutGeneration', 'releaseId',
      'releaseIdentitySha256', 'runtimeManifestSha256', 'runtimeInstanceId',
      'runtimeIdentitySha256', 'syntheticAdmissionId',
      'executionPlanSha256', 'executionPlan', 'executions'
    ]
    AND evidence->>'contractVersion' =
      'template-twin-provider-ownership-receipt-v2'
    AND evidence->>'scope' = expected_scope
    AND evidence->>'practiceId' = expected_practice_id
    AND evidence->>'actorUserId' = expected_actor_id
    AND evidence->>'providerMode' = expected_provider_mode
    AND (evidence->>'syntheticAdmissionId') IS NOT DISTINCT FROM
      expected_synthetic_admission_id
    AND evidence->>'pinnedGlobalRolloutGeneration' ~ '^[1-9][0-9]*$'
    AND evidence->>'pinnedPracticeRolloutGeneration' ~ '^[1-9][0-9]*$'
    AND evidence->>'runtimeIdentitySha256' ~ '^[0-9a-f]{64}$'
    AND (
      (expected_provider_mode = 'LIVE'
        AND expected_synthetic_admission_id IS NULL
        AND evidence->>'releaseId' ~
          '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        AND evidence->>'releaseIdentitySha256' ~ '^[0-9a-f]{64}$'
        AND evidence->>'runtimeManifestSha256' ~ '^[0-9a-f]{64}$'
        AND length(evidence->>'runtimeInstanceId') BETWEEN 1 AND 128)
      OR
      (expected_provider_mode = 'SYNTHETIC_QA'
        AND expected_synthetic_admission_id IS NOT NULL)
    )
    AND evidence->>'subjectId' = expected_subject_id
    AND evidence->>'subjectSha256' ~ '^[0-9a-f]{64}$'
    AND (expected_subject_sha256 IS NULL
      OR evidence->>'subjectSha256' = expected_subject_sha256)
    AND (evidence->>'visitId') IS NOT DISTINCT FROM expected_visit_id
    AND (evidence->>'visitInputMode') IS NOT DISTINCT FROM
      expected_visit_input_mode
    AND (evidence->>'sourceArtifactId') IS NOT DISTINCT FROM
      expected_source_artifact_id
    AND (evidence->>'compiledVersionId') IS NOT DISTINCT FROM
      expected_compiled_version_id
    AND (evidence->>'noteTemplateId') IS NOT DISTINCT FROM
      expected_note_template_id
    AND (
      (expected_note_template_version IS NULL
        AND evidence->>'noteTemplateVersion' IS NULL)
      OR (expected_note_template_version IS NOT NULL
        AND evidence->>'noteTemplateVersion' ~ '^[1-9][0-9]*$'
        AND (evidence->>'noteTemplateVersion')::INTEGER =
          expected_note_template_version)
    )
    AND evidence->>'logicalAttempt' ~ '^[1-9][0-9]{0,2}$'
    AND (evidence->>'logicalAttempt')::INTEGER = expected_logical_attempt
    AND (evidence->>'sourceLineageId') IS NOT DISTINCT FROM
      expected_source_lineage_id
    AND (
      (expected_source_lineage_version IS NULL
        AND evidence->>'sourceLineageVersion' IS NULL)
      OR (expected_source_lineage_version IS NOT NULL
        AND evidence->>'sourceLineageVersion' ~ '^[1-9][0-9]*$'
        AND (evidence->>'sourceLineageVersion')::INTEGER =
          expected_source_lineage_version)
    )
    AND (evidence->>'sourceSha256') IS NOT DISTINCT FROM expected_source_sha256
    AND (expected_source_sha256 IS NULL
      OR evidence->>'sourceSha256' ~ '^[0-9a-f]{64}$')
    AND jsonb_typeof(evidence->'executionPlan') = 'array'
    AND jsonb_array_length(evidence->'executionPlan') BETWEEN 1 AND 64
    AND evidence->>'executionPlanSha256' ~ '^[0-9a-f]{64}$'
    AND jsonb_typeof(evidence->'executions') = 'array'
    AND jsonb_array_length(evidence->'executions') BETWEEN 1 AND 64
    AND evidence_sha256 = encode(public.digest(
      public.template_twin_canonical_json(evidence), 'sha256'
    ), 'hex')
    AND evidence->>'executionPlanSha256' = encode(public.digest(
      public.template_twin_canonical_json(jsonb_build_object(
        'contractVersion', 'template-twin-provider-execution-plan-v1',
        'scope', expected_scope,
        'entries', evidence->'executionPlan'
      )), 'sha256'
    ), 'hex')
    AND jsonb_array_length(evidence->'executionPlan') = (
      SELECT count(DISTINCT concat_ws(':',
        item->>'operation', item->>'operationInstance'))
      FROM jsonb_array_elements(evidence->'executionPlan') item
    )
    AND jsonb_array_length(evidence->'executions') = (
      SELECT count(DISTINCT item->>'executionId')
      FROM jsonb_array_elements(evidence->'executions') item
    )
    AND jsonb_array_length(evidence->'executions') = (
      SELECT count(DISTINCT concat_ws(':',
        item->>'operation', item->>'operationInstance'))
      FROM jsonb_array_elements(evidence->'executions') item
    )
    AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(evidence->'executionPlan')
        WITH ORDINALITY AS plan(item, ordinal)
      WHERE jsonb_typeof(item) <> 'object'
        OR (SELECT count(*) FROM jsonb_object_keys(item)) <> 4
        OR NOT item ?& ARRAY[
          'operation', 'operationInstance', 'disposition', 'reasonCode'
        ]
        OR item->>'operation' !~ '^[A-Z0-9_]{3,80}$'
        OR item->>'operationInstance' !~
          '^[a-z0-9][a-z0-9._:-]{0,119}$'
        OR item->>'disposition' NOT IN ('EXECUTED', 'NOT_APPLICABLE')
        OR (item->>'disposition' = 'EXECUTED'
          AND item->'reasonCode' <> 'null'::JSONB)
        OR (item->>'disposition' = 'NOT_APPLICABLE' AND (
          item->>'reasonCode' !~ '^[A-Z0-9_]{3,80}$'
          OR NOT EXISTS (
            SELECT 1
            FROM "template_twin_provider_plan_decisions" decision
            WHERE decision."practiceId" = expected_practice_id
              AND decision."actorUserId" = expected_actor_id
              AND decision."scope" = expected_scope
              AND decision."providerMode" = expected_provider_mode
              AND decision."syntheticAdmissionId" IS NOT DISTINCT FROM
                expected_synthetic_admission_id
              AND decision."subjectId" = expected_subject_id
              AND decision."subjectSha256" = evidence->>'subjectSha256'
              AND decision."visitId" IS NOT DISTINCT FROM expected_visit_id
              AND decision."visitInputMode" IS NOT DISTINCT FROM
                expected_visit_input_mode
              AND decision."sourceArtifactId" IS NOT DISTINCT FROM
                expected_source_artifact_id
              AND decision."compiledVersionId" IS NOT DISTINCT FROM
                expected_compiled_version_id
              AND decision."noteTemplateId" IS NOT DISTINCT FROM
                expected_note_template_id
              AND decision."noteTemplateVersion" IS NOT DISTINCT FROM
                expected_note_template_version
              AND decision."logicalAttempt" = expected_logical_attempt
              AND decision."sourceLineageId" IS NOT DISTINCT FROM
                expected_source_lineage_id
              AND decision."sourceLineageVersion" IS NOT DISTINCT FROM
                expected_source_lineage_version
              AND decision."sourceSha256" IS NOT DISTINCT FROM
                expected_source_sha256
              AND decision."operation" = item->>'operation'
              AND decision."operationInstance" = item->>'operationInstance'
              AND decision."reasonCode" = item->>'reasonCode'
              AND decision."pinnedGlobalRolloutGeneration"::TEXT =
                evidence->>'pinnedGlobalRolloutGeneration'
              AND decision."pinnedPracticeRolloutGeneration"::TEXT =
                evidence->>'pinnedPracticeRolloutGeneration'
              AND decision."releaseId"::TEXT IS NOT DISTINCT FROM
                evidence->>'releaseId'
              AND decision."releaseIdentitySha256" IS NOT DISTINCT FROM
                evidence->>'releaseIdentitySha256'
              AND decision."runtimeManifestSha256" IS NOT DISTINCT FROM
                evidence->>'runtimeManifestSha256'
              AND decision."runtimeInstanceId" IS NOT DISTINCT FROM
                evidence->>'runtimeInstanceId'
              AND decision."runtimeIdentitySha256" =
                evidence->>'runtimeIdentitySha256'
          )
        ))
    )
    AND NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(evidence->'executions') item
      WHERE jsonb_typeof(item) <> 'object'
        OR (SELECT count(*) FROM jsonb_object_keys(item)) <> 4
        OR NOT item ?& ARRAY[
          'executionId', 'operation', 'operationInstance', 'resultSha256'
        ]
        OR item->>'executionId' IS NULL
        OR item->>'operation' IS NULL
        OR item->>'operationInstance' !~
          '^[a-z0-9][a-z0-9._:-]{0,119}$'
        OR item->>'resultSha256' !~ '^[0-9a-f]{64}$'
        OR NOT EXISTS (
          SELECT 1 FROM jsonb_array_elements(evidence->'executionPlan') plan
          WHERE plan->>'operation' = item->>'operation'
            AND plan->>'operationInstance' = item->>'operationInstance'
            AND plan->>'disposition' = 'EXECUTED'
        )
        OR NOT EXISTS (
          SELECT 1 FROM public."template_twin_provider_executions" execution
          WHERE execution."id" = item->>'executionId'
            AND execution."practiceId" = expected_practice_id
            AND execution."actorUserId" = expected_actor_id
            AND execution."providerMode" = expected_provider_mode
            AND execution."scope" = expected_scope
            AND execution."syntheticAdmissionId" IS NOT DISTINCT FROM
              expected_synthetic_admission_id
            AND execution."pinnedGlobalRolloutGeneration"::TEXT =
              evidence->>'pinnedGlobalRolloutGeneration'
            AND execution."pinnedPracticeRolloutGeneration"::TEXT =
              evidence->>'pinnedPracticeRolloutGeneration'
            AND execution."releaseId"::TEXT IS NOT DISTINCT FROM
              evidence->>'releaseId'
            AND execution."releaseIdentitySha256" IS NOT DISTINCT FROM
              evidence->>'releaseIdentitySha256'
            AND execution."runtimeManifestSha256" IS NOT DISTINCT FROM
              evidence->>'runtimeManifestSha256'
            AND execution."runtimeInstanceId" IS NOT DISTINCT FROM
              evidence->>'runtimeInstanceId'
            AND execution."runtimeIdentitySha256" =
              evidence->>'runtimeIdentitySha256'
            AND execution."subjectId" = expected_subject_id
            AND execution."subjectSha256" = evidence->>'subjectSha256'
            AND execution."visitId" IS NOT DISTINCT FROM expected_visit_id
            AND execution."visitInputMode" IS NOT DISTINCT FROM
              expected_visit_input_mode
            AND execution."sourceArtifactId" IS NOT DISTINCT FROM
              expected_source_artifact_id
            AND execution."compiledVersionId" IS NOT DISTINCT FROM
              expected_compiled_version_id
            AND execution."noteTemplateId" IS NOT DISTINCT FROM
              expected_note_template_id
            AND execution."noteTemplateVersion" IS NOT DISTINCT FROM
              expected_note_template_version
            AND execution."logicalAttempt" = expected_logical_attempt
            AND execution."sourceLineageId" IS NOT DISTINCT FROM
              expected_source_lineage_id
            AND execution."sourceLineageVersion" IS NOT DISTINCT FROM
              expected_source_lineage_version
            AND execution."sourceSha256" IS NOT DISTINCT FROM
              expected_source_sha256
            AND execution."operation" = item->>'operation'
            AND execution."operationInstance" = item->>'operationInstance'
            AND execution."status" = 'SUCCEEDED'
            AND execution."resultSha256" = item->>'resultSha256'
            AND execution."resultVersion" =
              'template-twin-provider-result-v1'
        )
    )
    AND NOT EXISTS (
      SELECT 1 FROM jsonb_array_elements(evidence->'executionPlan') plan
      WHERE (plan->>'disposition' = 'EXECUTED') <>
        EXISTS (
          SELECT 1 FROM jsonb_array_elements(evidence->'executions') item
          WHERE item->>'operation' = plan->>'operation'
            AND item->>'operationInstance' = plan->>'operationInstance'
        )
    )
    AND (
      SELECT count(*)
      FROM public."template_twin_provider_executions" execution
      WHERE execution."practiceId" = expected_practice_id
        AND execution."actorUserId" = expected_actor_id
        AND execution."scope" = expected_scope
        AND execution."providerMode" = expected_provider_mode
        AND execution."syntheticAdmissionId" IS NOT DISTINCT FROM
          expected_synthetic_admission_id
        AND execution."subjectId" = expected_subject_id
        AND execution."subjectSha256" = evidence->>'subjectSha256'
        AND execution."visitId" IS NOT DISTINCT FROM expected_visit_id
        AND execution."visitInputMode" IS NOT DISTINCT FROM
          expected_visit_input_mode
        AND execution."sourceArtifactId" IS NOT DISTINCT FROM
          expected_source_artifact_id
        AND execution."compiledVersionId" IS NOT DISTINCT FROM
          expected_compiled_version_id
        AND execution."noteTemplateId" IS NOT DISTINCT FROM
          expected_note_template_id
        AND execution."noteTemplateVersion" IS NOT DISTINCT FROM
          expected_note_template_version
        AND execution."logicalAttempt" = expected_logical_attempt
        AND execution."sourceLineageId" IS NOT DISTINCT FROM
          expected_source_lineage_id
        AND execution."sourceLineageVersion" IS NOT DISTINCT FROM
          expected_source_lineage_version
        AND execution."sourceSha256" IS NOT DISTINCT FROM
          expected_source_sha256
        AND execution."pinnedGlobalRolloutGeneration"::TEXT =
          evidence->>'pinnedGlobalRolloutGeneration'
        AND execution."pinnedPracticeRolloutGeneration"::TEXT =
          evidence->>'pinnedPracticeRolloutGeneration'
        AND execution."releaseId"::TEXT IS NOT DISTINCT FROM
          evidence->>'releaseId'
        AND execution."releaseIdentitySha256" IS NOT DISTINCT FROM
          evidence->>'releaseIdentitySha256'
        AND execution."runtimeManifestSha256" IS NOT DISTINCT FROM
          evidence->>'runtimeManifestSha256'
        AND execution."runtimeInstanceId" IS NOT DISTINCT FROM
          evidence->>'runtimeInstanceId'
        AND execution."runtimeIdentitySha256" =
          evidence->>'runtimeIdentitySha256'
    ) = (
      SELECT count(*) FROM jsonb_array_elements(evidence->'executionPlan') plan
      WHERE plan->>'disposition' = 'EXECUTED'
    )
    AND (
      SELECT count(*)
      FROM public."template_twin_provider_plan_decisions" decision
      WHERE decision."practiceId" = expected_practice_id
        AND decision."actorUserId" = expected_actor_id
        AND decision."scope" = expected_scope
        AND decision."providerMode" = expected_provider_mode
        AND decision."syntheticAdmissionId" IS NOT DISTINCT FROM
          expected_synthetic_admission_id
        AND decision."subjectId" = expected_subject_id
        AND decision."subjectSha256" = evidence->>'subjectSha256'
        AND decision."visitId" IS NOT DISTINCT FROM expected_visit_id
        AND decision."visitInputMode" IS NOT DISTINCT FROM
          expected_visit_input_mode
        AND decision."sourceArtifactId" IS NOT DISTINCT FROM
          expected_source_artifact_id
        AND decision."compiledVersionId" IS NOT DISTINCT FROM
          expected_compiled_version_id
        AND decision."noteTemplateId" IS NOT DISTINCT FROM
          expected_note_template_id
        AND decision."noteTemplateVersion" IS NOT DISTINCT FROM
          expected_note_template_version
        AND decision."logicalAttempt" = expected_logical_attempt
        AND decision."sourceLineageId" IS NOT DISTINCT FROM
          expected_source_lineage_id
        AND decision."sourceLineageVersion" IS NOT DISTINCT FROM
          expected_source_lineage_version
        AND decision."sourceSha256" IS NOT DISTINCT FROM
          expected_source_sha256
        AND decision."pinnedGlobalRolloutGeneration"::TEXT =
          evidence->>'pinnedGlobalRolloutGeneration'
        AND decision."pinnedPracticeRolloutGeneration"::TEXT =
          evidence->>'pinnedPracticeRolloutGeneration'
        AND decision."releaseId"::TEXT IS NOT DISTINCT FROM
          evidence->>'releaseId'
        AND decision."releaseIdentitySha256" IS NOT DISTINCT FROM
          evidence->>'releaseIdentitySha256'
        AND decision."runtimeManifestSha256" IS NOT DISTINCT FROM
          evidence->>'runtimeManifestSha256'
        AND decision."runtimeInstanceId" IS NOT DISTINCT FROM
          evidence->>'runtimeInstanceId'
        AND decision."runtimeIdentitySha256" =
          evidence->>'runtimeIdentitySha256'
    ) = (
      SELECT count(*) FROM jsonb_array_elements(evidence->'executionPlan') plan
      WHERE plan->>'disposition' = 'NOT_APPLICABLE'
    );
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_has_operation(
  evidence JSONB, expected_operation TEXT
) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT EXISTS (
    SELECT 1 FROM jsonb_array_elements(evidence->'executionPlan') item
    WHERE item->>'operation' = expected_operation
      AND item->>'disposition' = 'EXECUTED'
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_plan_has(
  evidence JSONB, expected_operation TEXT, expected_instance TEXT,
  expected_disposition TEXT, expected_reason TEXT
) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT 1 = (
    SELECT count(*) FROM jsonb_array_elements(evidence->'executionPlan') item
    WHERE item->>'operation' = expected_operation
      AND item->>'operationInstance' = expected_instance
      AND item->>'disposition' = expected_disposition
      AND item->>'reasonCode' IS NOT DISTINCT FROM expected_reason
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_provider_receipt_plan_is_exact(
  evidence JSONB, expected_plan JSONB
) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT evidence->'executionPlan' = expected_plan;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_provider_owned_artifact()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  source_row RECORD;
  receipt_mode TEXT;
  receipt_admission_id TEXT;
  receipt_visit_id TEXT;
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
  IF TG_TABLE_NAME = 'template_twin_custom_example_executions'
    AND NEW."providerOwnershipEvidence" IS NULL
    AND NEW."providerOwnershipSha256" IS NULL
    AND to_jsonb(NEW)->>'passed' = 'false'
    AND to_jsonb(NEW)->>'resultStatus' = 'extraction_rejected'
    AND to_jsonb(NEW)->>'resultFactCount' = '0'
    AND to_jsonb(NEW)->>'failureCode' IS NOT NULL
    AND to_jsonb(NEW)->>'failureCode' ~ '^[A-Z0-9_]{1,160}$'
    AND to_jsonb(NEW)->'resultValue' =
      '{"value":null,"unit":null}'::JSONB
    AND to_jsonb(NEW)->'resultSummary'->>'targetPresent' = 'false'
    AND to_jsonb(NEW)->'resultSummary'->>'extractionRejected' = 'true' THEN
    -- Preserve the PHI-safe terminal failure/audit row. It cannot satisfy the
    -- passing-example certification contract and carries no fabricated
    -- successful provider receipt.
    RETURN NEW;
  END IF;
  IF NEW."providerOwnershipEvidence" IS NULL
    OR NEW."providerOwnershipSha256" IS NULL THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RECEIPT_REQUIRED'
      USING ERRCODE = '23514';
  END IF;
  receipt_mode := NEW."providerOwnershipEvidence"->>'providerMode';
  receipt_admission_id :=
    NEW."providerOwnershipEvidence"->>'syntheticAdmissionId';
  receipt_visit_id := NEW."providerOwnershipEvidence"->>'visitId';
  -- Ordinary production artifacts require LIVE authority. The only
  -- SYNTHETIC_QA exception is the separately admitted, byte-allowlisted
  -- staging lifecycle checked again in the exact source/compiled/fill branch.
  IF (receipt_mode = 'LIVE' AND receipt_admission_id IS NOT NULL)
    OR (receipt_mode = 'SYNTHETIC_QA' AND receipt_admission_id IS NULL)
    OR (receipt_mode = 'SYNTHETIC_QA' AND TG_TABLE_NAME NOT IN (
      'template_twin_source_artifacts', 'template_twin_compiled_versions',
      'template_twin_fill_manifests'
    ))
    OR receipt_mode NOT IN ('LIVE', 'SYNTHETIC_QA') THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_PROVIDER_RECEIPT_MODE_INVALID'
      USING ERRCODE = '23514';
  END IF;

  -- Final artifact authority is checked again under row locks. A previously
  -- valid receipt cannot authorize an INSERT after actor/product/practice,
  -- rollout/release, visit, or synthetic-admission authority is revoked.
  PERFORM 1
  FROM "users" actor
  WHERE actor."id" = NEW."providerOwnershipEvidence"->>'actorUserId'
    AND actor."practiceId" =
      NEW."providerOwnershipEvidence"->>'practiceId'
    AND actor."isActive" = TRUE
    AND actor."deactivatedAt" IS NULL
    AND actor."suspendedAt" IS NULL
    AND actor."softDeletedAt" IS NULL
    AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    AND (
      (TG_TABLE_NAME = 'template_twin_static_assets'
        AND actor."role" IN ('ADMIN'::"UserRole", 'SUPER_ADMIN'::"UserRole"))
      OR (TG_TABLE_NAME <> 'template_twin_static_assets'
        AND actor."role" = 'DOCTOR'::"UserRole")
    )
  FOR SHARE OF actor;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_ARTIFACT_ACTOR_AUTHORITY_REVOKED'
      USING ERRCODE = '42501';
  END IF;

  IF receipt_mode = 'LIVE' THEN
    PERFORM 1
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
    WHERE candidate."id"::TEXT =
        NEW."providerOwnershipEvidence"->>'releaseId'
      AND candidate."releaseIdentitySha256" =
        NEW."providerOwnershipEvidence"->>'releaseIdentitySha256'
      AND candidate."runtimeManifestSha256" =
        NEW."providerOwnershipEvidence"->>'runtimeManifestSha256'
      AND candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
      AND manifest."practiceId" =
        NEW."providerOwnershipEvidence"->>'practiceId'
      AND runtime."instanceId" =
        NEW."providerOwnershipEvidence"->>'runtimeInstanceId'
      AND global_control."enabled" = TRUE
      AND global_control."rollbackFenceState" = 'OPEN'
      AND global_control."generation"::TEXT =
        NEW."providerOwnershipEvidence"->>'pinnedGlobalRolloutGeneration'
      AND practice."isActive" = TRUE
      AND practice."templateTwinEnabled" = TRUE
      AND practice."templateTwinRolloutGeneration"::TEXT =
        NEW."providerOwnershipEvidence"->>'pinnedPracticeRolloutGeneration'
      AND public.template_twin_release_approvals_are_current(
        candidate."id", candidate."releaseIdentitySha256"
      )
      AND public.template_twin_release_runtime_ready(
        candidate."id", candidate."releaseIdentitySha256"
      )
    FOR SHARE OF candidate, manifest, runtime, global_control, practice;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_ARTIFACT_LIVE_AUTHORITY_REVOKED'
        USING ERRCODE = '42501';
    END IF;
  ELSE
    PERFORM 1
    FROM "template_twin_synthetic_qa_admissions" admission
    WHERE admission."id" = receipt_admission_id
      AND admission."practiceId" =
        NEW."providerOwnershipEvidence"->>'practiceId'
      AND admission."actorId" =
        NEW."providerOwnershipEvidence"->>'actorUserId'
      AND admission."pinnedGlobalRolloutGeneration"::TEXT =
        NEW."providerOwnershipEvidence"->>'pinnedGlobalRolloutGeneration'
      AND admission."pinnedPracticeRolloutGeneration"::TEXT =
        NEW."providerOwnershipEvidence"->>'pinnedPracticeRolloutGeneration'
      AND admission."failedAt" IS NULL
      AND admission."revokedAt" IS NULL
      AND admission."expiresAt" > CURRENT_TIMESTAMP
    FOR SHARE OF admission;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_ARTIFACT_SYNTHETIC_AUTHORITY_REVOKED'
        USING ERRCODE = '42501';
    END IF;
  END IF;

  IF receipt_visit_id IS NOT NULL THEN
    PERFORM 1
    FROM "transcribe_visits" visit
    WHERE visit."id" = receipt_visit_id
      AND visit."userId" =
        NEW."providerOwnershipEvidence"->>'actorUserId'
      AND visit."inputMode" =
        NEW."providerOwnershipEvidence"->>'visitInputMode'
      AND visit."deletedAt" IS NULL
      AND visit."archivedAt" IS NULL
      AND visit."noteTemplateId" IS NOT DISTINCT FROM
        NEW."providerOwnershipEvidence"->>'noteTemplateId'
      AND visit."noteTemplateVersion"::TEXT IS NOT DISTINCT FROM
        NEW."providerOwnershipEvidence"->>'noteTemplateVersion'
    FOR SHARE OF visit;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_ARTIFACT_VISIT_AUTHORITY_REVOKED'
        USING ERRCODE = '42501';
    END IF;
  END IF;

  IF TG_TABLE_NAME = 'template_twin_source_artifacts' THEN
    IF NEW."createdById" IS NULL
      OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."createdById", 'SOURCE_INTAKE', receipt_mode,
      receipt_admission_id,
      NEW."id", NEW."sha256", receipt_visit_id, NULL,
      NEW."id",
      NEW."providerOwnershipEvidence"->>'compiledVersionId',
      NEW."providerOwnershipEvidence"->>'noteTemplateId',
      1, 1, NEW."lineageId", NEW."lineageVersion", NEW."sha256",
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_plan_is_exact(
      NEW."providerOwnershipEvidence",
      '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
    ) OR (receipt_mode = 'LIVE' AND receipt_visit_id IS NOT NULL)
    OR (receipt_mode = 'SYNTHETIC_QA' AND NOT EXISTS (
      SELECT 1
      FROM "template_twin_synthetic_qa_admissions" admission
      JOIN "template_twin_quarantine_artifacts" quarantine
        ON quarantine."id" = NEW."quarantineArtifactId"
      WHERE admission."id" = receipt_admission_id
        AND admission."practiceId" = NEW."practiceId"
        AND admission."actorId" = NEW."createdById"
        AND admission."providerMode" = 'SYNTHETIC_LIFECYCLE'
        AND admission."purpose" = 'UPLOAD'
        AND admission."phase" = 'ADMITTED'
        AND admission."fixtureVersion" =
          'template-twin-staging-safe-docx/1.0.0'
        AND admission."sourceArtifactId" IS NULL
        AND admission."noteTemplateId" IS NULL
        AND admission."visitId" IS NULL
        AND admission."failedAt" IS NULL
        AND admission."revokedAt" IS NULL
        AND admission."expiresAt" > CURRENT_TIMESTAMP
        AND admission."pinnedGlobalRolloutGeneration"::TEXT =
          NEW."providerOwnershipEvidence"->>'pinnedGlobalRolloutGeneration'
        AND admission."pinnedPracticeRolloutGeneration"::TEXT =
          NEW."providerOwnershipEvidence"->>'pinnedPracticeRolloutGeneration'
        AND receipt_visit_id IS NULL
        AND quarantine."practiceId" = admission."practiceId"
        AND quarantine."sha256" = admission."sourceSha256"
        AND quarantine."sizeBytes" = admission."sourceSizeBytes"
        AND quarantine."status" = 'MALWARE_CLEAN'
    )) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_SOURCE_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_compiled_versions' THEN
    SELECT source."practiceId", source."sha256", source."sizeBytes",
      source."lineageId", source."lineageVersion",
      source."quarantineArtifactId", template."doctorId",
      template."version" AS "noteTemplateVersion"
      INTO source_row
    FROM "template_twin_source_artifacts" source
    JOIN "note_templates" template ON template."id" = NEW."noteTemplateId"
    WHERE source."id" = NEW."sourceArtifactId"
    FOR SHARE OF source, template;
    IF NOT FOUND OR NOT public.template_twin_provider_receipt_is_valid(
      source_row."practiceId", source_row."doctorId", 'SOURCE_INTAKE',
      receipt_mode,
      receipt_admission_id,
      NEW."sourceArtifactId", source_row."sha256", receipt_visit_id, NULL,
      NEW."sourceArtifactId", NEW."id", NEW."noteTemplateId",
      source_row."noteTemplateVersion", 1, source_row."lineageId",
      source_row."lineageVersion", source_row."sha256",
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_plan_is_exact(
      NEW."providerOwnershipEvidence",
      '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
    ) OR (receipt_mode = 'LIVE' AND receipt_visit_id IS NOT NULL)
    OR (receipt_mode = 'SYNTHETIC_QA' AND NOT EXISTS (
      SELECT 1
      FROM "template_twin_synthetic_qa_admissions" admission
      JOIN "template_twin_quarantine_artifacts" quarantine
        ON quarantine."id" = source_row."quarantineArtifactId"
      WHERE admission."id" = receipt_admission_id
        AND admission."practiceId" = source_row."practiceId"
        AND admission."actorId" = source_row."doctorId"
        AND admission."providerMode" = 'SYNTHETIC_LIFECYCLE'
        AND admission."purpose" = 'UPLOAD'
        AND admission."phase" = 'ADMITTED'
        AND admission."fixtureVersion" =
          'template-twin-staging-safe-docx/1.0.0'
        AND admission."sourceArtifactId" IS NULL
        AND admission."noteTemplateId" IS NULL
        AND admission."visitId" IS NULL
        AND admission."failedAt" IS NULL
        AND admission."revokedAt" IS NULL
        AND admission."expiresAt" > CURRENT_TIMESTAMP
        AND admission."pinnedGlobalRolloutGeneration"::TEXT =
          NEW."providerOwnershipEvidence"->>'pinnedGlobalRolloutGeneration'
        AND admission."pinnedPracticeRolloutGeneration"::TEXT =
          NEW."providerOwnershipEvidence"->>'pinnedPracticeRolloutGeneration'
        AND receipt_visit_id IS NULL
        AND quarantine."practiceId" = admission."practiceId"
        AND quarantine."sha256" = admission."sourceSha256"
        AND quarantine."sizeBytes" = admission."sourceSizeBytes"
        AND quarantine."status" IN ('MALWARE_CLEAN', 'ADMITTED')
    )) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_COMPILED_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_fill_manifests' THEN
    SELECT source."id" AS "sourceArtifactId", source."lineageId",
      source."lineageVersion", source."sha256" AS "sourceSha256",
      visit."inputMode", visit."manualRetryCount",
      visit."userId" AS "actorUserId"
      INTO source_row
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN "transcribe_visits" visit ON visit."id" = NEW."visitId"
    JOIN "note_templates" template
      ON template."id" = compiled."noteTemplateId"
    JOIN "template_twin_certifications" certification
      ON certification."compiledVersionId" = compiled."id"
    LEFT JOIN "template_twin_synthetic_qa_admissions" admission
      ON admission."id" = receipt_admission_id
    WHERE compiled."id" = NEW."compiledVersionId"
      AND compiled."certificationStatus" = 'CERTIFIED'
      AND source."practiceId" = NEW."practiceId"
      AND source."validationStatus" = 'accepted'
      AND template."id" = NEW."noteTemplateId"
      AND template."version" = NEW."noteTemplateVersion"
      AND template."doctorId" = visit."userId"
      AND template."templateKind" = 'template_twin_docx'
      AND certification."certifiedById" = visit."userId"
      AND (
        (receipt_mode = 'LIVE'
          AND certification."providerAuthorizationMode" = 'LIVE'
          AND certification."providerAuthorizationAdmissionId" IS NULL)
        OR (receipt_mode = 'SYNTHETIC_QA'
          AND admission."parentAdmissionId" IS NOT NULL
          AND certification."providerAuthorizationMode" = 'SYNTHETIC_QA'
          AND certification."providerAuthorizationAdmissionId" =
            admission."parentAdmissionId")
      )
    FOR SHARE OF compiled, source, visit, template, certification;
    IF NOT FOUND OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", source_row."actorUserId", 'VISIT_PIPELINE',
      receipt_mode,
      receipt_admission_id,
      NEW."visitId", encode(public.digest(
        public.template_twin_canonical_json(jsonb_build_object(
          'contractVersion', 'template-twin-visit-provider-subject-v1',
          'practiceId', NEW."practiceId",
          'actorUserId', source_row."actorUserId",
          'visitId', NEW."visitId",
          'noteTemplateId', NEW."noteTemplateId",
          'noteTemplateVersion', NEW."noteTemplateVersion",
          'compiledVersionId', NEW."compiledVersionId",
          'sourceArtifactId', source_row."sourceArtifactId",
          'sourceLineageId', source_row."lineageId",
          'sourceLineageVersion', source_row."lineageVersion",
          'sourceSha256', source_row."sourceSha256",
          'logicalAttempt', source_row."manualRetryCount" + 1,
          'inputMode', source_row."inputMode"
        )), 'sha256'
      ), 'hex'), NEW."visitId", source_row."inputMode",
      source_row."sourceArtifactId", NEW."compiledVersionId",
      NEW."noteTemplateId", NEW."noteTemplateVersion",
      source_row."manualRetryCount" + 1, source_row."lineageId",
      source_row."lineageVersion", source_row."sourceSha256",
      NEW."providerOwnershipEvidence",
      NEW."providerOwnershipSha256"
    ) OR jsonb_array_length(
      NEW."providerOwnershipEvidence"->'executionPlan') <> 12
    OR NOT public.template_twin_provider_receipt_plan_has(
      NEW."providerOwnershipEvidence", 'L3_EXTRACT_ENTITIES', 'primary',
      'EXECUTED', NULL)
    OR NOT public.template_twin_provider_receipt_plan_has(
      NEW."providerOwnershipEvidence", 'L4_GENERATE_SOAP', 'primary',
      'EXECUTED', NULL)
    OR NOT public.template_twin_provider_receipt_plan_has(
      NEW."providerOwnershipEvidence", 'L5_SELF_CRITIQUE', 'primary',
      'EXECUTED', NULL)
    OR (source_row."inputMode" = 'audio_upload' AND (
      NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1_TRANSCRIBE', 'primary',
        'EXECUTED', NULL)
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1B_TRANSCRIBE', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_CONVERSATION')
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L2_SPEAKER_ROLES', 'primary',
        'EXECUTED', NULL)
    )) OR (source_row."inputMode" = 'voice_dictation' AND (
      NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1_TRANSCRIBE', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_DICTATION')
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1B_TRANSCRIBE', 'primary',
        'EXECUTED', NULL)
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L2_SPEAKER_ROLES', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_DICTATION')
    )) OR (source_row."inputMode" = 'text_notes' AND (
      NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1_TRANSCRIBE', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_TEXT')
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L1B_TRANSCRIBE', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_TEXT')
      OR NOT public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L2_SPEAKER_ROLES', 'primary',
        'NOT_APPLICABLE', 'INPUT_MODE_TEXT')
    )) OR 3 <> (
      SELECT count(*)
      FROM jsonb_array_elements(
        NEW."providerOwnershipEvidence"->'executionPlan'
      ) item
      WHERE item->>'operation' = 'L4_ANCHOR_VERIFY'
        AND item->>'operationInstance' IN
          ('ensemble-pass-1', 'ensemble-pass-2', 'ensemble-pass-3')
    ) OR NOT (
      3 = (
        SELECT count(*) FROM jsonb_array_elements(
          NEW."providerOwnershipEvidence"->'executionPlan'
        ) item
        WHERE item->>'operation' = 'L4_ANCHOR_VERIFY'
          AND item->>'disposition' = 'EXECUTED'
      ) OR (
        3 = (
          SELECT count(*) FROM jsonb_array_elements(
            NEW."providerOwnershipEvidence"->'executionPlan'
          ) item
          WHERE item->>'operation' = 'L4_ANCHOR_VERIFY'
            AND item->>'disposition' = 'NOT_APPLICABLE'
        ) AND 1 = (
          SELECT count(DISTINCT item->>'reasonCode')
          FROM jsonb_array_elements(
            NEW."providerOwnershipEvidence"->'executionPlan'
          ) item
          WHERE item->>'operation' = 'L4_ANCHOR_VERIFY'
        ) AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(
            NEW."providerOwnershipEvidence"->'executionPlan'
          ) item
          WHERE item->>'operation' = 'L4_ANCHOR_VERIFY'
            AND item->>'reasonCode' IN (
              'EVIDENCE_ANCHORS_DISABLED', 'NO_ANCHORED_CLAIMS',
              'DETERMINISTIC_ANCHOR_MOCK'
            )
        )
      )
    ) OR 1 <> (
      SELECT count(*) FROM jsonb_array_elements(
        NEW."providerOwnershipEvidence"->'executionPlan'
      ) item
      WHERE item->>'operation' = 'CUSTOM_CONCEPT_EXTRACTION'
        AND item->>'operationInstance' ~ '^spec-set-[0-9a-f]{48}$'
        AND (
          (item->>'disposition' = 'EXECUTED'
            AND item->>'reasonCode' IS NULL)
          OR (item->>'disposition' = 'NOT_APPLICABLE'
            AND item->>'reasonCode' =
              'NO_CERTIFIED_CUSTOM_SPECIFICATIONS')
        )
    ) OR NOT (
      (public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L6_POLISH', 'primary',
        'EXECUTED', NULL) AND (
          public.template_twin_provider_receipt_plan_has(
            NEW."providerOwnershipEvidence", 'L6_FIDELITY_VERIFY',
            'primary', 'EXECUTED', NULL)
          OR public.template_twin_provider_receipt_plan_has(
            NEW."providerOwnershipEvidence", 'L6_FIDELITY_VERIFY',
            'primary', 'NOT_APPLICABLE', 'EMPTY_POLISH_OUTPUT')
        ))
      OR (public.template_twin_provider_receipt_plan_has(
        NEW."providerOwnershipEvidence", 'L6_POLISH', 'primary',
        'NOT_APPLICABLE', 'NO_FIXABLE_CRITIQUE_WORK')
        AND public.template_twin_provider_receipt_plan_has(
          NEW."providerOwnershipEvidence", 'L6_FIDELITY_VERIFY', 'primary',
          'NOT_APPLICABLE', 'POLISH_NOT_EXECUTED'))
    ) OR (receipt_mode = 'SYNTHETIC_QA' AND NOT EXISTS (
      SELECT 1
      FROM "template_twin_synthetic_qa_admissions" admission
      JOIN "template_twin_synthetic_qa_runs" run
        ON run."admissionId" = admission."id"
      WHERE admission."id" = receipt_admission_id
        AND admission."practiceId" = NEW."practiceId"
        AND admission."actorId" = source_row."actorUserId"
        AND admission."purpose" = 'VISIT'
        AND admission."providerMode" IN
          ('SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE')
        AND admission."phase" IN ('PROCESSING', 'REVIEW_READY')
        AND admission."visitId" = NEW."visitId"
        AND admission."sourceArtifactId" = source_row."sourceArtifactId"
        AND admission."noteTemplateId" = NEW."noteTemplateId"
        AND admission."noteTemplateVersion" = NEW."noteTemplateVersion"
        AND admission."failedAt" IS NULL
        AND admission."revokedAt" IS NULL
        AND admission."expiresAt" > CURRENT_TIMESTAMP
        AND run."practiceId" = NEW."practiceId"
        AND run."doctorId" = source_row."actorUserId"
        AND run."visitId" = NEW."visitId"
        AND run."noteTemplateId" = NEW."noteTemplateId"
        AND run."noteTemplateVersion" = NEW."noteTemplateVersion"
        AND run."status" IN ('PROCESSING', 'COMPLETED')
    )) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_FILL_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_static_assets' THEN
    IF receipt_mode <> 'LIVE' OR receipt_admission_id IS NOT NULL
      OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."createdById", 'STATIC_ASSET', 'LIVE', NULL,
      NEW."sha256", NEW."sha256", NULL, NULL,
      NULL, NULL, NULL, NULL, 1, NULL, NULL, NULL,
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR NOT public.template_twin_provider_receipt_plan_is_exact(
      NEW."providerOwnershipEvidence",
      '[{"operation":"STATIC_ASSET_PRIVACY_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
    ) THEN
      RAISE EXCEPTION 'TEMPLATE_TWIN_STATIC_ASSET_PROVIDER_RECEIPT_INVALID'
        USING ERRCODE = '23514';
    END IF;
  ELSIF TG_TABLE_NAME = 'template_twin_custom_example_executions' THEN
    SELECT source."id" AS "sourceArtifactId", source."practiceId",
      source."lineageId", source."lineageVersion",
      source."sha256" AS "sourceSha256", compiled."noteTemplateId",
      template."version" AS "noteTemplateVersion" INTO source_row
    FROM "template_twin_compiled_versions" compiled
    JOIN "template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN "note_templates" template ON template."id" = compiled."noteTemplateId"
    WHERE compiled."id" = NEW."compiledVersionId"
      AND source."practiceId" = NEW."practiceId"
      AND template."doctorId" = NEW."executedById"
    FOR SHARE OF compiled, source, template;
    IF NOT FOUND OR receipt_mode <> 'LIVE'
      OR receipt_admission_id IS NOT NULL
      OR NOT public.template_twin_provider_receipt_is_valid(
      NEW."practiceId", NEW."executedById", 'CUSTOM_EXAMPLE', 'LIVE', NULL,
      NEW."id", NEW."exampleEvidenceSha256", NULL, NULL,
      source_row."sourceArtifactId",
      NEW."compiledVersionId", source_row."noteTemplateId",
      source_row."noteTemplateVersion", 1, source_row."lineageId",
      source_row."lineageVersion", source_row."sourceSha256",
      NEW."providerOwnershipEvidence", NEW."providerOwnershipSha256"
    ) OR jsonb_array_length(
      NEW."providerOwnershipEvidence"->'executionPlan') <> 1
    OR 1 <> (
      SELECT count(*) FROM jsonb_array_elements(
        NEW."providerOwnershipEvidence"->'executionPlan'
      ) item
      WHERE item->>'operation' = 'CUSTOM_EXAMPLE_EXTRACTION'
        AND item->>'operationInstance' ~ '^spec-set-[0-9a-f]{48}$'
        AND item->>'disposition' = 'EXECUTED'
        AND item->>'reasonCode' IS NULL
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

-- Synthetic staging may exercise the exact intake path, but its provider
-- receipts can never be promoted into an ordinary physician certification.
-- Keep this as a database predicate so direct SQL and future runtime
-- regressions fail closed at the same boundary.
CREATE OR REPLACE FUNCTION template_twin_staging_provider_compilation_is_valid(
  expected_compiled_version_id TEXT,
  expected_actor_id TEXT,
  expected_admission_id TEXT
) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public."template_twin_compiled_versions" compiled
    JOIN public."template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN public."note_templates" template
      ON template."id" = compiled."noteTemplateId"
    JOIN public."template_twin_synthetic_qa_admissions" admission
      ON admission."id" = expected_admission_id
    JOIN public."template_twin_quarantine_artifacts" quarantine
      ON quarantine."id" = source."quarantineArtifactId"
    WHERE compiled."id" = expected_compiled_version_id
      AND template."doctorId" = expected_actor_id
      AND template."templateKind" = 'template_twin_docx'
      AND source."createdById" = expected_actor_id
      AND source."validationStatus" = 'accepted'
      AND admission."practiceId" = source."practiceId"
      AND admission."actorId" = expected_actor_id
      AND admission."purpose" = 'UPLOAD'
      AND admission."providerMode" = 'SYNTHETIC_LIFECYCLE'
      AND admission."phase" IN ('TEMPLATE_LINKED', 'CERTIFIED')
      AND admission."fixtureVersion" =
        'template-twin-staging-safe-docx/1.0.0'
      AND admission."sourceArtifactId" = source."id"
      AND admission."noteTemplateId" = template."id"
      AND admission."noteTemplateVersion" = template."version"
      AND admission."visitId" IS NULL
      AND admission."failedAt" IS NULL
      AND admission."revokedAt" IS NULL
      AND admission."expiresAt" > CURRENT_TIMESTAMP
      AND quarantine."practiceId" = source."practiceId"
      AND quarantine."sha256" = admission."sourceSha256"
      AND quarantine."sizeBytes" = admission."sourceSizeBytes"
      AND quarantine."status" = 'ADMITTED'
      AND source."providerOwnershipEvidence"->>'providerMode' =
        'SYNTHETIC_QA'
      AND source."providerOwnershipEvidence"->>'syntheticAdmissionId' =
        expected_admission_id
      AND source."providerOwnershipEvidence"->>'visitId' IS NULL
      AND compiled."providerOwnershipEvidence"->>'providerMode' =
        'SYNTHETIC_QA'
      AND compiled."providerOwnershipEvidence"->>'syntheticAdmissionId' =
        expected_admission_id
      AND compiled."providerOwnershipEvidence"->>'visitId' IS NULL
      AND source."providerOwnershipEvidence"->>
        'pinnedGlobalRolloutGeneration' =
        admission."pinnedGlobalRolloutGeneration"::TEXT
      AND source."providerOwnershipEvidence"->>
        'pinnedPracticeRolloutGeneration' =
        admission."pinnedPracticeRolloutGeneration"::TEXT
      AND compiled."providerOwnershipEvidence"->>
        'pinnedGlobalRolloutGeneration' =
        admission."pinnedGlobalRolloutGeneration"::TEXT
      AND compiled."providerOwnershipEvidence"->>
        'pinnedPracticeRolloutGeneration' =
        admission."pinnedPracticeRolloutGeneration"::TEXT
      AND source."providerOwnershipEvidence" =
        compiled."providerOwnershipEvidence"
      AND source."providerOwnershipSha256" =
        compiled."providerOwnershipSha256"
      AND public.template_twin_provider_receipt_is_valid(
        source."practiceId", expected_actor_id, 'SOURCE_INTAKE',
        'SYNTHETIC_QA', expected_admission_id, source."id",
        source."sha256", NULL, NULL, source."id", compiled."id",
        template."id", template."version", 1, source."lineageId",
        source."lineageVersion", source."sha256",
        source."providerOwnershipEvidence", source."providerOwnershipSha256"
      )
      AND public.template_twin_provider_receipt_plan_is_exact(
        source."providerOwnershipEvidence",
        '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
      )
      AND public.template_twin_provider_receipt_is_valid(
        source."practiceId", expected_actor_id, 'SOURCE_INTAKE',
        'SYNTHETIC_QA', expected_admission_id, source."id",
        source."sha256", NULL, NULL, source."id", compiled."id",
        template."id", template."version", 1, source."lineageId",
        source."lineageVersion", source."sha256",
        compiled."providerOwnershipEvidence",
        compiled."providerOwnershipSha256"
      )
      AND public.template_twin_provider_receipt_plan_is_exact(
        compiled."providerOwnershipEvidence",
        '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
      )
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_live_provider_compilation_is_valid(
  expected_compiled_version_id TEXT,
  expected_actor_id TEXT
) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public."template_twin_compiled_versions" compiled
    JOIN public."template_twin_source_artifacts" source
      ON source."id" = compiled."sourceArtifactId"
    JOIN public."note_templates" template
      ON template."id" = compiled."noteTemplateId"
    WHERE compiled."id" = expected_compiled_version_id
      AND template."doctorId" = expected_actor_id
      AND template."templateKind" = 'template_twin_docx'
      AND source."createdById" = expected_actor_id
      AND source."validationStatus" = 'accepted'
      AND source."providerOwnershipEvidence"->>'providerMode' = 'LIVE'
      AND source."providerOwnershipEvidence"->>'syntheticAdmissionId' IS NULL
      AND source."providerOwnershipEvidence"->>'visitId' IS NULL
      AND compiled."providerOwnershipEvidence"->>'providerMode' = 'LIVE'
      AND compiled."providerOwnershipEvidence"->>'syntheticAdmissionId' IS NULL
      AND compiled."providerOwnershipEvidence"->>'visitId' IS NULL
      AND source."providerOwnershipEvidence" =
        compiled."providerOwnershipEvidence"
      AND source."providerOwnershipSha256" =
        compiled."providerOwnershipSha256"
      AND public.template_twin_provider_receipt_is_valid(
        source."practiceId", expected_actor_id, 'SOURCE_INTAKE', 'LIVE', NULL,
        source."id", source."sha256", NULL, NULL,
        source."id", compiled."id", template."id", template."version", 1,
        source."lineageId", source."lineageVersion", source."sha256",
        source."providerOwnershipEvidence", source."providerOwnershipSha256"
      )
      AND public.template_twin_provider_receipt_plan_is_exact(
        source."providerOwnershipEvidence",
        '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
      )
      AND public.template_twin_provider_receipt_is_valid(
        source."practiceId", expected_actor_id, 'SOURCE_INTAKE', 'LIVE', NULL,
        source."id", source."sha256", NULL, NULL,
        source."id", compiled."id", template."id", template."version", 1,
        source."lineageId", source."lineageVersion", source."sha256",
        compiled."providerOwnershipEvidence",
        compiled."providerOwnershipSha256"
      )
      AND public.template_twin_provider_receipt_plan_is_exact(
        compiled."providerOwnershipEvidence",
        '[{"operation":"SOURCE_PHI_SCAN","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null},{"operation":"SOURCE_SEMANTIC_MAPPING","operationInstance":"primary","disposition":"EXECUTED","reasonCode":null}]'::JSONB
      )
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_require_live_provider_certification()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF NOT (
    (NEW."providerAuthorizationMode" = 'LIVE'
      AND NEW."providerAuthorizationAdmissionId" IS NULL
      AND public.template_twin_live_provider_compilation_is_valid(
        NEW."compiledVersionId", NEW."certifiedById"
      ))
    OR
    (NEW."providerAuthorizationMode" = 'SYNTHETIC_QA'
      AND NEW."providerAuthorizationAdmissionId" IS NOT NULL
      AND public.template_twin_staging_provider_compilation_is_valid(
        NEW."compiledVersionId", NEW."certifiedById",
        NEW."providerAuthorizationAdmissionId"
      ))
  ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_CERTIFICATION_LIVE_PROVIDER_RECEIPT_REQUIRED'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_certification_live_provider_guard
BEFORE INSERT ON "template_twin_certifications"
FOR EACH ROW EXECUTE FUNCTION template_twin_require_live_provider_certification();

CREATE OR REPLACE FUNCTION template_twin_require_live_provider_activation()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
  IF NEW."templateKind" = 'template_twin_docx' AND NEW."status" = 'active'
    AND NOT EXISTS (
      SELECT 1
      FROM public."template_twin_compiled_versions" compiled
      JOIN public."template_twin_certifications" certification
        ON certification."compiledVersionId" = compiled."id"
      WHERE compiled."noteTemplateId" = NEW."id"
        AND certification."certifiedById" = NEW."doctorId"
        AND (
          (certification."providerAuthorizationMode" = 'LIVE'
            AND certification."providerAuthorizationAdmissionId" IS NULL
            AND public.template_twin_live_provider_compilation_is_valid(
              compiled."id", NEW."doctorId"
            ))
          OR
          (certification."providerAuthorizationMode" = 'SYNTHETIC_QA'
            AND certification."providerAuthorizationAdmissionId" IS NOT NULL
            AND public.template_twin_staging_provider_compilation_is_valid(
              compiled."id", NEW."doctorId",
              certification."providerAuthorizationAdmissionId"
            ))
        )
    ) THEN
    RAISE EXCEPTION 'TEMPLATE_TWIN_ACTIVATION_LIVE_PROVIDER_RECEIPT_REQUIRED'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_active_live_provider_insert_guard
BEFORE INSERT ON "note_templates"
FOR EACH ROW EXECUTE FUNCTION template_twin_require_live_provider_activation();
CREATE TRIGGER template_twin_active_live_provider_update_guard
-- Protect the resulting active state, not only the usual draft -> active
-- transition. A direct update that converts an already-active template kind
-- or transfers its physician owner must pass the same exact LIVE predicate.
BEFORE UPDATE ON "note_templates"
FOR EACH ROW EXECUTE FUNCTION template_twin_require_live_provider_activation();

REVOKE ALL ON FUNCTION template_twin_provider_execution_guard_identity()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_assert_synthetic_qa_admission_lineage()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_synthetic_qa_admission_transition()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_pre_cert_voice_admission_removal()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_pre_cert_voice_visit()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_synthetic_qa_patient()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_synthetic_qa_patient_truncate()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_execution_guard_transition()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_execution_guard_live_claim()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_execution_guard_remove()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_plan_decision_guard()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_guard_provider_owned_artifact()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_staging_provider_compilation_is_valid(
  TEXT, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_live_provider_compilation_is_valid(
  TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_require_live_provider_certification()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_require_live_provider_activation()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_is_valid(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT,
  TEXT, TEXT, INTEGER, INTEGER, TEXT, INTEGER, TEXT, JSONB, CHAR(64)
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_has_operation(JSONB, TEXT)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_plan_has(
  JSONB, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_provider_receipt_plan_is_exact(
  JSONB, JSONB
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_is_valid(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT,
  TEXT, TEXT, INTEGER, INTEGER, TEXT, INTEGER, TEXT, JSONB, CHAR(64)
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_has_operation(JSONB, TEXT)
  TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_plan_has(
  JSONB, TEXT, TEXT, TEXT, TEXT
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_provider_receipt_plan_is_exact(
  JSONB, JSONB
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_live_provider_compilation_is_valid(
  TEXT, TEXT
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_staging_provider_compilation_is_valid(
  TEXT, TEXT, TEXT
) TO quillmd_runtime;
GRANT SELECT, INSERT ON "template_twin_provider_executions"
  TO quillmd_runtime;
GRANT SELECT, INSERT ON "template_twin_provider_plan_decisions"
  TO quillmd_runtime;
GRANT UPDATE (
  "status", "invocationCount", "claimId", "claimedAt", "resultPayload",
  "resultSha256", "resultVersion", "failureCode", "invokedAt",
  "completedAt", "updatedAt"
) ON "template_twin_provider_executions" TO quillmd_runtime;
REVOKE DELETE, TRUNCATE ON "template_twin_provider_executions"
  FROM quillmd_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON "template_twin_provider_plan_decisions"
  FROM quillmd_runtime;

COMMENT ON TABLE "template_twin_provider_executions" IS
  'Private exact-owner ledger. resultPayload and claimId are prohibited from clients, logs, audit metadata, and screenshots.';
COMMENT ON COLUMN "template_twin_provider_executions"."claimId" IS
  'Server-only one-owner CAS token; never emit to logs, audits, or clients.';
COMMENT ON COLUMN "template_twin_provider_executions"."resultPayload" IS
  'Private provider result retained only for no-egress replay after projection contention.';

COMMIT;
