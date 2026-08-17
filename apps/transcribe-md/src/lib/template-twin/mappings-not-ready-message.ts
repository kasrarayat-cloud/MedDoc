// ============================================================================
// F16 — what a physician is told when certification refuses on unconfirmed
// mappings.
// ----------------------------------------------------------------------------
// This lives OUTSIDE the server action on purpose: `template-twin-certify.ts`
// is a `'use server'` file and may export async functions ONLY, so a pure
// helper cannot live there and be unit-testable. Putting it here is what makes
// the sentence assertable without standing up the whole certify path.
//
// WHY THIS EXISTS AT ALL. Measured on production 2026-08-17: a physician
// uploaded their form at 17:39Z, confirmed 74 of its 80 fields at 18:11:33Z,
// pressed Certify at 18:11:38Z and AGAIN at 18:11:52Z. `MAPPINGS_NOT_READY` —
// a DESIGNED refusal — was falling through to the action's unanticipated-throw
// branch, so both attempts returned:
//
//   "Certification could not be completed (MAPPINGS_NOT_READY). This has been
//    recorded — it will not succeed on a retry until it is fixed."
//
// That frames a state the doctor could clear in a minute as a fault somebody
// else must repair, and names neither how many fields remain nor which. They
// pressed twice and stopped.
//
// ⚠️ TWO CONSTRAINTS, AND BOTH ARE LOAD-BEARING:
//
//   1. THE GATE DOES NOT MOVE BY ONE FIELD. This module decides what is SAID
//      about a refusal that has already happened. `runTemplateTwinSyntheticTest`
//      decides the refusal, and nothing here can reach it. A certified twin
//      that nobody confirmed is worse than no twin.
//
//   2. NO FIELD LABELS, EVER. The template is the customer's own form and its
//      labels are theirs — which is exactly why the action withholds
//      `err.message`. Only COUNTS cross this boundary. The opaque fieldIds
//      stay in the audit row, where they already were.
// ============================================================================

/** Where a doctor goes to clear the refusal. Kept beside the sentence so the
 *  route and the count cannot drift apart into two different edits. */
export const MAPPINGS_NOT_READY_ROUTE_HINT =
  'Open the field list above, confirm the ones still marked as needing review, ' +
  'then certify again.';

/**
 * Build the doctor-facing refusal sentence.
 *
 * ⚠️ DERIVED, NEVER A CONSTANT. A hard-coded "6 of 80" would satisfy a
 * single-case test and be wrong the moment a seventh field appears — which is
 * precisely the shape that makes a half-landed fix invisible.
 *
 * @param remaining how many FIELDS still need confirming (never a count of
 *                  reasons — a field can be both unconfirmed and concept-less,
 *                  and reporting 7 for six fields sends someone hunting a
 *                  seventh that does not exist)
 * @param totalFields how many fields the form has, or null when unknown
 */
export function mappingsNotReadyMessage(
  remaining: number,
  totalFields: number | null,
): string {
  return `Not yet — ${mappingsNotReadyScope(remaining, totalFields)}. ${MAPPINGS_NOT_READY_ROUTE_HINT}`;
}

/** The scope clause alone — "6 of 80 fields still need confirming". */
export function mappingsNotReadyScope(
  remaining: number,
  totalFields: number | null,
): string {
  // Defensive, and deliberately not an exception: this is the error path
  // already. A nonsensical count must degrade to a vaguer TRUE sentence, never
  // to a crash on top of a refusal, and never to a confident wrong number.
  if (!Number.isFinite(remaining) || remaining <= 0) {
    return 'some fields still need confirming';
  }
  const noun = remaining === 1 ? 'field' : 'fields';
  const verb = remaining === 1 ? 'still needs' : 'still need';
  if (
    totalFields === null ||
    !Number.isFinite(totalFields) ||
    totalFields < remaining
  ) {
    // A total smaller than the remainder cannot be true of the same form, so
    // it is dropped rather than printed. "7 of 6" is worse than "7".
    return `${remaining} ${noun} ${verb} confirming`;
  }
  return `${remaining} of ${totalFields} ${noun} ${verb} confirming`;
}
