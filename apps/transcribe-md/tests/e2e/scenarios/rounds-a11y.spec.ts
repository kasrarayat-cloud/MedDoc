// ============================================================================
// ROUNDS — Gate B: axe across every Rounds surface, FLAG-ON.
// ----------------------------------------------------------------------------
// AXE HAS NEVER RUN AGAINST A ROUNDS SURFACE. `tests/e2e/a11y.spec.ts` sweeps
// routes under the `a11y` project, and `.github/workflows/a11y.yml` builds the
// app with plain `npm run build` and three NEXT_PUBLIC_* vars — none of them the
// skin flag. So the board, the stage, the gate flow and the signed screen have
// never been measured, including the `<main>` landmark change B1 made precisely
// because AppFrame already owns one.
//
// This pack runs on the `:rounds` image the e2e workflow ALREADY builds, so it
// costs a recreate rather than a second build — and it deliberately does NOT
// touch a11y.yml, which is a required check on every unrelated PR and would then
// be sweeping the whole product in a skin production is not running.
//
// THREE DECISIONS THAT DECIDE WHETHER THIS GATE MEANS ANYTHING:
//
//  1. `color-contrast` IS NOT ALLOWLISTED HERE. The shared sweep filters it out
//     as tracked design debt on the Linear-dark palette — scoped, in its own
//     comment, to `text-3`/`text-4` across 400+ existing surfaces. The Rounds
//     palette is a NEW set of tokens that debt does not cover, and BOTH of A2's
//     non-ARIA defects were contrast. Inheriting the filter would give a gate
//     that cannot fail on the only class this skin has already failed twice.
//
//  2. `incomplete` IS REPORTED. The shared runner reads `violations` and
//     discards `incomplete` without logging it. That matters here specifically:
//     the skin paints `body` with a radial gradient and layers translucent
//     `color-mix` surfaces over it, which is exactly the composition axe
//     declines to compute and files as incomplete rather than as a pass.
//     Silence there would read as green.
//
//  3. IT IS NOT SERIAL, and it asserts ONCE. A per-state assertion stops at the
//     first failure, so enumerating N defects costs N CI cycles.
//
// A2 defect 4 asked for sampling across the animation cycle. Done — and its
// honest limit is stated where it is done, at the sampling site.
// ============================================================================

import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import {
  blocking,
  inheritedBlocking,
  runAxe,
  settleEntrances,
  shoot,
  type AxeRun,
  type Finding,
  ROUNDS_OWNED,
} from '../helpers/rounds-axe';
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';

// The axe harness — `runAxe`, the DOM ownership adjudicator inside it, the
// blocking/inherited split and the screenshot sink — lives in
// `helpers/rounds-axe.ts` so that this pack and `rounds-c1` share ONE rule.
// See that file's header for why the whole of `runAxe` had to move rather than
// just the regex the plan named.

