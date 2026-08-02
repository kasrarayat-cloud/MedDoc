// ============================================================================
// ROUNDS — Gate B E2E: Screen 3, THE GATES.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md Screen 3. Flag-ON image only.
//
// THE BINDING CONSTRAINT IS WHAT THIS PACK IS FOR:
//
//   "Server refusals remain the sole source of truth — the gates are UI over
//    them; existing sign-block E2Es pass with semantics unchanged."
//
// So the assertions here are mostly about things NOT changing. The Rx override
// still goes through the real per-warning flow with its typed reason and its
// RX_OVERRIDE_RECORDED row; the E/M card still carries the adjust-level flow;
// the signature is still taken by the one existing SignAndSendModal. The flow
// re-sequences and restyles; it decides nothing.
//
// THE ONE TEST THIS PACK EXISTS FOR is "stepping back does not un-clear a
// gate". Both cleared-gate states are lazily-seeded local React state with no
// router.refresh() behind them, so a sequential flow that re-mounted its gates
// would send a doctor back to re-justify a warning already written to the
// database — and the blocker count would tick back up. Stepping back is the
// NORMAL interaction here, not an edge case, which is why the gates are moved
// by portal rather than re-rendered. Nothing but a browser can prove that.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { extractExportText } from '../helpers/exportText';
import {
  seedReviewDocVisit,
  findImagingEmArtifacts,
  IMAGING_NOTE_SOURCE,
  type ReviewDocClass,
} from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';
import { docxGeometry, hasFamily, pdfGeometry } from '../helpers/exportGeometry';

const OVERRIDE_REASON =
  'Benefit outweighs risk; monitoring renal function weekly and patient counselled.';

