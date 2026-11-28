'use strict';
/*
 * The viewer's speed (release 2: RELEASE-2-SPEC R2-10 to R2-18), through the shipped page in Chromium, against
 * ops/dev_preview_server.cjs's mock: what a page load and an opening ask the server for, what fades, the worker made ready
 * ahead, the re-open answered 304 and drawn from page memory (three times over, and after a re-open left while it was
 * answered), the view asked for with the click, what is left after another tab's sign-out, after a session ended or a
 * password to change met first at a viewer's frame - the PDF's fallback and the text's (refused with the site's own
 * headers) - and after pagehide (on a page that saves data too), a late 404 and pagehide met while a document opens, and
 * the lists above 200 documents (an unchanged search never asked again; a failure said under its own list; the list's
 * last page, come under a search answer, searched in the page, the answer's rows kept). Fourteen tests; release 1's page
 * fails all fourteen. A fifteenth (V13, integrated refutation round 1, failclosed-1): a view whose read cannot be
 * recorded is never answered with PDF bytes, the frame the viewer falls back to included, and nothing is drawn - a path
 * release 1's page has too, so it is outside that count. A sixteenth (V14, integrated refutation round 1, viewer-0): a
 * Word document kept open while a later round converts it again draws that round's conversion (the page's poll redraws
 * the viewer whole; its kept copy asked with its tag). A seventeenth (V15, integrated refutation round 2, viewer-1): one
 * zoomed and scrolled across a later round that reads back the same stored conversion keeps its viewer, its zoom and
 * the member's place, asking nothing. An eighteenth (V16, integrated refutation round 2, viewer-0): a Word document
 * opened again while a later round stores its conversion draws that conversion, whichever of the click's view and the
 * detail is read first. Skipped where Playwright is not installed
 * (CPT_VERIFY_PLAYWRIGHT, as ops/walk.cjs reads it), every skip's reason beginning "no Playwright at". CPT_WALK_TEST_PORTS
 * ('first-last') keeps the preview to a range of ports, as ops/test_walk.cjs does. Synthetic documents only.
 *
 *   node --test --test-reporter=tap ops/test_viewer_speed.cjs
 */
const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const test = require('node:test');

const { PLAYWRIGHT } = require('./walk.cjs');

const missing = !fs.existsSync(path.join(PLAYWRIGHT, 'package.json'));
const SKIP = missing && `no Playwright at ${PLAYWRIGHT}`;
// tests/fixtures/customer: two-page PDFs (ready, needs review, one code on two lines) and a text document
const READY = 'f5000000-0000-4000-8000-000000000001';
const REVIEW = 'f4000000-0000-4000-8000-000000000001';
const SAME_CODE = 'fc000000-0000-4000-8000-000000000001';
const TEXT = 'f3000000-0000-4000-8000-000000000001';
// a Word document viewed as the PDF its round 1 converted it to (V14)
const WORD = 'f9000000-0000-4000-8000-000000000001';
const viewOf = id => `/api/encounters/${id}/original?view=1`;
// each test's own limit, so a page that never reaches a state fails rather than waits (the quick leave waits 21.5 s)
const LIMIT_MS = 120000;

// A free loopback port: the first of CPT_WALK_TEST_PORTS that is free, else one the system gives.
async function freePort() {
  const listen = port => new Promise(resolve => {
    const probe = net.createServer();
    probe.once('error', () => resolve(null));
    probe.listen(port, '127.0.0.1', () => {
      const { port: got } = probe.address();
      probe.close(() => resolve(got));
    });
  });
  const range = /^(\d+)-(\d+)$/.exec(process.env.CPT_WALK_TEST_PORTS || '');
  if (!range) return (await listen(0)) ?? Promise.reject(new Error('no free port'));
  for (let port = Number(range[1]); port <= Number(range[2]); port += 1) {
    const got = await listen(port);
    if (got) return got;
  }
  throw new Error(`no free port in ${process.env.CPT_WALK_TEST_PORTS}`);
}

const kit = {};

test.before(async () => {
  if (missing) return;
  const { chromium } = require(PLAYWRIGHT);
  const port = await freePort();
  kit.server = childProcess.spawn(process.execPath, [path.join(__dirname, 'dev_preview_server.cjs'), `--port=${port}`], { stdio: ['ignore', 'pipe', 'pipe'] });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the preview server did not start')), 15000);
    kit.server.stdout.on('data', chunk => { if (String(chunk).includes('CPT Studio dev preview')) { clearTimeout(timer); resolve(); } });
    kit.server.once('exit', code => reject(new Error(`the preview server exited ${code}`)));
  });
  kit.base = `http://127.0.0.1:${port}`;
  kit.browser = await chromium.launch({ headless: true });
});

test.after(async () => {
  await kit.browser?.close();
  if (kit.server && kit.server.exitCode === null) {
    const exited = new Promise(resolve => kit.server.once('exit', resolve));
    kit.server.kill('SIGTERM');
    await exited;
  }
});

// A page of a fresh context (its own cache and storage) opened at `hash`: every request to the API, the session ping
// and the library's files is recorded with its If-None-Match, its poll mark, its status and its body's size; every
// error in the page, and every policy violation, is kept; the entrance fades are counted from the first paint.
async function open(context, hash = '#documents') {
  const page = await context.newPage();
  const calls = [];
  const errors = [];
  page.on('request', request => {
    const url = request.url().replace(kit.base, '');
    if (url.startsWith('/api/') || url.startsWith('/session/') || /\/pdf(\.worker)?\.min\.mjs/.test(url)) {
      const call = { url, request, method: request.method(), condition: request.headers()['if-none-match'] || '', poll: request.headers()['x-cpt-poll'] || '' };
      call.done = new Promise(resolve => { call.finish = resolve; });
      calls.push(call);
    }
  });
  const finished = failed => async request => {
    const call = calls.find(item => item.request === request);
    if (!call) return;
    if (failed) call.failed = true;
    else {
      try {
        Object.assign(call, { status: (await request.response())?.status(), body: (await request.sizes()).responseBodySize });
      } catch {
        call.failed = true;  // its page or context closed as it finished (a test's end): no status, never an unhandled rejection
      }
    }
    call.finish();
  };
  page.on('requestfinished', finished(false));
  page.on('requestfailed', finished(true));
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.addInitScript(() => {
    window.__fades = 0;
    document.addEventListener('animationstart', event => { if (event.animationName === 'enter') window.__fades += 1; }, true);
    document.addEventListener('securitypolicyviolation', event => console.error(`policy: ${event.violatedDirective}`));
  });
  await page.goto(`${kit.base}/${hash}`);
  return { page, calls, errors };
}

