// ============================================================================
// The two visit-time fill defects, pinned.
// ----------------------------------------------------------------------------
// Both were found by the real-visit harness against a CERTIFIED template, and
// both were invisible before the fallback learned to name its reason:
//
//  1. A data row carrying a trailing evidence QUOTE failed TABLE_ROW_RE. Since
//     it is typically the FIRST data row, table accumulation ended with zero
//     rows — parseMarkdownTables returned 2 tables with rows=0 and every
//     dictated measurement was dropped (filledCount=0).
//  2. projectEncounterFacts assumed non-null entities, but
//     TranscribeVisit.entities is nullable — the on-demand export path threw
//     "Cannot read properties of null (reading 'chief_complaint')" and degraded
//     to styled.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { parseMarkdownTablesForDiagnosis as parseMarkdownTables } from '../bridge-fill';
import { projectEncounterFacts } from '../encounter-facts';

// Exactly what L4 produced for the harness dictation.
const REAL_NOTE = [
  'DIAMETER AND REFLUX TIME — Right Leg',
  '',
  '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 | "Right great saphenous vein at the saphenofemoral junction: diameter 6.2 millimeters, reflux 3.4 seconds"',
  '| GSV at the Proximal Thigh | [not documented] | [not documented] |',
  '| GSV at the Knee | 5.1 | — | "Right great saphenous vein at the knee: diameter 5.1 millimeters, no reflux"',
  '| SSV at the SPJ | [not documented] | [not documented] |',
].join('\n');

describe('defect 1 — a trailing evidence quote must not kill the table', () => {
  it('parses the rows of the note L4 actually produced', () => {
    const tables = parseMarkdownTables(REAL_NOTE);
    expect(tables).toHaveLength(1);
    // The regression: 2 tables, rows=0.
    expect(tables[0]!.rows.length).toBe(4);
  });

  it('keeps the quoted row and its cell values intact', () => {
    const [table] = parseMarkdownTables(REAL_NOTE);
    const sfj = table!.rows.find((r) => r.label.includes('SFJ') && !r.label.includes('SSV'));
    expect(sfj, 'the quoted first data row was dropped').toBeDefined();
    // cells[0] is the row LABEL; the data columns follow, matching the header
    // (Segment | DIAMETER | REFLUX TIME) the bridge indexes by role.
    // The quote must not leak into a cell.
    expect(sfj!.cells[1]).toBe('6.2');
    expect(sfj!.cells[2]).toBe('3.4');
    expect(sfj!.cells.some((c) => c.includes('saphenofemoral'))).toBe(false);
  });

  it('still tolerates the bracketed-anchor form', () => {
    const withAnchor = [
      '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 | [S1: "SFJ six two"]',
    ].join('\n');
    const [table] = parseMarkdownTables(withAnchor);
    expect(table!.rows).toHaveLength(1);
    expect(table!.rows[0]!.cells[1]).toBe('6.2');
  });

  it('an unannotated row is unchanged', () => {
    const plain = [
      '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| --- | --- | --- |',
      '| GSV at the Knee | 5.1 | — |',
    ].join('\n');
    const [table] = parseMarkdownTables(plain);
    expect(table!.rows).toHaveLength(1);
    expect(table!.rows[0]!.cells[1]).toBe('5.1');
  });
});

describe('defect 2 — null entities project to no facts, not a crash', () => {
  it('does not throw when the visit has no persisted entities', () => {
    expect(() =>
      projectEncounterFacts({
        mode: 'text',
        contextText: 'anything',
        entities: null as never,
        asrQuality: 'unknown',
      }),
    ).not.toThrow();
  });

  it('yields an empty fact set — no evidence means no facts', () => {
    const facts = projectEncounterFacts({
      mode: 'text',
      contextText: 'anything',
      entities: null as never,
      asrQuality: 'unknown',
    });
    expect(facts).toEqual([]);
  });
});