test.describe('Rounds Screen 3 — the gates', () => {
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

  async function openFlow(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      specialtyClass?: ReviewDocClass;
      emPending?: boolean;
      imagingEmPending?: boolean;
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = requireSeed(seedReviewDocVisit(email, seedOpts), tag);
    if (!seeded) return null;
    await page.goto(`/visits/${seeded.visitId}`);
    await expect(page.getByTestId('rounds-stage')).toBeVisible();
    await page.getByTestId('rounds-review-sign').click();
    await expect(page.getByTestId('rounds-gate-flow')).toBeVisible();
    return seeded;
  }

  /**
   * ⚠️ IN CI, A SEEDER THAT CANNOT SEED IS A DEFECT, NOT A SKIP.
   *
   * Playwright EXITS 0 ON A FULLY SKIPPED FILE. When rounds-signed's seeding
   * broke on a misaligned column, all 11 of its tests skipped and the run went
   * green having proved nothing — A2 defect 0's shape in a new place. In CI the
   * psql channel is guaranteed, so a null here means the seeder is broken.
   *
   * (A probe of the CHANNEL does not catch it. That was tried and watched to
   * pass while the pack skipped: the channel was fine, the INSERT was rejected.)
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

  /** Clear Gate 1 the way a doctor does: the real per-warning override, with
   *  its free-text clinical reason, writing a real RX_OVERRIDE_RECORDED row. */
  async function clearGate1(page: import('@playwright/test').Page) {
    const host = page.getByTestId('rounds-gate-host-rx');
    await host.getByRole('button', { name: /override/i }).first().click();
    // SCOPED BY ITS OWN TEXTAREA, not by role. The gate flow is itself a
    // role="dialog" and the portaled gate inside it contains the word
    // "Override", so getByRole('dialog') matches two elements and a text filter
    // matches both. The reason field is the one thing only this modal has.
    const dialog = page
      .locator('[role="dialog"]')
      .filter({ has: page.locator('#override-reason') });
    await dialog.locator('#override-reason').fill(OVERRIDE_REASON);
    await dialog.getByRole('button', { name: /confirm override/i }).click();
    await expect(host).toContainText(/overridden/i);
  }

  // ── 1. The image is the right image, and the flow is reachable ───────────
  test('the rail opens the flow, on the flag-ON build', async ({ page }) => {
    const seeded = await openFlow(page, 'gates-1');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.locator('html')).toHaveAttribute('data-skin', 'rounds');
    const dlg = page.getByTestId('rounds-gate-flow');
    await expect(dlg).toHaveAttribute('aria-modal', 'true');
    // It opens on the first thing that actually blocks — the Rx gate on this
    // fixture, not step 1 by position.
    await expect(dlg).toHaveAttribute('data-step', 'rx');
  });

  // ── 2. Gate 1 keeps the REAL mechanism ──────────────────────────────────
  test('Gate 1 is the existing per-warning override, typed reason and all', async ({
    page,
  }) => {
    const seeded = await openFlow(page, 'gates-2');
    test.skip(!seeded, 'psql seeding unavailable');

    // The gate arrives by PORTAL — the same section, the same testid, inside
    // the step host. Not a re-implementation.
    const host = page.getByTestId('rounds-gate-host-rx');
    await expect(host.getByTestId('review-doc-rx-gate')).toHaveCount(1);
    // And there is still exactly one of it in the whole document.
    await expect(page.getByTestId('review-doc-rx-gate')).toHaveCount(1);

    // Blocked until the real override is recorded.
    await expect(page.getByTestId('rounds-gate-lock')).toBeVisible();
    await expect(page.getByTestId('rounds-gate-next')).toBeDisabled();

    // A FREE-TEXT CLINICAL REASON — there is no literal token to type. The
    // `> OVERRIDE` in the spec is a prompt aesthetic, not a gate condition, and
    // requiring a typed token would be a NEW condition on signing.
    await clearGate1(page);
    await expect(page.getByTestId('rounds-gate-lock')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-next')).toBeEnabled();
  });

  // ── THE THIRD REFUSAL CLASS — the attestation is a SERVER term ──────────
  test('POST /sign REFUSES a request with no attestation, on the real route', async ({
    page,
  }) => {
    // The UI cannot produce this request any more, which is exactly why it is
    // worth asserting: the gate used to live only in the UI, a second sign
    // control shipped that did not count it, and a signature could pass it with
    // no refusal and no audit row. This drives the ROUTE directly, past every
    // client-side guard, and asks the server the question the doctor's browser
    // no longer can.
    const seeded = await openFlow(page, 'gates-attest', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    const visitId = new URL(page.url()).pathname.split('/').pop()!;

    const refused = await page.request.post(`/api/visits/${visitId}/sign`, {
      data: { destinations: [] },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(refused.status(), 'a sign with no attestation was not refused').toBe(400);
    const body = (await refused.json()) as { ok: boolean; code: string };
    expect(body.ok).toBe(false);
    expect(body.code).toBe('ATTESTATION_REQUIRED');

    // POSITIVE CONTROL — the same request WITH the attestation is not refused
    // for this reason. Without it, a route that refused everything would pass.
    const withAck = await page.request.post(`/api/visits/${visitId}/sign`, {
      data: { destinations: [], attestation: { acknowledged: true } },
      headers: { 'Content-Type': 'application/json' },
    });
    const ackBody = (await withAck.json().catch(() => ({}))) as { code?: string };
    expect(
      ackBody.code,
      'the attested request was ALSO refused for want of an attestation — the ' +
        'route is refusing unconditionally and the assertion above proves nothing',
    ).not.toBe('ATTESTATION_REQUIRED');
  });

  // ── 3. THE TEST THIS PACK EXISTS FOR ────────────────────────────────────
  test('stepping BACK does not un-clear a gate', async ({ page }) => {
    // If the flow re-mounted its gates instead of portaling them, RxTab's
    // `overriddenIds` would reset to its seeded value and the doctor would be
    // asked to re-justify a warning already in rx_warning_overrides. The count
    // would climb back up too. Nothing about that failure is visible without a
    // browser, and stepping back is the normal interaction, not an edge case.
    //
    // Seeded emPending:false so the E/M step does not block — this test is
    // about the Rx gate surviving navigation, and a blocked step in the middle
    // would stop the walk for an unrelated reason.
    const seeded = await openFlow(page, 'gates-3', { emPending: false });
    test.skip(!seeded, 'psql seeding unavailable');

    await clearGate1(page);
    const cleared = await page
      .getByTestId('rounds-gate-n')
      .getAttribute('data-blockers');

    // Forward to the end, then all the way back.
    await page.getByTestId('rounds-gate-next').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'em');
    await page.getByTestId('rounds-gate-next').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute(
      'data-step',
      'attestation',
    );
    await page.getByTestId('rounds-gate-back').click();
    await page.getByTestId('rounds-gate-back').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'rx');

    // Still overridden, still not blocking, still the same count.
    await expect(page.getByTestId('rounds-gate-host-rx')).toContainText(/overridden/i);
    await expect(page.getByTestId('rounds-gate-lock')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-n')).toHaveAttribute(
      'data-blockers',
      cleared!,
    );
  });

  // ── 4. Gate 2 on a quiet visit — never dropped, never counted ───────────
  test('a quiet E/M step is a pass-through review screen', async ({ page }) => {
    // The billing surface exists wherever the specialty applies: the code, the
    // complexity, the rationale and the adjust-level flow live here and nowhere
    // else. On a visit where nothing changed it must still be REACHABLE, and it
    // must NOT be counted — the server would not refuse, so the padlock must
    // not claim it would.
    const seeded = await openFlow(page, 'gates-4', { emPending: false });
    test.skip(!seeded, 'psql seeding unavailable');

    // It is not where the flow opened, precisely BECAUSE it does not block.
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'rx');
    await expect(page.getByTestId('rounds-gate-step-em')).toBeVisible();

    await clearGate1(page);
    await page.getByTestId('rounds-gate-next').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'em');

    // Present, hosting the level card, and not in the way.
    await expect(page.getByTestId('rounds-gate-host-em')).toBeVisible();
    await expect(page.getByTestId('rounds-gate-lock')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-next')).toBeEnabled();
    // Attestation only — the E/M term contributes nothing.
    await expect(page.getByTestId('rounds-gate-n')).toHaveAttribute('data-blockers', '1');
  });

  // ── 5. Gate 2 blocks exactly when the server would ─────────────────────
  test('an unacknowledged E/M change blocks the step', async ({ page }) => {
    const seeded = await openFlow(page, 'gates-5');
    test.skip(!seeded, 'psql seeding unavailable');

    // Clear Rx first so E/M becomes the open step.
    await clearGate1(page);
    await page.getByTestId('rounds-gate-next').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute(
      'data-step',
      'em',
    );
    await expect(page.getByTestId('rounds-gate-lock')).toBeVisible();
    await expect(page.getByTestId('rounds-gate-next')).toBeDisabled();
  });

  // ── 6. Imaging — no Gate 2, anywhere ───────────────────────────────────
  test('an imaging visit has no E/M step at all', async ({ page }) => {
    const seeded = await openFlow(page, 'gates-6', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-gate-step-em')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-host-em')).toHaveCount(0);
    await expect(page.getByTestId('rounds-gate-summary-em')).toHaveCount(0);
    // ⚠️ Vacuous on its own — see the companion test below. Every imaging
    // fixture nulls `emPendingChange`, which is the only source of the anomaly,
    // so this passes against a build with the anomaly deleted.
    await expect(page.getByTestId('rounds-gate-em-artifact')).toHaveCount(0);
    // Attestation only.
    await expect(page.getByTestId('rounds-gate-steps').locator('li')).toHaveCount(1);
  });

  test('THE COMPANION — the anomaly stops the flow and hosts no signature', async ({
    page,
  }) => {
    // An imaging visit wrongly carrying an unacknowledged office E/M change.
    // No E/M gate exists (the invariant is absolute) but POST /sign is not
    // specialty-conditioned and WILL refuse — so the flow names the state and
    // refuses to host the signing bar, rather than offering a signature that
    // cannot succeed.
    const seeded = await openFlow(page, 'gates-6b', {
      specialtyClass: 'imaging',
      imagingEmPending: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-gate-em-artifact')).toHaveCount(1);
    // Still no E/M step — naming the anomaly is not growing a gate for it.
    await expect(page.getByTestId('rounds-gate-step-em')).toHaveCount(0);
    // And no signature host on the anomaly path.
    await expect(page.getByTestId('rounds-gate-host-attestation')).toHaveCount(0);
  });

  // ── 7. Gate 3 — one control can sign, and the summary is honest ────────
  test('the signature is the existing bar, and only applied gates are summarised', async ({
    page,
  }) => {
    const seeded = await openFlow(page, 'gates-7', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute(
      'data-step',
      'attestation',
    );

    // The imaging fixture has no medications, so there is no Rx row to claim
    // was cleared. A fabricated row would be a claim about work nobody did.
    await expect(page.getByTestId('rounds-gate-summary-rx')).toHaveCount(0);

    // The signing bar is PORTALED in — the same one, still the only one.
    await expect(
      page.getByTestId('rounds-gate-host-attestation').getByTestId('review-doc-signbar'),
    ).toHaveCount(1);
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(1);

    // The attestation is labelled as UI-only, because the route cannot see it.
    await expect(page.getByTestId('rounds-gate-attest-note')).toContainText(
      /server does not check/i,
    );
    await expect(page.getByTestId('rounds-gate-attest')).toBeVisible();
  });

  // ── 7b. PDF/WORD PARITY, RE-PROVEN UNDER THE SKIN, AT 1440 ─────────────
  test('PARITY AT 1440 — signing through the flow exports what the paper showed', async ({
    page,
  }, testInfo) => {
    // ⚠️ NOTHING HAD EVER PRODUCED AN EXPORT ON A FLAG-ON BUILD. Gate B asks
    // for parity to be RE-proven, and the evidence offered for it was the
    // `review-doc` and `visit-doc` packs — both of which run on images built
    // WITHOUT NEXT_PUBLIC_SKIN_ROUNDS. They measure the old skin's parity:
    // the same proof that existed before Rounds was written. A re-proof that
    // runs under the pre-change condition establishes nothing about the change,
    // and if the skin ever did alter what reaches the artifact, that whole
    // evidence set would stay green.
    //
    // The other half of the hole: no Rounds pack signs. `rounds-signed` seeds
    // `signed: true` straight into the database, and the walk above stops at
    // the bar without clicking it — so `POST /sign`, the export path, and the
    // artifacts had never been exercised with the skin on, at any width.
    //
    // Imaging, deliberately: it opens directly at attestation (no Rx gate, no
    // E/M gate), so the walk is short, and it is the class where a leak is
    // worst — an office E/M code on an ultrasound report is wrong as DATA and
    // reaches the signed record.
    await page.setViewportSize({ width: 1440, height: 900 });
    const seeded = await openFlow(page, 'gates-parity', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    // WHAT THE DOCTOR SEES, under the skin, at 1440 — read before signing,
    // because signing replaces the screen with Screen 4.
    const paper = await page.getByTestId('review-document-view').innerText();
    expect(
      paper.length,
      'the Rounds paper rendered empty — a parity assertion against it would ' +
        'pass on anything',
    ).toBeGreaterThan(200);

    // The markers come from the FIXTURE, not from a second hand-written copy,
    // so they cannot drift into agreeing with themselves.
    const HEADINGS = IMAGING_NOTE_SOURCE.filter((l) => l.startsWith('## ')).map((l) =>
      l.replace(/^##\s*/, ''),
    );
    expect(HEADINGS.length, 'no headings derived from the fixture').toBeGreaterThan(4);
    for (const h of HEADINGS) {
      expect(paper, `the paper is missing "${h}" before signing`).toContain(h);
    }

    // Register the listener BEFORE submitting — two sequential waitForEvent
    // calls can miss a download that already fired, which reads as a 60s
    // timeout and looks like a broken export rather than a racing test.
    const downloads: import('@playwright/test').Download[] = [];
    page.on('download', (d) => downloads.push(d));

    await page.getByTestId('rounds-gate-attest').check();
    const bar = page.getByTestId('review-doc-signbar');
    await bar.getByRole('button', { name: /sign & download/i }).click();
    const dialog = page.getByRole('dialog');
    // Toggles, not commands: PDF is pressed by default, so a blind click
    // DESELECTS it. Press only what is not already pressed.
    for (const label of [/download pdf/i, /download docx/i]) {
      const btn = dialog.getByRole('button', { name: label });
      if ((await btn.getAttribute('aria-pressed')) !== 'true') await btn.click();
    }
    await dialog.getByRole('button', { name: /sign & deliver/i }).dispatchEvent('click');

    await expect
      .poll(() => downloads.length, {
        message: 'expected a PDF and a DOCX from the Rounds sign submit',
        timeout: 90_000,
      })
      .toBeGreaterThanOrEqual(2);

    const files = downloads.slice(0, 2);
    expect(
      files.map((f) => f.suggestedFilename().replace(/^.*\./, '')).sort(),
      'one PDF and one DOCX',
    ).toEqual(['docx', 'pdf']);

    // ⚠️ C2-b — GEOMETRY AND TYPE, READ FROM THE BYTES, BESIDE THE TEXT CHECK.
    // The clause this test discharges is "PDF/Word parity re-proven at 1440",
    // and until now it compared section-heading STRINGS. `exportText.ts` strips
    // every XML tag to do that, so `w:pgSz` / `w:rFonts` / `w:sz` were never in
    // its universe — and a US-Letter PDF and an A4 Word file with the same
    // words passed it for as long as both existed. The preview is Gotenberg's
    // render of the DOCX, so that split was also preview-vs-download.
    {
      const byExt = new Map(
        files.map((f) => [f.suggestedFilename().replace(/^.*\./, ''), f]),
      );
      const pdfPath = await byExt.get('pdf')!.path();
      const docxPath = await byExt.get('docx')!.path();
      const [pdfG, docxG] = await Promise.all([
        pdfGeometry(pdfPath!),
        docxGeometry(docxPath!),
      ]);
      expect(
        { w: docxG.widthPt, h: docxG.heightPt },
        'the Word file is a different page size from the PDF — and since the ' +
          'on-screen preview is a render of that Word file, the doctor is ' +
          'reading one page and downloading another',
      ).toEqual({ w: pdfG.widthPt, h: pdfG.heightPt });
      // US Letter, stated rather than merely "equal to each other" — two
      // artifacts agreeing on the wrong page would satisfy an equality alone.
      expect({ w: pdfG.widthPt, h: pdfG.heightPt }).toEqual({ w: 612, h: 792 });
      // The PDF EMBEDS its faces; the DOCX can only name them, which is why the
      // converter image had to gain them.
      expect(
        hasFamily(pdfG.fonts, 'Charter'),
        `the PDF does not embed Charter — it carries ${pdfG.fonts.join(', ')}`,
      ).toBe(true);
      expect(
        hasFamily(docxG.fonts, 'Charter'),
        `the Word file does not name Charter — it names ${docxG.fonts.join(', ')}`,
      ).toBe(true);
    }

    for (const f of files) {
      const path = await f.path();
      expect(path, `no path for ${f.suggestedFilename()}`).toBeTruthy();
      // `extractExportText` throws rather than returning '' when it cannot find
      // the marker — so a broken extractor cannot turn the assertions below
      // into a no-op that reports success forever.
      const text = await extractExportText(path!, f.suggestedFilename(), 'EXAM TYPE');

      // PARITY: every section the doctor read on the Rounds paper is in the
      // bytes they receive.
      for (const h of HEADINGS) {
        expect(
          text,
          `${f.suggestedFilename()} is missing the "${h}" section the paper showed`,
        ).toContain(h);
      }
      // And the invariant the export path has no specialty guard for: no
      // office E/M code may reach an imaging artifact.
      expect(
        text,
        `${f.suggestedFilename()} leaked an office E/M code from an imaging visit`,
      ).not.toMatch(/\b992\d\d\b/);
    }

    await testInfo.attach('rounds-parity-filenames', {
      body: files.map((f) => f.suggestedFilename()).join('\n'),
    });
  });

  // ── 8. The flow and the strip cannot disagree about N ──────────────────
  test('the flow’s count and the padlock’s are the same number', async ({ page }) => {
    const seeded = await openFlow(page, 'gates-8');
    test.skip(!seeded, 'psql seeding unavailable');

    const flowN = await page.getByTestId('rounds-gate-n').getAttribute('data-blockers');
    await page.getByTestId('rounds-gate-close').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveCount(0);

    await expect(page.getByTestId('rounds-strip-signed')).toHaveAttribute(
      'data-blockers',
      flowN!,
    );
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      flowN!,
    );
  });
});