const listed = page => page.waitForFunction(() => document.querySelectorAll('#documentsTable .document-row').length > 0);
const drawn = page => page.waitForFunction(() => Boolean(document.querySelector('#documentViewer .pdf-text span')));
// the worker made ready ahead has said it is ready (and with it the library has loaded)
const ready = page => page.waitForFunction(() => Boolean(state.pdfStarted && state.pdfStandby));
const settled = calls => Promise.all(calls.map(call => call.done));
async function openRow(page, id) {
  await page.click(`a.document-row[href="#doc/${id}"]`);
  await drawn(page);
}
async function back(page) {
  await page.click('a.back-link');
  await listed(page);
}
// The site's own refusal headers, read from the server's code - studio/access.py's policy and cptstudio/settings.py's
// X_FRAME_OPTIONS (tests/test_frontend.py holds both on /api/session's 401) - each forbidding framing.
function siteRefusal() {
  const policy = /\n {4}CSP = \(((?:\s*"[^"]*")+)\)/.exec(fs.readFileSync(path.join(__dirname, '..', 'studio', 'access.py'), 'utf8'));
  const frames = /\nX_FRAME_OPTIONS = '([A-Z]+)'/.exec(fs.readFileSync(path.join(__dirname, '..', 'cptstudio', 'settings.py'), 'utf8'));
  assert.ok(policy && frames, 'the site\'s refusal headers, read from its code');
  const csp = [...policy[1].matchAll(/"([^"]*)"/g)].map(part => part[1]).join('');
  assert.deepEqual([/frame-ancestors 'none'/.test(csp), frames[1]], [true, 'DENY'], 'every refusal forbids framing');
  return (status, body) => ({ status, contentType: 'application/json', body: JSON.stringify(body),
    headers: { 'Content-Security-Policy': csp, 'X-Frame-Options': frames[1], 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
}

// a digest of the first page's canvas: its pixels and its size
const pixels = page => page.evaluate(async () => {
  const canvas = document.querySelector('.pdf-page[data-page="1"] canvas');
  const digest = await crypto.subtle.digest('SHA-256', canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data);
  return `${[...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('')} ${canvas.width}x${canvas.height}`;
});

test('V1, V6, V8: a page load asks for no session, fades in once and makes one worker ready; a tab change and an opening fade nothing', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => call.url), [], 'the shell carried the session (R2-17)');
    assert.equal(calls.filter(call => call.url.startsWith('/api/encounters')).length, 1, 'one list request');
    await ready(page);
    assert.equal(page.workers().length, 1, 'one worker waits, holding no document (R2-10)');
    assert.equal(await page.evaluate(() => window.__fades), 1, 'the approved fade, once, on the page load\'s first view (R2-14)');
    await page.click('[data-nav="queue"]');
    await listed(page);
    assert.equal(await page.evaluate(() => window.__fades), 1, 'a tab change fades nothing');
    await openRow(page, READY);
    assert.equal(await page.evaluate(() => window.__fades), 1, 'nor an opening');
    assert.ok(page.workers().length <= 2, 'at most the document\'s own worker and the one made ready ahead');
    assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => call.url), [], 'and no session read on an opening within the minute');
    assert.deepEqual(errors, [], 'no policy violation and no error in the page');
  } finally {
    await context.close();
  }
});

test('V2, V3: an opening asks for the document and its view alone; a re-open, three times over, is answered 304 with no body and draws the same pixels', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    calls.length = 0;
    await openRow(page, READY);
    await settled(calls);
    const api = () => calls.filter(call => call.url.startsWith('/api/')).map(call => [call.url, call.status]).sort();
    assert.deepEqual(api(), [[`/api/encounters/${READY}`, 200], [viewOf(READY), 200]].sort(), 'the details and the view: two requests');
    assert.equal(calls.find(call => call.url === viewOf(READY)).condition, '', 'nothing held yet: nothing asked of the server');
    const first = await pixels(page);
    // three times over: the kept copy is never the array the library is given (which it takes away), so each re-open
    // draws from it again
    for (let reopen = 1; reopen <= 3; reopen += 1) {
      await back(page);
      calls.length = 0;
      await openRow(page, READY);
      await settled(calls);
      const again = calls.filter(call => call.url === viewOf(READY));
      assert.equal(again.length, 1, `re-open ${reopen}: the view asked for once, one record`);
      assert.match(again[0].condition, /^"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"$/, `re-open ${reopen}: with the tag the page holds`);
      assert.deepEqual([again[0].status, again[0].body, again[0].poll], [304, 0, '1'], `re-open ${reopen}: answered 304, no body, as the page's own read`);
      assert.deepEqual(api(), [[`/api/encounters/${READY}`, 200], [viewOf(READY), 304]].sort());
      assert.equal(await pixels(page), first, `re-open ${reopen}: the same pixels, drawn from page memory`);
    }
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V1: leaving a document while its worker starts does not make the page load the library again', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);  // the library loaded and a worker started, in this page
    await back(page);
    // no worker waits, so the next document starts its own; the member leaves it while that worker starts
    await page.evaluate(() => { if (typeof endStandby === 'function') { state.standbyOn = false; endStandby(); } });
    const caught = await page.evaluate(id => new Promise(resolve => {
      location.hash = `doc/${id}`;
      const begun = Date.now();
      const look = setInterval(() => {
        const starting = Boolean(state.viewer?.thread && state.viewer.mode === 'loading');
        if (starting || Date.now() - begun > 10000) {
          clearInterval(look);
          location.hash = 'documents';
          resolve(starting);
        }
      }, 1);
    }), REVIEW);
    assert.ok(caught, 'the document was left while its worker started');
    await listed(page);
    await page.waitForTimeout(21500);  // past the library's 20 s limit
    calls.length = 0;
    await openRow(page, SAME_CODE);
    // the document starts its own worker (none waits), whose script the browser asks for again (from its cache); the
    // library's module is not loaded again, and nothing is asked at a fresh address
    const library = calls.filter(call => /\/pdf(\.worker)?\.min\.mjs/.test(call.url)).map(call => call.url);
    assert.deepEqual(library.filter(url => /\/pdf\.min\.mjs/.test(url)), [], 'the library is not loaded again');
    assert.deepEqual(library.filter(url => /attempt=/.test(url)), [], 'nothing at a fresh address');
    assert.equal(await page.evaluate(() => state.pdfAttempt), 1, 'the first load is the one in use');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V4: a click asks for the view at once where the list says it opens as a PDF, no later than the details; a text is asked for by its frame alone', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);  // the library and a worker have started in this page
    await back(page);
    calls.length = 0;
    await openRow(page, REVIEW);  // a row the list says opens as a PDF, whose bytes the page does not keep
    const at = url => calls.findIndex(call => call.url === url);
    assert.equal(calls.filter(call => call.url === viewOf(REVIEW)).length, 1, 'one request, taken over by the viewer');
    assert.equal(calls.find(call => call.url === viewOf(REVIEW)).condition, '', 'no copy held: the list\'s hint asked for it');
    assert.ok(at(viewOf(REVIEW)) >= 0 && at(viewOf(REVIEW)) < at(`/api/encounters/${REVIEW}`), 'asked for with the click, before the details');
    await back(page);
    calls.length = 0;
    await page.click(`a.document-row[href="#doc/${TEXT}"]`);
    await page.waitForFunction(() => document.querySelector('#documentViewer')?.tagName === 'IFRAME'
      && document.querySelector('#documentViewer').contentDocument?.readyState === 'complete');
    assert.equal(calls.filter(call => call.url === viewOf(TEXT)).length, 1, 'a text: its frame alone asks for it');
    assert.ok(at(viewOf(TEXT)) > at(`/api/encounters/${TEXT}`), 'after its details, as before');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V9: another tab\'s sign-out wipes this tab\'s kept copies and ends its worker; nothing is in the browser\'s storage', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const one = await open(context);
    await listed(one.page);
    await openRow(one.page, READY);
    assert.equal(await one.page.evaluate(() => state.keptViews?.size ?? 0), 1, 'a copy kept for a re-open');
    await one.page.waitForFunction(() => Boolean(state.pdfStandby));  // and a worker waiting for the next document
    const stored = page => page.evaluate(async () => [localStorage.length, sessionStorage.length, (await caches.keys()).length, (await indexedDB.databases()).length]);
    assert.deepEqual(await stored(one.page), [0, 0, 0, 0], 'never in Web Storage, the Cache API or IndexedDB');
    const two = await open(context);
    await listed(two.page);
    let wiped = null;
    await one.page.exposeFunction('reportWipe', value => { wiped = value; });
    await one.page.evaluate(() => {
      const forget = window.forgetMemory;
      window.forgetMemory = function wipeAndReport() {
        const copies = [...state.keptViews.values()].map(item => item.data);
        const waited = state.pdfStandby?.thread ? 'a worker' : 'none';
        forget();
        window.reportWipe({ copies: copies.length, zeroed: copies.every(copy => copy.every(byte => byte === 0)), kept: state.keptViews.size,
          waited, waiting: Boolean(state.pdfStandby), viewer: Boolean(state.viewer) });
      };
    });
    await two.page.evaluate(() => shareSession({ type: 'signed-out', reason: 'idle' }));
    await one.page.waitForURL(url => url.pathname.startsWith('/login'));
    assert.deepEqual(wiped, { copies: 1, zeroed: true, kept: 0, waited: 'a worker', waiting: false, viewer: false }, 'overwritten, dropped, the waiting worker ended');
    assert.deepEqual(await stored(two.page), [0, 0, 0, 0]);
    assert.deepEqual(one.errors, []);
  } finally {
    await context.close();
  }
});

