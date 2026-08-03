// ============================================================================
// ROUNDS — Gate A E2E: the Board.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md Screen 1. Runs against the flag-ON image only; with
// NEXT_PUBLIC_SKIN_ROUNDS off the route 404s, which is itself asserted so a
// mis-built image fails loudly instead of silently skipping the whole pack.
//
// What is worth an E2E rather than a unit test: that the real queue, the real
// filters and the real search reach the real component. The row model's rules
// are already unit-tested; this proves the wiring.
// ============================================================================

import { expect, test } from '@playwright/test';

import { signupFreshUser } from '../helpers/signup';
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';
import { cleanupTestUsers } from '../helpers/cleanup';

test.afterEach(() => {
  cleanupTestUsers();
});

/** ⚠️ A SEED THAT FAILED IS A DEFECT IN CI, NOT A SKIP. `test.skip(!seeded)`
 *  alone lets a broken fixture exit 0 on a pack that measured nothing — the
 *  failure mode B3 found in eleven never-run tests. Hoisted to module scope in
 *  R2 (it was nested inside one describe) so every block in this file uses the
 *  same rule rather than a second copy of it. */
function requireSeed<T>(seeded: T | null, what: string): T | null {
  if (seeded) return seeded;
  if (process.env.CI) {
    throw new Error(`seeding FAILED for ${what}. In CI this is a defect, not a skip.`);
  }
  return null;
}

test('the board renders for an invited clinician', async ({ page }) => {
  await signupFreshUser(page, 'board');
  await page.goto('/board');

  // A brand-new account has no visits — the empty state is the correct render,
  // and it must invite rather than shrug.
  await expect(page.getByTestId('rounds-board-empty')).toBeVisible();

  // ⚠️ R2 RENAMED THIS FROM "Start a visit". SPEC.md's copy register is
  // "actions keep their names end-to-end", and `/visits/new` is called "New
  // visit" from `/patients`, `/visits` and a patient's own page — this empty
  // state was the only surface in the product using a different verb for it.
  // ⚠️ ON AN EMPTY BOARD THERE ARE **TWO** — the top bar's primary and the
  // empty state's — so a bare role locator is a strict-mode violation, not a
  // missing element. That is the correct product behaviour and the reason this
  // test is the right place to pin the pair: it is the only state where both
  // mounts are on screen at once.
  const empty = page.getByTestId('rounds-new-visit-empty');
  const bar = page.getByTestId('rounds-new-visit-bar');
  await expect(page.getByRole('link', { name: /new visit/i })).toHaveCount(2);
  await expect(empty).toBeVisible();
  await expect(bar).toBeVisible();
  // ONE action, so one destination. Two CTAs that drifted apart would be the
  // board's own version of the two-sign-controls defect.
  await expect(empty).toHaveAttribute('href', '/visits/new');
  await expect(bar).toHaveAttribute('href', '/visits/new');

  // And the old name is GONE, not merely joined — otherwise a state rendering
  // both labels would satisfy the assertions above.
  await expect(page.getByRole('link', { name: /start a visit/i })).toHaveCount(0);

  // "Two mounts, exactly one shortcut" is observable only here. Two
  // document-level listeners on `n` means one press queues two navigations.
  await expect(bar).toHaveAttribute('data-shortcut', 'n');
  // ABSENT, not empty: the component passes `undefined` when it does not own
  // the key, so React omits the attribute entirely. `toHaveAttribute(…, /^$/)`
  // would fail here for the right reason and read like the wrong one.
  await expect(page.getByTestId('rounds-new-visit-empty')).not.toHaveAttribute(
    'data-shortcut',
  );
});

