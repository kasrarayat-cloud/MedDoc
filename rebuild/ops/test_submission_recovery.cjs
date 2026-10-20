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
    // Actual top-level editing DOM, rather than an iframe. The server fixture
    // models the separately tested ordinary Django save/reconciliation contract.
    const recovery = await browser.newContext({serviceWorkers:'block'});
    const crypto = require('node:crypto');
    let mode, revision, mutations, attempts, reads, receipts, heldSave;
    const initialBinding = 'a'.repeat(64), changedBinding = 'b'.repeat(64);
    const reset = value => {mode=value; revision=0; mutations=0; attempts=[]; reads=0; receipts=new Map(); heldSave=null;};
    const headersOf = request => request.headers();
    await recovery.route('**/*', async route => {
      const request = route.request(), headers = headersOf(request);
      assert.equal(new URL(request.url()).origin, 'https://save.invalid');
      if (!headers['x-quillmd-save']) return route.fulfill({contentType:'text/html', body:
        `<!doctype html><meta charset="utf-8"><form method="post" action="/edit/" data-submit-once data-unsaved-form data-recoverable-save="all" data-save-revision="${revision}" data-save-binding="${revision ? changedBinding : initialBinding}"><textarea name="answer">original</textarea><button type="submit">Save draft</button></form>`});
      const identity = {attempt:headers['x-quillmd-save-attempt'], digest:headers['x-quillmd-save-digest'],
        base_revision:Number(headers['x-quillmd-save-revision']), base_binding:headers['x-quillmd-save-binding']};
      const body = (state, extra={}) => ({contract:'revision-bound-form-save-v1', ...identity, state,
        current_revision:revision, current_binding:revision ? changedBinding : initialBinding, ...extra});
      if (request.method() === 'GET') {
        reads++;
        const receipt = receipts.get(identity.attempt);
        return route.fulfill({contentType:'application/json', body:JSON.stringify(receipt || body(revision === identity.base_revision ? 'not_recorded_at_read' : 'changed'))});
      }
      assert.equal(request.method(), 'POST');
      assert.equal(new URL(request.url()).pathname, '/edit/');
      const controls = new Map();
      for (const [key,value] of new URLSearchParams(request.postData())) {
        if (!controls.has(key)) controls.set(key, []);
        controls.get(key).push(value.replace(/\r\n?/g, '\n'));
      }
      assert.equal(crypto.createHash('sha256').update(JSON.stringify([...controls].sort())).digest('hex'), identity.digest);
      attempts.push({...identity, answer:controls.get('answer')?.[0]});
      if (mode === 'blocked') return route.abort('blockedbyclient');
      if (mode === 'denied') return route.fulfill({status:403, body:'Permission denied'});
      if (mode === 'stale') return route.fulfill({status:409, contentType:'application/json', body:JSON.stringify(body('changed'))});
      if (mode === 'validation') return route.fulfill({status:409, contentType:'text/plain',
        headers:{'X-QuillMD-Save-State':'rejected'}, body:'The required question quote is not in the original form.'});
      let receipt = receipts.get(identity.attempt);
      if (!receipt) {
        mutations++; revision++;
        receipt = body('committed', {saved_revision:revision, redirect_url:'/saved/'});
        receipts.set(identity.attempt, receipt);
      }
      if (mode === 'lost') return route.abort('failed');
      if (mode === 'held') { heldSave = {route, receipt}; return; }
      return route.fulfill({contentType:'application/json', body:mode === 'malformed' ? '{' : JSON.stringify(receipt)});
    });
    const open = async () => {
      const page = await recovery.newPage(); await page.goto('https://save.invalid/edit/');
      await page.addScriptTag({content:source});
      await page.locator('textarea').fill('Earlier baseline; current symptoms retained.');
      return page;
    };
    const submit = page => page.locator('button[type=submit]').click({noWaitAfter:true});
    const unconfirmed = page => page.waitForFunction(() => document.querySelector('button[type=submit]')?.textContent === 'Save result unconfirmed');
    reset('blocked');
    const topBlocked = await open(); await submit(topBlocked); await unconfirmed(topBlocked);
    assert.equal(topBlocked.url(), 'https://save.invalid/edit/');
    assert.equal(await topBlocked.locator('textarea').inputValue(), 'Earlier baseline; current symptoms retained.');
    await topBlocked.locator('button[type=submit]').evaluate(button => button.click());
    await topBlocked.waitForTimeout(30); assert.equal(attempts.length, 1); assert.equal(mutations, 0);
    await topBlocked.locator('[data-save-check]').click();
    await topBlocked.getByRole('button', {name:'Retry this save', exact:true}).waitFor();
    assert.equal(attempts.length, 1); assert.equal(reads, 1);
    mode = 'success'; await submit(topBlocked); await topBlocked.waitForURL('https://save.invalid/saved/');
    assert.equal(mutations, 1); assert.equal(attempts.length, 2);
    assert.equal(attempts[0].attempt, attempts[1].attempt); assert.equal(attempts[0].digest, attempts[1].digest);
    reset('lost');
    const lost = await open(); await submit(lost); await unconfirmed(lost);
    assert.equal(mutations, 1); assert.equal(attempts.length, 1);
    await lost.locator('[data-save-check]').click();
    await lost.getByRole('button', {name:'Save confirmed', exact:true}).waitFor();
    assert.equal(attempts.length, 1); assert.equal(reads, 1);
    assert.equal(await lost.locator('textarea').inputValue(), 'Earlier baseline; current symptoms retained.');
    reset('denied');
    const denied = await open(); await submit(denied);
    await denied.getByRole('button', {name:'Save denied', exact:true}).waitFor();
    await denied.locator('button[type=submit]').evaluate(button => button.click());
    await denied.waitForTimeout(30); assert.equal(attempts.length, 1); assert.equal(reads, 0); assert.equal(mutations, 0);
    assert.equal(denied.url(), 'https://save.invalid/edit/');
    assert.equal(await denied.locator('textarea').inputValue(), 'Earlier baseline; current symptoms retained.');
    reset('stale');
    const stale = await open(); revision = 1; await submit(stale);
    await stale.getByRole('button', {name:'Revision conflict', exact:true}).waitFor();
    assert.equal(mutations, 0); assert.equal(attempts.length, 1);
    reset('malformed');
    const malformed = await open(); await submit(malformed); await unconfirmed(malformed);
    await malformed.locator('[data-save-check]').click();
    await malformed.getByRole('button', {name:'Save confirmed', exact:true}).waitFor();
    assert.equal(mutations, 1); assert.equal(attempts.length, 1);
    reset('validation');
    const validation = await open(); await submit(validation);
    await validation.locator('[data-submission-recovery]').getByText(/required question quote/).waitFor();
    await submit(validation); await validation.waitForTimeout(30); assert.equal(attempts.length, 1);
    await validation.locator('textarea').fill('Corrected question requirement.');
    mode = 'success'; await submit(validation); await validation.waitForURL('https://save.invalid/saved/');
    assert.equal(mutations, 1); assert.equal(attempts.length, 2);
    assert.notEqual(attempts[0].attempt, attempts[1].attempt);
    reset('success');
    const duringDigest = await open();
    await duringDigest.evaluate(() => {
      const digest = crypto.subtle.digest.bind(crypto.subtle);
      crypto.subtle.digest = (...args) => new Promise(resolve => {
        window.releaseSaveDigest = () => resolve(digest(...args));
        window.saveDigestPending = true;
      });
    });
    await submit(duringDigest); await duringDigest.waitForFunction(() => window.saveDigestPending);
    await duringDigest.locator('textarea').fill('New qualifier typed during digest; still unsaved.');
    await duringDigest.evaluate(() => window.releaseSaveDigest());
    await duringDigest.getByRole('button', {name:'Earlier save confirmed', exact:true}).waitFor();
    assert.equal(duringDigest.url(), 'https://save.invalid/edit/');
    assert.equal(attempts[0].answer, 'Earlier baseline; current symptoms retained.');
    assert.equal(await duringDigest.locator('textarea').inputValue(), 'New qualifier typed during digest; still unsaved.');
    assert.match(await duringDigest.locator('[data-submission-recovery]').textContent(), /later edits are still unsaved/);
    reset('held');
    const duringPost = await open(); await submit(duringPost);
    for (let i=0; i<100 && !heldSave; i++) await duringPost.waitForTimeout(10);
    assert.ok(heldSave);
    await duringPost.locator('textarea').fill('New qualifier typed after submission; still unsaved.');
    await duringPost.locator('button[type=submit]').evaluate(button => {button.click(); button.click();});
    assert.equal(attempts.length, 1);
    await heldSave.route.fulfill({contentType:'application/json', body:JSON.stringify(heldSave.receipt)});
    await duringPost.getByRole('button', {name:'Earlier save confirmed', exact:true}).waitFor();
    assert.equal(duringPost.url(), 'https://save.invalid/edit/');
    assert.equal(await duringPost.locator('textarea').inputValue(), 'New qualifier typed after submission; still unsaved.');
    assert.equal(mutations, 1); assert.equal(attempts.length, 1);
    await recovery.close();
    console.log(JSON.stringify({result:'PASS', scope:'offline mocked browser navigation', provider_calls:0,
      controls:['later preventDefault releases native guard','other transport owns its UI',
        'uncertain in-flight save retains draft','one POST only','uncertain action cannot repeat',
        'read-only recovery link preserves original tab','late successful response is allowed',
        'actual browser block retains draft without repeating POST',
        'top-level blocked POST retains editing DOM', 'explicit same-identity retry after unchanged read',
        'committed response loss reconciles by GET', 'security denial has no retry or alternate route',
        'stale revision remains a visible conflict', 'malformed response reconciles without mutation',
        'unchanged rejected controls cannot resubmit', 'corrected refused controls require a new explicit attempt',
        'edits during asynchronous digest retain editing DOM', 'edits after send and repeated clicks retain later draft']}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
