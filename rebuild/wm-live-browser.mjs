/**
 * ONE private synthetic WM workflow with live generation, never an automatic retry.
 * Prepare only until guarded deployment; run from the permanent reviewed release:
 * node rebuild/wm-live-browser.mjs --release FULL_SHA --mapping-sha SDK_MAPPING_SHA --execute
 * PLAYWRIGHT_MODULE_DIR may locate existing installed browser dependencies.
 * Credentials and SDK-prepared inputs remain permanent operator-private0600 files.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import constants from 'node:constants';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const app=path.dirname(fileURLToPath(import.meta.url));
const permanent='/opt/meddoc-pro/rebuild';
const base='http://127.0.0.1:9130';
const originalSHA='c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b';
const args=process.argv.slice(2);
const value=name=>{const i=args.indexOf(name);return i>=0?args[i+1]:undefined;};
const release=value('--release');
const mappingSHA=value('--mapping-sha');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const expectedKeys=rows=>rows.map(row=>row.key).sort();
const uuidFrom=(uri,section)=>{const match=new URL(uri).pathname.match(new RegExp(`^/${section}/([0-9a-f-]{36})/`));assert(match);return match[1];};
const report={passed:false,synthetic_only:true,release,checks:[],generation_click_attempts:0,
  network_generation_submissions:0,voice_submissions:0,payment_submissions:0,
  maximum_authorized_charge_usd:'1.00',provider:'anthropic',billing_reconciliation:'Not established by this browser check.'};
let stage='argument and private-file validation';
let browser,output,encounterURL,templateURL,exportURL,apiURL,resultURL;
let generationArmed=false;
let wroteReport=false;

async function privateJSON(filename,document){
  const file=await fs.open(filename,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
  try{await file.writeFile(JSON.stringify(document,null,2)+'\n');await file.sync();}finally{await file.close();}
}
async function privateRead(filename){
  assert.equal(await fs.realpath(filename),filename);
  const file=await fs.open(filename,constants.O_RDONLY|constants.O_NOFOLLOW);
  try{
    const info=await file.stat();
    assert(info.isFile() && info.nlink===1 && info.uid===process.getuid() && (info.mode&0o777)===0o600 && info.size<=2*1024*1024);
    return JSON.parse(await file.readFile('utf8'));
  }finally{await file.close();}
}
async function check(name,action){stage=name;await action();report.checks.push({name,passed:true});console.log('PASS '+name);}
function belowCap(value){
  assert.match(value,/^\d+(?:\.\d+)?$/);
  const [whole,fraction='']=value.split('.');
  const places=10n**BigInt(fraction.length);
  const amount=BigInt(whole)*places+BigInt(fraction||'0');
  return amount>0n && amount<=places;
}
function localURL(uri){const url=new URL(uri,base);assert.equal(url.origin,base);assert(!url.username&&!url.password);return url.href;}
async function guardedContext(){
  const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:true});
  await context.route('**/*',async route=>{
    const request=route.request();const url=new URL(request.url());
    if(url.origin!==base){await route.abort('blockedbyclient');return;}
    if(request.method()==='POST'){
      if(/^\/encounters\/[0-9a-f-]+\/generate\/$/.test(url.pathname)){
        if(!generationArmed || report.network_generation_submissions!==0 || url.href!==new URL('generate/',encounterURL).href){await route.abort('blockedbyclient');return;}
        generationArmed=false;report.network_generation_submissions++;
      }
      if(url.pathname.endsWith('/voice/')){report.voice_submissions++;await route.abort('blockedbyclient');return;}
      if(url.pathname.startsWith('/billing/')){report.payment_submissions++;await route.abort('blockedbyclient');return;}
    }
    await route.continue();
  });
  return context;
}
async function login(page,account){
  assert(account && account.email.endsWith('@synthetic.quillmd.invalid') && typeof account.password==='string');
  await page.goto(base+'/login/');
  await page.locator('[name=email]').fill(account.email);
  await page.locator('[name=password]').fill(account.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.waitForURL(base+'/');
}
async function api(context){
  const response=await context.request.get(apiURL,{maxRedirects:0});assert.equal(response.status(),200);
  return response.json();
}
function evidenceSupports(notes,field,answer){
  if(!Array.isArray(answer.evidence) || answer.evidence.length===0)return false;
  const points=Array.from(notes);const full=field.label+': '+answer.text;
  return answer.evidence.every(e=>Number.isInteger(e.start)&&Number.isInteger(e.end)&&e.start>=0&&e.end>e.start&&e.end<=points.length
    && points.slice(e.start,e.end).join('')===e.quote && (e.quote===full||e.quote===answer.text)
    && notes.split(/\r?\n/).some(line=>line===full));
}

try{
  assert.deepEqual([...args].filter(x=>x.startsWith('--')).sort(),['--execute','--mapping-sha','--release']);
  assert.equal(args.length,5);assert.match(release,/^[a-f0-9]{40}$/);assert.match(mappingSHA,/^[a-f0-9]{64}$/);
  assert.equal(app,permanent,'Use the reviewed permanent release after activation.');
  assert.equal(await fs.realpath(app),app);
  const runtime=path.join(app,'.runtime');const info=await fs.lstat(runtime);
  assert(info.isDirectory()&&!info.isSymbolicLink()&&info.uid===process.getuid()&&(info.mode&0o777)===0o700);
  const credentials=await privateRead(path.join(runtime,'private-access.json'));
  const fixture=await privateRead(path.join(runtime,'wm-browser-input.json'));
  assert(fixture.synthetic_only===true && fixture.fields.length===90 && fixture.original_sha256===originalSHA);
  assert.equal(fixture.backend.backend,'wm-iov-foss-v2');assert.equal(fixture.backend.mapping_digest,mappingSHA);
  const scenario=fixture.scenarios.positive;
  assert(scenario && scenario.requirements.length===14 && typeof scenario.notes==='string' && scenario.notes.length<=50000);
  assert.deepEqual(Object.keys(scenario.answers).sort(),expectedKeys(fixture.fields));
  const original=path.join(app,'..','WM IOV Template.docx');assert.equal(hash(await fs.readFile(original)),originalSHA);
  // Exclusive evidence and attempt files deliberately survive failures. A new
  // invocation cannot hide or automatically repeat an uncertain paid request.
  output=path.join(runtime,'wm-live-browser-'+release.slice(0,12));
  await fs.mkdir(output,{mode:0o700});
  // Playwright API debug output can include fill() arguments. Keep credential
  // handling quiet even if the invoking shell previously enabled debug logging.
  delete process.env.DEBUG;delete process.env.PWDEBUG;
  const require=createRequire(import.meta.url);
  const dependency=name=>process.env.PLAYWRIGHT_MODULE_DIR?require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,name)):require(name);
  const {chromium}=dependency('@playwright/test');
  browser=await chromium.launch({headless:true});
  const context=await guardedContext();const page=await context.newPage();page.setDefaultTimeout(30000);
  const templateName='Synthetic WM live '+release.slice(0,12);

  await check('Running private release and synthetic-only gate',async()=>{
    for(const port of [9130,9131]){
      const response=await context.request.get(`http://127.0.0.1:${port}/health/`,{maxRedirects:0});assert.equal(response.status(),200);
      const health=await response.json();assert.equal(health.release,release);assert.equal(health.data_mode,'synthetic-only');
    }
  });
  await check('Synthetic doctor login and live Anthropic disclosure',async()=>{
    await login(page,credentials.doctor);
    const generation=page.locator('.integration-list li').filter({has:page.getByText('Answer generation',{exact:true})});
    assert.equal(await generation.locator('.badge').textContent(),'Live API configured');
    assert.match(await generation.locator('p').textContent(),/^claude-/);
    assert.equal(await page.locator('.integration-list .badge').filter({hasText:/^Synthetic only$/}).count(),1);
  });
  await check('Upload and preserve the qualified original and 90 labels',async()=>{
    await page.goto(base+'/templates/upload/');await page.locator('[name=name]').fill(templateName);
    const choices=await page.locator('[name=department] option').allTextContents();
    const labels=choices.filter(label=>label.includes('X-ray'));assert.equal(labels.length,1);
    await page.locator('[name=department]').selectOption({label:labels[0]});
    await page.locator('[name=file]').setInputFiles(original);await page.locator('[name=synthetic_only]').check();
    await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();
    await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);templateURL=localURL(page.url());report.template_id=uuidFrom(templateURL,'templates');
    const rows=await page.locator('.table-wrap tbody tr').evaluateAll(rows=>rows.map(row=>({label:row.cells[0].textContent,key:row.cells[1].textContent})));
    assert.deepEqual(rows,fixture.fields.map(field=>({label:field.label,key:field.key})));
    const response=await context.request.get(new URL('original/',templateURL).href,{maxRedirects:0});assert.equal(response.status(),200);
    assert.equal(hash(await response.body()),originalSHA);report.original_sha256=originalSHA;
  });
  await check('Create one synthetic encounter and record the JSON URI',async()=>{
    await page.goto(base+'/encounters/new/');
    await page.locator('[name=patient]').selectOption({label:'Synthetic Example X-ray · X-ray'});
    await page.locator('[name=template_version]').selectOption({label:templateName+' · mapping 1'});
    await page.locator('[name=notes]').fill(scenario.notes);await page.locator('[name=synthetic_only]').check();
    await page.getByRole('button',{name:'Create document',exact:true}).click();
    await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);encounterURL=localURL(page.url());
    report.encounter_id=uuidFrom(encounterURL,'encounters');apiURL=base+'/api/encounters/'+report.encounter_id+'/';
    report.encounter_json_uri=apiURL;const snapshot=await api(context);
    assert.equal(snapshot.notes,scenario.notes);assert.deepEqual(snapshot.answers,{});assert.equal(snapshot.status,'draft');
  });
  await check('Record maximum charge below USD1 before the single paid click',async()=>{
    const form=page.locator(`form[action="/encounters/${report.encounter_id}/generate/"]`);assert.equal(await form.count(),1);
    const match=(await form.locator('p').textContent()).match(/Reserve up to \$([0-9]+(?:\.[0-9]+)?)\.\s/);
    assert(match && belowCap(match[1]),'Displayed live maximum exceeds the fixed USD1 cap or is unavailable.');
    // The server's signed usage quote exposes only nonsecret provider/rate
    // configuration. Inspect its payload without logging or persisting the token;
    // Django verifies the signature and freshness when this same form submits.
    const quote=await form.locator('[name=usage_quote]').inputValue();
    const payload=quote.split(':')[0];assert(payload&&!payload.startsWith('.'));
    const quoted=JSON.parse(Buffer.from(payload,'base64url').toString('utf8'));
    assert.equal(quoted.encounter,report.encounter_id);assert.equal(quoted.config.mode,'live');
    assert.equal(quoted.config.provider,'anthropic');assert.match(quoted.config.model,/^claude-/);
    assert.equal(await form.getByRole('button',{name:'Generate supported answers',exact:true}).isEnabled(),true);
    report.displayed_maximum_charge_usd=match[1];
    const before={release,synthetic_only:true,encounter_id:report.encounter_id,encounter_json_uri:apiURL,
      displayed_maximum_charge_usd:match[1],maximum_authorized_charge_usd:'1.00',mapping_sha256:mappingSHA,
      generation_submissions_so_far:0,voice_submissions:0,payment_submissions:0,recorded_at:new Date().toISOString()};
    await privateJSON(path.join(output,'before-generation.json'),before);
    await privateJSON(path.join(runtime,'wm-live-generation-attempt.json'),before);
    report.generation_click_attempts=1;generationArmed=true;
    // Exactly one call. Neither navigation failures nor uncertain provider state
    // are grounds to repeat this click or invoke another provider request.
    await form.getByRole('button',{name:'Generate supported answers',exact:true}).click();
    assert.equal(report.network_generation_submissions,1);
  });
  await check('One Anthropic generation job reaches a terminal state',async()=>{
    const deadline=Date.now()+180000;let success=false;
    while(Date.now()<deadline){
      await page.waitForTimeout(1500);await page.reload();
      const record=page.getByRole('heading',{name:'Document record',exact:true}).locator('..');
      const states=await record.locator('.badge').allTextContents();assert(states.length<=1);
      if(states.some(state=>['failed','reconciliation'].includes(state.trim()))){report.requires_manual_review=true;throw new Error('Provider job requires inspection.');}
      if(states.length===1&&states[0].trim()==='succeeded'){
        assert.equal((await record.locator('strong').allTextContents()).filter(text=>text.trim()==='generation').length,1);
        assert.match(await record.locator('p').filter({hasText:/^Provider:/}).textContent(),/^Provider:\s*anthropic:/);
        resultURL=localURL(await record.getByRole('link',{name:'Download provider result',exact:true}).getAttribute('href'));
        report.job_id=uuidFrom(resultURL,'jobs');report.provider_result_uri=resultURL;success=true;break;
      }
    }
    assert(success,'Provider completion was not demonstrated; no request was retried.');
  });
  await check('All90 generated answers match supported source without replacement',async()=>{
    const snapshot=await api(context);assert.equal(snapshot.notes,scenario.notes);
    assert.deepEqual(Object.keys(snapshot.answers).sort(),expectedKeys(fixture.fields));
    const differences=[];
    for(const field of fixture.fields){
      const answer=snapshot.answers[field.key];
      if(answer.text!==scenario.answers[field.key].text || answer.status!=='supported' || !evidenceSupports(snapshot.notes,field,answer))differences.push(field.key);
      const control=page.locator(`[name="answer_${field.key}"]`);assert.equal(await control.inputValue(),answer.text);
    }
    if(differences.length){report.requires_manual_review=true;report.generated_answer_difference_keys=differences;throw new Error('Generated answers differ; clinician review required.');}
    assert.equal(await page.locator('select[name^=answer_]').count(),28);
    assert.equal(await page.locator('textarea[name^=answer_]').count(),62);
    report.supported_generated_answer_count=90;
  });
  await check('Select approved positive statements and save before review',async()=>{
    assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),0);
    assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
    for(const requirement of scenario.requirements){
      const variant=page.locator(`select[name="claim_variant_${requirement.key}"]`);
      if(await variant.count())await variant.selectOption(scenario.claim_variants[requirement.key]);
      else assert.equal(await page.locator(`input[name="claim_variant_${requirement.key}"]`).inputValue(),scenario.claim_variants[requirement.key]);
      if(requirement.kind==='assertion'){
        const prefix=requirement.label+':';
        const lines=scenario.notes.split('\n').filter(line=>line.startsWith(prefix));
        assert.equal(lines.length,1);assert.equal(lines[0].slice(prefix.length).trim(),requirement.text.trim());
        await page.locator(`[name="claim_source_${requirement.key}"]`).fill(lines[0]);
      }
    }
    await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();
    const snapshot=await api(context);assert.equal(snapshot.notes,scenario.notes);
    for(const field of fixture.fields)assert.equal(snapshot.answers[field.key].text,scenario.answers[field.key].text);
    assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
  });
  await check('Review actual displayed wording and source-bound answers',async()=>{
    for(const requirement of scenario.requirements){
      const box=page.locator(`[name="claim_reviewed_${requirement.key}"]`);
      const section=box.locator('xpath=ancestor::section[contains(@class,"answer")][1]');
      assert.equal((await section.locator('.answer-text').textContent()).trim(),requirement.text.trim());
      assert.equal(await section.locator('.error-text').filter({hasText:/could not be resolved/}).count(),0);
      assert.equal(await page.locator(`[name="claim_token_${requirement.key}"]`).inputValue()==='',false);
    }
    for(const field of fixture.fields)await page.locator(`[name="reviewed_${field.key}"]`).check();
    for(const requirement of scenario.requirements)await page.locator(`[name="claim_reviewed_${requirement.key}"]`).check();
    await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();
    assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),90);
    assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),14);
    assert.equal(await page.locator('.answer .error-text').count(),0);
  });
  await check('Finalize and download the single reviewed DOCX',async()=>{
    await page.locator('[name=reviewed]').check();
    await page.getByRole('button',{name:'Finalize document',exact:true}).click();await page.waitForLoadState();
    const link=page.getByRole('link',{name:'Export original format'});assert.equal(await link.count(),1);
    exportURL=localURL(await link.getAttribute('href'));
    const response=await context.request.get(exportURL,{maxRedirects:0});assert.equal(response.status(),200);
    const bytes=await response.body();assert(bytes.length>1000&&bytes.length<=30*1024*1024&&bytes.subarray(0,2).toString()==='PK');
    const destination=path.join(output,'synthetic-wm-live.docx');const file=await fs.open(destination,'wx',0o600);
    try{await file.writeFile(bytes);await file.sync();}finally{await file.close();}
    report.export_sha256=hash(bytes);report.export_bytes=bytes.length;report.export_artifact=destination;
    report.export_xml_control_and_structure_verification='Pending independent Python XML comparison; UI displayed28 original choices.';
    assert.equal((await api(context)).status,'finalized');
    const originalResponse=await context.request.get(new URL('original/',templateURL).href,{maxRedirects:0});
    assert.equal(originalResponse.status(),200);assert.equal(hash(await originalResponse.body()),originalSHA);
  });
  await check('Same-department access and cross-department and organization denial',async()=>{
    for(const name of ['xray_employee','ultrasound','other_org']){
      const separate=await guardedContext();const other=await separate.newPage();await login(other,credentials[name]);
      for(const uri of [templateURL,new URL('original/',templateURL).href,encounterURL,apiURL,resultURL,exportURL]){
        const response=await separate.request.get(uri,{maxRedirects:0});assert.equal(response.status(),name==='xray_employee'?200:404);
      }
      await separate.close();
    }
  });
  assert.equal(report.generation_click_attempts,1);assert.equal(report.network_generation_submissions,1);
  assert.equal(report.voice_submissions,0);assert.equal(report.payment_submissions,0);
  report.passed=true;report.completed_at=new Date().toISOString();
  await privateJSON(path.join(output,'report.json'),report);wroteReport=true;
  console.log('Live synthetic WM browser workflow passed. Private billing and export-structure checks remain separate.');
}catch(error){
  report.active_check=stage;report.error_class=error?.constructor?.name||'Error';
  if(output&&!wroteReport)await privateJSON(path.join(output,'report.json'),report).catch(()=>{});
  console.error('Live synthetic WM verification stopped at: '+stage+'. No automatic generation retry was attempted.');
  process.exitCode=1;
}finally{await browser?.close();}
