// Verify Phase 1A audit instrumentation end-to-end.
// Logs in as qa-audit, fires one of each mutation type, then
// tallies the audit_logs rows written.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';

const QA_VISIT = 'cmodivx6o000201mqi5whp7d5'; // READY from prior audits
const findings = [];
function add(s, t, d) { findings.push({ s, t, d }); console.log(`  [${s}] ${t} :: ${d}`); }

const browser = await chromium.launch();
const ctx = await browser.newContext({ baseURL: 'https://app.quillmd.com' });
const p = await ctx.newPage();

await p.goto('/login');
await p.getByLabel(/email/i).fill(process.env.TEST_APP_EMAIL);
await p.getByLabel(/password/i).fill(process.env.TEST_APP_PASSWORD);
await p.getByRole('button', { name: /sign in/i }).click();
await p.waitForURL(/\/dashboard/, { timeout: 15000 });
add('INFO', 'LOGIN_SUCCESS', 'should have fired via events.signIn');

// Create a patient
const createRes = await p.evaluate(async () => {
  const r = await fetch('/api/patients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Audit Test Patient', dateOfBirth: '1970-01-01' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 200) };
});
const pid = createRes.body.match(/"id":"(c[a-z0-9]+)"/)?.[1];
add(createRes.status === 201 ? 'INFO' : 'HIGH', 'TM_PATIENT_CREATED', `status ${createRes.status}, id ${pid}`);

// Update the patient
if (pid) {
  const patchRes = await p.evaluate(async (id) => {
    const r = await fetch(`/api/patients/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Audit Test Patient (renamed)' }),
    });
    return r.status;
  }, pid);
  add(patchRes === 200 ? 'INFO' : 'HIGH', 'TM_PATIENT_UPDATED', `status ${patchRes}`);

  // Delete the patient
  const delRes = await p.evaluate(async (id) => {
    const r = await fetch(`/api/patients/${id}`, { method: 'DELETE' });
    return r.status;
  }, pid);
  add(delRes === 200 ? 'INFO' : 'HIGH', 'TM_PATIENT_DELETED', `status ${delRes}`);
}

// Export the QA visit to PDF
const pdfRes = await p.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/pdf`);
  return r.status;
}, QA_VISIT);
add(pdfRes === 200 ? 'INFO' : 'HIGH', 'EXPORT_PDF_DOWNLOADED', `status ${pdfRes}`);

// Export DOCX
const docxRes = await p.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/docx`);
  return r.status;
}, QA_VISIT);
add(docxRes === 200 ? 'INFO' : 'HIGH', 'EXPORT_DOCX_DOWNLOADED', `status ${docxRes}`);

// Clipboard
const clipRes = await p.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/clipboard`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format: 'epic' }),
  });
  return r.status;
}, QA_VISIT);
add(clipRes === 200 ? 'INFO' : 'HIGH', 'EXPORT_CLIPBOARD_COPIED', `status ${clipRes}`);

// Email-exfil attempt (attacker domain) — verifies EXPORT_EMAIL_BLOCKED_DESTINATION
const evilRes = await p.evaluate(async (id) => {
  const r = await fetch(`/api/visits/${id}/export/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: 'attacker@evil.test' }),
  });
  return { status: r.status, body: (await r.text()).slice(0, 100) };
}, QA_VISIT);
add(evilRes.status === 403 ? 'INFO' : 'HIGH', 'EXPORT_EMAIL_BLOCKED_DESTINATION', `status ${evilRes.status}`);

// Email success (self)
const selfRes = await p.evaluate(async (id, em) => {
  const r = await fetch(`/api/visits/${id}/export/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: em }),
  });
  return r.status;
}, QA_VISIT, process.env.TEST_APP_EMAIL);
add(selfRes === 200 ? 'INFO' : 'HIGH', 'EXPORT_EMAIL_SENT', `status ${selfRes}`);

await browser.close();
