// Phase 1B verification: hit every /api/admin/* endpoint as
// (a) SUPER_ADMIN qa-audit, (b) qa-bundle (no SUPER_ADMIN),
// (c) unauthenticated. Confirm 200/404/404.

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';

const PRO = 'https://pro.quillmd.com';
const PASS = 'QaTestPassword2024!';
const ENDPOINTS = [
  { path: '/api/admin/audit-logs', method: 'GET' },
  { path: '/api/admin/audit-logs/stats', method: 'GET' },
  { path: '/api/admin/audit-logs/timeline', method: 'GET' },
  { path: '/api/admin/system/health', method: 'GET' },
  { path: '/api/admin/system/pipeline-metrics', method: 'GET' },
  { path: '/api/admin/system/external-services', method: 'GET' },
  { path: '/api/admin/users', method: 'GET' },
  { path: '/api/admin/users/qa-audit-user-unified', method: 'GET' },
  { path: '/api/admin/threats/recent', method: 'GET' },
];

async function login(page, email) {
  await page.goto(`${PRO}/login`);
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(PASS);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/(dashboard|system-admin)/, { timeout: 15000 });
}

const browser = await chromium.launch();

console.log('=== As qa-audit (SUPER_ADMIN) — expect 200 ===');
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await login(p, 'qa-audit@quillmd.local');
  for (const e of ENDPOINTS) {
    const r = await p.evaluate(async (path) => {
      const resp = await fetch(path);
      const ct = resp.headers.get('content-type') ?? '';
      let preview = '';
      if (ct.includes('json')) {
        const j = await resp.json().catch(() => null);
        preview = JSON.stringify(j).slice(0, 100);
      } else {
        preview = (await resp.text().catch(() => '')).slice(0, 60);
      }
      return { status: resp.status, preview };
    }, e.path);
    console.log(`  ${e.method} ${e.path} → ${r.status} :: ${r.preview}`);
  }
  await ctx.close();
}

console.log('\n=== As qa-bundle (no SUPER_ADMIN) — expect 404 ===');
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await login(p, 'qa-bundle@quillmd.local');
  for (const e of ENDPOINTS) {
    const r = await p.evaluate(async (path) => {
      const resp = await fetch(path);
      return resp.status;
    }, e.path);
    console.log(`  ${e.method} ${e.path} → ${r}`);
  }
  await ctx.close();
}

console.log('\n=== Unauthenticated — expect 404 ===');
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  for (const e of ENDPOINTS) {
    const r = await p.evaluate(async (path) => {
      const resp = await fetch(path);
      return resp.status;
    }, `${PRO}${e.path}`);
    console.log(`  ${e.method} ${e.path} → ${r}`);
  }
  await ctx.close();
}

await browser.close();
