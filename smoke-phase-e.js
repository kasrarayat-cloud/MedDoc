// Phase E — paste-text mode (steps 28-32).
// Bypasses transcription; goes Text → Understand → Draft → ... → Ready.
const fs = require('node:fs');
const path = require('node:path');
const {
  URL,
  SMOKE_DIR,
  shotPath,
  newSession,
  record,
} = require('./smoke-harness');

const PHASE = 'E';
const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const PATIENT_NAME = `Smoke PasteText Patient ${process.env.SMOKE_TS || Date.now()}`;
const PATIENT_DOB = '1958-11-30';

// 200-word HPI text suitable for SOAP draft
const PASTED_TEXT = `
SUBJECTIVE:
55-year-old female presents to clinic with complaint of right-sided headache for 3 days. Headache is throbbing, rated 7/10, associated with photophobia and mild nausea. No fever, no vision changes, no neurological deficits. Patient reports similar headaches in the past, typically lasting 1-2 days. Last episode 6 months ago. Takes ibuprofen 400mg with partial relief. No recent head trauma. No new medications. Denies neck stiffness.

PMH: Hypertension on lisinopril 10mg daily. Migraines (diagnosed age 30).
Allergies: NKDA.
Social: Non-smoker, occasional alcohol use.

OBJECTIVE:
BP 132/82, HR 78, RR 16, T 98.4F, SpO2 99% on RA.
Alert and oriented x3. Neuro exam grossly intact, CN II-XII normal. No focal deficits.
HEENT: PERRLA, EOMI. No sinus tenderness. No carotid bruits. Neck supple.

ASSESSMENT:
Recurrence of chronic migraine — clinically classic presentation, no red-flag features.

PLAN:
1. Sumatriptan 50mg PO at onset, may repeat in 2 hours (max 200mg/24h).
2. Continue lisinopril.
3. Keep headache diary; return if frequency increases or new neurological symptoms develop.
4. Follow up in 4 weeks if not improving.
`.trim();

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  let visitId = null;
  // Reuse Phase B's patient to avoid /api/patients rate limit
  const { patientId: BORROWED_PATIENT } = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'patient-id.json'), 'utf8'));
  await record(PHASE, '28-create-paste-text-visit', async () => {
    await page.goto(`${URL}/visits/new?patientId=${BORROWED_PATIENT}`, { waitUntil: 'networkidle' });
    await page.fill('input[name="chiefComplaint"]', 'Recurrent right-sided headache x 3 days');
    await page.screenshot({ path: shotPath(PHASE, '28a-form-filled'), fullPage: true });

    // The capture-mode tile shows "Text to SOAP — Type bullets, AI expands them."
    const textBtn = page.getByRole('button', { name: /text to soap/i }).first();
    if (await textBtn.count() === 0) throw new Error('Text to SOAP capture-mode tile not found');
    await textBtn.click();
    await page.waitForURL(/\/visits\/c[a-z0-9]{20,}/, { timeout: 25000 });
    visitId = page.url().match(/\/visits\/(c[a-z0-9]{20,})/)?.[1];
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-E', 'visit-id.json'),
      JSON.stringify({ visitId, patientId: BORROWED_PATIENT }, null, 2),
    );
  });

  await record(PHASE, '29-paste-text-content', async () => {
    await page.waitForTimeout(1500);
    const ta = page.locator('textarea').first();
    if (await ta.count() === 0) throw new Error('No textarea found on paste-text page');
    await ta.fill(PASTED_TEXT);
    await page.screenshot({ path: shotPath(PHASE, '29a-text-pasted'), fullPage: true });

    // The submit button is "Expand to SOAP →" (don't match /draft/ — that hits "Edit draft").
    const submitBtn = page.getByRole('button', { name: /expand to soap/i }).first();
    if (await submitBtn.count() === 0) throw new Error('"Expand to SOAP" button not found');
    await submitBtn.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: shotPath(PHASE, '29b-text-submitted'), fullPage: true });
  });

  await record(PHASE, '30-31-32-pipeline-and-outputs', async () => {
    let last = null;
    const tStart = Date.now();
    while (Date.now() - tStart < 6 * 60 * 1000) {
      const resp = await page.request.get(`${URL}/api/visits/${visitId}/status`);
      if (resp.ok()) {
        const d = await resp.json();
        if (d.status !== last) {
          console.log(`  [E] ${d.status}`);
          last = d.status;
        }
        if (['READY', 'SIGNED'].includes(d.status)) break;
        if (d.status === 'FAILED') throw new Error(`pipeline FAILED: ${d.reviewReason}`);
      }
      await page.waitForTimeout(3000);
    }
    if (!['READY', 'SIGNED'].includes(last)) throw new Error(`paste-text pipeline did not READY in 6 min (last: ${last})`);

    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '30a-visit-ready'), fullPage: true });
    const bodyText = await page.locator('body').innerText();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-E', 'paste-text-result.json'),
      JSON.stringify({
        visitId,
        finalStatus: last,
        soapPresent: /assessment|impression/i.test(bodyText) && /plan|recommend/i.test(bodyText),
        bodyLength: bodyText.length,
      }, null, 2),
    );
  });

  await browser.close();
})().catch((e) => {
  console.error('phase E FAIL:', e.stack || e.message);
  process.exit(1);
});
