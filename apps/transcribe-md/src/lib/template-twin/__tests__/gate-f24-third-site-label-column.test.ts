// ============================================================================
// RULING #140, THE THIRD SITE — THE TWIN FILL ASKS THE SHARED PREDICATE
// ----------------------------------------------------------------------------
// RELAY's F24-S3 close-out named this OWED, item 2, verbatim:
//
//   "⚠️ A THIRD SITE STILL DECIDES THIS QUESTION, AND THE DRIFT WIDENED FROM
//    TWO ANSWERS TO THREE. `template-twin/bridge-fill.ts` `classifyHeader`
//    (consumed at :425 for `labelColumnOffset`) uses its own two-valued
//    vocabulary. On `Vein Size` the three sites now say *no label column* /
//    *REFUSE* / *has a label column*."
//
// On `Vein Size`, before this change:
//
//     isDataColumnHeader   -> true         "no label column"     (generator)
//     classifyHeaderCell   -> cannot_tell  "REFUSE"              (editor)
//     classifyHeader       -> other        "has a label column"  (the FILL)
//
// The fill held the outlier, and this offset decides WHICH NOTE CELL a
// measurement is read out of before it is written into the doctor's own form.
//
// ⚠️ WHAT THIS GATE CLAIMS, AND WHAT IT DELIBERATELY DOES NOT.
//
//   · It does NOT assert `classifyHeader`'s divergence directly. That symbol is
//     still not exported (`bridge-fill.ts`), and re-implementing a shipped
//     predicate inside a test is the F12-g failure — an SQL re-implementation
//     answered 19 where the shipped predicate answered 15, and the 19 reached a
//     ledger row. The reconciliation is asserted BEHAVIOURALLY instead, by
//     running the real `bridgeNumericTableCells` over headers where the two
//     vocabularies disagree and checking which answer wins.
//   · It does NOT claim `classifyHeader` was deleted. It keeps its real job —
//     COLUMN ROLE (diameter / reflux / other), which decides `diameterCol` and
//     `refluxCol` and is exactly right for that. Canon: "a deletion is scoped by
//     what the component DOES, not by what the ruling CALLS it." The component
//     had two jobs; only one of them was the ruling's.
//   · It does NOT reach the note-EDITING path. That is `note-table-edit.ts` and
//     is already gated by `gate-f24-s3-label-column-from-evidence.test.ts`.
//
// ⚠️ AND ONE MECHANISM IS NAMED AS UNREACHABLE RATHER THAN GUARDED. The
// `md.header.length === 0 -> cannot_tell` branch in the shipped code cannot be
// reached: `pickTables` admits a table only when
// `t.header.some(h => classifyHeader(h) !== 'other')`, and `.some` on an empty
// array is false. It is defensive, it is not a live guard, and saying so here
// stops a future reader citing it as coverage.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { classifyHeaderCell, isDataColumnHeader } from '@/lib/table-header-shape';

import { bridgeNumericTableCells } from '../bridge-fill';
import { type TemplateDocIR, type TemplateField } from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));

// ---------------------------------------------------------------------------
// FIXTURES — copied in shape from `bridge-fill.test.ts`, deliberately.
// ---------------------------------------------------------------------------
// ⚠️ COPYING A FIXTURE IS FINE; COPYING A PREDICATE IS NOT. Nothing below
// re-implements a shipped decision — these are inputs. Every predicate under
// test is imported and run.
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

