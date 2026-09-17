/**
 * ONE fresh private synthetic WM IOV encounter through the deployed live
 * Anthropic mapping, in three explicit phases so a paid request is never
 * repeated automatically:
 *
 *   prepare  --release SHA --mapping-sha SHA --scenario absent --template UUID
 *            logs in, verifies the existing qualified template, creates ONE new
 *            draft encounter, records the displayed maximum charge. No provider call.
 *   generate --release SHA --mapping-sha SHA --scenario absent --encounter UUID --execute
 *            writes the exclusive second attempt marker, clicks Generate exactly once,
 *            waits for a terminal job state, snapshots the automatic AI draft and the
 *            stored provider result. Never retries.
 *   review   --release SHA --mapping-sha SHA --scenario absent --encounter UUID --job UUID --execute
 *            records automatic output vs expected values, applies only the clinician
 *            corrections that differ, selects reviewed statement variants, reviews all
 *            90 answers + 14 statements, finalizes, downloads the export, checks
 *            department/organization isolation. Zero provider requests.
 *
 * PLAYWRIGHT_MODULE_DIR locates the existing installed browser dependencies.
 * Credentials and SDK-prepared inputs stay in operator-private 0600 files.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import constants from 'node:constants';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';

const app='/opt/meddoc-pro/rebuild';
const base='http://127.0.0.1:9130';
const originalSHA='c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b';
const args=process.argv.slice(2);
const value=name=>{const i=args.indexOf(name);return i>=0?args[i+1]:undefined;};
const phase=value('--phase');
const release=value('--release');
const mappingSHA=value('--mapping-sha');
const scenarioName=value('--scenario');
const templateId=value('--template');
const encounterId=value('--encounter');
const jobId=value('--job');
const execute=args.includes('--execute');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const expectedKeys=rows=>rows.map(row=>row.key).sort();
const uuidFrom=(uri,section)=>{const match=new URL(uri).pathname.match(new RegExp(`^/${section}/([0-9a-f-]{36})/`));assert(match);return match[1];};
const report={passed:false,synthetic_only:true,release,phase,scenario:scenarioName,checks:[],generation_click_attempts:0,
  network_generation_submissions:0,voice_submissions:0,payment_submissions:0,
  maximum_authorized_charge_usd:'1.00',provider:'anthropic',billing_reconciliation:'Not established by this browser check.'};
let stage='argument and private-file validation';
let browser,output,encounterURL,templateURL,exportURL,apiURL,resultURL,reportName='report.json';
let generationArmed=false;
let wroteReport=false;

async function privateJSON(filename,document){
  const file=await fs.open(filename,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
  try{await file.writeFile(JSON.stringify(document,null,2)+'\n');await file.sync();}finally{await file.close();}
}
async function privateBytes(filename,bytes){
  const file=await fs.open(filename,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
  try{await file.writeFile(bytes);await file.sync();}finally{await file.close();}
}
async function privateRead(filename,maximum=2*1024*1024){
  assert.equal(await fs.realpath(filename),filename);
  const file=await fs.open(filename,constants.O_RDONLY|constants.O_NOFOLLOW);
  try{
    const info=await file.stat();
    assert(info.isFile() && info.nlink===1 && info.uid===process.getuid() && (info.mode&0o777)===0o600 && info.size<=maximum);
    return JSON.parse(await file.readFile('utf8'));
  }finally{await file.close();}
}
async function check(name,action){stage=name;await action();report.checks.push({name,passed:true});console.log('PASS '+name);}
function belowCap(text){
  assert.match(text,/^\d+(?:\.\d+)?$/);
  const [whole,fraction='']=text.split('.');
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
      if(url.pathname.endsWith('/notes/')){report.notes_edit_submissions=(report.notes_edit_submissions||0)+1;await route.abort('blockedbyclient');return;}
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
function labelledLine(notes,label){
  const prefix=label+':';
  const lines=notes.split('\n').map(line=>line.replace(/\r$/,'')).filter(line=>line.startsWith(prefix));
  assert.equal(lines.length,1,'Expected exactly one source line for '+label);
  return lines[0];
}
function evidenceSupports(notes,field,answer){
  if(!Array.isArray(answer.evidence) || answer.evidence.length===0)return false;
  const points=Array.from(notes);const full=field.label+': '+answer.text;
  const ownSpans=new Set();let offset=0;
  for(const match of notes.matchAll(/[^\r\n]*(?:\r\n|\r|\n|$)/g)){
    const raw=match[0];if(!raw)continue;
    const line=raw.replace(/(?:\r\n|\r|\n)$/,'');
    if(line===full){
      const end=offset+Array.from(line).length;
      ownSpans.add(offset+':'+end);
      ownSpans.add((offset+Array.from(field.label+': ').length)+':'+end);
    }
    offset+=Array.from(raw).length;
  }
  return answer.evidence.every(e=>Number.isInteger(e.start)&&Number.isInteger(e.end)&&e.start>=0&&e.end>e.start&&e.end<=points.length
    && points.slice(e.start,e.end).join('')===e.quote && (e.quote===full||e.quote===answer.text)
    && ownSpans.has(e.start+':'+e.end));
}

try{
  assert(['prepare','generate','review'].includes(phase),'Choose --phase prepare|generate|review');
  assert.match(release,/^[a-f0-9]{40}$/);assert.match(mappingSHA,/^[a-f0-9]{64}$/);
  assert(['positive','absent','no_prior','asymptomatic','long'].includes(scenarioName));
  if(phase==='prepare')assert.match(templateId,/^[0-9a-f-]{36}$/);
  if(phase!=='prepare'){assert.match(encounterId,/^[0-9a-f-]{36}$/);assert(execute,'--execute is required for the paid or mutating phases.');}
  if(phase==='review')assert.match(jobId,/^[0-9a-f-]{36}$/);
  assert.equal(await fs.realpath(app),app);
  const runtime=path.join(app,'.runtime');const info=await fs.lstat(runtime);
  assert(info.isDirectory()&&!info.isSymbolicLink()&&info.uid===process.getuid()&&(info.mode&0o777)===0o700);
  const credentials=await privateRead(path.join(runtime,'private-access.json'));
  const fixture=await privateRead(path.join(runtime,'wm-browser-input.json'));
  assert(fixture.synthetic_only===true && fixture.fields.length===90 && fixture.original_sha256===originalSHA);
  assert.equal(fixture.backend.backend,'wm-iov-foss-v2');assert.equal(fixture.backend.mapping_digest,mappingSHA);
  const scenario=fixture.scenarios[scenarioName];
  assert(scenario && scenario.requirements.length===14 && typeof scenario.notes==='string' && scenario.notes.length<=50000);
  assert.deepEqual(Object.keys(scenario.answers).sort(),expectedKeys(fixture.fields));
  const original=path.join(app,'..','WM IOV Template.docx');assert.equal(hash(await fs.readFile(original)),originalSHA);
  // The first authentic attempt marker must remain untouched; this run uses its own exclusive marker.
  const firstMarkerPath=path.join(runtime,'wm-live-generation-attempt.json');
  report.first_attempt_marker_sha256=hash(await fs.readFile(firstMarkerPath));
  const secondMarkerPath=path.join(runtime,'wm-live-generation-attempt-2.json');
  output=path.join(runtime,'wm-live-browser-'+release.slice(0,12)+'-fresh-'+scenarioName);
  if(phase==='prepare'){await fs.mkdir(output,{mode:0o700});reportName='prepare-report.json';}
  else{const out=await fs.lstat(output);assert(out.isDirectory()&&!out.isSymbolicLink()&&(out.mode&0o777)===0o700);
    const attempt=value('--attempt');if(attempt!==undefined){assert.match(attempt,/^[2-9]$/);assert.equal(phase,'review','Only the review phase (no provider call) may be resumed.');}
    reportName=phase+'-report'+(attempt?'-attempt'+attempt:'')+'.json';report.attempt=attempt?Number(attempt):1;
    await assert.rejects(fs.lstat(path.join(output,reportName)),'This phase already has a report; never rerun a phase blindly.');}
  delete process.env.DEBUG;delete process.env.PWDEBUG;
  const require=createRequire(path.join(app,'wm-live-browser.mjs'));
  const dependency=name=>process.env.PLAYWRIGHT_MODULE_DIR?require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,name)):require(name);
  const {chromium}=dependency('@playwright/test');
  browser=await chromium.launch({headless:true});
  const context=await guardedContext();const page=await context.newPage();page.setDefaultTimeout(30000);

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

  if(phase==='prepare'){
    let templateName;
    await check('Reuse the existing qualified template: original hash and 90 labels unchanged',async()=>{
      templateURL=localURL(base+'/templates/'+templateId+'/');report.template_id=templateId;
      await page.goto(templateURL);templateName=(await page.locator('h1').first().textContent()).trim();
      const rows=await page.locator('.table-wrap tbody tr').evaluateAll(rows=>rows.map(row=>({label:row.cells[0].textContent,key:row.cells[1].textContent})));
      assert.deepEqual(rows,fixture.fields.map(field=>({label:field.label,key:field.key})));
      const response=await context.request.get(new URL('original/',templateURL).href,{maxRedirects:0});assert.equal(response.status(),200);
      assert.equal(hash(await response.body()),originalSHA);report.original_sha256=originalSHA;report.template_name=templateName;
    });
    await check('Create one NEW synthetic encounter with the '+scenarioName+' scenario notes',async()=>{
      await page.goto(base+'/encounters/new/');
      await page.locator('[name=patient]').selectOption({label:'Synthetic Example X-ray · X-ray'});
      const options=await page.locator('[name=template_version] option').allTextContents();
      const wanted=options.filter(label=>label===templateName+' · mapping 1');assert.equal(wanted.length,1,'Expected exactly one mapping option for the reused template.');
      await page.locator('[name=template_version]').selectOption({label:wanted[0]});
      await page.locator('[name=notes]').fill(scenario.notes);await page.locator('[name=synthetic_only]').check();
      await page.getByRole('button',{name:'Create document',exact:true}).click();
      await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);encounterURL=localURL(page.url());
      report.encounter_id=uuidFrom(encounterURL,'encounters');apiURL=base+'/api/encounters/'+report.encounter_id+'/';
      report.encounter_json_uri=apiURL;const snapshot=await api(context);
      assert.equal(snapshot.notes.replace(/\r\n/g,'\n'),scenario.notes.replace(/\r\n/g,'\n'));
      assert.deepEqual(snapshot.answers,{});assert.equal(snapshot.status,'draft');assert.equal(snapshot.revision,0);
      report.stored_notes_sha256=hash(snapshot.notes);report.stored_notes_length=snapshot.notes.length;
    });
    await check('Displayed maximum charge is below the fixed USD1 cap (no click)',async()=>{
      const form=page.locator(`form[action="/encounters/${report.encounter_id}/generate/"]`);assert.equal(await form.count(),1);
      const match=(await form.locator('p').textContent()).match(/Reserve up to \$([0-9]+(?:\.[0-9]+)?)\.\s/);
      assert(match && belowCap(match[1]));report.displayed_maximum_charge_usd=match[1];
      const quote=await form.locator('[name=usage_quote]').inputValue();
      const quoted=JSON.parse(Buffer.from(quote.split(':')[0],'base64url').toString('utf8'));
      assert.equal(quoted.encounter,report.encounter_id);assert.equal(quoted.config.mode,'live');
      assert.equal(quoted.config.provider,'anthropic');assert.match(quoted.config.model,/^claude-/);
      report.configured_model=quoted.config.model;report.pricing_version=quoted.config.pricing_version;
    });
  }

  if(phase==='generate'){
    await check('Existing draft encounter carries the exact scenario notes and no answers',async()=>{
      report.encounter_id=encounterId;encounterURL=localURL(base+'/encounters/'+encounterId+'/');apiURL=base+'/api/encounters/'+encounterId+'/';
      report.encounter_json_uri=apiURL;
      const prepared=await privateRead(path.join(output,'prepare-report.json'));
      assert.equal(prepared.encounter_id,encounterId);assert.equal(prepared.passed,true);report.template_id=prepared.template_id;
      const snapshot=await api(context);
      assert.equal(snapshot.notes.replace(/\r\n/g,'\n'),scenario.notes.replace(/\r\n/g,'\n'));
      assert.equal(hash(snapshot.notes),prepared.stored_notes_sha256);
      assert.deepEqual(snapshot.answers,{});assert.equal(snapshot.status,'draft');assert.equal(snapshot.revision,0);
      scenario.notes=snapshot.notes;
      await page.goto(encounterURL);
      const record=page.getByRole('heading',{name:'Document record',exact:true}).locator('..');
      assert.equal(await record.locator('.badge').count(),0,'The encounter must have no prior job.');
    });
    await check('Record maximum charge below USD1 before the single paid click',async()=>{
      const form=page.locator(`form[action="/encounters/${report.encounter_id}/generate/"]`);assert.equal(await form.count(),1);
      const match=(await form.locator('p').textContent()).match(/Reserve up to \$([0-9]+(?:\.[0-9]+)?)\.\s/);
      assert(match && belowCap(match[1]),'Displayed live maximum exceeds the fixed USD1 cap or is unavailable.');
      const quote=await form.locator('[name=usage_quote]').inputValue();
      const quoted=JSON.parse(Buffer.from(quote.split(':')[0],'base64url').toString('utf8'));
      assert.equal(quoted.encounter,report.encounter_id);assert.equal(quoted.config.mode,'live');
      assert.equal(quoted.config.provider,'anthropic');assert.match(quoted.config.model,/^claude-/);
      assert.equal(await form.getByRole('button',{name:'Generate supported answers',exact:true}).isEnabled(),true);
      report.displayed_maximum_charge_usd=match[1];report.configured_model=quoted.config.model;report.pricing_version=quoted.config.pricing_version;
      const before={release,synthetic_only:true,scenario:scenarioName,encounter_id:report.encounter_id,encounter_json_uri:apiURL,
        displayed_maximum_charge_usd:match[1],maximum_authorized_charge_usd:'1.00',mapping_sha256:mappingSHA,
        first_attempt_marker_sha256:report.first_attempt_marker_sha256,
        generation_submissions_so_far:0,voice_submissions:0,payment_submissions:0,recorded_at:new Date().toISOString()};
      await privateJSON(path.join(output,'before-generation.json'),before);
      await privateJSON(secondMarkerPath,before);
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
        if(states.some(state=>['failed','reconciliation'].includes(state.trim()))){report.requires_manual_review=true;report.terminal_state=states[0].trim();throw new Error('Provider job requires inspection.');}
        if(states.length===1&&states[0].trim()==='succeeded'){
          assert.equal((await record.locator('strong').allTextContents()).filter(text=>text.trim()==='generation').length,1);
          assert.match(await record.locator('p').filter({hasText:/^Provider:/}).textContent(),/^Provider:\s*anthropic:/);
          resultURL=localURL(await record.getByRole('link',{name:'Download provider result',exact:true}).getAttribute('href'));
          report.job_id=uuidFrom(resultURL,'jobs');report.provider_result_uri=resultURL;report.terminal_state='succeeded';success=true;break;
        }
      }
      assert(success,'Provider completion was not demonstrated; no request was retried.');
    });
    await check('Snapshot the automatic AI draft and the stored provider result without editing',async()=>{
      const snapshot=await api(context);assert.equal(snapshot.notes,scenario.notes);assert.equal(snapshot.status,'review');
      assert.deepEqual(Object.keys(snapshot.answers).sort(),expectedKeys(fixture.fields));
      const providerResponse=await context.request.get(resultURL);assert.equal(providerResponse.status(),200);
      const providerBytes=await providerResponse.body();report.provider_result_sha256=hash(providerBytes);report.provider_result_bytes=providerBytes.length;
      await privateBytes(path.join(output,'provider-result.json'),providerBytes);
      const draft={encounter_id:report.encounter_id,job_id:report.job_id,revision:snapshot.revision,status:snapshot.status,
        notes_sha256:hash(snapshot.notes),answers:snapshot.answers,recorded_at:new Date().toISOString()};
      await privateJSON(path.join(output,'ai-draft.json'),draft);
      report.ai_draft_sha256=hash(JSON.stringify(draft,null,2)+'\n');
      const summary={supported:0,missing:0,conflict:0,other:0,matches_expected_value:0,differs_from_expected_value:0,evidence_bound:0,difference_keys:[]};
      for(const field of fixture.fields){
        const answer=snapshot.answers[field.key];
        summary[['supported','missing','conflict'].includes(answer.status)?answer.status:'other']++;
        const matches=answer.status==='supported' && answer.text===scenario.answers[field.key].text;
        if(matches)summary.matches_expected_value++;else{summary.differs_from_expected_value++;summary.difference_keys.push(field.key);}
        if(evidenceSupports(snapshot.notes,field,answer))summary.evidence_bound++;
      }
      report.automatic_output=summary;
      console.log('Automatic output summary: '+JSON.stringify(summary));
    });
  }

  if(phase==='review'){
    let draft,snapshotBefore;
    await check('Reuse the single fresh completed job; preserve its draft snapshot and provider result',async()=>{
      report.encounter_id=encounterId;report.job_id=jobId;
      const generated=await privateRead(path.join(output,'generate-report.json'));
      assert.equal(generated.encounter_id,encounterId);assert.equal(generated.job_id,jobId);assert.equal(generated.passed,true);
      assert.equal(generated.network_generation_submissions,1);report.template_id=generated.template_id;
      report.continuation_of={report:path.join(output,'generate-report.json'),sha256:hash(await fs.readFile(path.join(output,'generate-report.json')))};
      draft=await privateRead(path.join(output,'ai-draft.json'));assert.equal(draft.job_id,jobId);
      report.ai_draft_sha256=hash(await fs.readFile(path.join(output,'ai-draft.json')));assert.equal(report.ai_draft_sha256,generated.ai_draft_sha256);
      templateURL=localURL(base+'/templates/'+report.template_id+'/');
      encounterURL=localURL(base+'/encounters/'+encounterId+'/');apiURL=localURL(base+'/api/encounters/'+encounterId+'/');
      resultURL=localURL(base+'/jobs/'+jobId+'/result/');report.provider_result_uri=resultURL;
      const providerResponse=await context.request.get(resultURL);assert.equal(providerResponse.status(),200);
      report.provider_result_sha256_before=hash(await providerResponse.body());assert.equal(report.provider_result_sha256_before,generated.provider_result_sha256);
      const marker=await privateRead(secondMarkerPath);assert.equal(marker.encounter_id,encounterId);report.second_attempt_marker_sha256=hash(await fs.readFile(secondMarkerPath));
      assert.equal(hash(await fs.readFile(firstMarkerPath)),report.first_attempt_marker_sha256);
      await page.goto(encounterURL);snapshotBefore=await api(context);
      assert.equal(snapshotBefore.notes.replace(/\r\n/g,'\n'),scenario.notes.replace(/\r\n/g,'\n'));scenario.notes=snapshotBefore.notes;
      assert.equal(snapshotBefore.status,'review');assert([0,1].includes(snapshotBefore.revision),'Only the untouched draft or the single saved-but-unreviewed revision may be resumed.');
      if(snapshotBefore.revision===0)assert.deepEqual(snapshotBefore.answers,draft.answers,'Stored answers must still equal the automatic draft; nobody edited them.');
      else{
        // A prior review attempt saved the unchanged automatic values (revision1) and stopped before any review checkbox.
        for(const field of fixture.fields){const stored=snapshotBefore.answers[field.key];const auto=draft.answers[field.key];
          assert.equal(stored.text,auto.text);assert.equal(stored.status,auto.status);assert.equal(stored.reviewed,false);}
        report.resumed_after_unreviewed_save=true;
      }
      const record=page.getByRole('heading',{name:'Document record',exact:true}).locator('..');
      assert.deepEqual(await record.locator('.badge').allTextContents(),['succeeded']);
      assert.equal(localURL(await record.getByRole('link',{name:'Download provider result',exact:true}).getAttribute('href')),resultURL);
      assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),0);assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
    });
    await check('Record automatic values versus expected and apply only the clinician corrections that differ',async()=>{
      const fields=[];const edits=[];
      for(const field of fixture.fields){
        const auto=draft.answers[field.key];const expected=scenario.answers[field.key].text;
        const input=page.locator(`[name="answer_${field.key}"]`);
        assert.equal(await input.inputValue(),auto.text,'Form must display the automatic value before any edit.');
        const evidenceBound=evidenceSupports(scenario.notes,field,auto);
        const row={key:field.key,kind:field.kind,automatic_status:auto.status,automatic_text_sha256:hash(auto.text),
          automatic_evidence_count:Array.isArray(auto.evidence)?auto.evidence.length:0,automatic_evidence_bound:evidenceBound,
          matches_expected:auto.status==='supported'&&auto.text===expected,clinician_edited:false};
        if(!row.matches_expected){
          const line=labelledLine(scenario.notes,field.label);
          if(field.kind==='choice')await input.selectOption(expected);else await input.fill(expected);
          await page.locator(`[name="source_${field.key}"]`).fill(line);
          row.clinician_edited=true;edits.push({key:field.key,from_status:auto.status,reason:auto.status==='supported'?'automatic value differed from documented value':'automatic status '+auto.status});
        }
        fields.push(row);
      }
      report.field_review=fields;report.clinician_edits=edits;report.explicit_clinician_edit_count=edits.length;
      report.automatic_correct_count=fields.filter(row=>row.matches_expected).length;report.new_provider_requests=0;
      console.log('Clinician corrections required: '+edits.length+' of 90');
    });
    await check('Select approved statement alternatives and quote their sources, then save',async()=>{
      assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),0);
      assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
      const decisions=[];
      for(const requirement of scenario.requirements){
        const variant=page.locator(`select[name="claim_variant_${requirement.key}"]`);
        const chosen=scenario.claim_variants[requirement.key];
        if(await variant.count())await variant.selectOption(chosen);
        else assert.equal(await page.locator(`input[name="claim_variant_${requirement.key}"]`).inputValue(),chosen);
        let sourced=false;
        if(requirement.kind==='assertion'){
          const line=labelledLine(scenario.notes,requirement.label);
          assert.equal(line.slice(requirement.label.length+1).trim(),requirement.text.trim());
          await page.locator(`[name="claim_source_${requirement.key}"]`).fill(line);sourced=true;
        }
        decisions.push({key:requirement.key,kind:requirement.kind,variant:chosen,source_quoted:sourced});
      }
      report.clinician_statement_decisions=decisions;
      await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();
      const snapshot=await api(context);assert.equal(snapshot.notes,scenario.notes);assert.equal(snapshot.revision,snapshotBefore.revision+1);
      for(const field of fixture.fields)assert.equal(snapshot.answers[field.key].text,scenario.answers[field.key].text);
      assert.equal(await page.locator('input[name^=claim_reviewed_]:checked').count(),0);
      // Before any review checkbox, the only permitted blocker is the review requirement itself.
      const errors=await page.locator('.answer .error-text').allTextContents();
      const other=errors.map(text=>text.trim()).filter(text=>!text.startsWith('A clinician must review'));
      assert.deepEqual(other,[],'Saved answers must carry no blocker other than the pending clinician review.');
      report.pre_review_blockers={review_required:errors.length-other.length,other:other.length};
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
      const destination=path.join(output,'synthetic-wm-fresh-'+scenarioName+'.docx');await privateBytes(destination,bytes);
      report.export_sha256=hash(bytes);report.export_bytes=bytes.length;report.export_artifact=destination;
      report.export_xml_control_and_structure_verification='Pending independent Python XML/ledger verifier.';
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
    const finalProviderResponse=await context.request.get(resultURL);assert.equal(hash(await finalProviderResponse.body()),report.provider_result_sha256_before);
    assert.equal(hash(await fs.readFile(secondMarkerPath)),report.second_attempt_marker_sha256);
    assert.equal(report.generation_click_attempts,0);
  }
  if(phase==='generate'){assert.equal(report.generation_click_attempts,1);assert.equal(report.network_generation_submissions,1);}
  else{assert.equal(report.generation_click_attempts,0);assert.equal(report.network_generation_submissions,0);}
  assert.equal(report.voice_submissions,0);assert.equal(report.payment_submissions,0);assert.equal(report.notes_edit_submissions||0,0);
  report.passed=true;report.completed_at=new Date().toISOString();
  await privateJSON(path.join(output,reportName),report);wroteReport=true;
  console.log('Phase '+phase+' passed. Report: '+path.join(output,reportName));
}catch(error){
  report.active_check=stage;report.error_class=error?.constructor?.name||'Error';report.error_message=String(error?.message||'').slice(0,300);
  report.error_line=String(error?.stack||'').split('\n').find(line=>/^\s*at\s/.test(line)&&line.includes('wm-live-fresh.mjs'))?.trim()||'';
  if(output&&!wroteReport)await privateJSON(path.join(output,reportName),report).catch(()=>{});
  console.error('Phase '+phase+' stopped at: '+stage+'. No automatic generation retry was attempted. '+report.error_message);
  process.exitCode=1;
}finally{await browser?.close();}
