// ============================================================================
// Scenario 15 — MFA (TOTP) enrollment + login enforcement.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Enroll → verify with a real TOTP (generated in-test from the
// enrollment secret) → recovery codes shown. Then prove MFA is ENFORCED: a
// password-only login no longer reaches the dashboard — it demands the second
// factor. (If a password-only login DID reach the dashboard, that would be a
// high-severity auth bug — this spec is the regression guard for it.)
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { TEST_PASSWORD } from '../helpers/test-utils';
import { generateTotp, logoutViaMenu, totpSecretFromUri } from '../helpers/auth';

import { expectAtHome, HOME_URL_RE } from '../helpers/home';

test.afterEach(() => {
  cleanupTestUsers();
});

test('MFA: enroll TOTP → verify → recovery codes, then enforced at login', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'mfa');

  await page.goto('/settings/security/mfa');
  await page.getByRole('button', { name: /generate qr code/i }).click();

  // The verify step renders the otpauth:// URI (with the base32 secret) for
  // manual entry — read the secret straight out of it.
  const uriCode = page.locator('code').filter({ hasText: 'otpauth://' }).first();
  await expect(uriCode).toBeVisible({ timeout: 10_000 });
  const secret = totpSecretFromUri((await uriCode.textContent()) ?? '');

  await page.locator('#mfa-token').fill(generateTotp(secret));
  await page.getByRole('button', { name: /verify \+ enable/i }).click();

  // Step 3 — exactly 10 single-use recovery codes, shown once.
  await expect(
    page.getByRole('heading', { name: /save your recovery codes/i }),
  ).toBeVisible({ timeout: 10_000 });
  const recoveryBlock = page.locator('pre');
  await expect(recoveryBlock).toBeVisible();
  const codes = ((await recoveryBlock.textContent()) ?? '')
    .trim()
    .split('\n')
    .filter(Boolean);
  expect(codes.length).toBe(10);

  // Finish enrollment → back to /settings, then log out.
  await page.getByRole('button', { name: /saved them/i }).click();
  await logoutViaMenu(page);

  // ENFORCEMENT: email + password alone must NOT log in — the 2nd factor field
  // appears instead of a dashboard redirect.
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(page.locator('#totpToken')).toBeVisible({ timeout: 10_000 });
  // ⚠️ THIS LINE WAS `not.toHaveURL(/\/dashboard/)` AND IT WENT VACUOUS WHEN
  // THE ROUNDS SKIN SHIPPED. `actions/auth.ts:353` returns `recoveryHref()`,
  // which is `/board` under Rounds — so a login that WRONGLY SUCCEEDED lands on
  // /board and satisfies "not /dashboard". The assertion could no longer fail.
  //
  // Being precise about what that cost, because the first telling of it
  // overstated the damage: MFA enforcement was still guarded the whole time by
  // the `#totpToken` visibility check on the line above, which a successful
  // login would fail. One of two assertions went quiet, not the gate. A
  // weakened belt-and-braces, not an open door.
  //
  // Now written against the authenticated home BY BOTH ITS NAMES, so it holds
  // flag-ON and flag-OFF alike. A rollback to the flag-OFF image must not turn
  // this into a false red.
  //
  // 2026-08-04 — TIGHTENED FROM A HAND-ROLLED `/\/(board|dashboard)$/` TO THE
  // SHARED `HOME_URL_RE` (`helpers/home.ts:30`), for two reasons:
  //   1. The hand-rolled copy dropped the helper's `(\?.*)?` clause, and on a
  //      NEGATED assertion a narrower pattern is a HOLE, not a stricter check —
  //      a login that wrongly succeeded and landed on `/board?anything` fails to
  //      match, so `not.toHaveURL` passes. Re-opening the same vacuity in a
  //      smaller doorway is not a fix.
  //   2. The destination has ONE definition. `helpers/home.ts` mirrors the
  //      product's `recoveryHref()` (`src/lib/recovery-href.ts:30`, which
  //      `actions/auth.ts:353` returns as the post-login redirect). At item F,
  //      when home collapses to `/board` alone, the helper is what gets edited —
  //      a private copy here would silently keep accepting `/dashboard`.
  //
  // WHAT WOULD MAKE THIS FAIL: MFA enforcement regressing so that email +
  // password alone completes the sign-in. `loginAction` would return
  // `redirect: recoveryHref()` instead of `mfaRequired: true`, `login-form.tsx:55`
  // would `router.push` it, and the URL would be the app home — with or without
  // a query string.
  await expect(page).not.toHaveURL(HOME_URL_RE);

  // Completing the second factor logs in.
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.locator('#totpToken').fill(generateTotp(secret));
  await page.getByRole('button', { name: /^sign in$/i }).click();
  // Same reasoning as above, positive direction: the authenticated home has two
  // legitimate spellings right now and the claim is "login reached it".
  //
  // 2026-08-04 — was a hand-rolled `toHaveURL(/\/(board|dashboard)$/, 15_000)`.
  // `expectAtHome` (`helpers/home.ts:33`) IS that assertion — same 15s default,
  // same regex, plus a failure message that distinguishes "auto-login failed"
  // from "a redirect moved and nobody told the helper". Calling it keeps the
  // negative above and this positive reading from one definition, so they cannot
  // drift apart.
  //
  // WHAT WOULD MAKE THIS FAIL: the second factor not actually completing the
  // login — a wrong/rejected TOTP leaves the form on `/login` with the error
  // from `actions/auth.ts:312`, which is not the app home.
  await expectAtHome(page);
});
