import { createHash } from 'node:crypto';

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  certificationCreate: vi.fn(),
  compiledUpdate: vi.fn(),
  fieldUpdateMany: vi.fn(),
  findTemplate: vi.fn(),
  intentCreate: vi.fn(),
  mappingUpdate: vi.fn(),
  noteTemplateUpdate: vi.fn(),
  noteTemplateUpdateMany: vi.fn(),
  outboxCreate: vi.fn(),
  readWorkspace: vi.fn(),
  transaction: vi.fn(),
  waiverCreateMany: vi.fn(),
  finalRollout: vi.fn(),
}));

vi.mock('@meddoc/db', () => {
  const tx = {
    noteTemplate: {
      findFirst: mocks.findTemplate,
      update: mocks.noteTemplateUpdate,
      updateMany: mocks.noteTemplateUpdateMany,
    },
    templateTwinCertification: { create: mocks.certificationCreate },
    templateTwinCompiledVersion: { update: mocks.compiledUpdate },
    templateTwinFieldDefinition: { updateMany: mocks.fieldUpdateMany },
    templateTwinFieldIntentDecision: { create: mocks.intentCreate },
    templateTwinSemanticMapping: { update: mocks.mappingUpdate },
    templateTwinFieldTestWaiver: { createMany: mocks.waiverCreateMany },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  };
  return {
    default: {
      $transaction: mocks.transaction,
    },
    prisma: {
      $transaction: mocks.transaction,
    },
    __tx: tx,
  };
});

vi.mock('@/lib/template-twin/workspace-read', () => ({
  readTemplateTwinWorkspace: mocks.readWorkspace,
}));

vi.mock('../rollout', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../rollout')>();
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

// Provider-ledger behavior has its own exact unit/PG suites. These lifecycle
// tests keep their historical in-memory provider seam so privacy failures are
// asserted without requiring a second database emulator.
vi.mock('../provider-ownership', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('../provider-ownership')
  >();
  return {
    ...actual,
    runWithTemplateTwinProviderOwnershipContext: async <T>(
      _context: unknown,
      callback: () => Promise<T>,
    ) => callback(),
  };
});

import {
  certifyAndActivateTemplateTwin,
  updateTemplateTwinMappings,
} from '../certification-lifecycle';
import {
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  SemanticMappingSchema,
  templateTwinCounts,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import { createOutputArtifactKey } from '../storage';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { canonicalSha256 } from '../canonical';
import { canonicalSoapSha256 } from '../soap-binding';
import {
  TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
  TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
  nativeIdentityFromRendererBinding,
} from '../../note-template-docx/binding-fingerprint';
import { templateTwinSyntheticTestProvenanceSha256 } from '../synthetic-test-provenance';
import {
  parsePersistedFieldIntent,
  templateTwinFieldIntentsSha256,
  unresolvedFieldIntent,
  type PersistedTemplateTwinFieldIntent,
} from '../field-intent';
import { compileTemplateDocx } from '../../note-template-docx/compiler';
import { buildSyntheticDocx } from '../../note-template-docx/__tests__/synthetic-docx';
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from './integration-fixture';
import { TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 } from '../staging-qa-fixtures';
import { TemplateTwinSyntheticEvidenceScanUnavailableError } from '../synthetic-evidence-gate';

const ACTOR = {
  userId: 'doctor-synthetic-lifecycle',
  userEmail: 'lifecycle-doctor@synthetic.test',
  practiceId: 'practice-synthetic-lifecycle',
  rolloutToken: {
    practiceId: 'practice-synthetic-lifecycle',
    globalGeneration: BigInt(5),
    practiceGeneration: BigInt(8),
  },
};
const TEMPLATE_ID = 'template-synthetic-lifecycle';
const COMPILED_ID = 'compiled-synthetic-lifecycle';
const OUTPUT_SHA = 'b'.repeat(64);
const EMPTY_FIELD_INTENTS_SHA256 = templateTwinFieldIntentsSha256([]);
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: 'template-twin-source-phi-safe-alpha-v1' as const,
  provider: 'anthropic' as const,
  model: 'synthetic-privacy-model-v1',
  scannedAt: '2026-07-15T12:00:00.000Z',
  scannedPartCount: 8,
  approvedStaticAssetPolicySha256: 'a'.repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: 'b'.repeat(64),
};

function validQuarantineEvidence(input: {
  rawSha256: string;
  rawSizeBytes: number;
  minimizedSha256: string;
}) {
  const malware = {
    profileVersion: 'template-twin-clamd-instream-v1',
    scanner: 'clamav-clamd',
    transport: 'unix-domain-socket',
    engineVersion: '1.4.3',
    signatureVersion: '27888',
    sourceSha256: input.rawSha256,
    sourceSizeBytes: input.rawSizeBytes,
    verdict: 'clean',
    threatNameSha256: null,
    scannedAt: '2026-07-15T11:30:00.000Z',
  } as const;
  return {
    practiceId: ACTOR.practiceId,
    lineageId: 'lineage-synthetic-lifecycle',
    intakeMode: 'NATIVE_TEMPLATE',
    sha256: input.rawSha256,
    sizeBytes: input.rawSizeBytes,
    status: 'ADMITTED',
    malwareScanEvidence: {
      ...malware,
      attestationSha256: createHash('sha256')
        .update(JSON.stringify(malware))
        .digest('hex'),
    },
    metadataMinimizationEvidence: {
      profileVersion: 'template-twin-docx-metadata-minimization-v1',
      originalSha256: input.rawSha256,
      minimizedSha256: input.minimizedSha256,
      replacedParts: [] as string[],
      zipEntryTimestampsNormalized: true,
    },
    rejectionCodes: [] as string[],
    scannedAt: new Date(malware.scannedAt),
    admittedAt: new Date('2026-07-15T11:31:00.000Z'),
  };
}

