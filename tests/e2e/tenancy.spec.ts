import { test, expect, type Page } from '@playwright/test';

import { USERS, PATIENTS, TEST_PASSWORD } from '../fixtures/tenancy';

// ============================================================================
// Multi-tenancy — UI happy-path coverage
// ----------------------------------------------------------------------------
// Three scenarios that prove tenant isolation is actually visible to users:
//   1. Cross-tenant list — DOCTOR-A sees their own patient, never Practice-B's
//   2. Direct URL probe  — DOCTOR-A navigating to a Practice-B patient detail
//                          gets the "Patient Not Found" 404 surface
//   3. SUPER_ADMIN sees-all — both practices' users appear on /system-admin
//
// Adversarial cases (forged IDs, cross-tenant server-action writes) live in
// the Vitest suite — they're faster and more precise there.
//
// Prereq: `npm run seed:e2e` + dev server at :3000.
// ============================================================================

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  // Role-based redirect is a full page load (window.location.assign) —
  // wait for the post-login URL before proceeding.
  await page.waitForURL((url) => {
    const path = new URL(url).pathname;
    return path === '/dashboard' || path === '/system-admin';
  });
}

test.describe('tenant isolation — UI', () => {
  test('cross-tenant list: DOCTOR-A sees own patient, never Practice-B', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto('/dashboard/patients');

    // Wait for the patient table to render at least one row.
    await expect(
      page.getByText(`${PATIENTS.a1.firstName} ${PATIENTS.a1.lastName}`)
    ).toBeVisible();

    // Practice-B patients MUST NOT appear anywhere on the page.
    await expect(
      page.getByText(`${PATIENTS.b1.firstName} ${PATIENTS.b1.lastName}`)
    ).toHaveCount(0);
    await expect(
      page.getByText(`${PATIENTS.b2.firstName} ${PATIENTS.b2.lastName}`)
    ).toHaveCount(0);
  });

  test('direct URL probe: DOCTOR-A hitting a Practice-B patient id gets 404', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);

    // Forge the URL for a patient in the other practice.
    await page.goto(`/dashboard/patients/${PATIENTS.b1.id}`);

    // Server component renders the PatientNotFound view — "doesn't exist"
    // and "you can't see it" deliberately collapse to the same surface so
    // URL-probing cannot enumerate charts across practices.
    await expect(
      page.getByRole('heading', { name: /patient not found/i })
    ).toBeVisible();

    // And the forged id should NOT render as if it were loaded — check that
    // Bianca's name doesn't appear anywhere on the page.
    await expect(
      page.getByText(`${PATIENTS.b1.firstName} ${PATIENTS.b1.lastName}`)
    ).toHaveCount(0);
  });

  test('SUPER_ADMIN sees-all: /system-admin lists users from both practices', async ({ page }) => {
    await signIn(page, USERS.super.email, TEST_PASSWORD);
    await expect(page).toHaveURL(/\/system-admin$/);

    // Users from both Practice A and Practice B should be rendered in the
    // same admin users table, since `tenantScope(session)` returns {} for
    // SUPER_ADMIN.
    await expect(page.getByText(USERS.adminA.email)).toBeVisible();
    await expect(page.getByText(USERS.adminB.email)).toBeVisible();
    await expect(page.getByText(USERS.doctorA.email)).toBeVisible();
    await expect(page.getByText(USERS.doctorB.email)).toBeVisible();
  });
});
