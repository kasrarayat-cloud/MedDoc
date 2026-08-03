// ============================================================================
// ROUNDS R1 — one app, one nav. Measured on the LIVE DOM, route by route.
// ----------------------------------------------------------------------------
// ⚠️ THIS PACK EXISTS BECAUSE THE FLIP LEFT THE APP SPLIT-BRAIN AND EVERY
// EXISTING GATE WAS GREEN THROUGH IT.
//
// Measured on production the day after Item F flipped:
//
//   /board      qm-rounds                0 asides   Board · Templates · Settings
//   /patients   qm-c3 qm-lin             1 aside    Home · Patients · Settings
//   /dashboard  qm-c3 qm-lin             1 aside    (same legacy shell)
//   /settings   qm-c3 qm-lin qm-rounds   1 aside    (a Rounds host INSIDE it)
//
// Nothing failed. The Rounds packs walk Rounds' own screens — the board, the
// stage, the gate flow, the signed paper — and every one of them was correct.
// `AppFrame`, which wraps everything else, forked only on `isSkinBeta()` and no
// pack asked it anything. A doctor moving from the board to their patient list
// crossed into a different product, and the suite had no opinion.
//
// So the assertion is deliberately about the SHELL rather than about any
// screen: on every authenticated route, zero <aside>, exactly one <nav
// aria-label="Main">, and the same items in it (R1: four; R2 folded Templates
// into Settings, so three). That is a claim the old arrangement could not have
// satisfied by accident.
//
// ─── WHAT WOULD MAKE THIS FAIL (rule 7) ─────────────────────────────────────
//  · a route that renders SidebarC3 or IconRail under Rounds  → aside count 1
//  · a second nav (the board keeping its own inline copy)     → nav count 2
//  · the nav drifting on one surface but not the other        → labels differ
//  · /dashboard rendering instead of forwarding               → URL assertion
//  · the roster losing search or pagination in the restyle    → the function
//    test below drives both against the real server action
//
// Every one of those is a thing that was true, or nearly true, this session.
// ============================================================================

import { test, expect, type Page } from '@playwright/test';

import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';
import { seedReviewDocVisit } from '../helpers/seedReviewDocVisit';

/** Board · Patients · Settings. Written out rather than imported so a change to
 *  the nav has to be made in two places on purpose — the point of the pack is
 *  that the nav is a contract, not an implementation detail.
 *
 *  ⚠️ R2 DROPPED `Templates`, DELIBERATELY, and this line is the declaration.
 *  It pointed at `/settings/note-format` — a SECTION of Settings promoted to a
 *  peer of it. The screen, its URL and every link into it are unchanged; only
 *  the top-level noun is gone, and `/templates` now forwards there. Because the
 *  comparison below is `toEqual` on the whole array, this edit is what lets the
 *  pack go green — which is the intended shape: the expected set moves by hand,
 *  in the open, or not at all. */
const NAV = ['Board', 'Patients', 'Settings'];

/** Every authenticated route a clinician can reach. `/admin/*` is excluded on
 *  purpose and the boundary is stated rather than left implied: it is
 *  SUPER_ADMIN-only and 404s for a clinician, so it is a different product
 *  surface, not a route this pack silently skipped. */
const AUTHED_ROUTES = [
  '/board',
  '/patients',
  '/visits',
  '/visits/new',
  '/settings',
  '/settings/note-format',
  // ⚠️ THE VISIT STAGE JOINED LATE, AND ITS ABSENCE WAS A REAL COVERAGE GAP.
  // `/visits/[id]` is the single most-used authenticated route in the product
  // and the first version of this list omitted it, because it needs a visit id
  // and the others do not. A prod smoke walked it and reported two asides —
  // which turned out to be fine (see `shellShape`) but which this pack could
  // not have told anyone either way. Filled in by the caller below.
];

