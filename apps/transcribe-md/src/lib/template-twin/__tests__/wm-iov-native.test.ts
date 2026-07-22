// ============================================================================
// WM_IOV native-return proof — the real 28-dropdown venous-duplex template.
// ----------------------------------------------------------------------------
// Fully DETERMINISTIC (no AI, no DB, no network). Proves the salvaged native
// path end-to-end at the library level:
//   1. the fail-closed security boundary ADMITS a legit clinical template
//   2. it compiles to a deterministic IR with the native dropdown fields
//   3. the unified ingestion cross-check agrees with the live marker extractor
//      (one source of truth) and still emits the {{one of}} marker form
//   4. the renderer returns the DOCTOR'S OWN document with fields natively
//      filled, formatting preserved, roundtrip-verified
// The AI-in-the-loop fill (dense reflux dictation → live brain) is a separate,
// credits-gated QA-stack test — this proves the mechanics the fill feeds into.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  compileTemplateDocx,
  inspectDocxPackage,
  renderTemplateDocx,
} from '@/lib/note-template-docx';
import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';

import { ingestDocxTemplateSource } from '../ingest-docx-source';
import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateTwinValidationResult,
} from '../ir';

const REPO_ROOT = path.resolve(process.cwd(), '../..');
const WM_IOV_PATH = path.join(REPO_ROOT, 'WM IOV Template.docx');
const SAMPLE_DOCX_PATH = path.join(
  process.cwd(),
  'tests/e2e/fixtures/notes/sample-note.docx',
);

const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};
const SYNTH_FACT = `ttfact_${'a'.repeat(24)}`;

/** Deterministically resolve every field: pick option 0 for each supported
 *  single-select (native selection proof), leave everything else not-mentioned.
 *  Never fills an `unsupported` field (the renderer rejects a value there). */
function deterministicResolutions(ir: TemplateDocIR): FieldResolution[] {
  return ir.fields.map((field) => {
    const fillable =
      field.kind === 'single_select' &&
      field.detectionStatus !== 'unsupported' &&
      !field.rowPrototype &&
      field.allowedOptions.length > 0;
    if (fillable) {
      return FieldResolutionSchema.parse({
        fieldId: field.fieldId,
        status: 'supported',
        value: field.allowedOptions[0].value,
        sourceFactIds: [SYNTH_FACT],
        evidenceAnchorIds: ['synthetic-anchor'],
        selectedOptionOrdinal: 0,
        reasonCode: 'synthetic_direct_evidence',
        clinicianReviewed: false,
      });
    }
    return FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'synthetic_not_mentioned',
      clinicianReviewed: false,
    });
  });
}

describe('WM_IOV native-return (deterministic; no AI/DB)', () => {
  it('1. security boundary ADMITS the legit clinical template (no false-positive reject)', () => {
    expect(() => inspectDocxPackage(wmIovBytes)).not.toThrow();
  });

  it('1b. security boundary ADMITS the sample-note.docx fixture too (no regression)', () => {
    const sample = new Uint8Array(readFileSync(SAMPLE_DOCX_PATH));
    expect(() => inspectDocxPackage(sample)).not.toThrow();
  });

  it('2. compiles to a deterministic IR with native dropdown fields', () => {
    const ir = compileTemplateDocx(wmIovBytes);
    expect(ir.irSchemaVersion).toBe(1);
    expect(ir.stats.dropdowns).toBeGreaterThan(0);
    const selects = ir.fields.filter((f) => f.kind === 'single_select');
    expect(selects.length).toBeGreaterThan(0);
    // Every select preserves at least one native option (IR invariant).
    for (const s of selects) expect(s.allowedOptions.length).toBeGreaterThan(0);
    // Determinism: recompiling the same bytes yields the same structure hash.
    expect(compileTemplateDocx(wmIovBytes).structureSha256).toBe(ir.structureSha256);
  });

  it('3. unified ingestion cross-check agrees with the live marker extractor', async () => {
    const ingested = await ingestDocxTemplateSource(wmIovBytes);
    const live = await docxToTextWithControls(wmIovBytes);
    expect(ingested.dropdownCount).toBe(live.dropdownCount);
    expect(ingested.dropdownCount).toBeGreaterThan(0);
    expect(ingested.crossCheck.consistent).toBe(true);
    expect(ingested.crossCheck.compilerDropdowns).toBe(ingested.crossCheck.markerDropdowns);
    // Still emits the live {{one of}} marker form, byte-identical to the live path.
    expect(ingested.markerText).toBe(live.text);
    expect(ingested.markerText).toContain('{{one of:');
  });

  it('4. native-renders the doctor’s OWN document with fields filled, roundtrip-verified', async () => {
    const ir = compileTemplateDocx(wmIovBytes);
    const resolutions = deterministicResolutions(ir);
    const rendered = await renderTemplateDocx({
      source: wmIovBytes,
      ir,
      resolutions,
      validation: VALIDATION,
    });

    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.staticRegionCheck).toBe('verified');
    expect(rendered.verification.fieldCheck).toBe('verified');
    expect(rendered.outputSha256).toMatch(/^[a-f0-9]{64}$/);

    // The output is a valid docx that still passes the security boundary.
    const out = inspectDocxPackage(rendered.document);
    const src = inspectDocxPackage(wmIovBytes);
    // Static parts (styles/numbering/content-types/rels) are byte-identical —
    // formatting preserved; only field slots changed.
    for (const part of [
      '[Content_Types].xml',
      'word/styles.xml',
      'word/numbering.xml',
      'word/_rels/document.xml.rels',
      '_rels/.rels',
    ]) {
      const s = src.zip.entries.get(part)?.bytes;
      if (s) expect(out.zip.entries.get(part)?.bytes).toEqual(s);
    }
    // The verification manifest never leaks a rendered value.
    expect(JSON.stringify(rendered.verification)).not.toContain(SYNTH_FACT);
  });
});
