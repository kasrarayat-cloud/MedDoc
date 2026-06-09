// ============================================================================
// Scenario 26 — admin / SUPER_ADMIN surface: privilege boundary + tooling
// ----------------------------------------------------------------------------
// 🔴 SECURITY-CRITICAL. The /admin/* platform surface (user management, audit
// logs, HIPAA console, threats, usage, BullMQ queues) is gated on the
// `Product.SUPER_ADMIN` entitlement — enforced SERVER-side on every page
// (admin/layout.tsx → notFound()) and every API route (admin-api-gate.ts →
// 404), with a DB re-check of products so a stale JWT can't grant access.
//
// These specs assert the boundary is real, not UI-cloaked: a non-admin hitting
// admin routes/APIs DIRECTLY (bypassing the UI, riding the auth cookie) is
// rejected 404 — never served. They also cover the SUPER_ADMIN positive path,
// the queue dashboard, and key admin actions asserting the real DB EFFECT.
//
// Runs in the default chromium project against the standard qa stack (no
// special app flag). SUPER_ADMIN is seeded by promoting a freshly-signed-up
// user via the guarded psql channel (manual DB grant — the product's only
// path). MOCK_AI_CALLS=true.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { getAdminUser, promoteToSuperAdmin } from '../helpers/admin';

test.afterEach(() => {
  cleanupTestUsers();
});

// A representative spread of admin GET endpoints — list / system / audit /
// usage / threats. The boundary must hold on EVERY one (not just the page).
const ADMIN_API_GET = [
  '/api/admin/users',
  '/api/admin/system/health',
  '/api/admin/audit-logs',
  '/api/admin/usage/summary',
  '/api/admin/threats',
];

test('scenario 26: privilege boundary — a non-admin doctor is DENIED admin access SERVER-side (404), not just UI-cloaked', async ({
  page,
}) => {
  // A perfectly ordinary, fully-authenticated doctor (no SUPER_ADMIN product).
  await signupFreshUser(page, 'adm-deny');

  // 1. The admin PAGE is server-side notFound — a 404, not a 200-with-redirect
  //    UI cloak. (admin/layout.tsx calls notFound() before rendering anything.)
  const pageResp = await page.goto('/admin');
  expect(pageResp?.status(), '/admin must 404 for a non-admin').toBe(404);

  // 2. EVERY representative admin API, hit DIRECTLY with the authed cookie
  //    (bypassing the UI entirely), returns 404 — and crucially NEVER 200.
  //    This is the server-enforcement proof (same UI-vs-server gap class as
  //    the logout + sign-gate bugs).
  for (const path of ADMIN_API_GET) {
    const res = await page.request.get(path);
    expect(res.status(), `GET ${path} must be 404 for a non-admin`).toBe(404);
  }

  // 3. A MUTATING admin action hit directly is blocked by the gate BEFORE any
  //    effect — a non-admin cannot escalate privilege or suspend anyone.
  const grant = await page.request.post(
    '/api/admin/users/some-user-id/grant-admin',
    { data: { confirmEmail: 'whoever@example.com' } },
  );
  expect(grant.status(), 'grant-admin must be 404 for a non-admin').toBe(404);

  const suspend = await page.request.post(
    '/api/admin/users/some-user-id/suspend',
    { data: { reason: 'should never run' } },
  );
  expect(suspend.status(), 'suspend must be 404 for a non-admin').toBe(404);
});

test('scenario 26: unauthenticated access to an admin API is denied (404) — route existence not revealed', async ({
  browser,
}) => {
  const ctx = await browser.newContext(); // no auth cookie
  const res = await ctx.request.get('/api/admin/users');
  expect(res.status()).toBe(404);
  await ctx.close();
});

test('scenario 26: SUPER_ADMIN positive path — reaches /admin and the admin API serves data', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'adm-super');
  promoteToSuperAdmin(email); // manual DB grant: + SUPER_ADMIN product, + mfaEnabled

  // The admin page now renders (gate passes: SUPER_ADMIN product re-checked
  // from DB + mfaEnabled + fresh session). NOT redirected to MFA enrollment.
  const resp = await page.goto('/admin');
  expect(resp?.status(), '/admin must render for a SUPER_ADMIN').toBe(200);
  await expect(page).toHaveURL(/\/admin$/);

  // The admin API now serves the user list (was 404 for the non-admin above).
  const users = await page.request.get('/api/admin/users');
  expect(users.status()).toBe(200);
  const body = (await users.json()) as { users?: unknown };
  expect(Array.isArray(body.users)).toBe(true);
});

