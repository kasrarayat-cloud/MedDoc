// Bounded installed, synthetic-only upload/review/export. No generation or provider calls.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {chromium} from '/opt/meddoc-pro/node_modules/@playwright/test/index.mjs';

process.umask(0o077);
const revision=process.argv[2];
assert.match(revision??'',/^[a-f0-9]{40}$/);
assert(process.env.RULED_MUTATION_DECLARATION?.endsWith('/20260921-quillmd-colonoscopy-compatibility.md'));
const base='http://127.0.0.1:9130';
const root='/opt/meddoc-pro/rebuild/.runtime/colonoscopy-compatibility-20260921';
const out=root+'/installed-browser';
const source=root+'/originals/Colonoscopy_Operative_Template.docx';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const expected='8ae1e2b0ebeec317c038b8bfeed6a0824055f44d689c039ab450404593f2815a';
const original=await fs.readFile(source);assert.equal(original.length,38393);assert.equal(sha(original),expected);
const input=JSON.parse(await fs.readFile(root+'/browser-input.json','utf8'));
assert.equal(input.synthetic_only,true);assert.equal(input.fields.length,24);
assert.deepEqual(Object.keys(input.scenarios).sort(),['concise','long','missing']);
const creds=JSON.parse(await fs.readFile('/opt/meddoc-pro/rebuild/.runtime/private-access.json','utf8'));
assert(creds.doctor.email.endsWith('@synthetic.quillmd.invalid'));
await fs.mkdir(out,{mode:0o700}); // A previous attempt requires inspection, never blind replay.
delete process.env.DEBUG;delete process.env.PWDEBUG;
const report={complete:false,revision,source_sha256:expected,started_at:new Date().toISOString(),
  synthetic_only:true,provider_calls:0,generation_used:false,scenarios:[],blocked_requests:[]};
