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
//
// ----------------------------------------------------------------------------
// ⚠️ RE-POINTED 2026-08-05 (F-ret.3). THE PRODUCT DID NOT CHANGE; THIS PACK'S
// IMAGE DID.
//
// The `review-doc` CI job builds REVIEW_DOC_VIEW + SKIN_BETA + ULTRASOUND and
// used to omit NEXT_PUBLIC_SKIN_ROUNDS — so for its whole life it exercised the
// pre-sign document surface on the LEGACY skin. F-ret.3 deleted that flag AND
// its OFF arm, so the Rounds skin is unconditional and the configuration this
// pack was written against can no longer be built. Eight of eighteen tests went
// red on selectors that only ever existed on the legacy rendering. Same class as
// the rx-safety repair (commit 3d8cb23f), same day's cause.
//
// THE TWO DEAD SELECTORS, and what carries each claim now:
//
//   1. `[data-testid="review-doc-bar-msg"]` — the sticky footer bar's status
//      line. `review-sign-bar.tsx` still renders it, but only in its `footer`
//      variant, and under Rounds the paper passes `hostSignbar={false}`
//      (`visit-ready-view.tsx:1153`). There is no footer on the stage at all.
//      The bar named the NEXT blocker; three surfaces now do, each narrower and
//      each asserted where it belongs:
//        · `rounds-critical-band`     — RETIRED with the Rx surface (#109)
//        · `rounds-gate-lock`         — inside the flow, names the blocker AND
//                                       its count for the step being shown
//        · `review-doc-em-stale-gate` — "Documentation level needs re-checking"
//
//   2. `getByRole('button', { name: /sign & download/i })` on the page. The
//      string is not gone — it is the gate signbar's trigger — but the control
//      exists ONLY inside Gate 3 (`gate-flow.tsx:400`), and only once the gates
//      in front of it are clear. "Sign is disabled" therefore has a STRONGER
//      analogue than a disabled button: the signature is not reachable at all,
//      i.e. `review-doc-signbar` has count 0. Where the original asserted
//      ENABLED, the walk advances to the attestation step and asserts the real
//      button, which is disabled until `rounds-gate-attest` is ticked.
//
// NOTHING WAS RETIRED AND NOTHING WAS WEAKENED. Every claim survives, re-anchored
// on the element that now carries it, with the count or the exact phrase kept
// rather than softened to a substring. Three moved in the STRENGTHENING
// direction and each says so at the call site:
//
//   · "sign is disabled"  → the sign control is not MOUNTED (count 0), and the
//     attestation is not reachable either. A doctor cannot attest to a note
//     they cannot sign — a property the disabled button never had.
//   · "sign is enabled"   → the walk advances to Gate 3, where the real button
//     is disabled until `rounds-gate-attest` is ticked. The old footer bar's
//     `blocked` term did not count the attestation at all; that was R1's bypass.
//   · the imaging half of the stale spec asserted absence ON THE BAR. With the
//     bar unreachable that assertion resolves to zero nodes and passes for free,
//     so it is widened to `body` — a negative assertion whose subject does not
//     exist proves nothing.
//
// ⚠️ `openSignFlow` IS USED WHERE IT FITS AND DELIBERATELY NOT WHERE IT DOES
// NOT. It waits for `rounds-gate-attest` (`helpers/sign.ts:95`), which a
// deliberately-blocked visit never presents. The four blocked-visit tests drive
// the rail with `openGateFlow` and assert the lock instead. That distinction is
// the one the rx-safety repair got wrong first.
// ============================================================================

import { test, expect } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import {
  seedReviewDocVisit,
  assertImagingHasNoEm,
  findImagingEmArtifacts,
  psqlOne,
  REVIEW_DOC_CLASSES,
  SEEDED_EM_LEVEL,
  type ReviewDocClass,
} from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';
import { extractExportText } from '../helpers/exportText';
import {
  attestAndSubmit,
  expectGateStep,
  openGateFlow,
  openSignFlow,
} from '../helpers/sign';