interface RowOptions {
  mappings?: readonly SemanticMapping[];
  practiceId?: string;
  blockingUnsupportedCount?: number;
  includeSyntheticProof?: boolean;
  latestTestStaticContentSha256?: string;
  latestTestOutputSha256?: string;
  latestTestOutputObjectKey?: string;
  latestSyntheticTestManifest?: unknown;
  latestTestRoundTrip?: unknown;
  latestTestVerifiedAt?: Date;
  privacyScanEvidence?: unknown;
  validationStatus?: string;
  quarantineArtifact?: ReturnType<typeof validQuarantineEvidence> | null;
}

function validRoundTrip(
  ir: TemplateDocIR,
  manifest: { fields: Array<{ fieldId: string; value: unknown }> },
  outputSha256 = OUTPUT_SHA,
) {
  const resolutions = new Map(
    manifest.fields.map((field) => [field.fieldId, field]),
  );
  return {
    verificationContractVersion: TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
    verified: true,
    packageCheck: 'verified',
    fieldCheck: 'verified',
    staticRegionCheck: 'verified',
    sourceSha256: ir.source.sha256,
    outputSha256,
    untouchedEntriesVerified: 8,
    modifiedPartsVerified: 1,
    sourcePrivacyScanEvidenceSha256: canonicalSha256(
      SOURCE_PRIVACY_SCAN_EVIDENCE,
    ),
    fields: ir.fields.map(
      (field) =>
        ({
          fieldId: field.fieldId,
          partName: field.rendererBinding.partName,
          bindingPath: field.rendererBinding.path,
          bindingEvidence: {
            contractVersion: TEMPLATE_TWIN_BINDING_FINGERPRINT_VERSION,
            status: 'verified',
            certifiedFingerprintSha256:
              field.rendererBinding.certifiedBindingSha256,
            outputFingerprintSha256:
              field.rendererBinding.certifiedBindingSha256,
            outputPartName: field.rendererBinding.partName,
            outputCanonicalPath: field.rendererBinding.canonicalPath,
            outputBindingType: field.rendererBinding.bindingType,
            ...(field.rendererBinding.bindingProfile === undefined
              ? {}
              : {
                  outputBindingProfile: field.rendererBinding.bindingProfile,
                }),
            outputBindingOrdinal: field.rendererBinding.ordinal,
            outputNativeIdentity: nativeIdentityFromRendererBinding(
              field.rendererBinding,
            ),
            outputBindingIdentitySha256:
              field.rendererBinding.sourceBindingIdentitySha256,
            outputTableLocation: {
              tableIndex: field.rendererBinding.tableIndex,
              rowIndex: field.rendererBinding.rowIndex,
              cellIndex: field.rendererBinding.cellIndex,
            },
          },
          valueSha256: canonicalSha256({
            fieldId: field.fieldId,
            value: resolutions.get(field.fieldId)?.value,
          }),
          occurrences:
            field.rowPrototype &&
            Array.isArray(resolutions.get(field.fieldId)?.value)
              ? (resolutions.get(field.fieldId)!.value as unknown[]).length
              : 1,
          status: 'verified',
        }) as const,
    ),
    warningCodes: [],
  };
}

function validSyntheticManifest(
  ir: TemplateDocIR,
  mappings: readonly SemanticMapping[],
) {
  const facts = factsForMode('text');
  const fields = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    allowUncertifiedForSyntheticTest: true,
  });
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions: fields,
    tables: ir.tables,
    unsupported: ir.unsupported,
    allowUncertifiedForSyntheticTest: true,
    now: '2026-07-15T12:00:00.000Z',
  });
  return TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    soapVersion: 1,
    soapSha256: canonicalSoapSha256(
      'Synthetic certification SOAP review evidence.',
    ),
    compiledVersionId: COMPILED_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: 'synthetic-model-v1',
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    fieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
    customExtraction: null,
    facts,
    fields,
    validation,
    counts: templateTwinCounts(fields, ir.fields),
  });
}

function persistedMapping(mapping: SemanticMapping, index: number) {
  return {
    id: `mapping-synthetic-${index + 1}`,
    clinicalConcept: mapping.clinicalConcept,
    expectedDataType: mapping.expectedDataType,
    polarityBehavior: mapping.polarityBehavior,
    temporality: mapping.temporality,
    laterality: mapping.laterality,
    unitPolicy: mapping.unitPolicy,
    approvedSynonyms: mapping.approvedSynonyms,
    required: mapping.required,
    blankPolicy: mapping.blankPolicy,
    unknownPolicy: mapping.unknownPolicy,
    practiceDefault: mapping.practiceDefault,
    mappingStatus: mapping.status.toUpperCase(),
  };
}

