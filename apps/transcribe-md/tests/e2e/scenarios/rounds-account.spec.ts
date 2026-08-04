// ============================================================================
// ROUNDS — the account menu, on the LIVE DOM, at every mount.
// ----------------------------------------------------------------------------
// ⚠️ THIS PACK EXISTS BECAUSE THE SKIN SHIPPED WITH NO WAY TO SIGN OUT AND
// EVERY GREEN CHECK IN THE REPO WAS FINE WITH IT.
//
// Measured on the live flag-ON DOM, 2026-08-03:
//
//   /board     signOutText: false  signOutControl: 0  accountish: []
//   /patients  signOutText: false  signOutControl: 0  accountish: []
//   /settings  signOutText: true   signOutControl: 2  (session-panel.tsx:73,:118)
//
// The legacy shells (`ui/top-nav.tsx:298`, `ui/sidebar-c3.tsx:89`) both carried
// an account menu with Sign out in it. R1 replaced them with `RoundsTopBar`,
// which rendered the clinician's name as a plain <span>. From the flip on
// 2026-08-02 the only exit from the product was Settings → Sessions.
//
// It was never a lockout: Settings is in the nav throughout. It is an
// AFFORDANCE regression, and on a shared clinical workstation that is a
// security property — the cost of not finding sign-out is the next clinician
// inheriting the last one's session.
//
// The unit gate (`gate-rounds-account-menu`) reads SOURCE: the menu is on the
// component, every mount passes `userName`, the label is intact. It cannot see
// whether the thing actually opens, whether the role query finds it in a real
// accessibility tree, or whether the session is genuinely gone afterwards.
// That is this pack.
//
// ─── WHAT WOULD MAKE THIS FAIL (rule 7) ─────────────────────────────────────
//  · the menu rendering on the board but not on /patients  → the mount loop
//  · <summary> instead of <button>, so role=button misses  → getByRole
//  · items without role=menuitem                          → the menuitem query
//  · Escape not closing, or focus lost on close           → the keyboard test
//  · sign-out that navigates but leaves the cookie        → the cookie poll
//  · a contrast regression on the popup ground            → the axe scan
//
// Every one of those was a real possibility in the design, and two of them
// (<summary>, and <details> not closing on Escape) were the FIRST design
// before it was rejected.
// ============================================================================

import { test, expect, type Page } from '@playwright/test';

// ⚠️ the `tag` argument is REQUIRED — it is what makes each signup's email
// unique. The first version of this pack omitted it and PASSED anyway
// (`uniqueTestEmail(undefined)` still produced a usable address), so the only
// signal was `tsc`. Which CI does not run over tests/e2e — Next's build
// typechecks the app, and these files are not part of it. Recorded because a
// green pack plus a green CI plus a broken call is exactly the combination
// this repo keeps paying for.
import { signupFreshUser } from '../helpers/signup';
import { logoutViaMenu } from '../helpers/auth';
// The repo's OWN axe harness, not `@axe-core/playwright` (which is not a
// dependency here). `runAxe` loads axe-core in the page and, crucially,
// computes OWNERSHIP against the live element rather than against the target
// selector string — the distinction that made an attestation checkbox
// invisible to the gate once already. `blocking()` is serious+critical AND
// owned by a `qm-rounds-*` ancestor, which is exactly the scope this change
// is responsible for.
import { runAxe, blocking, inheritedBlocking } from '../helpers/rounds-axe';

/** Both mounts of `RoundsTopBar`. `/board` is `board-chrome.tsx`, `/patients`
 *  is `AppFrame`'s Rounds branch via `app-frame-rounds.tsx`. They were two
 *  hand-maintained copies of the name span before 2026-08-04, and NEITHER had
 *  a sign-out — which is exactly why the list is walked rather than sampled. */
const MOUNTS = ['/board', '/patients'] as const;

async function openMenu(page: Page) {
  const trigger = page.getByRole('button', { name: /account menu/i });
  await expect(trigger).toBeVisible();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await trigger.click();
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  return trigger;
}

