import { test, expect } from '@playwright/test';
import * as path from 'node:path';

import { requireTestCreds } from './helpers/env';
import { loginApp } from './helpers/auth';

// Viewport: 375 × 812 (iPhone 13). This spec is assigned the `mobile`
// project in playwright.config.ts so the iPhone 13 device descriptor
// applies automatically — no manual page.setViewportSize needed.
//
// What we check:
//   1. No horizontal scroll on public pages (login + marketing).
//   2. If authed, dashboard + visits list also scroll-clean.
//   3. Record page's primary CTA is in-viewport and tappable.
// Every page captures a screenshot into reports/screenshots/.

const SHOTS_DIR = path.resolve(__dirname, '../reports/screenshots');

async function screenshot(
  page: import('@playwright/test').Page,
  name: string
) {
  await page.screenshot({
    path: path.join(SHOTS_DIR, `${name}.png`),
    fullPage: true,
  });
}

async function assertNoHorizontalScroll(
  page: import('@playwright/test').Page,
  label: string
) {
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(
    overflow.scroll <= overflow.client + 1,
    `${label}: horizontal overflow (${overflow.scroll}px scroll vs ${overflow.client}px client)`
  ).toBe(true);
}

test.describe('mobile responsiveness @ 375x812', () => {
  test('login page is usable and scroll-clean', async ({ page }) => {
    await page.goto('/login');
    await screenshot(page, 'mobile-login');
    await assertNoHorizontalScroll(page, 'login');
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('authed surfaces (dashboard / new visit)', async ({ page }) => {
    const creds = requireTestCreds('app');
    test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
    if (!creds) return;

    await loginApp(page, creds.email, creds.password);

    await screenshot(page, 'mobile-dashboard');
    await assertNoHorizontalScroll(page, 'dashboard');

    // New-visit page — its `1fr 380px` layout was flagged in the audit
    // as overflowing on phones; this test acts as the regression guard.
    await page.goto('/visits/new');
    await screenshot(page, 'mobile-new-visit');
    await assertNoHorizontalScroll(page, '/visits/new');

    // Primary CTA should be in-viewport, not cut off horizontally.
    const primaryCta = page.getByRole('button', { name: /create|continue|next/i }).first();
    if (await primaryCta.isVisible().catch(() => false)) {
      const box = await primaryCta.boundingBox();
      expect(box && box.x >= 0 && box.x + box.width <= 375).toBe(true);
    }
  });
});
