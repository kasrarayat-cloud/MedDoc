// ============================================================================
// PHASE 2 — the visit page IS the document.
// ----------------------------------------------------------------------------
// What these hold to:
//   • a certified-template visit renders the doctor's OWN form, drawn
//   • an EDIT re-fills it (asserted on the fill's identity, not the counts
//     line — two different fills can report the same numbers)
//   • the preview WRITES NOTHING: no fill manifest appears, before or after,
//     because the sign gate validates a stored manifest and a mid-review one
//     could let a doctor sign a fill that predates their own edits
//   • NO suggestion lane: the verifier is audit-only, nothing is staged
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

/** One scalar out of the QA database. Hoisted: three tests declared it
 *  locally and a fourth needed it, and four copies of a psql shell-out is
 *  three chances for them to drift apart. */
const sqlOne = (q: string) =>
  execSync(`${QA_COMPOSE} exec -T postgres psql -U meddoc -d ${QA_DB} -A -t -f -`, {
    input: q,
    encoding: 'utf8',
  }).trim();

/** Written by the chat-editor walk and looked for in the signed file. */
const EDIT_MARK = 'Bilateral study completed without complication.';

/**
 * Amend one section THROUGH THE CHAT EDITOR — the only way to change a note
 * before signing now that the per-section edit pills are gone.
 *
 * The model is stubbed (MOCK_AI_CALLS; see the tm_chat_edit fixture in
 * packages/ai/src/mock.ts) so the section and the body are ours to choose and
 * the turn is deterministic. Everything downstream of the model is REAL: the
 * intent goes through the same dispatcher, the same `saveNoteSectionAction`,
 * the same splice, the same audit row and the same staleness flag the deleted
 * pill used to reach. That shared write path is why parity holds.
 */
async function chatEditSection(page: Page, section: string, body: string) {
  const editor = page.getByTestId('chat-editor');
  await expect(editor, 'the chat editor is the edit surface').toBeVisible({ timeout: 60_000 });
  const before = await page.getByTestId('chat-turn-assistant').count();
  await page.getByTestId('chat-input').fill(`MOCKEDIT ${section} :: ${body}`);
  await page.getByTestId('chat-send').click();
  await expect(page.getByTestId('chat-turn-assistant')).toHaveCount(before + 1, {
    timeout: 120_000,
  });
  // The turn must SAY it acted, and say it SUCCEEDED.
  //
  // Naming the section is not enough: the failure line is
  // "Could not change <section>: <error>", so an assertion that only looks for
  // the section name passes on a refused edit. That is not hypothetical — it
  // passed on one, and the test only failed two steps later when the staleness
  // flag it expected never appeared.
  const actions = page.getByTestId('chat-actions').last();
  await expect(actions).toContainText(new RegExp(`Changed ${section}`, 'i'));
  await expect(actions).not.toContainText(/could not/i);
  await expect(actions.locator('.qm-chat-action-fail')).toHaveCount(0);
}

/** The first anchored section heading on the drawn document — whatever the
 *  doctor's own template happens to call it. */
