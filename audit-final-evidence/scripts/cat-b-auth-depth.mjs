// CAT-B: IDOR + cross-tenant + session-tampering probes.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-final-evidence';
const APP = 'https://app.quillmd.com';
const PRO = 'https://pro.quillmd.com';
const findings = [];

function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 180)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ baseURL: APP });
const page = await ctx.newPage();

// Login as qa-audit
await page.goto('/login');
await page.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await page.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL(/\/dashboard/, { timeout: 15000 });
console.log('logged in as', process.env.TEST_APP_EMAIL);

// Get the session cookie for tampering probes
const cookies = await ctx.cookies();
const sessionCookie = cookies.find((c) => c.name.includes('session-token'));
console.log('session cookie:', sessionCookie?.name, 'length:', sessionCookie?.value?.length);

// === IDOR probes: other practices' visits ===
// These are known prod visits owned by kasra (cmo5ye2nm000c...) — NOT our QA user.
const OTHER_USER_VISIT_IDS = [
  'cmocbiexg000001p24z0a6jyt', // kasra's
  'cmo8asvl4000001mu0pgives2',
  'cmo61e0os000001qlh5w5mdhh',
  'cmo8tfejv000301mtnxkx640p',
];
const OTHER_PATIENT_IDS_IN_OTHER_PRACTICE = [
  // CRM patients from a different practice
  'cmo5z4ly2000d01s35ld71uvm',
];

console.log('\n=== IDOR visit-access probes ===');
for (const vid of OTHER_USER_VISIT_IDS) {
  for (const path of [
    `/api/visits/${vid}`,
    `/api/visits/${vid}/status`,
    `/api/visits/${vid}/progress`,
    `/api/visits/${vid}/export/pdf`,
    `/api/visits/${vid}/export/docx`,
    `/api/visits/${vid}/dictation/audio`,
  ]) {
    const r = await page.evaluate(async (p) => {
      const resp = await fetch(p);
      return { status: resp.status, size: (await resp.blob().catch(() => ({ size: 0 }))).size ?? 0 };
    }, path);
    if (r.status === 200) {
      add('CRITICAL', path, 'IDOR — 200 on another user\'s visit', JSON.stringify(r));
    } else if (r.status !== 404 && r.status !== 403 && r.status !== 405) {
      add('MEDIUM', path, `unexpected ${r.status} on foreign visit`, '');
    }
  }
}

// Mutating endpoints — try to sign / delete someone else's visit
for (const vid of OTHER_USER_VISIT_IDS.slice(0, 1)) {
  for (const action of ['sign', 'delete', 'archive', 'restore', 'retry', 'text']) {
    const r = await page.evaluate(async ({ p, m }) => {
      const resp = await fetch(p, { method: m, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      return { status: resp.status, body: (await resp.text()).slice(0, 100) };
    }, { p: `/api/visits/${vid}/${action}`, m: 'POST' });
    if (r.status >= 200 && r.status < 300) {
      add('CRITICAL', `/api/visits/${vid}/${action}`, `IDOR MUTATION success on foreign visit`, r.body);
    } else if (r.status !== 404 && r.status !== 403 && r.status !== 400 && r.status !== 405) {
      add('MEDIUM', `/api/visits/${vid}/${action}`, `unexpected ${r.status}`, r.body);
    }
  }
}

// === PATCH another practice's patient ===
console.log('\n=== IDOR patient-mutate probes ===');
for (const pid of OTHER_PATIENT_IDS_IN_OTHER_PRACTICE) {
  for (const method of ['PATCH', 'DELETE', 'GET']) {
    const r = await page.evaluate(async ({ p, m }) => {
      const resp = await fetch(p, {
        method: m,
        headers: { 'Content-Type': 'application/json' },
        body: m === 'GET' ? undefined : JSON.stringify({ name: 'HACK' }),
      });
      return { status: resp.status, body: (await resp.text()).slice(0, 100) };
    }, { p: `/api/patients/${pid}`, m: method });
    if (r.status >= 200 && r.status < 300 && method !== 'GET') {
      add('CRITICAL', `/api/patients/${pid}`, `IDOR ${method} on foreign patient`, r.body);
    } else if (r.status === 200 && method === 'GET') {
      add('HIGH', `/api/patients/${pid}`, `GET leaked foreign patient row`, r.body);
    }
  }
}

// === Cookie tampering — try a mangled session token ===
console.log('\n=== Cookie tampering probes ===');
if (sessionCookie) {
  // Replace session with a mangled version
  const orig = sessionCookie.value;
  const mangled = orig.slice(0, -10) + 'AAAAAAAAAA';
  await ctx.addCookies([{ ...sessionCookie, value: mangled }]);
  const mangledResp = await page.evaluate(async () => {
    const r = await fetch('/api/patients');
    return { status: r.status, body: (await r.text()).slice(0, 150) };
  });
  add(
    mangledResp.status === 401 ? 'INFO' : 'HIGH',
    '/api/patients',
    `mangled session cookie → ${mangledResp.status}`,
    mangledResp.body
  );
  // Restore
  await ctx.addCookies([{ ...sessionCookie, value: orig }]);

  // Try sending a blank session
  await ctx.addCookies([{ ...sessionCookie, value: '' }]);
  const emptyResp = await page.evaluate(async () => {
    const r = await fetch('/api/patients');
    return { status: r.status };
  });
  add(
    emptyResp.status === 401 ? 'INFO' : 'HIGH',
    '/api/patients',
    `empty session cookie → ${emptyResp.status}`,
    ''
  );
  // Restore
  await ctx.addCookies([{ ...sessionCookie, value: orig }]);
}

// === Cross-app: QA has both MEDDOC_PRO+TRANSCRIBE_MD; try to call pro.quillmd.com API ===
console.log('\n=== Cross-app session ===');
// Same cookie to pro.quillmd.com — the cookie domain is app.quillmd.com, so it shouldn't go
const prRes = await page.evaluate(async () => {
  const r = await fetch('https://pro.quillmd.com/api/health').catch((e) => ({ status: 0, e: String(e) }));
  return r.status ? { status: r.status } : r;
});
add('INFO', 'pro.quillmd.com/api/health cross-app', `status ${prRes.status}`, JSON.stringify(prRes));

// === JWT inspection: does the session-token cookie contain readable claims? ===
// NextAuth default is JWE (encrypted), not JWT signed-only. Verify.
if (sessionCookie) {
  const parts = sessionCookie.value.split('.');
  add(
    'INFO',
    'session-token shape',
    `parts=${parts.length}, length=${sessionCookie.value.length}`,
    `name=${sessionCookie.name}, first20=${sessionCookie.value.slice(0, 20)}, sameSite=${sessionCookie.sameSite}, httpOnly=${sessionCookie.httpOnly}, secure=${sessionCookie.secure}`
  );
}

fs.writeFileSync(`${EV}/logs/cat-b-findings.json`, JSON.stringify(findings, null, 2));
console.log(`\n${findings.length} findings`);
await browser.close();
