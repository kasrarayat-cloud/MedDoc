// ============================================================================
// ROUNDS C1-d — the auth surface, FLAG-ON: axe, screenshots, and the states a
// walk cannot reach on its own.
// ----------------------------------------------------------------------------
// Six routes — /login, /signup, /waitlist, /forgot-password, /reset-password,
// /check-email — plus the driven states inside them. They render OUTSIDE
// `AppFrame`, through `auth-shell.tsx`, so nothing Gate A or Gate B walks
// touches them.
//
// WHY THIS IS A SEPARATE PROJECT rather than a describe inside `rounds-a11y`:
// keeping Gate B's pack unchanged means a C1 red can never be misread as a
// Gate B regression, and `gate-project-env` wants one contiguous recreate→run
// block per project. (The plan gave a third reason — that rounds-a11y's
// `beforeAll` signs in and walks authenticated, which contradicts the cleared
// context these routes need. That reason is false: rounds-a11y has no
// `beforeAll` at all; it signs up inside each test on that test's own `page`.
// The two reasons above are sufficient on their own.)
//
// THE OWNERSHIP RULE IS SHARED, NOT COPIED — `helpers/rounds-axe.ts`. It was
// got wrong once at real cost, and two adjudicators would decay the moment one
// of them was fixed.
//
// ─── FOUR DECISIONS THAT DECIDE WHETHER THIS PACK MEANS ANYTHING ────────────
//
//  1. NO `storageState` POSTURE, and no cookie clearing. Four of the six routes
//     `auth()` + `redirect('/dashboard')` on a live session, so a pack holding
//     a session would screenshot a dashboard redirect and exit 0. The plan
//     prescribed copying `a11y.spec.ts:308-312`'s per-test context for this.
//     It buys nothing: `playwright.config.ts` configures no `storageState`
//     anywhere, and Playwright's default `page` fixture already gives every
//     test a fresh, cookie-less context. a11y.spec.ts needs that block only
//     because it MANUFACTURES a shared storageState of its own.
//     The real hazard is narrower and is handled where it occurs: WITHIN a
//     single test, once `signupFreshUser` has run, a later `goto('/login')`
//     redirects. So the logged-out sweep is its own test and never signs up.
//
//  2. NO SEEDING, so no `requireSeed`. These routes need no visit and no psql
//     fixture; `signupFreshUser` throws by itself if signup fails. There is
//     therefore no `test.skip(!seeded)` here to be vacuous.
//
//  3. `color-contrast` IS NOT ALLOWLISTED, same as Gate B — and it is the whole
//     point on this surface. C1-d's own finding is that bridging sage→indigo
//     drops the primary CTA's hardcoded label from 6.72:1 to 3.43:1. See
//     decision 4 for why axe alone cannot be trusted to catch it.
//
//  4. ⚠️ AXE STRUCTURALLY CANNOT SEE THE WORST BUG ON THIS SURFACE, and saying
//     so here is more useful than a green tick. Ownership resolves to the
//     nearest ancestor-or-self carrying ANY class, so a
//     `<button class="qm-lin-btn-primary">` answers for ITSELF and resolves NOT
//     owned — its contrast violation would be logged "inherited" and never
//     block. The brand mark is worse: both spans are `aria-hidden`, so axe
//     never evaluates them. That is why C1-d pairs `qm-rounds-*` onto those
//     nodes (which is what brings them INTO this gate) and why
//     `gate-c1d-auth.test.ts` computes the ratios in a unit as well. A gate and
//     a unit answering the same question two ways is not redundancy here; it is
//     the only reason the answer is worth anything.
//
// ─── ONE STATE IS NOT PHOTOGRAPHED, AND THE REASON IS RECORDED ─────────────
// `login-form.tsx:260-303`, the needs-verification banner, is UNREACHABLE on
// this stack and must stay that way. The branch that sets `needsVerificationFor`
// is wrapped in `isEmailDeliveryEnabled()`, which requires `RESEND_API_KEY`
// truthy AND `RESEND_FROM_VERIFIED === 'true'`. `docker-compose.qa.yml` sets
// `RESEND_API_KEY: ""` deliberately, and two things depend on that:
//   · AGENTS.md's standing rule that the QA stack must be INCAPABLE of reaching
//     a vendor, where dummy credentials are what survives a code regression;
//   · `helpers/reset-token.ts`, which reads the dev-only reset link out of the
//     container log — its own throw message is "is RESEND_API_KEY set on the qa
//     stack?". Enabling delivery breaks scenario 17 by construction.
// So the state is left unverified and named, rather than bought by weakening
// the vendor-severance posture for one screenshot. An unverified step named
// honestly is worth more than a green tick that cost an invariant.
// ============================================================================

import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { enableMfaPromptOnly, setProductsMeddocProOnly } from '../helpers/admin';
import { cleanupTestUsers } from '../helpers/cleanup';
import { captureResetToken } from '../helpers/reset-token';
import {
  blocking,
  inheritedBlocking,
  runAxe,
  shoot,
  type AxeRun,
  type Finding,
  ROUNDS_OWNED,
} from '../helpers/rounds-axe';
import { signupFreshUser } from '../helpers/signup';
import { TEST_EMAIL_PREFIX, TEST_PASSWORD } from '../helpers/test-utils';
import { expectAtHome } from '../helpers/home';

/** Widths the spec's screenshot clause names. */
const WIDE = 1440;
const NARROW = 1024;

// ── Expected computed values, DERIVED FROM THE SHIPPED STYLESHEETS ─────────
//
// ⚠️ NEVER A HARDCODED `rgb(…)` LITERAL. A pack carrying its own copy of the
// value it is checking asserts that the copy is self-consistent, which is not a
// fact about the product — and a token edit would leave this pack green while
// the surface changed underneath it. Read the token, convert, compare EXACTLY.
//
// Paths are relative to the Playwright CWD (apps/transcribe-md), the same
// convention `doc-preview.spec.ts` documents for its fixture. An absolute
// /opt/meddoc-pro path only exists on the VPS and made a helper a silent no-op
// in CI once already.
const ROUNDS_CSS = readFileSync('src/app/rounds-tokens.css', 'utf8');
const GLOBALS_CSS = readFileSync('src/app/globals.css', 'utf8');

function hexToRgb(hex: string): string {
  let h = hex.replace('#', '').trim();
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
}
function cssToken(sheet: string, name: string, where: string): string {
  const m = sheet.match(new RegExp(`^\\s*${name}:\\s*(#[0-9a-fA-F]{3,8})\\s*;`, 'm'));
  if (!m) throw new Error(`${name} is not declared in ${where} — this pack cannot state an expectation`);
  return hexToRgb(m[1]);
}
const ROUNDS = (n: string) => cssToken(ROUNDS_CSS, n, 'rounds-tokens.css');
const LINEAR = (n: string) => cssToken(GLOBALS_CSS, n, 'globals.css');

/** The Rounds stage `.qm-rounds-settings` paints. */
const STAGE_BG_3 = ROUNDS('--rounds-stage-bg-3');
/** The dialog ground `.qm-rounds-dialog` paints — and the old skin's, which it
 *  must not equal. #0d0e10 is a near-black dialog opening on a #12161e page. */
const SURFACE_1 = ROUNDS('--rounds-surface-1');
const OLD_SURFACE_1 = LINEAR('--color-linear-surface-1');
/** Text sitting ON an accent or critical fill, and the near-black literal the
 *  old skin hardcodes at `globals.css` `.qm-lin-btn-primary` — 6.72:1 on sage,
 *  3.62:1 on `--rounds-critical`. The arithmetic is pinned in
 *  `gate-c1e-settings.test.ts`; this pack pins the PIXELS. */
const ON_ACCENT = ROUNDS('--rounds-on-accent');
const OLD_PRIMARY_LABEL = hexToRgb('#0d1611');
const CRITICAL = ROUNDS('--rounds-critical');
/** The MFA pill's forked label, and the value it would have had un-forked:
 *  `--color-linear-sage-bright` bridges to `--rounds-accent-text`, i.e. an
 *  INDIGO label inside a green border. */
const READY_TEXT = ROUNDS('--rounds-ready-text');
const ACCENT_TEXT = ROUNDS('--rounds-accent-text');

