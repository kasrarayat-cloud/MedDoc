/** Headed Linux Chrome/Edge tests against the dedicated synthetic HTTPS fixture.
 * No live account, provider, inbox or Windows acceptance is represented.
 * The runtime config contains secrets and MUST be owner-only. Never print it.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
const require=createRequire(path.join(process.env.PLAYWRIGHT_MODULE_DIR||process.cwd(),'package.json'));
const {chromium}=require('@playwright/test');
const origin='https://app.quillmd.com:19443';
const run=process.env.QUILLMD_PREVIEW_BROWSER_STATE;
const attempt=process.env.QUILLMD_BROWSER_ATTEMPT||'1';if(!/^[1-9][0-9]*$/.test(attempt))throw Error('Invalid attempt');
if(!run || !run.includes('/.runtime/') || (fs.statSync(run).mode&511)!==448) throw Error('Protected runtime required');
for(const file of ['control.json','environment.json']){const x=fs.lstatSync(path.join(run,file));if(!x.isFile()||(x.mode&511)!==384||x.uid!==process.getuid())throw Error('Protected control file required');}
const secret=JSON.parse(fs.readFileSync(path.join(run,'control.json')));
const env={...process.env,...JSON.parse(fs.readFileSync(path.join(run,'environment.json')))};
if(secret.origin!==origin || !env.QUILLMD_DB_NAME.startsWith('quillmd_preview_browser_') || env.QUILLMD_DB_PORT!=='55439') throw Error('Isolated fixture required');
const python='/opt/meddoc-pro/rebuild/.venv/bin/python';
const sourceFiles=['core/preview_access.py','core/preview_logging.py','core/middleware.py','core/views.py','core/email_backend.py','core/email_delivery.py','core/recovery.py','quillmd/settings.py','quillmd/urls.py','templates/preview_error.html','templates/login.html','templates/encounter_input.html','ops/preview_browser_settings.py','ops/preview_browser_fixture.py','ops/preview_browser_tls.py','preview-form-browser.mjs'];
const sourceHashes=()=>Object.fromEntries(sourceFiles.map(file=>[file,crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
const beforeSources=sourceHashes();
const report={candidate_repository_revision:spawnSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).stdout.trim(),source_sha256:beforeSources,private_browser_contexts:true,started:new Date().toISOString(),origin,evidence:'operator-automated headed Linux browsers under Xvfb; isolated PostgreSQL; file outbox only',tls_validation:true,ignore_https_errors:false,owner_windows_acceptance:false,provider_delivery:false,inbox_receipt:false,real_elapsed_expiry:false,browsers:[]};
const checks=[]; let active='initialization'; let browser;
function requireThat(value,name){active=name;if(!value)throw Error('AssertionFailed');checks.push({check:name,passed:true});}
function fixture(action,payload={}) {const r=spawnSync(python,['-m','ops.preview_browser_fixture','--action',action],{cwd:process.cwd(),env,input:JSON.stringify(payload),encoding:'utf8'});if(r.status!==0)throw Error('FixtureFailed');return JSON.parse(r.stdout);}
function privateJSON(file,value) {const fd=fs.openSync(file,'wx',384);fs.writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fs.closeSync(fd);}
async function shot(page,name){const file=path.join(run,name+'-attempt'+attempt+'.png');fs.closeSync(fs.openSync(file,'wx',384));await page.screenshot({path:file,fullPage:true});return {file:path.basename(file),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')};}
async function click(page,label){await Promise.all([page.waitForNavigation(),page.getByRole('button',{name:label,exact:true}).click()]);}
async function login(page,account,password=account.password){await page.goto(origin+'/login/');await page.locator('[name=email]').fill(account.email);await page.locator('[name=password]').fill(password);await click(page,'Sign in');requireThat(new URL(page.url()).pathname==='/', 'normal individual account login succeeds');}
const apiPages=new WeakMap();
async function http(context,url,{form,method='GET'}={}) {
 let p=apiPages.get(context);if(!p){p=await context.newPage();await p.goto(origin+'/static/app.css');apiPages.set(context,p);}
 const result=await p.evaluate(async ({url,form,method})=>{const r=await fetch(url,{method,redirect:'manual',credentials:'same-origin',headers:form?{'Content-Type':'application/x-www-form-urlencoded'}:{},body:form?new URLSearchParams(form):undefined});return {status:r.status,headers:Object.fromEntries(r.headers),body:Array.from(new Uint8Array(await r.arrayBuffer()))};},{url,form,method});
 return {status:()=>result.status,headers:()=>result.headers,body:async()=>Buffer.from(result.body),json:async()=>JSON.parse(Buffer.from(result.body).toString())};
}
async function previewCookie(context){return (await context.cookies()).find(x=>x.name==='__Host-quillmd_preview');}
async function createContext(browser){const context=await browser.newContext();await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());return context;}
try {
 for(const [name,executable] of [['chrome','/opt/google/chrome/chrome'],['edge',process.env.QUILLMD_EDGE_EXECUTABLE]]) {
  active=name+' launch';checks.length=0;fixture('reset-limits');
  const version=spawnSync(executable,['--version'],{encoding:'utf8'}).stdout.trim();
  browser=await chromium.launch({executablePath:executable,headless:false,args:['--host-resolver-rules=MAP app.quillmd.com 127.0.0.1, EXCLUDE localhost','--no-proxy-server']});
  const contexts=[]; const context=await createContext(browser);contexts.push(context);const page=await context.newPage();const errors=[];page.on('pageerror',()=>errors.push('pageerror'));
  active='ordinary individual sign-in';await page.goto(origin+'/');
  requireThat(new URL(page.url()).pathname==='/login/' && await page.locator('[name=email]').isVisible(),'fresh browser directly reaches account login');
  requireThat(await page.locator('[name=username]').count()===0 && !(await page.locator('body').innerText()).includes('Private preview'),'separate shared preview form is absent');
  requireThat(!await previewCookie(context),'account login requires no preview cookie');
  const screenshots=[await shot(page,name+'-account-login')];
  const csrf=await http(context,origin+'/login/',{method:'POST',form:{email:secret.owner.email,password:'incorrect-synthetic'}});
  requireThat(csrf.status()===403,'account login without CSRF is rejected');
  await page.locator('[name=email]').fill(secret.owner.email);await page.locator('[name=password]').fill('incorrect-synthetic-password');await click(page,'Sign in');
  requireThat(new URL(page.url()).pathname==='/login/' && (await page.locator('body').innerText()).includes('Sign-in failed'),'invalid account credentials cannot authenticate');
  await page.locator('[name=password]').fill('');screenshots.push(await shot(page,name+'-invalid-account'));
  for(const route of ['/preview/sign-in/?flow=obsolete&next=//outside.invalid','/preview/sign-out/']) {
   await page.goto(origin+route);requireThat(new URL(page.url()).pathname==='/login/' && new URL(page.url()).search==='','retired preview link terminates at token-free account login');
  }
  requireThat((await http(context,origin+'/register/')).status()===404,'standalone account creation is unavailable');
  const blocked=await createContext(browser);contexts.push(blocked);
  await blocked.addCookies([{name:'__Host-quillmd_preview',value:'obsolete-preview-grant',url:origin,secure:true,httpOnly:true,sameSite:'Lax'}]);
  const protectedRoutes=['/patients/','/api/patients/',`/templates/${secret.fixtures.own.template_id}/original/`,`/encounters/${secret.fixtures.own.encounter_id}/export/`];
  const deniedPage=await blocked.newPage();
  for(const route of protectedRoutes) {
   await deniedPage.goto(origin+route);requireThat(new URL(deniedPage.url()).pathname==='/login/','old preview cookie cannot authorize protected pages API or files');
  }
  requireThat(!await previewCookie(blocked),'obsolete browser preview cookie is retired without account authority');
  await login(page,secret.owner);await page.reload();requireThat(new URL(page.url()).pathname==='/' && !await previewCookie(context),'account session independently authorizes refreshed workspace');
  const ownerSession=(await context.cookies()).find(x=>x.name==='quillmd_doctor_session');
  await context.addCookies([{name:'__Host-quillmd_preview',value:ownerSession.value,url:origin,secure:true,httpOnly:true,sameSite:'Lax'}]);
  await page.reload();requireThat(new URL(page.url()).pathname==='/' && !await previewCookie(context),'copied account session in old preview cookie neither invalidates nor replaces account session');
  await page.goto(origin+'/team/');await page.locator('aside [name=department]').selectOption(secret.fixtures.own.department_id);await page.locator('aside [name=email]').fill(secret.invitees[name].email);await page.locator('aside [name=role]').selectOption('employee');await click(page,'Create invitation');
  const invitationMail=fixture('mail',{browser:name,purpose:'invitation'});const invite=invitationMail.url;
  requireThat(invitationMail.canonical_account_url.startsWith('https://app.quillmd.com/invite/'),'invitation email uses ordinary account origin without special port');
  const employeeContext=await createContext(browser);contexts.push(employeeContext);const employee=await employeeContext.newPage();await employee.goto(invite);
  requireThat(employee.url()===invite && await employee.locator('[name=username]').count()===0,'valid invitation opens directly without shared gate');
  await employee.locator('[name=first_name]').fill('Synthetic');await employee.locator('[name=last_name]').fill(name+' Employee');await employee.locator('[name=password1]').fill(secret.invitees[name].password);await employee.locator('[name=password2]').fill(secret.invitees[name].password);await employee.locator('[name=synthetic_only]').check();await click(employee,'Accept invitation');
  await login(employee,secret.invitees[name]);const before=fixture('state',{browser:name});requireThat(before.exists&&before.verified&&!before.is_staff&&before.memberships.length===1&&before.memberships[0].department_id===secret.fixtures.own.department_id&&before.memberships[0].role==='employee','invitation creates only verified intended department Employee');requireThat(before.welcome_grants===1&&Number(before.wallets.find(x=>x.kind==='promo').balance)===10,'exactly one personal 10 dollar welcome grant');
  requireThat(!await previewCookie(employeeContext),'invited account needs only its individual account session');
  const patientResponse=await http(employeeContext,origin+'/api/patients/');const patients=(await patientResponse.json()).patients;requireThat(patients.length===1&&patients[0].id===secret.fixtures.own.patient_id,'patient API exposes intended department only');
  for(const scope of ['ultrasound','other']) for(const route of [`/api/encounters/${secret.fixtures[scope].encounter_id}/`,`/templates/${secret.fixtures[scope].template_id}/original/`,`/encounters/${secret.fixtures[scope].encounter_id}/export/`]) {const response=await http(employeeContext,origin+route);requireThat(response.status()===404,'foreign department encounter original and export remain inaccessible');}
  const own=await http(employeeContext,origin+`/encounters/${secret.fixtures.own.encounter_id}/export/`);requireThat(own.status()===200&&crypto.createHash('sha256').update(await own.body()).digest('hex')===secret.fixtures.own.file_sha256,'authorized synthetic export bytes match original fixture hash');
  screenshots.push(await shot(employee,name+'-authenticated-workspace'));
  await click(employee,'Sign out');requireThat(new URL(employee.url()).pathname==='/login/','logout returns directly to ordinary account login');await employee.goto(origin+'/patients/');requireThat(new URL(employee.url()).pathname==='/login/','logout revokes protected account access');
  await login(employee,secret.invitees[name]);await employee.goto(origin+'/recovery/');await employee.locator('[name=email]').fill(secret.invitees[name].email);await click(employee,'Prepare recovery link');
  const recoveryMail=fixture('mail',{browser:name,purpose:'recovery'});requireThat(recoveryMail.canonical_account_url.startsWith('https://app.quillmd.com/recovery/confirm/'),'recovery email uses ordinary account origin');
  const recoveryContext=await createContext(browser);contexts.push(recoveryContext);const recoveryPage=await recoveryContext.newPage();await recoveryPage.goto(recoveryMail.url);
  requireThat(new URL(recoveryPage.url()).pathname.endsWith('/set-password/') && await recoveryPage.getByRole('heading',{name:'Set a new password',exact:true}).isVisible(),'synthetic recovery capability enters directly without gate');
  await recoveryPage.locator('[name=new_password1]').fill(secret.invitees[name].replacement);await recoveryPage.locator('[name=new_password2]').fill(secret.invitees[name].replacement);await click(recoveryPage,'Update password');
  requireThat(await recoveryPage.getByRole('heading',{name:'Password updated',exact:true}).isVisible(),'authorized isolated invitee recovery still completes');
  const after=fixture('state',{browser:name});requireThat(after.password_sha256!==before.password_sha256&&after.owner_password_sha256===before.owner_password_sha256&&after.welcome_grants===1&&after.recovery_events===before.recovery_events+1,'isolated recovery affects target invitee only and preserves owner password');
  await employee.goto(origin+'/patients/');requireThat(new URL(employee.url()).pathname==='/login/','recovery invalidates old invitee session');await login(recoveryPage,secret.invitees[name],secret.invitees[name].replacement);
  requireThat((await http(recoveryContext,invite)).status()===404,'used invitation cannot replay');
  await recoveryPage.goto(recoveryMail.url);requireThat(await recoveryPage.getByRole('heading',{name:'Recovery link unavailable',exact:true}).isVisible(),'used recovery capability cannot replay');
  requireThat(errors.length===0,'no captured browser JavaScript page errors');requireThat(after.provider_jobs===0&&after.provider_usage===0&&after.provider_receipts===0,'no AI jobs usage or provider receipts created');
  report.browsers.push({name,version,headed:true,engine_platform:'Linux Xvfb',checks:[...checks],screenshots,passed:true});for(const c of contexts)await c.close();await browser.close();browser=null;
 }
 requireThat(JSON.stringify(beforeSources)===JSON.stringify(sourceHashes()),'application and harness sources unchanged during browser execution');report.sources_stable=true;report.passed=true;
} catch(e) {report.passed=false;report.failure={check:active,error_class:e?.constructor?.name||'Error',source_line:(e?.stack||'').match(/preview-form-browser\.mjs:\d+:\d+/)?.[0]||null};report.incomplete_checks=[...checks];if(browser)await browser.close();process.exitCode=1;}
report.finished=new Date().toISOString();privateJSON(path.join(run,'browser-report-'+attempt+'.json'),report);console.log(JSON.stringify({passed:report.passed,browsers:report.browsers.map(x=>({name:x.name,version:x.version,checks:x.checks.length})),failure:report.failure||null,report:path.join(run,'browser-report-'+attempt+'.json')}));
