// ============================================================================
// Where a doctor goes when something has gone wrong.
// ----------------------------------------------------------------------------
// Every recovery affordance in the product — the error boundary's "Back to
// dashboard", the root 404's primary button, the visit 404's link — sends the
// doctor to `/dashboard`. Under Rounds the home surface is `/board`, and
// `/dashboard` is not in the Rounds nav (`board-chrome.tsx` links `/board`).
//
// ⚠️ THIS IS A FORK, NEVER A SWAP, AND THE DIFFERENCE IS A 404 LOOP.
// `/board` FAILS CLOSED with the flag off — `app/board/page.tsx:76` runs
// `if (!isSkinRounds()) notFound();` BEFORE `auth()`, so with the flag off the
// route does not exist. Hard-swapping the recovery link would send a flag-OFF
// doctor from a 404 to a 404, with no way out but the browser's back button.
// The flag is OFF in production until item F, so that is not a hypothetical —
// it is what would ship.
//
// ⚠️ DELIBERATELY NOT UNDER `lib/rounds/`. Item F deletes the skin's
// namespace, and `error-fallback.tsx` and both `not-found.tsx` files SURVIVE
// item F — a component that outlives the skin must not import from a directory
// scheduled for deletion. Same placement reasoning as `lib/sign-gates.ts` and
// `lib/patient-display.ts`.
//
// At item F this collapses to a constant: the flag is on, the old skin is
// deleted, and `/board` is simply where recovery goes.
// ============================================================================

import { isSkinRounds } from '@/config/skin-rounds';

/** The home surface for the skin that is actually built. */
export function recoveryHref(): '/board' | '/dashboard' {
  return isSkinRounds() ? '/board' : '/dashboard';
}

/** The label that goes with it. Kept beside the href so the two cannot drift —
 *  "Back to dashboard" pointing at `/board` is the kind of small lie that
 *  survives review because each half looks right on its own. */
export function recoveryLabel(): string {
  return isSkinRounds() ? 'Back to the board' : 'Back to dashboard';
}
