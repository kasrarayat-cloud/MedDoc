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
      /** R4.1 — an imaging visit that DOES carry prescriptions. The default
       *  imaging fixture writes none, which is why the owner's cream panel was
       *  unrenderable in every automated environment. */
      imagingWithRx?: boolean;
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

  // ── R4.1 — THE Rx SURFACE IS ROUNDS-TREATED ON EVERY PATH ────────────────
  test('R4.1 — the Rx surface renders hosted, on the owner\'s own fixture', async ({
    page,
  }) => {
    // ⚠️ THE GUARD FOR A CLASS THE CENSUS CANNOT SEE. R3.4 hosted ONE of three
    // `RxTab` mounts and verified it on the stage — correctly, and
    // incompletely. The owner then found the cream panel on a path that walk
    // never rendered: an ULTRASOUND visit whose plan orders anticoagulation.
    //
    // Two things had to be true for that to hide:
    //   · the imaging fixture wrote `rxDrafts: null`, so no seeded imaging
    //     visit could show an Rx surface at all;
    //   · QA runs MOCK_AI, whose pipeline writes no rxDrafts either — measured:
    //     every visit in the QA database had `rxDrafts IS NULL`.
    // So the panel was unrenderable in every automated environment, and a route
    // walk reported it clean because it was never on screen. This test RENDERS
    // the state rather than walking to it.
    const seeded = await open(page, 'stage-r41', {
      specialtyClass: 'imaging',
      imagingWithRx: true,
    });
    test.skip(!seeded, 'psql seeding unavailable');

    // NON-VACUITY FIRST: an Rx surface must actually be on screen, or every
    // assertion below is about an element that is not there.
    const anyRx = page.locator('[class*="qm-lin-rx-"]').first();
    await expect(
      anyRx,
      'no Rx surface rendered — the fixture no longer produces one, and this ' +
        'test would pass by measuring nothing',
    ).toBeVisible();

    // THE ASSERTION: hosted, on this path, without a per-caller wrapper.
    const hosted = await page.evaluate(() => {
      const el = document.querySelector('[class*="qm-lin-rx-"]') as HTMLElement | null;
      return el ? !!el.closest('.qm-rounds-host') : null;
    });
    expect(
      hosted,
      'the Rx surface is not inside a qm-rounds-host — a legacy cream panel is ' +
        'rendering on a Rounds route, which is the R4 defect',
    ).toBe(true);

    // ⚠️ AND THE CLINICAL BEHAVIOUR IS UNCHANGED, which is the half a reskin
    // must never quietly cost. Both advisory classes on this fixture are
    // CORRECT and must survive un-softened: the plan orders anticoagulation
    // without naming an agent, so the prescription is `unclear` and the
    // advisory says so. A reskin that "cleaned up" either would be a clinical
    // regression wearing new paint.
    const body = await page.locator('body').innerText();
    expect(
      /unclear/i.test(body),
      'the unclear action disappeared — the agent is genuinely unspecified and ' +
        'the surface must keep saying so',
    ).toBe(true);
    expect(
      /agent not specified/i.test(body),
      'the advisory text was softened or dropped',
    ).toBe(true);
  });

  // ── R3.3 — THE RAIL IS REACHABLE WHILE THE PAPER SCROLLS ─────────────────
  test('R3.3 — the action rail is visible at the TOP and the BOTTOM of a long paper', async ({
    page,
  }) => {
    // ⚠️ THE PRIOR ATTEMPT AT THIS SHIPPED AND WAS REVERTED, so this test is
    // written against the failure mode rather than the feature. Pinning the
    // rail once trapped the chat drawer's `position: fixed` scrim, and the
    // symptom was NOT an invisible rail — it was `rounds-chat-close` reporting
    // "visible, enabled and stable" while swallowing every click. So visibility
    // alone would have passed on the reverted build. This asserts the rail is
    // reachable AND that the overlay it used to trap still works.
    const seeded = await open(page, 'stage-r33');
    test.skip(!seeded, 'psql seeding unavailable');

    for (const width of [1440, 1024]) {
      await page.setViewportSize({ width, height: 800 });
      const rail = page.getByTestId('rounds-action-rail');
      const sign = page.getByTestId('rounds-review-sign');

      // TOP of the paper.
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect(rail, `@${width}: rail not visible at the top`).toBeInViewport();

      // NON-VACUITY: a page too short to scroll would satisfy both checks
      // trivially, and every stage fixture would "pass" a docking test on a
      // build with no docking at all.
      const scrollable = await page.evaluate(
        () => document.documentElement.scrollHeight - window.innerHeight,
      );
      expect(
        scrollable,
        `@${width}: the paper does not scroll, so this proves nothing about a ` +
          'docked rail — seed a longer note or shrink the viewport',
      ).toBeGreaterThan(200);

      // BOTTOM of the paper.
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(250);
      await expect(rail, `@${width}: rail not visible after scrolling`).toBeInViewport();
      await expect(sign, `@${width}: the primary scrolled out of reach`).toBeInViewport();
    }

    // ── AND THE OVERLAY THE OLD ATTEMPT TRAPPED STILL WORKS ────────────────
    // This is the half that would have caught the revert. The rail is sticky;
    // the drawer is portalled to <body> so the rail cannot be its containing
    // block. If someone re-adds `backdrop-filter` or a taller `z-index` to the
    // rail, the close button goes back to being visible and unclickable.
    await page.setViewportSize({ width: 1440, height: 800 });
    await page.getByTestId('rounds-chat-trigger').click();
    await expect(page.getByTestId('rounds-chat-drawer')).toBeVisible();
    const scrimParent = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="rounds-chat-scrim"]');
      return el?.parentElement?.tagName.toLowerCase() ?? '(none)';
    });
    expect(
      scrimParent,
      'the chat overlay is no longer a direct child of <body> — a positioned ' +
        'rail can trap it again, which is exactly how the last pinning attempt ' +
        'failed',
    ).toBe('body');
    await page.getByTestId('rounds-chat-close').click();
    await expect(page.getByTestId('rounds-chat-drawer')).toHaveCount(0);
  });

  // ── 10. EXACTLY ONE control can start a signature, and it is not on the stage ──
  test('the stage carries NO signature control — the rail and the gates are the only path', async ({
    page,
  }) => {
    // ⚠️ THIS TEST HAS BEEN THREE DIFFERENT CLAIMS. Read the history before
    // changing it again, because two of the three were wrong on this screen.
    //
    // 1. ORIGINALLY it asserted `toHaveCount(1)` on the signing bar and called
    //    that "exactly one control can start a signature". One is the right
    //    number; it was the wrong claim about this screen. The rail and the
    //    embedded footer were BOTH live and they DISAGREED — measured on
    //    production 2026-08-02, one clean READY visit, one moment:
    //
    //        action rail   "Review & sign · 1 blocker"
    //        footer        "Reviewed"    Sign & Download   disabled=false
    //
    //    The footer's `blocked` had no `attested` term, so the enabled button
    //    signed straight past the attestation.
    //
    // 2. R1 COUPLED THEM (`signGateBlockers`) and this test became "the two
    //    cannot contradict each other" — the footer-agrees guard. That closed
    //    the bypass and left the duplication: a second sign control still sat
    //    pinned to the stage.
    //
    // 3. R2 RE-HOMED THE BAR into Gate 3, so the claim returns to ABSENCE —
    //    which is what it should have been able to say all along.
    //    THE FOOTER-AGREES GUARD IS RETIRED WITH THE FOOTER, deliberately and
    //    on the record (docs/rounds/RELAY.md, R2 row). It is not weakened and
    //    not silently dropped: it asserted a relationship between two controls,
    //    and there is now one control, so the relationship has no referent. Its
    //    replacement is strictly stronger — a bar that cannot be reached cannot
    //    disagree with anything.
    const seeded = await open(page, 'stage-10', { specialtyClass: 'imaging' });
    test.skip(!seeded, 'psql seeding unavailable');

    const rail = page.getByTestId('rounds-review-sign');
    await expect(rail).toBeVisible();

    // NON-VACUITY, FIRST. An absence assertion over a page that failed to load
    // is true and worthless. The stage must be present AND have something to
    // gate, or "no sign control here" proves nothing.
    const blockers = Number((await rail.getAttribute('data-blockers')) ?? '0');
    expect(
      blockers,
      'the fixture must reach the stage with at least one gate open (the ' +
        'attestation is always applicable) or this proves nothing',
    ).toBeGreaterThan(0);
    await expect(page.getByTestId('review-document-view')).toHaveCount(1);

    // THE ASSERTION. Zero signature controls on the stage itself.
    await expect(
      page.getByTestId('review-doc-signbar'),
      'the legacy sign bar is back on the stage — R2 re-homed it into Gate 3, ' +
        'and `hostSignbar` is what keeps it there',
    ).toHaveCount(0);

    // And nothing else grew one. A `Sign` button anywhere outside the gate flow
    // is the same defect wearing a different testid — this is the half that
    // survives someone re-adding the control under a new name.
    await expect(
      page.getByRole('button', { name: /sign & download/i }),
      'a Sign & Download control is reachable on the stage without opening the gates',
    ).toHaveCount(0);

    // ── AND IT IS NOT MERELY HIDDEN ─────────────────────────────────────────
    // `toHaveCount(0)` is satisfied by `display: none` too, and a hidden-but-
    // mounted button is still a second path. Assert ABSENCE FROM THE DOM, which
    // is the claim being made.
    const mounted = await page.evaluate(
      () => document.querySelectorAll('[data-testid="review-doc-signbar"]').length,
    );
    expect(mounted, 'the sign bar is mounted but hidden — that is not removal').toBe(0);

    // ── THE OTHER HALF: it exists where it SHOULD ───────────────────────────
    // Absence alone is satisfied by deleting the signature outright, which
    // would be a far worse bug with the same green tick. Walk to the
    // attestation and prove the one control is there, and disabled while the
    // gate is open.
    await rail.click();
    await expect(page.getByTestId('rounds-gate-flow')).toBeVisible();
    for (let i = 0; i < 4; i += 1) {
      if (await page.getByTestId('rounds-gate-attest').count()) break;
      const next = page.getByTestId('rounds-gate-next');
      if (!(await next.count()) || (await next.isDisabled())) break;
      await next.click();
    }
    await expect(
      page.getByTestId('rounds-gate-signbar-host').getByTestId('review-doc-signbar'),
      'the signature is not inside Gate 3 either — it has been lost, not re-homed',
    ).toHaveCount(1);

    const signBtn = page
      .getByTestId('review-doc-signbar')
      .getByRole('button', { name: /sign & download/i });
    await expect(signBtn).toHaveCount(1);
    await expect(
      signBtn,
      'the attestation is unticked and the signature is enabled',
    ).toBeDisabled();

    // ⇔ THE OTHER DIRECTION. "Disabled while blocked" alone is satisfied by a
    // button that is ALWAYS disabled — a different bug, same green tick.
    if (await page.getByTestId('rounds-gate-attest').count()) {
      await page.getByTestId('rounds-gate-attest').check();
      await expect(
        rail,
        'attesting did not drop the rail count — the overlay is not recomputing',
      ).toHaveAttribute('data-blockers', '0');
      await expect(
        signBtn,
        'the rail says zero blockers and the signature is STILL disabled',
      ).toBeEnabled();
    }

    // Closing returns to a stage with no signature control, not to a restored
    // footer. The four failed removals all died on the way BACK.
    await page.getByTestId('rounds-gate-close').click();
    await expect(page.getByTestId('rounds-gate-flow')).toHaveCount(0);
    await expect(
      page.getByTestId('review-doc-signbar'),
      'closing the gate flow put a sign bar back on the stage',
    ).toHaveCount(0);
    await expect(
      page.getByTestId('review-document-view'),
      'the paper did not survive the gate flow closing — this is the exact ' +
        'symptom of the DOM-adoption conflict the four prior removals hit',
    ).toHaveCount(1);
  });
});
