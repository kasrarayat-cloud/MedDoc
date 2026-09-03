// ============================================================================
// THE CONTAINERS THE CLEAR COPIES VERBATIM — ONE SYMBOL, ONE FILE.
// ----------------------------------------------------------------------------
// ⚠️ #175 — THIS FILE EXISTS BECAUSE THERE WERE TWO LISTS FOR ONE SET.
//
// The renderer copied these containers verbatim; the compiler kept its own
// hand-written list of "property blocks" to scan for smuggled content. The two
// drifted by NINE NAMES — `bookmarkStart` (which Word emits as `_GoBack` in
// nearly every document), `sectPr`, `tblGrid`, `proofErr`, the comment and
// permission range markers — and a `w:fldSimple` inside a bookmark was
// admitted, survived the clear, and earned counted blank credit.
//
// `w:fldSimple` was already item 9 of the compiler's OWN carrier list. It
// classified the element as content and never looked inside the container the
// renderer was going to copy.
//
// ⚠️ CANON 91 IN CODE FORM: two lists describing one set become ONE SYMBOL.
// Re-listing them by hand — even correctly, even today — re-arms the divergence
// the next time either grows, and nothing would say.
//
// The behavioural half is `gate-175-derived-keep-list`: for EVERY member here,
// a content carrier placed inside that container must be refused at admission.
// Adding a name to this set without teaching admission reds it.
// ============================================================================

/** Property containers the clear copies verbatim, and admission must scan. */
export const STRUCTURE_KEEP_WHOLE: ReadonlySet<string> = new Set([
  'pPr', 'tblPr', 'tblGrid', 'trPr', 'tcPr', 'sectPr', 'sdtPr', 'sdtEndPr',
  'bookmarkStart', 'bookmarkEnd', 'proofErr',
  'commentRangeStart', 'commentRangeEnd',
  // ⚠️ ADDED AFTER THE PASS MEASURED THEIR LOSS. `w:tblPrEx` carries per-row
  // border and shading exceptions, so deleting it silently dropped row borders
  // inside any cleared control; `w:permStart`/`w:permEnd` mark editable ranges.
  // All three are properties, none renders content, and losing them is the
  // inverse failure v1 and v2 died of.
  'tblPrEx', 'permStart', 'permEnd',
  // ⚠️ #168 — A RUN'S OWN PROPERTIES ARE SKELETON. v3 deleted the whole run, so
  // an emptied inline control lost `w:rPr` on all 28 controls of the real
  // template (307 -> 279). An EMPTY run with properties prints nothing, and it
  // is what a doctor TYPING into the cleared control inherits — the capability
  // v3 was silently costing.
  'rPr',
]);
