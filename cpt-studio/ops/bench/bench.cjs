// The bench's browser (RELEASE-2-SPEC R2-2, R2-32): real clicks in headless Chromium against a tree's own page, served by
// that tree's gunicorn through proxy.cjs on 127.0.0.1, over the bench's synthetic data. Run by bench_run.py:
//
//   node bench.cjs --flow <open|lists|office|records|left-behind|correct> --profile <P0..P3> --base <proxy url>
//       --control <proxy control port> --act <act port> --docs <docs.json> --password-file <file> --out <file>
//       [--playwright <path>] [--contexts 3] [--size n100]
//
// What it times, each from the click's (or the key's) own event timeStamp:
// - "first page": page 1's canvas is attached AND its marker pixel is dark (a PDF without the marker never counts);
//   the 12-bit barcode on page 1 is then read at fit width, at each square's centre, with its parity;
// - "opaque": the new view's section has computed opacity >= 0.99 with its content present (the review column, or rows);
// - "usable": the rows are painted and the last long task has ended;
// - "text": the first text-layer span; "frame": an in-page frame (a text document) holds its text.
// Counts come from the proxy's log - the server side - never from CDP, which counts cached scripts. No route() is used
// (it turns the HTTP cache off). Every host but 127.0.0.1 is unresolvable, and a blocked request fails the run. It
// prints no password and writes no document byte anywhere.
'use strict';
const fs = require('fs');
const http = require('http');
const crypto = require('crypto');

const arg = (name, fallback) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : fallback; };
// Set by setup() when run as a program; a test that requires this file reads only the pure helpers it exports.
let FLOW, PROFILE, BASE, CONTROL, ACT, OUT, CONTEXTS, SIZE, DATA, PASSWORD, DOC, chromium, INIT, result;
function setup() {
  FLOW = arg('flow', 'open'); PROFILE = arg('profile', 'P0'); BASE = arg('base');
  CONTROL = Number(arg('control')); ACT = Number(arg('act')); OUT = arg('out');
  CONTEXTS = Number(arg('contexts', '3')); SIZE = arg('size', 'n100');
  if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(BASE || '')) throw new Error('bench.cjs: the base must be loopback');
  DATA = JSON.parse(fs.readFileSync(arg('docs'), 'utf8'));
  PASSWORD = fs.readFileSync(arg('password-file'), 'utf8').trim();
  DOC = Object.fromEntries(DATA.docs.map(d => [d.label, d]));
  ({ chromium } = require(arg('playwright', '/opt/meddoc-pro/node_modules/playwright')));
  INIT = INIT_FOR(DATA.geometry);
  result = { flow: FLOW, profile: PROFILE, size: SIZE, chromium: null, metrics: {}, checks: {}, controls: {}, actions: [],
    errors: [], blocked: [], consoleErrors: [], pageErrors: [], unfinished: [] };
}
const TEXT_PDFS = ['text-2p', 'text-4p', 'text-10p'];
const THROTTLE = { P1: { cpu: 4, latency: 40, down: 10 * 1024 * 1024 / 8, up: 5 * 1024 * 1024 / 8 }, P2: { cpu: 1, latency: 200, down: -1, up: -1 } };
const SETTLE_MS = 400;

const metric = (name, value) => { if (value === null || value === undefined || Number.isNaN(value)) return; (result.metrics[name] = result.metrics[name] || []).push(value); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function call(port, method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = http.request({ host: '127.0.0.1', port, method, path, headers: { 'content-type': 'application/json', ...(data ? { 'content-length': data.length } : {}) }, timeout: 60000 }, res => {
      const chunks = []; res.on('data', c => chunks.push(c)); res.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}')); } catch (e) { reject(e); } });
    });
    req.on('error', reject); req.on('timeout', () => req.destroy(new Error('timeout')));
    if (data) req.write(data); req.end();
  });
}
const proxyLog = async since => (await call(CONTROL, 'GET', `/log?since=${since}`)).entries;
const proxySeq = async () => (await call(CONTROL, 'GET', '/state')).seq;
const proxyRule = rule => call(CONTROL, 'POST', '/rule', rule);
const act = async (name, args = {}) => { const answer = await call(ACT, 'POST', '/act', { name, ...args }); if (!answer.ok) throw new Error(`act ${name}: ${answer.error}`); return answer; };
const isStatic = url => url.startsWith('/static/');
const LIBRARY = /pdf(\.worker)?\.min\.([0-9a-f]{12}\.)?mjs/;  // the library's two files, hashed or not
const shape = url => url.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, '<id>').replace(/\.[0-9a-f]{12}\./, '.').replace(/before=[^&]+/, 'before=<cursor>');

// The barcode's 15 read squares (1 = dark) to its number, or null: start and stop squares dark, even parity over the 12
// bits and the parity square (benchdata.py's barcode_bits is the writer). Inlined into the page's probe, exported for tests.
function decodeSquares(bits, nbits) {
  if (!Array.isArray(bits) || bits.length !== nbits + 3 || bits.some(b => b !== 0 && b !== 1)) return null;
  const data = bits.slice(1, 1 + nbits);
  if (bits[0] !== 1 || bits[bits.length - 1] !== 1 || data.reduce((a, b) => a + b, 0) % 2 !== bits[1 + nbits]) return null;
  return data.reduce((a, b) => a * 2 + b, 0) || null;
}
function encodeForTest(number) {  // the writer's rule, for the test that checks the two agree
  const data = Array.from({ length: 12 }, (_, i) => (number >> (11 - i)) & 1);
  return [1, ...data, data.reduce((a, b) => a + b, 0) % 2, 1];
}