async function firstSectionLabel(page: Page): Promise<string> {
  const anchored = page.locator('[data-section]').first();
  await expect(anchored).toBeAttached({ timeout: 120_000 });
  return (await anchored.getAttribute('data-section'))!;
}

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

  // 'adopting a suggestion re-fills the document' lived here. The verifier is
  // AUDIT-ONLY — nothing is staged and there is no Accept button to press, so
  // the test is deleted rather than weakened into asserting the absence of a
  // button, which the no-remnants test already covers. The re-fill path it
  // exercised is still covered by the tap-to-edit test below, which drives the
  // SAME re-fill through an edit.

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


  test('chat edit: the edit reaches the document AND the delivered file', async ({ page }) => {
    test.setTimeout(420_000);
    await page.setViewportSize({ width: 1400, height: 1000 });
    const seeded = await openVisit(page);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    const counts = page.getByTestId('visit-document-counts');
    const shaBefore = await counts.getAttribute('data-fill-sha');

    // NO EDIT PILLS. The paper is read-only; the chat is the way in.
    await expect(page.locator('[data-testid^="section-edit-"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="section-textarea-"]')).toHaveCount(0);

    const label = await firstSectionLabel(page);
    await chatEditSection(page, label, EDIT_MARK);

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

    // THE TRIGGERING EDIT COMES THROUGH THE CHAT.
    //
    // This is the assertion that matters after deleting the pills: the gate has
    // to key on the note CHANGING, not on the surface that changed it. It does
    // — every editor funnels into saveSoapDraftAction, and that is the one line
    // that sets emStale. If the gate had been wired to the pill, deleting the
    // pill would have silently removed the staleness check from every edit.
    const label = await firstSectionLabel(page);
    await chatEditSection(page, label, 'Stale-gate probe.');
    await page.waitForTimeout(3000);

    expect(isStale(), 'a CHAT edit must mark the level stale').toBe('t');

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
    await chatEditSection(page, label, 'Second probe.');
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

    const label = await firstSectionLabel(page);
    await chatEditSection(page, label, 'Baseline seed probe.');

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

    // The card assertions that were here went with the lane. What they were
    // really protecting is below and is UNCHANGED: raw table markup must never
    // reach a reader. That check was always the stronger of the two — it is the
    // one that caught a header row being read out verbatim.

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

    // Same interaction model as a template visit: read-only paper, and the
    // three things a doctor can act on — chat, the gates, and the signature.
    await expect(page.locator('[data-testid^="section-edit-"]')).toHaveCount(0);
    await expect(page.getByTestId('chat-editor')).toBeVisible();
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

    // The billing panel used to be UNASSERTABLE here, and the reason is worth
    // keeping because it is the shape of a whole class of bad test: its
    // presence keyed on `hasSummary` → `emNotApplicable` → a BUILD FLAG
    // (NEXT_PUBLIC_ULTRASOUND_SPECIALTY) that prod's image sets and the CI
    // visit-doc image does not. An assertion either way passed in one
    // environment and failed in the other while the product was correct in
    // both, so the honest move was to assert nothing.
    //
    // It is assertable now, in every environment, because the panel is gone
    // unconditionally. A surface that does not exist cannot be flag-dependent.
    await expect(page.getByTestId('review-doc-billing-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-codes-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-dictation-panel')).toHaveCount(0);
  });

  test('the review page is PAPER — no panels, no pills, only the gates and Sign', async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1500, height: 1050 });
    // The TWIN visit: it has codes, a level, medications and a warning — so it
    // is the visit that WOULD have drawn every panel. If any survived, it is
    // the one that shows it.
    const seeded = await openVisit(page);
    await page.goto(`/visits/${seeded.visitId}`);
    await page.getByTestId('visit-document').waitFor({ state: 'visible', timeout: 120_000 });

    // GONE: the billing card, the codes table, the input transcript, and the
    // wrapper that held all three.
    await expect(page.getByTestId('review-doc-billing-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-codes-panel')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-dictation-panel')).toHaveCount(0);
    await expect(page.locator('.qm-rdoc-meta')).toHaveCount(0);
    await expect(page.locator('.qm-c3-bill-card')).toHaveCount(0);

    // GONE: every per-section edit affordance.
    await expect(page.locator('[data-testid^="section-edit-"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="section-textarea-"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="section-save-"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="section-uneditable-"]')).toHaveCount(0);
    // …including the whole-blob click-to-edit on the styled-note fallback.
    await expect(page.locator('[data-edit-affordance]')).toHaveCount(0);

    // STILL HERE, and these three are the whole interaction model:
    await expect(page.getByTestId('review-doc-rx-gate')).toBeVisible();
    await expect(page.getByTestId('chat-editor')).toBeVisible();
    await expect(page.getByRole('button', { name: /sign & download/i })).toBeVisible();

    // The coding did not stop being COMPUTED — it stopped being drawn. It is
    // still on the row, which is what export and billing read.
    const codes = sqlOne(
      `select case when "icdCodes" is null then 'null' else 'present' end ` +
        `from transcribe_visits where id='${seeded.visitId}'`,
    );
    expect(codes, 'the coding must still be stored, only not rendered').toBe('present');
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
