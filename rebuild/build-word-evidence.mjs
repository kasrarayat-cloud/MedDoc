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

/** Django rejects a cross-site POST without its token; `page.request` does not add one.
 *
 * ⚠️ READ IT FROM THE RENDERED FORM, NOT FROM A COOKIE NAMED `csrftoken`. This deployment renames the
 * cookie per surface — `CSRF_COOKIE_NAME` is `quillmd_doctor_csrf` on the doctor service and
 * `quillmd_admin_csrf` on the admin one — so looking for the Django default finds nothing and reports it
 * as "the session is not established", which is a true sentence about the wrong thing. The hidden input
 * that `{% csrf_token %}` renders is correct whatever the cookie is called, and correct under
 * `CSRF_USE_SESSIONS` too, where no cookie exists at all.
 */
async function csrf(page) {
  const field = page.locator('input[name=csrfmiddlewaretoken]').first();
  if (await field.count()) {
    const value = await field.inputValue();
    if (value) return value;
  }
  const cookies = await page.context().cookies(base);
  const token = cookies.find(c => /csrf/i.test(c.name) && c.value);
  assert(token, 'no CSRF token in the page or the cookie jar; the session is not established');
  return token.value;
}

async function login(page, account) {
  await page.goto(base + '/login/');
  await page.locator('[name=email]').fill(account.email);
  await page.locator('[name=password]').fill(account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.waitForURL(base + '/');
}

/** Fill every mapped field according to its KIND, review everything, save and finalize.
 *
 * ⚠️ THIS DRIVES THE RENDERED FORM RATHER THAN POSTING A HAND-BUILT BODY, and the first two attempts are
 * why. A hand-built POST missed the CSRF token, then read it from a cookie whose name this deployment
 * changes per surface, and then posted a revision taken from the FIRST of three `[name=revision]` inputs
 * on the page — a different form's. It also omitted the 14 `claim_reviewed_*` boxes entirely, so finalize
 * refused with "cannot authorize signing" and the encounter sat at `review`. Every one of those is a
 * detail of the page that the page already knows. `private-beta-browser.mjs` has driven this form
 * correctly for months; this follows it.
 */
async function completeAndFinalize(page, encounterId, mode, mapping) {
  await page.goto(`${base}/encounters/${encounterId}/`);
  for (const field of mapping.fields) {
    const control = page.locator(`[name="answer_${field.key}"]`).first();
    if (!(await control.count())) continue;
    const isSelect = await control.evaluate(node => node.tagName === 'SELECT');
    if (mode === 'missing') {
      // Every answer left empty, and every one of them still reviewed: "reviewed as missing".
      if (isSelect) await control.selectOption('');
      else await control.fill('');
      continue;
    }
    if (isSelect) {
      // ⚠️ A DROPDOWN GETS A VALID ORIGINAL OPTION. One that accepted arbitrary text would be the defect,
      // not the demonstration.
      const options = await control.locator('option').evaluateAll(nodes =>
        nodes.map(o => o.value).filter(v => v));
      assert(options.length, `no options offered for ${field.key}`);
      await control.selectOption(options[0]);
    } else if (field.kind === 'measurement') {
      await control.fill('4.25');            // numeric field: a valid number, not long text
    } else if (field.key.startsWith('location_') || field.key === 'patient_name') {
      await control.fill(LONG);              // the supported free-text and table-location cells
    } else {
      await control.fill('SYNTHETIC');
    }
  }
  for (const box of await page.locator('input[name^=reviewed_]').all()) await box.check();
  // ⚠️ THE 14 PREWRITTEN ASSERTIONS ARE A SEPARATE REVIEW, AND CHECKING THE BOX IS NOT ENOUGH.
  // `save_answers` runs each one through `source_quote_evidence`, which demands a COMPLETE SOURCE LINE
  // from the notes for that exact label; a claim it cannot evidence is forced back to reviewed=false and
  // the whole review is recorded `complete=False`, which the finalization helper then refuses. Four
  // attempts read that refusal as a form problem. It is the application being right: a statement nobody
  // can point at in the notes has not been reviewed.
  //
  // So the variant carries the truth instead of a quotation. These synthetic notes document none of the
  // prewritten findings, and most claims offer exactly that answer — `not_documented` or `not_assessed`.
  // Those need no evidence because they assert none. `trusted` claims (signer identity, signature
  // timestamp, interpreting physician) are server-supplied and are left as rendered.
  for (const select of await page.locator('select[name^=claim_variant_]').all()) {
    const options = await select.locator('option').evaluateAll(nodes => nodes.map(o => o.value));
    const honest = ['not_documented', 'not_assessed', 'none'].find(v => options.includes(v));
    if (honest) await select.selectOption(honest);
  }
  for (const box of await page.locator('input[name^=claim_reviewed_]').all()) await box.check();
  await page.getByRole('button', { name: 'Save answers and review decisions', exact: true }).click();
  await page.waitForLoadState();
  await page.locator('[name=reviewed]').check();
  await page.getByRole('button', { name: 'Finalize document', exact: true }).click();
  await page.waitForLoadState();
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
        + "existing=Encounter.objects.filter(template_version=tv,status__in=['draft','review'],notes=payload['notes']).order_by('created_at').first()\n"
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
