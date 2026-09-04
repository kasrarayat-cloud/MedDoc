// ============================================================================
// THE SPOKEN COPY MUST NOT LOSE THE NOTE, AND MUST NOT INVENT IT
// ----------------------------------------------------------------------------
// The visit document renders to <canvas>, so the DOM copy IS the reading order
// for assistive technology. The adversarial pass over PR #948 proved the old
// pipeline said three things the record does not. Each arm below is that pass's
// own reproduction, kept as an executable failure rather than a description.
//
// ⚠️ TWO DIRECTIONS, AND BOTH ARE DEFECTS. A subset check catches only the
// first: a spoken copy can be wrong by LOSING the doctor's words (the allergy)
// or by MANUFACTURING them ("Not documented." for a heading that never
// existed). Every arm here names which direction it guards.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { spokenSections, PREAMBLE_LABEL } from '@/lib/spoken-sections';
import { parseSoapSections, parseSoapSplit } from '@/lib/parse-soap-sections';
import { spokenBody } from '@/lib/spoken-body';

const spoken = (note: string) =>
  spokenSections(note).map((s) => `[${s.label}] ${s.body}`).join(' ');

describe('LOSS — the doctor\'s words must survive', () => {
  it('content above the first SOAP heading reaches the spoken copy', () => {
    // The pass's own reproduction. A sighted reader sees the allergy directly
    // above a penicillin-class prescription; before this, a listener did not.
    const note = [
      'ADDENDUM 2026-09-04: patient is ALLERGIC TO PENICILLIN — anaphylaxis.',
      '',
      '## Subjective',
      'Two weeks of dry cough.',
      '',
      '## Plan',
      'Amoxicillin 500 mg PO TID x7d.',
    ].join('\n');
    expect(spoken(note)).toContain('ALLERGIC TO PENICILLIN');
    expect(spokenSections(note)[0].label).toBe(PREAMBLE_LABEL);
    // …and it is spoken FIRST, because that is where it sits on the page.
    expect(spoken(note).indexOf('ALLERGIC')).toBeLessThan(spoken(note).indexOf('dry cough'));
  });

  it('a table header survives when its rows could NOT be rewritten', () => {
    // Row-text collision: `claimProse` needs a UNIQUE hit, so a bilateral study
    // whose legs carry identical rows came back as raw pipes with no column
    // names — numbers with no unit and no identity.
    const table = [
      '| Vein | Diameter (mm) | Reflux Time (seconds) |',
      '| --- | --- | --- |',
      '| GSV at the Knee | 6.2 | 1.8 |',
    ].join('\n');
    const note = ['## Findings', 'Right Leg', '', table, '', 'Left Leg', '', table].join('\n');
    const out = spoken(note);
    expect(out, 'the column names must reach the listener').toContain('Diameter (mm)');
    expect(out).toContain('Reflux Time (seconds)');
  });
});

describe('FABRICATION — the spoken copy must not assert what the record does not', () => {
  it('an ABSENT SOAP heading is never announced as "Not documented."', () => {
    const note = '## Subjective\nPatient declined further workup today.';
    expect(note.toLowerCase()).not.toContain('assessment');
    const out = spoken(note);
    expect(out).toContain('declined further workup');
    expect(out, 'the record makes no claim about an Assessment').not.toContain('Not documented');
    expect(spokenSections(note).map((s) => s.label)).toEqual(['Subjective']);
  });

  it('PARITY — a heading that IS present but empty still says "Not documented."', () => {
    // ⚠️ THE ARM THAT STOPS THE FIX OVERSHOOTING. The export prints those words
    // under a heading that exists, so suppressing empties would replace one
    // disagreement with another in the opposite direction.
    const note = '## Subjective\nx\n\n## Assessment\n';
    const out = spoken(note);
    expect(out).toContain('Not documented');
    expect(spokenSections(note).map((s) => s.label)).toEqual(['Subjective', 'Assessment']);
  });
});

describe('BLAST RADIUS — the shared parser\'s existing output is unchanged', () => {
  it('parseSoapSections still returns exactly four sections, in order, with the same bodies', () => {
    // ⚠️ THE ARM THAT PROTECTS E/M SCORING. `parseSoapSections` feeds
    // em-coding/score.ts and em-coding/deterministic.ts. The fix added FIELDS;
    // if it ever changes `body` or the shape of the array, clinical scoring
    // moves, and this arm is what says so.
    const note = 'preamble text\n\n## Subjective\nS body\n\n## Plan\nP body';
    const secs = parseSoapSections(note);
    expect(secs.map((s) => s.key)).toEqual(['S', 'O', 'A', 'P']);
    expect(secs.find((s) => s.key === 'S')!.body).toBe('S body');
    expect(secs.find((s) => s.key === 'P')!.body).toBe('P body');
    expect(secs.find((s) => s.key === 'O')!.body).toBe('');
    // the preamble is NOT smuggled into any section body
    for (const s of secs) expect(s.body).not.toContain('preamble text');
  });

  it('the new fields carry the information the spoken path needs', () => {
    const note = 'preamble text\n\n## Subjective\nS body';
    const split = parseSoapSplit(note);
    expect(split.preamble).toBe('preamble text');
    expect(split.sections.find((s) => s.key === 'S')!.present).toBe(true);
    expect(split.sections.find((s) => s.key === 'A')!.present).toBe(false);
  });

  it('a note with NO preamble yields an empty one — not the first section', () => {
    const split = parseSoapSplit('## Subjective\nonly this');
    expect(split.preamble).toBe('');
    expect(spokenSections('## Subjective\nonly this').map((s) => s.label)).toEqual(['Subjective']);
  });

  it('spokenBody still drops a table header when the rows WERE rewritten', () => {
    // The original behaviour, kept: where restoration happens the header is
    // redundant, and re-introducing raw markup would undo the fix it replaced.
    const note = [
      '## Findings',
      '| Vein | Diameter (mm) |',
      '| --- | --- |',
      '| GSV at the Knee | 6.2 |',
    ].join('\n');
    const body = spokenBody(
      ['| Vein | Diameter (mm) |', '| --- | --- |', '| GSV at the Knee | 6.2 |'].join('\n'),
      note
    );
    // whichever way claimProse resolves it, no ALIGNMENT RULE may ever survive
    expect(body).not.toContain('---');
  });
});
