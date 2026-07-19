\set ON_ERROR_STOP on

-- Synthetic-only PostgreSQL contract. Run only against a disposable database
-- whose complete migration history has just been applied. Every row is rolled
-- back; no document bytes, provider call, or patient-like content is used.
BEGIN;

INSERT INTO practices (id, name, slug, "updatedAt") VALUES
  ('tt-q-contract-practice', 'Synthetic Contract Practice',
   'tt-q-contract-practice', CURRENT_TIMESTAMP);

INSERT INTO users (
  id, email, "passwordHash", role, "practiceId", "updatedAt"
) VALUES (
  'tt-q-contract-doctor', 'template-contract@synthetic.invalid',
  'synthetic-not-a-credential', 'DOCTOR', 'tt-q-contract-practice',
  CURRENT_TIMESTAMP
);

INSERT INTO note_templates (
  id, "doctorId", name, "encounterType", sections, "styleProfile",
  version, status, "isSystemDefault", "updatedAt", "lineageId",
  "templateKind"
) VALUES (
  'tt-q-contract-template-good', 'tt-q-contract-doctor',
  'Synthetic admitted template', 'synthetic_contract', '[]'::jsonb,
  '{}'::jsonb, 1, 'active', false, CURRENT_TIMESTAMP,
  'tt-q-contract-lineage-good', 'template_twin_docx'
);

INSERT INTO template_twin_quarantine_artifacts (
  id, "practiceId", "createdById", "lineageId", "lineageVersion",
  "intakeMode", "objectKey", "objectVersionId", "objectEtag", sha256,
  "mimeType", "sizeBytes", status, "malwareScanEvidence",
  "metadataMinimizationEvidence", "rejectionCodes", "scannedAt",
  "admittedAt"
) VALUES (
  'tt-q-contract-quarantine-good', 'tt-q-contract-practice',
  'tt-q-contract-doctor', 'tt-q-contract-lineage-good', 1,
  'NATIVE_TEMPLATE',
  'practices/tt-q-contract-practice/template-twin/quarantine/contract-good.docx',
  'quarantine-version-good', 'quarantine-etag-good', repeat('a', 64),
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  140, 'ADMITTED',
  jsonb_build_object(
    'profileVersion', 'template-twin-clamd-instream-v1',
    'scanner', 'clamav-clamd',
    'transport', 'unix-domain-socket',
    'engineVersion', '1.4.3',
    'signatureVersion', '27888',
    'sourceSha256', repeat('a', 64),
    'sourceSizeBytes', 140,
    'verdict', 'clean',
    'threatNameSha256', NULL,
    'scannedAt', '2026-07-19T00:00:00.000Z',
    'attestationSha256', repeat('b', 64)
  ),
  jsonb_build_object(
    'profileVersion', 'template-twin-docx-metadata-minimization-v1',
    'originalSha256', repeat('a', 64),
    'minimizedSha256', repeat('c', 64),
    'replacedParts', jsonb_build_array(),
    'zipEntryTimestampsNormalized', true
  ),
  ARRAY[]::text[], '2026-07-19T00:00:00.000Z',
  '2026-07-19T00:01:00.000Z'
);

INSERT INTO template_twin_source_artifacts (
  id, "practiceId", "createdById", "lineageId", "lineageVersion",
  "objectKey", "objectVersionId", "objectEtag", sha256, "mimeType",
  "sizeBytes", "validationStatus", "rejectionCodes",
  "privacyScanEvidence", "quarantineArtifactId"
) VALUES (
  'tt-q-contract-source-good', 'tt-q-contract-practice',
  'tt-q-contract-doctor', 'tt-q-contract-lineage-good', 1,
  'practices/tt-q-contract-practice/template-twin/sources/contract-good.docx',
  'source-version-good', 'source-etag-good', repeat('c', 64),
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  120, 'accepted', ARRAY[]::text[],
  jsonb_build_object(
    'profileVersion', 'template-twin-source-phi-safe-alpha-v1',
    'approvedStaticAssetPolicySha256', repeat('7', 64),
    'approvedStaticAssetUsageSha256', repeat('8', 64)
  ),
  'tt-q-contract-quarantine-good'
);

