// ============================================================================
// PHASE 2 — the visit page IS the document.
// ----------------------------------------------------------------------------
// What these hold to:
//   • a certified-template visit renders the doctor's OWN form, drawn
//   • adopting a suggestion RE-FILLS it (asserted on the fill's identity, not
//     the counts line — two different fills can report the same numbers)
//   • the preview WRITES NOTHING: no fill manifest appears, before or after,
//     because the sign gate validates a stored manifest and a mid-review one
//     could let a doctor sign a fill that predates their own adoptions
//   • both gates still render, and Sign & Download still works
//   • sidecar down → the page still works, with a named reason
//
// Nothing here skips. A missing fixture FAILS.
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test, type Page } from '@playwright/test';

import { loginUser } from '../helpers/auth';
import { QA_COMPOSE } from '../helpers/qa-compose';
import {
  prepareVisitDocLogin,
  restoreOwnerCredentials,
  seedVisitDocVisit,
  visitDocManifestCount,
  VISIT_DOC_PASSWORD,
  type OwnerCredentials,
} from '../helpers/seedVisitDocVisit';

function converter(action: 'stop' | 'start') {
  try {
    execSync(`${QA_COMPOSE} ${action} gotenberg`, { stdio: 'ignore', timeout: 90_000 });
  } catch {
    // No converter in this stack is itself the fallback case.
  }
}

/** The shared owner account's credentials, so they can be put back. */
let borrowed: OwnerCredentials | null = null;

async function openVisit(page: Page) {
  const seeded = seedVisitDocVisit();
  if (!seeded) throw new Error('no CERTIFIED twin in this stack — fixture missing');
  borrowed = prepareVisitDocLogin(seeded.doctorEmail);
  if (!borrowed) throw new Error('could not prepare a login for the template owner');
  await loginUser(page, seeded.doctorEmail, VISIT_DOC_PASSWORD);
  await page.goto(`/visits/${seeded.visitId}`);
  return seeded;
}

test.describe('the visit page is the document', () => {
  test.afterAll(() => {
    converter('start');
    // The owner account is SHARED — other specs sign in as it and the admin
    // gate keys on its mfaEnabled. Put it back exactly as it was found.
    restoreOwnerCredentials(borrowed);
  });

  test('a certified-template visit renders the doctor’s own form', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    // Assert AFTER seeding, not before: the seed is what clears any manifest a
    // previous run left, so checking first was really asserting on history.
    await openVisit(page);
    expect(visitDocManifestCount(), 'the seed should start from no fill manifest').toBe(0);
    const doc = page.getByTestId('visit-document');
    await doc.waitFor({ state: 'visible', timeout: 120_000 });
    expect(Number(await doc.getAttribute('data-pages'))).toBeGreaterThan(0);
    await expect(page.getByTestId('visit-document-counts')).toBeVisible();

    // Looking at a document must not create one.
    expect(visitDocManifestCount(), 'the preview must not write a fill manifest').toBe(0);
  });

  test('adopting a suggestion re-fills the document', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    const counts = page.getByTestId('visit-document-counts');
    const shaBefore = await counts.getAttribute('data-fill-sha');
    expect(shaBefore, 'the fill should have an identity').toBeTruthy();

    const accept = page.getByRole('button', { name: /accept|add to note/i }).first();
    await expect(accept, 'the seeded claim should render a card').toBeVisible();
    await accept.click();

    await expect
      .poll(async () => counts.getAttribute('data-fill-sha').catch(() => shaBefore), {
        timeout: 120_000,
        message: 'the document should re-fill from the new note',
      })
      .not.toBe(shaBefore);

    expect(visitDocManifestCount(), 'adopting must not write a fill manifest either').toBe(0);
  });

  test('both gates still render, and signing is still reachable', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    // The Rx gate is the SAME component, in the same place in the flow.
    await expect(page.getByTestId('review-doc-rx-gate')).toBeVisible();
    // And the pinned bar is untouched.
    await expect(page.getByRole('button', { name: /sign & download/i })).toBeVisible();
  });

  test('390px: the document draws and nothing overflows sideways', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test('SIDECAR DOWN — the page still works and nothing is blocked', async ({ page }) => {
    test.setTimeout(360_000);
    converter('stop');
    try {
      await page.setViewportSize({ width: 1400, height: 1000 });
      await openVisit(page);

      // Either the browser draws the true DOCX, or the styled note renders.
      // Both are acceptable; a blank page is not, and signing must still work.
      await expect(
        page
          .getByTestId('visit-document-fallback')
          .or(page.getByTestId('review-document-view')),
      ).toBeVisible({ timeout: 120_000 });
      await expect(page.getByRole('button', { name: /sign & download/i })).toBeVisible();
      await expect(page.getByTestId('review-doc-rx-gate')).toBeVisible();
      expect(visitDocManifestCount()).toBe(0);
    } finally {
      converter('start');
    }
  });
});
