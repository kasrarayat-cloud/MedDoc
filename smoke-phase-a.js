// Phase A — onboarding (steps 1-6). Marketing → signup → dashboard → settings.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  MARKETING,
  EMAIL,
  PASSWORD,
  NAME,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'A';
const TIMINGS = [];

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);

  // Step 1 — land on marketing
  await record(PHASE, '01-marketing-land', async () => {
    const t0 = Date.now();
    const resp = await page.goto(MARKETING, { waitUntil: 'networkidle' });
    if (!resp.ok()) throw new Error(`marketing returned ${resp.status()}`);
    await page.screenshot({ path: shotPath(PHASE, '01-marketing'), fullPage: false });
    TIMINGS.push({ step: '01-marketing-load', ms: Date.now() - t0 });
  });

  // Step 2 — find Sign up CTA
  await record(PHASE, '02-find-signup-cta', async () => {
    // Marketing site might link directly to /signup on app subdomain.
    const links = await page.locator('a[href*="signup"], a[href*="sign-up"], a:has-text("Sign up"), a:has-text("Get started")').all();
    if (links.length === 0) throw new Error('no signup CTA found on marketing site');
    const hrefs = await Promise.all(links.slice(0, 5).map((l) => l.getAttribute('href')));
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-A', 'signup-ctas.json'),
      JSON.stringify({ count: links.length, sampleHrefs: hrefs }, null, 2),
    );
  });

  // Step 3 — go to /signup directly + fill
  await record(PHASE, '03-signup', async () => {
    const t0 = Date.now();
    await page.goto(`${URL}/signup`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: shotPath(PHASE, '03a-signup-form'), fullPage: false });

    await page.fill('input[name="name"]', NAME);
    await page.fill('input[name="email"]', EMAIL);
    await page.fill('input[name="password"]', PASSWORD);
    await page.fill('input[name="confirmPassword"]', PASSWORD);
    await page.locator('input[name="acceptTerms"]').check();
    await page.screenshot({ path: shotPath(PHASE, '03b-signup-filled'), fullPage: false });

    await page.getByRole('button', { name: /create account/i }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 25000 });
    TIMINGS.push({ step: '03-signup-to-dashboard', ms: Date.now() - t0 });
    await page.screenshot({ path: shotPath(PHASE, '03c-dashboard-empty'), fullPage: true });
  });

  // Step 4 — dashboard empty-state
  await record(PHASE, '04-dashboard-empty-state', async () => {
    // A fresh user has 0 patients + 0 visits.
    const text = await page.locator('body').innerText();
    const hasEmpty = /no (patient|visit)|get started|first|haven't/i.test(text);
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-A', 'dashboard-empty-state.txt'),
      `hasEmptyStateText=${hasEmpty}\n\nFull body text (first 800 chars):\n${text.slice(0, 800)}`,
    );
  });

  // Step 5 — settings fill
  await record(PHASE, '05-settings-fill', async () => {
    await page.goto(`${URL}/settings`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: shotPath(PHASE, '05a-settings-blank'), fullPage: true });

    // Profile form fields
    await page.locator('input[name="name"]').fill('Dr. Smoke Tester MD');
    await page.locator('select[name="specialty"]').selectOption('cardiology');
    await page.locator('input[name="npi"]').fill('1234567890');
    await page.locator('input[name="clinicName"]').fill('Smoke Test Cardiology Clinic');
    await page.locator('input[name="timeZone"]').fill('America/Los_Angeles');
    await page.screenshot({ path: shotPath(PHASE, '05b-settings-filled'), fullPage: true });

    await page.getByRole('button', { name: /save profile/i }).click();
    // Wait for "Saved" indicator OR toast.
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '05c-settings-saved'), fullPage: true });
  });

  // Step 6 — verify settings persisted by reloading page
  await record(PHASE, '06-settings-persist', async () => {
    await page.reload({ waitUntil: 'networkidle' });
    const name = await page.locator('input[name="name"]').inputValue();
    const specialty = await page.locator('select[name="specialty"]').inputValue();
    const npi = await page.locator('input[name="npi"]').inputValue();
    const clinic = await page.locator('input[name="clinicName"]').inputValue();
    const tz = await page.locator('input[name="timeZone"]').inputValue();
    const persisted = {
      name, specialty, npi, clinicName: clinic, timeZone: tz,
    };
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-A', 'settings-persisted.json'),
      JSON.stringify(persisted, null, 2),
    );
    if (specialty !== 'cardiology' || npi !== '1234567890') {
      throw new Error(`settings did not persist correctly: ${JSON.stringify(persisted)}`);
    }
  });

  // Save the session storage so subsequent phases don't need to re-signup.
  const storagePath = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
  await ctx.storageState({ path: storagePath });
  console.log(`[A] session saved to ${storagePath}`);

  fs.writeFileSync(
    path.join(SMOKE_DIR, 'phase-A', 'timings.json'),
    JSON.stringify({ phase: PHASE, email: EMAIL, timings: TIMINGS }, null, 2),
  );

  await browser.close();
})().catch((e) => {
  console.error('phase A FAIL:', e.stack || e.message);
  process.exit(1);
});