test('V9b, R2-18: a session ended elsewhere, or a password that must change, met first at the framed viewer\'s load - its refusal forbids framing, so the page asks the server - wipes the kept copies and the hints and ends the waiting worker; a refusal that is no end changes nothing', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const site = siteRefusal();
  const ended = { error: 'signed_out', reason: 'idle' };
  const change = { error: 'password_change_required' };
  for (const [what, frame, session, status, leaves] of [
    ['a session ended elsewhere', site(401, ended), site(401, ended), 401, '/login/'],
    ['a password that must change', site(403, change), site(403, change), 403, '/account/'],
    ['a 503, the session still open', site(503, { error: 'The service is not available right now.' }), null, 200, '']]) {
    const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
    try {
      const { page, calls, errors } = await open(context);
      await listed(page);
      await openRow(page, READY);
      assert.equal(await page.evaluate(() => state.keptViews?.size ?? 0), 1, `${what}: a copy kept for a re-open`);
      await page.waitForFunction(() => Boolean(state.pdfStandby?.thread));  // a worker waiting for the next document
      // from here the document's view is refused, with the site's own headers; the session answered as `session` says
      // (else by the preview, 200)
      await context.route(url => url.pathname === `/api/encounters/${READY}/original` && url.search === '?view=1', route => route.fulfill(frame));
      if (session) await context.route(url => url.pathname === '/api/session', route => route.fulfill(session));
      await context.route(url => url.pathname === '/account/', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>Account</title>' }));
      let wiped = null;
      await page.exposeFunction('reportWipe', value => { wiped = value; });
      const hints = await page.evaluate(() => {
        window.__copies = [...state.keptViews.values()].map(item => item.data);
        window.__ended = false;
        const thread = state.pdfStandby.thread;
        const terminate = thread.terminate.bind(thread);
        thread.terminate = () => { window.__ended = true; terminate(); };
        // what this page can read of the frame's answer: a frame the browser blocked throws
        window.__read = [];
        document.addEventListener('load', event => {
          if (event.target !== state.viewer?.frame) return;
          try {
            window.__read.push(String(event.target.contentWindow.performance.getEntriesByType('navigation')[0]?.responseStatus));
          } catch (error) {
            window.__read.push(error.name);
          }
        }, true);
        window.__left = () => ({ copies: window.__copies.length, zeroed: window.__copies.every(copy => copy.every(byte => byte === 0)),
          kept: state.keptViews.size, hints: state.viewHints.size, waiting: Boolean(state.pdfStandby), ended: window.__ended, read: window.__read.slice() });
        // at an end the page leaves at once: what is left is read as it wipes
        const forget = window.forgetMemory;
        window.forgetMemory = function wipeAndReport(...args) {
          forget(...args);
          window.reportWipe(window.__left());
        };
        return state.viewHints.size;
      });
      assert.ok(hints > 0, `${what}: the list's hints held`);
      calls.length = 0;
      // the library could not run (fallbackViewer): the browser's own viewer is framed, and its load is refused
      await page.evaluate(() => fallbackViewer(state.viewer, 'library'));
      if (leaves) {
        await page.waitForURL(url => url.pathname === leaves);
        for (let turn = 0; turn < 200 && wiped === null; turn += 1) await page.waitForTimeout(25);
      } else {
        await page.waitForFunction(() => window.__read.length > 0);
        for (let turn = 0; turn < 200 && !calls.some(call => call.url === '/api/session'); turn += 1) await page.waitForTimeout(25);
        await settled(calls.filter(call => call.url === '/api/session'));
        await page.waitForTimeout(500);
        wiped = await page.evaluate(() => window.__left());
      }
      await settled(calls.filter(call => call.url === '/api/session'));
      assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => [call.method, call.poll, call.status]), [['GET', '1', status]],
        `${what}: the session asked once, as a poll`);
      assert.deepEqual(wiped, leaves ? { copies: 1, zeroed: true, kept: 0, hints: 0, waiting: false, ended: true, read: ['SecurityError'] }
        : { copies: 1, zeroed: false, kept: 1, hints, waiting: true, ended: false, read: ['SecurityError'] },
      `${what}: the frame's answer unreadable; ${leaves ? 'an end: overwritten, dropped, the hints gone, the waiting worker ended' : 'no end: all kept'}`);
      // the blocked frame's own line, and the refused session's, are the only errors in the page
      assert.deepEqual(errors.filter(error => !/^Framing '[^']*' violates the following Content Security Policy directive: "frame-ancestors 'none'"|^Failed to load resource/.test(error)), [],
        `${what}: no other error in the page`);
    } finally {
      await context.close();
    }
  }
});

