// ============================================================================
// ROUNDS — Gate B E2E: Screen 2, the stage.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md Screen 2. Runs against the flag-ON image only.
//
// ONE DIFFERENCE FROM THE BOARD PACK, AND IT SETS THE SHAPE OF THIS FILE:
// /board does not exist with the flag off, so `rounds-board.spec.ts` can prove
// it is on the right image by asserting a 404. **`/visits/[id]` exists either
// way.** With the flag off it renders the old skin, perfectly well — so an
// assertion about the patient's name, the paper, or the Sign button passes on a
// flag-OFF build while proving nothing about Rounds at all.
//
// So the first test asserts a Rounds-only surface. Everything after it is
// downstream of that being true.
//
// What is worth a browser rather than a unit test: that the SERVER-computed
// gate set reaches the strip, that the live overlay moves it, that exactly ONE
// note renderer exists on the composed page, and that closing the chat drawer
// scrolls AFTER the overlay is gone. The last one cannot be unit-tested end to
// end and is the exact shape of defect this surface keeps producing — a
// handler that fires and does nothing.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import {
  seedReviewDocVisit,
  findImagingEmArtifacts,
  type ReviewDocClass,
} from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';

const MRN = 'E2E-MRN-4417';
const DOB = '1972-03-14';
const REASON = 'Asthma review';

