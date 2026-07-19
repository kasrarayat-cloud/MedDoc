-- Completed Document -> Template Candidate v1
-- Additive, synthetic-only, and fail-closed. A candidate is not a NoteTemplate
-- or admitted source and therefore cannot activate or render until it is
-- downloaded and re-enters the ordinary native-template intake gates.

BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EXPORT_TEMPLATE_TWIN_CANDIDATE_DOCX_DOWNLOADED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_COMPLETED_CANDIDATE_CREATED';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED';

ALTER TABLE "template_twin_object_ledgers"
  DROP CONSTRAINT "template_twin_object_kind",
  ADD CONSTRAINT "template_twin_object_kind"
    CHECK ("kind" IN ('source', 'output', 'quarantine', 'candidate'));

ALTER TABLE "template_twin_quarantine_artifacts"
  ADD COLUMN "isolatedAt" TIMESTAMPTZ(6);

ALTER TABLE "template_twin_quarantine_artifacts"
  DROP CONSTRAINT "template_twin_quarantine_status",
  DROP CONSTRAINT "template_twin_quarantine_state_evidence",
  ADD CONSTRAINT "template_twin_quarantine_status" CHECK (
    "status" IN ('QUARANTINED', 'MALWARE_CLEAN', 'REJECTED', 'ADMITTED', 'ISOLATED')
  ),
  ADD CONSTRAINT "template_twin_quarantine_state_evidence" CHECK (
    ("status" = 'QUARANTINED'
      AND "admittedAt" IS NULL AND "isolatedAt" IS NULL)
    OR ("status" = 'MALWARE_CLEAN'
      AND "malwareScanEvidence"->>'verdict' = 'clean'
      AND "scannedAt" IS NOT NULL
      AND "admittedAt" IS NULL AND "isolatedAt" IS NULL
      AND cardinality("rejectionCodes") = 0)
    OR ("status" = 'REJECTED'
      AND cardinality("rejectionCodes") > 0
      AND "admittedAt" IS NULL AND "isolatedAt" IS NULL)
    OR ("status" = 'ADMITTED'
      AND "malwareScanEvidence"->>'verdict' = 'clean'
      AND "metadataMinimizationEvidence" IS NOT NULL
      AND "scannedAt" IS NOT NULL AND "admittedAt" IS NOT NULL
      AND "isolatedAt" IS NULL
      AND cardinality("rejectionCodes") = 0)
    OR ("status" = 'ISOLATED'
      AND "intakeMode" = 'COMPLETED_EXAMPLE'
      AND "malwareScanEvidence"->>'verdict' = 'clean'
      AND "metadataMinimizationEvidence" IS NOT NULL
      AND "scannedAt" IS NOT NULL AND "isolatedAt" IS NOT NULL
      AND "admittedAt" IS NULL
      AND cardinality("rejectionCodes") = 0)
  );

CREATE TABLE "template_twin_completed_candidates" (
  "id" TEXT NOT NULL,
  "practiceId" TEXT NOT NULL,
  "createdById" TEXT,
  "name" TEXT NOT NULL,
  "encounterScope" TEXT NOT NULL,
  "versionDescription" TEXT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
  "candidateObjectKey" TEXT NOT NULL,
  "candidateObjectVersionId" TEXT NOT NULL,
  "candidateObjectEtag" TEXT NOT NULL,
  "candidateSha256" CHAR(64) NOT NULL,
  "candidateSizeBytes" INTEGER NOT NULL,
  "candidateStructureSha256" CHAR(64) NOT NULL,
  "inventorySha256" CHAR(64) NOT NULL,
  "converterVersion" TEXT NOT NULL,
  "comparisonEvidence" JSONB NOT NULL,
  "privacyEvidence" JSONB NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "reviewedAt" TIMESTAMPTZ(6),
  CONSTRAINT "template_twin_completed_candidates_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_completed_candidate_status" CHECK (
    "status" IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')
  ),
  CONSTRAINT "template_twin_completed_candidate_review_state" CHECK (
    ("status" = 'PENDING_REVIEW' AND "reviewedAt" IS NULL)
    OR ("status" IN ('APPROVED', 'REJECTED') AND "reviewedAt" IS NOT NULL)
  ),
  CONSTRAINT "template_twin_completed_candidate_identity" CHECK (
    char_length(btrim("name")) BETWEEN 3 AND 120
    AND char_length(btrim("encounterScope")) BETWEEN 3 AND 120
    AND char_length(btrim("versionDescription")) BETWEEN 3 AND 500
    AND char_length(btrim("candidateObjectVersionId")) > 0
    AND char_length(btrim("candidateObjectEtag")) > 0
    AND "candidateSizeBytes" > 0
    AND "candidateSha256" ~ '^[a-f0-9]{64}$'
    AND "candidateStructureSha256" ~ '^[a-f0-9]{64}$'
    AND "inventorySha256" ~ '^[a-f0-9]{64}$'
    AND "converterVersion" = 'completed-document-candidate/1.0.0'
    AND "privacyEvidence"->>'providerEgress' = 'false'
    AND "privacyEvidence"->>'sentinelVerified' = 'true'
  )
);

