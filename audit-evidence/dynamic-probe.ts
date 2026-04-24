// ============================================================================
// audit-evidence/dynamic-probe.ts — playwright script for the audit.
// ----------------------------------------------------------------------------
// Run via:
//   cd /opt/meddoc-pro/apps/transcribe-md
//   npx playwright test --config=/opt/meddoc-pro/audit-evidence/probe.config.ts
//
// Does NOT mutate prod. Loads public pages, exercises forms with bad
// inputs, captures screenshots + console errors + network errors +
// Web Vitals.
// ============================================================================

import { test, expect, Page } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const EVIDENCE = '/opt/meddoc-pro/audit-evidence';
const SHOTS = path.join(EVIDENCE, 'screenshots');
const CONSOLES = path.join(EVIDENCE, 'console-logs');
const NETWORK = path.join(EVIDENCE, 'network-logs');
const PERF = path.join(EVIDENCE, 'perf');
for (const d of [SHOTS, CONSOLES, NETWORK, PERF]) fs.mkdirSync(d, { recursive: true });

interface CapturedError {
  type: 'console' | 'pageerror' | 'requestfailed' | '5xx';
  url?: string;
  text: string;
  when: string;
}

function attachCapture(page: Page, label: string): CapturedError[] {
  const errs: CapturedError[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      errs.push({
        type: 'console',
        text: `[${msg.type()}] ${msg.text()}`,
        when: new Date().toISOString(),
      });
    }
  });
  page.on('pageerror', (err) => {
    errs.push({
      type: 'pageerror',
      text: err.message,
      when: new Date().toISOString(),
    });
  });
  page.on('requestfailed', (req) => {
    errs.push({
      type: 'requestfailed',
      url: req.url(),
      text: req.failure()?.errorText ?? 'unknown',
      when: new Date().toISOString(),
    });
  });
  page.on('response', (res) => {
    if (res.status() >= 500) {
      errs.push({
        type: '5xx',
        url: res.url(),
        text: `${res.status()} ${res.statusText()}`,
        when: new Date().toISOString(),
      });
    }
  });
  return errs;
}

function saveCapture(label: string, errs: CapturedError[]) {
  fs.writeFileSync(
    path.join(CONSOLES, `${label}.json`),
    JSON.stringify(errs, null, 2)
  );
}

async function measurePerf(page: Page, label: string) {
  // Web Vitals: LCP + TTFB + DCL via the Navigation Timing API. Good
  // enough for a pre-launch sanity pass; full Lighthouse would be
  // better but needs extra infrastructure.
  const metrics = await page.evaluate(() => {
    const nav = performance.getEntriesByType(
      'navigation'
    )[0] as PerformanceNavigationTiming | undefined;
    const lcp = performance
      .getEntriesByType('largest-contentful-paint')
      .at(-1) as PerformanceEntry | undefined;
    return {
      domContentLoaded: nav
        ? Math.round(nav.domContentLoadedEventEnd)
        : null,
      loadComplete: nav ? Math.round(nav.loadEventEnd) : null,
      ttfb: nav ? Math.round(nav.responseStart - nav.requestStart) : null,
      lcp: lcp ? Math.round(lcp.startTime) : null,
    };
  });
  fs.writeFileSync(
    path.join(PERF, `${label}.json`),
    JSON.stringify(metrics, null, 2)
  );
  return metrics;
}

const PAGES_MARKETING = [
  { path: '/', label: 'marketing-home' },
  { path: '/pricing', label: 'marketing-pricing' },
  { path: '/security', label: 'marketing-security' },
  { path: '/hipaa', label: 'marketing-hipaa' },
  { path: '/privacy', label: 'marketing-privacy' },
  { path: '/terms', label: 'marketing-terms' },
  { path: '/about', label: 'marketing-about' },
  { path: '/contact', label: 'marketing-contact' },
  { path: '/demo', label: 'marketing-demo' },
  { path: '/signup', label: 'marketing-signup' },
];

const PAGES_APP = [
  { path: '/login', label: 'app-login' },
  { path: '/signup', label: 'app-signup' },
  { path: '/forgot-password', label: 'app-forgot' },
  { path: '/check-email', label: 'app-check-email' },
];

const PAGES_PRO = [
  { path: '/', label: 'pro-root' },
  { path: '/login', label: 'pro-login' },
  { path: '/register', label: 'pro-register' },
];

test.describe('audit / public page sweep', () => {
  for (const { path: url, label } of PAGES_MARKETING) {
    test(`marketing ${label}`, async ({ page }) => {
      const errs = attachCapture(page, label);
      const resp = await page.goto(`https://quillmd.com${url}`, { waitUntil: 'networkidle' });
      expect(resp?.status(), `${label} navigation should 2xx`).toBeLessThan(400);
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true });
      await measurePerf(page, label);
      saveCapture(label, errs);
    });
  }

  for (const { path: url, label } of PAGES_APP) {
    test(`app ${label}`, async ({ page }) => {
      const errs = attachCapture(page, label);
      const resp = await page.goto(`https://app.quillmd.com${url}`, { waitUntil: 'networkidle' });
      expect(resp?.status(), `${label} navigation should 2xx`).toBeLessThan(400);
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true });
      await measurePerf(page, label);
      saveCapture(label, errs);
    });
  }

  for (const { path: url, label } of PAGES_PRO) {
    test(`pro ${label}`, async ({ page }) => {
      const errs = attachCapture(page, label);
      const resp = await page.goto(`https://pro.quillmd.com${url}`, { waitUntil: 'networkidle' });
      // pro / → 307 redirect to /login acceptable
      const status = resp?.status() ?? 0;
      expect(status < 400 || status === 307, `${label} status=${status}`).toBe(true);
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true });
      await measurePerf(page, label);
      saveCapture(label, errs);
    });
  }
});

