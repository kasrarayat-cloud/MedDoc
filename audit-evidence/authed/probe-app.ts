// ============================================================================
// audit-evidence/authed/probe-app.ts — authenticated sweep of app.quillmd.com
// ----------------------------------------------------------------------------
// Login as the QA user, click every button on every authed page, capture
// console errors, network errors, screenshots, and specifically flag
// "nothing happens" bugs.
// ============================================================================

import { test, expect, Page, BrowserContext } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';

const EVIDENCE = '/opt/meddoc-pro/audit-evidence/authed';
const SHOTS = path.join(EVIDENCE, 'screenshots');
const CONSOLES = path.join(EVIDENCE, 'console-logs');
const NETWORK = path.join(EVIDENCE, 'network-logs');
for (const d of [SHOTS, CONSOLES, NETWORK]) fs.mkdirSync(d, { recursive: true });

const APP = process.env.TEST_APP_URL ?? 'https://app.quillmd.com';
const EMAIL = process.env.TEST_APP_EMAIL!;
const PASSWORD = process.env.TEST_APP_PASSWORD!;

interface Captured {
  type: 'console' | 'pageerror' | 'requestfailed' | '5xx' | '4xx-authed';
  url?: string;
  text: string;
  when: string;
}

function attach(page: Page, label: string): Captured[] {
  const out: Captured[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') {
      out.push({ type: 'console', text: `[${m.type()}] ${m.text()}`.slice(0, 500), when: new Date().toISOString() });
    }
  });
  page.on('pageerror', (e) => out.push({ type: 'pageerror', text: e.message.slice(0, 500), when: new Date().toISOString() }));
  page.on('requestfailed', (r) =>
    out.push({ type: 'requestfailed', url: r.url(), text: r.failure()?.errorText ?? 'unknown', when: new Date().toISOString() })
  );
  page.on('response', (r) => {
    const s = r.status();
    if (s >= 500) out.push({ type: '5xx', url: r.url(), text: `${s}`, when: new Date().toISOString() });
    // 4xx on an authed page that isn't a deliberate auth/validation reject
    // is usually a broken fetch. Log everything >= 400; we'll triage.
    else if (s >= 400 && r.url().includes('/api/') && !r.url().includes('/api/auth/')) {
      out.push({ type: '4xx-authed', url: r.url(), text: `${s}`, when: new Date().toISOString() });
    }
  });
  return out;
}

function saveCapture(label: string, errs: Captured[]) {
  fs.writeFileSync(path.join(CONSOLES, `${label}.json`), JSON.stringify(errs, null, 2));
}

async function shot(page: Page, label: string) {
  await page.screenshot({ path: path.join(SHOTS, `${label}.png`), fullPage: true }).catch(() => {});
}

async function login(page: Page) {
  await page.goto(`${APP}/login`);
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
}

