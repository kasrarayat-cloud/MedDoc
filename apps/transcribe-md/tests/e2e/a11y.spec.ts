// ============================================================================
// A11y CI gate — Phase 3 Wave 1 (Subagent 5)
// ----------------------------------------------------------------------------
// Drives Chromium through every Clinician-migrated route at desktop +
// mobile viewports, injects axe-core 4.10.0, and FAILS the test if any
// violation has impact === 'critical' or 'serious'.
//
// Pass criterion mirrors the merge-prep round 2 gate in
// docs/qa-reports/: zero critical, zero serious. Anything moderate or
// minor is logged but not blocking — fix-on-sight, but doesn't block
// merge.
//
// Routes are derived from the merge-prep matrix in /tmp/mp/runner.mjs.
// /admin/* is intentionally skipped (TODO v1.1.0 — needs SUPER_ADMIN
// promotion + JWT-refresh logic). /dev/rx-warnings is excluded because
// the production build (which CI runs against) prunes the /dev tree.
//
// Auth: a single signup at the top of the suite captures storageState
// and reuses it across every authenticated test — re-signing per test
// would 10x the runtime for no extra coverage. The unauthenticated
// routes use a cleared context.
//
// Visit-state coverage: when the postgres seeding channel is reachable
// (PSQL_BIN env var on CI, or `docker compose exec postgres psql` on
// the live VPS), three visits in READY/SIGNED/PROCESSING states are
// seeded. When neither is available, the SIGNED + PROCESSING tests
// auto-skip — they're nice-to-have, the READY visit covers the same
// component tree minus the signed banner / progress card.
//
// Why CDN-loaded axe-core: the merge-prep runner used the CDN load and
// it worked headless on the VPS. Avoids a new npm devDep and the
// associated peer-dep churn. If the CDN ever fails in CI (corporate
// proxy, network outage), the `axeFailed` branch surfaces it as a
// per-test error with a clear "axe-load-error" violation ID — the
// fallback would be to `npm i -D axe-core` and inject from
// `node_modules/axe-core/axe.min.js`.
// ============================================================================

import { readFileSync } from 'node:fs';

import { test, expect } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';

import { cleanupTestUsers } from './helpers/cleanup';
import { seedVisitStates, type SeededVisitIds } from './helpers/seedVisitStates';
import { signupFreshUser } from './helpers/signup';

// ----- viewport matrix ------------------------------------------------------

interface Viewport {
  name: 'desktop' | 'mobile';
  width: number;
  height: number;
}

const VIEWPORTS: Viewport[] = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
];

// ----- route matrix ---------------------------------------------------------

type AuthMode = 'none' | 'user';
type VisitState = 'READY' | 'SIGNED' | 'PROCESSING';

interface RouteSpec {
  /** URL path. May contain `:READY|:SIGNED|:PROCESSING` placeholders that
   *  are substituted with seeded visit IDs at runtime. */
  path: string;
  /** Stable label for the test name. */
  label: string;
  /** Whether the route requires the auth storageState. */
  auth: AuthMode;
  /** When set, the test skips if the matching seeded visit isn't
   *  available (postgres seeding channel unreachable). */
  requiresVisit?: VisitState;
  /** Skip the test on root because it's a 307 redirect — there's
   *  nothing to scan in the response body. */
  navigateOnly?: boolean;

  /**
   * ⚠️ OPEN A DIALOG-HOSTED SURFACE BEFORE SCANNING.
   *
   * A sweep that only visits routes gates the HALLWAY, NOT THE ROOM. Every
   * dialog in this app is portalled to `document.body` and rendered only after
   * an interaction, so a route-only scan cannot see one — and the surface a
   * doctor SIGNS on is a dialog.
   *
   * This is not hypothetical: T4's re-skin introduced six nodes at 4.180:1 and
   * a 2.871:1 focus ring INSIDE the sign modal, and the route sweep over
   * `/visits/:READY` was structurally incapable of seeing either. They were
   * caught by an adversarial pass running axe by hand.
   */
  open?: (page: Page) => Promise<void>;

