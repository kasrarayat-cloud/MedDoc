/**
 * Word destination-authority regression — known failure L01 (legacy default path, fixture AI).
 *
 * The legacy Word inspector types a 'Patient signature' or 'Initials' table row as an ordinary text
 * question (documents/engine.py:336-337), generation asks every non-v3 field and excludes only clinician
 * identity (core/generation.py:3736-3737, :3299, :3516; 'Patient signature' is explicitly NOT the
 * clinician at core/tab_review.py NOT_THE_CLINICIAN), and the legacy fill writes by locator with no role
 * check (documents/engine.py:719-732). So a labelled note line lands in the exported document's signing
 * place. This walk does what a doctor does and asserts, on the exported original-format DOCX, that it
 * does NOT:
 *   (a) the ordinary rows carry their note values;
 *   (b) the signature/initials values are nowhere in the export and those answer cells are unchanged;
 *   (c) the heading and the instruction paragraph are preserved.
 * Reproduced on 43fcf214 (legacy default path): (b) FAILED there, (a) and (c) passed. Since the destination-roles
 * integration every check must pass; CI runs it in 'Private browser and accessibility'.
 *
 * Prepare first (candidate venv python, no Django, no network):
 *   <venv>/bin/python -B prepare-word-authority-browser.py   -> .runtime/word-authority-{form.docx,input.json}
 * Run against a fixture-mode doctor server and worker seeded with seed_private:
 *   QUILLMD_BROWSER_BASE_URL=http://127.0.0.1:9140 QUILLMD_BROWSER_CREDENTIALS=<private-access.json>
 *   PLAYWRIGHT_MODULE_DIR=<node_modules> node word-authority-browser.mjs
 *
 * Boundaries (same as browser-tests.mjs): loopback servers only; freshly seeded synthetic accounts only;
 * refuses unless /health/ says synthetic-only and the workspace discloses the $0 synthetic fixture (no
 * live generation); writes only synthetic records; prints check names and PASS/FAIL only (no credentials,
 * no document or note content); artifacts stay under .runtime/word-authority-artifacts/<run>/.
 * Tracing starts AFTER sign-in, so no credential is typed while the trace records.
 *
 * If a fix refuses the signing text at save or finalize instead of never asking it, no export is produced;
 * the script then records the refusal and marks (b) as not evaluated (failed) — adapt the flow to the
 * chosen design rather than reading that as the defect.
 */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import zlib from 'node:zlib';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
function dependency(name) {
  if (process.env.PLAYWRIGHT_MODULE_DIR) return require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR, name));
  return require(name);
}

const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(appDirectory, '.runtime');
const runName = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
const artifacts = path.join(runtime, 'word-authority-artifacts', runName);
const base = new URL(process.env.QUILLMD_BROWSER_BASE_URL || 'http://127.0.0.1:9130');
assert(['localhost', '127.0.0.1', '[::1]'].includes(base.hostname), 'Browser gate requires a loopback server.');
assert(!base.username && !base.password, 'Do not put credentials in the preview URL.');

// CONTROL MODE (not the regression): QUILLMD_WORD_AUTHORITY_CONTROL=clinician-leaves-signing-blank makes the
// doctor empty the signing answers and choose "Leave blank — reviewed" before finalizing. Every assertion must
// then PASS; if (b) still failed, the assertion would be failing for a reason other than the defect.
const control = process.env.QUILLMD_WORD_AUTHORITY_CONTROL || '';
assert(['', 'clinician-leaves-signing-blank'].includes(control), 'Unknown control mode.');
const checks = [];
const result = {
  regression: 'word-authority L01 (legacy signing rows filled from labelled notes)',
  expected_on_43fcf214: '(b) FAILS — the known defect reproduces; (a) and (c) pass',
  synthetic_only: true, generation: 'fixture, no provider requests', base_url: base.origin, run: runName,
  control_mode: control || null,
  checks, assertions: {}, mapping_review: null, review_page: null, finalized_page: null, artifacts: {},
};
if (control) result.expected_on_43fcf214 = 'CONTROL: every assertion passes (the clinician left the signing rows blank)';
let activeCheck = 'Initialize browser dependencies, synthetic inputs and private credentials';
let browser; let context; let page; let tracing = false;

