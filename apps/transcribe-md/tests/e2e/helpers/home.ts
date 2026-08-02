// ============================================================================
// "Where does an authenticated doctor land?" — one answer, for every pack.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE TEST-CALLER HALF OF R1'S TRAVERSAL, AND IT BROKE THE PACKS.
//
// `signupFreshUser` and `login` both asserted `toHaveURL(/\/dashboard$/)`. Under
// Rounds, `/dashboard` now forwards to `/board` — so the moment R1 landed,
// every flag-ON pack failed inside a HELPER, before its own first assertion,
// with "unexpected value http://localhost:9020/board". A dozen specs reporting
// a signup failure, for a signup that worked perfectly.
//
// The product's answer is `recoveryHref()` — `/board` under Rounds, `/dashboard`
// otherwise — and it is a BUILD-TIME fork, so a single test process can face
// either one depending on which image the pack was recreated onto. The helpers
// therefore cannot name one; they have to accept the app's own answer.
//
// Deliberately a REGEX OVER BOTH rather than reading the flag in the test
// process: `NEXT_PUBLIC_SKIN_ROUNDS` is inlined into the app's bundle at
// docker-build time and is NOT set in the Playwright runner's environment, so a
// test-side `isSkinRounds()` would read `undefined` and confidently assert the
// wrong destination on the flag-ON image — a check that fails for a reason that
// has nothing to do with the product. Same class as `/board` failing closed.
// ============================================================================

import { expect, type Page } from '@playwright/test';

/** `/board` (Rounds) or `/dashboard` (legacy). Anchored, so `/dashboards` and
 *  `/board-something` do not match — the substring trap this project has
 *  shipped three times ('dashboard' contains 'board'). */
export const HOME_URL_RE = /\/(board|dashboard)(\?.*)?$/;

/** Assert the page has landed on the app's home for whichever skin is built. */
export async function expectAtHome(page: Page, timeout = 15_000): Promise<void> {
  await expect(
    page,
    'not on the app home. Under Rounds that is /board; otherwise /dashboard. ' +
      'A /login here means auto-login failed (T-M9); anything else means a ' +
      'redirect changed and this helper was not told',
  ).toHaveURL(HOME_URL_RE, { timeout });
}
