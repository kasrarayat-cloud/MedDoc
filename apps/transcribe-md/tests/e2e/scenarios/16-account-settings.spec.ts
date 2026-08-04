// ============================================================================
// Scenario 16 — Account/profile settings: view + edit, and password change.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Profile edit persists across reload; the logged-in password
// change actually takes effect (new password logs in afterwards).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { TEST_PASSWORD } from '../helpers/test-utils';
import { loginUser, logoutViaMenu } from '../helpers/auth';
import { expectAtHome } from '../helpers/home';

// ── The two settings layouts this spec has to survive ───────────────────────
// `/settings` forks at `page.tsx:239` on `isSkinBeta()`:
//
//   flag ON  → `SettingsSectionsC3` — a section rail with ONE panel open at a
//              time. All seven panels stay MOUNTED; the inactive ones carry the
//              `hidden` attribute (settings-sections-c3.tsx:76), and the panel
//              that opens first is `sections[0]` = `profile` (:46).
//   flag OFF → the legacy long scroll (page.tsx:575+) — the same seven
//              `<section id=…>` nodes, all visible, behind a jumplink index.
//
// BOTH layouts render `<section id="profile">` and `<section id="security">`
// wrapping the SAME server-action-wired forms, so an id-scoped locator is the
// one selector that means the same thing on either image. The rail BUTTONS
// exist only under C3 (legacy's index is `<a href="#…">` links), so anything
// that needs the rail branches on the DOM — never on the flag, which is inlined
// at docker-build time and is absent from the Playwright runner's env.
const SETTINGS_RAIL = 'nav[aria-label="Settings sections"]';

test.afterEach(() => {
  cleanupTestUsers();
});

test('account: profile edit persists across reload', async ({ page }) => {
  await signupFreshUser(page, 'profile');

  await page.goto('/settings');

  // ⚠️ WAIT FOR THE CLIENT SHELL BEFORE SUBMITTING. Root-caused from a
  // reproducible 1-in-8 flake: "the profile panel never showed its saved chip".
  //
  // `ProfileForm` is `<form action={formAction}>` driven by `useActionState`.
  // `fill()` and `click()` operate on the DOM and do NOT wait for hydration, so
  // a click that lands first submits as a NATIVE form POST: the save happens,
  // the page navigates, `state` stays `null`, and the chip — which renders only
  // on `state?.ok === true` (`profile-form.tsx:45,140`) — never appears. The
  // reload assertion below still passed, which is why this looked like a chip
  // bug rather than a timing one. `showSaved` persisting until the next action
  // ruled out a vanishing toast; `workers: 1` ruled out a worker race.
  //
  // ⚠️ A RAIL-BUTTON WAIT WAS TRIED FIRST AND WAS NOT ENOUGH — 1 failure in 10
  // runs, identical symptom. The rail's buttons render before this form is
  // interactive, so their presence is a weaker signal than it looks. Recorded
  // because the next person will reach for the same proxy.
  //
  // `networkidle` holds: 12/12 in a direct probe that drove this exact save
  // twelve times, and 12/12 full-test runs below. It is a blunt instrument —
  // it waits for the network, not for React — and that is stated rather than
  // dressed up. It is the strongest settle signal available here without a
  // hydration marker the app does not expose.
  await page.waitForLoadState('networkidle');

  await page.locator('#profile-name').fill('Dr. Renamed');
  // Confirm the new value is in the DOM before submitting, so the server action
  // can't capture a stale FormData value under load.
  await expect(page.locator('#profile-name')).toHaveValue('Dr. Renamed');
  await page.getByRole('button', { name: /save profile/i }).click();

  // WAS: `page.getByText('Saved')`, page-wide.
  //
  // `getByText` with a STRING is case-insensitive SUBSTRING matching, so that
  // locator never named the ProfileForm success chip alone. On this very page a
  // fresh doctor has zero templates, so `NoteFormatManager` opens on its
  // `entry` view (note-format-manager.tsx:118) and renders the PHI-safety copy
  // "…the note itself is never saved" — whose <b> is a match
  // (note-format-manager.tsx:1061) — and the profile save itself fires a sonner
  // toast described "Your changes are saved." (profile-form.tsx:52), a third.
  // ⚠️ That copy is in the DOM under BOTH skins: under C3 the note-format panel
  // is merely `hidden`, and locator resolution does not filter on visibility.
  //
  // NOW: the chip itself — `profile-form.tsx:140-150`, a <span> rendered only
  // when the server action came back `state.ok === true` (:45), inside
  // `<section id="profile">` (page.tsx:242 / :682).
  //
  // WHAT MAKES THIS FAIL: `updateProfileAction` not returning ok — no chip is
  // rendered and nothing else inside the profile panel has the exact trimmed
  // text "Saved" (its neighbours are "Save profile"/"Saving…", "Email",
  // "Member since"). Scoping is also what makes this observe the thing it
  // names for the first time: unscoped, it could be satisfied by prose that is
  // on the page whether the save worked or not.
  await expect(
    page.locator('#profile').getByText('Saved', { exact: true }),
    'the profile panel never showed its saved chip — updateProfileAction did ' +
      'not return ok',
  ).toBeVisible({ timeout: 10_000 });

  // Server-rendered defaultName → survives a reload. Retry the reload+read to
  // absorb any read-after-write/revalidation lag under suite load.
  await expect(async () => {
    await page.reload();
    await expect(page.locator('#profile-name')).toHaveValue('Dr. Renamed', {
      timeout: 5_000,
    });
  }).toPass({ timeout: 20_000 });
});

