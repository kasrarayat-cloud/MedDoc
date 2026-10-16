/* Bounded delivery check of the already-reviewed synthetic encounter.
 * No new note, coding, approval, or provider task; ordinary clinician login.
 */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require('playwright');
const [runtime,out]=process.argv.slice(2);
if(!runtime||!out||![runtime,out].every(path.isAbsolute))throw Error('Absolute private input/output required.');
fs.mkdirSync(out,{mode:0o700});
const access=JSON.parse(fs.readFileSync(path.join(runtime,'clinician-access.json')));
const install=JSON.parse(fs.readFileSync(path.join(runtime,'installation.json')));
const base='https://app.quillmd.com/synthetic/corti';
const coding=base+'/encounters/'+install.encounter_id+'/?tab=coding';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const report={scope:'Normal HTTPS; authenticated nonstaff clinician; already finalized retained-response synthetic replay. Delivery verification only.',provider_calls:0,downloads:[],blocked_requests:[],errors:[]};
let browser,page;
async function download(locator,name){
 const pending=page.waitForEvent('download');await locator.click();const d=await pending;
 const target=path.join(out,name);await d.saveAs(target);fs.chmodSync(target,0o600);
 const result={file:name,suggested_name:d.suggestedFilename(),sha256:sha(fs.readFileSync(target))};report.downloads.push(result);return result;
}
(async()=>{
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 await context.route('**/*',r=>{
  const req=r.request(),u=new URL(req.url());
  if(u.origin==='https://app.quillmd.com'&&u.pathname.startsWith('/synthetic/corti/')
    &&(req.method()==='GET'||u.pathname==='/synthetic/corti/login/'))return r.continue();
  report.blocked_requests.push({method:req.method(),path:u.pathname});return r.abort();
 });
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 await page.goto(coding);assert.ok(page.url().startsWith(base+'/login/'));
 report.anonymous_document_access='sign-in required';
 await page.locator('[name=email]').fill(access.email);await page.locator('[name=password]').fill(access.password);
 await Promise.all([page.waitForURL(u=>!u.pathname.endsWith('/login/')),page.getByRole('button',{name:'Sign in',exact:true}).click()]);
 await page.goto(coding);await page.getByRole('link',{name:/Export with codes/}).waitFor();
 assert.equal(await page.locator('[data-corti-evidence]').count(),7);
 assert.equal(await page.locator('[data-code-held]').count(),1);
 const cpt=page.locator('[data-coding-item]').filter({has:page.locator('.mono',{hasText:'99213'})});
 assert.match(await cpt.locator('.coding-code-heading').innerText(),/Description unverified/);
 assert.equal(await cpt.locator('select').isDisabled(),true);
 assert.match(await page.locator('[data-corti-replay]').innerText(),/Synthetic replay/);
 const cookies=await context.cookies();report.cookies=cookies.map(({name,path,secure,httpOnly,sameSite})=>({name,path,secure,httpOnly,sameSite}));
 assert.ok(cookies.every(c=>['quillmd_corti_session','quillmd_corti_csrf'].includes(c.name)&&c.path==='/synthetic/corti/'&&c.secure));
 const links=await page.locator('a[href]').evaluateAll(items=>items.map(a=>a.href).filter(h=>h.startsWith(location.origin)));
 assert.ok(links.every(h=>new URL(h).pathname.startsWith('/synthetic/corti/')));
 const original=await download(page.getByRole('link',{name:/Export original format/}),'synthetic-original.docx');
 const approved=await download(page.getByRole('link',{name:/Export with codes/}),'synthetic-with-codes.docx');
 const draft=await download(page.getByRole('link',{name:/Download synthetic draft/}),'synthetic-draft-not-approved.docx');
 assert.equal(original.sha256,'63c0058fe4b9976d1d31ca31d081a2efb83d4ce87696dab70eb3277ea81344fa');
 assert.equal(approved.sha256,'5d05e781e2b9a514722c0a26d707764cefeb68ecf26cbfd5bce0c9170858eac1');
 await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
 report.desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
 assert.ok(report.desktop.scrollWidth<=report.desktop.width);
 await page.setViewportSize({width:390,height:844});await page.reload();
 assert.equal(await page.locator('[data-corti-evidence]').count(),7);
 const mobile=await download(page.getByRole('link',{name:/Download synthetic draft/}),'synthetic-draft-mobile.docx');
 assert.equal(mobile.sha256,draft.sha256);
 const approvedMobile=await download(page.getByRole('link',{name:/Export with codes/}),'synthetic-with-codes-mobile.docx');
 assert.equal(approvedMobile.sha256,approved.sha256);
 report.mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
 assert.ok(report.mobile.scrollWidth<=report.mobile.width);
 await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
 assert.deepEqual(report.blocked_requests,[]);assert.deepEqual(report.errors,[]);
 report.verdict='PASS';report.clinician_url=coding;
})().catch(e=>{report.verdict='FAIL';report.failure=String(e);process.exitCode=1;}).finally(async()=>{
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2),{mode:0o600});await browser?.close();
 console.log(JSON.stringify({verdict:report.verdict,failure:report.failure,output:out}));
});
