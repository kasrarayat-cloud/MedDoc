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

  /**
   * ⚠️ IN CI, A SEEDER THAT CANNOT SEED IS A DEFECT, NOT A SKIP.
   *
   * Every test here ends `test.skip(!seeded, …)`, which is right locally — the
   * psql channel genuinely may not exist. But **Playwright exits 0 on a fully
   * skipped file.** When this pack's seeding broke on a misaligned column, all
   * 11 tests skipped and the run went GREEN having proved nothing. That is A2
   * defect 0's shape exactly: a gate reporting success for work that never ran.
   *
   * A probe of the psql CHANNEL does not catch it — I wrote that first and
   * watched it pass while the pack skipped. The channel was fine; the INSERT was
   * rejected. The question has to be "did this seed succeed", not "could I reach
   * the database".
   *
   * In CI the channel is guaranteed, so a null here means the seeder is broken.
   */
  function requireSeed<T>(seeded: T | null, what: string): T | null {
    if (seeded) return seeded;
    if (process.env.CI) {
      throw new Error(
        `seeding FAILED for ${what}. In CI this is a defect, not a skip — ` +
          'letting it skip would exit 0 on a pack that proved nothing.',
      );
    }
    return null;
  }

  async function openSigned(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      specialtyClass?: ReviewDocClass;
      emPending?: boolean;
      withCriticalOverride?: boolean;
      emAcknowledged?: boolean;
      /** Seed the ANOMALY: an imaging visit carrying office E/M state. Without
       *  it every imaging fixture hard-nulls `emPendingChange`, and an absence
       *  assertion over the trail passes against a build with the suppression
       *  deleted. */
      imagingEmPending?: boolean;
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = requireSeed(
      seedReviewDocVisit(email, { ...seedOpts, signed: true }),
      tag,
    );
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

  // ── 1b. ARCHIVE IS REACHABLE ─────────────────────────────────────────────
  // ⚠️ THIS EXISTS BECAUSE IT WAS NOT, IN PRODUCTION, ON EVERY SIGNED NOTE,
  // FOR A DAY. R2 moved the lifecycle overflow into `RoundsStage` — which the
  // test above asserts is ABSENT on this screen — and `RoundsSigned` had no
  // slot for it, so `ArchiveButton` never reached the DOM. Production carried
  // 16 signed visits and 0 archived ones, and HIPAA retention forbids deleting
  // a signed note, so archiving is the only disposal a doctor has.
  //
  // The unit gate (`gate-rounds-visit-overflow`) reads SOURCE and asserts the
  // mount count. It cannot see whether the control actually renders, opens, or
  // carries a usable button. That is this test.
  test('ARCHIVE is reachable — the lifecycle overflow is on the signed screen', async ({
    page,
  }) => {
    const seeded = await openSigned(page, 'signed-archive');
    test.skip(!seeded, 'psql seeding unavailable');

    // Non-vacuity: we are on Screen 4, not on some other page that happens to
    // lack the control for an unrelated reason.
    await expect(page.getByTestId('rounds-signed-lock')).toBeVisible();

    const overflow = page.getByTestId('rounds-visit-overflow');
    await expect(
      overflow,
      'no Visit-actions disclosure on the signed screen — Archive is unreachable, ' +
        'which is exactly the regression this test was written for',
    ).toBeVisible();

    // Collapsed by default: a destructive control costs a deliberate click.
    await expect(overflow).not.toHaveAttribute('open', /.*/);

    // And it must actually CONTAIN the archive control, not merely exist. An
    // empty <details> is a control that appears to be there.
    await overflow.getByRole('group').or(overflow).click();
    await expect(
      page.getByRole('button', { name: 'Archive', exact: true }),
      'the disclosure opens but carries no Archive button',
    ).toBeVisible();
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

  test('the Rx card NEVER appears — even with a real override row (ruling #109)', async ({
    page,
  }) => {
    // ⚠️ THE INVERSE OF THE TEST IT REPLACES, AND DELIBERATELY THE STRONGEST
    // FORM. The old test proved the card rendered only from a persisted
    // `RxWarningOverride` row. Owner ruling #109 deleted the card, so this
    // seeds that row ANYWAY — the one input that used to make it appear — and
    // requires the card to stay absent. Asserting the absence on a visit with
    // no override row would prove nothing: it would hold on any signed visit.
    //
    // Production has 0 override rows across all 25 signed visits, so this state
    // exists nowhere but here; the seeder is the only way to ask the question.
    const seeded = await openSigned(page, 'signed-3b', {
      emPending: false,
      withCriticalOverride: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-signed-trail-rx')).toHaveCount(0);
    await expect(page.getByTestId('rounds-signed')).not.toContainText(/interaction/i);
    // …and with nothing else to show, the trail itself does not stand.
    await expect(page.getByTestId('rounds-signed-trail')).toHaveCount(0);
    // POSITIVE CONTROL — the signed screen rendered at all.
    await expect(page.getByTestId('rounds-signed')).toBeVisible();
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

    // The E/M card IS present, so this is not passing on an empty trail.
    // (The Rx card was the other half of this control until ruling #109.)
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

  test('THE COMPANION — an imaging visit carrying office E/M gets NO trail card', async ({
    page,
  }) => {
    // ⚠️ THE TEST ABOVE PROVES NOTHING ON ITS OWN, and neither did anything
    // else on this screen. `page.tsx` suppresses the trail's E/M card with
    // `emNotApplicable ? null : …`, and that guard had no fixture behind it:
    // every imaging seed hard-nulls `emPendingChange`, so the guarded and the
    // unguarded expression both evaluate to null and the ternary could be
    // deleted with the whole suite still green. The test above also scopes its
    // prose check to `rounds-signed-lock`, and the trail is a SIBLING of that
    // section — so the card's own text was outside it either way.
    //
    // The state is reachable in production: `POST /sign` is not
    // specialty-conditioned, so a signed imaging visit really can carry an
    // acknowledged office E/M change. Five imaging visits acquired office E/M
    // state in prod and sat two days before anyone noticed. On this screen that
    // would print "Documentation level change confirmed" on a signed ultrasound
    // report — a safety trail asserting a step that does not apply, on the one
    // surface whose entire job is to be true.
    const seeded = await openSigned(page, 'signed-4c', {
      specialtyClass: 'imaging',
      imagingEmPending: true,
      emAcknowledged: true,
      withCriticalOverride: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    // ⚠️ THE NON-VACUITY CONTROL MOVED, AND SAYING SO IS THE POINT. It used to
    // be the Rx card: seeded from its own persisted row, it kept the trail
    // standing so the E/M card's absence read as a decision rather than an
    // empty screen. Ruling #109 deleted that card, and with it the only other
    // thing this trail can hold — so on imaging the trail is now empty, and
    // "no E/M card" would be true of any blank screen.
    //
    // The control is therefore a COMPANION VISIT rather than a companion card:
    // same seed, same acknowledged E/M change, specialty the ONLY difference.
    // If the card fails to render there too, the absence here means nothing.
    await expect(page.getByTestId('rounds-signed-trail-em')).toHaveCount(0);
    // Scoped over the WHOLE screen, not one section — the card's text lives
    // outside the lock banner.
    await expect(page.getByTestId('rounds-signed')).not.toContainText(
      /documentation level/i,
    );
    await expect(page.getByTestId('rounds-signed-em')).toHaveCount(0);

    // THE COMPANION, IN THE SAME TEST so it cannot be skipped independently of
    // the claim it supports: identical seed, PRIMARY-CARE instead of imaging.
    // The card must render there. If it does not, the absence above is a fact
    // about a broken card rather than about the specialty.
    const control = await openSigned(page, 'signed-4c-ctl', {
      emPending: true,
      emAcknowledged: true,
    });
    test.skip(!control, 'psql seeding unavailable');
    await expect(
      page.getByTestId('rounds-signed-trail-em'),
      'the E/M card did not render on a NON-imaging visit with the same seed — ' +
        'the imaging absence above proves nothing',
    ).toBeVisible();
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
    const pending = requireSeed(seedReviewDocVisit(email, { idSalt: 'p' }), 'pending');
    const signed = requireSeed(
      seedReviewDocVisit(email, { idSalt: 's', signed: true }),
      'signed',
    );
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
