// Exact application scripts in real Chromium with loopback synthetic responses.
// This verifies review UI behavior, never installed accounts or provider results.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_DIR
  ? path.join(process.env.PLAYWRIGHT_MODULE_DIR, '@playwright/test') : '@playwright/test');
const root = path.dirname(fileURLToPath(import.meta.url));
const output = process.argv[2];
assert(output && path.isAbsolute(output), 'Provide a new protected evidence directory.');
process.umask(0o077);
await fs.mkdir(output, {mode: 0o700});
const scripts = Object.fromEntries(await Promise.all(['app.js', 'template-semantic-preparation.js', 'template-review.js']
  .map(async name => [name, await fs.readFile(path.join(root, 'static', name))])));
let state = 'queued', statusCode = 200, posts = 0, documents = 0, reads = 0, lastBody='';
const pageHtml = () => `<!doctype html><html><head><title>Synthetic definition review</title>
<script src="/static/app.js" defer></script><script src="/static/template-semantic-preparation.js" defer></script><script src="/static/template-review.js" defer></script></head><body>
<div data-definition-preparation data-state="${state}" data-status-url="/status/">
<h1>Synthetic definition review</h1><h2 data-definition-status>${state}</h2><p data-definition-progress>Retained request</p>
${['review','guided'].includes(state) ? `<form method="post" action="/correct/" data-submit-once data-unsaved-form data-template-review>
<article data-review-field="name"><h3>Patient name</h3><p data-meaning-summary>Only the documented patient name.</p>
<details><summary>Advanced</summary><label for="meaning">What belongs in this field?</label><textarea id="meaning" name="field_name_meaning" data-meaning>Only the documented patient name.</textarea>
<select data-value-type name="field_name_value_type"><option value="person_name">Name</option><option value="number">Number</option></select>
<div data-control-group="numeric" hidden><input name="field_name_minimum" value=""></div></details></article>
<label><input type="checkbox" name="review_summary" required>I compared all definitions with the original.</label><p data-review-feedback role="status"></p>
<button type="submit" data-review-save>Save decisions</button><button type="submit" formaction="/approve/" data-review-approve>Approve template</button></form>` : ''}
<a href="/other/">Other page</a></div></body></html>`;
const server = http.createServer((request, response) => {
  response.setHeader('Cache-Control', 'no-store');
  const url = new URL(request.url, 'http://fixture.invalid');
  if (url.pathname.startsWith('/static/')) {
    response.setHeader('Content-Type', 'application/javascript'); response.end(scripts[url.pathname.split('/').at(-1)]); return;
  }
  if (url.pathname === '/status/') {
    reads++; response.writeHead(statusCode, {'Content-Type':'application/json'});
    response.end(JSON.stringify({state, revision:0, stages:[]})); return;
  }
  if (request.method === 'POST') {posts++; const chunks=[]; request.on('data',chunk=>chunks.push(chunk)); request.on('end',()=>{lastBody=Buffer.concat(chunks).toString();response.writeHead(204);response.end();});return;}
  if (url.pathname === '/review/') documents++;
  response.writeHead(200, {'Content-Type':'text/html'}); response.end(pageHtml());
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const report = {format:'quillmd-semantic-preparation-browser-v1',complete:false,provider_calls:0,
  scope:'Exact application scripts, isolated real Chromium and synthetic loopback responses.',checks:[],errors:[],external_requests:[],
  sources:Object.entries(scripts).map(([name, raw]) => ({path:`rebuild/static/${name}`,sha256:createHash('sha256').update(raw).digest('hex')}))};
let browser, context, page;
const fresh = async nextState => {
  if (context) await context.close(); state = nextState; statusCode = 200; posts = documents = reads = 0;
  context = await browser.newContext();
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin === origin) return route.continue();
    report.external_requests.push(route.request().url()); return route.abort();
  });
  page = await context.newPage(); page.on('pageerror', error => report.errors.push(error.message));
  page.setDefaultTimeout(8000); await page.goto(origin+'/review/');
  await page.waitForFunction(() => Boolean(window.quillmdFormState));
};
const reconnect = () => page.evaluate(() => window.dispatchEvent(new Event('online')));
const waitLabel = text => page.waitForFunction(expected => document.querySelector('[data-definition-status]').textContent === expected, text);
const passed = text => report.checks.push({passed:true,check:text});
try {
  browser = await chromium.launch({headless:true,channel:'chromium'}); report.browser_version = browser.version();
  await fresh('queued'); await waitLabel('Waiting for the preparation worker');
  state = 'proposer'; await reconnect(); await waitLabel('AI proposer is defining answer meanings');
  state = 'checker'; await reconnect(); await waitLabel('Independent AI checker is checking definitions');
  state = 'review'; await reconnect(); await page.waitForSelector('[data-template-review]');
  assert.equal(posts,0); assert.equal(documents,2); assert.equal(await page.locator('#meaning').inputValue(),'Only the documented patient name.');
  passed('Preparation progress updates queued, proposer and independent checker; retained review appears automatically without any POST.');

  await fresh('queued'); statusCode = 503; await reconnect();
  await page.waitForFunction(() => document.querySelector('[data-definition-progress]').textContent.includes('Connection interrupted'));
  statusCode = 200; state = 'guided'; await reconnect(); await page.waitForSelector('[data-template-review]');
  assert.equal(posts,0); assert(reads >= 2);
  passed('An interrupted status connection reconnects and displays retained guided review without repeating a preparation request.');

  await fresh('review');
  assert.equal(await page.locator('[name=review_summary]').isChecked(),false);
  assert.equal(await page.locator('[data-control-group=numeric]').isVisible(),false);
  await page.locator('summary').click();await page.locator('#meaning').fill('My unsaved precise definition.');
  await page.locator('[name=review_summary]').check();await page.locator('[data-review-approve]').click();
  assert.equal(posts,0); assert.equal(await page.locator('#meaning').inputValue(),'My unsaved precise definition.');
  let warned = false;
  page.once('dialog', async dialog => {warned = dialog.type()==='beforeunload'; await dialog.dismiss();});
  await page.getByText('Other page',{exact:true}).click();
  assert.equal(warned,true); assert.equal(await page.locator('#meaning').inputValue(),'My unsaved precise definition.');
  passed('Unsaved definition edits block approval of older values and survive a dismissed navigation warning.');

  await fresh('review');
  await page.locator('[name=review_summary]').check();
  await page.locator('[data-template-review]').evaluate(form => {form.requestSubmit(); form.requestSubmit();});
  await page.waitForTimeout(100); assert.equal(posts,1);
  passed('Repeated correction submits send one POST; application submit-once protection remains active.');
  await fresh('review');await page.locator('summary').click();
  await page.locator('#meaning').fill('\nPatient name.\nPreserve all surnames.');
  await page.locator('[name=review_summary]').check();
  await page.locator('[data-review-save]').click();await page.waitForTimeout(100);
  assert.equal(new URLSearchParams(lastBody).get('field_name_meaning'),'\r\nPatient name.\r\nPreserve all surnames.');
  passed('Actual browser POST preserves leading textarea newline and uses CRLF serialization covered by the server adapter tests.');
  assert.deepEqual(report.errors,[]); assert.deepEqual(report.external_requests,[]); report.complete=true;
} catch (error) {report.failure=error.message; throw error;}
finally {
  await fs.writeFile(path.join(output,'result.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  if (context) await context.close(); if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
  console.log(JSON.stringify({complete:report.complete,checks:report.checks.length,provider_calls:0,evidence:path.join(output,'result.json')}));
}