test('V9c, R2-18: the text viewer\'s frame refused the same way - a session ended elsewhere, a password that must change - wipes the kept copies and the hints and ends the waiting worker; a refusal that is no end changes nothing', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const site = siteRefusal();
  const ended = { error: 'signed_out', reason: 'idle' };
  const change = { error: 'password_change_required' };
  for (const [what, frame, session, status, leaves] of [
    ['a session ended elsewhere', site(401, ended), site(401, ended), 401, '/login/'],
    ['a password that must change', site(403, change), site(403, change), 403, '/account/'],
    ['a 503, the session still open', site(503, { error: 'The service is not available right now.' }), null, 200, '']]) {
    const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
    try {
      const { page, calls, errors } = await open(context);
      await listed(page);
      await openRow(page, READY);
      assert.equal(await page.evaluate(() => state.keptViews?.size ?? 0), 1, `${what}: a copy kept for a re-open`);
      await back(page);
      await page.waitForFunction(() => Boolean(state.pdfStandby?.thread));  // a worker waiting for the next document
      // from here the text document's view - its frame's own load - is refused, with the site's own headers; the session
      // answered as `session` says (else by the preview, 200)
      await context.route(url => url.pathname === `/api/encounters/${TEXT}/original` && url.search === '?view=1', route => route.fulfill(frame));
      if (session) await context.route(url => url.pathname === '/api/session', route => route.fulfill(session));
      await context.route(url => url.pathname === '/account/', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>Account</title>' }));
      let wiped = null;
      await page.exposeFunction('reportWipe', value => { wiped = value; });
      const hints = await page.evaluate(() => {
        window.__copies = [...state.keptViews.values()].map(item => item.data);
        window.__ended = false;
        const thread = state.pdfStandby.thread;
        const terminate = thread.terminate.bind(thread);
        thread.terminate = () => { window.__ended = true; terminate(); };
        // what this page can read of the text frame's answer: a frame the browser blocked throws
        window.__read = [];
        document.addEventListener('load', event => {
          if (event.target?.id !== 'documentViewer' || event.target.tagName !== 'IFRAME') return;
          try {
            window.__read.push(String(event.target.contentWindow.performance.getEntriesByType('navigation')[0]?.responseStatus));
          } catch (error) {
            window.__read.push(error.name);
          }
        }, true);
        window.__left = () => ({ copies: window.__copies.length, zeroed: window.__copies.every(copy => copy.every(byte => byte === 0)),
          kept: state.keptViews.size, hints: state.viewHints.size, waiting: Boolean(state.pdfStandby), ended: window.__ended, read: window.__read.slice() });
        // at an end the page leaves at once: what is left is read as it wipes
        const forget = window.forgetMemory;
        window.forgetMemory = function wipeAndReport(...args) {
          forget(...args);
          window.reportWipe(window.__left());
        };
        return state.viewHints.size;
      });
      assert.ok(hints > 0, `${what}: the list's hints held`);
      calls.length = 0;
      await page.click(`a.document-row[href="#doc/${TEXT}"]`);  // the text document: its frame loads its view
      if (leaves) {
        await page.waitForURL(url => url.pathname === leaves);
        for (let turn = 0; turn < 200 && wiped === null; turn += 1) await page.waitForTimeout(25);
      } else {
        await page.waitForFunction(() => window.__read.length > 0);
        for (let turn = 0; turn < 200 && !calls.some(call => call.url === '/api/session'); turn += 1) await page.waitForTimeout(25);
        await settled(calls.filter(call => call.url === '/api/session'));
        await page.waitForTimeout(500);
        wiped = await page.evaluate(() => window.__left());
      }
      await settled(calls.filter(call => call.url === '/api/session'));
      assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => [call.method, call.poll, call.status]), [['GET', '1', status]],
        `${what}: the session asked once, as a poll`);
      assert.deepEqual(wiped, leaves ? { copies: 1, zeroed: true, kept: 0, hints: 0, waiting: false, ended: true, read: ['SecurityError'] }
        : { copies: 1, zeroed: false, kept: 1, hints, waiting: true, ended: false, read: ['SecurityError'] },
      `${what}: the text frame's answer unreadable; ${leaves ? 'an end: overwritten, dropped, the hints gone, the waiting worker ended' : 'no end: all kept'}`);
      // the blocked frame's own line, and the refused session's, are the only errors in the page
      assert.deepEqual(errors.filter(error => !/^Framing '[^']*' violates the following Content Security Policy directive: "frame-ancestors 'none'"|^Failed to load resource/.test(error)), [],
        `${what}: no other error in the page`);
    } finally {
      await context.close();
    }
  }
});

