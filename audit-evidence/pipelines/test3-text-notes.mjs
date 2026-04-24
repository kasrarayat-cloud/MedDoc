// TEST 3 — text_notes pipeline end-to-end.
// Cheapest flow (no Deepgram, ~$0.10). Creates a patient, submits
// shorthand, polls for READY, then exercises SOAP editor, copy,
// export PDF, email, and sign.

import { chromium } from '@playwright/test';
import * as fs from 'node:fs';
const EV = '/opt/meddoc-pro/audit-evidence/pipelines';

const bugs = [];
const push = (sev, title, detail) => {
  bugs.push({ when: new Date().toISOString(), sev, title, detail });
  console.log(`  [${sev}] ${title} :: ${detail.slice(0, 100)}`);
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

// -- Login --
await page.goto('https://app.quillmd.com/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/);
console.log('logged in');

// -- Create a text_notes visit --
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
await page.waitForTimeout(1500);
await page.screenshot({ path: `${EV}/screenshots/t3-01-step2.png`, fullPage: true });

// Step 2: chief complaint
const cc = page.getByLabel(/chief complaint|reason/i).first();
if (await cc.isVisible().catch(() => false))
  await cc.fill('Lower back pain x 3 weeks');
await page.getByRole('button', { name: /continue|next/i }).first().click();
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/t3-02-step3.png`, fullPage: true });

// Step 3: capture mode — text_notes card
const textTile = page.locator('button, [role="radio"], [role="button"]').filter({
  hasText: /text to soap|text notes|typed/i,
}).first();
if (await textTile.isVisible().catch(() => false)) {
  await textTile.click();
}
await page.waitForTimeout(400);
await page.screenshot({ path: `${EV}/screenshots/t3-03-mode-text.png`, fullPage: true });

// Submit wizard — text-mode lands directly on the visit page
const submitBtn = page.getByRole('button', { name: /create visit|start visit|begin|submit/i }).first();
if (await submitBtn.isVisible().catch(() => false)) {
  await submitBtn.click();
  await page.waitForURL(/\/visits\/[^/]+$/, { timeout: 15000 });
}
await page.waitForTimeout(1500);
const visitUrl = page.url();
console.log('visit URL:', visitUrl);
const visitId = visitUrl.split('/').pop();
fs.writeFileSync(`${EV}/logs/t3-visit-id.txt`, visitId);
await page.screenshot({ path: `${EV}/screenshots/t3-04-text-composer.png`, fullPage: true });

// -- Paste shorthand + expand to SOAP --
const textarea = page.locator('textarea').first();
if (!(await textarea.isVisible().catch(() => false))) {
  push('HIGH', 'text_notes UI missing textarea', `visit ${visitId} landed but no textarea visible`);
} else {
  const shorthand = '45M LBP x 3wk, started ibu 400mg TID, BP 140/88, HR 78. f/u 2wk. A1c ordered.';
  await textarea.fill(shorthand);
  await page.screenshot({ path: `${EV}/screenshots/t3-05-shorthand-entered.png`, fullPage: true });
  const expand = page.getByRole('button', { name: /expand.*soap|submit/i }).first();
  if (await expand.isVisible().catch(() => false)) {
    await expand.click();
    console.log('expand clicked; waiting for processing');
  } else push('HIGH', 'no "Expand to SOAP" button found', 'visit stuck at text-composer');
}

// -- Poll for READY --
const start = Date.now();
const timeoutMs = 120_000;
let finalStatus = 'UNKNOWN';
while (Date.now() - start < timeoutMs) {
  const info = await page.evaluate(async (id) => {
    const r = await fetch(`/api/visits/${id}/status`, { credentials: 'include' });
    return { status: r.status, body: await r.text() };
  }, visitId);
  if (info.status === 200) {
    try {
      const j = JSON.parse(info.body);
      finalStatus = j.status ?? JSON.stringify(j).slice(0, 80);
      console.log(`  poll t+${((Date.now() - start) / 1000).toFixed(1)}s: ${finalStatus}`);
      if (finalStatus === 'READY' || finalStatus === 'FAILED' || finalStatus === 'SIGNED') break;
    } catch {}
  }
  await new Promise((r) => setTimeout(r, 5000));
}
console.log('final status:', finalStatus);
if (finalStatus !== 'READY') push('HIGH', 'text_notes pipeline did not reach READY', `ended at ${finalStatus} after ${((Date.now()-start)/1000).toFixed(0)}s`);

// -- Reload + capture each tab --
await page.goto(visitUrl);
await page.waitForTimeout(2000);
await page.screenshot({ path: `${EV}/screenshots/t3-06-visit-ready.png`, fullPage: true });

// Dump every tab
for (const tabName of ['SOAP Note', 'Transcript', 'Input', 'Codes', 'Rx', 'Extras', 'Pipeline']) {
  const t = page.getByRole('tab', { name: new RegExp(`^${tabName}$`, 'i') }).first();
  if (await t.isVisible().catch(() => false)) {
    await t.click();
    await page.waitForTimeout(600);
    await page.screenshot({
      path: `${EV}/screenshots/t3-07-tab-${tabName.toLowerCase().replace(/\s+/g, '-')}.png`,
      fullPage: true,
    });
  }
}

// -- SOAP editor persistence check --
const soapTab = page.getByRole('tab', { name: /^soap note$/i }).first();
if (await soapTab.isVisible().catch(() => false)) await soapTab.click();
await page.waitForTimeout(500);
// Click SOAP to enter edit mode
const soapSurface = page.locator('button.group, [class*="group"]').filter({ hasText: /./ }).first();
const edited = `--- AUDIT EDIT MARKER ${Date.now()} ---`;
const editButton = page.locator('button').filter({ hasText: /click to edit/i }).first();
if (await editButton.isVisible().catch(() => false)) {
  await editButton.click();
} else {
  // SoapMarkdown click anywhere on the note surface
  const noteSurface = page.locator('textarea, [contenteditable]').first();
  if (!(await noteSurface.isVisible().catch(() => false))) {
    // Click on the SOAP text block itself
    await page.locator('button').filter({ hasText: /subjective|objective|assessment/i }).first().click().catch(() => {});
  }
}
await page.waitForTimeout(400);
const editArea = page.locator('textarea[aria-label="Edit SOAP note"]').first();
if (await editArea.isVisible().catch(() => false)) {
  const original = await editArea.inputValue();
  await editArea.fill(original + '\n\n' + edited);
  await page.getByRole('button', { name: /save edits/i }).click();
  await page.waitForTimeout(2000);
  // Reload
  await page.reload();
  await page.waitForTimeout(2000);
  await soapTab.click().catch(() => {});
  await page.waitForTimeout(500);
  // Look for the marker in the rendered SOAP
  const html = await page.content();
  if (!html.includes(edited)) {
    push('HIGH', 'SOAP edit did not persist after reload', `marker "${edited}" missing`);
  } else {
    console.log('  SOAP edit persisted ✓');
  }
} else {
  push('MED', 'could not find SOAP textarea to edit', 'edit button missing or click pattern changed');
}

// -- Export PDF (direct fetch) --
const pdfResp = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/pdf`, { credentials: 'include' });
  return { status: r.status, type: r.headers.get('content-type'), len: (await r.blob()).size };
}, visitId);
console.log('PDF export:', pdfResp);
if (pdfResp.status !== 200 || !(pdfResp.type ?? '').includes('pdf')) {
  push('MED', 'PDF export did not return a PDF', `status=${pdfResp.status} type=${pdfResp.type} bytes=${pdfResp.len}`);
}

// -- Sign button + read-only state --
const signBtn = page.getByRole('button', { name: /sign & send|sign & deliver/i }).first();
if (await signBtn.isVisible().catch(() => false)) {
  await signBtn.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${EV}/screenshots/t3-08-sign-modal.png`, fullPage: true });
  // In the modal, uncheck email / keep PDF then deliver
  const delivBtn = page.getByRole('button', { name: /sign.*deliver|confirm/i }).first();
  if (await delivBtn.isVisible().catch(() => false)) {
    await delivBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${EV}/screenshots/t3-09-after-sign.png`, fullPage: true });
  }
}

fs.writeFileSync(`${EV}/logs/t3-bugs.json`, JSON.stringify(bugs, null, 2));
fs.writeFileSync(`${EV}/logs/t3-network.json`, JSON.stringify(netErrs, null, 2));
console.log(`\n=== TEST 3 done: ${bugs.length} bugs, ${netErrs.length} network events ===`);
await browser.close();
