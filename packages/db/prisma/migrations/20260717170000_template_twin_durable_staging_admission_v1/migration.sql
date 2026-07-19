-- Template Twin durable synthetic-QA admission.
--
-- Expand-only: creates one empty capability table and adds one nullable link
-- to the existing default-off QA run table. Existing generic templates and
-- retained prototype QA evidence are not rewritten or admitted implicitly.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_ADMISSION_CREATED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_ADMISSION_ADVANCED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_STAGING_QA_ADMISSION_FAILED';

CREATE TABLE "template_twin_synthetic_qa_admissions" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "actorId" TEXT NOT NULL,
  "parentAdmissionId" TEXT,
  "sourceSha256" CHAR(64) NOT NULL,
  "sourceSizeBytes" INTEGER NOT NULL,
  "fixtureVersion" TEXT NOT NULL,
  "providerMode" TEXT NOT NULL,
  "purpose" TEXT NOT NULL,
  "phase" TEXT NOT NULL DEFAULT 'ADMITTED',
  "requestSha256" CHAR(64) NOT NULL,
  "payloadSha256" CHAR(64),
  "pinnedGlobalRolloutGeneration" BIGINT NOT NULL,
  "pinnedPracticeRolloutGeneration" BIGINT NOT NULL,
  "sourceArtifactId" TEXT,
  "noteTemplateId" TEXT,
  "noteTemplateVersion" INTEGER,
  "certificationId" TEXT,
  "mappingSha256" CHAR(64),
  "visitId" TEXT,
  "attempt" INTEGER NOT NULL DEFAULT 1,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  "sourceVerifiedAt" TIMESTAMPTZ(6),
  "templateLinkedAt" TIMESTAMPTZ(6),
  "certifiedAt" TIMESTAMPTZ(6),
  "visitLinkedAt" TIMESTAMPTZ(6),
  "failedAt" TIMESTAMPTZ(6),
  "revokedAt" TIMESTAMPTZ(6),
  "consumedAt" TIMESTAMPTZ(6),
  "failureCode" VARCHAR(80),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_synthetic_qa_admissions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_qa_admission_request_unique"
    UNIQUE ("practiceId", "actorId", "requestSha256"),
  CONSTRAINT "template_twin_qa_admission_visit_unique" UNIQUE ("visitId"),
  CONSTRAINT "template_twin_qa_admission_source_sha_hex"
    CHECK ("sourceSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_admission_request_sha_hex"
    CHECK ("requestSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_admission_payload_sha_hex"
    CHECK ("payloadSha256" IS NULL OR "payloadSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_admission_mapping_sha_hex"
    CHECK ("mappingSha256" IS NULL OR "mappingSha256" ~ '^[a-f0-9]{64}$'),
  CONSTRAINT "template_twin_qa_admission_fixture_version"
    CHECK ("fixtureVersion" = 'template-twin-staging-safe-docx/1.0.0'),
  CONSTRAINT "template_twin_qa_admission_source_size"
    CHECK ("sourceSizeBytes" > 0 AND "sourceSizeBytes" <= 1048576),
  CONSTRAINT "template_twin_qa_admission_rollout_generations"
    CHECK (
      "pinnedGlobalRolloutGeneration" > 0
      AND "pinnedPracticeRolloutGeneration" > 0
    ),
  CONSTRAINT "template_twin_qa_admission_attempt"
    CHECK ("attempt" > 0),
  CONSTRAINT "template_twin_qa_admission_expiry"
    CHECK ("expiresAt" > "createdAt"),
  CONSTRAINT "template_twin_qa_admission_provider_mode"
    CHECK (
      "providerMode" IN (
        'SYNTHETIC_LIFECYCLE', 'SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE'
      )
    ),
  CONSTRAINT "template_twin_qa_admission_purpose"
    CHECK ("purpose" IN ('UPLOAD', 'VISIT')),
  CONSTRAINT "template_twin_qa_admission_purpose_mode"
    CHECK (
      (
        "purpose" = 'UPLOAD'
        AND "providerMode" = 'SYNTHETIC_LIFECYCLE'
        AND "parentAdmissionId" IS NULL
        AND "payloadSha256" IS NULL
      )
      OR
      (
        "purpose" = 'VISIT'
        AND "providerMode" IN ('SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE')
        AND "parentAdmissionId" IS NOT NULL
        AND "payloadSha256" IS NOT NULL
      )
    ),
  CONSTRAINT "template_twin_qa_admission_phase"
    CHECK (
      "phase" IN (
        'ADMITTED', 'SOURCE_VERIFIED', 'TEMPLATE_LINKED', 'CERTIFIED',
        'VISIT_LINKED', 'PROCESSING', 'REVIEW_READY', 'SIGNED', 'FAILED',
        'REVOKED'
      )
    ),
  CONSTRAINT "template_twin_qa_admission_template_pair"
    CHECK (
      ("noteTemplateId" IS NULL AND "noteTemplateVersion" IS NULL)
      OR
      ("noteTemplateId" IS NOT NULL AND "noteTemplateVersion" > 0)
    ),
  CONSTRAINT "template_twin_qa_admission_phase_evidence"
    CHECK (
      (
        "phase" IN ('ADMITTED', 'FAILED', 'REVOKED')
        OR "sourceArtifactId" IS NOT NULL
      )
      AND (
        "phase" NOT IN (
          'TEMPLATE_LINKED', 'CERTIFIED', 'VISIT_LINKED', 'PROCESSING',
          'REVIEW_READY', 'SIGNED'
        )
        OR (
          "noteTemplateId" IS NOT NULL
          AND "noteTemplateVersion" IS NOT NULL
          AND "templateLinkedAt" IS NOT NULL
        )
      )
      AND (
        "phase" NOT IN ('CERTIFIED', 'VISIT_LINKED', 'PROCESSING', 'REVIEW_READY', 'SIGNED')
        OR (
          "certificationId" IS NOT NULL
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
    ),
  CONSTRAINT "template_twin_qa_admission_practice_fkey" FOREIGN KEY ("practiceId")
    REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_actor_fkey" FOREIGN KEY ("actorId")
    REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_parent_fkey" FOREIGN KEY ("parentAdmissionId")
    REFERENCES "template_twin_synthetic_qa_admissions"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_source_fkey" FOREIGN KEY ("sourceArtifactId")
    REFERENCES "template_twin_source_artifacts"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_template_fkey" FOREIGN KEY ("noteTemplateId")
    REFERENCES "note_templates"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_certification_fkey" FOREIGN KEY ("certificationId")
    REFERENCES "template_twin_certifications"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_qa_admission_visit_fkey" FOREIGN KEY ("visitId")
    REFERENCES "transcribe_visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "template_twin_qa_admission_practice_phase_idx"
  ON "template_twin_synthetic_qa_admissions"("practiceId", "phase", "createdAt");
CREATE INDEX "template_twin_qa_admission_actor_phase_idx"
  ON "template_twin_synthetic_qa_admissions"("actorId", "phase", "expiresAt");
CREATE INDEX "template_twin_qa_admission_template_phase_idx"
  ON "template_twin_synthetic_qa_admissions"("noteTemplateId", "noteTemplateVersion", "phase");
CREATE INDEX "template_twin_qa_admission_parent_phase_idx"
  ON "template_twin_synthetic_qa_admissions"("parentAdmissionId", "phase");

ALTER TABLE "template_twin_synthetic_qa_runs"
  ADD COLUMN "admissionId" TEXT;
CREATE UNIQUE INDEX "template_twin_qa_run_admission_unique"
  ON "template_twin_synthetic_qa_runs"("admissionId");
ALTER TABLE "template_twin_synthetic_qa_runs"
  ADD CONSTRAINT "template_twin_qa_run_admission_fkey"
  FOREIGN KEY ("admissionId")
  REFERENCES "template_twin_synthetic_qa_admissions"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;

-- Tenant, source, template, certification, and visit lineage are checked in
-- PostgreSQL as a backstop to application authorization. This trigger reads
-- identifiers and hashes only; no document or encounter content is inspected.
CREATE FUNCTION template_twin_assert_synthetic_qa_admission_lineage()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."sourceSha256" <> '9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4'
    OR NEW."sourceSizeBytes" <> 4686
  THEN
    RAISE EXCEPTION 'Template Twin synthetic QA source is not allowlisted';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM "users" actor
    WHERE actor."id" = NEW."actorId"
      AND actor."practiceId" = NEW."practiceId"
      AND actor."role" = 'DOCTOR'
      AND actor."isActive" = true
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission actor mismatch';
  END IF;

  IF NEW."parentAdmissionId" IS NOT NULL AND NOT EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_admissions" parent
    WHERE parent."id" = NEW."parentAdmissionId"
      AND parent."practiceId" = NEW."practiceId"
      AND parent."actorId" = NEW."actorId"
      AND parent."sourceSha256" = NEW."sourceSha256"
      AND parent."sourceSizeBytes" = NEW."sourceSizeBytes"
      AND parent."fixtureVersion" = NEW."fixtureVersion"
      AND parent."pinnedGlobalRolloutGeneration" = NEW."pinnedGlobalRolloutGeneration"
      AND parent."pinnedPracticeRolloutGeneration" = NEW."pinnedPracticeRolloutGeneration"
      AND parent."phase" = 'CERTIFIED'
      AND parent."failedAt" IS NULL
      AND parent."revokedAt" IS NULL
      AND parent."expiresAt" > clock_timestamp()
      AND parent."noteTemplateId" IS NOT DISTINCT FROM NEW."noteTemplateId"
      AND parent."noteTemplateVersion" IS NOT DISTINCT FROM NEW."noteTemplateVersion"
      AND parent."sourceArtifactId" IS NOT DISTINCT FROM NEW."sourceArtifactId"
      AND parent."certificationId" IS NOT DISTINCT FROM NEW."certificationId"
      AND parent."mappingSha256" IS NOT DISTINCT FROM NEW."mappingSha256"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA parent admission mismatch';
  END IF;

  IF NEW."sourceArtifactId" IS NOT NULL AND NOT EXISTS (
    SELECT 1
    FROM "template_twin_source_artifacts" source
    WHERE source."id" = NEW."sourceArtifactId"
      AND source."practiceId" = NEW."practiceId"
      AND source."sha256" = NEW."sourceSha256"
      AND source."sizeBytes" = NEW."sourceSizeBytes"
      AND source."validationStatus" = 'accepted'
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA source lineage mismatch';
  END IF;

  IF NEW."noteTemplateId" IS NOT NULL AND NOT EXISTS (
    SELECT 1
    FROM "note_templates" template
    JOIN "template_twin_compiled_versions" compiled
      ON compiled."noteTemplateId" = template."id"
    WHERE template."id" = NEW."noteTemplateId"
      AND template."doctorId" = NEW."actorId"
      AND template."version" = NEW."noteTemplateVersion"
      AND template."templateKind" = 'template_twin_docx'
      AND compiled."sourceArtifactId" = NEW."sourceArtifactId"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA template lineage mismatch';
  END IF;

  IF NEW."certificationId" IS NOT NULL AND NOT EXISTS (
    SELECT 1
    FROM "template_twin_certifications" certification
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
    SELECT 1
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient ON patient."id" = visit."patientId"
    WHERE visit."id" = NEW."visitId"
      AND visit."userId" = NEW."actorId"
      AND visit."noteTemplateId" = NEW."noteTemplateId"
      AND visit."noteTemplateVersion" = NEW."noteTemplateVersion"
      AND patient."practiceId" = NEW."practiceId"
      AND patient."name" = 'Template Twin Synthetic QA'
      AND patient."externalId" = 'SYNTHETIC-QA-ONLY'
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA visit lineage mismatch';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_synthetic_qa_admission_lineage_guard
BEFORE INSERT OR UPDATE OF
  "practiceId", "actorId", "parentAdmissionId", "sourceSha256",
  "sourceSizeBytes", "fixtureVersion", "sourceArtifactId", "noteTemplateId",
  "noteTemplateVersion", "certificationId", "mappingSha256", "visitId"
ON "template_twin_synthetic_qa_admissions"
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_synthetic_qa_admission_lineage();

-- Admission identity is immutable. Links may be filled once as the durable
-- state advances, never cleared or redirected. Terminal states cannot revive.
CREATE FUNCTION template_twin_guard_synthetic_qa_admission_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
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
    NEW."pinnedPracticeRolloutGeneration", NEW."createdAt", NEW."expiresAt"
  ) IS DISTINCT FROM ROW(
    OLD."practiceId", OLD."actorId", OLD."parentAdmissionId",
    OLD."sourceSha256", OLD."sourceSizeBytes", OLD."fixtureVersion",
    OLD."providerMode", OLD."purpose", OLD."requestSha256",
    OLD."payloadSha256", OLD."pinnedGlobalRolloutGeneration",
    OLD."pinnedPracticeRolloutGeneration", OLD."createdAt", OLD."expiresAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission identity is immutable';
  END IF;

  IF (OLD."sourceArtifactId" IS NOT NULL AND NEW."sourceArtifactId" IS DISTINCT FROM OLD."sourceArtifactId")
    OR (OLD."noteTemplateId" IS NOT NULL AND NEW."noteTemplateId" IS DISTINCT FROM OLD."noteTemplateId")
    OR (OLD."noteTemplateVersion" IS NOT NULL AND NEW."noteTemplateVersion" IS DISTINCT FROM OLD."noteTemplateVersion")
    OR (OLD."certificationId" IS NOT NULL AND NEW."certificationId" IS DISTINCT FROM OLD."certificationId")
    OR (OLD."mappingSha256" IS NOT NULL AND NEW."mappingSha256" IS DISTINCT FROM OLD."mappingSha256")
    OR (OLD."visitId" IS NOT NULL AND NEW."visitId" IS DISTINCT FROM OLD."visitId")
  THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission binding is immutable';
  END IF;

  IF NEW."attempt" < OLD."attempt" OR NEW."attempt" > OLD."attempt" + 1 THEN
    RAISE EXCEPTION 'Template Twin synthetic QA admission attempt is not monotonic';
  END IF;

  IF NOT (
    (NEW."phase" = OLD."phase" AND NEW."attempt" = OLD."attempt")
    OR (OLD."phase" = 'ADMITTED' AND NEW."phase" = 'SOURCE_VERIFIED')
    OR (OLD."phase" = 'SOURCE_VERIFIED' AND NEW."phase" = 'TEMPLATE_LINKED')
    OR (OLD."phase" = 'TEMPLATE_LINKED' AND NEW."phase" = 'CERTIFIED')
    OR (OLD."phase" = 'CERTIFIED' AND NEW."phase" = 'VISIT_LINKED')
    OR (OLD."phase" = 'VISIT_LINKED' AND NEW."phase" = 'PROCESSING')
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

CREATE TRIGGER template_twin_synthetic_qa_admission_transition_guard
BEFORE INSERT OR UPDATE ON "template_twin_synthetic_qa_admissions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_qa_admission_transition();

-- Replace the prior run-lineage function so every new run must be linked to
-- one committed, certified and visit-linked child admission. Retained prototype rows
-- remain readable but cannot be retried or claimed by the current application.
CREATE OR REPLACE FUNCTION template_twin_assert_synthetic_qa_run_lineage()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."admissionId" IS NULL OR NOT EXISTS (
    SELECT 1
    FROM "template_twin_synthetic_qa_admissions" admission
    WHERE admission."id" = NEW."admissionId"
      AND admission."purpose" = 'VISIT'
      AND admission."phase" = 'VISIT_LINKED'
      AND admission."practiceId" = NEW."practiceId"
      AND admission."actorId" = NEW."doctorId"
      AND admission."visitId" = NEW."visitId"
      AND admission."noteTemplateId" = NEW."noteTemplateId"
      AND admission."noteTemplateVersion" = NEW."noteTemplateVersion"
      AND admission."requestSha256" = NEW."requestSha256"
      AND admission."payloadSha256" = NEW."payloadSha256"
      AND admission."attempt" = 1
      AND admission."fixtureVersion" = NEW."fixtureVersion"
      AND admission."pinnedGlobalRolloutGeneration" = NEW."pinnedGlobalRolloutGeneration"
      AND admission."pinnedPracticeRolloutGeneration" = NEW."pinnedPracticeRolloutGeneration"
      AND (
        (NEW."mode" = 'typed' AND admission."providerMode" = 'SYNTHETIC_TYPED')
        OR
        (NEW."mode" = 'mock_voice' AND admission."providerMode" = 'SYNTHETIC_MOCK_VOICE')
      )
      AND admission."failedAt" IS NULL
      AND admission."revokedAt" IS NULL
      AND admission."expiresAt" > clock_timestamp()
  ) THEN
    RAISE EXCEPTION 'Template Twin synthetic QA run admission mismatch';
  END IF;

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

DROP TRIGGER template_twin_synthetic_qa_run_lineage_guard
  ON "template_twin_synthetic_qa_runs";
CREATE TRIGGER template_twin_synthetic_qa_run_lineage_guard
BEFORE INSERT OR UPDATE OF
  "admissionId", "practiceId", "doctorId", "visitId", "noteTemplateId",
  "noteTemplateVersion"
ON "template_twin_synthetic_qa_runs"
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_synthetic_qa_run_lineage();

COMMIT;
