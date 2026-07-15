import { TemplateTwinDetectionStatus } from '@prisma/client';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const audit = vi.hoisted(() => vi.fn());
vi.mock('@/lib/audit', () => ({ logAudit: audit }));

import { canonicalSha256 } from '../canonical';
import { type TemplateTwinFieldCorrectionRequest } from '../contracts';
import {
  TEMPLATE_TWIN_REVIEW_REASON,
  type FinalizeTemplateTwinFillInput,
  type PreparedTemplateTwinFill,
} from '../fill-engine';
import {
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from '../ir';
import {
  buildClinicianCorrection,
  reviewTemplateTwinField,
  TemplateTwinReviewError,
  type TemplateTwinReviewRepository,
} from '../review-service';
import { validateTemplateTwin } from '../validation';
import {
  DOCX_MIME_TYPE,
  type StoredTemplateTwinArtifact,
  type TemplateTwinArtifactStore,
} from '../storage';

const SHA = 'a'.repeat(64);
const OUTPUT_SHA = 'b'.repeat(64);
const FIELD_ID = `ttf_${'c'.repeat(24)}`;
const NOW = '2026-07-15T17:00:00.000Z';

type ReviewContext = NonNullable<
  Awaited<ReturnType<TemplateTwinReviewRepository['loadOwned']>>
>;
type CommitPlan = Parameters<TemplateTwinReviewRepository['commit']>[0];

function field(
  kind: TemplateField['kind'] = 'single_select',
  overrides: Partial<TemplateField> = {},
): TemplateField {
  return {
    fieldId: FIELD_ID,
    kind,
    originalLabel: 'Synthetic severity',
    labelSource: 'tag',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions:
      kind === 'single_select' || kind === 'multi_select'
        ? [
            { ordinal: 0, displayText: 'Mild', value: 'Mild' },
            { ordinal: 1, displayText: 'Severe', value: 'Severe' },
          ]
        : [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: '/document/body/sdt[0]',
      ordinal: 0,
      sdtId: '1',
      tag: 'synthetic_severity',
      alias: null,
      legacyName: null,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
    ...overrides,
  };
}

function mapping(
  definition: TemplateField,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  const dataTypes: Record<TemplateField['kind'], SemanticMapping['expectedDataType']> = {
    narrative_text: 'text',
    single_select: 'single_select',
    multi_select: 'multi_select',
    checkbox: 'boolean',
    date: 'date',
    number: 'number',
    measurement: 'measurement',
  };
  return {
    fieldId: definition.fieldId,
    clinicalConcept: 'hpi.severity',
    expectedDataType: dataTypes[definition.kind],
    polarityBehavior:
      definition.kind === 'checkbox'
        ? 'explicit_denial_allowed'
        : 'value_only',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy: definition.kind === 'measurement' ? 'required' : 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...overrides,
  };
}

function ir(definition = field()): TemplateDocIR {
  return {
    irSchemaVersion: 1,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    source: {
      sha256: SHA,
      sizeBytes: 20,
      mimeType: DOCX_MIME_TYPE,
    },
    parts: [
      {
        partName: '[Content_Types].xml',
        contentType: 'application/xml',
        kind: 'other',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
      {
        partName: '_rels/.rels',
        contentType: 'application/vnd.openxmlformats-package.relationships+xml',
        kind: 'relationships',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 1,
      },
      {
        partName: 'word/document.xml',
        contentType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
        kind: 'document',
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
    ],
    nodes: [
      {
        nodeId: `ttn_${'d'.repeat(20)}`,
        partName: 'word/document.xml',
        path: '/document/body/sdt[0]',
        displayOrder: 0,
        kind: definition.kind,
        fieldId: definition.fieldId,
        tableId: null,
        staticTextSha256: null,
        bookmarkNames: [],
      },
    ],
    fields: [definition],
    tables: [],
    unsupported: [],
    structureSha256: SHA,
    staticContentSha256: SHA,
    stats: {
      totalFields: 1,
      dropdowns: definition.kind === 'single_select' ? 1 : 0,
      comboBoxes: 0,
      checkboxes: definition.kind === 'checkbox' ? 1 : 0,
      dateControls: definition.kind === 'date' ? 1 : 0,
      tables: 0,
      repeatingTables: 0,
      headers: 0,
      footers: 0,
      unsupported: 0,
      blockingUnsupported: 0,
    },
  };
}

function unresolved(fieldId = FIELD_ID): FieldResolution {
  return {
    fieldId,
    status: 'needs_clinician_input',
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    selectedOptionOrdinal: null,
    reasonCode: 'required_fact_not_mentioned',
    clinicianReviewed: false,
  };
}

function persistedMapping(semantic: SemanticMapping) {
  return {
    clinicalConcept: semantic.clinicalConcept,
    expectedDataType: semantic.expectedDataType,
    polarityBehavior: semantic.polarityBehavior,
    temporality: semantic.temporality,
    laterality: semantic.laterality,
    unitPolicy: semantic.unitPolicy,
    approvedSynonyms: semantic.approvedSynonyms,
    required: semantic.required,
    blankPolicy: semantic.blankPolicy,
    unknownPolicy: semantic.unknownPolicy,
    practiceDefault: semantic.practiceDefault,
    mappingStatus: TemplateTwinDetectionStatus.CERTIFIED,
    proposedByModel: null,
    approvedById: 'doctor-1',
    approvedAt: new Date(NOW),
  };
}

function context(definition = field()): ReviewContext {
  const documentIr = ir(definition);
  const semantic = mapping(definition);
  const validation = validateTemplateTwin({
    fields: documentIr.fields,
    mappings: [semantic],
    facts: [],
    resolutions: [unresolved(definition.fieldId)],
    now: NOW,
  });
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    compiledVersionId: 'compiled-1',
    noteTemplateId: 'template-1',
    noteTemplateVersion: 1,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: null,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    facts: [],
    fields: [unresolved(definition.fieldId)],
    validation,
    counts: templateTwinCounts([unresolved(definition.fieldId)], [definition]),
  });
  return {
    id: 'fill-1',
    practiceId: 'practice-1',
    visitId: 'visit-1',
    status: 'NEEDS_REVIEW',
    signedDecisionAt: null,
    manifestVersion: 4,
    fillManifest: manifest,
    resolverModelVersion: null,
    visit: {
      userId: 'doctor-1',
      status: 'READY',
      reviewReason: TEMPLATE_TWIN_REVIEW_REASON,
    },
    compiledVersion: {
      id: 'compiled-1',
      sourceArtifactId: 'source-1',
      compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
      irSchemaVersion: 1,
      compiledDocumentIr: documentIr,
      unsupportedElements: [],
      structureSha256: SHA,
      staticContentSha256: SHA,
      certificationStatus: 'CERTIFIED',
      blockingUnsupportedCount: 0,
      sourceArtifact: {
        practiceId: 'practice-1',
        objectKey: `practices/practice-1/template-twin/sources/lineage-1/v1/${SHA}/artifact/${SHA}.docx`,
        sha256: SHA,
        sizeBytes: 20,
        validationStatus: 'accepted',
      },
      noteTemplate: {
        id: 'template-1',
        doctorId: 'doctor-1',
        name: 'Synthetic template',
        encounterType: null,
        specialtyBaseline: null,
        sections: [],
        styleProfile: null,
        version: 1,
        status: 'active',
        lineageId: 'lineage-1',
        templateKind: 'template_twin_docx',
      },
      fields: [
        {
          id: 'definition-1',
          fieldId: definition.fieldId,
          displayOrder: 0,
          originalLabel: definition.originalLabel,
          fieldKind: definition.kind,
          allowedOptions: definition.allowedOptions,
          rendererBinding: definition.rendererBinding,
          detectionStatus: TemplateTwinDetectionStatus.CERTIFIED,
          clinicallyMaterial: definition.clinicallyMaterial,
          criticality: definition.criticality,
          required: definition.required,
          mapping: persistedMapping(semantic),
        },
      ],
    },
  };
}

function correction(
  overrides: Partial<TemplateTwinFieldCorrectionRequest> = {},
): TemplateTwinFieldCorrectionRequest {
  return {
    expectedManifestVersion: 4,
    fieldId: FIELD_ID,
    value: 'Severe',
    sourceFactIds: [],
    reasonCode: 'physician_review_correction',
    createMappingRule: false,
    ...overrides,
  };
}

function repository(
  loaded: ReviewContext | null,
  result: Partial<Awaited<ReturnType<TemplateTwinReviewRepository['commit']>>> = {},
) {
  let committed: CommitPlan | null = null;
  const repo: TemplateTwinReviewRepository = {
    loadOwned: vi.fn(async () => loaded),
    commit: vi.fn(async (plan) => {
      committed = plan;
      return {
        applied: true,
        manifestVersion: 5,
        draftTemplateId: null,
        draftTemplateVersion: null,
        ...result,
      };
    }),
  };
  return { repo, committed: () => committed };
}

function storage(): TemplateTwinArtifactStore {
  const storeOutputArtifact: TemplateTwinArtifactStore['storeOutputArtifact'] =
    vi.fn(
      async (): Promise<StoredTemplateTwinArtifact> => ({
        bucket: 'synthetic-private-bucket',
        objectKey: `practices/practice-1/template-twin/outputs/visit-1/${SHA}/artifact/${OUTPUT_SHA}.docx`,
        sha256: OUTPUT_SHA,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: 24,
        created: true,
      }),
    );

  return {
    bucket: 'synthetic-private-bucket',
    storeSourceArtifact: vi.fn(),
    readOutputArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async () => Buffer.alloc(20, 1)),
    storeOutputArtifact,
  };
}

async function fakeFinalize(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const validation = validateTemplateTwin({
    fields: input.ir.fields,
    mappings: input.mappings,
    facts: input.facts,
    resolutions: input.resolutions,
    tables: input.ir.tables,
    unsupported: input.ir.unsupported,
    now: input.validationNow,
  });
  const counts = templateTwinCounts(input.resolutions, input.ir.fields);
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    compilerVersion: input.ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    facts: input.facts,
    fields: input.resolutions,
    validation,
    counts,
  });
  return {
    manifest,
    manifestSha256: canonicalSha256(manifest),
    factSetSha256: canonicalSha256(input.facts),
    render: validation.valid
      ? {
          document: Buffer.from('synthetic-corrected-docx'),
          outputSha256: OUTPUT_SHA,
          rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
          verification: {
            verified: true as const,
            packageCheck: 'verified' as const,
            fieldCheck: 'verified' as const,
            staticRegionCheck: 'verified' as const,
            sourceSha256: SHA,
            outputSha256: OUTPUT_SHA,
            untouchedEntriesVerified: 3,
            modifiedPartsVerified: 1,
            fields: [],
            warningCodes: [],
          },
        }
      : null,
  };
}