test('V10, R2-18: pagehide - the back-forward cache included - overwrites and drops the kept copies and the hints, and ends the waiting worker', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);
    assert.equal(await page.evaluate(() => state.keptViews?.size ?? 0), 1, 'a copy kept for a re-open');
    await page.waitForFunction(() => Boolean(state.pdfStandby?.thread));  // a worker waiting for the next document
    // Playwright's Chromium runs with --disable-back-forward-cache and the no-store shell is never cached here, so the
    // event the browser fires as the page goes into the cache is dispatched to the page's own listener, and what is left
    // is read back in the same task
    const left = await page.evaluate(() => {
      const copies = [...state.keptViews.values()].map(item => item.data);
      const thread = state.pdfStandby.thread;
      const terminate = thread.terminate.bind(thread);
      let ended = false;
      thread.terminate = () => { ended = true; terminate(); };
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
      return { copies: copies.length, zeroed: copies.every(copy => copy.every(byte => byte === 0)), kept: state.keptViews.size,
        hints: state.viewHints.size, waiting: Boolean(state.pdfStandby), ended };
    });
    assert.deepEqual(left, { copies: 1, zeroed: true, kept: 0, hints: 0, waiting: false, ended: true },
      'overwritten, dropped, the hints gone, the waiting worker ended');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V10b, R2-18: on a page that saves data, where no worker is made ready ahead, pagehide still overwrites and drops the kept copies and the hints', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    await context.addInitScript(() => Object.defineProperty(Object.getPrototypeOf(navigator.connection), 'saveData', { get: () => true }));
    const { page, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);
    assert.equal(await page.evaluate(() => state.keptViews?.size ?? 0), 1, 'a copy kept for a re-open');
    await page.waitForTimeout(3000);  // past a drawn page's 600 ms and the idle wait: no worker is made ready ahead
    const left = await page.evaluate(() => {
      const copies = [...state.keptViews.values()].map(item => item.data);
      const waiting = Boolean(state.pdfStandby);
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
      return { saveData: navigator.connection.saveData, waiting, copies: copies.length,
        zeroed: copies.every(copy => copy.every(byte => byte === 0)), kept: state.keptViews.size, hints: state.viewHints.size };
    });
    assert.deepEqual(left, { saveData: true, waiting: false, copies: 1, zeroed: true, kept: 0, hints: 0 },
      'overwritten, dropped, the hints gone, with no worker made ready ahead');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V11, R2-15: a re-open left while it is answered - the page aborts its own request - keeps the copy whole; the next re-open is answered 304 from it', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);
    assert.equal(await page.evaluate(() => state.keptViews?.size ?? 0), 1, 'a copy kept for a re-open');
    await back(page);
    // the re-open's answer is held; the member leaves before it comes
    let held = null;
    const pattern = `**${viewOf(READY)}`;
    await page.route(pattern, route => { held = route; });
    await page.click(`a.document-row[href="#doc/${READY}"]`);
    for (let turn = 0; turn < 200 && !held; turn += 1) await page.waitForTimeout(25);
    assert.ok(held, 'the re-open was asked for');
    await page.evaluate(() => { location.hash = 'documents'; });
    await listed(page);
    await held.abort().catch(() => {});  // the page has aborted it already
    await page.unroute(pattern);
    const left = await page.evaluate(view => {
      const item = state.keptViews.get(view);
      return [state.keptViews.size, Boolean(item) && item.data.length > 0 && item.data.some(byte => byte !== 0)];
    }, viewOf(READY));
    assert.deepEqual(left, [1, true], 'kept, and not overwritten');
    calls.length = 0;
    await openRow(page, READY);
    await settled(calls);
    const again = calls.filter(call => call.url === viewOf(READY));
    assert.equal(again.length, 1);
    assert.deepEqual([/^"[0-9a-f-]{36}"$/.test(again[0].condition), again[0].status, again[0].body], [true, 304, 0], 'asked with its tag, answered 304');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V11b, R2-15, R2-18: a late 404 to a route already left, met while the next document opens for the first time, leaves that open its copy - the re-open is a 304; pagehide met there keeps none - the re-open downloads', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const site = siteRefusal();
  const refused = 'f5000000-0000-4000-8000-0000000000ff';
  for (const [what, end] of [['no end', ''], ['the late 404', '404'], ['pagehide', 'pagehide']]) {
    const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
    try {
      const { page, calls, errors } = await open(context);
      await listed(page);
      const started = await page.waitForFunction(() => Boolean(state.pdfStarted && state.pdfStandby), null, { timeout: 20000 }).then(() => true, () => false);
      assert.equal(started, true, `${what}: a worker made ready ahead (R2-10)`);
      // the refused document's details are held; READY's first view is held while its viewer opens
      let detail = null;
      await context.route(url => url.pathname === `/api/encounters/${refused}`, route => { detail = route; });
      let view = null;
      await context.route(url => url.pathname === `/api/encounters/${READY}/original` && url.search === '?view=1', route => {
        if (view) route.continue();
        else view = route;
      });
      await page.evaluate(id => { location.hash = `doc/${id}`; }, refused);
      for (let turn = 0; turn < 400 && !detail; turn += 1) await page.waitForTimeout(25);
      await page.evaluate(id => { location.hash = `doc/${id}`; }, READY);  // the member goes on before that 404 comes
      for (let turn = 0; turn < 400 && !view; turn += 1) await page.waitForTimeout(25);
      await page.waitForFunction(address => state.viewer?.view === address && state.viewer.mode === 'loading' && state.early === null, viewOf(READY));
      const counted = await page.evaluate(() => {
        window.__forgets = [];
        const forget = window.forgetMemory;
        window.forgetMemory = function forgetAndSay(...args) {
          window.__forgets.push(typeof args[0] === 'string' ? args[0] : typeof args[0]);
          forget(...args);
        };
        return state.wipes;
      });
      if (end === '404') {
        await detail.fulfill(site(404, { error: 'Not found.' }));
        await page.waitForFunction(() => window.__forgets.length > 0);
      }
      if (end === 'pagehide') await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })));
      const met = await page.evaluate(address => ({ forgets: window.__forgets.slice(), counted: state.wipes, loading: state.viewer?.view === address && state.viewer.mode === 'loading' }),
        viewOf(READY));
      await view.continue();
      await drawn(page);
      const kept = await page.evaluate(() => [...state.keptViews.keys()]);
      await page.evaluate(() => { location.hash = 'documents'; });
      await listed(page);
      // the re-open's answer as the page receives it: Chromium at times reports that request to the test as aborted
      // (net::ERR_ABORTED) although the page reads it whole and draws it, with no abort of the page's after the route away
      await page.evaluate(address => {
        window.__reopen = [];
        const fetched = window.fetch.bind(window);
        window.fetch = async (url, init) => {
          const answer = await fetched(url, init);
          if (url === address) window.__reopen.push([/^"[0-9a-f-]{36}"$/.test(init?.headers?.['If-None-Match'] || ''), answer.status]);
          return answer;
        };
      }, viewOf(READY));
      calls.length = 0;
      await openRow(page, READY);
      await settled(calls);
      const asked = calls.filter(call => call.url === viewOf(READY)).length;
      const again = await page.evaluate(() => window.__reopen);
      const ended = end === 'pagehide';
      assert.deepEqual({ ...met, counted: met.counted - counted, kept, asked, again },
        // pagehide reaches the page's own listener, the function boot bound, not the name wrapped here
        { forgets: end === '404' ? [viewOf(READY)] : [], counted: ended ? 1 : 0, loading: true, kept: ended ? [] : [viewOf(READY)],
          asked: 1, again: [ended ? [false, 200] : [true, 304]] },
        `${what}: ${ended ? 'an end met while it opened: counted, no copy kept, the re-open downloads' : 'the open keeps its copy, the re-open is a 304'}`);
      assert.deepEqual(errors.filter(error => !/^Failed to load resource/.test(error)), [], `${what}: no error in the page`);
    } finally {
      await context.close();
    }
  }
});

test('V12, R2-22: above 200 documents a key that leaves the search words unchanged asks nothing and keeps the results loaded; a failure is said under its own list alone', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 }, extraHTTPHeaders: { 'X-Preview-Encounters': '400' } });
  try {
    // the list's own later pages are refused; the search and its pages are answered
    await context.route(/\/api\/encounters\?list=documents&before=/, route => route.fulfill({ status: 503, contentType: 'application/json',
      body: JSON.stringify({ error: 'The service is not available right now.' }) }));
    const { page, calls, errors } = await open(context);
    await listed(page);
    assert.equal(await page.evaluate(() => Boolean(document.querySelector('#listMore'))), true, 'the list\'s end, watched');
    const rows = () => page.evaluate(() => document.querySelectorAll('#documentsTable .document-row').length);
    const more = () => page.evaluate(() => document.querySelector('#listMore')?.textContent || '');
    const toEnd = () => page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const searches = () => calls.filter(call => call.url === '/api/encounters/search').length;
    await toEnd();
    await page.waitForFunction(() => /could not be loaded/.test(document.querySelector('#listMore')?.textContent || ''));
    assert.match(await more(), /Documents could not be loaded\. The service is not available right now\./, 'the list\'s failed page, under the list');
    await page.fill('#documentSearch', 'synthetic');
    await page.waitForFunction(() => state.list?.found?.query === 'synthetic' && !state.list.searching);
    assert.doesNotMatch(await more(), /could not be loaded/, 'not under the search\'s answer');
    for (const expected of [100, 150, 200]) {
      await toEnd();
      await page.waitForFunction(count => document.querySelectorAll('#documentsTable .document-row').length === count && !state.list.loading, expected);
    }
    const asked = searches();
    await page.type('#documentSearch', ' ');  // a key that leaves the words unchanged
    await page.waitForTimeout(1000);
    assert.deepEqual([searches(), await rows()], [asked, 200], 'nothing asked again; the results loaded stay');
    await page.fill('#documentSearch', '');
    await page.waitForFunction(() => state.list && !state.list.found);
    assert.match(await more(), /Documents could not be loaded\. The service is not available right now\./, 'cleared: the list\'s own failure, said again');
    assert.deepEqual(errors.filter(error => !/Failed to load resource/.test(error)), [], 'no error in the page but the refused pages\' own');
  } finally {
    await context.close();
  }
});

