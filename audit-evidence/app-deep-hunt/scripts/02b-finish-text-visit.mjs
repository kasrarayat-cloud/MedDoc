// Continue the text visit from cmodivx6o000201mqi5whp7d5 by submitting
// the TextComposer, then watch transitions through to READY.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const VID = 'cmodivx6o000201mqi5whp7d5';
const findings = [];
const consoleLog = [];

function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 200)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
const page = await ctx.newPage();

page.on('pageerror', (e) =>
  add('HIGH', page.url(), 'page error', e.message.slice(0, 300))
);
page.on('console', (m) => {
  if (m.type() === 'error') {
    const txt = m.text();
    if (/\[next-auth\]/i.test(txt)) return;
    consoleLog.push({ url: page.url(), text: txt });
  }
});
page.on('response', (r) => {
  if (r.status() >= 500) {
    add('HIGH', page.url(), '5xx response', `${r.status()} ${r.url()}`);
  }
});

await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });
console.log('logged in');

// Navigate to the queued visit — the TextComposer should render there
await page.goto(`/visits/${VID}`, { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForTimeout(800);
await page.screenshot({ path: `${EV}/screenshots/02b-composer-loaded.png`, fullPage: true });

const textArea = page.locator('textarea').first();
if (!(await textArea.isVisible().catch(() => false))) {
  add('HIGH', `/visits/${VID}`, 'text composer not visible', 'no <textarea> found on QUEUED visit page');
} else {
  const shorthand = `Pt c/o low back pain x 3 wks, no radiation. PMH HTN. BP 138/86. Started ibu 400mg TID. F/u 2 wks if no improvement.`;
  await textArea.fill(shorthand);
  await page.screenshot({ path: `${EV}/screenshots/02b-composer-filled.png`, fullPage: true });

  // Submit
  const submitBtn = page
    .getByRole('button', { name: /expand|generate|submit|continue|create/i })
    .first();
  if (!(await submitBtn.isVisible().catch(() => false))) {
    add('HIGH', `/visits/${VID}`, 'no submit button', 'composer has no obvious submit');
  } else {
    await submitBtn.click();
    console.log('submitted text');
  }
}

// Watch transitions for up to 180s
const transitions = [];
let lastStatus = null;
const start = Date.now();
let iteration = 0;
while (Date.now() - start < 180_000) {
  iteration++;
  const body = await page.locator('body').innerText().catch(() => '');
  const m = body.match(
    /(uploading|queued|processing|drafting|polishing|ready|signed|failed)/i
  );
  const cur = m?.[1]?.toLowerCase() ?? null;
  if (cur && cur !== lastStatus) {
    transitions.push({ at: Math.round((Date.now() - start) / 1000), status: cur });
    console.log(`  +${Math.round((Date.now() - start) / 1000)}s :: ${cur}`);
    lastStatus = cur;
    await page
      .screenshot({
        path: `${EV}/screenshots/02b-state-${transitions.length}-${cur}.png`,
        fullPage: true,
      })
      .catch(() => {});
  }
  if (cur === 'ready' || cur === 'failed') break;
  await page.waitForTimeout(2500);
}

fs.writeFileSync(
  `${EV}/logs/02b-transitions.json`,
  JSON.stringify(transitions, null, 2)
);
fs.writeFileSync(
  `${EV}/logs/02b-findings.json`,
  JSON.stringify({ findings, consoleLog }, null, 2)
);
console.log(`\n${findings.length} findings, ${consoleLog.length} console errors`);
console.log('final status:', lastStatus);

await browser.close();