// ============================================================================
// DEFECT 3 — header/cell alignment. A data row is always [label, ...values],
// but L4 emits the header BOTH with and without a column for the label.
// Indexing cells by header position assumed the first shape, so under the
// second the DIAMETER column read the row LABEL and the REFLUX column read the
// DIAMETER value. Measured on the pinned note: filledCount=0, and a 7 mm
// diameter was offered to a reflux cell — refused only because the evidence
// matcher checks concept against mapping.
// ============================================================================
describe('defect 3 — header with no label column', () => {
  const HEADERLESS = [
    '| DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- |',
    '| GSV at the SFJ | 7 | 2.4 | "Right great saphenous vein reflux 2.4 seconds, diameter 7 mm" |',
  ].join('\n');

  const WITH_LABEL = [
    '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 7 | 2.4 |',
  ].join('\n');

  it('parses both header shapes', () => {
    expect(parseMarkdownTables(HEADERLESS)[0]!.rows).toHaveLength(1);
    expect(parseMarkdownTables(WITH_LABEL)[0]!.rows).toHaveLength(1);
  });

  it('the row keeps label + both values regardless of header shape', () => {
    for (const note of [HEADERLESS, WITH_LABEL]) {
      const row = parseMarkdownTables(note)[0]!.rows[0]!;
      expect(row.label).toContain('SFJ');
      expect(row.cells[1]).toBe('7');
      expect(row.cells[2]).toBe('2.4');
    }
  });

  it('CANARY: the diameter value must never be read as the reflux value', () => {
    // The exact mis-placement: under the headerless shape, reflux column index
    // 1 pointed at cells[1] = "7", the DIAMETER. With the offset it points at
    // cells[2] = "2.4".
    const row = parseMarkdownTables(HEADERLESS)[0]!.rows[0]!;
    const headerCols = parseMarkdownTables(HEADERLESS)[0]!.header.length;
    const offset = headerCols === row.cells.length ? 0 : 1;
    expect(offset).toBe(1);
    expect(row.cells[1 + offset]).toBe('2.4');
    expect(row.cells[1 + offset]).not.toBe('7');
  });
});

describe('defect 1b — a BARE PROSE trailing annotation', () => {
  // The third form L4 emits. Enumerating annotation forms was a losing game;
  // the cells are fixed by the pipes before the annotation.
  const BARE = [
    '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- | --- |',
    '| GSV at the SFJ | 7 | 2.4 | Great saphenous vein at the saphenofemoral junction: diameter 7 millimeters, reflux 2.4 seconds.',
    '| GSV at the Proximal Thigh | 6.4 | 2.1 | Right great saphenous vein at the proximal thigh.',
    '| GSV Below Knee | [not documented] | [not documented] |',
  ].join('\n');

  it('parses every row', () => {
    expect(parseMarkdownTables(BARE)[0]!.rows).toHaveLength(3);
  });

  it('keeps the values and does not leak the prose into a cell', () => {
    const [table] = parseMarkdownTables(BARE);
    const sfj = table!.rows[0]!;
    expect(sfj.cells[1]).toBe('7');
    expect(sfj.cells[2]).toBe('2.4');
    expect(sfj.cells.some((c) => c.includes('saphenofemoral'))).toBe(false);
  });
});

// ============================================================================
// A DOCUMENT WITH NOTHING IN IT IS NOT A DOCUMENT.
// ----------------------------------------------------------------------------
// A fill that resolves no field validates trivially — there is no populated
// value to object to — so it produced a VERIFIED manifest and the export handed
// back the doctor's blank form as if it were their note. It was found by
// unzipping the exported file and looking for the dictated numbers: every one
// was absent, while the run had reported nativeTemplateApplied=true.
//
// The status now requires at least one filled field, so an empty fill withholds
// the native document and the styled export stands.
// ============================================================================

describe('the zero-fill floor', () => {
  const src = () => {
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    return readFileSync(join(__dirname, '..', 'fill-engine.ts'), 'utf-8');
  };

  it('VERIFIED requires a render AND at least one filled field', () => {
    expect(src()).toContain(
      "prepared.render && prepared.manifest.counts.filled > 0 ? 'VERIFIED' : 'NEEDS_REVIEW'",
    );
  });

  it('and says so — an empty fill is never silent', () => {
    expect(src()).toContain('NOTHING FILLED');
  });
});
