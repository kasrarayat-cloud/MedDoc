// ============================================================================
// Reaching the Rx safety gate on the SHIPPED surface.
// ----------------------------------------------------------------------------
// ⚠️ THERE IS NO Rx TAB, AND ITS ABSENCE IS THE FEATURE.
//
// Scenarios 24 and 25 each opened the rail with:
//
//     const rxTab = page.getByRole('tab', { name: 'Rx' });
//     await rxTab.click();
//     await expect(rxTab).toHaveAttribute('aria-selected', 'true');
//
// That drove `ReviewTabsV2`, which is unreachable under the shipped flag set —
// the same dead arm `8-visit-detail-tabs.spec.ts` documents:
//
//   visit-ready-view.tsx:645   if (isSkinBeta())                   TRUE in prod
//   …:848                      if (isReviewDocView() && !isSigned) → Rounds stage
//   …:1203                     if (isUxSimplify() && isSigned)     → signed screen
//   …:1317                     <ReviewTabsV2>   ← the tab strip, never reached
//
// `rg 'role="tab"'` finds exactly two definitions in the tree
// (`visit-ready-view.tsx:1766`, `review-tabs-v2.tsx:182`) and BOTH sit on that
// arm.
//
// WHY THESE PACKS ONLY NOTICED ON 2026-08-04. `rx-safety` and `phi-reject` run
// on the fixture image built by e2e.yml's "Build app + worker images" step.
// That step built FLAG-OFF until F-ret.1 gave it the production flag set, so
// these specs had been driving a surface no doctor could see. Nothing about the
// product changed on the day they went red; the harness simply started looking
// at the shipped one. Same class as the 19 default-pack failures, same day.
//
// WHAT REPLACED IT. The gate is rendered INLINE and unconditionally on the
// read-only paper (`review-document-view.tsx:271-279`), whose own comment is
// the point: "a blocker can no longer hide behind a tab nobody opened." So the
// re-point is not a weakening — the property being relied on got STRONGER. The
// old helper proved a tab could be opened; this one proves the gate is present
// without anyone opening anything.
//
// MEASURED, NOT ASSUMED. From the real DOM captured in the failing run's trace
// (run 30930087551) — not from the a11y snapshot, which cannot show testids:
//
//     review-doc-rx-gate     2      qm-warn-override-btn   7
//     data-gate-slot         4      qm-warn-critical      14
//     role="tab"             0      "Prescription safety"  3   ← positive control
//
// The zero is only meaningful because the positive control is not zero.
//
// ⚠️ ONE HELPER, NOT ONE PER SPEC. Both specs had their own copy of the tab
// dance and both broke identically. A per-caller list is kept complete by hand,
// and hand-kept lists are wrong eventually (R3.4). The behaviour lives here so
// a third Rx spec inherits it instead of re-deriving it.
// ============================================================================

import { expect, type Page } from '@playwright/test';

/** The gate's own testid on the read-only paper. Document-wide by design: the
 *  Rounds gate flow may PORTAL the node out of its `data-gate-slot` wrapper
 *  (`review-document-view.tsx` `gatePortalTarget`), so anchoring on the slot
 *  would find an empty box on the very surface this is meant to cover. */
const RX_GATE = 'review-doc-rx-gate';

/**
 * Navigate to a visit and wait for the Rx safety gate to be on the page.
 *
 * No click: the gate is inline on the shipped surface. If it is ever hidden
 * behind a disclosure again, this fails — which is the correct outcome, because
 * a critical interaction warning behind a closed panel is the exact defect the
 * inline rendering was introduced to remove.
 */
export async function openRxGate(page: Page, visitId: string): Promise<void> {
  await page.goto(`/visits/${visitId}`);
  await expect(
    page.getByTestId(RX_GATE),
    'the Rx safety gate is not on the visit page — a critical interaction ' +
      'warning would be invisible to the doctor before signing',
  ).toBeVisible({ timeout: 30_000 });
}
