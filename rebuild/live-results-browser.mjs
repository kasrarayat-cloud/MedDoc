// Exact application scripts in isolated real Chromium. Fixture responses model
// transport/state transitions; backend job durability has separate Django tests.
// No installed accounts, provider calls, secrets or native services are used.
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('@playwright/test');
const root=path.dirname(fileURLToPath(import.meta.url)),output=process.argv[2];
assert(output && path.isAbsolute(output),'An explicit fresh private evidence directory is required.');
process.umask(0o077);
await fs.mkdir(output,{mode:0o700});
const scripts=Object.fromEntries(await Promise.all(['app.js','encounter-live.js'].map(async name=>[name,await fs.readFile(path.join(root,'static',name))])));
const id='11111111-1111-4111-8111-111111111111',documentPath=`/encounters/${id}/`;
let state,posts,reads,documents,interruptPost,holdDocument,documentWaiting,releaseDocument,statusCode,postStatusCode;
const job=(state)=>({id:'22222222-2222-4222-8222-222222222222',kind:'generation',state,display_error:'',revision:1});
const reset=()=>{
  state={encounter_id:id,revision:1,status:'draft',pending:false,latest_job:null,result_version:'initial',answers_preview:[]};
  posts=reads=documents=0;interruptPost=holdDocument=documentWaiting=false;releaseDocument=null;statusCode=postStatusCode=200;
};
const transition=(next)=>{
  state={...state,latest_job:job(next),pending:['queued','running','reconciliation'].includes(next),
    result_version:`result-${next}`,status:next==='succeeded'?'review':'draft',
    answers_preview:next==='succeeded'?[{label:'Assessment',text:'Left ankle pain.',status:'supported'}]:[]};
  if(next==='failed')state.latest_job.display_error='Output validation failed; review the retained request. This platform failure is not charged to you.';
};
const html=()=>`<!doctype html><html><head><title>Isolated live-result controls</title><script src="/static/app.js" defer></script><script src="/static/encounter-live.js" defer></script></head><body>
<h1>Synthetic document</h1><span class="badge ${state.status}" data-live-document-status>${state.status}</span><ol data-live-workflow><li>${state.status==='review'?'Review answers':'Add notes'}</li></ol>
<section data-encounter-live data-encounter-id="${id}" data-status-url="${documentPath}status/" data-result-version="${state.result_version}" data-revision="${state.revision}">
<div data-latest-job role="status" hidden></div><div data-pending-job role="status" hidden>Request pending</div><p data-live-connection role="status" hidden></p><div data-live-error role="alert" hidden></div>
<section data-live-result-preview hidden><h3>Saved result ready for review</h3><p data-live-result-help></p><div data-live-result-content></div><button type="button" data-show-saved-result>Show saved result</button></section>
<form action="${documentPath}notes/" method="post" data-submit-once data-unsaved-form data-notes-form><input type="hidden" name="revision" value="${state.revision}"><label for="notes">Source notes</label><textarea id="notes" name="notes">Saved synthetic notes.</textarea><button type="submit">Save source notes</button><p data-notes-status role="status">Saved notes</p></form>
<section class="generation-action"><form action="${documentPath}generate/" method="post" data-submit-once data-generate-form data-generation-available="true"><input type="hidden" name="revision" value="${state.revision}"><button type="submit" data-pending-label="Queuing generation…">Generate supported answers</button><p data-generation-status role="status"></p></form></section>
<section class="voice-input"></section></section>
<div data-live-review><form action="${documentPath}save/" method="post" data-submit-once data-unsaved-form><label for="answer">Assessment</label><textarea id="answer" name="answer">${state.status==='review'?'Left ankle pain.':''}</textarea><p data-source-evidence>${state.status==='review'?'My assessment is left ankle pain.':''}</p><label><input name="reviewed" type="checkbox">I reviewed the answer and evidence.</label><button type="submit">Save review</button></form><aside>Retained request: ${state.latest_job?.state||'none'}</aside></div>
<a href="/other">Other page</a></body></html>`;
const server=http.createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://fixture.invalid').pathname;
  res.setHeader('Cache-Control','no-store');
  if(pathname.startsWith('/static/')){res.setHeader('Content-Type','application/javascript');res.end(scripts[pathname.split('/').at(-1)]);return;}
  if(pathname===documentPath+'status/'){
    reads++;res.writeHead(statusCode,{'Content-Type':'application/json'});res.end(JSON.stringify(state));return;
  }
  if(req.method==='POST'){
    req.resume();posts++;
    if(pathname===documentPath+'generate/'){
      if(postStatusCode===403){res.writeHead(403,{'Content-Type':'text/html'});res.end('<h1>Authorization expired</h1>');return;}
      if(postStatusCode===400){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({message:'The saved source revision changed. Check the document before generating.'}));return;}
      if(!state.latest_job)transition('queued');
      if(interruptPost){interruptPost=false;res.writeHead(200,{'Content-Type':'application/json'});res.write('{"encounter_id":');setTimeout(()=>res.destroy(),20);return;}
      res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({...state,reused:posts>1,message:'Generation queued.'}));return;
    }
    res.writeHead(204);res.end();return;
  }
  documents++;
  const content=html();
  if(holdDocument){documentWaiting=true;await new Promise(resolve=>{releaseDocument=resolve;});}
  res.writeHead(200,{'Content-Type':'text/html'});res.end(content);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const report={format:'quillmd-live-results-browser-v1',started_at:new Date().toISOString(),complete:false,
  scope:'Isolated real Chromium with exact application scripts. UI state/transport evidence; no served-account or provider claim.',provider_calls:0,cases:[],errors:[],external_requests:[]};