async function shellShape(page: Page) {
  return page.evaluate(() => {
    const navs = [...document.querySelectorAll('nav[aria-label="Main"]')];
    // ⚠️ THE PREDICATE IS "NO LEGACY SIDEBAR", NOT "NO <aside>", AND THE FIRST
    // VERSION GOT THAT WRONG. `<aside>` is the correct element for
    // complementary content, and the Rounds visit stage legitimately renders
    // two — `qm-rounds-peek-prev` / `-next`, the deck affordances. A blanket
    // `asides === 0` reds on correct markup and pushes the next person to
    // delete a landmark to satisfy a test. An over-strict probe is a defect in
    // the probe. What R1 actually removed is the 240px legacy sidebar, so that
    // is what is counted; `asides` is still reported, for context, never gated.
    const LEGACY_SHELL_ASIDE = /qm-lin-sidebar|qm-c3-sidebar|qm-lin-iconrail/;
    const asides = [...document.querySelectorAll('aside')];
    return {
      legacyAsides: asides.filter((a) => LEGACY_SHELL_ASIDE.test(a.className)).length,
      asidesTotal: asides.length,
      asideClasses: asides.map((a) => a.className || '(none)'),
      navCount: navs.length,
      navLabels: navs[0]
        ? [...navs[0].querySelectorAll('a')].map((a) => (a.textContent ?? '').trim())
        : [],
      // R2. Which item claims the current route, read from `aria-current` —
      // the thing a screen reader actually announces, not the `data-active`
      // mirror beside it. `null` when nothing is lit, which is a real answer
      // and a distinct one from "the label is wrong": folding Templates away
      // could leave `/settings/note-format` lighting NOTHING, and that would
      // be invisible to a labels-only assertion.
      activeNav:
        navs[0]
          ?.querySelector('a[aria-current="page"]')
          ?.textContent?.trim() ?? null,
      mains: document.querySelectorAll('main#main').length,
      skin: document.documentElement.getAttribute('data-skin'),
      // The legacy shells' own root classes. Presence of either means a route
      // resolved to a shell this skin is supposed to have replaced.
      legacyShellRoots: document.querySelectorAll('.qm-lin-app, .qm-c3-app').length,
    };
  });
}

