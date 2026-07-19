\set ON_ERROR_STOP on

-- Disposable PostgreSQL contract for the completed-document candidate
-- redacted comparison receipt. All identifiers and values are synthetic.

INSERT INTO "practices" (
  "id", "name", "slug", "updatedAt", "templateTwinEnabled",
  "templateTwinRolloutGeneration"
) VALUES (
  'tt_preview_practice', 'Synthetic Preview Practice',
  'synthetic-preview-practice', clock_timestamp(), true, 1
);

INSERT INTO "users" (
  "id", "email", "name", "passwordHash", "role", "isActive",
  "practiceId", "updatedAt"
) VALUES (
  'tt_preview_doctor', 'preview-doctor@synthetic.invalid',
  'Synthetic Preview Doctor', 'not-a-login-secret', 'DOCTOR', true,
  'tt_preview_practice', clock_timestamp()
);

UPDATE "template_twin_rollout_controls"
SET "enabled" = true, "generation" = 2, "updatedAt" = clock_timestamp()
WHERE "id" = 'global';

CREATE FUNCTION tt_preview_projection(tamper TEXT DEFAULT NULL)
RETURNS JSONB AS $$
DECLARE projection JSONB;
BEGIN
  projection := jsonb_build_object(
    'profileVersion', 'completed-candidate-redacted-structural-review/1.0.0',
    'valuesRedacted', true,
    'sourceBytesReturned', false,
    'providerEgress', false,
    'paginationRepresented', false,
    'sourceExampleSha256s', jsonb_build_array(repeat('1', 64), repeat('2', 64)),
    'sourceStructureSha256', repeat('f', 64),
    'candidateStructureSha256', repeat('d', 64),
    'inventorySha256', repeat('e', 64),
    'candidateSha256', repeat('c', 64),
    'blocks', jsonb_build_array(jsonb_build_object(
      'kind', 'table',
      'blockKey', 'table:0:/w:document[1]/w:body[1]/w:tbl[1]',
      'displayOrder', 0,
      'tableIndex', 0,
      'gridColumnBasisPoints', jsonb_build_array(4000, 6000),
      'rows', jsonb_build_array(jsonb_build_object(
        'rowIndex', 0,
        'cells', jsonb_build_array(
          jsonb_build_object(
            'cellKey', 'table:0:row:0:cell:0',
            'cellIndex', 0,
            'columnStart', 0,
            'columnSpan', 1,
            'rowSpan', 1,
            'role', jsonb_build_object(
              'kind', 'stable_label',
              'label', 'Finding',
              'forRegionId', 'tccr_111111111111111111111111'
            )
          ),
          jsonb_build_object(
            'cellKey', 'table:0:row:0:cell:1',
            'cellIndex', 1,
            'columnStart', 1,
            'columnSpan', 1,
            'rowSpan', 1,
            'role', jsonb_build_object(
              'kind', 'candidate_region',
              'regionId', 'tccr_111111111111111111111111',
              'candidateTag', 'qmd:candidate:111111111111111111111111',
              'controlKind', 'plain_text',
              'sourceState', 'VALUE_WITHHELD',
              'candidateState', 'BLANK_CONTROL'
            )
          )
        )
      ))
    )),
    'regionCount', 1
  );

  IF tamper = 'candidate_structure' THEN
    projection := jsonb_set(
      projection, '{candidateStructureSha256}', to_jsonb(repeat('a', 64))
    );
  ELSIF tamper = 'duplicate_cell' THEN
    projection := jsonb_set(
      projection, '{blocks,0,rows,0,cells,1,cellKey}',
      to_jsonb('table:0:row:0:cell:0'::TEXT)
    );
  ELSIF tamper = 'missing_label' THEN
    projection := jsonb_set(
      projection, '{blocks,0,rows,0,cells,0,role}',
      jsonb_build_object('kind', 'static_redacted')
    );
  ELSIF tamper = 'candidate_state' THEN
    projection := jsonb_set(
      projection, '{blocks,0,rows,0,cells,1,role,candidateState}',
      to_jsonb('SOURCE_VALUE_VISIBLE'::TEXT)
    );
  ELSIF tamper = 'reversed_source' THEN
    projection := jsonb_set(
      projection, '{sourceExampleSha256s}',
      jsonb_build_array(repeat('2', 64), repeat('1', 64))
    );
  END IF;
  RETURN projection;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION tt_preview_seed_candidate(candidate_id TEXT, tamper TEXT DEFAULT NULL)
