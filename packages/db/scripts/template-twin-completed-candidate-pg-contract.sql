\set ON_ERROR_STOP on

BEGIN;
SET CONSTRAINTS ALL DEFERRED;

DO $contract$
DECLARE
  practice_id TEXT;
  q1_sha TEXT := repeat('1', 64);
  q2_sha TEXT := repeat('2', 64);
  minimized_1 TEXT := repeat('3', 64);
  minimized_2 TEXT := repeat('4', 64);
  candidate_sha TEXT := repeat('5', 64);
  structure_sha TEXT := repeat('6', 64);
  inventory_sha TEXT := repeat('7', 64);
  privacy_sha TEXT := repeat('8', 64);
  evidence_sha TEXT := repeat('9', 64);
  candidate_key TEXT;
BEGIN
  SELECT p."id" INTO STRICT practice_id FROM "practices" p ORDER BY p."id" LIMIT 1;
  candidate_key := 'practices/' || practice_id ||
    '/template-twin/candidates/candidate_contract_v1/v1/artifact_candidate/' ||
    candidate_sha || '.docx';

  INSERT INTO "template_twin_quarantine_artifacts" (
    "id", "practiceId", "lineageId", "lineageVersion", "intakeMode",
    "objectKey", "objectVersionId", "objectEtag", "sha256", "mimeType",
    "sizeBytes", "status", "malwareScanEvidence", "scannedAt"
  ) VALUES
  (
    'q_candidate_contract_1', practice_id, 'candidate_contract_v1', 1,
    'COMPLETED_EXAMPLE',
    'practices/' || practice_id ||
      '/template-twin/quarantine/candidate_contract_v1/v1/artifact_q1/' || q1_sha || '.docx',
    'version-q1', 'etag-q1', q1_sha,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    101, 'MALWARE_CLEAN',
    jsonb_build_object(
      'profileVersion', 'template-twin-clamd-instream-v1',
      'scanner', 'clamav-clamd',
      'transport', 'unix-domain-socket',
      'engineVersion', '1.4.5',
      'signatureVersion', '28065',
      'sourceSha256', q1_sha,
      'sourceSizeBytes', 101,
      'verdict', 'clean',
      'threatNameSha256', NULL,
      'scannedAt', '2026-07-19T08:00:00.000Z',
      'attestationSha256',
        '6a00945caef5805ab670f33886ac912399a752710f579aa35b89c5bf183a79cd'
    ), '2026-07-19T08:00:00.000Z'
  ),
  (
    'q_candidate_contract_2', practice_id, 'candidate_contract_v1', 2,
    'COMPLETED_EXAMPLE',
    'practices/' || practice_id ||
      '/template-twin/quarantine/candidate_contract_v1/v2/artifact_q2/' || q2_sha || '.docx',
    'version-q2', 'etag-q2', q2_sha,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    102, 'MALWARE_CLEAN',
    jsonb_build_object(
      'profileVersion', 'template-twin-clamd-instream-v1',
      'scanner', 'clamav-clamd',
      'transport', 'unix-domain-socket',
      'engineVersion', '1.4.5',
      'signatureVersion', '28065',
      'sourceSha256', q2_sha,
      'sourceSizeBytes', 102,
      'verdict', 'clean',
      'threatNameSha256', NULL,
      'scannedAt', '2026-07-19T08:00:01.000Z',
      'attestationSha256',
        '60a13b82c7ad81f1fd5c0ea70c8760ac7c8d9f4d1ed24a77e17a2eaae120e591'
    ), '2026-07-19T08:00:01.000Z'
  );

  INSERT INTO "template_twin_object_ledgers" (
    "id", "practiceId", "objectKey", "objectVersionId", "objectEtag",
    "sha256", "sizeBytes", "kind", "state", "claimType", "claimId",
    "updatedAt"
  )
  SELECT 'ledger-' || q."id", q."practiceId", q."objectKey",
         q."objectVersionId", q."objectEtag", q."sha256", q."sizeBytes",
         'quarantine', 'CLAIMED', 'quarantine_artifact', q."id", clock_timestamp()
  FROM "template_twin_quarantine_artifacts" q
  WHERE q."id" IN ('q_candidate_contract_1', 'q_candidate_contract_2');

  INSERT INTO "template_twin_completed_candidates" (
    "id", "practiceId", "name", "encounterScope", "versionDescription",
    "status", "candidateObjectKey", "candidateObjectVersionId",
    "candidateObjectEtag", "candidateSha256", "candidateSizeBytes",
    "candidateStructureSha256", "inventorySha256", "converterVersion",
    "comparisonEvidence", "privacyEvidence"
  ) VALUES (
    'candidate_contract_v1', practice_id, 'Synthetic candidate contract',
    'Synthetic follow-up', 'Two structurally identical synthetic examples',
    'PENDING_REVIEW', candidate_key, 'version-candidate', 'etag-candidate',
    candidate_sha, 301, structure_sha, inventory_sha,
    'completed-document-candidate/1.0.0',
    jsonb_build_object(
      'exampleCount', 2, 'identicalStructure', true,
      'sourceBlockCount', 3, 'candidateFieldCount', 1,
      'preservedStaticBlockCount', 2,
      'sourceSummary', 'synthetic structure only',
      'candidateSummary', 'one blank deterministic binding'
    ),
    jsonb_build_object(
      'profileVersion', 'completed-candidate-local-synthetic-privacy/1.0.0',
      'providerEgress', false, 'exampleCount', 2,
      'sentinelVerified', true, 'structuredIdentifierClasses', jsonb_build_array(),
      'evidenceSha256', privacy_sha
    )
  );

  INSERT INTO "template_twin_completed_candidate_regions" (
    "id", "candidateId", "regionId", "displayOrder", "label",
    "evidenceType", "partName", "tableIndex", "rowIndex", "cellIndex",
    "candidateTag", "candidateSdtId", "sourceEvidenceSha256"
  ) VALUES (
    'region_candidate_contract_1', 'candidate_contract_v1',
    'tccr_111111111111111111111111', 0, 'Finding',
    'stable_label_changed_scalar_cell', 'word/document.xml', 0, 0, 1,
    'qmd:candidate:111111111111111111111111', '123456789', evidence_sha
  );

  INSERT INTO "template_twin_completed_candidate_examples" (
    "id", "candidateId", "quarantineArtifactId", "ordinal",
    "minimizedSha256", "documentStructureSha256",
    "localPrivacyEvidenceSha256"
  ) VALUES
    ('example_candidate_contract_1', 'candidate_contract_v1',
      'q_candidate_contract_1', 1, minimized_1, structure_sha, privacy_sha),
    ('example_candidate_contract_2', 'candidate_contract_v1',
      'q_candidate_contract_2', 2, minimized_2, structure_sha, privacy_sha);

  UPDATE "template_twin_quarantine_artifacts"
  SET "status" = 'ISOLATED',
      "isolatedAt" = clock_timestamp(),
      "metadataMinimizationEvidence" = CASE "id"
        WHEN 'q_candidate_contract_1' THEN jsonb_build_object(
          'profileVersion', 'template-twin-docx-metadata-minimization-v1',
          'originalSha256', q1_sha, 'minimizedSha256', minimized_1,
          'replacedParts', jsonb_build_array(),
          'zipEntryTimestampsNormalized', true)
        ELSE jsonb_build_object(
          'profileVersion', 'template-twin-docx-metadata-minimization-v1',
          'originalSha256', q2_sha, 'minimizedSha256', minimized_2,
          'replacedParts', jsonb_build_array(),
          'zipEntryTimestampsNormalized', true)
      END
  WHERE "id" IN ('q_candidate_contract_1', 'q_candidate_contract_2');

  INSERT INTO "template_twin_object_ledgers" (
    "id", "practiceId", "objectKey", "objectVersionId", "objectEtag",
    "sha256", "sizeBytes", "kind", "state", "claimType", "claimId",
    "updatedAt"
  ) VALUES (
    'ledger-candidate-contract', practice_id, candidate_key,
    'version-candidate', 'etag-candidate', candidate_sha, 301,
    'candidate', 'CLAIMED', 'completed_candidate',
    'candidate_contract_v1', clock_timestamp()
  );
