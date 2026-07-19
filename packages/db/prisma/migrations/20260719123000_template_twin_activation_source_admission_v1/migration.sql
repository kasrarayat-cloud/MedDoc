-- Template Twin activation source-admission backstop v1.
--
-- Runtime gates already reject historical certifications that predate raw
-- quarantine admission. This additive trigger closes the same boundary for
-- direct SQL and future application regressions. Existing rows are not
-- rewritten; any transition to active must prove the complete current native
-- source, certification, provider-identity, and object-ledger chain.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE OR REPLACE FUNCTION template_twin_metadata_minimization_receipt_valid(
  evidence JSONB,
  expected_original_sha256 TEXT,
  expected_minimized_sha256 TEXT
) RETURNS BOOLEAN AS $$
DECLARE
  replaced_parts JSONB;
  part_count INTEGER;
  distinct_part_count INTEGER;
  allowed_parts BOOLEAN;
  canonical_parts JSONB;
BEGIN
  IF jsonb_typeof(evidence) IS DISTINCT FROM 'object'
     OR evidence->>'profileVersion' IS DISTINCT FROM
       'template-twin-docx-metadata-minimization-v1'
     OR evidence->>'originalSha256' IS DISTINCT FROM expected_original_sha256
     OR evidence->>'minimizedSha256' IS DISTINCT FROM expected_minimized_sha256
     OR jsonb_typeof(evidence->'zipEntryTimestampsNormalized')
       IS DISTINCT FROM 'boolean'
     OR evidence->>'zipEntryTimestampsNormalized' IS DISTINCT FROM 'true'
     OR jsonb_typeof(evidence->'replacedParts') IS DISTINCT FROM 'array' THEN
    RETURN FALSE;
  END IF;

  replaced_parts := evidence->'replacedParts';
  SELECT count(*), count(DISTINCT item #>> '{}'),
         COALESCE(bool_and(
           jsonb_typeof(item) = 'string'
           AND item #>> '{}' = ANY (ARRAY[
             'docProps/app.xml',
             'docProps/core.xml',
             'docProps/custom.xml'
           ])
         ), TRUE),
         COALESCE(jsonb_agg(item ORDER BY item #>> '{}'), '[]'::JSONB)
    INTO part_count, distinct_part_count, allowed_parts, canonical_parts
    FROM jsonb_array_elements(replaced_parts) AS item;

  RETURN allowed_parts
    AND part_count = distinct_part_count
    AND replaced_parts = canonical_parts;
EXCEPTION WHEN OTHERS THEN
  RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;

CREATE OR REPLACE FUNCTION template_twin_require_active_source_admission()
RETURNS TRIGGER AS $$
DECLARE
  admission_current BOOLEAN;
BEGIN
  IF NEW."templateKind" <> 'template_twin_docx' OR NEW."status" <> 'active' THEN
    RETURN NEW;
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM "template_twin_compiled_versions" c
    JOIN "template_twin_certifications" cert
      ON cert."compiledVersionId" = c."id"
    JOIN "template_twin_source_artifacts" s
      ON s."id" = c."sourceArtifactId"
    JOIN "template_twin_quarantine_artifacts" q
      ON q."id" = s."quarantineArtifactId"
    JOIN "users" owner_user
      ON owner_user."id" = NEW."doctorId"
    JOIN "users" certifier
      ON certifier."id" = cert."certifiedById"
    JOIN "template_twin_object_ledgers" source_ledger
      ON source_ledger."claimType" = 'source_artifact'
     AND source_ledger."claimId" = s."id"
    JOIN "template_twin_object_ledgers" quarantine_ledger
      ON quarantine_ledger."claimType" = 'quarantine_artifact'
     AND quarantine_ledger."claimId" = q."id"
    JOIN "template_twin_object_ledgers" output_ledger
      ON output_ledger."claimType" = 'compiled_test_output'
     AND output_ledger."claimId" = c."id"
    WHERE c."noteTemplateId" = NEW."id"
      AND c."certificationStatus" = 'CERTIFIED'
      AND c."blockingUnsupportedCount" = 0
      AND owner_user."role" = 'DOCTOR'
      AND owner_user."isActive" = TRUE
      AND owner_user."practiceId" = s."practiceId"
      AND certifier."role" = 'DOCTOR'
      AND certifier."isActive" = TRUE
      AND certifier."practiceId" = s."practiceId"
      AND s."practiceId" = q."practiceId"
      AND s."lineageId" = q."lineageId"
      AND s."validationStatus" = 'accepted'
      AND cardinality(s."rejectionCodes") = 0
      AND s."objectKey" IS NOT NULL
      AND COALESCE(btrim(s."objectVersionId"), '') <> ''
      AND COALESCE(btrim(s."objectEtag"), '') <> ''
      AND q."intakeMode" = 'NATIVE_TEMPLATE'
      AND q."status" = 'ADMITTED'
      AND q."scannedAt" IS NOT NULL
      AND q."admittedAt" IS NOT NULL
      AND q."admittedAt" >= q."scannedAt"
      AND cardinality(q."rejectionCodes") = 0
      AND jsonb_typeof(q."malwareScanEvidence") = 'object'
      AND q."malwareScanEvidence" ?& ARRAY[
        'profileVersion', 'scanner', 'transport', 'engineVersion',
        'signatureVersion', 'sourceSha256', 'sourceSizeBytes', 'verdict',
        'threatNameSha256', 'scannedAt', 'attestationSha256'
      ]
      AND q."malwareScanEvidence"->>'profileVersion' =
        'template-twin-clamd-instream-v1'
      AND q."malwareScanEvidence"->>'scanner' = 'clamav-clamd'
      AND q."malwareScanEvidence"->>'transport' = 'unix-domain-socket'
      AND COALESCE(btrim(q."malwareScanEvidence"->>'engineVersion'), '') <> ''
      AND COALESCE(q."malwareScanEvidence"->>'signatureVersion', '') ~ '^[0-9]+$'
      AND q."malwareScanEvidence"->>'sourceSha256' = q."sha256"
      AND q."malwareScanEvidence"->>'sourceSizeBytes' = q."sizeBytes"::TEXT
      AND q."malwareScanEvidence"->>'verdict' = 'clean'
      AND jsonb_typeof(q."malwareScanEvidence"->'threatNameSha256') = 'null'
      AND q."malwareScanEvidence"->>'scannedAt' =
        to_char(q."scannedAt" AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
      AND q."malwareScanEvidence"->>'attestationSha256' =
        template_twin_malware_attestation_sha256(q."malwareScanEvidence")
      AND template_twin_metadata_minimization_receipt_valid(
        q."metadataMinimizationEvidence", q."sha256", s."sha256"
      )
      AND source_ledger."practiceId" = s."practiceId"
      AND source_ledger."objectKey" = s."objectKey"
      AND source_ledger."objectVersionId" = s."objectVersionId"
      AND source_ledger."objectEtag" = s."objectEtag"
      AND source_ledger."sha256" = s."sha256"
      AND source_ledger."sizeBytes" = s."sizeBytes"
      AND source_ledger."kind" = 'source'
      AND source_ledger."state" = 'CLAIMED'
      AND quarantine_ledger."practiceId" = q."practiceId"
      AND quarantine_ledger."objectKey" = q."objectKey"
      AND quarantine_ledger."objectVersionId" = q."objectVersionId"
      AND quarantine_ledger."objectEtag" = q."objectEtag"
      AND quarantine_ledger."sha256" = q."sha256"
      AND quarantine_ledger."sizeBytes" = q."sizeBytes"
      AND quarantine_ledger."kind" = 'quarantine'
      AND quarantine_ledger."state" = 'CLAIMED'
      AND output_ledger."practiceId" = s."practiceId"
      AND output_ledger."objectKey" = cert."testOutputObjectKey"
      AND output_ledger."objectVersionId" = cert."testOutputVersionId"
      AND output_ledger."objectEtag" = cert."testOutputEtag"
      AND output_ledger."sha256" = cert."testOutputSha256"
      AND output_ledger."kind" = 'output'
      AND output_ledger."state" = 'CLAIMED'
      AND cert."testOutputObjectKey" = c."latestTestOutputObjectKey"
      AND cert."testOutputVersionId" = c."latestTestOutputVersionId"
      AND cert."testOutputEtag" = c."latestTestOutputEtag"
      AND cert."testOutputSha256" = c."latestTestOutputSha256"
  ) INTO admission_current;

  IF NOT admission_current
     OR NEW."doctorId" IS NULL
     OR char_length(btrim(NEW."name")) < 3
     OR NEW."encounterType" IS NULL
     OR char_length(btrim(NEW."encounterType")) < 3
     OR NEW."versionDescription" IS NULL
     OR char_length(btrim(NEW."versionDescription")) < 3 THEN
    RAISE EXCEPTION 'Template Twin activation source admission mismatch'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_twin_active_source_admission_insert_guard
  BEFORE INSERT ON "note_templates"
  FOR EACH ROW EXECUTE FUNCTION template_twin_require_active_source_admission();

CREATE TRIGGER template_twin_active_source_admission_update_guard
  BEFORE UPDATE OF "status" ON "note_templates"
  FOR EACH ROW EXECUTE FUNCTION template_twin_require_active_source_admission();

COMMIT;