RETURNS VOID AS $$
DECLARE scan_at TIMESTAMPTZ(6) := clock_timestamp();
DECLARE malware_one JSONB;
DECLARE malware_two JSONB;
DECLARE metadata_one JSONB;
DECLARE metadata_two JSONB;
BEGIN
  malware_one := jsonb_build_object(
    'profileVersion', 'template-twin-clamd-instream-v1',
    'scanner', 'clamav-clamd',
    'transport', 'unix-domain-socket',
    'engineVersion', 'synthetic-1',
    'signatureVersion', '1',
    'sourceSha256', repeat('a', 64),
    'sourceSizeBytes', 100,
    'verdict', 'clean',
    'threatNameSha256', NULL,
    'scannedAt', to_char(
      scan_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
    ),
    'attestationSha256', repeat('0', 64)
  );
  malware_one := jsonb_set(
    malware_one, '{attestationSha256}',
    to_jsonb(template_twin_malware_attestation_sha256(malware_one))
  );
  malware_two := jsonb_set(
    malware_one,
    '{sourceSha256}',
    to_jsonb(repeat('b', 64))
  );
  malware_two := jsonb_set(
    malware_two, '{sourceSizeBytes}', to_jsonb(101)
  );
  malware_two := jsonb_set(
    malware_two, '{attestationSha256}',
    to_jsonb(template_twin_malware_attestation_sha256(malware_two))
  );
  metadata_one := jsonb_build_object(
    'profileVersion', 'template-twin-docx-metadata-minimization-v1',
    'originalSha256', repeat('a', 64),
    'minimizedSha256', repeat('1', 64),
    'zipEntryTimestampsNormalized', true,
    'replacedParts', '[]'::JSONB
  );
  metadata_two := jsonb_build_object(
    'profileVersion', 'template-twin-docx-metadata-minimization-v1',
    'originalSha256', repeat('b', 64),
    'minimizedSha256', repeat('2', 64),
    'zipEntryTimestampsNormalized', true,
    'replacedParts', '[]'::JSONB
  );

  INSERT INTO "template_twin_completed_candidates" (
    "id", "practiceId", "createdById", "name", "encounterScope",
    "versionDescription", "candidateObjectKey", "candidateObjectVersionId",
    "candidateObjectEtag", "candidateSha256", "candidateSizeBytes",
    "candidateStructureSha256", "inventorySha256", "converterVersion",
    "comparisonEvidence", "privacyEvidence", "reviewProjection",
    "reviewProjectionSha256"
  ) VALUES (
    candidate_id, 'tt_preview_practice', 'tt_preview_doctor',
    'Synthetic candidate', 'Synthetic follow-up', 'Synthetic comparison proof',
    'practices/tt_preview_practice/template-twin/candidates/' || candidate_id || '/candidate.docx',
    candidate_id || '-candidate-version', candidate_id || '-candidate-etag',
    repeat('c', 64), 200, repeat('d', 64), repeat('e', 64),
    'completed-document-candidate/1.1.0',
    jsonb_build_object('exampleCount', 2, 'candidateFieldCount', 1),
    jsonb_build_object(
      'exampleCount', 2, 'providerEgress', false, 'sentinelVerified', true
    ),
    tt_preview_projection(tamper), repeat('9', 64)
  );

  INSERT INTO "template_twin_quarantine_artifacts" (
    "id", "practiceId", "createdById", "lineageId", "lineageVersion",
    "intakeMode", "objectKey", "objectVersionId", "objectEtag", "sha256",
    "mimeType", "sizeBytes", "status", "malwareScanEvidence",
    "metadataMinimizationEvidence", "scannedAt", "isolatedAt"
  ) VALUES
  (
    candidate_id || ':q1', 'tt_preview_practice', 'tt_preview_doctor',
    candidate_id, 1, 'COMPLETED_EXAMPLE',
    'practices/tt_preview_practice/template-twin/quarantine/' || candidate_id || '/example-1.docx',
    candidate_id || '-q1-version', candidate_id || '-q1-etag', repeat('a', 64),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    100, 'ISOLATED', malware_one, metadata_one, scan_at, scan_at
  ),
  (
    candidate_id || ':q2', 'tt_preview_practice', 'tt_preview_doctor',
    candidate_id, 2, 'COMPLETED_EXAMPLE',
    'practices/tt_preview_practice/template-twin/quarantine/' || candidate_id || '/example-2.docx',
    candidate_id || '-q2-version', candidate_id || '-q2-etag', repeat('b', 64),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    101, 'ISOLATED', malware_two, metadata_two, scan_at, scan_at
  );

  INSERT INTO "template_twin_completed_candidate_examples" (
    "id", "candidateId", "quarantineArtifactId", "ordinal",
    "minimizedSha256", "documentStructureSha256",
    "localPrivacyEvidenceSha256"
  ) VALUES
    (candidate_id || ':e1', candidate_id, candidate_id || ':q1', 1,
      repeat('1', 64), repeat('f', 64), repeat('4', 64)),
    (candidate_id || ':e2', candidate_id, candidate_id || ':q2', 2,
      repeat('2', 64), repeat('f', 64), repeat('5', 64));

  INSERT INTO "template_twin_completed_candidate_regions" (
    "id", "candidateId", "regionId", "displayOrder", "label",
    "evidenceType", "partName", "tableIndex", "rowIndex", "cellIndex",
    "candidateTag", "candidateSdtId", "sourceEvidenceSha256"
  ) VALUES (
    candidate_id || ':r1', candidate_id,
    'tccr_111111111111111111111111', 0, 'Finding',
    'stable_label_changed_scalar_cell', 'word/document.xml', 0, 0, 1,
    'qmd:candidate:111111111111111111111111', '101', repeat('3', 64)
  );

  INSERT INTO "template_twin_object_ledgers" (
    "id", "practiceId", "objectKey", "objectVersionId", "objectEtag",
    "sha256", "sizeBytes", "kind", "state", "claimType", "claimId",
    "updatedAt"
  ) VALUES
  (
    candidate_id || ':lq1', 'tt_preview_practice',
    'practices/tt_preview_practice/template-twin/quarantine/' || candidate_id || '/example-1.docx',
    candidate_id || '-q1-version', candidate_id || '-q1-etag', repeat('a', 64),
    100, 'quarantine', 'CLAIMED', 'quarantine_artifact', candidate_id || ':q1',
    clock_timestamp()
  ),
  (
    candidate_id || ':lq2', 'tt_preview_practice',
    'practices/tt_preview_practice/template-twin/quarantine/' || candidate_id || '/example-2.docx',
    candidate_id || '-q2-version', candidate_id || '-q2-etag', repeat('b', 64),
    101, 'quarantine', 'CLAIMED', 'quarantine_artifact', candidate_id || ':q2',
    clock_timestamp()
  ),
  (
    candidate_id || ':lc', 'tt_preview_practice',
    'practices/tt_preview_practice/template-twin/candidates/' || candidate_id || '/candidate.docx',
    candidate_id || '-candidate-version', candidate_id || '-candidate-etag',
    repeat('c', 64), 200, 'candidate', 'CLAIMED', 'completed_candidate',
    candidate_id, clock_timestamp()
  );
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION tt_preview_seed_receipt(
  candidate_id TEXT,
  receipt_id TEXT,
  receipt_created_at TIMESTAMPTZ(6),
  global_generation BIGINT DEFAULT 2
) RETURNS VOID AS $$
BEGIN
  INSERT INTO "template_twin_completed_candidate_review_receipts" (
    "id", "candidateId", "practiceId", "reviewedById", "tokenSha256",
    "candidateSha256", "candidateStructureSha256", "inventorySha256",
    "reviewProjectionSha256", "converterVersion", "globalRolloutGeneration",
    "practiceRolloutGeneration", "createdAt", "expiresAt"
  ) VALUES (
    receipt_id, candidate_id, 'tt_preview_practice', 'tt_preview_doctor',
    encode(sha256(convert_to(receipt_id, 'UTF8')), 'hex'),
    repeat('c', 64), repeat('d', 64), repeat('e', 64),
    repeat('9', 64), 'completed-document-candidate/1.1.0',
    global_generation, 1, receipt_created_at,
    receipt_created_at + INTERVAL '15 minutes'
  );
