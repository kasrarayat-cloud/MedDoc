/* Focused offline browser control: a pending read cannot obscure or repeat a save. */
'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require('playwright');
const panel = (version='v1', value='one') => `<section data-coding-panel data-encounter-id="fixture" data-status-url="/status/" data-version="${version}" data-pending="false">
<div data-coding-error tabindex="-1" hidden></div><div data-coding-connection hidden></div><div data-coding-dirty hidden>Unsaved</div>
<div data-coding-update hidden><button data-coding-load>Load saved result</button></div>
<form data-coding-form="selections" action="/selections/"><input name="choice" value="${value}"><button type="submit">Save</button></form>
<form data-coding-form="approval" action="/approval/"><button type="submit">Approve</button></form>
<a href="/export/" data-export-with-codes>Export</a></section>`;
(async () => {
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:panel()}));
  await page.goto('https://offline.invalid/');
  await page.evaluate(() => {
   window.requests=[];
   window.fetch=(url,options={})=>new Promise((resolve,reject)=>{
    const item={method:options.method||'GET',url:String(url),aborted:false,settled:false};
    window.requests.push(item);
    item.finish=(status,data)=>{item.settled=true;resolve({status,json:async()=>data});};
    item.fail=()=>{item.settled=true;reject(new TypeError('Offline interruption'));};
    options.signal.addEventListener('abort',()=>{item.aborted=true;if(!item.settled)reject(new DOMException('Aborted','AbortError'));});
   });
  });
  await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../static/coding.js'),'utf8')});
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForFunction(()=>window.requests.length===1);
  await page.locator('[name=choice]').fill('two');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),true);
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await page.waitForFunction(()=>window.requests.filter(r=>r.method==='POST').length===1);
  assert.equal(await page.evaluate(()=>window.requests[0].aborted),true);
  await page.evaluate(html=>window.requests.find(r=>r.method==='POST').finish(409,{encounter_id:'fixture',version:'v2',html,error:'Stale selection'}),panel('v2','other'));
  await page.waitForFunction(()=>document.querySelector('[data-coding-error]').textContent==='Stale selection');
  assert.equal(await page.locator('[name=choice]').inputValue(),'two');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),true);
  assert.equal(await page.locator('[data-export-with-codes]').getAttribute('aria-disabled'),'true');
  await page.locator('[data-coding-load]').click();
  assert.equal(await page.locator('[name=choice]').inputValue(),'other');
  await page.locator('[name=choice]').fill('three');
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await page.waitForFunction(()=>window.requests.filter(r=>r.method==='POST').length===2);
  await page.evaluate(()=>window.requests.filter(r=>r.method==='POST')[1].fail());
  await page.waitForFunction(()=>document.querySelector('[data-coding-error]').textContent.includes('No action will be resent'));
  await page.evaluate(()=>document.querySelector('[data-coding-form=selections]').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  assert.equal(await page.evaluate(()=>window.requests.filter(r=>r.method==='POST').length),2);
  assert.equal(await page.locator('[name=choice]').inputValue(),'three');
  assert.equal(await page.locator('[data-coding-form=approval] button').isDisabled(),true);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'PASS',scope:'Offline mocked-fetch browser only',provider_calls:0,
   controls:['inflight GET aborted on save','one POST per explicit action','stale response stages saved data without losing edits','approval/export blocked while unsaved or stale','interrupted POST never resent','local edits retained after interruption']}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
