import { test, expect } from '@playwright/test';

// ============================================================================
// Product separation matrix — verifies that the F9-1 entitlement gate +
// the cross-app redirect UX hold together at both login surfaces.
//
// Pre-conditions (set up by the audit harness once, not by the test):
//   qa-tmd@quillmd.local        → products = {TRANSCRIBE_MD}
//   qa-pro@quillmd.local        → products = {MEDDOC_PRO}
//   qa-bundle@quillmd.local     → products = {MEDDOC_PRO, TRANSCRIBE_MD}
//   qa-noprod@quillmd.local     → products = {}
//
// All four share the password QaTestPassword2024! (matches the existing
// qa-audit user). The four IDs are stable so .env.test stays terse.
//
// All twelve cells are exercised:
//   - TMD-only / PRO-only / Bundle / No-products at app.quillmd.com
//   - same four user-types at pro.quillmd.com
//   - wrong-password and non-existent-email checks at both apps
// ============================================================================

const PASSWORD = 'QaTestPassword2024!';
const APP_URL = process.env.TEST_APP_URL ?? 'https://app.quillmd.com';
const PRO_URL = process.env.TEST_PRO_URL ?? 'https://pro.quillmd.com';

interface Cred {
  email: string;
  password?: string;
}

const TMD_ONLY: Cred = { email: 'qa-tmd@quillmd.local' };
const PRO_ONLY: Cred = { email: 'qa-pro@quillmd.local' };
const BUNDLE: Cred = { email: 'qa-bundle@quillmd.local' };
const NO_PRODUCT: Cred = { email: 'qa-noprod@quillmd.local' };
const NONEXISTENT: Cred = { email: 'definitely-not-a-real-user@quillmd.local' };
const WRONG_PW: Cred = {
  email: 'qa-bundle@quillmd.local',
  password: 'wrong-password-on-purpose',
};

// ---------------------------------------------------------------------------
// Helpers — keep the per-test bodies short.
// ---------------------------------------------------------------------------

async function tmdLogin(
  page: import('@playwright/test').Page,
  email: string,
  password: string
) {
  await page.goto(`${APP_URL}/login`);
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
}

async function proLogin(
  page: import('@playwright/test').Page,
  email: string,
  password: string
) {
  await page.goto(`${PRO_URL}/login`);
  // The CRM login uses the input id (not a <label>), so target by name.
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
}

// Each test case awaits ONE of three terminal states:
//   1. URL becomes /dashboard (or /system-admin)         → success
//   2. A "Go to <other app>" link appears on the page    → cross-app redirect
//   3. A generic "Invalid email or password" / inline error appears
async function expectTmdSuccess(page: import('@playwright/test').Page) {
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
  expect(page.url()).toMatch(/\/dashboard/);
}
async function expectProSuccess(page: import('@playwright/test').Page) {
  await page.waitForURL(/\/(dashboard|system-admin)/, { timeout: 15_000 });
  expect(page.url()).toMatch(/\/(dashboard|system-admin)/);
}
async function expectCrossAppRedirectToPro(
  page: import('@playwright/test').Page
) {
  // On TMD: surfaces a "Go to MedDoc Pro" link.
  await expect(
    page.getByRole('link', { name: /go to medd?oc pro/i })
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login/);
}
async function expectCrossAppRedirectToTmd(
  page: import('@playwright/test').Page
) {
  // On CRM: surfaces a "Go to TranscribeMD" link.
  await expect(
    page.getByRole('link', { name: /go to transcribe ?md/i })
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login/);
}
async function expectGenericFailureTmd(
  page: import('@playwright/test').Page
) {
  // Generic = NOT signed in, NOT showing the cross-app link.
  await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  await expect(
    page.getByRole('link', { name: /go to medd?oc pro/i })
  ).toHaveCount(0);
}
async function expectGenericFailurePro(
  page: import('@playwright/test').Page
) {
  await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  await expect(
    page.getByRole('link', { name: /go to transcribe ?md/i })
  ).toHaveCount(0);
}

