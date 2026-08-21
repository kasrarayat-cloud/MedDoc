/**
 * Does a markdown table header cell name a DATA column rather than the
 * row-label column?
 *
 * ONE PREDICATE, TWO CALLERS. `build-soap-prompt.ts` asks this to decide
 * whether the skeleton it emits needs a label cell; `note-table-edit.ts` asks
 * it to decide whether a header that is one cell short is short at the FRONT.
 * They must answer identically or the generator will emit a shape the editor
 * misreads — which is the defect this module exists to close.
 *
 * A header column that carries a unit in parentheses, or names a measured
 * quantity, is a DATA column. A plain word like "VEIN" or "Segment" is the
 * label column.
 */
export function isDataColumnHeader(h: string): boolean {
  return /\([^)]*\)\s*$/.test(h) || /diameter|reflux|velocity|length|depth|time|size/i.test(h);
}
