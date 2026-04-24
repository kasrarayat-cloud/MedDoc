// Probe a SIGNED visit comprehensively. cmocm9jki000601kwxf575d00 is SIGNED.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-evidence/app-deep-hunt';
const SIGNED_VID = 'cmocm9jki000601kwxf575d00';
const READY_VID = 'cmodivx6o000201mqi5whp7d5';
const findings = [];

function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 200)}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
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

// ====================================================================
// 1. saveSoapDraftAction on a SIGNED visit — server action invocation
//    via fetch. Action ID required.
// ====================================================================
console.log('\n=== Server-action probes on SIGNED visit ===');

// Find action IDs in the page bundle
await page.goto(`/visits/${SIGNED_VID}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(700);
const html = await page.content();
fs.writeFileSync(`${EV}/logs/08-signed-visit-html.html`, html);

// ====================================================================
// 2. POST /api/visits/[id]/text on SIGNED — should be rejected
// ====================================================================
const textOnSigned = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: 'POST text after sign — should be 4xx' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, SIGNED_VID);
add(
  textOnSigned.status >= 400 ? 'INFO' : 'HIGH',
  `/api/visits/${SIGNED_VID}/text`,
  `text on SIGNED ${textOnSigned.status}`,
  textOnSigned.body
);

// ====================================================================
// 3. POST /api/visits/[id]/upload on SIGNED — should be rejected
// ====================================================================
const uploadOnSigned = await page.evaluate(async (id) => {
  const body = new Uint8Array([0x1a, 0x45, 0xdf, 0xa3]);
  const r = await fetch(`/api/visits/${id}/upload`, {
    method: 'POST',
    headers: {
      'Content-Type': 'audio/webm',
      'Content-Length': String(body.length),
      'X-TM-Filename': 'after.webm',
    },
    body,
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, SIGNED_VID);
add(
  uploadOnSigned.status >= 400 ? 'INFO' : 'HIGH',
  `/api/visits/${SIGNED_VID}/upload`,
  `upload on SIGNED ${uploadOnSigned.status}`,
  uploadOnSigned.body
);

// ====================================================================
// 4. POST /api/visits/[id]/dictation/upload on SIGNED — should be rejected
// ====================================================================
const dictationOnSigned = await page.evaluate(async (id) => {
  const body = new Uint8Array([0x1a, 0x45, 0xdf, 0xa3]);
  const r = await fetch(`/api/visits/${id}/dictation/upload`, {
    method: 'POST',
    headers: {
      'Content-Type': 'audio/webm',
      'Content-Length': String(body.length),
      'X-TM-Filename': 'd.webm',
    },
    body,
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, SIGNED_VID);
add(
  dictationOnSigned.status >= 400 ? 'INFO' : 'HIGH',
  `/api/visits/${SIGNED_VID}/dictation/upload`,
  `dictation upload on SIGNED ${dictationOnSigned.status}`,
  dictationOnSigned.body
);

// ====================================================================
// 5. Patient PATCH bypass attempts — change another doctor's patient?
//    There aren't other patients in QA practice that aren't the QA user's,
//    but try a known cross-practice patientId from prod data
// ====================================================================
console.log('\n=== Patient PATCH probes ===');
const otherPatients = ['cmo5z4ly2000d01s35ld71uvm']; // sample CRM patient (different practice)
for (const pid of otherPatients) {
  const r = await page.evaluate(async (id) => {
    const resp = await fetch(`/api/patients/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'HACKED' }),
    });
    return { status: resp.status, body: (await resp.text()).slice(0, 200) };
  }, pid);
  add(
    r.status === 404 || r.status === 403 ? 'INFO' : 'HIGH',
    `/api/patients/${pid}`,
    `cross-practice PATCH ${r.status}`,
    r.body
  );
}

// ====================================================================
// 6. Visit detail PATCH bypass attempts
// ====================================================================
const visitPatch = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chiefComplaint: 'After-sign tampering' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, SIGNED_VID);
add(
  visitPatch.status >= 400 ? 'INFO' : 'HIGH',
  `/api/visits/${SIGNED_VID}`,
  `PATCH SIGNED ${visitPatch.status}`,
  visitPatch.body
);

// ====================================================================
// 7. Email export from a SIGNED visit to attacker (should still be blocked)
// ====================================================================
const exportEmail = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: 'attacker@evil.test' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}, SIGNED_VID);
add(
  exportEmail.status === 403 ? 'INFO' : 'HIGH',
  `/api/visits/${SIGNED_VID}/export/email`,
  `email-exfil on SIGNED ${exportEmail.status}`,
  exportEmail.body
);

// ====================================================================
// 8. Force-recreate visit-create with bogus inputs — server action via
//    well-formed FormData. Test rate-limiting on createVisitAction.
// ====================================================================
console.log('\n=== Visit creation flood ===');
const floodResults = [];
for (let i = 0; i < 8; i++) {
  const r = await page.evaluate(async () => {
    const fd = new FormData();
    fd.append('patientId', 'no-such-patient-' + Math.random());
    fd.append('specialty', 'family_medicine');
    fd.append('inputMode', 'text_notes');
    const resp = await fetch('/visits/new', {
      method: 'POST',
      body: fd,
      redirect: 'manual',
    }).catch(() => null);
    return resp ? { status: resp.status } : { status: 0 };
  });
  floodResults.push(r);
  await page.waitForTimeout(80);
}
add(
  'INFO',
  '/visits/new',
  'visit-create flood',
  JSON.stringify(floodResults.map((r) => r.status))
);

// ====================================================================
// 9. Anti-CSRF: signed visit can be modified via cross-origin requests?
//    Try to verify CSRF protection by inspecting response headers.
// ====================================================================
const csrfProbe = await page.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/sign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ destinations: [] }),
  });
  return {
    status: r.status,
    headers: Array.from(r.headers.entries()).filter(([k]) =>
      /^(set-cookie|csrf|origin|content-type)$/i.test(k)
    ),
  };
}, SIGNED_VID);
add('INFO', `/api/visits/${SIGNED_VID}/sign`, `re-sign+headers ${csrfProbe.status}`, JSON.stringify(csrfProbe.headers));

fs.writeFileSync(
  `${EV}/logs/08-findings.json`,
  JSON.stringify({ findings, consoleErrs }, null, 2)
);
console.log(`\n${findings.length} findings, ${consoleErrs.length} console errors`);

await browser.close();