// --- the probe, in every page ----------------------------------------------------------------------------------------------
const INIT_FOR = geometry => `(() => {
  if (window.top !== window) return;
  const G = ${JSON.stringify(geometry)};
  const decodeSquares = ${decodeSquares.toString()};
  const P = window.__bench = { cur: null, lt: [], ev: [], anim: [], workers: [] };
  const NativeWorker = window.Worker;
  if (NativeWorker) window.Worker = class extends NativeWorker {
    constructor(url, opts) { super(url, opts); const rec = { t: performance.now(), url: new URL(String(url), location.href).pathname, ready: null, gone: null }; P.workers.push(rec);
      this.addEventListener('message', e => { const d = e.data; if (rec.ready === null && d && d.action === 'ready') rec.ready = performance.now(); });
      const term = this.terminate.bind(this); this.terminate = () => { if (rec.gone === null) rec.gone = performance.now(); return term(); }; }
  };
  try { new PerformanceObserver(l => { for (const e of l.getEntries()) P.lt.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
  try { new PerformanceObserver(l => { for (const e of l.getEntries()) P.ev.push([e.name, e.startTime, e.duration, e.interactionId || 0]); }).observe({ type: 'event', durationThreshold: 16, buffered: true }); } catch (e) {}
  document.addEventListener('animationstart', e => { P.anim.push([e.animationName, performance.now()]); }, true);
  const sample = (canvas, fx, fy) => { const x = Math.min(canvas.width - 2, Math.max(1, Math.round(canvas.width * fx))); const y = Math.min(canvas.height - 2, Math.max(1, Math.round(canvas.height * fy)));
    const d = canvas.getContext('2d').getImageData(x - 1, y - 1, 3, 3).data; let s = 0; for (let i = 0; i < d.length; i += 4) s += (d[i] + d[i + 1] + d[i + 2]) / 3; return s / 9; };
  const dark = canvas => { try { return sample(canvas, G.marker[0], G.marker[1]) < 100; } catch (e) { return false; } };
  const barcode = canvas => { try { const bits = G.squares.map(([x, y]) => (sample(canvas, x, y) < 128 ? 1 : 0));
      return { bits: bits.join(''), number: decodeSquares(bits, G.bits) }; } catch (e) { return { bits: '', number: null }; } };
  const visible = () => { const rows = [...document.querySelectorAll('#documentsTable .document-row')].filter(r => !r.hidden && r.offsetParent !== null); return rows.length + '|' + (rows[0] ? rows[0].getAttribute('href') : '') + '|' + (rows.length ? rows[rows.length - 1].getAttribute('href') : ''); };
  P.visible = visible;
  const routed = () => { if (P.firstRoute === undefined && document.querySelector('#main > section')) P.firstRoute = performance.now(); };
  const look = () => {
    const c = P.cur; if (!c || c.stop || c.t0 === null) return; const now = performance.now();
    if (c.kind === 'search') { const sig = visible(); if (sig !== c.sig) { c.sig = sig; const at = [now, sig, null]; c.sigs.push(at);
      requestAnimationFrame(() => setTimeout(() => { at[2] = performance.now(); }, 0)); } return; }
    const sec = document.querySelector('#main > section');
    if (sec && c.sec0 === sec) return;
    if (!c.column && document.getElementById('reviewColumn')) c.column = now;
    const rows = document.querySelectorAll('#documentsTable .document-row');
    if (!c.rows && rows.length) { c.rows = now; c.rowCount = rows.length; }
    const v = document.getElementById('documentViewer');
    if (v && v.dataset.mode && !c.mode) { c.mode = v.dataset.mode; c.modeAt = now; }
    if (v && v.dataset.fallback && !c.fallback) { c.fallback = v.dataset.fallback; c.fallbackAt = now; }
    if (!c.canvas) { const cv = document.querySelector('.pdf-page[data-page="1"] canvas'); if (cv && cv.width > 0) { if (!c.attached) c.attached = now; if (dark(cv)) { c.canvas = now; c.canvasEpoch = performance.timeOrigin + now; c.barcode = barcode(cv); } } }
    if (!c.text && document.querySelector('.pdf-text span')) c.text = now;
    if (!c.frame && v && v.tagName === 'IFRAME') { try { const d = v.contentDocument; if (d && d.readyState === 'complete' && d.body && d.body.textContent.length > 20) c.frame = now; } catch (e) {} }
    if (sec && c.opaque === undefined) { const ready = c.kind === 'doc' ? Boolean(document.getElementById('reviewColumn')) : c.kind === 'list' ? rows.length > 0 : true;
      if (ready && parseFloat(getComputedStyle(sec).opacity) >= 0.99) c.opaque = now; }
  };
  const loop = () => { routed(); look(); requestAnimationFrame(loop); }; requestAnimationFrame(loop);
  const mo = new MutationObserver(() => { routed(); look(); });
  document.addEventListener('DOMContentLoaded', () => mo.observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-mode', 'data-fallback', 'hidden'] }));
  const start = e => { const c = P.cur; if (c && c.t0 === null && (c.kind !== 'search' || e.type === 'keydown')) { c.t0 = e.timeStamp; c.t0Epoch = performance.timeOrigin + e.timeStamp; } };
  document.addEventListener('click', start, true); document.addEventListener('keydown', start, true);
})();`;

