/* One bounded synthetic replay acceptance walk. No external requests or AI calls.
 * Uses a fresh installed candidate; never seeds, resets, or changes live records.
 * NODE_PATH=/opt/meddoc-pro/node_modules node <this> <private-runtime> <fresh-output>
 */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {execFileSync}=require('child_process');
const {chromium}=require('playwright');
const [runtime,out,mode]=process.argv.slice(2);
if(!runtime||!out||![runtime,out].every(path.isAbsolute))throw Error('Absolute private runtime and fresh output directory required.');
if(mode && mode!=='--approved-only')throw Error('Unknown mode.');
fs.mkdirSync(out,{mode:0o700});
const receipt=JSON.parse(fs.readFileSync(path.join(runtime,'installation.json')));
const access=JSON.parse(fs.readFileSync(path.join(runtime,'clinician-access.json')));
const origin=new URL(receipt.clinician_url).origin;
assert.equal(origin,'http://127.0.0.1:9146');assert.equal(receipt.mode,'synthetic_retained_response_replay');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const report={scope:'Authenticated ordinary clinician; retained-response replay; manual synthetic saved-answer fixture. No new AI generation or live provider validation.',provider_calls:0,steps:[],external_requests:[],errors:[]};
let browser,page;
async function download(locator,name){
  const promise=page.waitForEvent('download');await locator.click();const item=await promise;
  const target=path.join(out,name);await item.saveAs(target);fs.chmodSync(target,0o600);
  return {name,sha256:sha(fs.readFileSync(target)),suggested_name:item.suggestedFilename()};
}
async function geometry(){return page.evaluate(()=>({viewport:innerWidth,body_width:document.documentElement.scrollWidth,
  evidence:document.querySelectorAll('[data-corti-evidence]').length,
  items:[...document.querySelectorAll('[data-coding-item]')].map(el=>({code:el.querySelector('.mono').textContent,
    held:!!el.querySelector('[data-code-held]'),text:el.innerText}))}));}
