// TEST 3 (rev) — text_notes pipeline end-to-end. Fixed wizard flow:
// step 2 combines specialty + chief complaint + capture-mode tile;
// clicking the mode tile commits the visit directly.

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

const netErrs = [];
page.on('pageerror', (e) => netErrs.push({ type: 'pageerror', text: e.message.slice(0, 300) }));
page.on('response', (r) => {
  const u = r.url();
  if (r.status() >= 500) netErrs.push({ type: '5xx', url: u, status: r.status() });
  else if (r.status() >= 400 && /\/api\//.test(u) && !/\/api\/auth\//.test(u))
    netErrs.push({ type: `${r.status()}`, url: u, method: r.request().method() });
});
page.on('console', (m) => {
  if (m.type() === 'error') netErrs.push({ type: 'console', text: m.text().slice(0, 300) });
});

await page.goto('https://app.quillmd.com/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/);
console.log('logged in');

// --- Step 1: patient ---
await page.goto('https://app.quillmd.com/visits/new');
await page.waitForTimeout(500);
const pname = `TextNotes Patient ${Date.now().toString(36)}`;
await page.getByPlaceholder(/search by name or external id/i).fill(pname);
await page.waitForTimeout(600);
await page.getByRole('button', { name: /create new patient/i }).click();
await page.waitForTimeout(400);
await page.locator('input#name, input[placeholder="Jane Doe"]').first().fill(pname);
await page.locator('input[type="date"]').first().fill('1980-01-01');
await page.getByRole('button', { name: /create.*continue/i }).click();
await page.waitForTimeout(1200);

// --- Step 2: specialty (default), chief complaint, click "Text to SOAP" tile ---
const cc = page.getByPlaceholder(/headache|chief complaint/i).first();
if (await cc.isVisible().catch(() => false)) await cc.fill('Lower back pain x 3 weeks');
await page.waitForTimeout(200);
await page.screenshot({ path: `${EV}/screenshots/t3-02-step2-filled.png`, fullPage: true });

// The "Text to SOAP" tile — click the card itself.
const textTile = page.locator('text=/text to soap/i').first();
await textTile.click();
await page.waitForURL(/\/visits\/[^/]+$/, { timeout: 20000 });
const visitUrl = page.url();
const visitId = visitUrl.split('/').pop();
console.log('visit created:', visitId);
fs.writeFileSync(`${EV}/logs/t3-visit-id.txt`, visitId);
await page.screenshot({ path: `${EV}/screenshots/t3-03-text-composer.png`, fullPage: true });

// --- Paste shorthand + Expand to SOAP ---
const textarea = page.locator('textarea').first();
if (!(await textarea.isVisible().catch(() => false))) {
  push('HIGH', 'text_notes: textarea missing on visit page', `visit ${visitId}`);
} else {
  await textarea.fill('45M LBP x 3wk, started ibu 400mg TID, BP 140/88, HR 78. f/u 2wk. A1c ordered.');
  await page.screenshot({ path: `${EV}/screenshots/t3-04-shorthand-entered.png`, fullPage: true });
  const expand = page.getByRole('button', { name: /expand to soap|submit/i }).first();
  if (await expand.isVisible().catch(() => false)) {
    await expand.click();
    console.log('expand clicked');
  } else push('HIGH', 'text_notes: no Expand button', `visit ${visitId}`);
}

// --- Poll for READY ---
const start = Date.now();
const timeoutMs = 180_000;
let finalStatus = 'UNKNOWN';
let lastStatus = '';
while (Date.now() - start < timeoutMs) {
  const info = await page.evaluate(async (id) => {
    const r = await fetch(`/api/visits/${id}/status`, { credentials: 'include' });
    return { status: r.status, body: await r.text() };
  }, visitId);
  if (info.status === 200) {
    try {
      const j = JSON.parse(info.body);
      finalStatus = j.status ?? JSON.stringify(j).slice(0, 80);
      if (finalStatus !== lastStatus) {
        console.log(`  t+${((Date.now() - start) / 1000).toFixed(1)}s -> ${finalStatus}`);
        lastStatus = finalStatus;
      }
      if (['READY', 'FAILED', 'SIGNED'].includes(finalStatus)) break;
    } catch {}
  }
  await new Promise((r) => setTimeout(r, 4000));
}
console.log('final status:', finalStatus);
if (finalStatus !== 'READY') push('HIGH', 'text_notes pipeline stall', `ended at ${finalStatus}`);

// --- Reload visit page, screenshot each tab ---
await page.goto(visitUrl);
await page.waitForTimeout(2000);
await page.screenshot({ path: `${EV}/screenshots/t3-05-visit-ready.png`, fullPage: true });

// Every tab
const tabs = await page.locator('[role="tab"]').allInnerTexts();
fs.writeFileSync(`${EV}/logs/t3-tabs.json`, JSON.stringify(tabs));
console.log('tabs:', tabs);
for (const t of tabs) {
  const tab = page.getByRole('tab', { name: t }).first();
  if (await tab.isVisible().catch(() => false)) {
    await tab.click();
    await page.waitForTimeout(800);
    await page.screenshot({
      path: `${EV}/screenshots/t3-tab-${t.toLowerCase().replace(/\s+/g, '-')}.png`,
      fullPage: true,
    });
  }
}

// --- SOAP editor persistence ---
await page.getByRole('tab', { name: /^soap note$/i }).click().catch(() => {});
await page.waitForTimeout(500);
// SoapEditor is a <button> that toggles to textarea on click.
const editSurface = page.locator('button').filter({ hasText: /subjective|assessment|s:|a:/i }).first();
const hasEdit = await editSurface.isVisible().catch(() => false);
if (hasEdit) {
  await editSurface.click();
  await page.waitForTimeout(500);
  const ta = page.locator('textarea[aria-label="Edit SOAP note"]').first();
  if (await ta.isVisible().catch(() => false)) {
    const original = await ta.inputValue();
    const marker = `AUDIT_EDIT_MARKER_${Date.now().toString(36)}`;
    await ta.fill(original + '\n\n' + marker);
    await page.getByRole('button', { name: /save edits/i }).click();
    await page.waitForTimeout(2500);
    await page.reload();
    await page.waitForTimeout(2000);
    await page.getByRole('tab', { name: /^soap note$/i }).click().catch(() => {});
    await page.waitForTimeout(800);
    const html = await page.content();
    if (!html.includes(marker)) {
      push('HIGH', 'SOAP edit did not persist after reload', `marker ${marker} missing`);
    } else {
      console.log('  SOAP edit persisted ✓');
    }
  } else push('MED', 'SOAP edit mode: textarea not shown after click', '');
} else push('MED', 'SOAP editor surface not clickable', '');

// --- PDF export ---
const pdfResp = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/pdf`, { credentials: 'include' });
  const blob = await r.blob();
  return { status: r.status, type: r.headers.get('content-type'), len: blob.size };
}, visitId);
console.log('PDF:', pdfResp);
if (pdfResp.status !== 200 || !(pdfResp.type ?? '').includes('pdf'))
  push('MED', 'PDF export failed', JSON.stringify(pdfResp));

// --- Sign & deliver ---
const signBtn = page.getByRole('button', { name: /^sign & send$/i }).first();
if (await signBtn.isVisible().catch(() => false)) {
  await signBtn.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${EV}/screenshots/t3-06-sign-modal.png`, fullPage: true });
  const deliver = page.getByRole('button', { name: /sign & deliver/i }).first();
  if (await deliver.isVisible().catch(() => false)) {
    await deliver.click();
    await page.waitForTimeout(3000);
  }
  await page.screenshot({ path: `${EV}/screenshots/t3-07-after-sign.png`, fullPage: true });
}

// --- Final state check ---
await page.reload();
await page.waitForTimeout(1500);
const finalDom = await page.evaluate(() => ({
  signed: document.body.textContent?.includes('Signed') ?? false,
  readonly: document.querySelector('[aria-label="Edit SOAP note"]') === null,
}));
console.log('final dom:', finalDom);

fs.writeFileSync(`${EV}/logs/t3-bugs.json`, JSON.stringify(bugs, null, 2));
fs.writeFileSync(`${EV}/logs/t3-network.json`, JSON.stringify(netErrs, null, 2));
console.log(`\n=== TEST 3 done: ${bugs.length} bugs, ${netErrs.length} net events ===`);
await browser.close();
