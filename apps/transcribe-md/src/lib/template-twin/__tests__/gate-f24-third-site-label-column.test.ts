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
// 1. THE PRODUCTION UNIVERSE — AND THERE ARE **TWO** OF THEM
// ---------------------------------------------------------------------------
// ⚠️ AN EARLIER DRAFT OF THIS BLOCK WAS TITLED "the production universe" AND
// ENUMERATED THE SIX FIRST-CELL VALUES FROM THE NOTE-SHAPE CENSUS. That set is
// real, and it is the **editor's** universe. THIS FILE GUARDS THE **FILL**
// PATH, whose universe is a strict and much smaller subset — and conflating
// them is canon's "a check whose title is wider than what it measures", caught
// in this gate before merge.
//
// Both were measured READ-ONLY against production on 2026-08-23 by this
// session, with an independently written query — not inherited from another
// session's report:
//
//   THE FILL UNIVERSE (what `bridgeNumericTableCells` actually runs on):
//     1 compiled version · 1 certification · 2 fill manifests · 2 visits
//     -> 4 table header lines, and ALL FOUR are `DIAMETER (mm)`.
//
//   THE NOTE CORPUS (the editor's universe, a superset):
//     45 header lines · 24 visits · six distinct first cells.
//     Re-measured this session and it reproduces the census EXACTLY:
//     DIAMETER (mm) 27/14 · Location 8/4 · Segment 6/3 · Site 2/1 ·
//     DIAMETER 1/1 · Medication 1/1.
//
// ⚠️ SO THE HONEST COVERAGE CLAIM IS TWO SENTENCES, NOT ONE:
//   · this change covers **4 of 4** header lines the fill path meets today, and
//     that one shape is provably unmoved (`data` -> offset 1, which is what the
//     old vocabulary also answered);
//   · and **6 of 6** values the wider corpus holds classify safely, so the fill
//     is not walking into a refusal the day a second template certifies.
//
// The second sentence is a FORWARD-LOOKING claim about a set this code does not
// reach yet. It is asserted because that is when it is cheap, not because it is
// covered today.
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

  // ⚠️ AN ARM HERE ONCE CALLED ITSELF "THE ARM THAT ACTUALLY COVERS THIS CODE
  // PATH" AND NEVER CALLED `bridgeNumericTableCells` — it re-asserted
  // `classifyHeaderCell('DIAMETER (mm)') === 'data'`, which arm 1 of this
  // describe already does. It was written DURING the adversarial pass, in the
  // same edit that corrected a title-wider-than-it-measures defect, and the
  // pass caught it. Deleted rather than reworded.
  //
  // The fill universe's real coverage is BEHAVIOURAL and lives in §2 —
  // "PRE-Slice-1 legacy shape", which is exactly the 2-cell `DIAMETER (mm)`
  // header all 4 production fill-universe header lines carry.

  // ⚠️ SIX ARMS HERE USED TO ASSERT
  //     isDataColumnHeader(h) === (classifyHeaderCell(h) !== 'label')
  // OVER THE SIX PRODUCTION VALUES, AND THE ADVERSARIAL PASS PROVED THEM A
  // DEFINITIONAL TAUTOLOGY WITH ZERO PROTECTION. `isDataColumnHeader` IS that
  // expression (`table-header-shape.ts:230-232`), so the equality can only
  // discriminate on a `cannot_tell` input — and the arm two lines above
  // guarantees no member of this list is one. The universe was selected such
  // that the only discriminating input is absent.
  //
  // Demonstrated, not argued: mutating `isDataColumnHeader` to
  // `return classifyHeaderCell(h) === 'data'` — precisely the edit
  // `table-header-shape.ts:226-228` forbids in capitals, because it would
  // change what the GENERATOR emits into clinical notes — left all 25 arms
  // GREEN.
  //
  // Replaced by ONE arm aimed at the input that separates them.
  it('the generator still COLLAPSES cannot_tell to data — the forbidden edit is visible here', () => {
    expect(classifyHeaderCell('Vein Size')).toBe('cannot_tell');
    // If someone "fixes" isDataColumnHeader to return false on cannot_tell,
    // THIS reddens. Ruling #140 does not authorise that change: it would alter
    // the placeholder count the generator writes into notes.
    expect(isDataColumnHeader('Vein Size')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 1b. THE **FORWARD** UNIVERSE — what future notes will carry
// ---------------------------------------------------------------------------
// ⚠️ ADDED BY THE ADVERSARIAL PASS. §1 measures notes that ALREADY EXIST. The
// headers of notes not yet written come from `note_templates.sections[]
// .structure.columns`, which `renderStructureDirective` emits verbatim — a
// different set, and the one that decides whether this refusal ever fires
// again. Ruling #140 measured it and neither existing gate asserted it.
//
// Re-measured read-only on production 2026-08-23 by this session:
// **3 table structures, and all 3 lead with `DIAMETER (mm)`.** Reproduces
// #140's own figure rather than inheriting it.
describe('the forward universe — the columns future notes will carry', () => {
  it('every production template table leads with a column the predicate SETTLES', () => {
    expect(classifyHeaderCell('DIAMETER (mm)')).toBe('data');
  });

  // ⚠️ AND THE REFUSAL IS NEAR-UNREACHABLE FROM A GENERATED NOTE, WHICH BOUNDS
  // THE LOSS *AND* SHRINKS THE SAFETY BEING CLAIMED FOR IT — both halves stated.
  // `build-soap-prompt.ts` prepends an EMPTY first header cell whenever
  // `isDataColumnHeader(columns[0])`, so the emitted header has the same cell
  // count as its rows (delta 0 -> offset 0), and an empty cell classifies
  // `label` anyway. A `Vein Size`-shaped TEMPLATE column therefore cannot
  // produce a refusing header in a freshly generated note. The refusal can only
  // fire on a LEGACY note or one where the model deviated from the skeleton.
  it("the skeleton's empty leading cell classifies as label, so generated notes never refuse", () => {
    expect(classifyHeaderCell('')).toBe('label');
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

  // ⚠️ THIS ONE IS ALSO **THE ENTIRE PRODUCTION FILL UNIVERSE**. All 4 header
  // lines on the 2 visits carrying a fill manifest are this 2-cell
  // `DIAMETER (mm)` header. So the "zero production behaviour change" claim is
  // discharged by a PREDETERMINED control — which is the correct instrument for
  // "nothing moved", and is stated as such rather than counted as protection.
  it('PRE-Slice-1 legacy shape (= the production fill universe): header short at the FRONT', () => {
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
  // ⚠️ THE FIXTURE IS THE **DELTA-1** SHAPE, WHICH IS RULING #140's OWN, AND AN
  // EARLIER DRAFT OF THIS ARM USED THE DELTA-0 SHAPE AND WAS WRONG TO REFUSE
  // THERE. On a delta-0 table every header cell has a row cell and cell 0 is a
  // proven label, so `Vein Size` IS the label column by structure and the text
  // never gets a vote. Refusing there converted three CORRECT answers into
  // refusals — a capability loss with no safety behind it. See the delta-0 arms
  // below, which assert those same three headers now FILL.
  it.each(['Vein Size', 'Segment (right leg)', 'Site (see key)'])(
    'delta 1 + an ambiguous first column REFUSES: %s',
    (first) => {
      const got = fillsOf(
        `| ${first} | DIAMETER (mm) |`,
        '| Right GSV at the SFJ | 6.2 | 3.4 |',
      );
      expect(got.size).toBe(0);
    },
  );

  // ⚠️ THE OTHER HALF OF THE SAME COIN — AND THE ADVERSARIAL PASS'S FINDING 4.
  // Same three headers, delta 0. The structure settles it, so they fill, and
  // they fill in the RIGHT cells. A gate that only asserted the refusals would
  // have let a future edit refuse everything and still read green.
  it.each(['Vein Size', 'Segment (right leg)', 'Site (see key)'])(
    'delta 0 + the same ambiguous first column FILLS CORRECTLY: %s',
    (first) => {
      const got = fillsOf(
        `| ${first} | DIAMETER (mm) | REFLUX TIME (seconds) |`,
        '| Right GSV at the SFJ | 6.2 | 3.4 |',
      );
      expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
      expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
    },
  );

  // ⚠️ ADVERSARIAL PASS, FINDING 1 — A REFLUX TIME INTO A DIAMETER FIELD.
  // `classifyHeaderCell('Location (cm)')` is `data` (the trailing `(cm)` is a
  // unit), so a predicate-only offset read 1 on a delta-0 table: the DIAMETER
  // column resolved to the REFLUX cell and the reflux column ran off the end.
  // The OLD vocabulary answered this correctly, so the predicate-only form was
  // a REGRESSION of #140's own class.
  //
  // ⚠️ FOUR OF PRODUCTION'S SIX OBSERVED FIRST CELLS FLIP THIS WAY THE MOMENT A
  // UNIT IS APPENDED — `Location`, `Segment`, `Site`, `Medication`. Today none
  // carries one, which is why production was never exposed; that is a fact
  // about this corpus, not about the predicate.
  it.each(['Location (cm)', 'Segment (cm)', 'Site (mm)', 'Medication (mg)'])(
    'delta 0 + a LABEL column wearing a unit reads its OWN cells: %s',
    (first) => {
      const got = fillsOf(
        `| ${first} | DIAMETER (mm) | REFLUX TIME (seconds) |`,
        '| Right GSV at the SFJ | 6.2 | 3.4 |',
      );
      expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
      expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
    },
  );

  // ⚠️ ADVERSARIAL PASS, FINDING 2 — A DIAMETER INTO A REFLUX FIELD.
  // A 2-cell header over 3-cell rows CANNOT name the label column, so the
  // offset must be 1. `classifyHeaderCell('CFV mm')` returns `label` — the bare
  // unit never reaches #140's `cannot_tell` bucket — so a `label`-means-offset-0
  // rule put the DIAMETER value into the REFLUX field.
  //
  // delta 1 + `label` is INCOHERENT (the header claims to name the label column
  // AND the row has a spare cell), so it refuses. That is a real capability loss
  // against the old vocabulary, which read `CFV mm` as a diameter column and got
  // this shape right — and it is the honest answer, because the text cannot
  // settle it.
  it('delta 1 + a bare-unit first column REFUSES rather than shifting', () => {
    const got = fillsOf(
      '| CFV mm | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 6.2 | 3.4 |',
    );
    expect(got.size).toBe(0);
  });

  // ⚠️ THE OTHER DIVERGENCE DIRECTION, AND IT WAS ADDED BECAUSE THE ADVERSARIAL
  // PASS PROVED THE GATE BLIND TO IT. `§4` pinned `CFV mm -> label` at the
  // PREDICATE level and no fixture ever drove it through the bridge. The pass
  // reverted ONLY the `label` branch to the old vocabulary —
  //
  //     headerShape === 'data' ? 1 : classifyHeader(md.header[0]) !== 'other' ? 1 : 0
  //
  // — which is a real half-landed shape, and the gate stayed 25 of 25 GREEN.
  // Every other `label` first cell in this file (`VEIN`, `Segment`) is ALSO
  // `other` to the old vocabulary, so the two derivations agreed on every
  // behavioural fixture that existed. `CFV mm` is the only shape that separates
  // them, and it was the one shape with no behavioural arm.
  //
  // ⚠️ THIS IS THE PARTIAL APPLICATION THE AUTHOR'S OWN THREE MUTATIONS MISSED.
  // M1/M2/M3 moved the whole derivation or the `cannot_tell` branch; nobody
  // reverted ONE branch. Canon: "the interesting mutations are usually not
  // 'delete everything' but 'do the obvious first step'."
  //
  // `classifyHeader('CFV mm')` matches /(^|\W)mm(\W|$)/ -> 'diameter' -> offset 1,
  // so the diameter column reads the REFLUX cell and the reflux column runs off
  // the end of the row. Under the revert this arm sees ZERO fills.
  it('a bare-unit first column is the LABEL column — and this is asserted THROUGH the bridge', () => {
    const got = fillsOf(
      '| CFV mm | DIAMETER (mm) | REFLUX TIME (seconds) |',
      '| Right GSV at the SFJ | 6.2 | 3.4 |',
    );
    expect(got.get(cell(ir, DIAMETER_ROW, 1).fieldId)).toBe('6.2');
    expect(got.get(cell(ir, DIAMETER_ROW, 2).fieldId)).toBe('3.4');
  });

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