test.describe('R1 — the shell is the same on every authenticated route', () => {
  test('0 asides, exactly one Main nav, one <main id="main">, everywhere', async ({
    page,
  }) => {
    await signupFreshUser(page, 'r1shell');

    // NON-VACUITY FIRST. If the flag were off, every route below would render
    // the legacy shell and the aside assertion would fail loudly — but if the
    // ROUTE LIST were empty, or navigation silently failed, the loop would
    // assert nothing and read as a pass. Prove the skin is on and the walker
    // moves before trusting anything it reports.
    await page.goto('/board');
    const board = await shellShape(page);
    expect(
      board.skin,
      'the app is not rendering the Rounds skin — this pack measures nothing',
    ).toBe('rounds');
    expect(board.navLabels, 'the board has no Main nav at all').toEqual(NAV);

    // NON-VACUITY ON THE ASIDE PREDICATE ITSELF: the matcher must be able to
    // SEE a legacy sidebar, or `legacyAsides === 0` is true for every page in
    // the world including a blank one.
    const matcherWorks = await page.evaluate(() => {
      const probe = document.createElement('aside');
      probe.className = 'qm-lin-sidebar qm-c3-sidebar';
      document.body.appendChild(probe);
      const seen = [...document.querySelectorAll('aside')].filter((a) =>
        /qm-lin-sidebar|qm-c3-sidebar|qm-lin-iconrail/.test(a.className),
      ).length;
      probe.remove();
      return seen;
    });
    expect(
      matcherWorks,
      'the legacy-sidebar matcher cannot detect a legacy sidebar injected right ' +
        'in front of it — every zero it reports below is meaningless',
    ).toBe(1);

    // The visit stage — the route a doctor spends their day on, and the one
    // the first version of this list left out because it needs an id.
    const visitId = await createReadyTextVisit(page, { patientName: 'R1 Shell' });

    const seen: Record<string, Awaited<ReturnType<typeof shellShape>>> = {};
    for (const route of [...AUTHED_ROUTES, `/visits/${visitId}`]) {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      // A route that redirected to /login would render a clean, aside-free
      // page and pass every assertion below for the wrong reason.
      expect(new URL(page.url()).pathname, `${route} bounced to login`).not.toBe('/login');
      seen[route] = await shellShape(page);
    }

    for (const [route, shape] of Object.entries(seen)) {
      expect(
        shape.legacyAsides,
        `${route} still renders the legacy 240px sidebar — asides present: ` +
          `[${shape.asideClasses.join(', ')}]`,
      ).toBe(0);
      expect(
        shape.legacyShellRoots,
        `${route} resolved to the legacy .qm-lin-app / .qm-c3-app shell`,
      ).toBe(0);
      expect(shape.navCount, `${route} has ${shape.navCount} Main navs`).toBe(1);
      expect(shape.navLabels, `${route}'s nav does not read ${NAV.join(' · ')}`).toEqual(NAV);
      expect(
        shape.mains,
        `${route} has ${shape.mains} <main id="main"> — the skip-link target ` +
          'must exist exactly once or the skip link goes nowhere (or somewhere ambiguous)',
      ).toBe(1);
      expect(shape.skin, `${route} lost the skin attribute`).toBe('rounds');
    }
  });

  test('the legacy home forwards to the board, with its deep link mapped', async ({
    page,
  }) => {
    await signupFreshUser(page, 'r1home');

    // ⚠️ ASSERT THE **SERVER** REDIRECT, NOT JUST THE FINAL URL.
    // `app/dashboard/loading.tsx` wraps this segment in Suspense, so a redirect
    // placed after the route's first `await` STREAMS: Next answers 200 with the
    // loading skeleton and delivers the redirect later in the RSC payload. The
    // doctor still ends up on the board, so a `waitForURL` would go green — but
    // they pay a skeleton flash and a second round trip, and a bookmark or a
    // crawler sees `200 /dashboard`. That is what shipped on the first attempt
    // here, and only the raw status told me.
    const raw = await page.request.get('/dashboard', {
      maxRedirects: 0,
      failOnStatusCode: false,
    });
    expect(
      raw.status(),
      `GET /dashboard answered ${raw.status()}. A 200 means the redirect is ` +
        'STREAMED behind loading.tsx rather than issued — hoist it above every ' +
        'await in the route so the segment never suspends',
    ).toBeGreaterThanOrEqual(300);
    // ⚠️ PARSE THE LOCATION, DO NOT SUBSTRING IT. Next APPENDS any query params
    // the rule did not consume, so `/dashboard?tab=all` lands on
    // `/board?tab=all&filter=active` — the original `tab` rides along. The
    // board ignores unknown params, so this is harmless, but a
    // `toContain('/board?filter=active')` assertion fails on it and reads like
    // a broken redirect. Substring matching on URLs is the same trap as
    // 'dashboard'.includes('board'), one layer up.
    const loc = new URL(raw.headers()['location'] ?? '', 'http://x');
    expect(loc.pathname, 'no Location, or it does not point at the board').toBe('/board');

    await page.goto('/dashboard');
    expect(new URL(page.url()).pathname, '/dashboard still renders a second home').toBe('/board');

    // `?tab=all` was the whole-queue view. It maps, rather than being dropped
    // on the floor — a bookmark has to keep meaning what it meant.
    const rawAll = await page.request.get('/dashboard?tab=all', {
      maxRedirects: 0,
      failOnStatusCode: false,
    });
    const locAll = new URL(rawAll.headers()['location'] ?? '', 'http://x');
    expect(locAll.pathname).toBe('/board');
    expect(
      locAll.searchParams.get('filter'),
      'the deep link lost its meaning',
    ).toBe('active');

    await page.goto('/dashboard?tab=all');
    const url = new URL(page.url());
    expect(url.pathname).toBe('/board');
    expect(url.searchParams.get('filter'), 'the deep link lost its meaning').toBe('active');

    // And the root, so the first hop after login is not a double redirect.
    await page.goto('/');
    expect(new URL(page.url()).pathname).toBe('/board');
  });

  // ── R4.2 — THE PATIENT TRAVELS WITH THE ACTION ──────────────────────────
  test('R4.2 — every New-visit CTA carries patient context, or correctly omits it', async ({
    page,
  }) => {
    // ⚠️ THIS IS A REGRESSION I SHIPPED, and the test is written against the
    // exact failure. R3.2 replaced `/patients/[id]`'s header link — which
    // carried `?patientId=…` — with the SHARED `RoundsNewVisitCta`, and that
    // component hardcoded a bare `/visits/new`. So on the one page where the
    // patient is already known, the button dropped them and landed the doctor
    // in create-a-patient. The empty-state link on the same page still carried
    // the param, which is why only ONE of the two misbehaved — and why "the
    // patient page has a working New visit link" was true and useless.
    //
    // RED-PROVABLE: on today's production build the header CTA's href is
    // `/visits/new` with no query, so the first assertion fails.
    const { email } = await signupFreshUser(page, 'r4cta');
    const seeded = seedReviewDocVisit(email, { idSalt: 'r4' });
    expect(seeded, 'seeding failed — this test would prove nothing').not.toBeNull();

    await page.goto(`/patients/${seeded!.patientId}`);

    // 1. The header CTA CARRIES the patient.
    const header = page.getByTestId('rounds-new-visit-bar');
    await expect(header).toBeVisible();
    const href = await header.getAttribute('href');
    expect(
      href,
      'the patient-page New visit CTA dropped the patient — it lands the doctor ' +
        'in create-a-patient on the one page where the patient is known',
    ).toContain(`patientId=${seeded!.patientId}`);

    // 2. Following it PRESELECTS that patient — the destination honours the
    //    param, which is the half a href assertion alone cannot prove.
    await header.click();
    await page.waitForURL(/\/visits\/new/);
    await expect(
      page.getByLabel('Specialty'),
      'landed on "Who\'s this visit for?" rather than on specialty/capture — ' +
        'the patient was not preselected',
    ).toBeVisible({ timeout: 30_000 });
    // The posted contract still holds on this entry path.
    await expect(page.locator('input[name="patientId"]')).toHaveValue(seeded!.patientId);
    // And the doctor can still change their mind.
    await expect(page.getByRole('button', { name: /change patient/i })).toBeVisible();

    // 3. THE COMPLEMENT — surfaces with NO patient in scope must NOT invent one.
    //    Without this, a component that appended a stale id everywhere would
    //    satisfy assertion 1 and be a worse bug.
    for (const [route, testid] of [
      ['/board', 'rounds-new-visit-bar'],
      ['/patients', 'rounds-new-visit-bar'],
      ['/visits', 'rounds-new-visit-bar'],
    ] as const) {
      await page.goto(route);
      const cta = page.getByTestId(testid);
      if (!(await cta.count())) continue;
      expect(
        await cta.getAttribute('href'),
        `${route}'s CTA carries a patientId, and no patient is in scope there`,
      ).toBe('/visits/new');
    }
  });

  // ── R2 — Templates folded into Settings ──────────────────────────────────
  test('R2 — /templates forwards to the note-format section, query intact', async ({
    page,
  }) => {
    await signupFreshUser(page, 'r2tmpl');

    // Same discipline as /dashboard above: the RAW status, not the final URL.
    // A 200 here would mean the path started rendering something.
    const raw = await page.request.get('/templates', {
      maxRedirects: 0,
      failOnStatusCode: false,
    });
    expect(
      raw.status(),
      `GET /templates answered ${raw.status()} — expected a real 3xx from ` +
        'next.config redirects(), which run before routing',
    ).toBeGreaterThanOrEqual(300);
    expect(raw.status(), 'a 308 outlives the flag and is cached forever').toBe(307);

    // PARSE, do not substring: '/settings/note-format' CONTAINS '/settings',
    // so a forward to the Settings index would pass a `toContain` while
    // dropping the doctor on the wrong screen.
    const loc = new URL(raw.headers()['location'] ?? '', 'http://x');
    expect(loc.pathname, 'no Location, or it does not reach note-format').toBe(
      '/settings/note-format',
    );

    // THE QUERY SURVIVES. Next forwards it automatically when the destination
    // names none — asserted rather than assumed, because "automatically" is a
    // property of the framework version, not of this rule.
    const rawQ = await page.request.get('/templates?from=nav&x=1', {
      maxRedirects: 0,
      failOnStatusCode: false,
    });
    const locQ = new URL(rawQ.headers()['location'] ?? '', 'http://x');
    expect(locQ.pathname).toBe('/settings/note-format');
    expect(locQ.searchParams.get('from'), 'the deep link lost its query').toBe('nav');
    expect(locQ.searchParams.get('x')).toBe('1');

    // And it actually lands, with the shell intact and Settings lit — the fold
    // is only real if the destination claims the doctor's position in the nav.
    await page.goto('/templates');
    expect(new URL(page.url()).pathname).toBe('/settings/note-format');
    const shape = await shellShape(page);
    expect(shape.navLabels, 'the forwarded page lost the Rounds nav').toEqual(NAV);
    expect(
      shape.activeNav,
      'note-format lights nothing — Templates left the nav and Settings did ' +
        'not inherit the route. `activeNavHref` is longest-prefix; if this is ' +
        'null the entry it used to match is gone and nothing replaced it',
    ).toBe('Settings');
  });
});

