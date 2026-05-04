// Phase D — dictation mode (steps 22-27).
// Browser MediaRecorder + getUserMedia is heavily restricted under headless.
// We launched chromium with --use-fake-ui-for-media-stream + --use-fake-device-for-media-stream
// which gives a synthetic 1kHz tone source. Real dictation flow probes the
// Mic UI state machine, but we can't generate clinical content this way.
// Strategy: drive UI through Record → Stop → submit, validate that the
// pipeline accepts an empty / fake-tone audio gracefully.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'D';
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const PATIENT_NAME = `Smoke Dictation Patient ${process.env.SMOKE_TS || Date.now()}`;
const PATIENT_DOB = '1972-08-22';

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 22 — create patient + visit, pick DICTATION mode
  let visitId = null;
  // Reuse Phase B's patient to avoid /api/patients rate limit
  const { patientId } = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'patient-id.json'), 'utf8'));
  await record(PHASE, '22-start-dictation-visit', async () => {
    await page.goto(`${URL}/visits/new?patientId=${patientId}`, { waitUntil: 'networkidle' });
    await page.fill('input[name="chiefComplaint"]', 'Routine follow-up; dictation mode test');
    await page.screenshot({ path: shotPath(PHASE, '22a-form-filled'), fullPage: true });

    // The dictation capture-mode tile is labelled "Dictate live — Speak a summary into your mic."
    const dictateBtn = page.getByRole('button', { name: /dictate live/i }).first();
    if (await dictateBtn.count() === 0) {
      throw new Error('"Dictate live" capture-mode tile not found');
    }
    await dictateBtn.click();
    await page.waitForURL(/\/visits\/c[a-z0-9]{20,}/, { timeout: 25000 });
    visitId = page.url().match(/\/visits\/(c[a-z0-9]{20,})/)?.[1];
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-D', 'visit-id.json'),
      JSON.stringify({ visitId, patientId }, null, 2),
    );
    // patientId is the BORROWED constant, defined above record(); fine inside closure.
    await page.screenshot({ path: shotPath(PHASE, '22b-dictation-page'), fullPage: true });
  });

  // Step 23 — start recording. The voice-dictator component may take a moment
  // to render (Suspense boundary). Wait for the explicit "Start dictating" button.
  await record(PHASE, '23-start-recording', async () => {
    const recordBtn = page.getByRole('button', { name: /start dictating|getting mic/i });
    await recordBtn.waitFor({ state: 'visible', timeout: 20000 });
    await page.screenshot({ path: shotPath(PHASE, '23pre-button-visible'), fullPage: true });
    await recordBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '23a-recording-started'), fullPage: true });
  });

  // Step 24 — let it record for ~8s, then "Stop & process"
  await record(PHASE, '24-stop-recording', async () => {
    await page.waitForTimeout(8000);
    const stopBtn = page.getByRole('button', { name: /stop.*process|stop & process|stop and process/i }).first();
    if (await stopBtn.count() === 0) {
      fs.writeFileSync(
        path.join(SMOKE_DIR, 'phase-D', 'finding-24-no-stop-btn.json'),
        JSON.stringify({ note: 'Stop button not found; UI may rely on a different control' }),
      );
      return;
    }
    await stopBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: shotPath(PHASE, '24a-recording-stopped'), fullPage: true });
  });

  // Step 25 — submit / process the recording
  await record(PHASE, '25-submit-recording', async () => {
    const submitBtn = page.getByRole('button', { name: /upload|process|submit|transcribe|generate/i }).first();
    if (await submitBtn.count() > 0) {
      await submitBtn.click();
      await page.waitForTimeout(3000);
    }
    await page.screenshot({ path: shotPath(PHASE, '25a-submitted'), fullPage: true });
  });

  // Step 26-27 — wait briefly for pipeline; document state. Headless fake-tone
  // audio likely produces nonsense transcript — main goal is the UI state
  // transition + pipeline ingestion, not transcript quality.
  await record(PHASE, '26-27-pipeline-state', async () => {
    let lastStatus = null;
    const tStart = Date.now();
    while (Date.now() - tStart < 4 * 60 * 1000) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}`).catch(() => null);
      if (resp && resp.ok()) {
        const d = await resp.json();
        const v = d.visit ?? d;
        if (v.status !== lastStatus) {
          console.log(`  [D] visit status: ${v.status}`);
          lastStatus = v.status;
        }
        if (['READY', 'SIGNED', 'FAILED'].includes(v.status)) break;
      }
      await page.waitForTimeout(5000);
    }
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-D', 'pipeline-result.json'),
      JSON.stringify({ visitId, finalStatus: lastStatus, note: 'Headless fake-mic source produces low-quality audio; finding documents the dictation UX flow, not transcript accuracy.' }, null, 2),
    );
  });

  await browser.close();
})().catch((e) => {
  console.error('phase D FAIL:', e.stack || e.message);
  process.exit(1);
});
