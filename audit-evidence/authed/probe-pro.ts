// ============================================================================
// audit-evidence/authed/probe-pro.ts — authenticated sweep of pro.quillmd.com
// ============================================================================

import { test, Page, BrowserContext } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const EVIDENCE = '/opt/meddoc-pro/audit-evidence/authed';
const SHOTS = path.join(EVIDENCE, 'screenshots');
const NETWORK = path.join(EVIDENCE, 'network-logs');
const CONSOLES = path.join(EVIDENCE, 'console-logs');
for (const d of [SHOTS, NETWORK, CONSOLES]) fs.mkdirSync(d, { recursive: true });

const PRO = process.env.TEST_PRO_URL ?? 'https://pro.quillmd.com';
const EMAIL = process.env.TEST_PRO_EMAIL!;
const PASSWORD = process.env.TEST_PRO_PASSWORD!;

interface Captured {
  type: 'console' | 'pageerror' | 'requestfailed' | '5xx' | '4xx-authed';
  url?: string;
  text: string;
  when: string;
}

function attach(page: Page, label: string): Captured[] {
  const out: Captured[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error')
      out.push({ type: 'console', text: `[${m.type()}] ${m.text()}`.slice(0, 500), when: new Date().toISOString() });
  });
  page.on('pageerror', (e) => out.push({ type: 'pageerror', text: e.message.slice(0, 500), when: new Date().toISOString() }));
  page.on('requestfailed', (r) =>
    out.push({ type: 'requestfailed', url: r.url(), text: r.failure()?.errorText ?? 'unknown', when: new Date().toISOString() })
  );
  page.on('response', (r) => {
    const s = r.status();
    if (s >= 500) out.push({ type: '5xx', url: r.url(), text: `${s}`, when: new Date().toISOString() });
    else if (s >= 400 && r.url().includes('/api/') && !r.url().includes('/api/auth/'))
      out.push({ type: '4xx-authed', url: r.url(), text: `${s}`, when: new Date().toISOString() });
  });
  return out;
}

async function shot(page: Page, label: string) {
  await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true }).catch(() => {});
}

async function login(page: Page) {
  await page.goto(`${PRO}/login`);
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign in|log in/i }).click();
  // Pro may land on /dashboard or /dashboard/patients or a different home
  await page.waitForURL((u) => u.pathname.startsWith('/dashboard') || u.pathname.startsWith('/system-admin'), {
    timeout: 15_000,
  }).catch(() => {});
}

test.describe('authed / pro.quillmd.com', () => {
  test.describe.configure({ mode: 'serial' });
  let ctx: BrowserContext;
  let page: Page;
  let errs: Captured[] = [];

  test.beforeAll(async ({ browser }) => {
    ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    page = await ctx.newPage();
    errs = attach(page, 'pro-session');
    await login(page);
    await shot(page, 'pro-landing-after-login');
  });

  test.afterAll(async () => {
    fs.writeFileSync(path.join(CONSOLES, 'pro-session.json'), JSON.stringify(errs, null, 2));
    await ctx.close();
  });

  test('dashboard + patient list', async () => {
    await page.goto(`${PRO}/dashboard`);
    await shot(page, 'pro-dashboard');

    await page.goto(`${PRO}/dashboard/patients`);
    await page.waitForTimeout(500);
    await shot(page, 'pro-patients-list');

    // Search
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible().catch(() => false)) {
      await search.fill('Z');
      await page.waitForTimeout(600);
      await shot(page, 'pro-patients-search');
    }
  });

  test('landing buttons — find dead handlers (Watch Demo, More Filters)', async () => {
    // Hero "Watch Demo" button was flagged in first audit (Hero.tsx:141)
    // — verify it's still dead by clicking and measuring effects.
    await page.goto(`${PRO}/dashboard`);
    await page.waitForTimeout(400);
    const watchDemo = page.getByRole('button', { name: /watch demo/i }).first();
    const wdVisible = await watchDemo.isVisible().catch(() => false);
    let watchDemoEffect = 'not-present';
    if (wdVisible) {
      const beforeUrl = page.url();
      const beforeModals = await page.$$('[role="dialog"]').then((ds) => ds.length);
      await watchDemo.click({ trial: false }).catch(() => {});
      await page.waitForTimeout(1500);
      const afterUrl = page.url();
      const afterModals = await page.$$('[role="dialog"]').then((ds) => ds.length);
      watchDemoEffect = `before: ${beforeUrl} ${beforeModals} modals; after: ${afterUrl} ${afterModals} modals`;
      await shot(page, 'pro-watch-demo-after-click');
    }
    fs.writeFileSync(
      path.join(NETWORK, 'pro-watch-demo.json'),
      JSON.stringify({ visible: wdVisible, effect: watchDemoEffect })
    );

    // More Filters
    await page.goto(`${PRO}/dashboard/patients`);
    await page.waitForTimeout(500);
    const mf = page.getByRole('button', { name: /more filters/i }).first();
    const mfVisible = await mf.isVisible().catch(() => false);
    let mfEffect = 'not-present';
    if (mfVisible) {
      const beforeDrawers = await page.$$('[role="dialog"], [data-drawer], [aria-expanded="true"]').then((ds) => ds.length);
      await mf.click({ trial: false }).catch(() => {});
      await page.waitForTimeout(1000);
      const afterDrawers = await page.$$('[role="dialog"], [data-drawer], [aria-expanded="true"]').then((ds) => ds.length);
      mfEffect = `before: ${beforeDrawers} drawers; after: ${afterDrawers} drawers`;
      await shot(page, 'pro-more-filters-after-click');
    }
    fs.writeFileSync(
      path.join(NETWORK, 'pro-more-filters.json'),
      JSON.stringify({ visible: mfVisible, effect: mfEffect })
    );
  });

  test('settings — profile form + password form', async () => {
    await page.goto(`${PRO}/dashboard/settings`);
    await page.waitForTimeout(600);
    await shot(page, 'pro-settings');

    // Profile update
    const nameField = page.getByLabel(/^name$|full name/i).first();
    if (await nameField.isVisible().catch(() => false)) {
      const newName = `QA Pro ${Date.now().toString(36)}`;
      await nameField.fill(newName);
      await page.getByRole('button', { name: /save|update/i }).first().click();
      await page.waitForTimeout(1500);
      await shot(page, 'pro-settings-profile-save');
    }
  });

  test('crawl dashboard links', async () => {
    await page.goto(`${PRO}/dashboard`);
    await page.waitForTimeout(500);
    const hrefs = await page.evaluate(() => {
      const anchors = Array.from(document.querySelectorAll('a[href]'));
      return Array.from(
        new Set(
          anchors
            .map((a) => (a as HTMLAnchorElement).href)
            .filter((h) => h.startsWith(location.origin))
        )
      );
    });
    const results: Array<{ url: string; status: number | null; error?: string }> = [];
    for (const url of hrefs.slice(0, 30)) {
      try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 10_000 });
        results.push({ url, status: resp?.status() ?? null });
      } catch (err) {
        results.push({ url, status: null, error: (err as Error).message.slice(0, 120) });
      }
    }
    fs.writeFileSync(path.join(NETWORK, 'pro-crawl.json'), JSON.stringify(results, null, 2));
  });
});