END;
$$ LANGUAGE plpgsql;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_valid');
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;

DO $$
DECLARE test_case TEXT;
DECLARE candidate_id TEXT;
DECLARE blocked BOOLEAN;
BEGIN
  FOREACH test_case IN ARRAY ARRAY[
    'candidate_structure', 'duplicate_cell', 'missing_label',
    'candidate_state', 'reversed_source'
  ] LOOP
    candidate_id := 'candidate_tamper_' || test_case;
    blocked := false;
    BEGIN
      PERFORM tt_preview_seed_candidate(candidate_id, test_case);
      SET CONSTRAINTS ALL IMMEDIATE;
    EXCEPTION WHEN OTHERS THEN
      IF position('projection' IN SQLERRM) = 0 THEN
        RAISE EXCEPTION 'TT_PREVIEW_WRONG_TAMPER_FAILURE %: %', test_case, SQLERRM;
      END IF;
      blocked := true;
    END;
    IF NOT blocked THEN
      RAISE EXCEPTION 'TT_PREVIEW_TAMPER_DID_NOT_BLOCK %', test_case;
    END IF;
    IF EXISTS (
      SELECT 1 FROM "template_twin_completed_candidates" WHERE "id" = candidate_id
    ) THEN
      RAISE EXCEPTION 'TT_PREVIEW_TAMPER_LEFT_CANDIDATE %', test_case;
    END IF;
  END LOOP;
