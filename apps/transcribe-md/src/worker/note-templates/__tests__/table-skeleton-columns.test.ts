// ============================================================================
// A ROW GETS ONE CELL PER COLUMN — the skeleton that lost every diameter.
// ----------------------------------------------------------------------------
// The row builder used `columns.slice(1)`, assuming the header's first column
// is the row-label column. WM_IOV's is not: its header is
// [DIAMETER (mm) | REFLUX TIME (seconds)] and the vein name sits in an unheaded
// first cell. So each row offered ONE placeholder for TWO data columns, and the
// generator did exactly what it was shown — then said so in the note:
//
//   "Diameter values dictated for the right GSV (SFJ 7 mm, Proximal Thigh
//    6.4 mm, Knee 5.1 mm) could not be placed, as the table skeleton provides
//    only a single value column per row."
//
// Every diameter in the document was lost, and certification blocked on a fill
// path that had never been given room to work. Caught on the first prod run,
// where the gate refused to certify a template with zero measurement cells.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { buildSoapSystemPrompt } from '../build-soap-prompt';

function skeletonFor(columns: string[], rowLabels: string[]): string[] {
  const prompt = buildSoapSystemPrompt(
    {
      id: 't',
      version: 1,
      isSystemDefault: false,
      sections: [
        {
          key: 'table',
          label: 'DIAMETER AND REFLUX TIME',
          order: 1,
          formatHint: 'table',
          styleInstructions: null,
          structure: { kind: 'table', columns, rowLabels },
        },
      ],
      styleProfile: null,
    } as never,
    {} as never,
  );
  return prompt.split('\n').filter((l) => l.trim().startsWith('|'));
}

describe('table skeleton column count', () => {
  it('an all-data header means the label cell is EXTRA: one placeholder per column', () => {
    const lines = skeletonFor(
      ['DIAMETER (mm)', 'REFLUX TIME (seconds)'],
      ['GSV at the SFJ', 'GSV at the Knee'],
    );
    const row = lines.find((l) => l.includes('GSV at the SFJ'))!;
    // | label | [nd] | [nd] |  → two value cells, not one.
    expect(row.split('[not documented]').length - 1).toBe(2);
  });

  it('a header that NAMES the label column keeps its original shape', () => {
    const lines = skeletonFor(
      ['VEIN', 'DIAMETER (mm)', 'REFLUX TIME (seconds)'],
      ['GSV at the SFJ'],
    );
    const row = lines.find((l) => l.includes('GSV at the SFJ'))!;
    expect(row.split('[not documented]').length - 1).toBe(2);
  });

  it('a single-data-column table still gets exactly one cell', () => {
    const lines = skeletonFor(['REFLUX TIME (seconds)'], ['GSV at the SFJ']);
    const row = lines.find((l) => l.includes('GSV at the SFJ'))!;
    expect(row.split('[not documented]').length - 1).toBe(1);
  });
});
