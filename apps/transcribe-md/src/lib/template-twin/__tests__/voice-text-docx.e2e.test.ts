import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { inspectDocxPackage } from '../../note-template-docx';
import { prepareTemplateTwinFill } from '../fill-engine';
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from './integration-fixture';

describe('Template Twin voice/text to original-DOCX vertical slice', () => {
  it('uses the real projector, resolver, validator, and renderer for equivalent outputs', async () => {
    const fixture = await buildTemplateTwinIntegrationFixture();
    const common = {
      soapVersion: 1,
      soapFinal: 'Synthetic SOAP reviewed for the DOCX vertical slice.',
      compiledVersionId: 'compiled-synthetic-e2e',
      noteTemplateId: 'template-synthetic-e2e',
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

    expect(voice.render).not.toBeNull();
    expect(typed.render).not.toBeNull();
    expect(voice.manifest.validation.valid).toBe(true);
    expect(typed.manifest.validation.valid).toBe(true);
    expect(voice.render!.outputSha256).toBe(typed.render!.outputSha256);
    expect(voice.render!.document).toEqual(typed.render!.document);
    expect(voice.render!.verification).toMatchObject({
      verified: true,
      packageCheck: 'verified',
      fieldCheck: 'verified',
      staticRegionCheck: 'verified',
    });
    expect(
      voice.render!.verification.fields.map((field) => field.fieldId).sort(),
    ).toEqual(fixture.ir.fields.map((field) => field.fieldId).sort());

    const output = inspectDocxPackage(voice.render!.document);
    const documentXml = output.zip.entries
      .get('word/document.xml')!
      .bytes.toString('utf8');
    const headerXml = output.zip.entries
      .get('word/header1.xml')!
      .bytes.toString('utf8');
    expect(documentXml).toContain('synthetic wrist discomfort');
    expect(documentXml).toContain('<w:t>Current</w:t>');
    expect(documentXml).toContain('w14:checked w14:val="1"');
    expect(documentXml).toContain('Use synthetic brace');
    expect(headerXml).toContain('Synthetic Clinic Header');
    expect(voice.manifest.fields.every((field) => field.value !== null)).toBe(true);
    expect(
      voice.manifest.fields.every(
        (field) =>
          field.sourceFactIds.length > 0 && field.evidenceAnchorIds.length > 0,
      ),
    ).toBe(true);
  });
});
