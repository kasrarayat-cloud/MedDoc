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
