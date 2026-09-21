/** Real synthetic browser exports. Existing records are only changed through authenticated UI forms.
 * Database access below is read-only; no provider request or direct finalization is available here.
 * Every attempt gets a new report directory, including failed attempts. */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { scenario } from './word-evidence-scenarios.mjs';
const appRoot = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
function option(name, fallback) { const i = args.indexOf(name); return i < 0 ? fallback : args[i + 1]; }
const base = option('--base', 'http://127.0.0.1:9130');
const expected = option('--expected-release');
const artifact = path.resolve(option('--artifacts'));
const credentialsPath = path.resolve(option('--credentials'));
const dbEnv = path.resolve(option('--db-env'));
let ids = (option('--reuse', '')).split(',').filter(Boolean);
const create = args.includes('--create-candidate-drafts');
const url = new URL(base);
assert(['localhost', '127.0.0.1'].includes(url.hostname) && !url.username && !url.password);
assert(/^[a-f0-9]{40}$/.test(expected));
assert(ids.length === 2 || (create && !['9130', '9131'].includes(url.port)));
assert(ids.every(id => /^[a-f0-9-]{36}$/.test(id)));
assert(artifact.includes('/rebuild/.runtime/'));
await fs.mkdir(artifact, { mode: 0o700 }); // no recursive overwrite: prior attempts survive
const report = {startedAt: new Date().toISOString(), candidateRevision: expected, base,
  scope: create ? 'isolated candidate' : 'served private application', checks: [], complete: false,
  providerRequests: 0, directDatabaseWrites: 0, nativeWordAcceptance: 'pending'};
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
let current = 'startup', browser;
async function check(name, action) {
  current = name; const result = await action(); report.checks.push({name, passed: true});
  await fs.writeFile(path.join(artifact, 'report.json'), JSON.stringify(report, null, 2) + '\n', {mode:0o600});
  console.log('PASS ' + name); return result;
}
const credentials = JSON.parse(await fs.readFile(credentialsPath, 'utf8'));
assert(credentials.doctor.email.endsWith('@synthetic.quillmd.invalid'));
const PYTHON = `import os,json,sys,hashlib\nfrom pathlib import Path\nfrom dotenv import dotenv_values\npayload=json.loads(sys.stdin.read())\nconfig=Path(payload['env'])\nassert config.stat().st_mode & 0o077 == 0\nfor k,v in dotenv_values(config).items():\n if v is not None: os.environ[k]=v\nos.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'\nimport django\ndjango.setup()\nfrom django.db import connection\nfrom django.db.models import Sum\nfrom core.models import Encounter,TemplateVersion,User,Job,Usage,ProviderReceipt,Wallet,Reservation,LedgerEntry,Patient,Template,Department,Invitation,AuditEvent\nwith connection.cursor() as c: c.execute('SET default_transaction_read_only=on')\nu=User.objects.get(email=payload['email'])\nids=payload['ids']\nrows=list(Encounter.objects.filter(pk__in=ids).select_related('template_version__template'))\nassert len(rows)==len(ids)\nfor e in rows:\n assert e.department.membership_set.filter(user=u,active=True).exists()\nversions=TemplateVersion.objects.filter(template__department__membership__user=u,template__department__membership__active=True,document_backend__backend='wm-iov-foss-v2')\nv=rows[0].template_version if rows else versions.order_by('-created_at').first()\nif rows: assert all(e.template_version_id==v.pk for e in rows)\nsummary={'counts':{m.__name__:m.objects.count() for m in [Encounter,Job,Usage,ProviderReceipt,Wallet,Reservation,LedgerEntry,Patient,Template,User,Department,Invitation]},'charged':str(Usage.objects.aggregate(v=Sum('charged_cost'))['v'] or 0),'cost':str(Usage.objects.aggregate(v=Sum('actual_cost'))['v'] or 0),'wallets':list(Wallet.objects.order_by('pk').values('id','balance','reserved','kind')),'finalized':list(Encounter.objects.filter(status='finalized').order_by('pk').values('id','export_path','export_sha256')),'audit_count':AuditEvent.objects.count()}\nresult={'snapshot':summary,'mapping':None if v is None else {'id':str(v.pk),'template_id':str(v.template_id),'original_sha256':v.template.sha256,'fields':v.fields,'requirements':v.review_requirements},'encounters':{str(e.pk):{'status':e.status,'revision':e.revision,'notes':e.notes,'answers':e.answers,'review':e.template_review,'export_path':e.export_path,'export_sha256':e.export_sha256} for e in rows}}\nprint(json.dumps(result,default=str))\n`;
function readState() {
  const result = spawnSync(process.env.QUILLMD_TEST_PYTHON || '/opt/meddoc-pro/rebuild/.venv/bin/python',
    ['-B', '-c', PYTHON], {cwd:appRoot, input:JSON.stringify({env:dbEnv,email:credentials.doctor.email,ids}),
      encoding:'utf8', timeout:30000, maxBuffer:4*1024*1024});
  assert.equal(result.status, 0, 'Read-only evidence lookup failed; inspect private diagnostic');
  return JSON.parse(result.stdout);
}
async function save(page) {
  await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();
  await page.waitForLoadState('domcontentloaded');
}
async function editNotes(page, id, notes) {
  await page.goto(`${base}/encounters/${id}/`);

  await page.locator('#source-notes-edit').fill(notes);
  await page.getByRole('button',{name:'Save source notes',exact:true}).click();
  await page.waitForLoadState('domcontentloaded');
  const state=readState().encounters[id];
  assert.equal(state.notes.replace(/\r\n/g,'\n'),notes);
  return state;
}
async function answersAndVariants(page, mapping, input, reviewed) {
  for (const field of mapping.fields) {
    const control=page.locator(`[name="answer_${field.key}"]`);
    assert.equal(await control.count(),1,'Missing mapped control '+field.key);
    if (field.kind==='choice') await control.selectOption(input.values[field.key]);
    else await control.fill(input.values[field.key]);
    await page.locator(`[name="source_${field.key}"]`).fill(input.fieldQuotes[field.key]);
    await page.locator(`[name="reviewed_${field.key}"]`).setChecked(reviewed);
  }
  for (const row of mapping.requirements) {
    const select=page.locator(`select[name="claim_variant_${row.key}"]`);
    if (await select.count()) await select.selectOption(input.variants[row.key]);
    else assert.equal(await page.locator(`[name="claim_variant_${row.key}"]`).inputValue(),input.variants[row.key]);
    if (row.kind==='assertion') {
      const quote=page.locator(`[name="claim_source_${row.key}"]`);
      if (reviewed) {
        const actual=await quote.locator('xpath=..').locator('.answer-text').innerText();
        assert.equal(actual.replace(/\s+/g,' ').trim(),input.statements[row.key].replace(/\s+/g,' ').trim(),
          'Displayed statement differs from the supported source for '+row.key);
      }
      await quote.fill(input.statementQuotes[row.key]);
    }
    await page.locator(`[name="claim_reviewed_${row.key}"]`).setChecked(reviewed);
  }
}
async function finish(page,id,mapping,input,refuse=false) {
  await answersAndVariants(page,mapping,input,false);
  await save(page); // materialize chosen wording before signing its displayed token
  await answersAndVariants(page,mapping,input,true);
  await save(page);
  const saved=readState().encounters[id];
  if (!refuse) assert.equal(saved.review.assessment?.complete,true,'Clinical review incomplete');
  await page.locator('#final-review').check();
  await page.getByRole('button',{name:'Finalize document',exact:true}).click();
  await page.waitForLoadState('domcontentloaded');
  const final=readState().encounters[id];
  if (refuse) {
    assert.notEqual(final.status,'finalized');assert.equal(final.export_sha256,'');
    assert(final.review.assessment?.blockers.length>0);
    const refused=await page.request.get(`${base}/encounters/${id}/export/`);
    assert.equal(refused.status(),404);
    const evidence={encounter:id,finalizationRefused:true,exportStatus:404,revision:final.revision,
      missingAnswers:Object.values(final.answers).filter(a=>!a.text).length,
      blockers:final.review.assessment.blockers,notesSha256:hash(final.notes)};
    await fs.writeFile(path.join(artifact,'all-missing-refusal.json'),JSON.stringify(evidence,null,2)+'\n',{mode:0o600});
    return evidence;
  }
  assert.equal(final.status,'finalized');assert(final.export_sha256);
  const downloaded=await page.request.get(`${base}/encounters/${id}/export/`);
  assert.equal(downloaded.status(),200);
  const bytes=await downloaded.body();assert.equal(hash(bytes),final.export_sha256);
  for (const field of mapping.fields) {
    const answer=final.answers[field.key];assert.equal(answer.text,input.values[field.key]);
    assert.equal(answer.reviewed,true);assert.equal(answer.review_revision,final.revision);
    for (const item of answer.evidence) assert.equal([...final.notes].slice(item.start,item.end).join(''),item.quote);
    if (answer.text) assert(answer.evidence.length>0);
  }
  for (const decision of Object.values(final.review.decisions)) {
    assert.equal(decision.reviewed,true);
    for (const item of decision.evidence) assert.equal([...final.notes].slice(item.start,item.end).join(''),item.quote);
  }
  const file=`${input.mode}-genuine-application-export.docx`;
  await fs.writeFile(path.join(artifact,file),bytes,{mode:0o600});
  const detail={encounter:id,revision:final.revision,filename:file,bytes:bytes.length,
    downloadedSha256:hash(bytes),recordedSha256:final.export_sha256,
    originalSha256:mapping.original_sha256,missingAnswers:input.missing,
    longestMappedAnswer:input.longestMappedAnswer,reviewComplete:true,explicitReviewedFields:90,
    explicitReviewedStatements:14,providerCalls:0,servedRelease:expected};
  await fs.writeFile(path.join(artifact,`${input.mode}-review-evidence.json`),
    JSON.stringify({detail,source:final.notes,answers:final.answers,review:final.review},null,2)+'\n',{mode:0o600});
  return detail;
}
try {
  const {chromium}=process.env.PLAYWRIGHT_MODULE_DIR ?
    require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,'@playwright/test')) : require('@playwright/test');
  browser=await chromium.launch();const context=await browser.newContext();const page=await context.newPage();
  await context.route('**/*',route=>{
    const request=route.request();
    if (request.method()==='POST' && /\/(generate|voice|coding|payments|checkout)\//.test(new URL(request.url()).pathname)) {
      report.providerRequests++;return route.abort('blockedbyclient');
    }
    return route.continue();
  });
  await check('Actual HTTP revision and synthetic-only release gate',async()=>{
    const health=await (await page.request.get(base+'/health/')).json();
    assert.equal(health.release,expected);assert.equal(health.data_mode,'synthetic-only');report.servedRelease=health.release;
  });
  await check('Synthetic doctor authenticates',async()=>{
    await page.goto(base+'/login/');await page.locator('[name=email]').fill(credentials.doctor.email);
    await page.locator('[name=password]').fill(credentials.doctor.password);
    await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL(base+'/');
  });
  if (create) {
    await check('Candidate uploads the unchanged original through the interface',async()=>{
      await page.goto(base+'/templates/upload/');
      await page.locator('[name=name]').fill('SYNTHETIC genuine Word export verification');
      const departments=await page.locator('[name=department] option').evaluateAll(ns=>ns.map(n=>n.value).filter(Boolean));
      await page.locator('[name=department]').selectOption(departments[0]);
      await page.locator('[name=file]').setInputFiles(path.resolve(appRoot,'../WM IOV Template.docx'));
      await page.locator('[name=synthetic_only]').check();
      await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();await page.waitForLoadState();
    });
    const mapping=readState().mapping;assert(mapping);
    for (const mode of ['partial','long']) {
      await page.goto(base+'/encounters/new/');
      const patients=await page.locator('[name=patient] option').evaluateAll(ns=>ns.map(n=>n.value).filter(Boolean));
      await page.locator('[name=patient]').selectOption(patients[0]);
      await page.locator('[name=template_version]').selectOption(mapping.id);
      await page.locator('[name=notes]').fill('SYNTHETIC: the note documents nothing the mapping can support.');
      await page.locator('[name=service_date]').fill(new Date().toISOString().slice(0,10));
      await page.locator('[name=synthetic_only]').check();
      await page.getByRole('button',{name:'Create document',exact:true}).click();
      await page.waitForURL(/\/encounters\/[a-f0-9-]+\/$/);ids.push(page.url().split('/').at(-2));
    }
  }
  report.encounterIds=ids;
  const before=readState();const mapping=before.mapping;
  assert.equal(mapping.fields.length,90);assert.equal(mapping.requirements.length,14);
  assert(Object.values(before.encounters).every(e=>['draft','review'].includes(e.status)));
  report.before=before.snapshot;
  await fs.writeFile(path.join(artifact,'prior-draft-state.json'),JSON.stringify(before,null,2)+'\n',{mode:0o600});
  const priorBytes=await check('Read actual prior finalized downloads before changing the two drafts',async()=>{
    const result=[];
    for (const old of before.snapshot.finalized) {
      const response=await page.request.get(`${base}/encounters/${old.id}/export/`);
      if (response.status()===404) {
        result.push({id:old.id,scope:'not accessible to this clinician; recorded metadata checked only'});
        continue;
      }
      assert.equal(response.status(),200);
      const bytes=await response.body();assert.equal(hash(bytes),old.export_sha256);
      result.push({id:old.id,bytes:bytes.length,sha256:hash(bytes)});
    }
    report.priorDownloads=result;return result;
  });
  await check('All-missing source is refused without an export',async()=>{
    const input=scenario(mapping,'unsupported-missing');await editNotes(page,ids[0],input.notes);
    report.allMissing=await finish(page,ids[0],mapping,input,true);
  });
  for (const [index,mode] of ['partial','long'].entries()) {
    await check(`Genuine ${mode} mapped answers: source, review, finalize, storage and download hash`,async()=>{
      const input=scenario(mapping,mode);await editNotes(page,ids[index],input.notes);
      report[mode]=await finish(page,ids[index],mapping,input);
    });
  }
  await check('Original download remains byte-identical',async()=>{
    const response=await page.request.get(`${base}/templates/${mapping.template_id}/original/`);
    assert.equal(response.status(),200);const bytes=await response.body();assert.equal(hash(bytes),mapping.original_sha256);
    await fs.writeFile(path.join(artifact,'original-blank-WM-IOV-Template.docx'),bytes,{mode:0o600});
    report.original={filename:'original-blank-WM-IOV-Template.docx',bytes:bytes.length,sha256:hash(bytes)};
  });
  await check('No provider jobs, charges or prior finalized metadata changed; accessible export bytes match',async()=>{
    const after=readState().snapshot;report.after=after;
    assert.deepEqual(after.counts,before.snapshot.counts);
    for (const key of ['charged','cost','wallets']) assert.deepEqual(after[key],before.snapshot[key]);
    const prior=after.finalized.filter(e=>!ids.includes(e.id));assert.deepEqual(prior,before.snapshot.finalized);
    for (const old of priorBytes.filter(row=>row.sha256)) {
      const response=await page.request.get(`${base}/encounters/${old.id}/export/`);
      assert.equal(response.status(),200);const bytes=await response.body();
      assert.equal(bytes.length,old.bytes);assert.equal(hash(bytes),old.sha256);
    }
    assert.equal(after.finalized.length,before.snapshot.finalized.length+2);
    assert.equal(report.providerRequests,0);assert(after.audit_count>before.snapshot.audit_count);
  });
  report.complete=true;
} catch(error) {
  report.failedStage=current;report.failureClass=error.constructor.name;
  report.failureMessage=String(error.message).slice(0,300);
  console.error('FAIL '+current+': '+report.failureMessage);process.exitCode=1;
} finally {
  if (browser) await browser.close();report.finishedAt=new Date().toISOString();
  await fs.writeFile(path.join(artifact,'report.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  console.log(`Report: ${artifact}/report.json; complete=${report.complete}`);
}