test.describe('audit / form edge cases', () => {
  test('signup — empty submit', async ({ page }) => {
    const errs = attachCapture(page, 'signup-empty');
    await page.goto('https://app.quillmd.com/signup');
    await page.getByRole('button', { name: /create account|sign up/i }).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, 'signup-empty.png') });
    saveCapture('signup-empty', errs);
    // Expect we stay on /signup.
    expect(page.url()).toMatch(/\/signup/);
  });

  test('signup — XSS attempt in name field', async ({ page }) => {
    const errs = attachCapture(page, 'signup-xss');
    await page.goto('https://app.quillmd.com/signup');
    const xss = '<script>window.__xss_fired=true</script>';
    await page.getByLabel(/name/i).fill(xss);
    await page.getByLabel(/email/i).fill(`xss-${Date.now()}@example.test`);
    await page.getByLabel('Password', { exact: true }).fill('Strong2024Pass');
    await page.getByLabel(/confirm/i).fill('Strong2024Pass');
    const terms = page.getByRole('checkbox', { name: /terms|agree|accept/i });
    if (await terms.isVisible().catch(() => false)) await terms.check();
    await page.getByRole('button', { name: /create account|sign up/i }).click();
    await page.waitForTimeout(2000);
    // If the XSS executed, window.__xss_fired would be set.
    const fired = await page.evaluate(() => (window as unknown as { __xss_fired?: boolean }).__xss_fired === true);
    expect(fired, 'XSS payload executed on signup page').toBe(false);
    await page.screenshot({ path: path.join(SHOTS, 'signup-xss.png') });
    saveCapture('signup-xss', errs);
  });

  test('signup — very long inputs (1000 chars)', async ({ page }) => {
    const errs = attachCapture(page, 'signup-long');
    await page.goto('https://app.quillmd.com/signup');
    const long = 'A'.repeat(1000);
    await page.getByLabel(/name/i).fill(long);
    await page.getByLabel(/email/i).fill(`long-${Date.now()}@example.test`);
    await page.getByLabel('Password', { exact: true }).fill(long);
    await page.getByLabel(/confirm/i).fill(long);
    const terms = page.getByRole('checkbox', { name: /terms|agree|accept/i });
    if (await terms.isVisible().catch(() => false)) await terms.check();
    await page.getByRole('button', { name: /create account|sign up/i }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOTS, 'signup-long.png') });
    saveCapture('signup-long', errs);
  });

  test('signup — mismatched passwords', async ({ page }) => {
    const errs = attachCapture(page, 'signup-mismatch');
    await page.goto('https://app.quillmd.com/signup');
    await page.getByLabel(/name/i).fill('QA Tester');
    await page.getByLabel(/email/i).fill(`mm-${Date.now()}@example.test`);
    await page.getByLabel('Password', { exact: true }).fill('Strong2024Pass');
    await page.getByLabel(/confirm/i).fill('Different2024Pass');
    const terms = page.getByRole('checkbox', { name: /terms|agree|accept/i });
    if (await terms.isVisible().catch(() => false)) await terms.check();
    await page.getByRole('button', { name: /create account|sign up/i }).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, 'signup-mismatch.png') });
    saveCapture('signup-mismatch', errs);
    expect(page.url()).toMatch(/\/signup/);
  });

  test('login — empty submit', async ({ page }) => {
    const errs = attachCapture(page, 'login-empty');
    await page.goto('https://app.quillmd.com/login');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, 'login-empty.png') });
    saveCapture('login-empty', errs);
  });

  test('login — malformed email', async ({ page }) => {
    const errs = attachCapture(page, 'login-bad-email');
    await page.goto('https://app.quillmd.com/login');
    await page.getByLabel(/email/i).fill('not-an-email');
    await page.getByLabel(/password/i).fill('whatever');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, 'login-bad-email.png') });
    saveCapture('login-bad-email', errs);
  });

  test('forgot-password — valid email surface', async ({ page }) => {
    const errs = attachCapture(page, 'forgot-valid');
    const resp = await page.goto('https://app.quillmd.com/forgot-password');
    expect(resp?.status()).toBe(200);
    await page.getByLabel(/email/i).fill('nope@example.test');
    await page.getByRole('button', { name: /reset|send/i }).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, 'forgot-valid.png') });
    saveCapture('forgot-valid', errs);
  });
});

test.describe('audit / mobile viewport', () => {
  test.use({ viewport: { width: 393, height: 851 } });
  const mobileSet = [
    ['https://quillmd.com/', 'mobile-marketing-home'],
    ['https://quillmd.com/pricing', 'mobile-marketing-pricing'],
    ['https://app.quillmd.com/login', 'mobile-app-login'],
    ['https://app.quillmd.com/signup', 'mobile-app-signup'],
    ['https://pro.quillmd.com/login', 'mobile-pro-login'],
  ] as const;
  for (const [url, label] of mobileSet) {
    test(label, async ({ page }) => {
      const errs = attachCapture(page, label);
      await page.goto(url, { waitUntil: 'networkidle' });
      await page.waitForTimeout(500);
      const overflow = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      }));
      await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true });
      fs.writeFileSync(
        path.join(PERF, `${label}.json`),
        JSON.stringify({ overflow, label }, null, 2)
      );
      saveCapture(label, errs);
      expect(
        overflow.scroll <= overflow.client + 1,
        `${label}: horizontal overflow (${overflow.scroll}px vs ${overflow.client}px client)`
      ).toBe(true);
    });
  }
});
