// ============================================================================
// THE MISS VOCABULARY — a LEAF module, and that is the point.
// ----------------------------------------------------------------------------
// ⚠️ IT LIVES HERE RATHER THAN IN THE ACTION BECAUSE THE ACTION CANNOT BE
// IMPORTED BY A TEST. `preview-visit-document.ts` pulls in next-auth, so any
// gate importing it dies at `Cannot find module 'next/server'` — which is
// exactly why `gate-actionable-miss-is-spoken` PARSED THE SOURCE instead, and
// why it had to keep a hand-written copy of the member list that then went
// stale. A leaf with no server imports lets the gate ITERATE the shipped list.
// ============================================================================
/**
 * ⚠️ A RUNTIME LIST, AND THE TYPE IS DERIVED FROM IT — NOT THE OTHER WAY ROUND.
 *
 * This was a hand-written union, so the ONE gate that checks every actionable
 * miss is spoken (`gate-actionable-miss-is-spoken`) had to keep its own
 * hand-written copy of the members. Adding `no_tenant_template` (#287) was
 * therefore invisible to it — 8 of 8 green — and the new miss rendered NOTHING
 * to the doctor, deleting an explanation `main` had given.
 *
 * A list a test can ITERATE cannot go stale the way a list a test RESTATES can.
 * This is #289's rule one directory over: derived, never enumerated.
 */
export const VISIT_PREVIEW_MISSES = [
  /** Neither a certified twin NOR a styled document could be produced. */
  'not_template_visit',
  /** Template uploaded and compiled, but never certified. */
  'not_certified',
  /** The fill ran and produced no document (nothing renderable yet). */
  'no_render',
  /** The fill itself failed. Named, so it is never a blank screen. */
  'fill_failed',
  /**
   * ⚠️ RULING #287 — THE TENANT PRACTICE HAS NO ACTIVE CERTIFIED TEMPLATE.
   *
   * A visit is documented in the TENANT's format, so a locum from B seeing A's
   * patient fills A's template. When A has none, the honest outcome is "this
   * practice has no form yet" — the styled note with a NAMED reason — and NOT a
   * provenance error. The old shape reported `TEMPLATE_PROVENANCE_MISMATCH` for
   * a state that is entirely ordinary, which reads to a reader as corruption.
   */
  'no_tenant_template',
] as const;

export type VisitPreviewMiss = (typeof VISIT_PREVIEW_MISSES)[number];