function fact(n: number, concept: string, laterality: 'left' | 'right' = 'right') {
  const id = `ttfact_${Math.abs(hash(`${concept}${n}${laterality}`)).toString(16).padStart(24, '0').slice(0, 24)}`;
  return {
    factId: id,
    sourceType: 'encounter_evidence' as const,
    concept,
    value: String(n),
    polarity: 'affirmed' as const,
    temporality: 'current' as const,
    experiencer: 'patient' as const,
    laterality,
    number: n,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${id.slice(-8)}`],
    evidenceQuote: 'synthetic fixture evidence',
    segment: null,
    quality: { asr: 'unknown' as const, evidence: 'direct' as const },
  };
}

const FACTS = [
  fact(6.2, 'gsv sfj diameter', 'right'),
  fact(3.4, 'gsv sfj reflux', 'right'),
];

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

/** Row 1 is the RIGHT GSV-at-SFJ row; cell 1 is diameter, cell 2 is reflux. */
const DIAMETER_ROW = 1;

const ir = compileTemplateDocx(wmIovBytes);

/** Build the smallest note the bridge will walk: a header, a rule, one row. */
function noteWith(header: string, row: string): string {
  return ['FINDINGS', 'Right great saphenous vein reflux positive.', '', header, '| --- | --- | --- |', row].join(
    '\n',
  );
}

function fillsOf(header: string, row: string) {
  const res = bridgeNumericTableCells({ facts: FACTS, ir, filledNote: noteWith(header, row) });
  return new Map(res.map((r) => [r.fieldId, r.value]));
}

// ---------------------------------------------------------------------------
// 0. NON-VACUITY — before any count below is read
// ---------------------------------------------------------------------------
// ⚠️ WITHOUT THIS, A COMPILE THAT SILENTLY PRODUCED ZERO FIELDS WOULD MAKE
// EVERY "REFUSED" ARM PASS FOR THE WRONG REASON. A refusal and an empty
// universe are the two states this file exists to keep apart.
describe('non-vacuity — the real customer form actually compiled', () => {
  it('WM_IOV compiles to its 80 fields, with a diameter and a reflux cell on row 1', () => {
    expect(ir.fields.length).toBe(80);
    expect(cell(ir, DIAMETER_ROW, 1).fieldId).not.toBe(cell(ir, DIAMETER_ROW, 2).fieldId);
  });
});

// ---------------------------------------------------------------------------
// 1. THE PRODUCTION UNIVERSE — and it is a CLOSED, MEASURED set
// ---------------------------------------------------------------------------
// Every distinct header first cell production holds, from the census in
// `docs/qa-reports/f24-s3-production-note-shape-census-20260822.md` §4 —
// 45 header lines across 24 visits, six distinct values, re-measured there
// rather than inherited.
//
// ⚠️ THE SAFETY CLAIM OF THIS WHOLE CHANGE IS THIS ONE ARM: not one production
// header lands in `cannot_tell`, so the new refusal costs production nothing.
// And it COULD have come out otherwise — a `Vein Size`-shaped value in that
// census would appear here as a newly-refused header and redden this arm.
describe('the production universe — no production header is refused', () => {
  const PRODUCTION_FIRST_CELLS: [string, 'data' | 'label', number][] = [
    ['DIAMETER (mm)', 'data', 27],
    ['Location', 'label', 8],
    ['Segment', 'label', 6],
    ['Site', 'label', 2],
    ['DIAMETER', 'data', 1],
    ['Medication', 'label', 1],
  ];

  it.each(PRODUCTION_FIRST_CELLS)('%s -> %s', (header, verdict) => {
    expect(classifyHeaderCell(header)).toBe(verdict);
  });

  it('all 45 production header lines are accounted for by those six values', () => {
    expect(PRODUCTION_FIRST_CELLS.reduce((n, [, , lines]) => n + lines, 0)).toBe(45);
  });

  it('NOT ONE production header is cannot_tell — the refusal costs production nothing', () => {
    const refused = PRODUCTION_FIRST_CELLS.filter(([h]) => classifyHeaderCell(h) === 'cannot_tell');
    expect(refused.map(([h]) => h)).toEqual([]);
  });

  // The generator's binary view is the complement of `label` BY CONSTRUCTION,
  // so the generator and the fill cannot disagree once both read this module.
  it.each(PRODUCTION_FIRST_CELLS)('generator and classifier agree on %s', (header) => {
    expect(isDataColumnHeader(header)).toBe(classifyHeaderCell(header) !== 'label');
  });
});

// ---------------------------------------------------------------------------
// 2. THE REGRESSION CONTROLS — both shapes production actually holds
// ---------------------------------------------------------------------------
// ⚠️ LABELLED AS PREDETERMINED, HONESTLY. The old vocabulary and the new
// predicate agree on both of these, so neither arm can distinguish a working
// fix from a broken one. They are REGRESSION controls — they prove the change
// took nothing away — and canon's "mutate toward SUCCESS, not just toward
// failure" is exactly what they are for. The DISCRIMINATING arms are in §3.
describe('regression control — production keeps filling, both header shapes', () => {
  it('POST-Slice-1 shape: header names the label column (delta 0)', () => {
    const got = fillsOf(
      '| VEIN | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 6.2 | 3.4 |',
    );
    expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
    expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
  });

  it('PRE-Slice-1 legacy shape: header is short at the FRONT (delta 1)', () => {
    const got = fillsOf(
      '| DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 6.2 | 3.4 |',
    );
    expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
    expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
  });
});

// ---------------------------------------------------------------------------
// 3. THE DISCRIMINATING ARMS — where the two vocabularies disagree
// ---------------------------------------------------------------------------
describe('the third site now answers with the SHARED predicate', () => {
  // ⚠️ THE FIX DIRECTION. `classifyHeader` reads `VELOCITY (cm/s)` as `other`
  // and therefore "the header HAS a label column" -> offset 0, so the diameter
  // column resolved to the VELOCITY cell and a velocity was offered to a
  // diameter field. `classifyHeaderCell` reads it as `data` (cm/s is a unit) ->
  // offset 1, and the diameter resolves to the diameter.
  //
  // Under the old vocabulary this fixture fills NOTHING: 99 has no supporting
  // fact, and 6.2 offered to the REFLUX field is refused on concept by the
  // evidence matcher. So the arm discriminates in both directions at once.
  it('a unit-parenthetical first column is DATA — the measurement lands in its own field', () => {
    const got = fillsOf(
      '| VELOCITY (cm/s) | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 99 | 6.2 | 3.4 |',
    );
    expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
    expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
    // And the velocity is nowhere — it was never a candidate value.
    expect([...got.values()]).not.toContain('99');
  });

  // ⚠️ THE REFUSAL DIRECTION, AND THIS IS THE ARM RULING #140 EXISTS FOR.
  // `Vein Size` reads as {label, data} or {data, data} with equal force. The
  // old vocabulary GUESSED `other` and filled; the shared predicate refuses.
  //
  // ⚠️ IT IS A REAL CAPABILITY LOSS ON THIS SHAPE, AND IT IS THE ACCEPTED ONE:
  // #140 rules that ambiguity is refused rather than guessed better, and §1
  // measures the cost on production at ZERO. Refusing costs a retype; guessing
  // costs a measurement.
  it.each(['Vein Size', 'Segment (right leg)', 'Site (see key)'])(
    'an ambiguous first column REFUSES the whole candidate table: %s',
    (first) => {
      const got = fillsOf(
        `| ${first} | DIAMETER (mm) | REFLUX TIME (seconds) |`,
        '| Right GSV at the SFJ | 6.2 | 3.4 |',
      );
      expect(got.size).toBe(0);
    },
  );

  // ⚠️ AND THE REFUSAL IS A PROPERTY OF THE PREDICATE, NOT OF THE FIXTURE.
  // Same note, same facts, same row — only the first header cell changes, and
  // a first cell the predicate CAN settle fills. Without this, "size 0" could
  // mean the fixture never reached the bridge at all.
  it('control: the same fixture with a settleable first cell DOES fill', () => {
    const got = fillsOf(
      '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 6.2 | 3.4 |',
    );
    expect(got.size).toBeGreaterThan(0);
    expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
  });
});

// ---------------------------------------------------------------------------
// 4. THE SPLIT-FAMILY PIN — both directions of the reconciliation
// ---------------------------------------------------------------------------
// Canon: "asserting only the half you added lets a future edit remove the half
// that was already there." The two directions here are the two ways the fill
// can drift back out of step with the generator and the editor.
describe('both directions of the drift are pinned', () => {
  it('a first cell the OLD vocabulary called data and the shared one calls label', () => {
    // `CFV mm` matched `classifyHeader`'s /(^|\W)mm(\W|$)/ and was read as a
    // data column. The shared predicate reads it as the row-label column.
    expect(classifyHeaderCell('CFV mm')).toBe('label');
  });

  it('a first cell the OLD vocabulary called other and the shared one calls data', () => {
    expect(classifyHeaderCell('VELOCITY (cm/s)')).toBe('data');
  });
});
