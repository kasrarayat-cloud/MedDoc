import { describe, it, expect } from 'vitest';

import { groupPageFields } from '../group-fields';
import type { DetectedBox, DetectedPage, LabelSource } from '../types';

// Ruling #326, Slice A: a free-prose multi-line section's stacked boxes collapse
// to ONE field (one concept); single-line fields and numbered list slots stay one.
// A SECTION is a box labelled from a heading ABOVE (label_source 'above'); a
// field:value box (label_source 'left') never absorbs the box below it.

function box(
  x: number,
  y: number,
  w: number,
  h: number,
  label: string,
  source: LabelSource = 'left',
): DetectedBox {
  return { x, y, w, h, type: 'TextBox', label, labelSource: source };
}

function page(boxes: DetectedBox[]): DetectedPage {
  return { index: 0, widthPt: 612, heightPt: 792, boxes };
}

describe('group-fields (multi-line → one concept)', () => {
  it('collapses stacked same-heading boxes (label_source above) into one field', () => {
    const fields = groupPageFields(
      page([
        box(45, 400, 520, 16, 'DESCRIPTION OF PROCEDURE', 'above'),
        box(45, 382, 520, 16, 'DESCRIPTION OF PROCEDURE', 'above'),
        box(45, 364, 520, 16, '', ''), // empty continuation
      ]),
    );
    expect(fields).toHaveLength(1);
    expect(fields[0]!.multiline).toBe(true);
    expect(fields[0]!.boxes).toHaveLength(3);
    expect(fields[0]!.label).toBe('DESCRIPTION OF PROCEDURE');
  });

  it('merges a COLON-terminated section heading too (FINDINGS:, adv pass2 #2)', () => {
    const fields = groupPageFields(
      page([
        box(54, 570, 500, 12, 'FINDINGS:', 'above'),
        box(54, 553, 500, 12, '', ''),
      ]),
    );
    expect(fields).toHaveLength(1);
    expect(fields[0]!.multiline).toBe(true);
    expect(fields[0]!.label).toBe('FINDINGS:');
  });

  it('keeps numbered list slots as separate fields', () => {
    const fields = groupPageFields(
      page([
        box(63, 300, 500, 16, '1.'),
        box(63, 282, 500, 16, '2.'),
        box(63, 264, 500, 16, '3.'),
      ]),
    );
    expect(fields).toHaveLength(3);
    expect(fields.every((f) => !f.multiline)).toBe(true);
  });

  it('keeps distinct single-line field:value boxes separate', () => {
    const fields = groupPageFields(
      page([
        box(120, 690, 220, 16, 'PATIENT NAME:', 'left'),
        box(410, 690, 160, 16, 'PATIENT DOB:', 'left'),
        box(120, 668, 160, 16, 'PATIENT ID #:', 'left'),
      ]),
    );
    expect(fields).toHaveLength(3);
    expect(fields.map((f) => f.label)).toEqual([
      'PATIENT NAME:',
      'PATIENT DOB:',
      'PATIENT ID #:',
    ]);
  });

  it('does NOT absorb an unlabelled box under a field:value label (adv pass1 #3)', () => {
    const fields = groupPageFields(
      page([
        box(147, 690, 160, 12, 'PATIENT NAME:', 'left'),
        box(147, 676, 160, 12, '', ''), // a different field the detector left unlabelled
      ]),
    );
    expect(fields).toHaveLength(2);
    expect(fields[0]!.multiline).toBe(false);
  });

  it('does not merge across a large vertical gap even within a section', () => {
    const fields = groupPageFields(
      page([
        box(45, 400, 520, 16, 'NOTES', 'above'),
        box(45, 200, 520, 16, 'NOTES', 'above'), // far below — a different region
      ]),
    );
    expect(fields).toHaveLength(2);
  });

  it('assigns stable ids and preserves page index', () => {
    const fields = groupPageFields(page([box(45, 400, 520, 16, 'A')]));
    expect(fields[0]!.id).toBe('p0_f0');
    expect(fields[0]!.page).toBe(0);
  });
});
