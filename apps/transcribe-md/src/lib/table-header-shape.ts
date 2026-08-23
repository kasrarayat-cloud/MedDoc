// ============================================================================
// Does a markdown table header cell name a DATA column, or the ROW-LABEL column?
// ----------------------------------------------------------------------------
// ONE VOCABULARY, TWO VIEWS, AND THE TWO VIEWS ARE DELIBERATE — RULING #140.
//
// `build-soap-prompt.ts` asks this to decide whether the skeleton it emits needs
// a label cell. `note-table-edit.ts` asks it to decide whether a header that is
// one cell short is short at the FRONT. Those are the same QUESTION and they do
// NOT carry the same COST when the answer is wrong:
//
//   generator wrong -> a skeleton with the wrong number of placeholder columns,
//                      visible in the note, fixed by regenerating.
//   editor wrong    -> EVERY COLUMN RESOLVES ONE PLACE TO THE RIGHT, and a
//                      measurement is written into the neighbouring cell while
//                      the doctor is told the column they named was changed.
//
// ⚠️ RULING #140's DEFECT, VERBATIM, BECAUSE IT IS THE REASON THIS FILE CHANGED.
// `isDataColumnHeader` decided "is this a data column?" by asking whether the
// text LOOKS like a measurement — a trailing parenthetical, or one of a handful
// of measurement words. A header cell that genuinely IS the label column and
// happens to satisfy that text test was therefore classified as DATA:
//
//     | Vein Size | DIAMETER (mm) |
//     | GSV at the SFJ | 6.2 | 3.4 |
//     edit DIAMETER (mm) := 7.7
//       -> ok:true, column:"DIAMETER (mm)", before:"3.4"
//       -> | GSV at the SFJ | 6.2 | 7.7 |
//
// The diameter is untouched, the REFLUX TIME is destroyed, and the doctor is
// told the diameter changed. Reproduced identically for `Segment (right leg)`
// and `Site (see key)`; the controls `VEIN` and `Segment` refuse — so it is a
// property of the PREDICATE, not of a fixture.
//
// THE RULING: EVIDENCE OVER TEXT-GUESSING. The text heuristic survives ONLY as
// the untemplated fallback, and there it must REFUSE HONESTLY when the
// classification is ambiguous — never pad and shift.
//
// So the vocabulary below answers THREE ways rather than two. `cannot_tell` is
// the bucket ruling #140 exists to create: today it was silently merged into
// `data`, which is precisely how a label column became a measurement column.
//
// ⚠️ THE OTHER HALF OF #140 — RESOLVING THE LABEL COLUMN FROM THE TWIN'S
// COMPILED STRUCTURE — IS **NOT** IMPLEMENTED HERE, AND THE FIRST ATTEMPT AT
// IT WAS BUILT AND THEN REMOVED. It keyed on the twin's DATA COLUMN COUNT, and
// a count cannot answer a question about which END a header is short at: a
// header of {label + N-1 data} and one of {N data} both have N cells. It also
// widened grids the text route correctly refuses.
// **Do not re-add a twin route keyed on a count.**
//
// ⚠️ AND THE OBVIOUS REPLACEMENT MECHANISM IS **REFUTED BY MEASUREMENT** — I
// wrote it into this comment as "the twin can say whether its own header row's
// first cell is EMPTY", then went and looked. Production's single CERTIFIED
// compiled version, table 0:
//
//     row 0 (header)  cell0 HAS TEXT   cell1 HAS TEXT   cell2 HAS TEXT   0 fields
//     row 1 (data)    cell0 HAS TEXT   cell1 1 field    cell2 1 field
//
// So the twin's header row NAMES ALL THREE COLUMNS, cell 0 included, while the
// rendered note carries a TWO-cell header. The twin therefore knows there are
// 3 columns and that column 0 is the label (static text, no field) — and it
// still cannot say WHICH header cell the note dropped, because deciding that
// needs the header cells' TEXT and the IR stores only `staticTextSha256`.
//
// **THAT is the real blocker for #140's twin half, and it is now measured
// rather than assumed:** the evidence lives in the source artifact, not in the
// IR. Anyone building it needs the text, plus the note-table -> twin-table
// identification F24-S3 has not built either.
// ============================================================================