test('scenario 26: /admin/queues renders the BullMQ dashboard for a SUPER_ADMIN', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'adm-queues');
  promoteToSuperAdmin(email);

  const resp = await page.goto('/admin/queues');
  expect(resp?.status()).toBe(200);

  // Scope to the queue-counts table (its "completed (rolling)" header is unique)
  // so the queue names don't collide with the DLQ-jobs preview, which renders
  // the same names inside <code> elements lower on the page.
  const queueTable = page.locator('table').filter({ hasText: 'completed (rolling)' });
  await expect(queueTable).toBeVisible();

  // The three queues render against the qa stack's own redis/BullMQ.
  await expect(queueTable.getByText('transcribe-md', { exact: true })).toBeVisible();
  await expect(queueTable.getByText('transcribe-md-cleanup', { exact: true })).toBeVisible();
  await expect(queueTable.getByText('dlq-permanent-failures', { exact: true })).toBeVisible();
  // The count columns render (queue state, not just the names).
  await expect(queueTable.getByText('waiting', { exact: true })).toBeVisible();
  await expect(queueTable.getByText('failed', { exact: true })).toBeVisible();
});

test('scenario 26: grant/revoke SUPER_ADMIN takes real EFFECT (privilege management)', async ({
  page,
  browser,
}) => {
  const { email: superEmail } = await signupFreshUser(page, 'adm-grantor');
  promoteToSuperAdmin(superEmail);

  // A separate target doctor (the gate rejects acting on yourself with 403).
  const tctx = await browser.newContext();
  const tpage = await tctx.newPage();
  const { email: targetEmail } = await signupFreshUser(tpage, 'adm-target');
  const target = getAdminUser(targetEmail);
  expect(target.products).not.toContain('SUPER_ADMIN');

  // GRANT — and assert the DB EFFECT, not just the HTTP code.
  const grant = await page.request.post(
    `/api/admin/users/${target.id}/grant-admin`,
    { data: { confirmEmail: targetEmail } },
  );
  expect(grant.status()).toBe(200);
  expect(getAdminUser(targetEmail).products).toContain('SUPER_ADMIN');

  // REVOKE — assert SUPER_ADMIN removed.
  const revoke = await page.request.post(
    `/api/admin/users/${target.id}/revoke-admin`,
    { data: { confirmEmail: targetEmail } },
  );
  expect(revoke.status()).toBe(200);
  expect(getAdminUser(targetEmail).products).not.toContain('SUPER_ADMIN');

  await tctx.close();
});

test('scenario 26: suspend + force-logout take real EFFECT on a target user', async ({
  page,
  browser,
}) => {
  const { email: superEmail } = await signupFreshUser(page, 'adm-enforcer');
  promoteToSuperAdmin(superEmail);

  const tctx = await browser.newContext();
  const tpage = await tctx.newPage();
  const { email: targetEmail } = await signupFreshUser(tpage, 'adm-victim');
  const target = getAdminUser(targetEmail);
  expect(target.suspendedAt).toBeNull();
  expect(target.forceLogoutAt).toBeNull();

  // SUSPEND — assert suspendedAt is now set in the DB.
  const susp = await page.request.post(
    `/api/admin/users/${target.id}/suspend`,
    { data: { reason: 'qa e2e suspend' } },
  );
  expect(susp.status()).toBe(200);
  expect(getAdminUser(targetEmail).suspendedAt).not.toBeNull();

  // FORCE-LOGOUT — assert forceLogoutAt is now set (invalidates the target's sessions).
  const fl = await page.request.post(`/api/admin/users/${target.id}/force-logout`);
  expect(fl.status()).toBe(200);
  expect(getAdminUser(targetEmail).forceLogoutAt).not.toBeNull();

  await tctx.close();
});
