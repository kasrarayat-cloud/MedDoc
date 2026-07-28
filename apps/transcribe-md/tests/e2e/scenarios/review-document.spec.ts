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
    // The document itself, not a tab strip and not a card stack. This used to
    // assert THREE suggestion cards — the fixture seeds three claims and the
    // lane rendered them. The verifier is audit-only now, so the honest count
    // is zero; the dedicated no-remnants test below covers the rest.
    await expect(page.locator(SUGG)).toHaveCount(0);
    await expect(page.getByTestId('review-document-view')).toBeVisible();
  });

  // ── THE LANE IS GONE ─────────────────────────────────────────────────
  // Five tests lived here: suggestions placed under their section, the
  // read-gate, a taller-than-viewport card, accept-one, accept-remaining.
  // They pinned a surface that no longer exists — the verifier is audit-only
  // and nothing is staged for Accept/Dismiss.
  //
  // What replaces them is the assertion that matters now: NOTHING remains.
  // Deleting a feature and leaving its empty container behind is the failure
  // this guards, because an empty lane reads to a doctor as "nothing flagged"
  // rather than "this surface is gone".
  test('no suggestion surface remains — not even an empty one', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-2')), 'psql seeding unavailable');
    for (const sel of [
      SUGG,
      ACCEPT,
      BULK,
      '[data-testid="suggestions-lane"]',
      '[data-testid="suggestion-item"]',
      '[data-testid="review-doc-details-toggle"]',
    ]) {
      await expect(page.locator(sel), `${sel} must not exist`).toHaveCount(0);
    }
    // …and no copy that describes one.
    await expect(page.locator('body')).not.toContainText(/set aside for your review/i);
    await expect(page.locator('body')).not.toContainText(/suggestions? remaining/i);
    // The document itself still renders.
    await expect(page.getByTestId('review-document-view')).toBeVisible();
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

  test('the level can be adjusted — and an adjusted level still needs confirming', async ({
    page,
  }) => {
    test.skip(!(await open(page, 'rdoc-11')), 'psql seeding unavailable');
    await clearRxGate(page);

    // Clear the seeded change first, so what follows is provably caused by the
    // adjustment and not left over from the fixture.
    await page.getByTestId('review-doc-em-confirm').click();
    await expect(page.getByTestId('review-doc-em-confirm')).toContainText(/confirmed/i);
    const sign = page.getByRole('button', { name: /sign & download/i });
    await expect(sign).toBeEnabled();

    // THE LEVEL ROW: calm, states the level, offers to change it.
    const row = page.getByTestId('review-doc-em-level');
    await expect(row).toBeVisible();
    const current = await page.getByTestId('em-level-current').innerText();
    expect(current).toMatch(/^\d{5}$/);

    await page.getByTestId('em-level-adjust').click();

    // The save is not armed until the change is real AND a reason is given —
    // no validation scolding, the control simply is not live yet.
    const save = page.getByTestId('em-level-save');
    await expect(save).toBeDisabled();
    const target = current === '99214' ? '99213' : '99214';
    await page.getByTestId('em-level-select').selectOption(target);
    await expect(save, 'still disabled with no reason').toBeDisabled();
    await page.getByTestId('em-level-reason').fill('Exam and MDM documented at this level.');
    await expect(save).toBeEnabled();
    await save.click();

    // THE GATE DID NOT WEAKEN. Setting a level is not attesting to one: the
    // same confirm card the model's own re-scores raise comes back, and the
    // signature is blocked until it is answered.
    await expect(page.getByTestId('review-doc-em-gate')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('review-doc-em-gate')).toContainText(target);
    await expect(sign, 'an adjusted level must be confirmed before signing').toBeDisabled();
    await expect(page.locator(BAR)).toContainText('documentation level');

    await page.getByTestId('review-doc-em-confirm').click();
    await expect(sign).toBeEnabled();

    // And the row now states the level the doctor chose.
    await expect(page.getByTestId('em-level-current')).toHaveText(target);
  });

  test('the page carries no billing worksheet — only the level GATE', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-9')), 'psql seeding unavailable');
    // TWO MOVES, and this test has now seen both.
    //
    // First the "⋯ details" disclosure went, because it was hiding a
    // sign-blocker (the E/M stale badge) and a disclosure that hides one
    // blocker will hide the next. The panels came inline, and this test
    // asserted they were all still reachable.
    //
    // Now the panels have gone too. Inline was better than hidden, but the
    // question it answered — "can a doctor still dispute a level here?" — was
    // the wrong one for a page whose job is to show what is being signed. The
    // AMA rubric, the ICD table with confidence scores and the raw dictation
    // are reference material for three different jobs; none of them is
    // "read this and sign it".
    //
    // What stays is the part that BLOCKS the signature, because that belongs
    // on the page that takes the signature.
    await expect(page.locator('.qm-rdoc-meta-panels')).toHaveCount(0);
    await expect(page.locator('.qm-c3-bill-card')).toHaveCount(0);
    await expect(page.getByText(/why this level/i)).toHaveCount(0);
    await expect(page.getByTestId('review-doc-billing-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-codes-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-dictation-panel')).toHaveCount(0);
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
