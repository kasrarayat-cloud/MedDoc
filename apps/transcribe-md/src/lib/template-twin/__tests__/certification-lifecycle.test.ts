import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  certificationCreate: vi.fn(),
  compiledUpdate: vi.fn(),
  fieldUpdateMany: vi.fn(),
  findTemplate: vi.fn(),
  logAudit: vi.fn(),
  mappingUpdate: vi.fn(),
  noteTemplateUpdate: vi.fn(),
  noteTemplateUpdateMany: vi.fn(),
  readWorkspace: vi.fn(),
  transaction: vi.fn(),
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
    templateTwinSemanticMapping: { update: mocks.mappingUpdate },
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

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/lib/template-twin/workspace-read', () => ({
  readTemplateTwinWorkspace: mocks.readWorkspace,
}));

import {
  certifyAndActivateTemplateTwin,
  updateTemplateTwinMappings,
} from '../certification-lifecycle';
import {
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';
import { createOutputArtifactKey } from '../storage';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { canonicalSha256 } from '../canonical';
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from './integration-fixture';

const ACTOR = {
  userId: 'doctor-synthetic-lifecycle',
  userEmail: 'lifecycle-doctor@synthetic.test',
  practiceId: 'practice-synthetic-lifecycle',
};
const TEMPLATE_ID = 'template-synthetic-lifecycle';
const COMPILED_ID = 'compiled-synthetic-lifecycle';
const OUTPUT_SHA = 'b'.repeat(64);

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
    verified: true,
    packageCheck: 'verified',
    fieldCheck: 'verified',
    staticRegionCheck: 'verified',
    sourceSha256: ir.source.sha256,
    outputSha256,
    untouchedEntriesVerified: 8,
    modifiedPartsVerified: 1,
    fields: ir.fields.map((field) =>
      ({
        fieldId: field.fieldId,
        partName: field.rendererBinding.partName,
        bindingPath: field.rendererBinding.path,
        valueSha256: canonicalSha256({
          fieldId: field.fieldId,
          value: resolutions.get(field.fieldId)?.value,
        }),
        occurrences:
          field.rowPrototype && Array.isArray(resolutions.get(field.fieldId)?.value)
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
    compiledVersionId: COMPILED_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: 'synthetic-model-v1',
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
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

function ownedRow(ir: TemplateDocIR, baseMappings: readonly SemanticMapping[], options: RowOptions = {}) {
  const mappings = options.mappings ?? baseMappings;
  const includeProof = options.includeSyntheticProof ?? true;
  const outputSha256 = options.latestTestOutputSha256 ?? OUTPUT_SHA;
  const manifest =
    options.latestSyntheticTestManifest ?? validSyntheticManifest(ir, mappings);
  const parsedProofManifest = TemplateTwinFillManifestSchema.safeParse(manifest);
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
      latestSyntheticTestManifest: includeProof
        ? manifest
        : null,
      latestTestMappingsSha256: includeProof
        ? templateTwinMappingsSha256(mappings)
        : null,
      latestTestOutputObjectKey: includeProof
        ? options.latestTestOutputObjectKey ??
          createOutputArtifactKey({
              practiceId: ACTOR.practiceId,
              visitId: `synthetic_${COMPILED_ID}`,
              manifestSha256,
              outputSha256,
              idFactory: () => 'artifact-synthetic-lifecycle',
            })
        : null,
      latestTestOutputSha256: includeProof ? outputSha256 : null,
      latestTestStaticContentSha256: includeProof
        ? options.latestTestStaticContentSha256 ?? ir.staticContentSha256
        : null,
      latestTestRoundTrip: includeProof
        ? options.latestTestRoundTrip ??
          validRoundTrip(ir, proofManifest, outputSha256)
        : null,
      latestTestVerifiedAt: includeProof
        ? new Date('2026-07-15T12:00:00.000Z')
        : null,
      certification: null,
      sourceArtifact: {
        practiceId: options.practiceId ?? ACTOR.practiceId,
        sha256: ir.source.sha256,
      },
      fields: ir.fields.map((field, index) => ({
        id: `field-definition-synthetic-${index + 1}`,
        fieldId: field.fieldId,
        detectionStatus: field.detectionStatus.toUpperCase(),
        mapping: persistedMapping(mappings[index]!, index),
      })),
    },
  };
}

function workspace(ir: TemplateDocIR, mappings: readonly SemanticMapping[], certified = false) {
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
    })),
    unsupported: ir.unsupported,
    mappingsSha256: templateTwinMappingsSha256(mappings),
    latestSyntheticTest: null,
    canEdit: !certified,
  };
}

beforeEach(async () => {
  vi.clearAllMocks();
  const database = await import('@meddoc/db');
  const tx = (database as unknown as { __tx: unknown }).__tx;
  mocks.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  mocks.logAudit.mockResolvedValue(undefined);
  mocks.mappingUpdate.mockResolvedValue({});
  mocks.compiledUpdate.mockResolvedValue({});
  mocks.fieldUpdateMany.mockResolvedValue({ count: 1 });
  mocks.noteTemplateUpdateMany.mockResolvedValue({ count: 1 });
  mocks.noteTemplateUpdate.mockResolvedValue({});
  mocks.certificationCreate.mockResolvedValue({ id: 'certification-synthetic-1' });
});

describe('Template Twin certification lifecycle service', () => {
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
    mocks.findTemplate.mockResolvedValue(ownedRow(fixture.ir, fixture.mappings));

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
    expect(mocks.transaction).toHaveBeenCalledWith(
      expect.any(Function),
      { isolationLevel: 'Serializable' },
    );
  });

  it('updates the exact field set and invalidates the prior synthetic proof', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const changed = fixture.mappings.map((mapping, index) =>
      index === 0 ? { ...mapping, required: !mapping.required } : mapping,
    );
    mocks.findTemplate.mockResolvedValue(ownedRow(fixture.ir, fixture.mappings));
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
        latestTestOutputObjectKey: null,
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
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
        metadata: expect.objectContaining({
          mappingCount: fixture.ir.fields.length,
          mappingsSha256: templateTwinMappingsSha256(changed),
        }),
      }),
    );
  });

  it.each([
    'unconfirmed mapping',
    'missing synthetic proof',
    'blocking unsupported structure',
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
        compiledStructureSha256: fixture.ir.structureSha256,
        approvedMappingsSha256: mappingHash,
        syntheticTestManifest:
          row.templateTwinCompiledVersion.latestSyntheticTestManifest,
        testOutputObjectKey:
          row.templateTwinCompiledVersion.latestTestOutputObjectKey,
        testOutputSha256: OUTPUT_SHA,
      },
    });
    expect(mocks.noteTemplateUpdateMany.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.noteTemplateUpdate.mock.invocationCallOrder[0]!,
    );
    expect(mocks.noteTemplateUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.certificationCreate.mock.invocationCallOrder[0]!,
    );
    expect(mocks.logAudit).toHaveBeenCalledTimes(2);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'TEMPLATE_TWIN_CERTIFIED' }),
    );
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'TEMPLATE_TWIN_ACTIVATED' }),
    );
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
          index === 0 ? { ...field, occurrences: field.occurrences + 1 } : field,
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
  ])('rejects a synthetic proof with an invalid $mismatch', async ({ mutate }) => {
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
  });
});
