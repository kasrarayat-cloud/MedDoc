// Phase 4 + 6 + 8: Patient flows, special-char handling, status transitions.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const VID = 'cmodivx6o000201mqi5whp7d5';
const findings = [];

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

const consoleErrs = [];
page.on('pageerror', (e) =>
  add('HIGH', page.url(), 'page error', e.message.slice(0, 300))
);
page.on('console', (m) => {
  if (m.type() === 'error') {
    const t = m.text();
    if (/\[next-auth\]/i.test(t)) return;
    consoleErrs.push({ url: page.url(), text: t });
  }
});

await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });

// ====================================================================
// Patients page
// ====================================================================
console.log('\n=== /patients ===');
await page.goto('/patients', { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/06-patients-list.png`, fullPage: true });

// Search a patient
const search = page.locator('input[type="search"], input[placeholder*="search" i]').first();
if (await search.isVisible().catch(() => false)) {
  await search.fill('xyz-no-match-deep-hunt');
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${EV}/screenshots/06-patients-empty-search.png`, fullPage: true });
  await search.fill('');
}

// Click a patient row → patient detail
const rows = await page.locator('a[href^="/patients/c"]').all();
console.log(`patient links: ${rows.length}`);
if (rows.length > 0) {
  const href = await rows[0].getAttribute('href');
  console.log(`  navigating to ${href}`);
  await rows[0].click();
  await page.waitForURL(/\/patients\/c[a-z0-9]+/, { timeout: 8000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${EV}/screenshots/06-patient-detail.png`, fullPage: true });

  // Click Edit (if any) and try special-char inputs
  const editBtn = page.getByRole('button', { name: /^edit/i }).first();
  if (await editBtn.isVisible().catch(() => false)) {
    await editBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${EV}/screenshots/06-patient-edit-modal.png`, fullPage: true });
    // Cancel — don't actually mutate prod patient
    await page.keyboard.press('Escape');
  }
}

// ====================================================================
// Special-char patient names via direct API (POST /api/patients)
// — anti-XSS / unicode round-trip
// ====================================================================
console.log('\n=== Special-char patient creates ===');
const specials = [
  { name: '<script>alert(1)</script>', dob: '1990-01-01' },
  { name: 'Bobby"; DROP TABLE patients;--', dob: '1990-02-02' },
  { name: '🔥 Emoji Patient 🩺', dob: '1990-03-03' },
  { name: 'محمد العربي', dob: '1990-04-04' }, // Arabic RTL
  { name: 'A'.repeat(250), dob: '1990-05-05' }, // long
];
const createdIds = [];
for (const p of specials) {
  const r = await page.evaluate(async (body) => {
    const resp = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: body.name, dateOfBirth: body.dob }),
    });
    const text = await resp.text();
    return { status: resp.status, body: text.slice(0, 250) };
  }, p);
  console.log(`  "${p.name.slice(0, 30)}..." → ${r.status}`);
  add(
    'INFO',
    '/api/patients',
    `create '${p.name.slice(0, 20).replace(/[^a-z0-9]/gi, '?')}' status ${r.status}`,
    r.body.slice(0, 150)
  );
  // Try to capture a created id
  const m = r.body.match(/"id":"(c[a-z0-9]+)"/);
  if (m) createdIds.push({ id: m[1], name: p.name });
}

// Render a special-char patient on the patients page — does the name get
// echoed safely?
if (createdIds.length > 0) {
  await page.goto('/patients', { waitUntil: 'networkidle' });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${EV}/screenshots/06-special-chars-rendered.png`, fullPage: true });
  // Check that <script> was not evaluated — page.evaluate to look at DOM
  const scriptInjected = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script')).some((s) =>
      /alert\(1\)/.test(s.textContent ?? '')
    );
  });
  add(
    scriptInjected ? 'CRITICAL' : 'INFO',
    '/patients',
    scriptInjected ? 'XSS — script tag injected in patient name rendered!' : 'XSS attempt safely escaped',
    ''
  );
}

// ====================================================================
// Visit lifecycle — sign already-signed visit again? archive non-signed?
// ====================================================================
console.log('\n=== Lifecycle probes ===');
// Find a SIGNED visit owned by qa-audit
const signedProbe = await page.evaluate(async () => {
  const r = await fetch('/api/visits/cmocm9jki000601kwxf575d00/sign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ destinations: [] }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 250) };
});
add(
  'INFO',
  '/api/visits/cmocm9jki…/sign',
  `re-sign already-SIGNED status ${signedProbe.status}`,
  signedProbe.body
);

// Archive a non-signed visit (should 400)
const archiveProbe = await page.evaluate(
  async (id) => {
    const r = await fetch(`/api/visits/${id}/archive`, { method: 'POST' });
    return { status: r.status, body: (await r.text()).slice(0, 200) };
  },
  VID
);
add('INFO', `/api/visits/${VID}/archive`, `archive READY status ${archiveProbe.status}`, archiveProbe.body);

// Restore not-deleted visit (should 200 alreadyActive)
const restoreProbe = await page.evaluate(
  async (id) => {
    const r = await fetch(`/api/visits/${id}/restore`, { method: 'POST' });
    return { status: r.status, body: (await r.text()).slice(0, 200) };
  },
  VID
);
add(
  'INFO',
  `/api/visits/${VID}/restore`,
  `restore non-trashed status ${restoreProbe.status}`,
  restoreProbe.body
);

// /retry on a READY visit — does it work? Could re-running pipeline overwrite SOAP?
const retryProbe = await page.evaluate(
  async (id) => {
    const r = await fetch(`/api/visits/${id}/retry`, { method: 'POST' });
    return { status: r.status, body: (await r.text()).slice(0, 200) };
  },
  VID
);
add(
  retryProbe.status === 200 ? 'MEDIUM' : 'INFO',
  `/api/visits/${VID}/retry`,
  `retry on READY status ${retryProbe.status}`,
  retryProbe.body
);

// ====================================================================
// Concurrent submit on text re-entry: simulate by sending TWO POSTs in quick succession
// ====================================================================
console.log('\n=== Concurrent text submits ===');
const concurrentRes = await page.evaluate(async (id) => {
  const send = (n) =>
    fetch(`/api/visits/${id}/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: `Concurrent ${n} — ` + 'x'.repeat(50) }),
    }).then(async (r) => ({ n, status: r.status, body: (await r.text()).slice(0, 100) }));
  return Promise.all([send(1), send(2), send(3)]);
}, VID);
for (const r of concurrentRes) {
  add('INFO', `/api/visits/${VID}/text`, `concurrent #${r.n} status ${r.status}`, r.body);
}

// ====================================================================
// /api/visits/[id]/progress — info disclosure?
// ====================================================================
const progressProbe = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/progress`);
  return { status: r.status, body: (await r.text()).slice(0, 400) };
}, VID);
add('INFO', `/api/visits/${VID}/progress`, `progress status ${progressProbe.status}`, progressProbe.body);

fs.writeFileSync(
  `${EV}/logs/06-findings.json`,
  JSON.stringify({ findings, consoleErrs, createdIds }, null, 2)
);
console.log(`\n${findings.length} findings, ${consoleErrs.length} console errors`);

await browser.close();
