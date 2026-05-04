// Phase B retry — reuse existing visit (cmoqn96fe001501l543vfe1u2),
// re-trigger upload click, verify audioKey lands, then poll pipeline.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'B';
const TIMINGS = [];
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const AUDIO = '/tmp/smoke-audio/clinical-cardiology.wav';
const { visitId } = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(45000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 11-retry — navigate back to the visit, attach file, EXPLICITLY click the button
  await record(PHASE, '11-upload-audio-retry', async () => {
    const t0 = Date.now();
    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '11r-a-visit-loaded'), fullPage: true });

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(AUDIO);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: shotPath(PHASE, '11r-b-file-attached'), fullPage: true });

    // EXPLICITLY click the Upload & transcribe button. The button has both
    // microphone icon + "Upload & transcribe" text. Wait until it's enabled.
    const uploadBtn = page.getByRole('button', { name: /upload.*transcribe/i });
    await uploadBtn.waitFor({ state: 'visible', timeout: 10000 });
    const isEnabled = await uploadBtn.isEnabled();
    console.log(`  [B-retry] Upload button enabled: ${isEnabled}`);
    if (!isEnabled) {
      await page.waitForTimeout(2000);
    }
    await uploadBtn.click();
    console.log('  [B-retry] Clicked Upload & transcribe');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: shotPath(PHASE, '11r-c-after-click'), fullPage: true });

    // Verify audioKey landed by polling API
    let audioKey = null;
    for (let i = 0; i < 12; i++) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}`);
      if (resp.ok()) {
        const d = await resp.json();
        const v = d.visit ?? d;
        audioKey = v.audioKey ?? null;
        if (audioKey) break;
      }
      await page.waitForTimeout(2000);
    }
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-B', 'upload-retry-result.json'),
      JSON.stringify({ audioKey, durationMs: Date.now() - t0 }, null, 2),
    );
    if (!audioKey) throw new Error('audioKey did not appear in DB after upload click');
    TIMINGS.push({ step: '11-upload-retry', ms: Date.now() - t0 });
  });

  // Step 12 — wait for pipeline. Inspect the actual API response shape.
  await record(PHASE, '12-pipeline-wait', async () => {
    const t0 = Date.now();
    let lastStatus = null;
    let firstResponseShape = null;
    const maxWaitMs = 8 * 60 * 1000;
    const tStart = Date.now();
    while (Date.now() - tStart < maxWaitMs) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}`).catch(() => null);
      if (resp && resp.ok()) {
        const d = await resp.json().catch(() => ({}));
        if (!firstResponseShape) {
          firstResponseShape = Object.keys(d);
          console.log(`  [B] /api/visits/${visitId} top-level keys: ${firstResponseShape.join(',')}`);
        }
        const v = d.visit ?? d;
        const status = v.status ?? null;
        if (status !== lastStatus) {
          console.log(`  [B] visit status: ${status}`);
          fs.appendFileSync(
            path.join(SMOKE_DIR, 'phase-B', 'pipeline-progress.log'),
            `${new Date().toISOString()} ${status}\n`,
          );
          lastStatus = status;
        }
        if (status === 'READY' || status === 'SIGNED') {
          TIMINGS.push({ step: '12-pipeline', ms: Date.now() - t0, finalStatus: status });
          break;
        }
        if (status === 'FAILED') {
          throw new Error(`pipeline FAILED for visit ${visitId}`);
        }
      }
      await page.waitForTimeout(5000);
    }
    if (lastStatus !== 'READY' && lastStatus !== 'SIGNED') {
      throw new Error(`pipeline did not complete in 8 min (last status: ${lastStatus})`);
    }
  });

  // Step 13-14 — verify outputs render
  await record(PHASE, '13-14-verify-outputs', async () => {
    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '13a-visit-detail'), fullPage: true });

    const bodyText = await page.locator('body').innerText();
    const checks = {
      hasSubjective: /subjective|chief complaint|HPI/i.test(bodyText),
      hasObjective: /objective|exam|vitals/i.test(bodyText),
      hasAssessment: /assessment|impression/i.test(bodyText),
      hasPlan: /plan|recommend|disposition/i.test(bodyText),
    };

    const tabs = ['Transcript', 'Codes', 'Rx', 'Extras'];
    for (const tab of tabs) {
      try {
        await page.getByRole('tab', { name: new RegExp(tab, 'i') }).click({ timeout: 3000 });
        await page.waitForTimeout(800);
        await page.screenshot({ path: shotPath(PHASE, `13b-tab-${tab.toLowerCase()}`), fullPage: true });
      } catch {
        checks[`tab_${tab}_missing`] = true;
      }
    }

    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-B', 'output-checks.json'),
      JSON.stringify(checks, null, 2),
    );
  });

  fs.writeFileSync(
    path.join(SMOKE_DIR, 'phase-B', 'timings-retry.json'),
    JSON.stringify({ phase: PHASE, visitId, timings: TIMINGS }, null, 2),
  );

  await browser.close();
})().catch((e) => {
  console.error('phase B-retry FAIL:', e.stack || e.message);
  process.exit(1);
});