const SUGG = '[data-testid="review-doc-suggestion"]';
const ACCEPT = '[data-testid="review-doc-accept"]';
const BULK = '[data-testid="review-doc-accept-remaining"]';

// ⚠️ `BAR` WAS HERE. `[data-testid="review-doc-bar-msg"]` is the footer sign
// bar's status line and it is unreachable on this pack's image — see the header.
// Not replaced by one selector, because it was one element making three
// different claims; each is now asserted on the element that makes it.

/** The gate signbar's trigger — the ONLY control on the Rounds stage that can
 *  start a signature, and it exists only while Gate 3 is showing. Scoped to the
 *  bar rather than taken off the page: `expectSignModalClosed` relies on the
 *  same label appearing nowhere else, and scoping keeps a future second home
 *  from being silently absorbed by a page-wide `.first()`. */
const signTrigger = (page: import('@playwright/test').Page) =>
  page.getByTestId('review-doc-signbar').getByRole('button', { name: /sign & download/i });

/** "Sign is disabled" has no analogue under Rounds — the signature is not
 *  RENDERED until the gates in front of it are clear. This is the stronger
 *  reading of the same claim, and it is non-vacuous because the tests that
 *  clear the gates go on to assert the very same testid is present. */
async function expectSignatureUnreachable(page: import('@playwright/test').Page) {
  await expect(
    page.getByTestId('review-doc-signbar'),
    'a sign control is mounted while a gate is still outstanding',
  ).toHaveCount(0);
  await expect(
    page.getByTestId('rounds-gate-attest'),
    'the attestation is reachable while a gate is still outstanding — the ' +
      'doctor can attest to a note they cannot sign',
  ).toHaveCount(0);
}

/** The rail's own label. It is `signLabel(n)` over the SAME `n` the signature is
 *  wired to (`blocked = roundsView.n > 0`), so it is the doctor-facing statement
 *  of "is this note signable" that the footer bar used to make. Exact text, with
 *  the count — a substring would pass on any number of blockers. */
async function expectRail(page: import('@playwright/test').Page, label: string) {
  await expect(page.getByTestId('rounds-review-sign')).toHaveText(label);
}

