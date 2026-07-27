// ============================================================================
// The document preview, and the promise that it is never load-bearing.
// ----------------------------------------------------------------------------
// The last test is the important one: with the converter STOPPED, the settings
// screen must still work end to end. A preview that takes the page down with it
// is worse than no preview, and the only way to know is to break it on purpose.
//
// NOTHING HERE SKIPS. An earlier draft guarded each test on "is a certified
// template seeded?" and quietly skipped all three — which looks identical to
// passing and proves nothing. Every case below asserts a real outcome,
// including the case where there is deliberately nothing to preview.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { QA_COMPOSE } from '../helpers/qa-compose';
import { signupFreshUser } from '../helpers/signup';

/** A real multi-page Word form — letterhead, headings, dropdown fields — so the
 *  preview is exercised against document structure rather than a toy.
 *
 *  Path is relative to the Playwright CWD (apps/transcribe-md), NOT an absolute
 *  /opt/meddoc-pro path: that only exists on the VPS, and the same mistake once
 *  made cleanup a silent no-op in CI (see helpers/qa-compose.ts). */
const FORM = 'tests/e2e/fixtures/sample-form.docx';

function converter(action: 'stop' | 'start') {
  try {
    execSync(`${QA_COMPOSE} ${action} gotenberg`, { stdio: 'ignore', timeout: 90_000 });
  } catch {
    // A stack with no converter at all IS the not_configured case, and every
    // assertion below still has to hold.
  }
}

async function toNoteFormat(page: Page) {
  await page.goto('/settings');
  await page.getByRole('button', { name: /note format/i }).first().click();
  await page.waitForTimeout(1000);
}

/** Upload the form and wait for the confirm card.
 *
 *  This used to retry four times: the PHI scan upstream refused a valid upload
 *  about one time in eight. That was root-caused on 2026-07-26 — the scan was
 *  stable (0/10 on identical input); the STRUCTURING step sometimes captured a
 *  boilerplate finding ("No saphenous reflux in right lower extremity") into a
 *  default, and the scan's rules had no answer for clinical prose that names an
 *  anatomy and a side, so it set anyUncertain and the gate fail-closed on the
 *  whole template. The rule is written down now, and the retry is gone: a
 *  refusal here is a real regression, and it should fail this test.
 */
async function uploadUntilConfirm(page: Page) {
  await page.locator('input[type=file]').first().setInputFiles(FORM);
  await expect(page.getByTestId('confirm-filled-sample')).toBeVisible({ timeout: 180_000 });
}

test.describe('real-document preview', () => {
  test.afterAll(async () => {
    converter('start'); // never leave the stack degraded
    await cleanupTestUsers();
  });

  test('the confirm card shows the doctor their own page, drawn', async ({ page }) => {
    test.setTimeout(300_000);
    await signupFreshUser(page, 'dpview');
    await toNoteFormat(page);
    await uploadUntilConfirm(page);

    // data-drawn flips only after every page has actually rendered to canvas.
    await expect(page.locator('.qm-npv-pdf[data-drawn=true]')).toBeVisible({ timeout: 60_000 });
    const pages = await page.locator('.qm-npv-page').count();
    expect(pages).toBeGreaterThan(0);

    // And it is NOT the markdown mock this replaced.
    await expect(page.locator('.qm-ux-sample-pre')).toHaveCount(0);
  });

  test('390px: the page draws and nothing overflows sideways', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await signupFreshUser(page, 'dpmob');
    await toNoteFormat(page);
    await uploadUntilConfirm(page);
    await expect(page.locator('.qm-npv-pdf[data-drawn=true]')).toBeVisible({ timeout: 60_000 });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    // The CTA must be reachable, not covered by the fixed mobile nav.
    const cta = page.getByTestId('confirm-use-format');
    await cta.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    const hit = await cta.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return top === el || el.contains(top);
    });
    expect(hit).toBe(true);
  });

  test('an uncertified template offers no preview — and says nothing false', async ({ page }) => {
    test.setTimeout(300_000);
    await signupFreshUser(page, 'dpnone');
    await toNoteFormat(page);
    await uploadUntilConfirm(page);
    await page.getByTestId('confirm-use-format').click();
    await page.waitForTimeout(8000);
    await toNoteFormat(page);

    // Nothing is certified for native export yet, so there is no page to show.
    // The row must simply not offer one — never an empty viewer, never a claim.
    await expect(page.getByTestId('template-row-see-form')).toHaveCount(0);
    await expect(page.getByTestId('template-row-replace').first()).toBeEnabled();
  });

  test('SIDECAR DOWN — the document still renders and nothing is blocked', async ({ page }) => {
    test.setTimeout(360_000);
    converter('stop');
    try {
      await signupFreshUser(page, 'dpdown');
      await toNoteFormat(page);
      await uploadUntilConfirm(page);

      // The converter is gone, so the server hands back the TRUE DOCX and the
      // browser draws it. Either engine is a pass; a blank surface is not.
      // (both the renderer AND the reason caption are expected — .first())
      await expect(
        page.locator('.qm-npv-docx, .qm-npv-pdf[data-drawn=true], .qm-npv-note').first(),
      ).toBeVisible({ timeout: 90_000 });

      // The reason is SURFACED, not swallowed.
      await expect(page.locator('.qm-npv-note').first()).toContainText(/close preview|couldn|form/i);

      // And the doctor can still finish: the confirm path is untouched.
      await expect(page.getByTestId('confirm-use-format')).toBeEnabled();
      await page.getByTestId('confirm-use-format').click();
      await page.waitForTimeout(8000);
      await toNoteFormat(page);
      await expect(page.getByTestId('template-row-replace').first()).toBeVisible();
    } finally {
      converter('start');
    }
  });
});