const READ = () => { const P = window.__bench; const c = P.cur; c.stop = true; const end = performance.now(); const rel = v => (v ? Math.round((v - c.t0) * 10) / 10 : null);
  const lt = P.lt.filter(([s]) => s >= c.t0 - 1 && s <= end);
  return { t0Epoch: c.t0Epoch, column: rel(c.column), rows: rel(c.rows), rowCount: c.rowCount || 0, opaque: rel(c.opaque), attached: rel(c.attached), firstPage: rel(c.canvas), canvasEpoch: c.canvasEpoch || null,
    barcode: c.barcode || null, text: rel(c.text), frame: rel(c.frame), mode: c.mode || null, fallback: c.fallback || null, fallbackAt: rel(c.fallbackAt),
    longTasks: { n: lt.length, total: Math.round(lt.reduce((a, [, d]) => a + d, 0)), max: Math.round(Math.max(0, ...lt.map(([, d]) => d))) },
    lastTaskEnd: lt.length ? Math.round(Math.max(...lt.map(([s, d]) => s + d)) - c.t0) : 0,
    enter: P.anim.filter(([name, t]) => name === 'enter' && t >= c.t0 - 1).length,
    workersMade: P.workers.filter(w => w.t >= c.t0 - 1).length, workersAlive: P.workers.filter(w => w.gone === null).length,
    rowsNow: document.querySelectorAll('#documentsTable .document-row').length }; };

// --- contexts, sign-in, settling -------------------------------------------------------------------------------------------
let browser;
async function newContext(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, ...options });
  await context.addInitScript(INIT);
  const page = await context.newPage();
  page.on('console', m => { if (m.type() === 'error') result.consoleErrors.push(`${FLOW}/${PROFILE}: ${m.text().slice(0, 200)}`); });
  page.on('pageerror', e => result.pageErrors.push(`${FLOW}/${PROFILE}: ${String(e).slice(0, 200)}`));
  page.on('requestfailed', r => { const url = r.url(); if (!url.startsWith(BASE) && !url.startsWith('data:') && !url.startsWith('blob:')) result.blocked.push(url.slice(0, 120)); });
  const cdp = await context.newCDPSession(page);
  return { context, page, cdp };
}

