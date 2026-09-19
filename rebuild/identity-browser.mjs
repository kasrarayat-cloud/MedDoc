/** Actual private-service regression after OS isolation. Synthetic accounts only.
 * No generation, transcription or payment provider calls. Run from this release
 * after its guarded identity activation. Private artifacts never contain secrets.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const app=path.dirname(fileURLToPath(import.meta.url));
const runtime=path.join(app,'.runtime');
const doctor='http://127.0.0.1:9130',admin='http://127.0.0.1:9131';
const require=createRequire(import.meta.url);
const report={startedAt:new Date().toISOString(),checks:[],complete:false,providerCalls:0};
let browser,scratch,active='Initialization';
function python(code,payload={}){
 const header="import os,json,sys\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')\nimport django\ndjango.setup()\npayload=json.loads(sys.stdin.read())\n";
 const p=spawnSync(path.join(app,'.venv/bin/python'),['-c',header+code],{cwd:app,encoding:'utf8',input:JSON.stringify(payload),timeout:60000,maxBuffer:1024*1024});
 assert.equal(p.status,0,'Private helper failed; output suppressed.');
 return p.stdout?JSON.parse(p.stdout):null;
}
async function check(name,action){active=name;await action();report.checks.push({name,passed:true});console.log('PASS '+name);}
async function login(page,account,base=doctor,otp=''){
 await page.goto(base+'/login/');await page.locator('[name=email]').fill(account.email);await page.locator('[name=password]').fill(account.password);
 if(otp)await page.locator('[name=otp]').fill(otp);
 await page.getByRole('button',{name:base===admin?'Sign in to administration':'Sign in',exact:true}).click();
}
async function status(page,base,route){return(await page.request.get(base+route,{maxRedirects:0})).status();}
function otp(key){const n=Buffer.alloc(8);n.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));const h=crypto.createHmac('sha1',Buffer.from(key,'hex')).update(n).digest();return String((h.readUInt32BE(h.at(-1)&15)&0x7fffffff)%1000000).padStart(6,'0');}
// ⚠️ THE OUTBOX IS READ THROUGH ops/private_mail, NOT BY A LOCAL REGEX. The helper that used to live here
// selected at FILE level and took the first match in the file, and `assert len(matches)==1` counted FILES,
// not records. Django names outbox files with one second of entropy and the application opens them
// O_APPEND, so two sends in one second share a file — and a refutation pass ran this exact code against
// such a file and watched it return ANOTHER ACCOUNT'S invitation token, which this harness then navigates
// to. That consumes a stranger's invitation or resets a stranger's password. Record-level selection by
// exact addressee lives in one module now, so there is one reader to fix rather than four.
function mailSnapshot(){return python("from ops import private_mail\nfrom django.conf import settings\n"
 +"assert settings.QUILLMD_EMAIL_MODE=='file' and str(settings.EMAIL_FILE_PATH)==str(private_mail.OUTBOX)\n"
 +"print(json.dumps({'files':private_mail.snapshot()}))\n").files;}
function outbox(email,kind,before){const found=python("from ops import account_mail, private_mail\nnotes={}\n"
 +"route=account_mail.locate(payload['kind'],payload['email'],payload['before'],notes=notes)\n"
 +"print(json.dumps({'route':route,'described':private_mail.describe(route),'notes':notes}))\n",
 {email,kind:kind==='recovery'?'recovery/confirm':kind,before});
 assert.equal(found.notes.token_bound,true,'the located token is not bound to this run\'s own record');
 return found.route;}
try{
 assert.equal(app,'/opt/meddoc-pro/rebuild');
 const credentials=JSON.parse(await fs.readFile(path.join(runtime,'private-access.json'),'utf8'));
 for(const name of ['doctor','admin','xray_employee','ultrasound','other_org'])assert(credentials[name].email.endsWith('@synthetic.quillmd.invalid'));
 report.baseline=python("from django.conf import settings\nfrom core.models import Job,Usage,Encounter\nfrom pathlib import Path\nimport subprocess\nassert settings.SYNTHETIC_ONLY and settings.STATE_DIR==Path('/var/lib/quillmd')\ne=Encounter.objects.filter(status='finalized',department__membership__user__email=payload['email']).order_by('-created_at').first()\nassert e and e.export_path\nprint(json.dumps({'release':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'jobs':Job.objects.count(),'usage':Usage.objects.count(),'encounter':str(e.pk),'export_sha256':e.export_sha256}))",{email:credentials.doctor.email});
 scratch=await fs.mkdtemp(path.join(runtime,'identity-browser-'));await fs.chmod(scratch,0o700);
 python("from docx import Document\nfrom pathlib import Path\nd=Document();d.add_heading('Synthetic OS isolation form',0);d.add_paragraph('History: {{History}}');d.add_paragraph('Findings: {{Findings}}');d.save(Path(payload['scratch'])/'form.docx')",{scratch});
 const source=await fs.readFile(path.join(scratch,'form.docx'));const sourceHash=crypto.createHash('sha256').update(source).digest('hex');
 const {chromium}=require('@playwright/test');browser=await chromium.launch({headless:true});const ctx=await browser.newContext();const page=await ctx.newPage();page.setDefaultTimeout(20000);
 await check('Exact synthetic release, sign-in pages and stylesheet load under dedicated identity',async()=>{
  for(const base of [doctor,admin]){
   const health=await(await page.request.get(base+'/health/')).json();assert.equal(health.release,report.baseline.release);assert.equal(health.data_mode,'synthetic-only');
   assert.equal((await page.goto(base+'/login/')).status(),200);
   const css=await page.locator('link[rel=stylesheet]').first().getAttribute('href');assert(css.startsWith('/static/'));
   const asset=await page.request.get(base+css);assert.equal(asset.status(),200);assert(asset.headers()['content-type'].includes('text/css'));assert((await asset.body()).length>100);
  }
 });
 await check('Doctor authentication and existing finalized export bytes are intact',async()=>{
  await login(page,credentials.doctor);await page.waitForURL(doctor+'/');
  const response=await page.request.get(doctor+'/encounters/'+report.baseline.encounter+'/export/');assert.equal(response.status(),200);assert.equal(crypto.createHash('sha256').update(await response.body()).digest('hex'),report.baseline.export_sha256);
 });
 let template;
 await check('New synthetic Word upload runs isolated parser and preserves original bytes',async()=>{
  await page.goto(doctor+'/templates/upload/');await page.locator('[name=name]').fill('Synthetic identity verification '+Date.now());await page.locator('[name=department]').selectOption({label:'X-ray'});await page.locator('[name=file]').setInputFiles(path.join(scratch,'form.docx'));await page.locator('[name=synthetic_only]').check();await page.getByRole('button',{name:'Upload and inspect form',exact:true}).click();await page.waitForURL(/\/templates\/[0-9a-f-]+\/$/);template=new URL(page.url()).pathname.split('/')[2];
  assert.equal(await page.locator('tbody tr').count(),2);const original=await page.request.get(doctor+'/templates/'+template+'/original/');assert.equal(original.status(),200);assert.equal(crypto.createHash('sha256').update(await original.body()).digest('hex'),sourceHash);report.template=template;
 });
 await check('Department sharing and cross-department/organization file denials remain enforced',async()=>{
  const patients=await(await page.request.get(doctor+'/api/patients/')).json();
  for(const name of ['xray_employee','ultrasound','other_org']){
   const c=await browser.newContext(),p=await c.newPage();await login(p,credentials[name]);await p.waitForURL(doctor+'/');
   const list=await(await p.request.get(doctor+'/api/patients/')).json();
   if(name==='xray_employee')assert.deepEqual(list,patients);else assert.notDeepEqual(list,patients);
   for(const route of ['/templates/'+template+'/original/','/encounters/'+report.baseline.encounter+'/export/'])assert.equal(await status(p,doctor,route),name==='xray_employee'?200:404);
   assert.equal(await status(p,doctor,'/console/'),404);await c.close();
  }
 });
 let invited;
 await check('Invitation uses app-owned private outbox, one-use acceptance and one welcome credit',async()=>{
  invited={email:'identity-'+Date.now()+'@synthetic.quillmd.invalid',password:crypto.randomBytes(24).toString('base64url')};
  const before=mailSnapshot();
  await page.goto(doctor+'/team/');const form=page.locator('form').filter({has:page.getByRole('button',{name:'Create invitation',exact:true})});await form.locator('[name=email]').fill(invited.email);await form.locator('[name=department]').selectOption({label:'X-ray'});await form.locator('[name=role]').selectOption('employee');await form.getByRole('button',{name:'Create invitation',exact:true}).click();await page.waitForLoadState();
  const route=outbox(invited.email,'invite',before);const c=await browser.newContext(),p=await c.newPage();await p.goto(doctor+route);await p.locator('[name=email]').fill(invited.email);await p.locator('[name=first_name]').fill('Synthetic');await p.locator('[name=last_name]').fill('Identity Test');await p.locator('[name=password1]').fill(invited.password);await p.locator('[name=password2]').fill(invited.password);await p.locator('[name=synthetic_only]').check();await p.getByRole('button',{name:'Accept invitation',exact:true}).click();await p.waitForURL(doctor+'/login/');assert.equal(await status(p,doctor,route),404);
  python("from core.models import User,Wallet,LedgerEntry\nfrom decimal import Decimal\nu=User.objects.get(email=payload['email']);w=Wallet.objects.get(user=u,kind='promo');assert u.verified_at and w.balance==Decimal('10') and w.reserved==0;assert LedgerEntry.objects.filter(wallet=w,kind='welcome').count()==1",{email:invited.email});await c.close();
 });
 await check('Private recovery delivery, old-session revocation and reset-token replay denial',async()=>{
  const old=await browser.newContext(),op=await old.newPage();await login(op,invited);await op.waitForURL(doctor+'/');
  const recoveryBefore=mailSnapshot();
  const c=await browser.newContext(),p=await c.newPage();await p.goto(doctor+'/recovery/');await p.locator('[name=email]').fill(invited.email);await p.getByRole('button',{name:'Prepare recovery link',exact:true}).click();assert((await p.locator('[role=status]').innerText()).includes('If this address is eligible'));
  const route=outbox(invited.email,'recovery',recoveryBefore);await p.goto(doctor+route);assert(new URL(p.url()).pathname.endsWith('/set-password/'));const replacement=crypto.randomBytes(24).toString('base64url');await p.locator('[name=new_password1]').fill(replacement);await p.locator('[name=new_password2]').fill(replacement);await p.getByRole('button',{name:'Update password',exact:true}).click();await p.waitForURL(doctor+'/recovery/complete/');await op.goto(doctor+'/patients/');await op.waitForURL(/\/login\//);await login(p,invited);assert.equal(new URL(p.url()).pathname,'/login/');invited.password=replacement;await login(p,invited);await p.waitForURL(doctor+'/');await p.goto(doctor+route);assert.equal(await p.getByRole('heading',{name:'Recovery link unavailable',exact:true}).count(),1);await old.close();await c.close();
 });
 await check('Administrator requires MFA and rejects a reused code in another session',async()=>{
  const c=await browser.newContext(),p=await c.newPage();await login(p,credentials.admin,admin);assert.equal(new URL(p.url()).pathname,'/login/');await p.waitForTimeout(31000-Date.now()%30000);const code=otp(credentials.admin.totp_key_hex);await login(p,credentials.admin,admin,code);await p.waitForURL(admin+'/console/');const cookies=await c.cookies();assert(cookies.some(c=>c.name==='quillmd_admin_session'&&c.httpOnly&&c.sameSite==='Strict'));assert(!cookies.some(c=>c.name==='quillmd_doctor_session'));
  const r=await browser.newContext(),rp=await r.newPage();await login(rp,credentials.admin,admin,code);assert.equal(new URL(rp.url()).pathname,'/login/');assert.equal(await status(rp,admin,'/console/'),302);await r.close();await c.close();
 });
 await check('Verification made no provider jobs or usage charges',async()=>python("from core.models import Job,Usage\nassert Job.objects.count()==payload['jobs'] and Usage.objects.count()==payload['usage']",report.baseline));
 report.complete=true;
}catch(error){report.failureKind=error.name;report.failureLine=Number(error.stack?.match(/identity-browser\.mjs:(\d+):\d+/)?.[1])||null;report.checks.push({name:active,passed:false});console.error('FAIL '+active+'; sensitive details suppressed.');process.exitCode=1;
}finally{await browser?.close();if(scratch){assert.equal(path.dirname(scratch),runtime);assert(path.basename(scratch).startsWith('identity-browser-'));await fs.rm(scratch,{recursive:true});}report.finishedAt=new Date().toISOString();await fs.writeFile(path.join(runtime,'identity-browser-verification.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});console.log(`${report.checks.filter(c=>c.passed).length} checks passed; complete=${report.complete}`);}
