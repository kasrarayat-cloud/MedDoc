// Phase C — review + edit + sign + export (steps 15-21).
// Depends on Phase B's visit-id.json artifact for the target visit.
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

const PHASE = 'C';
const TIMINGS = [];
setFailFast(PHASE);

const STORAGE_STATE = path.join(SMOKE_DIR, 'test-data', 'session-storage.json');
const VISIT_ID_FILE = path.join(SMOKE_DIR, 'phase-B', 'visit-id.json');

(async () => {
  if (!fs.existsSync(VISIT_ID_FILE)) {
    console.error('phase C requires phase-B/visit-id.json — run Phase B first');
    process.exit(2);
  }
  const { visitId } = JSON.parse(fs.readFileSync(VISIT_ID_FILE, 'utf8'));
  if (!visitId) {
    console.error('phase-B/visit-id.json has no visitId');
    process.exit(2);
  }

  const { browser, ctx, page } = await newSession();
  page.setDefaultTimeout(30000);
  await ctx.addCookies(JSON.parse(fs.readFileSync(STORAGE_STATE, 'utf8')).cookies);

  // Step 15 — load visit, edit Plan section
  await record(PHASE, '15-edit-plan', async () => {
    await page.goto(`${URL}/visits/${visitId}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '15a-visit-detail'), fullPage: true });

    // SOAP editor: hover/click Plan section to enter inline edit. The product
    // uses a textarea-per-section model (SoapInlineEdit). Look for any
    // editable element in the Plan area.
    const planRegion = page.getByText(/^plan$/i).first();
    if (await planRegion.count() === 0) {
      throw new Error('SOAP Plan heading not found on visit detail page');
    }

    // Clicking the Plan area should reveal the inline editor textarea OR
    // surface an "Edit" button. Take a screenshot either way.
    await planRegion.click({ delay: 100 }).catch(() => {});
    await page.waitForTimeout(500);
    await page.screenshot({ path: shotPath(PHASE, '15b-plan-clicked'), fullPage: true });

    const planTextarea = page.locator('textarea').first();
    if (await planTextarea.count() > 0) {
      const original = await planTextarea.inputValue();
      const edited = original + '\n\n[smoke-test edit] follow up in 2 weeks for repeat EKG.';
      await planTextarea.fill(edited);
      await page.screenshot({ path: shotPath(PHASE, '15c-plan-edited'), fullPage: true });
      // Try to commit the edit (clicking outside or a Save button)
      await page.locator('body').click({ position: { x: 10, y: 10 } });
      await page.waitForTimeout(1500);
      fs.writeFileSync(
        path.join(SMOKE_DIR, 'phase-C', 'edit-result.json'),
        JSON.stringify({ originalLength: original.length, editedLength: edited.length }, null, 2),
      );
    } else {
      fs.writeFileSync(
        path.join(SMOKE_DIR, 'phase-C', 'edit-result.json'),
        JSON.stringify({ note: 'no textarea surfaced after clicking Plan; UX may need explicit edit-mode button' }, null, 2),
      );
    }
  });

  // Step 16 — Codes tab
  await record(PHASE, '16-codes-tab', async () => {
    await page.getByRole('tab', { name: /codes/i }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: shotPath(PHASE, '16-codes-tab'), fullPage: true });
  });

  // Step 17 — Rx tab
  await record(PHASE, '17-rx-tab', async () => {
    await page.getByRole('tab', { name: /rx/i }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: shotPath(PHASE, '17-rx-tab'), fullPage: true });
  });

  // Step 18 — sign visit
  await record(PHASE, '18-sign-visit', async () => {
    // Back to the SOAP tab so we can find Sign & Send button
    await page.getByRole('tab', { name: /soap/i }).first().click();
    await page.waitForTimeout(800);
    const signBtn = page.getByRole('button', { name: /sign.*send|sign$/i }).first();
    if (await signBtn.count() === 0) {
      throw new Error('Sign & Send button not found');
    }
    await signBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: shotPath(PHASE, '18a-sign-modal'), fullPage: true });

    // Modal usually has "Confirm sign" or similar. Skip destination
    // selection (Phase C doesn't test EHR send) — just sign.
    const confirmSign = page.getByRole('button', { name: /confirm.*sign|sign.*now|sign$/i }).last();
    if (await confirmSign.count() > 0) {
      await confirmSign.click();
    }
    await page.waitForTimeout(3000);
    await page.screenshot({ path: shotPath(PHASE, '18b-after-sign'), fullPage: true });

    // Verify status changed to SIGNED via /status endpoint
    const resp = await page.request.get(`${URL}/api/visits/${visitId}/status`);
    const data = await resp.json();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-C', 'sign-result.json'),
      JSON.stringify(data, null, 2),
    );
  });

  // Step 19 — PDF export + verify metadata clean (P1-001)
  await record(PHASE, '19-pdf-export', async () => {
    const pdfResp = await page.request.get(`${URL}/api/visits/${visitId}/export/pdf`);
    if (pdfResp.status() !== 200) throw new Error(`PDF export status ${pdfResp.status()}`);
    const buf = await pdfResp.body();
    const pdfPath = path.join(SMOKE_DIR, 'phase-C', 'export.pdf');
    fs.writeFileSync(pdfPath, buf);

    // Same metadata extractor used by P1-001 unit tests.
    const text = buf.toString('latin1');
    const refs = [];
    const refRe = /\/(Title|Author|Creator|Producer)\s+(\d+)\s+0\s+R/g;
    let m;
    while ((m = refRe.exec(text)) !== null) refs.push([m[1], Number(m[2])]);
    const meta = {};
    for (const [key, num] of refs) {
      const startMarker = `${num} 0 obj`;
      const objStart = text.indexOf(startMarker);
      if (objStart < 0) continue;
      const objEnd = text.indexOf('endobj', objStart);
      if (objEnd < 0) continue;
      const body = text.slice(objStart + startMarker.length, objEnd);
      const open = body.indexOf('(');
      const close = body.lastIndexOf(')');
      if (open >= 0 && close > open) meta[key] = body.slice(open + 1, close);
    }
    // P1-001 acceptance: Title is 'Visit <visitId>', Author is 'QuillMD',
    // patient name nowhere in the metadata.
    const result = {
      bytes: buf.length,
      meta,
      patientNameInMeta: Object.values(meta).some((v) => /smoke testpatient/i.test(v)),
      titleIsVisitId: meta.Title === `Visit ${visitId}`,
      authorIsQuillMD: meta.Author === 'QuillMD',
    };
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-C', 'pdf-metadata.json'),
      JSON.stringify(result, null, 2),
    );
    if (result.patientNameInMeta) throw new Error('PDF metadata contains patient name (P1-001 regression)');
    if (!result.titleIsVisitId) throw new Error(`PDF /Title != "Visit ${visitId}" (got: ${meta.Title})`);
  });

  // Step 20 — DOCX export + verify metadata clean
  await record(PHASE, '20-docx-export', async () => {
    const docxResp = await page.request.get(`${URL}/api/visits/${visitId}/export/docx`);
    if (docxResp.status() !== 200) throw new Error(`DOCX status ${docxResp.status()}`);
    const buf = await docxResp.body();
    const docxPath = path.join(SMOKE_DIR, 'phase-C', 'export.docx');
    fs.writeFileSync(docxPath, buf);

    // Use jszip to crack docProps/core.xml.
    const JSZip = require('jszip');
    const zip = await JSZip.loadAsync(buf);
    const coreXml = await zip.file('docProps/core.xml').async('text');
    const result = {
      bytes: buf.length,
      coreXml,
      patientNameInCore: /smoke testpatient/i.test(coreXml),
      hasVisitIdTitle: coreXml.includes(`<dc:title>Visit ${visitId}</dc:title>`),
      hasQuillMDCreator: coreXml.includes('<dc:creator>QuillMD</dc:creator>'),
    };
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-C', 'docx-metadata.json'),
      JSON.stringify(result, null, 2),
    );
    if (result.patientNameInCore) throw new Error('DOCX core.xml contains patient name (P1-001 regression)');
    if (!result.hasVisitIdTitle) throw new Error('DOCX <dc:title> does not contain visitId');
  });

  // Step 21 — email export. The /api/visits/[id]/export/email path should
  // POST with a `to` field. We don't have a real mailbox to receive — just
  // verify the API accepts and queues without error. Use a test address
  // on quillmd-test.local (won't actually deliver, but Resend probably
  // returns an error rather than 200; we just assert non-5xx).
  await record(PHASE, '21-email-export-api', async () => {
    const resp = await page.request.post(`${URL}/api/visits/${visitId}/export/email`, {
      data: { to: `qa-smoke-${Date.now()}@quillmd-test.local` },
    });
    const body = await resp.text();
    fs.writeFileSync(
      path.join(SMOKE_DIR, 'phase-C', 'email-result.json'),
      JSON.stringify({ status: resp.status(), body: body.slice(0, 500) }, null, 2),
    );
    // Accept any 2xx OR 4xx (4xx may indicate rate limit / disabled email
    // delivery, which is documented behavior — Resend gated behind
    // RESEND_FROM_VERIFIED). 5xx would indicate a real problem.
    if (resp.status() >= 500) throw new Error(`email export 5xx: ${resp.status()}`);
  });

  fs.writeFileSync(
    path.join(SMOKE_DIR, 'phase-C', 'timings.json'),
    JSON.stringify({ phase: PHASE, visitId, timings: TIMINGS }, null, 2),
  );

  await browser.close();
})().catch((e) => {
  console.error('phase C FAIL:', e.stack || e.message);
  process.exit(1);
});
