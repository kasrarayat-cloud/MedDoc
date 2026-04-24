import { test, expect, APIRequestContext } from '@playwright/test';

import { requireTestCreds, E2E_READ_ONLY } from './helpers/env';
import { loginApp } from './helpers/auth';

// Regression guard for the PHI-exfil critical. The bug was:
// POST /api/visits/[id]/export/email with body.to = <any address>
// went straight to Resend — a compromised session could mail every
// signed SOAP to an attacker-controlled inbox.
//
// Fix: destination must equal session.user.email.
//
// This test needs a SIGNED visit the QA user owns. Given seed-data
// availability we'd rather look one up than create one from scratch
// each run — falling back to "skip if none" so the test doesn't flake
// if the QA account's signed-visit inventory is empty.
//
// Running this against prod is safe: mismatched destinations 403
// without sending, and the matching case only emails the account
// owner (qa-audit@quillmd.local).

test.describe('PHI guard — email export destination', () => {
  test.skip(
    E2E_READ_ONLY,
    'emits a real PDF email on success; set E2E_READ_ONLY=false to run'
  );

  async function findReadyOrSignedVisit(
    request: APIRequestContext
  ): Promise<string | null> {
    // /api/patients returns patients with visitCount; we pick a
    // patient with visits, pull a visit from its detail page in the
    // UI, and scrape the id. Simpler: just query status 200 visits
    // via the dashboard HTML — if you find one, return its cuid.
    const dashboardHtml = await (
      await request.get('/dashboard', { failOnStatusCode: false })
    ).text();
    const m = dashboardHtml.match(/\/visits\/(c[a-z0-9]{20,})/);
    return m?.[1] ?? null;
  }

  test('attacker domain → 403 INVALID_DESTINATION', async ({ page, request }) => {
    const creds = requireTestCreds('app');
    test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
    if (!creds) return;

    await loginApp(page, creds.email, creds.password);
    const visitId = await findReadyOrSignedVisit(page.request);
    test.skip(!visitId, 'no READY/SIGNED visit available in QA dashboard');
    if (!visitId) return;

    const res = await page.request.post(
      `/api/visits/${visitId}/export/email`,
      { data: { to: 'attacker-exfil@example.test' } }
    );
    expect(res.status(), 'should 403 a mismatched destination').toBe(403);
    const body = await res.json();
    expect(body.code).toBe('INVALID_DESTINATION');
  });

  test('own account email → 200 ok', async ({ page }) => {
    const creds = requireTestCreds('app');
    test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
    if (!creds) return;

    await loginApp(page, creds.email, creds.password);
    const visitId = await findReadyOrSignedVisit(page.request);
    test.skip(!visitId, 'no READY/SIGNED visit available');
    if (!visitId) return;

    const res = await page.request.post(
      `/api/visits/${visitId}/export/email`,
      { data: { to: creds.email } }
    );
    expect(res.status(), 'session email should be accepted').toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(typeof body.messageId).toBe('string');
  });

  test('case-insensitive self-email is accepted', async ({ page }) => {
    const creds = requireTestCreds('app');
    test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
    if (!creds) return;

    await loginApp(page, creds.email, creds.password);
    const visitId = await findReadyOrSignedVisit(page.request);
    test.skip(!visitId, 'no READY/SIGNED visit available');
    if (!visitId) return;

    const upper = creds.email.toUpperCase();
    const res = await page.request.post(
      `/api/visits/${visitId}/export/email`,
      { data: { to: upper } }
    );
    expect(
      res.status(),
      'uppercase same email should pass the case-insensitive match'
    ).toBe(200);
  });

  test('sign endpoint with mismatched emailTo → 403', async ({ page }) => {
    const creds = requireTestCreds('app');
    test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
    if (!creds) return;

    await loginApp(page, creds.email, creds.password);
    const visitId = await findReadyOrSignedVisit(page.request);
    test.skip(!visitId, 'no READY/SIGNED visit available');
    if (!visitId) return;

    const res = await page.request.post(
      `/api/visits/${visitId}/sign`,
      {
        data: {
          destinations: ['email'],
          emailTo: 'attacker-exfil@example.test',
        },
      }
    );
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.code).toBe('INVALID_DESTINATION');
  });
});
