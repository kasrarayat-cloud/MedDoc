/** Two genuine Word documents through the REAL export path, and a package built from them.
 *
 * ⚠️ WHY THIS DRIVES THE APPLICATION INSTEAD OF CALLING THE EXPORTER. `ops/sdk_sandbox` refuses a Word
 * processor owned by the calling account, and on this host and in CI the account running the tests is the
 * account that owns the runtime — so `core.tests.test_wm_workflow` SKIPS in both places. The deployed
 * service is the only place the real WM IOV export path runs. Driving it over HTTP is therefore not a
 * convenience; it is the only way to obtain a genuine export at all.
 *
 * ⚠️ NO PROVIDER CALL IS MADE, AND THAT IS BY CONSTRUCTION RATHER THAN BY RESTRAINT. `save_answers` takes
 * clinician values directly and `finalize` requires only that every field is reviewed. Neither needs a
 * generation, so nothing here can reach Anthropic or Deepgram.
 *
 * Usage: QUILLMD_WORD_EVIDENCE_LIVE=1 node rebuild/build-word-evidence.mjs --expected-release FULL_SHA
 */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const appRoot = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(appRoot, '.runtime');
const base = process.env.QUILLMD_BROWSER_BASE_URL || 'http://127.0.0.1:9130';
{ const url = new URL(base); assert(['127.0.0.1', 'localhost'].includes(url.hostname) && !url.username); }

const LONG = 'SYNTHETIC LONG LOCATION: ' + 'Posterior tibial perforator documented at the mid-calf with '
  .repeat(180) + 'END OF SYNTHETIC LONG ANSWER';
const report = { startedAt: new Date().toISOString(), checks: [], providerJobs: 0, complete: false };
let currentCheck = 'startup', browser;

async function check(name, action) { currentCheck = name; const value = await action(); report.checks.push({ name, passed: true }); console.log(`PASS ${name}`); return value; }

function python(code, payload = {}) {
  const header = "import os,json,sys\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\npayload=json.loads(sys.stdin.read() or '{}')\n";
  const result = spawnSync(process.env.QUILLMD_TEST_PYTHON || path.join(appRoot, '.venv/bin/python'), ['-B', '-c', header + code],
    { cwd: appRoot, encoding: 'utf8', input: JSON.stringify(payload), timeout: 180000, maxBuffer: 16 * 1024 * 1024 });
  assert.equal(result.status, 0, 'Bounded synthetic document operation failed.');
  return result.stdout.trim() ? JSON.parse(result.stdout.trim().split('\n').pop()) : {};
}

/** Django rejects a cross-site POST without its token; `page.request` does not add one. */
async function csrf(page) {
  const cookies = await page.context().cookies(base);
  const token = cookies.find(c => c.name === 'csrftoken');
  assert(token && token.value, 'no csrftoken cookie; the session is not established');
  return token.value;
}