END;
$$;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_terminal');
SELECT tt_preview_seed_receipt(
  'candidate_terminal', '123e4567-e89b-42d3-a456-426614174001',
  clock_timestamp()
);
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;

DO $$
DECLARE review_time TIMESTAMPTZ(6) := clock_timestamp();
BEGIN
  UPDATE "template_twin_completed_candidate_review_receipts"
  SET "consumedAt" = review_time
  WHERE "id" = '123e4567-e89b-42d3-a456-426614174001';
  UPDATE "template_twin_completed_candidate_regions"
  SET "decision" = 'APPROVED', "decidedById" = 'tt_preview_doctor',
      "decidedAt" = review_time
  WHERE "candidateId" = 'candidate_terminal';
  UPDATE "template_twin_completed_candidates"
  SET "status" = 'APPROVED', "reviewedAt" = review_time,
      "reviewReceiptId" = '123e4567-e89b-42d3-a456-426614174001'
  WHERE "id" = 'candidate_terminal';
  SET CONSTRAINTS ALL IMMEDIATE;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "template_twin_completed_candidates" c
    JOIN "template_twin_completed_candidate_review_receipts" r
      ON r."id" = c."reviewReceiptId"
    WHERE c."id" = 'candidate_terminal' AND c."status" = 'APPROVED'
      AND r."consumedAt" = c."reviewedAt"
  ) THEN
    RAISE EXCEPTION 'TT_PREVIEW_VALID_TERMINAL_PATH_FAILED';
  END IF;
END;
$$;

DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
  BEGIN
    UPDATE "template_twin_completed_candidate_review_receipts"
    SET "consumedAt" = clock_timestamp()
    WHERE "id" = '123e4567-e89b-42d3-a456-426614174001';
  EXCEPTION WHEN OTHERS THEN
    blocked := true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'TT_PREVIEW_RECEIPT_REUSE_DID_NOT_BLOCK'; END IF;
