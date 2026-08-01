// ============================================================================
// The Rounds axe harness — ONE ownership rule, shared by every Rounds pack.
// ----------------------------------------------------------------------------
// Extracted from `rounds-a11y.spec.ts` when C1-d added a second pack. A COPY
// would have been the cheaper edit and the wrong one: the ownership rule below
// was got wrong once already, at real cost (B4), and a duplicated adjudicator
// decays the moment one of the two is fixed.
//
// ⚠️ WHY THE WHOLE OF `runAxe` MOVED, AND NOT JUST "THE ADJUDICATOR".
// The plan for this extraction named `ROUNDS_OWNED` as the thing to lift. It is
// not the adjudicator — it is a REPORTING regex, and lifting it alone would
// have shipped the log and left the gate behind. The real adjudicator is
// `ownedByDom`, declared INSIDE the `page.evaluate` callback, and a
// `page.evaluate` callback is serialised to the browser: it cannot close over
// a module-scope import. So `ownedByDom`, `resolve`, `project`, `FOCUSABLE`,
// the dialog scan and the aria-hidden probe can only move together, with
// `AXE_CDN` riding along as the evaluate argument.
//
// ⚠️ THIS FILE PULLS axe-core FROM A CDN AT RUN TIME (`AXE_CDN`). It is now on
// the critical path of TWO CI steps rather than one, and a jsdelivr outage
// surfaces as a pack-level error, not as an a11y result. Named here so the next
// red run is diagnosed in seconds rather than treated as a Rounds regression.
// ============================================================================

import type { Page } from '@playwright/test';

export const AXE_CDN = 'https://cdn.jsdelivr.net/npm/axe-core@4.10.0/axe.min.js';

export interface AxeEntry {
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
   *  screen and quietly convert this into a gate over other people's code.
   *
   *  ⚠️ THE COROLLARY C1-d PAID FOR, stated because it is invisible until a
   *  gate goes vacuously green: "the nearest classed ancestor decides" means a
   *  DENSELY CLASSED surface answers for itself all the way down. The auth
   *  shell classes every node it renders (`qm-c3-auth`, `-card`, `-form`, …),
   *  so putting `qm-rounds-host` on the outermost one buys NOTHING for the
   *  nodes inside it — the walk stops at `qm-c3-auth-form` and reports FALSE.
   *  That is why C1-d pairs a `qm-rounds-*` class onto the intermediate
   *  containers as well, and why the third positive-control case below exists. */
  owned: boolean;
}

export interface AxeRun {
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
export async function runAxe(page: Page): Promise<AxeRun> {
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
export const ROUNDS_OWNED = /qm-rounds-/;
/** Computed in the page, where the ELEMENT is reachable — see `AxeEntry.owned`.
 *  Reading `e.targets` here is what made the attestation checkbox invisible to
 *  the gate. */
export const isRoundsOwned = (e: AxeEntry) => e.owned;
export const blocking = (v: AxeEntry[]) =>
  v.filter(
    (x) => (x.impact === 'critical' || x.impact === 'serious') && isRoundsOwned(x)
  );
export const inheritedBlocking = (v: AxeEntry[]) =>
  v.filter(
    (x) => (x.impact === 'critical' || x.impact === 'serious') && !isRoundsOwned(x)
  );

export type Finding = { state: string; width: number; entry: AxeEntry };

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
 * the a11y pack (review-doc, doc-preview, visit-doc, phi-reject+rx-safety), so
 * the first of them deleted the captures. The upload step could not have saved
 * them either: it was `if: failure()`, and `page.screenshot({path})` registers
 * no `testInfo` attachment, so nothing reaches the always-uploaded HTML
 * report. The clause was being discharged by files nobody could ever open.
 *
 * `rounds-shots/` is outside every project's `outputDir`, so no runner task
 * touches it, and e2e.yml uploads it `if: always()`. `gate-shot-durability`
 * pins both halves — and now reads THIS file plus every `rounds-*` pack, by
 * traversal, rather than one spec by path.
 *
 * ⚠️ ORDERING CONSTRAINT ON THE WORKFLOW, which no unit can see: the upload
 * step runs immediately after the last Rounds pack. A pack added AFTER it
 * writes shots that nothing ever collects, and `if-no-files-found: error`
 * cannot catch that — the directory is non-empty from the earlier packs. New
 * Rounds packs go BEFORE the upload step.
 */
export const SHOT_DIR = 'rounds-shots';
export async function shoot(page: Page, state: string, width: number) {
  await page.screenshot({
    path: `${SHOT_DIR}/${state.replace(/[^a-z0-9]+/gi, '-')}@${width}.png`,
    fullPage: true,
  });
}