/**
 * The classification, three-valued.
 *
 * - `data`        the cell unambiguously names a measured quantity, so the
 *                 header has NO row-label column.
 * - `label`       the cell does not look like a measurement at all, so the
 *                 header DOES name its row-label column.
 * - `cannot_tell` the text test fires but does not settle it. ⚠️ THIS IS NOT A
 *                 MIDPOINT — it is a refusal. The editor must not widen on it.
 */
export type HeaderCellVerdict = 'data' | 'label' | 'cannot_tell';

/**
 * The ORIGINAL text test, preserved byte-for-byte as one expression.
 *
 * ⚠️ DO NOT "TIDY" THIS INTO THE CLASSIFIER BELOW. It is kept whole and
 * separate because `isDataColumnHeader` is defined as its negation-of-`label`,
 * which is what makes the generator's behaviour provably unchanged by ruling
 * #140 — asserted as a truth table in
 * `gate-f24-s3-label-column-from-evidence.test.ts`.
 */
function looksLikeDataColumn(h: string): boolean {
  return /\([^)]*\)\s*$/.test(h) || /diameter|reflux|velocity|length|depth|time|size/i.test(h);
}

/**
 * A trailing parenthetical whose content is a UNIT OF MEASURE.
 *
 * ⚠️ THIS IS THE DISCRIMINATOR THE OLD PREDICATE LACKED. It fired on ANY
 * trailing parenthetical, so `Segment (right leg)` — a LATERALITY — and
 * `Site (see key)` — a CROSS-REFERENCE — both read as measurements. A unit is
 * evidence that the column holds a measured quantity; a row-label column never
 * carries one. Anything else in the brackets settles nothing.
 *
 * ⚠️ NO SINGLE-LETTER UNITS, AND THE ADVERSARIAL PASS IS WHY. The first draft
 * of this list carried `l`, `m`, `s`, `g`, `in` and `deg`. In vascular imaging
 * `(L)` and `(R)` are the commonest laterality shorthand there is, so
 * `Vein (L)` parsed as LITRES and widened:
 *
 *     | Vein (L) | DIAMETER (mm) |        edit DIAMETER := 7.7
 *     | GSV at the SFJ | 6.2 | 3.4 |   ->  ok:true, before "3.4"
 *
 * — the REFLUX TIME destroyed, the diameter untouched, reported as success.
 * **And `(R)` refused, because `r` was not in the list: the right leg refused
 * and the left leg silently corrupted, in the same bilateral study.** That is
 * the exact defect #140 exists to close, reintroduced by the fix for it.
 *
 * ⚠️ SO THE RULE IS: A UNIT EARNS ITS PLACE ONLY IF IT CANNOT PLAUSIBLY BE AN
 * ABBREVIATION FOR SOMETHING ELSE IN A CLINICAL TABLE HEADER. Single letters
 * never clear that bar, and neither does `in` (the English word) or `deg`.
 * Losing a genuine unit costs a REFUSAL; keeping an ambiguous one costs a
 * WRONG-CELL WRITE, and those are not the same price.
 */
const UNIT_PARENTHETICAL = new RegExp(
  `\\(\\s*(${[
    'mm', 'cm', 'mm2', 'mm²', 'cm2', 'cm²', 'cm3', 'mm3', 'cc',
    'ml', 'mg', 'mcg', 'kg', 'lbs', 'mmol', 'kpa',
    '%', 'mmhg', 'mm\\s*hg',
    'ms', 'msec', 'sec', 'secs', 'second', 'seconds',
    'min', 'mins', 'minute', 'minutes',
    'cm\\/s', 'cm\\/sec', 'mm\\/s', 'm\\/s', 'l\\/min', 'ml\\/min',
    'hz', 'khz', 'bpm', 'degrees',
  ].join('|')})\\s*\\)\\s*$`,
  'i',
);

/** The measurement nouns the original vocabulary recognises, as whole words. */
const MEASUREMENT_NOUNS = new Set([
  'diameter',
  'reflux',
  'velocity',
  'length',
  'depth',
  'time',
  'size',
  // Not in the original regex vocabulary, so these can only ever be reached
  // when some OTHER word in the same cell already matched it — they widen
  // `data`, they can never create it. `Reflux Duration` is the motivating case.
  'duration',
]);

/** Unit tokens written WITHOUT brackets — `Diameter mm`, `Diameter [mm]`.
 *  Single letters are excluded for the same reason they are excluded above. */