async function throttle(cdp, on) {
  const t = THROTTLE[PROFILE];
  if (!t) return;
  await cdp.send('Network.enable');
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: on ? t.cpu : 1 });
  await cdp.send('Network.emulateNetworkConditions', on ? { offline: false, latency: t.latency, downloadThroughput: t.down, uploadThroughput: t.up } : { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
}

async function signIn(s, user, { count = false } = {}) {
  const { page, cdp } = s;
  await page.goto(`${BASE}/login/`);
  await page.fill('input[name=username]', user); await page.fill('input[name=password]', PASSWORD);
  await throttle(cdp, true);
  const seq = await proxySeq();
  const clicked = Date.now();
  await Promise.all([page.waitForURL(`${BASE}/`, { timeout: 120000 }), page.click('button[type=submit]')]);
  await page.waitForSelector('#documentsTable .document-row', { timeout: 180000 });
  s.loadedAt = Date.now();
  if (count) {
    await sleep(Math.max(0, clicked + 2600 - Date.now()));
    const entries = (await proxyLog(seq)).filter(e => e.t0 <= clicked + 2000);
    const shell = entries.find(e => e.method === 'GET' && e.url === '/');
    const afterRoute = await page.evaluate(() => { const P = window.__bench;
      const lib = performance.getEntriesByType('resource').filter(e => /pdf(\.worker)?\.min\./.test(e.name));
      return lib.length && P.firstRoute !== undefined ? Math.round(Math.min(...lib.map(e => e.startTime)) - P.firstRoute) : null; });
    return { requests: entries.length, list: entries.map(e => `${e.method} ${shape(e.url)} ${e.status}`), libraryAfterRouteMs: afterRoute,
      shellAt: shell ? shell.tEnd : null };
  }
  return null;
}

async function settle(page, quiet = SETTLE_MS, limit = 120000) {
  await page.evaluate(async ([q, max]) => { const P = window.__bench; const begin = performance.now();
    for (;;) { const last = P.lt.length ? P.lt[P.lt.length - 1][0] + P.lt[P.lt.length - 1][1] : 0; const now = performance.now();
      if (now - Math.max(last, begin) > q || now - begin > max) return; await new Promise(r => setTimeout(r, 50)); } }, [quiet, limit]);
}

async function arm(page, kind) { await page.evaluate(k => { window.__bench.cur = { kind: k, t0: null, sec0: document.querySelector('#main > section'), sigs: [], sig: null }; }, kind); }

async function windowEntries(seq, until) { return (await proxyLog(seq)).filter(e => e.t0 <= until); }

function summarize(entries) {
  return entries.map(e => [e.method, shape(e.url), e.status, e.bytes]);
}

// One document opened from the list by a real click on its row. `waitFor`: 'page' (the marker), 'frame', 'attached'.
async function openDoc(s, label, kind, { waitFor = null, limit = 90000 } = {}) {
  const { page } = s; const doc = DOC[label];
  const row = page.locator(`a.document-row[href="#doc/${doc.id}"]`);
  if (!(await row.count())) {  // not on this view (the Overview shows five): go to Documents first
    const seen = await page.evaluate(() => ({ url: location.hash, rows: document.querySelectorAll('#documentsTable .document-row').length,
      dialog: Boolean(document.querySelector('dialog[open]')) }));
    result.actions.push({ kind: 'row-missing', label, ...seen });
    await tab(s, 'documents', 'to-documents');
  }
  const seq = await proxySeq();
  await arm(page, 'doc');
  await row.first().click();
  const want = waitFor || (doc.kind === 'text' ? 'frame' : 'page');
  try {
    await page.waitForFunction(w => { const c = window.__bench.cur; if (c.t0 === null || !c.column) return false;
      return w === 'frame' ? Boolean(c.frame) : w === 'attached' ? Boolean(c.attached) : Boolean(c.canvas || c.mode === 'frame' || c.fallback); }, want, { timeout: limit, polling: 50 });
  } catch (e) { result.unfinished.push(`${PROFILE} ${kind} ${label}`); }
  if (want === 'attached') await sleep(2500);
  await settle(page); await sleep(SETTLE_MS);
  const m = await page.evaluate(READ);
  const entries = await windowEntries(seq, Date.now());
  const sample = { kind, label, number: doc.number, ...m, requests: summarize(entries), rids: entries.filter(e => !isStatic(e.url)).map(e => [e.method, shape(e.url), e.status, e.reqHeaders['x-request-id'], e.bytes]) };
  result.actions.push(sample);
  return sample;
}

async function back(s) {
  const { page } = s;
  const seq = await proxySeq();
  await arm(page, 'list');
  await page.locator('a.back-link').first().click();
  await page.waitForFunction(() => { const c = window.__bench.cur; return c.t0 !== null && c.rows && c.opaque !== undefined; }, null, { timeout: 180000, polling: 50 });
  await settle(page);
  const m = await page.evaluate(READ);
  result.actions.push({ kind: 'back', ...m, requests: summarize(await windowEntries(seq, Date.now())) });
  if (FLOW === 'open') metric(`open.tab.opaque.${PROFILE}`, m.opaque);  // a return to the 100-row list is a tab change
  return m;
}

async function tab(s, nav, kind, { limit = 180000 } = {}) {
  const { page } = s;
  const seq = await proxySeq();
  await arm(page, 'list');
  await page.locator(`[data-nav="${nav}"]`).first().click();
  try {
    await page.waitForFunction(() => { const c = window.__bench.cur; return c.t0 !== null && c.rows && c.opaque !== undefined; }, null, { timeout: limit, polling: 50 });
  } catch (e) { result.unfinished.push(`${PROFILE} ${kind} ${nav}`); await page.evaluate(() => { window.__bench.cur.stop = true; }); return null; }
  await settle(page, SETTLE_MS, limit);
  const m = await page.evaluate(READ);
  const entries = await windowEntries(seq, Date.now());
  // usable: the rows painted, the last long task ended and the view opaque (how section 8's A column was measured: at
  // 100 documents release 1's Documents is usable when its 350 ms fade ends, at 18,000 when its long tasks end)
  const usable = m.rows === null || m.opaque === null ? null : Math.max(m.rows, m.lastTaskEnd, m.opaque);
  const sample = { kind, nav, ...m, usable, requests: summarize(entries) };
  result.actions.push(sample);
  return sample;
}

// Heap snapshot: the sizes of every array buffer's backing store, and whether any string holds one of `markers`.
async function heap(cdp, markers = []) {
  const chunks = []; const on = e => chunks.push(e.chunk);
  cdp.on('HeapProfiler.addHeapSnapshotChunk', on);
  await cdp.send('HeapProfiler.enable'); await cdp.send('HeapProfiler.collectGarbage');
  await cdp.send('HeapProfiler.takeHeapSnapshot', { reportProgress: false });
  cdp.off('HeapProfiler.addHeapSnapshotChunk', on);
  const snap = JSON.parse(chunks.join(''));
  const fields = snap.snapshot.meta.node_fields; const ni = fields.indexOf('name'); const si = fields.indexOf('self_size');
  const sizes = [];
  for (let i = 0; i < snap.nodes.length; i += fields.length) { if (/JSArrayBufferData/.test(snap.strings[snap.nodes[i + ni]])) sizes.push(snap.nodes[i + si]); }
  return { sizes, markers: Object.fromEntries(markers.map(m => [m, snap.strings.some(x => x.includes(m))])) };
}

async function renderer(context) {
  const b = await context.browser().newBrowserCDPSession();
  const info = await b.send('SystemInfo.getProcessInfo');
  await b.detach();
  const sizes = info.processInfo.filter(p => p.type === 'renderer').map(p => {
    let priv = 0, rss = 0;
    try { for (const line of fs.readFileSync(`/proc/${p.id}/smaps_rollup`, 'utf8').split('\n')) { const m = /^(Private_Clean|Private_Dirty|Rss):\s+(\d+) kB/.exec(line); if (m) { if (m[1] === 'Rss') rss = Number(m[2]); else priv += Number(m[2]); } } } catch (e) {}
    return { pid: p.id, privateMb: Math.round(priv / 102.4) / 10, rssMb: Math.round(rss / 102.4) / 10 };
  });
  return sizes.sort((a, b2) => b2.privateMb - a.privateMb)[0] || null;
}

async function workerTargets(context) {
  const b = await context.browser().newBrowserCDPSession();
  const targets = (await b.send('Target.getTargets')).targetInfos.filter(t => t.type === 'worker');
  await b.detach();
  return targets.length;
}

function inflightMax(entries, member) {
  const mine = entries.filter(e => e.member === member && !isStatic(e.url)).flatMap(e => [[e.t0, 1], [e.tEnd, -1]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  let now = 0, max = 0; for (const [, d] of mine) { now += d; max = Math.max(max, now); } return max;
}

// --- flows -------------------------------------------------------------------------------------------------------------------

async function flowOpen() {
  for (let k = 0; k < CONTEXTS; k += 1) {
    const s = await newContext();
    try {
      const seq0 = await proxySeq();
      const signin = await signIn(s, DATA.users[SIZE], { count: true });
      metric(`open.signin.requests_2s.${PROFILE}`, signin.requests);
      result.actions.push({ kind: 'signin', ...signin });
      const standby = (await proxyLog(seq0)).filter(e => LIBRARY.test(e.url));
      metric(`open.standby.requests_before_open.${PROFILE}`, standby.length);
      const route = await s.page.evaluate(() => { const P = window.__bench;
        const lib = performance.getEntriesByType('resource').filter(e => /pdf(\.worker)?\.min\./.test(e.name) && e.transferSize > 0);
        return lib.length && P.firstRoute !== undefined ? Math.round(Math.min(...lib.map(e => e.startTime)) - P.firstRoute) : null; });
      if (route !== null) metric(`open.standby.after_route_ms.${PROFILE}`, route);
      await sleep(Math.max(0, s.loadedAt + 2000 - Date.now()) + 300);
      await settle(s.page, 600);
      const order = [0, 1, 2].map(i => TEXT_PDFS[(i + k) % 3]);
      const first = await openDoc(s, order[0], 'first');
      metric(`open.first.first_page.${PROFILE}`, first.firstPage);
      metric(`open.first.opaque.${PROFILE}`, first.opaque);
      metric(`open.requests.first.${PROFILE}`, first.requests.length);
      await back(s);
      for (const label of order.slice(1)) {
        const later = await openDoc(s, label, 'later');
        metric(`open.later.first_page.${PROFILE}`, later.firstPage);
        metric(`open.later.opaque.${PROFILE}`, later.opaque);
        metric(`open.later.long_tasks_total.${PROFILE}`, later.longTasks.total);
        metric(`open.later.long_tasks_max.${PROFILE}`, later.longTasks.max);
        metric(`open.requests.later.${PROFILE}`, later.requests.length);
        metric(`open.enter.per_open.${PROFILE}`, later.enter);
        await back(s);
      }
      const scan3 = await openDoc(s, 'scan-3p', 'scan3');
      metric(`open.scan3.first_page.${PROFILE}`, scan3.firstPage);
      await back(s);
      if (PROFILE === 'P0' || (PROFILE === 'P1' && k === 0)) {
        const scan20 = await openDoc(s, 'scan-20p', 'scan20');
        metric(`open.scan20.first_page.${PROFILE}`, scan20.firstPage);
        await back(s);
        if (PROFILE === 'P1') {
          const again = await openDoc(s, 'scan-20p', 'reopen-scan20');
          metric(`open.reopen_scan20.first_page.${PROFILE}`, again.firstPage);
          metric(`open.reopen_scan20.view_body_bytes.${PROFILE}`, again.requests.filter(r => /original\?view=1/.test(r[1])).reduce((a, r) => a + r[3], 0));
          await back(s);
        }
      }
      const word = await openDoc(s, 'word-3p', 'word');
      metric(`open.word.first_page.${PROFILE}`, word.firstPage);
      await back(s);
      const text = await openDoc(s, 'text-note', 'text');
      metric(`open.text.frame.${PROFILE}`, text.frame);
      metric(`open.requests.text.${PROFILE}`, text.requests.length);
      await back(s);
      for (const label of order.slice(1)) {
        const re = await openDoc(s, label, 'reopen');
        metric(`open.reopen.first_page.${PROFILE}`, re.firstPage);
        metric(`open.requests.reopen.${PROFILE}`, re.requests.length);
        metric(`open.reopen.view_body_bytes.${PROFILE}`, re.requests.filter(r => /original\?view=1/.test(r[1])).reduce((a, r) => a + r[3], 0));
        metric(`open.reopen.view_304.${PROFILE}`, re.requests.filter(r => /original\?view=1/.test(r[1]) && r[2] === 304).length);
        await back(s);
      }
      await openDoc(s, order[1], 'for-quote');
      for (const at of [0, 3]) {
        await s.page.evaluate(() => { window.__bench.cur = { kind: 'x', t0: null, sigs: [] }; });
        await s.page.locator('#quotesPanel button.quote').nth(at).click();
        await s.page.waitForFunction(() => { const v = document.getElementById('documentViewer'); return v && v.dataset.markStatus; }, null, { timeout: 30000, polling: 'raf' });
        const t = await s.page.evaluate(() => Math.round(performance.now() - window.__bench.cur.t0));
        metric(`open.quote_mark.${PROFILE}`, t);
        await sleep(300);
      }
      await back(s);
      for (const [nav, label] of [['queue', 'tab-queue'], ['workspace', 'tab-overview'], ['documents', 'tab-documents']]) {
        const t = await tab(s, nav, label);
        if (!t) continue;
        metric(`open.tab.opaque.${PROFILE}`, t.opaque);
        metric(`open.requests.tab.${PROFILE}`, t.requests.length);
        metric(`open.enter.per_tab.${PROFILE}`, t.enter);
      }
      const all = await proxyLog(seq0);
      const member = (all.find(e => e.member) || {}).member;
      metric(`open.inflight.max.${PROFILE}`, inflightMax(all, member));
    } catch (e) { result.errors.push(`open ${PROFILE} context ${k}: ${String(e && e.stack || e).slice(0, 600)}`); }
    finally { await s.context.close(); }
  }
  if (PROFILE === 'P0') { await flowControls(); await flowQuickLeave(); await flowMemory(); await flowFirstView(); }
}

// The approved fade on a page load's first view: animations started from the sign-in click to the first rows, then none.
async function flowFirstView() {
  const s = await newContext();
  try {
    await s.page.goto(`${BASE}/login/`);
    await s.page.fill('input[name=username]', DATA.users[SIZE]); await s.page.fill('input[name=password]', PASSWORD);
    await Promise.all([s.page.waitForURL(`${BASE}/`), s.page.click('button[type=submit]')]);
    await s.page.waitForSelector('#documentsTable .document-row'); await sleep(1200);
    metric(`open.enter.first_view.${PROFILE}`, await s.page.evaluate(() => window.__bench.anim.filter(([n]) => n === 'enter').length));
  } catch (e) { result.errors.push(`first view: ${String(e).slice(0, 300)}`); }
  finally { await s.context.close(); }
}

// The round's controls (P0). A missing or failed one makes the round INVALID (bench_run, judge.py).
async function flowControls() {
  const s = await newContext();
  try {
    await signIn(s, DATA.users[SIZE]);
    await sleep(2000);
    await openDoc(s, 'text-2p', 'control-warm'); await back(s);
    // (1) a PDF without the marker never counts as drawn
    const none = await openDoc(s, 'control-nomarker', 'control-nomarker', { waitFor: 'attached', limit: 30000 });
    result.controls.nomarker = { ok: none.attached !== null && none.firstPage === null, attached: none.attached, firstPage: none.firstPage };
    await back(s);
    // (2) a planted 150 ms delay on the 1.67 MB scan's view moves its first page by 150 +/- 40 ms (no click-time
    // download for it: over 1 MiB; and no kept copy: each open follows a fresh page load)
    const plain = [], planted = [];
    for (const delayed of [false, true, false, true]) {
      await s.page.reload(); await s.page.waitForSelector('#documentsTable .document-row'); await sleep(1500);
      await openDoc(s, 'text-2p', 'control-warm'); await back(s);
      if (delayed) await proxyRule({ kind: 'delay', match: `^/api/encounters/${DOC['scan-3p'].id}/original\\?view=1`, ms: 150, times: 1 });
      const o = await openDoc(s, 'scan-3p', delayed ? 'control-delay-planted' : 'control-delay-plain');
      (delayed ? planted : plain).push(o.firstPage);
      await back(s);
    }
    const mean = v => v.reduce((a, b) => a + b, 0) / v.length;
    const shift = plain.every(v => v !== null) && planted.every(v => v !== null) ? Math.round(mean(planted) - mean(plain)) : null;
    result.controls.planted_delay = { ok: shift !== null && Math.abs(shift - 150) <= 40, shift, plain, planted };
    // (3) a planted fetch adds exactly one server hit
    let seq = await proxySeq();
    await s.page.evaluate(() => fetch('/health/', { cache: 'no-store' }).then(r => r.status));
    await sleep(600);
    const hits = (await proxyLog(seq)).length;
    result.controls.planted_fetch = { ok: hits === 1, hits };
    // (4) a planted detail read adds exactly one record
    const rid = crypto.randomBytes(16).toString('hex');
    const before = (await act('count')).total;
    await s.page.evaluate(([id, h, v, r]) => fetch(`/api/encounters/${id}`, { headers: { [h]: v, 'X-Request-ID': r } }).then(x => x.status), [DOC['text-4p'].id, DATA.client[0], DATA.client[1], rid]);
    await sleep(400);
    const rows = (await act('records', { since: before })).rows;
    const mine = rows.filter(r => r.request_id === rid);
    result.controls.planted_detail = { ok: rows.length === 1 && mine.length === 1 && mine[0].view === 'member.detail', added: rows.length, views: mine.map(r => r.view) };
    // (5) a planted buffer is seen by the heap probe, and gone once dropped
    const size = 3333331;
    await s.page.evaluate(n => { const b = new Uint8Array(n); b[0] = 37; window.__benchPlanted = b; window.__benchMarker = ['zqx', 'bench', 'planted', 'marker'].join(''); }, size);
    const seen = await heap(s.cdp, ['zqxbenchplantedmarker']);
    await s.page.evaluate(() => { delete window.__benchPlanted; delete window.__benchMarker; });
    const gone = await heap(s.cdp, ['zqxbenchplantedmarker']);
    result.controls.heap_probe = { ok: seen.sizes.includes(size) && seen.markers.zqxbenchplantedmarker && !gone.sizes.includes(size) && !gone.markers.zqxbenchplantedmarker,
      seen: [seen.sizes.includes(size), seen.markers.zqxbenchplantedmarker], gone: [gone.sizes.includes(size), gone.markers.zqxbenchplantedmarker] };
  } catch (e) { result.errors.push(`controls: ${String(e && e.stack || e).slice(0, 600)}`); }
  finally { await s.context.close(); }
  // (6) with reduced motion, opaque equals the column +/- 20 ms
  const r = await newContext({ reducedMotion: 'reduce' });
  try {
    await signIn(r, DATA.users[SIZE]); await sleep(1500);
    const o = await openDoc(r, 'text-4p', 'control-reduced');
    const diff = o.opaque !== null && o.column !== null ? Math.round(o.opaque - o.column) : null;
    result.controls.reduced_motion = { ok: diff !== null && Math.abs(diff) <= 20, diff };
  } catch (e) { result.errors.push(`reduced motion: ${String(e).slice(0, 300)}`); }
  finally { await r.context.close(); }
}

// R2-11: leave a document 40 ms after its viewer appears (its worker still starting), wait 22.5 s, open the next.
async function flowQuickLeave() {
  const s = await newContext();
  try {
    await signIn(s, DATA.users[SIZE]); await sleep(2000);
    await openDoc(s, 'text-2p', 'quickleave-normal'); await back(s);
    await s.page.locator(`a.document-row[href="#doc/${DOC['text-4p'].id}"]`).first().click();
    await s.page.waitForSelector('#documentViewer', { timeout: 30000 }); await sleep(40);
    await s.page.evaluate(() => { location.hash = 'documents'; });
    await s.page.waitForSelector('#documentsTable .document-row'); await sleep(22500);
    const seq = await proxySeq();
    const o = await openDoc(s, 'text-10p', 'quickleave-next');
    const library = (await proxyLog(seq)).filter(e => LIBRARY.test(e.url));
    metric('open.quick_leave.first_text.P0', o.text);
    metric('open.quick_leave.library_requests.P0', library.length);
    metric('open.quick_leave.attempt_requests.P0', library.filter(e => /attempt=/.test(e.url)).length);
  } catch (e) { result.errors.push(`quick leave: ${String(e).slice(0, 300)}`); }
  finally { await s.context.close(); }
}

// The page after 30 opens: renderer private memory and heap on the list, PDF workers while viewing; then after sign-out.
async function flowMemory() {
  const s = await newContext();
  try {
    await signIn(s, DATA.users[SIZE]); await sleep(1500);
    const cycle = ['text-2p', 'text-4p', 'text-10p', 'word-3p'];  // text PDFs, as the viewer area's soak (soak.cjs)
    let viewingWorkers = 0;
    for (let i = 0; i < 30; i += 1) {
      await openDoc(s, cycle[i % cycle.length], 'memory');
      viewingWorkers = Math.max(viewingWorkers, await workerTargets(s.context));
      await back(s);
    }
    await sleep(5000); await settle(s.page, 800);
    await s.cdp.send('HeapProfiler.enable');
    for (let i = 0; i < 2; i += 1) { await s.cdp.send('HeapProfiler.collectGarbage'); await sleep(1500); }
    const onList = await renderer(s.context);
    const used = (await s.cdp.send('Runtime.getHeapUsage')).usedSize;
    metric('open.memory.renderer_private_list.P0', onList && onList.privateMb);
    metric('open.memory.heap_list_mb.P0', Math.round(used / 104857.6) / 10);
    metric('open.memory.workers_viewing.P0', viewingWorkers);
    metric('open.memory.workers_list.P0', await workerTargets(s.context));
    await Promise.all([s.page.waitForURL(/\/login\//, { timeout: 60000 }), s.page.locator('button[form="signoutForm"]').first().click()]);
    await sleep(5000);
    for (let i = 0; i < 2; i += 1) { await s.cdp.send('HeapProfiler.collectGarbage'); await sleep(1500); }
    const out = await renderer(s.context);
    metric('open.memory.renderer_private_signed_out.P0', out && out.privateMb);
    metric('open.memory.workers_signed_out.P0', await workerTargets(s.context));
  } catch (e) { result.errors.push(`memory: ${String(e && e.stack || e).slice(0, 600)}`); }
  finally { await s.context.close(); }
}

// Lists: tab changes, Documents usable, the Overview, a later page (paging trees), the search keys.
async function flowLists() {
  const size = DATA.rows[SIZE];
  const cap = PROFILE === 'P1' && size >= 18000 ? 150000 : 180000;
  const s = await newContext();
  try {
    await signIn(s, DATA.users[SIZE]); await sleep(1500); await settle(s.page, 600, cap);
    for (let i = 0; i < 3; i += 1) {
      const d = await tab(s, 'documents', 'documents', { limit: cap });
      if (!d) break;
      metric(`lists.documents.usable.${size}.${PROFILE}`, d.usable);
      metric(`lists.documents.long_task_max.${size}.${PROFILE}`, d.longTasks.max);
      metric(`lists.documents.opaque.${size}.${PROFILE}`, d.opaque);
      metric(`lists.requests.documents.${size}.${PROFILE}`, d.requests.length);
      if (size <= 1500) {
        const grown = await laterPage(s);
        if (grown !== null) metric(`lists.later_page.${size}.${PROFILE}`, grown);
      }
      const q = await tab(s, 'queue', 'queue', { limit: cap });
      if (q && size <= 100) metric(`lists.tab.opaque.${PROFILE}`, q.opaque);
      const o = await tab(s, 'workspace', 'overview', { limit: cap });
      if (!o) break;
      metric(`lists.overview.usable.${size}.${PROFILE}`, o.usable);
      if (size <= 100) metric(`lists.tab.opaque.${PROFILE}`, o.opaque);
      if (PROFILE === 'P1' && size >= 18000 && i === 0) break;  // one visit is enough where release 1 takes minutes
    }
    const d = await tab(s, 'documents', 'documents-for-search', { limit: cap });
    if (d) await searchKeys(s, ['0', '0', '4', '2'], size, cap);
  } catch (e) { result.errors.push(`lists ${size} ${PROFILE}: ${String(e && e.stack || e).slice(0, 600)}`); }
  finally { await s.context.close(); }
}

// A later page loaded by scrolling to the list's end (a paging tree); null when no row is added (a whole list).
async function laterPage(s) {
  const { page } = s;
  const before = await page.evaluate(() => document.querySelectorAll('#documentsTable .document-row').length);
  const started = await page.evaluate(() => { window.scrollTo(0, document.body.scrollHeight); return performance.now(); });
  try {
    await page.waitForFunction(n => document.querySelectorAll('#documentsTable .document-row').length > n, before, { timeout: 4000, polling: 'raf' });
  } catch (e) { await page.evaluate(() => window.scrollTo(0, 0)); return null; }
  const ms = await page.evaluate(t => Math.round(performance.now() - t), started);
  await settle(page); await page.evaluate(() => window.scrollTo(0, 0));
  return ms;
}

// Each key typed into the Documents search, one at a time; per key: its Event Timing duration (the interaction's
// longest entry; under 16 ms none is reported), and the time from its keydown to the visible rows' final state.
async function searchKeys(s, keys, size, cap) {
  const { page } = s;
  await page.locator('#documentSearch').click(); await sleep(300);
  const out = [];
  for (const [i, key] of keys.entries()) {
    const seq = await proxySeq();
    await page.evaluate(() => { const P = window.__bench; P.cur = { kind: 'search', t0: null, sigs: [], sig: P.visible() }; });
    await page.keyboard.press(key);
    const end = await waitSettledRows(page, cap);
    const m = await page.evaluate(() => { const P = window.__bench; const c = P.cur; c.stop = true;
      const ev = P.ev.filter(e => e[1] >= c.t0 - 1 && e[1] <= c.t0 + 1 && ['keydown', 'keypress', 'keyup', 'input', 'beforeinput'].includes(e[0]));
      const sigs = c.sigs; const final = sigs.length ? sigs[sigs.length - 1] : null;
      const eventMs = ev.length ? Math.max(...ev.map(e => e[2])) : 16;
      // the results are shown when the rows reach their final state AND that state is painted, and never before the key's
      // own interaction ended (its Event Timing, the filter included); a key that changes no row is its interaction
      const painted = final ? Math.round((final[2] || final[0]) - c.t0) : 0;
      return { eventMs, resultsMs: Math.max(eventMs, painted), changedAt: final ? Math.round(final[0] - c.t0) : null, visible: P.visible() }; });
    const entries = await windowEntries(seq, Date.now());
    out.push({ key, ...m, settled: end, requests: summarize(entries) });
    metric(`lists.search.key_event.${size}.${PROFILE}`, m.eventMs);
    if (i === 0) metric(`lists.search.first_key.${size}.${PROFILE}`, m.resultsMs);
    if (i === keys.length - 1) metric(`lists.search.after_last_key.${size}.${PROFILE}`, m.resultsMs);
    metric(`lists.requests.search_key.${size}.${PROFILE}`, entries.length);
  }
  result.actions.push({ kind: 'search', size, keys: out });
  try { await page.locator('#documentSearch').fill('', { timeout: 180000 }); await sleep(500); } catch (e) { result.actions.push({ kind: 'search-clear-slow' }); }
}

async function waitSettledRows(page, cap) {
  const started = Date.now(); let last = null; let stableSince = Date.now();
  while (Date.now() - started < cap) {
    const sig = await page.evaluate(() => window.__bench.visible());
    const busy = (await call(CONTROL, 'GET', '/state')).inFlight;
    if (sig !== last || busy) { last = sig; stableSince = Date.now(); }
    if (Date.now() - stableSince >= 900) return Date.now() - started;
    await sleep(60);
  }
  result.unfinished.push(`${PROFILE} search settle`);
  return null;
}

// The office model's measured inputs at one practice size: the sign-in's requests and 30 characters typed at 350 ms.
async function flowOffice() {
  const size = DATA.rows[SIZE];
  const s = await newContext();
  try {
    const signin = await signIn(s, DATA.users[SIZE], { count: true });
    result.actions.push({ kind: 'office-signin', ...signin });
    metric(`office.signin.requests_2s.${size}`, signin.requests);
    await sleep(1500);
    const d = await tab(s, 'documents', 'office-documents');
    metric(`office.documents.requests.${size}`, d ? d.requests.length : null);
    await s.page.locator('#documentSearch').click(); await sleep(400);
    const seq = await proxySeq();
    const text = 'synthetic gi note colonoscopy ';
    const t0 = Date.now();
    for (let i = 0; i < text.length; i += 1) {
      await sleep(Math.max(0, t0 + i * 350 - Date.now()));
      await s.page.keyboard.press(text[i] === ' ' ? 'Space' : text[i]);
    }
    await sleep(2500);
    const entries = (await proxyLog(seq)).map(e => ({ at: Math.round(e.t0 - t0), method: e.method, url: shape(e.url), status: e.status }));
    result.actions.push({ kind: 'office-typing', size, entries });
    metric(`office.typing.requests.${size}`, entries.length);
    result.office = { size, signin: signin.list, typing: entries, documents: d ? d.requests : [] };
  } catch (e) { result.errors.push(`office ${size}: ${String(e && e.stack || e).slice(0, 600)}`); }
  finally { await s.context.close(); }
}

const FLOWS = { open: flowOpen, lists: flowLists, office: flowOffice };

async function main() {
  setup();
  browser = await chromium.launch({ headless: true, args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  result.chromium = browser.version();
  try {
    const flow = FLOWS[FLOW] || (FLOW in EXTRA ? EXTRA[FLOW] : null);
    if (!flow) throw new Error(`unknown flow ${FLOW}`);
    await flow();
  } catch (e) { result.errors.push(`${FLOW}: ${String(e && e.stack || e).slice(0, 1200)}`); }
  finally {
    await browser.close();
    fs.writeFileSync(OUT, JSON.stringify(result, null, 1), { mode: 0o600 });
    console.log(`bench.cjs ${FLOW} ${PROFILE} ${SIZE}: actions ${result.actions.length}, errors ${result.errors.length}, console errors ${result.consoleErrors.length}, blocked ${result.blocked.length}`);
  }
}

// The gate flows (records, left-behind, correct) live below, in EXTRA.
const EXTRA = {};
module.exports = { EXTRA, INIT_FOR, decodeSquares, encodeForTest, shape, inflightMax, LIBRARY };
if (require.main === module) main().catch(e => { console.error(String(e && e.stack || e).slice(0, 3000)); process.exit(1); });
