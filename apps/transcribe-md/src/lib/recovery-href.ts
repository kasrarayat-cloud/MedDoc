// ============================================================================
// Where a doctor goes when something has gone wrong.
// ----------------------------------------------------------------------------
// COLLAPSED TO A CONSTANT 2026-08-05 (F-ret.3), exactly as this file predicted:
// "At item F this collapses to a constant: the flag is on, the old skin is
// deleted, and `/board` is simply where recovery goes."
//
// ⚠️ WHAT USED TO BE HERE, AND WHY IT IS SAFE TO REMOVE NOW. This chose between
// `/board` and `/dashboard`, and it was a FORK, never a swap — the difference
// being a 404 LOOP. `/board` failed closed with the skin flag off
// (`app/board/page.tsx` ran `notFound()` before `auth()`), so hard-swapping the
// recovery link to it would have sent a flag-OFF doctor from one 404 to another
// with no way out but the back button. That hazard is gone because the
// fail-closed guard is gone with the flag — `/board` now exists unconditionally,
// and `/dashboard` is a forward rather than a home.
//
// The fork and the thing it protected against were removed in the SAME change,
// which is the only safe ordering: deleting the guard first would have left this
// fork pointing at a route that could still 404, and deleting this fork first
// would have built the loop.
//
// ⚠️ THIS PARAGRAPH IS LOAD-BEARING FOR A TEST, not just for readers.
// `gate-c1c-recovery.test.ts`'s negative control asserts that this file mentions
// `/dashboard` in PROSE while the stripped CODE does not — that is how it proves
// its comment-stripper still works before trusting the assertions that depend on
// it. Removing the word from this header silently disarms that control.
//
// ⚠️ STILL DELIBERATELY NOT UNDER `lib/rounds/`. `error-fallback.tsx` and both
// `not-found.tsx` files import this, and a component that outlives a namespace
// must not import from one. Same placement reasoning as `lib/sign-gates.ts`.
//
// The two functions are KEPT rather than inlined at their three call sites: the
// href and its label belong together so they cannot drift. "Back to dashboard"
// pointing at `/board` is the kind of small lie that survives review because
// each half looks right on its own.
// ============================================================================

/** The home surface. One skin, one home. */
export function recoveryHref(): '/board' {
  return '/board';
}

/** The label that goes with it, kept beside the href so the two cannot drift. */
export function recoveryLabel(): string {
  return 'Back to the board';
}