test.describe('R1 — /patients kept every capability it had', () => {
  test('list, search, clear and per-patient history all work', async ({ page }) => {
    await signupFreshUser(page, 'r1roster');
    // Two patients so a search can actually discriminate. `createReadyTextVisit`
    // creates the patient as a side effect of the visit, which is also what
    // gives the roster a "1 visit" meta line to render.
    await createReadyTextVisit(page, { patientName: 'Rosalind Franklin' });
    await createReadyTextVisit(page, { patientName: 'Barbara McClintock' });

    await page.goto('/patients');
    const rows = page.getByTestId('rounds-patient-row');
    await expect(rows).toHaveCount(2);

    // SERVER search — the debounced `searchPatientsAction`, not a client filter.
    await page.getByTestId('rounds-patients-search').fill('Rosalind');
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText('Rosalind Franklin');

    // A search that matches nothing must say so, not render an empty list that
    // looks identical to a roster with no patients.
    await page.getByTestId('rounds-patients-search').fill('Zzzznobody');
    await expect(page.getByTestId('rounds-patients-empty')).toContainText('No patients match');

    await page.getByTestId('rounds-patients-clear').click();
    await expect(rows).toHaveCount(2);

    // Per-patient history.
    await rows.filter({ hasText: 'Barbara McClintock' }).first().click();
    await page.waitForURL(/\/patients\/c[a-z0-9]{10,}/);
    await expect(page.locator('body')).toContainText('Barbara McClintock');

    // New visit, from the roster.
    //
    // ⚠️ R3.1 CHANGED THE TESTID, AND THE REASON IS THE POINT. This asserted
    // `rounds-patients-new-visit` — a Link this file rendered itself, with its
    // own label and href. The roster now mounts the SHARED `RoundsNewVisitCta`
    // (`rounds-new-visit-bar`), the same component the board's top bar uses, so
    // the label, the destination and the hover treatment cannot drift between
    // the two surfaces. R2 already had to rename this action's sibling once for
    // exactly that reason.
    //
    // The expected set moved by hand, declared in the ledger. Asserting the
    // destination as well as the click keeps the claim about the ACTION rather
    // than about the element that happens to carry it.
    await page.goto('/patients');
    const rosterCta = page.getByTestId('rounds-new-visit-bar');
    await expect(rosterCta).toHaveAttribute('href', '/visits/new');
    await rosterCta.click();
    await page.waitForURL(/\/visits\/new/);
  });
});
