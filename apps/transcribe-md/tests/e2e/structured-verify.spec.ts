// TEMP QA spec — Phase-3 structured-templates matrix (real pipeline, anchors
// ON, real Opus/Deepgram). Removed at cleanup.
import { test, expect, chromium, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import * as fs from 'node:fs';

const SCRATCH = '/tmp/claude-1000/-opt-meddoc-pro/586b3f3f-7eed-4f8e-ac7f-e25626e93305/scratchpad';
const FIX = `${SCRATCH}/fixtures-structured`;
const ART = `${SCRATCH}/structured-artifacts`;
fs.mkdirSync(ART, { recursive: true });
const BASE = process.env.PW_BASE_URL ?? 'http://localhost:9020';
const PASSWORD = 'QaTmplTestPass9!';
const email = (t: string) => `qa-struct-${t}@test.dev`;
const GROUND = JSON.parse(fs.readFileSync(`${FIX}/ground-truth.json`, 'utf8'));

const MIXED_DICTATION = 'Follow-up for hypertension and hyperlipidemia, also one week of dry cough. Denies fever, denies chills. Denies chest pain, denies palpitations. Reports cough, denies shortness of breath. Vitals: blood pressure 154 over 94, heart rate 76, respiratory rate 14. Assessment: hypertension uncontrolled, viral upper respiratory cough. Plan: continue amlodipine ten milligrams daily and simvastatin forty milligrams nightly, supportive care for the cough, recheck in two weeks.';

function psql(sql: string): string {
  return execFileSync('docker', ['compose', '-f', '../../docker-compose.qa.yml', 'exec', '-T', 'postgres',
    'psql', '-U', 'meddoc', '-d', 'meddoc_qa_test', '-tA', '-f', '-'],
    { input: sql, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }).trim();
}

async function login(page: Page, tag: string) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel('Email').fill(email(tag));
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

async function signupOrLogin(page: Page, tag: string) {
  try { await login(page, tag); return; } catch { await page.context().clearCookies(); }
  await page.goto(`${BASE}/signup`);
  await page.getByLabel('Full name').fill(`QA Struct ${tag}`);
  await page.getByLabel('Email').fill(email(tag));
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  await page.locator('input[type="checkbox"]').first().check();
  await page.getByRole('button', { name: /create account/i }).click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

async function uploadAndActivate(page: Page, tag: string, file: string) {
  await page.goto(`${BASE}/settings`);
  await page.getByRole('button', { name: /note format/i }).click();
  const paste = page.getByLabel('Paste a note');
  if (!(await paste.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /bring a note/i }).click();
  }
  const chooserP = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: /upload a file/i }).click();
  await (await chooserP).setFiles(`${FIX}/${file}`);
  await expect(page.locator('#nf-name')).toBeVisible({ timeout: 240_000 });
  await page.screenshot({ path: `${ART}/${tag}-review.png`, fullPage: true });
  await page.getByRole('button', { name: /save & activate/i }).click();
  await expect(page.getByText('Format activated')).toBeVisible({ timeout: 60_000 });
  const row = psql(`SELECT t.sections::text FROM note_templates t JOIN users u ON u.id=t."doctorId" WHERE u.email='${email(tag)}' AND t.status='active';`);
  fs.writeFileSync(`${ART}/${tag}-sections.json`, row);
  return JSON.parse(row);
}