test('V12b, R2-22: above 200 documents, the list\'s last page that comes while a search answer is shown puts the whole list on the page: narrower words ask nothing, and their match is shown', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 }, extraHTTPHeaders: { 'X-Preview-Encounters': '230' } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    assert.equal(await page.evaluate(() => Boolean(document.querySelector('#listMore'))), true, 'the list\'s end, watched');
    const toEnd = () => page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    for (const expected of [100, 150, 200]) {
      await toEnd();
      await page.waitForFunction(count => document.querySelectorAll('#documentsTable .document-row').length === count && !state.list.loading, expected);
    }
    // the list's last page, asked for by the button, held while a search answer is drawn
    let held = null;
    const pattern = /\/api\/encounters\?list=documents&before=/;
    await page.route(pattern, route => { held = route; });
    await page.click('[data-action="more-documents"]');
    for (let turn = 0; turn < 200 && !held; turn += 1) await page.waitForTimeout(25);
    assert.ok(held, 'the list\'s last page, asked for');
    await page.fill('#documentSearch', 'synthetic');
    await page.waitForFunction(() => state.list?.found?.query === 'synthetic' && !state.list.searching);
    await held.continue();
    await page.unroute(pattern);
    await page.waitForFunction(() => !state.list.loading && state.list.browse.next === null);
    // narrower words: one document of the last page, named by its title (each ends in its own number)
    const title = await page.evaluate(() => state.list.browse.rows.slice(200).find(row => /synthetic/i.test(row.title)).title);
    const searches = () => calls.filter(call => call.url === '/api/encounters/search').length;
    const asked = searches();
    await page.fill('#documentSearch', title);
    await page.waitForTimeout(1000);
    const left = await page.evaluate(words => ({
      rows: document.querySelectorAll('#documentsTable .document-row').length,
      shown: [...document.querySelectorAll('#documentsTable .document-row')].filter(row => !row.hidden).map(row => row.textContent.toLowerCase().includes(words.toLowerCase())),
      said: document.querySelector('#searchEmpty')?.textContent || null, found: Boolean(state.list.found) }), title);
    assert.deepEqual([searches() - asked, left.found, left.rows, left.shown, left.said], [0, false, 230, [true], null],
      'the whole list on the page: nothing asked, its match shown, never "No documents match your search."');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
});

test('V12c, R2-22: above 200 documents, the list\'s last page that comes under a search answer keeps what that answer, asked later, showed - a document made since the list\'s first page, a state changed since', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const added = { id: '5effffff-0000-4000-8000-0000000fffff', title: 'Synthetic discharge summary (new)', state: 'ready', state_label: 'Ready for approval',
    service_date: '2026-11-21', insurance: 'medicare', created_at: '2026-11-20T10:30:00Z', kind: 'upload', opens_pdf: false };
  const changed = body => ({ ...body, encounters: body.encounters.map(row => (/Riley \(6\)$/.test(row.title) ? { ...row, state: 'reviewed', state_label: 'Reviewed' } : row)) });
  for (const [what, words, change, rows, says] of [['a document made since', 'discharge summary', body => ({ ...body, encounters: [added, ...body.encounters] }), 231, 'Synthetic discharge summary (new)'],
    ['a state changed since', 'Riley (6)', changed, 230, 'Reviewed']]) {
    const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 }, extraHTTPHeaders: { 'X-Preview-Encounters': '230' } });
    try {
      // the search answered as the server answers once the practice changed after the list's first page
      await context.route(/\/api\/encounters\/search$/, async route => {
        const answer = await route.fetch();
        await route.fulfill({ status: answer.status(), contentType: 'application/json', body: JSON.stringify(change(await answer.json())) });
      });
      const { page, errors } = await open(context);
      await listed(page);
      assert.equal(await page.evaluate(() => Boolean(document.querySelector('#listMore'))), true, 'the list\'s end, watched');
      for (const expected of [100, 150, 200]) {
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForFunction(count => document.querySelectorAll('#documentsTable .document-row').length === count && !state.list.loading, expected);
      }
      let held = null;
      const pattern = /\/api\/encounters\?list=documents&before=/;
      await page.route(pattern, route => { held = route; });
      await page.click('[data-action="more-documents"]');  // the list's last page, held
      for (let turn = 0; turn < 200 && !held; turn += 1) await page.waitForTimeout(25);
      await page.fill('#documentSearch', words);
      await page.waitForFunction(typed => state.list?.found?.query === typed.toLowerCase() && !state.list.searching, words);
      const look = () => page.evaluate(() => {
        const visible = [...document.querySelectorAll('#documentsTable .document-row')].filter(row => !row.hidden);
        return { found: Boolean(state.list.found), rows: document.querySelectorAll('#documentsTable .document-row').length, shown: visible.length,
          text: visible[0]?.textContent || '', said: document.querySelector('#searchEmpty')?.textContent || null };
      });
      const atAnswer = await look();
      await held.continue();
      await page.unroute(pattern);
      await page.waitForFunction(() => !state.list.loading && state.list.browse.next === null);
      const after = await look();
      assert.deepEqual([atAnswer.shown, atAnswer.text.includes(says)], [1, true], `${what}: the answer shows it`);
      assert.deepEqual([after.found, after.rows, after.shown, after.text.includes(says), after.said], [false, rows, 1, true, null],
        `${what}: the whole list on the page keeps the answer's row as the answer showed it`);
      if (rows === 231) {  // cleared: the whole list newest first, a document only the answer holds first
        await page.fill('#documentSearch', '');
        assert.equal(await page.evaluate(() => document.querySelector('#documentsTable .document-row')?.getAttribute('href')),
          `#doc/${added.id}`, `${what}: cleared, the newer document first`);
      }
      assert.deepEqual(errors, [], `${what}: no error in the page`);
    } finally {
      await context.close();
    }
  }
});

// POST a control address of the preview (ops/dev_preview_server.cjs); its modes hold until the next reset.
async function previewControl(route) {
  const answer = await fetch(`${kit.base}/__preview__/${route}`, { method: 'POST' });
  assert.equal(answer.status, 204, route);
}

