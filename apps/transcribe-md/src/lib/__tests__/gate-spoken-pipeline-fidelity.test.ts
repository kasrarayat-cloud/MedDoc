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
    //
    // ⚠️ THE FIXTURE IS THE GENERATOR'S REAL HEADER, NOT A TIDY ONE.
    // `build-soap-prompt.ts:411-416` deliberately emits an UNNAMED leading cell
    // whenever the template's first column is a data column — which is the real
    // customer form. The first version of this arm used `| Vein | … |`, a named
    // and width-matched header, and so passed while the shipped shape spoke two
    // names over a three-value row.
    const table = [
      '|  | DIAMETER (mm) | REFLUX TIME (ms) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');
    const note = ['## Findings', 'Right Leg', '', table, '', 'Left Leg', '', table].join('\n');
    const out = spoken(note);
    expect(out, 'the column names must reach the listener').toContain('DIAMETER (mm)');
    expect(out).toContain('REFLUX TIME (ms)');

    // ⚠️ AND THE NAMES MUST LINE UP WITH THE VALUES. Three cells, three names —
    // the unnamed column is spoken in position rather than compacted away, or a
    // listener pairs left-to-right and hears a diameter as a reflux time.
    const line = out.split('\n').find((l) => l.startsWith('Columns:'))!;
    expect(line, 'no Columns line was spoken').toBeTruthy();
    expect(line.replace(/^Columns: |\.$/g, '').split(', ')).toHaveLength(3);
  });

  it('a header is NOT named when it cannot be aligned to the rows', () => {
    // ⚠️ A PARTIAL MAPPING IS WORSE THAN NONE — `claim-prose.ts:60-64` and `:123`
    // both refuse for exactly this reason. A ragged header must produce silence
    // about columns, not a confident subset.
    const ragged = [
      '| DIAMETER (mm) | REFLUX TIME (s) |',
      '| --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
    ].join('\n');
    const note = ['## Findings', ragged, '', 'x', '', ragged].join('\n');
    expect(spoken(note)).not.toContain('Columns:');

    // …and a header of nothing but blanks names nothing.
    const blank = ['|  |  |  |', '| --- | --- | --- |', '| GSV at the SFJ | 6.2 | 3.4 |'].join('\n');
    const n2 = ['## Findings', blank, '', 'y', '', blank].join('\n');
    expect(spoken(n2)).not.toContain('Columns:');
  });

  it('an ANNOTATED row mid-table does not truncate the scan', () => {
    // `claimProse` reads rows through the tolerant `parseMarkdownRow`, which
    // accepts a trailing annotation that spoken-body's strict ROW_RE rejects.
    // Terminating on the first strict miss decided the drop over a PREFIX and
    // deleted the header while a later row still spoke as raw pipes — and the
    // truncation is unidirectional toward that harm.
    const table = [
      '| Segment | DIAMETER (mm) | REFLUX TIME (s) |',
      '| --- | --- | --- |',
      '| GSV at the SFJ | 6.2 | 3.4 |',
      '| SSV at the Proximal Calf | 3.1 | 0.4 | [S1: "small saphenous"]',
      '| PTV at the Ankle | 2.9 | 0.2 |',
    ].join('\n');
    const note = ['## Findings', 'Right Leg', '', table, '', 'Left Leg', '', table].join('\n');
    const out = spoken(note);
    // both legs named, and named the SAME way — not one spoken and one silent
    expect(out.split('Columns:').length - 1, 'both legs must be named').toBe(2);
    expect(out).toContain('PTV at the Ankle');
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
    // ⚠️ THE OTHER DIRECTION, OR THE ARM IS HALF A CLAIM. Without this, a
    // mutation that replaced most of the note with "Not documented." would
    // satisfy every arm in this file while erasing the doctor's words.
    expect(out, "the doctor's own text must still be spoken").toContain('[Subjective] x');
    expect(spokenSections(note).map((s) => s.label)).toEqual(['Subjective', 'Assessment']);
  });
});

describe('the header rules cannot be satisfied vacuously', () => {
  it('a table with NO data rows does not collapse the section to "Not documented."', () => {
    // `body.length > 0` guards `[].every()`, which is vacuously true. Without
    // it a header-and-rule-only table takes the drop path, the section empties,
    // and `spokenBody`'s fallback announces an absence the note never states.
    const t = ['| Vein | Diameter (mm) |', '| --- | --- |'].join('\n');
    expect(spokenBody(t, '## Findings\n' + t)).not.toBe('Not documented.');
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
    // ⚠️ AND THE FIELD SET IS PINNED. The design rests on the change being
    // ADDITIVE — an extra field appearing where a consumer spreads, stringifies
    // or key-counts the object is exactly what would break E/M scoring, and
    // nothing else in 5,730 tests measures it.
    expect(Object.keys(secs[0]).sort()).toEqual(['body', 'key', 'label', 'letter', 'present']);
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
    // ⚠️ ASSERT WHAT THE TITLE CLAIMS. The first version asserted only
    // `not.toContain('---')`, which passes on an implementation that NEVER drops
    // the header — the arm was named for a behaviour it did not measure.
    expect(body).not.toContain('Columns:');
    // and no ALIGNMENT RULE may ever survive
    expect(body).not.toContain('---');
  });
});
