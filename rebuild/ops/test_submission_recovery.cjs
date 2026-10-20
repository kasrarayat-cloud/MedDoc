/* Offline native-form cancellation and uncertain navigation: no application or provider. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
// Keep the navigation in an inert child frame so the test instrument can read
// the original form while a genuine POST is in flight. No application runs.
const fixture = '<!doctype html><iframe name="pending-save" title="Offline transport fixture"></iframe><form method="post" action="/save/" target="pending-save" data-submit-once data-unsaved-form><input name="answer" value="original"><button type="submit">Save</button></form>';
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext();
    let posts = 0, held, blockSubmission = false;
    await context.route('**/*', route => {
      if (route.request().method() === 'POST') {
        posts++;
        if (blockSubmission) return route.abort('blockedbyclient');
        held = route; return;
      }
      return route.fulfill({contentType:'text/html', body:fixture});
    });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto('https://offline.invalid/');
    await page.addScriptTag({content:source});
    await page.evaluate(() => {
      const form = document.querySelector('form');
      form.addEventListener('submit', event => event.preventDefault(), {once:true});
    });
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(20);
    assert.equal(await page.locator('form').getAttribute('data-submitting'), null);
    assert.equal(await page.locator('button[type=submit]').textContent(), 'Save');
    assert.equal(posts, 0);
    // An unrelated handler owns its own pending UI after preventing native
    // navigation; the native form guard must not overwrite that UI either.
    await page.evaluate(() => document.querySelector('form').addEventListener('submit', event => {
      event.preventDefault(); document.querySelector('button[type=submit]').textContent = 'Other transport';
    }, {once:true}));
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(20);
    assert.equal(await page.locator('button[type=submit]').textContent(), 'Other transport');
    await page.evaluate(() => {
      document.querySelector('button[type=submit]').textContent = 'Save';
      const realTimeout = window.setTimeout;
      window.setTimeout = (callback, delay, ...args) => realTimeout(callback, delay === 15000 ? 50 : delay, ...args);
    });
    await page.locator('input').fill('Retained unsaved qualifier');
    await page.locator('button[type=submit]').click({noWaitAfter:true});
    await page.waitForFunction(() => document.querySelector('form')?.dataset.submitting === 'uncertain');
    assert.equal(posts, 1);
    const uncertain = await page.evaluate(() => ({value:document.querySelector('input').value,
      label:document.querySelector('button[type=submit]').textContent,
      help:document.querySelector('[data-submission-recovery]').textContent,
      href:document.querySelector('[data-submission-recovery] a').getAttribute('href'),
      target:document.querySelector('[data-submission-recovery] a').getAttribute('target')}));
    assert.equal(uncertain.value, 'Retained unsaved qualifier');
    assert.equal(uncertain.label, 'Save result unconfirmed');
    assert.match(uncertain.help, /may still complete/);
    // A programmatic second click must not bypass the uncertainty guard.
    await page.evaluate(() => document.querySelector('button[type=submit]').click());
    await page.waitForTimeout(20); assert.equal(posts, 1);
    assert.equal(uncertain.href, 'https://offline.invalid/');
    assert.equal(uncertain.target, '_blank');
    // Confirmed native navigation can finish later. This is not a failed-save
    // claim, and no retry was issued while that response was unavailable.
    await held.fulfill({contentType:'text/html', body:'<!doctype html><p>Saved response</p>'});
    await page.frameLocator('iframe').getByText('Saved response', {exact:true}).waitFor();
    assert.equal(posts, 1);
    // An actual browser-aborted request has the same uncertain UI contract as
    // a lost response. The application cannot observe whether a server saw it.
    blockSubmission = true;
    const blocked = await context.newPage();
    const failed = [];
    blocked.on('requestfailed', request => failed.push(request.failure()?.errorText));
    await blocked.goto('https://offline.invalid/blocked/');
    await blocked.addScriptTag({content:source});
    await blocked.evaluate(() => {
      const realTimeout = window.setTimeout;
      window.setTimeout = (callback, delay, ...args) => realTimeout(callback, delay === 15000 ? 50 : delay, ...args);
    });
    await blocked.locator('input').fill('Draft retained after browser block');
    await blocked.locator('button[type=submit]').click({noWaitAfter:true});
    await blocked.waitForFunction(() => document.querySelector('form')?.dataset.submitting === 'uncertain');
    assert.equal(await blocked.locator('input').inputValue(), 'Draft retained after browser block');
    assert.equal(await blocked.locator('button[type=submit]').textContent(), 'Save result unconfirmed');
    assert.deepEqual(failed, ['net::ERR_BLOCKED_BY_CLIENT']);
    await blocked.evaluate(() => document.querySelector('button[type=submit]').click());
    await blocked.waitForTimeout(20);
    assert.equal(posts, 2); // One attempted POST on each independent form.
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({result:'PASS', scope:'offline mocked browser navigation', provider_calls:0,
      controls:['later preventDefault releases native guard','other transport owns its UI',
        'uncertain in-flight save retains draft','one POST only','uncertain action cannot repeat',
        'read-only recovery link preserves original tab','late successful response is allowed',
        'actual browser block retains draft without repeating POST']}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