test('V13, I1-6: a view whose read cannot be recorded (503) is never answered with PDF bytes - the click\'s re-open with its kept tag, the page\'s download, nor the frame the viewer falls back to - and nothing is drawn', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, errors } = await open(context);
    await listed(page);
    await openRow(page, READY);  // drawn, and its copy kept for a re-open
    assert.equal(await page.evaluate(view => state.keptViews?.has(view), viewOf(READY)), true, 'a copy kept');
    await back(page);
    await previewControl('unrecorded');  // from here the view's read record cannot be written (studio/api.py original)
    const views = [];
    page.on('response', async response => {
      if (response.url() !== `${kit.base}${viewOf(READY)}`) return;
      const request = response.request();
      const answer = { status: response.status(), poll: request.headers()['x-cpt-poll'] || '', tag: request.headers()['if-none-match'] || '',
        frame: request.frame() !== page.mainFrame(), head: '' };
      views.push(answer);
      try {
        answer.head = (await response.body()).subarray(0, 5).toString('latin1');
      } catch {
        answer.head = '(no body)';
      }
    });
    await page.click(`a.document-row[href="#doc/${READY}"]`);
    // the page's own download is refused, so it falls back to the browser's own viewer in a frame, whose load is refused
    // too - or, on a server that answered it, the page draws: either ends the wait, and the assertions below say which
    await page.waitForFunction(() => (state.viewer?.mode === 'frame' && state.viewer.fallback === 'download')
      || Boolean(document.querySelector('#documentViewer .pdf-page canvas, #documentViewer .pdf-text span')));
    for (let turn = 0; turn < 200 && !views.some(view => view.frame); turn += 1) await page.waitForTimeout(25);
    await page.waitForTimeout(500);
    console.log(`V13 views ${JSON.stringify(views)}`);
    assert.ok(views.some(view => !view.frame && view.poll === '1' && view.tag), `the click's re-open, with its kept tag: ${JSON.stringify(views)}`);
    assert.ok(views.some(view => view.frame && !view.poll && !view.tag), `the frame's own plain load: ${JSON.stringify(views)}`);
    assert.deepEqual(views.filter(view => view.status !== 503 || view.head.startsWith('%PDF')), [],
      'every read of the view answered 503, none 200 or 304, no PDF byte');
    assert.deepEqual(await page.evaluate(view => ({ canvas: Boolean(document.querySelector('#documentViewer .pdf-page canvas')),
      text: Boolean(document.querySelector('#documentViewer .pdf-text span')), kept: state.keptViews.has(view) }), viewOf(READY)),
    { canvas: false, text: false, kept: false }, 'nothing drawn, the kept copy dropped');
    // the frame's refusal forbids framing (the site's headers), and the refused loads: the only errors in the page
    assert.deepEqual(errors.filter(error => !/^Framing '[^']*' violates the following Content Security Policy directive: "frame-ancestors 'none'"|^Failed to load resource/.test(error)), []);
  } finally {
    await previewControl('reset');
    await context.close();
  }
});

test('V14, I1-12: a Word document kept open while a later round converts it again draws that round\'s conversion - the read that brings it redraws the viewer whole and asks with the kept tag (200, the new bytes) under the converted note, and the round\'s quote of words only it has is marked; a read serving the same conversion asks nothing; a re-open is a 304 from the new copy', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const { RECONVERTED_LINE } = require('./dev_preview_server.cjs');
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    await openRow(page, WORD);  // round 1's conversion drawn, and its copy kept under its tag
    const drawnText = () => page.evaluate(() => [...document.querySelectorAll('#documentViewer .pdf-text')].map(layer => layer.textContent).join(' | '));
    assert.ok(!(await drawnText()).includes(RECONVERTED_LINE), 'round 1\'s conversion');
    const firstTag = await page.evaluate(view => state.keptViews.get(view)?.tag || '', viewOf(WORD));
    assert.match(firstTag, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/, 'a copy kept under its tag');
    await page.evaluate(() => { window.__roundOneViewer = state.viewer; });
    await previewControl('reconvert');  // another member's answers began round 2, which converts the Word file again
    calls.length = 0;
    // this page's decision on round 1 is refused (409: the coding review changed) and the page reads the document again
    await page.click('button[data-decision="reject"][data-line="L2"]');
    await page.click('#saveReview');
    await page.waitForFunction(() => state.doc?.round?.number === 2 && state.doc.progress?.busy === true);
    // round 2 has not stored its own conversion yet: the same conversion is served, so the viewer stays and asks nothing
    const roundOne = await page.evaluate(() => state.viewer === window.__roundOneViewer && state.doc.document.view_conversion);
    assert.match(String(roundOne), /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/, 'the same viewer, round 1\'s conversion named');
    assert.deepEqual(calls.filter(call => call.url === viewOf(WORD)), [], 'nothing asked of the view');
    // the poll that brings round 2's own conversion redraws the viewer whole: asked with the kept tag, answered 200
    await page.waitForFunction(line => [...document.querySelectorAll('#documentViewer .pdf-text')].some(layer => layer.textContent.includes(line)),
      RECONVERTED_LINE, { timeout: 30000 });
    const views = calls.filter(call => call.url === viewOf(WORD));
    await settled(views);
    assert.deepEqual(views.map(call => [call.condition, call.status, call.poll, call.body > 0]), [[`"${firstTag}"`, 200, '1', true]],
      'once, with round 1\'s tag, answered 200 with the new bytes, as the page\'s own read');
    const secondTag = await page.evaluate(view => state.keptViews.get(view)?.tag || '', viewOf(WORD));
    assert.ok(secondTag && secondTag !== firstTag, 'the new conversion kept under its own tag');
    const named = await page.evaluate(() => [state.viewer !== window.__roundOneViewer, state.doc.document.view_conversion,
      document.querySelector('.viewer-note')?.textContent.trim()]);
    assert.deepEqual([named[0], named[2]], [true, 'Shown as the PDF the coding review read (converted from the Word file).']);
    assert.ok(named[1] && named[1] !== roundOne, 'round 2\'s own conversion named');
    // round 2 finishes: its codes are drawn beside its own conversion, which is not asked for again
    await page.waitForFunction(() => state.doc?.progress?.phase === 'done' && state.doc.round.number === 2, null, { timeout: 30000 });
    await page.waitForTimeout(300);
    assert.equal(calls.filter(call => call.url === viewOf(WORD)).length, 1, 'the finished round serves the same conversion: nothing asked');
    await page.click(`button.quote:has-text("${RECONVERTED_LINE.slice(0, 30)}")`);
    await page.waitForFunction(() => document.querySelector('#documentViewer')?.dataset.markStatus === 'marked', null, { timeout: 15000 });
    assert.ok((await drawnText()).includes(RECONVERTED_LINE), 'round 2\'s conversion drawn, its quote marked in it');
    // a re-open: the new copy, asked with its tag, is answered 304 and drawn from page memory
    await back(page);
    calls.length = 0;
    await openRow(page, WORD);
    const reopened = calls.filter(call => call.url === viewOf(WORD));
    await settled(reopened);
    assert.deepEqual(reopened.map(call => [call.condition, call.status]), [[`"${secondTag}"`, 304]], 'a re-open: 304 from the new copy');
    assert.ok((await drawnText()).includes(RECONVERTED_LINE));
    // the refused decision (the coding review changed under the page) is the one error the browser notes
    assert.deepEqual(errors, ['Failed to load resource: the server responded with a status of 409 (Conflict)']);
  } finally {
    await previewControl('reset');
    await context.close();
  }
});

