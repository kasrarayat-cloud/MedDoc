import { test, expect } from '@playwright/test';

// ============================================================================
// Auth — login flow lands a SUPER_ADMIN on /system-admin
// ----------------------------------------------------------------------------
// Prereq: `npx tsx scripts/seed-e2e-admin.ts` has been run against the DB
// pointed at by DATABASE_URL (creates admin@test.dev / admin-password /
// SUPER_ADMIN / clinic_main). The dev server must be running at :3000.
// ============================================================================

test('admin can sign in and lands on /system-admin', async ({ page }) => {
  await page.goto('/login');

  await page.getByLabel('Email address').fill('admin@test.dev');
  await page.getByLabel('Password').fill('admin-password');

  await page.getByRole('button', { name: /sign in/i }).click();

  // NextAuth credentials + middleware redirect can take a beat — wait for URL.
  await page.waitForURL('**/system-admin');
  await expect(page).toHaveURL(/\/system-admin$/);

  await expect(
    page.getByRole('heading', { name: /system admin/i })
  ).toBeVisible();
});