  /**
   * ⚠️ THE NON-VACUITY GUARD, AND IT IS THE POINT OF THE WHOLE FEATURE.
   *
   * A testid that MUST be present after `open` ran. Without it an opener that
   * silently does nothing leaves axe scanning the page WITHOUT the dialog —
   * which passes, and is indistinguishable from a real green. The sweep would
   * then claim coverage it does not have, under a route label that says it
   * does. Absence here is a FAILURE, never a skip.
   */
  opened?: string;

  /** When the `opened` marker is a PREFIX (`icd-reason-picker-<code>`), match
   *  on it instead of exactly. `getByTestId` is EXACT — a per-code testid
   *  would never match, and the guard would fail on correct code. */
  openedIsPrefix?: boolean;

  /**
   * A testid whose ABSENCE means the seeded data cannot reach this surface
   * (e.g. a visit with no suggested ICD codes has no Reject button to click).
   * Checked BEFORE `open`. Absence here SKIPS with a named reason — a data
   * condition is not a defect, and a skip that says why beats a green that
   * does not.
   */
  requiresPresent?: string;
}

const ROUTES: RouteSpec[] = [
  // `/` is a server redirect (→ /login or /dashboard); axe can't run on
  // a 307. We test the redirect targets directly, so this entry only
  // exists to verify the redirect itself doesn't fail.
  // (Skipped via navigateOnly so we don't generate a useless axe pass.)
  // -- omitted on purpose: covering /login and /dashboard already
  //    exercises both branches of the redirect.

  // Public auth surfaces
  { path: '/login',                  label: 'login',           auth: 'none' },
  { path: '/signup',                 label: 'signup',          auth: 'none' },
  // Invite-only pilot (2026-07-28): where every marketing CTA now lands, so it
  // is the most-visited unauthenticated page in the product.
  { path: '/waitlist',               label: 'waitlist',        auth: 'none' },
  { path: '/forgot-password',        label: 'forgot-password', auth: 'none' },
  { path: '/reset-password',         label: 'reset-password',  auth: 'none' },
  { path: '/check-email',            label: 'check-email',     auth: 'none' },

  // Authenticated clinician surfaces
  { path: '/dashboard',              label: 'dashboard',       auth: 'user' },
  { path: '/visits',                 label: 'visits-list',     auth: 'user' },
  { path: '/visits/new',             label: 'visits-new',      auth: 'user' },

  // Visit detail in three states. :READY/:SIGNED/:PROCESSING substituted
  // with seeded visit IDs; tests skip cleanly when seeding's not available.
  { path: '/visits/:READY',          label: 'visit-detail-ready',
    auth: 'user', requiresVisit: 'READY' },
  { path: '/visits/:SIGNED',         label: 'visit-detail-signed',
    auth: 'user', requiresVisit: 'SIGNED' },
  { path: '/visits/:PROCESSING',     label: 'visit-detail-processing',
    auth: 'user', requiresVisit: 'PROCESSING' },

  // ── ⚠️ DIALOG-HOSTED SURFACES — the rooms, not the hallway ──────────────
  //
  // Each of these re-visits a route already in the matrix and then OPENS the
  // dialog before scanning. The duplication is the feature: the route rows
  // prove the page, these prove the surface a doctor actually acts on.

  {
    path: '/visits/:READY',
    label: 'sign-modal (dialog)',
    auth: 'user',
    requiresVisit: 'READY',
    // The signing surface. Opened through the SHIPPED opener rather than a
    // second copy of the gate walk — one opener, so this cannot drift from
    // what the scenario packs drive.
    open: async (page) => {
      const { openSignFlow } = await import('./helpers/sign');
      await openSignFlow(page);
    },
    opened: 'sign-attestation-toggle',
  },
  {
    path: '/visits/:SIGNED',
    label: 'export-modal (dialog, post-sign)',
    auth: 'user',
    requiresVisit: 'SIGNED',
    // The post-sign deliver state — a DIFFERENT tree from the pre-sign modal:
    // no attestation block, a DOCUMENT SIGNED badge, and (after the action
    // shift lands) rows that commit individually.
    open: async (page) => {
      await page.getByRole('button', { name: /export again/i }).first().click();
    },
    opened: 't4-delivery-summary',
  },
  {
    path: '/visits/:READY',
    label: 'icd-reason-picker (dialog-hosted control)',
    auth: 'user',
    requiresVisit: 'READY',
    // The Receipt's rejection reason picker — five buttons that only exist
    // after a Reject click, so no route scan has ever seen them.
    //
    // ⚠️ GUARDED ON THE DATA, NOT ON THE OUTCOME. A seeded visit with no
    // suggested ICD codes has no Reject button at all; that is a data
    // condition and it SKIPS with a reason. What must never happen is a
    // silent pass over a page whose picker never opened.
    // ⚠️ THE REAL TESTIDS, CHECKED AGAINST THE SOURCE. My first draft used
    // `icd-coding-tab`, which does not exist (0 hits) — the tab is
    // `visit-view-tab-coding` — and `icd-reason-picker`, which is per-code
    // (`icd-reason-picker-<code>`) and so never matches an EXACT getByTestId.
    // A guard keyed on a name that is not there fails on correct code, which
    // is the false-rejection half of the same defect.
    requiresPresent: 'visit-view-tab-coding',
    open: async (page) => {
      await page.getByTestId('visit-view-tab-coding').click();
      await page.locator('[data-testid^="icd-reject-"]').first().click();
    },
    opened: 'icd-reason-picker-',
    openedIsPrefix: true,
  },

  // Recording surface (uses the READY visit — recording UI doesn't care
  // about visit status, only about visit existence).
  { path: '/visits/:READY/record',   label: 'visit-record',
    auth: 'user', requiresVisit: 'READY' },

  // Settings — includes the Phase-2b "My Note Format" section. On load the
  // note-format manager renders its default view (the form-dense entry screen
  // for a doctor with no template, or the templates list otherwise). The
  // review / rejected sub-states are gated behind a paste+parse (LLM-backed)
  // interaction, so they rely on component-level a11y attributes rather than
  // this static scan.
  { path: '/settings',               label: 'settings',        auth: 'user' },

  // ── F-ret.2, 2026-08-04 — THE ROUNDS SURFACES. ───────────────────────────
  // This sweep built flag-OFF until today, so none of these had ever been
  // measured for contrast — including the ones a doctor now spends their whole
  // day on. `/dashboard` above is KEPT rather than replaced: under Rounds it is
  // a config-level 307 to `/board`, so walking it still exercises the redirect,
  // and it keeps the route set equal-or-wider rather than a swap.
  //
  // ⚠️ `/patients` is here because a previous axe pass reported green about the
  // screens R1 had just rebuilt — it had never walked them. A gate that does
  // not visit a surface says nothing about it, and says it in the same colour
  // as a gate that did.
  //
  // ⚠️ `/patients/:id` IS NOT COVERED, AND THAT IS A NAMED GAP RATHER THAN AN
  // OVERSIGHT. `seedVisitStates` creates a patient row but returns only the
  // three visit ids (`SeededVisitIds`), and the route table's substitution
  // machinery is keyed on `requiresVisit`. Covering it means returning the
  // patient id and adding a second substitution key — a small change, but one
  // that touches the seeding channel every route in this file depends on, and
  // it is not worth risking the gate for inside F-ret. Recorded in
  // `docs/rounds/RELAY.md` as its own item.
  { path: '/board',                  label: 'board',           auth: 'user' },
  { path: '/patients',               label: 'patients',        auth: 'user' },
  { path: '/settings/note-format',   label: 'settings-note-format', auth: 'user' },

  // /admin/* — TODO(v1.1.0): cover after JWT-refresh helper exists.
  // /dev/rx-warnings — excluded; production build prunes /dev/*.
];

