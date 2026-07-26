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
import { readFileSync, writeFileSync } from 'node:fs';

import { expect, test, type Page } from '@playwright/test';

import { loginUser } from '../helpers/auth';
import { QA_COMPOSE, QA_DB } from '../helpers/qa-compose';
import {
  prepareVisitDocLogin,
  restoreOwnerCredentials,
  seedVisitDocVisit,
  visitDocManifestCount,
  VISIT_DOC_PASSWORD,
  type OwnerCredentials,
} from '../helpers/seedVisitDocVisit';

/** Written by the tap-to-edit walk and looked for in the signed file. */
const EDIT_MARK = 'Bilateral study completed without complication.';

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


  test('tap-to-edit: the edit reaches the document AND the delivered file', async ({ page }) => {
    test.setTimeout(420_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    const seeded = await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    const counts = page.getByTestId('visit-document-counts');
    const shaBefore = await counts.getAttribute('data-fill-sha');

    const opener = page.locator('[data-testid^="section-edit-"]').first();
    await expect(opener, 'every anchored section should offer an edit').toBeVisible();
    const label = (await opener.getAttribute('data-testid'))!.replace('section-edit-', '');
    await opener.click();
    // By testid, not by `#edit-${label}`: the DOM id is slugified (an id may
    // not contain whitespace), so a label like "Chief Complaint" would make
    // that selector a descendant combinator matching nothing.
    const ta = page.getByTestId(`section-textarea-${label}`);
    await expect(ta).toBeVisible();
    await ta.fill(`${await ta.inputValue()}\n${EDIT_MARK}`);
    await page.getByTestId(`section-save-${label}`).click();

    // The document re-fills through the SAME path an adopt uses.
    await expect
      .poll(async () => counts.getAttribute('data-fill-sha').catch(() => shaBefore), {
        timeout: 120_000,
        message: 'the document should re-fill after an edit',
      })
      .not.toBe(shaBefore);
    // And editing still writes no fill manifest.
    expect(visitDocManifestCount()).toBe(0);

    // The edit made the billing level stale — that is the new gate, and it
    // refuses the signature. Re-check the level the way a doctor would: open
    // the codes row, then acknowledge if it moved.
    await page.getByTestId('review-doc-codes-toggle').click();
    await expect(page.getByTestId('em-stale-badge')).toHaveCount(0, { timeout: 120_000 });
    const emConfirm = page.getByRole('button', { name: /confirm|acknowledge/i }).first();
    if (await emConfirm.count()) {
      await emConfirm.click();
      await page.waitForTimeout(2000);
    }

    // Sign, and read the file the doctor actually receives.
    const dismiss = page.getByRole('button', { name: /^dismiss/i }).first();
    if (await dismiss.count()) {
      await dismiss.click();
      await page.waitForTimeout(2500);
    }
    await page.getByRole('button', { name: /sign & download/i }).click();
    const pending = page.waitForEvent('download', { timeout: 120_000 });
    await page.getByRole('button', { name: /^sign & deliver$/i }).dispatchEvent('click');
    const download = await pending;
    const file = await download.path();
    writeFileSync('/tmp/qa-signed-preview.pdf', readFileSync(file!));

    // Read the PDF's TEXT. A byte search finds nothing — the streams are
    // compressed — and would pass as a false negative forever.
    const text = execSync(
      `node -e "const {extractText,getDocumentProxy}=require('unpdf');const fs=require('fs');` +
        `(async()=>{const d=await getDocumentProxy(new Uint8Array(` +
        `fs.readFileSync('/tmp/qa-signed-preview.pdf')));` +
        `const r=await extractText(d,{mergePages:true});process.stdout.write(r.text)})()"`,
      { encoding: 'utf8', cwd: process.cwd() },
    );
    expect(text, 'the signed file must carry the doctor’s edit').toContain(EDIT_MARK);
    void seeded;
  });


  test('E/M STALE: an edit blocks signing until the level is re-checked', async ({ page }) => {
    test.setTimeout(420_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    const seeded = await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    const isStale = () =>
      execSync(
        `${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`,
        {
          input: `select "emStale" from transcribe_visits where id='${seeded.visitId}'`,
          encoding: 'utf8',
        },
      ).trim();

    // Edit through tap-to-edit — the surface every editor funnels into.
    const opener = page.locator('[data-testid^="section-edit-"]').first();
    const label = (await opener.getAttribute('data-testid'))!.replace('section-edit-', '');
    await opener.click();
    const ta = page.getByTestId(`section-textarea-${label}`);
    await ta.fill(`${await ta.inputValue()}\nStale-gate probe.`);
    await page.getByTestId(`section-save-${label}`).click();
    await page.waitForTimeout(3000);

    expect(isStale(), 'an edit must mark the level stale').toBe('t');

    // The doctor is TOLD why, at the control that resolves it.
    await expect(page.getByTestId('em-stale-badge')).toBeVisible();

    const scoredCode = () =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: `select coalesce("emScoredCode",'-') from transcribe_visits where id='${seeded.visitId}'`,
        encoding: 'utf8',
      }).trim();

    // Opening the codes row re-scores: the flag clears AND a baseline is
    // recorded. Without a baseline the re-score compares the current level to
    // itself, concludes nothing moved, and clears the flag every time — a gate
    // that cannot catch anything looks exactly like one that checked.
    await page.getByTestId('review-doc-codes-toggle').click();
    await expect
      .poll(() => isStale(), { timeout: 120_000, message: 'the re-score should clear the flag' })
      .toBe('f');
    expect(scoredCode(), 'the validated level must be recorded').toMatch(/^\d{5}$/);

    // A SECOND edit is now gated against a real before.
    await opener.click();
    await ta.fill(`${await ta.inputValue()}\nSecond probe.`);
    await page.getByTestId(`section-save-${label}`).click();
    await expect.poll(() => isStale(), { timeout: 60_000 }).toBe('t');

    // Signing re-scores server-side rather than refusing and pointing at a
    // control that may not be rendered — the gate is enforced by the route
    // that owns the transition, not by whichever surface happens to be up.
    const attempt = await page.request.post(`/api/visits/${seeded.visitId}/sign`, {
      data: { destinations: [] },
    });
    expect([200, 400, 409]).toContain(attempt.status());
    expect(isStale(), 'the sign path must resolve staleness, not leave it').toBe('f');
  });


  test('E/M STALE: a MOVED level blocks the signature', async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await openVisit(page);
    const sqlOne = (q: string) =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: q,
        encoding: 'utf8',
      }).trim();

    // A validated level that differs from what this note scores at. Planting
    // the baseline is the only way to exercise "moved" deterministically — the
    // scorer is a real model and we do not get to choose its answer.
    sqlOne(
      `update transcribe_visits set "emScoredCode"='99214', "emStale"=true, ` +
        `"emPendingChange"=null where id='${seeded.visitId}'`,
    );

    const r = await page.request.post(`/api/visits/${seeded.visitId}/sign`, {
      data: { destinations: [] },
    });
    expect(r.status(), 'a moved level must block the signature').not.toBe(200);
    expect(await r.text()).toMatch(/confirm the new level/i);
    expect(sqlOne(`select status from transcribe_visits where id='${seeded.visitId}'`)).toBe(
      'READY',
    );
    // The record reaching the gate carries REAL codes, not the fail-closed
    // sentinel — a cause the parser rejects turns this into "unknown → unknown".
    expect(
      sqlOne(`select "emPendingChange"::text from transcribe_visits where id='${seeded.visitId}'`),
    ).toMatch(/99214/);
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