END;
$contract$;

SET CONSTRAINTS ALL IMMEDIATE;

DO $negative_review$
BEGIN
  BEGIN
    UPDATE "template_twin_completed_candidates"
    SET "status" = 'APPROVED', "reviewedAt" = clock_timestamp()
    WHERE "id" = 'candidate_contract_v1';
    SET CONSTRAINTS template_twin_completed_candidate_review_consistency IMMEDIATE;
    RAISE EXCEPTION 'review mismatch guard did not reject';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE '%review inventory mismatch%' THEN
      RAISE;
    END IF;
  END;
  SET CONSTRAINTS template_twin_completed_candidate_review_consistency DEFERRED;
END;
$negative_review$;

DO $negative_terminal$
BEGIN
  BEGIN
    UPDATE "template_twin_quarantine_artifacts"
    SET "isolatedAt" = "isolatedAt" + INTERVAL '1 second'
    WHERE "id" = 'q_candidate_contract_1';
    RAISE EXCEPTION 'terminal quarantine guard did not reject';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE '%terminal state is immutable%' THEN
      RAISE;
    END IF;
  END;
END;
$negative_terminal$;

DO $negative_tenant_key$
BEGIN
  BEGIN
    UPDATE "template_twin_object_ledgers"
    SET "objectKey" = 'practices/wrong_practice/template-twin/candidates/candidate_contract_v1/v1/a/' || repeat('5', 64) || '.docx'
    WHERE "id" = 'ledger-candidate-contract';
    RAISE EXCEPTION 'tenant object-key guard did not reject';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE '%tenant key mismatch%' THEN
      RAISE;
    END IF;
  END;
END;
$negative_tenant_key$;

ROLLBACK;
