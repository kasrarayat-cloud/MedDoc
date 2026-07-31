// ============================================================================
// ROUNDS — Gate B E2E: Screen 4, SIGNED & LOCKED.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md Screen 4. Flag-ON image only.
//
// WHAT ONLY A BROWSER CAN PROVE HERE is that the safety trail is driven by
// PERSISTED FACTS. Every card's presence is asserted against a fixture that
// either did or did not record the thing — so a build that inferred the trail
// from "the visit is signed, therefore its gates were cleared" fails, and it
// fails on the card whose fact is missing rather than on all of them.
//
// ⚠️ THE :rounds IMAGE GAINED NEXT_PUBLIC_UX_SIMPLIFY FOR THIS PACK. The whole
// signed branch of the review view is behind isUxSimplify(); without that build
// arg a signed visit renders the legacy tabbed view and Screen 4 is unreachable,
// so every test here would fail on a missing testid while the product was
// correct. The image had carried the other four flags since Gate A and nothing
// noticed, because until now no pack ever opened a signed visit.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import {
  seedReviewDocVisit,
  findImagingEmArtifacts,
  type ReviewDocClass,
} from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';

test.describe('Rounds Screen 4 — signed & locked', () => {
  test.beforeAll(() => {
    const dirty = findImagingEmArtifacts();
    expect(
      dirty,
      'imaging visits in the QA database carry office-E/M state:\n  ' +
        dirty.join('\n  '),
    ).toEqual([]);
  });

  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  async function openSigned(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      specialtyClass?: ReviewDocClass;
      emPending?: boolean;
      withCriticalOverride?: boolean;
      emAcknowledged?: boolean;
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = seedReviewDocVisit(email, { ...seedOpts, signed: true });
    if (!seeded) return null;
    await page.goto(`/visits/${seeded.visitId}`);
    await expect(page.getByTestId('rounds-signed')).toBeVisible();
    return { ...seeded, email };
  }

  // ── 1. The right image, and the screen exists ────────────────────────────
  test('a signed visit renders Screen 4 on the flag-ON build', async ({ page }) => {
    const seeded = await openSigned(page, 'signed-1');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.locator('html')).toHaveAttribute('data-skin', 'rounds');
    await expect(page.getByTestId('rounds-signed-lock')).toBeVisible();
    // The stage and the gate flow belong to the unsigned branch and must be gone.
    await expect(page.getByTestId('rounds-stage')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-flow')).toHaveCount(0);
  });

  // ── 2. The strip, fully checked ──────────────────────────────────────────
  test('the strip is fully checked, with nothing "now reviewing"', async ({ page }) => {
    const seeded = await openSigned(page, 'signed-2');
    test.skip(!seeded, 'psql seeding unavailable');

    for (let i = 1; i <= 5; i++) {
      await expect(page.getByTestId(`rounds-strip-node-${i}`)).toHaveAttribute(
        'data-stage-state',
        'done',
      );
    }
    await expect(page.getByTestId('rounds-strip-now')).toHaveCount(0);
    await expect(page.getByTestId('rounds-strip-signed')).toHaveAttribute(
      'data-stage-state',
      'done',
    );
    // Zero, not "1 blocker". The attestation gate reports unresolved forever
    // because nothing sets it server-side, so a screen that rendered the gate
    // set would claim an outstanding blocker on a note just signed.
    await expect(page.getByTestId('rounds-strip-signed')).toHaveAttribute(
      'data-blockers',
      '0',
    );
  });

  // ── 3. THE TRAIL IS DRIVEN BY FACTS — the pair that proves it ───────────
  test('NO trail when nothing was recorded', async ({ page }) => {
    // No override row, no acknowledgement. A signed visit with no safety step
    // to log must show none — not an empty frame, not "none recorded".
    const seeded = await openSigned(page, 'signed-3a', { emPending: false });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-trail')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed-trail-rx')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed-trail-em')).toHaveCount(0);
  });

  test('the Rx card appears ONLY when a real override row exists', async ({ page }) => {
    // Same signed visit, one difference: a persisted RxWarningOverride with a
    // reason and a timestamp before the signature. If the trail were inferred
    // rather than read, this test and the one above could not both pass.
    const seeded = await openSigned(page, 'signed-3b', {
      emPending: false,
      withCriticalOverride: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-trail-rx')).toContainText(
      /critical interaction overridden, with a recorded reason/i,
    );
    await expect(page.getByTestId('rounds-signed-trail-em')).toHaveCount(0);
  });

  test('the E/M card appears ONLY when the change was acknowledged', async ({ page }) => {
    const seeded = await openSigned(page, 'signed-3c', { emAcknowledged: true });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-trail-em')).toBeVisible();
    await expect(page.getByTestId('rounds-signed-trail-rx')).toHaveCount(0);
  });

  test('NEVER an attestation card — nothing persists it', async ({ page }) => {
    // Screen 3 tells the doctor the server does not check the attestation.
    // Screen 4 loads after that screen is gone, from data alone, and the value
    // was never transmitted. A tick here would re-assert on every reload
    // something nothing recorded.
    const seeded = await openSigned(page, 'signed-3d', {
      withCriticalOverride: true,
      emAcknowledged: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    // Both other cards ARE present, so this is not passing on an empty trail.
    await expect(page.getByTestId('rounds-signed-trail-rx')).toBeVisible();
    await expect(page.getByTestId('rounds-signed-trail-em')).toBeVisible();
    await expect(page.getByTestId('rounds-signed-trail-attestation')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed')).not.toContainText(/attest/i);
  });

  // ── 4. The lock banner, and the imaging invariant ────────────────────────
  test('the banner names patient, signer and moment; the level only when it applies', async ({
    page,
  }) => {
    const seeded = await openSigned(page, 'signed-4a');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-patient')).toContainText(
      'E2E Review Doc',
    );
    await expect(page.getByTestId('rounds-signed-by')).not.toBeEmpty();
    await expect(page.getByTestId('rounds-signed-at')).toHaveAttribute('dateTime', /.+/);
    await expect(page.getByTestId('rounds-signed-em')).toBeVisible();
  });

  test('an IMAGING signed visit has no documentation level row at all', async ({
    page,
  }) => {
    // Absent, not "n/a", not a blank slot. An imaging report has no office E/M
    // level and the invariant is absolute.
    const seeded = await openSigned(page, 'signed-4b', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-em')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed-lock')).not.toContainText(
      /documentation level/i,
    );
  });

  // ── 5. The paper and the footer ─────────────────────────────────────────
  test('the signed paper is composed, and the addendum rule is a sentence', async ({
    page,
  }) => {
    const seeded = await openSigned(page, 'signed-5');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-paper')).toBeVisible();
    const foot = page.getByTestId('rounds-signed-addendum');
    await expect(foot).toContainText(/corrections require a dated addendum/i);
    // Not a control — there is no addendum route anywhere to lead to.
    await expect(foot.locator('a, button')).toHaveCount(0);
  });

  // ── 6. The deck advance ─────────────────────────────────────────────────
  test('Continue is ABSENT when nothing is left to review', async ({ page }) => {
    // One visit, and it is signed, so the queue is empty. Absent — not a
    // disabled button, and not "all done for today": the queue is a 200-row
    // window and a still-to-review visit outside it looks identical.
    const seeded = await openSigned(page, 'signed-6a');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-deck')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed-continue')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed')).not.toContainText(
      /all done|nothing left|caught up/i,
    );
  });

  test('Continue advances to the next encounter still to review', async ({ page }) => {
    const { email } = await signupFreshUser(page, 'signed-6b');
    // One still to review, and one signed. The signed visit has LEFT the queue,
    // so its own `nextVisitId` is null by construction — the deck advance reads
    // the queue HEAD instead, which is what makes this test meaningful.
    const pending = seedReviewDocVisit(email, { idSalt: 'p' });
    const signed = seedReviewDocVisit(email, { idSalt: 's', signed: true });
    test.skip(!pending || !signed, 'psql seeding unavailable');
    expect(pending!.visitId).not.toBe(signed!.visitId);

    await page.goto(`/visits/${signed!.visitId}`);
    await expect(page.getByTestId('rounds-signed')).toBeVisible();

    await expect(page.getByTestId('rounds-signed-continue')).toBeVisible();
    await page.getByTestId('rounds-signed-continue').click();

    // It lands on the one still to review — and that visit shows the STAGE,
    // which is the proof it is genuinely un-signed rather than just a URL.
    await expect(page).toHaveURL(new RegExp(`/visits/${pending!.visitId}$`));
    await expect(page.getByTestId('rounds-stage')).toBeVisible();
  });
});