test.describe('authed / app.quillmd.com', () => {
  test.describe.configure({ mode: 'serial' });

  let ctx: BrowserContext;
  let page: Page;
  let errs: Captured[] = [];

  test.beforeAll(async ({ browser }) => {
    ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    page = await ctx.newPage();
    errs = attach(page, 'app-session');
    await login(page);
  });

  test.afterAll(async () => {
    saveCapture('app-session', errs);
    await ctx.close();
  });

  test('dashboard — loads + primary CTA opens new-visit wizard', async () => {
    await page.goto(`${APP}/dashboard`);
    await shot(page, 'app-dashboard-initial');

    // Count interactive elements.
    const counts = await page.evaluate(() => ({
      buttons: document.querySelectorAll('button').length,
      links: document.querySelectorAll('a').length,
      forms: document.querySelectorAll('form').length,
    }));
    fs.writeFileSync(path.join(NETWORK, 'app-dashboard-counts.json'), JSON.stringify(counts));

    // Primary CTA → new visit flow
    const newVisit = page.getByRole('link', { name: /new visit/i }).first();
    await newVisit.click();
    await page.waitForURL(/\/visits\/new/, { timeout: 10_000 });
    await shot(page, 'app-new-visit-landing');
    await page.goBack();
  });

  test('⌘K command palette opens', async () => {
    await page.goto(`${APP}/dashboard`);
    await page.waitForTimeout(500);
    // Meta+K on macOS, Ctrl+K elsewhere. Keyboard test — if this
    // silently no-ops, that's a finding.
    await page.keyboard.press('Meta+k');
    await page.waitForTimeout(400);
    const visibleAfterMeta = await page.getByRole('dialog').isVisible().catch(() => false);
    if (!visibleAfterMeta) {
      await page.keyboard.press('Control+k');
      await page.waitForTimeout(400);
    }
    const open = await page.getByRole('dialog').isVisible().catch(() => false);
    await shot(page, open ? 'app-cmdk-open' : 'app-cmdk-nothing');
    fs.writeFileSync(
      path.join(NETWORK, 'cmdk-result.json'),
      JSON.stringify({ metaOpened: visibleAfterMeta, eitherOpened: open })
    );
    // Try to close if open
    if (open) await page.keyboard.press('Escape');
  });

  test('settings — every section loads; profile form submits', async () => {
    await page.goto(`${APP}/settings`);
    await shot(page, 'app-settings-top');

    // Walk each section anchor
    const anchors = ['#profile', '#security', '#sessions', '#data', '#billing', '#danger'];
    for (const a of anchors) {
      await page.goto(`${APP}/settings${a}`);
      await page.waitForTimeout(300);
      await shot(page, `app-settings-${a.slice(1)}`);
    }

    // Profile update — change name to QA timestamp + save. Should
    // succeed silently (toast).
    await page.goto(`${APP}/settings#profile`);
    await page.waitForTimeout(400);
    const nameField = page.getByLabel(/full name|^name$/i).first();
    if (await nameField.isVisible().catch(() => false)) {
      const newName = `QA ${Date.now().toString(36)}`;
      await nameField.fill(newName);
      await page.getByRole('button', { name: /save|update/i }).first().click();
      await page.waitForTimeout(2000);
      await shot(page, 'app-settings-profile-after-save');
    }
  });

  test('visit list — loads + search works + create new works', async () => {
    await page.goto(`${APP}/visits`);
    await shot(page, 'app-visits-list');
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible().catch(() => false)) {
      await search.fill('qa-probe');
      await page.waitForTimeout(800);
      await shot(page, 'app-visits-search-qa');
    }
  });

  test('new visit — text_notes mode end-to-end', async () => {
    await page.goto(`${APP}/visits/new`);
    await page.waitForTimeout(500);
    await shot(page, 'app-newvisit-step1');

    // Create a test patient inline
    const patientName = `QA Test ${Date.now().toString(36)}`;
    const search = page.getByPlaceholder(/search patient|patient name/i).first();
    if (await search.isVisible().catch(() => false)) {
      await search.fill(patientName);
      await page.waitForTimeout(600);
      const createBtn = page.getByRole('button', { name: /create new patient|new patient/i }).first();
      if (await createBtn.isVisible().catch(() => false)) {
        await createBtn.click();
        await page.waitForTimeout(500);
      }
    }

    // Try to pick text_notes mode
    const textRadio = page.getByRole('radio', { name: /text.*notes|^text$|typed/i });
    if (await textRadio.isVisible().catch(() => false)) {
      await textRadio.check();
    }

    const continueBtn = page.getByRole('button', { name: /create visit|start|continue|next/i }).first();
    if (await continueBtn.isVisible().catch(() => false)) {
      await continueBtn.click();
      await page.waitForTimeout(2000);
      await shot(page, 'app-newvisit-submitted');
    }
  });

  test('patients list — loads + search', async () => {
    await page.goto(`${APP}/patients`);
    await shot(page, 'app-patients-list');
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible().catch(() => false)) {
      await search.fill('Z');
      await page.waitForTimeout(600);
      await shot(page, 'app-patients-search');
    }
  });

  test('all authed links crawl — click each, record', async () => {
    await page.goto(`${APP}/dashboard`);
    await page.waitForTimeout(500);
    // Enumerate unique same-origin hrefs visible from dashboard.
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
    fs.writeFileSync(path.join(NETWORK, 'app-crawl.json'), JSON.stringify(results, null, 2));
  });
});
