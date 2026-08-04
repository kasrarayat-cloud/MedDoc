// ============================================================================
// Scenario 8 — Open an EXISTING visit from the list.
// ----------------------------------------------------------------------------
// ⚠️ RETIRED IN PART, 2026-08-04, F-ret.1 #18 — DECLARED, NOT QUIETLY DROPPED.
//
// WHAT THIS SPEC USED TO PIN. Three assertions on a tabbed visit-detail
// workspace: that `role=tab` "SOAP Note" was selected by default, and that
// clicking "Codes" and "Extras" flipped `aria-selected` AND swapped the panel
// body — the second half deliberately, so an aria-only pass could not slip a
// panel-render regression through.
//
// WHY IT IS NO LONGER LOAD-BEARING. The tab strip is unreachable under the
// shipped flag set. The arithmetic is written out because "the selector missed"
// and "the surface is gone" look identical from inside a failing test:
//
//   visit-ready-view.tsx:645   if (isSkinBeta())                    TRUE in prod
//                              (docker-compose passes ${…:-true}, and `:-`
//                              substitutes on EMPTY as well as unset — the
//                              .env line is blank, so the default wins)
//   …:848                      if (isReviewDocView() && !isSigned)  → returns
//                              the Rounds stage
//   …:1203                     if (isUxSimplify() && isSigned)      → returns
//                              the signed screen
//   …:1317                     <ReviewTabsV2>   ← the tab strip
//
// Both inner flags are `true` in production. An unsigned visit exits at :848; a
// signed one exits at :1203. Reaching :1317 needs a visit that is NEITHER
// signed nor unsigned, so the strip cannot render. `rg 'role="tab"'` finds two
// definitions in the tree and both sit on that dead arm; `rg 'SOAP Note'` finds
// exactly one, likewise.
//
// It died with the C3 promotion (2026-06-15) and the read-only paper
// (2026-07-28) — NOT with the Rounds flip. This flag-ON run is simply the first
// run that ever looked, which is the entire reason F-ret migrated the pack.
//
// ⚠️ THE SHIPPED BUNDLE STILL CONTAINS THE STRINGS, and that is not evidence
// against any of the above. Dead code is still compiled; grepping the chunks
// for "SOAP Note" returns a hit either way. Reachability is a source argument,
// never a grep.
//
// WHAT REPLACED IT: the read-only paper (`review-document-view.tsx`) for an
// unsigned visit, `RoundsSigned` for a signed one — one document, no tabs.
// Covered by the `rounds-stage`, `rounds-gates` and `rounds-signed` packs.
//
// WHAT SURVIVES HERE, DELIBERATELY: the list → detail navigation. It is the
// only place in the tree proving a `/visits` list anchor resolves to a real
// visit page, and it holds whichever skin renders that page. Retiring the whole
// file would have dropped that along with the tabs — which is why this is a
// partial retire and says so.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('visit detail: the list link opens the visit, and the note renders', async ({
  page,
}) => {
  await signupFreshUser(page, 'v-detail');
  const visitId = await createReadyTextVisit(page, { patientName: 'Detail Patient' });

  // Open the EXISTING visit via the list link — not by navigating to the URL.
  // The claim is that the list's anchor resolves, which is why the click and
  // the URL assertion are both here and neither is redundant.
  await page.goto('/visits');
  await page.locator(`a[href="/visits/${visitId}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/visits/${visitId}$`));

  // The note body renders. Skin-independent on purpose: this asserts the VISIT
  // opened and its content is on the page, not which chrome surrounds it — the
  // Rounds packs own the chrome. `tension headache` is the MOCK_AI fixture's
  // assessment text, so it is a real content assertion rather than a shell one.
  await expect(page.getByText(/tension headache/i)).toBeVisible({ timeout: 15_000 });
});
