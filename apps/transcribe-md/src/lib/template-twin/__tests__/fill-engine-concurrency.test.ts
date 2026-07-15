import { createHash } from 'node:crypto';

import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  audit: vi.fn(),
  claimVisit: vi.fn(),
  createFill: vi.fn(),
  findFill: vi.fn(),
  findTemplate: vi.fn(),
  updateFill: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { updateMany: mocks.claimVisit },
    noteTemplate: { findFirst: mocks.findTemplate },
    templateTwinFillManifest: {
      create: mocks.createFill,
      findUnique: mocks.findFill,
      updateMany: mocks.updateFill,
    },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.audit }));

import { templateTwinMappingsSha256 } from '../mapping-hash';
import { processTemplateTwinVisit } from '../fill-engine';
import type { TemplateTwinArtifactStore } from '../storage';
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from './integration-fixture';

const PRACTICE_ID = 'practice-fill-concurrency';
const DOCTOR_ID = 'doctor-fill-concurrency';
const VISIT_ID = 'visit-fill-concurrency';
const TEMPLATE_ID = 'template-fill-concurrency';
const COMPILED_ID = 'compiled-fill-concurrency';
const OLD_MANIFEST_SHA = 'b'.repeat(64);

type Fixture = Awaited<ReturnType<typeof buildTemplateTwinIntegrationFixture>>;
let fixture: Fixture;
let outputWrites: number;

function templateRow() {
  return {
    id: TEMPLATE_ID,
    version: 1,
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compilerVersion: fixture.ir.compilerVersion,
      compiledDocumentIr: fixture.ir,
      certificationStatus: 'CERTIFIED',
      certification: {
        id: 'certification-fill-concurrency',
        approvedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
      },
      sourceArtifact: {
        practiceId: PRACTICE_ID,
        objectKey:
          `practices/${PRACTICE_ID}/template-twin/sources/lineage/v1/source/${fixture.ir.source.sha256}.docx`,
        sha256: fixture.ir.source.sha256,
        sizeBytes: fixture.source.byteLength,
        validationStatus: 'accepted',
      },
      fields: fixture.mappings.map((mapping) => ({
        fieldId: mapping.fieldId,
        detectionStatus: 'CERTIFIED',
        mapping: {
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
          mappingStatus: 'CERTIFIED',
        },
      })),
    },
  };
}

function storage(): TemplateTwinArtifactStore {
  return {
    bucket: 'synthetic-memory-only',
    storeSourceArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async () => Buffer.from(fixture.source)),
    readOutputArtifact: vi.fn(),
    storeOutputArtifact: vi.fn(async (input) => {
      outputWrites += 1;
      const outputSha256 = createHash('sha256')
        .update(input.bytes)
        .digest('hex');
      return {
        bucket: 'synthetic-memory-only',
        objectKey:
          `practices/${PRACTICE_ID}/template-twin/outputs/${VISIT_ID}/${input.manifestSha256}/artifact/${outputSha256}.docx`,
        sha256: outputSha256,
        mimeType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document' as const,
        sizeBytes: input.bytes.byteLength,
        created: true,
      };
    }),
  };
}

function processInput(artifactStorage = storage()) {
  return {
    visitId: VISIT_ID,
    practiceId: PRACTICE_ID,
    doctorId: DOCTOR_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    inputMode: 'text' as const,
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
    validationNow: '2026-07-15T12:00:00.000Z',
    resolverModelVersion: 'synthetic-resolver-model',
    storage: artifactStorage,
  };
}

beforeAll(async () => {
  fixture = await buildTemplateTwinIntegrationFixture();
});

beforeEach(() => {
  vi.clearAllMocks();
  outputWrites = 0;
  mocks.claimVisit.mockResolvedValue({ count: 1 });
  mocks.findTemplate.mockImplementation(async () => templateRow());
  mocks.createFill.mockResolvedValue({ id: 'fill-created' });
  mocks.updateFill.mockResolvedValue({ count: 1 });
  mocks.audit.mockResolvedValue(undefined);
});

describe('Template Twin worker provenance and manifest concurrency', () => {
  it('pins the selected template before source access and stops on a conflicting pin', async () => {
    const artifacts = storage();
    mocks.claimVisit.mockResolvedValue({ count: 0 });

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({ code: 'TEMPLATE_PROVENANCE_MISMATCH' });

    expect(mocks.claimVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: VISIT_ID,
          userId: DOCTOR_ID,
        }),
        data: {
          noteTemplateId: TEMPLATE_ID,
          noteTemplateVersion: 1,
        },
      }),
    );
    expect(mocks.findTemplate).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
  });

  it('cannot overwrite a manifest that is signed while rendering is in flight', async () => {
    mocks.findFill
      .mockResolvedValueOnce({
        id: 'fill-existing',
        status: 'VERIFIED',
        signedDecisionAt: null,
        reviewedAt: null,
        manifestVersion: 4,
        manifestSha256: OLD_MANIFEST_SHA,
        roundTripVerified: true,
      })
      .mockResolvedValueOnce({
        status: 'SIGNED',
        signedDecisionAt: new Date('2026-07-15T12:05:00.000Z'),
      });
    mocks.updateFill.mockResolvedValue({ count: 0 });

    await expect(processTemplateTwinVisit(processInput())).rejects.toMatchObject({
      code: 'SIGNED_MANIFEST_IMMUTABLE',
    });

    expect(outputWrites).toBe(1);
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: 'fill-existing',
          status: { not: 'SIGNED' },
          signedDecisionAt: null,
          reviewedAt: null,
          manifestVersion: 4,
          manifestSha256: OLD_MANIFEST_SHA,
        }),
      }),
    );
    expect(mocks.createFill).not.toHaveBeenCalled();
  });

  it('never replaces a clinician-reviewed manifest with stale worker evidence', async () => {
    mocks.findFill.mockResolvedValue({
      id: 'fill-existing',
      status: 'VERIFIED',
      signedDecisionAt: null,
      reviewedAt: new Date('2026-07-15T12:03:00.000Z'),
      manifestVersion: 5,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: true,
    });

    await expect(processTemplateTwinVisit(processInput())).rejects.toMatchObject({
      code: 'MANIFEST_CONFLICT',
    });

    expect(outputWrites).toBe(0);
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.createFill).not.toHaveBeenCalled();
  });

  it('updates only the exact unsigned manifest version observed before storage', async () => {
    mocks.findFill.mockResolvedValue({
      id: 'fill-existing',
      status: 'NEEDS_REVIEW',
      signedDecisionAt: null,
      reviewedAt: null,
      manifestVersion: 7,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: false,
    });

    const result = await processTemplateTwinVisit(processInput());

    expect(result.manifest.validation.issues).toEqual([]);
    expect(result.render?.verification.verified).toBe(true);
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: 'fill-existing',
          manifestVersion: 7,
          manifestSha256: OLD_MANIFEST_SHA,
          signedDecisionAt: null,
          reviewedAt: null,
        }),
        data: expect.objectContaining({
          status: 'VERIFIED',
          manifestVersion: { increment: 1 },
          criticalUnresolvedCount: 0,
          roundTripVerified: true,
        }),
      }),
    );
  });
});
