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
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';
import { signupFreshUser } from '../helpers/signup';

const AXE_CDN = 'https://cdn.jsdelivr.net/npm/axe-core@4.10.0/axe.min.js';

interface AxeEntry {
  id: string;
  impact: 'minor' | 'moderate' | 'serious' | 'critical' | null;
  help: string;
  nodeCount: number;
  /** CSS targets, so a failure can be ADJUDICATED rather than just counted.
   *  A contrast hit on a Rounds token and one on an inherited Linear surface
   *  are different findings with different owners, and a bare count cannot
   *  tell them apart.
   *
   *  ⚠️ NOT TRUNCATED. This was `.slice(0, 8)` — a DISPLAY truncation that was
   *  also the SOLE input to the ownership decision, so a Rounds-owned node
   *  sorting past the 8th was reclassified as inherited and could never block.
   *  It vanished from both the blocking summary and the inherited log, because
   *  the log filters the already-truncated array. Truncation now happens where
   *  it belongs — at the print site. */
  targets: string[];
  /** OWNERSHIP, DECIDED IN THE DOM RATHER THAN ON THE SELECTOR STRING.
   *
   *  axe names an element by `#id`, or by `tag[attr]` when that is unique, and
   *  short-circuits without ever climbing to an ancestor class. So
   *  `qm-rounds-*` is absent from the selector for precisely the elements this
   *  skin renders ITSELF — the attestation checkbox (`gate-flow.tsx`) carries
   *  no class at all, and a `data-testid` is enough for axe to stop there.
   *  A regex over the selector therefore cannot see the one control the flow
   *  authors, which is the element class axe most exists to catch.
   *
   *  THE RULE: the nearest ancestor-or-self carrying ANY class decides. Every
   *  composed component brings its own classes (`.qm-lin-rx-row`,
   *  `.qm-warn-override-btn`, `.cell > .l`), so it answers for itself; a bare
   *  element resolves to the Rounds container that placed it. Not
   *  `closest('[data-testid^="rounds-"]')` — the paper renders INSIDE
   *  `rounds-stage`, so that would claim every inherited violation on the
   *  screen and quietly convert this into a gate over other people's code. */
  owned: boolean;
}
interface AxeRun {
  violations: AxeEntry[];
  incomplete: AxeEntry[];
  /** Focusable elements sitting inside an `aria-hidden` container Rounds owns.
   *
   *  axe files `aria-hidden-focus` as INCOMPLETE — "I could not determine" —
   *  and the previous pass adjudicated it by hand: zero focusable elements, on
   *  the states it could reach. That was true, and it is the wrong SHAPE of
   *  answer: a hand adjudication is only true of the day it was made, and the
   *  attestation step was not among the states reached. Probing it makes the
   *  adjudication executable, so it re-answers itself on every run.
   *
   *  ⚠️ EMPTY BY CONSTRUCTION WHILE A MODAL IS OPEN, and that is not a hole —
   *  it is a different question, asked below. When the override dialog opens,
   *  the dialog primitive marks the rest of the document `aria-hidden` and
   *  traps focus inside itself. That is the CORRECT pattern, and a probe that
   *  flagged it would be reporting the whole stage — every rail button, the
   *  peek link, the chat trigger — as an accessibility defect on a screen
   *  behaving exactly as intended. The first version of this probe did exactly
   *  that, on 18 elements. */
  ariaHiddenFocusable: string[];
  /** What replaces the probe while a modal owns the screen: the trap itself.
   *  Skipping a check and asserting nothing in its place is how a state ends up
   *  measured by nothing at all. */
  modal: { open: boolean; focusInside: boolean; label: string };
}