// ---------------------------------------------------------------------------
// Matrix
// ---------------------------------------------------------------------------

test.describe('Product separation — app.quillmd.com (TranscribeMD)', () => {
  test('TMD-only user → success', async ({ page }) => {
    await tmdLogin(page, TMD_ONLY.email, PASSWORD);
    await expectTmdSuccess(page);
  });

  test('PRO-only user → cross-app redirect to MedDoc Pro', async ({ page }) => {
    await tmdLogin(page, PRO_ONLY.email, PASSWORD);
    await expectCrossAppRedirectToPro(page);
  });

  test('Bundle user → success', async ({ page }) => {
    await tmdLogin(page, BUNDLE.email, PASSWORD);
    await expectTmdSuccess(page);
  });

  test('No-product user → generic reject', async ({ page }) => {
    await tmdLogin(page, NO_PRODUCT.email, PASSWORD);
    await expectGenericFailureTmd(page);
  });

  test('Wrong password → generic reject', async ({ page }) => {
    await tmdLogin(page, WRONG_PW.email, WRONG_PW.password!);
    await expectGenericFailureTmd(page);
  });

  test('Non-existent email → generic reject', async ({ page }) => {
    await tmdLogin(page, NONEXISTENT.email, PASSWORD);
    await expectGenericFailureTmd(page);
  });
});

// ⚠️ SKIPPED 2026-08-04, DECLARED — this whole describe block logs INTO
// pro.quillmd.com, which no longer answers.
//
// pro.quillmd.com was taken offline on 2026-08-04: a publicly reachable,
// PHI-capable WRITE path into the production clinical database, decommissioned
// since 2026-05-04 and still serving, sharing one DATABASE_URL with the live
// app. Owner ruling — the capability dies now; the CODE deletion is item A6 in
// docs/foundation/RELAY.md, and this file is retired for good at that point.
// See DEPLOYMENT_RUNBOOK §3.5.
//
// SKIPPED RATHER THAN DELETED, on purpose. This file and the two smoke
// assertions were, by DISCOVERY §A.7's own reckoning, the only things keeping
// the CRM "in use". Deleting the block now would erase the record of what the
// twelve-cell matrix used to prove, three weeks before the deletion PR that
// should be reading it. `.skip` keeps the specification visible and stops the
// nightly going red for an intended state.
//
// ⚠️ THE SIX APP-SIDE CELLS ABOVE STAY LIVE, INCLUDING
// 'PRO-only user → cross-app redirect to MedDoc Pro'. That one now asserts a
// redirect to a host that answers 410 — which is the CORRECT thing to assert
// today: the redirect branch still exists in `actions/auth.ts:227-241` and is
// retired in item A5 together with the fate of the 12 MEDDOC_PRO-only
// accounts. If it starts failing, that is a real signal about A5, not noise.
test.describe.skip('Product separation — pro.quillmd.com (MedDoc Pro)', () => {
  test('PRO-only user → success', async ({ page }) => {
    await proLogin(page, PRO_ONLY.email, PASSWORD);
    await expectProSuccess(page);
  });

  test('TMD-only user → cross-app redirect to TranscribeMD', async ({ page }) => {
    await proLogin(page, TMD_ONLY.email, PASSWORD);
    await expectCrossAppRedirectToTmd(page);
  });

  test('Bundle user → success', async ({ page }) => {
    await proLogin(page, BUNDLE.email, PASSWORD);
    await expectProSuccess(page);
  });

  test('No-product user → generic reject', async ({ page }) => {
    await proLogin(page, NO_PRODUCT.email, PASSWORD);
    await expectGenericFailurePro(page);
  });

  test('Wrong password → generic reject', async ({ page }) => {
    await proLogin(page, WRONG_PW.email, WRONG_PW.password!);
    await expectGenericFailurePro(page);
  });

  test('Non-existent email → generic reject', async ({ page }) => {
    await proLogin(page, NONEXISTENT.email, PASSWORD);
    await expectGenericFailurePro(page);
  });
});
