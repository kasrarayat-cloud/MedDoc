// TEST 3 (rev2) — use an existing pre-seeded patient, skip the
// rate-limited create-patient path. Focus the test on the pipeline
// downstream of visit-creation.

import { chromium } from '@playwright/test';
import * as fs from 'node:fs';
const EV = '/opt/meddoc-pro/audit-evidence/pipelines';

const bugs = [];
const push = (sev, title, detail) => {
  bugs.push({ when: new Date().toISOString(), sev, title, detail });
  console.log(`  [${sev}] ${title} :: ${detail.slice(0, 120)}`);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const net = [];
page.on('pageerror', (e) => net.push({ k: 'pageerror', t: e.message.slice(0, 300) }));
page.on('response', (r) => {
  const u = r.url();
  if (r.status() >= 500) net.push({ k: '5xx', u, s: r.status() });
  else if (r.status() >= 400 && /\/api\//.test(u) && !/\/api\/auth\//.test(u))
    net.push({ k: `${r.status()}`, u, m: r.request().method() });
});
page.on('console', (m) => { if (m.type() === 'error') net.push({ k: 'console', t: m.text().slice(0, 300) }); });

await page.goto('https://app.quillmd.com/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/);
console.log('logged in');

// --- Step 1: pick an EXISTING patient (QA AudioUpload) ---
await page.goto('https://app.quillmd.com/visits/new');
await page.waitForTimeout(500);
await page.getByPlaceholder(/search by name or external id/i).fill('QA AudioUpload');
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/t3c-01-search.png`, fullPage: true });
// Click the first matching card (not "Create new patient")
const match = page.locator('button').filter({ hasText: /^QA AudioUpload/i }).first();
if (await match.isVisible().catch(() => false)) {
  await match.click();
} else {
  push('HIGH', 'Patient search did not return seeded patient', 'QA AudioUpload not findable');
  process.exit(2);
}
await page.waitForTimeout(800);

// --- Step 2: chief complaint + pick Text tile ---
const cc = page.getByPlaceholder(/headache|chief complaint/i).first();
if (await cc.isVisible().catch(() => false)) await cc.fill('Lower back pain x 3 weeks');
await page.screenshot({ path: `${EV}/screenshots/t3c-02-step2.png`, fullPage: true });

// The tile has text "Text to SOAP" but the click target is the whole card div/button.
// Try each locator style.
const tile = page.locator('button, [role="button"]').filter({ hasText: /text to soap/i }).first();
await tile.click();
await page.waitForURL(/\/visits\/[^/]+$/, { timeout: 20000 });
const visitId = page.url().split('/').pop();
console.log('visit:', visitId);
fs.writeFileSync(`${EV}/logs/t3c-visit-id.txt`, visitId);
await page.screenshot({ path: `${EV}/screenshots/t3c-03-text-page.png`, fullPage: true });

// --- Fill shorthand + Expand ---
const ta = page.locator('textarea').first();
await ta.fill('45M LBP x 3wk, started ibu 400mg TID, BP 140/88, HR 78. f/u 2wk. A1c ordered.');
await page.screenshot({ path: `${EV}/screenshots/t3c-04-filled.png`, fullPage: true });
const expand = page.getByRole('button', { name: /expand to soap/i }).first();
if (!(await expand.isVisible().catch(() => false))) push('HIGH', 'No Expand button', '');
else await expand.click();

// --- Poll for READY ---
const start = Date.now();
let final = 'UNKNOWN', last = '';
while (Date.now() - start < 180000) {
  const info = await page.evaluate(async (id) => {
    const r = await fetch(`/api/visits/${id}/status`, { credentials: 'include' });
    return { s: r.status, b: await r.text() };
  }, visitId);
  if (info.s === 200) {
    try {
      const j = JSON.parse(info.b);
      final = j.status ?? 'parse?';
      if (final !== last) { console.log(`  +${((Date.now() - start) / 1000).toFixed(1)}s ${final}`); last = final; }
      if (['READY', 'FAILED', 'SIGNED'].includes(final)) break;
    } catch {}
  }
  await new Promise((r) => setTimeout(r, 3000));
}
console.log('final:', final);
if (final !== 'READY') push('HIGH', 'text_notes pipeline did not reach READY', `ended=${final}`);

// --- Dump SOAP + other tabs ---
await page.goto(`https://app.quillmd.com/visits/${visitId}`);
await page.waitForTimeout(2500);
await page.screenshot({ path: `${EV}/screenshots/t3c-05-ready.png`, fullPage: true });

// Save the SOAP text as captured now
const soapText = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}`, { credentials: 'include' });
  if (!r.ok) return null;
  const j = await r.json();
  return { soapFinal: j.soapFinal?.slice(0, 2000), signedSoap: j.signedSoap?.slice(0, 200), status: j.status, needsReview: j.needsReview, reviewReason: j.reviewReason };
}).catch(() => null);
console.log('visit snapshot:', JSON.stringify(soapText, null, 2).slice(0, 400));
fs.writeFileSync(`${EV}/logs/t3c-visit-snapshot.json`, JSON.stringify(soapText, null, 2));

// --- PDF export ---
const pdf = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/pdf`, { credentials: 'include' });
  const b = await r.blob();
  return { s: r.status, t: r.headers.get('content-type'), len: b.size };
}, visitId);
console.log('pdf:', pdf);
if (pdf.s !== 200 || !(pdf.t ?? '').includes('pdf')) push('MED', 'PDF export bad', JSON.stringify(pdf));

// --- SOAP editor persistence check ---
await page.goto(`https://app.quillmd.com/visits/${visitId}`);
await page.waitForTimeout(1500);
// Click SOAP tab (should already be active, but ensure)
const soapTab = page.getByRole('tab', { name: /^soap note$/i });
if (await soapTab.isVisible().catch(() => false)) await soapTab.click();
await page.waitForTimeout(500);
// SoapEditor renders as a <button> (not editing) or <textarea> (editing).
// Click the preview to toggle edit mode.
const soapButton = page.locator('button.group, button[class*="group"]').filter({
  hasText: /subjective|objective|assessment|plan/i,
}).first();
if (await soapButton.isVisible().catch(() => false)) {
  await soapButton.click();
} else {
  // fallback: click any visible SoapMarkdown surface
  const anyPreview = page.locator('button').filter({ hasText: /s:|o:|a:|p:/i }).first();
  if (await anyPreview.isVisible().catch(() => false)) await anyPreview.click();
}
await page.waitForTimeout(600);
const editTa = page.locator('textarea[aria-label="Edit SOAP note"]').first();
if (await editTa.isVisible().catch(() => false)) {
  const before = await editTa.inputValue();
  const marker = `AUDIT_MARKER_${Date.now().toString(36)}`;
  await editTa.fill(before + '\n\n' + marker);
  await page.getByRole('button', { name: /save edits/i }).click();
  await page.waitForTimeout(2500);
  await page.reload();
  await page.waitForTimeout(2500);
  const after = await page.content();
  if (!after.includes(marker)) push('HIGH', 'SOAP edit did not persist after reload', marker);
  else console.log('  SOAP edit persisted ✓');
} else {
  push('MED', 'SOAP edit: textarea did not appear', 'click pattern may have changed');
}

fs.writeFileSync(`${EV}/logs/t3c-bugs.json`, JSON.stringify(bugs, null, 2));
fs.writeFileSync(`${EV}/logs/t3c-net.json`, JSON.stringify(net, null, 2));
console.log(`\n=== TEST 3 done: ${bugs.length} bugs, ${net.length} net events ===`);
await browser.close();