/** Inject axe and return BOTH buckets. */
async function runAxe(page: Page): Promise<AxeRun> {
  return page.evaluate(async (cdnUrl) => {
    interface AxeWindow extends Window {
      __rounds_axe__?: boolean;
      axe?: {
        run: (
          ctx: Document,
          opts: { resultTypes: string[] }
        ) => Promise<{
          violations: Array<{ id: string; impact: string | null; help: string; nodes: Array<{ target?: string[] }> }>;
          incomplete: Array<{ id: string; impact: string | null; help: string; nodes: Array<{ target?: string[] }> }>;
        }>;
      };
    }
    const w = window as unknown as AxeWindow;
    if (!w.__rounds_axe__) {
      const script = document.createElement('script');
      script.src = cdnUrl;
      await new Promise<void>((resolve, reject) => {
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`axe-core CDN load failed: ${cdnUrl}`));
        document.head.appendChild(script);
      });
      w.__rounds_axe__ = true;
    }
    const res = await w.axe!.run(document, { resultTypes: ['violations', 'incomplete'] });

    /** The nearest ancestor-or-self carrying ANY class decides ownership. */
    const ownedByDom = (start: Element | null): boolean => {
      let cur: Element | null = start;
      while (cur && cur !== document.documentElement) {
        const raw = cur.getAttribute('class') ?? '';
        if (raw.trim().length > 0) return /qm-rounds-/.test(raw);
        cur = cur.parentElement;
      }
      return false;
    };
    const resolve = (target?: string[]): Element | null => {
      if (!target || target.length === 0) return null;
      // The LAST entry is the innermost frame's selector.
      const sel = target[target.length - 1];
      if (typeof sel !== 'string') return null;
      try {
        return document.querySelector(sel);
      } catch {
        return null;
      }
    };

    const project = (xs: typeof res.violations) =>
      xs.map((v) => ({
        id: v.id,
        impact: v.impact as AxeEntry['impact'],
        help: v.help,
        nodeCount: v.nodes.length,
        targets: v.nodes.flatMap((n) => n.target ?? []),
        owned: v.nodes.some((n) => {
          // Belt and braces: a selector that literally names a Rounds class is
          // the element's OWN class, so the two rules agree where both apply.
          if ((n.target ?? []).some((t) => /qm-rounds-/.test(t))) return true;
          return ownedByDom(resolve(n.target));
        }),
      }));
    // The aria-hidden-focus probe. Scoped to containers Rounds OWNS, for the
    // same reason the violation gate is: a composed component's own
    // `aria-hidden` is not this item's to answer for.
    const FOCUSABLE =
      'a[href],button,input,select,textarea,summary,iframe,[tabindex],[contenteditable="true"]';

    // Is a modal standing? Visible, not merely present — a closed dialog is
    // still in the DOM in several of these components.
    const dialogs = [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(
      (d) => (d as HTMLElement).offsetParent !== null || d.getAttribute('data-state') === 'open',
    );
    const openDialog = dialogs[0] ?? null;
    const modal = {
      open: openDialog !== null,
      focusInside: openDialog ? openDialog.contains(document.activeElement) : false,
      label: openDialog
        ? openDialog.getAttribute('aria-label') ??
          openDialog.getAttribute('data-testid') ??
          openDialog.className ??
          'dialog'
        : '',
    };

    const ariaHiddenFocusable: string[] = [];
    document.querySelectorAll('[aria-hidden="true"]').forEach((container) => {
      const raw = container.getAttribute('class') ?? '';
      if (!/qm-rounds-/.test(raw)) return;
      // While a modal is open the rest of the document is SUPPOSED to be
      // aria-hidden. See the note on `ariaHiddenFocusable`.
      if (modal.open) return;
      container.querySelectorAll(FOCUSABLE).forEach((el) => {
        // `tabindex="-1"` is not focusable by the keyboard, which is the thing
        // the rule protects. Anything else inside aria-hidden is a trap: it can
        // be tabbed to and is not announced.
        if (el.getAttribute('tabindex') === '-1') return;
        if ((el as HTMLElement).hasAttribute('disabled')) return;
        ariaHiddenFocusable.push(
          `${raw.split(/\s+/)[0]} >> ${el.tagName.toLowerCase()}` +
            (el.getAttribute('data-testid') ? `[${el.getAttribute('data-testid')}]` : ''),
        );
      });
    });

    return {
      violations: project(res.violations),
      incomplete: project(res.incomplete),
      ariaHiddenFocusable,
      modal,
    };
  }, AXE_CDN);
}

