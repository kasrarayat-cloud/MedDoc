// ============================================================================
// A doctor deciding whether something belongs in a patient's record should be
// shown a sentence, not a fragment of markup.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { claimProse } from '../claim-prose';

// The real shape, from a live ultrasound visit.
const NOTE = [
  '## FINDINGS',
  'DIAMETER AND REFLUX TIME — Right Leg',
  '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| GSV at the Knee | 3.4 | 1.8 |',
  '| SSV at the Proximal Calf | [not documented] | [not documented] |',
  '| AAGSV at the SFJ | 3.0 | [not documented] |',
  '',
  '## IMPRESSION',
  'Right great saphenous vein is reflux positive.',
].join('\n');

describe('table rows become prose', () => {
  it('reads a measurement row as a sentence, in the doctor’s own column names', () => {
    expect(claimProse('| GSV at the Knee | 3.4 | 1.8 |', NOTE)).toBe(
      'Right Leg — GSV at the Knee: diameter 3.4 mm, reflux time 1.8 seconds',
    );
  });

  it('leaves out a cell that documents nothing rather than printing a dash', () => {
    expect(claimProse('| AAGSV at the SFJ | 3.0 | [not documented] |', NOTE)).toBe(
      'Right Leg — AAGSV at the SFJ: diameter 3.0 mm',
    );
  });

  it('says so plainly when the whole row is undocumented', () => {
    expect(claimProse('| SSV at the Proximal Calf | [not documented] | [not documented] |', NOTE)).toBe(
      'Right Leg — SSV at the Proximal Calf: nothing documented',
    );
  });
});

describe('it never touches anything that is not a table row', () => {
  it('ordinary prose is returned verbatim', () => {
    const s = 'Right great saphenous vein is reflux positive.';
    expect(claimProse(s, NOTE)).toBe(s);
  });

  it('a row whose table is not in the note is left alone', () => {
    // Better a raw row than a confident mis-labelling against the wrong header.
    const row = '| Something Else | 9.9 | 9.9 |';
    expect(claimProse(row, NOTE)).toBe(row);
  });

  it('the alignment rule is never mistaken for content', () => {
    expect(claimProse('| --- | --- | --- |', NOTE)).toBe('| --- | --- | --- |');
  });

  it('a row with a different column count than its header is left alone', () => {
    const note = ['| A | B |', '| --- | --- |', '| x | 1 | 2 |'].join('\n');
    expect(claimProse('| x | 1 | 2 |', note)).toBe('| x | 1 | 2 |');
  });

  it('a header without units still reads', () => {
    const note = ['| Segment | Finding |', '| --- | --- |', '| GSV | patent |'].join('\n');
    expect(claimProse('| GSV | patent |', note)).toBe('GSV: finding patent');
  });

  it('an em-dash cell counts as undocumented (post-export convention)', () => {
    const note = ['| Segment | DIAMETER (mm) |', '| --- | --- |', '| GSV | — |'].join('\n');
    expect(claimProse('| GSV | — |', note)).toBe('GSV: nothing documented');
  });
});

describe('a bilateral study must never be mislabelled', () => {
  const BILATERAL = [
    '## FINDINGS',
    'DIAMETER AND REFLUX TIME — Right Leg',
    '| Segment | DIAMETER (mm) |',
    '| --- | --- |',
    '| GSV at the Knee | 3.4 |',
    '',
    'DIAMETER AND REFLUX TIME — Left Leg',
    '| Segment | DIAMETER (mm) |',
    '| --- | --- |',
    '| GSV at the Knee | 3.4 |',
  ].join('\n');

  it('refuses a row that appears in BOTH tables rather than guessing a leg', () => {
    // Pairing against whichever table came first would label a left-leg
    // measurement with the right leg's context — authoritative-sounding and
    // wrong. One match or nothing.
    const row = '| GSV at the Knee | 3.4 |';
    expect(claimProse(row, BILATERAL)).toBe(row);
  });

  it('carries the leg when the row is unambiguous', () => {
    const note = BILATERAL.replace('| GSV at the Knee | 3.4 |\n\nDIAMETER', '| GSV at the SFJ | 6.0 |\n\nDIAMETER');
    expect(claimProse('| GSV at the Knee | 3.4 |', note)).toBe(
      'Left Leg — GSV at the Knee: diameter 3.4 mm',
    );
  });

  it('does not double a unit the cell already carries', () => {
    const note = ['| Segment | DIAMETER (mm) |', '| --- | --- |', '| GSV | 6.2 mm |'].join('\n');
    expect(claimProse('| GSV | 6.2 mm |', note)).toBe('GSV: diameter 6.2 mm');
  });
});
