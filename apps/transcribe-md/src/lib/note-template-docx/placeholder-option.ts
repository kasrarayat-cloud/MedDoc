// ============================================================================
// WORD'S DROPDOWN PLACEHOLDER IS FURNITURE, NOT A CHOICE.
// ----------------------------------------------------------------------------
// Word seeds every dropdown content control with a first `listItem` whose text
// is "Choose an item." It is the empty state the user sees before picking, and
// it is stored in the document exactly like a real option.
//
// ⚠️ MEASURED ON PRODUCTION, 2026-08-24, on the one certified twin:
//   · 80 compiled fields = 52 narrative_text (0 options) + 28 single_select
//   · 28 of 28 single_select carry "Choose an item." at ordinal 0
//   · it appears at NO other ordinal, ever (28 occurrences, all ordinal 0)
//   · excluding it leaves every control with 1..10 real options — none is
//     emptied, so no control becomes unselectable
//
// Until this module the placeholder was offered as a real option, and the
// adversarial pass drove it end to end: `status: supported`,
// `clinicianReviewed: true`, no validator issue, and the literal string
// "Choose an item." rendered INTO an imaging report — on the
// laterality-critical SIDE OF EXAM control, with every needs-review surface
// silent because the manifest counted the field FILLED and REVIEWED.
//
// ⚠️ THE TELL WAS IN THE TEST HELPER. The gate's own `twoDistinctOptions`
// filtered `^choose an item` to pick sensible test data. The test knew it was
// not a clinical value while the product did not. When a helper excludes a
// value to make a test sensible, the production path owes the same exclusion.
// ============================================================================

/**
 * Is this option Word's placeholder rather than a clinical choice?
 *
 * ⚠️ PREFIX MATCH, CASE-INSENSITIVE, AND THE LOOSENESS IS DELIBERATE — the two
 * error directions are not symmetric:
 *
 *   · over-match (drop a real option) -> the doctor cannot select it. VISIBLY
 *     missing, and it fails toward the fence.
 *   · under-match (keep the placeholder) -> "Choose an item." is a settable,
 *     validated, clinician-attested value in a signed clinical document.
 *     SILENTLY WRONG.
 *
 * "An absent field is content the doctor did not see. A WRONG field is content
 * that says the opposite of the record being signed." So this errs toward the
 * edge that has a fence.
 *
 * The trailing period is not required: Word has shipped the string both with
 * and without it across versions, and a locale that renders it differently is
 * simply not matched — which is the safe direction only because the SECOND
 * layer (the override path) refuses placeholders it can still recognise.
 */
export function isWordPlaceholderOption(
  displayText: string | null | undefined,
): boolean {
  if (typeof displayText !== 'string') return false;
  return /^\s*choose an item/i.test(displayText);
}

/**
 * Drop placeholder options while LEAVING EVERY SURVIVING ORDINAL UNCHANGED.
 *
 * ⚠️ THE ORDINALS ARE NOT RENUMBERED, AND THAT IS THE WHOLE POINT OF THIS
 * FUNCTION EXISTING RATHER THAN AN INLINE `.filter()`. Renumbering is the
 * obvious implementation and it is wrong twice over:
 *
 *   1. **A stored ordinal would change what it names.** `selectedOptionOrdinal`
 *      is persisted on fill manifests and on clinician overrides, and an
 *      override row is keyed by (visitId, fieldId) with NO compiled-version
 *      reference — so it outlives a recompile. Shifting the set by one silently
 *      re-points every stored ordinal at its NEIGHBOUR. That resolves
 *      successfully, so the fail-closed `ordinal_not_in_options` decline never
 *      fires: it is the wrong-cell write this arc has already paid for twice.
 *   2. **It would corrupt legacy `w:ddList` renders.** `renderer.ts:692-701`
 *      writes the ordinal into the document as `w:result val`, which Word
 *      resolves as an index into the DOCUMENT's own `listEntry` array — and the
 *      compiler never rewrites that array. A renumbered ordinal would select a
 *      different option in Word than the one the manifest says was chosen.
 *
 * So the compiled set becomes sparse (typically starting at 1). Verified safe:
 * every non-test consumer of `allowedOptions` resolves by
 * `.find(o => o.value === …)` or `.find(o => o.ordinal === …)` — value- or
 * ordinal-keyed, never positional.
 */
export function withoutPlaceholderOptions<
  T extends { ordinal: number; displayText: string },
>(options: readonly T[]): T[] {
  return options.filter((option) => !isWordPlaceholderOption(option.displayText));
}