let phase=0;
const checkpoint=async()=>fs.writeFile(out+`/phase-${String(phase++).padStart(2,'0')}.json`,JSON.stringify(report,null,2)+'\n',{mode:0o600,flag:'wx'});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext();
await context.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.origin!==base||/\/(generate|voice|coding)\//.test(u.pathname)||/^\/(billing|register|recover)/.test(u.pathname)){
    report.blocked_requests.push({origin:u.origin,path:u.pathname});return route.abort();
  }
  return route.continue();
});
const download=async(page,link,name)=>{
  const pending=page.waitForEvent('download');await link.click();const d=await pending;
  const path=out+'/'+name;await d.saveAs(path);await fs.chmod(path,0o600);
  assert.equal(await d.failure(),null);const bytes=await fs.readFile(path);
  assert.equal(bytes.subarray(0,2).toString(),'PK');
  return {path,bytes:bytes.length,sha256:sha(bytes)};
};
try{
  const h=await context.request.get(base+'/health/');const health=await h.json();
  assert.equal(health.release,revision);assert.equal(health.data_mode,'synthetic-only');report.health=health;
  const p=await context.newPage();await p.goto(base+'/login/');
  await p.locator('[name=email]').fill(creds.doctor.email);await p.locator('[name=password]').fill(creds.doctor.password);
  await p.getByRole('button',{name:'Sign in',exact:true}).click();await p.waitForURL(base+'/');
  await p.goto(base+'/templates/upload/');await p.locator('[name=name]').fill('Synthetic Colonoscopy original compatibility');
  const departments=await p.locator('[name=department] option').evaluateAll(a=>a.map(x=>({label:x.textContent,value:x.value})));
  const department=departments.filter(x=>x.label.includes('X-ray'));assert.equal(department.length,1);
  await p.locator('[name=department]').selectOption(department[0].value);
  await p.locator('[name=file]').setInputFiles(source);await p.locator('[name=synthetic_only]').check();
  await p.getByRole('button',{name:'Upload and inspect form',exact:true}).click();
  await p.waitForURL(/\/templates\/[a-f0-9-]{36}\/$/);
  report.template_id=p.url().split('/').at(-2);report.mapping_v1_url=p.url();await checkpoint();
  assert.equal(await p.locator('tbody tr').count(),24);
  const visible=await p.locator('body').innerText();
  for(const field of input.fields)assert(visible.includes(field.label));
  assert(visible.includes('Confirm that these consecutive answer lines belong to one question.'));
  report.original_download=await download(p,p.getByRole('link',{name:'Download original',exact:true}),'original-authenticated.docx');
  assert.equal(report.original_download.sha256,expected);
  await p.getByText('Edit field mapping',{exact:true}).click();
  assert.equal(await p.locator('[data-mapping-editor] input').count(),24);
  // Deliberate clinical-label review; original headings and physical anchors remain immutable.
  const consent=input.fields.findIndex(f=>f.label==='CONSENT');assert(consent>=0);
  await p.locator(`#mapping-label-${consent}`).fill('CONSENT DOCUMENTATION');
  await p.getByRole('button',{name:'Save new mapping version',exact:true}).click();
  await p.getByText('Mapping v2',{exact:true}).waitFor();report.mapping_version=2;
  await p.screenshot({path:out+'/mapping-reviewed.png',fullPage:true});await checkpoint();
  for(const name of ['concise','missing','long']){
    const scenario=input.scenarios[name];assert(typeof scenario.notes==='string'&&scenario.notes.length<50000);
    assert.equal(Object.keys(scenario.answers).length,24);
    await p.goto(base+'/encounters/new/');
    const patients=await p.locator('[name=patient] option').evaluateAll(a=>a.map(x=>({label:x.textContent,value:x.value})));
    const patient=patients.filter(x=>x.label==='Synthetic Example X-ray · X-ray');assert.equal(patient.length,1);
    await p.locator('[name=patient]').selectOption(patient[0].value);
    const templates=await p.locator('[name=template_version] option').evaluateAll(a=>a.map(x=>({label:x.textContent,value:x.value})));
    const template=templates.filter(x=>x.label==='Synthetic Colonoscopy original compatibility · mapping 2');assert.equal(template.length,1);
    await p.locator('[name=template_version]').selectOption(template[0].value);
    await p.locator('[name=service_date]').fill('2026-09-20');await p.locator('[name=notes]').fill(scenario.notes);
    await p.locator('[name=synthetic_only]').check();await p.getByRole('button',{name:'Create document',exact:true}).click();
    await p.waitForURL(/\/encounters\/[a-f0-9-]{36}\/$/);
    const encounter=p.url().split('/').at(-2);const result={name,encounter_id:encounter,manual_review:true};report.scenarios.push(result);await checkpoint();
    assert.equal(await p.locator('textarea[name^=answer_]').count(),24);
    for(const field of input.fields){
      const answer=scenario.answers[field.key];assert.equal(typeof answer,'string');assert(answer.length<=20000);
      await p.locator(`[name=answer_${field.key}]`).fill(answer);await p.locator(`[name=reviewed_${field.key}]`).check();
    }
    await p.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();
    await p.locator('#final-review').check();await p.getByRole('button',{name:'Finalize document',exact:true}).click();
    await p.getByText('Finalized after clinical review. This document is read-only and ready to export in its original format.',{exact:true}).waitFor();
    const response=await context.request.get(base+`/api/encounters/${encounter}/`);assert.equal(response.status(),200);
    const state=await response.json();assert.equal(state.status,'finalized');assert.equal(state.notes,scenario.notes);
    for(const field of input.fields){assert.equal(state.answers[field.key].text,scenario.answers[field.key]);assert.equal(state.answers[field.key].reviewed,true);}
    result.export=await download(p,p.getByRole('link',{name:/Export original format/}),name+'-authenticated.docx');
    result.finalized_state=state;result.finished_at=new Date().toISOString();await checkpoint();
    await p.screenshot({path:out+`/${name}-finalized.png`,fullPage:true});
  }
  assert.equal(report.blocked_requests.length,0);assert.equal(sha(await fs.readFile(source)),expected);
  report.complete=true;report.finished_at=new Date().toISOString();await checkpoint();
}catch(error){report.failure={name:error.name,message:error.message};await checkpoint();throw error;}
finally{await browser.close();await fs.writeFile(out+'/result.json',JSON.stringify(report,null,2)+'\n',{mode:0o600,flag:'wx'});}
console.log(JSON.stringify({complete:report.complete,revision,template_id:report.template_id,encounters:report.scenarios.map(x=>x.encounter_id),provider_calls:0}));
