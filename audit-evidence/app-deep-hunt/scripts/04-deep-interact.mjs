// Phase 3-deep: click everything on the visit detail page.
// Capture every API call. Look for IDOR / leaks / unexpected state.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const VID = 'cmodivx6o000201mqi5whp7d5';
const findings = [];
const apiCalls = [];

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

page.on('pageerror', (e) =>
  add('HIGH', page.url(), 'page error', e.message.slice(0, 300))
);
page.on('response', async (r) => {
  const u = r.url();
  if (!/\/api\//.test(u)) return;
  let bodySize = 0;
  try {
    bodySize = (await r.body().catch(() => Buffer.alloc(0))).length;
  } catch {}
  apiCalls.push({
    method: r.request().method(),
    url: u.replace('https://app.quillmd.com', ''),
    status: r.status(),
    bytes: bodySize,
  });
});
page.on('console', (m) => {
  if (m.type() === 'error') {
    const t = m.text();
    if (/\[next-auth\]/i.test(t)) return;
    add('LOW', page.url(), 'console error', t.slice(0, 200));
  }
});

await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });
console.log('logged in');

await page.goto(`/visits/${VID}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);

// Click every visible button. Wait between each click. Capture screenshot of
// any modal that opens and dismiss it.
const buttons = await page.locator('button:visible').all();
console.log(`Found ${buttons.length} visible buttons on visit detail`);

for (let i = 0; i < buttons.length; i++) {
  const btn = buttons[i];
  // Re-query in case earlier clicks changed the DOM
  const visible = await btn.isVisible().catch(() => false);
  if (!visible) continue;
  const label = (await btn.innerText().catch(() => ''))?.trim().slice(0, 40) || `btn-${i}`;
  const aria = (await btn.getAttribute('aria-label').catch(() => null)) || '';
  const id = `${i}-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  console.log(`  [${i}] click "${label}" (aria="${aria}")`);

  // Skip the destructive ones we don't want to fire
  if (/delete|sign out|trash|sign\s*&|sign\s*and|sign$/i.test(label)) {
    console.log(`    skip — destructive`);
    continue;
  }

  const startCalls = apiCalls.length;
  await btn.click({ timeout: 2000 }).catch(() => {});
  await page.waitForTimeout(700);
  const newCalls = apiCalls.slice(startCalls);
  if (newCalls.length > 0) {
    add(
      'INFO',
      `/visits/${VID}`,
      `click '${label.slice(0, 30)}' fired API`,
      newCalls.map((c) => `${c.method} ${c.url} → ${c.status}`).join('; ').slice(0, 250)
    );
  }
  await page.screenshot({ path: `${EV}/screenshots/04-after-click-${id}.png`, fullPage: false }).catch(() => {});
  // Close any open dialog with Escape
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(200);
}

// Try the IDOR probe: load another user's visit
console.log('\n=== IDOR probe ===');
const idorVisits = [
  // Pick known SIGNED visits owned by another user
  'cmo8asvl4000001mu0pgives2', // signed, owned by cmo5ye2nm... user
  'cmo61e0os000001qlh5w5mdhh',
  'cmo8tfejv000301mtnxkx640p',
];
for (const otherId of idorVisits) {
  const r = await page.evaluate(async (id) => {
    const probes = [];
    for (const path of [
      `/api/visits/${id}`,
      `/api/visits/${id}/status`,
      `/api/visits/${id}/progress`,
      `/api/visits/${id}/export/clipboard?format=epic`,
      `/api/visits/${id}/export/pdf`,
      `/api/visits/${id}/export/docx`,
      `/api/visits/${id}/dictation/audio`,
    ]) {
      try {
        const res = await fetch(path);
        const ct = res.headers.get('content-type') || '';
        const sample = ct.startsWith('application/json')
          ? (await res.text()).slice(0, 150)
          : `(non-json, ${res.headers.get('content-length') ?? '?'} bytes)`;
        probes.push({ path, status: res.status, sample });
      } catch (e) {
        probes.push({ path, error: String(e).slice(0, 100) });
      }
    }
    return probes;
  }, otherId);
  for (const p of r) {
    if (p.status >= 200 && p.status < 300) {
      add('HIGH', p.path, 'IDOR? — 2xx on another user\'s visit', JSON.stringify(p));
    } else if (p.status === 404 || p.status === 403) {
      add('INFO', p.path, `${p.status} on another user`, '');
    } else {
      add('MEDIUM', p.path, `unexpected ${p.status}`, JSON.stringify(p));
    }
  }
}

// Try /export endpoints on OUR own UNSIGNED visit (some apps gate exports
// behind sign — check)
console.log('\n=== Export-on-unsigned probe ===');
const exportAttempts = await page.evaluate(async (id) => {
  const out = [];
  for (const path of [
    `/api/visits/${id}/export/pdf`,
    `/api/visits/${id}/export/docx`,
    `/api/visits/${id}/export/clipboard?format=epic`,
  ]) {
    try {
      const r = await fetch(path);
      const ct = r.headers.get('content-type') || '';
      const sample = ct.startsWith('application/json') || ct.startsWith('text/')
        ? (await r.text()).slice(0, 100)
        : `(${ct}, ${r.headers.get('content-length') ?? '?'} bytes)`;
      out.push({ path, status: r.status, sample });
    } catch (e) {
      out.push({ path, error: String(e).slice(0, 100) });
    }
  }
  return out;
}, VID);
for (const p of exportAttempts) {
  add(
    p.status >= 200 && p.status < 300 ? 'INFO' : 'INFO',
    p.path,
    `unsigned-export status ${p.status}`,
    JSON.stringify(p).slice(0, 250)
  );
}

fs.writeFileSync(
  `${EV}/logs/04-findings.json`,
  JSON.stringify({ findings, apiCalls: apiCalls.slice(-100) }, null, 2)
);
console.log(`\n${findings.length} findings, ${apiCalls.length} api calls`);

await browser.close();