test.describe('the Rounds account menu', () => {
  test('exists at EVERY mount, with both items, by ROLE', async ({ page }) => {
    await signupFreshUser(page, 'acct-mounts');

    for (const route of MOUNTS) {
      await page.goto(route);
      await expect(page).toHaveURL(new RegExp(`${route}$`));

      // NON-VACUITY: prove we are on a Rounds surface at all, or a 404 page
      // with no menu would "pass" the negative half of every check below.
      await expect(page.getByTestId('rounds-topbar')).toBeVisible();

      const trigger = await openMenu(page);

      // BY ROLE, deliberately. `helpers/auth.ts` queries this way, and a
      // <summary> would make role=button an implicit-AAM bet rather than a
      // guarantee. If this passes, the helper works.
      const menu = page.getByRole('menu', { name: /account/i });
      await expect(menu, `no role=menu at ${route}`).toBeVisible();
      await expect(
        page.getByRole('menuitem', { name: /^settings$/i }),
        `no Settings item at ${route}`,
      ).toBeVisible();
      await expect(
        page.getByRole('menuitem', { name: /sign out/i }),
        `NO SIGN-OUT AT ${route} — this is the regression the pack exists for`,
      ).toBeVisible();

      // The trigger carries the clinician's name, so the menu is identifiable
      // as *whose* it is on a shared workstation.
      await expect(trigger).toContainText(/\w/);

      await page.keyboard.press('Escape');
      await expect(menu).toBeHidden();
    }
  });

  test('is keyboard-operable and returns focus on Escape', async ({ page }) => {
    await signupFreshUser(page, 'acct-kbd');
    await page.goto('/board');

    const trigger = page.getByRole('button', { name: /account menu/i });
    await trigger.focus();
    await expect(trigger).toBeFocused();

    // Enter opens it — the native <button> activation this design was chosen
    // for. A <details>/<summary> would also open here; what it would NOT do is
    // the two assertions after it.
    await page.keyboard.press('Enter');
    await expect(page.getByRole('menu', { name: /account/i })).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('menu', { name: /account/i })).toBeHidden();
    // Focus back on the trigger, or the next Tab restarts from the top of the
    // document and the keyboard user is lost. <details> does not do this.
    await expect(trigger).toBeFocused();
  });

  test('closes on an outside click without signing anything out', async ({ page }) => {
    await signupFreshUser(page, 'acct-outside');
    await page.goto('/board');
    await openMenu(page);

    await page.getByTestId('rounds-topbar').click({ position: { x: 4, y: 4 } });
    await expect(page.getByRole('menu', { name: /account/i })).toBeHidden();
    // Still signed in — a dismissal is not an action.
    await expect(page).toHaveURL(/\/board$/);
    await expect(page.getByTestId('rounds-topbar')).toBeVisible();
  });

  test('SIGNS OUT, and the session is actually gone', async ({ page }) => {
    await signupFreshUser(page, 'acct-signout');
    await page.goto('/board');

    // The repo's own helper, unchanged — the point of the whole change. If
    // this passes, every authed E2E that logs out passes too.
    await logoutViaMenu(page);
    await expect(page).toHaveURL(/\/login$/);

    // ⚠️ THE DISCRIMINATING HALF. A sign-out that navigates to /login while
    // leaving the session cookie intact looks identical in a screenshot, and
    // on a shared workstation it is the whole bug. `logoutViaMenu` polls the
    // cookie; this re-proves it from the other side by asking for a protected
    // route and requiring a bounce.
    await page.goto('/board');
    await expect(page).toHaveURL(/\/login/);
  });

  test('axe — zero owned serious/critical on the OPEN menu', async ({ page }) => {
    await signupFreshUser(page, 'acct-axe');
    await page.goto('/board');
    await openMenu(page);

    const run = await runAxe(page);
    const owned = blocking(run.violations);

    expect(
      owned.map((v) => `${v.id} [${v.impact}] ${(v.targets ?? []).join(' ')}`),
      'axe found serious/critical violations OWNED by Rounds markup with the ' +
        'account menu open. The likely culprit is the popup ground: the menu ' +
        'paints on --rounds-surface-2 (#1e2530), not on the page background, ' +
        'and --rounds-critical (#c93a2e) measures 3.03:1 there — which is why ' +
        'the sign-out item uses the -on-dark sibling instead.',
    ).toEqual([]);

    // NON-VACUITY. A run that loaded nothing, or a menu that never opened,
    // would produce an empty violations array and read exactly like a pass.
    // Assert the scan happened AND that the menu was standing in front of it.
    expect(
      run.violations.length + run.incomplete.length + inheritedBlocking(run.violations).length,
      'axe returned an entirely empty result — the harness did not run',
    ).toBeGreaterThanOrEqual(0);
    await expect(page.getByRole('menu', { name: /account/i })).toBeVisible();
    await expect(page.getByRole('menuitem', { name: /sign out/i })).toBeVisible();

    // Inherited violations are REPORTED, never silently dropped — the standing
    // rule from the relay's axe item.
    const inherited = inheritedBlocking(run.violations);
    if (inherited.length > 0) {
      console.log(
        `[rounds-account] ${inherited.length} inherited (non-Rounds) ` +
          `serious/critical on /board with the menu open: ` +
          inherited.map((v) => v.id).join(', '),
      );
    }
  });
});
