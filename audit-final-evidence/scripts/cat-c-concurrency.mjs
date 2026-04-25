// CAT-C: concurrent edits — two-tab SOAP-save race + sign-vs-edit.
// Uses the existing READY QA visit cmodivx6o000201mqi5whp7d5.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-final-evidence';
const VID = 'cmodivx6o000201mqi5whp7d5';
const findings = [];
function add(sev, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity: sev, area, title, detail });
  console.log(`  [${sev}] ${area}: ${title} :: ${detail.slice(0, 180)}`);
}

const browser = await chromium.launch();
// Two contexts = two tabs in two different sessions (could also be same session with two pages)
const c1 = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
const p1 = await c1.newPage();

await p1.goto('/login');
await p1.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await p1.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await p1.getByRole('button', { name: /sign in/i }).click();
await p1.waitForURL(/\/dashboard/, { timeout: 15000 });
// Copy cookies to a second context so both have the same session
const cookies = await c1.cookies();
const c2 = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
await c2.addCookies(cookies);
const p2 = await c2.newPage();

// Load the same visit in both tabs
await Promise.all([
  p1.goto(`/visits/${VID}`, { waitUntil: 'networkidle' }),
  p2.goto(`/visits/${VID}`, { waitUntil: 'networkidle' }),
]);
await p1.waitForTimeout(800);
console.log('both tabs loaded');

// Trigger the click-to-edit mode on both tabs
async function enterEdit(p) {
  const btn = p.locator('button:has-text("Click to edit"), button[class*="cursor-text"]').first();
  if (await btn.isVisible().catch(() => false)) await btn.click();
  await p.waitForTimeout(400);
}
await enterEdit(p1);
await enterEdit(p2);

// Both tabs now in edit mode — fire simultaneous fills + saves with different markers
const MARK_A = `\n\n[CONCURRENT_A_${Date.now()}]`;
const MARK_B = `\n\n[CONCURRENT_B_${Date.now()}]`;
async function fillAndSave(p, marker) {
  const ta = p.locator('textarea[aria-label="Edit SOAP note"]').first();
  if (!(await ta.isVisible().catch(() => false))) return null;
  const orig = (await ta.inputValue()) ?? '';
  await ta.fill(orig + marker);
  const saveBtn = p.getByRole('button', { name: /save edits/i }).first();
  if (!(await saveBtn.isVisible().catch(() => false))) return null;
  await saveBtn.click();
  return marker;
}

const [resA, resB] = await Promise.all([
  fillAndSave(p1, MARK_A),
  fillAndSave(p2, MARK_B),
]);
await p1.waitForTimeout(2500);
await p2.waitForTimeout(2500);

// Reload p1 and check which marker(s) survived
await p1.reload({ waitUntil: 'networkidle' });
await p1.waitForTimeout(800);
const after = await p1.locator('main').first().innerText().catch(() => '');
const hasA = after.includes(MARK_A);
const hasB = after.includes(MARK_B);

if (!hasA && !hasB) {
  add('HIGH', `/visits/${VID}`, 'concurrent save: both edits LOST', 'neither marker persisted');
} else if (hasA && hasB) {
  add('INFO', `/visits/${VID}`, 'concurrent save: both markers persisted (possible)', 'unlikely unless sequential');
} else {
  const winner = hasA ? 'A' : 'B';
  add('MEDIUM', `/visits/${VID}`, `concurrent save: silent last-write-wins, ${winner} won`, 'no optimistic-locking → the losing tab\'s edits dropped without warning');
}

await p1.screenshot({ path: `${EV}/screenshots/cat-c-conc-p1-after.png`, fullPage: true });

fs.writeFileSync(`${EV}/logs/cat-c-findings.json`, JSON.stringify(findings, null, 2));
console.log(`\n${findings.length} findings`);
await browser.close();
