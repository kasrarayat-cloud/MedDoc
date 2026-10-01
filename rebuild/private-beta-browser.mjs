/** Private synthetic beta checks. No raw exception, credential, note or export is logged.
 * Defaults to fixture listeners 9140/9141. Live mode requires QUILLMD_BETA_LIVE=1;
 * the sum of displayed reservation ceilings must stay at or below USD 1.
 * Supply QUILLMD_TEST_ENV_FILE and QUILLMD_TEST_PYTHON for the existing private
 * Django environment; QUILLMD_TEST_APP points to the code actually being served.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const require=createRequire(import.meta.url);
const scriptRoot=path.dirname(fileURLToPath(import.meta.url));
const app=path.resolve(process.env.QUILLMD_TEST_APP||scriptRoot);
const runtime=path.join(app,'.runtime');
const live=process.env.QUILLMD_BETA_LIVE==='1';
const doctorBase=process.env.QUILLMD_BROWSER_BASE_URL||'http://127.0.0.1:9140';
const adminBase=process.env.QUILLMD_ADMIN_BASE_URL||'http://127.0.0.1:9141';
for(const url of [doctorBase,adminBase])assert(['127.0.0.1','localhost'].includes(new URL(url).hostname));
const report={startedAt:new Date().toISOString(),mode:live?'live':'fixture',checks:[],maximumReservedUsd:0,usage:[],complete:false};
let active='Initialization',browser,scratch;
function python(code,payload={}){
 const header=`import os,json,sys\nfrom dotenv import dotenv_values\nsource=os.environ.get('QUILLMD_TEST_ENV_FILE')\nif source:\n for k,v in dotenv_values(source).items():\n  if v is not None:os.environ.setdefault(k,v)\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\npayload=json.loads(sys.stdin.read())\n`;
 const result=spawnSync(process.env.QUILLMD_TEST_PYTHON||path.join(app,'.venv/bin/python'),['-c',header+code],{cwd:app,encoding:'utf8',input:JSON.stringify(payload),timeout:30000,maxBuffer:2*1024*1024});
 assert.equal(result.status,0,'Private helper failed; output intentionally suppressed.');return result.stdout?JSON.parse(result.stdout):null;
}
async function check(name,action){active=name;await action();report.checks.push({name,passed:true});console.log('PASS '+name);}
function token(key){const b=Buffer.alloc(8);b.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));const h=crypto.createHmac('sha1',Buffer.from(key,'hex')).update(b).digest();return String((h.readUInt32BE(h.at(-1)&15)&0x7fffffff)%1000000).padStart(6,'0');}
async function login(page,account,base=doctorBase,otp=''){
 await page.goto(base+'/login/');await page.locator('[name=email]').fill(account.email);await page.locator('[name=password]').fill(account.password);
 if(otp)await page.locator('[name=otp]').fill(otp);
 await page.getByRole('button',{name:base===adminBase?'Sign in to administration':'Sign in',exact:true}).click();
}
async function status(page,url){return (await page.request.get(url,{maxRedirects:0})).status();}
async function reserve(form){
 const text=await form.innerText();
 if(!live){assert(text.includes('Synthetic fixture'));return;}
 const amount=Number(text.match(/(?:Reserve up to|Limit) \$([0-9]+(?:\.[0-9]+)?)/)?.[1]);assert(Number.isFinite(amount)&&amount>0);
 assert(report.maximumReservedUsd+amount<=1,'Total displayed live reservation exceeds USD 1.');
 assert((await form.locator('[name=usage_quote]').inputValue()).length>20);report.maximumReservedUsd+=amount;
}
async function generated(page){
 const form=page.locator('form').filter({has:page.getByRole('button',{name:'Generate supported answers',exact:true})});await reserve(form);
 await page.getByRole('button',{name:'Generate supported answers',exact:true}).click();
 for(let i=0;i<90;i++){await page.waitForTimeout(1000);await page.reload();if(await page.locator('textarea[name^=answer_]').count())return;assert(!(await page.locator('.source-panel [data-request-status]').evaluateAll(n=>n.map(e=>e.dataset.requestStatus))).some(s=>['held','not_completed','completed_not_applied','unknown'].includes(s)));}
 assert.fail('Generation timed out');
}
async function upload(page,file,label){
 await page.goto(doctorBase+'/templates/upload/');await page.locator('[name=name]').fill(label);await page.locator('[name=department]').selectOption({label:'X-ray'});
 await page.locator('[name=file]').setInputFiles(file);await page.locator('[name=synthetic_only]').check();await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();
}
async function encounter(page,label,notes){
 await page.goto(doctorBase+'/encounters/new/');await page.locator('[name=patient]').selectOption({label:'Synthetic Example X-ray · X-ray'});
 await page.locator('[name=template_version]').selectOption({label});await page.locator('[name=notes]').fill(notes);await page.locator('[name=synthetic_only]').check();
 await page.getByRole('button',{name:'Create document',exact:true}).click();await page.waitForURL(/\/encounters\/[0-9a-f-]+\/$/);return new URL(page.url()).pathname.split('/')[2];
}
async function review(page){for(const box of await page.locator('input[name^=reviewed_]').all())await box.check();await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();await page.waitForLoadState();}
async function finalize(page){await page.locator('[name=reviewed]').check();await page.getByRole('button',{name:'Finalize document',exact:true}).click();await page.waitForLoadState();}
async function download(page,extension){const pending=page.waitForEvent('download');await page.getByRole('link',{name:'Export original format'}).click();const item=await pending;const dest=path.join(scratch,'result.'+extension);await item.saveAs(dest);return dest;}
function mailSnapshot(){return python("from ops import private_mail\nfrom django.conf import settings\n"
 +"assert settings.QUILLMD_EMAIL_MODE=='file' and str(settings.EMAIL_FILE_PATH)==str(private_mail.OUTBOX)\n"
 +"print(json.dumps({'files':private_mail.snapshot()}))\n").files;}
function mailRoute(kind,address,before){const found=python("from ops import account_mail\nnotes={}\n"
 +"route=account_mail.locate(payload['kind'],payload['address'],payload['before'],notes=notes)\n"
 +"print(json.dumps({'route':route,'notes':notes}))\n",{kind,address,before});
 assert.equal(found.notes.token_bound,true,'the located token is not bound to this run\'s own record');
 return found.route;}
try{
 const credentials=JSON.parse(await fs.readFile(process.env.QUILLMD_BROWSER_CREDENTIALS||path.join(runtime,'private-access.json'),'utf8'));
 for(const key of ['doctor','xray_employee','ultrasound','other_org','admin'])assert(credentials[key].email.endsWith('@synthetic.quillmd.invalid'));
 const {chromium}=process.env.PLAYWRIGHT_MODULE_DIR?require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,'@playwright/test')):require('@playwright/test');
 scratch=await fs.mkdtemp(path.join(runtime,'beta-browser-'));await fs.chmod(scratch,0o700);
 report.source=python("from django.conf import settings\nimport subprocess\nassert settings.SYNTHETIC_ONLY and settings.QUILLMD_EMAIL_MODE=='file'\nassert (settings.AI_MODE=='live')==payload['live']\nprint(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'code_root':str(settings.BASE_DIR),'session_age_seconds':settings.SESSION_COOKIE_AGE}))",{live});
 python("from docx import Document\nfrom reportlab.pdfgen import canvas\nfrom pathlib import Path\nr=Path(payload['directory'])\nd=Document();d.add_heading('Synthetic beta form',0);t=d.add_table(rows=0,cols=2)\nfor label in ['History','Findings','Plan']:\n c=t.add_row().cells;c[0].text=label\nd.save(r/'form.docx')\np=canvas.Canvas(str(r/'form.pdf'))\nfor i,label in enumerate(['History','Findings','Plan']):\n y=700-i*180;p.drawString(30,y+100,label);p.acroForm.textfield(name=label,x=30,y=y,width=500,height=90,fontName='Helvetica',fontSize=10,maxlen=20000,fieldFlags='multiline')\np.showPage();p.save()\np=canvas.Canvas(str(r/'flat.pdf'));p.drawString(30,700,'Synthetic flat question');p.showPage();p.save()",{directory:scratch});
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:true});const page=await context.newPage();page.setDefaultTimeout(20000);
 await check('Doctor login, protected cookies, logout, and fresh relogin',async()=>{
  await login(page,credentials.doctor);await page.waitForURL(doctorBase+'/');
  const session=(await context.cookies()).find(c=>c.name==='quillmd_doctor_session');assert(session.httpOnly&&session.sameSite==='Strict');
  assert.equal(await status(page,doctorBase+'/logout/'),405);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL(doctorBase+'/login/');assert.equal(await status(page,doctorBase+'/'),302);
  await login(page,credentials.doctor);await page.waitForURL(doctorBase+'/');
 });
 await check('Server-side expiry of this test session requires authentication',async()=>{
  const session=(await context.cookies()).find(c=>c.name==='quillmd_doctor_session');
  python("from django.contrib.sessions.models import Session\nfrom django.utils import timezone\nfrom datetime import timedelta\ns=Session.objects.get(session_key=payload['session']);assert s.get_decoded().get('_auth_user_id')\ns.expire_date=timezone.now()-timedelta(seconds=1);s.save(update_fields=['expire_date'])",{session:session.value});
  await page.goto(doctorBase+'/patients/');await page.waitForURL(/\/login\//);await login(page,credentials.doctor);await page.waitForURL(doctorBase+'/');
 });
 let docTemplate,docId,pdfId,resultJob,invitedAccount;
 const suffix=Date.now();const docName='Synthetic beta Word '+suffix,pdfName='Synthetic beta PDF '+suffix;
 await check('Upload Word original and version the reviewed field mapping',async()=>{
  await upload(page,path.join(scratch,'form.docx'),docName);await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);docTemplate=new URL(page.url()).pathname.split('/')[2];
  assert.equal(await page.locator('tbody tr').count(),3);await page.getByText('Edit field mapping',{exact:true}).click();await page.getByRole('button',{name:'Save new mapping version',exact:true}).click();await page.waitForLoadState();assert.equal(await page.getByText('Mapping v2',{exact:true}).count(),1);
 });
 await check('Missing information and contradictory statements remain explicit',async()=>{
  docId=await encounter(page,docName+' · mapping 2','History: Synthetic pain started yesterday.\nHistory: Synthetic pain started last month.\nFindings: No deformity documented.');
  await generated(page);assert.equal(await page.locator('.answer .badge.conflict').count(),1);assert.equal(await page.locator('.answer .badge.missing').count(),1);assert.equal(await page.locator('.answer .badge.supported').count(),1);
  assert.equal(await page.locator('.answer').filter({has:page.locator('.badge.conflict')}).locator('.evidence blockquote').count(),2);
  await review(page);await finalize(page);assert.equal(await page.getByRole('link',{name:'Export original format'}).count(),0);assert((await page.locator('body').innerText()).includes('Resolve every conflict'));
  resultJob=(await page.getByRole('link',{name:'Download provider result',exact:true}).getAttribute('href')).split('/')[2];
 });
 await check('Long edited answers export completely after explicit clinical review',async()=>{
  await page.locator('.answer').nth(0).locator('textarea').fill('A'.repeat(20001));await page.getByRole('button',{name:'Save answers and review decisions',exact:true}).click();assert((await page.locator('body').innerText()).includes('nothing was truncated or saved'));await page.goto(doctorBase+'/encounters/'+docId+'/');
  const rows=page.locator('.answer');const long='Synthetic clinician correction. '.repeat(600);
  await rows.nth(0).locator('textarea').fill(long);await rows.nth(2).locator('textarea').fill('');await review(page);await finalize(page);
  const exported=await download(page,'docx');python("from docx import Document\nfrom core.models import Encounter\nfrom core.security import private_path\nimport hashlib\ne=Encounter.objects.get(pk=payload['id']);d=Document(payload['file'])\nassert e.status=='finalized' and len(d.tables[0].cell(0,1).text)==payload['length']\nassert [r.cells[0].text for r in d.tables[0].rows]==['History','Findings','Plan']\nassert [r.cells[1].text for r in d.tables[0].rows]==[e.answers[f['key']]['text'] for f in e.template_version.fields]\nt=e.template_version.template;assert hashlib.sha256(private_path(t.original_path).read_bytes()).hexdigest()==t.sha256",{id:docId,file:exported,length:long.length});
 });
 await check('Upload fillable PDF, generate, review, and export preserved questions',async()=>{
  await upload(page,path.join(scratch,'form.pdf'),pdfName);await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);
  pdfId=await encounter(page,pdfName+' · mapping 1','History: Synthetic wrist discomfort.\nFindings: No deformity documented.\nPlan: Synthetic follow-up planned.');await generated(page);assert.equal(await page.locator('.answer .badge.supported').count(),3);await review(page);await finalize(page);
  const exported=await download(page,'pdf');python("from pypdf import PdfReader\nfrom core.models import Encounter\ne=Encounter.objects.get(pk=payload['id']);r=PdfReader(payload['file'])\nassert e.status=='finalized'\nassert r.get_form_text_fields()=={k:v['text'] for k,v in e.answers.items()}\nassert all(label in r.pages[0].extract_text() for label in ['History','Findings','Plan'])\nassert all('/AP' in a.get_object() for a in r.pages[0]['/Annots'])",{id:pdfId,file:exported});
 });
 await check('Unsupported flat PDF produces an explicit upload error',async()=>{
  await upload(page,path.join(scratch,'flat.pdf'),'Synthetic unsupported flat PDF '+suffix);assert(new URL(page.url()).pathname==='/templates/upload/');assert((await page.locator('.errorlist').innerText()).includes('Flat or scanned PDFs'));
 });
 const allAccounts={};
 await check('Each employee uses an individual login and exact department patient scope',async()=>{
  const doctorPatients=await (await page.request.get(doctorBase+'/api/patients/')).json();allAccounts.doctor=doctorPatients;
  for(const name of ['xray_employee','ultrasound','other_org']){
   const ctx=await browser.newContext();const p=await ctx.newPage();await login(p,credentials[name]);await p.waitForURL(doctorBase+'/');
   const response=await p.request.get(doctorBase+'/api/patients/');assert.equal(response.status(),200);allAccounts[name]=await response.json();
   if(name==='xray_employee'){assert.deepEqual(allAccounts[name],doctorPatients);assert.equal(await status(p,doctorBase+'/encounters/'+docId+'/'),200);assert.equal(await status(p,doctorBase+'/encounters/'+docId+'/export/'),200);}
   else{
    for(const route of ['/encounters/'+docId+'/','/api/encounters/'+docId+'/','/encounters/'+docId+'/export/','/templates/'+docTemplate+'/','/templates/'+docTemplate+'/original/','/jobs/'+resultJob+'/result/'])assert.equal(await status(p,doctorBase+route),404);
    assert.notDeepEqual(allAccounts[name],doctorPatients);
   }
   assert.equal(await status(p,doctorBase+'/console/'),404);await ctx.close();
  }
 });
 await check('Invitation acceptance is single use and grants exactly one personal welcome credit',async()=>{
  const email='beta-'+suffix+'@synthetic.quillmd.invalid',password=crypto.randomBytes(24).toString('base64url');invitedAccount={email,password};
  const invitationOutbox=mailSnapshot();
  await page.goto(doctorBase+'/team/');const invitationForm=page.locator('form').filter({has:page.getByRole('button',{name:'Create invitation',exact:true})});await invitationForm.locator('[name=email]').fill(email);await invitationForm.locator('[name=department]').selectOption({label:'X-ray'});await invitationForm.locator('[name=role]').selectOption('employee');await page.getByRole('button',{name:'Create invitation',exact:true}).click();await page.waitForLoadState();
  // ⚠️ THE OUTBOX IS READ THROUGH ops/private_mail. The local reader that used to be here globbed
  // EMAIL_FILE_PATH as the OPERATOR account — which the service identity now refuses, correctly — and,
  // where it could read, matched the address against a whole FILE and took the first link in it. Django
  // gives outbox filenames one second of entropy and the application opens them O_APPEND, so two sends in
  // one second share a file; a refutation pass ran that shape and watched it return another account's raw
  // invitation token, which this harness then navigates to. One reader, record-level, exact addressee.
  const invitation={route:mailRoute('invite',email,invitationOutbox)};
  const invitedContext=await browser.newContext();const invited=await invitedContext.newPage();await invited.goto(doctorBase+invitation.route);
  await invited.locator('[name=email]').fill(email);await invited.locator('[name=first_name]').fill('Synthetic');await invited.locator('[name=last_name]').fill('Invited Beta');await invited.locator('[name=password1]').fill(password);await invited.locator('[name=password2]').fill(password);await invited.locator('[name=synthetic_only]').check();await invited.getByRole('button',{name:'Accept invitation',exact:true}).click();await invited.waitForURL(doctorBase+'/login/');
  assert.equal(await status(invited,doctorBase+invitation.route),404);await login(invited,{email,password});await invited.waitForURL(doctorBase+'/');assert.deepEqual(await (await invited.request.get(doctorBase+'/api/patients/')).json(),allAccounts.doctor);
  python("from core.models import User,Wallet,LedgerEntry,Membership\nfrom decimal import Decimal\nu=User.objects.get(email=payload['email']);w=Wallet.objects.get(user=u,kind='promo')\nassert u.verified_at and w.balance==Decimal('10') and w.reserved==0\nassert LedgerEntry.objects.filter(wallet=w,kind='welcome').count()==1\nassert Membership.objects.filter(user=u,active=True).count()==1",{email});await invitedContext.close();
 });
 if(live)await check('Live voice transcript can be corrected without retaining stale answers',async()=>{
  const voiceId=await encounter(page,docName+' · mapping 2','History: Synthetic voice review pending.');
  const audio=process.env.QUILLMD_SYNTHETIC_AUDIO;assert(audio,'Provide a previously verified synthetic audio fixture.');
  const form=page.locator('[data-voice-form]');await reserve(form);await form.locator('[name=audio]').setInputFiles(audio);await form.locator('[name=consent]').check();await page.getByRole('button',{name:'Transcribe recording',exact:true}).click();
  for(let i=0;i<90;i++){await page.waitForTimeout(1000);await page.reload();if((await page.locator('.source-notes').innerText()).includes('wrist'))break;assert(!(await page.locator('.source-panel [data-request-status]').evaluateAll(n=>n.map(e=>e.dataset.requestStatus))).some(s=>['held','not_completed','completed_not_applied','unknown'].includes(s)));}
  assert((await page.locator('.source-notes').innerText()).toLowerCase().includes('no fracture'));await page.getByText('Edit source notes',{exact:true}).click();const corrected='History: Synthetic voice transcription corrected by clinician.\nFindings: No fracture documented.';await page.locator('#source-notes-edit').fill(corrected);await page.getByRole('button',{name:'Save source notes',exact:true}).click();await page.waitForLoadState();assert.equal(await page.locator('.source-notes').innerText(),corrected);assert.equal(await page.locator('textarea[name^=answer_]').count(),0);report.voiceEncounter=voiceId;
 });
 await check('Administrator MFA is required, replay refused, and separate logout enforced',async()=>{
  const ctx=await browser.newContext();const admin=await ctx.newPage();await login(admin,credentials.admin,adminBase);assert(new URL(admin.url()).pathname==='/login/');
  await admin.waitForTimeout(31000-Date.now()%30000);const otp=token(credentials.admin.totp_key_hex);await login(admin,credentials.admin,adminBase,otp);await admin.waitForURL(adminBase+'/console/');
  const cookies=await ctx.cookies();assert(cookies.some(c=>c.name==='quillmd_admin_session'&&c.httpOnly&&c.sameSite==='Strict'));assert(!cookies.some(c=>c.name==='quillmd_doctor_session'));
  const replayContext=await browser.newContext();const replay=await replayContext.newPage();await login(replay,credentials.admin,adminBase,otp);assert(new URL(replay.url()).pathname==='/login/');assert.equal(await status(replay,adminBase+'/console/'),302);await replayContext.close();
  await admin.getByRole('button',{name:'Sign out',exact:true}).click();await admin.waitForURL(adminBase+'/login/');assert.equal(await status(admin,adminBase+'/console/'),302);await ctx.close();
 });
 if(!live||process.env.QUILLMD_BETA_RECOVERY==='1'){
  await check('Password recovery invalidates old sessions and one-time reset links',async()=>{
   const oldContext=await browser.newContext(),oldPage=await oldContext.newPage();await login(oldPage,invitedAccount);await oldPage.waitForURL(doctorBase+'/');
   const recoveryOutbox=mailSnapshot();
   const recoveryContext=await browser.newContext(),recovery=await recoveryContext.newPage();await recovery.goto(doctorBase+'/recovery/');await recovery.locator('[name=email]').fill(invitedAccount.email);await recovery.getByRole('button',{name:'Prepare recovery link',exact:true}).click();assert((await recovery.locator('[role=status]').innerText()).includes('If this address is eligible'));
   const reset={route:mailRoute('recovery/confirm',invitedAccount.email,recoveryOutbox)};
   await recovery.goto(doctorBase+reset.route);assert(new URL(recovery.url()).pathname.endsWith('/set-password/'));
   const replacement=crypto.randomBytes(24).toString('base64url');await recovery.locator('[name=new_password1]').fill(replacement);await recovery.locator('[name=new_password2]').fill(replacement);await recovery.getByRole('button',{name:'Update password',exact:true}).click();await recovery.waitForURL(doctorBase+'/recovery/complete/');assert.equal(await status(recovery,doctorBase+'/'),302);
   await oldPage.goto(doctorBase+'/patients/');await oldPage.waitForURL(/\/login\//);await login(recovery,invitedAccount);assert.equal(new URL(recovery.url()).pathname,'/login/');invitedAccount.password=replacement;await login(recovery,invitedAccount);await recovery.waitForURL(doctorBase+'/');
   await recovery.goto(doctorBase+reset.route);assert.equal(await recovery.getByRole('heading',{name:'Recovery link unavailable',exact:true}).count(),1);await oldContext.close();await recoveryContext.close();
  });
  await check('Expired sessions restore an authorized page after reauthentication',async()=>{
   await page.goto(doctorBase+'/encounters/'+docId+'/');const session=(await context.cookies()).find(c=>c.name==='quillmd_doctor_session');python("from django.contrib.sessions.models import Session\nfrom django.utils import timezone\nfrom datetime import timedelta\nSession.objects.filter(session_key=payload['session']).update(expire_date=timezone.now()-timedelta(seconds=1))",{session:session.value});
   await page.reload();assert.equal(new URL(page.url()).searchParams.get('next'),'/encounters/'+docId+'/');await page.locator('[name=email]').fill(credentials.doctor.email);await page.locator('[name=password]').fill(credentials.doctor.password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL(doctorBase+'/encounters/'+docId+'/');
  });
 }
 await check('Exact provider settlement and original storage remain auditable',async()=>{
  report.usage=python("from core.models import Job,Usage,ProviderReceipt\nfrom core.management.commands.audit_billing import audit_report\nfrom decimal import Decimal\nids=payload['ids'];rows=[]\naudit={x['job_id']:x['checks'] for x in audit_report()['rows']}\nfor j in Job.objects.filter(encounter_id__in=ids):\n u=Usage.objects.get(job=j);r=ProviderReceipt.objects.get(job=j);c=audit[str(j.pk)]\n assert j.state=='succeeded' and c['exact_1_5_multiplier'] and c['over_limit_absorbed_exactly'] and u.simulated==r.simulated\n assert u.simulated != payload['live']\n rows.append({'job':str(j.pk),'provider':u.provider,'actual_cost':format(u.actual_cost,'f'),'cost_basis':'Provider-reported units priced at the configured rates; not reconciled to a provider invoice.','user_charge':format(u.charged_cost,'f'),'simulated':u.simulated})\nassert sum(Decimal(r['user_charge']) for r in rows)<=1\nprint(json.dumps(rows))",{ids:[docId,pdfId,...(report.voiceEncounter?[report.voiceEncounter]:[])],live});
 });
 report.complete=true;
}catch(error){
 report.errorClass=error.name;report.testLine=Number(error.stack?.match(/private-beta-browser\.mjs:(\d+):\d+/)?.[1])||null;
 report.checks.push({name:active,passed:false});console.error('FAIL '+active+'; sensitive details suppressed.');process.exitCode=1;
}finally{
 await browser?.close();if(scratch){assert.equal(path.dirname(scratch),runtime);assert(path.basename(scratch).startsWith('beta-browser-'));await fs.rm(scratch,{recursive:true,force:true});}
 report.finishedAt=new Date().toISOString();report.scratchRemoved=true;
 const destination=process.env.QUILLMD_BETA_REPORT||path.join(runtime,'private-beta-browser-'+(live?'live':'fixture')+'.json');await fs.writeFile(destination,JSON.stringify(report,null,2)+'\n',{mode:0o600});console.log(`${report.checks.filter(r=>r.passed).length} checks passed; complete=${report.complete}`);
}