report.sources=Object.entries(scripts).map(([name,bytes])=>({path:`rebuild/static/${name}`,sha256:createHash('sha256').update(bytes).digest('hex')}));
let browser,context,page;
const fresh=async()=>{
  if(context)await context.close();
  reset();context=await browser.newContext();
  await context.route('**/*',route=>{
    if(new URL(route.request().url()).origin===base)return route.continue();
    report.external_requests.push(route.request().url());return route.abort();
  });
  page=await context.newPage();page.on('pageerror',error=>report.errors.push(error.message));
  await page.goto(base+documentPath);
  await page.waitForFunction(()=>Boolean(window.quillmdFormState));
};
const reconnect=()=>page.evaluate(()=>window.dispatchEvent(new Event('online')));
const status=async(pattern)=>{await page.waitForFunction(source=>new RegExp(source).test(document.querySelector('[data-latest-job]').textContent),pattern,{timeout:8000});};
const evidence=message=>report.cases.push({passed:true,check:message});
try{
  browser=await chromium.launch({headless:true,channel:'chromium'});report.browser_version=browser.version();
  await fresh();
  await page.locator('[data-generate-form] button').dblclick({force:true});
  await status('Queued');assert.equal(posts,1);
  assert.equal(await page.locator('#notes').getAttribute('readonly'),'');
  transition('running');await status('Running');
  transition('succeeded');await status('Ready for review');
  await page.waitForFunction(()=>document.querySelector('#answer').value==='Left ankle pain.');
  assert.equal(await page.locator('[data-live-document-status]').textContent(),'review');
  assert.equal(await page.locator('[data-live-document-status]').getAttribute('class'),'badge review');
  assert.equal(await page.locator('[data-source-evidence]').textContent(),'My assessment is left ankle pain.');
  assert.equal(await page.locator('#notes').inputValue(),'Saved synthetic notes.');
  assert.equal(await page.locator('#notes').getAttribute('readonly'),null);
  assert.equal(await page.locator('[data-generate-form]').isVisible(),false);
  assert.equal(posts,1);assert.equal(await page.url(),base+documentPath);
  evidence('One AJAX submission shows queued, running and complete review form/evidence without navigation or a repeated POST.');
  await page.locator('#answer').fill('My unsaved clinician correction.');
  await page.locator('[data-notes-form] button[type=submit]').click();
  assert.equal(posts,1);assert.match(await page.locator('[data-notes-status]').textContent(),/Save or undo/);
  let prompted=false;
  page.once('dialog',async dialog=>{prompted=dialog.type()==='beforeunload';await dialog.dismiss();});
  await page.getByText('Other page',{exact:true}).click();
  assert.equal(prompted,true);assert.equal(await page.locator('#answer').inputValue(),'My unsaved clinician correction.');
  evidence('Dynamically returned review forms retain unsaved-edit, cross-form submission and navigation guards.');

  await fresh();
  await page.locator('#notes').fill('Unsaved synthetic source correction.');
  await page.locator('[data-generate-form] button').click();
  assert.equal(posts,0);assert.match(await page.locator('[data-generation-status]').textContent(),/Save or undo/);
  transition('succeeded');await reconnect();await status('Ready for review');
  await page.waitForFunction(()=>document.querySelector('#answer').value==='Left ankle pain.');
  assert.equal(await page.locator('#notes').inputValue(),'Unsaved synthetic source correction.');
  assert.equal(await page.locator('[data-live-result-preview]').isVisible(),false);assert.equal(posts,0);
  evidence('Unsaved source notes block older-source generation and survive a result arriving from another window.');

  await fresh();
  await page.locator('#answer').fill('Unsaved review answer.');
  transition('succeeded');await reconnect();await status('Ready for review');
  await page.waitForSelector('[data-live-result-preview]:not([hidden])');
  assert.equal(await page.locator('#answer').inputValue(),'Unsaved review answer.');
  assert.match(await page.locator('[data-live-result-content]').textContent(),/Assessment.*Left ankle pain/s);
  await page.locator('[data-show-saved-result]').click();
  assert.equal(await page.locator('#answer').inputValue(),'Unsaved review answer.');
  assert.match(await page.locator('[data-live-result-help]').textContent(),/Save or undo/);
  await page.locator('[data-live-review] [data-undo-edits]').click();
  await page.locator('[data-show-saved-result]').click();
  await page.waitForFunction(()=>document.querySelector('#answer').value==='Left ankle pain.');
  assert.equal(posts,0);
  evidence('A returned result is previewed beside unsaved review edits; only explicit save/undo allows the complete saved form to replace them.');

  await fresh();holdDocument=true;
  transition('succeeded');await reconnect();await status('Ready for review');
  for(let i=0;i<60&&!documentWaiting;i++)await new Promise(resolve=>setTimeout(resolve,50));
  assert.equal(documentWaiting,true);
  await page.locator('#answer').fill('Typed while saved HTML was in flight.');
  holdDocument=false;releaseDocument();
  await page.waitForSelector('[data-live-result-preview]:not([hidden])');
  assert.equal(await page.locator('#answer').inputValue(),'Typed while saved HTML was in flight.');assert.equal(posts,0);
  evidence('Edits typed while the result HTML is in flight are rechecked and preserved before any replacement.');

  await fresh();interruptPost=true;
  await page.locator('[data-generate-form] button').click();
  await status('Queued');assert.equal(posts,1);
  transition('failed');await reconnect();await status('Failed');
  assert.match(await page.locator('[data-latest-job]').textContent(),/save the source notes again.*unchanged is fine/is);
  assert.match(await page.locator('[data-latest-job]').textContent(),/not charged to you/);
  assert.equal(await page.locator('[data-live-error]').isVisible(),false);
  assert.equal(posts,1);
  await reconnect();await page.waitForTimeout(300);assert.equal(posts,1);
  await page.reload();await page.waitForTimeout(300);assert.equal(posts,1);
  evidence('A lost POST response reconciles through GET; failure is actionable, and reconnect/reload sends no automatic retry.');

  await fresh();await page.locator('#notes').fill('Offline unsaved source.');
  await context.setOffline(true);await page.evaluate(()=>window.dispatchEvent(new Event('offline')));await reconnect();
  await page.waitForFunction(()=>!document.querySelector('[data-live-connection]').hidden);
  assert.equal(await page.locator('#notes').inputValue(),'Offline unsaved source.');
  transition('succeeded');await context.setOffline(false);await reconnect();await status('Ready for review');
  await page.waitForFunction(()=>document.querySelector('#answer').value==='Left ankle pain.');
  assert.equal(await page.locator('#notes').inputValue(),'Offline unsaved source.');assert.equal(posts,0);
  evidence('Offline interruption reconnects automatically and presents the result without losing unsaved notes or submitting a job.');

  await fresh();await page.locator('#notes').fill('Preserved after access ended.');statusCode=403;await reconnect();
  await page.waitForSelector('[data-live-error]:not([hidden])');
  assert.match(await page.locator('[data-live-error]').textContent(),/session or access ended/);
  assert.equal(await page.locator('[data-live-error] a').getAttribute('href'),'/login/');
  assert.equal(await page.locator('#notes').inputValue(),'Preserved after access ended.');
  assert.equal(await page.locator('[data-generate-form] button').isDisabled(),true);assert.equal(posts,0);
  evidence('Expired access stops polling/submission, provides a sign-in action and keeps local edits.');

  await fresh();postStatusCode=403;
  await page.locator('[data-generate-form] button').click();
  await page.waitForSelector('[data-live-error]:not([hidden])');
  assert.match(await page.locator('[data-live-error]').textContent(),/session or access ended/);
  assert.equal(await page.locator('[data-generate-form] button').isDisabled(),true);
  assert.equal(posts,1);assert.equal(state.latest_job,null);
  evidence('A refused/expired POST authorization gives an actionable sign-in error instead of treating it as a silently successful submission.');

  await fresh();postStatusCode=400;
  await page.locator('[data-generate-form] button').click();
  await page.waitForSelector('[data-live-error]:not([hidden])');await page.waitForTimeout(300);
  assert.match(await page.locator('[data-live-error]').textContent(),/saved source revision changed/);
  assert.equal(await page.locator('#notes').inputValue(),'Saved synthetic notes.');
  assert.equal(await page.locator('[data-generate-form] button').isDisabled(),false);
  assert.equal(posts,1);assert.equal(state.latest_job,null);
  evidence('A server validation refusal displays its actionable message without navigation, lost source text or an automatic retry.');

  await fresh();await page.locator('#notes').fill('Local earlier revision.');
  transition('succeeded');state.revision=2;state.result_version='new-source';await reconnect();await status('Ready for review');
  assert.equal(await page.locator('#notes').inputValue(),'Local earlier revision.');
  assert.equal(await page.locator('[data-notes-form] input[name=revision]').inputValue(),'1');
  assert.equal(await page.locator('[data-notes-form] button[type=submit]').isDisabled(),true);
  assert.match(await page.locator('[data-live-error]').textContent(),/changed in another window/);assert.equal(posts,0);
  evidence('A new server source revision never silently rebinds or submits an older local draft.');
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external_requests,[]);report.complete=true;
}catch(error){report.failure=error.message;throw error;}
finally{
  report.finished_at=new Date().toISOString();
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  if(releaseDocument)releaseDocument();
  if(context)await context.close();if(browser)await browser.close();
  await new Promise(resolve=>server.close(resolve));
  console.log(JSON.stringify({complete:report.complete,checks:report.cases.length,provider_calls:0,evidence:path.join(output,'result.json')}));
}
