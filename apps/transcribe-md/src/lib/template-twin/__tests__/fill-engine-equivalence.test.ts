import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  renderTemplateDocx: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('@/lib/note-template-docx', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('../../note-template-docx')
  >();
  return { ...actual, renderTemplateDocx: mocks.renderTemplateDocx };
});

import { prepareTemplateTwinFill } from '../fill-engine';
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from './integration-fixture';

const OUTPUT_SHA = 'e'.repeat(64);

beforeEach(() => {
  vi.clearAllMocks();
  mocks.renderTemplateDocx.mockImplementation(
    async (input: { resolutions: Array<{ fieldId: string }> }) => ({
      document: Buffer.from('synthetic-mocked-render'),
      outputSha256: OUTPUT_SHA,
      rendererVersion: 'template-docx-renderer/1.0.0',
      verification: {
        verificationContractVersion: 'template-docx-readback/2.0.0',
        verified: true,
        packageCheck: 'verified',
        fieldCheck: 'verified',
        staticRegionCheck: 'verified',
        sourceSha256: 'a'.repeat(64),
        outputSha256: OUTPUT_SHA,
        untouchedEntriesVerified: 1,
        modifiedPartsVerified: 1,
        fields: input.resolutions.map((field) => ({
          fieldId: field.fieldId,
          partName: 'word/document.xml',
          bindingPath: '/synthetic[0]',
          valueSha256: 'b'.repeat(64),
          occurrences: 1,
          status: 'verified',
        })),
        warningCodes: [],
      },
    }),
  );
});

function clinicalResolutionShape(
  prepared: Awaited<ReturnType<typeof prepareTemplateTwinFill>>,
) {
  return prepared.manifest.fields.map((field) => ({
    fieldId: field.fieldId,
    status: field.status,
    value: field.value,
    selectedOptionOrdinal: field.selectedOptionOrdinal,
    reasonCode: field.reasonCode,
  }));
}

describe('Template Twin pure fill-engine input equivalence', () => {
  it('resolves voice and typed evidence to the same clinical fields before rendering', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const common = {
      soapVersion: 1,
      soapFinal: 'Synthetic SOAP reviewed for equivalent voice and typed evidence.',
      compiledVersionId: 'compiled-synthetic-1',
      noteTemplateId: 'template-synthetic-1',
      noteTemplateVersion: 1,
      ir: fixture.ir,
      mappings: fixture.mappings,
      source: fixture.source,
      resolverModelVersion: 'synthetic-model-v1',
      validationNow: '2026-07-15T12:00:00.000Z',
      allowUncertifiedForSyntheticTest: true,
    } as const;

    const voice = await prepareTemplateTwinFill({
      ...common,
      facts: factsForMode('conversation'),
    });
    const typed = await prepareTemplateTwinFill({
      ...common,
      facts: factsForMode('text'),
    });

    expect(voice.manifest.validation.valid).toBe(true);
    expect(typed.manifest.validation.valid).toBe(true);
    expect(clinicalResolutionShape(voice)).toEqual(
      clinicalResolutionShape(typed),
    );
    expect(voice.manifest.counts).toEqual(typed.manifest.counts);
    expect(voice.manifest.counts.filled).toBe(fixture.ir.fields.length);
    expect(voice.factSetSha256).not.toBe(typed.factSetSha256);
    expect(mocks.renderTemplateDocx).toHaveBeenCalledTimes(2);
    for (const call of mocks.renderTemplateDocx.mock.calls) {
      expect(call[0]).toEqual(
        expect.objectContaining({
          source: fixture.source,
          ir: fixture.ir,
          validation: expect.objectContaining({ valid: true }),
        }),
      );
      expect(
        call[0].resolutions.every(
          (field: { value: unknown; sourceFactIds: string[]; evidenceAnchorIds: string[] }) =>
            field.value === null ||
            (field.sourceFactIds.length > 0 && field.evidenceAnchorIds.length > 0),
        ),
      ).toBe(true);
    }
  });
});
