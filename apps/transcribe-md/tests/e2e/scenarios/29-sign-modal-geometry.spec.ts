// ============================================================================
// The sign modal's footer is REACHABLE — measured, not assumed.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A REQUIRED CONTROL WENT OFF-SCREEN AND NOTHING SAID SO.
//
// `POST /sign` gained a required attestation (2026-08-02). The modal collects it
// on every path where nothing upstream has, and the block was added above the
// action row — which was the one place it could not go. The dialog had NO height
// bound and its body a fixed `max-h-[60vh]`, so total height was
// `12vh + header + 60vh + gates + action row`. That already overflowed 720px;
// one more required block pushed "Sign & Deliver" fully below the fold.
//
// Three signing specs failed, and NONE of them said "the button is off-screen".
// They said "waiting for event download" and "expected dialog to be hidden" —
// symptoms one whole interaction downstream of the cause. A geometry assertion
// is the cheapest thing that would have named it immediately.
//
// So: the attestation and the submit are one control region, pinned, and this
// asserts they are both inside the viewport at the size the default pack runs.
// ============================================================================

import { test, expect } from '@playwright/test';

import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

/** The default pack runs `devices['Desktop Chrome']` — 1280×720. 720 is the
 *  number that matters: the overflow was vertical. */
const VIEWPORTS = [
  { name: 'desktop-chrome-720', width: 1280, height: 720 },
  // The shortest viewport any pack uses. If the footer survives here it
  // survives everywhere the suite looks.
  { name: 'short-640', width: 1280, height: 640 },
];

test.describe('the sign modal keeps its signature controls on screen', () => {
  for (const vp of VIEWPORTS) {
    test(`attestation + submit are both inside the viewport @${vp.name}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await signupFreshUser(page, `signgeo-${vp.height}`);
      const visitId = await createReadyTextVisit(page, {
        patientName: 'Sign Geometry',
      });
      await page.goto(`/visits/${visitId}`);

      await page
        .getByRole('button', { name: /sign (&|and) (download|deliver|send)/i })
        .first()
        .click();

      const submit = page
        .getByRole('button', { name: /sign & deliver/i })
        .first();
      await expect(submit).toBeVisible();

      // NON-VACUITY: if the attestation block never rendered, the geometry
      // assertion below would be about a control that is not the one at risk.
      const attestation = page.getByTestId('sign-attestation');
      await expect(
        attestation,
        'no attestation block — this build collects it upstream, so this test ' +
          'is not measuring the case that broke',
      ).toHaveCount(1);

      const vh = vp.height;
      for (const [label, loc] of [
        ['attestation', attestation],
        ['sign submit', submit],
      ] as const) {
        const box = await loc.boundingBox();
        expect(box, `${label} has no box — it is not laid out at all`).not.toBeNull();
        expect(
          box!.y,
          `${label} starts at y=${box!.y} on a ${vh}px viewport — above the fold`,
        ).toBeGreaterThanOrEqual(0);
        expect(
          box!.y + box!.height,
          `${label} ends at y=${Math.round(box!.y + box!.height)} on a ${vh}px ` +
            'viewport — BELOW THE FOLD, so the doctor cannot reach it without ' +
            'scrolling a region that does not scroll',
        ).toBeLessThanOrEqual(vh);
      }

      // And the coupling the ruling asks for: the submit refuses until the
      // attestation beside it is checked.
      await expect(submit).toBeDisabled();
      await page.getByTestId('sign-attestation-toggle').click();
      await expect(submit).toBeEnabled();
    });
  }
});
