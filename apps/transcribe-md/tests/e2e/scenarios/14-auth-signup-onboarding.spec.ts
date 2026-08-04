// ============================================================================
// Scenario 14 — Signup → first authenticated screen.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. The full new-account path through the signup form to the
// first-run home surface — asserting the onboarding/landing state, not just that
// signup returned.
//
// "The dashboard" in the test names below is now WHICHEVER HOME THE IMAGE BUILT:
// `/board` under Rounds, `/dashboard` otherwise (`src/lib/recovery-href.ts:31`).
// The names are left alone so the packs' history stays greppable; every
// assertion goes through helpers/home.ts.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { expectAtHome, HOME_URL_RE } from '../helpers/home';
import { E2E_INVITE_CODE } from '../helpers/signup';
import { TEST_PASSWORD, uniqueTestEmail } from '../helpers/test-utils';

test.afterEach(() => {
  cleanupTestUsers();
});

test('signup: a brand-new account lands on the first-run dashboard', async ({
  page,
}) => {
  const email = uniqueTestEmail('signup');

  await page.goto('/signup');
  // Invite-only pilot (2026-07-28). This spec fills the form inline rather than
  // through signupFreshUser, so it needs the code explicitly.
  await page.getByLabel('Invite code').fill(E2E_INVITE_CODE);
  await page.getByLabel('Full name').fill('New Doctor');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check(); // accept terms
  await page.getByRole('button', { name: /create account/i }).click();

  // ── 1. THE FIRST AUTHENTICATED SCREEN ───────────────────────────────────
  // WAS: `toHaveURL(/\/dashboard$/)`. The destination is no longer a constant —
  // `actions/auth.ts:582` returns `recoveryHref()` (`src/lib/recovery-href.ts:31`),
  // which is `/board` under Rounds and `/dashboard` otherwise, decided at
  // docker-build time. Naming either one here makes the OTHER image a false red,
  // so this asks the helper that accepts both (anchored — 'dashboard' contains
  // 'board', and this project has shipped that substring trap three times).
  // FAILS IF: signup lands anywhere that is not the app home — /login (auto-login
  // broke), /check-email (a verification gate switched on), or a 500.
  await expectAtHome(page);

  // ── 2. WHOSE SCREEN IT IS ───────────────────────────────────────────────
  // Unchanged, and it is skin-agnostic on purpose: the same accessible name is
  // built by `components/rounds/account-menu.tsx:93` and `components/ui/top-nav.tsx:210`.
  // Asserted BEFORE the empty state so it doubles as the sync point — on /board
  // the whole shell streams in behind `app/board/loading.tsx`, so this is the
  // first moment the real page (rather than the skeleton) is in the DOM.
  // FAILS IF: the session belongs to somebody else, or no session rendered.
  await expect(
    page.getByRole('button', { name: /account menu for new doctor/i }),
    'the home surface rendered without THIS account — auto-login did not carry',
  ).toBeVisible({ timeout: 15_000 });

  // ── 3. THE FIRST-RUN EMPTY STATE ────────────────────────────────────────
  // ⚠️ THE OLD ASSERTION WAS VACUOUS ON EVERY IMAGE THE PACK ACTUALLY RUNS, and
  // it is retired rather than re-pointed. It was
  // `getByText(/start your first visit/i).first()`. That copy lives at
  // `app/dashboard/page.tsx:638,652` — inside `EmptyPatients`, which renders ONLY
  // when `NEXT_PUBLIC_SKIN_BETA` is off. BOTH QA images build it ON
  // (docker-compose.qa.rounds.yml:6, docker-compose.qa.flagoff.yml:20), so
  // /dashboard renders `DashboardC3Body` and that copy is not on the page at all.
  // What the substring DID resolve against is the signup success TOAST —
  // "You're in. Start your first visit whenever you're ready."
  // (`app/signup/signup-form.tsx:59`) — which sonner keeps mounted across the
  // router.push. So the assertion proved a toast fired, not that a landing state
  // rendered, and it would have stayed green on a home surface that rendered
  // nothing at all.
  //
  // The replacement branches ON THE DOM, never on a flag: NEXT_PUBLIC_SKIN_ROUNDS
  // is inlined at docker-build time and is absent from the Playwright runner's
  // env, so a test-side `isSkinRounds()` reads undefined and picks the wrong
  // branch on the flag-ON image. Same reasoning as helpers/home.ts and
  // helpers/sign.ts.
  if (await page.getByTestId('rounds-topbar').count()) {
    // ROUNDS — the board's zero-visit invitation, `components/rounds/board.tsx:325-372`.
    const empty = page.getByTestId('rounds-board-empty');
    await expect(
      empty,
      'landed on /board but not in its zero-visit state — a brand-new account ' +
        'has no lanes, so a rendered board here means the queue is not ' +
        'user-scoped',
    ).toBeVisible({ timeout: 15_000 });
    // Scoped to the container and exact, so it cannot resolve against the toast
    // or any other page text. board.tsx:350.
    await expect(
      empty.getByText('No visits yet today', { exact: true }),
    ).toBeVisible();
    // The one thing a first-run doctor is meant to do next. board.tsx:369 →
    // new-visit-cta.tsx:108. FAILS IF: the empty state renders as a bare "nothing
    // here" with no way forward — the R2 regression this CTA exists to prevent.
    await expect(empty.getByTestId('rounds-new-visit-empty')).toBeVisible();
  } else {
    // LEGACY — /dashboard's own first-run state, whichever of its two skins is
    // built. `dashboard-c3.tsx:250` (SKIN_BETA on, what the flag-OFF QA image
    // builds) or `dashboard/page.tsx:626` (SKIN_BETA off). Both anchored with
    // ^…$ so the signup toast's longer sentence cannot satisfy either.
    await expect(
      page
        .getByText(/^You.re all caught up\.$/)
        .or(page.getByRole('heading', { name: 'No patients yet', exact: true })),
      'landed on /dashboard but not in a first-run empty state',
    ).toBeVisible({ timeout: 15_000 });
  }
});

