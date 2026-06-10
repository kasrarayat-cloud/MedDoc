// ============================================================================
// Scenario 28 — marketing site smoke (apps/marketing, quillmd.com)
// ----------------------------------------------------------------------------
// Light smoke that completes "whole website" coverage: the key marketing pages
// render (200, no 5xx) and the primary CTA leads to the signup funnel. The
// actual signup happens on the APP (app.quillmd.com/signup — covered by the
// app scenarios); the marketing CTAs are cross-app links to APP_SIGNUP_URL, so
// this asserts the funnel HANDOFF, not a second signup implementation.
//
// Runs ONLY via `--project=marketing` (its own baseURL = the marketing app,
// default http://localhost:9010), gated on MARKETING_E2E=1. NOT in the default
// chromium project and — deliberately — NOT wired into the required e2e CI gate:
// the marketing app is a separate build, and adding a 2nd full app build to the
// critical gate for a static-page smoke isn't worth the bloat. Validated
// locally against a marketing container on the qa network; a small follow-up
// can add it to CI if ongoing protection is wanted.
// ============================================================================

import { expect, test } from '@playwright/test';

const GATE = process.env.MARKETING_E2E !== '1';

// Key pages — the funnel + the trust/compliance pages doctors actually read.
// Not exhaustive static-page coverage (per the brief).
const KEY_PAGES = ['/', '/pricing', '/security', '/hipaa', '/privacy', '/terms', '/demo'];

test.describe('scenario 28: marketing site smoke', () => {
  test.skip(
    GATE,
    'Needs the marketing app — run `--project=marketing` with MARKETING_E2E=1 against a marketing container.',
  );

  for (const path of KEY_PAGES) {
    test(`marketing ${path} renders (200, no 5xx, real content)`, async ({ page }) => {
      const resp = await page.goto(path);
      expect(resp?.status(), `${path} should be 200`).toBe(200);
      // Real rendered content — not a 500/error shell or blank document.
      await expect(page.locator('h1, .hero-title, nav, header').first()).toBeVisible();
    });
  }

  test('the primary "Get started" CTA leads to the signup funnel', async ({ page }) => {
    await page.goto('/');
    const cta = page.getByRole('link', { name: /get started/i }).first();
    await expect(cta).toBeVisible();
    const href = await cta.getAttribute('href');
    // APP_SIGNUP_URL = `${NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL}/signup` (baked at build).
    expect(href, 'Get started CTA must point at the signup funnel').toMatch(/\/signup$/);
  });

  test('/signup forwards to the app signup (the cross-app funnel handoff)', async ({ page }) => {
    const resp = await page.goto('/signup');
    expect(resp?.status()).toBe(200);
    const cont = page.getByRole('link', { name: /continue to signup/i });
    await expect(cont).toBeVisible();
    const href = await cont.getAttribute('href');
    expect(href).toMatch(/\/signup$/);
  });
});