const UNIT_WORDS = new Set([
  'mm', 'cm', 'ml', 'cc', 'mg', 'mcg', 'kg', 'lbs',
  'ms', 'msec', 'sec', 'secs', 'second', 'seconds',
  'min', 'mins', 'minute', 'minutes', 'hz', 'khz', 'bpm', 'mmhg', 'degrees',
]);

/**
 * Every word in the cell is a measurement noun or a unit — `DIAMETER`,
 * `REFLUX TIME`, `Diameter mm`.
 *
 * ⚠️ "CONTAINS a measurement word" IS THE DEFECT; "IS MADE OF THEM" IS THE
 * EVIDENCE. `Vein Size` contains `size` and ruling #140 rules it a row-label
 * column; `REFLUX TIME` is nothing but measurement nouns and is a data column.
 * The old predicate could not tell those apart because it asked the weaker
 * question.
 *
 * ⚠️ AND THE KNOWN COST OF ASKING THE STRONGER ONE, MEASURED BY THE ADVERSARIAL
 * PASS AND ACCEPTED RATHER THAN HIDDEN: a measurement noun carrying a
 * NON-measurement qualifier — `Max Diameter`, `Peak Velocity`, `Nodule Size`,
 * `Total Length` — now lands in `cannot_tell` and is REFUSED where `main`
 * widened it. That is real capability loss on shapes production does not
 * currently hold (its three widening headers are unaffected, asserted in the
 * gate).
 *
 * It is NOT patched by adding a qualifier list, and that is a decision: a
 * qualified measurement noun is ambiguous in exactly the way `Vein Size` is —
 * `| Max Diameter | REFLUX |` reads as {label, data} or {data, data} with equal
 * force — and ruling #140's instruction for that case is to refuse, not to
 * guess better. **Refusing costs a retype; guessing costs a measurement.**
 * The retirement condition is named: a properly-built twin route, which
 * resolves it from the document instead of from words.
 */
function isEntirelyMeasurementWords(h: string): boolean {
  const bare = h
    .replace(/\*\*/g, '')
    .replace(/\([^)]*\)\s*$/, '')
    .trim()
    .toLowerCase();
  if (bare === '') return false;
  const words = bare.split(/[^a-z0-9]+/i).filter(Boolean);
  if (words.length === 0) return false;
  return words.every((w) => MEASUREMENT_NOUNS.has(w) || UNIT_WORDS.has(w));
}

/**
 * Classify ONE header cell.
 *
 * ⚠️ IT WAS `classifyFirstHeaderCell` AND THE NAME WAS A CLAIM THE CALLER
 * OUTGREW. The editor now asks this of EVERY header cell, not just cell 0 —
 * see the `Time` / `HEART RATE` case in `note-table-edit.ts`. A function whose
 * name says FIRST while callers pass it cell 2 is the check-whose-title-is-
 * narrower-than-what-it-measures family, so the name moved with the use.
 *
 * ⚠️ THE PARTITION IS TOTAL AND EVERY CELL LANDS IN EXACTLY ONE BUCKET, which
 * is what lets the editor's guard assert a reconciled census rather than a
 * ratio. `label` is exactly the complement of the original text test, so the
 * generator's view (below) is unchanged by construction.
 */
export function classifyHeaderCell(h: string): HeaderCellVerdict {
  if (!looksLikeDataColumn(h)) return 'label';
  if (UNIT_PARENTHETICAL.test(h) || isEntirelyMeasurementWords(h)) return 'data';
  return 'cannot_tell';
}

/**
 * The GENERATOR's binary view — behaviour unchanged by ruling #140.
 *
 * ⚠️ THE COLLAPSE IS EXPLICIT AND IT IS THE OLD BEHAVIOUR: `cannot_tell` is
 * treated as `data`, which is exactly what the original predicate did for
 * `Vein Size`, `Segment (right leg)` and `Site (see key)`. It is kept for the
 * generator on purpose — the generator cannot refuse, it must emit some number
 * of columns — and it is NOT kept for the editor, which can and now does.
 *
 * ⚠️ SO DO NOT "FIX" THIS TO RETURN `false` ON `cannot_tell`. That would change
 * what the generator emits into clinical notes, which is a different change
 * with a different blast radius, and ruling #140 does not authorise it.
 */
export function isDataColumnHeader(h: string): boolean {
  return classifyHeaderCell(h) !== 'label';
}
