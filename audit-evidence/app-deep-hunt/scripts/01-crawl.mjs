// ============================================================================
// Deep-hunt phase 1: broad crawl. Login as QA, visit every authed page,
// capture console + network + page errors, take a screenshot of each.
// Writes findings into ../logs/01-crawl-findings.json.
// ============================================================================

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const findings = [];
const errors = [];

function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 200)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  baseURL: 'https://app.quillmd.com',
  viewport: { width: 1280, height: 900 },
});
const page = await ctx.newPage();

page.on('pageerror', (e) => {
  errors.push({ type: 'pageerror', url: page.url(), text: e.message });
  add('HIGH', page.url(), 'page error', e.message.slice(0, 300));
});
page.on('response', (r) => {
  const u = r.url();
  if (r.status() >= 500) {
    errors.push({ type: '5xx', url: u, status: r.status() });
    add('HIGH', page.url(), '5xx response', `${r.status()} on ${u}`);
  } else if (r.status() >= 400 && /\/api\//.test(u) && !/\/api\/auth\/(callback|session|providers|csrf)/.test(u)) {
    errors.push({ type: `${r.status()}`, url: u, method: r.request().method() });
  }
});
page.on('console', (m) => {
  if (m.type() === 'error') {
    const txt = m.text();
    // Suppress NextAuth's normal cache misses + benign warnings.
    if (/\[next-auth\]/i.test(txt)) return;
    errors.push({ type: 'console', url: page.url(), text: txt });
    add('LOW', page.url(), 'console error', txt.slice(0, 250));
  }
});

// Login
console.log('=== Login ===');
await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });
await page.screenshot({ path: `${EV}/screenshots/01-dashboard-loaded.png`, fullPage: true });

// Pages to crawl
const pages = [
  { name: 'dashboard', url: '/dashboard' },
  { name: 'visits-list', url: '/visits' },
  { name: 'patients-list', url: '/patients' },
  { name: 'new-visit', url: '/visits/new' },
  { name: 'settings', url: '/settings' },
];

for (const p of pages) {
  console.log(`\n=== ${p.name} (${p.url}) ===`);
  const startErrors = errors.length;
  await page.goto(p.url, { waitUntil: 'networkidle', timeout: 20000 }).catch((e) => {
    add('HIGH', p.url, 'goto failed', e.message.slice(0, 200));
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${EV}/screenshots/01-${p.name}.png`, fullPage: true }).catch(() => {});
  const newErrs = errors.length - startErrors;
  console.log(`  errors during load: ${newErrs}`);

  // Tab/button enumeration
  const buttons = await page.locator('button:visible').all();
  const links = await page.locator('a:visible').all();
  console.log(`  visible buttons: ${buttons.length}, links: ${links.length}`);
  add('INFO', p.url, 'element count', `buttons=${buttons.length}, links=${links.length}`);
}

// Probe a few invalid URLs
console.log('\n=== Invalid URL probes ===');
const probes = [
  { name: 'visit-nonexistent', url: '/visits/nonexistent-id' },
  { name: 'patient-nonexistent', url: '/patients/nonexistent-id' },
  { name: 'dashboard-nonexistent', url: '/dashboard/no-such-section' },
  { name: 'visit-cuid-collision', url: '/visits/' + 'c' + 'a'.repeat(24) },
  { name: 'visit-sql-injection', url: "/visits/' OR 1=1 --" },
];
for (const p of probes) {
  await page.goto(p.url, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(400);
  const status = page.url();
  const visible = (await page.title()) || (await page.locator('body').innerText().catch(() => ''));
  await page.screenshot({ path: `${EV}/screenshots/01-probe-${p.name}.png`, fullPage: false }).catch(() => {});
  // Check for 500-style content
  const body = await page.locator('body').innerText().catch(() => '');
  if (/Internal Server Error|something went wrong|Application error/i.test(body)) {
    add('HIGH', p.url, '500-class on probe', body.slice(0, 200));
  } else if (/404|not found/i.test(body)) {
    add('INFO', p.url, '404 as expected', body.slice(0, 100));
  } else {
    add('MEDIUM', p.url, 'unexpected response', `landed on ${status}, body: ${body.slice(0, 100)}`);
  }
}

// Cmd+K command palette
console.log('\n=== Command palette ===');
await page.goto('/dashboard', { waitUntil: 'networkidle' });
await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
await page.waitForTimeout(500);
await page.screenshot({ path: `${EV}/screenshots/01-cmdk.png`, fullPage: false });
const cmdkVisible = await page.locator('[role="dialog"]:visible, [cmdk-dialog]:visible').count();
if (cmdkVisible === 0) {
  add('INFO', '/dashboard', 'no command palette', 'Ctrl+K did not open a palette');
} else {
  add('INFO', '/dashboard', 'command palette opened', 'palette visible');
}
await page.keyboard.press('Escape');

// User menu (top right)
console.log('\n=== User menu ===');
await page.goto('/dashboard', { waitUntil: 'networkidle' });
const userMenuTriggers = await page
  .locator('[aria-label*="account" i], [aria-label*="user" i], button:has-text("@")')
  .all();
console.log(`  user menu triggers: ${userMenuTriggers.length}`);
if (userMenuTriggers.length > 0) {
  await userMenuTriggers[0].click().catch(() => {});
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${EV}/screenshots/01-user-menu.png`, fullPage: false });
  await page.keyboard.press('Escape');
}

// Save findings
fs.writeFileSync(
  `${EV}/logs/01-crawl-findings.json`,
  JSON.stringify({ findings, errors }, null, 2)
);
console.log(
  `\n=== Done. ${findings.length} findings, ${errors.length} raw errors. ===`
);

await browser.close();