INSERT INTO template_twin_compiled_versions (
  id, "sourceArtifactId", "noteTemplateId", "compilerVersion",
  "irSchemaVersion", "compiledDocumentIr", "unsupportedElements",
  "structureSha256", "staticContentSha256", "certificationStatus",
  "blockingUnsupportedCount", "latestSyntheticTestManifest",
  "latestTestMappingsSha256", "latestTestOutputObjectKey",
  "latestTestOutputVersionId", "latestTestOutputEtag",
  "latestTestOutputSha256", "latestTestStaticContentSha256",
  "latestTestRoundTrip", "latestTestVerifiedAt"
) VALUES (
  'tt-q-contract-compiled-good', 'tt-q-contract-source-good',
  'tt-q-contract-template-good', 'synthetic-contract-compiler', 1,
  '{}'::jsonb, '[]'::jsonb, repeat('d', 64), repeat('e', 64),
  'CERTIFIED', 0, '{}'::jsonb, repeat('1', 64),
  'practices/tt-q-contract-practice/template-twin/outputs/contract-good.docx',
  'output-version-good', 'output-etag-good', repeat('f', 64),
  repeat('e', 64), '{}'::jsonb, '2026-07-19T00:02:00.000Z'
);

INSERT INTO template_twin_object_ledgers (
  id, "practiceId", "objectKey", "objectVersionId", "objectEtag", sha256,
  "sizeBytes", kind, state, "claimType", "claimId", "updatedAt"
) VALUES
  (
    'tt-q-contract-ledger-quarantine', 'tt-q-contract-practice',
    'practices/tt-q-contract-practice/template-twin/quarantine/contract-good.docx',
    'quarantine-version-good', 'quarantine-etag-good', repeat('a', 64),
    140, 'quarantine', 'CLAIMED', 'quarantine_artifact',
    'tt-q-contract-quarantine-good', CURRENT_TIMESTAMP
  ),
  (
    'tt-q-contract-ledger-source', 'tt-q-contract-practice',
    'practices/tt-q-contract-practice/template-twin/sources/contract-good.docx',
    'source-version-good', 'source-etag-good', repeat('c', 64),
    120, 'source', 'CLAIMED', 'source_artifact',
    'tt-q-contract-source-good', CURRENT_TIMESTAMP
  ),
  (
    'tt-q-contract-ledger-output', 'tt-q-contract-practice',
    'practices/tt-q-contract-practice/template-twin/outputs/contract-good.docx',
    'output-version-good', 'output-etag-good', repeat('f', 64),
    110, 'output', 'CLAIMED', 'compiled_test_output',
    'tt-q-contract-compiled-good', CURRENT_TIMESTAMP
  );

SET CONSTRAINTS ALL IMMEDIATE;

INSERT INTO template_twin_certifications (
  id, "compiledVersionId", "certifiedById", "compiledStructureSha256",
  "approvedMappingsSha256", "syntheticTestManifest",
  "testOutputObjectKey", "testOutputVersionId", "testOutputEtag",
  "testOutputSha256"
) VALUES (
  'tt-q-contract-cert-good', 'tt-q-contract-compiled-good',
  'tt-q-contract-doctor', repeat('d', 64), repeat('1', 64), '{}'::jsonb,
  'practices/tt-q-contract-practice/template-twin/outputs/contract-good.docx',
  'output-version-good', 'output-etag-good', repeat('f', 64)
);

-- A structurally valid historical source without quarantine linkage remains
-- readable, but direct SQL certification must fail at the BEFORE INSERT gate.
INSERT INTO note_templates (
  id, "doctorId", name, "encounterType", sections, "styleProfile",
  version, status, "isSystemDefault", "updatedAt", "lineageId",
  "templateKind"
) VALUES (
  'tt-q-contract-template-missing', 'tt-q-contract-doctor',
  'Synthetic pre-GA template', 'synthetic_contract_missing', '[]'::jsonb,
  '{}'::jsonb, 1, 'draft', false, CURRENT_TIMESTAMP,
  'tt-q-contract-lineage-missing', 'template_twin_docx'
);

