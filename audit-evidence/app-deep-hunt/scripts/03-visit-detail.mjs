// Phase 3: visit-detail tab + sign + post-sign probing.

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

page.on('pageerror', (e) =>
  add('HIGH', page.url(), 'page error', e.message.slice(0, 300))
);
page.on('response', (r) => {
  if (r.status() >= 500)
    add('HIGH', page.url(), '5xx response', `${r.status()} ${r.url()}`);
});
const consoleErrs = [];
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

await page.goto(`/visits/${VID}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/03-visit-loaded.png`, fullPage: true });

// Discover tabs
const tabs = await page.locator('[role="tab"], [data-tab], .tab').all();
console.log(`Found ${tabs.length} tabs`);
const tabNames = [];
for (const t of tabs) {
  const txt = (await t.innerText().catch(() => ''))?.trim();
  if (txt) tabNames.push(txt);
}
console.log('Tab names:', tabNames);
add('INFO', `/visits/${VID}`, 'tab inventory', tabNames.join(' | '));

// Click each tab, screenshot, look for empty/broken states
for (let i = 0; i < tabs.length; i++) {
  const t = tabs[i];
  const txt = ((await t.innerText().catch(() => '')) || `tab-${i}`)
    .trim()
    .replace(/[^a-z0-9]+/gi, '-')
    .toLowerCase()
    .slice(0, 30);
  await t.click().catch(() => {});
  await page.waitForTimeout(800);
  await page
    .screenshot({ path: `${EV}/screenshots/03-tab-${i}-${txt}.png`, fullPage: true })
    .catch(() => {});
  // Check for "no data" / "error" markers
  const body = await page.locator('main, body').first().innerText().catch(() => '');
  if (/something went wrong|error loading|undefined|null/i.test(body) && body.length < 1000) {
    add('MEDIUM', `/visits/${VID}#${txt}`, 'broken-tab marker', body.slice(0, 200));
  }
}

// SOAP edit attempt
console.log('\n=== SOAP edit ===');
const soapTab = page.getByRole('tab', { name: /soap|note/i }).first();
if (await soapTab.isVisible().catch(() => false)) {
  await soapTab.click();
  await page.waitForTimeout(500);
}
const editBtn = page.getByRole('button', { name: /^edit/i }).first();
const editVisible = await editBtn.isVisible().catch(() => false);
add('INFO', `/visits/${VID}`, 'SOAP edit button visible', String(editVisible));
if (editVisible) {
  await editBtn.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${EV}/screenshots/03-soap-edit-mode.png`, fullPage: true });
  const editor = page.locator('[contenteditable="true"], textarea').first();
  const editorVisible = await editor.isVisible().catch(() => false);
  add('INFO', `/visits/${VID}`, 'SOAP editor visible', String(editorVisible));
  if (editorVisible) {
    // Append a marker
    await editor.click();
    await editor.evaluate((el) => {
      if (el instanceof HTMLTextAreaElement) {
        el.value += '\n\nDEEP HUNT MARKER ' + Date.now();
        el.dispatchEvent(new Event('input', { bubbles: true }));
      } else {
        el.focus();
        document.execCommand('insertText', false, '\n\nDEEP HUNT MARKER ' + Date.now());
      }
    });
    await page.waitForTimeout(300);
    const saveBtn = page.getByRole('button', { name: /^save/i }).first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(1500);
      await page.screenshot({
        path: `${EV}/screenshots/03-soap-after-save.png`,
        fullPage: true,
      });
      // Refresh and verify persistence
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(500);
      const after = await page.locator('main').first().innerText().catch(() => '');
      const persisted = /DEEP HUNT MARKER/.test(after);
      if (persisted) {
        add('INFO', `/visits/${VID}`, 'SOAP edit persisted', 'marker visible after refresh');
      } else {
        add('HIGH', `/visits/${VID}`, 'SOAP edit did NOT persist', 'no marker after refresh');
      }
      await page.screenshot({
        path: `${EV}/screenshots/03-soap-after-refresh.png`,
        fullPage: true,
      });
    } else {
      add('MEDIUM', `/visits/${VID}`, 'SOAP edit no save button', '');
    }
  }
}

// Sign flow
console.log('\n=== Sign flow ===');
const signBtn = page.getByRole('button', { name: /^sign|sign.*visit/i }).first();
if (await signBtn.isVisible().catch(() => false)) {
  await signBtn.click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${EV}/screenshots/03-sign-modal.png`, fullPage: true });
  // Pick destinations: clipboard_generic only (no email side-effect; safe)
  // Look for a "generic" or "copy" option
  const genericOpt = page
    .getByRole('button', { name: /generic|copy/i })
    .or(page.getByLabel(/generic|copy/i))
    .first();
  if (await genericOpt.isVisible().catch(() => false)) {
    await genericOpt.click().catch(() => {});
    await page.waitForTimeout(300);
  }
  // Submit / sign
  const confirmBtn = page
    .getByRole('button', { name: /^sign|confirm|continue/i })
    .last();
  if (await confirmBtn.isVisible().catch(() => false)) {
    await confirmBtn.click();
    await page.waitForTimeout(2500);
    await page.screenshot({
      path: `${EV}/screenshots/03-after-sign.png`,
      fullPage: true,
    });
  }
}

// Now try to edit AFTER sign
console.log('\n=== Edit-after-sign attempt ===');
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/03-signed-view.png`, fullPage: true });
const editBtn2 = page.getByRole('button', { name: /^edit/i }).first();
const editAfterSignVisible = await editBtn2.isVisible().catch(() => false);
if (editAfterSignVisible) {
  add('HIGH', `/visits/${VID}`, 'edit button visible AFTER sign', 'should be disabled/hidden on SIGNED visit');
  await editBtn2.click().catch(() => {});
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${EV}/screenshots/03-attempted-edit-after-sign.png`, fullPage: true });
}

// Direct API attempt: PATCH the visit text after sign?
const directApiAttempt = await page.evaluate(async (id) => {
  // Try common edit/PATCH endpoints
  const probes = [
    { method: 'PATCH', url: `/api/visits/${id}` },
    { method: 'POST', url: `/api/visits/${id}/text` },
    { method: 'POST', url: `/api/visits/${id}/upload` },
  ];
  const results = [];
  for (const p of probes) {
    try {
      const r = await fetch(p.url, {
        method: p.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'AFTER SIGN tampering attempt — should be 4xx or 409' }),
      });
      results.push({ ...p, status: r.status, body: (await r.text()).slice(0, 200) });
    } catch (e) {
      results.push({ ...p, error: String(e).slice(0, 200) });
    }
  }
  return results;
}, VID);
add('INFO', `/visits/${VID}`, 'direct-API after-sign probes', JSON.stringify(directApiAttempt));

// Try /api/visits/[id]/retry on a SIGNED visit
const retryAttempt = await page.evaluate(async (id) => {
  try {
    const r = await fetch(`/api/visits/${id}/retry`, { method: 'POST' });
    return { status: r.status, body: (await r.text()).slice(0, 200) };
  } catch (e) {
    return { error: String(e).slice(0, 200) };
  }
}, VID);
add('INFO', `/visits/${VID}`, 'retry on SIGNED visit', JSON.stringify(retryAttempt));

// Save findings
fs.writeFileSync(
  `${EV}/logs/03-findings.json`,
  JSON.stringify({ findings, consoleErrs }, null, 2)
);
console.log(`\n${findings.length} findings, ${consoleErrs.length} console errors`);

await browser.close();
