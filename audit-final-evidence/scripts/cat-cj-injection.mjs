// CAT-C/J: injection, path traversal, malicious file names.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-final-evidence';
const findings = [];
function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 180)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
const page = await ctx.newPage();
await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });

// === Evil patient names — SQL/XSS/command/header injection payloads ===
// All properly-escaped patients will be cleaned up at end.
const PAYLOADS = [
  { name: "'; DROP TABLE users; --", dob: '1990-01-01', tag: 'sql-classic' },
  { name: "x' OR '1'='1", dob: '1990-01-02', tag: 'sql-or' },
  { name: '<script>window.__xss=true</script>', dob: '1990-01-03', tag: 'xss-script' },
  { name: '<img src=x onerror=window.__xss=true>', dob: '1990-01-04', tag: 'xss-img' },
  { name: '<iframe src=javascript:alert(1)>', dob: '1990-01-05', tag: 'xss-iframe' },
  { name: 'javascript:alert(1)', dob: '1990-01-06', tag: 'xss-js-uri' },
  { name: '${{7*7}}', dob: '1990-01-07', tag: 'template' },
  { name: '{{7*7}}', dob: '1990-01-08', tag: 'handlebars' },
  { name: 'A\x00B', dob: '1990-01-09', tag: 'null-byte' }, // null byte
  { name: '../../../etc/passwd', dob: '1990-01-10', tag: 'path-traversal' },
  { name: '\r\nBcc: attacker@evil.test', dob: '1990-01-11', tag: 'crlf-email-header' },
];

const createdIds = [];
console.log('=== Patient name injection probes ===');
for (const p of PAYLOADS) {
  const r = await page.evaluate(async (body) => {
    const resp = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: body.name, dateOfBirth: body.dob }),
    });
    return { status: resp.status, body: (await resp.text()).slice(0, 200) };
  }, p);
  const m = r.body.match(/"id":"(c[a-z0-9]+)"/);
  if (m) createdIds.push({ id: m[1], tag: p.tag, name: p.name });
  const reflected = /__xss=true/.test(r.body) || /<script/.test(r.body);
  add(
    reflected ? 'HIGH' : 'INFO',
    '/api/patients create',
    `${p.tag} → ${r.status}`,
    reflected ? 'payload reflected unescaped in response!' : ''
  );
}

// === Load /patients and check for XSS execution ===
console.log('\n=== /patients rendering check ===');
let xssFlagFired = false;
page.on('dialog', async (d) => {
  xssFlagFired = true;
  console.log('!! DIALOG:', d.type(), d.message());
  await d.dismiss();
});
await page.evaluate(() => { window.__xss = undefined; });
await page.goto('/patients', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const xssFromImg = await page.evaluate(() => window.__xss === true);
add(xssFromImg || xssFlagFired ? 'CRITICAL' : 'INFO', '/patients', 'XSS execution on render', `img_set=${xssFromImg}, dialog=${xssFlagFired}`);

// Check HTML for unescaped payloads
const html = await page.content();
const rawScript = html.includes('<script>window.__xss=true</script>');
const rawIframe = html.includes('<iframe src=javascript:alert(1)>');
add(rawScript ? 'CRITICAL' : 'INFO', '/patients', 'raw <script> in HTML', String(rawScript));
add(rawIframe ? 'CRITICAL' : 'INFO', '/patients', 'raw <iframe> in HTML', String(rawIframe));

// === Filename / X-TM-Filename injection on upload route ===
console.log('\n=== Upload filename probes ===');
// Need a QUEUED audio_upload visit. Create one.
const createVisitPatient = createdIds[0] ?? { id: null };
// Skip if no safe patient id available; just use any real patient
const patientsList = await page.evaluate(async () => {
  const r = await fetch('/api/patients');
  return (await r.json()).patients ?? [];
});
const safePatient = patientsList.find((p) => /Deep Hunt|qa-/.test(p.name)) ?? patientsList[0];
if (safePatient) {
  // Create a QUEUED audio_upload visit
  const fd = new FormData();
  fd.append('patientId', safePatient.id);
  fd.append('specialty', 'family_medicine');
  fd.append('inputMode', 'audio_upload');
  // We can't POST to the server action without the Next-Action header.
  // Instead use a raw SQL or bypass via… actually simplest: use existing code path.
  // Skip — the upload route auth-gates + checks audioKey null anyway. Test the
  // endpoint on an invalid visit id so we just see the status-200 / 4xx behavior.
}

// Without a safe way to create an audio_upload visit without mutating real data,
// probe the upload endpoint with a bogus-visit-id and nasty X-TM-Filename values.
// The 404 happens BEFORE the filename is used, so we can't test the filename's
// effect on MinIO keying this way. Fall through.

// === SSRF: Forgot-password with malicious email domain ===
console.log('\n=== CRLF / SSRF probes ===');
const crlfEmail = await page.evaluate(async () => {
  const r = await fetch('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'test@evil\r\nBcc:extra@evil.test' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
});
add('INFO', '/api/auth/forgot-password CRLF', `status ${crlfEmail.status}`, crlfEmail.body);

// === Cleanup: delete test patients created ===
console.log('\n=== Cleanup ===');
for (const p of createdIds) {
  const r = await page.evaluate(async (id) => {
    const resp = await fetch(`/api/patients/${id}`, { method: 'DELETE' });
    return resp.status;
  }, p.id);
  console.log(`  deleted ${p.tag} → ${r}`);
}

fs.writeFileSync(`${EV}/logs/cat-cj-findings.json`, JSON.stringify({ findings, createdIds }, null, 2));
console.log(`\n${findings.length} findings`);
await browser.close();