// ----- axe-core injection ---------------------------------------------------

// ⚠️ THE SECOND CDN REACH — and it was a DUPLICATE, which is why fixing the
// helper alone would not have fixed the class. `helpers/rounds-axe.ts` had its
// own `AXE_CDN`; this file had its own `AXE_CDN_URL`. One outage, two red paths,
// and a sweep that stopped at the first would have reported the problem solved.
// Both now read the same pinned package off disk. See `axeSource()` there for
// why the version is asserted rather than merely resolved.
const AXE_EXPECTED_VERSION = '4.10.0';

function axeSource(): string {
   
  const pkg = require('axe-core/package.json') as { version: string };
  if (pkg.version !== AXE_EXPECTED_VERSION) {
    throw new Error(
      `axe-core version drift: resolved ${pkg.version}, gates calibrated on ` +
        `${AXE_EXPECTED_VERSION}. Re-baseline deliberately, or pin it back.`,
    );
  }
  return readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
}

/** AxeViolation — projection of axe-core's full result object,
 *  trimmed to the fields we need for reporting. */
interface AxeViolation {
  id: string;
  impact: 'minor' | 'moderate' | 'serious' | 'critical' | null;
  help: string;
  helpUrl?: string;
  nodes: number;
  /**
   * The CSS selectors axe resolved, capped at five.
   *
   * WHY THIS EXISTS: "1 node" is not a finding, it is a riddle. On 2026-08-04
   * this gate reported `[serious] scrollable-region-focusable (1 node)` on the
   * Rounds stage and named nothing. It did not reproduce locally at any
   * viewport, so identifying the element meant guessing among four scroll
   * containers -- and guessing which one to make focusable risks adding a
   * stray tab stop to the doctor's primary surface.
   *
   * A check that says a surface is wrong without saying WHERE forces the next
   * person to reproduce it before they can act. Same reasoning as the sweep
   * rule's "state the boundary": an answer nobody can check is worth less
   * than it looks.
   */
  targets: string[];
}

