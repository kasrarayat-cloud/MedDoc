/* Browser contract: a committed save and a failed panel refresh are distinct. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const panel = (version='v1', value='one') => `<section data-coding-panel data-encounter-id="fixture" data-status-url="/status/" data-version="${version}" data-pending="false">
<div data-coding-error tabindex="-1" hidden></div><div data-coding-connection hidden></div><div data-coding-dirty hidden></div>
<div data-coding-update hidden><button data-coding-load>Load saved result</button></div>
<form data-coding-form="selections" action="/selections/"><input name="choice" value="${value}"><button id="save-selection" type="submit">Save</button></form>
<form data-coding-form="approval" action="/approval/"><button type="submit">Approve</button></form>
<a href="/export/" data-export-with-codes>Export</a></section>`;
const receipt = {encounter_id:'fixture', saved:true, action:'selections', contract:'coding-mutation-receipt-v1', receipt:'signed-bound-receipt', status_url:'/status/'};
(async () => {
 const browser = await chromium.launch({headless:true});
 try {
  const page = await browser.newPage(); const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => route.fulfill({contentType:'text/html',body:panel()}));
  await page.goto('https://offline.invalid/');
  await page.evaluate(() => {
   window.requests=[]; window.timeoutDelays=[];
   const realTimeout=window.setTimeout;
   window.setTimeout=(fn,ms,...args)=>{window.timeoutDelays.push(ms);return realTimeout(fn,ms>=2000&&ms<=30000?60000:ms,...args);};
   window.fetch=(url, options={}) => new Promise((resolve,reject) => {
    const item={method:options.method||'GET',url:String(url),headers:options.headers};window.requests.push(item);
    item.finish=(status,data)=>resolve({status,json:async()=>data});
    item.fail=()=>reject(new TypeError('Connection lost'));
    options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));
   });
  });
  await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../static/coding.js'),'utf8')});
  await page.locator('[name=choice]').fill('two');
  await page.locator('#save-selection').click();
  await page.waitForFunction(()=>window.requests.length===1);
  assert.equal(await page.evaluate(()=>window.requests[0].headers['X-QuillMD-Coding-Response']),receipt.contract);
  assert(await page.evaluate(()=>window.timeoutDelays.includes(135000)));
  await page.evaluate(value=>window.requests[0].finish(200,value),receipt);
  await page.waitForFunction(()=>window.requests.length===2);
  assert.equal(await page.evaluate(()=>window.requests[1].method),'GET');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),true);
  await page.evaluate(()=>window.requests[1].fail());
  await page.waitForFunction(()=>document.querySelector('[data-coding-error]').textContent.startsWith('Saved. The current review could not be loaded.'));
  assert(!(await page.locator('[data-coding-error]').textContent()).includes('save response was interrupted'));
  assert.equal(await page.locator('[name=choice]').inputValue(),'two');
  await page.locator('[data-coding-load]').click();
  await page.waitForFunction(()=>window.requests.length===3);
  await page.evaluate(html=>window.requests[2].finish(200,{encounter_id:'fixture',version:'v2',html}),panel('v2','two'));
  await page.waitForFunction(()=>document.querySelector('[data-coding-connection]').hidden && !document.querySelector('[data-coding-update]').hidden);
  await page.waitForTimeout(20);
  await page.locator('[data-coding-load]').click();
  assert.equal(await page.locator('[name=choice]').inputValue(),'two');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),false);
  // A committed no-op can retain the same view version. Its receipt still
  // permits an explicit reload after a failed refresh.
  await page.locator('#save-selection').click();
  await page.waitForFunction(()=>window.requests.filter(r=>r.method==='POST').length===2);
  await page.evaluate(value=>window.requests.filter(r=>r.method==='POST')[1].finish(200,value),receipt);
  await page.waitForFunction(()=>window.requests.length===5);
  await page.evaluate(()=>window.requests[4].fail());
  await page.waitForFunction(()=>document.querySelector('[data-coding-error]').textContent.startsWith('Saved. The current review could not be loaded.'));
  await page.locator('[data-coding-load]').click();
  await page.waitForFunction(()=>window.requests.length===6);
  await page.evaluate(html=>window.requests[5].finish(200,{encounter_id:'fixture',version:'v2',html}),panel('v2','two'));
  await page.waitForTimeout(20);
  await page.locator('[data-coding-load]').click();
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),false);
  await page.locator('[name=choice]').fill('three'); await page.locator('#save-selection').click();
  await page.waitForFunction(()=>window.requests.length===7);
  await page.evaluate(value=>window.requests[6].finish(200,value),receipt);
  await page.waitForFunction(()=>window.requests.length===8);
  await page.evaluate(html=>window.requests[7].finish(200,{encounter_id:'fixture',version:'v3',html}),panel('v3','three'));
  await page.waitForFunction(()=>document.querySelector('[data-coding-panel]').dataset.version==='v3');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'save-selection');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),false);
  assert.equal(await page.evaluate(()=>window.requests.filter(r=>r.method==='POST').length),3);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'PASS',provider_calls:0,scope:'Offline mocked transport browser',
   controls:['negotiated compact mutation receipt','POST covers server request budget','one POST per explicit action','saved receipt survives failed GET','acknowledged no-op reloads with unchanged version','current read staged explicitly','focus restored after receipt plus refresh']}));
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
