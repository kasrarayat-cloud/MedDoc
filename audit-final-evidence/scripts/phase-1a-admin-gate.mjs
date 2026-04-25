// Verify /admin gate on pro.quillmd.com.
// 1. qa-audit (SUPER_ADMIN) → sees placeholder
// 2. qa-bundle (no SUPER_ADMIN) → 404
// 3. logged-out → 404

import { chromium } from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';

const PRO = 'https://pro.quillmd.com';
const PASSWORD = 'QaTestPassword2024!';

async function login(page, email) {
  await page.goto(`${PRO}/login`);
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/(dashboard|system-admin)/, { timeout: 15000 });
}

const browser = await chromium.launch();

// 1. qa-audit — SUPER_ADMIN
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await login(p, 'qa-audit@quillmd.local');
  const resp = await p.goto(`${PRO}/admin`, { waitUntil: 'networkidle' });
  const body = (await p.locator('body').innerText()).slice(0, 400);
  console.log(`  qa-audit /admin → status ${resp?.status()}`);
  console.log(`    body preview: ${body.slice(0, 120)}`);
  console.log(`    sees placeholder: ${/Admin Dashboard/.test(body) && /Phase 1B coming soon/.test(body)}`);
  await ctx.close();
}

// 2. qa-bundle — no SUPER_ADMIN
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  await login(p, 'qa-bundle@quillmd.local');
  const resp = await p.goto(`${PRO}/admin`, { waitUntil: 'networkidle' });
  const body = (await p.locator('body').innerText()).slice(0, 400);
  console.log(`  qa-bundle /admin → status ${resp?.status()}`);
  console.log(`    body preview: ${body.slice(0, 120)}`);
  console.log(`    is 404: ${/404|not found|This page could not be found/i.test(body)}`);
  await ctx.close();
}

// 3. Logged-out
{
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  const resp = await p.goto(`${PRO}/admin`, { waitUntil: 'networkidle' });
  const body = (await p.locator('body').innerText()).slice(0, 400);
  console.log(`  logged-out /admin → status ${resp?.status()}`);
  console.log(`    body preview: ${body.slice(0, 120)}`);
  console.log(`    is 404 (not login redirect): ${/404|not found|This page could not be found/i.test(body)}`);
  await ctx.close();
}

await browser.close();