CREATE TABLE "template_twin_completed_candidate_examples" (
  "id" TEXT NOT NULL,
  "candidateId" TEXT NOT NULL,
  "quarantineArtifactId" TEXT NOT NULL,
  "ordinal" INTEGER NOT NULL,
  "minimizedSha256" CHAR(64) NOT NULL,
  "documentStructureSha256" CHAR(64) NOT NULL,
  "localPrivacyEvidenceSha256" CHAR(64) NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_completed_candidate_examples_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_completed_candidate_example_ordinal" CHECK (
    "ordinal" BETWEEN 1 AND 3
  ),
  CONSTRAINT "template_twin_completed_candidate_example_hashes" CHECK (
    "minimizedSha256" ~ '^[a-f0-9]{64}$'
    AND "documentStructureSha256" ~ '^[a-f0-9]{64}$'
    AND "localPrivacyEvidenceSha256" ~ '^[a-f0-9]{64}$'
  )
);

CREATE TABLE "template_twin_completed_candidate_regions" (
  "id" TEXT NOT NULL,
  "candidateId" TEXT NOT NULL,
  "regionId" TEXT NOT NULL,
  "displayOrder" INTEGER NOT NULL,
  "label" TEXT NOT NULL,
  "evidenceType" TEXT NOT NULL,
  "partName" TEXT NOT NULL,
  "tableIndex" INTEGER NOT NULL,
  "rowIndex" INTEGER NOT NULL,
  "cellIndex" INTEGER NOT NULL,
  "candidateTag" TEXT NOT NULL,
  "candidateSdtId" TEXT NOT NULL,
  "sourceEvidenceSha256" CHAR(64) NOT NULL,
  "decision" TEXT NOT NULL DEFAULT 'PENDING',
  "decidedById" TEXT,
  "decidedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_completed_candidate_regions_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_completed_candidate_region_location" CHECK (
    "displayOrder" >= 0 AND "tableIndex" >= 0 AND "rowIndex" >= 0
    AND "cellIndex" > 0 AND "partName" = 'word/document.xml'
  ),
  CONSTRAINT "template_twin_completed_candidate_region_identity" CHECK (
    "regionId" ~ '^tccr_[a-f0-9]{24}$'
    AND char_length(btrim("label")) BETWEEN 1 AND 120
    AND "evidenceType" = 'stable_label_changed_scalar_cell'
    AND "candidateTag" ~ '^qmd:candidate:[a-f0-9]{24}$'
    AND "candidateSdtId" ~ '^[1-9][0-9]{0,9}$'
    AND "sourceEvidenceSha256" ~ '^[a-f0-9]{64}$'
  ),
  CONSTRAINT "template_twin_completed_candidate_region_decision" CHECK (
    "decision" IN ('PENDING', 'APPROVED', 'REJECTED')
    AND (("decision" = 'PENDING' AND "decidedById" IS NULL AND "decidedAt" IS NULL)
      OR ("decision" IN ('APPROVED', 'REJECTED')
        AND "decidedById" IS NOT NULL AND "decidedAt" IS NOT NULL))
  )
);

CREATE UNIQUE INDEX "template_twin_completed_candidates_object_key"
  ON "template_twin_completed_candidates"("candidateObjectKey");
CREATE INDEX "template_twin_completed_candidates_owner_status_idx"
  ON "template_twin_completed_candidates"("practiceId", "createdById", "status", "createdAt");
CREATE INDEX "template_twin_completed_candidates_sha_idx"
  ON "template_twin_completed_candidates"("candidateSha256");
CREATE UNIQUE INDEX "template_twin_completed_candidate_example_quarantine_key"
  ON "template_twin_completed_candidate_examples"("quarantineArtifactId");
CREATE UNIQUE INDEX "template_twin_completed_candidate_example_ordinal_key"
  ON "template_twin_completed_candidate_examples"("candidateId", "ordinal");