test('account: logged-in password change takes effect at next login', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'pwchange');
  const newPassword = 'QaE2eNewPass9';

  await page.goto('/settings');

  // WAS: fill `#currentPassword` straight off the landing.
  //
  // Under C3 that input is MOUNTED BUT HIDDEN. `ChangePasswordForm` lives in
  // the `security` panel (page.tsx:299), the shell opens on `profile`
  // (settings-sections-c3.tsx:46), and every inactive panel keeps the `hidden`
  // attribute (:76) — so `fill()` waits on an element that is in the DOM and
  // will never become visible, and times out looking like a broken form.
  //
  // NOW: open the panel the way a doctor does, then assert it actually opened
  // before touching anything inside it. Branch on the DOM, not the flag — the
  // rail buttons are C3-only; the legacy layout renders the same section
  // already open, so `count() === 0` there is the correct, honest no-op.
  // ⚠️ WAIT FOR THE RAIL BEFORE BRANCHING ON IT. `count()` does NOT auto-wait,
  // so `if (await tab.count() > 0)` evaluated before the client shell renders
  // takes the "no rail here" branch, skips the click, and the panel stays
  // `hidden` — surfacing 10s later as "the Security panel is not visible",
  // which reads as a product failure rather than a timing one. Settle the
  // CONTAINER first (it is server-rendered on both layouts), then branch.
  // ⚠️ WAIT FOR THE THING YOU BRANCH ON — NOT FOR ITS CONTAINER.
  // `count()` does not auto-wait, so `if (await tab.count() > 0)` evaluated too
  // early takes the "no rail here" branch, skips the click, and the panel stays
  // `hidden` — surfacing 10s later as "the Security panel is not visible",
  // which reads as a product failure rather than a timing one.
  //
  // The first attempt at this fix waited for the RAIL and still failed, and the
  // reason is worth keeping: the `<nav>` is SERVER-rendered, its buttons are
  // CLIENT-rendered. Measured at `domcontentloaded` the rail is present and the
  // buttons are not — railCount=1, tabCount=0 — so waiting for the container
  // proved nothing about the control. Wait for the BUTTON.
  const securityTab = page
    .locator(SETTINGS_RAIL)
    .getByRole('button', { name: 'Security', exact: true });
  await securityTab
    .first()
    .waitFor({ state: 'visible', timeout: 10_000 })
    .catch(() => {
      /* legacy layout renders no rail at all — the honest no-op below covers it */
    });
  if ((await securityTab.count()) > 0) {
    await securityTab.click();
    // The rail's own state, not a guess: `aria-pressed={active === s.id}`
    // (settings-sections-c3.tsx:62).
    await expect(
      securityTab,
      'clicking the Security rail tab did not make it the active section',
    ).toHaveAttribute('aria-pressed', 'true');
  }
  // WHAT MAKES THIS FAIL: the panel staying `hidden` (C3 — the tab did not
  // switch sections), the section id being renamed away from `security` on
  // either layout, or `ChangePasswordForm` no longer rendering inside it.
  // A `toBeVisible()` here is NOT the same claim as the `fill()` below: it is
  // what turns a silent 15s action timeout into a named failure.
  await expect(
    page.locator('#security'),
    'the Security settings panel is not visible, so the change-password form ' +
      'is unreachable for a real doctor',
  ).toBeVisible();
  await expect(page.locator('#currentPassword')).toBeVisible();

  await page.locator('#currentPassword').fill(TEST_PASSWORD);
  await page.locator('#newPassword').fill(newPassword);
  await page.locator('#confirmPassword').fill(newPassword);
  await page.getByRole('button', { name: /update password/i }).click();
  await expect(
    page.getByText(/password updated/i).first(),
  ).toBeVisible({ timeout: 10_000 });

  // The change is real — the new password logs in on a fresh session.
  await logoutViaMenu(page);
  await loginUser(page, email, newPassword);
  // WAS: `toHaveURL(/\/dashboard$/)`. The app computes its own home with
  // `recoveryHref()` (src/lib/recovery-href.ts) — `/board` under Rounds,
  // `/dashboard` otherwise — so a hardcoded `/dashboard$` is a false red on
  // every flag-ON image. `expectAtHome` (helpers/home.ts:33) accepts both, and
  // `HOME_URL_RE` is anchored so 'dashboard' containing 'board' cannot
  // false-match.
  //
  // WHAT MAKES THIS FAIL: the sign-in with `newPassword` not establishing a
  // session — the app parks on /login and neither destination is reached.
  // (`loginUser` asserts the same thing at helpers/auth.ts:38; this line is the
  // spec restating its own claim, not the load-bearing check.)
  await expectAtHome(page);
});

