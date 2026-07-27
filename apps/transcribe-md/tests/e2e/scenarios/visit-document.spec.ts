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
  STYLED_VISIT_ID,
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
    // refuses the signature. Re-check it the way a doctor now does: the
    // control is INLINE in the gate stack, next to the signature it blocks,
    // not folded behind a disclosure they had no reason to open.
    await page.getByTestId('review-doc-em-rescore').click();
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

    // The doctor is TOLD why, at the control that resolves it — and that
    // control is now on the page rather than inside a collapsible. A blocker
    // behind a disclosure is a dead end: the sign route refuses and the reason
    // is folded away.
    await expect(page.getByTestId('review-doc-em-stale-gate')).toBeVisible();
    await expect(page.getByTestId('em-stale-badge')).toBeVisible();
    await expect(page.getByTestId('review-doc-em-rescore')).toBeVisible();
    // …and the sign bar says so too, where the signature is.
    await expect(page.getByTestId('review-doc-bar-msg')).toContainText(/re-check/i);

    const scoredCode = () =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: `select coalesce("emScoredCode",'-') from transcribe_visits where id='${seeded.visitId}'`,
        encoding: 'utf8',
      }).trim();

    // Pressing re-check re-scores: the flag clears AND a baseline is recorded.
    // Without a baseline the re-score compares the current level to itself,
    // concludes nothing moved, and clears the flag every time — a gate that
    // cannot catch anything looks exactly like one that checked.
    await page.getByTestId('review-doc-em-rescore').click();
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

    // TWO LEGITIMATE OUTCOMES, and the re-score is a real model call so which
    // one happens is not ours to choose:
    //
    //   • the level did NOT move  -> the route clears the flag and signs.
    //   • the level MOVED         -> the route REFUSES and records the change
    //                                for the doctor to acknowledge. Leaving the
    //                                visit stale is the safer state, not a leak.
    //
    // This used to assert only the first, so a run where the scorer landed on a
    // different code failed the gate for doing its job. The invariant that
    // actually matters is that the sign path never leaves the visit stale with
    // NOTHING recorded — a flag nobody can act on.
    const pending = () =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: `select coalesce("emPendingChange"::text,'-') from transcribe_visits where id='${seeded.visitId}'`,
        encoding: 'utf8',
      }).trim();

    if (attempt.status() === 200) {
      expect(isStale(), 'a completed signature must leave nothing stale').toBe('f');
    } else {
      expect(
        pending(),
        'a refused signature must record WHAT moved, not just decline',
      ).toMatch(/\d{5}/);
    }
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


  test('an existing baseline is NEVER overwritten', async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await openVisit(page);
    const sqlOne = (q: string) =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: q,
        encoding: 'utf8',
      }).trim();

    // The baseline is the level the doctor last had VALIDATED. Re-seeding it
    // from a later note would quietly move the goalposts: the next comparison
    // would be against a level nobody confirmed.
    sqlOne(
      `update transcribe_visits set "emScoredCode"='99999', "emStale"=false ` +
        `where id='${seeded.visitId}'`,
    );
    await page.goto(`/visits/${seeded.visitId}`);
    await page.waitForTimeout(4000);
    const r = await page.request.post(`/api/visits/${seeded.visitId}/retry`, { data: {} });
    expect(r.status()).toBe(200);
    await page.waitForTimeout(3000);

    expect(
      sqlOne(`select "emScoredCode" from transcribe_visits where id='${seeded.visitId}'`),
      'a planted baseline must survive both the page view and the mutation',
    ).toBe('99999');
  });

  test('an EDIT seeds the baseline when none exists', async ({ page }) => {
    test.setTimeout(300_000);
    const seeded = await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });
    const sqlOne = (q: string) =>
      execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
        input: q,
        encoding: 'utf8',
      }).trim();

    // Clear the baseline AFTER the page has loaded, so the page-view seed
    // cannot be what re-establishes it. This is the doctor whose first action
    // on a visit is an edit: without the save path seeding, their first
    // re-score finds no baseline, concludes nothing moved, and clears the gate.
    //
    // (Retry deliberately does NOT seed — it is a regeneration, and the
    // canonical failed-during-L7 retry has no scoring signals yet.)
    sqlOne(
      `update transcribe_visits set "emScoredCode"=null, "emStale"=false ` +
        `where id='${seeded.visitId}'`,
    );

    const opener = page.locator('[data-testid^="section-edit-"]').first();
    const label = (await opener.getAttribute('data-testid'))!.replace('section-edit-', '');
    await opener.click();
    const ta = page.getByTestId(`section-textarea-${label}`);
    await ta.fill(`${await ta.inputValue()}\nBaseline seed probe.`);
    await page.getByTestId(`section-save-${label}`).click();

    await expect
      .poll(
        () =>
          sqlOne(
            `select coalesce("emScoredCode",'-') from transcribe_visits where id='${seeded.visitId}'`,
          ),
        { timeout: 120_000, message: 'the edit must seed the baseline' },
      )
      .toMatch(/^\d{5}$/);
  });


  test('a STYLED visit reviews as the SAME document', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1500, height: 1050 });
    await openVisit(page); // seeds both the twin and its styled counterpart
    await page.goto(`/visits/${STYLED_VISIT_ID}`);

    // No template, no certified twin — and still a paginated document, not a
    // wall of cards. This is the common case: a doctor who taught us a note
    // FORMAT from a note, and never uploaded a FORM.
    const doc = page.getByTestId('visit-document');
    await doc.waitFor({ state: 'visible', timeout: 120_000 });
    expect(Number(await doc.getAttribute('data-pages'))).toBeGreaterThan(0);

    // It says whose layout this is, and what to do about it.
    await expect(page.getByTestId('visit-document-styled-note')).toBeVisible();

    // A table-row suggestion reads as a sentence, never as markup.
    const cards = await page.locator('.qm-rdoc-sugg-text').allInnerTexts();
    expect(cards.some((c) => c.includes('|')), `raw markup in a card: ${cards}`).toBe(false);
    expect(cards.join(' ')).toContain('GSV at the Knee: diameter 3.4 mm');

    // The review placeholder never reaches a review surface.
    expect(await page.locator('body').innerText()).not.toContain('All AI-drafted content');

    // THE ACCESSIBLE SURFACE, held to the same standard.
    //
    // The page is drawn to a canvas, so this block is the reading order a
    // screen reader gets — and asserting only on the CARDS let raw markup live
    // here unnoticed: the table's HEADER row reached a listener verbatim,
    // because claimProse rewrites a row by reading its table's header and a
    // header has no header of its own. A blind doctor was the only one still
    // being shown pipes.
    const spoken = await page.getByTestId('visit-document-text').innerText();
    expect(spoken, `raw markup in the screen-reader block: ${spoken}`).not.toMatch(/\|/);
    expect(spoken).toContain('GSV at the SFJ: diameter 6.2 mm, reflux time 3.4 seconds');
    // An undocumented row asserts nothing, and says so rather than staying mute.
    expect(spoken).toContain('SSV at the Proximal Calf: nothing documented');
    expect(spoken).toContain('Set aside for your review');

    // Same interaction model as a template visit.
    await expect(page.locator('[data-testid^="section-edit-"]').first()).toBeVisible();
    await expect(page.getByRole('button', { name: /sign & download/i })).toBeVisible();

    // And the preview offers both formats.
    await expect(page.getByTestId('preview-format-pdf')).toBeVisible();
    await expect(page.getByTestId('preview-format-word')).toBeVisible();
  });

  test('the Word view is honest, and is not a one-way door', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1500, height: 1050 });
    await openVisit(page);
    await page.goto(`/visits/${STYLED_VISIT_ID}`);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    await page.getByTestId('preview-format-word').click();
    // Word hands the browser the true DOCX, which lands in the fallback branch.
    await page.getByTestId('visit-document-fallback').waitFor({ state: 'visible', timeout: 120_000 });

    // BOTH bugs this test exists for. The toggle used to render only in the PDF
    // branch, so choosing Word removed the control that would bring you back;
    // and the fallback branch called QuillMD's own layout "your form" — the
    // exact false claim this surface exists to stop making.
    await expect(page.getByTestId('preview-format-pdf')).toBeVisible();
    await expect(page.getByTestId('preview-format-word')).toHaveAttribute('aria-pressed', 'true');
    const inWord = await page.locator('body').innerText();
    expect(inWord).not.toContain('Your form, filled so far');
    expect(inWord).toContain('QuillMD’s layout');

    // And back again — the door opens from both sides.
    await page.getByTestId('preview-format-pdf').click();
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });
    await expect(page.getByTestId('preview-format-pdf')).toHaveAttribute('aria-pressed', 'true');
  });

  // ── SURFACE CLEANUP ────────────────────────────────────────────────────
  test('an imaging report carries NO prescription, billing or input chrome', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1500, height: 1050 });
    await openVisit(page);
    await page.goto(`/visits/${STYLED_VISIT_ID}`);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    // No medications and no warnings on this visit, so there is nothing for a
    // prescription-safety heading to be about. It used to draw anyway.
    await expect(page.getByTestId('review-doc-rx-gate')).toHaveCount(0);
    const body = await page.locator('body').innerText();
    expect(body).not.toContain('Prescription safety');

    // The two standing rows are gone — not emptied, gone.
    expect(body).not.toContain('CODES · BILLING');
    await expect(page.getByTestId('review-doc-codes-toggle')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-dictation-toggle')).toHaveCount(0);

    // What remains is one quiet affordance.
    await expect(page.getByTestId('review-doc-billing-panel')).toBeVisible();
  });

  test('NOTHING became unreachable — every datum is still one tap away', async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1500, height: 1050 });
    // The TWIN visit: it has codes, a level, medications and a warning, so it
    // is the one that can prove each of them survived the fold.
    const seeded = await openVisit(page);
    await page.goto(`/visits/${seeded.visitId}`);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    // A visit WITH prescriptions and a warning still gets the gate, unchanged.
    await expect(page.getByTestId('review-doc-rx-gate')).toBeVisible();

    // Billing: the level, and the control that CHANGES it.
    const billing = page.getByTestId('review-doc-billing-panel');
    await expect(billing).toBeVisible();
    await expect(billing.locator('.qm-c3-bill-card')).toBeVisible();
    await expect(billing.locator('select, [role="combobox"]').first()).toBeVisible();
    // Codes: the ICD list.
    await expect(page.getByTestId('review-doc-codes-panel')).toBeVisible();
    // And the original dictation, under its own heading.
    await expect(page.getByTestId('review-doc-dictation-panel')).toBeVisible();
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