async function check(name, action) {
  activeCheck = name;
  await action();
  checks.push({ name, passed: true });
  console.log(`PASS ${name}`);
}

// ---- DOCX reading: a minimal ZIP central-directory reader and WordprocessingML text helpers ----
function unzip(buffer) {
  const entries = new Map();
  let eocd = -1;
  for (let i = buffer.length - 22; i >= Math.max(0, buffer.length - 22 - 65535); i--) {
    if (buffer.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  assert(eocd >= 0, 'Not a ZIP archive');
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    assert.equal(buffer.readUInt32LE(offset), 0x02014b50, 'Corrupt ZIP central directory');
    const method = buffer.readUInt16LE(offset + 10);
    const compressed = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const local = buffer.readUInt32LE(offset + 42);
    const name = buffer.subarray(offset + 46, offset + 46 + nameLength).toString('utf8');
    assert.equal(buffer.readUInt32LE(local), 0x04034b50, 'Corrupt ZIP local header');
    const start = local + 30 + buffer.readUInt16LE(local + 26) + buffer.readUInt16LE(local + 28);
    const data = buffer.subarray(start, start + compressed);
    assert([0, 8].includes(method), 'Unsupported ZIP compression');
    entries.set(name, method === 0 ? Buffer.from(data) : zlib.inflateRawSync(data));
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}
const decode = s => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
  .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/&amp;/g, '&');
const texts = xml => [...xml.matchAll(/<w:t(?:\s[^>]*)?>([^<]*)<\/w:t>/g)].map(m => decode(m[1])).join('');
// Whole-part text keeps paragraph (and so cell) boundaries: joining every run of a part made the label cell and the
// answer cell one word ('…signatureVALUE'), which a whole-token search can never see.
const partText = xml => [...xml.matchAll(/<w:p(?=[\s>])[\s\S]*?<\/w:p>/g)].map(m => texts(m[0])).join('\n');
function tableRows(xml) {
  return new Map([...xml.matchAll(/<w:tr(?=[\s>])[\s\S]*?<\/w:tr>/g)].map(m => {
    const cells = [...m[0].matchAll(/<w:tc(?=[\s>])[\s\S]*?<\/w:tc>/g)].map(c => c[0]);
    return [texts(cells[0] || '').trim(), cells];
  }));
}
function leadingParagraphs(xml) {
  const body = xml.slice(xml.indexOf('<w:body'), xml.indexOf('<w:tbl'));
  return [...body.matchAll(/<w:p(?=[\s>])[\s\S]*?<\/w:p>/g)].map(m => ({ xml: m[0], text: texts(m[0]).trim() }));
}
const token = value => new RegExp('(?<![\\p{L}\\p{N}])' + value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}])', 'u');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

async function screenshot(name, locator = page, options = { fullPage: true }) {
  const file = path.join(artifacts, name);
  await locator.screenshot(locator === page ? { path: file, ...options } : { path: file });
  result.artifacts[name.replace(/\.png$/, '')] = file;
}