test.describe('pre-sign review as the document', () => {
  test.beforeAll(() => {
    // A DIRTY DATABASE FAILS THE PACK, LOUDLY. Two long-lived QA fixtures once
    // carried office-E/M state written by a pre-label-fix page render — no
    // seeder produced it, and every walk and spec that read those rows was
    // reading the bug as truth. Asserting here means the next occurrence is a
    // red pack with the offending ids named, not a quietly wrong green.
    const dirty = findImagingEmArtifacts();
    expect(
      dirty,
      'imaging visits in the QA database carry office-E/M state:\n  ' +
        dirty.join('\n  ') +
        '\nAn office level on an imaging report is wrong as data. Purge it before trusting this pack.',
    ).toEqual([]);
  });

  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  /** Fresh user + a purpose-built visit per test — the suite's own pattern, and
   *  it keeps each flow independent of what the previous one adopted or signed.
   *  Returns null when the psql channel is unavailable so the test skips for an
   *  environment reason rather than failing. */
  async function open(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      emStale?: boolean;
      emPending?: boolean;
      specialtyClass?: ReviewDocClass;
      imagingEmArtifact?: boolean;
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = seedReviewDocVisit(email, seedOpts);
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

  // ⚠️ `clearRxGate` WAS REMOVED HERE — owner ruling #109 deleted the gate it
  // cleared. Six tests called it; each now either drops the step (the Rx
  // blocker is gone, so E/M is the first) or asserts the gate's absence.

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


  test('NO prescription card, and no critical band — owner ruling #109', async ({ page }) => {
    // ⚠️ REPLACES 'the critical-Rx card blocks signing until a typed override is
    // recorded'. That test's subject was deleted; its SHAPE is preserved,
    // because what it really proved is that this surface names its blockers
    // honestly and never presents a signature in front of one. That property is
    // now carried by the E/M half, asserted below on the same fixture.
    test.skip(!(await open(page, 'rdoc-7')), 'psql seeding unavailable');

    await expect(page.getByTestId('review-doc-rx-gate')).toHaveCount(0);
    await expect(page.getByTestId('rounds-critical-band')).toHaveCount(0);
    await expect(page.locator('[class*="qm-lin-rx"]')).toHaveCount(0);
    await expect(page.locator('[class*="qm-warn"]')).toHaveCount(0);

    // There is no sign control while a gate is still in front of it.
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(0);

    // ⚠️ `openGateFlow`, NOT `openSignFlow`. This visit is deliberately blocked,
    // so the flow opens ON the blocker and never presents the attestation —
    // a helper that waits for one can only time out (helpers/sign.ts:95).
    //
    // POSITIVE CONTROL for every zero above: the surface DOES still block, and
    // it blocks on the E/M level, which is now the first gate.
    await openGateFlow(page);
    await expectGateStep(page, 'em');
    await expect(page.getByTestId('rounds-gate-lock')).toContainText(
      '1 documentation level outstanding',
    );
    await expect(page.getByTestId('rounds-gate-next')).toBeDisabled();
    await expectSignatureUnreachable(page);
  });

  test('the E/M card blocks signing until the level is confirmed', async ({ page }) => {
    test.skip(!(await open(page, 'rdoc-8')), 'psql seeding unavailable');
    // ⚠️ No Rx blocker to clear first — ruling #109 — so E/M is the first gate.
    const em = page.getByTestId('review-doc-em-gate');
    await expect(em).toBeVisible();
    await expect(em).toContainText('99214');

    // WAS: `expect(BAR).toContainText('documentation level')` + a disabled Sign.
    // With Rx already cleared the flow opens straight on E/M, and the lock names
    // it with its count.
    await openGateFlow(page);
    await expectGateStep(page, 'em');
    await expect(page.getByTestId('rounds-gate-lock')).toContainText(
      '1 documentation level outstanding',
    );
    await expectSignatureUnreachable(page);

    await page.getByTestId('review-doc-em-confirm').click();
    await expect(page.getByTestId('review-doc-em-confirm')).toContainText(/confirmed/i);

    // WAS: `expect(sign).toBeEnabled()`. The signature becomes REACHABLE — and
    // then, and only then, is there a button to talk about being enabled. It is
    // disabled until the attestation is ticked, which is the same gate the old
    // footer bar's `blocked` term never counted (R1's bypass).
    await expect(page.getByTestId('rounds-gate-lock')).toHaveCount(0);
    await page.getByTestId('rounds-gate-next').click();
    await expectGateStep(page, 'attestation');
    await expect(signTrigger(page)).toBeDisabled();
    await page.getByTestId('rounds-gate-attest').click();
    await expect(signTrigger(page)).toBeEnabled();
  });

  test('the level can be adjusted — and an adjusted level still needs confirming', async ({
    page,
  }) => {
    test.skip(!(await open(page, 'rdoc-11')), 'psql seeding unavailable');

    // Clear the seeded change first, so what follows is provably caused by the
    // adjustment and not left over from the fixture.
    await page.getByTestId('review-doc-em-confirm').click();
    await expect(page.getByTestId('review-doc-em-confirm')).toContainText(/confirmed/i);
    // WAS: `expect(sign).toBeEnabled()`. There is no sign control on the stage,
    // so the claim is anchored on the rail's own label — `signLabel(n)` over the
    // SAME `n` the signature is wired to (`blocked = roundsView.n > 0`). Rx
    // overridden and the level confirmed leaves exactly one term: the
    // attestation. Exact text, because '· 1 blocker' is a substring of nothing
    // useful and 'Review & sign' is a substring of every state including the
    // blocked ones.
    await expectRail(page, 'Review & sign · 1 blocker');

    // THE LEVEL ROW: calm, states the level, offers to change it.
    const row = page.getByTestId('review-doc-em-level');
    await expect(row).toBeVisible();
    // ASSERT THE FIXTURE'S LEVEL, do not read it and adapt. Deriving `target`
    // from whatever the row happened to say made this pass either way — it could
    // not see the row disagreeing with the confirm card it had just cleared,
    // which is exactly the bug that shipped (the row was seeded from the raw L7b
    // blob while the card used the engine projection).
    await expect(page.getByTestId('em-level-current')).toHaveText(SEEDED_EM_LEVEL);

    await page.getByTestId('em-level-adjust').click();

    // The save is not armed until the change is real AND a reason is given —
    // no validation scolding, the control simply is not live yet.
    const save = page.getByTestId('em-level-save');
    await expect(save).toBeDisabled();
    // DOWNWARD on purpose. A doctor disagreeing with a level disagrees in both
    // directions, and the copy on the confirm card that follows used to say "up
    // from" unconditionally — a downgrade rendered as an upgrade on the last
    // card before a signature.
    //
    // 99212, not 99213: the fixture's unacknowledged record was raised FROM
    // 99213, and the route carries that baseline forward, so setting 99213 would
    // land back on the reviewed level and correctly clear the gate instead of
    // arming it. Two levels down is unambiguously a change.
    const target = '99212';
    await page.getByTestId('em-level-select').selectOption(target);
    await expect(save, 'still disabled with no reason').toBeDisabled();
    await page.getByTestId('em-level-reason').fill('Exam and MDM documented at this level.');
    await expect(save).toBeEnabled();
    await save.click();

    // THE GATE DID NOT WEAKEN. Setting a level is not attesting to one: the
    // same confirm card the model's own re-scores raise comes back, and the
    // signature is blocked until it is answered.
    const gate = page.getByTestId('review-doc-em-gate');
    await expect(gate).toBeVisible({ timeout: 30_000 });
    await expect(gate).toContainText(target);
    // WAS: `expect(sign).toBeDisabled()` + `expect(BAR).toContainText(…)`. The
    // count went back UP — from one term (the attestation) to two — which is the
    // arithmetic behind "an adjusted level must be confirmed before signing".
    await expectRail(
      page,
      'Review & sign · 2 blockers',
    );

    // NO DIRECTION IN THE COPY. This adjustment went DOWN; the card must not
    // describe it as going up, and must not argue for the level at all.
    const gateText = (await gate.innerText()).toLowerCase();
    expect(gateText).not.toMatch(/\bup from\b|\bdown from\b|\bsupports\b|\bhigher\b|\blower\b/);
    expect(gateText).toContain('changed from');

    // …and it is a real BLOCK, not just a number: the flow re-opens on E/M and
    // the signature is once again out of reach. This is the half a count alone
    // cannot prove — `n` could rise while the gate flow happily walked past it.
    await openGateFlow(page);
    await expectGateStep(page, 'em');
    await expect(page.getByTestId('rounds-gate-lock')).toContainText(
      '1 documentation level outstanding',
    );
    await expectSignatureUnreachable(page);

    await page.getByTestId('review-doc-em-confirm').click();
    // WAS: `expect(sign).toBeEnabled()`. Confirming clears the step, the flow
    // advances, and the signature exists — disabled until attested, then live.
    await expect(page.getByTestId('rounds-gate-lock')).toHaveCount(0);
    await page.getByTestId('rounds-gate-next').click();
    await expectGateStep(page, 'attestation');
    await expect(signTrigger(page)).toBeDisabled();
    await page.getByTestId('rounds-gate-attest').click();
    await expect(signTrigger(page)).toBeEnabled();

    // And the row — back on the paper, where the doctor reads it — now states
    // the level they chose. Closed first, so this is measured on the stage and
    // not on a node the flow had borrowed.
    await page.getByTestId('rounds-gate-close').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveCount(0);
    await expect(page.getByTestId('em-level-current')).toHaveText(target);
  });

  test('re-checking the level does NOT take the level row away', async ({ page }) => {
    // Seeded STALE, so the re-check control is present by construction. A
    // conditional `if (await control.count())` here would report success for
    // having found nothing to click, which is how this whole class of bug
    // survives a green suite.
    // Stale AND no pending change: the stale gate renders only when there is
    // nothing already awaiting confirmation, so seeding both hid the very
    // control this test drives.
    test.skip(
      !(await open(page, 'rdoc-12', { emStale: true, emPending: false })),
      'psql seeding unavailable',
    );

    const row = page.getByTestId('review-doc-em-level');
    await expect(row).toBeVisible();
    await expect(page.getByTestId('em-level-current')).toHaveText(SEEDED_EM_LEVEL);

    const recheck = page.getByTestId('review-doc-em-rescore');
    await expect(recheck, 'a stale visit must offer the re-check').toBeVisible();
    await recheck.click();

    // THE REGRESSION THIS EXISTS FOR. The client read the new level out of the
    // "did it move" field, so a re-check that found no movement — the ordinary
    // outcome, and the guaranteed one when the level has not changed — set the
    // level to null and unmounted the whole row: the level text AND the Adjust
    // button, i.e. the only place a doctor can disagree with the level, gone
    // until a full page reload.
    await expect(row, 'the level row must survive a no-move re-check').toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId('em-level-adjust')).toBeVisible();
    // The level still reads as a real code — never blank, never absent.
    await expect(page.getByTestId('em-level-current')).toHaveText(/^\d{5}$/);
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
    // Clear the gate, then sign with DOCX selected and assert the download
    // actually starts — "signed" without a file is the failure this surface
    // exists to make impossible. (There were two gates until ruling #109.)
    await page.getByTestId('review-doc-em-confirm').click();

    // ⚠️ `openSignFlow` FITS HERE and does not fit four tests above: both gates
    // in front of the signature are clear, so the flow opens ON the attestation
    // and the helper's walk (rail → tick → the bar's Sign & Download) completes.
    // Re-pointed from a page-level `getByRole('button', /sign & download/i)`,
    // which under Rounds resolves to nothing until Gate 3 is showing.
    await openSignFlow(page);

    // ⚠️ NOT `getByRole('dialog')`. The gate flow carries `role="dialog"` too
    // (`gate-flow.tsx:228`) and both are open at this moment, so the role query
    // goes strict-mode ambiguous. "Download DOCX" is defined once in the whole
    // app (`sign-and-send-modal.tsx:47`) and lives only inside the modal, so it
    // identifies the modal's controls without a container at all.
    await page.getByRole('button', { name: /^download docx$/i }).click();
    // The modal keeps its OWN E/M confirmation, and it remains the enforcement:
    // the inline card is an additional visible blocker in front of it, never a
    // replacement. Two acknowledgements for a billing-level change is the
    // deliberate design, so the test acknowledges twice too.
    const modalEm = page.getByTestId('em-change-confirm-toggle');
    if (await modalEm.count()) await modalEm.click();

    // dispatchEvent, not click(): submitting triggers a download, and the
    // actionability check never settles behind one even though the button
    // reports visible/enabled/stable. The real handler still runs — this
    // bypasses Playwright's wait, not the application.
    const download = page.waitForEvent('download', { timeout: 60_000 });
    await attestAndSubmit(page);
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/\.(docx|pdf)$/);
  });

  // =====================================================================
  // THE SPECIALTY MATRIX — every core review-doc spec, once per specialty
  // class.
  // ---------------------------------------------------------------------
  // Added 2026-07-28 after a regression that CI could not have caught. The
  // pack was entirely primary-care, so the E/M surface was only ever
  // exercised in the direction where it EXISTS. When `emStale` was wired
  // through, an edited ultrasound report began demanding "Re-check the
  // documentation level above" — for a level the same page correctly
  // refuses to show. It took a hand-run production smoke to see it.
  //
  // `emApplies` is the one switch. Each spec below asserts the SAME
  // invariant from both sides, so a specialty-conditional surface cannot be
  // half-tested again: what must be present for an office visit must be
  // ABSENT for an imaging report, and the reverse.
  // =====================================================================
  for (const cls of REVIEW_DOC_CLASSES) {
    test.describe(`${cls.label} (${cls.key})`, () => {
      /** Every E/M control on this surface, in one place — so "absent" means
       *  all of them and a newly added one has to be classified. */
      const EM_SURFACE = [
        'review-doc-em-level',
        'em-level-current',
        'em-level-adjust',
        'review-doc-em-gate',
        'review-doc-em-stale-gate',
        'review-doc-em-rescore',
      ];

      test('renders as the document', async ({ page }) => {
        test.skip(
          !(await open(page, `mx-doc-${cls.key}`, { specialtyClass: cls.key })),
          'psql seeding unavailable',
        );
        await expect(page.locator('.qm-c3-rev2-tabs')).toHaveCount(0);
        await expect(page.getByTestId('review-document-view')).toBeVisible();
        // Read-only paper, both classes: no edit pills, no worksheet panels.
        await expect(page.locator('[data-testid^="section-edit-"]')).toHaveCount(0);
        await expect(page.locator('.qm-rdoc-meta-panels')).toHaveCount(0);
        await expect(page.locator('.qm-c3-bill-card')).toHaveCount(0);
        await expect(page.locator('.qm-lin-coding-rail-slot')).toHaveCount(0);
      });

      test(`the E/M surface is ${cls.emApplies ? 'PRESENT' : 'ABSENT'}`, async ({ page }) => {
        const seeded = await open(page, `mx-em-${cls.key}`, { specialtyClass: cls.key });
        test.skip(!seeded, 'psql seeding unavailable');

        if (cls.emApplies) {
          await expect(page.getByTestId('review-doc-em-level')).toBeVisible();
          await expect(page.getByTestId('em-level-current')).toHaveText(SEEDED_EM_LEVEL);
          await expect(page.getByTestId('em-level-adjust')).toBeVisible();
          // The fixture seeds an unacknowledged change, so the gate is up.
          await expect(page.getByTestId('review-doc-em-gate')).toBeVisible();
        } else {
          // NOT ONE OF THEM. An imaging report has no office-visit level, so
          // there is nothing to show, nothing to adjust and nothing to confirm.
          for (const id of EM_SURFACE) {
            await expect(page.getByTestId(id), `${id} must not exist on ${cls.key}`).toHaveCount(0);
          }
          // And no prose about one either — the bar included, which is where the
          // regression actually spoke to the doctor.
          await expect(page.locator('body')).not.toContainText(/documentation level/i);
          await expect(page.locator('body')).not.toContainText(/\b992\d\d\b/);
        }
      });

      test('the prescription gate is ABSENT — on every specialty (#109)', async ({ page }) => {
        test.skip(
          !(await open(page, `mx-rx-${cls.key}`, { specialtyClass: cls.key })),
          'psql seeding unavailable',
        );
        // ⚠️ THIS ROW USED TO BE A MATRIX ARM (`cls.hasRxGate ? 1 : 0`). Owner
        // ruling #109 collapsed it to a constant: the gate is gone for every
        // specialty, including the one that used to have it. Kept inside the
        // per-specialty loop deliberately — a single test on one specialty
        // would not notice the surface surviving on another, which is exactly
        // how the R4 cream panel hid.
        await expect(page.getByTestId('review-doc-rx-gate')).toHaveCount(0);
        // POSITIVE CONTROL — this specialty's page rendered at all.
        await expect(page.getByTestId('review-document-view')).toBeVisible();
      });

      test(`a stale note ${cls.emApplies ? 'asks for a re-check' : 'asks for NOTHING'}`, async ({
        page,
      }) => {
        // ⚠️ THE REGRESSION TEST. Seeded stale with no pending change, which is
        // exactly the state a note edit leaves behind — and the state in which an
        // ultrasound report demanded a re-check of a level it does not have.
        const seeded = await open(page, `mx-stale-${cls.key}`, {
          specialtyClass: cls.key,
          emStale: true,
          emPending: false,
        });
        test.skip(!seeded, 'psql seeding unavailable');

        // The bar names the NEXT blocker. An unresolved prescription warning
        // used to outrank the level and had to be cleared first; ruling #109
        // removed that gate, so the level is now the first thing named.

        if (cls.emApplies) {
          await expect(page.getByTestId('review-doc-em-stale-gate')).toBeVisible();
          await expect(page.getByTestId('review-doc-em-rescore')).toBeVisible();
          // WAS: `expect(BAR).toContainText(/documentation level/i)` — the
          // footer bar's "Re-check the documentation level above". The bar is
          // gone; the same sentence is the stale gate's own heading, which is
          // where the doctor now reads it. Asserted as exact text rather than
          // the old case-insensitive fragment.
          await expect(page.getByTestId('review-doc-em-stale-gate')).toContainText(
            'Documentation level needs re-checking',
          );
        } else {
          await expect(
            page.getByTestId('review-doc-em-stale-gate'),
            'an imaging report has no level to re-check',
          ).toHaveCount(0);
          await expect(page.getByTestId('review-doc-em-rescore')).toHaveCount(0);
          // The surface must not name a blocker that cannot be cleared.
          //
          // ⚠️ WIDENED FROM `BAR` TO `body`, AND THAT IS THE POINT. With the
          // footer bar unreachable, `expect(BAR).not.toContainText(…)` would
          // resolve to ZERO nodes and pass for free — a negative assertion whose
          // subject does not exist proves nothing, and it would have gone on
          // reporting green while the regression this test was written for
          // (an ultrasound demanding a level re-check) reappeared anywhere else
          // on the page. The office half above is the positive control for the
          // same words.
          await expect(page.locator('body')).not.toContainText(/documentation level/i);
          await expect(page.locator('body')).not.toContainText(/re-check/i);
        }
      });

      if (!cls.emApplies) {
        test('EXPORTS NO OFFICE E/M EVEN WHEN THE ROW WRONGLY CARRIES ONE', async ({
          page,
        }, testInfo) => {
          // THE EXPORT-LAYER GUARD, end to end, on the artifact fixture.
          //
          // Compute and store were guarded; export was not. `loadVisitExportData`
          // projected `cptCodes.em` unconditionally and both renderers print
          // `em.code` when truthy, so an imaging row that had ALREADY acquired a
          // blob printed an office code. One unsigned production row did — a
          // doctor-set 99212 whose EHR line read "99212 — undefined".
          //
          // A clean fixture cannot test this: it would pass with no guard at all.
          // So this one is seeded WITH code + override + signedCode, and the
          // assertion is on the exported BYTES, not on the screen.
          const seeded = await open(page, `mx-exportguard-${cls.key}`, {
            specialtyClass: cls.key,
            imagingEmArtifact: true,
          });
          test.skip(!seeded, 'psql seeding unavailable');

          // The row really is dirty — otherwise this test proves nothing.
          const blob = psqlOne(
            `select "cptCodes"->'em'->>'code' || '|' ||
                    ("cptCodes"->'em'->'override'->>'code') || '|' ||
                    ("cptCodes"->'em'->>'signedCode')
               from transcribe_visits where id = '${seeded!.visitId}'`,
          );
          expect(blob, 'the artifact fixture must actually carry the blob').toBe(
            '99213|99212|99214',
          );

          // And the screen shows none of it (the UI guard, already covered above,
          // re-checked here so a failure localises to export vs render).
          await expect(page.locator('body')).not.toContainText(/\b992\d\d\b/);

          // Export BOTH formats and read the artifacts as text.
          //
          // Downloads are collected from an event listener registered BEFORE the
          // submit, not two sequential waitForEvent calls: the second call can be
          // registered after its download already fired, which reads as a 60s
          // timeout and looks like a broken export rather than a racing test.
          const downloads: import('@playwright/test').Download[] = [];
          page.on('download', (d) => downloads.push(d));

          // ⚠️ RE-POINTED. This fixture's ONLY gate is the attestation — an
          // imaging report has no Rx gate and no E/M gate, and `emArtifact` is
          // false here because the row carries a `cptCodes` blob but NO pending
          // change (`sign-gates.ts:231` needs both). So the flow opens straight
          // on Gate 3 and `openSignFlow` walks it. A page-level
          // `getByRole('button', /sign & download/i)` matched nothing: the
          // trigger exists only inside Gate 3.
          await openSignFlow(page);

          // Toggles, not commands: PDF is pressed by default, so a blind click
          // DESELECTS it. Press only what is not already pressed.
          //
          // ⚠️ NO `getByRole('dialog')` CONTAINER — the gate flow carries that
          // role as well (`gate-flow.tsx:228`) and both are open here, so the
          // query is strict-mode ambiguous. Anchored on the exact labels
          // instead, which are defined once in the app and only in this modal.
          for (const label of [/^download pdf$/i, /^download docx$/i]) {
            const btn = page.getByRole('button', { name: label });
            if ((await btn.getAttribute('aria-pressed')) !== 'true') await btn.click();
          }
          for (const label of [/^download pdf$/i, /^download docx$/i]) {
            await expect(
              page.getByRole('button', { name: label }),
              `${label} must be selected before submitting`,
            ).toHaveAttribute('aria-pressed', 'true');
          }

          // dispatchEvent, not click(): the actionability check never settles
          // behind a download, and the dialog is taller than the viewport.
          await attestAndSubmit(page);

          await expect
            .poll(() => downloads.length, {
              message: 'expected a PDF and a DOCX from the sign submit',
              timeout: 90_000,
            })
            .toBeGreaterThanOrEqual(2);

          const files = downloads.slice(0, 2);
          expect(
            files.map((f) => f.suggestedFilename().replace(/^.*\./, '')).sort(),
            'one PDF and one DOCX',
          ).toEqual(['docx', 'pdf']);

          for (const f of files) {
            const path = await f.path();
            expect(path, `no path for ${f.suggestedFilename()}`).toBeTruthy();
            // Non-vacuity marker: a heading from the seeded imaging note, which
            // both artifacts render. NOT the patient name — exports anonymise
            // PHI ("PATIENT Anonymous"), and that mistake is exactly what this
            // check is for: it turned a wrong marker into a loud failure instead
            // of letting an absence assertion run against text I had misread.
            const text = await extractExportText(
              path!,
              f.suggestedFilename(),
              'EXAM TYPE',
            );
            // THE ASSERTION. Not "no 99212" — no office E/M code at all, in
            // either artifact, from a row that holds three of them.
            expect(
              text,
              `${f.suggestedFilename()} leaked an office E/M code from an imaging row`,
            ).not.toMatch(/\b992\d\d\b/);
          }

          await testInfo.attach('exported-filenames', {
            body: files.map((f) => f.suggestedFilename()).join('\n'),
          });
        });

        test('NO office E/M is computed, stored, or exported', async ({ page }) => {
          const seeded = await open(page, `mx-store-${cls.key}`, {
            specialtyClass: cls.key,
          });
          test.skip(!seeded, 'psql seeding unavailable');

          // The page has now RENDERED — which is where `emScoredCode` gets
          // seeded for a visit that has none. That render is the exact writer
          // the label-vs-id bug turned loose on every ultrasound visit, so
          // asserting after it is the assertion that matters.
          assertImagingHasNoEm(seeded!.visitId);

          // Then the artifact. The signed export is what outlives every UI
          // decision, so it gets checked as text rather than trusted.
          const dl = page.waitForEvent('download', { timeout: 60_000 });
          // Re-pointed with the export-guard test above, same cause, same shape:
          // the attestation is this visit's only gate, so `openSignFlow` reaches
          // the modal, and the modal's controls are found by their unique labels
          // rather than through an ambiguous `role="dialog"`.
          await openSignFlow(page);
          await page.getByRole('button', { name: /^download docx$/i }).click();
          const modalEm = page.getByTestId('em-change-confirm-toggle');
          await expect(modalEm, 'nothing to confirm on an imaging report').toHaveCount(0);
          await attestAndSubmit(page);
          const file = await dl;
          expect(file.suggestedFilename()).toMatch(/\.(docx|pdf)$/);

          // …and the level never appeared at sign time either.
          assertImagingHasNoEm(seeded!.visitId);
        });
      }
    });
  }
});
