// ============================================================================
// Phase 2: Create a text_notes visit, watch transitions, then exercise the
// visit-detail tabs once READY. Captures unexpected console / 4xx / 5xx
// alongside.
// ============================================================================

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const findings = [];
const netLog = [];
const consoleLog = [];

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
  const u = r.url();
  if (r.status() >= 500) {
    add('HIGH', page.url(), '5xx response', `${r.status()} ${u}`);
  }
  if (/\/api\//.test(u)) {
    netLog.push({ method: r.request().method(), url: u, status: r.status() });
  }
});
page.on('console', (m) => {
  if (m.type() === 'error') {
    const txt = m.text();
    if (/\[next-auth\]/i.test(txt)) return;
    consoleLog.push({ type: 'error', url: page.url(), text: txt });
  }
});

// Login
await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });
console.log('logged in');

// New visit
await page.goto('/visits/new');
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/02-newvisit-step1.png`, fullPage: true });

// Patient search → create new
const patientName = `Deep Hunt Patient ${Date.now().toString(36)}`;
const search = page.getByPlaceholder(/search by name or external id/i);
await search.fill(patientName);
await page.waitForTimeout(700);
await page.screenshot({ path: `${EV}/screenshots/02-newvisit-search-empty.png`, fullPage: true });

const createBtn = page.getByRole('button', { name: /create new patient/i });
const createBtnCount = await createBtn.count();
if (createBtnCount === 0) {
  add('HIGH', '/visits/new', 'no create patient button', `search '${patientName}' shows no fallback`);
} else {
  await createBtn.first().click();
  await page.waitForTimeout(500);
  // Inline create fields
  const nameInput = page.locator('input#name, input[placeholder="Jane Doe"]').first();
  await nameInput.fill(patientName);
  const dobInput = page.locator('input[type="date"]').first();
  await dobInput.fill('1980-01-01');
  await page.getByRole('button', { name: /create.*continue/i }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${EV}/screenshots/02-newvisit-step2.png`, fullPage: true });
}

// Step 2: chief complaint + text mode
const cc = page.getByLabel(/chief complaint|reason for visit/i).first();
if (await cc.isVisible().catch(() => false)) {
  await cc.fill('Lower back pain x 3 weeks');
}
const continueBtn = page.getByRole('button', { name: /continue|next/i }).first();
await continueBtn.click().catch(() => {});
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/02-newvisit-step3.png`, fullPage: true });

// Mode picker — pick text
const textTile = page.getByRole('button', { name: /text|note|paste/i }).first();
if (await textTile.isVisible().catch(() => false)) {
  await textTile.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${EV}/screenshots/02-newvisit-text-input.png`, fullPage: true });
}

// Find textarea + submit
const textArea = page.locator('textarea').first();
if (await textArea.isVisible().catch(() => false)) {
  const shorthand = `Pt c/o low back pain x 3 wks, no radiation. PMH HTN. Started ibu 400mg TID. F/u 2 wks if no improvement.`;
  await textArea.fill(shorthand);
  await page.screenshot({ path: `${EV}/screenshots/02-newvisit-text-filled.png`, fullPage: true });
  // Submit
  await page
    .getByRole('button', { name: /submit|generate|create.*visit|process/i })
    .first()
    .click()
    .catch(() => {});
}

// Wait for landing on a visit page and capture the id
await page.waitForURL(/\/visits\/[a-z0-9]{20,}/, { timeout: 30000 }).catch(() => {});
const landed = page.url();
const m = landed.match(/\/visits\/(c[a-z0-9]{20,})/);
const visitId = m?.[1];
if (!visitId) {
  add('HIGH', '/visits/new', 'did not land on visit page', `landed on ${landed}`);
} else {
  console.log(`landed on visit ${visitId}`);
  fs.writeFileSync(`${EV}/logs/02-text-visit-id.txt`, visitId);
}
await page.screenshot({ path: `${EV}/screenshots/02-postsubmit.png`, fullPage: true });

// Watch transitions for ~90s
console.log('watching transitions...');
const transitions = [];
let lastStatus = null;
const start = Date.now();
while (Date.now() - start < 120_000) {
  const body = await page.locator('body').innerText().catch(() => '');
  const banners = await page
    .locator('[role="status"], [role="alert"], .processing, .uploading')
    .allTextContents()
    .catch(() => []);
  // Heuristic: pull words like "uploading" / "processing" / "ready" / "failed" out of visible text
  const m2 = body.match(/(uploading|queued|processing|drafting|polishing|ready|signed|failed)/i);
  const cur = m2?.[1]?.toLowerCase() ?? null;
  if (cur && cur !== lastStatus) {
    transitions.push({ at: Math.round((Date.now() - start) / 1000), status: cur });
    console.log(`  +${Math.round((Date.now() - start) / 1000)}s :: ${cur}`);
    lastStatus = cur;
    await page.screenshot({
      path: `${EV}/screenshots/02-state-${transitions.length}-${cur}.png`,
      fullPage: true,
    });
  }
  if (cur === 'ready' || cur === 'failed') break;
  await page.waitForTimeout(2000);
}
console.log('transitions:', JSON.stringify(transitions));
fs.writeFileSync(`${EV}/logs/02-transitions.json`, JSON.stringify(transitions, null, 2));

if (lastStatus !== 'ready') {
  add('HIGH', `/visits/${visitId}`, 'did not reach READY in 120s', `final status: ${lastStatus}`);
}

// Save logs
fs.writeFileSync(
  `${EV}/logs/02-findings.json`,
  JSON.stringify({ findings, netLog: netLog.slice(-100), consoleLog }, null, 2)
);
console.log(`\n${findings.length} findings, ${netLog.length} api calls, ${consoleLog.length} console errors`);

await browser.close();