/**
 * Gate-blocking = critical or serious, ON A SURFACE ROUNDS OWNS.
 *
 * NO RULE-ID ALLOWLIST — the shared sweep filters `color-contrast` out entirely
 * as tracked Linear-dark debt, and inheriting that would give a gate that cannot
 * fail on the one class this skin has already failed twice.
 *
 * But the Rounds screens COMPOSE existing components — the Rx card, the warnings
 * rail, the paper — and those carry their own pre-existing violations that
 * failed here on the first run: `.qm-lin-rx-row` (nested-interactive),
 * `.qm-warn-override-btn`, `.qm-lin-rx-rail-group-n`, `.cell > .l`. Those are
 * real, and they are not this item's to fix: they are on the flag-OFF surface
 * too, unchanged, and a reskin that silently rewrote them would be changing the
 * shipped product under cover of a skin.
 *
 * So OWNERSHIP is the filter, not the rule id. A violation blocks when any of
 * its targets names a `qm-rounds-*` class. Everything else is REPORTED by state
 * and selector so it can be triaged as its own item — counted, named, and not
 * quietly dropped.
 */
const ROUNDS_OWNED = /qm-rounds-/;
/** Computed in the page, where the ELEMENT is reachable — see `AxeEntry.owned`.
 *  Reading `e.targets` here is what made the attestation checkbox invisible to
 *  the gate. */
const isRoundsOwned = (e: AxeEntry) => e.owned;
const blocking = (v: AxeEntry[]) =>
  v.filter(
    (x) => (x.impact === 'critical' || x.impact === 'serious') && isRoundsOwned(x)
  );
const inheritedBlocking = (v: AxeEntry[]) =>
  v.filter(
    (x) => (x.impact === 'critical' || x.impact === 'serious') && !isRoundsOwned(x)
  );

type Finding = { state: string; width: number; entry: AxeEntry };

test.describe('Rounds — axe across every surface, flag-ON', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const incomplete: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  const untrapped: Array<{ state: string; width: number; label: string }> = [];
  /** How many states were measured with a modal standing. If this is 0 the
   *  trap assertion below is vacuous, and says so. */
  let modalStates = 0;

  /**
   * Capture the state, alongside the axe pass that is already standing there.
   *
   * ⚠️ WHERE THESE MAY LIVE IS A RULE, NOT A PREFERENCE. A screenshot of a
   * rendered note is a rendered note. AGENTS.md treats a filled clinical export
   * as PHI "regardless of whether the patient is real or synthetic" — the
   * posture deliberately does not depend on knowing which, because by the time
   * you are asking, the file already exists somewhere it should not.
   *
   * So they go to a gitignored directory, swept by the close-out, and CI
   * uploads them as a run ARTIFACT. They are never committed, and the ledger
   * cites the run rather than a path in the repository.
   *
   * ⚠️ NOT UNDER `test-results/`, AND THAT IS THE WHOLE POINT.
   *
   * This wrote to `test-results/rounds-shots/` and the files could never
   * survive a green run. Playwright's runner pushes `createRemoveOutputDirsTask`
   * into global setup, which `fs.rm(outputDir, {recursive: true, force: true})`
   * before the first test — and with no `outputDir` override every project
   * shares `test-results`. FOUR further `playwright test` invocations run after
   * this pack (review-doc, doc-preview, visit-doc, phi-reject+rx-safety), so the
   * first of them deleted the captures. The upload step could not have saved
   * them either: it is `if: failure()`, and `page.screenshot({path})` registers
   * no `testInfo` attachment, so nothing reaches the always-uploaded HTML
   * report. The clause was being discharged by files nobody could ever open.
   *
   * `rounds-shots/` is outside every project's `outputDir`, so no runner task
   * touches it, and e2e.yml uploads it `if: always()`. `gate-shot-durability`
   * pins both halves.
   */
  const SHOT_DIR = 'rounds-shots';
  async function shoot(page: Page, state: string, width: number) {
    await page.screenshot({
      path: `${SHOT_DIR}/${state.replace(/[^a-z0-9]+/gi, '-')}@${width}.png`,
      fullPage: true,
    });
  }

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
