// ============================================================================
// Numeric table-cell fill bridge — deterministic (no AI/DB/network).
// Proves: given a generated note with known measurements, the native render
// lands EXACTLY those values in EXACTLY those table cells (laterality-correct
// via forward-cursor vein alignment), and never invents / mis-places / fills a
// stated-normal ("—") or not-assessed ("[not documented]") cell.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx, renderTemplateDocx } from '@/lib/note-template-docx';

import {
  bridgeNumericTableCells,
  bridgeTemplateFill,
  mergeFieldResolutions,
} from '../bridge-fill';
import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};

/** All-blank baseline (one per field), as the resolver would emit for WM_IOV. */
function blankBaseline(ir: TemplateDocIR): FieldResolution[] {
  return ir.fields.map((f) =>
    FieldResolutionSchema.parse({
      fieldId: f.fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'blank_when_unsaid',
      clinicianReviewed: false,
    }),
  );
}

function cell(ir: TemplateDocIR, rowIndex: number, cellIndex: number): TemplateField {
  const f = ir.fields.find(
    (x) =>
      x.rendererBinding.bindingType === 'table_cell' &&
      x.rendererBinding.rowIndex === rowIndex &&
      x.rendererBinding.cellIndex === cellIndex,
  );
  if (!f) throw new Error(`no table_cell field at row ${rowIndex} col ${cellIndex}`);
  return f;
}

// Right block = rowIndex 1..13, Left block = 15..27 (row 0/14 are leg headers).
// GSV-at-SFJ is row 1 (right) and row 15 (left); Prox-Thigh is 2/16; Knee is 3/17.
// diameter cell = cellIndex 1, reflux cell = cellIndex 2.
const NOTE = [
  'IMPRESSION',
  'Right great saphenous vein reflux positive.',
  '',
  '| VEIN | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| Right GSV at the SFJ | 6.2 | 3.4 | [S1: "SFJ six two, reflux three four"]',
  '| Right GSV at the Proximal Thigh | [not documented] | [not documented] |',
  '| Right GSV at the Knee | 5.1 | — |',
  '| Left GSV at the SFJ | 5.8 | 3.1 |',
  '| Left GSV at the Proximal Thigh | 4.1 | 1.8 |',
].join('\n');

