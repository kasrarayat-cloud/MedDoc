// ============================================================================
// Scenario 13 — Logout clears the session.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Sign out via the user menu → land on /login → the session
// is gone (a protected route bounces back to /login).
// ============================================================================

import { execSync } from 'node:child_process';

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { logoutViaMenu } from '../helpers/auth';

/** Same door the cleanup helper uses — `docker compose exec postgres psql`,
 *  not the Prisma client, so this reads the SAME database the app wrote to. */
function psqlScalar(sql: string): string {
  const compose = process.env.E2E_COMPOSE ?? 'docker compose -f ../../docker-compose.qa.yml';
  const db = process.env.E2E_DB ?? 'meddoc_qa_test';
  return execSync(
    `${compose} exec -T postgres psql -U meddoc -d ${db} -A -t -c "${sql.replace(/"/g, '\\"')}"`,
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
  ).trim();
}

test.afterEach(() => {
  cleanupTestUsers();
});

test('logout: signing out clears the session + protected routes bounce', async ({
  page,
}) => {
  // signupFreshUser already asserts we land authenticated on /dashboard.
  await signupFreshUser(page, 'logout');

  // ⚠️ CAPTURE THE COOKIE BEFORE SIGNING OUT. "Absent after sign-out" is a
  // fact about THIS BROWSER; it says nothing about whether a COPY of the token
  // still works. #181's whole defect was a session that stayed valid server-side
  // while the local cookie went away, so the local view is exactly the view that
  // could not see it.
  const before = (await page.context().cookies()).filter((c) =>
    /session-token/i.test(c.name),
  );
  expect(before.length, 'no session cookie to re-present — the arm is vacuous').toBeGreaterThan(0);

  await logoutViaMenu(page); // asserts redirect to /login

  // Session cleared locally — the protected route redirects back to /login.
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);

  // ══ #181 — THE COOKIE IS REJECTED, NOT MERELY ABSENT ════════════════════
  // Put the captured token back and ask a protected route again. If the
  // UserSession row survived sign-out, this lands on /dashboard and the doctor
  // was never signed out at all.
  await page.context().addCookies(before);
  const restored = (await page.context().cookies()).filter((c) =>
    /session-token/i.test(c.name),
  );
  expect(restored.length, 'the re-presented cookie did not stick').toBeGreaterThan(0);

  await page.goto('/dashboard');
  await expect(
    page,
    'THE SIGNED-OUT SESSION STILL WORKS — the server honoured a revoked token',
  ).toHaveURL(/\/login/);
});

test('#181: the LOGOUT audit row is written — the revoke path was actually reached', async ({
  page,
}) => {
  // ⚠️ THE AUDIT ROW IS THE PROOF THAT `events.signOut` RAN AT ALL. It lives in
  // the same handler as the UserSession revoke, downstream of @auth/core's CSRF
  // gate — so before #181 a failed CSRF skipped BOTH, and the incident left no
  // artefact anywhere. A sign-out with no audit row is indistinguishable from a
  // sign-out that never happened, which is precisely how this hid.
  const email = await signupFreshUser(page, 'logout-audit');

  const before = Number(
    psqlScalar("select count(*) from audit_logs where action::text like '%LOGOUT%'"),
  );
  await logoutViaMenu(page);

  await expect
    .poll(
      () =>
        Number(psqlScalar("select count(*) from audit_logs where action::text like '%LOGOUT%'")),
      { timeout: 15_000 },
    )
    .toBeGreaterThan(before);

  expect(typeof email).toBe('string');
});

test('#181: a CSRF blip no longer reaches the sign-out path at all', async ({ page }) => {
  // ⚠️ THIS ARM IS THE CLASS BEING CLOSED, AND ITS SHAPE IS DELIBERATE.
  //
  // The trigger was `getCsrfToken()` in `next-auth/react`, which ends
  // `return response?.csrfToken ?? ""` — one transient blip on the preceding GET
  // silently produced an unverifiable POST, @auth/core's CSRF gate threw, and
  // `events.signOut` (the revoke AND the audit row) never ran while the response
  // was still 200.
  //
  // So this test breaks the CSRF endpoint outright and asserts sign-out STILL
  // WORKS — because the client no longer takes that path. Asserting a "loud
  // failure" here would be asserting a dependency that has been REMOVED; the
  // honest arm is that the blip is now inert.
  await signupFreshUser(page, 'logout-csrf');

  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{}' }),
  );

  await logoutViaMenu(page);

  await page.goto('/dashboard');
  await expect(
    page,
    'a CSRF blip still breaks sign-out — the client is back on the gated path',
  ).toHaveURL(/\/login/);
});
