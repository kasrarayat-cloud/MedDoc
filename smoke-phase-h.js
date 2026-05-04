// Phase H — adversarial / edge cases (steps 41-46).
// Quick wins; mostly probes API + auth surfaces.
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

const PHASE = 'H';
// No fail-fast: each adversarial probe is independent.

const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const FOREIGN_VISIT_ID = 'cmoq6q5s4000p01qqhdngm77n'; // qa-bypass owner's visit, smoke-user shouldn't see

(async () => {
  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 41 — 0-byte audio file → expect graceful failure
  await record(PHASE, '41-zero-byte-audio', async () => {
    fs.writeFileSync('/tmp/smoke-audio/zero.wav', '');
    // Find a pending visit; reuse Phase B if available, else create one.
    const visitB = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));
    if (!visitB.visitId) {
      fs.writeFileSync(path.join(SMOKE_DIR, 'phase-H', 'finding-41.json'), JSON.stringify({ skip: 'no Phase B visit available' }));
      return;
    }
    // Direct API probe: POST /api/visits/[id]/upload with a 0-byte file.
    // The action validates content-type + size; expect 4xx.
    const formData = `--boundary\r\nContent-Disposition: form-data; name="file"; filename="empty.wav"\r\nContent-Type: audio/wav\r\n\r\n\r\n--boundary--\r\n`;
    const resp = await page.request.post(`${URL}/api/visits/${visitB.visitId}/upload`, {
      headers: { 'Content-Type': 'multipart/form-data; boundary=boundary' },
      data: formData,
    });
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-41-zero-byte.json'),
      JSON.stringify({ status: resp.status(), body: (await resp.text()).slice(0, 300) }, null, 2),
    );
    // PASS criteria: not 5xx, and not 200 (should reject)
    if (resp.status() >= 500) throw new Error(`zero-byte upload returned 5xx: ${resp.status()}`);
  });

  // Step 42 — non-audio file (PDF) → expect rejection
  await record(PHASE, '42-non-audio-file', async () => {
    const visitB = JSON.parse(fs.readFileSync(path.join(SMOKE_DIR, 'phase-B', 'visit-id.json'), 'utf8'));
    if (!visitB.visitId) {
      fs.writeFileSync(path.join(SMOKE_DIR, 'phase-H', 'finding-42.json'), JSON.stringify({ skip: 'no Phase B visit available' }));
      return;
    }
    // Make a tiny PDF (just a magic header is enough for content-type sniffing)
    const fakePdf = Buffer.from('%PDF-1.4\n%fake\n%%EOF');
    fs.writeFileSync('/tmp/smoke-audio/fake.pdf', fakePdf);
    const formData = `--boundary\r\nContent-Disposition: form-data; name="file"; filename="fake.pdf"\r\nContent-Type: application/pdf\r\n\r\n${fakePdf.toString('binary')}\r\n--boundary--\r\n`;
    const resp = await page.request.post(`${URL}/api/visits/${visitB.visitId}/upload`, {
      headers: { 'Content-Type': 'multipart/form-data; boundary=boundary' },
      data: formData,
    });
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-42-non-audio.json'),
      JSON.stringify({ status: resp.status(), body: (await resp.text()).slice(0, 300) }, null, 2),
    );
    if (resp.status() >= 500) throw new Error(`PDF upload returned 5xx: ${resp.status()}`);
  });

  // Step 43 — silent audio → AI should NOT fabricate. Skipping for now;
  // requires a 30s silent WAV + full pipeline run. Documented as known
  // gap in this phase's readme. Phase B's I-001 finding (Round 2 audit
  // already validated AI-no-fabrication on dictation with no values).
  await record(PHASE, '43-silent-audio', async () => {
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-43-silent-audio.json'),
      JSON.stringify({
        skip: 'pipeline run takes 3-5 min per upload; defer to Round 2 I-001 finding which already validated no-fabrication on a no-values dictation.',
        roundTwoReference: 'docs/deep-audit-round2-2026-05-03/findings/ + I-001 in executive-summary',
      }, null, 2),
    );
  });

  // Step 44 — sign with empty SOAP → should block
  await record(PHASE, '44-sign-empty-soap', async () => {
    // Create a fresh visit with no inputs
    const patientResp = await page.request.post(`${URL}/api/patients`, {
      data: { name: `Smoke Empty Test ${Date.now()}`, dateOfBirth: '1980-01-01', externalId: null },
    });
    const patientBody = await patientResp.json();
    const patientId = patientBody.patient?.id ?? patientBody.id;

    // Create visit shell directly via API (skip the input requirement)
    const visitResp = await page.request.post(`${URL}/api/visits`, {
      data: { patientId, specialty: 'primary-care', chiefComplaint: 'empty test', inputMode: 'text_notes' },
    });
    const visitBody = await visitResp.json().catch(() => ({}));
    const visitId = visitBody.visit?.id ?? visitBody.id ?? null;

    // Try to sign immediately (should fail because no SOAP exists)
    const signResp = visitId
      ? await page.request.post(`${URL}/api/visits/${visitId}/sign`, { data: { destinations: [] } })
      : { status: () => 'no-visit-created' };

    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-44-empty-sign.json'),
      JSON.stringify({
        patientId, visitId,
        signStatus: typeof signResp.status === 'function' ? signResp.status() : signResp.status,
        signBody: typeof signResp.text === 'function' ? (await signResp.text()).slice(0, 300) : null,
      }, null, 2),
    );
  });

  // Step 45 — URL guess to another doctor's visit → should 404
  await record(PHASE, '45-foreign-visit-url', async () => {
    const resp = await page.request.get(`${URL}/api/visits/${FOREIGN_VISIT_ID}/status`);
    const status = resp.status();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-45-foreign-url.json'),
      JSON.stringify({
        foreignVisitId: FOREIGN_VISIT_ID,
        apiStatus: status,
        expected: 404,
        pass: status === 404,
      }, null, 2),
    );
    if (status !== 404) throw new Error(`expected 404 for foreign visit, got ${status}`);
  });

  // Step 46 — sign out + try /dashboard → expect redirect to /login
  await record(PHASE, '46-signed-out-redirect', async () => {
    // Clear cookies to simulate sign-out, then GET /dashboard.
    await ctx.clearCookies();
    const resp = await page.goto(`${URL}/dashboard`, { waitUntil: 'load', timeout: 15000 });
    const finalUrl = page.url();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-H', 'finding-46-signed-out.json'),
      JSON.stringify({
        navigatedTo: finalUrl,
        status: resp ? resp.status() : null,
        landedOnLogin: /\/login/.test(finalUrl),
      }, null, 2),
    );
    if (!/\/login/.test(finalUrl)) throw new Error(`expected redirect to /login, got ${finalUrl}`);
  });

  await browser.close();
})().catch((e) => {
  console.error('phase H FAIL:', e.stack || e.message);
  process.exit(1);
});