describe('bridgeNumericTableCells — exact measurement placement (WM_IOV)', () => {
  const ir = compileTemplateDocx(wmIovBytes);

  it('resolves exactly the dictated numeric cells, laterality-correct, nothing else', () => {
    const res = bridgeNumericTableCells({ ir, filledNote: NOTE });
    const byField = new Map(res.map((r) => [r.fieldId, r]));

    // Every produced resolution is a supported, evidence-carrying measurement.
    for (const r of res) {
      expect(r.status).toBe('supported');
      expect(r.reasonCode).toBe('table_cell_measurement');
      expect(r.sourceFactIds.length).toBeGreaterThan(0);
      expect(r.evidenceAnchorIds.length).toBeGreaterThan(0);
      expect(r.selectedOptionOrdinal).toBeNull();
    }

    // Right GSV-SFJ (row 1): diameter 6.2, reflux 3.4.
    expect(byField.get(cell(ir, 1, 1).fieldId)?.value).toBe('6.2');
    expect(byField.get(cell(ir, 1, 2).fieldId)?.value).toBe('3.4');
    // Right GSV-Knee (row 3): diameter 5.1 filled; reflux is "—" (stated normal) → NOT filled.
    expect(byField.get(cell(ir, 3, 1).fieldId)?.value).toBe('5.1');
    expect(byField.has(cell(ir, 3, 2).fieldId)).toBe(false);
    // Right GSV-ProxThigh (row 2): "[not documented]" → NOT filled either cell.
    expect(byField.has(cell(ir, 2, 1).fieldId)).toBe(false);
    expect(byField.has(cell(ir, 2, 2).fieldId)).toBe(false);
    // LEFT GSV-SFJ (row 15): diameter 5.8, reflux 3.1 — placed on the LEFT fields,
    // NOT the right ones (the whole laterality point).
    expect(byField.get(cell(ir, 15, 1).fieldId)?.value).toBe('5.8');
    expect(byField.get(cell(ir, 15, 2).fieldId)?.value).toBe('3.1');
    // Left GSV-ProxThigh (row 16): 4.1 / 1.8.
    expect(byField.get(cell(ir, 16, 1).fieldId)?.value).toBe('4.1');
    expect(byField.get(cell(ir, 16, 2).fieldId)?.value).toBe('1.8');

    // Right-SFJ and Left-SFJ are DISTINCT fields with DISTINCT values.
    expect(cell(ir, 1, 1).fieldId).not.toBe(cell(ir, 15, 1).fieldId);
    // Exactly 7 cells filled (2 + 1 + 2 + 2).
    expect(res.length).toBe(7);
  });

  it('native-renders the doctor’s own docx with the values in the correct cells, roundtrip-verified', async () => {
    const numerics = bridgeNumericTableCells({ ir, filledNote: NOTE });
    const merged = mergeFieldResolutions(ir, blankBaseline(ir), numerics);
    expect(merged.length).toBe(ir.fields.length); // renderer requires 1:1

    const rendered = await renderTemplateDocx({ source: wmIovBytes, ir, resolutions: merged, validation: VALIDATION });
    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.staticRegionCheck).toBe('verified');

    const doc = Buffer.from(rendered.document);
    // Re-open and read the main document text so we assert on the RENDERED cells.
    const { docxToText } = await import('@/lib/note-template-parse/docx-to-text');
    const text = await docxToText(new Uint8Array(doc));

    for (const v of ['6.2', '3.4', '5.1', '5.8', '3.1', '4.1', '1.8']) {
      expect(text).toContain(v);
    }
    // A value that was never dictated must not appear.
    expect(text).not.toContain('9.9');
    // Laterality in document order: the RIGHT SFJ diameter (6.2) precedes the
    // LEFT SFJ diameter (5.8).
    expect(text.indexOf('6.2')).toBeLessThan(text.indexOf('5.8'));
  });
});

describe('bridgeNumericTableCells — one-leg dictation never mis-places (laterality)', () => {
  const ir = compileTemplateDocx(wmIovBytes);

  it('a full skeleton with ONLY the left block filled leaves every right cell blank', () => {
    // Build the FULL skeleton the note-generation always reproduces: every IR
    // table row (both legs, document order) seeded "[not documented]", then fill
    // ONLY the left GSV-at-SFJ (rowIndex 15) — the right block stays all blank.
    const rows = ir.fields
      .filter((f) => f.rendererBinding.bindingType === 'table_cell')
      .reduce<Map<number, { vein: string }>>((m, f) => {
        const r = f.rendererBinding.rowIndex ?? -1;
        if (f.labelSource === 'left_cell') m.set(r, { vein: f.originalLabel });
        else if (!m.has(r)) m.set(r, { vein: f.originalLabel });
        return m;
      }, new Map());
    const ordered = [...rows.entries()].sort((a, b) => a[0] - b[0]);
    const lines = ['| VEIN | DIAMETER (mm) | REFLUX TIME (seconds) |', '| --- | --- | --- |'];
    let seenSfj = 0;
    for (const [, { vein }] of ordered) {
      // The SECOND exact "GSV at the SFJ" is the left one (rowIndex 15). Exact
      // match — "AAGSV/PAGSV at the SFJ" must NOT count.
      const leftGsvSfj = vein === 'GSV at the SFJ' && ++seenSfj === 2;
      lines.push(leftGsvSfj ? `| Left ${vein} | 5.8 | 3.1 |` : `| ${vein} | [not documented] | [not documented] |`);
    }
    const note = 'FINDINGS\nLeft leg only.\n\n' + lines.join('\n');

    const res = bridgeNumericTableCells({ ir, filledNote: note });
    const byField = new Map(res.map((r) => [r.fieldId, r]));
    // Left GSV-SFJ (row 15) is filled.
    expect(byField.get(cell(ir, 15, 1).fieldId)?.value).toBe('5.8');
    expect(byField.get(cell(ir, 15, 2).fieldId)?.value).toBe('3.1');
    // The RIGHT GSV-SFJ (row 1) — same vein name, other leg — MUST stay blank.
    expect(byField.has(cell(ir, 1, 1).fieldId)).toBe(false);
    expect(byField.has(cell(ir, 1, 2).fieldId)).toBe(false);
    // Nothing else filled.
    expect(res.length).toBe(2);
  });
});

