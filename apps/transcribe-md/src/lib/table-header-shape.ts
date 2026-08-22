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
// THE RULING: EVIDENCE OVER TEXT-GUESSING. Where the visit is TEMPLATE-BOUND
// the label column is resolved from the twin's compiled structure, which knows
// its own columns (`note-table-edit.ts`, `TwinTableStructure`). The text
// heuristic survives ONLY as the untemplated fallback, and there it must REFUSE
// HONESTLY when the classification is ambiguous — never pad and shift.
//
// So the vocabulary below answers THREE ways rather than two. `cannot_tell` is
// the bucket ruling #140 exists to create: today it was silently merged into
// `data`, which is precisely how a label column became a measurement column.
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
 */
const UNIT_PARENTHETICAL =
  /\(\s*(mm|cm|m|in|mm2|mm²|cm2|cm²|ml|l|%|mmhg|mm\s*hg|ms|msec|s|sec|secs|second|seconds|min|mins|minute|minutes|cm\/s|cm\/sec|mm\/s|m\/s|hz|khz|db|deg|degrees|°|kg|g|lb|lbs|bpm)\s*\)\s*$/i;

/** The measurement nouns the original vocabulary recognises, as whole words. */
const MEASUREMENT_NOUNS = new Set([
  'diameter',
  'reflux',
  'velocity',
  'length',
  'depth',
  'time',
  'size',
]);

/**
 * Every word in the cell is a measurement noun — `DIAMETER`, `REFLUX TIME`.
 *
 * ⚠️ "CONTAINS a measurement word" IS THE DEFECT; "IS MADE OF THEM" IS THE
 * EVIDENCE. `Vein Size` contains `size` and is a row-label column; `REFLUX
 * TIME` is nothing but measurement nouns and is a data column. The old
 * predicate could not tell those apart because it asked the weaker question.
 */
function isEntirelyMeasurementWords(h: string): boolean {
  const bare = h
    .replace(/\*\*/g, '')
    .replace(/\([^)]*\)\s*$/, '')
    .trim()
    .toLowerCase();
  if (bare === '') return false;
  const words = bare.split(/[^a-z]+/i).filter(Boolean);
  if (words.length === 0) return false;
  return words.every((w) => MEASUREMENT_NOUNS.has(w));
}

/**
 * Classify a header's FIRST cell.
 *
 * ⚠️ THE PARTITION IS TOTAL AND EVERY CELL LANDS IN EXACTLY ONE BUCKET, which
 * is what lets the editor's guard assert a reconciled census rather than a
 * ratio. `label` is exactly the complement of the original text test, so the
 * generator's view (below) is unchanged by construction.
 */
export function classifyFirstHeaderCell(h: string): HeaderCellVerdict {
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
  return classifyFirstHeaderCell(h) !== 'label';
}
