// Re-login the smoke test user to regenerate session-storage.json.
// Smoke harness's TS env should match the original signup.
const fs = require('node:fs');
const path = require('node:path');
const { newSession, URL, SMOKE_DIR } = require('./smoke-harness');

const EMAIL = 'qa-smoke-1777863896718@quillmd-test.local';
// Password derivation matches smoke-harness: `Smoke${TS}!Aa`
const PASSWORD = 'Smoke1777863896718!Aa';

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await page.goto(`${URL}/login`, { waitUntil: 'networkidle' });
  await page.fill('input[name="email"]', EMAIL);
  await page.fill('input[name="password"]', PASSWORD);
  await page.getByRole('button', { name: /sign in|log in/i }).first().click();
  await page.waitForURL(/\/dashboard/, { timeout: 25000 });
  const storagePath = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
  await ctx.storageState({ path: storagePath });
  console.log(`session re-saved to ${storagePath}`);
  await browser.close();
})().catch((e) => {
  console.error('relogin FAIL:', e.stack || e.message);
  process.exit(1);
});
