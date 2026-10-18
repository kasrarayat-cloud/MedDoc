/* Offline Chromium regression: disabled save controls must not lose keyboard focus. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const script = fs.readFileSync(path.join(__dirname, '../static/coding.js'), 'utf8');
const panel = (version = 'v1', {complete = false, retained = false} = {}) => `<section data-coding-panel data-encounter-id="fixture" data-status-url="/status/" data-version="${version}" data-pending="false">
<div id="coding-error" data-coding-error tabindex="-1" hidden></div><div data-coding-connection hidden></div><div data-coding-dirty hidden>Unsaved</div>
<div data-coding-update hidden><button id="coding-load" data-coding-load>Load saved result</button></div>
<h3 id="coding-source-review-heading" tabindex="-1">Source review</h3>
${retained ? '<p data-retained-outcome>Previously approved outcome retained</p>' : ''}
${complete ? '<p>Source review complete</p>' : `<form data-coding-form="source-review" action="/source-review/">
<div data-source-row><select id="source-action" name="action:condition" data-source-action><option value="">Choose outcome</option><option value="accept">Accept</option><option value="no_code">No code</option></select>
<input id="source-candidate" name="suggestion:condition" value="candidate" type="checkbox" data-source-candidate>
<textarea id="source-reason" name="reason:condition" data-source-reason></textarea></div>
<button id="coding-source-approve" type="submit" data-source-approve>Approve source review</button></form>`}
<form data-coding-form="selections" action="/selections/"><input id="selection-value" name="choice" value="one"><button id="selection-save" type="submit">Save selections</button></form>
<a id="coding-export" href="/export/" data-export-with-codes>Export</a></section>`;
const controls = [];
let browser;
async function fixture(run) {
  const page = await browser.newPage();
  const errors = [], network = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    network.push(route.request().url());
    if (route.request().url() === 'https://offline.invalid/') return route.fulfill({contentType:'text/html', body:`<button id="outside">Outside panel</button>${panel()}`});
    return route.abort();
  });
  try {
    await page.goto('https://offline.invalid/');
    await page.evaluate(() => {
      window.requests = [];
      window.fetch = (url, options = {}) => new Promise((resolve, reject) => {
        const item = {method:options.method || 'GET', url:String(url), settled:false};
        item.finish = (status, data) => { item.settled = true; resolve({status, json:async () => data}); };
        item.fail = () => { item.settled = true; reject(new TypeError('Offline interruption')); };
        options.signal.addEventListener('abort', () => { if (!item.settled) reject(new DOMException('Aborted', 'AbortError')); });
        window.requests.push(item);
      });
    });
    await page.addScriptTag({content:script});
    await run(page);
    assert.deepEqual(errors, []);
    assert.deepEqual(network, ['https://offline.invalid/']);
  } finally { await page.close(); }
}
async function focused(page, id) {
  await page.waitForFunction(expected => document.activeElement.id === expected, id, {timeout:3000});
}
async function choose(page) {
  await page.locator('#source-action').selectOption('accept');
  await page.locator('#source-candidate').check();
}
async function sourcePost(page, count = 1) {
  await choose(page);
  await page.locator('#coding-source-approve').focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(n => window.requests.filter(r => r.method === 'POST').length === n, count);
  assert.equal(await page.locator('#coding-source-approve').isDisabled(), true);
  assert.equal(await page.evaluate(() => document.activeElement.tagName), 'BODY');
}
async function reply(page, status, version, options = {}, error = '') {
  await page.evaluate(({status, version, html, error}) => window.requests.find(r => !r.settled).finish(status, {encounter_id:'fixture', version, html, error}), {status, version, html:panel(version, options), error});
}
async function poll(page) {
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForFunction(() => window.requests.some(r => !r.settled && r.method === 'GET'));
}
(async () => {
  browser = await chromium.launch({headless:true});
  try {
    await fixture(async page => {
      await sourcePost(page);
      await reply(page, 200, 'v2', {complete:true});
      await focused(page, 'coding-source-review-heading');
      assert.equal(await page.locator('[data-coding-form="source-review"]').count(), 0);
      assert.equal(await page.evaluate(() => window.requests.filter(r => r.method === 'POST').length), 1);
      controls.push('completed source save restores heading after focused submitter is disabled and removed');
      await page.locator('#selection-save').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => window.requests.filter(r => r.method === 'POST').length === 2);
      await reply(page, 200, 'v3', {complete:true});
      await focused(page, 'selection-save');
      controls.push('subsequent save restores its own control without reusing source focus');
    });
    await fixture(async page => {
      await sourcePost(page);
      await reply(page, 200, 'v2', {retained:true});
      await focused(page, 'coding-source-approve');
      assert.equal(await page.locator('#coding-source-approve').isDisabled(), false);
      assert.equal(await page.locator('[data-retained-outcome]').count(), 1);
      assert.equal(await page.locator('#source-action').inputValue(), '');
      await page.keyboard.press('Enter');
      await focused(page, 'coding-error');
      assert.equal(await page.evaluate(() => window.requests.filter(r => r.method === 'POST').length), 1);
      controls.push('partial source save retains approved outcome and restores usable submitter; validation error keeps focus');
    });
    await fixture(async page => {
      await sourcePost(page);
      await reply(page, 409, 'v2', {retained:true}, 'Saved review changed');
      await focused(page, 'coding-error');
      assert.equal(await page.locator('#source-action').inputValue(), 'accept');
      assert.equal(await page.locator('#source-candidate').isChecked(), true);
      await page.locator('#coding-load').click();
      await page.waitForFunction(() => document.querySelector('[data-coding-panel]').dataset.version === 'v2');
      assert.notEqual(await page.evaluate(() => document.activeElement.id), 'coding-source-review-heading');
      assert.notEqual(await page.evaluate(() => document.activeElement.id), 'coding-source-approve');
      await page.locator('#outside').focus();
      await poll(page);
      await reply(page, 200, 'v3', {complete:true});
      await focused(page, 'outside');
      assert.equal(await page.evaluate(() => window.requests.filter(r => r.method === 'POST').length), 1);
      controls.push('409 keeps error focus and edits; staged load and later poll do not inherit POST focus');
    });
    await fixture(async page => {
      await sourcePost(page);
      await page.evaluate(() => window.requests.find(r => !r.settled).fail());
      await focused(page, 'coding-error');
      assert.match(await page.locator('#coding-error').textContent(), /No action will be resent/);
      assert.equal(await page.locator('#source-action').inputValue(), 'accept');
      await page.evaluate(() => document.querySelector('[data-coding-form="source-review"]').requestSubmit(document.querySelector('#coding-source-approve')));
      assert.equal(await page.evaluate(() => window.requests.filter(r => r.method === 'POST').length), 1);
      await focused(page, 'coding-error');
      controls.push('interrupted save keeps error focus and edits without resending');
    });
    await fixture(async page => {
      await sourcePost(page);
      await page.locator('#outside').focus();
      await reply(page, 200, 'v2', {complete:true});
      await page.waitForFunction(() => document.querySelector('[data-coding-panel]').dataset.version === 'v2');
      await focused(page, 'outside');
      controls.push('newer deliberate outside focus is not stolen by successful save');
    });
    await fixture(async page => {
      await page.locator('#source-action').focus();
      await poll(page);
      await reply(page, 200, 'v2', {complete:true});
      await focused(page, 'coding-source-review-heading');
      assert.equal(await page.evaluate(() => window.requests.filter(r => r.method === 'POST').length), 0);
      controls.push('ordinary clean polling retains its current source focus fallback');
    });
    await fixture(async page => {
      await sourcePost(page);
      await page.evaluate(() => window.requests.find(r => !r.settled).finish(200, {encounter_id:'fixture', version:'v2', html:'<p>Invalid panel</p>'}));
      await focused(page, 'coding-error');
      assert.match(await page.locator('#coding-error').textContent(), /No action will be resent/);
      controls.push('invalid response keeps error focus instead of restoring submitter');
    });
    console.log(JSON.stringify({result:'PASS', scope:'Offline Chromium with mocked fetch; no native records or providers', controls, provider_calls:0, native_requests:0}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
