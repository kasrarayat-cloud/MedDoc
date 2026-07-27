// ============================================================================
// The pre-sign document surface — the flows that now carry sign-path weight.
// ----------------------------------------------------------------------------
// Flag NEXT_PUBLIC_REVIEW_DOC_VIEW. Every control here decides whether a note
// gets signed, and three of them shipped broken in ways that were invisible on
// screen:
//
//   • the read-gate observer was built in useEffect and never observed anything
//   • intersectionRatio can't express "fully read" — a card 5% taller than the
//     viewport tops out at 0.75 and the gate never unlocks
//   • the "seen" set was keyed by index, so accepting one claim silently
//     un-read the rest
//
// All three FAILED CLOSED, which is exactly why they survived review: a gate
// that hasn't unlocked and a gate that can't unlock render identically. Only
// driving them in a browser tells them apart, so that is what this does.
// ============================================================================

import { test, expect } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';

const SUGG = '[data-testid="review-doc-suggestion"]';
const ACCEPT = '[data-testid="review-doc-accept"]';
const BULK = '[data-testid="review-doc-accept-remaining"]';
const BAR = '[data-testid="review-doc-bar-msg"]';

test.describe('pre-sign review as the document', () => {
  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  /** Fresh user + a purpose-built visit per test — the suite's own pattern, and
   *  it keeps each flow independent of what the previous one adopted or signed.
   *  Returns null when the psql channel is unavailable so the test skips for an
   *  environment reason rather than failing. */
  async function open(page: import('@playwright/test').Page, tag: string) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = seedReviewDocVisit(email);
    if (!seeded) return null;
    await page.goto(`/visits/${seeded.visitId}`);
    await expect(page.getByTestId('review-document-view')).toBeVisible();
    // The view mounting is NOT the review being ready. Suggestions are anchored
    // into the document and rendered by its per-page callback, so they exist
    // only once it has drawn — measured at ~900ms, and asserting before that
    // reads as "no suggestions" rather than "not yet". Waiting on the drawn
    // document is the real signal; a sleep here would only hide the race.
    await expect(page.getByText('Opening your document…')).toHaveCount(0);
    return seeded;
  }

  async function scrollThroughSuggestions(page: import('@playwright/test').Page) {
    const cards = page.locator(SUGG);
    for (let i = 0; i < (await cards.count()); i++) {
      await cards.nth(i).scrollIntoViewIfNeeded();
      await page.waitForTimeout(250);
    }
  }

  async function clearRxGate(page: import('@playwright/test').Page) {
    const gate = page.getByTestId('review-doc-rx-gate');
    await gate.getByRole('button', { name: /override/i }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog
      .locator('textarea')
      .fill('Benefit outweighs risk; monitoring renal function weekly and patient counselled.');
    await dialog.getByRole('button', { name: /confirm override/i }).click();
    await expect(gate).toContainText(/overridden/i);
  }

  test('renders the document, not the tab strip', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-1')), 'psql seeding unavailable');
    await expect(page.locator('.qm-c3-rev2-tabs')).toHaveCount(0);
    await expect(page.locator(SUGG)).toHaveCount(3);
  });

  test('each suggestion sits under the section it would join', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-2')), 'psql seeding unavailable');
    // Placement, not presence: a claim rendered in the wrong section is a claim
    // the doctor reviews in one place and signs in another. The document view
    // anchors each section's suggestions under that section's page slot, so the
    // assertion is now against the slot's own label rather than the old
    // card-wall's section container.
    for (const label of ['Subjective', 'Objective', 'Plan']) {
      await expect(page.locator(`[data-section="${label}"] ${SUGG}`)).toHaveCount(1);
    }
  });

  test('the read-gate stays locked until every suggestion has been on screen', async ({ page }) => {
    // A phone viewport, deliberately: at desktop height all three cards can be
    // on screen at once, in which case the gate SHOULD unlock immediately and
    // there is no lock to test. The invariant is "not until they have been
    // seen", not "not until you have scrolled".
    await page.setViewportSize({ width: 390, height: 700 });
    test.skip(!(await open(page, 'rdoc-3')), 'psql seeding unavailable');
    // The invariant is the BUTTON, not the bar copy: a blocking drug warning
    // outranks "you have suggestions to read", and rightly so — asserting on
    // bar text here would be testing the message priority, not the read-gate.
    await expect(page.locator(BULK)).toHaveCount(0);
    await scrollThroughSuggestions(page);
    await expect(page.locator(BULK)).toBeVisible();
  });

  test('a card TALLER than the viewport still unlocks the gate', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-4')), 'psql seeding unavailable');
    // The regression that shipped: intersectionRatio can never reach 1 for a
    // card taller than the root, so the gate stayed locked forever with nothing
    // to report. The seeded third claim is long; force the case explicitly so
    // the test does not depend on how the text happens to wrap.
    await page.addStyleTag({
      content: `${SUGG} { min-height: 105vh; }`,
    });
    const cards = page.locator(SUGG);
    for (let i = 0; i < (await cards.count()); i++) {
      await cards.nth(i).locator('.qm-rdoc-sugg-end').scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
    }
    await expect(page.locator(BULK)).toBeVisible();
  });

  test('accepting one suggestion moves it into the note and keeps the gate open', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-5')), 'psql seeding unavailable');
    await scrollThroughSuggestions(page);
    await expect(page.locator(BULK)).toBeVisible();

    await page.locator(ACCEPT).first().click();
    await expect(page.locator(SUGG)).toHaveCount(2);
    // The accepted text is now note body, not a card. The document draws to a
    // canvas, so the DOM copy of the note is the reading-order block the screen
    // reader uses — which is the honest place to assert it landed, and doubles
    // as a check that the block a blind doctor reads was refreshed too.
    await expect(page.getByTestId('visit-document-text')).toContainText('nocturnal cough');
    await expect(page.locator(SUGG).filter({ hasText: 'nocturnal cough' })).toHaveCount(0);
    // And the bar does NOT fall back to "scroll to review" — the index-keyed
    // "seen" set used to un-read every surviving claim here.
    await expect(page.locator(BULK)).toBeVisible();
  });

  test('accept-remaining clears them all, one adoption at a time', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-6')), 'psql seeding unavailable');
    await scrollThroughSuggestions(page);
    await page.locator(BULK).click();
    await expect(page.locator(SUGG)).toHaveCount(0, { timeout: 30_000 });
    // The bar now reports the REMAINING blocker — this visit still has an
    // un-overridden critical interaction, and a surface that said "Reviewed"
    // with a drug warning outstanding would be lying. Clearing it yields
    // "Reviewed" only once nothing is left.
    await expect(page.locator(BAR)).toContainText('prescription');
    await clearRxGate(page);
    await page.getByTestId('review-doc-em-confirm').click();
    await expect(page.locator(BAR)).toContainText('Reviewed');
  });

  test('the critical-Rx card blocks signing until a typed override is recorded', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-7')), 'psql seeding unavailable');
    const gate = page.getByTestId('review-doc-rx-gate');
    await expect(gate).toBeVisible();
    await expect(page.locator(BAR)).toContainText('prescription');
    const sign = page.getByRole('button', { name: /sign & download/i });
    await expect(sign).toBeDisabled();

    await clearRxGate(page);
    // Sign stays disabled — the E/M level is ALSO pending. The bar names the
    // next blocker rather than pretending the note is ready.
    await expect(page.locator(BAR)).toContainText('documentation level');
    await expect(sign).toBeDisabled();
  });

  test('the E/M card blocks signing until the level is confirmed', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-8')), 'psql seeding unavailable');
    // Clear the Rx blocker first so E/M is the only thing left holding the bar.
    await clearRxGate(page);

    const em = page.getByTestId('review-doc-em-gate');
    await expect(em).toBeVisible();
    await expect(em).toContainText('99214');
    await expect(page.locator(BAR)).toContainText('documentation level');
    await expect(page.getByRole('button', { name: /sign & download/i })).toBeDisabled();

    await page.getByTestId('review-doc-em-confirm').click();
    await expect(page.getByTestId('review-doc-em-confirm')).toContainText(/confirmed/i);
    await expect(page.getByRole('button', { name: /sign & download/i })).toBeEnabled();
  });

  test('the codes row expands to the real billing panel — a level stays changeable', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-9')), 'psql seeding unavailable');
    // Collapsing a surface is not removing it. Override / rescore / dispute
    // must be reachable here, or a doctor who disagrees with a level would need
    // the flag toggled under them.
    await page.getByTestId('review-doc-codes-toggle').click();
    const panel = page.locator('.qm-rdoc-meta-panels');
    await expect(panel).toBeVisible();
    await expect(panel.locator('.qm-c3-bill-card')).toBeVisible();
    await expect(panel.getByText(/why this level/i)).toBeVisible();
    await expect(panel.locator('select, [role="combobox"]').first()).toBeVisible();
  });

  test('sign delivers the file', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-10')), 'psql seeding unavailable');
    // Clear both gates, then sign with DOCX selected and assert the download
    // actually starts — "signed" without a file is the failure this surface
    // exists to make impossible.
    await clearRxGate(page);
    await page.getByTestId('review-doc-em-confirm').click();

    await page.getByRole('button', { name: /sign & download/i }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: /download docx/i }).click();
    // The modal keeps its OWN E/M confirmation, and it remains the enforcement:
    // the inline card is an additional visible blocker in front of it, never a
    // replacement. Two acknowledgements for a billing-level change is the
    // deliberate design, so the test acknowledges twice too.
    const modalEm = dialog.getByTestId('em-change-confirm-toggle');
    if (await modalEm.count()) await modalEm.click();

    // dispatchEvent, not click(): submitting triggers a download, and the
    // actionability check never settles behind one even though the button
    // reports visible/enabled/stable. The real handler still runs — this
    // bypasses Playwright's wait, not the application.
    const download = page.waitForEvent('download', { timeout: 60_000 });
    await dialog.getByRole('button', { name: /sign & deliver/i }).dispatchEvent('click');
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/\.(docx|pdf)$/);
  });
});