// ============================================================================
// THE GATE ITSELF — invite-only pilot (2026-07-28).
// ----------------------------------------------------------------------------
// Every other spec in the suite proves an INVITED signup works. This one proves
// the other half: without a code, no account comes into existence. Registration
// used to be open, rate-limited at 5/hour/IP and nothing else, and production
// accumulated 195 accounts of which 172 never logged in.
// ============================================================================

test('signup: WITHOUT an invite code, no account is created', async ({ page }) => {
  const email = uniqueTestEmail('uninvited');

  await page.goto('/signup');
  await page.getByLabel('Invite code').fill('DEFINITELY-NOT-A-REAL-CODE');
  await page.getByLabel('Full name').fill('Uninvited Doctor');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /create account/i }).click();

  // Refused, and still on the form — not bounced to a dashboard.
  //
  // ⚠️ SCOPED TO THE ALERT, and the unscoped version asserted nothing.
  // `getByText(/invite-only during the pilot/i).first()` DOM-order-resolves to
  // the STATIC helper paragraph at `signup-form.tsx:113`, which is on the page
  // before the form is ever submitted. It was visible at t=0, so the assertion
  // passed whether or not the gate fired — and the `toHaveURL(/\/signup$/)`
  // below inherited that, because it ran before the server action had returned
  // and the page was trivially still on /signup.
  //
  // `AuthFieldError` (auth-shell.tsx) is the only `role="alert"` reachable on
  // /signup — verified against every globally-mounted component, including the
  // toaster, which carries no role at all. On this path `actions/auth.ts` sets
  // exactly one field error, so precisely one alert is in the DOM. Waiting on
  // it is waiting on the server's refusal.
  await expect(
    page.getByRole('alert').filter({ hasText: /invite/i }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/signup$/);

  // AND THE ACCOUNT MUST NOT EXIST. A gate that shows an error while still
  // writing the row is the failure this whole change exists to prevent — so the
  // proof is that logging in with those credentials cannot work.
  //
  // ⚠️ THE NEGATED URL ASSERTION BELOW CANNOT FAIL ON ITS OWN, so it is no
  // longer asked to. `expect(page).not.toHaveURL(...)` compiles to
  // `waitForURL(url => !isNot === matches)`, and `waitForURL` tests the CURRENT
  // url first and returns immediately when the predicate holds. The click does
  // not await navigation, so at the first poll the page is still /login and the
  // assertion resolves green — before a leaked account's redirect to /dashboard
  // could possibly have landed. It passes on a broken gate.
  // The cure is a POSITIVE wait on the refusal that must happen first; only
  // then does the URL check have anything to say.
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(
    page.getByRole('alert'),
    'no sign-in refusal appeared — the credentials may have been accepted',
  ).toBeVisible({ timeout: 10_000 });
  // WAS: `not.toHaveURL(/\/dashboard$/)`. Kept negated (the positive wait on the
  // refusal above is what gives it teeth — see the block comment), but re-pointed
  // at HOME_URL_RE, because a leaked account signing in under Rounds lands on
  // `/board`, not `/dashboard`. Naming the old constant meant this assertion had
  // nothing left to rule out on the flag-ON image: it would have passed while the
  // uninvited doctor stood on the board. helpers/home.ts:30 covers both.
  await expect(page).not.toHaveURL(HOME_URL_RE);
});

test('the waitlist is reachable and creates no session', async ({ page }) => {
  await page.goto('/waitlist');
  await expect(page.getByRole('button', { name: /join the waitlist/i })).toBeVisible();
  // A prospect is not a user: nothing here grants access.
  //
  // `/dashboard` stays as the ENTRY the prospect tries — it is the home surface
  // flag-OFF, and flag-ON it forwards to `/board`, which then bounces an
  // anonymous visitor (`app/board/page.tsx:76-80`). Either way `goto` settles on
  // the final URL, so the check below is asserted against a resolved page, not a
  // half-navigated one.
  //
  // WAS: `not.toHaveURL(/\/dashboard$/)`. Under Rounds that could only ever be
  // true — the forward guarantees the URL is not `/dashboard` whether or not a
  // session existed — so it had become an assertion that cannot fail.
  // HOME_URL_RE is what it has to rule out now.
  // FAILS IF: /waitlist ever mints a session, or either home surface stops
  // requiring one.
  await page.goto('/dashboard');
  await expect(page).not.toHaveURL(HOME_URL_RE, { timeout: 8_000 });
});
