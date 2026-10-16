/* Focused read-only delivery proof. Never submits a clinician decision. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require('playwright');
const [runtime,out,revision,expectedState='pending']=process.argv.slice(2);
if(!runtime||!out||!revision||![runtime,out].every(path.isAbsolute))throw Error('Absolute private paths and revision required.');
fs.mkdirSync(out,{mode:0o700});
const access=JSON.parse(fs.readFileSync(path.join(runtime,'clinician-access.json')));
const base='https://app.quillmd.com/synthetic/corti';
const url=base+'/encounters/a724dfab-59fe-45ac-87de-88cbc9d92d17/?tab=coding';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const report={scope:'Focused synthetic output review, ordinary clinician HTTPS, read-only; no acceptance submitted.',provider_calls:0,decision_posts:0,downloads:[],errors:[]};
let browser,page;
async function save(locator,name){const pending=page.waitForEvent('download');await locator.click();const d=await pending;const target=path.join(out,name);await d.saveAs(target);fs.chmodSync(target,0o600);const sha256=hash(fs.readFileSync(target));report.downloads.push({file:name,sha256});return sha256;}
(async()=>{
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 await context.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.origin==='https://app.quillmd.com'&&u.pathname.startsWith('/synthetic/corti/')&&(r.method()==='GET'||u.pathname==='/synthetic/corti/login/'))return route.continue();report.errors.push('Unexpected request: '+r.method()+' '+u.pathname);return route.abort();});
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>report.errors.push(e.message));
 const health=await (await context.request.get(base+'/health/')).json();assert.deepEqual(health,{status:'ok',data_mode:'synthetic-only',surface:'doctor',release:revision});
 await page.goto(url);assert.ok(page.url().startsWith(base+'/login/'));
 await page.locator('[name=email]').fill(access.email);await page.locator('[name=password]').fill(access.password);
 await Promise.all([page.waitForURL(u=>!u.pathname.endsWith('/login/')),page.getByRole('button',{name:'Sign in',exact:true}).click()]);
 await page.goto(url);await page.locator('[data-coding-output-review]').waitFor();
 assert.equal(await page.locator('[data-corti-evidence]').count(),7);
 assert.equal(await page.locator('[data-coding-output-review]').getAttribute('data-output-review-state'),expectedState);
 report.saved_state=expectedState;
 if(expectedState==='pending'){
  assert.equal(await page.locator('#coding-output-confirm').isChecked(),false);
  assert.equal(await page.getByRole('button',{name:'Confirm note facts and accept 99213',exact:true}).isEnabled(),true);
 }
 assert.match(await page.locator('[data-output-review-basis]').innerText(),/upstream description and terminology version remain unresolved/);
 assert.equal(await page.locator('[data-output-note-fact]').count(),8);
 const original=await save(page.getByRole('link',{name:/Export original format/}),'synthetic-original.docx');
 assert.equal(original,'63c0058fe4b9976d1d31ca31d081a2efb83d4ce87696dab70eb3277ea81344fa');
 const approved=await save(page.getByRole('link',{name:/Export with codes/}),'synthetic-approved.docx');
 if(expectedState==='pending')assert.equal(approved,'5d05e781e2b9a514722c0a26d707764cefeb68ecf26cbfd5bce0c9170858eac1');
 await save(page.getByRole('link',{name:/Download synthetic draft/}),'synthetic-draft-not-approved.docx');
 await page.locator('[data-coding-output-review]').screenshot({path:path.join(out,'review-desktop.png')});
 await page.setViewportSize({width:390,height:844});
 const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(size.scroll<=size.width);report.mobile_width=size;
 await page.locator('[data-coding-output-review]').screenshot({path:path.join(out,'review-mobile.png')});
 assert.deepEqual(report.errors,[]);report.verdict='PASS';report.url=url;
})().catch(e=>{report.verdict='FAIL';report.failure=String(e);process.exitCode=1;}).finally(async()=>{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2),{mode:0o600});await browser?.close();console.log(JSON.stringify({verdict:report.verdict,failure:report.failure,out}));});
