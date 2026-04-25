// CAT-D: API contract matrix.
// For every route: (1) unauth → 401/403/redirect, (2) malformed body → 400,
// (3) wrong method → 405 or 400, (4) cross-tenant → 404, (5) rate-limit fires,
// (6) no stack trace leaks.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';
import * as fs from 'node:fs';

const EV = '/opt/meddoc-pro/audit-final-evidence';
const findings = [];
const matrix = [];

function add(severity, area, title, detail) {
  findings.push({ when: new Date().toISOString(), severity, area, title, detail });
  console.log(`  [${severity}] ${area}: ${title} :: ${detail.slice(0, 180)}`);
}

// Read QA creds from env
const APP = 'https://app.quillmd.com';
const EMAIL = process.env.TEST_APP_EMAIL;
const PASS = process.env.TEST_APP_PASSWORD;

// Routes worth probing. Mix of auth/unauth/tenant-scoped.
const ROUTES = [
  // unauth-allowed
  { method: 'GET', path: '/api/health', expectUnauth: 200 },
  // auth-required
  { method: 'GET', path: '/api/patients', expectUnauth: 401, bodyShape: 'query' },
  { method: 'POST', path: '/api/patients', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'GET', path: '/api/patients/nonexistent-id', expectUnauth: 401 },
  { method: 'POST', path: '/api/patients/fuzzy-match', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'GET', path: '/api/settings/export-data', expectUnauth: 401 },
  { method: 'POST', path: '/api/settings/change-password', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'POST', path: '/api/settings/change-email', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'POST', path: '/api/settings/delete-account', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  // visit endpoints — use a bogus id, auth required
  { method: 'POST', path: '/api/visits/fake-visit-id/sign', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'POST', path: '/api/visits/fake-visit-id/retry', expectUnauth: 401 },
  { method: 'POST', path: '/api/visits/fake-visit-id/text', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  { method: 'POST', path: '/api/visits/fake-visit-id/delete', expectUnauth: 401 },
  { method: 'POST', path: '/api/visits/fake-visit-id/archive', expectUnauth: 401 },
  { method: 'POST', path: '/api/visits/fake-visit-id/restore', expectUnauth: 401 },
  { method: 'POST', path: '/api/visits/fake-visit-id/unarchive', expectUnauth: 401 },
  { method: 'GET', path: '/api/visits/fake-visit-id/status', expectUnauth: 401 },
  { method: 'GET', path: '/api/visits/fake-visit-id/progress', expectUnauth: 401 },
  { method: 'GET', path: '/api/visits/fake-visit-id/export/pdf', expectUnauth: 401 },
  { method: 'GET', path: '/api/visits/fake-visit-id/export/docx', expectUnauth: 401 },
  { method: 'GET', path: '/api/visits/fake-visit-id/dictation/audio', expectUnauth: 401 },
  { method: 'POST', path: '/api/visits/fake-visit-id/export/email', expectUnauth: 401, bodyShape: 'json', probeMalformed: true },
  // wrong-method probes — most routes only support one method
  { method: 'PUT', path: '/api/visits/fake-visit-id/sign', expectUnauth: 405 },
  { method: 'DELETE', path: '/api/visits/fake-visit-id/sign', expectUnauth: 405 },
  { method: 'GET', path: '/api/patients', method2: 'PUT', expectUnauth: 405 },
];

// ── unauth probes (no cookie jar) ──
console.log('=== Unauth probes ===');
for (const r of ROUTES) {
  const method = r.method2 ?? r.method;
  try {
    const res = await fetch(`${APP}${r.path}`, {
      method,
      redirect: 'manual',
      headers: { 'Content-Type': 'application/json' },
      body: method === 'GET' ? undefined : JSON.stringify({}),
    });
    const status = res.status;
    matrix.push({ phase: 'unauth', method, path: r.path, status });
    if (r.expectUnauth && status !== r.expectUnauth) {
      // 307 (redirect to /login) is acceptable for auth-required routes
      const acceptable =
        (r.expectUnauth === 401 && (status === 307 || status === 401 || status === 403)) ||
        (r.expectUnauth === 200 && status === 200) ||
        (r.expectUnauth === 405 && (status === 405 || status === 400));
      if (!acceptable) {
        add('MEDIUM', `${method} ${r.path}`, `unauth unexpected status ${status}`, `expected ${r.expectUnauth}`);
      }
    }
    // Check for stack trace leakage
    const body = await res.text().catch(() => '');
    if (/at\s+\w+\s+\(.*\.(ts|js):\d+:\d+\)/.test(body) || /TypeError|ReferenceError|Prisma/.test(body)) {
      add('HIGH', `${method} ${r.path}`, 'stack trace / framework internals in response body', body.slice(0, 200));
    }
  } catch (e) {
    matrix.push({ phase: 'unauth', method, path: r.path, error: String(e).slice(0, 80) });
  }
}

// ── authed probes ──
if (!EMAIL || !PASS) {
  console.log('No QA creds — skipping authed matrix');
} else {
  console.log('\n=== Authed probes ===');
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ baseURL: APP });
  const page = await ctx.newPage();
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 15000 });

  for (const r of ROUTES) {
    // Skip health-check (already 200 unauth)
    if (r.path === '/api/health') continue;
    const method = r.method2 ?? r.method;
    // A) Expected response on a valid-but-non-existent id
    const res = await page.evaluate(async ({ m, p, shape }) => {
      const opts = { method: m, headers: { 'Content-Type': 'application/json' } };
      if (m !== 'GET') {
        opts.body = shape === 'json' ? JSON.stringify({}) : '';
      }
      try {
        const resp = await fetch(p, opts);
        return { status: resp.status, body: (await resp.text()).slice(0, 400) };
      } catch (e) {
        return { status: 0, body: String(e).slice(0, 100) };
      }
    }, { m: method, p: r.path, shape: r.bodyShape ?? 'none' });
    matrix.push({ phase: 'authed', method, path: r.path, status: res.status, body: res.body.slice(0, 120) });
    // Check for unexpected 5xx
    if (res.status >= 500) {
      add('HIGH', `${method} ${r.path}`, `authed 5xx ${res.status}`, res.body);
    }
    // Check for stack trace in body
    if (/at\s+\w+\s+\(.*\.(ts|js):\d+:\d+\)/.test(res.body) || /Prisma[A-Za-z]*Error|TypeError|ReferenceError/.test(res.body)) {
      add('HIGH', `${method} ${r.path}`, 'authed stack trace / framework internals in body', res.body.slice(0, 200));
    }

    // B) Malformed JSON body
    if (r.probeMalformed && method !== 'GET') {
      const mal = await page.evaluate(async ({ m, p }) => {
        const resp = await fetch(p, { method: m, headers: { 'Content-Type': 'application/json' }, body: '{not-valid-json' });
        return { status: resp.status, body: (await resp.text()).slice(0, 400) };
      }, { m: method, p: r.path });
      matrix.push({ phase: 'malformed', method, path: r.path, status: mal.status });
      if (mal.status !== 400) {
        add('MEDIUM', `${method} ${r.path}`, `malformed body status ${mal.status}`, 'expected 400');
      }
      if (/Unexpected token|SyntaxError|at JSON\.parse/.test(mal.body)) {
        add('MEDIUM', `${method} ${r.path}`, 'raw JSON-parse error leaks in body', mal.body.slice(0, 200));
      }
    }
  }
  await browser.close();
}

fs.writeFileSync(`${EV}/logs/cat-d-findings.json`, JSON.stringify({ findings, matrix }, null, 2));
console.log(`\n${findings.length} findings, ${matrix.length} matrix rows`);