INSERT INTO template_twin_source_artifacts (
  id, "practiceId", "createdById", "lineageId", "lineageVersion",
  "objectKey", "objectVersionId", "objectEtag", sha256, "mimeType",
  "sizeBytes", "validationStatus", "rejectionCodes", "privacyScanEvidence"
) VALUES (
  'tt-q-contract-source-missing', 'tt-q-contract-practice',
  'tt-q-contract-doctor', 'tt-q-contract-lineage-missing', 1,
  'practices/tt-q-contract-practice/template-twin/sources/contract-missing.docx',
  'source-version-missing', 'source-etag-missing', repeat('2', 64),
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  90, 'accepted', ARRAY[]::text[],
  jsonb_build_object(
    'profileVersion', 'template-twin-source-phi-safe-alpha-v1',
    'approvedStaticAssetPolicySha256', repeat('9', 64),
    'approvedStaticAssetUsageSha256', repeat('0', 64)
  )
);

INSERT INTO template_twin_compiled_versions (
  id, "sourceArtifactId", "noteTemplateId", "compilerVersion",
  "irSchemaVersion", "compiledDocumentIr", "unsupportedElements",
  "structureSha256", "staticContentSha256", "certificationStatus",
  "blockingUnsupportedCount", "latestSyntheticTestManifest",
  "latestTestMappingsSha256", "latestTestOutputObjectKey",
  "latestTestOutputVersionId", "latestTestOutputEtag",
  "latestTestOutputSha256", "latestTestStaticContentSha256",
  "latestTestRoundTrip", "latestTestVerifiedAt"
) VALUES (
  'tt-q-contract-compiled-missing', 'tt-q-contract-source-missing',
  'tt-q-contract-template-missing', 'synthetic-contract-compiler', 1,
  '{}'::jsonb, '[]'::jsonb, repeat('3', 64), repeat('4', 64),
  'CERTIFIED', 0, '{}'::jsonb, repeat('6', 64),
  'practices/tt-q-contract-practice/template-twin/outputs/contract-missing.docx',
  'output-version-missing', 'output-etag-missing', repeat('5', 64),
  repeat('4', 64), '{}'::jsonb, '2026-07-19T00:02:00.000Z'
);

INSERT INTO template_twin_object_ledgers (
  id, "practiceId", "objectKey", "objectVersionId", "objectEtag", sha256,
  "sizeBytes", kind, state, "claimType", "claimId", "updatedAt"
) VALUES
  (
    'tt-q-contract-ledger-source-missing', 'tt-q-contract-practice',
    'practices/tt-q-contract-practice/template-twin/sources/contract-missing.docx',
    'source-version-missing', 'source-etag-missing', repeat('2', 64),
    90, 'source', 'CLAIMED', 'source_artifact',
    'tt-q-contract-source-missing', CURRENT_TIMESTAMP
  ),
  (
    'tt-q-contract-ledger-output-missing', 'tt-q-contract-practice',
    'practices/tt-q-contract-practice/template-twin/outputs/contract-missing.docx',
    'output-version-missing', 'output-etag-missing', repeat('5', 64),
    80, 'output', 'CLAIMED', 'compiled_test_output',
    'tt-q-contract-compiled-missing', CURRENT_TIMESTAMP
  );

SET CONSTRAINTS ALL IMMEDIATE;

DO $$
BEGIN
  BEGIN
    INSERT INTO template_twin_certifications (
      id, "compiledVersionId", "certifiedById", "compiledStructureSha256",
      "approvedMappingsSha256", "syntheticTestManifest",
      "testOutputObjectKey", "testOutputVersionId", "testOutputEtag",
      "testOutputSha256"
    ) VALUES (
      'tt-q-contract-cert-missing', 'tt-q-contract-compiled-missing',
      'tt-q-contract-doctor', repeat('3', 64), repeat('6', 64), '{}'::jsonb,
      'practices/tt-q-contract-practice/template-twin/outputs/contract-missing.docx',
      'output-version-missing', 'output-etag-missing', repeat('5', 64)
    );
    RAISE EXCEPTION 'TT_QUARANTINE_CERTIFICATION_CONTRACT_DID_NOT_BLOCK';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE '%certification quarantine admission mismatch%' THEN
      RAISE;
    END IF;
  END;
END;
$$;

DO $$
BEGIN
  IF (SELECT count(*) FROM template_twin_certifications
      WHERE id = 'tt-q-contract-cert-good') <> 1 THEN
    RAISE EXCEPTION 'TT_QUARANTINE_CERTIFICATION_CONTRACT_VALID_PATH_FAILED';
  END IF;
END;
$$;

SELECT 'PASS template-twin-quarantine-certification-contract-v1';
ROLLBACK;