function ownedRow(
  ir: TemplateDocIR,
  baseMappings: readonly SemanticMapping[],
  options: RowOptions = {},
) {
  const mappings = options.mappings ?? baseMappings;
  const includeProof = options.includeSyntheticProof ?? true;
  const outputSha256 = options.latestTestOutputSha256 ?? OUTPUT_SHA;
  const manifest =
    options.latestSyntheticTestManifest ?? validSyntheticManifest(ir, mappings);
  const parsedProofManifest =
    TemplateTwinFillManifestSchema.safeParse(manifest);
  const proofManifest = parsedProofManifest.success
    ? parsedProofManifest.data
    : validSyntheticManifest(ir, mappings);
  const manifestSha256 = canonicalSha256(manifest);
  return {
    id: TEMPLATE_ID,
    doctorId: ACTOR.userId,
    encounterType: 'synthetic_follow_up',
    version: 1,
    status: 'draft',
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compiledDocumentIr: ir,
      certificationStatus: 'NEEDS_CONFIRMATION',
      blockingUnsupportedCount: options.blockingUnsupportedCount ?? 0,
      latestSyntheticTestManifest: includeProof ? manifest : null,
      latestTestMappingsSha256: includeProof
        ? templateTwinMappingsSha256(mappings)
        : null,
      latestTestFieldIntentsSha256: includeProof
        ? EMPTY_FIELD_INTENTS_SHA256
        : null,
      latestTestOutputObjectKey: includeProof
        ? (options.latestTestOutputObjectKey ??
          createOutputArtifactKey({
            practiceId: ACTOR.practiceId,
            visitId: `synthetic_${COMPILED_ID}`,
            manifestSha256,
            outputSha256,
            idFactory: () => 'artifact-synthetic-lifecycle',
          }))
        : null,
      latestTestOutputVersionId: includeProof
        ? 'provider-version-synthetic-1'
        : null,
      latestTestOutputEtag: includeProof ? 'provider-etag-synthetic-1' : null,
      latestTestOutputSha256: includeProof ? outputSha256 : null,
      latestTestStaticContentSha256: includeProof
        ? (options.latestTestStaticContentSha256 ?? ir.staticContentSha256)
        : null,
      latestTestRoundTrip: includeProof
        ? (options.latestTestRoundTrip ??
          validRoundTrip(ir, proofManifest, outputSha256))
        : null,
      latestTestVerifiedAt: includeProof
        ? (options.latestTestVerifiedAt ?? new Date('2026-07-15T12:00:00.000Z'))
        : null,
      certification: null,
      sourceArtifact: {
        practiceId: options.practiceId ?? ACTOR.practiceId,
        lineageId: 'lineage-synthetic-lifecycle',
        objectVersionId: 'provider-source-version-synthetic-1',
        objectEtag: 'provider-source-etag-synthetic-1',
        sha256: ir.source.sha256,
        sizeBytes: ir.source.sizeBytes,
        validationStatus: options.validationStatus ?? 'accepted',
        privacyScanEvidence:
          options.privacyScanEvidence === undefined
            ? SOURCE_PRIVACY_SCAN_EVIDENCE
            : options.privacyScanEvidence,
        quarantineArtifact:
          options.quarantineArtifact === undefined
            ? validQuarantineEvidence({
                rawSha256: 'e'.repeat(64),
                rawSizeBytes: ir.source.sizeBytes + 17,
                minimizedSha256: ir.source.sha256,
              })
            : options.quarantineArtifact,
      },
      fields: ir.fields.map((field, index) => ({
        id: `field-definition-synthetic-${index + 1}`,
        fieldId: field.fieldId,
        detectionStatus: field.detectionStatus.toUpperCase(),
        intentDecisions: [] as Array<
          Omit<
            PersistedTemplateTwinFieldIntent,
            'fieldDefinitionId' | 'fieldId'
          >
        >,
        mapping: persistedMapping(mappings[index]!, index),
      })),
    },
  };
}

function syntheticTestProvenanceSha256(
  row: ReturnType<typeof ownedRow>,
): string {
  const compiled = row.templateTwinCompiledVersion;
  const digest = templateTwinSyntheticTestProvenanceSha256({
    compiledVersionId: compiled.id,
    latestSyntheticTestManifest: compiled.latestSyntheticTestManifest,
    latestTestMappingsSha256: compiled.latestTestMappingsSha256,
    latestTestFieldIntentsSha256:
      compiled.latestTestFieldIntentsSha256,
    latestTestOutputObjectKey: compiled.latestTestOutputObjectKey,
    latestTestOutputVersionId: compiled.latestTestOutputVersionId,
    latestTestOutputEtag: compiled.latestTestOutputEtag,
    latestTestOutputSha256: compiled.latestTestOutputSha256,
    latestTestStaticContentSha256: compiled.latestTestStaticContentSha256,
    latestTestRoundTrip: compiled.latestTestRoundTrip,
    latestTestVerifiedAt: compiled.latestTestVerifiedAt,
  });
  if (!digest)
    throw new Error('Synthetic test provenance fixture is incomplete');
  return digest;
}

function workspace(
  ir: TemplateDocIR,
  mappings: readonly SemanticMapping[],
  certified = false,
) {
  return {
    template: {
      id: TEMPLATE_ID,
      lineageId: 'lineage-synthetic-lifecycle',
      version: 1,
      name: 'Synthetic original Word template',
      encounterType: 'synthetic_follow_up',
      status: certified ? 'active' : 'draft',
      certificationStatus: certified ? 'certified' : 'needs_confirmation',
    },
    source: {
      sha256: ir.source.sha256,
      sizeBytes: ir.source.sizeBytes,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      compiledAtIso: '2026-07-15T11:00:00.000Z',
      compilerVersion: ir.compilerVersion,
    },
    stats: ir.stats,
    fields: ir.fields.map((field, index) => ({
      definitionId: `field-definition-synthetic-${index + 1}`,
      field,
      mapping: mappings[index]!,
      intent: unresolvedFieldIntent(),
      customConceptScaffold: null,
    })),
    unsupported: ir.unsupported,
    mappingsSha256: templateTwinMappingsSha256(mappings),
    fieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
    latestSyntheticTest: null,
    canEdit: !certified,
  };
}

async function ordinaryPlaceholderLifecycleFixture() {
  const source = await buildSyntheticDocx({
    documentXml:
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
      '<w:body><w:p><w:r><w:t>&lt;&lt;insert synthetic clinical detail&gt;&gt;</w:t></w:r></w:p>' +
      '<w:sectPr/></w:body></w:document>',
  });
  const ir = compileTemplateDocx(source);
  const field = ir.fields.find(
    (candidate) =>
      candidate.rendererBinding.bindingType === 'ordinary_placeholder',
  );
  if (!field) throw new Error('Synthetic placeholder was not compiled.');
  const fieldIndex = ir.fields.findIndex(
    (candidate) => candidate.fieldId === field.fieldId,
  );
  const initialMappings = ir.fields.map((candidate) =>
    SemanticMappingSchema.parse({
      fieldId: candidate.fieldId,
      clinicalConcept:
        candidate.fieldId === field.fieldId
          ? null
          : 'chief_complaint',
      expectedDataType: 'text',
      polarityBehavior: 'value_only',
      temporality: 'any',
      laterality: 'optional',
      unitPolicy: 'not_applicable',
      approvedSynonyms: [],
      required: false,
      blankPolicy: 'blank',
      unknownPolicy: 'requires_input',
      practiceDefault: null,
      status:
        candidate.fieldId === field.fieldId
          ? 'needs_confirmation'
          : 'certified',
    }),
  );
  const approvedMappings = initialMappings.map((mapping) =>
    mapping.fieldId === field.fieldId
      ? SemanticMappingSchema.parse({
          ...mapping,
          clinicalConcept: 'chief_complaint',
          status: 'certified',
        })
      : mapping,
  );
  return { ir, field, fieldIndex, initialMappings, approvedMappings };
}