test.describe('Rounds — axe across every surface, flag-ON', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const incomplete: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  const untrapped: Array<{ state: string; width: number; label: string }> = [];
  /** How many states were measured with a modal standing. If this is 0 the
   *  trap assertion below is vacuous, and says so. */
  let modalStates = 0;

  function record(state: string, width: number, run: AxeRun) {
    for (const e of blocking(run.violations)) violations.push({ state, width, entry: e });
    for (const e of inheritedBlocking(run.violations))
      inherited.push({ state, width, entry: e });
    for (const e of run.incomplete) incomplete.push({ state, width, entry: e });
    for (const sel of run.ariaHiddenFocusable) hiddenTraps.push({ state, width, sel });
    if (run.modal.open) {
      modalStates += 1;
      if (!run.modal.focusInside)
        untrapped.push({ state, width, label: run.modal.label });
    }
  }

  /**
   * Sample across the animation cycle. A2 defect 4: axe samples at an instant,
   * and text at 35% opacity mid-pulse really is unreadable at that instant.
   *
   * ⚠️ ITS HONEST LIMIT, stated where it is done: on THESE screens the only
   * continuous animation is a `transform: scale()` pulse on a 6px dot, and
   * axe's contrast rule does not read transform. So this sampling is correct
   * and cheap, but it is NOT re-testing A2 defect 4's class here — that was an
   * opacity pulse on TEXT, on the board's kicker, and it was fixed by moving
   * the motion onto a dot. Sampling is kept so a future re-introduction on any
   * of these surfaces is caught.
   */
  async function sampleAcrossAnimation(page: Page, state: string, width: number) {
    // ⚠️ SETTLE ONE-SHOT ENTRANCES FIRST — see `settleEntrances`. R2's card
    // entrance made axe return `incomplete` for every marker card on the first
    // sample, which is the gate silently ceasing to measure them. Infinite
    // animations (the REC pulse) are deliberately NOT awaited; the 3-sample
    // sweep below is what covers those, and it is unchanged.
    const settle = await settleEntrances(page);
    expect(
      settle.timedOut,
      `${state}@${width}: one-shot animations did not finish in 2s — axe is ` +
        'about to sample a moving surface and will report incomplete rather ' +
        'than measuring it',
    ).toBe(false);

    for (let i = 0; i < 3; i++) {
      record(state, width, await runAxe(page));
      if (i === 0) await shoot(page, state, width);
      if (i < 2) await page.waitForTimeout(550);
    }
  }

  function requireSeed<T>(seeded: T | null, what: string): T | null {
    if (seeded) return seeded;
    if (process.env.CI) {
      throw new Error(
        `seeding FAILED for ${what}. In CI this is a defect, not a skip — ` +
          'letting it skip would exit 0 on a sweep that measured nothing.',
      );
    }
    return null;
  }

  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  test('every Rounds surface is clean of serious and critical violations', async ({
    page,
  }) => {
    const { email } = await signupFreshUser(page, 'rounds-axe');
    const primary = requireSeed(seedReviewDocVisit(email, { idSalt: 'a' }), 'primary');
    const imaging = requireSeed(
      seedReviewDocVisit(email, { idSalt: 'b', specialtyClass: 'imaging' }),
      'imaging',
    );
    const signed = requireSeed(
      seedReviewDocVisit(email, { idSalt: 'c', signed: true, withCriticalOverride: true }),
      'signed',
    );
    test.skip(!primary || !imaging || !signed, 'psql seeding unavailable');

    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });

      // ── The board ────────────────────────────────────────────────────────
      await page.goto('/board');
      await expect(page.getByTestId('rounds-board')).toBeVisible();
      await sampleAcrossAnimation(page, 'board', width);

      // ── R3.1 / R3.2 — THE PATIENTS SURFACES ──────────────────────────────
      // ⚠️ ADDED BECAUSE THE GATE WAS GREEN ABOUT SURFACES IT NEVER WALKED.
      // This sweep covered board · stage · signed (and rounds-c1 covers auth,
      // settings and templates). `/patients` and `/patients/[id]` were swept by
      // NOTHING — so R3 could rebuild both and still report "axe zero
      // serious/critical", which would have been an answer about a set that
      // excluded the very screens the round changed.
      //
      // The roster's marker cards paint their own ground and their status lines
      // take `-text` status tokens, so they are exactly the pairing this file
      // records nine previous contrast failures for. They get measured now.
      await page.goto('/patients');
      await expect(page.getByTestId('rounds-patients')).toBeVisible();
      await sampleAcrossAnimation(page, 'patients', width);

      await page.goto(`/patients/${primary!.patientId}`);
      await expect(page.locator('body')).toBeVisible();
      await sampleAcrossAnimation(page, 'patient:detail', width);

      // ── The stage, primary-care ──────────────────────────────────────────
      await page.goto(`/visits/${primary!.visitId}`);
      await expect(page.getByTestId('rounds-stage')).toBeVisible();
      await sampleAcrossAnimation(page, 'stage:primary', width);

      // The chat drawer is an overlay with its own focus trap — a distinct DOM.
      await page.getByTestId('rounds-chat-trigger').click();
      await expect(page.getByTestId('rounds-chat-drawer')).toBeVisible();
      record('stage:chat-open', width, await runAxe(page));
      await shoot(page, 'stage:chat-open', width);
      await page.getByTestId('rounds-chat-close').click();

      // ── The stage, imaging — a DIFFERENT gate set, so a different tree ───
      await page.goto(`/visits/${imaging!.visitId}`);
      await expect(page.getByTestId('rounds-stage')).toBeVisible();
      record('stage:imaging', width, await runAxe(page));
      await shoot(page, 'stage:imaging', width);

      // ── The gate flow, every step ────────────────────────────────────────
      // A dialog behind a click, so a route-list sweep cannot reach it. Each
      // step is its own DOM: the blocked state, the cleared state, and the
      // attestation step all render different controls.
      //
      // ⚠️ A FRESH VISIT PER WIDTH. Clearing Gate 1 writes a REAL
      // RxWarningOverride row, so reusing one fixture across both widths meant
      // the second pass found "Overridden" where it expected "Override" and
      // timed out. The walk mutates its own fixture — every repetition of it
      // needs its own.
      const gateVisit = requireSeed(
        seedReviewDocVisit(email, { idSalt: `g${width}` }),
        `gate-walk@${width}`,
      );
      test.skip(!gateVisit, 'psql seeding unavailable');
      await page.goto(`/visits/${gateVisit!.visitId}`);
      await page.getByTestId('rounds-review-sign').click();
      await expect(page.getByTestId('rounds-gate-flow')).toBeVisible();
      record('gates:rx-blocked', width, await runAxe(page));
      await shoot(page, 'gates:rx-blocked', width);

      const host = page.getByTestId('rounds-gate-host-rx');
      await host.getByRole('button', { name: /override/i }).first().click();
      const dialog = page
        .locator('[role="dialog"]')
        .filter({ has: page.locator('#override-reason') });
      record('gates:override-modal', width, await runAxe(page));
      await shoot(page, 'gates:override-modal', width);
      await dialog
        .locator('#override-reason')
        .fill('Benefit outweighs risk; monitoring renal function weekly and patient counselled.');
      await dialog.getByRole('button', { name: /confirm override/i }).click();
      await expect(host).toContainText(/overridden/i);
      record('gates:rx-cleared', width, await runAxe(page));
      await shoot(page, 'gates:rx-cleared', width);

      await page.getByTestId('rounds-gate-next').click();
      await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'em');
      record('gates:em', width, await runAxe(page));
      await shoot(page, 'gates:em', width);

      // ── Gate 3, the attestation step ─────────────────────────────────────
      // GATE B SAYS "ALL GATES", AND THIS ONE WAS NEVER MEASURED. The walk
      // above ends at Gate 2 and jumped straight to the signed fixture, so the
      // summary rows, the attestation checkbox and the lock copy had never been
      // rendered under axe — and the checkbox is the ONLY form control the flow
      // authors itself, which is the element class axe most exists to catch.
      //
      // It is not that the walk chose to stop. On the default fixture the E/M
      // step BLOCKS (`rounds-gates.spec.ts` pins `rounds-gate-next` disabled
      // there), so it could not advance. Reaching Gate 3 needs a visit whose
      // E/M step is a pass-through, which is what `emPending:false` seeds — the
      // same door `rounds-gates.spec.ts` uses. A fresh visit again, for the
      // reason above: clearing Gate 1 writes a real override row.
      const attestVisit = requireSeed(
        seedReviewDocVisit(email, { idSalt: `t${width}`, emPending: false }),
        `attestation-walk@${width}`,
      );
      test.skip(!attestVisit, 'psql seeding unavailable');
      await page.goto(`/visits/${attestVisit!.visitId}`);
      await page.getByTestId('rounds-review-sign').click();
      await expect(page.getByTestId('rounds-gate-flow')).toBeVisible();
      const attestHost = page.getByTestId('rounds-gate-host-rx');
      await attestHost.getByRole('button', { name: /override/i }).first().click();
      const attestDialog = page
        .locator('[role="dialog"]')
        .filter({ has: page.locator('#override-reason') });
      await attestDialog
        .locator('#override-reason')
        .fill('Benefit outweighs risk; monitoring renal function weekly and patient counselled.');
      await attestDialog.getByRole('button', { name: /confirm override/i }).click();
      await expect(attestHost).toContainText(/overridden/i);
      await page.getByTestId('rounds-gate-next').click();
      await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute('data-step', 'em');
      await page.getByTestId('rounds-gate-next').click();
      await expect(page.getByTestId('rounds-gate-flow')).toHaveAttribute(
        'data-step',
        'attestation',
      );
      // Assert the step's OWN DOM is standing before measuring it — an axe pass
      // over a step that failed to render reports zero violations and reads
      // exactly like a clean one.
      await expect(page.getByTestId('rounds-gate-attest')).toBeVisible();
      await expect(page.getByTestId('rounds-gate-summary')).toBeVisible();
      record('gates:attestation', width, await runAxe(page));
      await shoot(page, 'gates:attestation', width);

      // ── The signed screen ────────────────────────────────────────────────
      await page.goto(`/visits/${signed!.visitId}`);
      await expect(page.getByTestId('rounds-signed')).toBeVisible();
      await sampleAcrossAnimation(page, 'signed', width);
    }

    // ── 1024: the stage only. The board collapses to one column below 1100px
    //    and hides the track by design, and the strip has its OWN breakpoint —
    //    borrowing the board's would have deleted the strip at this width, which
    //    is one of Gate B's two screenshot widths. ────────────────────────────
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.goto(`/visits/${primary!.visitId}`);
    await expect(page.getByTestId('rounds-stage')).toBeVisible();
    record('stage:primary@1024', 1024, await runAxe(page));
    await shoot(page, 'stage:primary', 1024);

    // ── ONE assertion, at the end ────────────────────────────────────────────
    // Collected rather than asserted per state, so a run enumerates every defect
    // instead of stopping at the first and costing a CI cycle per finding.
    // Truncation lives HERE, at the print site, and nowhere upstream of a
    // decision.
    const summary = violations
      .map(
        (f) =>
          `  ${f.state} @${f.width}: [${f.entry.impact}] ${f.entry.id} (${f.entry.nodeCount} node(s))\n` +
          f.entry.targets.slice(0, 8).map((t) => `      ${t}`).join('\n') +
          (f.entry.targets.length > 8
            ? `\n      … and ${f.entry.targets.length - 8} more`
            : ''),
      )
      .join('\n');

    // `incomplete` is REPORTED, never asserted on. axe files a check there when
    // it cannot compute an answer — most often contrast over a gradient, which
    // this skin paints on `body`. "I could not check" must be visible in the
    // log rather than silently counted as a pass; adjudication is a human call
    // recorded in the ledger, not a gate.
    // Pre-existing violations on the components Rounds composes. REPORTED, not
    // asserted — and reported with selectors so the follow-up item starts from
    // an inventory rather than a rediscovery.
    if (inherited.length > 0) {
      const byRule = new Map<string, Set<string>>();
      for (const f of inherited) {
        const set = byRule.get(f.entry.id) ?? new Set<string>();
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
        byRule.set(f.entry.id, set);
      }
      console.log(
        '[rounds-a11y] INHERITED serious/critical on composed components ' +
          '(pre-existing, present flag-OFF too, NOT this item to fix):\n' +
          [...byRule]
            .map(([id, sels]) => `  ${id}:\n${[...sels].map((t) => `      ${t}`).join('\n')}`)
            .join('\n'),
      );
    }

    if (incomplete.length > 0) {
      // Split by ownership. "axe could not determine" on a Rounds element is a
      // question this item must answer; on a composed one it is inherited.
      // Reporting a single total would bury the first inside the second.
      const mine = new Map<string, Set<string>>();
      const theirs = new Map<string, number>();
      for (const f of incomplete) {
        const owned = f.entry.targets.filter((t) => ROUNDS_OWNED.test(t));
        if (owned.length > 0) {
          const set = mine.get(f.entry.id) ?? new Set<string>();
          owned.forEach((t) => set.add(t));
          mine.set(f.entry.id, set);
        } else {
          theirs.set(f.entry.id, (theirs.get(f.entry.id) ?? 0) + 1);
        }
      }
      console.log(
        '[rounds-a11y] axe INCOMPLETE — ROUNDS-OWNED (adjudicate in the ledger):\n' +
          (mine.size === 0
            ? '  (none)\n'
            : [...mine]
                .map(([id, sels]) => `  ${id}:\n${[...sels].map((t) => `      ${t}`).join('\n')}`)
                .join('\n') + '\n') +
          '[rounds-a11y] axe INCOMPLETE — composed components (inherited):\n' +
          [...theirs].map(([id, n]) => `  ${id}: ${n} occurrence(s)`).join('\n'),
      );
    }

    expect(
      violations,
      `axe found serious/critical violations on ROUNDS-OWNED elements:\n${summary}`,
    ).toEqual([]);

    // The adjudication axe declined to make, made here instead — across every
    // state the walk visited, including the attestation step that no previous
    // pass reached.
    expect(
      hiddenTraps,
      'focusable elements inside an aria-hidden Rounds container — tabbable ' +
        'but not announced:\n' +
        hiddenTraps.map((t) => `  ${t.state} @${t.width}: ${t.sel}`).join('\n'),
    ).toEqual([]);

    // And the half that replaces the probe while a modal stands. Asserted with
    // its own boundary stated, because "no untrapped modals" is trivially true
    // on a walk that never opened one — which is the failure this whole pack
    // keeps finding in other people's checks.
    expect(modalStates, 'no state was measured with a modal open, so the ' +
      'focus-trap assertion below is vacuous').toBeGreaterThan(0);
    expect(
      untrapped,
      'a modal was open and focus was NOT inside it — the rest of the document ' +
        'is aria-hidden in that state, so a keyboard user is somewhere the ' +
        'screen reader says is not there:\n' +
        untrapped.map((t) => `  ${t.state} @${t.width}: ${t.label}`).join('\n'),
    ).toEqual([]);
  });

  // ── THE POSITIVE CONTROL ────────────────────────────────────────────────
  // Without this, a clean run and a run whose harness silently measures nothing
  // emit the IDENTICAL output — `violations: []`. That is this project's named
  // recurring defect in its exact canonical form: an answer about a set whose
  // boundary was never established. The only evidence the gate could ever fail
  // was a narrative in one commit body about three contrast defects that were
  // then fixed; after the fix, nothing standing would notice if axe stopped
  // being injected, if the CDN 404'd behind a caught error, or if the ownership
  // rule started classifying everything as inherited.
  //
  // It probes the WHOLE pipeline, not just axe: inject → run → project →
  // ownership → impact filter → `blocking()`. The same function the gate calls.
  test('the axe harness can actually fail — positive control', async ({ page }) => {
    const { email } = await signupFreshUser(page, 'rounds-axe-pc');
    const probe = requireSeed(seedReviewDocVisit(email, { idSalt: 'pc' }), 'positive-control');
    test.skip(!probe, 'psql seeding unavailable');

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/visits/${probe!.visitId}`);
    await expect(page.getByTestId('rounds-stage')).toBeVisible();

    // Clean first, on the very surface the probe will be planted in — so a
    // failure below is the probe and not the page.
    const before = blocking((await runAxe(page)).violations);
    expect(
      before,
      `the control's own surface must start clean:\n${before.map((e) => e.id).join(', ')}`,
    ).toEqual([]);

    // A Rounds-owned element with unreadable contrast: #777 on #888 is ~1.2:1,
    // far under AA, and `color-contrast` is serious. It carries a `qm-rounds-`
    // class, so BOTH ownership rules must claim it.
    await page.evaluate(() => {
      const el = document.createElement('p');
      el.className = 'qm-rounds-axe-positive-control';
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'positive control — deliberately unreadable';
      document.body.appendChild(el);
    });

    const withProbe = blocking((await runAxe(page)).violations);
    expect(
      withProbe.map((e) => e.id),
      'the harness did not catch a deliberately-planted serious violation on a ' +
        'Rounds-owned element — so a green run above proves nothing',
    ).toContain('color-contrast');

    // And a bare element with NO class of its own, inside a Rounds container:
    // the case the selector regex is blind to, and the shape of the attestation
    // checkbox. This is what the DOM ownership rule exists for.
    const bareCaught = await page.evaluate(() => {
      const host = document.querySelector('[class*="qm-rounds-"]');
      if (!host) return null;
      const el = document.createElement('p');
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.setAttribute('id', 'rounds-axe-bare-probe');
      el.textContent = 'bare probe — no class of its own';
      host.appendChild(el);
      return true;
    });
    expect(bareCaught, 'no qm-rounds-* container on the stage to plant into').toBe(true);

    const withBare = blocking((await runAxe(page)).violations);
    expect(
      withBare.some((e) => e.targets.some((t) => t.includes('rounds-axe-bare-probe'))),
      'a classless element inside a Rounds container was NOT claimed as ' +
        'Rounds-owned — the attestation checkbox is exactly this shape, and it ' +
        'would sit outside the gate',
    ).toBe(true);

    await cleanupTestUsers();
  });
});
