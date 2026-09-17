/** Private WM IOV walkthrough. Synthetic accounts and fixture AI only. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const dependency=name=>process.env.PLAYWRIGHT_MODULE_DIR?require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,name)):require(name);
const {chromium}=dependency('@playwright/test');
const axeModule=dependency('@axe-core/playwright');
const AxeBuilder=axeModule.default || axeModule;
const app=path.dirname(fileURLToPath(import.meta.url));
const base=new URL(process.env.QUILLMD_BROWSER_BASE_URL || 'http://127.0.0.1:9130');
assert(['localhost','127.0.0.1','[::1]'].includes(base.hostname) && !base.username && !base.password);
const output=path.join(app,'.runtime/wm-browser-artifacts');
const credentials=JSON.parse(await fs.readFile(process.env.QUILLMD_BROWSER_CREDENTIALS || path.join(app,'.runtime/private-access.json'),'utf8'));
assert(credentials.doctor.email.endsWith('@synthetic.quillmd.invalid'));
const fixture=JSON.parse(await fs.readFile(path.join(app,'.runtime/wm-browser-input.json'),'utf8'));
assert(fixture.synthetic_only===true && fixture.fields.length===90);
await fs.mkdir(output,{recursive:true,mode:0o700});
const checks=[];
let current='initialization';
let stage='';
let browser;
let page;
let templateURL;
const exports=[];
async function check(name,action){current=name;await action();checks.push({name,passed:true});console.log('PASS '+name);}
async function login(account,activePage=page){await activePage.goto(new URL('/login/',base).href);await activePage.locator('[name=email]').fill(account.email);await activePage.locator('[name=password]').fill(account.password);await activePage.getByRole('button',{name:'Sign in',exact:true}).click();await activePage.waitForURL(new URL('/',base).href);}
async function create(scenario,notes=scenario.notes){
 await page.goto(new URL('/encounters/new/',base).href);
 await page.locator('[name=patient]').selectOption({label:'Synthetic Example X-ray · X-ray'});
 await page.locator('[name=template_version]').selectOption({label:templateName+' · mapping 1'});
 await page.locator('[name=notes]').fill(notes);
 await page.locator('[name=synthetic_only]').check();
 await page.getByRole('button',{name:'Create document',exact:true}).click();
 await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);
 return page.url();
}
async function generate(){
 assert.equal(await page.getByText('Synthetic fixture · $0 charge. No live AI service is called.',{exact:true}).isVisible(),true);
 await page.getByRole('button',{name:'Generate supported answers',exact:true}).click();
 for(let n=0;n<40;n++){await page.waitForTimeout(500);await page.reload();if(await page.locator('.source-panel .badge').filter({hasText:/^succeeded$/}).count())return;assert.equal(await page.locator('.source-panel .badge').filter({hasText:/^(failed|reconciliation)$/}).count(),0);}
 throw new Error('Fixture generation timeout');
}
async function review(scenario,reviewed=true){
 for(const field of fixture.fields){
  stage='review answer '+field.key;
  const answer=scenario.answers[field.key];const control=page.locator(`[name="answer_${field.key}"]`);
  if(field.kind==='choice')await control.selectOption(answer.text);else await control.fill(answer.text);
  await page.locator(`[name="source_${field.key}"]`).fill(answer.evidence.map(e=>e.quote).join('\n'));
  if(reviewed)await page.locator(`[name="reviewed_${field.key}"]`).check();
 }
 for(const requirement of scenario.requirements){
  stage='review statement '+requirement.key;
  const variant=page.locator(`select[name="claim_variant_${requirement.key}"]`);
  if(await variant.count())await variant.selectOption(scenario.claim_variants[requirement.key]);
  if(requirement.kind==='assertion')await page.locator(`[name="claim_source_${requirement.key}"]`).fill(scenario.notes.split('\n').find(line=>line.startsWith(requirement.label+':')));
  if(reviewed)await page.locator(`[name="claim_reviewed_${requirement.key}"]`).check();
 }
 stage='save review';
 await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();
}
async function finalize(){stage='finalize';await page.locator('[name=reviewed]').check();await page.getByRole('button',{name:'Finalize document',exact:true}).click();await page.waitForLoadState();}
const templateName='Synthetic WM browser '+Date.now();
try{
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:true});page=await context.newPage();page.setDefaultTimeout(30000);
 await check('Synthetic doctor login and fixture spending boundary',async()=>{await login(credentials.doctor);assert.equal(await page.locator('.integration-list .badge').filter({hasText:/^Synthetic fixture$/}).count(),1);});
 await check('Upload preserved WM IOV original with 90 fields',async()=>{
  await page.goto(new URL('/templates/upload/',base).href);await page.locator('[name=name]').fill(templateName);
  const options=await page.locator('[name=department] option').allTextContents();const label=options.find(t=>t.includes('X-ray'));assert(label);await page.locator('[name=department]').selectOption({label});
  await page.locator('[name=file]').setInputFiles(path.join(app,'..','WM IOV Template.docx'));await page.locator('[name=synthetic_only]').check();
  await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);templateURL=page.url();
  assert.equal(await page.locator('.table-wrap tbody tr').count(),90);
  const response=await context.request.get(new URL(await page.getByRole('link',{name:'Download original',exact:true}).getAttribute('href'),base).href);assert.equal(response.status(),200);
  assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'),fixture.original_sha256);
 });
 for(const name of ['positive','absent','no_prior','asymptomatic','long']){
  const scenario=fixture.scenarios[name];
  await check(`WM ${name}: notes → fixture answers → reviewed export`,async()=>{
   const url=await create(scenario);await generate();
   assert.equal(await page.locator('select[name^=answer_]').count(),28);
   assert.equal(await page.locator('textarea[name^=answer_]').count(),62);
   for(const field of fixture.fields)assert.equal(await page.locator(`[name="answer_${field.key}"]`).inputValue(),scenario.answers[field.key].text);
   // Select choices first; review only after current materialized wording is visible.
   await review(scenario,false);
   await review(scenario);
   assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),14);
   if(name==='positive'){
    const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(result.violations.map(v=>v.id),[]);
    await page.screenshot({path:path.join(output,'review-desktop.png')});
    await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    const mobile=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(mobile.violations.map(v=>v.id),[]);
    await page.screenshot({path:path.join(output,'review-mobile.png')});await page.setViewportSize({width:1440,height:1080});
   }
   await finalize();const link=page.getByRole('link',{name:'Export original format'});assert.equal(await link.count(),1);
   const response=await context.request.get(new URL(await link.getAttribute('href'),base).href);assert.equal(response.status(),200);const bytes=await response.body();assert.equal(bytes.subarray(0,2).toString(),'PK');
   const destination=path.join(output,name+'.docx');await fs.writeFile(destination,bytes,{mode:0o600});
   exports.push({scenario:name,encounter:url,exportURL:new URL(await link.getAttribute('href'),base).href,path:destination,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length});
   if(name==='long')assert.equal(await page.locator('.answer-text').filter({hasText:'Synthetic long answer'}).textContent(),scenario.answers.patient_name.text);
  });
 }
 await check('Conflicting source blocks finalization; source correction clears review',async()=>{
  const scenario=fixture.scenarios.absent;const field=fixture.fields.find(f=>f.kind==='measurement');
  await create(scenario,scenario.notes+'\n'+field.label+': 99 '+field.locator.unit);await generate();
  assert.equal(await page.locator(`[name="answer_${field.key}"]`).inputValue(),'');
  await review(scenario,false);await review(scenario);await finalize();assert.equal(await page.getByRole('link',{name:'Export original format'}).count(),0);
  await page.getByText('Edit source notes',{exact:true}).click();await page.locator('[name=notes]').fill(scenario.notes);await page.getByRole('button',{name:'Save source notes',exact:true}).click();await page.waitForLoadState();
  assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),0);assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
  assert.equal(await page.locator('textarea[name=answer_patient_name]').inputValue(),'');
 });
 await check('Same-department sharing and cross-department/organization denial',async()=>{
  for(const name of ['xray_employee','ultrasound','other_org']){
   const separate=await browser.newContext();const other=await separate.newPage();await login(credentials[name],other);
   for(const target of [templateURL,new URL('original/',templateURL).href,exports[0].encounter,exports[0].exportURL]){
    const response=await separate.request.get(target);assert.equal(response.status(),name==='xray_employee'?200:404);
   }
   await separate.close();
  }
 });
 await fs.writeFile(path.join(output,'report.json'),JSON.stringify({passed:true,synthetic_only:true,generation:'fixture, no provider requests',backend:fixture.backend,checks,exports},null,2),{mode:0o600});
 console.log(`WM browser gate: ${checks.length}/${checks.length} passed.`);
}catch(error){
 await fs.writeFile(path.join(output,'report.json'),JSON.stringify({passed:false,active_check:current,error_class:error.constructor.name,stage,checks,exports},null,2),{mode:0o600});
 if(page)await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});
 console.error('WM browser gate failed at: '+current+'; inspect private evidence.');process.exitCode=1;
}finally{await browser?.close();}