/** Inject axe-core from the PINNED LOCAL PACKAGE, run axe.run on the
 *  document, and return the trimmed violation list. Sets
 *  window.__axe_loaded__ once so a second injection on the same page
 *  is a no-op (currently unused since we run one axe pass per page,
 *  but keeps the pattern compatible with multi-pass diagnostics). */
async function runAxeViolations(page: Page): Promise<AxeViolation[]> {
  // Use evaluate with a string template so we don't have to depend on
  // `axe-core`'s TypeScript types in the test runner — page.evaluate
  // runs in the browser, where the global is created at runtime.
  return page.evaluate(async (axeSrc) => {
    interface AxeWindow extends Window {
      __axe_loaded__?: boolean;
      // axe-core attaches `axe.run()` to the global; we type it
      // narrowly so eslint stays happy.
      axe?: {
        run: (
          context: Document,
          opts: { resultTypes: string[] }
        ) => Promise<{
          violations: Array<{
            id: string;
            impact: 'minor' | 'moderate' | 'serious' | 'critical' | null;
            help: string;
            helpUrl?: string;
            nodes: unknown[];
          }>;
        }>;
      };
    }
    const w = window as unknown as AxeWindow;
    if (!w.__axe_loaded__) {
      // Injected as SOURCE TEXT — synchronous, no network, nothing to time out.
      const script = document.createElement('script');
      script.textContent = axeSrc;
      document.head.appendChild(script);
      w.__axe_loaded__ = true;
    }
    if (!w.axe) {
      throw new Error('axe-core loaded but window.axe is undefined');
    }
    const results = await w.axe.run(document, { resultTypes: ['violations'] });
    return results.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      helpUrl: v.helpUrl,
      nodes: v.nodes.length,
      // First five nodes' selectors -- enough to act on, bounded so a
      // 200-node contrast violation does not produce an unreadable error.
      targets: (v.nodes as Array<{ target?: unknown[] }>)
        .slice(0, 5)
        .map((n) => (Array.isArray(n.target) ? n.target.join(' ') : String(n.target)))
        .filter((t) => Boolean(t) && t !== 'undefined'),
    }));
  }, axeSource());
}