test('the chrome carries the shipped capabilities', async ({ page }) => {
  await signupFreshUser(page, 'board-chrome');
  await page.goto('/board');

  // SEARCH AND PAGINATION SURVIVE — the spec is explicit that the designs'
  // bans lose to shipped features. If a future redesign quietly drops the
  // search box, this fails.
  await expect(page.getByTestId('rounds-search')).toBeVisible();

  // All six filters, and they are links so the view is shareable.
  for (const f of ['active', 'signed', 'soap', 'ultrasound', 'critical', 'failed']) {
    await expect(page.getByTestId(`rounds-filter-${f}`)).toBeVisible();
  }

  await expect(page.getByTestId('rounds-day-meter')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
});

test('a filter narrows the queue and survives a reload', async ({ page }) => {
  await signupFreshUser(page, 'board-filter');
  await page.goto('/board');
  await page.getByTestId('rounds-filter-signed').click();
  await expect(page).toHaveURL(/filter=signed/);

  // The filter is in the URL, so a reload keeps it — which is what makes a
  // board view something a clinician can bookmark or send to a colleague.
  await page.reload();
  await expect(page.getByTestId('rounds-filter-signed')).toHaveAttribute(
    'aria-current',
    'true',
  );
});

test('search is a GET, so the result is linkable', async ({ page }) => {
  await signupFreshUser(page, 'board-search');
  await page.goto('/board');
  await page.getByTestId('rounds-search').fill('nobody-matches-this');
  await page.getByRole('button', { name: /^search$/i }).click();

  await expect(page).toHaveURL(/q=nobody-matches-this/);
  // No results is the empty state, not a broken board.
  await expect(page.getByTestId('rounds-board-empty')).toBeVisible();
});

test('the flag gates the route — a flag-OFF build has no board', async ({
  page,
}) => {
  // Deliberately asserted from the POSITIVE side in this pack: the pack only
  // runs on the flag-ON image, so reaching /board proves the image really is
  // flag-ON. A flag-OFF image would 404 here and fail the whole pack loudly,
  // rather than passing a suite that never exercised Rounds at all.
  await signupFreshUser(page, 'board-flag');
  const res = await page.goto('/board');
  expect(res?.status()).toBe(200);
});

test.describe('the ultrasound filter splits on the ID, not the label', () => {
  // THE ONLY SPECIALTY-CONDITIONAL BEHAVIOUR ON /board is
  //   const isImaging = (s) => !emAppliesToSpecialty(s)
  // and until now it had ZERO end-to-end coverage in either direction: every
  // board test seeds no visits at all and asserts the empty state, and the unit
  // test injects `isImaging` as a STUB.
  //
  // That is exactly the seam that once made every ultrasound visit compute and
  // PERSIST an office E/M level — a display LABEL was fed to a comparator that
  // takes an id, so the comparison was permanently false and nothing threw. A
  // stubbed predicate cannot see that; only a real row with a real specialty
  // column can.
  //
  // Both directions are asserted, because "the imaging visit appears under
  // Ultrasound" alone is satisfied by a filter that lets EVERYTHING through.

  test('an imaging visit is under Ultrasound and a SOAP visit is not', async ({ page }) => {
    const { email } = await signupFreshUser(page, 'board-imaging');
    const soap = requireSeed(seedReviewDocVisit(email, { idSalt: 'q' }), 'soap');
    const imaging = requireSeed(
      seedReviewDocVisit(email, { idSalt: 'r', specialtyClass: 'imaging' }),
      'imaging',
    );
    test.skip(!soap || !imaging, 'psql seeding unavailable');

    await page.goto('/board?filter=ultrasound');
    await expect(page.getByTestId(`rounds-lane-card-${imaging!.visitId}`)).toBeVisible();
    await expect(page.getByTestId(`rounds-lane-card-${soap!.visitId}`)).toHaveCount(0);

    // And the complement — a filter that passed everything would satisfy the
    // assertion above and fail this one.
    await page.goto('/board?filter=soap');
    await expect(page.getByTestId(`rounds-lane-card-${soap!.visitId}`)).toBeVisible();
    await expect(page.getByTestId(`rounds-lane-card-${imaging!.visitId}`)).toHaveCount(0);
  });
});

// ── R2 — the entrance honours prefers-reduced-motion, PROVEN BOTH WAYS ───────
//
// ⚠️ AN ABSENCE ASSERTION ALONE IS WORTHLESS HERE, and this pack has the scar
// tissue to say so. "No animation under reduced motion" is satisfied by a card
// that has no animation at all, by a selector that matches nothing, and by a
// stylesheet that failed to load. So the reduced-motion case is asserted
// BESIDE its own positive control, in the same file, against the same element:
// motion present by default, absent when asked. Neither half means anything
// without the other.
test.describe('the board entrance honours reduced motion', () => {
  /** Computed motion on the first marker card. */
  async function motionOf(page: import('@playwright/test').Page, testid: string) {
    return page.evaluate((id) => {
      const el = document.querySelector<HTMLElement>(`[data-testid="${id}"]`);
      if (!el) return null;
      const cs = getComputedStyle(el);
      const secs = (v: string) =>
        v.split(',').map((s) => {
          const t = s.trim();
          return t.endsWith('ms') ? parseFloat(t) / 1000 : parseFloat(t) || 0;
        });
      return {
        animationName: cs.animationName,
        // The longest declared duration, in seconds.
        animationDuration: Math.max(...secs(cs.animationDuration), 0),
        transitionDuration: Math.max(...secs(cs.transitionDuration), 0),
      };
    }, testid);
  }

  test('motion is PRESENT by default — the positive control', async ({ page }) => {
    const { email } = await signupFreshUser(page, 'board-motion-on');
    const v = requireSeed(seedReviewDocVisit(email, { idSalt: 'm1' }), 'motion-on');
    test.skip(!v, 'psql seeding unavailable');

    await page.goto('/board');
    const id = `rounds-lane-card-${v!.visitId}`;
    await expect(page.getByTestId(id)).toBeVisible();

    const m = await motionOf(page, id);
    expect(m, 'the card was not found — the reduced-motion case below would ' +
      'have passed for that reason alone').not.toBeNull();
    expect(
      m!.animationName,
      'no entrance animation is declared at all, so the reduced-motion ' +
        'assertion below proves nothing',
    ).toContain('qm-rounds-card-in');
    expect(m!.animationDuration).toBeGreaterThan(0);
    expect(
      m!.transitionDuration,
      'no hover/press transition is declared — same problem',
    ).toBeGreaterThan(0);
  });

  test('motion is ABSENT under prefers-reduced-motion', async ({ browser }) => {
    // A separate context: the emulation must be in place BEFORE first paint,
    // and toggling it on a live page leaves the already-started animation
    // running — which would read as "the rule does not work".
    const ctx = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    try {
      const { email } = await signupFreshUser(page, 'board-motion-off');
      const v = requireSeed(seedReviewDocVisit(email, { idSalt: 'm2' }), 'motion-off');
      test.skip(!v, 'psql seeding unavailable');

      await page.goto('/board');
      const id = `rounds-lane-card-${v!.visitId}`;
      await expect(page.getByTestId(id)).toBeVisible();

      const m = await motionOf(page, id);
      expect(m, 'the card was not found — this assertion would be vacuous').not.toBeNull();
      expect(
        m!.animationName,
        'the entrance still runs with reduced motion requested',
      ).toBe('none');
      expect(
        m!.transitionDuration,
        'the hover/press transition still runs with reduced motion requested',
      ).toBe(0);

      // AND THE CARD IS STILL THERE. This is the failure the CSS is written to
      // avoid: an entrance that hides the element and relies on an animation to
      // reveal it leaves a board of INVISIBLE cards the moment the animation is
      // dropped — a doctor's patient list, gone, with nothing reporting an
      // error. The `from` keyframe carries the hidden state for exactly this
      // reason, and this asserts it worked.
      const opacity = await page.evaluate(
        (t) => getComputedStyle(document.querySelector(`[data-testid="${t}"]`)!).opacity,
        id,
      );
      expect(
        Number(opacity),
        'reduced motion left the card invisible — the hidden state escaped the ' +
          'keyframe onto the element',
      ).toBe(1);
    } finally {
      await ctx.close();
    }
  });
});