const actor = {
  userId: 'doctor-1',
  userEmail: 'synthetic-doctor@example.test',
  practiceId: 'practice-1',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('buildClinicianCorrection exact rules', () => {
  it('accepts only an exact native dropdown option and records physician evidence', () => {
    const definition = field();
    expect(() =>
      buildClinicianCorrection({
        field: definition,
        mapping: mapping(definition),
        value: 'Closest severe option',
        existingFactIds: new Set(),
        factIdFactory: () => '1'.repeat(24),
      }),
    ).toThrow(TemplateTwinReviewError);

    const result = buildClinicianCorrection({
      field: definition,
      mapping: mapping(definition),
      value: 'Severe',
      existingFactIds: new Set(),
      factIdFactory: () => '1'.repeat(24),
    });
    expect(result.resolution).toMatchObject({
      value: 'Severe',
      selectedOptionOrdinal: 1,
      clinicianReviewed: true,
    });
    expect(result.facts[0]).toMatchObject({
      speaker: 'Physician correction',
      evidenceQuote: 'Physician correction entered during Template Twin review.',
      quality: { asr: 'unknown', evidence: 'direct' },
    });
  });

  it('requires checkbox polarity and explicit measurement units', () => {
    const checkbox = field('checkbox');
    const checked = buildClinicianCorrection({
      field: checkbox,
      mapping: mapping(checkbox),
      value: false,
      existingFactIds: new Set(),
      factIdFactory: () => '2'.repeat(24),
    });
    expect(checked.resolution.status).toBe('explicitly_denied');
    expect(checked.facts[0]?.polarity).toBe('denied');

    const measurement = field('measurement');
    expect(() =>
      buildClinicianCorrection({
        field: measurement,
        mapping: mapping(measurement),
        value: 12,
        existingFactIds: new Set(),
        factIdFactory: () => '3'.repeat(24),
      }),
    ).toThrow(/explicit unit/i);
    const measured = buildClinicianCorrection({
      field: measurement,
      mapping: mapping(measurement),
      value: '12 mg',
      existingFactIds: new Set(),
      factIdFactory: () => '3'.repeat(24),
    });
    expect(measured.resolution.value).toBe('12 mg');
    expect(measured.facts[0]).toMatchObject({ number: 12, unit: 'mg' });
  });

  it('validates exact multi-selects and typed values in repeating rows', () => {
    const multi = field('multi_select');
    const selected = buildClinicianCorrection({
      field: multi,
      mapping: mapping(multi),
      value: ['Mild', 'Severe'],
      existingFactIds: new Set(),
      factIdFactory: vi
        .fn()
        .mockReturnValueOnce('4'.repeat(24))
        .mockReturnValueOnce('5'.repeat(24)),
    });
    expect(selected.resolution.value).toEqual(['Mild', 'Severe']);
    expect(selected.resolution.sourceFactIds).toHaveLength(2);
    expect(() =>
      buildClinicianCorrection({
        field: multi,
        mapping: mapping(multi),
        value: ['Mild', 'Closest option'],
        existingFactIds: new Set(),
      }),
    ).toThrow(/exact certified options/i);

    const repeatingNumber = field('number', { rowPrototype: true });
    const rows = buildClinicianCorrection({
      field: repeatingNumber,
      mapping: mapping(repeatingNumber),
      value: [{ value: '12' }, { value: '13.5' }],
      existingFactIds: new Set(),
      factIdFactory: vi
        .fn()
        .mockReturnValueOnce('6'.repeat(24))
        .mockReturnValueOnce('7'.repeat(24)),
    });
    expect(rows.resolution.value).toEqual([
      expect.objectContaining({ value: '12' }),
      expect.objectContaining({ value: '13.5' }),
    ]);
    expect(rows.facts.map((fact) => fact.number)).toEqual([12, 13.5]);
  });
});

describe('reviewTemplateTwinField lifecycle', () => {
  it('fails closed when the authenticated doctor/practice does not own the visit', async () => {
    const { repo } = repository(null);

    await expect(
      reviewTemplateTwinField(
        { visitId: 'visit-1', actor, correction: correction() },
        { repository: repo },
      ),
    ).rejects.toMatchObject({ code: 'NOT_FOUND' });
    expect(repo.commit).not.toHaveBeenCalled();
  });

  it('rejects stale and signed manifests before reading or writing artifacts', async () => {
    const stale = context();
    stale.manifestVersion = 5;
    const staleRepo = repository(stale).repo;
    const signed = context();
    signed.status = 'SIGNED';
    signed.signedDecisionAt = new Date(NOW);
    const signedRepo = repository(signed).repo;
    const artifacts = storage();

    await expect(
      reviewTemplateTwinField(
        { visitId: 'visit-1', actor, correction: correction() },
        { repository: staleRepo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: 'OPTIMISTIC_CONFLICT' });
    await expect(
      reviewTemplateTwinField(
        { visitId: 'visit-1', actor, correction: correction() },
        { repository: signedRepo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: 'SIGNED_IMMUTABLE' });
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(artifacts.storeOutputArtifact).not.toHaveBeenCalled();
  });

  it('appends a value delta, independently validates, renders, stores, and commits once', async () => {
    const loaded = context();
    const { repo, committed } = repository(loaded);
    const artifacts = storage();

    const result = await reviewTemplateTwinField(
      { visitId: 'visit-1', actor, correction: correction(), validationNow: NOW },
      {
        repository: repo,
        storage: artifacts,
        finalizeFill: fakeFinalize,
        factIdFactory: () => '4'.repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(result).toMatchObject({
      manifestVersion: 5,
      status: 'verified',
      roundTripVerified: true,
      certificationUrl: null,
    });
    expect(artifacts.readSourceArtifact).toHaveBeenCalledTimes(1);
    expect(artifacts.storeOutputArtifact).toHaveBeenCalledTimes(1);
    expect(committed()?.decision).toMatchObject({
      previousValue: null,
      correctedValue: 'Severe',
      decisionKind: 'clinician_correction',
      expectedManifestVersion: 4,
      createMappingRule: false,
    });
    expect(committed()?.prepared.manifest.facts.at(-1)).toMatchObject({
      speaker: 'Physician correction',
    });
    expect(committed()).not.toHaveProperty('clearTemplateTwinVisitReview');
    expect(audit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'TEMPLATE_TWIN_FIELD_REVIEWED',
        metadata: expect.not.objectContaining({
          previousValue: expect.anything(),
          correctedValue: expect.anything(),
          evidenceQuote: expect.anything(),
        }),
      }),
    );
  });

  it('never asks the repository to clear generic visit review state', async () => {
    const loaded = context();
    loaded.visit.reviewReason =
      'Synthetic unrelated pipeline warning that still requires review.';
    const { repo, committed } = repository(loaded);

    await reviewTemplateTwinField(
      { visitId: 'visit-1', actor, correction: correction(), validationNow: NOW },
      {
        repository: repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => '7'.repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(committed()).not.toHaveProperty('clearTemplateTwinVisitReview');
  });

  it('records an explicit required-field clear while keeping review and signing blocked', async () => {
    const requiredField = field('narrative_text', { required: true });
    const loaded = context(requiredField);
    const { repo, committed } = repository(loaded);
    const artifacts = storage();

    const result = await reviewTemplateTwinField(
      {
        visitId: 'visit-1',
        actor,
        correction: correction({ value: null }),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: artifacts,
        finalizeFill: fakeFinalize,
        now: () => new Date(NOW),
      },
    );

    expect(result).toMatchObject({
      status: 'needs_review',
      roundTripVerified: false,
    });
    expect(committed()?.decision).toMatchObject({
      decisionKind: 'clinician_clear',
      correctedValue: null,
    });
    expect(committed()).not.toHaveProperty('clearTemplateTwinVisitReview');
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(artifacts.storeOutputArtifact).not.toHaveBeenCalled();
  });

  it('plans an immutable-source mapping fork and returns its certification URL', async () => {
    const loaded = context();
    const { repo, committed } = repository(loaded, {
      draftTemplateId: 'template-draft-2',
      draftTemplateVersion: 2,
    });

    const result = await reviewTemplateTwinField(
      {
        visitId: 'visit-1',
        actor,
        correction: correction({ createMappingRule: true }),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => '5'.repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(committed()?.fork).toMatchObject({
      targetFieldId: FIELD_ID,
      context: {
        compiledVersion: {
          sourceArtifactId: 'source-1',
          noteTemplate: { id: 'template-1', lineageId: 'lineage-1' },
        },
      },
    });
    expect(result).toMatchObject({
      certificationUrl: '/settings/note-format/template-draft-2/certify',
      draftTemplateVersion: 2,
    });
  });

  it('rejects a transaction-time optimistic conflict after rendering', async () => {
    const { repo } = repository(context(), {
      applied: false,
      manifestVersion: null,
    });
    await expect(
      reviewTemplateTwinField(
        { visitId: 'visit-1', actor, correction: correction(), validationNow: NOW },
        {
          repository: repo,
          storage: storage(),
          finalizeFill: fakeFinalize,
          factIdFactory: () => '6'.repeat(24),
        },
      ),
    ).rejects.toMatchObject({ code: 'OPTIMISTIC_CONFLICT' });
  });
});
