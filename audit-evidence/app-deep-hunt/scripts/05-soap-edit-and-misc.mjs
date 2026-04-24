// Phase 3+5: SOAP click-to-edit deep test, settings flow probes, mobile viewport
// snapshot. Picks at corners.

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
console.log('logged in');

// ====================================================================
// SOAP click-to-edit deep test
// ====================================================================
console.log('\n=== SOAP edit deep test ===');
await page.goto(`/visits/${VID}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
// Find SOAP tab
const soapTabBtn = page.getByRole('tab', { name: /SOAP|note/i }).first();
if (await soapTabBtn.isVisible().catch(() => false)) {
  await soapTabBtn.click();
  await page.waitForTimeout(400);
}
await page.screenshot({ path: `${EV}/screenshots/05-soap-readonly.png`, fullPage: true });

// Click the click-to-edit area: button containing SoapMarkdown
const editTrigger = page
  .locator('button:has-text("Click to edit"), button[class*="cursor-text"]')
  .first();
const triggerVisible = await editTrigger.isVisible().catch(() => false);
add('INFO', `/visits/${VID}`, 'soap edit trigger visible', String(triggerVisible));
if (triggerVisible) {
  await editTrigger.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${EV}/screenshots/05-soap-editing.png`, fullPage: true });

  // Find textarea inside SOAP editor
  const ta = page.locator('textarea[aria-label="Edit SOAP note"]').first();
  if (!(await ta.isVisible().catch(() => false))) {
    add('HIGH', `/visits/${VID}`, 'SOAP textarea not found after click-to-edit', '');
  } else {
    const orig = (await ta.inputValue()) ?? '';
    const marker = `\n\n[DEEP_HUNT_${Date.now()}]`;
    await ta.fill(orig + marker);
    await page.screenshot({ path: `${EV}/screenshots/05-soap-edited.png`, fullPage: true });

    // Save
    const saveBtn = page.getByRole('button', { name: /save edits/i }).first();
    if (!(await saveBtn.isVisible().catch(() => false))) {
      add('HIGH', `/visits/${VID}`, 'no save edits button', '');
    } else {
      await saveBtn.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: `${EV}/screenshots/05-soap-saved.png`, fullPage: true });
      // Reload + verify persistence
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(700);
      const after = await page.locator('main').first().innerText().catch(() => '');
      const persisted = /DEEP_HUNT_\d+/.test(after);
      add(
        persisted ? 'INFO' : 'HIGH',
        `/visits/${VID}`,
        persisted ? 'SOAP edit persisted across refresh' : 'SOAP edit NOT persisted',
        ''
      );
    }
  }
}

// ====================================================================
// /api/visits/[id]/text — POST after a text visit already has rawTextInput
// (status check should reject)
// ====================================================================
console.log('\n=== Re-submit text on existing visit ===');
const reText = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: 'Second submission attempt — should be rejected as state is past QUEUED' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, VID);
add(
  reText.status === 409 || reText.status === 400 ? 'INFO' : 'HIGH',
  `/visits/${VID}`,
  `re-submit text status ${reText.status}`,
  reText.body
);

// ====================================================================
// /api/visits/[id]/upload — POST audio when inputMode is text_notes
// ====================================================================
console.log('\n=== Upload audio on text visit ===');
const reUpload = await page.evaluate(async (id) => {
  // Tiny dummy webm body
  const body = new Uint8Array([0x1a, 0x45, 0xdf, 0xa3]);
  const r = await fetch(`/api/visits/${id}/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'audio/webm', 'Content-Length': String(body.length), 'X-TM-Filename': 'a.webm' },
    body,
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, VID);
add(
  reUpload.status >= 400 ? 'INFO' : 'HIGH',
  `/visits/${VID}`,
  `audio upload to text visit ${reUpload.status}`,
  reUpload.body
);

// ====================================================================
// Settings page deep probe
// ====================================================================
console.log('\n=== Settings page ===');
await page.goto('/settings', { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/05-settings.png`, fullPage: true });

// Inventory of fields
const fieldCount = {
  inputs: await page.locator('input:visible').count(),
  textareas: await page.locator('textarea:visible').count(),
  selects: await page.locator('select:visible').count(),
  buttons: await page.locator('button:visible').count(),
};
add('INFO', '/settings', 'field inventory', JSON.stringify(fieldCount));

// Look for any links/buttons that suggest dev/admin
const danger = await page
  .locator(':has-text("Delete"), :has-text("delete account"), :has-text("Danger")')
  .all();
for (const d of danger) {
  const t = ((await d.innerText().catch(() => '')) || '').slice(0, 60);
  if (t) console.log(`  danger label: ${t}`);
}

// Click delete account to see modal (DON'T confirm)
const delBtn = page
  .getByRole('button', { name: /delete account|delete my account/i })
  .first();
if (await delBtn.isVisible().catch(() => false)) {
  await delBtn.click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${EV}/screenshots/05-delete-account-modal.png`, fullPage: true });
  // Look for the warning text + cancel button
  const cancelBtn = page.getByRole('button', { name: /cancel|never mind|keep/i }).first();
  if (await cancelBtn.isVisible().catch(() => false)) {
    await cancelBtn.click();
    add('INFO', '/settings', 'delete-account modal opened + cancelled', '');
  }
}

// ====================================================================
// /api/auth/forgot-password while logged in (defensive)
// ====================================================================
const fp = await page.evaluate(async (email) => {
  const r = await fetch('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 250) };
}, process.env.TEST_APP_EMAIL);
add('INFO', '/api/auth/forgot-password', `status ${fp.status}`, fp.body);

// ====================================================================
// Mobile viewport
// ====================================================================
console.log('\n=== Mobile viewport ===');
await page.setViewportSize({ width: 393, height: 851 });
await page.goto('/dashboard', { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/05-mobile-dashboard.png`, fullPage: true });
await page.goto(`/visits/${VID}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/05-mobile-visit.png`, fullPage: true });
await page.goto('/visits/new', { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/05-mobile-newvisit.png`, fullPage: true });
await page.goto('/settings', { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/05-mobile-settings.png`, fullPage: true });

// Check for horizontal overflow
for (const [name, url] of [
  ['mobile-dashboard', '/dashboard'],
  ['mobile-visit', `/visits/${VID}`],
]) {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  const hasOverflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  if (hasOverflow) {
    add('MEDIUM', url, `mobile horizontal overflow`, `at 393px viewport`);
  }
}

fs.writeFileSync(
  `${EV}/logs/05-findings.json`,
  JSON.stringify({ findings, consoleErrs }, null, 2)
);
console.log(`\n${findings.length} findings, ${consoleErrs.length} console errors`);

await browser.close();
