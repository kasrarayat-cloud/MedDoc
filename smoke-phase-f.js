// Phase F — multi-patient navigation (steps 33-37).
// Validates: dashboard list, patient detail, search, multi-patient context-switching.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'F';
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(20000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 33 — dashboard with multiple patients
  await record(PHASE, '33-dashboard-multi-patient', async () => {
    await page.goto(`${URL}/dashboard`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '33a-dashboard'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-F', 'dashboard-snapshot.txt'),
      bodyText.slice(0, 1500),
    );
  });

  // Step 34 — patients list
  await record(PHASE, '34-patients-list', async () => {
    await page.goto(`${URL}/patients`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '34a-patients-list'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    const hasSmokePatient = /smoke testpatient|smoke pastetext|smoke dictation/i.test(bodyText);
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-F', 'patients-snapshot.json'),
      JSON.stringify({ hasSmokePatient, bodyChars: bodyText.length }, null, 2),
    );
  });

  // Step 35 — search
  await record(PHASE, '35-search', async () => {
    // Global search via Cmd+K equivalent? Or top search bar.
    const searchInput = page.locator('input[placeholder*="search" i], input[type="search"]').first();
    if (await searchInput.count() === 0) {
      // Try keyboard shortcut
      await page.keyboard.press('Meta+K').catch(() => page.keyboard.press('Control+K'));
      await page.waitForTimeout(1000);
      await page.screenshot({ path: shotPath(PHASE, '35a-search-shortcut'), fullPage: true });
      const dialog = page.locator('[role="dialog"], [role="combobox"]').first();
      if (await dialog.count() > 0) {
        await page.keyboard.type('smoke');
        await page.waitForTimeout(1500);
        await page.screenshot({ path: shotPath(PHASE, '35b-search-results'), fullPage: true });
      }
    } else {
      await searchInput.fill('smoke');
      await page.waitForTimeout(1500);
      await page.screenshot({ path: shotPath(PHASE, '35b-search-results'), fullPage: true });
    }
  });

  // Step 36 — patient detail
  await record(PHASE, '36-patient-detail', async () => {
    const visitB = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));
    if (!visitB.patientId) {
      fs.writeFileSync(
        path.join(SMOKE_DIR, 'phase-F', 'finding-36.json'),
        JSON.stringify({ skip: 'no Phase B patient available' }),
      );
      return;
    }
    await page.goto(`${URL}/patients/${visitB.patientId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '36a-patient-detail'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-F', 'patient-detail.json'),
      JSON.stringify({
        patientId: visitB.patientId,
        showsVisitHistory: /visit|encounter|history/i.test(bodyText),
        bodyChars: bodyText.length,
      }, null, 2),
    );
  });

  // Step 37 — visits list / index
  await record(PHASE, '37-visits-list', async () => {
    await page.goto(`${URL}/visits`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '37a-visits-list'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-F', 'visits-list-snapshot.json'),
      JSON.stringify({
        hasSmokeVisit: /smoke testpatient|chest pain/i.test(bodyText),
        bodyChars: bodyText.length,
      }, null, 2),
    );
  });

  await browser.close();
})().catch((e) => {
  console.error('phase F FAIL:', e.stack || e.message);
  process.exit(1);
});