beforeEach(async () => {
  vi.clearAllMocks();
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: ACTOR.rolloutToken,
  });
  const database = await import('@meddoc/db');
  const tx = (database as unknown as { __tx: unknown }).__tx;
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  mocks.mappingUpdate.mockResolvedValue({});
  mocks.intentCreate.mockResolvedValue({});
  mocks.compiledUpdate.mockResolvedValue({});
  mocks.fieldUpdateMany.mockResolvedValue({ count: 1 });
  mocks.noteTemplateUpdateMany.mockResolvedValue({ count: 1 });
  mocks.noteTemplateUpdate.mockResolvedValue({});
  mocks.certificationCreate.mockResolvedValue({
    id: 'certification-synthetic-1',
  });
  mocks.waiverCreateMany.mockResolvedValue({ count: 0 });
  mocks.outboxCreate.mockResolvedValue({ id: 'outbox-synthetic-1' });
});

describe('Template Twin certification lifecycle service', () => {
  it.each([
    ['mapping and field-intent update', 'mapping'] as const,
    ['certification and activation', 'certification'] as const,
  ])(
    'rejects a stale rollout token before any %s state is read or written',
    async (_name, operation) => {
      mocks.finalRollout.mockResolvedValueOnce({
        allowed: false,
        code: 'TEMPLATE_TWIN_GLOBAL_GENERATION_STALE',
        reason: 'Synthetic global generation changed.',
        currentToken: {
          practiceId: ACTOR.practiceId,
          globalGeneration: BigInt(6),
          practiceGeneration: BigInt(8),
        },
      });

      const pending =
        operation === 'mapping'
          ? updateTemplateTwinMappings({
              noteTemplateId: TEMPLATE_ID,
              actor: ACTOR,
              expectedMappingsSha256: 'a'.repeat(64),
              mappings: [],
              fieldIntents: [],
            })
          : certifyAndActivateTemplateTwin({
              noteTemplateId: TEMPLATE_ID,
              actor: ACTOR,
              expectedMappingsSha256: 'a'.repeat(64),
            });

      await expect(pending).rejects.toMatchObject({
        code: 'ROLLOUT_CHANGED',
        message: expect.stringContaining(
          'TEMPLATE_TWIN_GLOBAL_GENERATION_STALE',
        ),
      });
      expect(mocks.findTemplate).not.toHaveBeenCalled();
      expect(mocks.mappingUpdate).not.toHaveBeenCalled();
      expect(mocks.compiledUpdate).not.toHaveBeenCalled();
      expect(mocks.certificationCreate).not.toHaveBeenCalled();
      expect(mocks.outboxCreate).not.toHaveBeenCalled();
    },
  );

  it('fails opaquely for another doctor and another practice before any write', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.findTemplate.mockResolvedValueOnce(null);

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        mappings: fixture.mappings,
      }),
    ).rejects.toMatchObject({ code: 'NOT_FOUND' });
    expect(mocks.findTemplate).toHaveBeenLastCalledWith(
      expect.objectContaining({
        where: {
          id: TEMPLATE_ID,
          doctorId: ACTOR.userId,
          templateKind: 'template_twin_docx',
        },
      }),
    );

    mocks.findTemplate.mockResolvedValueOnce(
      ownedRow(fixture.ir, fixture.mappings, {
        practiceId: 'practice-synthetic-other',
      }),
    );
    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      }),
    ).rejects.toMatchObject({ code: 'NOT_FOUND' });

    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
    expect(mocks.certificationCreate).not.toHaveBeenCalled();
  });

  it('rejects a stale mapping hash before invalidating proof or updating mappings', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings),
    );

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: 'f'.repeat(64),
        mappings: fixture.mappings,
      }),
    ).rejects.toMatchObject({ code: 'CONFLICT' });

    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
    expect(mocks.transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: 'Serializable',
    });
  });

  it('records physician-confirmed placeholder intent atomically and resets synthetic proof', async () => {
    const fixture = await ordinaryPlaceholderLifecycleFixture();
    const unresolvedHash = templateTwinFieldIntentsSha256([
      { fieldId: fixture.field.fieldId, intent: unresolvedFieldIntent() },
    ]);
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.initialMappings, {
        includeSyntheticProof: false,
      }),
    );
    mocks.readWorkspace.mockResolvedValue(
      workspace(fixture.ir, fixture.approvedMappings),
    );

    await updateTemplateTwinMappings({
      noteTemplateId: TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: templateTwinMappingsSha256(
        fixture.initialMappings,
      ),
      expectedFieldIntentsSha256: unresolvedHash,
      mappings: fixture.approvedMappings,
      fieldIntents: [
        {
          fieldId: fixture.field.fieldId,
          intentKind: 'supported_concept',
          supportedConcept: 'chief_complaint',
        },
      ],
    });

    expect(mocks.intentCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        fieldDefinitionId: `field-definition-synthetic-${fixture.fieldIndex + 1}`,
        version: 1,
        intentKind: 'SUPPORTED_CONCEPT',
        supportedConcept: 'chief_complaint',
        decidedById: ACTOR.userId,
      }),
    });
    expect(mocks.compiledUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          latestTestMappingsSha256: null,
          latestTestFieldIntentsSha256: null,
          latestSyntheticTestManifest: expect.anything(),
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_FIELD_INTENT_RECORDED',
        actorId: ACTOR.userId,
      }),
    });
  });

  it('does not fan out or blame a field when the authored-corpus privacy scan is unavailable', async () => {
    const fixture = await ordinaryPlaceholderLifecycleFixture();
    const unresolvedHash = templateTwinFieldIntentsSha256([
      { fieldId: fixture.field.fieldId, intent: unresolvedFieldIntent() },
    ]);
    const staticMappings = fixture.initialMappings.map((mapping) =>
      mapping.fieldId === fixture.field.fieldId
        ? SemanticMappingSchema.parse({
            ...mapping,
            clinicalConcept: null,
            required: false,
            practiceDefault: null,
            status: 'certified',
          })
        : mapping,
    );
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.initialMappings, {
        includeSyntheticProof: false,
      }),
    );
    const privacyClient = {
      complete: vi.fn().mockRejectedValue(new Error('provider unavailable')),
    };

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(
          fixture.initialMappings,
        ),
        expectedFieldIntentsSha256: unresolvedHash,
        mappings: staticMappings,
        fieldIntents: [
          {
            fieldId: fixture.field.fieldId,
            intentKind: 'static',
            reason:
              'Synthetic fixed wording remains unchanged in this template.',
          },
        ],
        privacyClient,
      }),
    ).rejects.toBeInstanceOf(
      TemplateTwinSyntheticEvidenceScanUnavailableError,
    );

    expect(privacyClient.complete).toHaveBeenCalledTimes(1);
    expect(mocks.intentCreate).not.toHaveBeenCalled();
    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
  });

  it('fails closed when a placeholder-bearing mapping request omits its intent generation hash', async () => {
    const fixture = await ordinaryPlaceholderLifecycleFixture();
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.initialMappings, {
        includeSyntheticProof: false,
      }),
    );

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(
          fixture.initialMappings,
        ),
        mappings: fixture.approvedMappings,
        fieldIntents: [
          {
            fieldId: fixture.field.fieldId,
            intentKind: 'supported_concept',
            supportedConcept: 'chief_complaint',
          },
        ],
      }),
    ).rejects.toMatchObject({
      code: 'CONFLICT',
      message: expect.stringContaining('field-intent draft changed'),
    });
    expect(mocks.intentCreate).not.toHaveBeenCalled();
    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
  });

  it('requires a new template version before changing recorded placeholder intent', async () => {
    const fixture = await ordinaryPlaceholderLifecycleFixture();
    const row = ownedRow(fixture.ir, fixture.approvedMappings, {
      includeSyntheticProof: false,
    });
    const decision = {
      id: 'intent-synthetic-1',
      version: 1,
      intentKind: 'SUPPORTED_CONCEPT',
      supportedConcept: 'chief_complaint',
      customConceptId: null,
      customSpec: null,
      customSpecSha256: null,
      reason: null,
      decidedById: ACTOR.userId,
      decidedAt: new Date('2026-07-15T12:00:00.000Z'),
    };
    row.templateTwinCompiledVersion.fields[
      fixture.fieldIndex
    ]!.intentDecisions = [decision];
    const intent = parsePersistedFieldIntent({
      ...decision,
      fieldDefinitionId: `field-definition-synthetic-${fixture.fieldIndex + 1}`,
      fieldId: fixture.field.fieldId,
    });
    mocks.findTemplate.mockResolvedValue(row);

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(
          fixture.approvedMappings,
        ),
        expectedFieldIntentsSha256: templateTwinFieldIntentsSha256([
          { fieldId: fixture.field.fieldId, intent },
        ]),
        mappings: fixture.approvedMappings.map((mapping) =>
          mapping.fieldId === fixture.field.fieldId
            ? SemanticMappingSchema.parse({
                ...mapping,
                clinicalConcept: null,
                required: false,
              })
            : mapping,
        ),
        fieldIntents: [
          {
            fieldId: fixture.field.fieldId,
            intentKind: 'static',
            reason:
              'Synthetic fixed wording must remain unchanged in this version.',
          },
        ],
      }),
    ).rejects.toMatchObject({
      code: 'IMMUTABLE',
      message: expect.stringContaining('Create a new draft version'),
    });
    expect(mocks.intentCreate).not.toHaveBeenCalled();
    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
  });

  it.each([
    'gad_7.total_score',
    'pregnancy.status',
    'exam.monofilament',
    'measurement.custom_ankle_width',
  ])(
    'rejects unsupported safe-alpha mapping %s before persistence',
    async (concept) => {
      const fixture = await buildTemplateTwinIntegrationFixture();
      const unsupported = fixture.mappings.map((mapping, index) =>
        index === 0 ? { ...mapping, clinicalConcept: concept } : mapping,
      );
      mocks.findTemplate.mockResolvedValue(
        ownedRow(fixture.ir, fixture.mappings),
      );

      await expect(
        updateTemplateTwinMappings({
          noteTemplateId: TEMPLATE_ID,
          actor: ACTOR,
          expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
          mappings: unsupported,
        }),
      ).rejects.toMatchObject({
        code: 'UNSUPPORTED_CLINICAL_CONCEPT',
        message: expect.stringContaining('TT_CONCEPT_UNSUPPORTED_V1'),
      });

      expect(mocks.mappingUpdate).not.toHaveBeenCalled();
      expect(mocks.compiledUpdate).not.toHaveBeenCalled();
    },
  );

  it('identifies the exact reviewed-fixture field and synonym setting before persistence', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const row = ownedRow(fixture.ir, fixture.mappings);
    row.templateTwinCompiledVersion.sourceArtifact.sha256 =
      TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256;
    mocks.findTemplate.mockResolvedValue(row);
    const changed = fixture.mappings.map((mapping, index) =>
      index === 0
        ? SemanticMappingSchema.parse({
            ...mapping,
            approvedSynonyms: ['synthetic alias'],
          })
        : mapping,
    );

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        mappings: changed,
      }),
    ).rejects.toMatchObject({
      code: 'MAPPING_INVALID',
      fieldErrors: [
        {
          fieldId: fixture.ir.fields[0]!.fieldId,
          fieldLabel: fixture.ir.fields[0]!.originalLabel,
          setting: 'approvedSynonyms',
          message: expect.stringMatching(/does not allow additional synonyms/u),
        },
      ],
    });
    expect(mocks.mappingUpdate).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
  });

  it('updates the exact field set and invalidates the prior synthetic proof', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const changed = fixture.mappings.map((mapping, index) =>
      index === 0 ? { ...mapping, required: !mapping.required } : mapping,
    );
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings),
    );
    mocks.readWorkspace.mockResolvedValue(workspace(fixture.ir, changed));

    const result = await updateTemplateTwinMappings({
      noteTemplateId: TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      mappings: changed,
    });

    expect(result.mappingsSha256).toBe(templateTwinMappingsSha256(changed));
    expect(mocks.mappingUpdate).toHaveBeenCalledTimes(fixture.ir.fields.length);
    expect(mocks.mappingUpdate).toHaveBeenCalledWith({
      where: { id: 'mapping-synthetic-1' },
      data: expect.objectContaining({
        required: changed[0]!.required,
        mappingStatus: 'CERTIFIED',
        approvedById: ACTOR.userId,
        approvedAt: expect.any(Date),
      }),
    });
    expect(mocks.compiledUpdate).toHaveBeenCalledWith({
      where: { id: COMPILED_ID },
      data: {
        certificationStatus: 'NEEDS_CONFIRMATION',
        latestSyntheticTestManifest: expect.anything(),
        latestTestMappingsSha256: null,
        latestTestFieldIntentsSha256: null,
        latestTestOutputObjectKey: null,
        latestTestOutputVersionId: null,
        latestTestOutputEtag: null,
        latestTestOutputSha256: null,
        latestTestStaticContentSha256: null,
        latestTestRoundTrip: expect.anything(),
        latestTestVerifiedAt: null,
      },
    });
    expect(mocks.readWorkspace).toHaveBeenCalledWith({
      noteTemplateId: TEMPLATE_ID,
      doctorId: ACTOR.userId,
      practiceId: ACTOR.practiceId,
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
        targetType: 'TemplateTwinCompiledVersion',
        targetId: COMPILED_ID,
        status: 'PENDING',
        metadata: expect.objectContaining({
          mappingCount: fixture.ir.fields.length,
          mappingsSha256: templateTwinMappingsSha256(changed),
        }),
      }),
    });
    expect(mocks.compiledUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.outboxCreate.mock.invocationCallOrder[0]!,
    );
  });

  it('fails the mapping transaction when its critical audit event cannot be enqueued', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const changed = fixture.mappings.map((mapping, index) =>
      index === 0 ? { ...mapping, required: !mapping.required } : mapping,
    );
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings),
    );
    mocks.readWorkspace.mockResolvedValue(workspace(fixture.ir, changed));
    mocks.outboxCreate.mockRejectedValueOnce(
      new Error('synthetic audit outbox unavailable'),
    );

    await expect(
      updateTemplateTwinMappings({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        mappings: changed,
      }),
    ).rejects.toThrow('synthetic audit outbox unavailable');

    expect(mocks.compiledUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
    expect(mocks.readWorkspace).not.toHaveBeenCalled();
  });

  it.each([
    'unconfirmed mapping',
    'missing synthetic proof',
    'blocking unsupported structure',
    'missing privacy evidence',
  ] as const)('blocks certification for %s', async (blocker) => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const mappings =
      blocker === 'unconfirmed mapping'
        ? fixture.mappings.map((mapping, index) =>
            index === 0
              ? { ...mapping, status: 'needs_confirmation' as const }
              : mapping,
          )
        : fixture.mappings;
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings, {
        mappings,
        includeSyntheticProof: blocker !== 'missing synthetic proof',
        blockingUnsupportedCount:
          blocker === 'blocking unsupported structure' ? 1 : 0,
        privacyScanEvidence:
          blocker === 'missing privacy evidence'
            ? null
            : SOURCE_PRIVACY_SCAN_EVIDENCE,
      }),
    );

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(mappings),
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });

    expect(mocks.fieldUpdateMany).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
    expect(mocks.certificationCreate).not.toHaveBeenCalled();
  });

  it('blocks certification when immutable quarantine admission evidence is missing or tampered', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const missing = ownedRow(fixture.ir, fixture.mappings, {
      quarantineArtifact: null,
    });
    const tampered = ownedRow(fixture.ir, fixture.mappings);
    const tamperedMalwareEvidence = tampered.templateTwinCompiledVersion
      .sourceArtifact.quarantineArtifact!.malwareScanEvidence as unknown as Record<
      string,
      unknown
    >;
    tamperedMalwareEvidence.signatureVersion = '99999';
    mocks.findTemplate
      .mockResolvedValueOnce(missing)
      .mockResolvedValueOnce(tampered);

    for (const row of [missing, tampered]) {
      await expect(
        certifyAndActivateTemplateTwin({
          noteTemplateId: TEMPLATE_ID,
          actor: ACTOR,
          expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
          expectedSyntheticTestProvenanceSha256:
            syntheticTestProvenanceSha256(row),
        }),
      ).rejects.toMatchObject({
        code: 'CERTIFICATION_BLOCKED',
        message: expect.stringContaining('quarantine record'),
      });
    }

    expect(mocks.fieldUpdateMany).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
    expect(mocks.certificationCreate).not.toHaveBeenCalled();
  });

  it('deactivates the prior template, activates this exact version, and appends certification', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const mappingHash = templateTwinMappingsSha256(fixture.mappings);
    const row = ownedRow(fixture.ir, fixture.mappings);
    mocks.findTemplate.mockResolvedValue(row);
    mocks.readWorkspace.mockResolvedValue(
      workspace(fixture.ir, fixture.mappings, true),
    );

    const result = await certifyAndActivateTemplateTwin({
      noteTemplateId: TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: mappingHash,
      expectedSyntheticTestProvenanceSha256: syntheticTestProvenanceSha256(row),
    });

    expect(result.template).toMatchObject({
      id: TEMPLATE_ID,
      status: 'active',
      certificationStatus: 'certified',
    });
    expect(mocks.fieldUpdateMany).toHaveBeenCalledWith({
      where: { compiledVersionId: COMPILED_ID },
      data: { detectionStatus: 'CERTIFIED' },
    });
    expect(mocks.compiledUpdate).toHaveBeenCalledWith({
      where: { id: COMPILED_ID },
      data: { certificationStatus: 'CERTIFIED' },
    });
    expect(mocks.noteTemplateUpdateMany).toHaveBeenCalledWith({
      where: {
        doctorId: ACTOR.userId,
        encounterType: 'synthetic_follow_up',
        status: 'active',
        NOT: { id: TEMPLATE_ID },
      },
      data: { status: 'inactive' },
    });
    expect(mocks.noteTemplateUpdate).toHaveBeenCalledWith({
      where: { id: TEMPLATE_ID },
      data: { status: 'active' },
    });
    expect(mocks.certificationCreate).toHaveBeenCalledWith({
      data: {
        compiledVersionId: COMPILED_ID,
        certifiedById: ACTOR.userId,
        providerAuthorizationMode: 'LIVE',
        providerAuthorizationAdmissionId: null,
        compiledStructureSha256: fixture.ir.structureSha256,
        approvedMappingsSha256: mappingHash,
        approvedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        approvedCustomExampleProofSha256: null,
        sourcePrivacyScanEvidenceSha256: canonicalSha256(
          SOURCE_PRIVACY_SCAN_EVIDENCE,
        ),
        syntheticTestManifest:
          row.templateTwinCompiledVersion.latestSyntheticTestManifest,
        testOutputObjectKey:
          row.templateTwinCompiledVersion.latestTestOutputObjectKey,
        testOutputVersionId:
          row.templateTwinCompiledVersion.latestTestOutputVersionId,
        testOutputEtag: row.templateTwinCompiledVersion.latestTestOutputEtag,
        testOutputSha256: OUTPUT_SHA,
      },
    });
    expect(mocks.certificationCreate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.noteTemplateUpdateMany.mock.invocationCallOrder[0]!,
    );
    expect(
      mocks.noteTemplateUpdateMany.mock.invocationCallOrder[0],
    ).toBeLessThan(mocks.noteTemplateUpdate.mock.invocationCallOrder[0]!);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(2);
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: `template-twin:certified:${COMPILED_ID}:${mappingHash}`,
        action: 'TEMPLATE_TWIN_CERTIFIED',
        status: 'PENDING',
        metadata: expect.objectContaining({
          syntheticTestProvenanceSha256: syntheticTestProvenanceSha256(row),
        }),
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: `template-twin:activated:${TEMPLATE_ID}:v1`,
        action: 'TEMPLATE_TWIN_ACTIVATED',
        status: 'PENDING',
      }),
    });
  });

  it('persists an actor- and mapping-bound waiver only for an optional unexercised field', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const ir: TemplateDocIR = {
      ...fixture.ir,
      fields: fixture.ir.fields.map((field, index) =>
        index === 0
          ? { ...field, required: false, clinicallyMaterial: false }
          : field,
      ),
    };
    const mappings = fixture.mappings.map((mapping, index) =>
      index === 0
        ? {
            ...mapping,
            required: false,
            blankPolicy: 'blank' as const,
            unknownPolicy: 'blank' as const,
          }
        : mapping,
    );
    const baseManifest = validSyntheticManifest(ir, mappings);
    const fields = baseManifest.fields.map((resolution, index) =>
      index === 0
        ? {
            ...resolution,
            status: 'not_mentioned' as const,
            value: null,
            sourceFactIds: [],
            evidenceAnchorIds: [],
            selectedOptionOrdinal: null,
            reasonCode: 'synthetic_optional_not_exercised',
          }
        : resolution,
    );
    const validation = validateTemplateTwin({
      fields: ir.fields,
      mappings,
      facts: baseManifest.facts,
      resolutions: fields,
      tables: ir.tables,
      unsupported: ir.unsupported,
      allowUncertifiedForSyntheticTest: true,
      now: baseManifest.validation.checkedAt,
    });
    const unexercisedManifest = TemplateTwinFillManifestSchema.parse({
      ...baseManifest,
      fields,
      validation,
      counts: templateTwinCounts(fields, ir.fields),
    });
    const row = ownedRow(ir, mappings, {
      latestSyntheticTestManifest: unexercisedManifest,
    });
    mocks.findTemplate.mockResolvedValue(row);

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(mappings),
      }),
    ).rejects.toMatchObject({
      code: 'CERTIFICATION_BLOCKED',
      message: expect.stringContaining('CERT_OPTIONAL_FIELD_NEEDS_WAIVER'),
    });
    expect(mocks.waiverCreateMany).not.toHaveBeenCalled();

    mocks.readWorkspace.mockResolvedValue(workspace(ir, mappings, true));
    await certifyAndActivateTemplateTwin({
      noteTemplateId: TEMPLATE_ID,
      actor: ACTOR,
      expectedMappingsSha256: templateTwinMappingsSha256(mappings),
      expectedSyntheticTestProvenanceSha256: syntheticTestProvenanceSha256(row),
      optionalFieldWaivers: [
        {
          fieldId: ir.fields[0]!.fieldId,
          reason:
            'Optional display field is not used for this encounter workflow.',
        },
      ],
    });

    expect(mocks.waiverCreateMany).toHaveBeenCalledWith({
      data: [
        expect.objectContaining({
          compiledVersionId: COMPILED_ID,
          fieldDefinitionId: 'field-definition-synthetic-1',
          fieldId: ir.fields[0]!.fieldId,
          mappingsSha256: templateTwinMappingsSha256(mappings),
          waivedById: ACTOR.userId,
          reason:
            'Optional display field is not used for this encounter workflow.',
          waivedAt: expect.any(Date),
        }),
      ],
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_FIELD_TEST_WAIVED',
        metadata: expect.objectContaining({
          fieldId: ir.fields[0]!.fieldId,
          mappingsSha256: templateTwinMappingsSha256(mappings),
        }),
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: 'TEMPLATE_TWIN_CERTIFIED',
        metadata: expect.objectContaining({ optionalFieldWaiverCount: 1 }),
      }),
    });
  });

  it('rejects a stale physician acknowledgement when another tab replaces the synthetic test', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const acknowledged = ownedRow(fixture.ir, fixture.mappings);
    const replacement = ownedRow(fixture.ir, fixture.mappings, {
      // The mappings and rendered bytes can be identical. A re-run is still a
      // new review boundary and must invalidate the older acknowledgement.
      latestTestVerifiedAt: new Date('2026-07-15T12:01:00.000Z'),
    });
    mocks.findTemplate.mockResolvedValue(replacement);

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        expectedSyntheticTestProvenanceSha256:
          syntheticTestProvenanceSha256(acknowledged),
      }),
    ).rejects.toMatchObject({
      code: 'CONFLICT',
      message: expect.stringContaining('synthetic test changed'),
    });

    expect(mocks.waiverCreateMany).not.toHaveBeenCalled();
    expect(mocks.fieldUpdateMany).not.toHaveBeenCalled();
    expect(mocks.compiledUpdate).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdate).not.toHaveBeenCalled();
    expect(mocks.certificationCreate).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it('rejects a synthetic proof whose static-content hash does not match the compiled IR', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings, {
        latestTestStaticContentSha256: '0'.repeat(64),
      }),
    );

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });

    expect(mocks.certificationCreate).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdate).not.toHaveBeenCalled();
  });

  it('rejects a synthetic proof whose output key is not bound to the actor tenant and digest', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings, {
        latestTestOutputObjectKey: createOutputArtifactKey({
          practiceId: 'practice-synthetic-other',
          visitId: `synthetic_${COMPILED_ID}`,
          manifestSha256: canonicalSha256(
            validSyntheticManifest(fixture.ir, fixture.mappings),
          ),
          outputSha256: OUTPUT_SHA,
          idFactory: () => 'artifact-synthetic-lifecycle',
        }),
      }),
    );

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });

    expect(mocks.certificationCreate).not.toHaveBeenCalled();
  });

  it('rejects a canonically keyed synthetic manifest whose clinical counts were tampered', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const manifest = validSyntheticManifest(fixture.ir, fixture.mappings);
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings, {
        latestSyntheticTestManifest: {
          ...manifest,
          counts: { ...manifest.counts, filled: 0 },
        },
      }),
    );

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });
    expect(mocks.certificationCreate).not.toHaveBeenCalled();
  });

  it.each([
    {
      mismatch: 'source hash',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        sourceSha256: '0'.repeat(64),
      }),
    },
    {
      mismatch: 'output hash',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        outputSha256: '0'.repeat(64),
      }),
    },
    {
      mismatch: 'package verification status',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        packageCheck: 'failed',
      }),
    },
    {
      mismatch: 'field verification status',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        fieldCheck: 'failed',
      }),
    },
    {
      mismatch: 'static-region verification status',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        staticRegionCheck: 'failed',
      }),
    },
    {
      mismatch: 'individual field proof status',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        fields: [{ ...proof.fields[0]!, status: 'failed' }],
      }),
    },
    {
      mismatch: 'field value hash',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        fields: proof.fields.map((field, index) =>
          index === 0 ? { ...field, valueSha256: '0'.repeat(64) } : field,
        ),
      }),
    },
    {
      mismatch: 'field occurrence count',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        fields: proof.fields.map((field, index) =>
          index === 0
            ? { ...field, occurrences: field.occurrences + 1 }
            : field,
        ),
      }),
    },
    {
      mismatch: 'warning-code shape',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        warningCodes: [42],
      }),
    },
    {
      mismatch: 'verification-count shape',
      mutate: (proof: ReturnType<typeof validRoundTrip>) => ({
        ...proof,
        untouchedEntriesVerified: -1,
      }),
    },
  ])(
    'rejects a synthetic proof with an invalid $mismatch',
    async ({ mutate }) => {
      const fixture = await buildTemplateTwinIntegrationFixture();
      mocks.findTemplate.mockResolvedValue(
        ownedRow(fixture.ir, fixture.mappings, {
          latestTestRoundTrip: mutate(
            validRoundTrip(
              fixture.ir,
              validSyntheticManifest(fixture.ir, fixture.mappings),
            ),
          ),
        }),
      );

      await expect(
        certifyAndActivateTemplateTwin({
          noteTemplateId: TEMPLATE_ID,
          actor: ACTOR,
          expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        }),
      ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });

      expect(mocks.certificationCreate).not.toHaveBeenCalled();
      expect(mocks.noteTemplateUpdate).not.toHaveBeenCalled();
    },
  );

  it('rejects certification when a profiled cell proof omits its output-derived profile', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const proof = structuredClone(
      validRoundTrip(
        fixture.ir,
        validSyntheticManifest(fixture.ir, fixture.mappings),
      ),
    ) as {
      fields: Array<{
        bindingEvidence: { outputBindingProfile?: string };
      }>;
    };
    const profiled = proof.fields.find(
      (field) =>
        field.bindingEvidence.outputBindingProfile ===
        'TAB_ONLY_BLANK_TABLE_CELL_V1',
    );
    expect(profiled).toBeDefined();
    delete profiled!.bindingEvidence.outputBindingProfile;
    mocks.findTemplate.mockResolvedValue(
      ownedRow(fixture.ir, fixture.mappings, {
        latestTestRoundTrip: proof,
      }),
    );

    await expect(
      certifyAndActivateTemplateTwin({
        noteTemplateId: TEMPLATE_ID,
        actor: ACTOR,
        expectedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      }),
    ).rejects.toMatchObject({ code: 'CERTIFICATION_BLOCKED' });

    expect(mocks.certificationCreate).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdate).not.toHaveBeenCalled();
  });
});