test.describe('Rounds Screen 2 — the stage', () => {
  test.beforeAll(() => {
    // A DIRTY DATABASE FAILS THE PACK, LOUDLY — the same guard the document
    // pack carries. An imaging visit holding office-E/M state would make the
    // imaging test below assert against the bug instead of the invariant.
    const dirty = findImagingEmArtifacts();
    expect(
      dirty,
      'imaging visits in the QA database carry office-E/M state:\n  ' +
        dirty.join('\n  ') +
        '\nPurge it before trusting this pack.',
    ).toEqual([]);
  });

  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  async function open(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      specialtyClass?: ReviewDocClass;
      emPending?: boolean;
      chiefComplaint?: string;
      patient?: { dob?: string; externalId?: string };
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = seedReviewDocVisit(email, seedOpts);
    if (!seeded) return null;
    await page.goto(`/visits/${seeded.visitId}`);
    await expect(page.getByTestId('rounds-stage')).toBeVisible();
    return { ...seeded, email };
  }

  // ── 1. The image is the right image ──────────────────────────────────────
  test('the stage renders, and it is the flag-ON build', async ({ page }) => {
    // Without this the whole pack could run green against a flag-OFF image,
    // because this route renders either way. `rounds-stage` exists only under
    // the flag; `data-skin` is set on <html> only by isSkinRounds().
    const seeded = await open(page, 'stage-1');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.locator('html')).toHaveAttribute('data-skin', 'rounds');
    await expect(page.getByTestId('rounds-pipeline-strip')).toBeVisible();
  });

  // ── 2. The slot invariant, where it can actually be broken ───────────────
  test('exactly ONE note renderer, and it is inside the sheet', async ({ page }) => {
    // `stage.test.tsx` proves the STAGE adds no note of its own. It cannot see
    // the route, which is where a second renderer would be introduced — and a
    // flag-ON duplicate carrying the imaging E/M suppression while the flag-OFF
    // original lost it would satisfy every source guard in the repo.
    const seeded = await open(page, 'stage-2');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('review-document-view')).toHaveCount(1);
    await expect(page.getByTestId('rounds-sheet')).toContainText(/asthma/i);
    const sheet = page.getByTestId('rounds-sheet');
    await expect(sheet.getByTestId('review-document-view')).toHaveCount(1);
  });

  // ── 3. The strip, and the two-readers-one-number contract ────────────────
  test('the padlock and the rail carry the SAME N', async ({ page }) => {
    const seeded = await open(page, 'stage-3');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-strip-now')).toBeVisible();

    const padlock = page.getByTestId('rounds-strip-signed');
    await expect(padlock).toHaveAttribute('data-stage-state', 'locked');

    // The whole reason `signGates` exists: one derivation, two readers. If a
    // future change recomputes the count in the component, this goes red.
    const n = await padlock.getAttribute('data-blockers');
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      n!,
    );

    // The primary-care fixture: 1 unmet critical Rx + 1 unacknowledged E/M
    // change + attestation. Attestation is ALWAYS counted and is never
    // server-enforced — a clean visit still reads 1. Do not "fix" this number
    // by dropping attestation; it is a real term in the contract with the
    // doctor and sign-gates.ts marks it `serverEnforced: false` for exactly
    // this reconciliation.
    expect(n).toBe('3');
  });

  // ── 4. The number is live, not a frozen server render ────────────────────
  test('clearing the Rx gate moves BOTH counts', async ({ page }) => {
    const seeded = await open(page, 'stage-4');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-critical-band')).toBeVisible();

    const gate = page.getByTestId('review-doc-rx-gate');
    await gate.getByRole('button', { name: /override/i }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog
      .locator('textarea')
      .fill('Benefit outweighs risk; monitoring renal function weekly and patient counselled.');
    await dialog.getByRole('button', { name: /confirm override/i }).click();
    await expect(gate).toContainText(/overridden/i);

    // Both readers move together, and the band goes with them — the band and
    // the padlock disagreeing is the specific contradiction the single
    // derivation exists to prevent.
    await expect(page.getByTestId('rounds-strip-signed')).toHaveAttribute(
      'data-blockers',
      '2',
    );
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      '2',
    );
    await expect(page.getByTestId('rounds-critical-band')).toHaveCount(0);
  });

  // ── 5. The invariant: imaging has no E/M gate, anywhere ──────────────────
  test('an imaging visit has NO E/M gate — absent, not zeroed', async ({ page }) => {
    const seeded = await open(page, 'stage-5', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    // No artifact marker: the fixture is clean, so there is nothing anomalous
    // to name. (The marker exists for an imaging row that WRONGLY carries an
    // unacknowledged E/M change — the server would refuse that sign while the
    // invariant forbids drawing a gate for it.)
    await expect(page.getByTestId('rounds-strip-em-artifact')).toHaveCount(0);

    // The imaging fixture has no medications and no E/M — attestation only.
    // If NEXT_PUBLIC_ULTRASOUND_SPECIALTY were missing from the image, E/M
    // would apply to every specialty and this would read 2, which is why that
    // flag is pinned in gate-flag-coverage.test.ts.
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      '1',
    );
    await expect(page.getByTestId('rounds-critical-band')).toHaveCount(0);
  });

  // ── 6. The identity header, from real columns ────────────────────────────
  test('the identity header reads the visit, and the vitals slot stays EMPTY', async ({
    page,
  }) => {
    const seeded = await open(page, 'stage-6', {
      chiefComplaint: REASON,
      patient: { dob: DOB, externalId: MRN },
    });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-stage-patient')).toContainText(
      'E2E Review Doc',
    );
    await expect(page.getByTestId('rounds-stage-demographics')).toContainText(MRN);
    await expect(page.getByTestId('rounds-stage-reason')).toContainText(REASON);

    // PARKED, NEVER FAKED. L3 has a `measurements` slot but no vitals shape, so
    // the reservation renders and stays empty. A plausible number on a clinical
    // header is the one thing this screen must never invent.
    const vitals = page.getByTestId('rounds-vitals-slot');
    await expect(vitals).toHaveAttribute('data-parked', 'true');
    expect((await vitals.textContent())?.trim()).toBe('');

    // Deliberately NOT asserting the recorded-at timestamp: it is rendered by
    // `formatLocalDateTime`, whose output is timezone-dependent, and the SSR
    // pass runs in the container's zone. Asserting it would be flaky by
    // timezone rather than by product behaviour.
  });

  // ── 7. The queue, and it agrees with the board ───────────────────────────
  test('the peek and the board cannot disagree about what is next', async ({ page }) => {
    const { email } = await signupFreshUser(page, 'stage-7');
    // `idSalt` because the ids are keyed on Date.now() and the insert is
    // `on conflict do nothing` — three seeds inside one millisecond would
    // silently be one visit, and this test would assert "1 of 1" against a
    // fixture it believes is three.
    const seeds = ['a', 'b', 'c'].map((salt) =>
      seedReviewDocVisit(email, { idSalt: salt }),
    );
    test.skip(seeds.some((s) => !s), 'psql seeding unavailable');

    const ids = seeds.map((s) => s!.visitId);
    // Prove the fixture before trusting it — collided ids would make every
    // assertion below vacuously true.
    expect(new Set(ids).size).toBe(3);

    // The board's order is the contract. Read it first, then check the stage
    // agrees — rather than hard-coding an order both could be wrong about.
    await page.goto('/board');
    const boardOrder = await page
      .locator('[data-testid^="rounds-lane-card-"]')
      .evaluateAll((els) =>
        els.map((e) => e.getAttribute('data-testid')!.replace('rounds-lane-card-', '')),
      );
    const readyOrder = boardOrder.filter((id) => ids.includes(id));
    expect(readyOrder).toHaveLength(3);

    // Open the middle one and expect the queue to place it there.
    await page.goto(`/visits/${readyOrder[1]}`);
    await expect(page.getByTestId('rounds-queue-position')).toContainText(
      '2 of 3 to review',
    );
    await expect(page.getByTestId('rounds-peek-prev')).toHaveAttribute(
      'href',
      `/visits/${readyOrder[0]}`,
    );
    await expect(page.getByTestId('rounds-peek-next')).toHaveAttribute(
      'href',
      `/visits/${readyOrder[2]}`,
    );

    // The ends degrade honestly: no previous at the head.
    await page.goto(`/visits/${readyOrder[0]}`);
    await expect(page.getByTestId('rounds-queue-position')).toContainText(
      '1 of 3 to review',
    );
    await expect(page.getByTestId('rounds-peek-prev')).toHaveCount(0);
  });

  // ── 8. The chat drawer ───────────────────────────────────────────────────
  test('the drawer opens, holds the editor, and returns focus', async ({ page }) => {
    const seeded = await open(page, 'stage-8');
    test.skip(!seeded, 'psql seeding unavailable');

    const trigger = page.getByTestId('rounds-chat-trigger');
    await expect(trigger).toBeVisible();
    await trigger.click();

    const drawer = page.getByTestId('rounds-chat-drawer');
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveAttribute('aria-modal', 'true');
    await expect(drawer.getByTestId('chat-editor')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(drawer).toHaveCount(0);
    // Focus must come back to where it left, or a keyboard user is stranded.
    await expect(trigger).toBeFocused();

    // The 'E' shortcut is the rail's advertised way in.
    await page.keyboard.press('e');
    await expect(page.getByTestId('rounds-chat-drawer')).toBeVisible();
  });

  // ── 9. Close, THEN scroll — both halves ──────────────────────────────────
  test('a chat navigation lands AFTER the drawer is gone', async ({ page }) => {
    // THE FAILURE THIS EXISTS FOR: the handler fires, the scroll runs while the
    // overlay is still mounted, the chat says "took you to the E/M gate", and
    // nothing the doctor can see has moved. Asserting only that the drawer
    // closed, or only that the handler ran, passes on exactly that bug — so
    // both halves are asserted, in order.
    const seeded = await open(page, 'stage-9');
    test.skip(!seeded, 'psql seeding unavailable');

    await page.getByTestId('rounds-chat-trigger').click();
    const drawer = page.getByTestId('rounds-chat-drawer');
    await expect(drawer).toBeVisible();

    // MOCKSCROLL is a mock-only directive; the real model path burns tokens and
    // lives in an .eval.spec.ts.
    await drawer.getByRole('textbox').fill('MOCKSCROLL em_gate');
    await drawer.getByRole('textbox').press('Enter');
    await expect(drawer).toContainText(/took you to the em gate/i);

    const gate = page.locator('[data-chat-target="em_gate"]');
    // HALF ONE: still open, and therefore NOT yet scrolled to.
    await expect(drawer).toBeVisible();
    await expect(gate).not.toBeInViewport();

    await page.getByTestId('rounds-chat-close').click();

    // HALF TWO: the overlay is gone AND the target is on screen.
    await expect(page.getByTestId('rounds-chat-drawer')).toHaveCount(0);
    await expect(gate).toBeInViewport();
  });

  // ── 10. One control can start a signature ────────────────────────────────
  test('the rail NAVIGATES; the sign bar is the only thing that signs', async ({
    page,
  }) => {
    const seeded = await open(page, 'stage-10');
    test.skip(!seeded, 'psql seeding unavailable');

    await page.getByTestId('rounds-review-sign').click();

    // It took the doctor to the first blocking gate. It did NOT open a signing
    // modal — two controls that can both start a signature is two places for
    // the gate logic to drift apart.
    await expect(page.getByTestId('review-doc-rx-gate')).toBeInViewport();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(1);
  });
});