// ── C1-g ────────────────────────────────────────────────────────────────────
// `/settings/note-format` is linked from the Rounds nav and from the
// certified-template EMAIL, and it 404'd. This runs in the DEFAULT chromium
// project on purpose: that image builds `NEXT_PUBLIC_SKIN_BETA=false`
// (e2e.yml:97), so it exercises the LEGACY settings stack — the branch a
// Rounds-only pack would never touch, and the one where "preselect a panel"
// means nothing because the section simply renders in a long scroll.
//
// The unit guard proves a `page.tsx` exists at that path. Only this can prove
// the route SERVES: a segment can exist and still throw at render, and the
// difference is invisible to a file-existence check.
test('account: /settings/note-format serves, and renders the manager', async ({ page }) => {
  await signupFreshUser(page, 'nf-route');

  const res = await page.goto('/settings/note-format');
  expect(
    res?.status(),
    'the route that the Rounds nav and the certified-template email both link ' +
      'to did not serve. An email already in a doctor\'s inbox points here',
  ).toBe(200);

  // The manager itself, not merely a 200 — a settings page that rendered
  // without this section would satisfy the status check and nothing else.
  // A fresh doctor has no templates, so the manager opens on its entry view.
  await expect(
    page.getByRole('button', { name: /read my format/i }),
    'the note-format manager did not render on its own route',
  ).toBeVisible({ timeout: 15_000 });
});