END;
$$;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_wrong_generation');
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
  BEGIN
    PERFORM tt_preview_seed_receipt(
      'candidate_wrong_generation',
      '223e4567-e89b-42d3-a456-426614174002',
      clock_timestamp(), 99
    );
    SET CONSTRAINTS ALL IMMEDIATE;
  EXCEPTION WHEN OTHERS THEN
    IF position('receipt invalid' IN SQLERRM) = 0 THEN
      RAISE EXCEPTION 'TT_PREVIEW_WRONG_GENERATION_FAILURE: %', SQLERRM;
    END IF;
    blocked := true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'TT_PREVIEW_WRONG_GENERATION_DID_NOT_BLOCK'; END IF;
END;
$$;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_receipt_only');
SELECT tt_preview_seed_receipt(
  'candidate_receipt_only', '323e4567-e89b-42d3-a456-426614174003',
  clock_timestamp()
);
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
  BEGIN
    UPDATE "template_twin_completed_candidate_review_receipts"
    SET "consumedAt" = clock_timestamp()
    WHERE "id" = '323e4567-e89b-42d3-a456-426614174003';
    SET CONSTRAINTS ALL IMMEDIATE;
  EXCEPTION WHEN OTHERS THEN
    blocked := true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'TT_PREVIEW_RECEIPT_ONLY_DID_NOT_BLOCK'; END IF;
END;
$$;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_unconsumed');
SELECT tt_preview_seed_receipt(
  'candidate_unconsumed', '423e4567-e89b-42d3-a456-426614174004',
  clock_timestamp()
);
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
DO $$
DECLARE blocked BOOLEAN := false;
DECLARE review_time TIMESTAMPTZ(6) := clock_timestamp();
BEGIN
  BEGIN
    UPDATE "template_twin_completed_candidate_regions"
    SET "decision" = 'REJECTED', "decidedById" = 'tt_preview_doctor',
        "decidedAt" = review_time
    WHERE "candidateId" = 'candidate_unconsumed';
    UPDATE "template_twin_completed_candidates"
    SET "status" = 'REJECTED', "reviewedAt" = review_time,
        "reviewReceiptId" = '423e4567-e89b-42d3-a456-426614174004'
    WHERE "id" = 'candidate_unconsumed';
    SET CONSTRAINTS ALL IMMEDIATE;
  EXCEPTION WHEN OTHERS THEN
    blocked := true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'TT_PREVIEW_UNCONSUMED_TERMINAL_DID_NOT_BLOCK'; END IF;
END;
$$;

BEGIN;
SELECT tt_preview_seed_candidate('candidate_expired');
SELECT tt_preview_seed_receipt(
  'candidate_expired', '523e4567-e89b-42d3-a456-426614174005',
  clock_timestamp() - INTERVAL '20 minutes'
);
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
DO $$
DECLARE blocked BOOLEAN := false;
BEGIN
  BEGIN
    UPDATE "template_twin_completed_candidate_review_receipts"
    SET "consumedAt" = "expiresAt" - INTERVAL '1 second'
    WHERE "id" = '523e4567-e89b-42d3-a456-426614174005';
  EXCEPTION WHEN OTHERS THEN
    IF position('immutable' IN SQLERRM) = 0 THEN
      RAISE EXCEPTION 'TT_PREVIEW_WRONG_EXPIRY_FAILURE: %', SQLERRM;
    END IF;
    blocked := true;
  END;
  IF NOT blocked THEN RAISE EXCEPTION 'TT_PREVIEW_EXPIRED_RECEIPT_DID_NOT_BLOCK'; END IF;
END;
$$;

DROP FUNCTION tt_preview_seed_receipt(TEXT, TEXT, TIMESTAMPTZ, BIGINT);
DROP FUNCTION tt_preview_seed_candidate(TEXT, TEXT);
DROP FUNCTION tt_preview_projection(TEXT);

SELECT 'PASS template-twin-completed-candidate-review-preview-contract-v1' AS result;
