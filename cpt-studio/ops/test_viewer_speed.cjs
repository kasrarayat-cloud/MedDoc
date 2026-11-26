'use strict';
/*
 * The viewer's speed (release 2: RELEASE-2-SPEC R2-10 to R2-18), through the shipped page in Chromium, against
 * ops/dev_preview_server.cjs's mock: what a page load and an opening ask the server for, what fades, the worker made ready
 * ahead, the re-open answered 304 and drawn from page memory, the view asked for with the click, and what is left after
 * another tab's sign-out. Five tests; release 1's page fails all five. Skipped where Playwright is not installed
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
    else Object.assign(call, { status: (await request.response())?.status(), body: (await request.sizes()).responseBodySize });
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

test('V2, V3: an opening asks for the document and its view alone; a re-open is answered 304 with no body and draws the same pixels', { skip: SKIP, timeout: LIMIT_MS }, async () => {
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
    await back(page);
    calls.length = 0;
    await openRow(page, READY);
    await settled(calls);
    const again = calls.filter(call => call.url === viewOf(READY));
    assert.equal(again.length, 1, 'the view asked for once: one record');
    assert.match(again[0].condition, /^"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"$/, 'with the tag the page holds');
    assert.deepEqual([again[0].status, again[0].body, again[0].poll], [304, 0, '1'], 'answered 304, no body, as the page\'s own read');
    assert.deepEqual(api(), [[`/api/encounters/${READY}`, 200], [viewOf(READY), 304]].sort());
    assert.equal(await pixels(page), first, 'the same pixels, drawn from page memory');
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