/** Rule IDs that are tracked as known design debt rather than CI
 *  blockers. They still surface in the warnings list (`Full violation
 *  count` log line) so we can see if the count grows, but they don't
 *  fail the build.
 *
 *  - `color-contrast`: text-3 (#6c737f) + text-4 (#4b5159) on the
 *    Linear-dark bg fall just under WCAG AA 4.5:1. Token-level fix
 *    cascades through 400+ surfaces and is tracked as Round 1 UX-01.
 *    Until that ships, axe would block every PR for the same surfaces.
 */
const KNOWN_NON_BLOCKING_RULE_IDS = new Set<string>(['color-contrast']);

/** Filter violations to the gate-blocking impact tiers, excluding
 *  rule IDs we explicitly track as known design debt. */
function blockingViolations(violations: AxeViolation[]): AxeViolation[] {
  return violations.filter(
    (v) =>
      (v.impact === 'critical' || v.impact === 'serious') &&
      !KNOWN_NON_BLOCKING_RULE_IDS.has(v.id)
  );
}

/** Pretty-print a list of violations into the failure assertion message. */
function formatViolations(violations: AxeViolation[]): string {
  return violations
    .map(
      (v) =>
        `  [${v.impact}] ${v.id} (${v.nodes} node${v.nodes === 1 ? '' : 's'}) — ${v.help}` +
        (v.targets && v.targets.length
          ? `\n    nodes: ` + v.targets.join(' | ') +
            (v.nodes > v.targets.length ? ` … and ${v.nodes - v.targets.length} more` : '')
          : '') +
        (v.helpUrl ? `\n    ${v.helpUrl}` : '')
    )
    .join('\n');
}

// ----- shared state across describe ----------------------------------------

interface Suite {
  /** Path to the storageState JSON written by the signup beforeAll. */
  storageStatePath: string;
  /** Email of the seeded a11y user — kept around for explicit cleanup. */
  email: string;
  /** Visit IDs (one per state) when seeding succeeded; null otherwise. */
  visitIds: SeededVisitIds | null;
}

const suite: Suite = {
  storageStatePath: '',
  email: '',
  visitIds: null,
};

// ----- fixtures + setup -----------------------------------------------------

test.describe.configure({ mode: 'serial' });

test.beforeAll(async ({ browser }) => {
  // Sign up a brand-new user via the existing UI helper. We get a
  // dashboard-redirected page back; capture its storage so subsequent
  // contexts can skip the signup.
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();
  const signup = await signupFreshUser(page, 'a11y');
  suite.email = signup.email;
  suite.storageStatePath = test.info().outputPath('a11y-storage.json');
  await ctx.storageState({ path: suite.storageStatePath });
  await ctx.close();

  // Try to seed READY/SIGNED/PROCESSING visits for the visit-detail
  // matrix. Failure is non-fatal — those tests skip if seeding's
  // not reachable.
  try {
    suite.visitIds = seedVisitStates(suite.email);
  } catch (err) {
    console.error('[a11y] seedVisitStates threw:', (err as Error).message);
    suite.visitIds = null;
  }
});

test.afterAll(() => {
  // The cleanup helper deletes everything matching the qa-e2e-* prefix
  // (which is what `uniqueTestEmail('a11y')` generates), so the
  // seeded visits + patient + user all cascade out.
  cleanupTestUsers();
});

// ----- generated tests ------------------------------------------------------

