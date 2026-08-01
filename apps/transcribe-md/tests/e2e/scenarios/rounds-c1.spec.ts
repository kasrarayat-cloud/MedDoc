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

/** Widths the spec's screenshot clause names. */
const WIDE = 1440;
const NARROW = 1024;

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
        `${f.entry.targets.slice(0, 4).join(', ')}`),
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
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
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

  test('the ownership rule can fail — three positive controls', async ({ page }) => {
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
    cleanupTestUsers();
  });
});
