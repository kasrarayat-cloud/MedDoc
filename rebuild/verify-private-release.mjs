/** Bounded private release proof. Run only with authorization to spend up to USD 1.
 * Usage: node rebuild/verify-private-release.mjs --expected-release FULL_COMMIT_SHA
 * Requires synthetic seed credentials, local espeak-ng, real configured providers,
 * the existing Django venv, and Playwright. No screenshot or clinical export is
 * retained outside application storage; only a sanitized JSON report is written.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const require=createRequire(import.meta.url);
const appRoot=path.dirname(fileURLToPath(import.meta.url));
const runtime=path.join(appRoot,'.runtime');
const doctorBase=process.env.QUILLMD_BROWSER_BASE_URL||'http://127.0.0.1:9130';
const adminBase=process.env.QUILLMD_ADMIN_BASE_URL||'http://127.0.0.1:9131';
for(const value of [doctorBase,adminBase]){const url=new URL(value);assert(['127.0.0.1','localhost'].includes(url.hostname)&&!url.username&&!url.password);}
const moduleDirectory=process.env.PLAYWRIGHT_MODULE_DIR;
const report={providerJobLimit:2,maximumAuthorizedUsd:1,startedAt:new Date().toISOString(),checks:[],liveGeneration:null,liveVoice:null,maximumTotalReservationsUsd:0,complete:false};
let currentCheck='Permanent application path and private synthetic credentials',browser,temporaryDirectory;
async function check(name,action){currentCheck=name;await action();report.checks.push({name,passed:true});console.log(`PASS ${name}`);}
function python(code,args=[]){
 const result=spawnSync(path.join(appRoot,'.venv','bin','python'),['-c',code,...args],{cwd:appRoot,encoding:'utf8',timeout:30000,maxBuffer:1024*1024});
 assert.equal(result.status,0,'Bounded synthetic document operation failed.');return result.stdout;
}
function totp(hexKey){const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));const digest=crypto.createHmac('sha1',Buffer.from(hexKey,'hex')).update(counter).digest();return String((digest.readUInt32BE(digest[digest.length-1]&15)&0x7fffffff)%1000000).padStart(6,'0');}
try{
 assert.equal(process.env.QUILLMD_BETA_LIVE,'1','Set QUILLMD_BETA_LIVE=1 to authorize the bounded provider smoke.');
 assert.equal(await fs.realpath(appRoot),appRoot);
 const cli=process.argv.slice(2);assert(cli.length===0||(cli.length===2&&cli[0]==='--expected-release'));
 const expectedRelease=cli[1]||process.env.QUILLMD_EXPECTED_RELEASE;assert(/^[0-9a-f]{40}$/.test(expectedRelease||''));report.release=expectedRelease;
 const credentialsPath=process.env.QUILLMD_BROWSER_CREDENTIALS||path.join(runtime,'private-access.json');
 const credentialsMeta=await fs.lstat(credentialsPath);assert(credentialsMeta.isFile()&&(credentialsMeta.mode&0o077)===0,'Credentials must be a private regular file.');
 const credentials=JSON.parse(await fs.readFile(credentialsPath,'utf8'));
 assert(credentials.doctor?.email.endsWith('@synthetic.quillmd.invalid'));
 assert(credentials.admin?.email.endsWith('@synthetic.quillmd.invalid'));
 const {chromium}=moduleDirectory?require(path.resolve(moduleDirectory,'@playwright/test')):require('@playwright/test');
 temporaryDirectory=await fs.mkdtemp(path.join(runtime,'activation-smoke-'));await fs.chmod(temporaryDirectory,0o700);
 const templatePath=path.join(temporaryDirectory,'synthetic-activation-template.docx');
 await check('Create a bounded blank synthetic Word form',async()=>{
  python(`from docx import Document\nfrom pathlib import Path\nimport sys\np=Path(sys.argv[1])\ndoc=Document()\ndoc.add_heading('Synthetic activation assessment',0)\ndoc.add_paragraph('Private activation verification. No patient data.')\ntable=doc.add_table(rows=0,cols=2)\ntable.style='Table Grid'\nfor label in ['History','Findings','Plan']:\n cells=table.add_row().cells\n cells[0].text=label\n cells[1].text=''\ndoc.save(p)\np.chmod(0o600)\n`,[templatePath]);
 });
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:true});
 const page=await context.newPage();page.setDefaultTimeout(25000);
 await check('Both permanent services identify the exact promoted release',async()=>{for(const base of [doctorBase,adminBase]){const response=await page.request.get(base+'/health/');assert.equal(response.status(),200);assert.equal((await response.json()).release,expectedRelease);}});
 const clientErrors=[];page.on('pageerror',()=>clientErrors.push('Doctor client script error'));
 await check('Doctor signs into the permanent private service',async()=>{
  const response=await page.goto(doctorBase+'/login/');assert.equal(response.status(),200);
  await page.locator('[name=email]').fill(credentials.doctor.email);await page.locator('[name=password]').fill(credentials.doctor.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL(doctorBase+'/');
  assert.equal(await page.locator('.integration-list .badge').filter({hasText:/^Live API configured$/}).count(),1);
 });
 await check('Upload blank form through the supervised application parser',async()=>{
  await page.goto(doctorBase+'/templates/upload/');await page.locator('[name=name]').fill('Synthetic activation assessment '+Date.now());
  await page.locator('[name=department]').selectOption({label:'X-ray'});await page.locator('[name=file]').setInputFiles(templatePath);await page.locator('[name=synthetic_only]').check();
  await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);
  assert.equal(await page.locator('tbody tr').count(),3);assert.deepEqual(await page.locator('tbody tr td:first-child').allTextContents(),['History','Findings','Plan']);
 });
 let selectedTemplateLabel;
 await check('Review original mapping and save its next version',async()=>{
  await page.getByText('Edit field mapping',{exact:true}).click();assert.equal(await page.locator('[data-mapping-editor] input').count(),3);
  await page.getByRole('button',{name:'Save new mapping version',exact:true}).click();await page.waitForLoadState();assert.equal(await page.getByText('Mapping v2',{exact:true}).count(),1);
  selectedTemplateLabel=(await page.locator('h1').innerText())+' · mapping 2';await page.getByRole('link',{name:'Use this form'}).click();
 });
 await check('Create a new synthetic encounter with three documented statements',async()=>{
  await page.locator('[name=patient]').selectOption({label:'Synthetic Example X-ray · X-ray'});await page.locator('[name=template_version]').selectOption({label:selectedTemplateLabel});
  await page.locator('[name=notes]').fill('History: Synthetic adult reports left wrist discomfort after a fall yesterday.\nFindings: No visible deformity documented. Wrist range of motion is limited by discomfort.\nPlan: Wrist radiographs requested and follow-up assessment planned.');
  await page.locator('[name=synthetic_only]').check();await page.getByRole('button',{name:'Create document',exact:true}).click();await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);
  report.encounterId=new URL(page.url()).pathname.split('/')[2];
 });
 await check('Transcribe one synthetic speech sample and correct its notes',async()=>{
  const form=page.locator('[data-voice-form]');const quoted=(await form.innerText()).match(/Limit \$([0-9]+(?:\.[0-9]+)?) per recording/);assert(quoted);const ceiling=Number(quoted[1]);assert(ceiling>0&&ceiling<=1);assert((await form.locator('[name=usage_quote]').inputValue()).length>20);report.maximumTotalReservationsUsd+=ceiling;
  const audioPath=path.join(temporaryDirectory,'synthetic-speech.wav');const speech=spawnSync(process.env.QUILLMD_ESPEAK||'espeak-ng',['-s','145','-w',audioPath,'Synthetic patient with left wrist pain. No fracture seen. Follow up in one week.'],{encoding:'utf8',timeout:15000});assert.equal(speech.status,0,'Local synthetic speech generation failed.');await fs.chmod(audioPath,0o600);
  report.audioSeconds=JSON.parse(python("import wave,json,sys\nwith wave.open(sys.argv[1]) as f: duration=f.getnframes()/f.getframerate()\nassert 0<duration<=15\nprint(json.dumps(duration))\n",[audioPath]));await form.locator('[name=audio]').setInputFiles(audioPath);await form.locator('[name=consent]').check();await page.getByRole('button',{name:'Transcribe recording',exact:true}).click();
  for(let i=0;i<90;i++){await page.waitForTimeout(1000);await page.reload();if(await page.getByRole('link',{name:'Download provider result',exact:true}).count())break;assert(!(await page.locator('.source-panel .badge').allTextContents()).some(s=>['failed','reconciliation'].includes(s)));}
  const notes=(await page.locator('.source-notes').innerText()).toLowerCase();assert(notes.includes('left wrist')&&notes.includes('no fracture')&&notes.includes('follow'));
  report.liveVoice=JSON.parse(python(`import os,json,sys\nfrom decimal import Decimal\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django;django.setup()\nfrom core.models import Job,Usage,ProviderReceipt\nj=Job.objects.get(encounter_id=sys.argv[1],kind='transcription');u=Usage.objects.get(job=j);r=ProviderReceipt.objects.get(job=j)\nassert j.state=='succeeded' and not u.simulated and u.provider=='deepgram:nova-3-medical'\nassert u.provider_request_id and u.provider_request_id==r.provider_request_id==j.provider_request_id\nassert j.pricing_snapshot.startswith('configured-v1:')\nfrom core.management.commands.audit_billing import audit_report\nrow=[x for x in audit_report()['rows'] if x['job_id']==str(j.pk)]\nassert u.actual_cost>0 and len(row)==1 and row[0]['checks']['exact_1_5_multiplier'] and row[0]['checks']['over_limit_absorbed_exactly'] and u.charged_cost<=Decimal(sys.argv[2])\nprint(json.dumps({'jobId':str(j.pk),'provider':u.provider,'actualCostUsd':str(u.actual_cost),'userChargeUsd':str(u.charged_cost),'httpRequestId':u.http_request_id,'pricingVersion':j.pricing_snapshot,'simulated':False}))\n`,[report.encounterId,quoted[1]]));
  await page.getByText('Edit source notes',{exact:true}).click();await page.locator('#source-notes-edit').fill('History: Synthetic adult reports left wrist discomfort after a fall yesterday.\nFindings: No fracture documented.\nPlan: Follow-up in one week documented.');await page.getByRole('button',{name:'Save source notes',exact:true}).click();await page.waitForLoadState();assert.equal(await page.locator('textarea[name^=answer_]').count(),0);report.voiceCorrectionSaved=true;
 });
 await check('Authorize live generation only within the displayed USD 1 ceiling',async()=>{
  const form=page.locator('form').filter({has:page.getByRole('button',{name:'Generate supported answers',exact:true})});const text=await form.innerText();const match=text.match(/Reserve up to \$([0-9]+(?:\.[0-9]+)?)/);
  assert(match,'A live reservation quote must be visible.');const reservation=Number(match[1]);assert(Number.isFinite(reservation)&&reservation>0&&report.maximumTotalReservationsUsd+reservation<=1);report.maximumTotalReservationsUsd+=reservation;
  assert(text.includes('personal promotional credit used first'));assert((await form.locator('[name=usage_quote]').inputValue()).length>20);report.maximumReservationUsd=match[1];
  await page.getByRole('button',{name:'Generate supported answers',exact:true}).click();
  for(let attempt=0;attempt<150;attempt++){await page.waitForTimeout(1000);await page.reload();if(await page.locator('textarea[name^=answer_]').count())break;const states=await page.locator('.source-panel .badge').allTextContents();assert(!states.some(state=>['failed','reconciliation'].includes(state)),'Provider job requires intervention.');}
  assert.equal(await page.locator('textarea[name^=answer_]').count(),3);assert.equal(await page.locator('.evidence blockquote').count(),3);assert.equal(await page.getByRole('link',{name:'Download provider result',exact:true}).count(),2);
 });
 await check('Verify actual Anthropic receipt and exact settled promotional charge',async()=>{
  report.liveGeneration=JSON.parse(python(`import os,json,sys\nfrom decimal import Decimal\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\nfrom core.models import Encounter,Job,Usage,ProviderReceipt,LedgerEntry\ne=Encounter.objects.get(pk=sys.argv[1])\nassert e.created_by.email.endswith('@synthetic.quillmd.invalid')\nj=Job.objects.get(encounter=e,kind='generation')\nu=Usage.objects.get(job=j)\nr=ProviderReceipt.objects.get(job=j)\nassert j.state=='succeeded'\nassert u.provider.startswith('anthropic:') and not u.simulated and not r.simulated\nassert j.http_request_id.startswith('req_') and j.resource_id.startswith('msg_')\nassert u.http_request_id==r.http_request_id==j.http_request_id and u.resource_id==r.resource_id==j.resource_id\nassert j.pricing_snapshot.startswith('configured-v1:')\nassert u.actual_cost>0 and u.charged_cost==u.actual_cost*Decimal('1.5')\nassert r.actual_cost==u.actual_cost and u.charged_cost<=Decimal(sys.argv[2])\ndebits=LedgerEntry.objects.filter(job=j,amount__lt=0).select_related('wallet')\nassert debits.exists() and all(x.wallet.kind=='promo' and x.wallet.user_id==e.created_by_id for x in debits)\nprint(json.dumps({'provider':u.provider,'actualCostUsd':str(u.actual_cost),'userChargeUsd':str(u.charged_cost),'simulated':u.simulated,'payer':'personal promotional credit','jobId':str(j.pk),'httpRequestId':j.http_request_id,'resourceId':j.resource_id,'pricingVersion':j.pricing_snapshot}))\n`,[report.encounterId,report.maximumReservationUsd]));
 });
 await check('Clinician reviews and finalizes all three supported answers',async()=>{
  for(const field of await page.locator('textarea[name^=answer_]').all())assert((await field.inputValue()).trim().length>0);
  for(const checkbox of await page.locator('input[name^=reviewed_]').all())await checkbox.check();await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();
  assert.equal(await page.locator('input[name^=reviewed_]:checked').count(),3);await page.locator('[name=reviewed]').check();await page.getByRole('button',{name:'Finalize document',exact:true}).click();await page.waitForLoadState();assert.equal(await page.getByRole('link',{name:'Export original format'}).count(),1);
 });
 await check('Download Word export and verify original questions and complete answers',async()=>{
  const pending=page.waitForEvent('download');await page.getByRole('link',{name:'Export original format'}).click();const download=await pending;assert(download.suggestedFilename().endsWith('.docx'));
  const exportPath=path.join(temporaryDirectory,'synthetic-finalized.docx');await download.saveAs(exportPath);
  python(`from docx import Document\nimport os,sys\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\nfrom core.models import Encounter\ne=Encounter.objects.get(pk=sys.argv[2])\ndoc=Document(sys.argv[1])\nassert e.status=='finalized'\nassert len(doc.tables)==1 and len(doc.tables[0].rows)==3\nassert [row.cells[0].text for row in doc.tables[0].rows]==['History','Findings','Plan']\nfields=e.template_version.fields\nassert [row.cells[1].text for row in doc.tables[0].rows]==[e.answers[field['key']]['text'] for field in fields]\n`,[exportPath,report.encounterId]);
 });
 await check('Private invitation, single welcome grant, and password recovery work after deployment',async()=>{
  python("import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django;django.setup()\nfrom django.conf import settings\nassert settings.QUILLMD_EMAIL_MODE=='file'\n");
  const email='release-'+Date.now()+'@synthetic.quillmd.invalid',password=crypto.randomBytes(24).toString('base64url');
  await page.goto(doctorBase+'/team/');const invitationForm=page.locator('form').filter({has:page.getByRole('button',{name:'Create invitation',exact:true})});await invitationForm.locator('[name=email]').fill(email);await invitationForm.locator('[name=department]').selectOption({label:'X-ray'});await invitationForm.locator('[name=role]').selectOption('employee');await page.getByRole('button',{name:'Create invitation',exact:true}).click();await page.waitForLoadState();
  function privateMailRoute(kind){return JSON.parse(python(`import os,json,re,sys\nfrom pathlib import Path\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django;django.setup()\nfrom django.conf import settings\nassert settings.QUILLMD_EMAIL_MODE=='file'\nfound=[]\npattern=r'/'+sys.argv[2]+r'/([A-Za-z0-9_/-]+)/'\nfor p in Path(settings.EMAIL_FILE_PATH).glob('*'):\n text=p.read_text()\n if sys.argv[1] in text:\n  match=re.search(pattern,text)\n  if match:found.append('/'+sys.argv[2]+'/'+match.group(1).rstrip('/')+'/')\nassert len(found)==1\nprint(json.dumps(found[0]))\n`,[email,kind]));}
  const invitation=privateMailRoute('invite');const employeeContext=await browser.newContext();const employee=await employeeContext.newPage();await employee.goto(doctorBase+invitation);await employee.locator('[name=email]').fill(email);await employee.locator('[name=first_name]').fill('Synthetic');await employee.locator('[name=last_name]').fill('Release Test');await employee.locator('[name=password1]').fill(password);await employee.locator('[name=password2]').fill(password);await employee.locator('[name=synthetic_only]').check();await employee.getByRole('button',{name:'Accept invitation',exact:true}).click();await employee.waitForURL(doctorBase+'/login/');assert.equal((await employee.request.get(doctorBase+invitation)).status(),404);
  async function employeeLogin(target,secret){await target.goto(doctorBase+'/login/');await target.locator('[name=email]').fill(email);await target.locator('[name=password]').fill(secret);await target.getByRole('button',{name:'Sign in',exact:true}).click();}
  await employeeLogin(employee,password);await employee.waitForURL(doctorBase+'/');assert.deepEqual(await(await employee.request.get(doctorBase+'/api/patients/')).json(),await(await page.request.get(doctorBase+'/api/patients/')).json());
  const recoveryContext=await browser.newContext(),recovery=await recoveryContext.newPage();await recovery.goto(doctorBase+'/recovery/');await recovery.locator('[name=email]').fill(email);await recovery.getByRole('button',{name:'Prepare recovery link',exact:true}).click();assert((await recovery.locator('[role=status]').innerText()).includes('If this address is eligible'));
  const reset=privateMailRoute('recovery/confirm');await recovery.goto(doctorBase+reset);assert(new URL(recovery.url()).pathname.endsWith('/set-password/'));const replacement=crypto.randomBytes(24).toString('base64url');await recovery.locator('[name=new_password1]').fill(replacement);await recovery.locator('[name=new_password2]').fill(replacement);await recovery.getByRole('button',{name:'Update password',exact:true}).click();await recovery.waitForURL(doctorBase+'/recovery/complete/');assert.equal((await recovery.request.get(doctorBase+'/',{maxRedirects:0})).status(),302);
  await employee.goto(doctorBase+'/patients/');assert.equal(new URL(employee.url()).pathname,'/login/');await employeeLogin(recovery,password);assert.equal(new URL(recovery.url()).pathname,'/login/');await employeeLogin(recovery,replacement);await recovery.waitForURL(doctorBase+'/');await recovery.goto(doctorBase+reset);assert.equal(await recovery.getByRole('heading',{name:'Recovery link unavailable',exact:true}).count(),1);
  python("import os,sys\nfrom decimal import Decimal\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django;django.setup()\nfrom core.models import User,Wallet,LedgerEntry\nu=User.objects.get(email=sys.argv[1]);w=Wallet.objects.get(user=u,kind='promo')\nassert u.verified_at and w.balance==Decimal('10') and w.reserved==0\nassert LedgerEntry.objects.filter(wallet=w,kind='welcome').count()==1\n",[email]);await employeeContext.close();await recoveryContext.close();
 });
 await check('Administrator authenticates with MFA on the separate permanent service',async()=>{
  const adminContext=await browser.newContext({viewport:{width:1440,height:1080}});const admin=await adminContext.newPage();admin.on('pageerror',()=>clientErrors.push('Administrator client script error'));
  const response=await admin.goto(adminBase+'/login/');assert.equal(response.status(),200);await admin.locator('[name=email]').fill(credentials.admin.email);await admin.locator('[name=password]').fill(credentials.admin.password);
  await admin.waitForTimeout(31000-Date.now()%30000);await admin.locator('[name=otp]').fill(totp(credentials.admin.totp_key_hex));await admin.getByRole('button',{name:'Sign in to administration',exact:true}).click();await admin.waitForURL(adminBase+'/console/');
  for(const name of ['Accounts','Document jobs','Underlying costs & user charges','Provider cost receipts','Reconciliation'])assert.equal(await admin.getByRole('heading',{name,exact:true}).count(),1);
  assert((await admin.locator('#provider-receipts').innerText()).includes(report.liveGeneration.jobId));
 });
 await check('Exactly two metered jobs remain within the total authorized charge',async()=>{
  report.total=JSON.parse(python(`import os,json,sys\nfrom decimal import Decimal\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django;django.setup()\nfrom core.models import Job,Usage,Reservation\njobs=Job.objects.filter(encounter_id=sys.argv[1])\nassert jobs.count()==2 and set(jobs.values_list('kind',flat=True))=={'generation','transcription'}\nassert all(j.state=='succeeded' for j in jobs)\nassert not Reservation.objects.filter(job__in=jobs,state='held').exists()\nusage=Usage.objects.filter(job__in=jobs);assert usage.count()==2\ncharged=sum(usage.values_list('charged_cost',flat=True),Decimal('0'))\nassert 0<charged<=Decimal('1')\nprint(json.dumps({'providerJobs':2,'userChargeUsd':str(charged),'heldReservations':0}))\n`,[report.encounterId]));
 });
 await check('No doctor or administrator client script errors',async()=>assert.equal(clientErrors.length,0));report.complete=true;
}catch(error){
 report.errorClass=error.name;report.testLine=Number(error.stack?.match(/verify-private-release\.mjs:(\d+):\d+/)?.[1])||null;
 report.checks.push({name:currentCheck,passed:false});console.error(`FAIL ${currentCheck}; sensitive exception details suppressed.`);process.exitCode=1;
}finally{
 await browser?.close();
 if(temporaryDirectory){assert.equal(path.dirname(temporaryDirectory),runtime);assert(path.basename(temporaryDirectory).startsWith('activation-smoke-'));await fs.rm(temporaryDirectory,{recursive:true,force:true});}
 report.finishedAt=new Date().toISOString();report.scratchFilesRemoved=true;
 await fs.writeFile(path.join(runtime,'beta-deployed-browser-verification.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
 console.log(`${report.checks.filter(item=>item.passed).length} activated browser checks passed; complete=${report.complete}.`);
}