try {
  const { chromium } = dependency('@playwright/test');
  const credentialPath = process.env.QUILLMD_BROWSER_CREDENTIALS || path.join(appDirectory, '.runtime', 'private-access.json');
  const credentials = JSON.parse(await fs.readFile(credentialPath, 'utf8'));
  assert(credentials.doctor?.email.endsWith('@synthetic.quillmd.invalid'), 'Use freshly seeded synthetic accounts.');
  const input = JSON.parse(await fs.readFile(path.join(runtime, 'word-authority-input.json'), 'utf8'));
  assert(input.synthetic_only === true && input.rows.length === 8, 'Run prepare-word-authority-browser.py first.');
  const formPath = path.join(runtime, input.form);
  const originalBytes = await fs.readFile(formPath);
  assert.equal(sha256(originalBytes), input.original_sha256, 'The prepared blank form changed after preparation.');
  await fs.mkdir(artifacts, { recursive: true, mode: 0o700 });
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, acceptDownloads: true });
  page = await context.newPage();
  const scriptErrors = [];
  page.on('pageerror', () => scriptErrors.push('Client script error'));
  page.setDefaultTimeout(30_000);
  const templateName = 'Synthetic legacy signing rows ' + Date.now();
  let templateURL; let exportBytes; let originalDownload;

  await check('Server is synthetic-only and reports its release', async () => {
    const response = await context.request.get(new URL('/health/', base).href);
    assert.equal(response.status(), 200);
    const health = await response.json();
    assert.equal(health.data_mode, 'synthetic-only');
    result.health = { status: health.status, data_mode: health.data_mode, surface: health.surface, release: health.release };
  });
  await check('Synthetic doctor sign-in and fixture spending boundary', async () => {
    await page.goto(new URL('/login/', base).href);
    await page.locator('[name=email]').fill(credentials.doctor.email);
    await page.locator('[name=password]').fill(credentials.doctor.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForURL(new URL('/', base).href);
    // Spending boundary: never run paid generation from a regression.
    assert.equal(await page.locator('.integration-list .badge').filter({ hasText: /^Synthetic fixture$/ }).count(), 1);
  });
  await context.tracing.start({ screenshots: true, snapshots: true, sources: false, title: 'word-authority L01' });
  tracing = true;

  await check('Upload the blank synthetic legacy form through the upload page', async () => {
    await page.goto(new URL('/templates/upload/', base).href);
    await page.locator('[name=name]').fill(templateName);
    const options = await page.locator('[name=department] option').allTextContents();
    const label = options.find(text => text.includes('X-ray'));
    assert(label, 'The seeded X-ray department is not offered.');
    await page.locator('[name=department]').selectOption({ label });
    await page.locator('[name=file]').setInputFiles(formPath);
    await page.locator('[name=synthetic_only]').check();
    await page.getByRole('button', { name: 'Upload and inspect form', exact: true }).click();
    await page.waitForLoadState();
    if (!/\/templates\/[0-9a-f-]+\/$/.test(new URL(page.url()).pathname)) {
      // Application refusal text only (it names the reason), never form or note content.
      result.upload_refusal = (await page.locator('.errorlist, .notice.error, .error-text').allInnerTexts()).map(t => t.trim());
      await screenshot('upload-refused.png');
      throw new Error('Upload refused');
    }
    templateURL = page.url();
  });
  await check('Mapping review lists every legacy row and keeps the original', async () => {
    const rows = await page.locator('.table-wrap tbody tr').evaluateAll(trs => trs.map(tr => ({
      label: tr.cells[0].childNodes[0]?.textContent.trim() ?? '',
      notes: tr.cells[0].querySelectorAll('p').length,
      location: tr.cells[1].childNodes[0]?.textContent.trim() ?? '',
      key: tr.cells[1].querySelector('.mono')?.textContent.trim() ?? '',
    })));
    result.mapping_review = {
      rows: rows.map(row => ({ label: row.label, key: row.key, location: row.location, review_notes: row.notes,
        signing_row: Object.hasOwn(input.signing, row.label) })),
      signing_rows_offered_as_ordinary_fields: Object.keys(input.signing).every(label =>
        rows.some(row => row.label === label && row.notes === 0)),
      use_this_form_offered: await page.getByRole('link', { name: /Use this form/ }).count() === 1,
    };
    await screenshot('mapping-review.png');
    assert.equal(rows.length, input.rows.length);
    assert.deepEqual(rows.map(row => row.label), input.rows);
    const href = await page.getByRole('link', { name: 'Download original', exact: true }).getAttribute('href');
    const response = await context.request.get(new URL(href, base).href);
    assert.equal(response.status(), 200);
    originalDownload = await response.body();
    assert.equal(sha256(originalDownload), input.original_sha256);
  });
  await check('Activate the mapping and start a document from it', async () => {
    // A legacy mapping needs no confirmation (TemplateVersion.needs_confirmation is v3-only), so the
    // form page offers "Use this form" at once; that link is the activation a doctor sees.
    await page.getByRole('link', { name: /Use this form/ }).click();
    await page.waitForURL(/\/encounters\/new\/\?template=/);
    await page.locator('[name=patient]').selectOption({ label: 'Synthetic Example X-ray · X-ray' });
    await page.locator('[name=template_version]').selectOption({ label: templateName + ' · mapping 1' });
    await page.locator('[name=notes]').fill(input.notes);
    await page.locator('[name=synthetic_only]').check();
    await page.getByRole('button', { name: 'Create document', exact: true }).click();
    await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);
    result.encounter_path = new URL(page.url()).pathname;
  });
  await check('Generate with the synthetic fixture at zero charge', async () => {
    assert.equal(await page.getByText('Synthetic fixture · $0 charge. No live AI service is called.', { exact: true }).isVisible(), true);
    await page.getByRole('button', { name: 'Generate supported answers', exact: true }).click();
    for (let attempt = 0; attempt < 40; attempt++) {
      await page.waitForTimeout(1000);
      await page.reload();
      if (await page.locator('.source-panel .badge').filter({ hasText: /^succeeded$/ }).count()) break;
      assert.equal(await page.locator('.source-panel .badge').filter({ hasText: /^(failed|reconciliation)$/ }).count(), 0, 'Fixture job did not complete.');
    }
    assert(await page.locator('section.answer').count() > 0, 'No answers were generated.');
  });
  await check('Record how the review page presents the signing rows', async () => {
    const sections = await page.locator('section.answer').evaluateAll(nodes => nodes.map(node => {
      const control = node.querySelector('[name^="answer_"]');
      return {
        label: (node.querySelector('h3')?.textContent || '').replace(/^\s*\d+\.\s*/, '').trim(),
        badge: (node.querySelector('.answer-heading .badge')?.textContent || '').trim(),
        control: control ? control.tagName.toLowerCase() : 'none',
        editable: control ? !control.disabled && !control.readOnly : false,
        value: control ? control.value : null,
        evidence: node.querySelectorAll('.evidence blockquote').length,
        signed_by_hand: /Signed by hand/.test(node.textContent),
      };
    }));
    const describe = (label, expected) => {
      const row = sections.find(section => section.label === label);
      if (!row) return { present: false };
      return { present: true, badge: row.badge, control: row.control, editable: row.editable,
        value_equals_note_value: row.value === expected, value_empty: !row.value, evidence_quotes: row.evidence,
        signing_marker_shown: row.signed_by_hand,
        shown_as_ordinary_answer: row.control === 'textarea' && row.editable && row.value === expected && !row.signed_by_hand };
    };
    result.review_page = {
      answer_sections: sections.length,
      signing_rows: Object.fromEntries(Object.entries(input.signing).map(([label, value]) => [label, describe(label, value)])),
      ordinary_rows: Object.fromEntries(Object.entries(input.ordinary).map(([label, value]) => [label, describe(label, value)])),
    };
    await screenshot('review-desktop.png');
    for (const label of Object.keys(input.signing)) {
      const section = page.locator('section.answer').filter({ has: page.locator('h3', { hasText: label }) }).first();
      if (await section.count()) await screenshot(`review-${label.toLowerCase().replace(/[^a-z]+/g, '-')}.png`, section);
    }
  });
  if (control === 'clinician-leaves-signing-blank') await check('CONTROL: clinician empties the signing answers and leaves them blank', async () => {
    for (const label of Object.keys(input.signing)) {
      const section = page.locator('section.answer').filter({ has: page.locator('h3', { hasText: label }) }).first();
      await section.locator('textarea[name^=answer_]').fill('');
      await section.locator('input[type=checkbox][name^=blank_]').check();   // not the hidden blank_shown_ input
    }
  });
  await check('Save clinician review decisions', async () => {
    const boxes = await page.locator('input[name^=reviewed_]').all();
    for (const box of boxes) await box.check();
    await page.getByRole('button', { name: 'Save answers and review decisions', exact: true }).click();
    await page.waitForLoadState();
    assert.equal(await page.locator('input[name^=reviewed_]:checked').count(), boxes.length);
  });
  await check('Finalize the reviewed document', async () => {
    await page.locator('[name=reviewed]').check();
    await page.getByRole('button', { name: 'Finalize document', exact: true }).click();
    await page.waitForLoadState();
    if (await page.getByRole('link', { name: 'Export original format' }).count() !== 1) {
      result.finalize_refusal = (await page.locator('.notice.warning, .notice.error, .errorlist').allInnerTexts()).map(t => t.trim()).slice(0, 5);
      await screenshot('finalize-refused.png');
      throw new Error('Finalize refused');
    }
    const shown = await page.locator('section.answer').evaluateAll(nodes => nodes.map(node => ({
      label: (node.querySelector('h3')?.textContent || '').replace(/^\s*\d+\.\s*/, '').trim(),
      text: (node.querySelector('.answer-text')?.textContent || '').trim() })));
    result.finalized_page = Object.fromEntries(Object.entries(input.signing).map(([label, value]) =>
      [label, { shows_note_value: shown.some(row => row.label === label && row.text === value) }]));
    await screenshot('finalized.png');
  });
  await check('Download the original-format export', async () => {
    const href = await page.getByRole('link', { name: 'Export original format' }).getAttribute('href');
    const response = await context.request.get(new URL(href, base).href);
    assert.equal(response.status(), 200);
    exportBytes = await response.body();
    assert.equal(exportBytes.subarray(0, 2).toString(), 'PK');
    const destination = path.join(artifacts, 'export.docx');
    await fs.writeFile(destination, exportBytes, { mode: 0o600 });
    await fs.writeFile(path.join(artifacts, 'original.docx'), originalDownload, { mode: 0o600 });
    result.artifacts.export = destination;
    result.artifacts.original = path.join(artifacts, 'original.docx');
    result.export = { sha256: sha256(exportBytes), bytes: exportBytes.length, original_sha256: input.original_sha256 };
  });
  await context.tracing.stop({ path: path.join(artifacts, 'trace.zip') });
  tracing = false;
  result.artifacts.trace = path.join(artifacts, 'trace.zip');
  await check('No client-side JavaScript errors', async () => assert.equal(scriptErrors.length, 0));

  // ---- Assertions on the exported DOCX (evaluated even when an earlier one fails) ----
  activeCheck = 'Assertions on the exported document';
  const original = unzip(originalDownload);
  const exported = unzip(exportBytes);
  const originalXml = original.get('word/document.xml').toString('utf8');
  const exportXml = exported.get('word/document.xml').toString('utf8');
  const originalRows = tableRows(originalXml);
  const exportRows = tableRows(exportXml);
  // Positive control for the "unchanged" instrument: the label cells are never filled, so their XML must
  // compare equal between original and export. If it does not, XML equality cannot mean "unchanged".
  const controlEqual = input.rows.filter(label => originalRows.get(label)?.[0] === exportRows.get(label)?.[0]).length;
  const instrumentValid = controlEqual === input.rows.length;

  const a = { rows: {} };
  for (const [label, value] of Object.entries(input.ordinary)) {
    const cell = exportRows.get(label)?.[1];
    a.rows[label] = { row_found: Boolean(cell), value_present: Boolean(cell) && texts(cell).includes(value) };
  }
  a.passed = Object.values(a.rows).every(row => row.value_present);

  const parts = [...exported.entries()].filter(([name]) => name.startsWith('word/') && name.endsWith('.xml'));
  const partsWith = value => { const pattern = token(value);
    return parts.filter(([, bytes]) => { const xml = bytes.toString('utf8'); return pattern.test(partText(xml)) || pattern.test(xml); }).map(([name]) => name); };
  // Positive control for the "absent" instrument: the same search must FIND every ordinary value the export carries.
  const ordinaryFound = Object.values(input.ordinary).filter(value => partsWith(value).length > 0).length;
  const absentValid = ordinaryFound === Object.keys(input.ordinary).length;
  const b = { unchanged_instrument_control: { label_cells_xml_equal: controlEqual, of: input.rows.length, valid: instrumentValid },
    absent_instrument_control: { ordinary_values_found: ordinaryFound, of: Object.keys(input.ordinary).length, valid: absentValid }, rows: {} };
  for (const [label, value] of Object.entries(input.signing)) {
    const before = originalRows.get(label)?.[1];
    const after = exportRows.get(label)?.[1];
    const pattern = token(value);
    const found = partsWith(value);
    b.rows[label] = {
      value_absent_from_export: found.length === 0,
      parts_containing_value: found,
      value_in_own_answer_cell: Boolean(after) && pattern.test(texts(after)),
      answer_cell_text_unchanged: Boolean(before && after) && texts(before) === texts(after),
      answer_cell_xml_unchanged: Boolean(before && after) && before === after,
    };
  }
  b.passed = absentValid && Object.values(b.rows).every(row => row.value_absent_from_export && row.answer_cell_text_unchanged
    && (instrumentValid ? row.answer_cell_xml_unchanged : true));

  const beforeParagraphs = leadingParagraphs(originalXml);
  const afterParagraphs = leadingParagraphs(exportXml);
  const paragraph = (list, text) => list.find(item => item.text === text);
  const c = {
    heading_present: Boolean(paragraph(afterParagraphs, input.heading)),
    heading_xml_unchanged: paragraph(beforeParagraphs, input.heading)?.xml === paragraph(afterParagraphs, input.heading)?.xml,
    instruction_present: Boolean(paragraph(afterParagraphs, input.instruction)),
    instruction_xml_unchanged: paragraph(beforeParagraphs, input.instruction)?.xml === paragraph(afterParagraphs, input.instruction)?.xml,
    heading_before_instruction_before_table: afterParagraphs.findIndex(p => p.text === input.heading) === 0
      && afterParagraphs.findIndex(p => p.text === input.instruction) === 1 && exportXml.indexOf('<w:tbl') > 0,
  };
  c.passed = c.heading_present && c.instruction_present && c.heading_xml_unchanged && c.instruction_xml_unchanged
    && c.heading_before_instruction_before_table;

  result.assertions = {
    a_ordinary_rows_filled: a,
    b_signing_rows_not_filled: b,
    c_heading_and_instruction_preserved: c,
  };
  for (const [name, value] of Object.entries(result.assertions)) {
    console.log(`${value.passed ? 'PASS' : 'FAIL'} assertion ${name}`);
    if (!value.passed) process.exitCode = 1;
  }
} catch {
  // Never log the raw exception: Playwright errors can echo fill() arguments (credentials, notes).
  if (!checks.some(item => item.name === activeCheck && !item.passed)) checks.push({ name: activeCheck, passed: false });
  if (page) await screenshot('failure.png').catch(() => {});
  console.error(`FAIL ${activeCheck}. Inspect the private result.json; no credentials or content were logged.`);
  for (const name of ['a_ordinary_rows_filled', 'b_signing_rows_not_filled', 'c_heading_and_instruction_preserved']) {
    result.assertions[name] ??= { passed: false, evaluated: false };
  }
  process.exitCode = 1;
} finally {
  if (tracing) {
    await context.tracing.stop({ path: path.join(artifacts, 'trace.zip') }).catch(() => {});
    result.artifacts.trace = path.join(artifacts, 'trace.zip');
  }
  await browser?.close();
  result.finished = new Date().toISOString();
  result.passed = checks.every(item => item.passed) && Object.values(result.assertions).every(item => item.passed);
  await fs.mkdir(artifacts, { recursive: true, mode: 0o700 });
  const body = JSON.stringify(result, null, 2);
  await fs.writeFile(path.join(artifacts, 'result.json'), body, { mode: 0o600 });
  await fs.writeFile(path.join(runtime, 'word-authority-artifacts', 'result.json'), body, { mode: 0o600 });
  console.log(`${checks.filter(item => item.passed).length} checks passed; ${checks.filter(item => !item.passed).length} failed. Result: .runtime/word-authority-artifacts/${runName}/result.json`);
}