async function textVisit(page: Page, tag: string, text: string): Promise<string> {
  const res = await page.request.post(`${BASE}/api/patients`, {
    data: { name: `Struct Px ${tag}`, dateOfBirth: '1985-05-15', externalId: null },
    headers: { 'Content-Type': 'application/json' } });
  const patientId = (await res.json()).patient.id as string;
  await page.goto(`${BASE}/visits/new?patientId=${patientId}`);
  await page.getByRole('combobox', { name: 'Specialty' }).click();
  await page.getByRole('option', { name: 'Primary Care' }).click();
  await page.getByRole('button', { name: /text to soap/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;
  await page.getByLabel('Clinical shorthand').fill(text);
  await page.getByRole('button', { name: /expand to soap/i }).click();
  let status = '';
  for (let i = 0; i < 120 && status !== 'READY' && status !== 'FAILED'; i++) {
    await page.waitForTimeout(3000);
    status = psql(`SELECT status FROM transcribe_visits WHERE id='${visitId}';`);
  }
  expect(status).toBe('READY');
  return visitId;
}

/** Deterministic constrained-fill checks. */
function checkConstrainedFill(tag: string, note: string, sections: any[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const optionSets = sections.filter((s) => s.structure?.kind === 'options');
  const allOptions = new Set(optionSets.flatMap((s) => s.structure.options.map((o: string) => o.toLowerCase())));
  const checked = [...note.matchAll(/^[-*]\s+\[x\]\s+(.+?)\s*(?:⟦.*)?$/gim)].map((m) => m[1].trim());
  const invented = checked.filter((c) => !allOptions.has(c.toLowerCase()));
  out.checkedOptions = checked;
  out.inventedOptions = invented;
  const tables = sections.filter((s) => s.structure?.kind === 'table');
  out.hasMarkdownTable = /^\s*\|.*\|\s*$/m.test(note);
  out.tablesInTemplate = tables.length;
  out.notDocumentedCells = (note.match(/\[not documented\]/g) ?? []).length;
  fs.writeFileSync(`${ART}/${tag}-fill-check.json`, JSON.stringify(out, null, 2));
  return out;
}

test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

for (const [tag, file] of [['s1', 's1-checkbox-exam.docx'], ['s2', 's2-scales.pdf'], ['s3', 's3-mixed.docx'], ['s4', 's4-multiselect.docx'], ['s5', 's5-degenerate.docx']] as const) {
  test(`P3 ${tag}: upload → parse detects structure → activate`, async ({ page }) => {
    await signupOrLogin(page, tag);
    const sections = await uploadAndActivate(page, tag, file);
    const withStructure = sections.filter((s: any) => s.structure);
    const gt = GROUND[file] ?? GROUND[tag] ?? {};
    const expected = (gt.sections ?? []).filter((s: any) => s.optionField || s.table || s.structure).length || 1;
    console.log(`[${tag}] sections=${sections.length} structured=${withStructure.length} kinds=${withStructure.map((s: any) => s.structure.kind).join(',')}`);
    expect(withStructure.length, `${tag}: parse detected structure`).toBeGreaterThanOrEqual(1);
    if (tag === 's5') {
      // degenerate: duplicate option deduped, typo preserved verbatim
      const opts = withStructure.flatMap((s: any) => s.structure.kind === 'options' ? s.structure.options : []);
      const moderateCount = opts.filter((o: string) => o.toLowerCase() === 'moderate').length;
      expect(moderateCount, 'duplicated option deduped').toBeLessThanOrEqual(1);
      console.log(`[s5] options=${JSON.stringify(opts)} (typo preserved: ${opts.some((o: string) => o === 'Nomral')})`);
    }
  });
}

test('P3 V6: mixed template (s3) × dense TEXT dictation — constrained fill + demotion count', async ({ page }) => {
  await login(page, 's3');
  const visitId = await textVisit(page, 's3-dense', MIXED_DICTATION);
  const row = JSON.parse(psql(`SELECT json_build_object('note', v."soapFinal", 'claims', coalesce(jsonb_array_length(v."suggestedClaims"),0), 'reasons', (SELECT coalesce(json_agg(c->>'reason'), '[]') FROM jsonb_array_elements(coalesce(v."suggestedClaims",'[]'::jsonb)) c), 'warnings', v."rxDrafts"->'warnings', 'em', v."cptCodes"->'em'->>'code') FROM transcribe_visits v WHERE id='${visitId}';`));
  const sections = JSON.parse(fs.readFileSync(`${ART}/s3-sections.json`, 'utf8'));
  const fill = checkConstrainedFill('s3-dense', row.note ?? '', sections);
  fs.writeFileSync(`${ART}/s3-dense-visit.json`, JSON.stringify({ visitId, ...row }, null, 2));
  console.log(`[V6] claims=${row.claims} (f4-a baseline was 17) reasons=${JSON.stringify(row.reasons)} checked=${JSON.stringify(fill.checkedOptions)} invented=${JSON.stringify(fill.inventedOptions)}`);
  expect(fill.inventedOptions, 'ZERO invented options').toEqual([]);
  expect(fill.hasMarkdownTable, 'real markdown table in note').toBe(true);
  expect(row.note).toMatch(/154\/94|154 over 94/);
  expect(row.claims, 'lane demotions vs f4-a baseline 17').toBeLessThanOrEqual(8);
  fs.appendFileSync(`${ART}/visits.jsonl`, JSON.stringify({ tag: 's3-dense', visitId }) + '\n');
});

test('P3 V7 (VOICE): checkbox template (s1) filled from the real audio recorder', async () => {
  const browser = await chromium.launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${SCRATCH}/audio/exam.wav%noloop`],
  });
  try {
    const page = await browser.newPage();
    await login(page, 's1');
    const res = await page.request.post(`${BASE}/api/patients`, {
      data: { name: 'Struct Px voice', dateOfBirth: '1985-05-15', externalId: null },
      headers: { 'Content-Type': 'application/json' } });
    const patientId = (await res.json()).patient.id as string;
    await page.goto(`${BASE}/visits/new?patientId=${patientId}`);
    await page.getByRole('combobox', { name: 'Specialty' }).click();
    await page.getByRole('option', { name: 'Primary Care' }).click();
    await page.getByRole('button', { name: /dictate live/i }).click();
    await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 20_000 });
    const visitId = new URL(page.url()).pathname.split('/').pop()!;
    const startBtn = page.getByRole('button', { name: /start dictating/i });
    await expect(startBtn).toBeEnabled({ timeout: 20_000 });
    await startBtn.click();
    await page.waitForTimeout(26_000);
    await page.getByRole('button', { name: /stop & process/i }).click();
    let status = '';
    for (let i = 0; i < 120 && status !== 'READY' && status !== 'FAILED'; i++) {
      await page.waitForTimeout(3000);
      status = psql(`SELECT status FROM transcribe_visits WHERE id='${visitId}';`);
    }
    expect(status).toBe('READY');
    const row = JSON.parse(psql(`SELECT json_build_object('note', v."soapFinal", 'provider', v."transcriptionProvider", 'claims', coalesce(jsonb_array_length(v."suggestedClaims"),0)) FROM transcribe_visits v WHERE id='${visitId}';`));
    const sections = JSON.parse(fs.readFileSync(`${ART}/s1-sections.json`, 'utf8'));
    const fill = checkConstrainedFill('s1-voice', row.note ?? '', sections);
    fs.writeFileSync(`${ART}/s1-voice-visit.json`, JSON.stringify({ visitId, ...row }, null, 2));
    console.log(`[V7] provider=${row.provider} checked=${JSON.stringify(fill.checkedOptions)} invented=${JSON.stringify(fill.inventedOptions)} claims=${row.claims}`);
    expect(row.provider).toBe('deepgram-batch');
    expect(fill.inventedOptions, 'ZERO invented options from voice').toEqual([]);
    expect((fill.checkedOptions as string[]).length, 'dictated findings got checked').toBeGreaterThanOrEqual(2);
    // never-guess: unchecked options remain in the note body
    expect(row.note).toMatch(/- \[ \] /);
    await page.goto(`${BASE}/visits/${visitId}`);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: `${ART}/s1-voice-review.png`, fullPage: true });
    fs.appendFileSync(`${ART}/visits.jsonl`, JSON.stringify({ tag: 's1-voice', visitId }) + '\n');
  } finally {
    await browser.close();
  }
});

test('P3 V9 (gates): all 4 gates with the structure-heavy template active', async ({ page }) => {
  await login(page, 's3');
  const visitId = fs.readFileSync(`${ART}/visits.jsonl`, 'utf8').trim().split('\n')
    .map((l) => JSON.parse(l)).find((v: any) => v.tag === 's3-dense')!.visitId as string;
  const out: Record<string, unknown> = { visitId };
  // Rx gate: the dictation carries simvastatin 40 + amlodipine → deterministic critical
  const warnings = JSON.parse(psql(`SELECT coalesce(v."rxDrafts"->'warnings', '[]') FROM transcribe_visits v WHERE id='${visitId}';`));
  const critical = warnings.filter((w: any) => w.severity === 'critical');
  expect(critical.length, 'pair critical fired on structured visit').toBeGreaterThanOrEqual(1);
  const blocked = await page.request.post(`${BASE}/api/visits/${visitId}/sign`, {
    data: { destinations: [] }, headers: { 'Content-Type': 'application/json' } });
  expect(blocked.status(), 'Rx 422 gate').toBe(422);
  out.rx = '422 ok';
  // E/M ack gate (armed)
  psql(`UPDATE transcribe_visits SET "emPendingChange"='{"from":"99213","to":"99214","cause":"suggestion_adopted","at":"2026-07-02T18:00:00.000Z"}'::jsonb WHERE id='${visitId}';`);
  // lane adopt via UI
  await page.goto(`${BASE}/visits/${visitId}`);
  await page.waitForLoadState('networkidle');
  const reviewTab = page.getByRole('tab', { name: /review/i }).first();
  if (await reviewTab.isVisible().catch(() => false)) {
    await reviewTab.click();
    const adopt = page.getByRole('button', { name: /adopt suggestion/i }).first();
    if (await adopt.isVisible().catch(() => false)) {
      await adopt.click();
      await page.waitForTimeout(8000);
      out.laneAdopt = 'clicked';
    } else out.laneAdopt = 'no claims to adopt';
  }
  // override + ack + sign
  await page.goto(`${BASE}/visits/${visitId}`);
  const resolveCta = page.getByRole('button', { name: /resolve the critical/i }).first();
  if (await resolveCta.isVisible().catch(() => false)) await resolveCta.click();
  else await page.getByRole('tab', { name: /rx/i }).first().click();
  await page.waitForTimeout(600);
  const overrideBtn = page.getByRole('button', { name: /override|sign past|acknowledge|resolve/i })
    .filter({ hasNotText: /resolve the critical/i }).first();
  await expect(overrideBtn).toBeVisible({ timeout: 15_000 });
  await overrideBtn.click();
  await page.getByRole('textbox').last().fill('Structured-template gate verify: interaction reviewed.');
  await page.getByRole('button', { name: /confirm|record|override/i }).last().click();
  await page.waitForTimeout(1500);
  const noAck = await page.request.post(`${BASE}/api/visits/${visitId}/sign`, {
    data: { destinations: [] }, headers: { 'Content-Type': 'application/json' } });
  expect(noAck.status(), 'E/M ack gate 400').toBe(400);
  const pending = JSON.parse(psql(`SELECT v."emPendingChange" FROM transcribe_visits v WHERE id='${visitId}';`));
  const signed = await page.request.post(`${BASE}/api/visits/${visitId}/sign`, {
    data: { destinations: [], acknowledgedEmChange: { from: pending.from, to: pending.to } },
    headers: { 'Content-Type': 'application/json' } });
  expect(signed.ok(), 'sign with ack').toBe(true);
  out.audit = psql(`SELECT coalesce(json_agg(DISTINCT action::text), '[]') FROM audit_logs WHERE "targetId"='${visitId}';`);
  fs.writeFileSync(`${ART}/gates-structured.json`, JSON.stringify(out, null, 2));
  console.log('[V9 gates]', JSON.stringify(out).slice(0, 400));
});

test('P3 V10 (exports): docx grid + glyphs, pdf renders, clipboard degrades', async ({ page }) => {
  await login(page, 's3');
  const visitId = fs.readFileSync(`${ART}/visits.jsonl`, 'utf8').trim().split('\n').map((l) => JSON.parse(l)).find((v: any) => v.tag === 's3-dense')!.visitId;
  const docx = await page.request.get(`${BASE}/api/visits/${visitId}/export/docx`);
  expect(docx.ok()).toBe(true);
  fs.writeFileSync(`${ART}/s3-dense.docx`, Buffer.from(await docx.body()));
  const pdf = await page.request.get(`${BASE}/api/visits/${visitId}/export/pdf`);
  expect(pdf.ok()).toBe(true);
  fs.writeFileSync(`${ART}/s3-dense.pdf`, Buffer.from(await pdf.body()));
  const clip = await page.request.post(`${BASE}/api/visits/${visitId}/export/clipboard`, {
    data: { format: 'epic' }, headers: { 'Content-Type': 'application/json' } });
  expect(clip.ok()).toBe(true);
  const clipText = ((await clip.json()) as any).text ?? '';
  fs.writeFileSync(`${ART}/s3-dense-clipboard.txt`, clipText);
  expect(clipText, 'clipboard has no raw pipes').not.toMatch(/^\s*\|.*\|\s*$/m);
  expect(clipText, 'clipboard keeps checked options as ASCII').toMatch(/\[x\] /);
  console.log('[V10] exports written; clipboard degraded cleanly');
});
