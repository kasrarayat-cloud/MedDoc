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

/** Every E/M control the PAPER renders, in one place — so "absent" means all of
 *  them and a newly added one has to be classified rather than quietly escaping
 *  the imaging invariant. Kept identical to `review-document.spec.ts`'s list on
 *  purpose: that pack proves the same suppression on the `:review-doc` image,
 *  and this one proves it survives the Rounds composition, which ADOPTS these
 *  nodes out of the paper and into the gate flow. */
const EM_SURFACE = [
  'review-doc-em-level',
  'em-level-current',
  'em-level-adjust',
  'review-doc-em-gate',
  'review-doc-em-stale-gate',
  'review-doc-em-rescore',
];

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

  async function open(
    page: import('@playwright/test').Page,
    tag: string,
    seedOpts: {
      specialtyClass?: ReviewDocClass;
      emPending?: boolean;
      imagingEmPending?: boolean;
      chiefComplaint?: string;
      patient?: { dob?: string; externalId?: string };
    } = {},
  ) {
    const { email } = await signupFreshUser(page, tag);
    const seeded = requireSeed(seedReviewDocVisit(email, seedOpts), tag);
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

    // The fixture is clean, so there is nothing anomalous to name.
    //
    // ⚠️ THIS ASSERTION ALONE PROVES NOTHING and the companion test below is
    // what makes it mean something. Every imaging fixture hard-nulls
    // `emPendingChange`, and `emArtifact` is set ONLY when that column is
    // non-null on a non-applicable specialty — so this passes against a build
    // with the anomaly rendering deleted entirely. Absence is only evidence
    // when presence has been shown to be reachable.
    await expect(page.getByTestId('rounds-strip-em-artifact')).toHaveCount(0);

    // The imaging fixture has no medications and no E/M — attestation only.
    //
    // ⚠️ THIS IS NOT A NET FOR A MIS-BUILT IMAGE, and it used to claim it was.
    // The old comment here said a missing NEXT_PUBLIC_ULTRASOUND_SPECIALTY
    // would make this read 2. It would not. B2's ruling made the E/M gate
    // EXIST wherever the specialty applies but COUNT only when the server would
    // refuse, and this fixture nulls `emPendingChange` — so with the flag off
    // the gate is pushed with `unresolved: 0` and the count is still 1. The
    // assertion passes either way. A false claim about what a test would catch
    // is worse than no claim: it is the reason the next reader stops looking.
    // The real nets are `rounds-gates.spec.ts` (no E/M STEP on imaging) and
    // `gate-flag-coverage.test.ts` (the flag is on the image at all).
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      '1',
    );
    await expect(page.getByTestId('rounds-critical-band')).toHaveCount(0);

    // ── "no E/M gate ANYWHERE" includes the PAPER, and nothing checked it ──
    // The clause is absolute, and the Rounds packs only ever asserted the
    // skin's OWN surfaces — the strip marker, the flow's step, the signed
    // banner. The in-paper E/M stack was covered exclusively by
    // `review-document.spec.ts`, which runs on the `:review-doc` image: a
    // different build that does not carry NEXT_PUBLIC_SKIN_ROUNDS. So a
    // flag-ON composition that lost the imaging suppression while the flag-OFF
    // original kept it would satisfy every guard in the repo — and the Rounds
    // gate flow ADOPTS these very nodes out of the paper, so the flag-ON
    // composition genuinely is not the flag-OFF one. This pack's own header
    // names that risk; until now it answered it with a renderer count.
    for (const id of EM_SURFACE) {
      await expect(
        page.getByTestId(id),
        `${id} must not exist on an imaging visit, flag-ON`,
      ).toHaveCount(0);
    }
    await expect(page.getByTestId('rounds-stage')).not.toContainText(/documentation level/i);
    await expect(page.getByTestId('rounds-stage')).not.toContainText(/\b992\d\d\b/);
  });

  test('the in-paper E/M surface IS present on primary care — flag-ON', async ({
    page,
  }) => {
    // The presence half. Without it the absence loop above is satisfied by a
    // build where the paper renders no E/M controls at all, in either
    // specialty — which is the same defect class the strip's anomaly marker
    // needed its own companion for.
    const seeded = await open(page, 'stage-5c');
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('review-doc-em-level')).toBeVisible();
    await expect(page.getByTestId('em-level-adjust')).toBeVisible();
    // The fixture seeds an unacknowledged change, so the in-paper gate is up.
    await expect(page.getByTestId('review-doc-em-gate')).toBeVisible();
  });

  test('THE COMPANION — an imaging visit that DOES carry office E/M names it', async ({
    page,
  }) => {
    // The production defect, reproduced: five imaging visits acquired office E/M
    // state and sat there two days. The invariant forbids drawing an E/M GATE
    // for them, but `POST /sign` is not specialty-conditioned and WILL refuse —
    // so the strip names the anomaly rather than rendering a clean zero and
    // walking the doctor into a 400 they were not warned about.
    //
    // This is the presence half. Without it the absence assertion above is
    // satisfied by a build that cannot produce the marker at all.
    const seeded = await open(page, 'stage-5b', {
      specialtyClass: 'imaging',
      imagingEmPending: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    await expect(page.getByTestId('rounds-strip-em-artifact')).toHaveCount(1);
    // And STILL no E/M gate — the invariant is absolute even when the data is
    // wrong. Naming the anomaly is not the same as growing a gate for it.
    await expect(page.getByTestId('rounds-review-sign')).toHaveAttribute(
      'data-blockers',
      '1',
    );
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

  // ── 9. Close, THEN scroll — asserted on ORDER, not on geometry ──────────
  test('a chat navigation lands AFTER the drawer is gone', async ({ page }) => {
    // THE FAILURE THIS EXISTS FOR: the handler fires, the scroll runs while the
    // overlay is still mounted, the chat says "took you to the E/M gate", and
    // nothing the doctor can see has moved.
    //
    // THE FIRST VERSION OF THIS TEST ASSERTED THE WRONG PROPERTY, and CI was
    // right to reject it. It used `not.toBeInViewport()` while the drawer was
    // open — but that matcher measures geometric intersection with the viewport,
    // NOT occlusion. The drawer covers the gate; the gate is still inside the
    // viewport rectangle, so it reported "viewport ratio 1" and failed against a
    // correct implementation. A scroll-position assertion is no better here: the
    // seeded note is short enough that the whole document fits on screen, so
    // `scrollIntoView` on an already-centred element is a no-op.
    //
    // The contract is not "the gate becomes visible". It is "the scroll is
    // issued only once the overlay is gone" — an ORDER, not a geometry. So
    // instrument the call and assert the order, which no layout can invalidate
    // and which still fails on the original bug.
    const seeded = await open(page, 'stage-9');
    test.skip(!seeded, 'psql seeding unavailable');

    type ScrollEntry = { target: string | null; drawerOpen: boolean };

    await page.evaluate(() => {
      const log: ScrollEntry[] = [];
      (window as unknown as { __scrollLog: ScrollEntry[] }).__scrollLog = log;
      const original = Element.prototype.scrollIntoView;
      Element.prototype.scrollIntoView = function patched(
        this: Element,
        ...args: unknown[]
      ) {
        log.push({
          target: this.getAttribute('data-chat-target'),
          // The drawer UNMOUNTS on close, so its presence in the DOM is exactly
          // its open state — no separate signal to get out of step.
          drawerOpen: !!document.querySelector(
            '[data-testid="rounds-chat-drawer"]',
          ),
        });
        return (original as (...a: unknown[]) => void).apply(this, args);
      } as typeof Element.prototype.scrollIntoView;
    });

    const gateScrolls = () =>
      page.evaluate(() =>
        (window as unknown as { __scrollLog: ScrollEntry[] }).__scrollLog.filter(
          (e) => e.target === 'em_gate',
        ),
      );

    await page.getByTestId('rounds-chat-trigger').click();
    const drawer = page.getByTestId('rounds-chat-drawer');
    await expect(drawer).toBeVisible();

    // MOCKSCROLL is a mock-only directive; the real model path burns tokens and
    // lives in an .eval.spec.ts.
    await drawer.getByRole('textbox').fill('MOCKSCROLL em_gate');
    await drawer.getByRole('textbox').press('Enter');
    await expect(drawer).toContainText(/took you to the em gate/i);

    // HALF ONE — the reply has arrived and the gate has NOT been scrolled to.
    // This is the half that goes red on a synchronous scroll.
    expect(await gateScrolls()).toEqual([]);
    await expect(drawer).toBeVisible();

    await page.getByTestId('rounds-chat-close').click();
    await expect(page.getByTestId('rounds-chat-drawer')).toHaveCount(0);

    // HALF TWO — it happened, exactly once, and with the drawer already gone.
    await expect.poll(async () => (await gateScrolls()).length).toBe(1);
    expect((await gateScrolls())[0].drawerOpen).toBe(false);
  });

  // ── 10. One control can start a signature ────────────────────────────────
  test('the signing bar does not exist on the stage — only inside the gate flow', async ({
    page,
  }) => {
    // ⚠️ THIS TEST INVERTED IN R1, AND THE OLD ASSERTION WAS THE BUG.
    //
    // It used to assert `toHaveCount(1)` on the stage and call that "exactly one
    // control can start a signature". One is the right number of signing
    // controls; it was the wrong number of them ON THIS SCREEN. The Rounds rail
    // and the embedded footer were both visible, and they DISAGREED — measured
    // on production 2026-08-02, one clean READY visit, one moment:
    //
    //     action rail   "Review & sign · 1 blocker"
    //     footer        "Reviewed"   Sign & Download  disabled=false
    //
    // The rail's N counts every applicable gate including `attestation`; the
    // footer's `blocked` was `rxBlocking || emBlocking` and had no `attested`
    // term. So the enabled button signed straight past the attestation — and
    // `sign-gates.ts` marks that gate `serverEnforced: false`, so nothing behind
    // it caught the bypass.
    //
    // The bar is now ABSENT until the flow adopts it, not hidden: a hidden
    // button is still focusable, still clickable, still announced.
    const seeded = await open(page, 'stage-10');
    test.skip(!seeded, 'psql seeding unavailable');

    // THE FIX, STATED AS THE ASSERTION: nothing on the stage can start a
    // signature.
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(0);

    // NON-VACUITY. A zero over a page that failed to render is not a pass, so
    // prove the stage is really here and really unsigned first.
    await expect(page.getByTestId('rounds-action-rail')).toHaveCount(1);
    await expect(page.getByTestId('review-document-view')).toHaveCount(1);
    const rail = page.getByTestId('rounds-review-sign');
    await expect(rail).toBeVisible();

    // AND THE CONTRADICTION CANNOT RECUR: whatever the rail claims, there is no
    // second control on screen making a different claim about the same visit.
    const blockers = Number((await rail.getAttribute('data-blockers')) ?? '0');
    expect(
      blockers,
      'the fixture is meant to reach the stage with at least the attestation ' +
        'gate open — with zero blockers this test could not tell the fix from ' +
        'a visit that had nothing to gate',
    ).toBeGreaterThan(0);
    await expect(page.getByTestId('review-doc-bar-msg')).toHaveCount(0);

    // Walk the flow to the step that hosts it.
    await rail.click();
    await expect(page.getByTestId('rounds-gate-flow')).toBeVisible();
    for (let i = 0; i < 4; i += 1) {
      if (await page.getByTestId('rounds-gate-attest').count()) break;
      const next = page.getByTestId('rounds-gate-next');
      if (!(await next.count()) || (await next.isDisabled())) break;
      await next.click();
    }
    await expect(page.getByTestId('rounds-gate-attest')).toHaveCount(1);

    // NOW it exists — exactly once, and inside the flow rather than the paper.
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(1);
    await expect(
      page.getByTestId('rounds-gate-flow').getByTestId('review-doc-signbar'),
      'the bar must be INSIDE the flow — if it rendered back in the paper the ' +
        'count would still be 1 and the bypass would be back',
    ).toHaveCount(1);

    // And closing puts the stage back to having no signing control at all.
    await page.getByTestId('rounds-gate-close').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveCount(0);
    await expect(page.getByTestId('review-doc-signbar')).toHaveCount(0);
    await expect(page.getByTestId('review-document-view')).toHaveCount(1);
  });
});
