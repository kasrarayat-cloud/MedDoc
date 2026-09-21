// Isolated real Chromium recorder/control checks. Synthetic browser media only;
// no installed-account access, provider calls or claim about a physical microphone.
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('@playwright/test');
const root=path.dirname(fileURLToPath(import.meta.url));
const output=process.argv[2];
assert(output && path.isAbsolute(output),'An explicit new evidence directory is required');
process.umask(0o077);
await fs.mkdir(output,{mode:0o700});
const script=await fs.readFile(path.join(root,'static/app.js'));
const html=`<!doctype html><html><head><title>Isolated input controls</title><script src="/app.js" defer></script></head><body>
<h1>Isolated synthetic controls fixture</h1>
<form action="/save" method="post" data-submit-once data-unsaved-form data-notes-form><label for="notes">Source notes</label><textarea id="notes" name="notes">Saved synthetic notes.</textarea><button type="submit">Save source notes</button><p data-notes-status role="status">Saved notes</p></form>
<form action="/generate" method="post" data-submit-once data-generate-form><button type="submit">Generate supported answers</button><p data-generation-status role="status"></p></form>
<form action="/voice" method="post" data-submit-once data-voice-form><button type="button" data-voice-record>Record voice</button><button type="button" data-voice-stop disabled>Stop</button><button type="button" data-voice-discard disabled>Discard recording</button><p data-voice-status role="status"></p><audio data-voice-preview controls hidden></audio><label for="audio">Audio</label><input id="audio" name="audio" type="file" required><label><input name="consent" type="checkbox" required>Explicit processing consent</label><button type="submit">Transcribe recording</button></form>
<form action="/answers" method="post" data-submit-once data-unsaved-form><label for="answer">Synthetic answer</label><textarea id="answer" name="answer">Saved synthetic answer.</textarea><button type="submit">Save answers</button></form>
<form action="/transcript" method="post" data-submit-once data-unsaved-form data-transcript-form><label for="transcript">Synthetic transcript correction</label><textarea id="transcript" name="transcript">Raw synthetic transcript.</textarea><button type="submit">Save reviewed transcript</button></form>
<a href="/other">Other page</a></body></html>`;
const requests=[];
const server=http.createServer((req,res)=>{
  if(req.method==='POST'){requests.push(req.url); req.resume(); res.writeHead(204);res.end();return;}
  if(req.url==='/app.js'){res.writeHead(200,{'Content-Type':'application/javascript'});res.end(script);return;}
  res.writeHead(200,{'Content-Type':'text/html'});res.end(html);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const report={complete:false,evidence:'isolated Chromium with genuine MediaRecorder and synthetic browser audio',provider_requests:0,physical_microphone_verified:false,checks:[],started_at:new Date().toISOString()};
let activePage;
const browser=await chromium.launch({headless:true,channel:'chromium',args:['--use-fake-device-for-media-stream']});
try{
  const context=await browser.newContext({permissions:['microphone']});
  await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  await context.addInitScript(()=>{
    window.testStreams=[];
    const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async(...args)=>{try {const stream=await get(...args);window.testStreams.push(stream);return stream;} catch(error){window.fixtureMediaError={name:error.name,message:error.message};throw error;}};
  });
  const page=await context.newPage();activePage=page;
  await page.goto(base);
  assert.equal(await page.evaluate(()=>window.testStreams.length),0);
  assert.equal(requests.length,0);report.checks.push('Page opening neither records nor submits audio.');
  await page.locator('#notes').fill('Unsaved synthetic correction.');
  await page.getByText('Generate supported answers',{exact:true}).click();
  assert.equal(requests.length,0);
  assert.match(await page.locator('[data-generation-status]').textContent(),/Save or undo the unsaved edits/);
  assert.equal(await page.locator('#notes').inputValue(),'Unsaved synthetic correction.');
  let unloadDialog=false;
  page.once('dialog',async d=>{unloadDialog=d.type()==='beforeunload';await d.dismiss();});
  await page.getByText('Other page',{exact:true}).click();
  assert.equal(unloadDialog,true);
  assert.equal(await page.locator('#notes').inputValue(),'Unsaved synthetic correction.');
  report.checks.push('Unsaved notes block older-source generation and navigation prompts before discard.');
  for (const [selector, initial, edited] of [['#answer','Saved synthetic answer.','Unsaved synthetic answer.'], ['#transcript','Raw synthetic transcript.','Corrected synthetic transcript.']]) {
    await page.locator(selector).fill(edited);
    await page.getByText('Save source notes',{exact:true}).click();
    assert.equal(requests.length,0);
    const other=page.locator(selector).locator('..');
    await other.locator('[data-undo-edits]').click();
    assert.equal(await page.locator(selector).inputValue(),initial);
    await other.locator('[data-undo-edits]').click();
    assert.equal(await page.locator(selector).inputValue(),edited);
    await other.locator('[data-undo-edits]').click();
    assert.equal(await page.locator('#notes').inputValue(),'Unsaved synthetic correction.');
  }
  report.checks.push('Simultaneously edited notes/answers or notes/transcript have explicit reversible undo; no edit is silently discarded.');
  await page.locator('#notes').fill('Saved synthetic notes.');
  await page.locator('[data-voice-record]').click();
  await page.waitForFunction(()=>document.querySelector('[data-voice-status]').textContent.startsWith('Recording.'));
  await page.waitForFunction(()=>window.testStreams.length===1 && window.testStreams[0].getTracks().some(t=>t.readyState==='live'));
  assert.equal(await page.locator('input[type=file]').isDisabled(),true);
  // Genuine recorder needs an actual first data interval before the stop path.
  await page.waitForTimeout(1200);
  await page.locator('[data-voice-stop]').click();
  await page.waitForFunction(()=>document.querySelector('input[type=file]').files.length===1);
  const recording=await page.locator('input[type=file]').evaluate(e=>({bytes:e.files[0].size,type:e.files[0].type}));
  assert(recording.bytes>0);assert.match(recording.type,/audio\/(webm|mp4)/);
  assert.equal(await page.locator('[data-voice-preview]').isVisible(),true);
  assert.equal(await page.locator('input[name=consent]').isChecked(),false);
  assert.equal(await page.evaluate(()=>window.testStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))),true);
  assert.equal(requests.length,0);
  await page.getByText('Transcribe recording',{exact:true}).click();
  assert.equal(requests.length,0);report.checks.push('Genuine recorder start/stop produces synthetic audio, releases tracks and requires consent before submission.');
  await page.getByText('Generate supported answers',{exact:true}).click();
  assert.equal(requests.length,0);
  assert.match(await page.locator('[data-generation-status]').textContent(),/Transcribe or discard/);
  await page.locator('[data-voice-discard]').click();
  assert.equal(await page.locator('input[type=file]').evaluate(e=>e.files.length),0);
  assert.equal(await page.locator('[data-voice-preview]').isVisible(),false);
  assert.match(await page.locator('[data-voice-status]').textContent(),/Nothing was sent/);
  report.checks.push('Selected recording blocks unrelated submission and explicit discard clears it without sending.');
  // A synthetic permission refusal exercises the actual browser denial route;
  // no getUserMedia or MediaRecorder implementation is mocked here.
  const denied=await browser.newContext();
  const deniedPage=await denied.newPage();await deniedPage.goto(base);
  await deniedPage.locator('[data-voice-record]').click();
  await deniedPage.waitForFunction(()=>document.querySelector('[data-voice-status]').textContent.includes('Microphone permission was denied'));
  assert.equal(await deniedPage.locator('[data-voice-record]').isEnabled(),true);
  report.checks.push('Browser microphone permission refusal offers site-permission and file-upload recovery.');
  await denied.close();
  const unavailable=await browser.newContext();
  await unavailable.addInitScript(()=>{window.MediaRecorder=undefined;});
  const unsupported=await unavailable.newPage();await unsupported.goto(base);
  assert.equal(await unsupported.locator('[data-voice-record]').isDisabled(),true);
  assert.match(await unsupported.locator('[data-voice-status]').textContent(),/upload a recording/);
  assert.equal(await unsupported.locator('input[type=file]').isEnabled(),true);
  report.checks.push('Missing recording capability keeps file upload usable.');
  await unavailable.close();
  // Confirm one HTTP action even when the local transport has not navigated.
  await Promise.all([page.waitForResponse(response=>response.url()===base+'/generate' && response.status()===204),
    page.getByText('Generate supported answers',{exact:true}).dblclick()]);
  await page.waitForFunction(()=>document.querySelector('[data-generate-form]').dataset.submitting==='true');
  assert.deepEqual(requests,['/generate']);
  report.checks.push('Repeated submit produces one local request; HTTP/worker tests separately prove reservation idempotency.');
  report.recording=recording;
  report.complete=true;
}catch(error){report.failure={name:error.name,message:error.message};if(activePage)report.fixture_failure_state=await activePage.evaluate(()=>({status:document.querySelector('[data-voice-status]')?.textContent,error:window.fixtureMediaError,streams:window.testStreams?.length}));throw error;}
finally{
  await browser.close();await new Promise(resolve=>server.close(resolve));
  report.finished_at=new Date().toISOString();
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600,flag:'wx'});
}