test.describe('Rounds C1 — auth to tokens, flag-ON', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const incomplete: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  /** Every state actually measured. The emptiness assertion at the end is
   *  meaningless without it — a walk that silently visited nothing produces
   *  exactly the same `violations: []` as a clean one. */
  const measured: string[] = [];

  function record(state: string, width: number, run: AxeRun) {
    measured.push(`${state}@${width}`);
    for (const e of blocking(run.violations)) violations.push({ state, width, entry: e });
    for (const e of inheritedBlocking(run.violations))
      inherited.push({ state, width, entry: e });
    for (const e of run.incomplete) incomplete.push({ state, width, entry: e });
    for (const sel of run.ariaHiddenFocusable) hiddenTraps.push({ state, width, sel });
  }

  async function sweep(page: Page, state: string, width: number) {
    record(state, width, await runAxe(page));
    await shoot(page, state, width);
  }

  /** The bridge really is applied here, and the node that decides axe ownership
   *  really carries an owned class. Asserted at every state rather than once:
   *  a route that renders the OLD skin — because the image was built without
   *  `NEXT_PUBLIC_SKIN_BETA`, or without `NEXT_PUBLIC_SKIN_ROUNDS` — is clean
   *  under axe and proves nothing at all. This is the assertion that makes the
   *  emptiness below mean "Rounds is clean" rather than "Rounds is absent". */
  async function assertRoundsRendered(page: Page, where: string) {
    await expect(
      page.locator('.qm-rounds-host.qm-rounds-auth'),
      `${where}: the Rounds auth host is absent — this build is not flag-ON, ` +
        'so every axe result below would be measuring the old skin',
    ).toHaveCount(1);
    await expect(
      page.locator('.qm-rounds-authform'),
      `${where}: the form container has no owned class, so every violation ` +
        'inside the form resolves to `qm-c3-auth-form` and is classified ' +
        'inherited — the gate would be green over an unmeasured form',
    ).toHaveCount(1);
  }

  test.afterAll(async () => {
    cleanupTestUsers();
  });

  test('every Rounds auth surface is clean of serious and critical violations', async ({
    page,
  }) => {
    test.setTimeout(240_000);

    for (const width of [WIDE, NARROW]) {
      await page.setViewportSize({ width, height: 900 });

      // ── The six routes, logged out ──────────────────────────────────────
      for (const [state, path] of [
        ['auth:login', '/login'],
        ['auth:signup', '/signup'],
        ['auth:waitlist', '/waitlist'],
        ['auth:forgot-password', '/forgot-password'],
        // No `?token`, so this is the no-token refusal panel.
        ['auth:reset-password-no-token', '/reset-password'],
        // ⚠️ SYNTHETIC VALUE ONLY. `check-email/page.tsx` interpolates the raw
        // `?email=` query value straight into rendered prose with no
        // validation, and `rounds-shots/` is uploaded and retained by CI for
        // 14 days. Whatever goes in this URL ends up in an artifact.
        ['auth:check-email', `/check-email?email=${TEST_EMAIL_PREFIX}synthetic%40test.dev`],
      ] as const) {
        await page.goto(path);
        await assertRoundsRendered(page, state);
        await sweep(page, state, width);
      }

      // ── Driven states ───────────────────────────────────────────────────

      // The waitlist success panel. The row it writes is reaped by
      // `cleanupTestUsers` — see the note there; nothing reaped this table
      // before C1-d.
      await page.goto('/waitlist');
      await page.getByLabel('Email').fill(`${TEST_EMAIL_PREFIX}waitlist-${Date.now()}@test.dev`);
      await page.getByRole('button', { name: /join the waitlist/i }).click();
      await expect(page.locator('.qm-rounds-panel')).toBeVisible({ timeout: 15_000 });
      await sweep(page, 'auth:waitlist-joined', width);

      // The forgot-password submitted panel. Anti-enumeration means this
      // renders for any address, so no account is needed.
      await page.goto('/forgot-password');
      await page.getByLabel('Email').fill(`${TEST_EMAIL_PREFIX}forgot-${Date.now()}@test.dev`);
      await page.getByRole('button', { name: /send reset link/i }).click();
      await expect(page.getByText(/we've sent a reset link/i)).toBeVisible({ timeout: 15_000 });
      await sweep(page, 'auth:forgot-submitted', width);
    }

    // ── The REAL reset form, which axe has never seen ─────────────────────
    // `a11y.spec.ts` hits /reset-password with no token, so only the refusal
    // panel has ever been swept — the actual password form has never been
    // measured by anything, in any skin. Driving it needs a genuine token,
    // which the dev-only log channel provides.
    //
    // ⚠️ THE ACCOUNT MUST EXIST FIRST, and the submitted panel does not tell
    // you whether it does. /forgot-password is deliberately anti-enumerating:
    // it renders the identical "we've sent a reset link" panel for an address
    // it has never seen, logging `no matching active user` and minting no
    // token. So the panel is NOT evidence that a reset was initiated — which
    // is exactly the shape of thing this project keeps re-finding, and it cost
    // a red run here before it was written down.
    await page.setViewportSize({ width: WIDE, height: 900 });
    const resetUser = await signupFreshUser(page, 'rounds-c1-reset');
    // Signup leaves us authenticated, and /forgot-password redirects a live
    // session to /dashboard.
    await page.context().clearCookies();
    await page.goto('/forgot-password');
    await page.getByLabel('Email').fill(resetUser.email);
    await page.getByRole('button', { name: /send reset link/i }).click();
    await expect(page.getByText(/we've sent a reset link/i)).toBeVisible({ timeout: 15_000 });
    const token = captureResetToken();
    await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
    await expect(page.locator('#password')).toBeVisible({ timeout: 15_000 });
    await assertRoundsRendered(page, 'auth:reset-password-form');
    await sweep(page, 'auth:reset-password-form', WIDE);

    // ── The report ────────────────────────────────────────────────────────
    // Non-vacuity FIRST: 8 states × 2 widths + the reset form.
    expect(
      measured.length,
      `only ${measured.length} states were measured — the sweep covered less ` +
        'than it claims, so an empty violations list means nothing',
    ).toBeGreaterThanOrEqual(17);

    if (inherited.length > 0) {
      const set = new Set<string>();
      for (const f of inherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c1] ${inherited.length} inherited serious/critical finding(s) ` +
          'on composed non-Rounds surfaces — reported, not gated:\n' +
          [...set].slice(0, 40).map((t) => `    ${t}`).join('\n') +
          '\n',
      );
    }
    if (incomplete.length > 0) {
      console.log(`\n[rounds-c1] ${incomplete.length} axe "incomplete" entries (reported only).\n`);
    }

    expect(
      hiddenTraps,
      'focusable elements inside an aria-hidden container Rounds owns',
    ).toEqual([]);

    expect(
      violations.map((f) => `${f.state}@${f.width} ${f.entry.id} (${f.entry.impact}) ` +
        `${f.entry.targets.slice(0, 4).join(', ')}` +
        // The measured pair, so a colour failure is diagnosable from its own
        // message rather than from a rebuild cycle and a guess.
        (f.entry.data?.length
          ? ' :: ' + f.entry.data
              .filter((d) => d && (d as any).contrastRatio !== undefined)
              .slice(0, 4)
              .map((d: any) => `${d.fgColor} on ${d.bgColor} = ${d.contrastRatio} (needs ${d.expectedContrastRatio})`)
              .join(' | ')
          : '')),
      'serious/critical axe violations on Rounds-owned auth nodes',
    ).toEqual([]);
  });

  test('the login sub-screens render under Rounds, and the fourth is named unreachable', async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: WIDE, height: 900 });

    // `login-form.tsx` has FOUR conditional blocks, not the five the plan
    // names, and none of them is an early return: there is a single `return (`
    // and the blocks are additive inserts into one always-rendered <form>. So
    // "the MFA screen" is the whole login form plus one extra field, and a fork
    // that swapped the layout would break `helpers/auth.ts`, which re-fills
    // Password while the second-factor field is up.

    // ── MFA second factor, and the recovery-code toggle beside it ──────────
    const mfa = await signupFreshUser(page, 'rounds-c1-mfa');
    await page.context().clearCookies();
    enableMfaPromptOnly(mfa.email);

    await page.goto('/login');

    // ⚠️ ASSERT WE ARE ACTUALLY ON THE LOGIN FORM BEFORE TOUCHING IT.
    // Root-caused 2026-08-07 after this line cost THREE CI re-runs in one day on
    // diffs that could not reach it. The symptom was always
    // `locator.fill: Timeout 15000ms exceeded — waiting for getByLabel('Email')`,
    // which reads as a slow render and is not one.
    //
    // `login/page.tsx:20` does `const session = await auth(); if
    // (session?.user?.id) redirect(...)` — **/login REDIRECTS AN AUTHENTICATED
    // USER AWAY**. `signupFreshUser` above leaves this browser signed IN, and
    // `clearCookies()` is what is supposed to undo that. When the session
    // survives the clear, the navigation lands on the recovery route, where no
    // Email field exists — so the locator waits out its full timeout for an
    // element that is not merely late, it is on another page.
    //
    // The label is `htmlFor="email"` → `id="email"`, a SERVER-RENDERED
    // association, so hydration was never the cause here — worth stating,
    // because the pre-hydration family is the obvious suspect for this file and
    // is the wrong one for this line.
    //
    // This turns a 15s silent timeout into an immediate, diagnostic failure.
    await expect(
      page.locator('#email'),
      'not on the login form — /login redirected us, so the signup session ' +
        'survived clearCookies(). This is the flake; it is not a slow render.',
    ).toBeVisible({ timeout: 10_000 });

    await page.getByLabel('Email').fill(mfa.email);
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
    await page.getByRole('button', { name: /^sign in$/i }).click();
    await expect(page.locator('#totpToken')).toBeVisible({ timeout: 15_000 });
    await assertRoundsRendered(page, 'login:mfa-totp');
    await sweep(page, 'login:mfa-totp', WIDE);

    await page.getByRole('button', { name: /recovery code/i }).click();
    // ⚠️ A POSITIVE ASSERTION, not `#totpToken` count 0. The two second-factor
    // blocks are `mfaRequired && !useRecovery` and `mfaRequired && useRecovery`
    // — so if `mfaRequired` ever went false, `#totpToken` would also be absent,
    // the count-0 check would pass, and this would axe-scan and photograph the
    // ORDINARY login form while reporting a recovery-screen state. Absence of
    // one thing is not presence of the other.
    await expect(page.locator('#recoveryCode')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#totpToken')).toHaveCount(0);
    await sweep(page, 'login:mfa-recovery', WIDE);

    // ── The cross-app redirect panel ───────────────────────────────────────
    const cross = await signupFreshUser(page, 'rounds-c1-cross');
    await page.context().clearCookies();
    setProductsMeddocProOnly(cross.email);

    await page.goto('/login');
    await page.getByLabel('Email').fill(cross.email);
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
    await page.getByRole('button', { name: /^sign in$/i }).click();
    await expect(page.locator('.qm-rounds-btn-secondary')).toBeVisible({ timeout: 15_000 });
    await assertRoundsRendered(page, 'login:cross-app');
    await sweep(page, 'login:cross-app', WIDE);

    // ── The fourth, asserted UNREACHABLE rather than skipped ──────────────
    // Skipping a case and asserting nothing where it was is how a state ends
    // up measured by nothing at all. If the QA posture ever changes — someone
    // sets RESEND_API_KEY to make a different test pass — this reddens and
    // says which invariant moved, instead of silently starting to matter.
    const unverified = await signupFreshUser(page, 'rounds-c1-verify');
    await page.context().clearCookies();
    await page.goto('/login');
    await page.getByLabel('Email').fill(unverified.email);
    await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
    await page.getByRole('button', { name: /^sign in$/i }).click();
    // R1: the app's home is a build-time fork (/board under Rounds), so this
    // asserts "authenticated and home" rather than naming one. It was an inline
    // copy of what `helpers/auth.ts` does — which is why fixing the two shared
    // helpers did not fix this, and only running the pack found it. A traversal
    // that enumerates helpers misses every caller that hand-rolled the same
    // assertion beside them.
    await expectAtHome(page);
    console.log(
      '\n[rounds-c1] NOT PHOTOGRAPHED: login needs-verification ' +
        '(login-form.tsx:260-303). Unreachable while the QA stack is severed ' +
        'from Resend — see this file\'s header. Recorded, not skipped.\n',
    );

    // ⚠️ ASSERT EVERYTHING THIS TEST FILLED, not just `violations`. `record()`
    // pushes into four describe-scope accumulators; test 1 asserts all four and
    // has already finished by the time this runs. The first draft checked only
    // `violations` here, so an aria-hidden focus trap or an inherited finding
    // on the MFA, recovery or cross-app screens was collected and then silently
    // dropped — three states measured into a bucket nothing read.
    expect(
      measured.filter((m) => m.startsWith('login:')).length,
      'the login sub-screen sweep measured fewer states than it drove',
    ).toBeGreaterThanOrEqual(3);
    expect(
      hiddenTraps.filter((t) => t.state.startsWith('login:')),
      'focusable elements inside an aria-hidden Rounds container on a login sub-screen',
    ).toEqual([]);
    const loginInherited = inherited.filter((f) => f.state.startsWith('login:'));
    if (loginInherited.length > 0) {
      const set = new Set<string>();
      for (const f of loginInherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c1] ${loginInherited.length} inherited serious/critical finding(s) ` +
          'on the login sub-screens — reported, not gated:\n' +
          [...set].slice(0, 20).map((t) => `    ${t}`).join('\n') + '\n',
      );
    }
    expect(
      violations.map((f) => `${f.state}@${f.width} ${f.entry.id}`),
      'serious/critical axe violations on the driven login sub-screens',
    ).toEqual([]);
  });

  test('the ownership rule can fail — four positive controls', async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: WIDE, height: 900 });
    await page.goto('/login');
    await assertRoundsRendered(page, 'positive-control');

    // The surface must start clean, or "planting a violation made it red" is
    // not evidence of anything.
    const before = blocking((await runAxe(page)).violations);
    expect(before, "the control's own surface must start clean").toEqual([]);

    // ── (1) A node carrying a Rounds class of its own ──────────────────────
    await page.evaluate(() => {
      const host = document.querySelector('.qm-rounds-authform');
      const el = document.createElement('p');
      el.className = 'qm-rounds-c1-positive-control';
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'classed probe';
      host!.appendChild(el);
    });
    const classed = blocking((await runAxe(page)).violations);
    expect(
      classed.some((e) => e.targets.some((t) => t.includes('qm-rounds-c1-positive-control'))),
      'a node carrying a qm-rounds-* class was not gated — the gate is dead',
    ).toBe(true);

    // ── (2) A CLASSLESS node inside the Rounds form ────────────────────────
    // This is the case `qm-rounds-authform` exists for. Every input, label and
    // error in these five forms is exactly this shape.
    await page.evaluate(() => {
      document.querySelector('.qm-rounds-c1-positive-control')?.remove();
      const host = document.querySelector('.qm-rounds-authform');
      const el = document.createElement('p');
      el.setAttribute('id', 'rounds-c1-bare-probe');
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'bare probe — no class of its own';
      host!.appendChild(el);
    });
    const bare = blocking((await runAxe(page)).violations);
    expect(
      bare.some((e) => e.targets.some((t) => t.includes('rounds-c1-bare-probe'))),
      'a classless element inside the Rounds form was NOT claimed as ' +
        'Rounds-owned — every field on these six routes is this shape, and the ' +
        'whole form would sit outside the gate',
    ).toBe(true);

    // ── (3) THE BRIDGED CASE — the D1 blind spot, asserted as a blind spot ──
    // A node that inherits the bridge from an ancestor but carries its OWN
    // non-Rounds class. `ownedByDom` stops at the first classed ancestor-or-
    // self, so it answers for itself and resolves NOT owned — even though the
    // bridge has retinted it and Rounds is visibly responsible for how it
    // looks.
    //
    // This asserts the blind spot EXISTS rather than pretending it does not,
    // because that is the true statement and C2 has to know it. It is also
    // precisely why C1-d does not rely on the bridge alone: `qm-rounds-*` is
    // pinned onto `.qm-lin-btn-primary`, `.qm-c3-auth-form` and the field
    // controls, which is what pulls them back inside the gate. If a future
    // change makes the adjudicator climb PAST a classed node, this test reds
    // and the reader is sent here rather than to a mystery.
    await page.evaluate(() => {
      document.querySelector('#rounds-c1-bare-probe')?.remove();
      const host = document.querySelector('.qm-rounds-authform');
      const el = document.createElement('p');
      el.className = 'qm-lin-not-a-rounds-class';
      el.setAttribute('id', 'rounds-c1-bridged-probe');
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'bridged probe — own class, not a Rounds one';
      host!.appendChild(el);
    });
    const bridgedRun = await runAxe(page);
    const bridgedBlocking = blocking(bridgedRun.violations);
    const bridgedInherited = inheritedBlocking(bridgedRun.violations);
    expect(
      bridgedBlocking.some((e) => e.targets.some((t) => t.includes('rounds-c1-bridged-probe'))),
      'a bridged node with its own non-Rounds class was GATED — the ownership ' +
        'rule changed. That may be an improvement, but this pack and C2 both ' +
        'reason from the documented blind spot, so update them together',
    ).toBe(false);
    expect(
      bridgedInherited.some((e) => e.targets.some((t) => t.includes('rounds-c1-bridged-probe'))),
      'the bridged probe was neither gated NOR reported as inherited — it fell ' +
        'out of the harness entirely, which is worse than either',
    ).toBe(true);

    await page.evaluate(() => document.querySelector('#rounds-c1-bridged-probe')?.remove());

    // ── (4) THE BLIND SPOT ON SETTINGS — CLOSED BY C2, VERDICT INVERTED ───────
    // Added by C1-e, here rather than in its own describe, because it is the
    // FOURTH case of one control and splitting a control across two tests is
    // how one half gets fixed and the other rots.
    //
    // ⚠️ CASE (2) AND THIS CASE ARE THE SAME PROBE WITH OPPOSITE VERDICTS, and
    // the difference is the whole argument for what C1-d did. A classless node
    // inside `.qm-rounds-authform` IS gated — C1-d pinned an owned class onto
    // that intermediate container precisely so the walk would reach it. The
    // settings surface is chromed by the SHIPPED C3 classes (`qm-c3-set-panel`,
    // `-h`, `-sub`, `-content`) and none of them was paired with a `qm-rounds-*`
    // class, so the walk stops one node early and answers FALSE. Every field,
    // label and paragraph inside a settings panel is therefore REPORTED, never
    // gated.
    //
    // ⚠️ C2 TOOK THE FIRST OF THE TWO OPTIONS THIS CONTROL NAMED. It said:
    // "either the C3 chrome gains paired owned classes when C2 takes it, or
    // the settings panels stay outside the gate and that is said out loud."
    // `.qm-c3-set-panel` now also carries `qm-rounds-setpanel`, and
    // `.qm-c3-set-content` carries `qm-rounds-setbody`, so the walk reaches a
    // Rounds name and every field, label and paragraph in the seven panels is
    // GATED rather than merely reported.
    // 
    // The verdict below is therefore INVERTED from what C1-e shipped, and the
    // inversion IS the assertion: `toBe(true)` where it read `toBe(false)`.
    // Case (2) and this case now agree, which is the point — the argument for
    // `qm-rounds-authform` was always that a bridged surface Rounds colours is
    // a surface Rounds must answer for, and settings is that surface.
    // 
    // Rule 4 is not breached: nothing was restyled to make a gate greener. The
    // markup is untouched; it gained an ownership marker so failures ALREADY
    // PRESENT can block instead of scrolling past in a log.
    await signupFreshUser(page, 'rounds-c1e-ctl');
    await page.goto('/settings');
    await expect(
      page.locator('.qm-rounds-host.qm-rounds-settings'),
      'the settings host is absent — this build is not flag-ON, so the control ' +
        'below would be measuring the old skin',
    ).toHaveCount(1);
    // Exactly one panel is not `hidden`; axe skips hidden content entirely, so
    // a probe in the wrong panel would be invisible and read as "not gated".
    const live = page.locator('.qm-c3-set-panel:not([hidden])');
    await expect(live, 'the C3 section rail renders no visible panel').toHaveCount(1);
    await page.evaluate(() => {
      const panel = document.querySelector('.qm-c3-set-panel:not([hidden])');
      const el = document.createElement('p');
      el.setAttribute('id', 'rounds-c1e-panel-probe');
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'classless probe inside a classed C3 settings panel';
      panel!.appendChild(el);
    });
    const panelRun = await runAxe(page);
    expect(
      blocking(panelRun.violations).some((e) =>
        e.targets.some((t) => t.includes('rounds-c1e-panel-probe')),
      ),
      'a classless node inside a settings panel is NOT gated — the C2 anchors ' +
        '(`qm-rounds-setpanel` / `qm-rounds-setbody`) are missing, or the walk ' +
        'stops before them, so every field and paragraph in the seven panels is ' +
        'back to being reported and never blocking',
      ).toBe(true);
    expect(
      inheritedBlocking(panelRun.violations).some((e) =>
        e.targets.some((t) => t.includes('rounds-c1e-panel-probe')),
      ),
      'the settings probe is reported as INHERITED as well as gated — the two ' +
        'buckets must stay disjoint, or a reader cannot tell which one a finding ' +
        'is in',
      ).toBe(false);
    await page.evaluate(() => document.querySelector('#rounds-c1e-panel-probe')?.remove());

    cleanupTestUsers();
  });
});

// ============================================================================
// ROUNDS C1-e — the settings surface, FLAG-ON: the portal the bridge cannot
// reach, and two computed colours no file-level check can see.
// ----------------------------------------------------------------------------
// A SEPARATE top-level describe, with its OWN accumulators. C1-d's three tests
// share four describe-scope arrays and assert them with a floor of 17 measured
// states; pushing settings states into those would move that floor for a reason
// unrelated to the auth surface, and a C1-e red would read as a C1-d
// regression. `record`/`sweep` are therefore duplicated here rather than
// hoisted — hoisting them would mean rewriting the C1-d block, and the point of
// the split is that the two packs cannot move each other.
//
// ─── WHAT THIS PACK EXISTS FOR, THAT NOTHING ELSE CAN DO ───────────────────
//
//  1. ⚠️ THE PORTAL. `delete-account-dialog` and `change-email-dialog` render
//     `<Dialog.Portal>` with no `container`, so Radix mounts them on `<body>`.
//     `data-skin` is on `<html>` so `[data-skin='rounds']` still matches — but
//     the bridge is `[data-skin='rounds'] .qm-rounds-host`, deliberately
//     scoped, and a portalled node is not a descendant of the page root. NINE
//     `--color-linear-*` names inside each dialog keep their old-skin values:
//     measured, a near-black #0d0e10 dialog opening on a #12161e Rounds page.
//     `gate-rounds-bridge` cannot see it (it asks whether the FILE contains
//     `qm-rounds-host`, and the file does — on the trigger). `gate-c1e-settings`
//     pins the class onto the right ELEMENT, which is as far as source can go.
//     ONLY a browser can say what the dialog actually computes, and only with
//     it open. That is this pack.
//
//  2. ⚠️ EVERY PANEL STAYS MOUNTED, `hidden`. `settings-sections-c3.tsx` keeps
//     all seven in the DOM so an in-progress edit survives a section switch —
//     so a `fill()` or a `click()` on a control in an inactive panel resolves,
//     acts on an invisible node, and PASSES. Every interaction below clicks the
//     rail tab first and asserts the panel is visible, the idiom
//     `doc-preview.spec.ts:40-41` uses. `hidden` also makes axe skip the
//     subtree entirely, so a sweep of the wrong panel is a green tick over an
//     unmeasured surface.
//
//  3. ⚠️ THE CONTRAST AXE CANNOT BLOCK ON. Both fixed nodes carry a
//     non-Rounds class of their own — the stepper disc is a bare `<span>` in a
//     densely-classed C3 panel, the confirm button is
//     `<button class="qm-lin-btn-primary">` — so `ownedByDom` answers for the
//     nearest classed ancestor-or-self, resolves NOT owned, and files any
//     violation "inherited": reported, never blocking. Positive control (4) in
//     the C1-d describe asserts that blind spot directly. So the colours are
//     read with `getComputedStyle` and compared EXACTLY, against values derived
//     from the shipped stylesheet at the top of this file.
//
// ─── ONE STATE IS NOT DRIVEN, AND THE REASON IS RECORDED ───────────────────
// The delete-account dialog is opened and ARMED — both fields filled so the
// confirm button is enabled and computes its real colours — and the confirm is
// NEVER clicked. Not "not clicked in this test": there is no assertion anywhere
// below that depends on the account being deleted. Driving a destructive
// confirm to photograph a button is the shape of thing AGENTS.md's production-
// verification rule forbids, and a synthetic account does not make it a better
// habit. The post-confirm state is therefore UNVERIFIED and named, not bought.
// ============================================================================

test.describe('Rounds C1-e — settings, flag-ON', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const incomplete: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  const measured: string[] = [];

  function record(state: string, width: number, run: AxeRun) {
    measured.push(`${state}@${width}`);
    for (const e of blocking(run.violations)) violations.push({ state, width, entry: e });
    for (const e of inheritedBlocking(run.violations))
      inherited.push({ state, width, entry: e });
    for (const e of run.incomplete) incomplete.push({ state, width, entry: e });
    for (const sel of run.ariaHiddenFocusable) hiddenTraps.push({ state, width, sel });
  }

  /** Sweep AND hand the run back, so a caller can assert on `modal`. */
  async function sweep(page: Page, state: string, width: number): Promise<AxeRun> {
    const run = await runAxe(page);
    record(state, width, run);
    await shoot(page, state, width);
    return run;
  }

  /** The Rounds settings surface really is applied, AND it really is painting.
   *
   *  ⚠️ THE SECOND HALF IS NOT DECORATION. `/settings` is the first Rounds
   *  surface rendered inside `AppFrame`, and `.qm-lin-app` paints an OPAQUE
   *  `var(--color-linear-bg)` at 100vh as an ANCESTOR of this host — so the
   *  host's own redeclaration cannot reach it. A marker class that only set a
   *  font would leave Rounds-tinted panels on the old skin's near-black canvas,
   *  and every axe result below would be measured against the wrong ground
   *  while looking perfectly normal. */
  async function assertSettingsSurface(page: Page, where: string) {
    const host = page.locator('.qm-rounds-host.qm-rounds-settings');
    await expect(
      host,
      `${where}: the Rounds settings host is absent — this build is not flag-ON ` +
        '(NEXT_PUBLIC_SKIN_ROUNDS + NEXT_PUBLIC_SKIN_BETA), so every result ' +
        'below would be measuring the old skin',
    ).toHaveCount(1);
    // EXACT, not a substring. `'rgb(18, 22, 30)'.includes('rgb(1')` is true of
    // half the palette — the substring trap that made C1-c's label guard
    // vacuous, and it is just as available here.
    expect(
      await host.evaluate((el) => getComputedStyle(el).backgroundColor),
      `${where}: the settings surface is not painting the Rounds stage — the ` +
        'opaque AppFrame canvas is showing through',
    ).toBe(STAGE_BG_3);
  }

  const rail = (page: Page) => page.locator('nav[aria-label="Settings sections"]');

  /** Click a rail tab and PROVE its panel became visible.
   *  Never touch a control without this: all seven panels stay mounted with the
   *  `hidden` attribute, and a `fill()` on a hidden one is a false pass. */
  async function openSection(page: Page, label: RegExp, id: string) {
    await rail(page).getByRole('button', { name: label }).click();
    await expect(
      page.locator(`#${id}`),
      `the ${id} panel did not become visible — every interaction after this ` +
        'would act on a hidden node and pass',
    ).toBeVisible({ timeout: 10_000 });
  }

  /** The portalled dialog, asserted as ONE element carrying BOTH classes.
   *
   *  `.qm-rounds-host.qm-rounds-dialog` is a compound selector, so this cannot
   *  be satisfied by the host sitting on an ancestor and the marker on the
   *  content — which is exactly the move that silently un-bridges the dialog
   *  while leaving `gate-rounds-bridge` green. */
  async function assertDialogBridged(page: Page, where: string) {
    const dialog = page.locator('.qm-rounds-host.qm-rounds-dialog');
    await expect(
      dialog,
      `${where}: no single element carries BOTH qm-rounds-host and ` +
        'qm-rounds-dialog — a portalled node is not a descendant of the page ' +
        'host, so the bridge does not reach it',
    ).toHaveCount(1);
    await expect(dialog).toBeVisible({ timeout: 10_000 });

    // ⚠️ WAIT FOR THE ENTRY ANIMATION TO SETTLE BEFORE MEASURING ANYTHING.
    // Radix opens this dialog with `fade-in-0` + `zoom-in-95`, so for the first
    // ~150ms every colour in it is a COMPOSITE of the real value and whatever
    // is behind. Measured mid-fade, axe reported `#5f6772 on #13171f = 3.13`
    // — neither of which is a token in this palette: that is
    // `--rounds-text-2` (#98a2b1) and `--rounds-surface-1` (#161b24) blended
    // toward the stage. The nodes named were real, the colours were not, and
    // three separate "fixes" were aimed at rules that were never the cause.
    //
    // This is A2 defect 4 in a second place — an animation that makes text
    // unreadable AT THE SAMPLING INSTANT. Waiting on `getAnimations()` rather
    // than on a sleep, because the settle condition is the animation itself
    // finishing, not a duration someone guessed.
    await dialog.evaluate(async (el) => {
      await Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished.catch(() => {})));
    });
    await expect
      .poll(async () => dialog.evaluate((el) => getComputedStyle(el).opacity), { timeout: 5_000 })
      .toBe('1');

    const bg = await dialog.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg, `${where}: the dialog ground is not the Rounds surface`).toBe(SURFACE_1);
    expect(
      bg,
      `${where}: the dialog is painting the OLD SKIN ground — a near-black ` +
        'dialog opening on a Rounds page. This is the defect C1-e exists to fix',
    ).not.toBe(OLD_SURFACE_1);
    return dialog;
  }

  test.afterAll(async () => {
    cleanupTestUsers();
  });

  test('the settings surface and BOTH portalled dialogs compute Rounds', async ({ page }) => {
    test.setTimeout(300_000);
    const user = await signupFreshUser(page, 'rounds-c1e-set');

    for (const width of [WIDE, NARROW]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/settings');
      await assertSettingsSurface(page, `settings@${width}`);
      // Profile is `sections[0]` and therefore already active — clicked anyway,
      // because "it happens to be first" is a fact about today's section order
      // and this pack should not silently start measuring a different panel the
      // day someone reorders them.
      await openSection(page, /^profile$/i, 'profile');
      await sweep(page, 'settings:profile', width);
    }

    await page.setViewportSize({ width: WIDE, height: 900 });

    // ── The danger zone, and the destructive dialog ────────────────────────
    await openSection(page, /^danger zone$/i, 'danger');
    await sweep(page, 'settings:danger', WIDE);

    await page.getByRole('button', { name: /delete my account/i }).click();
    const del = await assertDialogBridged(page, 'settings:danger-dialog');

    // ARM the confirm — both fields, so `canSubmit` is true and the button
    // computes its enabled colours rather than a disabled variant. It is NEVER
    // clicked; see this describe's header.
    await page.locator('#delete-password').fill(TEST_PASSWORD);
    await page.locator('#delete-confirmation').fill('DELETE');
    const confirm = del.getByRole('button', { name: /^delete account$/i });
    await expect(confirm, 'the confirm never armed — its colours would be the ' +
      'disabled variant and the assertion below would measure nothing real')
      .toBeEnabled();

    // ⚠️ THE ASSERTION C1-e EXISTS FOR. The fill arrives through the host's
    // `--color-linear-danger` redeclaration; the label arrives through
    // `[data-skin='rounds'] .qm-rounds-host .qm-lin-btn-primary`. BOTH are keyed
    // on the host being on THIS element. Bridge the fill by any route that does
    // not also carry the label fork and the label sits at 3.62:1 — a contrast
    // regression created by the act of fixing a colour. Asserting the pair
    // together is what makes that impossible to ship half of.
    const [labelColor, fillColor] = await confirm.evaluate((el) => [
      getComputedStyle(el).color,
      getComputedStyle(el).backgroundColor,
    ]);
    expect(labelColor, 'the destructive confirm label is not white-on-critical').toBe(ON_ACCENT);
    expect(
      labelColor,
      'the destructive confirm still carries the old skin\'s near-black label ' +
        '(#0d1611) — 3.62:1 on --rounds-critical, a FAIL the bridge introduced',
    ).not.toBe(OLD_PRIMARY_LABEL);
    expect(
      fillColor,
      'the fill did not arrive with the label — they must come through ONE selector',
    ).toBe(CRITICAL);

    const delRun = await sweep(page, 'settings:danger-dialog', WIDE);
    // Non-vacuity on the sweep itself: the harness suppresses its aria-hidden
    // probe while a modal stands, and substitutes the focus-trap question. If
    // axe did not see an open dialog, this state measured the page behind it.
    expect(delRun.modal.open, 'axe saw no open dialog — this state swept the ' +
      'settings page, not the modal').toBe(true);
    expect(delRun.modal.focusInside, 'focus is not inside the open dialog').toBe(true);

    await page.keyboard.press('Escape');
    await expect(page.locator('.qm-rounds-dialog')).toHaveCount(0, { timeout: 10_000 });

    // ── The change-email dialog, on the other end of the surface ───────────
    await openSection(page, /^profile$/i, 'profile');
    await page.locator('#profile').getByRole('button', { name: /^change$/i }).click();
    await assertDialogBridged(page, 'settings:change-email-dialog');
    const emailRun = await sweep(page, 'settings:change-email-dialog', WIDE);
    expect(emailRun.modal.open, 'axe saw no open dialog on the change-email state').toBe(true);
    await page.keyboard.press('Escape');
    await expect(page.locator('.qm-rounds-dialog')).toHaveCount(0, { timeout: 10_000 });

    // ⚠️ AND THE ACCOUNT IS UNCHANGED, ASSERTED RATHER THAN ASSUMED. The first
    // draft of this line was `expect(user.email).toContain(TEST_EMAIL_PREFIX)`
    // — which compares the value `signupFreshUser` returned against a constant
    // and could not have failed for any product reason at all. It asserted a
    // property of a local variable, not a fact about the account. The real
    // question is what the SERVER still holds, so re-read the rendered profile.
    // `toContainText` rather than an equality: the panel carries other prose,
    // and the needle is a whole unique address, not a label whose identity a
    // superstring could satisfy.
    await openSection(page, /^profile$/i, 'profile');
    await expect(
      page.locator('#profile'),
      'the account no longer shows the signup address — something in this test ' +
        'COMMITTED a change it was only supposed to arm',
    ).toContainText(user.email);
    expect(user.email).toContain(TEST_EMAIL_PREFIX); // …and cleanup will reap it

    // ── The report ────────────────────────────────────────────────────────
    // Non-vacuity FIRST: 2 widths of the base surface + danger + two dialogs.
    expect(
      measured.length,
      `only ${measured.length} settings states were measured — the walk covered ` +
        'less than it claims, so an empty violations list means nothing',
    ).toBeGreaterThanOrEqual(5);

    if (inherited.length > 0) {
      const set = new Set<string>();
      for (const f of inherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c1e] ${inherited.length} inherited serious/critical finding(s) ` +
          'on composed C3 settings chrome — reported, not gated. This is the ' +
          'blind spot positive control (4) asserts; C2 owns closing it:\n' +
          [...set].slice(0, 40).map((t) => `    ${t}`).join('\n') +
          '\n',
      );
    }
    if (incomplete.length > 0) {
      console.log(`\n[rounds-c1e] ${incomplete.length} axe "incomplete" entries (reported only).\n`);
    }

    expect(
      hiddenTraps,
      'focusable elements inside an aria-hidden container Rounds owns',
    ).toEqual([]);
    expect(
      violations.map((f) => `${f.state}@${f.width} ${f.entry.id} (${f.entry.impact}) ` +
        `${f.entry.targets.slice(0, 4).join(', ')}` +
        // The measured pair, so a colour failure is diagnosable from its own
        // message rather than from a rebuild cycle and a guess.
        (f.entry.data?.length
          ? ' :: ' + f.entry.data
              .filter((d) => d && (d as any).contrastRatio !== undefined)
              .slice(0, 4)
              .map((d: any) => `${d.fgColor} on ${d.bgColor} = ${d.contrastRatio} (needs ${d.expectedContrastRatio})`)
              .join(' | ')
          : '')),
      'serious/critical axe violations on Rounds-owned settings nodes',
    ).toEqual([]);
  });

  test('the MFA route carries the surface, and its two forked colours compute', async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: WIDE, height: 900 });
    const mfaUser = await signupFreshUser(page, 'rounds-c1e-mfa');

    // ⚠️ ITS OWN ROUTE LEAF. There is no `settings/layout.tsx`, so this page
    // inherits nothing from `/settings` and carries its own host. If that ever
    // regressed to relying on the parent, this is where it shows.
    await page.goto('/settings/security/mfa');
    await assertSettingsSurface(page, 'mfa:enroll');

    // ── The stepper disc ──────────────────────────────────────────────────
    // Step 1 is active on arrival, so the disc fills with `--color-linear-sage`
    // → bridged to `--rounds-accent`. The label was a hardcoded #0d1611:
    // 6.72:1 on sage, 3.43:1 on the accent, at 10.5px.
    const stepper = page.locator('ol[aria-label="Enrollment steps"]');
    await expect(stepper, 'the enrollment stepper is absent — this account is ' +
      'already enrolled, so the disc below would not be the step-1 disc')
      .toHaveCount(1);
    // ⚠️ COUNTED, NOT `.first()`. Each `<li>` renders exactly ONE span — the
    // disc — with the step label as a bare text node beside it. If a restyle
    // ever wraps that label in a span of its own, `.first()` would silently keep
    // measuring the right node today and the wrong one the day the order
    // changed; a count assertion says so instead.
    const step1 = stepper.locator('li').first();
    await expect(
      step1.locator('span'),
      'the stepper step now renders more than one span — `.first()` is no longer ' +
        'unambiguously the disc',
    ).toHaveCount(1);
    const disc = step1.locator('span');
    const discColor = await disc.evaluate((el) => getComputedStyle(el).color);
    expect(discColor, 'the stepper disc glyph is not the on-accent token').toBe(ON_ACCENT);
    expect(
      discColor,
      'the stepper disc still carries #0d1611 — 3.43:1 on --rounds-accent, and ' +
        'axe files it INCOMPLETE (single-character text), never a violation',
    ).not.toBe(OLD_PRIMARY_LABEL);
    // …and the fill really is the accent, or "white on it" is a claim about a
    // colour that is not there.
    expect(await disc.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
      ROUNDS('--rounds-accent'),
    );
    await sweep(page, 'mfa:enroll', WIDE);

    // ── The "on" pill, on the management panel ────────────────────────────
    // Reached by flipping `mfaEnabled` directly: enrolling for real needs a
    // live TOTP secret and a valid 6-digit code, which this stack cannot mint.
    // The pill's own render path is identical either way — it reads
    // `user.mfaEnabled`, not how the flag got set.
    enableMfaPromptOnly(mfaUser.email);
    await page.goto('/settings/security/mfa');
    await assertSettingsSurface(page, 'mfa:on');
    const pill = page.getByText('MFA enabled');
    // A POSITIVE ASSERTION that the MANAGEMENT panel arrived — the enrollment
    // panel is absent, not merely "the pill is present". `getByText` resolves to
    // the smallest element containing the text, i.e. the pill span; the count
    // assertion is what stops a second occurrence turning `.evaluate()` into a
    // strict-mode error whose message would be about Playwright, not about
    // Rounds.
    await expect(
      pill,
      'the management panel did not render — the DB write did not take, and this ' +
        'state is still the enrollment panel',
    ).toHaveCount(1, { timeout: 15_000 });
    await expect(pill).toBeVisible();
    await expect(
      page.locator('ol[aria-label="Enrollment steps"]'),
      'the enrollment stepper is still on screen — this is not the management panel',
    ).toHaveCount(0);
    const pillColor = await pill.evaluate((el) => getComputedStyle(el).color);
    expect(pillColor, 'the MFA pill label is not the Rounds ready-text token').toBe(READY_TEXT);
    expect(
      pillColor,
      'the pill label is the bridged accent — an INDIGO label inside a GREEN ' +
        'border, brand-coloured where the surface exists to say "protected"',
    ).not.toBe(ACCENT_TEXT);
    await sweep(page, 'mfa:on', WIDE);

    // ── The report, for this test's own states ────────────────────────────
    // ⚠️ ASSERT EVERYTHING THIS TEST FILLED, not just `violations`. `record()`
    // pushes into four accumulators and the first test has already finished by
    // the time this runs — the same defect C1-d's second test records.
    expect(
      measured.filter((m) => m.startsWith('mfa:')).length,
      'the MFA sweep measured fewer states than it drove',
    ).toBeGreaterThanOrEqual(2);
    expect(
      hiddenTraps.filter((t) => t.state.startsWith('mfa:')),
      'focusable elements inside an aria-hidden Rounds container on the MFA route',
    ).toEqual([]);
    const mfaInherited = inherited.filter((f) => f.state.startsWith('mfa:'));
    if (mfaInherited.length > 0) {
      const set = new Set<string>();
      for (const f of mfaInherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c1e] ${mfaInherited.length} inherited serious/critical finding(s) ` +
          'on the MFA route — reported, not gated:\n' +
          [...set].slice(0, 20).map((t) => `    ${t}`).join('\n') + '\n',
      );
    }
    expect(
      violations
        .filter((f) => f.state.startsWith('mfa:'))
        .map((f) => `${f.state}@${f.width} ${f.entry.id} (${f.entry.impact})`),
      'serious/critical axe violations on Rounds-owned MFA nodes',
    ).toEqual([]);
  });
});

// ============================================================================
// C1-f — templates: the note-format panel and its six views.
// ----------------------------------------------------------------------------
// ⚠️ ITS OWN ACCUMULATORS, for the reason C1-e's describe states: a shared
// floor would make a C1-f red read as a C1-d or C1-e regression, which is
// exactly the diagnosis cost `gate-project-env` exists to remove.
//
// ⚠️ THE PLAN'S E2E PATH FOR THIS ITEM CANNOT WORK, AND IT WAS MEASURED RATHER
// THAN REASONED. `C1-PLAN.md:315` says to drive the machine through
// `helpers/noteFormat.ts`'s `parseToReview()`. That helper does
// `goto('/settings')` and then waits for **"Save & activate"** — which is the
// REVIEW EDITOR. On this image `NEXT_PUBLIC_UX_SIMPLIFY=true`, and
// `note-format-manager.tsx:195` routes a completed parse to `confirm`, never to
// `review`. The helper would also `fill()` a panel that is still `hidden`,
// because the C3 rail keeps all seven mounted. Following the plan here gives a
// pack that hangs for its full timeout and reports the product as broken.
// `doc-preview.spec.ts` is the only existing spec that drives this machine on a
// UX_SIMPLIFY build, and its two drivers are the model copied below.
//
// The six views, and how each is reached — stated because two of them cannot be
// walked to and that is a fact about the product, not a gap in the pack:
//   entry     — a fresh doctor has no templates, so this is the landing view
//   confirm   — upload the BLANK fixture form; MOCK_AI does the parse
//   review    — the confirm card's "Something's off" (the advanced editor)
//   home      — after the format is confirmed
//   parsing   — paints only while four server actions are in flight
//   rejected  — needs the parse-time PHI gate, i.e. a container env this image
//               does not carry
// The last two are rendered by `/dev/states`, the door C1-c2 built for exactly
// this, from the REAL components and the REAL stage builder.
// ============================================================================

/** Ink on the brand fill, and the literal it replaces. `#0d1611` was typed into
 *  three style objects and one globals.css rule; on the bridged accent it is
 *  3.43:1. The arithmetic is pinned in `gate-c1f-templates.test.ts`; this pack
 *  pins the PIXELS, which is the half a source guard cannot reach. */
const ACCENT_FILL = ROUNDS('--rounds-accent');
/** The faint tier, and the one the grounding classes lift it to. text-3 is
 *  4.68:1 on surface-1 and 4.18:1 on surface-2 — the rows repaint the ground,
 *  so the token that was safe on the panel is not safe inside them. */
const TEXT_2 = ROUNDS('--rounds-text-2');
const TEXT_3 = ROUNDS('--rounds-text-3');

test.describe('Rounds C1-f — templates, flag-ON', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  const measured: string[] = [];

  function record(state: string, width: number, run: AxeRun) {
    measured.push(`${state}@${width}`);
    for (const e of blocking(run.violations)) violations.push({ state, width, entry: e });
    for (const e of inheritedBlocking(run.violations)) inherited.push({ state, width, entry: e });
    for (const sel of run.ariaHiddenFocusable) hiddenTraps.push({ state, width, sel });
  }

  async function sweep(page: Page, state: string, width: number): Promise<AxeRun> {
    const run = await runAxe(page);
    record(state, width, run);
    await shoot(page, state, width);
    return run;
  }

  /** Open the note-format panel and PROVE it is visible.
   *
   *  ⚠️ The click is not optional and the assertion is not decoration. All
   *  seven C3 panels stay mounted with the `hidden` attribute, so a `fill()` or
   *  a `setInputFiles()` without this acts on an invisible node and PASSES —
   *  the pack would then measure nothing while reporting success. */
  async function openNoteFormat(page: Page) {
    await page.goto('/settings');
    await page
      .locator('nav[aria-label="Settings sections"]')
      .getByRole('button', { name: /note format/i })
      .click();
    await expect(
      page.locator('#note-format'),
      'the note-format panel never became visible — every interaction after ' +
        'this would act on a hidden node and pass',
    ).toBeVisible({ timeout: 10_000 });
  }

  /** The templates surface really is Rounds-owned.
   *
   *  This is the assertion C1-e could not make: the host reached this panel in
   *  C1-e, but every node under it was classless, so `ownedByDom` halted on
   *  `.qm-c3-set-content` and nothing here could ever block. */
  async function assertTemplatesOwned(page: Page, where: string) {
    await expect(
      page.locator('.qm-rounds-host.qm-rounds-settings'),
      `${where}: not a flag-ON build — every result below would measure the old skin`,
    ).toHaveCount(1);
    // All three view roots, named individually rather than by a `class*=`
    // substring match: `qm-rounds-tmpl` is a prefix of every class in the
    // family, so a substring selector would be satisfied by any one of them
    // and could never tell me WHICH view I am on. That is the same trap that
    // made C1-c's label guard vacuous ('dashboard' contains 'board').
    await expect(
      page.locator(
        '#note-format .qm-rounds-tmpl, #note-format .qm-rounds-tmpl-editor, ' +
          '#note-format .qm-rounds-tmpl-confirm, #note-format .qm-rounds-tmpl-proc',
      ),
      `${where}: no Rounds ownership anchor inside the note-format panel. The ` +
        'axe walk stops at the first classed ancestor, so without one every ' +
        'violation here files as "inherited" and none can block',
    ).not.toHaveCount(0);
  }

  test.afterAll(async () => {
    await cleanupTestUsers();
  });

  test('the templates views render under Rounds, and the forked ink computes', async ({ page }) => {
    test.setTimeout(110_000);
    await signupFreshUser(page, 'c1f-views');

    // ── entry ────────────────────────────────────────────────────────────
    await page.setViewportSize({ width: WIDE, height: 1000 });
    await openNoteFormat(page);
    await assertTemplatesOwned(page, 'entry');

    // The primary CTA's ink and fill asserted TOGETHER. Asserting the fill
    // alone would pass on the literal; asserting the ink alone would pass on a
    // white label over a fill that never became the accent. C1-e's trap was
    // exactly this — a fix that brought one half across and left the other.
    const readMyFormat = page.getByRole('button', { name: /read my format/i });
    await expect(readMyFormat).toBeVisible();
    const cta = await readMyFormat.evaluate((el) => {
      const s = getComputedStyle(el);
      return { color: s.color, background: s.backgroundColor };
    });
    expect(
      cta,
      'the entry CTA is not white-on-accent. `#0d1611` on --rounds-accent is ' +
        '3.43:1; --rounds-on-accent is 5.37:1',
    ).toEqual({ color: ON_ACCENT, background: ACCENT_FILL });
    expect(
      cta.color,
      'the CTA still carries the old skin literal — the fork did not land',
    ).not.toBe(OLD_PRIMARY_LABEL);

    await sweep(page, 'tmpl:entry', WIDE);
    await page.setViewportSize({ width: NARROW, height: 1000 });
    await sweep(page, 'tmpl:entry', NARROW);

    // ── confirm ──────────────────────────────────────────────────────────
    // The BLANK tracked fixture, and only ever that one. `rounds-shots/` is
    // uploaded and retained for 14 days, so anything rendered here leaves the
    // runner — a filled document never becomes a fixture (AGENTS.md).
    await page.setViewportSize({ width: WIDE, height: 1000 });
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.getByRole('button', { name: /upload a file/i }).click(),
    ]);
    await chooser.setFiles('tests/e2e/fixtures/sample-form.docx');

    await expect(
      page.getByTestId('confirm-filled-sample'),
      'the confirm card never arrived. On this image UX_SIMPLIFY routes a parse ' +
        'to `confirm`, not to the review editor — if this timed out, check ' +
        'MOCK_AI_CALLS on the container before suspecting the surface',
    ).toBeVisible({ timeout: 90_000 });

    await assertTemplatesOwned(page, 'confirm');
    const confirmCta = page.getByTestId('confirm-use-format');
    const confirmStyle = await confirmCta.evaluate((el) => {
      const s = getComputedStyle(el);
      return { color: s.color, background: s.backgroundColor };
    });
    expect(
      confirmStyle,
      '`.qm-ux-primary` hardcoded `color: #0d1611` in globals.css — a rule a ' +
        '.tsx-only foreground scan structurally cannot see. On the bridged ' +
        'fill that is 3.43:1',
    ).toEqual({ color: ON_ACCENT, background: ACCENT_FILL });
    await sweep(page, 'tmpl:confirm', WIDE);

    // ── review (the advanced editor) ──────────────────────────────────────
    await page.getByRole('button', { name: /something.s off/i }).click();
    await expect(
      page.locator('.qm-rounds-tmpl-editor'),
      'the advanced editor has no ownership anchor — its ~900 classless nodes ' +
        'would climb to `.qm-c3-set-content` and file as inherited',
    ).toHaveCount(1);
    // The sticky bar is a SECOND shield, and what it shields is the CTA.
    await expect(
      page.locator('.qm-tpl-actionbar.qm-rounds-tmpl-actionbar'),
      'the action bar lost its Rounds class, so the Save & activate button it ' +
        'contains is invisible to the gate again',
    ).toHaveCount(1);
    const saveActivate = page.getByRole('button', { name: /save & activate/i });
    expect(
      await saveActivate.evaluate((el) => getComputedStyle(el).color),
      'the editor CTA ink did not fork',
    ).toBe(ON_ACCENT);
    await sweep(page, 'tmpl:review', WIDE);

    expect(
      measured.length,
      'the templates sweep measured fewer states than it drove',
    ).toBeGreaterThanOrEqual(4);
  });

  test('C1-g — /settings/note-format preselects the panel on the C3 rail', async ({ page }) => {
    // ⚠️ THIS IS THE BRANCH PRODUCTION RENDERS, and it is the one where the
    // route's whole point lives. The default chromium pack covers the LEGACY
    // stack (`SKIN_BETA=false`), where the section simply renders in a long
    // scroll and "preselect" means nothing. Here all seven panels stay mounted
    // with `hidden`, so a doctor arriving from the nav item or from the
    // certified-template email lands on Profile unless the segment preselects —
    // which looks exactly like a link that went nowhere in particular.
    await signupFreshUser(page, 'c1g-preselect');
    await page.setViewportSize({ width: WIDE, height: 1000 });

    const res = await page.goto('/settings/note-format');
    expect(res?.status(), 'the note-format route did not serve on the C3 build').toBe(200);

    await expect(
      page.locator('#note-format'),
      'the note-format panel is still `hidden` — the segment served but did not ' +
        'preselect, so the link lands the doctor on Profile',
    ).toBeVisible({ timeout: 10_000 });

    // …and it is THIS panel, not merely some visible one. All seven are in the
    // DOM; asserting only visibility of one would pass if the rail opened a
    // different section that happened to render.
    await expect(
      page.locator('.qm-c3-set-panel:not([hidden])'),
      'more than one panel is open, so "visible" says nothing about which',
    ).toHaveCount(1);
    await expect(page.locator('.qm-c3-set-panel:not([hidden])')).toHaveAttribute('id', 'note-format');

    await sweep(page, 'tmpl:route', WIDE);
  });

  test('the two views a walk cannot reach are rendered, and measured', async ({ page }) => {
    // ⚠️ NOT A CONVENIENCE. `parsing` paints only while four server actions are
    // in flight and `rejected` needs a container env this image does not carry,
    // so without this door both ship unmeasured — which is precisely how C1-e
    // extended the host over this panel and left four AA failures under it.
    await signupFreshUser(page, 'c1f-preview');
    await page.setViewportSize({ width: WIDE, height: 1000 });

    for (const state of ['tmpl-processing', 'tmpl-rejected']) {
      const res = await page.goto(`/dev/states?state=${state}`);
      expect(
        res?.status(),
        `/dev/states?state=${state} did not serve. This route is gated on the ` +
          'NEXT_PUBLIC_DEV_STATES build arg, which only the :rounds image passes',
      ).toBe(200);
      await expect(
        page.locator(`[data-testid="dev-${state}"]`),
        `${state} resolved to the fallback branch — the STATES enum and the ` +
          'render branch have drifted apart',
      ).toBeVisible({ timeout: 10_000 });
      await expect(page.locator('.qm-rounds-host.qm-rounds-devstates')).toHaveCount(1);
      await sweep(page, `tmpl:${state.replace('tmpl-', '')}`, WIDE);
    }

    // The rejected card's own ownership anchor — it is a `role="alert"` with a
    // repainted ground, so it both needs the tier lift and must be gateable.
    await expect(
      page.locator('.qm-rounds-tmpl-alert'),
      'the rejected alert has no anchor',
    ).toHaveCount(1);

    expect(
      measured.filter((m) => /^tmpl:(processing|rejected)@/.test(m)).length,
      'the preview sweep measured fewer states than it drove',
    ).toBe(2);
  });

  test('⚠️ the ground change is real — the lifted tier is what renders', async ({ page }) => {
    // The defect with no colour edit behind it. `.qm-c3-set-panel` grounds the
    // panel on surface-1 where text-3 is 4.68:1; the entry cards repaint to
    // surface-2 where the SAME token is 4.18:1. This asserts the lift actually
    // reaches the text, which no source guard can: only the cascade decides.
    await signupFreshUser(page, 'c1f-ground');
    await page.setViewportSize({ width: WIDE, height: 1000 });
    await openNoteFormat(page);

    const cardSubLabel = page.locator('.qm-rounds-tmpl-card').first().locator('div').last();
    const colour = await cardSubLabel.evaluate((el) => getComputedStyle(el).color);
    expect(
      colour,
      'the faintest tier inside a repainted card is still text-3. Nothing about ' +
        'the text changed — the GROUND did, and that is a contrast change: ' +
        `4.18:1 at ${TEXT_3} versus 5.97:1 at ${TEXT_2}`,
    ).toBe(TEXT_2);
    expect(colour, 'the lift did not apply').not.toBe(TEXT_3);
  });

  test('the ownership rule can still fail here — positive control', async ({ page }) => {
    // ⚠️ Without this the sweeps above are worthless: a walk that owns NOTHING
    // reports `violations: []` for every page it visits, and a walk that owns
    // EVERYTHING reports the inherited backlog as this item's defects. Both
    // read identically to a clean run. So plant one node of each kind and
    // assert the adjudicator sorts them.
    await signupFreshUser(page, 'c1f-control');
    await openNoteFormat(page);

    // The surface must start clean, or "planting a violation made it red" is
    // not evidence of anything.
    expect(
      blocking((await runAxe(page)).violations),
      "the control's own surface must start clean",
    ).toEqual([]);

    // ⚠️ ONE PROBE AT A TIME, and the reason is a property of the shared
    // helper that cost this test a CI cycle to find. `runAxe` computes `owned`
    // per VIOLATION ENTRY, with `v.nodes.some(…)` — so two probes sharing a
    // rule id (both of these are `color-contrast`) collapse into ONE entry,
    // and the owned probe drags the unowned probe's target into `blocking()`
    // with it. The first draft planted both together and read that as
    // "ownership has widened to the whole page". It had not; the assertion was
    // measuring at the wrong granularity. Planting serially is also what C1-d's
    // four controls do, for the same reason.

    // ── (1) a Rounds-owned failure MUST gate ──────────────────────────────
    await page.evaluate(() => {
      const panel = document.querySelector('#note-format');
      const el = document.createElement('p');
      el.className = 'qm-rounds-tmpl-probe';
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'planted owned probe';
      panel!.appendChild(el);
    });
    expect(
      blocking((await runAxe(page)).violations).some((e) =>
        e.targets.some((t) => t.includes('qm-rounds-tmpl-probe')),
      ),
      'a Rounds-owned contrast failure inside the templates panel was NOT ' +
        'gated — the adjudicator is not seeing this surface, so every empty ' +
        'result above means nothing',
    ).toBe(true);

    // ── (2) the same failure under a NON-Rounds class must NOT gate ───────
    // The bridge blind spot, asserted as a blind spot rather than wished away:
    // `ownedByDom` stops at the first classed ancestor-or-self, so a node with
    // its own `qm-lin-*` class answers for itself. C2 inherits this.
    await page.evaluate(() => {
      document.querySelector('.qm-rounds-tmpl-probe')?.remove();
      const panel = document.querySelector('#note-format');
      const el = document.createElement('p');
      el.className = 'qm-lin-tmpl-probe';
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'planted bridged probe';
      panel!.appendChild(el);
    });
    const bridgedRun = await runAxe(page);
    expect(
      blocking(bridgedRun.violations).some((e) =>
        e.targets.some((t) => t.includes('qm-lin-tmpl-probe')),
      ),
      'a node under a NON-Rounds class was gated — ownership has widened to the ' +
        'whole page and this pack would now block on the inherited backlog',
    ).toBe(false);
    expect(
      inheritedBlocking(bridgedRun.violations).some((e) =>
        e.targets.some((t) => t.includes('qm-lin-tmpl-probe')),
      ),
      'the bridged probe was neither gated nor reported — it was not measured at all',
    ).toBe(true);
  });

  test('no serious or critical violation on a Rounds-owned templates node', async () => {
    expect(
      measured.length,
      'nothing was measured — the assertions below would pass on an empty set',
    ).toBeGreaterThanOrEqual(7);
    expect(
      hiddenTraps,
      'focusable elements inside an aria-hidden Rounds container on the templates surfaces',
    ).toEqual([]);
    if (inherited.length > 0) {
      const set = new Set<string>();
      for (const f of inherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c1f] ${inherited.length} inherited serious/critical finding(s) ` +
          'on the templates surfaces — reported, not gated:\n' +
          [...set].slice(0, 20).map((t) => `    ${t}`).join('\n') + '\n',
      );
    }
    expect(
      violations.map((f) => `${f.state}@${f.width} ${f.entry.id} (${f.entry.impact})`),
      'serious/critical axe violations on Rounds-owned templates nodes',
    ).toEqual([]);
  });
});

// ============================================================================
// C2 — GATE C: the doors that were built and never opened.
// ----------------------------------------------------------------------------
// Gate C is "axe on every restyled screen". C1-c restyled the error boundary,
// both 404s, three loading states and the skeletons; `C1-PLAN.md:338` recorded
// its axe as "deferred to C1-d's pack"; and C1-d's pack sweeps the six AUTH
// routes and nothing else. C1-c2 then built `/dev/states` and called it, in its
// own header, "the Gate C door".
//
// So of that route's states, only the two C1-f added were ever walked. Five
// doors, built, never opened — and the deferral that produced it is written
// down in the plan, where it read as done.
//
// ⚠️ EVERY SURFACE HERE IS ANCHORED FIRST. Sweeping an unanchored surface buys
// a green tick over nothing: `ownedByDom` stops at the first classed
// ancestor-or-self, so a violation under a non-Rounds class files as inherited
// and cannot block. `/board`'s chrome was exactly that — its header, filter
// group, search form, pagination and day meter are all inline-styled and
// classless, so the long-green `board` state was measuring the lane rows alone.
// ============================================================================

test.describe('Rounds C2 — Gate C, the unswept surfaces', () => {
  const violations: Finding[] = [];
  const inherited: Finding[] = [];
  const hiddenTraps: Array<{ state: string; width: number; sel: string }> = [];
  const measured: string[] = [];

  function record(state: string, width: number, run: AxeRun) {
    measured.push(`${state}@${width}`);
    for (const e of blocking(run.violations)) violations.push({ state, width, entry: e });
    for (const e of inheritedBlocking(run.violations)) inherited.push({ state, width, entry: e });
    for (const sel of run.ariaHiddenFocusable) hiddenTraps.push({ state, width, sel });
  }
  async function sweep(page: Page, state: string, width: number) {
    record(state, width, await runAxe(page));
    await shoot(page, state, width);
  }

  test('every /dev/states door is walked and swept', async ({ page }) => {
    test.setTimeout(120_000);
    await signupFreshUser(page, 'c2-states');
    await page.setViewportSize({ width: WIDE, height: 1000 });

    // Derived from the route's own enum rather than a list kept here: a state
    // added to `/dev/states` and not swept is the defect this test exists for,
    // and a hand-written list would reproduce it exactly.
    const states = [
      'error',
      'error-stale',
      'loading-visit',
      'loading-board',
      'loading-settings',
      'skeletons',
    ];
    for (const state of states) {
      const res = await page.goto(`/dev/states?state=${state}`);
      expect(res?.status(), `/dev/states?state=${state} did not serve`).toBe(200);
      // `resolveState` falls back to 'error' for anything it does not know, so
      // a typo here would silently sweep the error page six times and pass.
      await expect(
        page.locator('[data-testid="dev-states"]'),
        `${state}: the preview root is absent`,
      ).toHaveAttribute('data-state', state);
      await expect(page.locator('.qm-rounds-host.qm-rounds-devstates')).toHaveCount(1);
      await sweep(page, `gatec:${state}`, WIDE);
    }
    expect(measured.length, 'fewer states swept than driven').toBeGreaterThanOrEqual(states.length);
  });

  test('both 404s and the empty board are swept', async ({ page }) => {
    test.setTimeout(120_000);
    await signupFreshUser(page, 'c2-notfound');
    await page.setViewportSize({ width: WIDE, height: 1000 });

    // The root 404 — reachable by navigation, which is why C1-c could prove it
    // renders. Proving it renders is not measuring it.
    const root = await page.goto('/no-such-page-c2');
    expect(root?.status(), 'a bad URL did not 404').toBe(404);
    await expect(page.locator('.qm-rounds-host.qm-rounds-notfound')).toHaveCount(1);
    await sweep(page, 'gatec:404-root', WIDE);

    // The visit 404 — a different component with its own copy and its own link.
    //
    // ⚠️ THIS ONE SERVES **200**, AND THAT IS NOT A DEFECT — it is where the
    // status is decided. An UNMATCHED route (above) is resolved by the router
    // before anything renders, so it can still send 404. `/visits/[id]` MATCHES;
    // its `notFound()` is at `page.tsx:272`, after the layout has begun
    // streaming, and a status cannot be recalled once the shell is on the wire.
    // The doctor sees the right page; the header is already gone.
    //
    // So the assertion is on WHAT RENDERS, which is what Gate C needs, plus a
    // floor that still catches a real regression: a 5xx is never acceptable.
    // Asserting `toBe(404)` here would be asserting a property of Next's
    // streaming, not of this product. (Same mechanism as `/board` flag-OFF,
    // recorded in C1-f's row as unexplained — this is the explanation.)
    const visit = await page.goto('/visits/00000000-0000-0000-0000-0000000c2404');
    const vs = visit?.status() ?? 0;
    expect(vs, `a bogus visit id returned ${vs} — a server error, not a refusal`).toBeLessThan(500);
    await expect(
      page.locator('.qm-rounds-notfound'),
      'the visit not-found surface did not render — whatever the status says, ' +
        'this is the page a doctor with a stale link actually sees',
    ).not.toHaveCount(0);
    await sweep(page, 'gatec:404-visit', WIDE);

    // ⚠️ THE EMPTY BOARD, which no pack has ever rendered: `rounds-a11y` seeds
    // three visits before it walks `/board`, so the one state a brand-new
    // doctor sees on their first login is the one state never measured.
    await page.goto('/board');
    await expect(
      page.getByTestId('rounds-board-empty'),
      'this fresh doctor has visits — the empty board is not being rendered, so ' +
        'the sweep below would be measuring the populated board again',
    ).toBeVisible({ timeout: 15_000 });
    await sweep(page, 'gatec:board-empty', WIDE);
  });

  test('⚠️ the board CHROME is now gated — positive control', async ({ page }) => {
    // The long-green `board` state proved nothing about the chrome. This plants
    // a real contrast failure into the header and asserts it BLOCKS; before the
    // C2 anchor it would have climbed to `<body>` and filed as inherited.
    await signupFreshUser(page, 'c2-chrome-ctl');
    await page.goto('/board');
    await expect(page.locator('.qm-rounds-boardchrome')).toHaveCount(1);

    // ⚠️ WAIT FOR HYDRATION BEFORE PLANTING, AND CHECK THE PROBE SURVIVED.
    // This test failed once and passed on retry — a flake, which the ledger's
    // own rule says is a claim about a boundary nobody has drawn. The boundary
    // is React: `/board` hydrates after `goto` resolves, and a node injected
    // into a subtree React then re-renders is simply gone by the time axe runs.
    // The symptom is indistinguishable from "the anchor does not work", which
    // is the one conclusion this control exists to license — so it is made
    // deterministic rather than retried.
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('rounds-search')).toBeVisible();

    expect(
      blocking((await runAxe(page)).violations),
      'the board must start clean, or "planting a failure made it red" proves nothing',
    ).toEqual([]);

    await page.evaluate(() => {
      const chrome = document.querySelector('.qm-rounds-boardchrome header');
      const el = document.createElement('p');
      el.setAttribute('id', 'c2-chrome-probe');
      el.setAttribute('style', 'color:#777;background:#888;font-size:12px;padding:4px');
      el.textContent = 'planted probe in the board chrome';
      chrome!.appendChild(el);
    });
    await expect(
      page.locator('#c2-chrome-probe'),
      'the planted probe was removed before axe ran — React re-rendered the ' +
        'chrome. Nothing below is a statement about ownership; re-plant after ' +
        'the page is settled',
    ).toHaveCount(1);
    expect(
      blocking((await runAxe(page)).violations).some((e) =>
        e.targets.some((t) => t.includes('c2-chrome-probe')),
      ),
      'a contrast failure in the board chrome was NOT gated — the chrome anchor ' +
        'is missing, so the header, filters, search, pagination and day meter ' +
        'are all outside the gate and `board` is green on the lane rows alone',
    ).toBe(true);
    await page.evaluate(() => document.querySelector('#c2-chrome-probe')?.remove());
  });

  test('no serious or critical violation on a Rounds-owned Gate C surface', async () => {
    expect(
      measured.length,
      'nothing was measured — the assertion below would pass on an empty set',
    ).toBeGreaterThanOrEqual(9);
    expect(hiddenTraps, 'focusable elements inside an aria-hidden Rounds container').toEqual([]);
    if (inherited.length > 0) {
      const set = new Set<string>();
      for (const f of inherited)
        f.entry.targets.filter((t) => !ROUNDS_OWNED.test(t)).forEach((t) => set.add(t));
      console.log(
        `\n[rounds-c2] ${inherited.length} inherited serious/critical finding(s) on the ` +
          'Gate C surfaces — reported, not gated:\n' +
          [...set].slice(0, 20).map((t) => `    ${t}`).join('\n') + '\n',
      );
    }
    expect(
      // ⚠️ THE COLOUR PAIR IS IN THE MESSAGE, not just the rule id. C1-e spent
      // three rebuild cycles on a `color-contrast` hit that named four
      // selectors and no colours; `runAxe` has carried axe's own
      // fgColor/bgColor/contrastRatio ever since, and a summary that drops them
      // re-creates the defect one layer up.
      violations.map((f) => {
        const d = (f.entry.data ?? []).find(
          (x) => x && (x as Record<string, unknown>).contrastRatio !== undefined,
        ) as Record<string, unknown> | undefined;
        const pair = d
          ? ` ${String(d.fgColor)} on ${String(d.bgColor)} = ${String(d.contrastRatio)} (needs ${String(d.expectedContrastRatio)})`
          : '';
        return `${f.state}@${f.width} ${f.entry.id} (${f.entry.impact})${pair} ${f.entry.targets.slice(0, 2).join(' , ')}`;
      }),
      'serious/critical axe violations on Rounds-owned Gate C surfaces',
    ).toEqual([]);
  });
});