describe('mergeFieldResolutions — overlay precedence', () => {
  const ir = compileTemplateDocx(wmIovBytes);

  it('overlay fills only where the baseline is unfilled; real evidence wins', () => {
    const target = cell(ir, 1, 1);
    // Baseline already SUPPORTED this field from real evidence.
    const baseline = blankBaseline(ir).map((r) =>
      r.fieldId === target.fieldId
        ? FieldResolutionSchema.parse({
            fieldId: target.fieldId,
            status: 'supported',
            value: '7.0',
            sourceFactIds: [`ttfact_${'a'.repeat(24)}`],
            evidenceAnchorIds: ['real-evidence'],
            selectedOptionOrdinal: null,
            reasonCode: 'direct_evidence_supported',
            clinicianReviewed: false,
          })
        : r,
    );
    const overlay = bridgeNumericTableCells({ ir, filledNote: NOTE }); // would set 6.2
    const merged = mergeFieldResolutions(ir, baseline, overlay);
    const m = new Map(merged.map((r) => [r.fieldId, r]));
    // Evidence-backed baseline (7.0) is NOT overwritten by the note overlay (6.2).
    expect(m.get(target.fieldId)?.value).toBe('7.0');
    // A DIFFERENT unfilled cell still receives the overlay.
    expect(m.get(cell(ir, 1, 2).fieldId)?.value).toBe('3.4');
    expect(merged.length).toBe(ir.fields.length);
  });
});

describe('bridgeTemplateFill — unified picks + numeric overlay', () => {
  it('fills dropdowns AND table numerics in one pass over the real template', async () => {
    const ir = compileTemplateDocx(wmIovBytes);
    const { docxToTextWithControls } = await import('@/lib/note-template-parse/docx-content-controls');
    const { text: markerText } = await docxToTextWithControls(wmIovBytes);

    // Fill each {{one of}} marker with its FIRST option so the picks bridge has
    // something to recover, and append the measurement table.
    const MARKER_RE = /\{\{one of:\s*([^}]*)\}\}/g;
    const pickedNote =
      markerText.replace(MARKER_RE, (_f, opts: string) =>
        String(opts).split('|').map((o) => o.trim()).filter(Boolean)[0] ?? '',
      ) + '\n' + NOTE;

    const merged = bridgeTemplateFill({
      ir,
      markerText,
      filledNote: pickedNote,
      baseline: blankBaseline(ir),
    });
    expect(merged.length).toBe(ir.fields.length);

    const filledSelects = merged.filter(
      (r) => r.status === 'supported' && r.reasonCode === 'choice_slot_pick',
    );
    const filledNumerics = merged.filter((r) => r.reasonCode === 'table_cell_measurement');
    expect(filledSelects.length).toBeGreaterThan(0); // dropdowns filled
    expect(filledNumerics.length).toBe(7); // measurements filled

    // Renders cleanly with both kinds of fill present.
    const rendered = await renderTemplateDocx({ source: wmIovBytes, ir, resolutions: merged, validation: VALIDATION });
    expect(rendered.verification.verified).toBe(true);
  });
});