test('V15, I2-2: a Word document kept open, zoomed and scrolled, across a later round that reads back the same stored conversion (a clean Word file\'s answers round) keeps its viewer, its zoom and the member\'s place: nothing is asked of the view, as in release 1', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const { page, calls, errors } = await open(context);
    await listed(page);
    await openRow(page, WORD);
    // the member zooms in twice (150%) and scrolls the viewer to the second page
    for (let step = 0; step < 2; step += 1) await page.click('#viewerZoom [data-zoom="in"]');
    await page.waitForFunction(() => document.querySelector('#zoomLevel')?.textContent === '150%');
    await page.evaluate(() => {
      const viewer = document.querySelector('#documentViewer');
      viewer.scrollTop = viewer.scrollHeight - viewer.clientHeight;
    });
    await page.waitForFunction(() => document.querySelector('#viewerPage')?.textContent === 'Page 2 of 2');
    const place = () => page.evaluate(() => ({ zoom: document.querySelector('#zoomLevel')?.textContent, page: document.querySelector('#viewerPage')?.textContent,
      top: Math.round(document.querySelector('#documentViewer').scrollTop), conversion: state.doc.document.view_conversion }));
    const before = await place();
    assert.ok(before.top > 0, `scrolled: ${JSON.stringify(before)}`);
    await page.evaluate(() => { window.__keptViewer = state.viewer; });
    await previewControl('reread');  // another member's answers began round 2, which reads back round 1's stored conversion
    calls.length = 0;
    // this page's decision on round 1 is refused (409: the coding review changed) and the page reads the document again
    await page.click('button[data-decision="reject"][data-line="L2"]');
    await page.click('#saveReview');
    await page.waitForFunction(() => state.doc?.round?.number === 2 && state.doc.progress?.busy === true);
    // round 2 runs (reading, checking) and finishes: every read names the same conversion
    await page.waitForFunction(() => state.doc?.progress?.phase === 'done' && state.doc.round.number === 2, null, { timeout: 30000 });
    await page.waitForTimeout(300);
    const reads = calls.filter(call => call.url === `/api/encounters/${WORD}`);
    assert.ok(reads.length >= 3, `the round was read as it ran: ${reads.length} reads`);
    assert.deepEqual(calls.filter(call => call.url === viewOf(WORD)).map(call => call.url), [], 'nothing asked of the view');
    assert.equal(await page.evaluate(() => state.viewer === window.__keptViewer), true, 'the same viewer');
    assert.deepEqual(await place(), before, 'its zoom, its page and the member\'s place, and the same conversion named');
    // the refused decision (the coding review changed under the page) is the one error the browser notes
    assert.deepEqual(errors, ['Failed to load resource: the server responded with a status of 409 (Conflict)']);
  } finally {
    await previewControl('reset');
    await context.close();
  }
});

test('V16, I2-1: a Word document opened again while a later round stores its own conversion draws that conversion - the click\'s view read before the round stored it (a 304 of the kept copy) and the detail after, or the detail first and the view after - asking again until the bytes are the conversion the detail names; its quote is marked', { skip: SKIP, timeout: LIMIT_MS }, async () => {
  const { RECONVERTED_LINE } = require('./dev_preview_server.cjs');
  for (const order of ['the view first', 'the detail first']) {
    const context = await kit.browser.newContext({ viewport: { width: 1440, height: 900 } });
    try {
      const { page, calls, errors } = await open(context);
      await listed(page);
      await openRow(page, WORD);  // round 1's conversion drawn, its copy kept under its tag
      const firstTag = await page.evaluate(view => state.keptViews.get(view)?.tag || '', viewOf(WORD));
      assert.match(firstTag, /^[0-9a-f-]{36}$/, `${order}: a copy kept`);
      await back(page);
      await previewControl('reconvert');  // another member's answers began round 2, which converts the file again
      const detailUrl = `${kit.base}/api/encounters/${WORD}`;
      let held = false;
      const answered = { view: null, detail: null };
      const seen = { view: new Promise(resolve => { answered.view = resolve; }), detail: new Promise(resolve => { answered.detail = resolve; }) };
      page.on('response', response => {
        if (response.url() === `${kit.base}${viewOf(WORD)}`) answered.view();
        if (response.url() === detailUrl) answered.detail();
      });
      if (order === 'the view first') {
        // the round has been read once (reading): the click's view is read while round 1's conversion is still served,
        // and the detail - held in the browser until that view's answer came - is read once the round stored its own
        assert.equal((await fetch(detailUrl)).status, 200);
        await page.route(url => url.href === detailUrl, async route => {
          if (!held) {
            held = true;
            await seen.view;
          }
          await route.continue();
        });
      } else {
        // the detail is read first (round 1's conversion still served); the round stores its own; then the click's view
        await page.route(url => url.href === `${kit.base}${viewOf(WORD)}`, async route => {
          if (!held) {
            held = true;
            await seen.detail;
            assert.equal((await fetch(detailUrl)).status, 200);  // the round's next read: its own conversion stored
          }
          await route.continue();
        });
      }
      calls.length = 0;
      await page.click(`a.document-row[href="#doc/${WORD}"]`);
      await page.waitForFunction(line => [...document.querySelectorAll('#documentViewer .pdf-text')].some(layer => layer.textContent.includes(line)),
        RECONVERTED_LINE, { timeout: 30000 });
      const views = calls.filter(call => call.url === viewOf(WORD));
      await settled(views);
      console.log(`V16 ${order} ${JSON.stringify(views.map(call => [call.condition, call.status, call.body > 0]))}`);
      const first = views[0];
      assert.deepEqual([first.condition, first.status], order === 'the view first' ? [`"${firstTag}"`, 304] : [`"${firstTag}"`, 200],
        `${order}: the click's view, with the kept tag`);
      assert.ok(views.slice(1).every(call => call.status === 200 && call.body > 0), `${order}: asked again, the new bytes`);
      const shown = await page.evaluate(view => ({ conversion: state.doc.document.view_conversion, viewer: state.viewer?.conversion,
        kept: state.keptViews.get(view)?.tag || '' }), viewOf(WORD));
      assert.equal(shown.viewer, shown.conversion, `${order}: the viewer draws the conversion the detail names`);
      assert.ok(shown.kept && shown.kept !== firstTag, `${order}: the new conversion kept under its own tag`);
      // round 2 finishes: its quote of words only its conversion has is marked in it
      await page.waitForFunction(() => state.doc?.progress?.phase === 'done' && state.doc.round.number === 2, null, { timeout: 30000 });
      await page.click(`button.quote:has-text("${RECONVERTED_LINE.slice(0, 30)}")`);
      await page.waitForFunction(() => document.querySelector('#documentViewer')?.dataset.markStatus === 'marked', null, { timeout: 15000 });
      assert.deepEqual(errors, [], `${order}: no error in the page`);
    } finally {
      await previewControl('reset');
      await context.close();
    }
  }
});