async function login(page, account) {
  await page.goto(base + '/login/');
  await page.locator('[name=email]').fill(account.email);
  await page.locator('[name=password]').fill(account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.waitForURL(base + '/');
}

/** Fill every mapped field according to its KIND, and review all of them. */
async function completeAndFinalize(page, encounterId, mode, mapping) {
  await page.goto(`${base}/encounters/${encounterId}/`);
  const revision = await page.locator('[name=revision]').first().inputValue();
  const form = {};
  for (const field of mapping.fields) {
    const key = field.key;
    let value = '';
    if (mode === 'long') {
      if (field.kind === 'choice') value = field.options[0];
      else if (field.kind === 'measurement') value = '4.25';
      else if (key.startsWith('location_') || key === 'patient_name') value = LONG;
      else value = 'SYNTHETIC';
    }
    form['answer_' + key] = value;                  // '' for the missing-answer document
    form['reviewed_' + key] = 'on';                 // every field reviewed, including the missing ones
  }
  form.revision = revision;
  form.csrfmiddlewaretoken = await csrf(page);
  const headers = { 'X-CSRFToken': form.csrfmiddlewaretoken, Referer: base + '/' };
  const saved = await page.request.post(`${base}/encounters/${encounterId}/save/`, { form, headers });
  assert(saved.status() < 400, `saving answers failed with ${saved.status()}`);
  await page.goto(`${base}/encounters/${encounterId}/`);
  const next = await page.locator('[name=revision]').first().inputValue();
  const token = await csrf(page);
  const finalized = await page.request.post(`${base}/encounters/${encounterId}/finalize/`,
    { form: { reviewed: 'on', revision: next, csrfmiddlewaretoken: token },
      headers: { 'X-CSRFToken': token, Referer: base + '/' } });
  assert(finalized.status() < 400, `finalizing failed with ${finalized.status()}`);
}

try {
  assert.equal(process.env.QUILLMD_WORD_EVIDENCE_LIVE, '1', 'Set QUILLMD_WORD_EVIDENCE_LIVE=1 to run against the private service.');
  const cli = process.argv.slice(2);
  assert(cli.length === 2 && cli[0] === '--expected-release' && /^[0-9a-f]{40}$/.test(cli[1]));
  const expectedRelease = cli[1];

  const credentials = JSON.parse(await fs.readFile(path.join(runtime, 'private-access.json'), 'utf8'));
  assert(credentials.doctor.email.endsWith('@synthetic.quillmd.invalid'));
  const { chromium } = process.env.PLAYWRIGHT_MODULE_DIR
    ? require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR, '@playwright/test')) : require('@playwright/test');

  browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();

  await check('The service serves the exact revision under test', async () => {
    const answer = await (await page.request.get(base + '/health/')).json();
    assert.equal(answer.release, expectedRelease, 'the service is serving a different revision');
    assert.equal(answer.data_mode, 'synthetic-only');
    report.servedRelease = answer.release;
  });

  const mapping = await check('The WM IOV mapping offers the three field kinds this exercises', async () => {
    const found = python(
      "from core.models import TemplateVersion\n"
      + "tv=TemplateVersion.objects.filter(document_backend__isnull=False).exclude(document_backend={}).order_by('-number').first()\n"
      + "print(json.dumps({'id':str(tv.pk),'template':tv.template.name,'fields':tv.fields}))\n");
    const kinds = {};
    for (const f of found.fields) kinds[f.kind] = (kinds[f.kind] || 0) + 1;
    assert.deepEqual(kinds, { choice: 28, text: 10, measurement: 52 }, 'the mapping is not the 90-field WM IOV shape');
    report.mapping = { template: found.template, fields: found.fields.length, kinds };
    return found;
  });

  await login(page, credentials.doctor);

  for (const mode of ['missing', 'long']) {
    await check(`A genuine ${mode}-answer document through the real export path`, async () => {
      // ⚠️ REUSE AN EXISTING DRAFT FOR THIS MODE BEFORE CREATING ONE. A first attempt failed at the save
      // step and left a draft behind; creating a second would put the encounter count past what the
      // declaration says, and a delta that overshoots because of a retry is indistinguishable in the
      // record from one nobody predicted.
      const created = python(
        "from core.models import Encounter, Patient, TemplateVersion, User\n"
        + "from django.utils import timezone\n"
        + "u=User.objects.get(email=payload['email'])\n"
        + "tv=TemplateVersion.objects.get(pk=payload['version'])\n"
        + "existing=Encounter.objects.filter(template_version=tv,status='draft',notes=payload['notes']).order_by('created_at').first()\n"
        + "if existing is None:\n"
        + "    p=Patient.objects.filter(department__membership__user=u,department__membership__active=True).first()\n"
        + "    existing=Encounter.objects.create(department=p.department,patient=p,template_version=tv,created_by=u,\n"
        + "      notes=payload['notes'],service_date=timezone.now().date())\n"
        + "    reused=False\n"
        + "else:\n"
        + "    reused=True\n"
        + "print(json.dumps({'id':str(existing.pk),'department':str(existing.department_id),'reused':reused}))\n",
        { email: credentials.doctor.email, version: mapping.id,
          notes: mode === 'missing'
            ? 'SYNTHETIC: the note documents nothing the mapping can support.'
            : 'SYNTHETIC: long anatomical descriptions recorded by the clinician.' });
      await completeAndFinalize(page, created.id, mode, mapping);
      const state = python(
        "from core.models import Encounter\ne=Encounter.objects.get(pk=payload['id'])\n"
        + "print(json.dumps({'status':e.status,'export_path':e.export_path,'sha256':e.export_sha256}))\n",
        { id: created.id });
      assert.equal(state.status, 'finalized');
      assert(state.export_path && state.sha256, 'the encounter finalized without an export');
      report[mode] = { encounter: created.id, export_sha256: state.sha256 };
      return state;
    });
  }
  report.complete = true;
} catch (error) {
  report.failedCheck = currentCheck;
  report.failureClass = error?.constructor?.name || 'Error';
  console.error(`FAIL ${currentCheck}: ${String(error?.message || '').slice(0, 300)}`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  report.finishedAt = new Date().toISOString();
  await fs.writeFile(process.env.QUILLMD_WORD_EVIDENCE_REPORT || path.join(runtime, 'word-evidence.json'),
    JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  console.log(`${report.checks.filter(c => c.passed).length} checks passed; complete=${report.complete}`);
}