CREATE INDEX "template_twin_completed_candidate_examples_candidate_idx"
  ON "template_twin_completed_candidate_examples"("candidateId");
CREATE UNIQUE INDEX "template_twin_completed_candidate_region_id_key"
  ON "template_twin_completed_candidate_regions"("candidateId", "regionId");
CREATE UNIQUE INDEX "template_twin_completed_candidate_region_order_key"
  ON "template_twin_completed_candidate_regions"("candidateId", "displayOrder");
CREATE UNIQUE INDEX "template_twin_completed_candidate_region_tag_key"
  ON "template_twin_completed_candidate_regions"("candidateId", "candidateTag");
CREATE INDEX "template_twin_completed_candidate_region_decision_idx"
  ON "template_twin_completed_candidate_regions"("candidateId", "decision");

ALTER TABLE "template_twin_completed_candidates"
  ADD CONSTRAINT "template_twin_completed_candidate_practice_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_completed_candidate_creator_fkey"
    FOREIGN KEY ("createdById") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "template_twin_completed_candidate_examples"
  ADD CONSTRAINT "template_twin_completed_candidate_example_candidate_fkey"
    FOREIGN KEY ("candidateId") REFERENCES "template_twin_completed_candidates"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_completed_candidate_example_quarantine_fkey"
    FOREIGN KEY ("quarantineArtifactId") REFERENCES "template_twin_quarantine_artifacts"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "template_twin_completed_candidate_regions"
  ADD CONSTRAINT "template_twin_completed_candidate_region_candidate_fkey"
    FOREIGN KEY ("candidateId") REFERENCES "template_twin_completed_candidates"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT "template_twin_completed_candidate_region_decider_fkey"
    FOREIGN KEY ("decidedById") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE OR REPLACE FUNCTION template_twin_quarantine_immutable_identity() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin quarantine artifacts are append-only';
  END IF;
  IF OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR OLD."createdById" IS DISTINCT FROM NEW."createdById"
     OR OLD."lineageId" IS DISTINCT FROM NEW."lineageId"
     OR OLD."lineageVersion" IS DISTINCT FROM NEW."lineageVersion"
     OR OLD."intakeMode" IS DISTINCT FROM NEW."intakeMode"
     OR OLD."objectKey" IS DISTINCT FROM NEW."objectKey"
     OR OLD."objectVersionId" IS DISTINCT FROM NEW."objectVersionId"
     OR OLD."objectEtag" IS DISTINCT FROM NEW."objectEtag"
     OR OLD."sha256" IS DISTINCT FROM NEW."sha256"
     OR OLD."mimeType" IS DISTINCT FROM NEW."mimeType"
     OR OLD."sizeBytes" IS DISTINCT FROM NEW."sizeBytes"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt" THEN
    RAISE EXCEPTION 'Template Twin quarantine identity is immutable';
  END IF;
  IF OLD."status" IN ('REJECTED', 'ADMITTED', 'ISOLATED')
     AND OLD IS DISTINCT FROM NEW THEN
    RAISE EXCEPTION 'Template Twin quarantine terminal state is immutable';
  END IF;
  IF NOT (
    OLD."status" = NEW."status"
    OR (OLD."status" = 'QUARANTINED' AND NEW."status" IN ('MALWARE_CLEAN', 'REJECTED'))
    OR (OLD."status" = 'MALWARE_CLEAN' AND NEW."status" IN ('ADMITTED', 'ISOLATED', 'REJECTED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin quarantine state transition is invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION template_twin_completed_candidate_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin completed candidates are append-only';
  END IF;
  IF OLD."practiceId" IS DISTINCT FROM NEW."practiceId"
     OR OLD."createdById" IS DISTINCT FROM NEW."createdById"
     OR OLD."name" IS DISTINCT FROM NEW."name"
     OR OLD."encounterScope" IS DISTINCT FROM NEW."encounterScope"
     OR OLD."versionDescription" IS DISTINCT FROM NEW."versionDescription"
     OR OLD."candidateObjectKey" IS DISTINCT FROM NEW."candidateObjectKey"
     OR OLD."candidateObjectVersionId" IS DISTINCT FROM NEW."candidateObjectVersionId"
     OR OLD."candidateObjectEtag" IS DISTINCT FROM NEW."candidateObjectEtag"
     OR OLD."candidateSha256" IS DISTINCT FROM NEW."candidateSha256"
     OR OLD."candidateSizeBytes" IS DISTINCT FROM NEW."candidateSizeBytes"
     OR OLD."candidateStructureSha256" IS DISTINCT FROM NEW."candidateStructureSha256"
     OR OLD."inventorySha256" IS DISTINCT FROM NEW."inventorySha256"
     OR OLD."converterVersion" IS DISTINCT FROM NEW."converterVersion"
     OR OLD."comparisonEvidence" IS DISTINCT FROM NEW."comparisonEvidence"
     OR OLD."privacyEvidence" IS DISTINCT FROM NEW."privacyEvidence"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt" THEN
    RAISE EXCEPTION 'Template Twin completed candidate identity is immutable';
  END IF;
  IF OLD."status" IN ('APPROVED', 'REJECTED') AND OLD IS DISTINCT FROM NEW THEN
    RAISE EXCEPTION 'Template Twin completed candidate review is terminal';
  END IF;
  IF NOT (
    OLD."status" = NEW."status"
    OR (OLD."status" = 'PENDING_REVIEW' AND NEW."status" IN ('APPROVED', 'REJECTED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate transition is invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_twin_completed_candidate_immutable_guard
  BEFORE UPDATE OR DELETE ON "template_twin_completed_candidates"
  FOR EACH ROW EXECUTE FUNCTION template_twin_completed_candidate_immutable();

CREATE OR REPLACE FUNCTION template_twin_completed_candidate_example_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    RAISE EXCEPTION 'Template Twin completed candidate examples are append-only';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_completed_candidate_example_immutable_guard
  BEFORE UPDATE OR DELETE ON "template_twin_completed_candidate_examples"
  FOR EACH ROW EXECUTE FUNCTION template_twin_completed_candidate_example_immutable();

CREATE OR REPLACE FUNCTION template_twin_completed_candidate_region_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin completed candidate regions are append-only';
  END IF;
  IF OLD."candidateId" IS DISTINCT FROM NEW."candidateId"
     OR OLD."regionId" IS DISTINCT FROM NEW."regionId"
     OR OLD."displayOrder" IS DISTINCT FROM NEW."displayOrder"
     OR OLD."label" IS DISTINCT FROM NEW."label"
     OR OLD."evidenceType" IS DISTINCT FROM NEW."evidenceType"
     OR OLD."partName" IS DISTINCT FROM NEW."partName"
     OR OLD."tableIndex" IS DISTINCT FROM NEW."tableIndex"
     OR OLD."rowIndex" IS DISTINCT FROM NEW."rowIndex"
     OR OLD."cellIndex" IS DISTINCT FROM NEW."cellIndex"
     OR OLD."candidateTag" IS DISTINCT FROM NEW."candidateTag"
     OR OLD."candidateSdtId" IS DISTINCT FROM NEW."candidateSdtId"
     OR OLD."sourceEvidenceSha256" IS DISTINCT FROM NEW."sourceEvidenceSha256"
     OR OLD."createdAt" IS DISTINCT FROM NEW."createdAt" THEN
    RAISE EXCEPTION 'Template Twin completed candidate region identity is immutable';
  END IF;
  IF OLD."decision" IN ('APPROVED', 'REJECTED') AND OLD IS DISTINCT FROM NEW THEN
    RAISE EXCEPTION 'Template Twin completed candidate region decision is terminal';
  END IF;
  IF NOT (
    OLD."decision" = NEW."decision"
    OR (OLD."decision" = 'PENDING' AND NEW."decision" IN ('APPROVED', 'REJECTED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate region transition is invalid';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER template_twin_completed_candidate_region_immutable_guard
  BEFORE UPDATE OR DELETE ON "template_twin_completed_candidate_regions"
  FOR EACH ROW EXECUTE FUNCTION template_twin_completed_candidate_region_immutable();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_example() RETURNS trigger AS $$
DECLARE candidate_practice TEXT;
DECLARE quarantine_practice TEXT;
DECLARE quarantine_lineage TEXT;
DECLARE quarantine_version INTEGER;
DECLARE quarantine_mode TEXT;
DECLARE quarantine_status TEXT;
DECLARE minimized_sha256 TEXT;
BEGIN
  SELECT c."practiceId" INTO candidate_practice
    FROM "template_twin_completed_candidates" c WHERE c."id" = NEW."candidateId";
  SELECT q."practiceId", q."lineageId", q."lineageVersion", q."intakeMode", q."status",
         q."metadataMinimizationEvidence"->>'minimizedSha256'
    INTO quarantine_practice, quarantine_lineage, quarantine_version,
         quarantine_mode, quarantine_status, minimized_sha256
    FROM "template_twin_quarantine_artifacts" q
    WHERE q."id" = NEW."quarantineArtifactId";
  IF candidate_practice IS NULL OR quarantine_practice <> candidate_practice
     OR quarantine_lineage <> NEW."candidateId"
     OR quarantine_version <> NEW."ordinal"
     OR quarantine_mode <> 'COMPLETED_EXAMPLE'
     OR quarantine_status <> 'ISOLATED'
     OR minimized_sha256 <> NEW."minimizedSha256" THEN
    RAISE EXCEPTION 'Template Twin completed candidate example isolation mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER template_twin_completed_candidate_example_consistency
  AFTER INSERT OR UPDATE ON "template_twin_completed_candidate_examples"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_example();

CREATE OR REPLACE FUNCTION template_twin_assert_isolated_completed_example() RETURNS trigger AS $$
BEGIN
  IF NEW."status" = 'ISOLATED' AND NOT EXISTS (
    SELECT 1 FROM "template_twin_completed_candidate_examples" e
    JOIN "template_twin_completed_candidates" c ON c."id" = e."candidateId"
    WHERE e."quarantineArtifactId" = NEW."id"
      AND c."practiceId" = NEW."practiceId"
  ) THEN
    RAISE EXCEPTION 'Template Twin isolated example has no candidate claim';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER template_twin_isolated_completed_example_consistency
  AFTER INSERT OR UPDATE ON "template_twin_quarantine_artifacts"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_isolated_completed_example();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_review() RETURNS trigger AS $$
DECLARE total_count INTEGER;
DECLARE pending_count INTEGER;
DECLARE rejected_count INTEGER;
DECLARE example_count INTEGER;
DECLARE example_structure_count INTEGER;
DECLARE minimum_ordinal INTEGER;
DECLARE maximum_ordinal INTEGER;
BEGIN
  SELECT count(*), count(DISTINCT e."documentStructureSha256"),
         min(e."ordinal"), max(e."ordinal")
    INTO example_count, example_structure_count, minimum_ordinal, maximum_ordinal
    FROM "template_twin_completed_candidate_examples" e
    WHERE e."candidateId" = NEW."id";
  IF example_count NOT BETWEEN 2 AND 3
     OR example_structure_count <> 1
     OR minimum_ordinal <> 1 OR maximum_ordinal <> example_count
     OR (NEW."comparisonEvidence"->>'exampleCount')::INTEGER <> example_count
     OR (NEW."privacyEvidence"->>'exampleCount')::INTEGER <> example_count THEN
    RAISE EXCEPTION 'Template Twin completed candidate example census mismatch';
  END IF;
  SELECT count(*), count(*) FILTER (WHERE r."decision" = 'PENDING'),
         count(*) FILTER (WHERE r."decision" = 'REJECTED')
    INTO total_count, pending_count, rejected_count
    FROM "template_twin_completed_candidate_regions" r
    WHERE r."candidateId" = NEW."id";
  IF total_count < 1
     OR (NEW."comparisonEvidence"->>'candidateFieldCount')::INTEGER <> total_count THEN
    RAISE EXCEPTION 'Template Twin completed candidate has no field inventory';
  END IF;
  IF (NEW."status" = 'PENDING_REVIEW' AND pending_count <> total_count)
     OR (NEW."status" = 'APPROVED' AND (pending_count <> 0 OR rejected_count <> 0))
     OR (NEW."status" = 'REJECTED' AND (pending_count <> 0 OR rejected_count < 1)) THEN
    RAISE EXCEPTION 'Template Twin completed candidate review inventory mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER template_twin_completed_candidate_review_consistency
  AFTER INSERT OR UPDATE ON "template_twin_completed_candidates"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_review();

CREATE OR REPLACE FUNCTION template_twin_assert_completed_candidate_ledger() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM "template_twin_object_ledgers" l
    WHERE l."objectKey" = NEW."candidateObjectKey"
      AND l."practiceId" = NEW."practiceId"
      AND l."objectVersionId" = NEW."candidateObjectVersionId"
      AND l."objectEtag" = NEW."candidateObjectEtag"
      AND l."sha256" = NEW."candidateSha256"
      AND l."sizeBytes" = NEW."candidateSizeBytes"
      AND l."kind" = 'candidate'
      AND l."state" = 'CLAIMED'
      AND l."claimType" = 'completed_candidate'
      AND l."claimId" = NEW."id"
  ) THEN
    RAISE EXCEPTION 'Template Twin completed candidate object ledger mismatch';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER template_twin_completed_candidate_ledger_consistency
  AFTER INSERT OR UPDATE ON "template_twin_completed_candidates"
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION template_twin_assert_completed_candidate_ledger();

-- Preserve every accepted ledger ownership contract and add the candidate.
CREATE OR REPLACE FUNCTION template_twin_assert_object_ledger_tenant() RETURNS trigger AS $$
DECLARE owner_practice TEXT;
DECLARE owner_key TEXT;
DECLARE owner_sha256 TEXT;
DECLARE owner_size_bytes INTEGER;
DECLARE owner_version_id TEXT;
DECLARE owner_etag TEXT;
BEGIN
  IF NEW."objectKey" NOT LIKE ('practices/' || NEW."practiceId" || '/template-twin/%') THEN
    RAISE EXCEPTION 'Template Twin object ledger tenant key mismatch';
  END IF;
  IF NEW."claimType" = 'fill_manifest' THEN
    SELECT f."practiceId", f."outputObjectKey", f."outputSha256", f."outputSizeBytes",
           f."outputVersionId", f."outputEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_fill_manifests" f WHERE f."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'source_artifact' THEN
    SELECT s."practiceId", s."objectKey", s."sha256", s."sizeBytes",
           s."objectVersionId", s."objectEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_source_artifacts" s WHERE s."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'quarantine_artifact' THEN
    SELECT q."practiceId", q."objectKey", q."sha256", q."sizeBytes",
           q."objectVersionId", q."objectEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_quarantine_artifacts" q WHERE q."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'completed_candidate' THEN
    SELECT c."practiceId", c."candidateObjectKey", c."candidateSha256", c."candidateSizeBytes",
           c."candidateObjectVersionId", c."candidateObjectEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_completed_candidates" c WHERE c."id" = NEW."claimId";
  ELSIF NEW."claimType" = 'compiled_test_output' THEN
    SELECT s."practiceId", c."latestTestOutputObjectKey",
           c."latestTestOutputSha256", NULL,
           c."latestTestOutputVersionId", c."latestTestOutputEtag"
      INTO owner_practice, owner_key, owner_sha256, owner_size_bytes,
           owner_version_id, owner_etag
      FROM "template_twin_compiled_versions" c
      JOIN "template_twin_source_artifacts" s ON s."id" = c."sourceArtifactId"
      WHERE c."id" = NEW."claimId";
  ELSIF NEW."claimType" IS NOT NULL THEN
    RAISE EXCEPTION 'Template Twin object ledger claim type is unsupported';
  END IF;
  IF NEW."claimType" IS NOT NULL
     AND (owner_practice IS NULL OR owner_practice <> NEW."practiceId" OR owner_key <> NEW."objectKey") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim lineage mismatch';
  END IF;
  IF NEW."claimType" IS NOT NULL
     AND (NEW."state" <> 'CLAIMED'
       OR owner_version_id IS NULL OR owner_version_id <> NEW."objectVersionId"
       OR owner_etag IS NULL OR owner_etag <> NEW."objectEtag") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim provider identity mismatch';
  END IF;
  IF NEW."claimType" = 'source_artifact'
     AND (NEW."kind" <> 'source'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin source object ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" = 'quarantine_artifact'
     AND (NEW."kind" <> 'quarantine'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin quarantine object ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" = 'completed_candidate'
     AND (NEW."kind" <> 'candidate'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin completed candidate ledger integrity mismatch';
  END IF;
  IF NEW."claimType" = 'compiled_test_output'
     AND (NEW."kind" <> 'output'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256") THEN
    RAISE EXCEPTION 'Template Twin synthetic output ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" = 'fill_manifest'
     AND (NEW."kind" <> 'output' OR NEW."state" <> 'CLAIMED'
       OR owner_sha256 IS NULL OR owner_sha256 <> NEW."sha256"
       OR owner_size_bytes IS NULL OR owner_size_bytes <> NEW."sizeBytes") THEN
    RAISE EXCEPTION 'Template Twin object ledger claim integrity mismatch';
  END IF;
  IF NEW."claimType" IS NULL AND EXISTS (
    SELECT 1 FROM "template_twin_fill_manifests" f
    WHERE f."outputObjectKey" = NEW."objectKey"
  ) THEN
    RAISE EXCEPTION 'Template Twin object ledger claim ownership missing';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMIT;