(async()=>{
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route('**/*',route=>{if(route.request().url().startsWith(origin+'/'))return route.continue();report.external_requests.push(route.request().url());return route.abort();});
  page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(origin+'/login/');await page.locator('[name=email]').fill(access.email);await page.locator('[name=password]').fill(access.password);
  await Promise.all([page.waitForURL(url=>!url.pathname.includes('/login/')),page.getByRole('button',{name:'Sign in',exact:true}).click()]);
  if(mode!=='--approved-only'){
  await page.goto(receipt.clinician_url);
  assert.equal(await page.locator('input[name^=reviewed_]').count(),1);
  await page.locator('input[name^=reviewed_]').check();
  await Promise.all([page.waitForNavigation(),page.getByRole('button',{name:'Save answers and review decisions'}).click()]);
  await page.locator('#final-review').check();
  await Promise.all([page.waitForNavigation(),page.getByRole('button',{name:/Finalize document/}).click()]);
  assert.equal(await page.getByRole('link',{name:/Export original format/}).count(),1);
  report.steps.push('Saved explicit clinical review and finalized through ordinary UI.');
  report.original=await download(page.getByRole('link',{name:/Export original format/}),'synthetic-original.docx');
  await page.goto(receipt.coding_url);
  if(await page.locator('[data-coding-form=request]').count()){
    await page.locator('[data-coding-form=request] button').click();
    await page.waitForFunction(()=>document.querySelector('[data-coding-panel]')?.dataset.pending==='true');
  }
  execFileSync('python3',[path.join(runtime,'run.py'),'manage.py','worker','--once'],{timeout:30000,stdio:'pipe'});
  await page.waitForFunction(()=>document.querySelectorAll('[data-coding-item]').length===3,{},{timeout:15000});
  assert.equal(await page.locator('[data-corti-evidence]').count(),7);
  assert.match(await page.locator('[data-corti-replay]').innerText(),/original response-quality failure/);
  const row=code=>page.locator('[data-coding-item]').filter({has:page.locator('.mono',{hasText:new RegExp('^'+code.replace('.','\\.')+'$')})});
  assert.equal(await row('99213').locator('select').isDisabled(),true);
  assert.match(await row('99213').innerText(),/Terminology unresolved/);
  await row('99213').locator('summary').first().click();
  assert.match(await row('99213').innerText(),/15 MINUTES/);
  assert.equal(await row('R12').locator('select').isDisabled(),false);
  assert.equal(await row('K59.00').locator('select').isDisabled(),false);
  report.desktop_review=await geometry();
  assert.ok(report.desktop_review.body_width<=report.desktop_review.viewport);
  await page.screenshot({path:path.join(out,'desktop-review.png'),fullPage:true});
  const stale=await page.locator('[data-coding-form=approval]').evaluate(f=>({url:f.action,values:Object.fromEntries(new FormData(f))}));
  await row('R12').locator('select').selectOption('include');
  await row('K59.00').locator('select').selectOption('exclude');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),true);
  await page.waitForTimeout(8500); // one ordinary read-only polling interval
  assert.equal(await row('K59.00').locator('select').inputValue(),'exclude');
  assert.equal(await page.locator('[data-coding-dirty]').isVisible(),true);
  const save=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/selections/'));
  await page.getByRole('button',{name:'Save code selections',exact:true}).click();
  // URL structure is asserted from the completed form response below, not retried.
  await save;
  await page.waitForFunction(()=>document.querySelector('[data-coding-form=approval] button')?.disabled===false);
  const refusal=await context.request.post(stale.url,{form:stale.values,headers:{Accept:'application/json'}});
  assert.equal(refusal.status(),409);report.stale_approval_status=refusal.status();
  await page.getByRole('button',{name:'Approve code selections',exact:true}).click();
  await page.locator('[data-export-with-codes]').waitFor();
  report.steps.push('Seven spans retained; CPT held; rejected K59.00 preserved through polling; stale approval refused; saved R12 approved.');
  }else{
    await page.goto(receipt.coding_url);await page.locator('[data-export-with-codes]').waitFor();
    assert.equal(await page.locator('[data-corti-evidence]').count(),7);
    assert.equal(await page.locator('[data-code-held]').count(),1);
    report.steps.push('Read-only acceptance of already approved candidate; no repeated clinical review or coding request.');
    report.original=await download(page.getByRole('link',{name:/Export original format/}),'synthetic-original.docx');
  }
  let exportRequests=0;
  page.on('request',r=>{if(r.url().includes('/export-with-codes/'))exportRequests++;});
  await page.locator('#coding-time').fill('25');
  assert.equal(await page.locator('[data-export-with-codes]').getAttribute('aria-disabled'),'true');
  // Exercise the click guard even though Playwright correctly recognizes the
  // aria-disabled link. This bypasses only its enabled-element wait; the app
  // handler must still prevent the request and explain the unsaved edit.
  await page.locator('[data-export-with-codes]').click({force:true});
  assert.match(await page.locator('[data-coding-error]').innerText(),/Save or undo/);
  assert.equal(exportRequests,0);
  await page.locator('[data-coding-form=context] [data-coding-undo]').click();
  assert.equal(await page.locator('[data-export-with-codes]').getAttribute('aria-disabled'),'false');
  assert.equal(await page.locator('[data-coding-error]').isVisible(),false);
  report.steps.push('Unsaved coding context blocks export without a request; undo restores the persisted approval.');
  report.with_codes=await download(page.locator('[data-export-with-codes]'),'synthetic-with-codes.docx');
  report.repeat=await download(page.locator('[data-export-with-codes]'),'synthetic-with-codes-repeat.docx');
  assert.equal(report.with_codes.sha256,report.repeat.sha256);
  report.original_after=await download(page.getByRole('link',{name:/Export original format/}),'synthetic-original-after.docx');
  assert.equal(report.original.sha256,report.original_after.sha256);
  await page.screenshot({path:path.join(out,'desktop-approved.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  report.mobile=await geometry();assert.ok(report.mobile.body_width<=report.mobile.viewport);
  report.mobile_download=await download(page.locator('[data-export-with-codes]'),'synthetic-with-codes-mobile.docx');
  assert.equal(report.with_codes.sha256,report.mobile_download.sha256);
  await page.screenshot({path:path.join(out,'mobile-approved.png'),fullPage:true});
  assert.deepEqual(report.external_requests,[]);assert.deepEqual(report.errors,[]);
  report.verdict='PASS';
})().catch(async e=>{report.verdict='FAIL';report.failure=String(e);if(page){report.page_text=await page.locator('body').innerText().catch(()=>'<unavailable>');await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}process.exitCode=1;
}).finally(async()=>{report.finished_at=new Date().toISOString();fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2),{mode:0o600});await browser?.close();console.log(JSON.stringify({verdict:report.verdict,output:out,failure:report.failure}));});