for (const viewport of VIEWPORTS) {
  for (const route of ROUTES) {
    const testName = `a11y :: ${viewport.name} :: ${route.label} (${route.path})`;

    test(testName, async ({ browser }) => {
      // Resolve :READY/:SIGNED/:PROCESSING placeholders and skip if the
      // matching visit wasn't seeded.
      let resolvedPath = route.path;
      if (route.requiresVisit) {
        if (!suite.visitIds) {
          test.skip(
            true,
            `[a11y] ${route.label} skipped — visit seeding channel unavailable ` +
              `(PSQL_BIN unset and docker compose unreachable). Run on the VPS ` +
              `or expose postgres to the runner to enable.`
          );
          return;
        }
        const id = suite.visitIds[route.requiresVisit];
        resolvedPath = route.path.replace(`:${route.requiresVisit}`, id);
      }

      const ctx: BrowserContext = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        storageState:
          route.auth === 'user' ? suite.storageStatePath : undefined,
      });
      const page = await ctx.newPage();

      try {
        const resp = await page.goto(resolvedPath, {
          waitUntil: 'networkidle',
          timeout: 25_000,
        });

        // Sanity: any 4xx/5xx other than the auth-redirect 307 means the
        // route is broken before a11y can even be evaluated.
        const status = resp ? resp.status() : 0;
        expect(
          status,
          `Expected ${resolvedPath} to return 2xx/3xx, got ${status}`
        ).toBeLessThan(400);

        // Let any deferred animations / toasts settle. The merge-prep
        // runner found a 500ms wait was sufficient against the same
        // pages.
        await page.waitForTimeout(500);

        // ── ⚠️ OPEN THE DIALOG, THEN PROVE IT OPENED ────────────────────────
        if (route.open) {
          // A data precondition is checked FIRST and skips with a reason. A
          // visit that cannot reach this surface is not a defect; a green that
          // pretends it did is.
          if (route.requiresPresent) {
            const present = await page
              .getByTestId(route.requiresPresent)
              .count()
              .catch(() => 0);
            if (present === 0) {
              test.skip(
                true,
                `[a11y] ${route.label} skipped — the seeded visit has no ` +
                  `\`${route.requiresPresent}\`, so this surface is unreachable ` +
                  `from it. A skip that names the reason beats a pass that ` +
                  `scanned the page WITHOUT the dialog.`
              );
              return;
            }
          }

          await route.open(page);
          await page.waitForTimeout(400);

          // ⚠️ THE GUARD THAT MAKES THE WHOLE ROW MEAN ANYTHING.
          //
          // An opener that silently does nothing leaves axe scanning the page
          // WITHOUT the dialog — which passes, and looks exactly like a real
          // green under a label claiming the dialog was covered. That is the
          // absent-check shape this row exists to close, wearing a new name.
          //
          // So the opened marker is REQUIRED, and its absence FAILS.
          const openedLocator = route.openedIsPrefix
            ? page.locator(`[data-testid^="${route.opened}"]`)
            : page.getByTestId(route.opened!);
          await expect(
            openedLocator.first(),
            `[a11y] ${route.label}: \`open()\` ran but ` +
              `\`${route.opened}\` never appeared — the scan below would have ` +
              `run on the page WITHOUT the dialog and PASSED, gating the ` +
              `hallway and not the room. Failing here instead.`
          ).toBeVisible({ timeout: 15_000 });
        }

        let violations: AxeViolation[];
        try {
          violations = await runAxeViolations(page);
        } catch (err) {
          throw new Error(
            `axe-core failed to load or run on ${resolvedPath}: ${(err as Error).message}\n` +
              `If this fails repeatedly in CI, drop the CDN strategy and add ` +
              `axe-core as an npm devDep: \`npm i -D axe-core\` then import ` +
              `from 'axe-core/axe.min.js'.`
          );
        }

        const blocking = blockingViolations(violations);
        if (blocking.length > 0) {
          throw new Error(
            `${blocking.length} blocking a11y violation(s) on ` +
              `${resolvedPath} (viewport=${viewport.name}):\n` +
              formatViolations(blocking) +
              `\n\nFull violation count (incl. minor/moderate): ${violations.length}.\n` +
              `Pass criterion: zero critical, zero serious — see docs/A11Y_TESTING.md.`
          );
        }

        // Log non-blocking violations for visibility without failing.
        if (violations.length > 0) {
          console.log(
            `[a11y] ${resolvedPath} — ${violations.length} non-blocking violation(s) ` +
              `(moderate/minor). Tracked but not gating.`
          );
        }
      } finally {
        await ctx.close();
      }
    });
  }
}

// ----- self-check tests are not needed -------------------------------------
// The signup beforeAll fails loudly if the auto-login flow regresses, so
// we don't need a separate "is-the-app-up" probe like the existing
// scenario specs. The first authenticated route's `expect(status < 400)`
// will catch it too.
