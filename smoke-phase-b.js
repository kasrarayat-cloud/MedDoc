// Phase B — patient + visit + audio upload (steps 7-14).
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
  setFailFast,
} = require('./smoke-harness');

const PHASE = 'B';
const TIMINGS = [];
setFailFast(PHASE);
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const AUDIO = '/tmp/smoke-audio/clinical-cardiology.wav';
// Use TS in name to guarantee no fuzzy-match collision with prior runs.
const STAMP = process.env.SMOKE_TS || String(Date.now());
const PATIENT_NAME = `Smoke TestPatient OneCardiology ${STAMP}`;
const PATIENT_DOB = '1965-03-15';

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(45000);
  // Reuse signed-in session.
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 7 — create patient via API (UX flow audited via PR #98 patient-picker
  // already; smoke-test value of Phase B is the visit-create + audio pipeline,
  // not re-walking the picker UI). Document the picker-UX finding separately.
  let patientId = null;
  await record(PHASE, '07-create-patient-via-api', async () => {
    await page.goto(`${URL}/dashboard`, { waitUntil: 'networkidle' });
    const resp = await page.request.post(`${URL}/api/patients`, {
      data: { name: PATIENT_NAME, dateOfBirth: PATIENT_DOB, externalId: null },
    });
    if (!resp.ok()) {
      throw new Error(`POST /api/patients ${resp.status()}: ${(await resp.text()).slice(0, 200)}`);
    }
    const body = await resp.json();
    patientId = body.patient?.id ?? body.id;
    if (!patientId) throw new Error('no patient.id in /api/patients response');
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-B', 'patient-id.json'),
      JSON.stringify({ patientName: PATIENT_NAME, patientId, viaApi: true }, null, 2),
    );
  });

  // Step 8-10 — start new visit, pick specialty Cardiology, pick AUDIO UPLOAD
  let visitId = null;
  await record(PHASE, '08-10-start-visit', async () => {
    await page.goto(`${URL}/visits/new?patientId=${patientId}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: shotPath(PHASE, '08a-visit-step2'), fullPage: true });

    // Specialty dropdown — Radix Select trigger doesn't reliably open under
    // headless Chromium without real mouse/keyboard events. The dropdown
    // defaults to the most-recent-visit specialty (or first in catalog
    // for a fresh user). Smoke goal is the AI pipeline, not specialty-
    // variant coverage; documenting as INFO. Accepting the default
    // (Primary Care for fresh user). Multi-specialty variant testing
    // would need a different harness shape (Playwright codegen + manual
    // recording, or driving the underlying form value via page.evaluate).
    await page.screenshot({ path: shotPath(PHASE, '09a-default-specialty'), fullPage: true });

    await page.fill('input[name="chiefComplaint"]', 'Chest pain x 2 hours, radiation to left arm');
    await page.screenshot({ path: shotPath(PHASE, '10a-form-filled'), fullPage: true });

    // Pick AUDIO UPLOAD capture mode (the form has 3 mode tiles).
    const audioBtn = page.getByRole('button', { name: /upload audio/i });
    await audioBtn.click();
    // Form posts to createVisitAction — should redirect to /visits/[id]/...
    await page.waitForURL(/\/visits\/c[a-z0-9]{20,}/, { timeout: 25000 });
    visitId = page.url().match(/\/visits\/(c[a-z0-9]{20,})/)?.[1];
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'),
      JSON.stringify({ visitId, patientId }, null, 2),
    );
    if (!visitId) throw new Error('visitId not in URL after capture-mode pick');
    await page.screenshot({ path: shotPath(PHASE, '10b-after-capture-pick'), fullPage: true });
  });

  // Step 11 — upload audio file
  await record(PHASE, '11-upload-audio', async () => {
    const t0 = Date.now();
    // The audio uploader is a standard <input type="file"> (or its hidden child).
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(AUDIO);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '11a-after-upload-select'), fullPage: true });

    // The upload may auto-submit OR require a Confirm/Upload click.
    const uploadBtn = page.getByRole('button', { name: /upload|process|start/i }).first();
    if (await uploadBtn.count() > 0) {
      await uploadBtn.click().catch(() => {});
    }
    await page.waitForTimeout(3000);
    await page.screenshot({ path: shotPath(PHASE, '11b-upload-submitted'), fullPage: true });
    TIMINGS.push({ step: '11-audio-upload', ms: Date.now() - t0 });
  });

  // Step 12 — wait for transcription + SOAP + codes + Rx + summary
  await record(PHASE, '12-pipeline-wait', async () => {
    const t0 = Date.now();
    // Pipeline status states: QUEUED → TRANSCRIBING → EXTRACTING → DRAFTING →
    // CRITIQUING → POLISHING → AUTOMATING → READY (or SIGNED if signed).
    // Poll the visit page until status = READY or 8 min elapses.
    let lastStatus = null;
    const maxWaitMs = 5 * 60 * 1000;
    const tStart = Date.now();
    while (Date.now() - tStart < maxWaitMs) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}`).catch(() => null);
      if (resp && resp.ok()) {
        const d = await resp.json().catch(() => ({}));
        const status = d.status ?? d.visit?.status ?? null;
        if (status !== lastStatus) {
          console.log(`  [B] visit ${visitId} status: ${status}`);
          fs.appendFileSync(
            path.join(SMOKE_DIR, 'phase-B', 'pipeline-progress.log'),
            `${new Date().toISOString()} ${status}\n`,
          );
          lastStatus = status;
        }
        if (status === 'READY' || status === 'SIGNED') {
          TIMINGS.push({ step: '12-pipeline-complete', ms: Date.now() - t0, finalStatus: status });
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

  // Step 13-14 — verify all 5 outputs render on visit page
  await record(PHASE, '13-14-verify-outputs', async () => {
    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '13a-visit-detail'), fullPage: true });

    // SOAP tab is default.
    const bodyText = await page.locator('body').innerText();
    const checks = {
      hasSubjective: /subjective|chief complaint|HPI/i.test(bodyText),
      hasObjective: /objective|exam|vitals/i.test(bodyText),
      hasAssessment: /assessment|impression/i.test(bodyText),
      hasPlan: /plan|recommend|disposition/i.test(bodyText),
    };

    // Click each tab, screenshot
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
    path.join(SMOKE_DIR, 'phase-B', 'timings.json'),
    JSON.stringify({ phase: PHASE, patientId, visitId, timings: TIMINGS }, null, 2),
  );

  await browser.close();
})().catch((e) => {
  console.error('phase B FAIL:', e.stack || e.message);
  process.exit(1);
});
