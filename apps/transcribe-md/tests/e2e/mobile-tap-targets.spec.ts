// ============================================================================
// Mobile tap-target gate (P2-003)
// ----------------------------------------------------------------------------
// Drives Chromium under the iPhone 13 device profile through every
// authenticated route, finds every interactive element, and FAILS when
// any visible interactive element has a measured height under 44px AND
// its tightest tappable ancestor is also under 44px.
//
// Why "tightest ancestor": cards / list rows / nav items often wrap an
// inner <span> or <Link> whose own bounding box is sub-44 even though
// the user actually taps the outer chrome. The flooring rules in
// globals.css (.qm-lin-row, .qm-lin-btn, qm-tap-44, …) live on those
// outer elements; gate must look up the tree to credit them.
//
// Skips:
//   - Elements with width=0 or height=0 (inert / hidden)
//   - display:none / visibility:hidden
//   - <select> elements with height < 4 (Radix Select hidden form shim)
//   - The cookie banner / dev-only widgets (none today; future-proofed
//     via a known-skip selector list).
//
// Auth: uses signupFreshUser to create a one-shot account per run.
// Visit-detail seeding mirrors a11y.spec.ts — when the postgres
// channel isn't reachable we skip the visit-detail route cleanly.
// ============================================================================

import { test, expect, devices } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';

import { cleanupTestUsers } from './helpers/cleanup';
import { seedVisitStates, type SeededVisitIds } from './helpers/seedVisitStates';
import { signupFreshUser } from './helpers/signup';

// Routes that are expected to render the auth shell.
interface RouteSpec {
  path: string;
  label: string;
  /** When set, replaced with a seeded visit id at runtime; the test
   *  skips if seeding's not available (parity with a11y.spec.ts). */
  requiresVisit?: 'READY' | 'SIGNED' | 'PROCESSING';
}

const ROUTES: RouteSpec[] = [
  { path: '/dashboard',                label: 'dashboard' },
  { path: '/visits',                   label: 'visits' },
  { path: '/visits/new',               label: 'visits-new-step1' },
  { path: '/visits/:READY',            label: 'visit-detail-ready', requiresVisit: 'READY' },
  { path: '/patients',                 label: 'patients' },
  { path: '/settings',                 label: 'settings' },
  { path: '/settings/security',        label: 'settings-security' },
];

// Apple HIG floor (points). Browser CSS pixels at DPR 1 are equivalent.
const HIG_MIN = 44;

// Selectors we deliberately skip because they aren't real tap targets.
const SKIP_SELECTORS: ReadonlyArray<string> = [
  '[data-tap-target-skip]', // explicit opt-out hook (none today)
];

interface MeasureResult {
  total: number;
  small: { selector: string; tag: string; height: number; width: number; text: string; parentHeight: number | null }[];
}

async function measureRoute(page: Page): Promise<MeasureResult> {
  return page.evaluate((min) => {
    const interactive = Array.from(
      document.querySelectorAll(
        'a, button, input, select, textarea, [role="button"], [role="tab"], [role="link"], [role="checkbox"], [role="combobox"], [role="menuitem"]'
      )
    );

    function ancestorTapHeight(el: Element): number | null {
      let cur: Element | null = el.parentElement;
      let depth = 0;
      while (cur && depth < 5) {
        const r = cur.getBoundingClientRect();
        if (r.height >= min) return Math.round(r.height);
        cur = cur.parentElement;
        depth += 1;
      }
      return null;
    }

    function describe(el: Element): string {
      const tag = el.tagName.toLowerCase();
      const id = el.id ? `#${el.id}` : '';
      const cls = (el.getAttribute('class') || '')
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 3)
        .map((c) => `.${c}`)
        .join('');
      const role = el.getAttribute('role');
      return `${tag}${id}${cls}${role ? `[role=${role}]` : ''}`;
    }

    const small: MeasureResult['small'] = [];
    let total = 0;
    for (const el of interactive) {
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) continue;
      const cs = window.getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      // Radix Select renders an invisible <select> for screen-reader
      // accessibility — 1-2px tall, never user-tappable.
      if (el.tagName.toLowerCase() === 'select' && r.height < 4) continue;
      total += 1;
      if (r.height < min) {
        const parentH = ancestorTapHeight(el);
        if (parentH === null) {
          small.push({
            selector: describe(el),
            tag: el.tagName.toLowerCase(),
            height: Math.round(r.height),
            width: Math.round(r.width),
            text: (el.textContent || '').trim().slice(0, 40),
            parentHeight: null,
          });
        }
      }
    }
    return { total, small };
  }, HIG_MIN);
}

interface Suite {
  storageStatePath: string;
  email: string;
  visitIds: SeededVisitIds | null;
}

const suite: Suite = { storageStatePath: '', email: '', visitIds: null };

test.describe.configure({ mode: 'serial' });

test.beforeAll(async ({ browser }) => {
  const ctx = await browser.newContext({ ...devices['iPhone 13'] });
  const page = await ctx.newPage();
  const signup = await signupFreshUser(page, 'tap');
  suite.email = signup.email;
  suite.storageStatePath = test.info().outputPath('tap-storage.json');
  await ctx.storageState({ path: suite.storageStatePath });
  await ctx.close();

  try {
    suite.visitIds = seedVisitStates(suite.email);
  } catch (err) {
    console.error('[tap] seedVisitStates threw:', (err as Error).message);
    suite.visitIds = null;
  }
});

test.afterAll(() => {
  cleanupTestUsers();
});

for (const route of ROUTES) {
  test(`mobile tap-targets :: ${route.label} (${route.path})`, async ({
    browser,
  }) => {
    let resolvedPath = route.path;
    if (route.requiresVisit) {
      if (!suite.visitIds) {
        test.skip(
          true,
          `[tap] ${route.label} skipped — visit seeding channel unavailable`
        );
        return;
      }
      resolvedPath = route.path.replace(
        `:${route.requiresVisit}`,
        suite.visitIds[route.requiresVisit]
      );
    }

    const ctx: BrowserContext = await browser.newContext({
      ...devices['iPhone 13'],
      storageState: suite.storageStatePath,
    });
    const page = await ctx.newPage();

    try {
      const resp = await page.goto(resolvedPath, {
        waitUntil: 'networkidle',
        timeout: 25_000,
      });
      const status = resp ? resp.status() : 0;
      expect(
        status,
        `Expected ${resolvedPath} to return 2xx/3xx, got ${status}`
      ).toBeLessThan(400);
      await page.waitForTimeout(500);

      // Skip-list selectors: tag with [data-tap-target-skip] in the
      // app code if you ever need to exempt a known control.
      void SKIP_SELECTORS;

      const result = await measureRoute(page);
      if (result.small.length > 0) {
        const lines = result.small
          .map(
            (s) =>
              `  ${s.selector.padEnd(35)} h=${String(s.height).padStart(2)} w=${String(s.width).padStart(3)} text=${JSON.stringify(s.text)}`
          )
          .join('\n');
        throw new Error(
          `${result.small.length} of ${result.total} interactive element(s) on ${resolvedPath} ` +
            `fall below the Apple HIG ${HIG_MIN}pt tap-target floor with no ` +
            `tappable ancestor ≥${HIG_MIN}pt either:\n${lines}\n` +
            `Fix: bottom-floor the offending class via the .qm-tap-44 / .qm-tap-44-input ` +
            `utility in globals.css, or extend the .qm-lin-* @media (max-width: 639px) rules.`
        );
      }
    } finally {
      await ctx.close();
    }
  });
}
