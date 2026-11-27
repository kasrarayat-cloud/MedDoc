'use strict';
// Unit tests for the customer page, studio/static/studio/app.js, over the customer contract customer-2026-11-26 (the
// build specification, sections 6 and 7, with the fix passes' line identity: every code row is named by its line, a
// decision names the line and the coding review the page shows, an Undo the decision it undoes and a download the
// coding review its dialog was opened on) and its fixtures in tests/fixtures/customer.
// Run: node --test tests/frontend/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');

const app = require('../../studio/static/studio/app.js');
const preview = require('../../ops/dev_preview_server.cjs');

const ROOT = path.join(__dirname, '..', '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'customer');
const BUNDLE = path.join(ROOT, 'studio', 'static', 'studio', 'app.js');
const STYLES = path.join(ROOT, 'studio', 'static', 'studio', 'styles.css');
const TEMPLATES = path.join(ROOT, 'studio', 'templates', 'studio');
const DENYLIST = path.join(ROOT, 'ops', 'verification', 'customer-denylist.json');
const CONTRACT = JSON.parse(fs.readFileSync(path.join(ROOT, 'ops', 'verification', 'customer-contract.json'), 'utf8'));
const fixture = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const ENCOUNTERS = fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort();
const clone = value => JSON.parse(JSON.stringify(value));
const UUID = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
// the second check's own sentences where it gave no verdict (studio/customer.py): for a code it added, the status it
// gave it (ADDED_WITH_STATUS; FIX-SPEC-2 section 3), or ADDED_BY_CHECK for a line stored without one; NOT_CHECKED
const ADDED_WITH_STATUS = ['ready for approval', 'needing an answer']
  .map(status => `The second check found this code and listed it as ${status}; it needs your review.`);
const ADDED_BY_CHECK = 'The second check found this code; it needs your review.';
const ADDED_SENTENCES = [...ADDED_WITH_STATUS, ADDED_BY_CHECK];
const NOT_CHECKED = 'The second check did not review this code.';
// the note on the encounter for a review of the second check that could not be tied to one line (studio/customer.py
// UNPLACED_NOTE, followed by the review's reason as written)
const UNPLACED_NOTE = 'The second check made a comment that could not be tied to one line';

function ui(doc, extra = {}) {
  return { open: new Set(), answers: new Map(), ack: null, reconnecting: false, nowMs: Date.parse(doc?.progress?.server_time || '2026-11-20T00:00:00Z'), clock: 0, ...extra };
}

function render(doc, extra = {}) {
  return app.reviewView(doc, ui(doc, extra));
}

// --- a small DOM over the page's own markup: tag, #id, .class, [attr], [attr="value"], descendant and child ---------

const VOID = new Set(['area', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' };
const decode = value => value.replace(/&(?:amp|lt|gt|quot|#x27|#x60);/g, entity => ENTITIES[entity]);

class El {
  constructor(tag, attrs, parent) {
    this.tag = tag;
    this.attrs = attrs;
    this.parent = parent;
    this.children = [];
  }

  get text() { return this.children.map(child => (typeof child === 'string' ? child : child.text)).join(''); }

  attr(name) { return Object.hasOwn(this.attrs, name) ? this.attrs[name] : null; }

  * walk() {
    for (const child of this.children) {
      if (child instanceof El) {
        yield child;
        yield* child.walk();
      }
    }
  }

  all(selector) {
    const parsed = selectorSteps(selector);
    return [...this.walk()].filter(el => matchSteps(el, parsed));
  }

  one(selector) { return this.all(selector)[0] || null; }
}

function compound(part) {
  const out = { tag: null, id: null, classes: [], attrs: [] };
  let rest = part;
  const tag = /^[a-z][a-z0-9-]*/i.exec(rest);
  if (tag) {
    out.tag = tag[0].toLowerCase();
    rest = rest.slice(tag[0].length);
  }
  while (rest) {
    let m;
    if ((m = /^#([\w-]+)/.exec(rest))) out.id = m[1];
    else if ((m = /^\.([\w-]+)/.exec(rest))) out.classes.push(m[1]);
    else if ((m = /^\[([\w-]+)(?:="([^"]*)")?\]/.exec(rest))) out.attrs.push([m[1], m[2]]);
    else throw new Error(`selector part not understood: ${rest}`);
    rest = rest.slice(m[0].length);
  }
  return out;
}

function selectorSteps(selector) {
  const out = [];
  let combinator = ' ';
  for (const token of selector.trim().replace(/\s*>\s*/g, ' > ').split(/\s+/)) {
    if (token === '>') {
      combinator = '>';
      continue;
    }
    out.push([combinator, compound(token)]);
    combinator = ' ';
  }
  return out;
}

function matchCompound(el, part) {
  if (part.tag && el.tag !== part.tag) return false;
  if (part.id && el.attrs.id !== part.id) return false;
  const classes = (el.attrs.class || '').split(/\s+/);
  if (part.classes.some(name => !classes.includes(name))) return false;
  return part.attrs.every(([name, value]) => Object.hasOwn(el.attrs, name) && (value === undefined || el.attrs[name] === value));
}

function matchSteps(el, parsed, index = parsed.length - 1) {
  const [combinator, part] = parsed[index];
  if (!(el instanceof El) || el.tag === '#root' || !matchCompound(el, part)) return false;
  if (index === 0) return true;
  if (combinator === '>') return matchSteps(el.parent, parsed, index - 1);
  for (let up = el.parent; up; up = up.parent) if (matchSteps(up, parsed, index - 1)) return true;
  return false;
}

function dom(html) {
  const root = new El('#root', {}, null);
  let node = root;
  const token = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
  for (const m of html.matchAll(token)) {
    if (m[5] !== undefined) {
      node.children.push(decode(m[5]));
      continue;
    }
    const tag = m[2].toLowerCase();
    if (m[1]) {
      let open = node;
      while (open && open.tag !== tag) open = open.parent;
      if (open && open.parent) node = open.parent;
      continue;
    }
    const attrs = {};
    for (const a of m[3].matchAll(/([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) attrs[a[1].toLowerCase()] = decode(a[2] ?? a[3] ?? a[4] ?? '');
    const el = new El(tag, attrs, node);
    node.children.push(el);
    if (!VOID.has(tag) && !m[4]) node = el;
  }
  return root;
}

// --- what a customer surface must never carry ------------------------------------------------------------------------

// Vendor and model names, and the words the customer copy never uses (the build specification, section 0 and 7): this
// page says "coding review" and "second check".
const NAMES = /(?<![a-z0-9])(?:corti|astra|fable|openai|anthropic|claude|gemini|google)(?![a-z0-9])|\b(?:gpt|claude|gemini)-/i;
const WORDS = /\b(?:providers?|models?|tokens?|credits?|vendors?|participants?|peers?|harness|traces?|sha-?256|readers?|interpret\w*|engine|pipeline|endpoints?|latency|replay\w*|request[\s_-]?ids?|tool[\s_-]?calls?)\b|\/ops\/|\bHTTP\s?\d{3}\b/i;
function forbidden(value) {
  return [NAMES, WORDS].map(pattern => pattern.exec(value)?.[0]).filter(Boolean);
}

const denylist = JSON.parse(fs.readFileSync(DENYLIST, 'utf8'));
// The shipped denylist's hard patterns for one surface, read as its own "about" says: every allowed string removed
// first, case-blind unless a pattern says otherwise.
function shippedHits(value, surface) {
  let scanned = String(value);
  for (const allowed of denylist.allowed || []) scanned = scanned.split(allowed).join('');
  return (denylist.patterns || []).filter(item => item.severity === 'hard' && item.surfaces.includes(surface))
    .flatMap(item => [...scanned.matchAll(new RegExp(item.source, item.case_sensitive ? 'g' : 'gi'))].map(match => `${item.id}: ${match[0]}`));
}

// The text nodes and the scanned attributes of a page (the denylist's dom surface).
const SCANNED_ATTRIBUTES = /^(?:aria-[\w-]+|data-[\w-]+|title|alt|placeholder|value|label|href|src|action|download)$/;
function surfaceStrings(html) {
  const root = dom(html);
  const out = [];
  const visit = node => {
    for (const child of node.children) {
      if (typeof child === 'string') {
        if (child.trim()) out.push(child);
      } else {
        for (const [name, value] of Object.entries(child.attrs)) if (SCANNED_ATTRIBUTES.test(name) && value) out.push(value);
        visit(child);
      }
    }
  };
  visit(root);
  return out;
}

function leaks(html) {
  return surfaceStrings(html).flatMap(value => [...forbidden(value), ...shippedHits(value, 'dom')].map(word => `${word} in ${JSON.stringify(value.slice(0, 80))}`));
}

// Every piece of markup the page can draw for a document, in one string.
function markup(doc) {
  return [render(doc), render(doc, { open: new Set(['activity']) }), app.exportOptions(doc),
    app.exportOptions(doc, { kind: 'draft', fmt: 'pdf' }), app.exportOptions(doc, { kind: 'approved', fmt: 'pdf' }),
    app.progressPanel(doc, ui(doc, { reconnecting: true, ack: { id: doc.id, at: Date.parse('2026-11-20T10:00:00Z') } })),
    `<p>${app.escapeHtml(app.exportStatusText(doc))}</p>`].join('\n');
}

// --- a few page elements and a recording fetch, for the page's own calls ---------------------------------------------

function fakeElement(extra = {}) {
  const classes = new Set();
  return {
    textContent: '', hidden: false, value: '', checked: false, disabled: false, open: false, dataset: {}, attributes: {},
    classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name), toggle: (name, on) => ((on ?? !classes.has(name)) ? classes.add(name) : classes.delete(name)) },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    removeAttribute(name) { delete this.attributes[name]; },
    toggleAttribute(name, on) { if (on) this.attributes[name] = ''; else delete this.attributes[name]; },
    focus() {}, showModal() { this.open = true; }, close() { this.open = false; }, addEventListener() {},
    ...extra,
  };
}

function response({ status = 200, body = {}, type = 'application/json', redirected = false, url = '/', headers = {} } = {}) {
  const named = Object.fromEntries(Object.entries({ 'content-type': type, ...headers }).map(([name, value]) => [name.toLowerCase(), value]));
  return {
    status, ok: status >= 200 && status < 300, redirected, url: `http://studio.test${url}`,
    headers: { get: name => named[name.toLowerCase()] ?? null },
    json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
  };
}

// Runs fn with a page of fake elements (any #id answers one, made on first use), a recording fetch and a location that
// records where the page sends the member. The fetch answers each call with the first of `answers` whose match accepts
// it (an answer without one takes any call but the session read the page makes after every change), the session read
// with the session fixture, and anything else with 201 {}. Work the page leaves running finishes before the page goes,
// and a poll it scheduled is cancelled.
async function withPage({ elements = {}, answers = [] } = {}, fn) {
  const saved = { document: global.document, fetch: global.fetch, location: global.location, window: global.window };
  const byId = new Map(Object.entries(elements));
  const calls = [];
  const element = selector => {
    if (!selector.startsWith('#')) return null;
    const id = selector.slice(1);
    if (!byId.has(id)) byId.set(id, fakeElement());
    return byId.get(id);
  };
  // a download the page starts (startDownload: a hidden link it clicks) is recorded as {download, filename}
  const link = () => fakeElement({ click() { calls.push({ download: this.href, filename: this.download }); }, remove() {} });
  global.document = { cookie: 'cptstudio_csrf=token123', querySelector: element, querySelectorAll: () => [], activeElement: null, hidden: false,
    createElement: link, body: { appendChild() {} } };
  global.fetch = async (url, init = {}) => {
    const method = init.method || 'GET';
    calls.push({ url, method: init.method, headers: init.headers, body: init.body, credentials: init.credentials, cache: init.cache });
    const session = method === 'GET' && url === '/api/session';
    const index = answers.findIndex(answer => (answer.match ? answer.match(method, url) : !session));
    const answer = index >= 0 ? answers.splice(index, 1)[0] : session ? { status: 200, body: fixture('session.json') } : { status: 201, body: {} };
    // the bytes of a file the page saves (saveDownload): a Blob that names the address it came from
    return Object.assign(response(answer), { blob: async () => Object.assign(new Blob([JSON.stringify(answer.body ?? {})]), { source: url }) });
  };
  // the address a saved file gets names the file the page fetched, so a test reads which file the member was given
  const objectUrls = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  URL.createObjectURL = blob => blob?.source || 'blob:test';
  URL.revokeObjectURL = () => {};
  global.location = { hash: '', assign(url) { calls.push({ assign: url }); } };
  global.window = { scrollY: 0, scrollTo() {}, matchMedia: () => ({ matches: false }) };
  const kept = ['doc', 'session', 'route', 'routeSerial', 'review', 'answers', 'leaving', 'outdated', 'docKey', 'viewerKey', 'selectedQuote', 'clock', 'reconnecting', 'ack',
    'exporting', 'making', 'made', 'madeRead', 'rereading', 'rereadAfter', 'sessionReadAt', 'standbyOn', 'standbyFails', 'pdfStandby', 'pdfStarted',
    'list'];
  const before = Object.fromEntries(kept.map(key => [key, app.state[key]]));
  const idleBefore = { ...app.idle };  // the idle timer's state is the page's too (B5)
  try {
    await fn({ calls, element });
  } finally {
    await new Promise(resolve => setImmediate(resolve));
    Object.assign(URL, { createObjectURL: objectUrls.create, revokeObjectURL: objectUrls.revoke });
    clearTimeout(app.idle.timer);
    Object.assign(app.idle, idleBefore);
    clearTimeout(app.state.madeTimer);
    clearTimeout(app.state.toastTimer);
    clearTimeout(app.state.standbyTimer);
    if (app.state.pdfStandby !== before.pdfStandby) app.state.pdfStandby?.thread?.terminate?.();
    clearTimeout(app.state.poll.timer);
    clearTimeout(app.state.tickTimer);
    Object.assign(global, saved);
    Object.assign(app.state, before, { pending: new Set(), poll: { timer: 0, count: 0, errors: 0 } });
  }
}

const posted = calls => calls.filter(call => call.method === 'POST').map(call => ({ url: call.url, body: JSON.parse(call.body) }));

// A click the page's own handler receives (onClick): the target's closest(selector) is an element with `dataset`.
function click(selector, dataset) {
  app.onClick({ target: { closest: wanted => (wanted === selector ? fakeElement({ dataset }) : null) } });
}

// Lets the page's own asynchronous work run until `done()` holds (at most 50 turns of the event loop).
async function settle(done) {
  for (let turn = 0; turn < 50 && !done(); turn += 1) await new Promise(resolve => setImmediate(resolve));
}

// --- helpers kept from the earlier page ---------------------------------------------------------------------------

test('escapeHtml escapes every markup-significant character and tolerates empty values', () => {
  assert.equal(app.escapeHtml(`<a href="x" onclick='y'>&\`</a>`), '&lt;a href=&quot;x&quot; onclick=&#x27;y&#x27;&gt;&amp;&#x60;&lt;/a&gt;');
  assert.equal(app.escapeHtml(null), '');
  assert.equal(app.escapeHtml(undefined), '');
  assert.equal(app.escapeHtml(0), '0');
});

test('lookup only answers own keys, never prototype members', () => {
  assert.equal(app.lookup({ ready: 'Ready' }, 'ready', 'x'), 'Ready');
  assert.equal(app.lookup({ ready: 'Ready' }, 'constructor', 'fallback'), 'fallback');
  assert.equal(app.lookup({ ready: 'Ready' }, '__proto__', 'fallback'), 'fallback');
  assert.equal(app.lookup({ ready: 'Ready' }, 7, 'fallback'), 'fallback');
});

test('dates are formatted from their parts, so no time zone can shift the day', () => {
  assert.deepEqual(app.parseIsoDate('2026-10-21'), { year: 2026, month: 10, day: 21 });
  for (const bad of ['2026-02-30', '2026-13-01', '2026-1-01', '21/10/2026', '', null, undefined, '2026-10-21T00:00:00Z']) {
    assert.equal(app.parseIsoDate(bad), null, String(bad));
  }
  assert.equal(app.formatDate('2026-10-21'), '21 Oct 2026');
  assert.equal(app.formatDate('2026-10-01', true), '1 October 2026');
  assert.equal(app.formatTimestamp('2026-10-23T23:30:00Z'), '23 Oct 2026, 23:30 UTC');
  assert.equal(app.formatTimestamp('garbage'), '');
  assert.equal(app.formatTimestamp(null), '');
});

test('readCookie finds the named cookie only and survives malformed encoding', () => {
  assert.equal(app.readCookie('other=1; cptstudio_csrf=abc%3D123; cptstudio_csrf_x=no', 'cptstudio_csrf'), 'abc=123');
  assert.equal(app.readCookie('cptstudio_csrf=%E0%A4%A', 'cptstudio_csrf'), '');
  assert.equal(app.readCookie('', 'cptstudio_csrf'), '');
});

test('download, original and view addresses are accepted only as same-origin paths of their own shape', () => {
  assert.equal(app.safeDownloadUrl(`/api/reports/${UUID}/download`), `/api/reports/${UUID}/download`);
  assert.equal(app.safeOriginalUrl(`/api/encounters/${UUID}/original`), `/api/encounters/${UUID}/original`);
  assert.equal(app.safeViewUrl(`/api/encounters/${UUID}/original?view=1`), `/api/encounters/${UUID}/original?view=1`);
  assert.equal(app.safeViewUrl(`/api/encounters/${UUID}/original?lang=en&view=1`), `/api/encounters/${UUID}/original?lang=en&view=1`);
  for (const bad of ['javascript:alert(1)', `https://evil.test/api/encounters/${UUID}/original?view=1`, `//evil.test/api/encounters/${UUID}/original?view=1`,
    `/api/encounters/${UUID}/original`, `/api/encounters/${UUID}/original?view=0`, `/api/encounters/${UUID}/original?view=1#x`, `/api/encounters/x/original?view=1`,
    `/api/encounters/${UUID}/original?view=1&next=/x"`, null, 7]) {
    assert.equal(app.safeViewUrl(bad), '', String(bad));
  }
  assert.equal(app.safeOriginalUrl('javascript:alert(1)'), '');
  assert.equal(app.safeDownloadUrl(`/api/reports/${UUID}/download?x=1`), '');
});

test('polling starts at 2.5 s, backs off, and is bounded', () => {
  assert.equal(app.pollDelay(0, 0), 2500);
  assert.ok(app.pollDelay(3, 0) > 2500);
  assert.equal(app.pollDelay(100, 0), 15000);
  assert.equal(app.pollDelay(0, 1), 5000);
  assert.equal(app.pollDelay(0, 10), 30000);
});

test('routes resolve known views and fall back to the overview', () => {
  assert.deepEqual(app.parseRoute('#documents'), { name: 'documents' });
  assert.deepEqual(app.parseRoute('#queue'), { name: 'queue' });
  assert.deepEqual(app.parseRoute('#how-it-works'), { name: 'how-it-works' });
  assert.deepEqual(app.parseRoute(`#doc/${UUID}`), { name: 'doc', id: UUID });
  assert.deepEqual(app.parseRoute('#constructor'), { name: 'workspace' });
  assert.deepEqual(app.parseRoute('#doc'), { name: 'workspace' });
  assert.deepEqual(app.parseRoute(''), { name: 'workspace' });
});

test('every upload attempt carries a version-4 client key', () => {
  const key = app.newClientKey(n => new Uint8Array(n).fill(255));
  assert.match(key, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('the page names its build, and a 409 client_outdated is the update notice while other answers are plain sentences', () => {
  assert.equal(app.CLIENT_VERSION, 'customer-2026-11-26');
  assert.equal(app.CLIENT_HEADER, 'X-CPT-Studio-Client');
  assert.equal(app.isClientOutdated(409, { error_code: 'client_outdated' }), true);
  assert.equal(app.isClientOutdated(409, { error: 'x' }), false);
  assert.equal(app.isClientOutdated(400, { error_code: 'client_outdated' }), false);
  assert.equal(app.errorText(400, { error: '  Choose a file.  ' }), 'Choose a file.');
  for (const status of [400, 403, 404, 409, 413, 429, 500, 0]) assert.doesNotMatch(app.errorText(status, null), /\d{3}/, String(status));
});

test('elapsed and duration text: seconds, minutes and hours, never negative', () => {
  assert.equal(app.durationText(45000), '45 s');
  assert.equal(app.durationText(245000), '4 min 05 s');
  assert.equal(app.durationText(3720000), '1 h 02 min');
  assert.equal(app.durationText(-5), '0 s');
  assert.equal(app.elapsedText('2026-11-20T09:00:00Z', Date.parse('2026-11-20T09:00:30Z')), '30 s');
  assert.equal(app.clockOffset('2026-11-20T09:00:10Z', Date.parse('2026-11-20T09:00:00Z')), 10000);
});

// --- the fixtures are the contract ------------------------------------------------------------------------------------

const CONTRACT_ISO = new RegExp(CONTRACT.iso_pattern);
const CONTRACT_DATE = new RegExp(CONTRACT.date_pattern);

// Every place `value` departs from one node of ops/verification/customer-contract.json (its "about" says how a node
// reads): a type name with an optional '?', {ref}, {enum}, {items}, {map} or {keys} - exactly these keys, at every
// level - each nullable where it says so.
function contractProblems(value, node, where) {
  if (typeof node === 'string') {
    const nullable = node.endsWith('?');
    const type = nullable ? node.slice(0, -1) : node;
    if (value === null) return nullable || type === 'any' ? [] : [`${where}: null`];
    const ok = {
      string: typeof value === 'string', integer: Number.isInteger(value), number: typeof value === 'number', boolean: typeof value === 'boolean',
      any: true, date: typeof value === 'string' && CONTRACT_DATE.test(value), iso: typeof value === 'string' && CONTRACT_ISO.test(value),
    }[type];
    if (ok === undefined) return [`${where}: the contract names an unknown type ${type}`];
    return ok ? [] : [`${where}: not ${type}: ${JSON.stringify(value)}`];
  }
  if (node.ref) return value === null && node.nullable ? [] : contractProblems(value, CONTRACT.types[node.ref], where);
  if (value === null) return node.nullable ? [] : [`${where}: null`];
  if (node.enum) return node.enum.includes(value) ? [] : [`${where}: ${JSON.stringify(value)} is not one of ${node.enum.join(', ')}`];
  if (node.items) return Array.isArray(value) ? value.flatMap((item, index) => contractProblems(item, node.items, `${where}[${index}]`)) : [`${where}: not a list`];
  const isObject = value && typeof value === 'object' && !Array.isArray(value);
  if (node.map) return isObject ? Object.entries(value).flatMap(([key, item]) => contractProblems(item, node.map, `${where}.${key}`)) : [`${where}: not an object`];
  if (!node.keys) return [`${where}: the contract node is not understood`];
  if (!isObject) return [`${where}: not an object`];
  const want = Object.keys(node.keys).sort();
  const have = Object.keys(value).sort();
  const keys = JSON.stringify(have) === JSON.stringify(want) ? [] : [`${where}: keys ${have.join(',')} are not ${want.join(',')}`];
  return [...keys, ...want.filter(key => Object.hasOwn(value, key)).flatMap(key => contractProblems(value[key], node.keys[key], `${where}.${key}`))];
}

test('every customer fixture matches ops/verification/customer-contract.json exactly: its keys at every level and their types', () => {
  for (const name of ENCOUNTERS) assert.deepEqual(contractProblems(fixture(name), CONTRACT.encounter, name), [], name);
  for (const name of ['session.json', 'session-agent.json']) assert.deepEqual(contractProblems(fixture(name), CONTRACT.session, name), [], name);
  for (const name of ['encounters.json', 'encounters-empty.json']) assert.deepEqual(contractProblems(fixture(name), CONTRACT.list, name), [], name);
  // the check finds a key too many, a key missing, a wrong type and a value outside its vocabulary, so a clean result
  // means something
  const planted = clone(fixture('encounter-word.json'));
  planted.document.preview_type = 'pdf';
  delete planted.document.converted;
  planted.codes[0].second_check.agrees = 'yes';
  planted.progress.phase = 'finished';
  const found = contractProblems(planted, CONTRACT.encounter, 'planted');
  assert.deepEqual(found.sort(), [
    'planted.codes[0].second_check.agrees: not boolean: "yes"',
    'planted.document: keys kind,media_type,name,original_url,preview_type,size,view_conversion,view_media_type,view_url are not converted,kind,media_type,name,original_url,size,view_conversion,view_media_type,view_url',
    'planted.progress.phase: "finished" is not one of queued, reading, checking, done, failed, stopped, earlier',
  ]);
});

test('the page and the fixtures speak the contract\'s vocabulary: states, phases, code statuses and insurance', () => {
  const vocabulary = CONTRACT.vocabulary;
  assert.deepEqual(app.STATE_LABELS, vocabulary.states);
  assert.deepEqual(app.PHASES, vocabulary.phases);
  assert.deepEqual(Object.fromEntries(Object.entries(app.CODE_STATUSES).map(([key, [label]]) => [key, label])), vocabulary.code_statuses);
  assert.deepEqual(Object.fromEntries(app.INSURANCE_CHOICES), vocabulary.insurance);
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    assert.equal(doc.state_label, vocabulary.states[doc.state], name);
    for (const code of doc.codes) {
      assert.equal(code.status_label, vocabulary.code_statuses[code.status], `${name} ${code.code}`);
      // section 6: ready and needs_review take approve and reject; needs_answer and not_supported none; a decision, revoke
      const expected = code.decision ? ['revoke'] : ['ready', 'needs_review'].includes(code.status) ? ['approve', 'reject'] : [];
      assert.deepEqual(code.allowed_actions, expected, `${name} ${code.code}`);
      // the second check's reason without a verdict is one of the server's own sentences, and a code it gave none is
      // one that needs review
      if (code.second_check.agrees === null) {
        assert.ok([...ADDED_SENTENCES, NOT_CHECKED].includes(code.second_check.reason), `${name} ${code.code}`);
        assert.equal(code.status, 'needs_review', `${name} ${code.code}`);
      }
    }
    if (doc.state === 'earlier') {
      assert.equal(doc.progress.message, vocabulary.earlier_message, name);
      assert.deepEqual([doc.progress.phase, doc.round, doc.codes, doc.questions, doc.notes], ['earlier', null, [], [], []], name);
    }
    if (doc.readiness.draft && !doc.readiness.approved) assert.deepEqual(doc.readiness.blockers, [vocabulary.none_approved_blocker], name);
  }
  for (const row of fixture('encounters.json').encounters) assert.equal(row.state_label, vocabulary.states[row.state], row.id);
});

// What studio/customer.py document_json gives each kind of document: the view type and the converted flag.
function expectedView(part) {
  if (part.kind === 'paste') return ['text/plain', false];
  if (part.media_type === DOCX) return part.view_url ? ['application/pdf', true] : [null, false];
  return [part.media_type, false];
}

test('the fixtures cover every state the page draws, and the list matches them, newest first', () => {
  const states = Object.fromEntries(ENCOUNTERS.map(name => [name, [fixture(name).state, fixture(name).progress.phase]]));
  assert.deepEqual(states, {
    'encounter-awaiting-answer.json': ['awaiting_answer', 'done'], 'encounter-checking.json': ['processing', 'checking'],
    'encounter-earlier.json': ['earlier', 'earlier'], 'encounter-failed.json': ['failed', 'failed'],
    'encounter-needs-review.json': ['needs_review', 'done'], 'encounter-no-codes.json': ['no_codes', 'done'],
    'encounter-reading.json': ['processing', 'reading'], 'encounter-ready.json': ['ready', 'done'],
    'encounter-reviewed.json': ['reviewed', 'done'], 'encounter-same-code.json': ['needs_review', 'done'],
    'encounter-shared-question.json': ['awaiting_answer', 'done'], 'encounter-word.json': ['needs_review', 'done'],
  });
  // every document's view as the server builds it: a PDF or a text as uploaded, a pasted text as text, a Word file as
  // the PDF it was converted to - or, never converted (an earlier review), no view
  const views = Object.fromEntries(ENCOUNTERS.map(name => {
    const part = fixture(name).document;
    assert.deepEqual([part.view_media_type, part.converted], expectedView(part), name);
    assert.equal(part.view_url, part.view_media_type ? `/api/encounters/${fixture(name).id}/original?view=1` : null, name);
    // I1-12, I2-2: a Word document's view names the stored conversion it serves (a UUID), any other document none
    assert.ok(part.converted ? /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(part.view_conversion) : part.view_conversion === null, name);
    return [name, part.view_media_type];
  }));
  assert.deepEqual([views['encounter-word.json'], views['encounter-earlier.json'], views['encounter-awaiting-answer.json'], views['encounter-no-codes.json']],
    ['application/pdf', null, 'text/plain', 'text/plain']);
  const rows = fixture('encounters.json').encounters;
  assert.equal(rows.length, ENCOUNTERS.length);
  for (const row of rows) {
    const doc = ENCOUNTERS.map(fixture).find(item => item.id === row.id);
    assert.ok(doc, row.id);
    assert.deepEqual([row.title, row.state, row.state_label, row.service_date, row.insurance, row.kind, row.created_at],
      [doc.title, doc.state, doc.state_label, doc.context.service_date, doc.context.insurance, doc.document.kind, doc.created_at]);
  }
  const created = rows.map(row => row.created_at);
  assert.deepEqual(created, [...created].sort().reverse(), 'GET /api/encounters lists the newest first');
  for (const name of ['session.json', 'session-agent.json']) {
    assert.deepEqual(fixture(name).counts, { documents: rows.length, queue: rows.filter(app.inQueue).length }, name);
  }
  // R2-19: a list answer carries next and total, and (I1-2) the practice it was read in, the session's
  assert.deepEqual(fixture('encounters-empty.json'), { encounters: [], next: null, total: 0, workspace: fixture('session.json').workspace.id });
});

test('every quote in the fixtures is the synthetic document\'s own text, on the page it names', () => {
  let checked = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const key = preview.documentFor(doc);
    const source = preview.SYNTHETIC_DOCUMENTS[key];
    assert.ok(source, name);
    assert.match(source.pages[0][0], /^SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT/, name);
    assert.equal(doc.document.media_type, source.type, name);
    assert.equal(doc.document.size, preview.documentBytes(key).bytes.length, `${name}: the size of the original the preview serves`);
    // a PDF view has pages (a Word file's is the PDF it was converted to, of the same pages); a text has none
    const paged = doc.document.view_media_type === 'application/pdf';
    for (const code of doc.codes) {
      for (const quote of code.quotes) {
        if (paged) assert.ok(source.pages[quote.page - 1]?.includes(quote.text), `${name} ${code.code}: ${quote.text}`);
        else assert.ok(quote.page === null && source.pages.flat().includes(quote.text), `${name} ${code.code}: ${quote.text}`);
        checked += 1;
      }
    }
    assert.match(doc.title, /^Synthetic /, name);
  }
  assert.ok(checked >= 23, checked);
});

// The line ids the server gives the rows of a coding review (the fix pass, section 1): "L1".."Ln" for the codes the
// coding review listed, in its order, then "M1".."Mk" for the codes the second check added, in theirs.
const LINE_ID = /^[LM][1-9][0-9]{0,2}$/;

test('every fixture code names its line: L1..Ln for the coding review\'s codes, then M1..Mk for those the second check added', () => {
  let pairs = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const lines = doc.codes.map(code => code.line);
    for (const line of lines) assert.match(String(line), LINE_ID, `${name}: ${line}`);
    const listed = lines.filter(line => line.startsWith('L'));
    const added = lines.filter(line => line.startsWith('M'));
    assert.deepEqual(lines, [...listed, ...added], `${name}: the second check's lines come after the coding review's`);
    assert.deepEqual(listed, listed.map((_, index) => `L${index + 1}`), name);
    assert.deepEqual(added, added.map((_, index) => `M${index + 1}`), name);
    // a line the second check added is exactly a row whose second check is its own sentence for an added code
    doc.codes.forEach(code => assert.equal(code.line.startsWith('M'), ADDED_SENTENCES.includes(code.second_check.reason), `${name} ${code.line}`));
    const codes = doc.codes.map(code => code.code);
    pairs += codes.length - new Set(codes).size;
    // a question names the lines it affects, and shows those lines' codes
    for (const question of doc.questions) {
      assert.ok(Array.isArray(question.lines) && question.lines.length > 0 && question.lines.every(line => lines.includes(line)), `${name} ${question.id}`);
      assert.deepEqual(question.codes, [...new Set(question.lines.map(line => doc.codes.find(code => code.line === line).code))], `${name} ${question.id}`);
    }
    // a line that needs an answer has a question the member can answer
    for (const code of doc.codes.filter(item => item.status === 'needs_answer')) {
      assert.ok(doc.questions.some(question => question.lines.includes(code.line)), `${name} ${code.line}`);
    }
  }
  // and one coding review lists one code on two lines, so the page is proven to tell them apart
  assert.ok(pairs >= 1, 'a fixture with one code on two lines');
  const twice = fixture('encounter-same-code.json').codes.filter(code => code.code === '45380');
  assert.deepEqual(twice.map(code => [code.line, code.modifiers, code.status]), [['L3', [], 'needs_review'], ['M1', ['XS'], 'needs_review']]);
});

// The entries of a ZIP archive of stored (uncompressed) files, read from its central directory: name -> bytes.
function storedEntries(bytes) {
  const end = bytes.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  assert.ok(end > 0, 'an end of central directory record');
  const count = bytes.readUInt16LE(end + 10);
  let at = bytes.readUInt32LE(end + 16);
  const out = new Map();
  for (let index = 0; index < count; index += 1) {
    assert.equal(bytes.readUInt32LE(at), 0x02014b50, `central directory entry ${index}`);
    const [method, crc, size, nameLength, local] = [bytes.readUInt16LE(at + 10), bytes.readUInt32LE(at + 16), bytes.readUInt32LE(at + 20), bytes.readUInt16LE(at + 28), bytes.readUInt32LE(at + 42)];
    const name = bytes.toString('utf8', at + 46, at + 46 + nameLength);
    assert.equal(method, 0, `${name} is stored`);
    assert.equal(bytes.readUInt32LE(local), 0x04034b50, `${name}: its local header`);
    const start = local + 30 + bytes.readUInt16LE(local + 26) + bytes.readUInt16LE(local + 28);
    const data = bytes.subarray(start, start + size);
    if (typeof zlib.crc32 === 'function') assert.equal(zlib.crc32(data), crc, `${name}: its checksum`);
    out.set(name, data);
    at += 46 + nameLength + bytes.readUInt16LE(at + 30) + bytes.readUInt16LE(at + 32);
  }
  return out;
}

test('the preview server\'s synthetic originals are a real two-page PDF, plain text and a Word file viewed as its PDF', () => {
  const pdf = preview.documentBytes('synthetic-egd-colonoscopy.pdf');
  assert.equal(pdf.type, 'application/pdf');
  const body = pdf.bytes.toString('latin1');
  assert.ok(body.startsWith('%PDF-1.4\n') && body.endsWith('%%EOF\n'));
  assert.equal((body.match(/\/Type \/Page /g) || []).length, 2);
  // every xref offset points at its object
  const xref = Number(/startxref\n(\d+)\n/.exec(body)[1]);
  assert.ok(body.slice(xref).startsWith('xref\n'));
  const offsets = [...body.slice(xref).matchAll(/^(\d{10}) 00000 n $/gm)].map(match => Number(match[1]));
  offsets.forEach((offset, index) => assert.ok(body.slice(offset).startsWith(`${index + 1} 0 obj\n`), `object ${index + 1}`));
  assert.equal(fixture('encounter-ready.json').document.size, pdf.bytes.length);
  assert.deepEqual(preview.viewBytes('synthetic-egd-colonoscopy.pdf'), pdf, 'a PDF is viewed as it is');
  const note = preview.documentBytes('synthetic-colonoscopy-note.txt');
  assert.match(note.type, /^text\/plain/);
  assert.match(note.bytes.toString('utf8'), /descending colon was removed\./);
  // the Word file: a package of the three parts a Word file needs, one paragraph per line and a page break between the
  // pages; its view is the two-page PDF of the same pages
  const name = 'synthetic-colonoscopy-report.docx';
  const word = preview.documentBytes(name);
  assert.equal(word.type, DOCX);
  assert.equal(word.bytes.readUInt32LE(0), 0x04034b50);
  const parts = storedEntries(word.bytes);
  assert.deepEqual([...parts.keys()], ['[Content_Types].xml', '_rels/.rels', 'word/document.xml']);
  assert.match(parts.get('[Content_Types].xml').toString('utf8'), /PartName="\/word\/document\.xml" ContentType="application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document\.main\+xml"/);
  assert.match(parts.get('_rels/.rels').toString('utf8'), /Target="word\/document\.xml"/);
  const xml = parts.get('word/document.xml').toString('utf8');
  const pages = xml.split('<w:br w:type="page"/>').map(page => [...page.matchAll(/<w:t xml:space="preserve">([^<]*)<\/w:t>/g)].map(match => match[1]));
  assert.deepEqual(pages, preview.SYNTHETIC_DOCUMENTS[name].pages);
  assert.equal(fixture('encounter-word.json').document.size, word.bytes.length);
  const view = preview.viewBytes(name);
  assert.equal(view.type, 'application/pdf');
  assert.deepEqual(view.bytes, preview.syntheticPdf(preview.SYNTHETIC_DOCUMENTS[name].pages));
  assert.equal((view.bytes.toString('latin1').match(/\/Type \/Page /g) || []).length, 2);
});

// --- labels -----------------------------------------------------------------------------------------------------------

test('status labels: the four statuses and the two decisions keep their fixed labels and tones', () => {
  assert.deepEqual(Object.fromEntries(Object.entries(app.CODE_STATUSES).map(([key, [label, tone]]) => [key, [label, tone]])), {
    ready: ['Ready for approval', 'green'], needs_answer: ['Needs your answer', 'amber'], needs_review: ['Needs your review', 'amber-outline'],
    not_supported: ['Not supported', 'gray'],
  });
  assert.deepEqual(app.shownStatus({ status: 'ready', decision: { action: 'approve', by: 'R', at: '2026-11-20T00:00:00Z', note: '' } }).label, 'Approved');
  assert.deepEqual(app.shownStatus({ status: 'needs_review', decision: { action: 'reject', by: 'R', at: '2026-11-20T00:00:00Z', note: '' } }).key, 'rejected');
  assert.equal(app.shownStatus({ status: 'ready', decision: { action: 'revoke' } }).label, 'Ready for approval', 'revoke is never a standing decision');
  assert.equal(app.shownStatus({ status: 'ready', decision: null }).label, 'Ready for approval');
  // a status this page does not know is never drawn as reviewable
  assert.deepEqual(app.codeStatus({ status: 'held' }), { key: 'held', label: 'Not reviewable', tone: 'gray', icon: '' });
  assert.equal(app.codeStatus({ status: 'held', status_label: 'Held' }).label, 'Held');
  assert.deepEqual(app.STATE_LABELS, {
    processing: 'Processing', stopped: 'Stopped', failed: 'Could not finish', awaiting_answer: 'Questions for you', needs_review: 'Needs your review',
    ready: 'Ready for approval', reviewed: 'Reviewed', no_codes: 'No codes found', earlier: 'Earlier review',
  });
  assert.equal(app.stateLabel('constructor', ''), 'Unknown');
});

test('insurance: four choices with fixed labels, sent as the upload\'s insurance field, shown plainly on the page', () => {
  assert.deepEqual(app.INSURANCE_CHOICES, [['medicare', 'Medicare'], ['medicaid', 'Medicaid'], ['commercial', 'Commercial or other'], ['unknown', 'Not sure']]);
  assert.equal(app.insuranceLabel('commercial'), 'Commercial or other');
  assert.equal(app.insuranceLabel('constructor'), 'Not sure');
  assert.equal(app.insuranceText('medicare'), 'Medicare');
  assert.equal(app.insuranceText('unknown'), 'Insurance not given');
  assert.equal(app.insuranceText(undefined), 'Insurance not given');
  // the upload dialog's select offers exactly these, in this order, with Not sure chosen until the member chooses
  const html = fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8');
  const select = dom(html).one('select#insurance');
  assert.ok(select);
  assert.deepEqual(select.all('option').map(option => [option.attr('value'), option.text]), app.INSURANCE_CHOICES);
  assert.deepEqual(select.all('option').filter(option => option.attr('selected') !== null).map(option => option.attr('value')), ['unknown']);
  assert.equal(select.parent.tag, 'label');
  assert.match(select.parent.text, /^Insurance/);
  const meta = dom(app.reviewMeta(fixture('encounter-ready.json'))).text;
  assert.match(meta, /Medicare/);
  assert.match(dom(app.reviewMeta(fixture('encounter-failed.json'))).text, /Insurance not given/);
});

test('the upload form refuses what the server would refuse, and sends the insurance chosen', () => {
  const file = new File(['synthetic'], 'note.txt', { type: 'text/plain' });
  const base = { paste: false, file, serviceDate: '', insurance: 'medicaid', attested: true };
  const form = app.uploadForm(base, UUID);
  assert.ok(form instanceof FormData);
  assert.deepEqual([form.get('insurance'), form.get('synthetic_attestation'), form.get('client_key'), form.has('service_date')], ['medicaid', 'yes', UUID, false]);
  assert.equal(app.uploadForm({ ...base, insurance: undefined }, UUID).get('insurance'), 'unknown');
  assert.equal(app.uploadForm({ ...base, serviceDate: '2026-11-02' }, UUID).get('service_date'), '2026-11-02');
  assert.equal(app.uploadForm({ ...base, insurance: 'private' }, UUID), 'Choose the insurance, or Not sure.');
  assert.equal(app.uploadForm({ ...base, insurance: '' }, UUID), 'Choose the insurance, or Not sure.');
  assert.match(app.uploadForm({ ...base, file: null }, UUID), /Choose a PDF/);
  assert.match(app.uploadForm({ ...base, attested: false }, UUID), /synthetic/);
  assert.match(app.uploadForm({ ...base, serviceDate: '2026-02-30' }, UUID), /valid date/);
  assert.match(app.uploadForm({ ...base, paste: true, text: '   ' }, UUID), /Paste the clinical text/);
  assert.equal(app.uploadForm({ ...base, paste: true, text: 'Synthetic note.' }, UUID).get('text'), 'Synthetic note.');
});

// --- the review page's DOM contract (section 7) -----------------------------------------------------------------------

test('every fixture draws the DOM contract: viewer, quotes, progress, questions, codes and notes', () => {
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const page = dom(render(doc));
    // the original when the server names a view type, else no viewer at all: a PDF in the region the page draws it in, a
    // text in an iframe, each keeping view_url in data-view-url, with the polite note under it that says what a chosen
    // quote marked; the note under a converted Word document's PDF; the download of the original when there is one
    const viewer = page.one('#documentViewer');
    if (doc.document.view_media_type === 'application/pdf') {
      assert.ok(viewer && viewer.tag === 'div' && viewer.attr('class') === 'viewer-frame pdf-viewer', name);
      assert.equal(viewer.attr('data-view-url'), doc.document.view_url, name);
      assert.deepEqual([viewer.attr('role'), viewer.attr('tabindex')], ['region', '0'], name);
      assert.match(viewer.attr('aria-label'), /^Original document: /, name);
      assert.equal(page.all('iframe').length, 0, `${name}: the page draws the PDF itself`);
      assert.equal(page.one('.viewer-toolbar #viewerPage').text, '', name);
    } else if (doc.document.view_media_type) {
      assert.ok(viewer && viewer.tag === 'iframe', name);
      assert.equal(viewer.attr('src'), doc.document.view_url, name);
      assert.equal(viewer.attr('data-view-url'), doc.document.view_url, name);
      assert.ok(viewer.attr('title'), name);
      assert.equal(page.one('#viewerPage'), null, `${name}: a text has no pages`);
    } else {
      assert.equal(viewer, null, name);
      assert.equal(page.all('iframe').length, 0, name);
    }
    const note = page.one('.viewer-panel p#viewerMark');
    if (doc.document.view_media_type) {
      assert.deepEqual([note?.attr('role'), note?.attr('aria-live'), note?.text], ['status', 'polite', ''], name);
    } else {
      assert.equal(note, null, `${name}: nothing to mark where nothing is shown`);
    }
    assert.deepEqual(page.all('.viewer-panel .viewer-note').map(note => note.text), doc.document.converted ? [app.CONVERTED_NOTE] : [], name);
    // the download of the original (C6): a PDF or a text as it was; a Word document's is the PDF the coding review read,
    // and its Word file only behind a warning, as ?format=original - the Word file of one not converted yet too
    const download = page.one('#downloadOriginal');
    const word = page.one('#downloadWord');
    if (!doc.document.original_url) assert.deepEqual([download, word], [null, null], name);
    else if (doc.document.media_type !== DOCX) {
      assert.deepEqual([download.attr('href'), download.text, download.attr('download')], [doc.document.original_url, 'Download original', ''], name);
      assert.equal(word, null, name);
    } else {
      if (doc.document.converted) assert.deepEqual([download.attr('href'), download.text, download.attr('download')], [doc.document.original_url, 'Download PDF', ''], name);
      else assert.equal(download, null, name);
      assert.deepEqual([word.tag, word.attr('href'), word.attr('data-word-original'), word.text],
        ['button', null, `${doc.document.original_url}?format=original`, 'Download the Word file'], name);
    }
    // every quote, once, in the quotes panel, named by its code and its line
    const quotes = page.all('#quotesPanel .quote[data-code][data-line][data-page]');
    assert.deepEqual(quotes.map(quote => [quote.attr('data-code'), quote.attr('data-line'), quote.attr('data-page')]),
      doc.codes.flatMap(code => code.quotes.map(quote => [code.code, code.line, quote.page === null ? '' : String(quote.page)])), name);
    // no element id is drawn twice, whatever the codes repeat
    const ids = page.all('[id]').map(element => element.attr('id'));
    assert.deepEqual(ids.filter((id, index) => ids.indexOf(id) !== index), [], `${name}: repeated ids`);
    assert.equal(page.all('.quote').length, quotes.length, `${name}: .quote is the quotes panel's only`);
    // progress: the phase and the three steps (an earlier review has none)
    const panel = page.one('section.progress-panel[data-phase]');
    assert.equal(panel.attr('data-phase'), doc.progress.phase, name);
    assert.deepEqual(panel.all('.progress-step[data-step][data-state]').map(step => step.attr('data-step')),
      doc.progress.phase === 'earlier' ? [] : ['reading', 'checking', 'finished'], name);
    assert.equal(panel.all('ol.progress-steps').length, doc.progress.phase === 'earlier' ? 0 : 1, name);
    // questions, when asked, with a labelled answer field each
    const questions = page.one('section#questionsPanel');
    assert.equal(Boolean(questions), doc.questions.length > 0, name);
    if (questions) {
      assert.equal(questions.one('h2').text, 'Questions for you');
      assert.deepEqual(questions.all('.question-row[data-question]').map(row => row.attr('data-question')), doc.questions.map(question => question.id), name);
      for (const row of questions.all('.question-row')) {
        const field = row.one('textarea');
        assert.ok(field, name);
        assert.equal(row.one('label').attr('for'), field.attr('id'), name);
      }
      assert.ok(page.one('#sendAnswers'), name);
    }
    // the codes, in the served order, each named by its line, with the hooks the walk reads
    const rows = page.all('ol#codesList > li.code-row[data-code][data-line][data-status]');
    assert.deepEqual(rows.map(row => [row.attr('data-code'), row.attr('data-line'), row.attr('data-status')]),
      doc.codes.map(code => [code.code, code.line, code.status]), name);
    rows.forEach((row, index) => {
      const code = doc.codes[index];
      assert.equal(row.attr('id'), `code-${code.line}`, `${name} ${code.line}`);
      for (const hook of ['.code-number', '.code-units', '.code-modifiers', '.status[data-status]', '.code-reason', '.code-check', '.code-quotes']) {
        assert.ok(row.one(hook), `${name} ${code.line} ${hook}`);
      }
      assert.equal(row.one('.code-number').text, code.code);
      assert.equal(row.one('.code-units').text, code.units === null ? 'Units not given' : code.units === 1 ? '1 unit' : `${code.units} units`);
      assert.equal(row.one('.code-reason').text, code.reason);
      // the verdict and its reason; without a verdict, the server's own sentence alone, as given
      const check = row.one('.code-check').text;
      if (code.second_check.agrees === null) assert.equal(check, code.second_check.reason, `${name} ${code.code}`);
      else {
        assert.match(check, code.second_check.agrees ? /^Second check: agrees\./ : /^Second check: disagrees\./);
        assert.ok(check.endsWith(code.second_check.reason));
      }
    });
    // documentation notes once the review is done; earlier answers under the questions
    assert.equal(Boolean(page.one('section#notesPanel')), doc.progress.phase === 'done' || doc.notes.length > 0, name);
    assert.deepEqual(page.all('#notesPanel .notes-list li').map(item => item.text), doc.notes, name);
    assert.deepEqual(page.all('#answersPanel .answer-item .answer-text').map(item => item.text), doc.answers.map(item => item.answer), name);
    // the export button: whenever the server allows a download, or there are earlier downloads to list
    assert.equal(page.all('[data-action="export"]').length > 0, doc.readiness.draft === true || doc.readiness.approved === true || doc.reports.length > 0, name);
  }
});

test('only the actions in allowed_actions are drawn, as button[data-decision][data-code][data-line], and only for a reviewer', () => {
  let drawn = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const page = dom(render(doc));
    for (const code of doc.codes) {
      const row = page.one(`li.code-row[data-line="${code.line}"]`);
      const buttons = row.all('button[data-decision][data-code][data-line]');
      assert.deepEqual(buttons.map(button => [button.attr('data-decision'), button.attr('data-code'), button.attr('data-line'), button.attr('id')]),
        code.allowed_actions.map(action => [action, code.code, code.line, `act-${code.line}-${action}`]), `${name} ${code.line}`);
      drawn += buttons.length;
      for (const button of buttons) assert.equal(button.text.trim(), { approve: 'Approve', reject: 'Reject', revoke: 'Undo' }[button.attr('data-decision')]);
    }
    // a member who may not review gets none, whatever the server lists
    const viewer = clone(doc);
    viewer.permissions.can_review = false;
    assert.equal(dom(render(viewer)).all('button[data-decision]').length, 0, name);
  }
  assert.ok(drawn >= 18, drawn);
  // an action the page does not know is never drawn, and the order is fixed
  const code = { line: 'L1', code: '45385', status: 'ready', allowed_actions: ['confirm', 'reject', 'approve', 'reinstate'] };
  const reviewer = (item, extra = {}) => ({ permissions: { can_review: true }, round: { number: 1, trigger: 'upload', finished_at: null }, codes: [item], ...extra });
  assert.deepEqual(app.allowedActions(code, reviewer(code)), ['approve', 'reject']);
  assert.deepEqual(app.allowedActions(code, reviewer(code, { permissions: {} })), []);
  // a decision names a line of the coding review the page shows: without either, the page offers none
  for (const line of [undefined, null, '', 'X1', 'L0', 'l1', 'L1 ', 'L1000', 7]) {
    const item = { ...code, line };
    assert.deepEqual(app.allowedActions(item, reviewer(item)), [], String(line));
  }
  for (const round of [null, { number: 0 }, { number: '1' }, {}]) assert.deepEqual(app.allowedActions(code, reviewer(code, { round })), [], JSON.stringify(round));
  // and a line the document names on two rows, or not at all, is not one the page can decide
  assert.deepEqual(app.allowedActions(code, reviewer(code, { codes: [code, { ...code, code: '45380' }] })), []);
  assert.deepEqual(app.allowedActions(code, reviewer(code, { codes: [] })), []);
});

test('the badge says Approved or Rejected once a decision stands, with who and when, and Undo offered', () => {
  const page = dom(render(fixture('encounter-reviewed.json')));
  const badges = page.all('li.code-row .status[data-status]').map(item => [item.attr('data-status'), item.text]);
  assert.deepEqual(badges, [['approved', 'Approved'], ['approved', 'Approved'], ['rejected', 'Rejected']]);
  assert.deepEqual(page.all('li.code-row').map(row => [row.attr('data-status'), row.attr('data-decision')]), [['ready', 'approve'], ['ready', 'approve'], ['ready', 'reject']]);
  const rejected = page.one('li.code-row[data-code="45380"] .code-decision');
  assert.match(rejected.text, /^Rejected by Reviewer20 Nov 2026, 07:53 UTC · synthetic review, not clinical approvalNote: The practice codes/);
  // the open statuses: their own labels, a hint where nothing can be approved yet
  const ready = dom(render(fixture('encounter-ready.json')));
  assert.equal(ready.one('li.code-row[data-code="43251"] .status').text, 'Not supported');
  assert.match(ready.one('li.code-row[data-code="43251"] .code-hint').text, /cannot be approved/);
  const asking = dom(render(fixture('encounter-awaiting-answer.json')));
  assert.equal(asking.one('li.code-row[data-code="45385"] .status').text, 'Needs your answer');
  assert.match(asking.one('li.code-row[data-code="45385"] .code-question').text, /How was the 12 mm descending colon polyp removed/);
  const review = dom(render(fixture('encounter-needs-review.json')));
  const disputed = review.one('li.code-row[data-code="45380"]');
  assert.deepEqual([disputed.one('.status').attr('class'), disputed.one('.status').text], ['status amber-outline', 'Needs your review']);
  assert.equal(disputed.one('.code-check').attr('data-check'), 'disagrees');
  assert.equal(disputed.one('.code-modifiers').text, 'Modifier 59');
  assert.equal(review.one('li.code-row[data-code="43239"] .code-modifiers').text, 'No modifier');
  assert.equal(app.modifiersLabel({ modifiers: ['59', 'XS'] }), 'Modifiers 59, XS');
  assert.equal(app.unitsLabel(2), '2 units');
  assert.equal(app.secondCheck({ second_check: { agrees: null, reason: '' } }).label, 'Second check: no verdict.');
});

test('modifiers the coding review did not give read "Modifiers not given", never "No modifier"', async () => {
  assert.equal(app.modifiersLabel({ modifiers: [] }), 'No modifier', 'an empty list is the server saying there is none');
  assert.equal(app.modifiersLabel({ modifiers: ['XS'] }), 'Modifier XS');
  assert.equal(app.modifiersLabel({ modifiers: ['59', 'XS'] }), 'Modifiers 59, XS');
  // the contract's null, or anything that is not a list of modifiers, is not a statement that there is none
  for (const modifiers of [null, undefined, '25', [25], ['25', 7], [''], [null], {}]) {
    assert.equal(app.modifiersLabel({ modifiers }), 'Modifiers not given', JSON.stringify(modifiers));
  }
  assert.equal(app.MODIFIERS_NOT_GIVEN, 'Modifiers not given');
  const doc = clone(fixture('encounter-same-code.json'));
  doc.codes[1].modifiers = null;
  const row = dom(render(doc)).one('li.code-row[data-line="L2"]');
  assert.deepEqual([row.one('.code-modifiers').text, row.attr('data-modifiers')], ['Modifiers not given', '']);
  await withPage({}, async ({ element }) => {
    Object.assign(app.state, { session: fixture('session.json'), doc, route: null });
    await app.handleDecision('approve', 'L2', fakeElement());
    assert.equal(element('#reviewLine').textContent, '1 unit · Modifiers not given');
  });
});

test('units the coding review did not give read "Units not given", never a number or nothing', () => {
  assert.equal(app.unitsLabel(1), '1 unit');
  assert.equal(app.unitsLabel(3), '3 units');
  // 0 is a number the coding review wrote (it writes 0 on a code it does not support): shown as written, never as not
  // given (the server serves it as 0; the exports print "units 0")
  assert.equal(app.unitsLabel(0), '0 units');
  const zero = clone(fixture('encounter-ready.json'));
  zero.codes.find(code => code.line === 'L4').units = 0;
  const zeroRow = dom(render(zero)).one('li.code-row[data-line="L4"]');
  assert.deepEqual([zeroRow.one('.code-units').text, zeroRow.attr('data-units')], ['0 units', '0']);
  // the contract's units are a whole number or null; anything else is not a count the page can state
  for (const value of [null, undefined, -1, 1.5, '2', NaN]) assert.equal(app.unitsLabel(value), 'Units not given', String(value));
  assert.equal(app.UNITS_NOT_GIVEN, 'Units not given');
  const doc = fixture('encounter-same-code.json');
  const row = dom(render(doc)).one('li.code-row[data-line="M1"]');
  assert.equal(doc.codes.find(code => code.line === 'M1').units, null);
  assert.deepEqual([row.one('.code-units').text, row.attr('data-units')], ['Units not given', '']);
  assert.equal(dom(render(doc)).one('li.code-row[data-line="L3"] .code-units').text, '1 unit');
});

test('quote page links: a quote names its page; the browser\'s own viewer opens at view_url#page=N; a text quote has no page', () => {
  const view = `/api/encounters/${UUID}/original?view=1`;
  assert.equal(app.viewerUrl(view, 3), `${view}#page=3`);
  assert.equal(app.viewerUrl(view, null), view);
  assert.equal(app.viewerUrl(view, 0), view);
  assert.equal(app.viewerUrl(view, 2.5), view);
  assert.equal(app.viewerUrl('javascript:alert(1)', 2), '');
  assert.deepEqual(app.quotesOf({ quotes: [{ text: ' A quote. ', page: 2 }, { text: 'B', page: -1 }, { text: '', page: 1 }, { text: 'C', page: '3' }] }),
    [{ text: 'A quote.', page: 2 }, { text: 'B', page: null }, { text: 'C', page: null }]);
  // the quotes panel and each row's own quotes name the same passages
  const doc = fixture('encounter-needs-review.json');
  const page = dom(render(doc));
  const panel = page.all('#quotesPanel .quote').map(quote => quote.attr('data-quote'));
  const rows = page.all('li.code-row .code-quote').map(quote => quote.attr('data-quote'));
  assert.deepEqual(panel, rows);
  assert.deepEqual(panel.slice(0, 3), ['L1#0', 'L1#1', 'L2#0']);
  assert.deepEqual(page.all('li.code-row .code-quote').map(quote => quote.attr('data-view-page')), ['1', '1', '2', '2', '2']);
  assert.equal(page.one('#quotesPanel .quote').one('.quote-page').text, 'Page 1');
  assert.equal(page.one('#quotesPanel .quotes-lead').text, 'Each code rests on these passages. Choose one to open its page and mark its words there.');
  // a text document's quotes carry no page, and the panel says they are marked in the document
  const text = dom(render(fixture('encounter-awaiting-answer.json')));
  assert.deepEqual(text.all('#quotesPanel .quote').map(quote => quote.attr('data-page')), ['', '', '']);
  assert.equal(text.one('#quotesPanel .quotes-lead').text, 'Each code rests on these passages. Choose one to mark it in the document.');
});

test('the viewer follows document.view_media_type, never media_type: a PDF or a text in the page, else only the download', () => {
  const base = { view_url: `/api/encounters/${UUID}/original?view=1`, original_url: `/api/encounters/${UUID}/original`, kind: 'upload', converted: false };
  assert.equal(app.viewerKind({ ...base, media_type: 'application/pdf', view_media_type: 'application/pdf' }), 'pdf');
  assert.equal(app.viewerKind({ ...base, media_type: 'text/plain', view_media_type: 'text/plain' }), 'text');
  assert.equal(app.viewerKind({ ...base, kind: 'paste', media_type: 'text/plain', view_media_type: 'text/plain' }), 'text');
  assert.equal(app.viewerKind({ ...base, media_type: DOCX, view_media_type: 'application/pdf', converted: true }), 'pdf', 'a Word file viewed as its PDF');
  // the type of the original decides nothing: no view type is no viewer, whatever was uploaded
  for (const media of ['application/pdf', 'text/plain', DOCX]) {
    assert.equal(app.viewerKind({ ...base, media_type: media, view_media_type: null }), 'none', media);
    assert.equal(app.viewerKind({ ...base, media_type: media }), 'none', `${media} without view_media_type`);
  }
  for (const other of ['image/png', 'text/plain; charset=utf-8', 'APPLICATION/PDF', DOCX, 'constructor', 7]) {
    assert.equal(app.viewerKind({ ...base, view_media_type: other }), 'none', String(other));
  }
  assert.equal(app.viewerKind({ ...base, view_url: null, view_media_type: 'application/pdf' }), 'none');
  assert.equal(app.viewerKind({ ...base, view_url: 'https://evil.test/x', view_media_type: 'application/pdf' }), 'none');
  // a PDF uploaded and no view type served: no viewer at all, only the download of the original
  const unviewable = clone(fixture('encounter-ready.json'));
  unviewable.document.view_media_type = null;
  const page = dom(render(unviewable));
  assert.equal(page.all('iframe').length, 0);
  assert.equal(page.one('#documentViewer'), null);
  assert.equal(page.one('.viewer-empty'), null, 'nothing drawn where the viewer would be');
  assert.equal(page.one('section.viewer-panel').attr('class'), 'viewer-panel no-view');
  assert.deepEqual([page.one('#downloadOriginal').attr('href'), page.one('#downloadOriginal').text], [unviewable.document.original_url, 'Download original']);
  const gone = clone(unviewable);
  gone.document.original_url = 'javascript:alert(1)';
  assert.equal(dom(render(gone)).one('#downloadOriginal'), null);
  // a passage promises to be shown only where a viewer can show it
  assert.equal(page.one('#quotesPanel .quote').attr('title'), null);
  assert.equal(page.one('.code-quote').attr('title'), null);
  assert.match(page.one('#quotesPanel .quotes-lead').text, /^Each code rests on these passages of the original document\.$/);
  const viewed = dom(render(fixture('encounter-ready.json')));
  assert.equal(viewed.one('#quotesPanel .quote').attr('title'), 'Show this passage in the document');
  assert.equal(viewed.one('section.viewer-panel').attr('class'), 'viewer-panel');
  // the earlier review of a Word file the earlier version never converted: no viewer, and the Word file is offered only
  // behind its warning (C6)
  const earlier = dom(render(fixture('encounter-earlier.json')));
  assert.equal(earlier.all('iframe').length, 0);
  assert.equal(earlier.one('#downloadOriginal'), null);
  assert.equal(earlier.one('#downloadWord').attr('data-word-original'), `${fixture('encounter-earlier.json').document.original_url}?format=original`);
});

test('a Word document is viewed as the PDF the coding review read, with the note saying so under the viewer', () => {
  const doc = fixture('encounter-word.json');
  assert.equal(app.CONVERTED_NOTE, 'Shown as the PDF the coding review read (converted from the Word file).');
  const panel = dom(app.viewerPanel(doc)).one('section.viewer-panel');
  const children = panel.children.filter(child => typeof child !== 'string').map(child => child.attr('class') || child.attr('id'));
  assert.deepEqual(children, ['viewer-toolbar', 'viewer-frame pdf-viewer', 'viewer-mark', 'viewer-note', 'viewer-bottom'],
    'the notes sit under the viewer: what a chosen quote marked, then that the PDF is a converted one');
  assert.equal(panel.one('div#documentViewer').attr('data-view-url'), doc.document.view_url);
  assert.equal(panel.all('iframe').length, 0);
  assert.equal(panel.one('.viewer-note').text, app.CONVERTED_NOTE);
  assert.equal(panel.one('.viewer-name').text, 'synthetic-colonoscopy-report.docx');
  // C6: the download is the PDF the coding review read (the server's default for a Word document), and the Word file
  // itself is a separate choice behind a warning
  assert.deepEqual([panel.one('#downloadOriginal').attr('href'), panel.one('#downloadOriginal').text], [doc.document.original_url, 'Download PDF']);
  assert.equal(panel.one('#downloadWord').attr('data-word-original'), `${doc.document.original_url}?format=original`);
  // its quotes open their pages: the PDF's pages are the pages the quotes name
  const page = dom(render(doc));
  assert.match(page.one('#quotesPanel .quotes-lead').text, /open its page and mark its words/);
  assert.deepEqual(page.all('#quotesPanel .quote').map(quote => quote.attr('data-page')), ['2', '1', '1', '2']);
  // the note only for a converted PDF: not for a PDF or a text uploaded as such, not without a view
  for (const name of ['encounter-ready.json', 'encounter-awaiting-answer.json', 'encounter-no-codes.json', 'encounter-earlier.json']) {
    assert.equal(dom(render(fixture(name))).one('.viewer-note'), null, name);
  }
  const unviewed = clone(doc);
  Object.assign(unviewed.document, { view_url: null, view_media_type: null });
  assert.equal(dom(render(unviewed)).one('.viewer-note'), null, 'no note where nothing is shown');
  const flagged = clone(fixture('encounter-awaiting-answer.json'));
  flagged.document.converted = true;
  assert.equal(dom(render(flagged)).one('.viewer-note'), null, 'a text view is never called a converted PDF');
  // a change of the converted flag redraws the viewer
  const plain = clone(doc);
  plain.document.converted = false;
  assert.notEqual(app.viewerKey(plain), app.viewerKey(doc));
});

test('the second check without a verdict shows the server\'s own sentence as given', () => {
  const doc = fixture('encounter-word.json');
  const page = dom(render(doc));
  const check = code => page.one(`li.code-row[data-code="${code}"] .code-check`);
  assert.deepEqual([check('45385').attr('data-check'), check('45385').text], ['agrees', 'Second check: agrees. Removal by snare is documented on page 2, and the colonoscope reached the cecum.']);
  assert.deepEqual([check('45380').attr('data-check'), check('45380').text, check('45380').one('strong').text], ['none', NOT_CHECKED, NOT_CHECKED]);
  assert.deepEqual([check('45381').attr('data-check'), check('45381').text], ['none', ADDED_WITH_STATUS[0]]);
  assert.deepEqual(app.secondCheck({ second_check: { agrees: null, reason: ` ${ADDED_BY_CHECK} ` } }), { verdict: 'none', label: ADDED_BY_CHECK, reason: '' });
  // a verdict with no reason, or no verdict and no sentence: the verdict alone
  assert.deepEqual(app.secondCheck({ second_check: { agrees: false, reason: null } }), { verdict: 'disagrees', label: 'Second check: disagrees.', reason: '' });
  assert.deepEqual(app.secondCheck({ second_check: { agrees: null, reason: null } }), { verdict: 'none', label: 'Second check: no verdict.', reason: '' });
  assert.deepEqual(app.secondCheck({}), { verdict: 'none', label: 'Second check: no verdict.', reason: '' });
  assert.equal(app.tallyText(doc), '1 ready for approval · 2 need your review');
});

// A viewer element as the browser wiring holds it: what it is given to show, and the data it is marked with.
function viewerElement(extra = {}) {
  return fakeElement({ children: [], replaceChildren(...nodes) { this.children = nodes; }, scrollIntoView() {}, removeEventListener() {},
    scrollTo(options) { this.scrolled = options; }, ...extra });
}

// One page of a PDF as the library serves it: its text items, read once each.
function pdfPage(strings, reads) {
  return { getTextContent: async () => { reads.push(strings); return { items: strings.map(str => ({ str, hasEOL: false })) }; } };
}

test('where the PDF library cannot run, the browser\'s own viewer is framed and opens a quoted page, saying marking needs a newer browser', async () => {
  const word = fixture('encounter-word.json');
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  const saved = { viewer: app.state.viewer, pdfLibrary: app.state.pdfLibrary };
  try {
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      Object.assign(app.state, { doc: word, route: null, pdfLibrary: null });
      // no IntersectionObserver here: the browser lacks what marking needs, and the library is never asked for
      assert.equal(app.pdfCapable(), false);
      const loads = [];
      const load = app.PDF_IMPORT.load;
      app.PDF_IMPORT.load = specifier => { loads.push(specifier); return new Promise(() => {}); };
      try {
        app.mountViewer(word);
        await settle(() => app.state.viewer?.mode === 'frame');
      } finally {
        app.PDF_IMPORT.load = load;
      }
      const viewer = app.state.viewer;
      assert.deepEqual(loads, [], 'the library is not downloaded');
      assert.equal(viewer.mode, 'frame');
      assert.equal(element.dataset.mode, 'frame');
      assert.deepEqual([viewer.fallback, element.dataset.fallback], ['browser', 'browser'], 'the browser is why');
      assert.deepEqual(element.children, [viewer.frame], 'the frame alone, in the viewer\'s place');
      assert.equal(viewer.frame.src, word.document.view_url);
      assert.equal(viewer.frame.className, 'viewer-fallback');
      assert.equal(viewer.frame.title, 'Original document: synthetic-colonoscopy-report.docx');
      assert.equal(find('#viewerMark').textContent, '', 'nothing said before a quote is chosen');
      // a quote on another page than the frame was opened at gets a new frame at its page: the browser's viewer opens
      // #page=N only as its frame loads, so changing the address of the frame it has would move nothing
      const first = viewer.frame;
      app.showQuote('L2#0');
      assert.notEqual(viewer.frame, first, 'a new frame element');
      assert.deepEqual(element.children, [viewer.frame]);
      assert.equal(viewer.frame.src, `${word.document.view_url}#page=1`);
      assert.equal(first.src, word.document.view_url, 'the old frame was not moved, it was replaced');
      assert.equal(app.state.selectedQuote, 'L2#0');
      // the note says why and names the quote's page, never what the frame shows
      assert.equal(find('#viewerMark').textContent, 'Marking needs a newer browser. The quote is on page 1.');
      assert.ok(find('#viewerMark').classList.contains('is-missing'));
      assert.equal(element.dataset.marked, '', 'nothing marked');
      // the same page again: the frame is kept, not reloaded
      const atOne = viewer.frame;
      app.showQuote('L1#1');
      assert.equal(viewer.frame, atOne, 'the same page keeps its frame');
      app.showQuote('M1#0');
      assert.notEqual(viewer.frame, atOne);
      assert.equal(viewer.frame.src, `${word.document.view_url}#page=2`);
      assert.equal(find('#viewerMark').textContent, 'Marking needs a newer browser. The quote is on page 2.');
      const atTwo = viewer.frame;
      app.showQuote('L9#0');
      app.showQuote('45381#0');
      assert.equal(app.state.selectedQuote, 'M1#0', 'a quote the page does not hold changes nothing');
      assert.equal(viewer.frame, atTwo);
      // a quote with no page keeps the frame where it is, and the note says why alone
      const pageless = clone(word);
      pageless.codes[1].quotes[0].page = null;
      app.state.doc = pageless;
      app.showQuote('L2#0');
      assert.equal(viewer.frame, atTwo, 'no page: no new frame');
      assert.equal(find('#viewerMark').textContent, 'Marking needs a newer browser.');
      app.closeViewer();
      assert.equal(app.state.viewer, null);
      assert.equal(viewer.mode, 'closed');
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('the browser\'s own viewer says why it is shown: the browser, the library, a document the library cannot draw, a stalled download, a failed download', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  // the five reasons, word for word; a reason the page does not name is read as the document's, never as the browser's
  assert.deepEqual(app.FRAME_REASONS, {
    browser: 'Marking needs a newer browser.',
    library: 'The marking tool did not work here, so nothing is marked.',
    document: 'This document cannot be drawn here, so nothing is marked.',
    slow: 'The document took too long to load here, so nothing is marked.',
    download: 'The document could not be downloaded for marking, so nothing is marked.',
  });
  const cases = [['browser', 'browser'], ['library', 'library'], ['document', 'document'], ['slow', 'slow'], ['download', 'download'],
    ['toString', 'document'], [undefined, 'document']];
  try {
    for (const [reason, kept] of cases) {
      const said = app.FRAME_REASONS[kept];
      const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
      await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
        Object.assign(app.state, { doc: word, route: null });
        // a quote was chosen while the document was still opening
        const viewer = { element, view: word.document.view_url, name: 'x', mode: 'loading', pages: [], texts: new Map(), prepared: new Map(), mark: null,
          pending: { quote: { text: 'A 7 mm sessile polyp', page: 2 }, key: 'M1#0' }, chosen: null, markSerial: 0, reveal: 0, frame: null, framePage: null,
          fallback: '', task: null, worker: null };
        app.state.viewer = viewer;
        app.fallbackViewer(viewer, reason);
        assert.deepEqual([viewer.mode, viewer.fallback, element.dataset.mode, element.dataset.fallback], ['frame', kept, 'frame', kept], String(reason));
        assert.equal(viewer.frame.src, `${word.document.view_url}#page=2`, 'the page of the quote that was waiting');
        assert.equal(viewer.framePage, 2);
        assert.equal(find('#viewerMark').textContent, `${said} The quote is on page 2.`);
        assert.ok(find('#viewerMark').classList.contains('is-missing'));
        // a quote chosen in the frame says the same of its own page, in a new frame there
        app.showQuote('L2#0');
        assert.equal(viewer.frame.src, `${word.document.view_url}#page=1`);
        assert.equal(find('#viewerMark').textContent, `${said} The quote is on page 1.`);
        // once framed, the reason stays: a second failure does not change what the note says
        app.fallbackViewer(viewer, 'browser');
        assert.equal(viewer.fallback, kept);
        app.closeViewer();
      });
    }
  } finally {
    Object.assign(app.state, saved);
  }
});

// A viewer of the PDF of `doc` as the browser wiring holds it, its pages built from `pages` (each page's text items).
function pdfViewer(doc, element, pages, reads, extra = {}) {
  const pageAt = number => ({ number, proxy: pdfPage(pages[number - 1], reads), element: fakeElement({ offsetTop: 400 * (number - 1), querySelector: () => null, replaceChildren() {} }),
    drawn: '', layer: null, painted: [], serial: 0 });
  return { element, view: doc.document.view_url, name: 'x', mode: 'pdf', pages: pages.map((_, index) => pageAt(index + 1)), texts: new Map(),
    prepared: new Map(), mark: null, pending: null, chosen: null, markSerial: 0, reveal: 0, frame: null, framePage: null, fallback: '', zoom: app.ZOOM_FIT,
    task: null, worker: null, ...extra };
}

test('a quote chosen in the PDF viewer reads its page and the next, is located, and says what was marked', async () => {
  const word = fixture('encounter-word.json');
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  const reads = [];
  // the synthetic Word document's two pages, as its PDF's text items (dev_preview_server.cjs SYNTHETIC_DOCUMENTS)
  const pages = preview.SYNTHETIC_DOCUMENTS['synthetic-colonoscopy-report.docx'].pages;
  const saved = { viewer: app.state.viewer };
  try {
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      Object.assign(app.state, { doc: word, route: null });
      const viewer = pdfViewer(word, element, pages, reads, { mode: 'loading', pages: [] });
      app.state.viewer = viewer;
      // while the PDF is still opening, the choice waits
      app.showQuote('L2#0');
      assert.deepEqual(viewer.pending, { quote: { text: 'Two biopsies were taken from the cecum with cold forceps.', page: 1 }, key: 'L2#0' });
      assert.deepEqual(viewer.chosen, viewer.pending, 'the quote being chosen is kept');
      viewer.pending = null;
      Object.assign(viewer, { mode: 'pdf', pages: pdfViewer(word, element, pages, reads).pages });
      const result = await app.showQuote('L2#0');
      assert.deepEqual(reads, pages, 'the quote\'s page and the next are read, in order');
      assert.equal(result.status, 'marked');
      assert.deepEqual([result.scope, result.count, result.pages, result.caseBlind], ['page', 1, [1], false]);
      assert.deepEqual(viewer.mark.key, 'L2#0');
      assert.equal(find('#viewerMark').textContent, 'Marked on page 1.');
      assert.equal(find('#viewerMark').classList.contains('is-missing'), false);
      assert.deepEqual([element.dataset.marked, element.dataset.markStatus, element.dataset.markPages, element.dataset.markCount], ['L2#0', 'marked', '1', '1']);
      assert.deepEqual(element.scrolled, { top: 0, behavior: 'smooth' }, 'the page is scrolled to');
      // each page's text is read and prepared once for the document: a second quote of the same pages reads nothing
      const prepared = [...viewer.prepared.entries()];
      await app.showQuote('M1#0');
      assert.equal(reads.length, 2);
      assert.ok(prepared.length === 2 && prepared.every(([number, text]) => viewer.prepared.get(number) === text), 'the same prepared texts, not made again');
      assert.equal(find('#viewerMark').textContent, 'Marked on page 2.');
      assert.equal(element.scrolled.top, 400 - app.PDF_VIEW.gap);
      // a quote whose words are not on its page, which has text: nothing marked, the page still opened, and the note says
      // what was searched
      const missing = clone(word);
      missing.codes[0].quotes[0] = { text: 'A passage that is in no page of this document.', page: 2 };
      app.state.doc = missing;
      const none = await app.showQuote('L1#0');
      assert.deepEqual([none.status, none.count, none.pages, none.textless], ['not_found', 0, [], false]);
      assert.equal(find('#viewerMark').textContent, 'The exact words were not found in the searchable text of page 2, so nothing is marked. Page 2 is shown.');
      assert.ok(find('#viewerMark').classList.contains('is-missing'));
      assert.deepEqual([element.dataset.marked, element.dataset.markStatus, element.dataset.markCount], ['L1#0', 'not_found', '0']);
      assert.equal(element.scrolled.top, 400 - app.PDF_VIEW.gap);
      // a newer coding review clears the mark, its note and the quote being chosen
      app.clearViewerMark();
      assert.equal(viewer.mark, null);
      assert.equal(viewer.chosen, null);
      assert.equal(find('#viewerMark').textContent, '');
      assert.equal(element.dataset.marked, '');
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('a page with no text to search says so, whatever the next page holds, and is told apart from words not found', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const scanned = [[], ['A 7 mm sessile polyp in the transverse colon was removed with a cold snare.']];
  try {
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      const doc = clone(word);
      doc.codes[0].quotes = [{ text: 'Two biopsies were taken from the cecum with cold forceps.', page: 1 }, { text: 'Two biopsies were taken', page: null }];
      Object.assign(app.state, { doc, route: null });
      app.state.viewer = pdfViewer(doc, element, scanned, []);
      const result = await app.showQuote('L1#0');
      assert.deepEqual([result.status, result.textless], ['not_found', true]);
      assert.equal(find('#viewerMark').textContent, 'Page 1 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 1 is shown.');
      assert.ok(find('#viewerMark').classList.contains('is-missing'));
      // with no page, every page is searched: one of them has text, so the words are said not to be found in it
      const pageless = await app.showQuote('L1#1');
      assert.deepEqual([pageless.status, pageless.textless], ['not_found', false]);
      assert.equal(find('#viewerMark').textContent, 'The exact words were not found in the searchable text of this document, so nothing is marked.');
    });
  } finally {
    Object.assign(app.state, saved);
  }
  // the rule itself: zero characters after folding, overprint copies left out
  const run = (texts, quote) => app.locateQuote(quote, texts);
  assert.equal(run([['   ', '\n'], ['words']], { text: 'words', page: 1 }).textless, true, 'white space only is no text');
  const drawnTwice = [{ str: 'BOLD', transform: [10, 0, 0, 10, 50, 700], hasEOL: false }, { str: 'BOLD', transform: [10, 0, 0, 10, 50.3, 700], hasEOL: false }];
  assert.equal(run([drawnTwice], { text: 'other', page: 1 }).textless, false, 'one copy of overprinted words is text');
  assert.equal(run([[]], { text: 'words', page: null }).textless, true, 'a document with no text at all');
  assert.equal(app.markNote(run([[]], { text: 'words', page: null })), 'This document has no text the viewer can search (it may be a scanned image), so nothing is marked.');
  assert.equal(run([[], ['x']], { text: 'words', page: null }).textless, false);
  assert.equal(run([['x']], { text: 'words', page: 1 }).textless, false);
  assert.equal(run([null], { text: 'words', page: 1 }).textless, false, 'a page not read is not said to have no text');
  assert.equal(app.markNote(run([['x']], { text: 'words', page: 1 })), 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.');
});

test('a read that changes the page never reloads the viewer: its mark stays, a new coding review clears it, a new document closes it - and a later round that serves another conversion of the Word file (I1-12) redraws it whole, while one that reads back the same conversion keeps it, its zoom and its place (I2-2)', async () => {
  const word = fixture('encounter-word.json');
  assert.match(word.document.view_conversion, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/, 'the fixture: a Word document whose view names its stored conversion');
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  const saved = { viewer: app.state.viewer };
  try {
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      const viewer = { element, view: word.document.view_url, name: 'x', mode: 'pdf', pages: [], texts: new Map(), markSerial: 0, reveal: 0, frame: null,
        mark: { key: 'L2#0', quote: word.codes[1].quotes[0], result: { status: 'marked', pages: [1], count: 1, marks: {} } }, pending: null, zoom: 3 };
      element.scrollTop = 2867;
      Object.assign(app.state, { doc: word, route: { name: 'doc', id: word.id }, docKey: 'drawn', viewerKey: app.viewerKey(word), selectedQuote: 'L2#0', viewer });
      find('#viewerMark').textContent = 'Marked on page 1.';
      // the same coding review, read again with a change (a decision recorded): the review column is redrawn, the viewer kept
      const decided = clone(word);
      decided.codes[1].reason = `${decided.codes[1].reason} Again.`;
      app.renderDocument(decided, false);
      assert.equal(app.state.viewer, viewer, 'the same viewer');
      assert.equal(viewer.mode, 'pdf');
      assert.equal(viewer.mark.key, 'L2#0', 'its mark stays');
      assert.equal(app.state.selectedQuote, 'L2#0');
      assert.equal(find('#viewerMark').textContent, 'Marked on page 1.');
      // a newer coding review of the same document whose view is still the same conversion (view_conversion unchanged:
      // a PDF's; a Word round that has not stored its own yet; or one that reads back the same stored file - I2-2, a
      // clean Word file's answers round, which records round 1's file on its own row): the passage chosen and its mark
      // go, the viewer stays, at the member's zoom and place
      const newer = clone(decided);
      newer.round = { ...newer.round, number: newer.round.number + 1 };
      assert.equal(app.viewerKey(newer), app.viewerKey(word), 'the round is not in the viewer key: the conversion is');
      app.renderDocument(newer, false);
      assert.equal(app.state.viewer, viewer);
      assert.deepEqual([viewer.mode, app.ZOOM_STEPS[viewer.zoom], element.scrollTop], ['pdf', 1.5, 2867], 'its zoom (150%) and place kept');
      assert.equal(viewer.mark, null);
      assert.equal(app.state.selectedQuote, '');
      assert.equal(find('#viewerMark').textContent, '');
      // I1-12 (viewer-0): that round converted the Word file again (C8) and serves its own conversion at the same
      // view_url - the detail names it (view_conversion) - so the page is redrawn whole: the viewer that drew the earlier
      // conversion is closed, and a new one asks for the view (with the kept copy's tag: 304 the same bytes, 200 new ones)
      const reconverted = clone(newer);
      reconverted.document.view_conversion = 'c9000000-0000-4000-8000-0000000000c2';
      assert.notEqual(app.viewerKey(reconverted), app.viewerKey(newer), 'the served conversion is in the viewer key');
      app.renderDocument(reconverted, false);
      assert.equal(viewer.mode, 'closed', 'the viewer of the earlier conversion is closed');
      assert.notEqual(app.state.viewer, viewer, 'a new viewer');
      assert.equal(app.state.viewerKey, app.viewerKey(reconverted));
      // a later read of that round (a decision recorded), and a later round reading its conversion back: the new viewer stays
      const drawn = app.state.viewer;
      const again = clone(reconverted);
      again.codes[1].reason = `${again.codes[1].reason} Once more.`;
      app.renderDocument(again, false);
      assert.equal(app.state.viewer, drawn, 'the same conversion: the same viewer');
      const reread = clone(again);
      reread.round = { ...reread.round, number: reread.round.number + 1 };
      app.renderDocument(reread, false);
      assert.equal(app.state.viewer, drawn, 'a later round that reads back the same conversion: the same viewer');
      // another view of the document (another viewer key): the page is redrawn whole and the viewer closed
      const other = clone(reread);
      other.document.converted = false;
      app.renderDocument(other, false);
      assert.equal(drawn?.mode ?? 'closed', 'closed', 'the old viewer is closed');
      assert.notEqual(app.state.viewer, drawn);
      // the key reads view_conversion as the server sends it: a UUID, or nothing
      for (const value of [null, undefined, '', '2', 2, 'c9000000-0000-4000-8000-0000000000c', `${word.document.view_conversion} `, [word.document.view_conversion],
        { id: word.document.view_conversion }]) {
        const odd = clone(word);
        odd.document.view_conversion = value;
        const none = clone(word);
        delete none.document.view_conversion;
        assert.equal(app.viewerKey(odd), app.viewerKey(none), String(value));
      }
      assert.notEqual(app.viewerKey(word), app.viewerKey({ ...word, document: { ...word.document, view_conversion: null } }), 'a UUID is a conversion');
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

// The PDF library as a test stands it in: a module whose PDFWorker takes the viewer's own worker as its port, and whose
// documents open as `open(task)` says (never, by default).
function fakeLibrary({ open = null } = {}) {
  const made = { workers: [], tasks: [] };
  const library = {
    GlobalWorkerOptions: { workerSrc: '' }, VerbosityLevel: { ERRORS: 0 }, AnnotationMode: { ENABLE: 2 },
    PDFWorker: class {
      constructor(options) {
        made.workers.push(this);
        this.options = options;
        this.destroyed = false;
        this.promise = Promise.resolve();
      }

      destroy() { this.destroyed = true; }
    },
    getDocument(options) {
      const task = { options, destroyed: false, destroy() { this.destroyed = true; return Promise.resolve(); } };
      task.promise = open ? open(task) : new Promise(() => {});
      task.promise.catch(() => {});
      made.tasks.push(task);
      return task;
    },
  };
  return { library, made };
}

// The viewer's own worker as a test stands it in (A4): made with `new Worker(address, {type: 'module'})`, it says it is
// ready with the message the library's worker sends ({sourceName: 'worker', targetName: 'main', action: 'ready'}), or
// fails ('error' or 'messageerror' before ready), or never answers, as FakeWorker.start says; emit() sends it anything.
class FakeWorker {
  constructor(url, options) {
    this.url = url;
    this.options = options;
    this.terminated = false;
    this.listeners = new Map();
    FakeWorker.made.push(this);
    const start = FakeWorker.start;
    if (start === 'ready') setImmediate(() => this.emit('message', { data: { sourceName: 'worker', targetName: 'main', action: 'ready', data: new Uint8Array() } }));
    else if (start !== 'never') setImmediate(() => this.emit(start, {}));
  }

  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(fn);
  }

  removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }

  emit(type, event = {}) {
    if (this.terminated) return;
    for (const fn of [...(this.listeners.get(type) || [])]) fn(event);
  }

  terminate() { this.terminated = true; }
}
FakeWorker.made = [];
FakeWorker.start = 'ready';

// A response to the viewer's own download of the document (A5): `status`, a body read in `chunks`, which breaks off after
// them where `breaks` is set.
function viewResponse({ status = 200, chunks = [Uint8Array.from([37, 80, 68, 70, 45]), Uint8Array.from([49, 46, 52])], breaks = false } = {}) {
  return {
    ok: status >= 200 && status < 300, status,
    body: { getReader() {
      let next = 0;
      return { read: async () => {
        if (next < chunks.length) return { done: false, value: chunks[next++] };
        if (breaks) throw new TypeError('network error');
        return { done: true, value: undefined };
      } };
    } },
  };
}

const PDF_MODULE = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.min.0123456789ab.mjs';
const PDF_WORKER = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.worker.min.0123456789ab.mjs';

// Runs fn on a page that can draw a PDF (the observers a browser has, and Worker), with the library's module loaded by
// `load`, the view's download answered by `download(url, init)` (a whole document by default) and the page's state kept
// apart. fn gets {element, loads, fetches} besides the page's own.
async function withPdfPage(load, fn, download = () => Promise.resolve(viewResponse())) {
  const saved = { viewer: app.state.viewer, pdfLibrary: app.state.pdfLibrary, pdfAttempt: app.state.pdfAttempt, framePassage: app.state.framePassage };
  const globals = { IntersectionObserver: global.IntersectionObserver, ResizeObserver: global.ResizeObserver, Worker: global.Worker };
  const loader = app.PDF_IMPORT.load;
  global.IntersectionObserver = function IntersectionObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  global.ResizeObserver = function ResizeObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  global.Worker = FakeWorker;
  FakeWorker.made = [];
  FakeWorker.start = 'ready';
  const loads = [];
  app.PDF_IMPORT.load = specifier => { loads.push(specifier); return load(specifier); };
  try {
    await withPage({}, async page => {
      global.document.body.dataset = { pdfModule: PDF_MODULE, pdfWorker: PDF_WORKER };
      global.location.href = 'http://studio.test/';
      const fetches = [];
      global.fetch = (url, init = {}) => {
        fetches.push({ url, init });
        return download(url, init);
      };
      Object.assign(app.state, { pdfLibrary: null, pdfAttempt: 0, viewer: null, pdfStarted: false });
      await fn({ ...page, loads, fetches });
      app.closeViewer();
    });
  } finally {
    app.PDF_IMPORT.load = loader;
    Object.assign(global, globals);
    Object.assign(app.state, saved);
  }
}

// Mounts the viewer of `doc` on a fresh #documentViewer and lets it run until `done(viewer)` holds.
async function mount(doc, find, done) {
  const element = viewerElement({ dataset: { viewUrl: doc.document.view_url } });
  find('#documentViewer');
  Object.assign(find('#documentViewer'), element);
  app.state.doc = doc;
  app.mountViewer(doc);
  const viewer = app.state.viewer;
  await settle(() => done(viewer));
  return viewer;
}

test('L1, A4: a library or its worker that does not start is the library\'s note, and the next document tries again at fresh addresses', async () => {
  const word = fixture('encounter-word.json');
  let answer = () => Promise.reject(new Error('404'));
  await withPdfPage(specifier => answer(specifier), async ({ element: find, loads, fetches }) => {
    // the module does not load: the frame, and the note blames neither the browser nor the document; no worker is made
    const first = await mount(word, find, viewer => viewer.mode === 'frame');
    assert.deepEqual([first.fallback, first.element.dataset.fallback], ['library', 'library']);
    assert.deepEqual(loads, [PDF_MODULE], 'the first attempt asks for the address the page names');
    assert.equal(FakeWorker.made.length, 0);
    assert.equal(app.state.pdfLibrary, null, 'a failure is not kept');
    app.showQuote('L2#0');
    assert.equal(find('#viewerMark').textContent, 'The marking tool did not work here, so nothing is marked. The quote is on page 1.');
    assert.equal(first.mode, 'frame', 'the document that failed stays framed with the library\'s note');
    // the next document: fresh addresses for the module and its worker (the browser keeps a failed module by its address
    // for the life of the page); the module loads, and the viewer starts its own worker there, which fails before it is
    // ready (an 'error' event: its script did not load) - the library's failure too
    const broken = fakeLibrary();
    answer = () => Promise.resolve(broken.library);
    FakeWorker.start = 'error';
    const second = await mount(word, find, viewer => viewer.mode === 'frame');
    assert.equal(second.fallback, 'library');
    assert.deepEqual(loads, [PDF_MODULE, `${PDF_MODULE}?attempt=2`]);
    assert.equal(broken.library.GlobalWorkerOptions.workerSrc, `${PDF_WORKER}?attempt=2`);
    assert.deepEqual(FakeWorker.made.map(made => [made.url, made.options]), [[`${PDF_WORKER}?attempt=2`, { type: 'module' }]], 'the viewer\'s own module worker');
    assert.equal(broken.made.workers.length, 0, 'the library is never handed a worker that did not start');
    await settle(() => FakeWorker.made[0].terminated);
    assert.ok(FakeWorker.made[0].terminated, 'the worker that failed is ended');
    assert.equal(app.state.pdfLibrary, null);
    assert.deepEqual(fetches, [], 'nothing is downloaded before the library and its worker start');
    // the third: a worker whose first message cannot be read ('messageerror') fails the same way
    FakeWorker.start = 'messageerror';
    const third = await mount(word, find, viewer => viewer.mode === 'frame');
    assert.equal(third.fallback, 'library');
    assert.equal(FakeWorker.made.at(-1).url, `${PDF_WORKER}?attempt=3`);
    // the fourth: the worker says it is ready, and only then is it handed to the library as its port; the viewer downloads
    // the document itself and gives the library its bytes
    const working = fakeLibrary();
    answer = () => Promise.resolve(working.library);
    FakeWorker.start = 'ready';
    const fourth = await mount(word, find, () => working.made.tasks.length === 1);
    assert.equal(fourth.mode, 'loading', 'opening the document');
    assert.deepEqual(loads.slice(3), [`${PDF_MODULE}?attempt=4`]);
    const own = FakeWorker.made.at(-1);
    assert.equal(own.url, `${PDF_WORKER}?attempt=4`);
    assert.deepEqual(working.made.workers.map(worker => worker.options), [{ port: own, verbosity: 0 }], 'the library takes the viewer\'s worker as its port');
    const { options } = working.made.tasks[0];
    assert.equal(options.worker, working.made.workers[0], 'the document is opened with that worker');
    assert.deepEqual([...options.data], [37, 80, 68, 70, 45, 49, 46, 52], 'the bytes the viewer downloaded, chunk after chunk');
    assert.equal(options.url, undefined, 'the library fetches nothing itself');
    assert.deepEqual(fetches.map(({ url, init }) => [url, init.credentials, init.cache, init.signal === fourth.download?.signal]), [[word.document.view_url, 'same-origin', 'no-store', true]]);
    const kept = app.state.pdfLibrary;
    assert.ok(kept);
    // a working library is kept for the next document, which starts its own worker again (one per document)
    const fifth = await mount(word, find, () => working.made.tasks.length === 2);
    assert.equal(loads.length, 4, 'loaded once while it works');
    assert.equal(app.state.pdfLibrary, kept);
    assert.equal(FakeWorker.made.length, 4, 'a worker for each document opened (none for the first)');
    await settle(() => own.terminated && working.made.workers[0].destroyed);
    assert.ok(own.terminated && working.made.workers[0].destroyed, 'the document closed: the library let go of its worker, and the worker is ended');
    // a worker that fails once it has started ('error' after ready) is the library not working: the frame, and the next
    // document tries again at fresh addresses
    FakeWorker.made.at(-1).emit('error', {});
    await settle(() => fifth.mode === 'frame');
    assert.deepEqual([fifth.mode, fifth.fallback], ['frame', 'library']);
    assert.equal(app.state.pdfLibrary, null);
    await mount(word, find, () => working.made.tasks.length === 3);
    assert.equal(loads.at(-1), `${PDF_MODULE}?attempt=5`);
    assert.equal(FakeWorker.made.at(-1).url, `${PDF_WORKER}?attempt=5`);
    app.closeViewer();
    await settle(() => FakeWorker.made.every(made => made.terminated));
    assert.ok(FakeWorker.made.every(made => made.terminated), 'no worker is left running');
  });
});

test('L1: loading the library and starting its worker has a time limit of 20 s, after which the next document tries again', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  let answer = () => new Promise(() => {});
  await withPdfPage(specifier => answer(specifier), async ({ element: find, loads }) => {
    // the module never arrives (a request held, never answered)
    const held = await mount(word, find, () => loads.length === 1);
    t.mock.timers.tick(19999);
    await settle(() => false);
    assert.equal(held.mode, 'loading', 'still opening before 20 s');
    t.mock.timers.tick(1);
    await settle(() => held.mode === 'frame');
    assert.deepEqual([held.mode, held.fallback], ['frame', 'library'], 'at 20 s: the frame, as the library not working');
    assert.equal(app.state.pdfLibrary, null, 'a timeout is not kept');
    // a worker that never says it is ready is given up the same way, and ended
    const stuck = fakeLibrary();
    answer = () => Promise.resolve(stuck.library);
    FakeWorker.start = 'never';
    const second = await mount(word, find, () => FakeWorker.made.length === 1);
    assert.equal(loads[1], `${PDF_MODULE}?attempt=2`);
    t.mock.timers.tick(20000);
    await settle(() => second.mode === 'frame');
    assert.deepEqual([second.mode, second.fallback], ['frame', 'library']);
    await settle(() => FakeWorker.made[0].terminated);
    assert.ok(FakeWorker.made[0].terminated, 'the worker given up is ended');
    assert.equal(stuck.made.workers.length, 0);
  });
});

test('a time limit counts only the time the page is visible: a hidden tab draws nothing', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const saved = global.document;
  const listeners = new Set();
  global.document = { hidden: true, addEventListener(type, fn) { if (type === 'visibilitychange') listeners.add(fn); }, removeEventListener(type, fn) { listeners.delete(fn); } };
  const show = hidden => { global.document.hidden = hidden; for (const fn of [...listeners]) fn(); };
  try {
    let outcome = 'waiting';
    app.withinLimit(new Promise(() => {}), 20000).catch(error => { outcome = error instanceof app.TimeLimit ? 'limit' : 'other'; });
    t.mock.timers.tick(60000);
    await settle(() => false);
    assert.equal(outcome, 'waiting', 'a minute hidden counts nothing');
    show(false);
    t.mock.timers.tick(15000);
    show(true);
    t.mock.timers.tick(60000);
    show(false);
    t.mock.timers.tick(4999);
    await settle(() => false);
    assert.equal(outcome, 'waiting', '15 s + 4.999 s visible');
    t.mock.timers.tick(1);
    await settle(() => outcome !== 'waiting');
    assert.equal(outcome, 'limit', 'at 20 s visible');
    assert.equal(listeners.size, 0, 'it stops listening once settled');
    // a wait that settles in time settles as it did, and stops its timer
    const value = await app.withinLimit(Promise.resolve(7), 20000);
    assert.equal(value, 7);
    await assert.rejects(app.withinLimit(Promise.reject(new Error('refused')), 20000), /refused/);
  } finally {
    global.document = saved;
  }
});

test('B3, A3, A5: a document with no page gives the frame; once it opened, the download\'s timer stops and the watchdog takes over', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  // a document the library opens with no page (a page tree that says /Count 0): the document's note
  const empty = fakeLibrary({ open: () => Promise.resolve({ numPages: 0, getPage: () => Promise.reject(new Error('none')) }) });
  await withPdfPage(() => Promise.resolve(empty.library), async ({ element: find }) => {
    const viewer = await mount(word, find, opened => opened.mode === 'frame');
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'document']);
  });
  for (const pages of [-1, 1.5, undefined]) {
    const odd = fakeLibrary({ open: () => Promise.resolve({ numPages: pages, getPage: () => new Promise(() => {}) }) });
    await withPdfPage(() => Promise.resolve(odd.library), async ({ element: find }) => {
      const viewer = await mount(word, find, opened => opened.mode === 'frame');
      assert.equal(viewer.fallback, 'document', String(pages));
    });
  }
  // the document opens, then its pages do not come (the worker stopped): the download's timer has stopped, so the frame
  // that follows at 20 s is the library's (the watchdog: nothing answered), never "took too long to load"
  const stopped = fakeLibrary({ open: () => Promise.resolve({ numPages: 3, getPage: () => new Promise(() => {}) }) });
  await withPdfPage(() => Promise.resolve(stopped.library), async ({ element: find }) => {
    const viewer = await mount(word, find, opened => stopped.made.tasks.length === 1 && opened.stallTimer === 0 && opened.watchdog);
    assert.equal(viewer.stallTimer, 0, 'the download\'s timer stopped once the document opened');
    t.mock.timers.tick(19999);
    await settle(() => false);
    assert.equal(viewer.mode, 'loading');
    t.mock.timers.tick(1);
    await settle(() => viewer.mode === 'frame');
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'library']);
  });
  // the same, but the worker keeps answering (busy decoding other pages' images): the pages are waited for, however long;
  // only once it has said nothing for 20 s is it taken as not working
  const busy = fakeLibrary({ open: () => Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }) });
  await withPdfPage(() => Promise.resolve(busy.library), async ({ element: find }) => {
    const viewer = await mount(word, find, opened => busy.made.tasks.length === 1 && opened.watchdog);
    const thread = FakeWorker.made.at(-1);
    for (let second = 5; second <= 60; second += 5) {
      t.mock.timers.tick(5000);
      thread.emit('message', { data: { sourceName: 'worker', targetName: 'main', action: 'commonobj' } });
      await settle(() => false);
      assert.equal(viewer.mode, 'loading', `${second} s, answering all along: busy is not broken`);
    }
    t.mock.timers.tick(19999);
    await settle(() => false);
    assert.equal(viewer.mode, 'loading', '19.999 s after its last answer');
    t.mock.timers.tick(1);
    await settle(() => viewer.mode === 'frame');
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'library'], '20 s after its last answer');
  });
});

test('B4, N4: a page\'s text read or drawing that does not settle within 20 s is the library\'s note, naming the quote being chosen', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const pages = preview.SYNTHETIC_DOCUMENTS['synthetic-colonoscopy-report.docx'].pages;
  try {
    for (const [what, read, reason] of [['a text read that never settles', () => new Promise(() => {}), 'library'],
      ['a text read that fails', () => Promise.reject(new Error('bad page')), 'document']]) {
      const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
      await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
        Object.assign(app.state, { doc: word, route: null });
        const viewer = pdfViewer(word, element, pages, []);
        // page 2's text was read and a quote on it marked; page 1's text cannot be read
        viewer.pages[0].proxy = { getTextContent: read };
        app.state.viewer = viewer;
        await app.showQuote('M1#0');
        assert.equal(find('#viewerMark').textContent, 'Marked on page 2.');
        app.showQuote('L2#0');
        await settle(() => viewer.mode === 'frame');
        t.mock.timers.tick(20000);
        await settle(() => viewer.mode === 'frame');
        assert.deepEqual([viewer.mode, viewer.fallback], ['frame', reason], what);
        // the quote being chosen is the one named: its page, not the page of the quote marked before
        assert.equal(viewer.frame.src, `${word.document.view_url}#page=1`, what);
        assert.equal(find('#viewerMark').textContent, `${app.FRAME_REASONS[reason]} The quote is on page 1.`, what);
        app.closeViewer();
      });
    }
    // a page's drawing that never settles: the library's note; one that fails: the document's
    for (const [render, reason] of [[() => ({ promise: new Promise(() => {}), cancel() {} }), 'library'],
      [() => ({ promise: Promise.reject(new Error('bad drawing')), cancel() {} }), 'document']]) {
      const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
      await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
        Object.assign(app.state, { doc: word, route: null });
        const viewer = pdfViewer(word, element, pages, [], { library: { AnnotationMode: { ENABLE: 2 } }, ratio: 1,
          chosen: { quote: word.codes[2].quotes[0], key: 'M1#0' } });
        const page = viewer.pages[0];
        Object.assign(page, { viewport: { width: 612, height: 792, scale: 1 }, proxy: { render, getTextContent: async () => ({ items: [] }) } });
        app.state.viewer = viewer;
        app.drawPage(viewer, page);
        await settle(() => viewer.mode === 'frame');
        t.mock.timers.tick(20000);
        await settle(() => viewer.mode === 'frame');
        assert.deepEqual([viewer.mode, viewer.fallback], ['frame', reason]);
        assert.equal(find('#viewerMark').textContent, `${app.FRAME_REASONS[reason]} The quote is on page 2.`);
        app.closeViewer();
      });
    }
    // a page whose drawing is given up because it left the view is not a failure: no frame
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
    await withPage({ elements: { documentViewer: element } }, async () => {
      Object.assign(app.state, { doc: word, route: null });
      const viewer = pdfViewer(word, element, pages, [], { library: { AnnotationMode: { ENABLE: 2 } }, ratio: 1 });
      const page = viewer.pages[0];
      const cleaned = [];
      Object.assign(page, { viewport: { width: 612, height: 792, scale: 1 }, proxy: { render: () => ({ promise: new Promise(() => {}), cancel() {} }),
        getTextContent: () => new Promise(() => {}), cleanup: () => cleaned.push(page.number) } });
      app.state.viewer = viewer;
      app.drawPage(viewer, page);
      app.releasePage(page);
      t.mock.timers.tick(20000);
      await settle(() => false);
      assert.equal(viewer.mode, 'pdf', 'a page released is not waited on');
      // B1: a page released lets the library free what it decoded to draw it
      assert.deepEqual(cleaned, [1]);
      app.closeViewer();
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

// Page nodes as the text layer holds them, for a test that paints marks: textContent, append, and the nodes made.
function layerNodes() {
  const made = [];
  const node = tag => {
    const made1 = { tag, children: [], dataset: {}, className: '', set textContent(value) { this.children = value === '' ? [] : [value]; },
      get textContent() { return this.children.map(child => (typeof child === 'string' ? child : child.textContent)).join(''); },
      append(...items) { this.children.push(...items); } };
    made.push(made1);
    return made1;
  };
  const layer = strings => ({ textDivs: strings.map(value => { const div = node('span'); div.textContent = value; return div; }), textContentItemsStr: strings });
  const marks = layered => layered.textDivs.flatMap(div => div.children.filter(child => typeof child !== 'string').map(child => child.textContent));
  return { node, layer, marks };
}

test('A2: a new choice clears the old one at once - its marks on every drawn page, the mark state and the note - before anything is waited on', async () => {
  const word = fixture('encounter-word.json');
  const pages = preview.SYNTHETIC_DOCUMENTS['synthetic-colonoscopy-report.docx'].pages;
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  const saved = { viewer: app.state.viewer };
  const { node, layer, marks } = layerNodes();
  try {
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      global.document.createElement = node;
      Object.assign(app.state, { doc: word, route: null });
      const viewer = pdfViewer(word, element, pages, []);
      const first = viewer.pages[0];
      Object.assign(first, { drawn: 'key', layer: layer(pages[0]) });
      app.state.viewer = viewer;
      const state = () => [element.dataset.marked, element.dataset.markStatus, element.dataset.markPages, element.dataset.markCount, find('#viewerMark').textContent];
      // a quote on page 1, marked
      await app.showQuote('L2#0');
      assert.deepEqual(state(), ['L2#0', 'marked', '1', '1', 'Marked on page 1.']);
      assert.deepEqual(marks(first.layer), ['Two biopsies were taken from the cecum with cold forceps.']);
      // the next quote's page has to be read first, and its read is held: at once, in the same task, nothing of the first
      // quote is shown - no mark on any drawn page, no mark state, no note
      let release;
      viewer.prepared.delete(2);
      viewer.texts.delete(2);
      viewer.pages[1].proxy = { getTextContent: () => new Promise(resolve => { release = () => resolve({ items: pages[1].map(str => ({ str, hasEOL: false })) }); }) };
      const shown = app.showQuote('M1#0');
      assert.equal(viewer.mark, null);
      assert.deepEqual(marks(first.layer), [], 'the first quote\'s marks are gone from its page');
      assert.deepEqual(state(), ['', '', '', '', ''], 'no mark state and no note');
      assert.equal(app.state.selectedQuote, 'M1#0');
      // a page drawn meanwhile gets nothing of the first quote
      first.drawn = 'key2';
      app.paintPage(viewer, first);
      assert.deepEqual(marks(first.layer), []);
      release();
      const result = await shown;
      assert.equal(result.status, 'marked');
      assert.deepEqual(state(), ['M1#0', 'marked', '2', '1', 'Marked on page 2.']);
      // a quote whose pages are prepared already: cleared and shown in the same task, so nothing flickers
      app.showQuote('L2#0');
      assert.deepEqual(state(), ['L2#0', 'marked', '1', '1', 'Marked on page 1.'], 'already shown when showQuote returns');
      assert.deepEqual(marks(first.layer), ['Two biopsies were taken from the cecum with cold forceps.']);
      // while the PDF is still loading, a choice clears what was said and waits
      viewer.mode = 'loading';
      app.showQuote('M1#0');
      assert.deepEqual(state(), ['', '', '', '', '']);
      assert.deepEqual(marks(first.layer), [], 'and its marks go');
      assert.deepEqual(viewer.pending, { quote: word.codes[2].quotes[0], key: 'M1#0' });
      viewer.mode = 'pdf';
      viewer.pending = null;
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('A3: the watchdog gives up waits on the library only when it has not answered for 20 s, from the later of its last answer and the wait\'s start', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const run = async fn => {
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
    await withPage({ elements: { documentViewer: element } }, async page => {
      Object.assign(app.state, { doc: word, route: null });
      const viewer = pdfViewer(word, element, [['a'], ['b']], []);
      app.state.viewer = viewer;
      await fn(viewer, app.libraryWatchdog(viewer), page);
      app.closeViewer();
    });
  };
  const outcome = promise => {
    const seen = { value: 'waiting' };
    promise.then(() => { seen.value = 'settled'; }, error => { seen.value = error instanceof app.TimeLimit ? 'limit' : error?.name || 'error'; });
    return seen;
  };
  try {
    // answers keep a wait alive however long it takes; 20 s with none gives every pending wait up, and the frame
    await run(async (viewer, dog) => {
      assert.equal(app.libraryWatchdog(viewer), dog, 'one watchdog per viewer');
      const one = outcome(dog.wait(new Promise(() => {})));
      for (let step = 0; step < 6; step += 1) {
        t.mock.timers.tick(15000);
        dog.answer();
        await settle(() => false);
      }
      const two = outcome(dog.wait(new Promise(() => {})));
      t.mock.timers.tick(19999);
      await settle(() => false);
      assert.deepEqual([one.value, two.value, viewer.mode], ['waiting', 'waiting', 'pdf'], '90 s of answers, then 19.999 s quiet');
      t.mock.timers.tick(1);
      await settle(() => one.value !== 'waiting' && two.value !== 'waiting');
      assert.deepEqual([one.value, two.value], ['limit', 'limit'], 'every pending wait rejects with TimeLimit');
      assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'library']);
    });
    // counted from the later of the last answer and the start of the wait: quiet before a wait does not count
    await run(async (viewer, dog) => {
      dog.answer();
      t.mock.timers.tick(15000);
      const one = outcome(dog.wait(new Promise(() => {})));
      t.mock.timers.tick(19999);
      await settle(() => false);
      assert.equal(one.value, 'waiting', '35 s after the last answer, 19.999 s after the wait began');
      t.mock.timers.tick(1);
      await settle(() => one.value !== 'waiting');
      assert.equal(one.value, 'limit');
    });
    // a wait settling is an answer; a wait that settles settles as it did
    await run(async (viewer, dog) => {
      const pending = outcome(dog.wait(new Promise(() => {})));
      const quick = outcome(dog.wait(new Promise(resolve => setTimeout(resolve, 10000))));
      t.mock.timers.tick(10000);
      await settle(() => quick.value !== 'waiting');
      assert.equal(quick.value, 'settled');
      t.mock.timers.tick(19999);
      await settle(() => false);
      assert.equal(pending.value, 'waiting', '29.999 s: 19.999 s after the other wait settled');
      t.mock.timers.tick(1);
      await settle(() => pending.value !== 'waiting');
      assert.equal(pending.value, 'limit');
      await assert.rejects(app.libraryWatchdog(viewer).wait(Promise.reject(new Error('refused'))), /refused|no longer shown/);
    });
    // a page released is no longer waited on: its waits are let go, and nothing fires
    await run(async (viewer, dog) => {
      const page = viewer.pages[0];
      const drawing = outcome(dog.wait(new Promise(() => {}), page));
      dog.forget(page);
      await settle(() => drawing.value !== 'waiting');
      assert.equal(drawing.value, 'AbortException');
      t.mock.timers.tick(60000);
      await settle(() => false);
      assert.equal(viewer.mode, 'pdf');
    });
    // only visible time counts: a hidden tab draws nothing
    await run(async (viewer, dog, page) => {
      const listeners = new Set();
      Object.assign(global.document, { hidden: false, addEventListener(type, fn) { if (type === 'visibilitychange') listeners.add(fn); },
        removeEventListener(type, fn) { listeners.delete(fn); } });
      viewer.watchdog = null;
      const watchdog = app.libraryWatchdog(viewer);
      const show = hidden => { global.document.hidden = hidden; for (const fn of [...listeners]) fn(); };
      const one = outcome(watchdog.wait(new Promise(() => {})));
      t.mock.timers.tick(15000);
      show(true);
      t.mock.timers.tick(60000);
      show(false);
      t.mock.timers.tick(4999);
      await settle(() => false);
      assert.equal(one.value, 'waiting', '15 s + 4.999 s visible');
      t.mock.timers.tick(1);
      await settle(() => one.value !== 'waiting');
      assert.equal(one.value, 'limit');
      assert.equal(page.element('#viewerMark').textContent, '', 'no quote chosen: nothing said');
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('A3: the pages are drawn one at a time, the quote\'s page first, and a page that leaves the view before its turn is never drawn', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  try {
    await withPage({ elements: { documentViewer: element } }, async () => {
      Object.assign(app.state, { doc: word, route: null });
      const started = [];
      const finish = new Map();
      const viewer = pdfViewer(word, element, [['a'], ['b'], ['c'], ['d']], [], { ratio: 1, library: { AnnotationMode: { ENABLE: 2 },
        TextLayer: class { constructor() { this.textDivs = []; this.textContentItemsStr = []; } render() { return Promise.resolve(); } cancel() {} } } });
      for (const page of viewer.pages) {
        page.viewport = { width: 612, height: 792, scale: 1 };
        page.proxy = { getTextContent: async () => ({ items: [] }), cleanup() {}, render: () => {
          started.push(page.number);
          let settle;
          const promise = new Promise((resolve, reject) => { settle = { resolve, reject }; });
          finish.set(page.number, settle);
          return { promise, cancel: () => settle.reject(Object.assign(new Error('cancelled'), { name: 'RenderingCancelledException' })) };
        } };
      }
      app.state.viewer = viewer;
      for (const page of viewer.pages) app.drawPage(viewer, page);
      assert.deepEqual(started, [1], 'one page at a time');
      // the quote is waiting for page 4; page 2 leaves the view before its turn
      viewer.reveal = 4;
      app.releasePage(viewer.pages[1]);
      finish.get(1).resolve();
      await settle(() => started.length === 2);
      assert.deepEqual(started, [1, 4], 'the quote\'s page next');
      assert.equal(viewer.pages[0].drawn, '1 1', 'page 1 drawn');
      finish.get(4).resolve();
      await settle(() => started.length === 3);
      assert.deepEqual(started, [1, 4, 3], 'then the others still asked for, in order; page 2 never');
      // a page released while it is drawn lets the next one start at once
      app.releasePage(viewer.pages[2]);
      await settle(() => viewer.busy === null);
      assert.equal(viewer.busy, null);
      assert.deepEqual(viewer.queue, []);
      assert.equal(viewer.mode, 'pdf', 'nothing given up is a failure');
      // a page asked for at a new size while it is drawn (a zoom) is not cancelled: its drawing finishes and is shown, then
      // it is drawn again at the new size (from what the library decoded for it)
      viewer.reveal = 0;
      const first = viewer.pages[0];
      first.drawn = '';
      app.drawPage(viewer, first);
      assert.deepEqual(started.slice(3), [1]);
      let cancelled = false;
      const settle1 = finish.get(1);
      finish.set(1, { resolve: settle1.resolve, reject: error => { cancelled = true; settle1.reject(error); } });
      first.viewport = { width: 765, height: 990, scale: 1.25 };
      app.drawPage(viewer, first);
      assert.equal(cancelled, false, 'the drawing under way is not cancelled');
      assert.deepEqual(viewer.queue, [first], 'the page is asked for again');
      settle1.resolve();
      await settle(() => started.length === 5);
      assert.equal(first.drawn, '1 1', 'the first drawing was shown');
      assert.deepEqual(started.slice(3), [1, 1], 'and the page is drawn again at the new size');
      finish.get(1).resolve();
      await settle(() => first.drawn === '1.25 1');
      assert.deepEqual([first.drawn, first.drawing], ['1.25 1', '']);
      app.closeViewer();
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('A3: while the view scrolls no page is started, so a page the view only passes is never decoded', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  try {
    await withPage({ elements: { documentViewer: element } }, async () => {
      Object.assign(app.state, { doc: word, route: null });
      const started = [];
      const viewer = pdfViewer(word, element, [['a'], ['b'], ['c']], [], { ratio: 1, library: { AnnotationMode: { ENABLE: 2 } } });
      for (const page of viewer.pages) {
        page.viewport = { width: 612, height: 792, scale: 1 };
        page.proxy = { cleanup() {}, getTextContent: async () => ({ items: [] }), render: () => { started.push(page.number); return { promise: new Promise(() => {}), cancel() {} }; } };
      }
      app.state.viewer = viewer;
      // the view is scrolling (a smooth scroll to a quote): pages 1 and 2 come near and are asked for, page 1 leaves again
      viewer.scrolledAt = Date.now();
      app.drawPage(viewer, viewer.pages[0]);
      app.drawPage(viewer, viewer.pages[1]);
      t.mock.timers.tick(100);
      viewer.scrolledAt = Date.now();
      app.releasePage(viewer.pages[0]);
      t.mock.timers.tick(app.PDF_VIEW.settleMs - 1);
      await settle(() => false);
      assert.deepEqual(started, [], 'nothing is started while the view moves');
      t.mock.timers.tick(1);
      await settle(() => started.length === 1);
      assert.deepEqual(started, [2], 'once it has stopped: the page still near; the page passed is never asked of the library');
      app.closeViewer();
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('A5: the viewer downloads the document itself - a failed download is said so, a stalled one too, a refused one is the document\'s, and closing stops it', async t => {
  const word = fixture('encounter-word.json');
  const failing = [['a 503', () => Promise.resolve(viewResponse({ status: 503, chunks: [] }))], ['a 502', () => Promise.resolve(viewResponse({ status: 502, chunks: [] }))],
    ['an app 500', () => Promise.resolve(viewResponse({ status: 500, chunks: [] }))], ['a fetch that fails', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['a body cut short', () => Promise.resolve(viewResponse({ breaks: true }))], ['a 401', () => Promise.resolve(viewResponse({ status: 401, chunks: [] }))]];
  for (const [what, download] of failing) {
    const library = fakeLibrary({ open: () => Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }) });
    await withPdfPage(() => Promise.resolve(library.library), async ({ element: find, fetches }) => {
      const viewer = await mount(word, find, opened => opened.mode === 'frame');
      assert.deepEqual([viewer.fallback, viewer.element.dataset.fallback], ['download', 'download'], what);
      assert.equal(library.made.tasks.length, 0, `${what}: the library is given nothing`);
      assert.equal(fetches.length, 1, `${what}: one download, never repeated by itself`);
      app.showQuote('L2#0');
      assert.equal(find('#viewerMark').textContent, 'The document could not be downloaded for marking, so nothing is marked. The quote is on page 1.', what);
      // the frame tries the document again with the browser's own viewer, at the quote's page
      assert.equal(viewer.frame.src, `${word.document.view_url}#page=1`);
    }, download);
  }
  // bytes the library refuses (a file that is no PDF): the document's note, as before
  const refusing = fakeLibrary({ open: () => Promise.reject(Object.assign(new Error('Invalid PDF structure.'), { name: 'InvalidPDFException' })) });
  await withPdfPage(() => Promise.resolve(refusing.library), async ({ element: find }) => {
    const viewer = await mount(word, find, opened => opened.mode === 'frame');
    assert.equal(viewer.fallback, 'document');
    assert.equal(refusing.made.tasks.length, 1);
  });
  // closing the viewer while the document downloads stops the download
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ element: find, fetches }) => {
    const viewer = await mount(word, find, () => fetches.length === 1);
    const { signal } = fetches[0].init;
    assert.equal(signal.aborted, false);
    app.closeViewer();
    assert.equal(signal.aborted, true, 'the download is aborted');
    assert.equal(viewer.mode, 'closed');
  }, () => new Promise(() => {}));
  // a download that stops moving: each chunk restarts the 20 s stall timer; 20 s with no byte before the document opens
  // gives 'slow', and stops the download
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const deliveries = [];
  const trickle = () => Promise.resolve({ ok: true, status: 200, body: { getReader: () => ({ read: () => new Promise(resolve => deliveries.push(resolve)) }) } });
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ element: find, fetches }) => {
    const viewer = await mount(word, find, () => deliveries.length === 1);
    for (let chunk = 0; chunk < 3; chunk += 1) {
      t.mock.timers.tick(15000);
      deliveries.at(-1)({ done: false, value: Uint8Array.from([37]) });
      await settle(() => deliveries.length === chunk + 2);
      assert.equal(viewer.mode, 'loading', `${(chunk + 1) * 15} s, a chunk every 15 s`);
    }
    t.mock.timers.tick(19999);
    await settle(() => false);
    assert.equal(viewer.mode, 'loading');
    t.mock.timers.tick(1);
    await settle(() => viewer.mode === 'frame');
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'slow']);
    assert.equal(fetches[0].init.signal.aborted, true);
  }, trickle);
});

test('A6: choosing a quote brings its first mark into view across as well, where the pages are wider than the viewer; nothing changes at fit width', () => {
  const geometry = ({ scrollWidth, scrollLeft = 0, mark }) => {
    const element = { clientWidth: 554, clientHeight: 600, scrollWidth, scrollLeft, scrollTop: 0, scrollTo(options) { this.scrolled = options; } };
    const box = { top: 300, left: mark[0], width: mark[1], height: 14 };
    const page = { number: 1, drawn: 'key', element: { offsetTop: 12, offsetLeft: 12, getBoundingClientRect: () => ({ top: 0, left: 0 }), querySelector: () => ({ getBoundingClientRect: () => box }) } };
    const viewer = { element, pages: [page], mode: 'pdf', settleTimer: 0, quoteScroll: null, reveal: 0 };
    app.scrollToQuote(viewer, page);
    clearTimeout(viewer.settleTimer);
    return element.scrolled;
  };
  const saved = global.window;
  global.window = { matchMedia: () => ({ matches: false }) };
  try {
    const top = 12 + 300 - 600 / 3;
    // fit width: the page is as wide as the viewer, and only the vertical position is set, as before
    assert.deepEqual(geometry({ scrollWidth: 554, mark: [400, 100] }), { top, behavior: 'smooth' });
    // a mark out of view to the right that fits: the least distance that shows it all with the gap after it
    assert.deepEqual(geometry({ scrollWidth: 1108, mark: [700, 100] }), { top, behavior: 'smooth', left: 712 + 100 + 12 - 554 });
    // out of view to the left: its start the gap from the viewer's start
    assert.deepEqual(geometry({ scrollWidth: 1108, scrollLeft: 600, mark: [100, 100] }), { top, behavior: 'smooth', left: 112 - 12 });
    // partly out of view at the right edge
    assert.deepEqual(geometry({ scrollWidth: 1108, scrollLeft: 300, mark: [800, 60] }), { top, behavior: 'smooth', left: 812 + 60 + 12 - 554 });
    // already in view with its gaps: nothing moves across
    assert.deepEqual(geometry({ scrollWidth: 1108, scrollLeft: 600, mark: [700, 100] }), { top, behavior: 'smooth' });
    // wider than the viewer: its start the gap from the viewer's start
    assert.deepEqual(geometry({ scrollWidth: 1662, mark: [900, 600] }), { top, behavior: 'smooth', left: 912 - 12 });
    // never beyond what the viewer can scroll
    assert.deepEqual(geometry({ scrollWidth: 1108, mark: [1060, 40] }), { top, behavior: 'smooth', left: 1108 - 554 });
  } finally {
    global.window = saved;
  }
});

test('A7: a zoom or a new width while a quote is being scrolled to keeps the quote; the member\'s own scrolling ends it', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const style = global.getComputedStyle;
  global.getComputedStyle = () => ({ paddingLeft: '12px', paddingRight: '12px' });
  const globals = { IntersectionObserver: global.IntersectionObserver, ResizeObserver: global.ResizeObserver };
  global.IntersectionObserver = function IntersectionObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  global.ResizeObserver = function ResizeObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  try {
    const listeners = {};
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url }, clientWidth: 636, clientHeight: 800, scrollTop: 0, scrollLeft: 0, scrollWidth: 636,
      addEventListener(type, fn) { (listeners[type] ||= []).push(fn); }, removeEventListener(type, fn) { listeners[type] = (listeners[type] || []).filter(item => item !== fn); } });
    element.scrollTo = function scrollTo(options) { this.scrolled = options; this.scrolls = (this.scrolls || 0) + 1; };
    await withPage({ elements: { documentViewer: element } }, async () => {
      global.window.devicePixelRatio = 1;
      const made = () => ({ className: '', dataset: {}, style: { setProperty(name, value) { this[name] = value; } }, children: [], append(...nodes) { this.children.push(...nodes); },
        setAttribute() {}, replaceChildren(...nodes) { this.children = nodes; }, querySelector: () => null });
      global.document.createElement = made;
      Object.assign(app.state, { doc: word, route: null });
      const viewer = { element, view: word.document.view_url, name: 'x', mode: 'loading', pages: [], texts: new Map(), prepared: new Map(), mark: null, pending: null,
        chosen: null, markSerial: 0, reveal: 0, quoteScroll: null, frame: null, framePage: null, fallback: '', zoom: app.ZOOM_FIT, inputs: [], settleTimer: 0 };
      app.state.viewer = viewer;
      const proxy = () => ({ getViewport: ({ scale }) => ({ width: 612 * scale, height: 792 * scale, scale, userUnit: 1 }),
        render: () => ({ promise: new Promise(() => {}), cancel() {} }), getTextContent: () => new Promise(() => {}) });
      viewer.library = { AnnotationMode: { ENABLE: 2 } };
      app.buildPages(viewer, [proxy(), proxy(), proxy()]);
      viewer.pages.forEach((page, index) => {
        Object.defineProperty(page.element, 'offsetTop', { get: () => 12 + index * (parseFloat(page.element.style.height) + 12) });
        Object.defineProperty(page.element, 'offsetHeight', { get: () => parseFloat(page.element.style.height) });
        page.element.offsetLeft = 12;
        page.element.getBoundingClientRect = () => ({ top: 0, left: 0 });
      });
      // the quote's page 3 is not drawn yet: the view is sent to its top and its reveal armed
      const third = viewer.pages[2];
      viewer.reveal = 3;
      app.scrollToQuote(viewer, third);
      assert.deepEqual(viewer.quoteScroll, { page: 3 });
      assert.equal(element.scrolled.top, third.element.offsetTop - app.PDF_VIEW.gap);
      // the smooth scroll is under way (the view moves) when Zoom in is pressed: the relayout keeps the quote - its page's
      // top at the new size, its reveal kept - not the page that was passing the top of the view
      element.scrollTop = 900;
      t.mock.timers.tick(app.PDF_VIEW.settleMs);
      assert.deepEqual(viewer.quoteScroll, { page: 3 }, 'still moving');
      app.zoomViewer('in');
      assert.equal(viewer.pages[0].viewport.scale, 1.25);
      assert.equal(element.scrolled.top, third.element.offsetTop - app.PDF_VIEW.gap, 'its page\'s top at 125%');
      assert.equal(viewer.reveal, 3, 'the reveal kept');
      // its page drawn, with a mark: a new width keeps the quote at its first mark
      Object.assign(third, { drawn: 'key' });
      third.element.querySelector = () => ({ getBoundingClientRect: () => ({ top: 500, left: 40, width: 80, height: 14 }) });
      element.clientWidth = 524;
      viewer.resize?.disconnect();
      app.relayoutPages(viewer);
      assert.equal(element.scrolled.top, third.element.offsetTop + 500 - element.clientHeight / 3, 'to its first mark');
      // once the view stops moving, the scroll is over, and a relayout keeps the page at the top as before
      t.mock.timers.tick(app.PDF_VIEW.settleMs);
      assert.equal(viewer.quoteScroll, null, 'the view stopped: the scroll is over');
      viewer.reveal = 0;
      const before = element.scrolls;
      app.zoomViewer('in');
      assert.equal(element.scrolls, before, 'nothing scrolls to the quote any more');
      // the member's own scrolling ends the scroll to a quote and its reveal: a wheel, a touch, a pointer on the viewer, a
      // scroll key (another key does not)
      for (const [type, event, ends] of [['wheel', {}, true], ['touchstart', {}, true], ['pointerdown', {}, true], ['keydown', { key: 'PageDown' }, true],
        ['keydown', { key: 'ArrowDown' }, true], ['keydown', { key: ' ' }, true], ['keydown', { key: 'a' }, false], ['keydown', { key: 'Tab' }, false]]) {
        viewer.reveal = 3;
        app.scrollToQuote(viewer, third);
        for (const fn of listeners[type] || []) fn(event);
        assert.deepEqual([viewer.reveal === 0, viewer.quoteScroll === null], [ends, ends], `${type} ${event.key || ''}`);
      }
      // and then nothing moves the view later, unasked: a relayout anchors on the page at the top
      viewer.reveal = 3;
      app.scrollToQuote(viewer, third);
      for (const fn of listeners.wheel) fn({});
      const count = element.scrolls;
      app.zoomViewer('out');
      assert.equal(element.scrolls, count);
      app.closeViewer();
      assert.deepEqual(Object.values(listeners).map(list => list.length), Object.keys(listeners).map(() => 0), 'its listeners go with the viewer');
    });
  } finally {
    global.getComputedStyle = style;
    Object.assign(global, globals);
    Object.assign(app.state, saved);
  }
});

test('A8: the toolbar keeps the file name\'s room, with its full text as its title, and an unavailable zoom step looks unavailable in forced colours', () => {
  const doc = clone(fixture('encounter-word.json'));
  doc.document.name = 'a "very" long & <odd> name.docx';
  const html = app.viewerPanel(doc);
  assert.match(html, /<span class="viewer-name" title="a &quot;very&quot; long &amp; &lt;odd&gt; name\.docx">a &quot;very&quot; long &amp; &lt;odd&gt; name\.docx<\/span>/);
  const appended = fs.readFileSync(STYLES, 'utf8').slice(32785);
  assert.ok(appended.includes('@media (forced-colors: active){.zoom-button[aria-disabled="true"]{color:GrayText;border-color:GrayText}\n}'), 'GrayText in forced colours');
  // last in the toolbar, at least 12 characters (or all of it), as wide as it is where there is room
  assert.ok(appended.includes('.viewer-name{order:1;flex:1 0 12ch;max-width:max-content}'));
  assert.ok(appended.lastIndexOf('.viewer-name{order:1') > appended.lastIndexOf('.viewer-name{flex:1 1 0'), 'the later rule wins');
});

test('V3: the zoom steps through 75%, 100% (fit width), 125%, 150%, 200% and 300%, and the pages follow at every step', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const style = global.getComputedStyle;
  global.getComputedStyle = () => ({ paddingLeft: '12px', paddingRight: '12px' });
  try {
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url }, clientWidth: 636, clientHeight: 800, scrollTop: 0, scrollLeft: 0, scrollWidth: 636 });
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      global.window.devicePixelRatio = 1;
      Object.assign(app.state, { doc: word, route: null });
      const viewer = pdfViewer(word, element, [['a'], ['b']], []);
      const sizes = [];
      for (const page of viewer.pages) {
        page.proxy.getViewport = ({ scale }) => ({ width: 612 * scale, height: 792 * scale, scale, userUnit: 1 });
        page.element.style = { setProperty(name, value) { this[name] = value; } };
        Object.defineProperty(page.element, 'offsetHeight', { get: () => parseFloat(page.element.style.height) });
      }
      app.state.viewer = viewer;
      app.layoutPages(viewer);
      const shown = () => ({ scale: viewer.pages[0].viewport.scale, width: viewer.pages[0].element.style.width, level: find('#zoomLevel').textContent,
        out: find('#viewerZoom [data-zoom="out"]').attributes['aria-disabled'], in: find('#viewerZoom [data-zoom="in"]').attributes['aria-disabled'],
        fit: find('#viewerZoom [data-zoom="fit"]').attributes['aria-disabled'], hidden: find('#viewerZoom').hidden });
      assert.equal(viewer.pages[0].viewport.scale, 1, 'fitted to the 612 px the viewer holds inside its padding');
      assert.deepEqual(app.ZOOM_STEPS, [0.75, 1, 1.25, 1.5, 2, 3]);
      for (const action of ['in', 'in', 'in', 'in', 'in', 'out', 'out', 'out', 'out', 'out', 'out', 'fit']) {
        app.zoomViewer(action);
        sizes.push(shown());
      }
      assert.deepEqual(sizes.map(size => size.level), ['125%', '150%', '200%', '300%', '300%', '200%', '150%', '125%', '100%', '75%', '75%', '100%']);
      assert.deepEqual(sizes.map(size => size.scale), [1.25, 1.5, 2, 3, 3, 2, 1.5, 1.25, 1, 0.75, 0.75, 1]);
      assert.deepEqual(sizes.map(size => size.width), ['765px', '918px', '1224px', '1836px', '1836px', '1224px', '918px', '765px', '612px', '459px', '459px', '612px']);
      assert.ok(sizes.every(size => size.hidden === false), 'the zoom shows with the drawn pages');
      // a step that cannot go further says so, and keeps the focus (aria-disabled, not disabled)
      assert.deepEqual([sizes[3].in, sizes[3].out, sizes[3].fit], ['true', 'false', 'false']);
      assert.deepEqual([sizes[9].in, sizes[9].out, sizes[9].fit], ['false', 'true', 'false']);
      assert.deepEqual([sizes[11].in, sizes[11].out, sizes[11].fit], ['false', 'false', 'true']);
      // the text layer's scale follows the zoom
      app.zoomViewer('in');
      assert.equal(viewer.pages[1].element.style['--total-scale-factor'], '1.25');
      // a new width keeps the zoom: the pages are 125% of the new fit
      element.clientWidth = 524;
      viewer.width = 0;
      app.layoutPages(viewer);
      assert.equal(viewer.pages[0].viewport.scale, (500 / 612) * 1.25);
      // the zoom is the drawn pages' only: in the frame it is hidden, and asks for nothing
      app.fallbackViewer(viewer, 'document');
      assert.equal(find('#viewerZoom').hidden, true);
      app.zoomViewer('in');
      assert.equal(viewer.zoom, 2);
      app.closeViewer();
    });
  } finally {
    global.getComputedStyle = style;
    Object.assign(app.state, saved);
  }
});

test('a text has no pages: a quote is marked in the text frame, never by moving the frame', async () => {
  const text = clone(fixture('encounter-awaiting-answer.json'));
  text.codes[0].quotes[0].page = 1;
  const frame = fakeElement({ tagName: 'IFRAME', src: 'unchanged', scrollIntoView() {} });
  const saved = { framePassage: app.state.framePassage };
  try {
    await withPage({ elements: { documentViewer: frame } }, async () => {
      Object.assign(app.state, { doc: text, route: null });
      app.showQuote('L1#0');
      assert.equal(frame.src, 'unchanged');
      assert.equal(app.state.selectedQuote, 'L1#0');
      // the frame's text is not loaded here: the passage waits for it
      assert.deepEqual(app.state.framePassage, { passage: text.codes[0].quotes[0].text, key: 'L1#0', frame });
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('a text frame that does not hold the document is never searched: the note says it could not be downloaded', async () => {
  const size = 376;
  const view = 'http://studio.test/api/encounters/x/original?view=1';
  const pageOf = (fields = {}) => ({ URL: view, readyState: 'complete', body: {}, ...fields });
  // a frame as the page sees it: its current document (null when this page cannot read it) and its navigation entry,
  // both changeable, as a reload changes them
  const frameOf = ({ page = pageOf(), entry = { responseStatus: 200, decodedBodySize: size }, throws = false } = {}) => {
    const frame = fakeElement({ tagName: 'IFRAME', id: 'documentViewer', scrollIntoView() {} });
    Object.assign(frame, { page, entry });
    Object.defineProperty(frame, 'contentDocument', { get() { if (throws) throw new Error('blocked'); return this.page; } });
    frame.contentWindow = { performance: { getEntriesByType: type => (type === 'navigation' && frame.entry ? [frame.entry] : []) } };
    return frame;
  };
  const loaded = frame => {
    app.noteFrameLoad({ target: frame });
    return frame;
  };
  // only a document whose own load has come is the frame's: one still loading, or a load the browser stopped mid-body
  // (complete, with no load event), is waited for and never searched
  assert.equal(app.frameHolds(frameOf(), size), 'waiting');
  assert.equal(app.frameHolds(loaded(frameOf()), size), 'document');
  // the edge's own page while the app restarts: readable, its own size and status
  assert.equal(app.frameHolds(loaded(frameOf({ entry: { responseStatus: 503, decodedBodySize: 39 } })), size), 'failed');
  assert.equal(app.frameHolds(loaded(frameOf({ entry: { decodedBodySize: 39 } })), size), 'failed', 'a positive size that is not the document\'s');
  assert.equal(app.frameHolds(loaded(frameOf({ entry: { responseStatus: 503, decodedBodySize: size } })), size), 'failed', 'an answer other than 200');
  // what the browser does not tell (no entry, a status of 0, a size of 0) is not held against the frame
  assert.equal(app.frameHolds(loaded(frameOf({ entry: null })), size), 'document');
  assert.equal(app.frameHolds(loaded(frameOf({ entry: { responseStatus: 0, decodedBodySize: 0 } })), size), 'document');
  assert.equal(app.frameHolds(loaded(frameOf({ entry: { decodedBodySize: 39 } })), null), 'document', 'no size to compare with');
  const noTiming = loaded(frameOf());
  noTiming.contentWindow = { get performance() { throw new Error('no timing'); } };
  assert.equal(app.frameHolds(noTiming, size), 'document');
  // a frame this page cannot read: waited for until its load, then it does not hold the document
  for (const unreadable of [frameOf({ page: null }), frameOf({ throws: true })]) {
    assert.equal(app.frameHolds(unreadable, size), 'waiting');
    app.noteFrameLoad({ target: unreadable });
    assert.equal(app.frameHolds(unreadable, size), 'failed');
  }
  // the frame's first, empty document is not its load
  const blank = loaded(frameOf({ page: pageOf({ URL: 'about:blank' }) }));
  assert.equal(app.frameHolds(blank, size), 'waiting');
  // a reload from the frame's menu: the new document is waited for, loading or stopped, until its own load
  const reloaded = loaded(frameOf());
  reloaded.page = pageOf({ readyState: 'loading' });
  assert.equal(app.frameHolds(reloaded, size), 'waiting');
  reloaded.page = pageOf();
  assert.equal(app.frameHolds(reloaded, size), 'waiting', 'complete with no load of its own: stopped');
  reloaded.entry = { responseStatus: 503, decodedBodySize: 39 };
  assert.equal(app.frameHolds(loaded(reloaded), size), 'failed');
  app.noteFrameLoad({ target: fakeElement({ tagName: 'IMG' }) });

  const text = clone(fixture('encounter-awaiting-answer.json'));
  assert.equal(text.document.size, size);
  const note = fakeElement();
  const saved = { framePassage: app.state.framePassage, doc: app.state.doc, route: app.state.route };
  try {
    const failed = loaded(frameOf({ entry: { responseStatus: 503, decodedBodySize: 39 } }));
    await withPage({ elements: { documentViewer: failed, viewerMark: note } }, async () => {
      Object.assign(app.state, { doc: text, route: null });
      app.showQuote('L1#0');
      assert.equal(note.textContent, app.FRAME_REASONS.download);
      assert.equal(note.classList.contains('is-missing'), true);
      assert.deepEqual({ ...failed.dataset }, { fallback: 'download', marked: 'L1#0', markStatus: 'unavailable', markCount: '0' });
      app.clearViewerMark();
      assert.equal(note.textContent, '');
      assert.deepEqual({ ...failed.dataset }, { fallback: 'download', marked: '', markStatus: '', markCount: '' });
    });
    // a choice made while the frame waits clears what an earlier one said, and the frame's load paints it
    const waiting = frameOf({ page: pageOf({ readyState: 'loading' }) });
    await withPage({ elements: { documentViewer: waiting, viewerMark: note } }, async () => {
      Object.assign(app.state, { doc: text, route: null });
      note.textContent = 'Marked in the document.';
      waiting.dataset.markStatus = 'marked';
      app.showQuote('L1#1');
      assert.equal(note.textContent, '');
      assert.deepEqual({ ...waiting.dataset }, { marked: '', markStatus: '', markCount: '' }, 'no answer yet: no quote named');
      // the load brings the edge's page: the note follows it
      Object.assign(waiting, { page: pageOf(), entry: { responseStatus: 503, decodedBodySize: 39 } });
      app.noteFrameLoad({ target: waiting });
      assert.equal(note.textContent, app.FRAME_REASONS.download);
      assert.deepEqual({ ...waiting.dataset }, { fallback: 'download', marked: 'L1#1', markStatus: 'unavailable', markCount: '0' });
      // a load of another frame paints nothing
      const other = frameOf({ page: pageOf(), entry: { responseStatus: 503, decodedBodySize: 39 } });
      note.textContent = 'unchanged';
      app.noteFrameLoad({ target: other });
      assert.equal(note.textContent, 'unchanged');
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

test('the progress panel: three steps per phase, Stop, Resume and Retry only when offered to a reviewer', () => {
  const states = phase => app.progressSteps(phase).map(step => step.state);
  assert.deepEqual(states('queued'), ['waiting', 'waiting', 'waiting']);
  assert.deepEqual(states('reading'), ['active', 'waiting', 'waiting']);
  assert.deepEqual(states('checking'), ['done', 'active', 'waiting']);
  assert.deepEqual(states('done'), ['done', 'done', 'done']);
  assert.deepEqual(states('failed'), ['unknown', 'unknown', 'failed'], 'a failed review claims nothing about how far it got');
  assert.deepEqual(states('stopped'), ['unknown', 'unknown', 'stopped']);
  assert.deepEqual(app.progressSteps('reading').map(step => step.label), ['Reading', 'Checking', 'Finished']);
  const buttons = doc => dom(app.progressPanel(doc, ui(doc))).all('button[data-action]').map(button => button.attr('data-action'));
  const reading = fixture('encounter-reading.json');
  assert.deepEqual(buttons(reading), ['stop']);
  assert.equal(dom(app.progressPanel(reading, ui(reading))).one('h2').text, 'Reading your document');
  assert.match(dom(app.progressPanel(reading, ui(reading))).one('.progress-time').text, /^Elapsed 45 s$/);
  assert.match(dom(app.progressPanel(reading, ui(reading))).one('.leave-note').text, /You can leave this page/);
  assert.deepEqual(buttons(fixture('encounter-failed.json')), ['retry']);
  assert.match(dom(app.progressPanel(fixture('encounter-failed.json'), {})).one('.progress-error').text, /was busy and could not finish/);
  assert.deepEqual(buttons(fixture('encounter-ready.json')), []);
  const stopped = clone(fixture('encounter-failed.json'));
  Object.assign(stopped, { state: 'stopped', state_label: 'Stopped' });
  Object.assign(stopped.progress, { phase: 'stopped', can_resume: true, can_retry: true, error: null });
  assert.deepEqual(buttons(stopped), ['resume', 'retry']);
  assert.equal(dom(app.progressPanel(stopped, {})).one('h2').text, 'The coding review was stopped');
  // a viewer, or a flag the server did not set, gets none; Stop never once the review has ended
  for (const doc of [reading, stopped]) {
    const viewer = clone(doc);
    viewer.permissions.can_review = false;
    assert.deepEqual(buttons(viewer), []);
  }
  const ended = clone(stopped);
  ended.progress.can_stop = true;
  assert.ok(!buttons(ended).includes('stop'));
  // done: one compact line with the steps, finished in its time
  const done = dom(app.progressPanel(fixture('encounter-ready.json'), {}));
  assert.match(done.one('.progress-summary').text, /^Coding review finished · finished in 6 min 04 s$/);
  assert.deepEqual(done.all('.progress-step').map(step => step.attr('data-state')), ['done', 'done', 'done']);
});

test('an earlier review: the server\'s message, no steps, never done, and Review again only when the server offers it', () => {
  const doc = fixture('encounter-earlier.json');
  assert.equal(app.progressPhase(doc), 'earlier');
  assert.equal(app.progressPhase({ state: 'earlier' }), 'earlier', 'read from the state when the phase is missing');
  assert.equal(app.isBusy(doc), false);
  assert.equal(app.shouldPoll(doc), false, 'nothing runs, so nothing is polled');
  assert.deepEqual(app.progressSteps('earlier'), []);
  const panel = dom(app.progressPanel(doc, ui(doc))).one('section.progress-panel');
  assert.deepEqual([panel.attr('data-phase'), panel.attr('class'), panel.one('h2').text], ['earlier', 'progress-panel', 'Earlier review']);
  assert.equal(panel.one('.progress-message').text, doc.progress.message, 'the server\'s message, as given');
  for (const absent of ['ol.progress-steps', '.progress-step', '.progress-time', '.leave-note', '.progress-error', '.progress-summary']) {
    assert.equal(panel.one(absent), null, absent);
  }
  const buttons = item => dom(app.progressPanel(item, ui(item))).all('button[data-action]').map(button => [button.attr('data-action'), button.attr('class'), button.text.trim()]);
  assert.deepEqual(buttons(doc), [['retry', 'button primary', 'Review again']]);
  assert.equal(app.REVIEW_AGAIN, 'Review again');
  // only when offered, and only to a member who may review
  const unoffered = clone(doc);
  unoffered.progress.can_retry = false;
  assert.deepEqual(buttons(unoffered), []);
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  assert.deepEqual(buttons(viewer), []);
  const flagged = clone(doc);
  Object.assign(flagged.progress, { can_stop: true, can_resume: true });
  assert.deepEqual(buttons(flagged).map(([action]) => action), ['resume', 'retry'], 'Stop never once nothing runs');
  // a failed review's retry keeps its own label
  assert.deepEqual(buttons(fixture('encounter-failed.json')), [['retry', 'button primary', 'Retry']]);
  // never drawn as a finished review: no codes said to be found, no notes panel, nothing to download
  const page = dom(render(doc));
  assert.equal(page.one('.results-empty').text, 'Codes appear here once the document is reviewed again with the current version.');
  assert.equal(app.emptyCodesText(doc), 'Codes appear here once the document is reviewed again with the current version.');
  assert.equal(page.one('#quotesPanel .quotes-empty').text, 'Quoted passages appear here once the document is reviewed again.');
  assert.equal(page.one('#notesPanel'), null);
  assert.equal(page.one('.progress-compact'), null);
  assert.equal(page.all('[data-action="export"]').length, 0);
  assert.deepEqual(page.all('.review-meta > span').map(item => item.text), ['Earlier review', 'Date of service 9 Nov 2026', 'Insurance not given']);
  // listed with its label, and never in the queue
  const row = fixture('encounters.json').encounters.find(item => item.state === 'earlier');
  assert.match(dom(app.documentRow(row)).text, /Earlier review/);
  assert.equal(app.inQueue(row), false);
  assert.equal(app.stateLabel('earlier', ''), 'Earlier review');
});

test('Review again posts retry, then reads the document again and polls while the new coding review runs', async () => {
  const doc = fixture('encounter-earlier.json');
  const queued = clone(doc);
  Object.assign(queued, { state: 'processing', state_label: 'Processing', round: { number: 1, trigger: 'retry', finished_at: null } });
  Object.assign(queued.progress, { phase: 'queued', busy: true, message: '', can_stop: true, can_retry: false });
  queued.readiness.blockers = ['The coding review has not finished.'];
  const address = `/api/encounters/${doc.id}`;
  const answers = [
    { match: (method, url) => method === 'POST' && url === `${address}/retry`, status: 201, body: { round: queued.round } },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: queued },
  ];
  await withPage({ answers }, async ({ calls, element }) => {
    Object.assign(app.state, { doc, route: { name: 'doc', id: doc.id }, routeSerial: 7, docKey: '', viewerKey: '' });
    const button = dom(app.progressPanel(doc, ui(doc))).one('button[data-action="retry"]');
    assert.equal(button.text.trim(), 'Review again');
    // the click, as the page's one click handler receives it
    const clicked = fakeElement({ dataset: { action: button.attr('data-action') } });
    app.onClick({ target: { closest: selector => (selector === '[data-action]' ? clicked : null) } });
    for (let turn = 0; turn < 20 && !app.state.poll.timer; turn += 1) await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(posted(calls), [{ url: `${address}/retry`, body: {} }]);
    const reads = calls.filter(call => call.method === 'GET' && call.url === address);
    assert.equal(reads.length, 1, 'the document is read again once the retry is accepted');
    assert.ok(calls.indexOf(reads[0]) > calls.findIndex(call => call.method === 'POST'), 'after the retry, not before');
    assert.equal(app.state.doc.progress.phase, 'queued');
    assert.ok(app.state.poll.timer, 'and polled while it runs');
    assert.equal(element('#toast').textContent, 'The coding review starts again.');
    assert.match(element('#main').innerHTML, /data-phase="queued"/);
  });
  // a refusal is said in the server's words, and nothing is read again
  await withPage({ answers: [{ status: 409, body: { error: 'This document cannot be coded again right now.' } }] }, async ({ calls, element }) => {
    Object.assign(app.state, { doc, route: { name: 'doc', id: doc.id }, routeSerial: 7 });
    await app.progressAction('retry', fakeElement());
    assert.equal(element('#toast').textContent, 'This document cannot be coded again right now.');
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === address).length, 0);
    assert.equal(app.state.poll.timer, 0);
  });
});

test('polling follows the review: queued, reading and checking poll; finished, failed and stopped do not', () => {
  assert.equal(app.shouldPoll(fixture('encounter-reading.json')), true);
  assert.equal(app.shouldPoll(fixture('encounter-checking.json')), true);
  for (const name of ['encounter-ready.json', 'encounter-failed.json', 'encounter-no-codes.json', 'encounter-awaiting-answer.json', 'encounter-earlier.json', 'encounter-word.json']) {
    assert.equal(app.shouldPoll(fixture(name)), false, name);
  }
  assert.equal(app.shouldPoll({ state: 'processing' }), true, 'a document said to be processing is polled even without its progress');
  assert.equal(app.shouldPoll({ progress: { phase: 'done', busy: true } }), true, 'the server\'s busy flag wins');
  assert.equal(app.shouldPoll(null), false);
});

test('the answers payload: every answered question, trimmed, in the order asked, as {answers: [{question_id, text}]}', () => {
  const doc = fixture('encounter-awaiting-answer.json');
  const [first, second] = doc.questions.map(question => question.id);
  assert.deepEqual(app.answersPayload(doc, new Map([[second, '  Not performed.  '], [first, 'With a cold snare.\nRetrieved.']])),
    { answers: [{ question_id: first, text: 'With a cold snare.\nRetrieved.' }, { question_id: second, text: 'Not performed.' }] });
  assert.deepEqual(app.answersPayload(doc, new Map([[first, 'Snare.'], [second, '   '], ['not-asked', 'x']])), { answers: [{ question_id: first, text: 'Snare.' }] });
  assert.equal(app.answersPayload(doc, new Map()), 'Write an answer to at least one question, then send.');
  assert.equal(app.answersPayload(doc, new Map([['not-asked', 'x']])), 'Write an answer to at least one question, then send.');
  assert.equal(app.answersPayload(doc, null), 'Write an answer to at least one question, then send.');
  // 2,000 characters as the server counts them (code points): an astral character counts once
  assert.equal(app.answersPayload(doc, new Map([[first, '\u{1F600}'.repeat(2000)]])).answers[0].text.length, 4000);
  assert.match(app.answersPayload(doc, new Map([[first, 'x'.repeat(2001)]])), /at most 2,000 characters/);
  assert.equal(app.MAX_ANSWER_CHARS, 2000);
});

test('questions: a reviewer types an answer per question; a busy review or a viewer reads them only', () => {
  const doc = fixture('encounter-awaiting-answer.json');
  const [first] = doc.questions.map(question => question.id);
  const page = dom(app.questionsPanel(doc, ui(doc, { answers: new Map([[first, 'Typed <b>before</b> a redraw']]) })));
  assert.equal(page.one('textarea[data-answer]').text, 'Typed <b>before</b> a redraw', 'a typed answer survives a redraw, as text');
  assert.equal(page.one('textarea').attr('maxlength'), '2000');
  assert.match(page.one('.question-row').text, /^Question 1How was the 12 mm/);
  assert.equal(page.one('.question-codes').text, 'About 45385');
  assert.match(page.one('.questions-head p').text, /2 questions about this document/);
  assert.match(page.one('.questions-actions p').text, /decisions on these codes do not carry over/);
  const busy = clone(doc);
  busy.progress = { ...busy.progress, phase: 'reading', busy: true };
  const waiting = dom(app.questionsPanel(busy, ui(busy)));
  assert.equal(waiting.all('textarea').length, 0);
  assert.equal(waiting.one('#sendAnswers'), null);
  assert.equal(waiting.all('.question-row[data-question]').length, 2);
  assert.match(waiting.one('.questions-head p').text, /once the coding review has finished/);
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  assert.match(dom(app.questionsPanel(viewer, ui(viewer))).one('.questions-head p').text, /A reviewer can answer/);
  assert.equal(app.questionsPanel({ ...doc, questions: [] }, ui(doc)), '');
  // earlier answers are listed under the questions
  const reviewed = dom(render(fixture('encounter-reviewed.json')));
  assert.equal(reviewed.one('#answersPanel h2').text, 'Earlier answers');
  assert.match(reviewed.one('#answersPanel .answer-item').text, /^Were both colon polyps removed.*Yes\. Both were removed.*Reviewer, 20 Nov 2026, 07:31 UTC$/s);
});

test('documentation notes are listed as written once the review is done, and never called empty while it runs', () => {
  const asking = dom(render(fixture('encounter-awaiting-answer.json')));
  assert.equal(asking.one('#notesPanel h2').text, 'Documentation notes');
  assert.deepEqual(asking.all('#notesPanel li').map(item => item.text), fixture('encounter-awaiting-answer.json').notes);
  // a review of the second check that could not be tied to one line is a note too, with its reason as written, and the
  // panel's lead says so (FIX-SPEC-2 section 3)
  const placed = fixture('encounter-needs-review.json');
  const unplaced = placed.notes.filter(note => note.startsWith(`${UNPLACED_NOTE}: `));
  assert.equal(unplaced.length, 1);
  const placedPage = dom(render(placed));
  assert.deepEqual(placedPage.all('#notesPanel li').map(item => item.text), placed.notes);
  assert.match(placedPage.one('#notesPanel p').text, /any comment of the second check that could not be tied to one line/);
  const none = clone(fixture('encounter-ready.json'));
  none.notes = [];
  assert.match(dom(render(none)).one('#notesPanel').text, /made no notes/);
  assert.match(dom(render(fixture('encounter-word.json'))).one('#notesPanel').text, /made no notes/);
  assert.equal(dom(render(fixture('encounter-reading.json'))).one('#notesPanel'), null);
  assert.equal(dom(render(fixture('encounter-earlier.json'))).one('#notesPanel'), null, 'an earlier review has no coding review to have made notes');
});

test('empty code lists say why, in the review\'s own state', () => {
  assert.equal(app.emptyCodesText(fixture('encounter-reading.json')), 'Codes appear here when the coding review finishes.');
  assert.equal(app.emptyCodesText(fixture('encounter-failed.json')), 'No codes: the coding review could not finish.');
  assert.equal(app.emptyCodesText(fixture('encounter-no-codes.json')), 'The coding review found no CPT code to report for this document.');
  assert.equal(app.emptyCodesText(fixture('encounter-earlier.json')), 'Codes appear here once the document is reviewed again with the current version.');
  const page = dom(render(fixture('encounter-no-codes.json')));
  assert.equal(page.one('ol#codesList').attr('hidden'), '');
  assert.equal(page.all('ol#codesList > li').length, 0);
  assert.match(page.one('#quotesPanel').text, /No passage of the document is quoted/);
  assert.match(dom(render(fixture('encounter-reading.json'))).one('#quotesPanel').text, /appear here when the coding review finishes/);
});

test('the tally and the export dialog never claim an approval the server did not report', () => {
  assert.equal(app.tallyText(fixture('encounter-ready.json')), '3 ready for approval · 1 not supported');
  assert.equal(app.tallyText(fixture('encounter-reviewed.json')), '2 approved · 1 rejected');
  assert.equal(app.tallyText(fixture('encounter-needs-review.json')), '2 ready for approval · 1 needs your review');
  assert.equal(app.tallyText(fixture('encounter-same-code.json')), '1 rejected · 2 ready for approval · 1 needs your review');
  assert.equal(app.tallyText(fixture('encounter-no-codes.json')), 'No codes found', 'a finished review with no codes says so');
  assert.equal(app.tallyText(fixture('encounter-reading.json')), 'No codes yet');
  const options = doc => dom(app.exportOptions(doc)).all('[data-export-kind]').map(option => [option.attr('data-export-kind'), option.attr('data-export-fmt'), option.attr('disabled') === null]);
  assert.deepEqual(options(fixture('encounter-ready.json')), [['draft', 'pdf', true], ['approved', 'pdf', false]]);
  assert.deepEqual(options(fixture('encounter-reviewed.json')), [['draft', 'pdf', true], ['approved', 'pdf', true]]);
  assert.deepEqual(options(fixture('encounter-reading.json')).map(option => option[2]), [false, false]);
  assert.deepEqual(dom(app.exportOptions(fixture('encounter-ready.json'))).all('.export-blockers li').map(item => item.text), ['No code has been approved.']);
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    if (doc.readiness.approved !== true) assert.doesNotMatch(app.exportStatusText(doc), /is approved/, name);
  }
  // the downloads in the order served, newest first; one from an earlier coding review is still linked, and says so
  const served = fixture('encounter-reviewed.json').reports;
  assert.deepEqual(served.map(report => report.generated_at), ['2026-11-20T07:55:00Z', '2026-11-20T07:24:00Z'], 'the fixture is newest first, as the server sends it');
  const reports = dom(app.exportOptions(fixture('encounter-reviewed.json'))).all('.report-item');
  assert.deepEqual(reports.map(item => [item.attr('class'), item.one('a').attr('href')]), [
    ['report-item', '/api/reports/f6100000-0000-4000-8000-000000000002/download'], ['report-item earlier', '/api/reports/f6100000-0000-4000-8000-000000000001/download']]);
  assert.match(reports[0].one('small').text, /^Approved codes · CSV · 20 Nov 2026, 07:55 UTC$/);
  assert.match(reports[1].one('small').text, /Earlier: made before a later decision or coding review/);
  // whatever order the server sends is the order shown: nothing is re-sorted on the page
  const reversed = clone(fixture('encounter-reviewed.json'));
  reversed.reports.reverse();
  assert.deepEqual(dom(app.exportOptions(reversed)).all('.report-item a').map(link => link.attr('href')), reversed.reports.map(report => report.download_url));
  assert.equal(dom(app.reportItem({ filename: 'x.txt', download_url: 'javascript:alert(1)', current: true })).one('a'), null);
});

test('the page offers a download whenever the server allows one: a finished review with no codes can still be downloaded as a draft', () => {
  const doc = fixture('encounter-no-codes.json');
  assert.deepEqual([doc.codes.length, doc.reports.length, doc.readiness.draft, doc.readiness.approved], [0, 0, true, false]);
  const page = dom(render(doc));
  assert.ok(page.all('[data-action="export"]').length > 0, 'the export dialog can be opened');
  assert.deepEqual(page.all('[data-action="export"]').map(button => button.text.trim()), ['Download', 'Review and download']);
  assert.equal(page.one('.review-tally').text, 'No codes found');
  assert.equal(page.one('.review-readiness').text, 'You can download the draft report as a PDF. Approve codes to download the approved report.');
  assert.equal(page.one('.results-empty').text, 'The coding review found no CPT code to report for this document.');
  // the dialog it opens offers the draft, and the approved download stays closed until a code is approved
  assert.deepEqual(dom(app.exportOptions(doc)).all('[data-export-kind]').map(option => [option.attr('data-export-kind'), option.attr('data-export-fmt'), option.attr('disabled') === null]),
    [['draft', 'pdf', true], ['approved', 'pdf', false]]);
  // nothing the server allows and nothing made earlier: no button
  for (const name of ['encounter-reading.json', 'encounter-checking.json', 'encounter-failed.json', 'encounter-earlier.json']) {
    assert.equal(dom(render(fixture(name))).all('[data-action="export"]').length, 0, name);
  }
  // downloads made earlier are listed even while nothing new can be made
  const listed = clone(fixture('encounter-failed.json'));
  listed.reports = clone(fixture('encounter-reviewed.json').reports).map(report => ({ ...report, current: false }));
  assert.ok(dom(render(listed)).all('[data-action="export"]').length > 0);
});

// --- the export dialog: the PDF first (the physician PDF, owner directive 2026-11-21) -------------------------------

// The server's own sentences the dialog shows, read from studio/exports.py so a test cannot drift from them.
const EXPORTS_SOURCE = fs.readFileSync(path.join(ROOT, 'studio', 'exports.py'), 'utf8');
const serverSentence = name => new RegExp(`^${name} = '([^'\\n]+)'$`, 'm').exec(EXPORTS_SOURCE)?.[1];
const PDF_NOT_MADE = serverSentence('PDF_NOT_MADE');
const FORMAT_REQUIRED = serverSentence('FORMAT_REQUIRED');
const PDF_NOTES = {
  draft: 'Every code with its status, any saved decision, the evidence and what still needs a decision.',
  approved: 'Only approved codes, with who approved them and when.',
};
// what each control of the export dialog is: [kind, format, disabled, busy, its words]
const controlsOf = html => dom(html).all('[data-export-kind]').map(item => [item.attr('data-export-kind'), item.attr('data-export-fmt'),
  item.attr('disabled') !== null, item.attr('aria-busy') === 'true', (item.one('small') || item).text.trim()]);

test('the export dialog offers each group its PDF, the report for the doctor and the only one made, as the primary button; no data file follows', () => {
  assert.equal(PDF_NOT_MADE, 'The PDF could not be made. Nothing was saved. Try again.');
  assert.equal(FORMAT_REQUIRED, 'Choose a draft or an approved PDF report.');
  const page = dom(app.exportOptions(fixture('encounter-ready.json')));
  const groups = page.all('.export-group');
  assert.deepEqual(groups.map(group => group.one('.evidence-label').text), ['Draft report', 'Approved report']);
  for (const [group, kind] of [[groups[0], 'draft'], [groups[1], 'approved']]) {
    // the group's one control is its PDF, a primary button (owner direction 2026-11-21: no TXT or CSV is made)
    const controls = group.all('[data-export-kind]');
    assert.deepEqual(controls.map(item => [item.tag, item.attr('type'), item.attr('class'), item.attr('data-export-kind'), item.attr('data-export-fmt')]), [
      ['button', 'button', 'button primary export-pdf', kind, 'pdf']]);
    assert.equal(controls[0].text.trim(), 'Download PDF');
    // the line under it says what that PDF holds, and is the button's description
    const note = group.one(`p#${controls[0].attr('aria-describedby')}`);
    assert.equal(note?.attr('class'), 'export-pdf-note', kind);
    assert.equal(note.text, PDF_NOTES[kind]);
    // no "Other formats": nothing beside the PDF offers the codes as a data file
    assert.deepEqual([group.all('.export-other').length, group.all('.export-option').length, group.all('.export-format').length], [0, 0, 0], kind);
    assert.doesNotMatch(group.text, /Other formats|CSV|TXT|spreadsheet|plain text/, kind);
  }
  assert.deepEqual(page.all('[data-export-fmt]').map(item => item.attr('data-export-fmt')), ['pdf', 'pdf'], 'the dialog offers no format but the PDF');
  assert.notEqual(groups[0].one('.export-pdf').attr('aria-describedby'), groups[1].one('.export-pdf').attr('aria-describedby'));
  // in order: the label, the PDF, its line, then why the approved report waits (when it does), and nothing after
  const order = group => group.children.filter(child => typeof child !== 'string').map(child => child.attr('class'));
  assert.deepEqual(order(groups[0]), ['evidence-label', 'button primary export-pdf', 'export-pdf-note']);
  assert.deepEqual(order(groups[1]), ['evidence-label', 'button primary export-pdf', 'export-pdf-note', 'export-blockers']);
  // the enable rules are the readiness's: the draft PDF now, the approved PDF once a code is approved
  assert.deepEqual(controlsOf(app.exportOptions(fixture('encounter-ready.json'))).map(([kind, fmt, disabled]) => [kind, fmt, disabled]), [
    ['draft', 'pdf', false], ['approved', 'pdf', true]]);
  assert.deepEqual(order(dom(app.exportOptions(fixture('encounter-reviewed.json'))).all('.export-group')[1]),
    ['evidence-label', 'button primary export-pdf', 'export-pdf-note'], 'nothing waits once a code is approved');
  // the walk's hook (ops/walk.cjs exportPdf): each report is an .export-pdf of #exportOptions, by its kind and the format pdf
  for (const kind of ['draft', 'approved']) {
    assert.equal(page.all(`.export-pdf[data-export-kind="${kind}"][data-export-fmt="pdf"]`).length, 1, kind);
  }
});

test('while a file is made every option waits, and the one chosen says it is being prepared', () => {
  const doc = fixture('encounter-reviewed.json');
  const pdf = (kind, busy) => [kind, 'pdf', true, busy, busy ? 'Preparing PDF…' : 'Download PDF'];
  // the draft PDF: every option disabled, that one busy and saying so
  assert.deepEqual(controlsOf(app.exportOptions(doc, { kind: 'draft', fmt: 'pdf' })), [pdf('draft', true), pdf('approved', false)]);
  // the approved PDF: every option disabled, that one busy and saying so
  assert.deepEqual(controlsOf(app.exportOptions(doc, { kind: 'approved', fmt: 'pdf' })), [pdf('draft', false), pdf('approved', true)]);
  // another document's file: everything waits and nothing here is named
  assert.deepEqual(controlsOf(app.exportOptions(doc, { kind: null, fmt: null })).map(([, , disabled, busy]) => [disabled, busy]), Array(2).fill([true, false]));
  // nothing being made: as the readiness allows
  assert.deepEqual(controlsOf(app.exportOptions(doc)).map(([, , disabled, busy]) => [disabled, busy]), Array(2).fill([false, false]));
  // the earlier downloads stay links while a file is made
  assert.equal(dom(app.exportOptions(doc, { kind: 'draft', fmt: 'pdf' })).all('.report-item a[download]').length, doc.reports.length);
});

test('an earlier download names its format beside its kind and time; one served without a format still renders, linked', () => {
  const base = { kind: 'approved', filename: 'CPT-Studio-approved-r2-20261121T090000.pdf', generated_at: '2026-11-21T09:00:00Z',
    download_url: `/api/reports/${UUID}/download`, current: true };
  const meta = report => dom(app.reportItem(report)).one('small').text;
  assert.equal(meta({ ...base, fmt: 'pdf' }), 'Approved codes · PDF · 21 Nov 2026, 09:00 UTC');
  assert.equal(meta({ ...base, kind: 'draft', fmt: 'csv' }), 'Codes (draft) · CSV · 21 Nov 2026, 09:00 UTC');
  assert.equal(meta({ ...base, fmt: 'txt' }), 'Approved codes · TXT · 21 Nov 2026, 09:00 UTC');
  assert.equal(meta({ ...base, fmt: 'pdf', current: false }),
    'Approved codes · PDF · 21 Nov 2026, 09:00 UTC · Earlier: made before a later decision or coding review; it may not show the current codes');
  // an old download served without a format, or with one the page does not know, keeps its kind, time and link
  const old = { ...base, kind: 'draft', filename: 'CPT-Studio-draft-r1-20261101T080000.txt' };
  assert.equal(meta(old), 'Codes (draft) · 21 Nov 2026, 09:00 UTC');
  assert.deepEqual([dom(app.reportItem(old)).one('a').attr('href'), dom(app.reportItem(old)).one('a').text], [old.download_url, old.filename]);
  for (const fmt of ['zip', 'PDF', 'constructor', '__proto__', null, 7]) assert.equal(meta({ ...base, fmt }), 'Approved codes · 21 Nov 2026, 09:00 UTC', String(fmt));
  // in the dialog: a new PDF beside the old CSV and TXT, in the order served
  const doc = clone(fixture('encounter-reviewed.json'));
  doc.reports.unshift({ id: 'f6100000-0000-4000-8000-0000000000c1', ...base, fmt: 'pdf', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000c1/download' });
  assert.deepEqual(dom(app.exportOptions(doc)).all('.report-item').map(item => [item.one('a').attr('href'), item.one('small').text.split(' · ').slice(0, 2).join(' · ')]), [
    ['/api/reports/f6100000-0000-4000-8000-0000000000c1/download', 'Approved codes · PDF'],
    ['/api/reports/f6100000-0000-4000-8000-000000000002/download', 'Approved codes · CSV'],
    ['/api/reports/f6100000-0000-4000-8000-000000000001/download', 'Codes (draft) · TXT']]);
});

test('the export dialog\'s copy presents the PDF as the doctor\'s report, the only one made; its status is announced', () => {
  const dialog = dom(fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8')).one('dialog#exportDialog');
  const copy = dialog.one('p.dialog-copy').text;
  assert.match(copy, /^The PDF is the report for the doctor, made on the server from the saved codes and decisions/);
  // it promises no data file beside the PDF (owner direction 2026-11-21: no TXT or CSV is made), and says every report is
  // marked synthetic
  assert.doesNotMatch(copy, /CSV|TXT|data files?/);
  assert.match(copy, /Every report is marked as synthetic data, not for billing\.$/);
  assert.deepEqual([dialog.one('#exportStatus').attr('role'), dialog.one('#exportError').attr('role')], ['status', 'alert']);
  assert.ok(dialog.one('div#exportOptions'));
  // the review bar and the dialog's status say "report"
  assert.equal(app.readinessText(fixture('encounter-reviewed.json')), 'The approved report can be downloaded as a PDF. It lists only approved codes.');
  assert.equal(app.readinessText(fixture('encounter-reading.json')), 'Downloads become available when the coding review finishes.');
  assert.equal(app.exportStatusText(fixture('encounter-ready.json')), 'Draft only: the codes are the coding review\'s, not approvals. Before the approved report: No code has been approved.');
  assert.equal(app.exportStatusText(fixture('encounter-reviewed.json')), 'At least one code is approved. The approved report lists only approved codes, with who approved them and when.');
});

test('list rows show the state, the kind, the insurance and the date; the queue lists what waits on the member', () => {
  const rows = fixture('encounters.json').encounters;
  const page = dom(app.listBody('documents', rows));
  assert.equal(page.all('a.document-row').length, rows.length);
  const ready = page.all('a.document-row').find(row => row.attr('href') === '#doc/f5000000-0000-4000-8000-000000000001');
  assert.match(ready.text, /Synthetic EGD and colonoscopy, RileyUploaded file · MedicareReady for approval2 Nov 2026/);
  const pasted = page.all('a.document-row').find(row => row.attr('href') === '#doc/f8000000-0000-4000-8000-000000000001');
  assert.match(pasted.text, /Pasted textNo codes foundNot entered/);
  const queue = dom(app.listBody('queue', rows)).all('a.document-row').map(row => row.attr('href'));
  assert.deepEqual(queue, ['#doc/f3000000-0000-4000-8000-000000000001', '#doc/fd000000-0000-4000-8000-000000000001', '#doc/f4000000-0000-4000-8000-000000000001',
    '#doc/f5000000-0000-4000-8000-000000000001', '#doc/f9000000-0000-4000-8000-000000000001', '#doc/fc000000-0000-4000-8000-000000000001']);
  assert.match(app.listDescription('queue', app.listBody('queue', rows).match(/class="document-row"/g).length), /^6 documents wait on you: questions to answer, or codes to review or approve\.$/);
  const earlier = page.all('a.document-row').find(row => row.attr('href') === '#doc/fb000000-0000-4000-8000-000000000001');
  assert.match(earlier.text, /Synthetic colonoscopy report, earlier reviewUploaded fileEarlier review9 Nov 2026/);
  assert.equal(app.listDescription('queue', 0), 'No document waits on you for an answer or a decision.');
  assert.match(dom(app.listBody('queue', [])).text, /Nothing is waiting for you/);
  assert.equal(dom(app.listBody('workspace', rows)).all('a.document-row').length, 5);
  assert.match(dom(app.inviteMarkup(rows)).text, /Most recent · Processing · service date not entered/);
});

test('model-written text (reasons, questions, notes, quotes) is escaped wherever it is drawn', () => {
  const payload = '<img src=x onerror=alert(1)>"\'`&';
  const poison = value => {
    if (typeof value === 'string') return `${value}${payload}`;
    if (Array.isArray(value)) return value.map(poison);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, poison(item)]));
    return value;
  };
  for (const name of ENCOUNTERS) {
    const plain = fixture(name);
    const doc = poison(plain);
    // keep the structure the page needs to draw everything: lines, statuses, actions, phase and the addresses
    doc.codes.forEach((code, index) => Object.assign(code, { line: plain.codes[index].line, status: plain.codes[index].status, allowed_actions: plain.codes[index].allowed_actions, decision: code.decision && { ...code.decision, action: plain.codes[index].decision.action } }));
    Object.assign(doc.progress, { phase: plain.progress.phase });
    Object.assign(doc.document, { view_url: plain.document.view_url, original_url: plain.document.original_url, media_type: plain.document.media_type, kind: plain.document.kind, view_media_type: plain.document.view_media_type });
    const html = [markup(doc), app.listBody('documents', [poison(fixture('encounters.json').encounters[0])]), app.inviteMarkup([poison(fixture('encounters.json').encounters[0])])].join('\n');
    assert.doesNotMatch(html, /<img/i, name);
    assert.doesNotMatch(html, /\son\w+="/i, `${name}: no handler attribute`);
    assert.doesNotMatch(html, /="[^"]*"[^\s>/]/, `${name}: no attribute breakout`);
    assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;&quot;&#x27;&#x60;&amp;/, name);
    // the model's own words are shown as written, once decoded
    const page = dom(render(doc));
    for (const code of doc.codes) {
      const row = page.all('li.code-row').find(item => item.attr('data-line') === code.line);
      assert.ok(row, `${name} ${code.line}`);
      assert.equal(row.attr('data-code'), code.code);
      assert.equal(row.one('.code-reason').text, code.reason.trim());
      assert.deepEqual(row.all('.code-quote .quote-text').map(item => item.text), code.quotes.map(quote => quote.text.trim()));
    }
    for (const note of doc.notes) assert.ok(page.all('#notesPanel li').some(item => item.text === note.trim()), name);
    for (const question of doc.questions) assert.ok(page.all('.question-text').some(item => item.text === question.text.trim()), name);
  }
});

test('no customer page names a vendor, a model or the machinery, in text or attributes, and the scan catches a planted name', () => {
  for (const name of ENCOUNTERS) assert.deepEqual(leaks(markup(fixture(name))), [], name);
  const rows = fixture('encounters.json').encounters;
  const lists = [app.overviewView(), app.documentsView('documents'), app.documentsView('queue'), app.howItWorksView(), app.listBody('documents', rows),
    app.listBody('queue', rows), `<p>${app.listDescription('queue', 6)}</p>`, `<p>${app.listDescription('documents', 117)}</p>`, app.inviteMarkup(rows), app.ackView({ id: rows[0].id, at: 0 }),
    app.messageView('This document is not available.', 'It does not exist, or it is not in your workspace.', true)].join('\n');
  assert.deepEqual(leaks(lists), []);
  const planted = clone(fixture('encounter-ready.json'));
  planted.codes[0].reason = 'Chosen by Claude.';
  planted.notes.push('See /ops/encounters for the request id.');
  const found = leaks(markup(planted)).join('\n');
  for (const word of ['Claude', '/ops/', 'request id']) assert.match(found, new RegExp(word.replace('/', '\\/'), 'i'), word);
});

test('the customer bundle, stylesheet and templates pass the shipped bundle scan and name no vendor, model or machinery', () => {
  const files = [BUNDLE, STYLES, path.join(TEMPLATES, 'index.html'), path.join(TEMPLATES, 'login.html')];
  for (const file of files) {
    const source = fs.readFileSync(file, 'utf8');
    assert.deepEqual(shippedHits(source, 'bundle'), [], file);
    assert.deepEqual([...source.matchAll(new RegExp(NAMES.source, 'gi'))].map(match => match[0]), [], file);
    assert.deepEqual([...source.matchAll(new RegExp(WORDS.source, 'gi'))].map(match => match[0]), [], file);
  }
  // the scans find a planted word, so a clean result means something
  assert.deepEqual(shippedHits('// sent to claude-fable-5-2', 'bundle').length > 0, true);
  assert.ok(new RegExp(WORDS.source, 'i').test('the model said'));
  assert.ok(new RegExp(WORDS.source, 'i').test('three tokens'));
  // the page sends Django's CSRF header once
  assert.equal(fs.readFileSync(BUNDLE, 'utf8').split('X-CSRFToken').length - 1, 1);
});

test('the old page\'s concepts are gone from the bundle and the template', () => {
  const bundle = fs.readFileSync(BUNDLE, 'utf8');
  for (const old of ['addend', 'recheck', 'second-review', 'details_needed', 'detail-row', 'earlier_codes', 'earlierCodes', 'what_changed', 'whatChanged',
    'not_separately', 'other_codes', 'modifier_review', 'reviewModifier', 'date_conflict', 'reinstate', 'retry-reading', 'retry-update', 'being_confirmed',
    'Still open', 'Earlier decisions', 'use_document', 'proposal', 'layoutDocument', 'sourcePanel', 'evidence-mark']) {
    assert.ok(!bundle.includes(old), old);
  }
  const template = fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8');
  for (const old of ['addendum', 'reviewModifier', 'Modifier <span>']) assert.ok(!template.includes(old), old);
});

test('the review dialog: #reviewAcknowledgement holds exactly the session\'s statement, and the note is optional', () => {
  const page = dom(fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8'));
  const label = page.one('dialog#reviewDialog label#reviewAcknowledgement');
  assert.ok(label, 'the statement is a label');
  assert.deepEqual(label.children.map(child => (typeof child === 'string' ? 'text' : `${child.tag}#${child.attr('id')}`)), ['input#reviewAckBox', 'span#reviewAckText'],
    'nothing but the checkbox and the statement, so the label reads as the statement alone');
  assert.equal(page.one('#reviewAckBox').attr('type'), 'checkbox');
  // the line being decided is stated under its status: its units and modifiers, then its own reason
  assert.deepEqual(page.one('dialog#reviewDialog .review-summary div').children.map(child => child.attr('id')), ['reviewStatus', 'reviewLine', 'reviewSummary']);
  assert.ok(page.one('dialog#reviewDialog small#reviewLine.review-line'));
  assert.ok(page.one('dialog#reviewDialog textarea#reviewNote'));
  assert.ok(page.one('dialog#reviewDialog button#saveReview[type="submit"]'));
  // and release 1's two: the idle warning (B5) and the one confirmation the team and the Word download ask (C4, C6)
  const dialogs = ['uploadDialog', 'reviewDialog', 'exportDialog', 'aboutDialog', 'idleDialog', 'confirmDialog'];
  for (const id of dialogs) assert.ok(page.one(`dialog#${id}`), id);
  assert.equal(page.all('dialog').length, dialogs.length);
});

test('Approve opens the dialog with the session\'s statement; the approval posts {round, line, code, action, acknowledgement, note}', async () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-ready.json');
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc, route: null });
    await app.handleDecision('approve', 'L2', fakeElement());
    assert.equal(element('#reviewAckText').textContent, session.acknowledgement);
    assert.equal(element('#reviewAcknowledgement').hidden, false);
    assert.equal(element('#reviewAckBox').checked, false);
    assert.equal(element('#saveReview').disabled, true, 'no approval until the statement is confirmed');
    assert.equal(element('#reviewCode').textContent, '45385');
    assert.equal(element('#reviewLine').textContent, '1 unit · No modifier');
    assert.equal(element('#reviewSummary').textContent, doc.codes[1].reason);
    assert.equal(element('#reviewDialog').open, true);
    // unconfirmed: nothing is sent
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls), []);
    assert.match(element('#reviewError').textContent, /Confirm the statement/);
    // confirmed, with a note
    element('#reviewAckBox').checked = true;
    element('#reviewNote').value = '  Read page 2.  ';
    await app.submitReview({ preventDefault() {} });
    const [sent] = posted(calls);
    assert.deepEqual(sent, { url: `/api/encounters/${doc.id}/decisions`, body: { round: 1, line: 'L2', code: '45385', action: 'approve', acknowledgement: session.acknowledgement, note: 'Read page 2.' } });
    assert.deepEqual(Object.keys(sent.body), ['round', 'line', 'code', 'action', 'acknowledgement', 'note']);
    const call = calls.find(item => item.method === 'POST');
    assert.deepEqual([call.headers['X-CSRFToken'], call.headers['X-CPT-Studio-Client'], call.headers['Content-Type'], call.credentials, call.cache],
      ['token123', 'customer-2026-11-26', 'application/json', 'same-origin', 'no-store']);
    assert.equal(element('#reviewDialog').open, false);
  });
});

test('Reject asks only for an optional note; Undo posts revoke; an action the server does not allow does nothing', async () => {
  const session = fixture('session-agent.json');
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: fixture('encounter-needs-review.json'), route: null });
    await app.handleDecision('reject', 'L3', fakeElement());
    assert.equal(element('#reviewAcknowledgement').hidden, true);
    assert.equal(element('#reviewAckText').textContent, '');
    assert.equal(element('#saveReview').disabled, false);
    assert.equal(element('#reviewLine').textContent, '1 unit · Modifier 59');
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).pop().body, { round: 1, line: 'L3', code: '45380', action: 'reject', acknowledgement: '', note: '' });
    // the round named is the one the page shows (the reviewed document is on its second coding review)
    Object.assign(app.state, { doc: fixture('encounter-reviewed.json') });
    await app.handleDecision('revoke', 'L1', fakeElement());
    assert.deepEqual(posted(calls).pop().body, { round: 2, line: 'L1', code: '43239', action: 'revoke', acknowledgement: '', note: '', decision: 'f6200000-0000-4000-8000-000000000001' });
    const before = calls.length;
    element('#reviewDialog').open = false;
    await app.handleDecision('approve', 'L1', fakeElement());
    await app.handleDecision('revoke', 'L9', fakeElement());
    await app.handleDecision('revoke', '43239', fakeElement());
    assert.equal(calls.length, before, 'a code is never a line: nothing is sent');
    assert.equal(element('#reviewDialog').open, false);
  });
  // the agent's approval dialog says it is an agent-executed review, with the agent's own statement
  await withPage({}, async ({ element }) => {
    Object.assign(app.state, { session, doc: fixture('encounter-ready.json'), route: null });
    await app.handleDecision('approve', 'L1', fakeElement());
    assert.equal(element('#reviewAckText').textContent, session.acknowledgement);
    assert.match(element('#reviewCopy').textContent, /agent-executed synthetic review/);
  });
});

test('one code on two lines: each row is drawn, quoted, reviewed and decided as its own line', async () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-same-code.json');
  const [rejected, added] = ['L3', 'M1'].map(line => doc.codes.find(code => code.line === line));
  assert.deepEqual([rejected.code, added.code], ['45380', '45380']);
  const page = dom(render(doc));
  // two rows of 45380, each with its own id, its own buttons and its own quotes
  const rows = page.all('li.code-row[data-code="45380"]');
  assert.deepEqual(rows.map(row => [row.attr('id'), row.attr('data-line'), row.attr('data-decision'), row.one('.code-modifiers').text]),
    [['code-L3', 'L3', 'reject', 'No modifier'], ['code-M1', 'M1', null, 'Modifier XS']]);
  assert.deepEqual(rows.map(row => row.all('button[data-decision]').map(button => [button.attr('id'), button.attr('data-line')])),
    [[['act-L3-revoke', 'L3']], [['act-M1-approve', 'M1'], ['act-M1-reject', 'M1']]]);
  assert.deepEqual(rows.map(row => row.all('.code-quote').map(quote => quote.attr('data-quote'))), [['L3#0'], ['M1#0']]);
  assert.deepEqual(page.all('#quotesPanel .quote[data-code="45380"]').map(quote => [quote.attr('data-line'), quote.attr('data-quote')]), [['L3', 'L3#0'], ['M1', 'M1#0']]);
  // choosing one line's quote selects that line's passage only
  await withPage({ elements: { documentViewer: fakeElement({ src: '', scrollIntoView() {} }) } }, async () => {
    Object.assign(app.state, { doc, route: null });
    app.showQuote('M1#0');
    assert.equal(app.state.selectedQuote, 'M1#0');
  });
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc, route: null });
    // the decided line offers only Undo: approving it does nothing, and never reaches the other line
    await app.handleDecision('approve', 'L3', fakeElement());
    assert.equal(element('#reviewDialog').open, false);
    // the added line's dialog shows that line: its code, units and modifier, its status and its own reason
    await app.handleDecision('approve', 'M1', fakeElement());
    assert.equal(element('#reviewDialog').open, true);
    assert.deepEqual([element('#reviewCode').textContent, element('#reviewLine').textContent, element('#reviewStatus').textContent, element('#reviewSummary').textContent],
      ['45380', 'Units not given · Modifier XS', 'Needs your review', added.reason]);
    assert.notEqual(element('#reviewSummary').textContent, rejected.reason);
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).pop().body, { round: 2, line: 'M1', code: '45380', action: 'approve', acknowledgement: session.acknowledgement, note: '' });
    // Undo on the rejected line names that line
    await app.handleDecision('revoke', 'L3', fakeElement());
    assert.deepEqual(posted(calls).pop().body, { round: 2, line: 'L3', code: '45380', action: 'revoke', acknowledgement: '', note: '', decision: 'fc200000-0000-4000-8000-000000000003' });
    assert.equal(posted(calls).length, 2);
  });
  // the page's clicks carry the line: the button's data-line reaches the decision
  await withPage({}, async ({ calls }) => {
    Object.assign(app.state, { session, doc, route: null });
    const button = page.one('#act-L3-revoke');
    const clicked = fakeElement({ dataset: { decision: button.attr('data-decision'), code: button.attr('data-code'), line: button.attr('data-line') } });
    app.onClick({ target: { closest: selector => (selector === '[data-decision]' ? clicked : null) } });
    for (let turn = 0; turn < 20 && !posted(calls).length; turn += 1) await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(posted(calls).map(call => call.body.line), ['L3']);
  });
});

test('a row without a line, or a page without its round number, is shown but never decided', async () => {
  const doc = clone(fixture('encounter-same-code.json'));
  delete doc.codes[3].line;
  const page = dom(render(doc));
  const rows = page.all('li.code-row');
  assert.equal(rows.length, 4, 'every code is drawn');
  assert.deepEqual([rows[3].attr('data-code'), rows[3].attr('data-line'), rows[3].all('button[data-decision]').length], ['45380', '', 0]);
  assert.deepEqual(rows.map(row => row.attr('id')), ['code-L1', 'code-L2', 'code-L3', 'code-row_4']);
  const ids = page.all('[id]').map(element => element.attr('id'));
  assert.equal(new Set(ids).size, ids.length);
  assert.deepEqual(page.all('#quotesPanel .quote').map(quote => quote.attr('data-quote')), ['L1#0', 'L2#0', 'L3#0', 'row-4#0']);
  const roundless = clone(fixture('encounter-same-code.json'));
  roundless.round = null;
  assert.equal(dom(render(roundless)).all('button[data-decision]').length, 0);
  // one line named on two rows: the page cannot tell which row a decision is about, so it decides neither
  const twice = clone(fixture('encounter-same-code.json'));
  twice.codes[3].line = 'L2';
  const doubled = dom(render(twice));
  assert.deepEqual(doubled.all('li.code-row').map(row => [row.attr('id'), row.attr('data-line'), row.all('button[data-decision]').length]),
    [['code-L1', 'L1', 2], ['code-row_2', '', 0], ['code-L3', 'L3', 1], ['code-row_4', '', 0]]);
  const doubledIds = doubled.all('[id]').map(element => element.attr('id'));
  assert.equal(new Set(doubledIds).size, doubledIds.length);
  assert.equal(app.findLine(twice, 'L2'), null);
  for (const [name, broken] of [['roundless', roundless], ['twice', twice]]) {
    await withPage({}, async ({ calls, element }) => {
      Object.assign(app.state, { session: fixture('session.json'), doc: broken, route: null });
      await app.handleDecision('approve', name === 'twice' ? 'L2' : 'M1', fakeElement());
      await app.handleDecision('revoke', name === 'twice' ? 'L2' : 'L3', fakeElement());
      assert.deepEqual([posted(calls), element('#reviewDialog').open], [[], false], name);
    });
  }
});

test('a decision refused because the coding review changed (409) reloads the document and says so; nothing is sent again', async () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-ready.json');
  const address = `/api/encounters/${doc.id}`;
  // the coding review the server has now: a second one, after answers, with another line under L2
  const newer = clone(doc);
  newer.round = { number: 2, trigger: 'answers', finished_at: '2026-11-20T08:40:00Z' };
  newer.codes[1] = { ...newer.codes[1], modifiers: ['PT'], reason: 'A different line of a later coding review.' };
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  const answers = () => [
    { match: (method, url) => method === 'POST' && url === `${address}/decisions`, status: 409, body: changed },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: newer },
  ];
  await withPage({ answers: answers() }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc, route: { name: 'doc', id: doc.id }, routeSerial: 3, docKey: '', viewerKey: app.viewerKey(doc), selectedQuote: 'L2#0' });
    await app.handleDecision('approve', 'L2', fakeElement());
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls), [{ url: `${address}/decisions`, body: { round: 1, line: 'L2', code: '45385', action: 'approve', acknowledgement: session.acknowledgement, note: '' } }]);
    const read = calls.findIndex(call => call.method === 'GET' && call.url === address);
    assert.ok(read > calls.findIndex(call => call.method === 'POST'), 'the document is read again after the refusal');
    assert.equal(app.state.doc.round.number, 2, 'the page now shows the latest coding review');
    // the same original: its viewer is kept, and the heading and the codes are redrawn
    assert.match(element('#reviewHead').innerHTML, /Coding review 2, after your answers/);
    assert.match(element('#reviewColumn').innerHTML, /Modifier PT/);
    assert.equal(element('#main').innerHTML, undefined, 'the viewer is not reloaded');
    assert.equal(app.state.selectedQuote, '', 'a passage chosen on the earlier coding review is not carried to the new one');
    assert.equal(element('#reviewDialog').open, false, 'the dialog of a line that may no longer exist is closed');
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
    assert.equal(app.CHANGED_TEXT, 'This coding review has changed, so nothing was recorded. The page now shows the latest.');
    assert.deepEqual([element('#reviewError').hidden, element('#reviewError').textContent], [true, ''], 'the refusal is not shown as a form error');
  });
  // Undo refused the same way: read again and said
  const reviewed = fixture('encounter-reviewed.json');
  const reviewedAt = `/api/encounters/${reviewed.id}`;
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${reviewedAt}/decisions`, status: 409, body: changed },
    { match: (method, url) => method === 'GET' && url === reviewedAt, status: 200, body: reviewed },
  ] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 4, docKey: '', viewerKey: '' });
    await app.handleDecision('revoke', 'L2', fakeElement());
    assert.deepEqual(posted(calls).map(call => call.body), [{ round: 2, line: 'L2', code: '45385', action: 'revoke', acknowledgement: '', note: '', decision: 'f6200000-0000-4000-8000-000000000002' }]);
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === reviewedAt).length, 1);
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
  });
  // any other refusal stays in the dialog and reads nothing again; a stale build is the update notice, not a reload
  for (const [status, body, outdated] of [[400, { error: 'The acknowledgement is not the current review attestation. Reload the page and approve again.', details: {} }, false],
    [409, { error: 'CPT Studio was updated. Reload this page to continue.', error_code: 'client_outdated' }, true]]) {
    await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/decisions`, status, body }] }, async ({ calls, element }) => {
      Object.assign(app.state, { session, doc, route: { name: 'doc', id: doc.id }, routeSerial: 5, outdated: false });
      await app.handleDecision('approve', 'L2', fakeElement());
      element('#reviewAckBox').checked = true;
      await app.submitReview({ preventDefault() {} });
      assert.equal(calls.filter(call => call.method === 'GET' && call.url === address).length, 0, String(status));
      assert.equal(app.state.outdated, outdated);
      assert.equal(element('#reviewError').textContent, outdated ? app.OUTDATED_TEXT : body.error);
      assert.notEqual(element('#toast').textContent, app.CHANGED_TEXT);
    });
  }
});

test('Undo names the decision it undoes: the id the page shows for the line\'s current decision (LINES-5)', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const shown = reviewed.codes.map(code => code.decision.id);
  assert.deepEqual(shown, ['f6200000-0000-4000-8000-000000000001', 'f6200000-0000-4000-8000-000000000002', 'f6200000-0000-4000-8000-000000000003']);
  await withPage({}, async ({ calls }) => {
    Object.assign(app.state, { session, doc: reviewed, route: null });
    await app.handleDecision('revoke', 'L2', fakeElement());
    assert.deepEqual(posted(calls), [{ url: `${address}/decisions`,
      body: { round: 2, line: 'L2', code: '45385', action: 'revoke', acknowledgement: '', note: '', decision: shown[1] } }]);
  });
  // approve and reject name no decision: there is none on the line yet
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: fixture('encounter-ready.json'), route: null });
    await app.handleDecision('reject', 'L1', fakeElement());
    await app.submitReview({ preventDefault() {} });
    await app.handleDecision('approve', 'L2', fakeElement());
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).map(call => Object.keys(call.body)), [['round', 'line', 'code', 'action', 'acknowledgement', 'note'],
      ['round', 'line', 'code', 'action', 'acknowledgement', 'note']]);
  });
  // a current decision the page cannot name - no id, or one that is not an id - offers no Undo, and none is sent
  for (const id of [undefined, null, '', ' ', 7, 'a decision', 'x'.repeat(65), ['f6200000'], {}]) {
    const doc = clone(reviewed);
    if (id === undefined) delete doc.codes[0].decision.id;
    else doc.codes[0].decision.id = id;
    assert.deepEqual(app.allowedActions(doc.codes[0], doc), [], JSON.stringify(id));
    assert.equal(dom(render(doc)).all('li.code-row[data-line="L1"] button[data-decision]').length, 0, JSON.stringify(id));
    assert.equal(dom(render(doc)).all('li.code-row[data-line="L2"] button[data-decision="revoke"]').length, 1, 'the other lines keep theirs');
    await withPage({}, async ({ calls }) => {
      Object.assign(app.state, { session, doc, route: null });
      await app.handleDecision('revoke', 'L1', fakeElement());
      assert.deepEqual(posted(calls), [], JSON.stringify(id));
    });
  }
  // the page drew Coder13's approval; meanwhile it was undone and Coder19 rejected the line. The Undo names the approval
  // the page showed, the server refuses it (409: not the current decision), and the page reads the document again and
  // says so - it never undoes a decision the member did not see
  const now = clone(reviewed);
  now.codes[0].decision = { id: 'f6200000-0000-4000-8000-000000000009', action: 'reject', by: 'Coder19', at: '2026-11-20T08:10:00Z', note: 'Not documented.' };
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/decisions`, status: 409, body: changed },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: now },
  ] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 11, docKey: '', viewerKey: app.viewerKey(reviewed) });
    await app.handleDecision('revoke', 'L1', fakeElement());
    assert.deepEqual(posted(calls).map(call => call.body.decision), [shown[0]]);
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
    assert.equal(app.state.doc.codes[0].decision.by, 'Coder19', 'the page now shows the decision that stands');
    assert.match(element('#reviewColumn').innerHTML, /Rejected by Coder19/);
  });
});

test('the review dialog keeps the round, line and code it opened on while the page redraws under it (LINES-3)', async () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-ready.json');
  const address = `/api/encounters/${doc.id}`;
  // what the server has once the read lands: a second coding review, with another line under L2
  const newer = clone(doc);
  newer.round = { number: 2, trigger: 'answers', finished_at: '2026-11-20T08:40:00Z' };
  newer.codes[1] = { ...newer.codes[1], modifiers: ['PT'], reason: 'A different line of a later coding review.' };
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/decisions`, status: 201, body: { line: 'L1', code: '43239', action: 'approve' } },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: held },
    { match: (method, url) => method === 'POST' && url === `${address}/decisions`, status: 409, body: changed },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: newer },
  ] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc, route: { name: 'doc', id: doc.id }, routeSerial: 12, docKey: '', viewerKey: app.viewerKey(doc) });
    // L1 is approved, and the read of the document that follows the approval is still in flight
    await app.handleDecision('approve', 'L1', fakeElement());
    element('#reviewAckBox').checked = true;
    const first = app.submitReview({ preventDefault() {} });
    await settle(() => calls.some(call => call.method === 'GET' && call.url === address));
    // meanwhile the member opens L2's dialog: it shows round 1's L2
    await app.handleDecision('approve', 'L2', fakeElement());
    assert.deepEqual([element('#reviewDialog').open, element('#reviewCode').textContent, element('#reviewLine').textContent],
      [true, '45385', '1 unit · No modifier']);
    // the read lands: round 2 has finished, and the page redraws under the open dialog
    release(newer);
    await first;
    assert.equal(app.state.doc.round.number, 2);
    assert.match(element('#reviewColumn').innerHTML, /Modifier PT/);
    assert.equal(element('#reviewDialog').open, true, 'the redraw leaves the dialog open');
    // the member saves: the decision names what the dialog showed - round 1, L2, 45385 - never the round redrawn
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).map(call => call.body), [
      { round: 1, line: 'L1', code: '43239', action: 'approve', acknowledgement: session.acknowledgement, note: '' },
      { round: 1, line: 'L2', code: '45385', action: 'approve', acknowledgement: session.acknowledgement, note: '' }]);
    // the server refuses round 1 (no longer the latest): the dialog closes, the page reads again and says so
    assert.equal(element('#reviewDialog').open, false);
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === address).length, 2);
  });
});

test('a decision posts to the document its dialog opened on, and leaving that document closes the dialog', async () => {
  const session = fixture('session.json');
  const first = fixture('encounter-ready.json');
  const second = { ...clone(first), id: 'f5000000-0000-4000-8000-0000000000b2', title: 'Synthetic second document' };
  // Approve open on the first document's L1, the member goes to the second one (browser Back runs route()): the dialog
  // of a document the page no longer shows is closed, so nothing it showed can be saved on the other one
  await withPage({ answers: [{ match: (method, url) => method === 'GET' && url === `/api/encounters/${second.id}`, status: 200, body: second }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: first, route: { name: 'doc', id: first.id }, routeSerial: 13, docKey: '', viewerKey: app.viewerKey(first) });
    await app.handleDecision('approve', 'L1', fakeElement());
    assert.equal(element('#reviewDialog').open, true);
    global.location.hash = `#doc/${second.id}`;
    click('[data-action]', { action: 'reload-view' });  // route(), as the hash change runs it
    await settle(() => app.state.doc?.id === second.id);
    assert.equal(app.state.doc.id, second.id);
    assert.equal(element('#reviewDialog').open, false, 'the dialog of a document no longer shown is closed');
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls), [], 'nothing is decided once its dialog is gone');
  });
  // and whichever document the page shows when the dialog is saved, the decision goes to the one it opened on
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: first, route: null });
    await app.handleDecision('approve', 'L1', fakeElement());
    app.state.doc = second;
    element('#reviewAckBox').checked = true;
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).map(call => call.url), [`/api/encounters/${first.id}/decisions`]);
  });
});

test('a download names the coding review its dialog was opened on; one refused because it changed reloads the page (LINES-6)', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const report = { id: 'f6100000-0000-4000-8000-0000000000a1', kind: 'approved', fmt: 'pdf', filename: 'CPT-Studio-approved-r2-20261120T090000.pdf',
    generated_at: '2026-11-20T09:00:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000a1/download', current: true };
  // the option posts {kind, fmt, round}: the number of the coding review the page shows; then the download starts
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: report }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 14, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportDialog').open, true);
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(posted(calls), [{ url: `${address}/reports`, body: { kind: 'approved', fmt: 'pdf', round: 2 } }]);
    assert.deepEqual(calls.filter(call => call.download).map(call => [call.download, call.filename]), [[report.download_url, report.filename]]);
  });
  // the dialog was opened on round 1; the page has moved on to round 2 under it: the option still names round 1, the
  // server refuses it (409, no blockers), and the page closes the dialog, reads the document again and says so
  const ready = fixture('encounter-ready.json');
  const later = { ...clone(ready), round: { number: 2, trigger: 'answers', finished_at: '2026-11-20T08:40:00Z' } };
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `/api/encounters/${ready.id}/reports`, status: 409, body: changed },
    { match: (method, url) => method === 'GET' && url === `/api/encounters/${ready.id}`, status: 200, body: later },
  ] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 15, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    app.state.doc = later;
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => element('#toast').textContent === app.CHANGED_TEXT && app.state.doc.round.number === 2 && calls.some(call => call.method === 'GET'));
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'draft', fmt: 'pdf', round: 1 }]);
    assert.equal(element('#exportDialog').open, false, 'the dialog of a coding review that changed is closed');
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === `/api/encounters/${ready.id}`).length, 1, 'the document is read again');
    assert.deepEqual(calls.filter(call => call.download), [], 'nothing is downloaded');
  });
  // a refusal that says what is missing (409 with the readiness blockers) stays in the dialog and reads nothing again
  const blocked = { error: 'The approved export is not available yet.', details: { blockers: ['No code has been approved.'] } };
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 409, body: blocked }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 16, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => element('#exportError').textContent !== '');
    assert.equal(element('#exportError').textContent, 'The approved export is not available yet. No code has been approved.');
    assert.equal(element('#exportDialog').open, true);
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === address).length, 0);
    assert.notEqual(element('#toast').textContent, app.CHANGED_TEXT);
  });
  // a page that does not know which coding review it shows posts no download
  const roundless = { ...clone(reviewed), round: null };
  await withPage({}, async ({ calls }) => {
    Object.assign(app.state, { session, doc: roundless, route: null });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => false);
    assert.deepEqual(posted(calls), []);
  });
});

test('Download PDF posts {kind, fmt: "pdf", round}; it is said to be prepared until the 201, then downloaded, and the dialog lists it', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const report = { id: 'f6100000-0000-4000-8000-0000000000b1', kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r2-20261121T090000.pdf',
    generated_at: '2026-11-21T09:00:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000b1/download', current: true };
  const after = { ...clone(reviewed), reports: [report, ...clone(reviewed.reports)] };
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: report },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: after },
  ] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 31, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).slice(0, 1), [['draft', 'pdf', false, false, 'Download PDF']]);
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    // the request runs: posted once with the round shown; nothing is downloaded or said to be ready
    assert.deepEqual(posted(calls), [{ url: `${address}/reports`, body: { kind: 'draft', fmt: 'pdf', round: 2 } }]);
    assert.deepEqual(calls.filter(call => call.download), []);
    assert.equal(element('#exportStatus').textContent, 'Your PDF is being prepared. The download starts when it is ready.');
    const waiting = controlsOf(element('#exportOptions').innerHTML);
    assert.deepEqual(waiting.map(([, , disabled]) => disabled), Array(2).fill(true), 'every option waits');
    assert.deepEqual(waiting.filter(([, , , busy]) => busy), [['draft', 'pdf', true, true, 'Preparing PDF…']]);
    // another choice meanwhile sends nothing
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    assert.equal(posted(calls).length, 1);
    // the 201: downloaded, and said so
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(calls.filter(call => call.download).map(call => [call.download, call.filename]), [[report.download_url, report.filename]]);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${report.filename}.`);
    // once the page has read the document again, the dialog lists the new file, its format named, with the options back
    // but the PDF just made, which waits a moment so one gesture makes one file (L5-1)
    await settle(() => (element('#exportOptions').innerHTML || '').includes(report.filename));
    const page = dom(element('#exportOptions').innerHTML);
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]), [[true, false], [false, false]]);
    const first = page.one('.report-item');
    assert.deepEqual([first.one('a').attr('href'), first.one('a').text, first.one('small').text], [report.download_url, report.filename, 'Codes (draft) · PDF · 21 Nov 2026, 09:00 UTC']);
    assert.equal(page.all('.report-item').length, 3);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${report.filename}.`, 'the status stays');
    assert.equal(element('#exportError').hidden, true);
    assert.equal(element('#exportDialog').open, true);
    assert.equal(calls.filter(call => call.method === 'GET' && call.url === address).length, 1, 'the document is read once again');
    assert.equal(app.state.making, null);
    t.mock.timers.tick(app.MADE_HOLD_MS);
    await settle(() => false);
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]), Array(2).fill([false, false]), 'then it is offered again');
  });
});

test('a PDF the server could not make: its sentence shows in the dialog, nothing is claimed, the options come back and a retry posts again', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const report = { id: 'f6100000-0000-4000-8000-0000000000b2', kind: 'approved', fmt: 'pdf', filename: 'CPT-Studio-approved-r2-20261121T091000.pdf',
    generated_at: '2026-11-21T09:10:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000b2/download', current: true };
  const reports = (method, url) => method === 'POST' && url === `${address}/reports`;
  await withPage({ answers: [{ match: reports, status: 503, body: { error: PDF_NOT_MADE, details: {} } }, { match: reports, status: 201, body: report }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: null });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => element('#exportError').textContent !== '');
    assert.equal(element('#exportError').textContent, PDF_NOT_MADE);
    assert.equal(element('#exportError').hidden, false);
    assert.equal(element('#exportDialog').open, true, 'the dialog stays open');
    assert.deepEqual(calls.filter(call => call.download), [], 'nothing is downloaded');
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(reviewed), 'nothing is said to be prepared or ready');
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]), Array(2).fill([false, false]), 'the options are back');
    assert.equal(controlsOf(element('#exportOptions').innerHTML)[1][4], 'Download PDF');
    // the retry posts again; its 201 downloads the file and clears the sentence
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    assert.equal(element('#exportError').hidden, true);
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'approved', fmt: 'pdf', round: 2 }, { kind: 'approved', fmt: 'pdf', round: 2 }]);
    assert.deepEqual(calls.filter(call => call.download).map(call => call.filename), [report.filename]);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${report.filename}.`);
  });
  // a refusal that says what is missing (409 with the blockers) is shown the same way and gives the options back; the
  // draft PDF chosen next is said to be prepared and ready
  const ready = fixture('encounter-ready.json');
  const blocked = { error: 'The approved export is not available yet.', details: { blockers: ['No code has been approved.'] } };
  const draft = { id: 'f6100000-0000-4000-8000-0000000000b3', kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r1-20261121T092000.pdf',
    generated_at: '2026-11-21T09:20:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000b3/download', current: true };
  const posts = (method, url) => method === 'POST' && url === `/api/encounters/${ready.id}/reports`;
  await withPage({ answers: [{ match: posts, status: 409, body: blocked }, { match: posts, status: 201, body: draft }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: ready, route: null });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => element('#exportError').textContent !== '');
    assert.equal(element('#exportError').textContent, 'The approved export is not available yet. No code has been approved.');
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([kind, fmt, disabled]) => [kind, fmt, disabled]), [
      ['draft', 'pdf', false], ['approved', 'pdf', true]]);
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    assert.equal(element('#exportStatus').textContent, 'Your PDF is being prepared. The download starts when it is ready.');
    assert.equal(controlsOf(element('#exportOptions').innerHTML)[0][4], 'Preparing PDF…');
    await settle(() => calls.some(call => call.download));
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${draft.filename}.`);
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'approved', fmt: 'pdf', round: 1 }, { kind: 'draft', fmt: 'pdf', round: 1 }]);
  });
});

test('the export dialog opened again while a file is made says so and waits; on another document it waits without naming that file', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const ready = fixture('encounter-ready.json');
  const report = { id: 'f6100000-0000-4000-8000-0000000000b4', kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r2-20261121T093000.pdf',
    generated_at: '2026-11-21T09:30:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000b4/download', current: true };
  for (const elsewhere of [false, true]) {
    await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `/api/encounters/${reviewed.id}/reports`, status: 201, body: report }] }, async ({ calls, element }) => {
      // the request is held until released, so what the page shows meanwhile can be read
      const reply = global.fetch;
      let release = null;
      global.fetch = (url, init = {}) => {
        const answer = reply(url, init);
        return init.method === 'POST' ? new Promise(resolve => { release = () => resolve(answer); }) : answer;
      };
      Object.assign(app.state, { session, doc: reviewed, route: null });
      click('[data-action]', { action: 'export' });
      click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
      element('#exportDialog').close();
      if (elsewhere) app.state.doc = ready;
      click('[data-action]', { action: 'export' });
      const waiting = controlsOf(element('#exportOptions').innerHTML);
      assert.deepEqual(waiting.map(([, , disabled]) => disabled), Array(2).fill(true), 'every option waits');
      if (elsewhere) {
        assert.equal(element('#exportStatus').textContent, 'Another download is still being prepared. Wait a moment, then choose again.');
        assert.deepEqual(waiting.filter(([, , , busy]) => busy), [], 'no option here is said to be prepared');
      } else {
        assert.equal(element('#exportStatus').textContent, 'Your PDF is being prepared. The download starts when it is ready.');
        assert.deepEqual(waiting.filter(([, , , busy]) => busy), [['draft', 'pdf', true, true, 'Preparing PDF…']]);
      }
      release();
      await settle(() => calls.some(call => call.download));
      // the file asked for downloads either way; the options come back; only its own document's dialog says it is ready
      assert.deepEqual(calls.filter(call => call.download).map(call => call.filename), [report.filename]);
      await settle(() => controlsOf(element('#exportOptions').innerHTML).every(([, , , busy]) => !busy) && app.state.making === null);
      const back = controlsOf(element('#exportOptions').innerHTML).map(([kind, fmt, disabled]) => [kind, fmt, disabled]);
      // on its own document the PDF just made waits a moment (L5-1); the other document's options are its own
      assert.deepEqual(back.map(([, , disabled]) => disabled), elsewhere ? [false, true] : [true, false]);
      assert.equal(element('#exportStatus').textContent, elsewhere ? app.exportStatusText(ready) : `Your PDF is ready. Downloading ${report.filename}.`);
      assert.equal(posted(calls).length, 1);
      t.mock.timers.tick(app.MADE_HOLD_MS);
      await settle(() => false);
      assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled]) => disabled), elsewhere ? [false, true] : Array(2).fill(false));
    });
  }
});

test('a refusal that comes after the dialog was closed is a notice; one for a document left meanwhile names it and closes nothing', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const ready = fixture('encounter-ready.json');
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  // [what the member does while the request runs, the refusal, then what is checked]
  const cases = [
    ['closed', 503, { error: PDF_NOT_MADE, details: {} }, element => {
      assert.equal(element('#toast').textContent, PDF_NOT_MADE, 'the notice says it');
      assert.equal(element('#exportDialog').open, false);
    }],
    ['elsewhere', 503, { error: PDF_NOT_MADE, details: {} }, element => {
      assert.equal(element('#toast').textContent, `${reviewed.title}: ${PDF_NOT_MADE}`, 'the notice names the document');
      assert.equal(element('#exportDialog').open, true, 'the other document\'s dialog stays open');
      assert.equal(element('#exportError').hidden, true, 'and is not told about the other file');
    }],
    ['elsewhere', 409, changed, element => {
      assert.equal(element('#toast').textContent, `${reviewed.title}: ${changed.error}`);
      assert.equal(element('#exportDialog').open, true, 'a change to the document left closes nothing here');
      assert.notEqual(element('#toast').textContent, app.CHANGED_TEXT);
    }],
  ];
  for (const [what, status, body, check] of cases) {
    await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `/api/encounters/${reviewed.id}/reports`, status, body }] }, async ({ calls, element }) => {
      const reply = global.fetch;
      let release = null;
      global.fetch = (url, init = {}) => {
        const answer = reply(url, init);
        return init.method === 'POST' ? new Promise(resolve => { release = () => resolve(answer); }) : answer;
      };
      Object.assign(app.state, { session, doc: reviewed, route: null });
      click('[data-action]', { action: 'export' });
      click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
      element('#exportDialog').close();
      if (what === 'elsewhere') {
        app.state.doc = ready;
        click('[data-action]', { action: 'export' });
      }
      release();
      await settle(() => app.state.making === null && element('#toast').textContent !== '');
      check(element);
      assert.deepEqual(calls.filter(call => call.download), [], `${what} ${status}: nothing is downloaded`);
      assert.equal(calls.filter(call => call.method === 'GET' && call.url.startsWith('/api/encounters/')).length, 0, `${what} ${status}: nothing is read again`);
      if (what === 'elsewhere') {
        // the other document's dialog is drawn again for its own document, its options as its readiness allows
        assert.equal(element('#exportStatus').textContent, app.exportStatusText(ready));
        assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]),
          [[false, false], [true, false]]);
      }
    });
  }
});

// --- the export dialog after the physician PDF's refutation (round 1, lens 5 and lens 1) -----------------------------

// A click as the browser hands it to the page's one handler: event.detail counts the clicks of one gesture (1 for a
// click, 2 for the second click of a double click, 0 for a key that presses the button).
function press(selector, dataset, detail) {
  app.onClick({ detail, target: { closest: wanted => (wanted === selector ? fakeElement({ dataset }) : null) } });
}

// A fetch that holds the first `count` reads of `address` until the test releases them, in any order: holds[n]() lets
// the n-th read through.
function holdReads(address, count = 1) {
  const reply = global.fetch;
  const holds = [];
  global.fetch = (url, init = {}) => {
    const answer = reply(url, init);
    if ((init.method || 'GET') !== 'GET' || url !== address || holds.length >= count) return answer;
    return new Promise(resolve => { holds.push(() => resolve(answer)); });
  };
  return holds;
}

test('L5-1: one gesture makes one download - a double click\'s second click is ignored, and the option just used waits a moment once its file is made', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const made = n => ({ id: `f6100000-0000-4000-8000-00000000d0${n}0`, kind: 'draft', fmt: 'pdf', filename: `CPT-Studio-draft-r2-20261121T09000${n}.pdf`,
    generated_at: `2026-11-21T09:00:0${n}Z`, download_url: `/api/reports/f6100000-0000-4000-8000-00000000d0${n}0/download`, current: true });
  const reports = (method, url) => method === 'POST' && url === `${address}/reports`;
  const option = { exportKind: 'draft', exportFmt: 'pdf' };
  const states = element => controlsOf(element('#exportOptions').innerHTML).map(([kind, fmt, disabled, busy]) => [`${kind} ${fmt}`, disabled, busy]);
  await withPage({ answers: [{ match: reports, status: 201, body: made(1) }, { match: reports, status: 201, body: made(2) }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: null });
    click('[data-action]', { action: 'export' });
    // the second (or third) click of one gesture is not a choice of its own, even on an option that is free
    press('[data-export-kind]', option, 2);
    press('[data-export-kind]', option, 3);
    await settle(() => false);
    assert.deepEqual(posted(calls), [], 'the second click of a double click made a download');
    // a double click with a server that answers between its two clicks: the first click makes the file ...
    press('[data-export-kind]', option, 1);
    await settle(() => calls.some(call => call.download));
    // ... the second makes nothing, and neither does another single click a moment later: the option just used waits,
    // drawn unavailable, while every other option is back
    press('[data-export-kind]', option, 2);
    press('[data-export-kind]', option, 1);
    await settle(() => false);
    assert.equal(posted(calls).length, 1, 'one gesture made more than one file');
    assert.deepEqual(calls.filter(call => call.download).map(call => call.filename), [made(1).filename]);
    assert.deepEqual(states(element), [['draft pdf', true, false], ['approved pdf', false, false]]);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${made(1).filename}.`);
    // a moment later it is offered again, and a deliberate second download (here by a key: detail 0) is made
    t.mock.timers.tick(app.MADE_HOLD_MS);
    await settle(() => false);
    assert.deepEqual(states(element).map(([, disabled]) => disabled), Array(2).fill(false));
    press('[data-export-kind]', option, 0);
    await settle(() => calls.filter(call => call.download).length === 2);
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'draft', fmt: 'pdf', round: 2 }, { kind: 'draft', fmt: 'pdf', round: 2 }]);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${made(2).filename}.`);
  });
  // on the document's page, the option waits until the dialog has been drawn from the document read again, however long
  // that read takes, and is offered again then
  const after = { ...clone(reviewed), reports: [made(3), ...clone(reviewed.reports)] };
  await withPage({ answers: [{ match: reports, status: 201, body: made(3) }, { match: (method, url) => method === 'GET' && url === address, status: 200, body: after }] }, async ({ calls, element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 81, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    press('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' }, 1);
    await settle(() => holds.length === 1);
    t.mock.timers.tick(app.MADE_HOLD_MS * 3);
    press('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' }, 1);
    await settle(() => false);
    assert.equal(posted(calls).length, 1, 'the option was offered again before the dialog was drawn from the new read');
    assert.deepEqual(states(element)[0], ['draft pdf', true, false]);
    holds[0]();
    await settle(() => (element('#exportOptions').innerHTML || '').includes(made(3).filename) && !states(element)[0][1]);
    assert.deepEqual(states(element).map(([, disabled]) => disabled), Array(2).fill(false), 'offered again once drawn from the new read');
    assert.equal(posted(calls).length, 1);
  });
});

test('R2-4-2: the option of a file just made is offered again once the hold has passed and any later read is shown, though its own read stalls', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const made = { id: 'f6100000-0000-4000-8000-00000000d0a0', kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r2-20261121T090010.pdf',
    generated_at: '2026-11-21T09:00:10Z', download_url: '/api/reports/f6100000-0000-4000-8000-00000000d0a0/download', current: true };
  const listed = { ...clone(reviewed), reports: [made, ...clone(reviewed.reports)] };
  const reads = (method, url) => method === 'GET' && url === address;
  const states = element => controlsOf(element('#exportOptions').innerHTML).map(([kind, fmt, disabled]) => [`${kind} ${fmt}`, disabled]);
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: made },
    { match: reads, status: 200, body: listed }, { match: reads, status: 200, body: listed }] }, async ({ calls, element }) => {
    const holds = holdReads(address);  // the hold's own read of the document stalls
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 181, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    press('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' }, 1);
    await settle(() => holds.length === 1);
    assert.deepEqual(states(element)[0], ['draft pdf', true]);
    // another read, asked after the file was made (an act's read, or a poll), is shown; the hold then passes
    await app.refreshDocument();
    t.mock.timers.tick(app.MADE_HOLD_MS);
    await settle(() => !states(element)[0][1]);
    assert.deepEqual(states(element).map(([, disabled]) => disabled), Array(2).fill(false), 'the option waited on for a read that stalled');
    // the stalled read, answering last, is older than what the page shows and changes nothing
    holds[0]();
    await settle(() => false);
    assert.deepEqual(states(element).map(([, disabled]) => disabled), Array(2).fill(false));
    assert.equal(posted(calls).length, 1);
  });
});

test('R2-4-1: a dialog waiting for the latest after a refused download is drawn from any later read the page shows, though its own read stalls', async () => {
  const session = fixture('session.json');
  const ready = fixture('encounter-ready.json');
  const later = { ...clone(ready), round: { number: 2, trigger: 'answers', finished_at: '2026-11-20T08:40:00Z' } };
  const address = `/api/encounters/${ready.id}`;
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  const reads = (method, url) => method === 'GET' && url === address;
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 409, body: changed },
    { match: reads, status: 200, body: later }, { match: reads, status: 200, body: later }] }, async ({ calls, element }) => {
    const holds = holdReads(address);  // the read after the refusal stalls
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 182, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => holds.length === 1);
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.LOADING_LATEST_TEXT);
    // another read, asked after the refusal, is shown: the dialog waits no longer, and is drawn from it
    await app.refreshDocument();
    await settle(() => app.state.exporting?.round === 2);
    assert.equal(app.state.rereading, null);
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(later));
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled]) => disabled), [false, true]);
    // the stalled read, answering last, is older than what the page shows and changes nothing
    holds[0]();
    await settle(() => false);
    assert.equal(app.state.doc.round.number, 2);
    assert.equal(posted(calls).length, 1);
  });
});

test('R2-4-5: the dialog waiting for the latest promises only what the latest allows', () => {
  assert.equal(app.LOADING_LATEST_TEXT, 'This coding review has changed. The page is loading the latest; what it allows can be downloaded once it has.');
  assert.doesNotMatch(app.LOADING_LATEST_TEXT, /offered again/);
});

test('L5-2: an open export dialog follows each read of its document - an approval or a finished review shows at once; a file being made is left as it is', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const session = fixture('session.json');
  const ready = fixture('encounter-ready.json');
  const address = `/api/encounters/${ready.id}`;
  const approved = clone(ready);
  approved.codes[0].decision = { id: 'f6200000-0000-4000-8000-0000000000a9', action: 'approve', by: 'Reviewer', at: '2026-11-21T09:00:00Z', note: '' };
  approved.codes[0].allowed_actions = ['revoke'];
  approved.readiness = { draft: true, approved: true, blockers: [] };
  approved.state = 'reviewed';
  const offered = element => controlsOf(element('#exportOptions').innerHTML).filter(([, , disabled]) => !disabled).map(([kind, fmt]) => `${kind} ${fmt}`);
  const all = ['draft pdf', 'approved pdf'];
  // (1) the member approves a code and chooses "Review and download" while the page reads the document again
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/decisions`, status: 201, body: { line: 'L1', code: ready.codes[0].code, action: 'approve' } },
    { match: (method, url) => method === 'GET' && url === address, status: 200, body: approved },
  ] }, async ({ element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 71, docKey: '', viewerKey: app.viewerKey(ready) });
    await app.handleDecision('approve', 'L1', fakeElement());
    element('#reviewAckBox').checked = true;
    const saving = app.submitReview({ preventDefault() {} });
    await settle(() => holds.length === 1);
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(ready), 'opened on the read the page has');
    assert.deepEqual(offered(element), ['draft pdf']);
    holds[0]();
    await saving;
    assert.equal(app.state.doc, approved, 'the page read the approval');
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(approved), 'the dialog\'s status still says no code is approved');
    assert.equal(element('#exportStatus').classList.contains('reviewed'), true);
    assert.deepEqual(offered(element), all, 'the approved downloads stay closed after the approval was read');
    assert.doesNotMatch(element('#exportOptions').innerHTML, /export-blockers/, 'nothing says the approved report waits');
  });
  // (2) opened while a coding review runs (an earlier download is listed): the page's poll reads it finished
  const reading = fixture('encounter-reading.json');
  const failed = fixture('encounter-failed.json');
  const earlier = clone(fixture('encounter-reviewed.json').reports).map(report => ({ ...report, current: false }));
  const before = { ...clone(ready), state: 'failed', progress: clone(failed.progress), round: { number: 1, trigger: 'upload', finished_at: null },
    codes: [], questions: [], notes: [], readiness: clone(failed.readiness), reports: earlier };
  const busy = { ...clone(before), state: reading.state, progress: clone(reading.progress), round: { number: 2, trigger: 'retry', finished_at: null }, readiness: clone(reading.readiness) };
  const done = { ...clone(ready), round: { number: 2, trigger: 'retry', finished_at: '2026-11-21T09:00:00Z' }, reports: earlier };
  const reads = (method, url) => method === 'GET' && url === address;
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/retry`, status: 201, body: { round: { number: 2, trigger: 'retry', finished_at: null } } },
    { match: reads, status: 200, body: busy }, { match: reads, status: 200, body: done },
  ] }, async ({ element }) => {
    Object.assign(app.state, { session, doc: before, route: { name: 'doc', id: ready.id }, routeSerial: 72, docKey: '', viewerKey: app.viewerKey(before) });
    await app.progressAction('retry', fakeElement());
    assert.ok(app.state.poll.timer, 'the page polls the running review');
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(busy));
    assert.deepEqual(offered(element), []);
    t.mock.timers.tick(app.pollDelay(0, 0));
    await settle(() => app.state.doc === done);
    assert.equal(app.state.doc, done, 'the poll read the finished review');
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(done), 'the dialog still says nothing can be downloaded');
    assert.equal(element('#exportStatus').classList.contains('reviewed'), false);
    assert.deepEqual(offered(element), ['draft pdf']);
  });
  // (3) a read that lands while a file of the document is being made leaves the dialog as it is: every option waits and
  // the status says the file is being prepared; once it is made the dialog shows that read
  const pdf = { id: 'f6100000-0000-4000-8000-0000000000e3', kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r1-20261121T095000.pdf',
    generated_at: '2026-11-21T09:50:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000e3/download', current: true };
  const approvedWithPdf = { ...clone(approved), reports: [pdf] };
  await withPage({ answers: [
    { match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: pdf },
    { match: reads, status: 200, body: approved }, { match: reads, status: 200, body: approvedWithPdf },
  ] }, async ({ calls, element }) => {
    const reply = global.fetch;
    let release = null;
    global.fetch = (url, init = {}) => {
      const answer = reply(url, init);
      return init.method === 'POST' ? new Promise(resolve => { release = () => resolve(answer); }) : answer;
    };
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 73, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await app.loadDocument(ready.id, 73, true);
    assert.equal(app.state.doc, approved);
    assert.equal(element('#exportStatus').textContent, 'Your PDF is being prepared. The download starts when it is ready.');
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]),
      [[true, true], [true, false]]);
    release();
    await settle(() => calls.some(call => call.download) && (element('#exportOptions').innerHTML || '').includes(pdf.filename));
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${pdf.filename}.`, 'the status keeps saying the file is ready');
    assert.deepEqual(offered(element), all.filter(name => name !== 'draft pdf'), 'drawn from the approval, the PDF just made waiting a moment');
  });
  // (4) a read that changes nothing in the dialog writes nothing to it: its status is announced, and its options would be
  // taken from under the pointer and the focus
  const counted = () => {
    const item = fakeElement();
    let value = '';
    item.writes = 0;
    for (const name of ['textContent', 'innerHTML']) Object.defineProperty(item, name, { get: () => value, set: next => { value = next; item.writes += 1; } });
    return item;
  };
  const status = counted();
  const options = counted();
  await withPage({ elements: { exportStatus: status, exportOptions: options }, answers: [{ match: reads, status: 200, body: clone(busy) }, { match: reads, status: 200, body: clone(busy) }] }, async () => {
    Object.assign(app.state, { session, doc: busy, route: { name: 'doc', id: ready.id }, routeSerial: 74, docKey: '', viewerKey: app.viewerKey(busy) });
    click('[data-action]', { action: 'export' });
    assert.deepEqual([status.writes, options.writes], [1, 1]);
    await app.refreshDocument();
    await app.refreshDocument();
    assert.deepEqual([status.writes, options.writes], [1, 1], 'a read that changes nothing wrote to the dialog again');
    assert.equal(status.textContent, app.exportStatusText(busy));
  });
});

test('L5-3: a dialog opened while the page reads the document again after a refused download says so and waits, then shows the latest coding review', async () => {
  const session = fixture('session.json');
  const ready = fixture('encounter-ready.json');
  const reviewed = fixture('encounter-reviewed.json');
  const later = { ...clone(ready), round: { number: 2, trigger: 'answers', finished_at: '2026-11-20T08:40:00Z' } };
  const address = `/api/encounters/${ready.id}`;
  const changed = { error: 'This coding review has changed. Reload to see the latest.', details: {} };
  const pdf = n => ({ id: `f6100000-0000-4000-8000-0000000000e${n}`, kind: 'draft', fmt: 'pdf', filename: `CPT-Studio-draft-r2-20261121T09400${n}.pdf`,
    generated_at: `2026-11-21T09:40:0${n}Z`, download_url: `/api/reports/f6100000-0000-4000-8000-0000000000e${n}/download`, current: true });
  const posts = (method, url) => method === 'POST' && url === `${address}/reports`;
  const reads = (method, url) => method === 'GET' && url === address;
  await withPage({ answers: [
    { match: posts, status: 409, body: changed }, { match: reads, status: 200, body: later },
    { match: posts, status: 201, body: pdf(4) }, { match: reads, status: 200, body: { ...clone(later), reports: [pdf(4)] } },
  ] }, async ({ calls, element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 91, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => holds.length === 1);
    assert.equal(element('#exportDialog').open, false, 'the refusal closed the dialog');
    assert.equal(element('#toast').textContent, app.CHANGED_TEXT);
    // opened again before the page's read has come back: it says the page is loading the latest, and offers nothing
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportDialog').open, true);
    assert.equal(element('#exportStatus').textContent, app.LOADING_LATEST_TEXT, 'the reopened dialog does not say the page is loading the latest');
    assert.equal(element('#exportStatus').classList.contains('reviewed'), false);
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled, busy]) => [disabled, busy]), Array(2).fill([true, false]));
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => false);
    assert.equal(posted(calls).length, 1, 'nothing is sent for a coding review the page is still loading');
    // the read comes back: the dialog shows the latest coding review, and its download names it
    holds[0]();
    await settle(() => app.state.exporting?.round === 2);
    assert.equal(app.state.doc.round.number, 2);
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(later));
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([kind, fmt, disabled]) => [kind, fmt, disabled]), [
      ['draft', 'pdf', false], ['approved', 'pdf', true]]);
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'draft', fmt: 'pdf', round: 1 }, { kind: 'draft', fmt: 'pdf', round: 2 }]);
    assert.equal(element('#exportDialog').open, true);
  });
  // while the page reads one document again, a download of another document is still made: no click is dropped
  const other = `/api/encounters/${reviewed.id}`;
  await withPage({ answers: [
    { match: posts, status: 409, body: changed }, { match: reads, status: 200, body: later },
    { match: (method, url) => method === 'POST' && url === `${other}/reports`, status: 201, body: pdf(5) },
    { match: (method, url) => method === 'GET' && url === other, status: 200, body: { ...clone(reviewed), reports: [pdf(5), ...clone(reviewed.reports)] } },
  ] }, async ({ calls, element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 92, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => holds.length === 1);
    // the member goes to the other document (a route closes the dialogs and moves on) and downloads its PDF
    element('#exportDialog').close();
    Object.assign(app.state, { exporting: null, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 93, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(reviewed), 'that document is not the one being loaded');
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(posted(calls).map(call => [call.url, call.body.fmt]), [[`${address}/reports`, 'pdf'], [`${other}/reports`, 'pdf']],
      'the other document\'s download was dropped while the page read the first one again');
    holds[0]();
    await settle(() => false);
    assert.equal(app.state.doc.id, reviewed.id, 'the first document\'s late read is not shown');
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${pdf(5).filename}.`);
  });
  // a read that fails leaves the dialog on the read the page has, offered again, rather than loading forever
  await withPage({ answers: [{ match: posts, status: 409, body: changed }] }, async ({ calls, element }) => {
    const reply = global.fetch;
    let fail = null;
    global.fetch = (url, init = {}) => ((init.method || 'GET') === 'GET' && url === address ? new Promise((resolve, reject) => { fail = () => reject(new TypeError('offline')); }) : reply(url, init));
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 94, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => fail !== null);
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.LOADING_LATEST_TEXT);
    fail();
    await settle(() => element('#exportStatus').textContent !== app.LOADING_LATEST_TEXT);
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(ready));
    assert.match(element('#toast').textContent, /^The review could not be refreshed\./);
    assert.deepEqual(controlsOf(element('#exportOptions').innerHTML).map(([, , disabled]) => disabled), [false, true]);
    assert.equal(posted(calls).length, 1);
  });
  // a route reads the document afresh: a dialog opened after it is drawn from that read, though the read asked for after
  // the refusal has not come back (a route forgets it)
  await withPage({ answers: [{ match: posts, status: 409, body: changed }, { match: reads, status: 200, body: later }, { match: reads, status: 200, body: later }] }, async ({ element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 95, docKey: '', viewerKey: app.viewerKey(ready) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => holds.length === 1);
    global.location.hash = `#doc/${ready.id}`;
    click('[data-action]', { action: 'reload-view' });  // route(), as the hash change runs it
    await settle(() => app.state.doc?.round?.number === 2);
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(later), 'a dialog opened after the route waits for a read the route replaced');
    assert.equal(app.state.exporting.round, 2);
    holds[0]();
    await settle(() => false);
    assert.equal(app.state.exporting.round, 2);
    assert.equal(element('#exportStatus').textContent, app.exportStatusText(later));
  });
});

test('L5-4: the two "Download PDF" buttons are told apart by name, each name starting with the words shown; each group is named by its label', () => {
  const names = html => dom(html).all('.export-pdf').map(button => [button.attr('data-export-kind'), button.text.trim(), button.attr('aria-label')]);
  const doc = fixture('encounter-reviewed.json');
  assert.deepEqual(names(app.exportOptions(doc)), [['draft', 'Download PDF', 'Download PDF (draft report)'], ['approved', 'Download PDF', 'Download PDF (approved report)']]);
  // while one is made its name says so, as its words do
  assert.deepEqual(names(app.exportOptions(doc, { kind: 'approved', fmt: 'pdf' })),
    [['draft', 'Download PDF', 'Download PDF (draft report)'], ['approved', 'Preparing PDF…', 'Preparing PDF… (approved report)']]);
  for (const making of [null, { kind: 'draft', fmt: 'pdf' }, { kind: 'approved', fmt: 'pdf' }]) {
    const found = names(app.exportOptions(doc, making));
    assert.equal(new Set(found.map(([, , name]) => name)).size, 2, 'two buttons, one name');
    for (const [, shown, name] of found) assert.ok(name.startsWith(shown), `${name} does not start with ${shown}`);
  }
  // each group is a named group: its label names it
  const page = dom(app.exportOptions(doc));
  assert.deepEqual(page.all('.export-group').map(group => [group.attr('role'), group.one(`#${group.attr('aria-labelledby')}`)?.text ?? null]), [
    ['group', 'Draft report'], ['group', 'Approved report'], ['group', 'Earlier downloads']]);
  const ids = page.all('[id]').map(item => item.attr('id'));
  assert.equal(new Set(ids).size, ids.length, 'every id in the dialog is its own');
  // every option the dialog offers is one of the two named PDF buttons: no data file is offered beside them
  assert.deepEqual(page.all('[data-export-kind]').map(item => item.attr('aria-label')), ['Download PDF (draft report)', 'Download PDF (approved report)']);
});

test('L5-5: reads of the document are applied in the order asked - an older read that answers last changes nothing', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const report = (n, kind) => ({ id: `f6100000-0000-4000-8000-00000000f0${n}0`, kind, fmt: 'pdf', filename: `CPT-Studio-${kind}-r2-20261121T09000${n}.pdf`,
    generated_at: `2026-11-21T09:00:0${n}Z`, download_url: `/api/reports/f6100000-0000-4000-8000-00000000f0${n}0/download`, current: true });
  const one = report(1, 'draft');
  const two = report(2, 'approved');
  const afterOne = { ...clone(reviewed), reports: [one, ...clone(reviewed.reports)] };
  const afterTwo = { ...clone(reviewed), reports: [two, one, ...clone(reviewed.reports)] };
  const posts = (method, url) => method === 'POST' && url === `${address}/reports`;
  const reads = (method, url) => method === 'GET' && url === address;
  const listed = element => dom(element('#exportOptions').innerHTML).all('.report-item a').map(link => link.text);
  // two downloads in a row, the first one's read slower than the second's: the dialog keeps the file it said was ready
  await withPage({ answers: [
    { match: posts, status: 201, body: one }, { match: posts, status: 201, body: two },
    { match: reads, status: 200, body: afterOne }, { match: reads, status: 200, body: afterTwo },
  ] }, async ({ element }) => {
    const holds = holdReads(address);
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 61, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'pdf' });
    await settle(() => holds.length === 1);
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => listed(element).includes(two.filename));
    holds[0]();
    await settle(() => false);
    assert.equal(element('#exportStatus').textContent, `Your PDF is ready. Downloading ${two.filename}.`);
    assert.deepEqual(listed(element), afterTwo.reports.map(item => item.filename), 'the dialog dropped the PDF it said was ready (drawn from an older read)');
    assert.equal(app.state.doc.reports.length, afterTwo.reports.length);
  });
  // any two reads: the one asked later is what the page shows, and an older read's failure says nothing once a newer
  // read is shown; a read asked after them all is shown
  const ready = fixture('encounter-ready.json');
  const older = { ...clone(ready), title: 'Synthetic older read' };
  const newer = { ...clone(ready), title: 'Synthetic newer read' };
  await withPage({}, async ({ element }) => {
    const pending = [];
    global.fetch = url => new Promise((resolve, reject) => pending.push({ url, resolve, reject }));
    Object.assign(app.state, { session, doc: ready, route: { name: 'doc', id: ready.id }, routeSerial: 101, docKey: '', viewerKey: app.viewerKey(ready) });
    const first = app.loadDocument(ready.id, 101, true);
    const second = app.loadDocument(ready.id, 101, true);
    pending[1].resolve(response({ body: newer }));
    await second;
    assert.equal(app.state.doc.title, newer.title);
    pending[0].resolve(response({ body: older }));
    await first;
    assert.equal(app.state.doc.title, newer.title, 'the older read, answered last, replaced the newer one');
    const third = app.loadDocument(ready.id, 101, true);
    const fourth = app.loadDocument(ready.id, 101, true);
    pending[3].resolve(response({ body: newer }));
    await fourth;
    element('#toast').textContent = '';
    pending[2].reject(new TypeError('offline'));
    await third;
    assert.equal(element('#toast').textContent, '', 'an older read\'s failure was said after a newer read was shown');
    assert.equal(app.state.reconnecting, false);
    const fifth = app.loadDocument(ready.id, 101, true);
    pending[4].resolve(response({ body: older }));
    await fifth;
    assert.equal(app.state.doc.title, older.title, 'a read asked after the others is shown');
  });
});

test('L1-6: a download that is no longer current is described truthfully, whether a later decision or a later coding review made it so', () => {
  const base = { kind: 'draft', fmt: 'pdf', filename: 'CPT-Studio-draft-r1-20261121T165600.pdf', generated_at: '2026-11-21T16:56:00Z',
    download_url: `/api/reports/${UUID}/download` };
  const words = report => dom(app.reportItem(report)).one('small').text;
  // the server lists a download of the latest coding review as not current once a decision is recorded after it, and one
  // of an earlier coding review likewise: one sentence holds for both
  assert.equal(words({ ...base, current: false }),
    'Codes (draft) · PDF · 21 Nov 2026, 16:56 UTC · Earlier: made before a later decision or coding review; it may not show the current codes');
  assert.doesNotMatch(app.reportItem({ ...base, current: false }), /made from an earlier coding review/);
  assert.equal(words({ ...base, current: true }), 'Codes (draft) · PDF · 21 Nov 2026, 16:56 UTC');
});

test('L1-7: the draft downloads are described by what they hold, saved decisions included; none says nothing in it is approved', () => {
  for (const name of ['encounter-ready.json', 'encounter-reviewed.json']) {
    const draft = dom(app.exportOptions(fixture(name))).all('.export-group')[0];
    // the draft's one description is its PDF's line: no data file is offered beside it, so no other line describes one
    assert.deepEqual([...draft.all('.export-pdf-note'), ...draft.all('small')].map(item => item.text), [
      'Every code with its status, any saved decision, the evidence and what still needs a decision.',
    ], name);
    assert.doesNotMatch(app.exportOptions(fixture(name)), /Nothing in it is approved/, name);
  }
});

test('the activity names a decision\'s line with its code ("L2 45380"), drawn as the server writes it', () => {
  let checked = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    for (const item of doc.activity) {
      const decided = /^.+? (?:approved|rejected|undid the decision on) (\S+) (\S+)\.$/.exec(item.text);
      if (!/ (?:approved|rejected|undid the decision on) /.test(item.text)) continue;
      assert.ok(decided && LINE_ID.test(decided[1]), `${name}: ${item.text}`);
      assert.ok(doc.codes.some(code => code.line === decided[1] && code.code === decided[2]), `${name}: ${item.text}`);
      checked += 1;
    }
  }
  assert.ok(checked >= 4, checked);
  const page = dom(render(fixture('encounter-reviewed.json'), { open: new Set(['activity']) }));
  assert.deepEqual(page.all('details.activity-log li strong').map(item => item.text).filter(text => / L\d /.test(text)),
    ['Reviewer approved L1 43239.', 'Reviewer approved L2 45385.', 'Reviewer rejected L3 45380.']);
});

test('the preview server answers decisions as the server does: by round and line, 409 when the coding review changed', () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-same-code.json');
  const body = extra => ({ round: 2, line: 'M1', code: '45380', action: 'approve', acknowledgement: session.acknowledgement, note: '', ...extra });
  const [status, answer] = preview.decisionAnswer(doc, body(), session);
  assert.equal(status, 201);
  assert.deepEqual([answer.line, answer.code, answer.action, answer.by], ['M1', '45380', 'approve', 'Reviewer']);
  for (const stale of [{ round: 1 }, { round: '2' }, { round: undefined }, { line: 'M2' }, { line: undefined }, { code: '45385' }]) {
    assert.deepEqual(preview.decisionAnswer(doc, body(stale), session), [409, { error: preview.CHANGED, details: {} }], JSON.stringify(stale));
  }
  assert.equal(preview.CHANGED, 'This coding review has changed. Reload to see the latest.');
  assert.equal(preview.decisionAnswer(doc, body({ line: 'L3' }), session)[0], 409, 'a decided line takes only Undo');
  // an Undo names the decision it undoes: the line's current one, or 409 (LINES-5)
  const undo = extra => body({ line: 'L3', action: 'revoke', acknowledgement: '', decision: 'fc200000-0000-4000-8000-000000000003', ...extra });
  assert.equal(preview.decisionAnswer(doc, undo(), session)[0], 201);
  for (const stale of [{ decision: undefined }, { decision: '' }, { decision: 'fc200000-0000-4000-8000-000000000009' }, { decision: 3 }]) {
    assert.deepEqual(preview.decisionAnswer(doc, undo(stale), session), [409, { error: preview.CHANGED, details: {} }], JSON.stringify(stale));
  }
  assert.equal(preview.decisionAnswer(doc, body({ acknowledgement: 'yes' }), session)[0], 400);
  const running = fixture('encounter-reading.json');
  assert.equal(preview.decisionAnswer(running, body({ round: 1 }), session)[0], 409, 'nothing is decided while a review runs');
});

test('the preview server answers downloads as the server does: by the round shown, 409 when the coding review changed', () => {
  const reviewed = fixture('encounter-reviewed.json');
  const [status, report] = preview.reportAnswer(reviewed, { kind: 'approved', fmt: 'pdf', round: 2 });
  assert.equal(status, 201);
  assert.deepEqual([report.kind, report.fmt, report.current, app.safeDownloadUrl(report.download_url) === report.download_url], ['approved', 'pdf', true, true]);
  for (const stale of [{ round: 1 }, { round: '2' }, { round: undefined }, { round: 3 }]) {
    assert.deepEqual(preview.reportAnswer(reviewed, { kind: 'draft', fmt: 'pdf', ...stale }), [409, { error: preview.CHANGED, details: {} }], JSON.stringify(stale));
  }
  const ready = fixture('encounter-ready.json');
  assert.deepEqual(preview.reportAnswer(ready, { kind: 'approved', fmt: 'pdf', round: 1 }),
    [409, { error: 'The approved download is not available yet.', details: { blockers: ['No code has been approved.'] } }]);
  assert.equal(preview.reportAnswer(ready, { kind: 'draft', fmt: 'pdf', round: 1 })[0], 201);
  assert.equal(preview.reportAnswer(ready, { kind: 'zip', fmt: 'pdf', round: 1 })[0], 400);
  const running = fixture('encounter-reading.json');
  assert.equal(preview.reportAnswer(running, { kind: 'draft', fmt: 'pdf', round: 1 })[0], 409, 'nothing is exported while a review runs');
  // the PDF, as the server makes it: a .pdf served as application/pdf, its bytes a PDF made here
  const [made, pdf] = preview.reportAnswer(reviewed, { kind: 'draft', fmt: 'pdf', round: 2 });
  assert.equal(made, 201);
  assert.deepEqual([pdf.kind, pdf.fmt, pdf.current, /\.pdf$/.test(pdf.filename), app.safeDownloadUrl(pdf.download_url) === pdf.download_url], ['draft', 'pdf', true, true, true]);
  const file = preview.reportFile(pdf.id);
  assert.deepEqual([file.type, file.filename], ['application/pdf', pdf.filename]);
  assert.match(file.content.subarray(0, 9).toString('latin1'), /^%PDF-1\.\d\n/);
  assert.match(file.content.subarray(-6).toString('latin1'), /^%%EOF\n$/);
  // CSV and TXT are no longer made (owner direction 2026-11-21): a request the PDF would answer 201 is refused for them
  // with the server's own sentence
  for (const fmt of ['csv', 'txt']) {
    assert.deepEqual(preview.reportAnswer(reviewed, { kind: 'approved', fmt, round: 2 }), [400, { error: FORMAT_REQUIRED, details: {} }], fmt);
  }
  // as is any other format
  assert.equal(preview.FORMAT_REQUIRED, FORMAT_REQUIRED);
  // a format that is not a string - ['pdf'] reads as the key 'pdf' to a plain lookup - is refused too, as the server
  // refuses it (refutation round 4, R4-1-4)
  for (const fmt of ['csv', 'txt', 'docx', 'PDF', undefined, 'constructor', ['pdf'], { toString: () => 'pdf' }]) {
    assert.deepEqual(preview.reportAnswer(ready, { kind: 'draft', fmt, round: 1 }), [400, { error: FORMAT_REQUIRED, details: {} }], String(fmt));
  }
  assert.equal(preview.reportFile('f6100000-0000-4000-8000-000000000000'), null);
});

test('Send answers posts the typed answers once, to /answers, and forgets only what was sent', async () => {
  const doc = fixture('encounter-awaiting-answer.json');
  const [first, second] = doc.questions.map(question => question.id);
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { doc, route: null, answers: new Map([[first, '  With a cold snare.  '], [second, '']]) });
    await app.sendAnswers(fakeElement());
    assert.deepEqual(posted(calls), [{ url: `/api/encounters/${doc.id}/answers`, body: { answers: [{ question_id: first, text: 'With a cold snare.' }] } }]);
    assert.deepEqual([...app.state.answers.keys()], [second]);
    assert.match(element('#toast').textContent, /^Answer sent\. A new coding review has started\.$/);
    // nothing typed: nothing sent, and the panel says why
    await app.sendAnswers(fakeElement());
    assert.equal(posted(calls).length, 1);
    assert.equal(element('#answersError').textContent, 'Write an answer to at least one question, then send.');
    assert.equal(element('#answersError').hidden, false);
  });
  // a refusal keeps the answers and shows the server's sentence
  await withPage({ answers: [{ status: 409, body: { error: 'A coding review is already running.' } }] }, async ({ element }) => {
    Object.assign(app.state, { doc, route: null, answers: new Map([[first, 'Snare.']]) });
    await app.sendAnswers(fakeElement());
    assert.equal(element('#answersError').textContent, 'A coding review is already running.');
    assert.deepEqual([...app.state.answers.keys()], [first]);
  });
});

test('typing an answer keeps it on the page until it is sent', () => {
  const saved = app.state.answers;
  try {
    app.state.answers = new Map();
    global.document = { querySelector: () => null };
    app.onInput({ target: { id: 'answer-1', value: 'A snare.', dataset: { answer: 'q-1' }, matches: selector => selector === 'textarea[data-answer]' } });
    assert.deepEqual([...app.state.answers], [['q-1', 'A snare.']]);
  } finally {
    app.state.answers = saved;
    delete global.document;
  }
});

test('Stop, Resume and Retry post to their own address; a refusal says why in the server\'s words', async () => {
  await withPage({ answers: [{ status: 201, body: { round: 2 } }, { status: 409, body: { error: 'Nothing is running for this document.' } }] }, async ({ calls, element }) => {
    const doc = fixture('encounter-failed.json');
    Object.assign(app.state, { doc, route: null });
    await app.progressAction('retry', fakeElement());
    await app.progressAction('stop', fakeElement());
    assert.deepEqual(posted(calls).map(call => [call.url, call.body]), [[`/api/encounters/${doc.id}/retry`, {}], [`/api/encounters/${doc.id}/stop`, {}]]);
    assert.equal(element('#toast').textContent, 'Nothing is running for this document.');
    assert.equal(app.progressAction('unknown', fakeElement()), undefined);
  });
});

test('api(): a 401 sends the member to sign in, a stale build shows the update notice, a bodiless change reads as done', async () => {
  await withPage({ answers: [{ match: () => true, status: 401, body: {} }] }, async ({ calls }) => {
    await assert.rejects(app.api('/api/session'), { status: 401 });
    // B5: a session that ended for a reason the server does not name is simply over
    assert.deepEqual(calls.pop(), { assign: '/login/?reason=expired&next=%2F' });
  });
  await withPage({ answers: [{ status: 409, body: { error_code: 'client_outdated' } }] }, async ({ element }) => {
    await assert.rejects(app.api('/api/encounters'), { message: app.OUTDATED_TEXT });
    assert.equal(element('#updateNotice').hidden, false);
    assert.equal(app.state.outdated, true);
  });
  await withPage({ answers: [{ status: 201, body: '', type: 'text/html' }, { match: () => true, status: 200, body: '', type: 'text/html' }] }, async ({ calls }) => {
    assert.deepEqual(await app.api('/api/encounters/x/answers', { method: 'POST', json: {} }), {});
    await assert.rejects(app.api('/api/session'), /cannot read/);
    assert.equal(calls[1].headers['X-CSRFToken'], undefined, 'a read sends no CSRF header');
  });
});

test('a poll that brings only the server clock is the same page; the viewer is redrawn only when the original changes', () => {
  const doc = fixture('encounter-checking.json');
  const later = clone(doc);
  later.progress.server_time = '2026-11-20T09:06:00Z';
  assert.equal(app.renderKey(later), app.renderKey(doc));
  const moved = clone(doc);
  moved.progress.phase = 'done';
  assert.notEqual(app.renderKey(moved), app.renderKey(doc));
  // new codes, questions or a new phase leave the viewer as it is; another original does not
  const finished = clone(fixture('encounter-ready.json'));
  const asking = { ...clone(finished), codes: [], questions: fixture('encounter-awaiting-answer.json').questions };
  assert.equal(app.viewerKey(asking), app.viewerKey(finished));
  assert.notEqual(app.viewerKey({ ...finished, document: { ...finished.document, view_url: null } }), app.viewerKey(finished));
  assert.notEqual(app.viewerKey(fixture('encounter-needs-review.json')), app.viewerKey(finished));
});

test('a quoted passage is found in a text despite line breaks and case', () => {
  const source = 'Line one.\nThe colonoscope was\nadvanced to   the cecum.\nEnd.';
  const found = app.findPassage(source, 'The colonoscope was advanced to the cecum.');
  assert.deepEqual(found, [10, 54]);
  assert.equal(source.slice(...found), 'The colonoscope was\nadvanced to   the cecum.');
  assert.deepEqual(app.findPassage(source, 'THE COLONOSCOPE'), [10, 25]);
  assert.equal(app.findPassage(source, 'not in the text'), null);
  assert.equal(app.findPassage(source, '   '), null);
  assert.deepEqual(app.findPassage('\u{1F600} cecum', 'cecum'), [3, 8], 'offsets are the text\'s own UTF-16 units');
});

test('a text document\'s passage is counted by the same rule: every occurrence, exact case before case-blind', () => {
  const source = 'The cecum was reached.\nThe  cecum\nwas reached again. the cecum was reached';
  assert.deepEqual(app.findPassages(source, 'The cecum was reached'), [[0, 21], [23, 45]], 'exact case: the lower-case one is not counted');
  assert.equal(source.slice(23, 45), 'The  cecum\nwas reached', 'white space runs are one space');
  assert.deepEqual(app.findPassages(source, 'THE CECUM WAS REACHED'), [[0, 21], [23, 45], [53, 74]], 'case-blind: all three');
  assert.deepEqual(app.findPassages(source, 'not in it'), []);
  assert.deepEqual(app.findPassages(source, ' \n '), []);
  assert.deepEqual(app.findPassages('aaaa', 'aa'), [[0, 2], [2, 4]], 'left to right, without overlap');
  assert.deepEqual(app.findPassage(source, 'THE CECUM WAS REACHED'), [0, 21], 'findPassage is the first of them');
  // a letter whose lower case is two units is compared as written, so no offset moves
  assert.deepEqual(app.findPassages('İstanbul cecum', 'CECUM'), [[9, 14]]);
  assert.equal(app.textMarkNote(0), 'The exact words could not be found in the document, so nothing is marked.');
  assert.equal(app.textMarkNote(1), 'Marked in the document.');
  assert.equal(app.textMarkNote(3), 'These words appear 3 times in the document. Each is marked.');
});

// --- the quoted words, marked on a page of a PDF (the owner's direction of 2026-11-20, DECISIONS D368) ------------------

// What locateQuote marks, as [page, the marked text of each item part, occurrence], read back from the page strings.
function markedParts(result, texts) {
  return Object.entries(result.marks).flatMap(([page, parts]) => parts.map(part => [Number(page), texts[page - 1][part.item].slice(part.start, part.end), part.occurrence]));
}

test('the matcher marks the quote\'s own characters: white space ignored entirely, NFKC on both sides', () => {
  const pages = [['Patchy erythema was seen in the gastric antrum.', 'Cold forceps biop', 'sies were taken.'], ['Second page.']];
  // exact: one item
  const exact = app.locateQuote({ text: 'Patchy erythema was seen in the gastric antrum.', page: 1 }, pages);
  assert.deepEqual([exact.status, exact.scope, exact.count, exact.pages, exact.caseBlind], ['marked', 'page', 1, [1], false]);
  assert.deepEqual(markedParts(exact, pages), [[1, 'Patchy erythema was seen in the gastric antrum.', 0]]);
  // white space differences: line breaks and runs of spaces in the quote, a word split across two items on the page
  const spaced = app.locateQuote({ text: 'Cold  forceps\nbiopsies were', page: 1 }, pages);
  assert.deepEqual(markedParts(spaced, pages), [[1, 'Cold forceps biop', 0], [1, 'sies were', 0]]);
  // ...and white space ignored entirely: the page's "biop" + "sies" is the quote's "biopsies", a quote without spaces too
  assert.equal(app.locateQuote({ text: 'Coldforcepsbiopsies', page: 1 }, pages).count, 1);
  // only the characters matched are marked: no white space before or after them
  const inner = app.locateQuote({ text: 'erythema was', page: 1 }, pages);
  assert.deepEqual(inner.marks, { 1: [{ item: 0, start: 7, end: 19, occurrence: 0 }] });
  // NFKC: a ligature on the page and plain letters in the quote, and the other way round; full-width letters; NBSP
  const ligature = [['The ﬁnding was conﬁrmed.', 'Ｓｎａｒｅ polypectomy']];
  assert.deepEqual(markedParts(app.locateQuote({ text: 'finding was confirmed', page: 1 }, ligature), ligature), [[1, 'ﬁnding was conﬁrmed', 0]]);
  assert.equal(app.locateQuote({ text: 'Snare polypectomy', page: 1 }, ligature).count, 1);
  assert.equal(app.locateQuote({ text: 'The ﬁnding', page: 1 }, [['The finding']]).count, 1);
  // whole characters only: never half of a ligature, never a letter without its accent
  assert.equal(app.locateQuote({ text: 'The f', page: 1 }, ligature).status, 'not_found');
  const accented = [['café au lait']];
  assert.equal(app.locateQuote({ text: 'cafe au', page: 1 }, accented).status, 'not_found');
  assert.deepEqual(markedParts(app.locateQuote({ text: 'café au', page: 1 }, accented), accented), [[1, 'café au', 0]], 'composed and decomposed are one character');
  // offsets are the item's own UTF-16 units, astral characters included
  const astral = [['\u{1F600} cecum reached']];
  assert.deepEqual(app.locateQuote({ text: 'cecum', page: 1 }, astral).marks, { 1: [{ item: 0, start: 3, end: 8, occurrence: 0 }] });
});

test('a character is cut from the page\'s whole text: an accent the PDF draws as an item of its own belongs to the letter before it', () => {
  // the PDF library starts a new item where the font changes, so an accent drawn in another font is an item of its own
  const split = [['The patient Jose', '́', ' ', 'Garcia was seen today.']];
  const bare = app.locateQuote({ text: 'The patient Jose', page: 1 }, split);
  assert.deepEqual([bare.status, bare.count, bare.marks], ['not_found', 0, {}], 'never a letter without its accent');
  for (const text of ['The patient José Garcia was seen today.', 'The patient José Garcia was seen today.']) {
    const whole = app.locateQuote({ text, page: 1 }, split);
    assert.deepEqual([whole.status, whole.count], ['marked', 1], 'the accented quote is on the page, composed or not');
    assert.deepEqual(whole.marks, { 1: [{ item: 0, start: 0, end: 16, occurrence: 0 }, { item: 1, start: 0, end: 1, occurrence: 0 },
      { item: 3, start: 0, end: 22, occurrence: 0 }] }, 'the letter and its accent are marked together, in both items');
  }
  // so a plain "Jose" elsewhere on the page is counted once, not twice
  const count = app.locateQuote({ text: 'Jose', page: 1 }, [['Jose', '́', ' and Jose was seen.']]);
  assert.deepEqual([count.count, count.marks], [1, { 1: [{ item: 2, start: 5, end: 9, occurrence: 0 }] }]);
  // an accent that follows white space stands on its own: the letter before the space is whole
  assert.deepEqual(app.locateQuote({ text: 'Jose', page: 1 }, [['Jose ', '́']]).marks, { 1: [{ item: 0, start: 0, end: 4, occurrence: 0 }] });
  // a mark NFKC has no composed letter for is still part of its letter
  assert.equal(app.locateQuote({ text: 'q', page: 1 }, [['q', '́']]).status, 'not_found');
  // two marks in another order, the second in the next item: NFKC orders them and composes the letter with one
  assert.equal(app.locateQuote({ text: 'a̖', page: 1 }, [['a̖', '̀']]).status, 'not_found');
  assert.equal(app.locateQuote({ text: 'à̖', page: 1 }, [['a̖', '̀']]).count, 1);
  // Hangul: a syllable written as conjoining jamo is one character, in one item or two
  assert.equal(app.locateQuote({ text: '하', page: 1 }, [['한']]).status, 'not_found');
  assert.equal(app.locateQuote({ text: '하', page: 1 }, [['하', 'ᆫ']]).status, 'not_found');
  assert.deepEqual(app.locateQuote({ text: '한', page: 1 }, [['하', 'ᆫ']]).marks,
    { 1: [{ item: 0, start: 0, end: 2, occurrence: 0 }, { item: 1, start: 0, end: 1, occurrence: 0 }] });
  // NFKC combines across what a reader sees as two characters: compatibility jamo, a half-width kana and its voiced mark
  assert.equal(app.locateQuote({ text: '하', page: 1 }, [['ㅎㅏ']]).count, 1);
  assert.equal(app.locateQuote({ text: 'ㅎ', page: 1 }, [['ㅎㅏ']]).status, 'not_found');
  assert.equal(app.locateQuote({ text: 'ガ', page: 1 }, [['ｶ', 'ﾞ']]).count, 1);
  assert.equal(app.locateQuote({ text: 'カ', page: 1 }, [['ｶ', 'ﾞ']]).status, 'not_found');
  // a flag is one character (a sequence held together by a joiner is its characters: the joiner is a format character,
  // dropped on both sides, as the library drops it - R3)
  assert.equal(app.locateQuote({ text: '\u{1F1FA}', page: 1 }, [['\u{1F1FA}\u{1F1F8} ok']]).status, 'not_found');
  assert.equal(app.locateQuote({ text: '\u{1F1FA}\u{1F1F8} ok', page: 1 }, [['\u{1F1FA}\u{1F1F8} ok']]).count, 1);
  // a character never spans two pages: an accent at the top of the next page is not the last letter's
  const pages = [['the end of page one'], ['́ page two']];
  assert.deepEqual(app.locateQuote({ text: 'the end of page one', page: 1 }, pages).pages, [1]);
  // the page's characters fold to NFKC of its whole text, white space dropped, and each lists the pieces it is made of
  assert.deepEqual(app.pageCharacters(['Jose', '́', ' x']).map(({ pieces, folded }) => [folded, pieces]), [
    ['J', [{ item: 0, start: 0, end: 1 }]], ['o', [{ item: 0, start: 1, end: 2 }]], ['s', [{ item: 0, start: 2, end: 3 }]],
    ['é', [{ item: 0, start: 3, end: 4 }, { item: 1, start: 0, end: 1 }]], ['x', [{ item: 2, start: 1, end: 2 }]]]);
  assert.deepEqual(app.characterSpans('é\u{1F469}‍\u{1F4BB}한'), [[0, 2], [2, 7], [7, 10]]);
});

// A text with its format characters (\p{Cf}) dropped, and where each UTF-16 unit left came from.
function dropFormat(value) {
  let text = '';
  const origin = [];
  for (let at = 0; at < value.length;) {
    const size = value.codePointAt(at) > 0xffff ? 2 : 1;
    const point = value.slice(at, at + size);
    if (!/\p{Cf}/u.test(point)) {
      text += point;
      for (let unit = 0; unit < size; unit += 1) origin.push(at + unit);
    }
    at += size;
  }
  return { text, origin };
}

// The rule stated again by brute force, apart from the matcher: the page's text is its items joined, format characters
// dropped (R3), and the places between one item's last character and the next item's first are where two drawings meet
// (bare strings have no geometry, so each such place is a word edge: R2b); an occurrence is a stretch of the text that
// begins and ends where one character ends and the next begins and NFKC of the whole text is cut cleanly, begins with a
// character that is not only white space, and whose NFKC, white space dropped, is the quote's; the first such stretch is
// the shortest. At each end, a place where two drawings meet is an edge; else, where the quote's character there (its
// first or last that is not white space) begins with a letter or a digit that is not a Han ideograph or a hiragana
// character, the code point beside the stretch is none of a letter, a digit or a mark other than those (R2, R2c; the
// text's start and end are edges); and then a digit with a number separator beside the stretch and a digit beyond it, or
// a separator ending the quote beside a digit, keeps the stretch inside a number (R2a; reading stops where two drawings
// meet). A stretch turned away takes nothing. They are taken left to right without overlap, exact-case first; returned in
// the given text's offsets.
const BRUTE_SEPARATORS = new Set([0x27, 0x2c, 0x2e, 0x3b, 0x37e, 0x589, 0x60c, 0x60d, 0x66c, 0x7f8, 0x2018, 0x2019, 0x2024, 0x2044,
  0xfe50, 0xfe52, 0xfe54, 0xff07, 0xff0c, 0xff0e, 0xff1b]);
function bruteOccurrences(items, quote) {
  const nfkc = value => value.normalize('NFKC');
  const fold = value => nfkc(value).replace(/\s+/gu, '');
  const boundsOf = value => {
    const whole = nfkc(value);
    return [...new Intl.Segmenter('en', { granularity: 'grapheme' }).segment(value)].map(segment => segment.index)
      .concat(value.length).filter(at => nfkc(value.slice(0, at)) + nfkc(value.slice(at)) === whole);
  };
  let text = '';
  const origin = [];
  const meets = new Set();
  let base = 0;
  for (const item of items) {
    const own = dropFormat(item);
    if (own.text && text) meets.add(text.length);
    text += own.text;
    for (const at of own.origin) origin.push(base + at);
    base += item.length;
  }
  const bounds = boundsOf(text);
  const asked = dropFormat(quote).text;
  const want = fold(asked);
  const own = boundsOf(asked);
  const characters = own.slice(0, -1).map((at, index) => fold(asked.slice(at, own[index + 1]))).filter(Boolean);
  const first = point => (point === undefined ? '' : String.fromCodePoint(point));
  const lone = character => /^[\p{Ideographic}\p{Script=Hiragana}]/u.test(character);
  const keeps = character => Boolean(character) && /^[\p{L}\p{N}]/u.test(character) && !lone(character);
  const digit = character => Boolean(character) && /^\p{Nd}/u.test(character);
  const separator = character => Boolean(character) && BRUTE_SEPARATORS.has(character.codePointAt(0));
  const joins = character => Boolean(character) && /^[\p{L}\p{N}\p{M}]$/u.test(character) && !lone(character);
  const [head, second] = characters;
  const tail = characters[characters.length - 1];
  const beforeTail = characters[characters.length - 2];
  const startOk = start => {
    if (meets.has(start)) return true;
    const one = [...text.slice(0, start)].pop();
    if (one === undefined) return true;
    if (keeps(head) && joins(one)) return false;
    if (digit(head) && separator(one)) {
      const from = start - one.length;
      const two = meets.has(from) ? undefined : [...text.slice(0, from)].pop();
      if (digit(two)) return false;
    }
    return !(separator(head) && digit(second) && digit(one));
  };
  const endOk = end => {
    if (meets.has(end)) return true;
    const one = first(text.codePointAt(end));
    if (!one) return true;
    if (keeps(tail) && joins(one)) return false;
    if (digit(tail) && separator(one)) {
      const from = end + one.length;
      const two = meets.has(from) ? '' : first(text.codePointAt(from));
      if (digit(two)) return false;
    }
    return !(separator(tail) && digit(beforeTail) && digit(one));
  };
  let turned = false;
  const scan = same => {
    const found = [];
    let from = 0;
    bounds.forEach((start, index) => {
      if (!want || start < from || index === bounds.length - 1 || !fold(text.slice(start, bounds[index + 1]))) return;
      for (let next = index + 1; next < bounds.length; next += 1) {
        if (same(fold(text.slice(start, bounds[next])))) {
          const end = bounds[next];
          if (!startOk(start) || !endOk(end)) {
            turned = true;
            return;
          }
          found.push([start, end]);
          from = end;
          return;
        }
      }
    });
    return found;
  };
  const exact = scan(value => value === want);
  const chosen = exact.length ? { found: exact, caseBlind: false } : { found: scan(value => value.toLowerCase() === want.toLowerCase()), caseBlind: true };
  return { found: chosen.found.map(([start, end]) => [origin[start], origin[end - 1] + 1]), caseBlind: chosen.caseBlind, turned };
}

test('the matcher agrees with the rule stated by brute force on pages of accents, jamo, kana, ligatures, emoji, numbers and CJK split into items', () => {
  const alphabet = ['a', 'e', 'E', 'q', ' ', '\n', '́', '̖', '̀', 'é', 'É', 'ﬁ', 'f', 'i', 'I', 'İ',
    'ᄒ', 'ᅡ', 'ᆫ', '하', '한', 'ㅎ', 'ㅏ', 'ㄳ', 'ｶ', 'ﾞ', 'カ', 'ガ', '\u{1F469}',
    '‍', '\u{1F4BB}', '\u{1F1FA}', '\u{1F1F8}', '¨', 'ß', 'S', 'k', 'K', 'क', '्', 'ष', 'େ',
    'ା', '½', '1', '⁄', '2', ' ', '　', '゛', 'か',
    // R2a: digits and number separators (ASCII, fullwidth, Arabic), and what is neither; R2c: Han, hiragana, katakana
    '1', '2', '5', '.', ',', '.', '’', '/', '-', '１', '．', '٥', '٬', '²', '糖', '病', 'の', 'ア', '゙', '〇'];
  let seed = 20261120;
  const random = bound => {
    seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
    return (seed >>> 8) % bound;
  };
  let marked = 0;
  let turned = 0;
  for (let trial = 0; trial < 6000; trial += 1) {
    const items = Array.from({ length: 1 + random(4) }, () => Array.from({ length: random(6) }, () => alphabet[random(alphabet.length)]).join(''));
    const text = items.join('');
    let quote;
    if (text && random(3)) {
      const points = [...text];
      const from = random(points.length);
      quote = points.slice(from, from + 1 + random(Math.min(6, points.length - from))).join('');
      if (random(4) === 0) quote = quote.toUpperCase();
    } else {
      quote = Array.from({ length: 1 + random(4) }, () => alphabet[random(alphabet.length)]).join('');
    }
    const label = JSON.stringify({ items, quote });
    assert.equal(app.pageCharacters(items).map(character => character.folded).join(''), dropFormat(text).text.normalize('NFKC').replace(/\s+/gu, ''), label);
    const result = app.locateQuote({ text: quote, page: 1 }, [items]);
    const starts = items.map((_, index) => items.slice(0, index).join('').length);
    const spans = new Map();
    for (const part of result.marks[1] || []) {
      const span = spans.get(part.occurrence) || [Infinity, -Infinity];
      spans.set(part.occurrence, [Math.min(span[0], starts[part.item] + part.start), Math.max(span[1], starts[part.item] + part.end)]);
    }
    const expected = bruteOccurrences(items, quote);
    if (expected.turned) turned += 1;
    assert.deepEqual([...spans.keys()].sort((a, b) => a - b).map(key => spans.get(key)), expected.found, label);
    assert.equal(result.count, expected.found.length, label);
    if (expected.found.length) {
      assert.equal(result.caseBlind, expected.caseBlind, label);
      marked += 1;
    }
  }
  assert.ok(marked > 900, `the trials mark often enough to mean something (${marked})`);
  assert.ok(turned > 300, `and the word edges turn some away (${turned})`);
});

// What a page has that a bare script realm does not: the observers and structuredClone (the rest the viewer needs is the
// language's own, as in a browser).
const PAGE_APIS = 'globalThis.IntersectionObserver = function () {}; globalThis.ResizeObserver = function () {};'
  + ' globalThis.structuredClone = function () {};';

test('without Intl.Segmenter the matcher still cuts characters from the page\'s whole text, and the viewer is not offered', () => {
  const context = vm.createContext({ module: { exports: {} } });
  vm.runInContext('delete Intl.Segmenter;', context);
  vm.runInContext(fs.readFileSync(BUNDLE, 'utf8'), context, { filename: BUNDLE });
  const bare = context.module.exports;
  const split = [['The patient Jose', '́', ' ', 'Garcia was seen today.']];
  assert.equal(bare.locateQuote({ text: 'The patient Jose', page: 1 }, split).status, 'not_found');
  assert.equal(bare.locateQuote({ text: 'The patient José Garcia', page: 1 }, split).count, 1);
  assert.equal(bare.locateQuote({ text: '하', page: 1 }, [['ㅎㅏ']]).count, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(bare.characterSpans('éx'))), [[0, 2], [2, 3]]);
  // everything else the viewer needs is there; without Intl.Segmenter the browser's own viewer is framed instead
  vm.runInContext(PAGE_APIS, context);
  assert.equal(bare.pdfCapable(), false);
  vm.runInContext('Intl.Segmenter = function () {};', context);
  assert.equal(bare.pdfCapable(), true);
});

test('the viewer is offered only where every built-in it and the legacy library need natively is there, and no other is asked for', () => {
  const context = vm.createContext({ module: { exports: {} } });
  vm.runInContext(fs.readFileSync(BUNDLE, 'utf8'), context, { filename: BUNDLE });
  const bare = context.module.exports;
  assert.equal(bare.pdfCapable(), false, 'no observers in a bare realm');
  vm.runInContext(PAGE_APIS, context);
  assert.equal(bare.pdfCapable(), true);
  const without = (holder, key, check) => {
    vm.runInContext(`globalThis.__kept = ${holder}[${JSON.stringify(key)}]; delete ${holder}[${JSON.stringify(key)}];`, context);
    assert.equal(vm.runInContext(`typeof ${holder}[${JSON.stringify(key)}]`, context), 'undefined', `${holder}.${key} deleted`);
    check(bare.pdfCapable(), `${holder}.${key}`);
    vm.runInContext(`${holder}[${JSON.stringify(key)}] = globalThis.__kept;`, context);
    assert.equal(bare.pdfCapable(), true);
  };
  // asked for: our own code's (the observers, the matcher's Intl.Segmenter), what the measurement found the legacy
  // library cannot run without (Promise.withResolvers, ArrayBuffer.prototype.transferToFixedLength, Array.prototype.at)
  // and what it calls with no stand-in on paths the viewer can take (structuredClone, Object.hasOwn)
  for (const [holder, key] of [['globalThis', 'IntersectionObserver'], ['globalThis', 'ResizeObserver'], ['Intl', 'Segmenter'],
    ['Promise', 'withResolvers'], ['ArrayBuffer.prototype', 'transferToFixedLength'], ['Array.prototype', 'at'],
    ['globalThis', 'structuredClone'], ['Object', 'hasOwn']]) {
    without(holder, key, (capable, name) => assert.equal(capable, false, name));
  }
  // not asked for: what the legacy build brings its own stand-ins for (the modern build needed several natively - Map
  // getOrInsertComputed from Chrome 145, Math.sumPrecise from Chrome 147), what it uses only where it exists, and what the
  // page script no longer calls (Array.prototype.findLast)
  for (const [holder, key] of [['Map.prototype', 'getOrInsertComputed'], ['Map.prototype', 'getOrInsert'], ['WeakMap.prototype', 'getOrInsertComputed'],
    ['Math', 'sumPrecise'], ['Promise', 'try'], ['Uint8Array', 'fromBase64'], ['Uint8Array.prototype', 'toBase64'], ['Uint8Array.prototype', 'toHex'],
    ['Set.prototype', 'union'], ['Set.prototype', 'intersection'], ['globalThis', 'Iterator'], ['globalThis', 'Float16Array'],
    ['Array.prototype', 'findLast']]) {
    // one this node does not have is given a stand-in first, so that its going is a real deletion
    vm.runInContext(`if (typeof ${holder}[${JSON.stringify(key)}] === 'undefined') ${holder}[${JSON.stringify(key)}] = function () {};`, context);
    without(holder, key, (capable, name) => assert.equal(capable, true, name));
  }
});

// I1-19 (the independent check's F3): I1-3 trimmed the comment above pdfCapable to keep app.js's weight, pointing at
// CORE-UX-DESIGN.md for what it moved, and two measured facts reached no file. The section it points at records how the
// measurement deleted each built-in and what the documents did without each one the legacy build puts back.
test('the measurement the pdfCapable comment points at is recorded in CORE-UX-DESIGN.md: how each built-in was deleted, and that the documents drew and marked as before (I1-19)', () => {
  assert.ok(fs.readFileSync(BUNDLE, 'utf8').includes('CORE-UX-DESIGN.md ("Browsers that mark")'), 'the comment points at it');
  const design = fs.readFileSync(path.join(ROOT, 'CORE-UX-DESIGN.md'), 'utf8');
  const start = design.indexOf('\n- **Browsers that mark**');
  assert.ok(start >= 0, 'the section is there');
  const end = design.indexOf('\n- **', start + 1);
  const section = design.slice(start, end < 0 ? undefined : end).replace(/\s+/g, ' ');
  for (const fact of [
    'deleted in the page and in the library\'s worker before the library loaded',
    'its `typeof` read before and after, so a deletion that did not apply could not pass',
    'then the preview\'s PDFs and the walk\'s gi-02 opened and every quote chosen',
    'seen present again once it had run, and with each one deleted the documents drew and marked exactly as before',
  ]) assert.ok(section.includes(fact), fact);
});

// A synthetic PDF, one content stream per page, with Helvetica as /F1 and Helvetica-Bold as /F2 (standard fonts, no
// embedded data): enough to read what the library makes of a drawing.
function rawPdf(pages) {
  const objects = [];
  const add = body => { objects.push(body); return objects.length; };
  const catalog = add(null);
  const tree = add(null);
  const regular = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>');
  const bold = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>');
  const kids = pages.map(content => {
    const stream = add(`<< /Length ${Buffer.byteLength(content, 'latin1')} >>\nstream\n${content}\nendstream`);
    return add(`<< /Type /Page /Parent ${tree} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${regular} 0 R /F2 ${bold} 0 R >> >> /Contents ${stream} 0 R >>`);
  });
  objects[catalog - 1] = `<< /Type /Catalog /Pages ${tree} 0 R >>`;
  objects[tree - 1] = `<< /Type /Pages /Kids [${kids.map(kid => `${kid} 0 R`).join(' ')}] /Count ${kids.length} >>`;
  let out = '%PDF-1.4\n';
  const offsets = [];
  objects.forEach((body, index) => {
    offsets.push(Buffer.byteLength(out, 'latin1'));
    out += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = Buffer.byteLength(out, 'latin1');
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root ${catalog} 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, 'latin1');
}

// Every page's text items as the pinned library reads them (getTextContent with its defaults, as the viewer calls it), in
// node: {str, transform, width, hasEOL} of each item that has a string.
async function readPdfItems(bytes) {
  const { pathToFileURL } = require('node:url');
  const build = path.join(ROOT, 'studio', 'static', 'studio', 'lib', 'pdfjs-6.5.438', 'legacy', 'build');
  const library = await import(pathToFileURL(path.join(build, 'pdf.min.mjs')).href);
  library.GlobalWorkerOptions.workerSrc = pathToFileURL(path.join(build, 'pdf.worker.min.mjs')).href;
  const task = library.getDocument({ data: new Uint8Array(bytes), isEvalSupported: false, enableXfa: false, useWasm: false, useSystemFonts: false,
    verbosity: 0, standardFontDataUrl: pathToFileURL(path.join(build, '..', '..', 'standard_fonts', path.sep)).href });
  try {
    const pdf = await task.promise;
    const pages = [];
    for (let number = 1; number <= pdf.numPages; number += 1) {
      const content = await (await pdf.getPage(number)).getTextContent();
      pages.push(content.items.filter(made => typeof made.str === 'string').map(({ str, transform, width, hasEOL }) => ({ str, transform, width, hasEOL })));
    }
    return pages;
  } finally {
    await task.destroy();
  }
}

// A text item as the PDF library reads it: its string, its transform (font size, origin), its width (the advance along
// its text; none unless given, so no R2b geometry) and whether a line ends after it.
function item(str, x = 0, y = 0, { size = 10, eol = false, width } = {}) {
  return width === undefined ? { str, transform: [size, 0, 0, size, x, y], hasEOL: eol } : { str, transform: [size, 0, 0, size, x, y], width, hasEOL: eol };
}

test('R1: text drawn again over an earlier drawing of the same words and font height is one occurrence, never marked, and does not break a passage that crosses it', t => {
  // fake bold: the same string drawn twice 0.35 pt apart, as two items
  const bold = [item('DIAGNOSIS: TUBULAR ADENOMA.', 46.56, 700, { eol: true }), item('DIAGNOSIS: TUBULAR ADENOMA.', 46.91, 700, { eol: true }),
    item('The procedure was uneventful.', 46.56, 680), item(' ', 160, 680), item('Impression:', 180, 680), item('Impression:', 180.3, 680),
    item(' ', 230, 680), item('two polyps were removed.', 236, 680, { eol: true })];
  assert.deepEqual([...app.overprintCopies(bold)], [1, 5], 'the second drawing of each is the copy');
  const once = app.locateQuote({ text: 'DIAGNOSIS: TUBULAR ADENOMA.', page: 1 }, [bold]);
  assert.deepEqual([once.status, once.count, once.marks], ['marked', 1, { 1: [{ item: 0, start: 0, end: 27, occurrence: 0 }] }], 'counted once, the copy unmarked');
  assert.equal(app.markNote(once), 'Marked on page 1.');
  const across = app.locateQuote({ text: 'The procedure was uneventful. Impression: two polyps were removed.', page: 1 }, [bold]);
  assert.deepEqual([across.status, across.count], ['marked', 1], 'the passage crosses the doubled label');
  assert.ok(across.marks[1].every(part => part.item !== 5), 'the copy is never marked');
  assert.deepEqual(app.pageText(bold).copies, [1, 5]);
  // what makes a copy, part by part: the distance, a straight line within max(1, 0.2 x the later item's height)
  const copies = items => [...app.overprintCopies(items)];
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51, 700)]), [1], 'within max(1, 0.2 x 10) = 2 units');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 52, 700)]), [1], 'exactly 2 units: within');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 52.01, 700)]), [], 'just beyond');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51.2, 701.5)]), [1], 'the distance is measured as a straight line (1.2, 1.5: 1.92)');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51.3, 701.6)]), [], '(1.3, 1.6: 2.06)');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 2 }), item('Polyp', 50.9, 700, { size: 2 })]), [1], 'a small font: at least 1 unit');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 2 }), item('Polyp', 51.1, 700, { size: 2 })]), []);
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 30 }), item('Polyp', 55.9, 700, { size: 30 })]), [1], 'a large font: 0.2 x 30 = 6 units');
  // the font heights, hypot(transform[2], transform[3]), agree within 1% (|h1 - h2| <= 0.01 x the larger): a rotated font
  // has the same height; the same words at the same place in another size are other words (shared example 22)
  assert.deepEqual(copies([item('Polyp', 50, 700), { str: 'Polyp', transform: [0, 10, -10, 0, 51.9, 700], hasEOL: false }]), [1]);
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 50, 700, { size: 10.1 })]), [1], '10 and 10.1: within 1%');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 50, 700, { size: 10.11 })]), [], '10 and 10.11: beyond');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 50, 700, { size: 10.103 })]), [], '10 and 10.103: just beyond 1%, though close in size');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 10.103 }), item('Polyp', 50, 700)]), [], 'in either order');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 50, 700, { size: 10.1009 })]), [1], '10 and 10.1009: within');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 10.1 }), item('Polyp', 50, 700)]), [1], 'the later one smaller, within 1%');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 50, 700, { size: 24 })]), [], '10 and 24 at one place: two drawings');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 0 }), item('Polyp', 50.5, 700, { size: 0 })]), [1], 'two heights of 0 agree, reach 1');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 0 }), item('Polyp', 50.5, 700, { size: 0.001 })]), []);
  assert.deepEqual(copies([item('Polyp', 50, 700), item('polyp', 50.3, 700)]), [], 'another case is another string');
  assert.deepEqual(copies([item('ﬁ', 50, 700), item('fi', 50.3, 700)]), [1], 'equal after NFKC');
  assert.deepEqual(copies([item(' ', 50, 700), item(' ', 50.3, 700)]), [], 'white space alone is never a copy');
  assert.deepEqual(copies([item('', 50, 700), item('', 50, 700)]), []);
  // the earlier item is any earlier item of the page: there is no window
  const between = n => [item('Polyp', 50, 700), ...Array.from({ length: n }, (_, i) => item(`w${i}`, 100 + i * 20, 700)), item('Polyp', 50.3, 700)];
  for (const n of [7, 8, 9, 40, 3000]) assert.deepEqual(copies(between(n)), [n + 1], `${n} items between`);
  // a copy of a copy counts (each is within its own reach of the one before), and the earlier item's place is its own
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51.9, 700), item('Polyp', 53.8, 700)]), [1, 2]);
  assert.deepEqual(copies([item('Polyp', 53.8, 700), item('Polyp', 50, 700)]), [], '3.8 apart: two drawings, in either order');
  // bare strings carry no geometry: never a copy, nor the earlier item of one
  assert.deepEqual(copies(['Polyp', 'Polyp']), []);
  assert.deepEqual(copies([{ str: 'Polyp' }, { str: 'Polyp', transform: [10, 0, 0, 10, 0, 0] }]), []);
  assert.deepEqual(copies([item('Polyp', 50, 700), { str: 'Polyp', transform: [10, 0, 0, NaN, 50, 700] }]), []);
  // the same words drawn at another place are two occurrences
  const twice = app.locateQuote({ text: 'Polyp', page: 1 }, [[item('Polyp', 50, 700, { eol: true }), item('Polyp', 50, 600, { eol: true })]]);
  assert.equal(twice.count, 2);
  // a line-printer line drawn as 9 items and overstruck 0.2 pt to the right: every copy is the 9th item after its original
  // (shared example 21)
  const words = ['IMPRESSION:', ' ', 'TWO', ' ', 'POLYPS', ' ', 'WERE', ' ', 'REMOVED.'];
  const line = dx => { let x = 56 + dx; return words.map(word => { const made = item(word, x, 700, { size: 9, width: word.length * 5.4 }); x += word.length * 5.4; return made; }); };
  const overstruck = [...line(0), ...line(0.2)];
  assert.deepEqual(copies(overstruck), [9, 11, 13, 15, 17]);
  // the cost is linear in the page's items: a page of 20,000 items holding 2,000 strings drawn 10 times each at distinct
  // places, and one of 20,000 identical strings at distinct places, are each prepared well under a second
  const page = name => Array.from({ length: 20000 }, (_, index) => item(name(index), 50 + (index % 100) * 6, 700 - Math.floor(index / 100) * 12,
    { width: 5, eol: index % 100 === 99 }));
  for (const [label, name] of [['2,000 strings x 10', index => `w${index % 2000}`], ['20,000 identical strings', () => 'Polyp']]) {
    const began = performance.now();
    const text = app.pageText(page(name));
    const took = performance.now() - began;
    t.diagnostic(`R1 cost, ${label}: ${took.toFixed(1)} ms`);
    assert.deepEqual(text.copies, [], label);
    assert.ok(took < 1000, `${label}: ${took.toFixed(1)} ms`);
  }
});

test('R2: a quote that begins or ends with a letter or a digit is never counted inside a longer word', () => {
  const page = [['The patient was told to bathe ending the preparation at noon.', ' ', 'Findings: the end of the procedure was uneventful.', ' ',
    'Mild pain was reported; the abdomen was painless on palpation.', ' ', 'A 5 mm polyp was found; polypectomy was performed; no other polyps.']];
  const count = (text, pages = page) => app.locateQuote({ text, page: 1 }, pages).count;
  assert.equal(count('the end'), 1, '"the end" inside "bathe ending" is not counted');
  assert.equal(count('pain'), 1, '"pain" inside "painless" is not counted');
  assert.equal(count('polyp'), 1, 'nor "polyp" inside "polypectomy" or "polyps"');
  assert.deepEqual(app.locateQuote({ text: 'the end', page: 1 }, page).marks, { 1: [{ item: 2, start: 10, end: 17, occurrence: 0 }] });
  // white space inside the quote stays ignored entirely: spaces the page has or lacks inside the words do not matter
  assert.equal(count('the end of'), 1);
  assert.equal(count('theendof'), 1);
  // so a quote whose words run together on the page is found where they make one whole word (the rule as stated)
  assert.equal(count('not able', [['This is notable.']]), 1);
  assert.equal(count('not able', [['This is notables.']]), 0);
  assert.equal(count('notable', [['It is not able.']]), 1, 'but the page\'s words may run together inside the quote');
  // digits keep to the edge too
  assert.equal(count('5 mm', [['A 15 mm polyp; a 5 mm polyp.']]), 1);
  assert.deepEqual(app.locateQuote({ text: '5 mm', page: 1 }, [['A 15 mm polyp; a 5 mm polyp.']]).marks[1][0].start, 17);
  // a quote that begins or ends with something else keeps no edge there
  assert.equal(count('.', [['a.b.']]), 2);
  assert.equal(count('polyp;', [['polyp; xpolyp;']]), 1, 'it begins with a letter: the start keeps to an edge');
  assert.equal(count('(polyp', [['x(polyps']]), 0, 'it ends with a letter: the end keeps to an edge');
  assert.equal(count('(polyp)', [['x(polyp)y']]), 1, 'neither end is a letter or a digit');
  // the page's start and end are edges
  assert.equal(count('polyp', [['polyp']]), 1);
  // what is read before and after: the items' strings in order, joined with nothing between them, and a line break after
  // an item the library ends a line with; where two items meet with nothing between them, they run their words together
  // only where the second visibly continues the first (R2b): bare strings have no geometry, so they meet at an edge
  assert.equal(count('polyp', [['the', 'polyp', 's']]), 1, 'bare strings meet at word edges (shared example 15)');
  assert.equal(count('polyp', [[item('the', 0, 0, { eol: true }), item('polyp', 0, -12, { eol: true }), item('s', 0, -24)]]), 1, 'line breaks between them: a word');
  const continued = [[item('pain', 56, 700, { size: 11, width: 20.2 }), item('less', 76.2, 700, { size: 11, width: 18.3 })]];
  assert.deepEqual([count('pain', continued), count('less', continued), count('painless', continued)], [0, 0, 1], 'one word drawn in two (shared example 13)');
  // a letter, a digit or a combining mark joins a word; another character does not
  assert.equal(count('polyp', [['xpolyp']]), 0);
  assert.equal(count('polyp', [['2polyp']]), 0);
  assert.equal(count('polyp', [['́polyp']]), 0, 'a mark before it');
  assert.equal(count('polyp', [['épolyp']]), 0, 'an accented letter before it');
  assert.equal(count('polyp', [['\u{1D49C}polyp']]), 0, 'an astral letter before it (read as one character, not half of one)');
  assert.equal(count('polyp', [['-polyp/']]), 1);
  // the characters before and after are read as the page writes them, not after NFKC (the walk's judge reads them so too)
  assert.equal(count('Botox', [['Botox™ was given.']]), 1, 'a trade mark sign after it is an edge, though NFKC writes it "TM"');
  assert.equal(count('5', [['5㎏ dose']]), 1, 'a unit sign after it is an edge, though NFKC writes it "kg"');
  assert.equal(count('polyp', [['⑴polyp']]), 0, 'a parenthesised digit before it is a digit, though NFKC writes it "(1)"');
  assert.equal(count('polyp', [[' polyp ']]), 1, 'other spaces are edges');
  // an overprint copy is not read as the character before: what is read is the page's text, copies left out
  assert.equal(count('polyp', [[item('polyp', 10, 0), item('polyp', 10.3, 0)]]), 1, 'the copy right after it is not read');
  assert.equal(count('polyp', [[item('polyp', 10, 0, { width: 20 }), item('polyp', 30, 0, { width: 20 })]]), 0, 'one drawing continuing another: one word "polyppolyp"');
  assert.equal(count('polyp', [[item('polyp', 10, 0, { width: 20 }), item('polyp', 40, 0, { width: 20 })]]), 2, 'a gap between them: two drawings, two words');
  // a place turned away is passed over by one unit only, so a word right after it is still found
  assert.equal(count('aa', [['a aa']]), 1, 'not "a a" (inside "a aa"), but "aa"');
  assert.deepEqual(app.locateQuote({ text: 'aa', page: 1 }, [['a aa']]).marks, { 1: [{ item: 0, start: 2, end: 4, occurrence: 0 }] });
  assert.equal(count('aa', [['aaaa']]), 0, 'one word: none of it is these words');
  // case-blind keeps to the edges as exact case does
  assert.equal(app.locateQuote({ text: 'PAIN', page: 1 }, page).count, 1);
  // the quote's own first and last characters decide: a letter with its accent counts as a letter, a final mark too
  assert.equal(count('café', [['cafés']]), 0);
  assert.equal(count('café', [['café s']]), 1);
  const ends = text => app.quoteEdges(app.pageText([text]));
  const none = { start: false, end: false, startDigit: false, endDigit: false, startSeparated: false, endSeparated: false };
  assert.deepEqual(ends('.polyp'), { ...none, end: true });
  assert.deepEqual(ends('q́'), { ...none, start: true, end: true }, 'the last character is q with its accent');
  assert.deepEqual(ends(' (x) '), none);
  assert.deepEqual(ends('2.5 mg'), { ...none, start: true, end: true, startDigit: true });
  assert.deepEqual(ends('.5 mg.'), { ...none, startSeparated: true }, 'a separator with a digit after it in the quote');
  assert.deepEqual(ends('Take 2.'), { ...none, start: true, endSeparated: true }, 'a separator with a digit before it in the quote');
  assert.deepEqual(ends('１２．'), { ...none, start: true, startDigit: true, endSeparated: true }, 'its folded characters: NFKC first');
  assert.deepEqual(ends('糖尿病'), none, 'a Han ideograph asks for no edge (R2c)');
  // continuation: the edges are read in the two pages - the start on the quote's page, the end on the next
  const pages = [['It ends with the start of a'], ['passage that runs on.']];
  assert.equal(app.locateQuote({ text: 'the start of a passage', page: 1 }, pages).scope, 'continued');
  assert.equal(app.locateQuote({ text: 'he start of a passage', page: 1 }, pages).status, 'not_found', 'its start is inside "the"');
  assert.equal(app.locateQuote({ text: 'the start of a passag', page: 1 }, pages).status, 'not_found', 'its end is inside "passage"');
  // a text document keeps its own rule (findPassages): no word edges there
  assert.deepEqual(app.findPassages('bathe ending', 'the end'), [[2, 9]]);
});

test('R2a: a number\'s own separator keeps its digits in one word, at both ends of an occurrence, as Unicode\'s word boundaries have it', () => {
  // the table: exactly the 21 code points Unicode 16.0 calls MidNum, MidNumLet or Single_Quote, which join two digits only
  // when a digit stands on each side (UAX #29 WB11, WB12), pinned and held to Intl.Segmenter here
  const table = [0x0027, 0x002c, 0x002e, 0x003b, 0x037e, 0x0589, 0x060c, 0x060d, 0x066c, 0x07f8, 0x2018, 0x2019, 0x2024, 0x2044,
    0xfe50, 0xfe52, 0xfe54, 0xff07, 0xff0c, 0xff0e, 0xff1b];
  assert.deepEqual([...app.NUMBER_SEPARATORS].sort((a, b) => a - b), table);
  const words = new Intl.Segmenter('en', { granularity: 'word' });
  const parts = value => [...words.segment(value)].length;
  for (const point of table) {
    const x = String.fromCodePoint(point);
    assert.deepEqual([parts(`1${x}2`), parts(`1${x}`), parts(`${x}2`)], [1, 2, 2], `U+${point.toString(16)}`);
  }
  for (const other of ['/', '-', ':', '·', ' ', 'x']) assert.ok(!app.NUMBER_SEPARATORS.has(other.codePointAt(0)), other);
  const count = (text, items) => app.locateQuote({ text, page: 1 }, [items]).count;
  // (start, a): the quote begins with a digit; before it, a separator with a digit before that
  assert.equal(count('1 cm lesion', ['A 2.1 cm lesion was excised.']), 0);
  assert.equal(count('500 mL', ['Estimated blood loss 1,500 mL.']), 0);
  assert.equal(count('000 m', ['Total 1’000 m walked']), 0, 'an apostrophe as a thousands separator');
  assert.equal(count('٥٠٠', ['١٬٥٠٠ ml']), 0, 'Arabic-Indic digits and the Arabic thousands separator');
  assert.equal(count('5 mg', ['Dose 2. 5 mg later']), 1, 'a space after the point: two words');
  assert.equal(count('2', ['1/2 tablet']), 1, 'a slash is no separator');
  assert.equal(count('2', ['1-2 tablets']), 1, 'nor a hyphen');
  assert.equal(count('5 mg', ['Take .5 mg']), 1, 'no digit before the separator');
  // (start, b): the quote begins with a separator and a digit; before it, a digit
  assert.equal(count('.5 mg', ['Take 2.5 mg']), 0);
  assert.equal(count('.5 mg', ['Take .5 mg']), 1);
  // (end, a): the quote ends with a digit; after it, a separator with a digit after that
  assert.equal(count('Hemoglobin 12', ['Hemoglobin 12.5 g/dL']), 0);
  assert.equal(count('3.1', ['Sections 3.1.2 and 4.']), 0);
  assert.equal(count('1990', ['the 1990’s']), 1, 'a letter after the separator');
  assert.equal(count('Hemoglobin 12', ['Hemoglobin 12. Next']), 1);
  // (end, b): the quote ends with a separator after a digit; after it, a digit
  assert.equal(count('2.', ['Take 2.5 mg.']), 0);
  assert.equal(count('2.', ['Take 2. Then 5 mg.']), 1);
  assert.deepEqual(app.locateQuote({ text: '1.', page: 1 }, [['1. Hypokalemia, potassium 3.1.']]).marks, { 1: [{ item: 0, start: 0, end: 2, occurrence: 0 }] }, 'the list number only');
  // the quote's characters are folded (NFKC) and the page's read as written
  assert.equal(count('５ mg', ['１２．５ mg']), 0, 'full-width digits and point');
  assert.equal(count('２．', ['Take 2.5 mg']), 0, 'a full-width quote of "2."');
  // reading stops at an edge two drawings make (R2b): a code point beyond it counts as none
  const at = (str, x, width) => item(str, x, 700, { width });
  assert.equal(count('5 mg', [at('Total 12', 56, 40), at('.5 mg', 96, 25)]), 0, 'the second continues the first (shared example 16)');
  assert.equal(count('5 mg', [at('Total 12', 56, 40), at('.5 mg', 50, 25)]), 1, 'it jumps back: an edge (shared example 17)');
  assert.equal(count('Dose 2', [at('Dose 2.', 56, 35), at('5 mg', 91, 25)]), 0, 'the end: continued');
  assert.equal(count('Dose 2', [at('Dose 2.', 56, 35), at('5 mg', 40, 25)]), 1, 'the end: an edge beyond the separator');
});

test('R2b: two drawings meet at a word edge unless the second visibly continues the first', async () => {
  const drawing = (str, transform, width) => ({ str, transform, width, hasEOL: false });
  const flat = (x, y, size, width, str = 'w') => drawing(str, [size, 0, 0, size, x, y], width);
  const continues = (a, b) => app.continuesDrawing(a, b);
  // the next one's origin at the first one's end: along within 0.25 x its height of its width, across within 0.1 x it
  assert.ok(continues(flat(56, 700, 10, 40), flat(96, 700, 10, 9)));
  assert.ok(continues(flat(56, 700, 10, 40), flat(98.5, 700, 10, 9)), '2.5 further along');
  assert.ok(!continues(flat(56, 700, 10, 40), flat(98.6, 700, 10, 9)), '2.6 further');
  assert.ok(continues(flat(56, 700, 10, 40), flat(93.5, 700, 10, 9)), '2.5 back');
  assert.ok(!continues(flat(56, 700, 10, 40), flat(93.4, 700, 10, 9)), '2.6 back');
  assert.ok(continues(flat(56, 700, 10, 40), flat(96, 701, 10, 9)), '1 up');
  assert.ok(!continues(flat(56, 700, 10, 40), flat(96, 701.1, 10, 9)), '1.1 up: raised');
  assert.ok(!continues(flat(56, 700, 10, 40), flat(96, 698.9, 10, 9)), '1.1 down');
  // font heights within 5%
  assert.ok(continues(flat(56, 700, 11, 40), flat(96, 700, 11.55, 9)));
  assert.ok(!continues(flat(56, 700, 11, 40), flat(96, 700, 11.6, 9)), 'a smaller or larger marker');
  // both need that geometry: a finite transform and a finite width above 0
  assert.ok(!continues(flat(56, 700, 10, 0), flat(96, 700, 10, 9)), 'no width');
  assert.ok(!continues({ str: 'w', transform: [10, 0, 0, 10, 56, 700] }, flat(66, 700, 10, 9)), 'no width given');
  assert.ok(!continues(drawing('w', [10, 0, 0, 10, NaN, 700], 40), flat(96, 700, 10, 9)), 'no finite transform');
  assert.ok(!continues('the', 'polyp'), 'bare strings');
  assert.ok(!continues(flat(56, 700, 10, 40), flat(96, 700, 10, Infinity)), 'an infinite width');
  // rotated text: the library's width is the advance along the text (read below), so along and across follow the text
  const turned = (y, width, str) => drawing(str, [0, 11, -11, 0, 300, y], width);
  assert.ok(continues(turned(100, 20.2, 'pain'), turned(120.2, 18.3, 'less')), 'shared example 20');
  assert.ok(!continues(turned(100, 20.2, 'pain'), turned(124, 18.3, 'less')));
  assert.equal(app.locateQuote({ text: 'pain', page: 1 }, [[turned(100, 20.2, 'pain'), turned(120.2, 18.3, 'less')]]).count, 0);
  // the place lies between two items' characters with nothing between them: a line break or an item that gives nothing
  // in between does not make one; a drawing that gives only a format character does not count
  const pain = flat(56, 700, 11, 20.2, 'pain');
  const less = flat(76.2, 700, 11, 18.3, 'less');
  const countPain = items => app.locateQuote({ text: 'pain', page: 1 }, [items]).count;
  assert.equal(countPain([pain, { ...flat(200, 500, 11, 5, '​') }, less]), 0, 'a zero-width space drawn elsewhere between them gives nothing');
  assert.equal(countPain([{ ...pain, hasEOL: true }, less]), 1, 'a line break between them');
  assert.deepEqual([...app.pageText([pain, less]).edges], new Array(9).fill(0), 'no edge where one continues the other');
  assert.deepEqual([...app.pageText([pain, { ...less, transform: [11, 0, 0, 11, 56, 700] }]).edges].indexOf(1), 4, 'an edge at the place between them');
  // a footnote marker raised and smaller, glued to a word (shared example 12), and fake bold's jump back (example 14)
  const footnote = [flat(56, 700, 11, 190, 'Assessment: type 2 diabetes mellitus'), flat(246, 704, 7, 3.9, '1'), flat(249.9, 700, 11, 85, ', well controlled.')];
  assert.equal(app.locateQuote({ text: 'type 2 diabetes mellitus', page: 1 }, [footnote]).count, 1);
  // what the library gives, read with the pinned library itself: a word drawn in two fonts, flat and turned a quarter
  // round by its text matrix or by the page's matrix, is two items; each width is its advance along its text (Helvetica
  // "pain" at 11 pt: 20.79), so the rule finds them continued and "pain" is no word of its own there
  const items = await readPdfItems(rawPdf([
    'BT /F1 11 Tf 56 700 Td (pain) Tj ET BT /F2 11 Tf 76.79 700 Td (less) Tj ET',
    'BT /F1 11 Tf 0 1 -1 0 300 100 Tm (pain) Tj ET BT /F2 11 Tf 0 1 -1 0 300 120.79 Tm (less) Tj ET',
    'q 0 1 -1 0 300 100 cm BT /F1 11 Tf 0 0 Td (pain) Tj ET BT /F2 11 Tf 20.79 0 Td (less) Tj ET Q',
    'BT /F1 11 Tf 56 700 Td (pain) Tj ET BT /F2 7 Tf 76.79 704 Td (1) Tj ET',
  ]));
  for (const [index, page] of items.slice(0, 3).entries()) {
    assert.deepEqual(page.map(made => made.str), ['pain', 'less'], `page ${index + 1}`);
    assert.ok(Math.abs(page[0].width - 20.79) < 1e-6, `page ${index + 1}: the advance along the text, ${page[0].width}`);
    assert.ok(continues(page[0], page[1]), `page ${index + 1}`);
    assert.equal(app.locateQuote({ text: 'pain', page: 1 }, [page]).count, 0, `page ${index + 1}`);
    assert.equal(app.locateQuote({ text: 'painless', page: 1 }, [page]).count, 1, `page ${index + 1}`);
  }
  assert.deepEqual(items[3].map(made => made.str), ['pain', '1'], 'a raised, smaller marker is an item of its own');
  assert.equal(app.locateQuote({ text: 'pain', page: 1 }, [items[3]]).count, 1, 'and meets the word at an edge');
});

test('R2c: a Han ideograph or a hiragana character is a word of its own; katakana stays a word part', () => {
  const count = (text, items) => app.locateQuote({ text, page: 1 }, [items]).count;
  assert.equal(count('糖尿病', ['患者有糖尿病史和高血压']), 1, 'shared example 18');
  assert.equal(count('高血压', ['患者有糖尿病史和高血压']), 1);
  assert.equal(count('高血圧', ['高血圧の治療']), 1, 'shared example 19: before a hiragana character');
  assert.equal(count('Botox', ['Botox注射']), 1, 'a Latin word before a Han ideograph');
  assert.equal(count('こと', ['ひとつのこと']), 1, 'hiragana among hiragana');
  assert.equal(count('カナ', ['カタカナテスト']), 0, 'katakana inside katakana: inside a word');
  assert.equal(count('テスト', ['カタカナ テスト']), 1);
  assert.equal(count('糖x', ['a糖xb']), 0, 'a Han ideograph asks for no edge, the Latin end still does');
  assert.equal(count('糖x', ['a糖x b']), 1);
  assert.equal(count('x', ['〇x〇']), 1, 'an ideographic number sign is a word of its own too');
});

test('the shared examples of round 5, as the walk\'s judge pins them', () => {
  const at = (str, size, x, y, width) => ({ str, transform: [size, 0, 0, size, x, y], width, hasEOL: false });
  const courier = dx => {
    let x = 56 + dx;
    return ['IMPRESSION:', ' ', 'TWO', ' ', 'POLYPS', ' ', 'WERE', ' ', 'REMOVED.'].map(word => {
      const made = at(word, 9, x, 700, word.length * 5.4);
      x += word.length * 5.4;
      return made;
    });
  };
  const rows = [
    [1, ['A 2.1 cm lesion was excised.'], [['1 cm lesion', 0]]],
    [2, ['Lisinopril 2.5 mg daily.'], [['5 mg daily', 0], ['2.5 mg daily', 1]]],
    [3, ['Hemoglobin 12.5 g/dL'], [['Hemoglobin 12', 0]]],
    [4, ['Estimated blood loss 1,500 mL.'], [['500 mL', 0], ['1,500 mL', 1]]],
    [5, ['1. Hypokalemia, potassium 3.1.'], [['1.', 1]]],
    [6, ['Take 2.5 mg.'], [['2.', 0]]],
    [7, ['A 15 mm polyp; a 5 mm polyp.'], [['5 mm', 1]]],
    [8, ['Sections 3.1.2 and 4.'], [['3.1', 0], ['3.1.2', 1]]],
    [9, ['Dose 2. 5 mg later'], [['5 mg', 1]]],
    [10, ['１２．５ mg'], [['５ mg', 0]]],
    [11, ['the 1990’s'], [['1990', 1]]],
    [12, [at('Assessment: type 2 diabetes mellitus', 11, 56, 700, 190), at('1', 7, 246, 704, 3.9), at(', well controlled.', 11, 249.9, 700, 85)],
      [['type 2 diabetes mellitus', 1], ['mellitus1', 1]]],
    [13, [at('pain', 11, 56, 700, 20.2), at('less', 11, 76.2, 700, 18.3)], [['pain', 0], ['painless', 1]]],
    [14, [at('Diagnosis: Chest pain', 11, 56, 700, 107), at('Chest pain since this morning.', 11, 111.3, 700, 150)],
      [['Diagnosis: Chest pain', 1], ['Chest pain since this morning.', 1], ['Chest pain', 2]]],
    [15, ['the', 'polyp', 's'], [['polyp', 1]]],
    [16, [at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 96, 700, 25)], [['5 mg', 0]]],
    [17, [at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 50, 700, 25)], [['5 mg', 1]]],
    [18, ['患者有糖尿病史和高血压'], [['糖尿病', 1], ['高血压', 1]]],
    [19, ['高血圧の治療'], [['高血圧', 1]]],
    [20, [{ str: 'pain', transform: [0, 11, -11, 0, 300, 100], width: 20.2, hasEOL: false }, { str: 'less', transform: [0, 11, -11, 0, 300, 120.2], width: 18.3, hasEOL: false }],
      [['pain', 0]]],
    [21, [...courier(0), ...courier(0.2)], [['TWO POLYPS', 1], ['IMPRESSION: TWO POLYPS WERE REMOVED.', 1]]],
    [22, [at('Polyp', 10, 50, 700, 26), at('Polyp', 24, 50, 700, 62)], [['Polyp', 2]]],
  ];
  assert.equal(rows.length, 22);
  for (const [number, items, quotes] of rows) {
    for (const [text, count] of quotes) assert.equal(app.locateQuote({ text, page: 1 }, [items]).count, count, `row ${number}: ${JSON.stringify(text)}`);
  }
});

test('whole characters of the text as the PDF library reads it, which is not always the text as drawn', () => {
  // the library never gives a ligature character: a drawn ligature the PDF declares as two letters reads as two letters
  // ("fi" below is one glyph on the page), so only the word-edge rule keeps a mark from ending between them
  const ligature = [['The finding was confirmed.']];
  assert.equal(app.locateQuote({ text: 'The f', page: 1 }, ligature).status, 'not_found', 'it would end inside the word');
  assert.equal(app.locateQuote({ text: 'The finding', page: 1 }, ligature).count, 1);
  // a spacing accent (U+00B4) kerned back over a letter is a character of its own, after the letter: the letter is marked
  // without the accent it is drawn with, and the accented quote is not found
  const accent = [['Patient Jose', '\u00b4 was seen.']];
  assert.deepEqual(app.locateQuote({ text: 'Patient Jose', page: 1 }, accent).marks, { 1: [{ item: 0, start: 0, end: 12, occurrence: 0 }] });
  assert.equal(app.locateQuote({ text: 'Patient Jos\u00e9', page: 1 }, accent).status, 'not_found');
});

test('R3: format characters are dropped from the quote as the PDF library drops them from the page', () => {
  // the library drops a glyph whose Unicode is a format character (a soft hyphen, a zero-width space or joiner, a
  // direction mark, a word joiner, a byte-order mark): the quote drops the same, and is found
  const page = [['alphabeta north gate softhyphen']];
  for (const mark of ['­', '​', '‌', '‍', '‎', '⁠', '﻿']) {
    const result = app.locateQuote({ text: `alpha${mark}beta`, page: 1 }, page);
    assert.deepEqual([result.status, result.count], ['marked', 1], `U+${mark.codePointAt(0).toString(16)}`);
  }
  assert.equal(app.locateQuote({ text: 'soft­hyphen', page: 1 }, page).count, 1);
  assert.equal(app.locateQuote({ text: '​‍', page: 1 }, page).status, 'empty', 'a quote of format characters only has nothing to mark');
  // the page's own format characters, where a text holds them, are dropped too, and an item's offsets are its own
  const own = [['alpha­beta and more']];
  const found = app.locateQuote({ text: 'alphabeta', page: 1 }, own);
  assert.deepEqual(found.marks, { 1: [{ item: 0, start: 0, end: 10, occurrence: 0 }] }, 'the mark covers the dropped character between its letters');
  assert.equal(app.pageText(own[0]).joined, 'alphabeta and more');
  // a joiner dropped: a sequence the joiner held together is its characters (the library never keeps one)
  assert.equal(app.locateQuote({ text: '\u{1F469}', page: 1 }, [['\u{1F469}‍\u{1F4BB} ok']]).count, 1);
  assert.equal(app.locateQuote({ text: '\u{1F469}‍\u{1F4BB}', page: 1 }, [['\u{1F469}\u{1F4BB} ok']]).count, 1);
});

test('the matcher is exact-case first, case-blind only where no exact-case occurrence exists, and counts every one', () => {
  const pages = [['Gastric antrum biopsy. The gastric antrum was red. gastric antrum.']];
  const exact = app.locateQuote({ text: 'gastric antrum', page: 1 }, pages);
  assert.deepEqual([exact.count, exact.caseBlind], [2, false], 'the capitalised one is not counted while exact ones exist');
  assert.deepEqual(markedParts(exact, pages).map(([, , occurrence]) => occurrence), [0, 1]);
  const blind = app.locateQuote({ text: 'GASTRIC ANTRUM', page: 1 }, pages);
  assert.deepEqual([blind.count, blind.caseBlind], [3, true]);
  assert.equal(app.markNote(blind), 'These words appear 3 times on page 1. Each is marked.');
  // duplicates: each is marked and counted, left to right, never overlapping
  const twice = [['the gastric antrum.', ' x ', 'the gastric antrum.']];
  const both = app.locateQuote({ text: 'the gastric antrum.', page: 1 }, twice);
  assert.deepEqual(markedParts(both, twice), [[1, 'the gastric antrum.', 0], [1, 'the gastric antrum.', 1]]);
  assert.equal(app.markNote(both), 'These words appear 2 times on page 1. Each is marked.');
  assert.equal(app.locateQuote({ text: 'aa', page: 1 }, [['aa aa aa']]).count, 3);
});

test('the matcher looks on the quote\'s page, then from it onto the next, and never marks another page', () => {
  const pages = [['First page text.', 'It ends with the start of a'], ['passage that runs on.', 'Only on page two.'], ['Only on page three.']];
  // not found: nothing marked, and the page is named
  const none = app.locateQuote({ text: 'Not in the document.', page: 1 }, pages);
  assert.deepEqual([none.status, none.count, none.pages, none.marks], ['not_found', 0, [], {}]);
  assert.equal(app.markNote(none), 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.');
  // continuation: it starts on the quote's page and runs onto the next; the marked part on each page is shown
  const run = app.locateQuote({ text: 'the start of a passage that runs on', page: 1 }, pages);
  assert.deepEqual([run.status, run.scope, run.count, run.pages], ['marked', 'continued', 1, [1, 2]]);
  assert.deepEqual(markedParts(run, pages), [[1, 'the start of a', 0], [2, 'passage that runs on', 0]]);
  assert.equal(app.markNote(run), 'Marked on page 1, continuing onto page 2.');
  // a quote found only on another page is NOT marked: not the next page, not any other
  for (const [text, page] of [['Only on page two.', 1], ['Only on page three.', 1], ['Only on page three.', 2], ['First page text.', 2]]) {
    const other = app.locateQuote({ text, page }, pages);
    assert.deepEqual([other.status, other.pages, other.marks], ['not_found', [], {}], `${text} on page ${page}`);
  }
  // a passage that starts on the page before the quote's is not the quote's page's either
  assert.equal(app.locateQuote({ text: 'the start of a passage that runs on', page: 2 }, pages).status, 'not_found');
  // the quote's own page wins: found there, the next page is not looked at
  const both = [['repeat me'], ['repeat me']];
  assert.deepEqual(app.locateQuote({ text: 'repeat me', page: 2 }, both).pages, [2]);
  // the last page has no next page
  assert.equal(app.locateQuote({ text: 'three. More', page: 3 }, pages).status, 'not_found');
  // case-blind continuation only where there is no exact one
  const shouting = app.locateQuote({ text: 'THE START OF A PASSAGE', page: 1 }, pages);
  assert.deepEqual([shouting.scope, shouting.caseBlind, shouting.pages], ['continued', true, [1, 2]]);
  // only the pages read are needed: the quote's page and the next
  assert.equal(app.locateQuote({ text: 'passage that runs on', page: 2 }, [null, ['passage that runs on.'], null]).count, 1);
});

test('a quote with no page is looked for on every page, every occurrence marked, the pages named', () => {
  const pages = [['The cecum was reached.'], ['No match here.'], ['The cecum was reached again.', 'the cecum']];
  const all = app.locateQuote({ text: 'The cecum', page: null }, pages);
  assert.deepEqual([all.status, all.scope, all.count, all.pages, all.caseBlind], ['marked', 'document', 2, [1, 3], false]);
  assert.equal(app.markNote(all), 'These words appear 2 times, on pages 1 and 3. Each is marked.');
  const one = app.locateQuote({ text: 'No match here.' }, pages);
  assert.equal(app.markNote(one), 'Marked on page 2.');
  const none = app.locateQuote({ text: 'Absent words.', page: null }, pages);
  assert.equal(app.markNote(none), 'The exact words were not found in the searchable text of this document, so nothing is marked.');
  const across = app.locateQuote({ text: 'reached. No match', page: null }, pages);
  assert.deepEqual([across.count, across.pages], [1, [1, 2]]);
  assert.equal(app.markNote(across), 'Marked on pages 1 and 2.');
  const three = app.locateQuote({ text: 'e' }, [['e'], ['e'], ['e']]);
  assert.equal(app.markNote(three), 'These words appear 3 times, on pages 1, 2 and 3. Each is marked.');
});

test('the matcher refuses empty and odd input, and names a page the document does not have', () => {
  const pages = [['Some text.']];
  for (const quote of [null, undefined, {}, { text: '' }, { text: '   \n\t ' }, { text: 7 }, { text: null, page: 1 }]) {
    const result = app.locateQuote(quote, pages);
    assert.deepEqual([result.status, result.count, result.marks], ['empty', 0, {}], JSON.stringify(quote));
  }
  assert.equal(app.markNote(app.locateQuote({ text: ' ' }, pages)), 'This passage has no words to mark.');
  const beyond = app.locateQuote({ text: 'Some text.', page: 4 }, pages);
  assert.deepEqual([beyond.status, beyond.pageCount, beyond.marks], ['missing_page', 1, {}]);
  assert.equal(app.markNote(beyond), 'This passage names page 4, but the document has 1 page. Nothing is marked.');
  // a page that is not a positive whole number is no page: every page is searched
  for (const page of [0, -1, 1.5, '1', null]) assert.equal(app.locateQuote({ text: 'Some text.', page }, pages).scope, 'document', String(page));
  // no pages, unreadable pages and odd items
  assert.equal(app.locateQuote({ text: 'x', page: 1 }, null).status, 'missing_page');
  assert.equal(app.locateQuote({ text: 'x' }, []).status, 'not_found');
  assert.equal(app.locateQuote({ text: 'Some', page: 1 }, [['', null, 7, 'Some', { str: ' x' }]]).count, 1, 'an item the library gives ({str}) is read too');
  assert.deepEqual(app.locateQuote({ text: 'Some', page: 1 }, [['', null, 7, 'Some']]).marks, { 1: [{ item: 3, start: 0, end: 4, occurrence: 0 }] });
  assert.equal(app.locateQuote({ text: 'x', page: 1 }, [null]).status, 'not_found');
  assert.equal(app.markNote(null), 'The exact words were not found in the searchable text of this document, so nothing is marked.');
  // the frame's note says why the PDF is not drawn and marked in the page, then the quote's page - never what the frame
  // shows: the browser, the library, the document, or a stalled download
  assert.equal(app.frameNote(3, 'browser'), 'Marking needs a newer browser. The quote is on page 3.');
  assert.equal(app.frameNote(null, 'browser'), 'Marking needs a newer browser.');
  assert.equal(app.frameNote(3, 'library'), 'The marking tool did not work here, so nothing is marked. The quote is on page 3.');
  assert.equal(app.frameNote(null, 'library'), 'The marking tool did not work here, so nothing is marked.');
  assert.equal(app.frameNote(3, 'document'), 'This document cannot be drawn here, so nothing is marked. The quote is on page 3.');
  assert.equal(app.frameNote(null, 'document'), 'This document cannot be drawn here, so nothing is marked.');
  assert.equal(app.frameNote(2, 'slow'), 'The document took too long to load here, so nothing is marked. The quote is on page 2.');
  for (const odd of [undefined, '', 'toString', '__proto__', 7]) {
    assert.equal(app.frameNote(1, odd), 'This document cannot be drawn here, so nothing is marked. The quote is on page 1.', String(odd));
  }
  for (const reason of Object.keys(app.FRAME_REASONS)) assert.doesNotMatch(app.frameNote(4, reason), /is shown|Page 4/, reason);
});

test('a drawn page\'s marks split exactly the matched characters out of the text layer\'s spans, as text only', async () => {
  const strings = ['Cold forceps <b>biopsies</b>', 'were taken.', 'Other text.'];
  const made = [];
  const element = tag => {
    const node = { tag, children: [], dataset: {}, className: '', set textContent(value) { this.children = value === '' ? [] : [value]; },
      get textContent() { return this.children.map(child => (typeof child === 'string' ? child : child.textContent)).join(''); },
      append(...items) { this.children.push(...items); } };
    made.push(node);
    return node;
  };
  const saved = global.document;
  global.document = { createElement: element };
  try {
    const divs = strings.map(value => { const div = element(); div.textContent = value; return div; });
    const page = { number: 1, drawn: 'key', layer: { textDivs: divs, textContentItemsStr: strings }, painted: [] };
    const result = app.locateQuote({ text: 'forceps <b>biopsies</b> were', page: 1 }, [strings]);
    app.paintPage({ mark: { key: 'L1#0', result } }, page);
    const shape = div => div.children.map(child => (typeof child === 'string' ? child : [`${child.tag}.${child.className}`, child.dataset.occurrence, child.textContent]));
    assert.deepEqual(shape(divs[0]), ['Cold ', ['mark.pdf-mark', '0', 'forceps <b>biopsies</b>']], 'the markup-like text stays text');
    assert.deepEqual(shape(divs[1]), [['mark.pdf-mark', '0', 'were'], ' taken.']);
    assert.deepEqual(shape(divs[2]), ['Other text.'], 'an item with no mark is not touched');
    assert.deepEqual(page.painted, [0, 1]);
    // another quote: the spans painted before are restored first
    app.paintPage({ mark: { key: 'L2#0', result: app.locateQuote({ text: 'Other', page: 1 }, [strings]) } }, page);
    assert.deepEqual([shape(divs[0]), shape(divs[1]), shape(divs[2])], [[strings[0]], [strings[1]], [['mark.pdf-mark', '0', 'Other'], ' text.']]);
    // no mark (the document changed, or a new coding review): every span as it was
    app.paintPage({ mark: null }, page);
    assert.deepEqual(divs.map(shape), strings.map(value => [value]));
    // a page not drawn yet is left alone; it is painted when it is drawn
    app.paintPage({ mark: { key: 'L1#0', result } }, { ...page, layer: null });
    assert.deepEqual(divs.map(shape), strings.map(value => [value]));
  } finally {
    global.document = saved;
  }
});

test('nothing the page script declares shadows a property of window the page or the walk reads', () => {
  // app.js is a classic script: every function it declares at its top level becomes a property of window, so one named
  // innerWidth replaced window.innerWidth (the walk's viewport check reads it) while the viewer was being built
  const source = fs.readFileSync(BUNDLE, 'utf8');
  const declared = [...source.matchAll(/^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)].map(match => match[1] || match[2]);
  assert.ok(declared.includes('locateQuote') && declared.includes('viewerWidth'), 'the declarations are read');
  const windowProperties = ['innerWidth', 'innerHeight', 'outerWidth', 'outerHeight', 'scrollX', 'scrollY', 'pageXOffset', 'pageYOffset', 'screenX',
    'screenY', 'screenLeft', 'screenTop', 'devicePixelRatio', 'name', 'status', 'closed', 'length', 'opener', 'parent', 'top', 'frames', 'self',
    'window', 'document', 'location', 'history', 'navigator', 'origin', 'event', 'external', 'screen', 'visualViewport', 'performance', 'crypto',
    'open', 'close', 'stop', 'focus', 'blur', 'print', 'alert', 'confirm', 'prompt', 'find', 'scroll', 'scrollTo', 'scrollBy', 'moveTo', 'moveBy',
    'resizeTo', 'resizeBy', 'postMessage', 'fetch', 'getComputedStyle', 'getSelection', 'matchMedia', 'requestAnimationFrame',
    'cancelAnimationFrame', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'queueMicrotask', 'structuredClone', 'atob', 'btoa',
    'customElements', 'localStorage', 'sessionStorage', 'indexedDB', 'caches', 'menubar', 'toolbar', 'statusbar', 'scrollbars', 'personalbar',
    'locationbar', 'onload', 'onerror', 'onresize', 'onscroll', 'reportError', 'createImageBitmap', 'IntersectionObserver', 'ResizeObserver',
    'Worker', 'URL', 'Map', 'Promise'];
  assert.deepEqual(declared.filter(name => windowProperties.includes(name)), []);
});

test('the PDF library is named on the page as same-origin static modules, and nothing else is accepted', () => {
  const saved = global.document;
  try {
    const page = data => { global.document = { body: { dataset: data } }; return app.pdfAssets(); };
    const module = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.min.0123456789ab.mjs';
    const worker = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.worker.min.0123456789ab.mjs';
    assert.deepEqual(page({ pdfModule: module, pdfWorker: worker }), { module, worker });
    for (const bad of ['https://cdn.example/pdf.mjs', '//cdn.example/pdf.mjs', '/static/x.js', 'data:text/javascript,1', '/api/x.mjs', '/static/a b.mjs', 7, null]) {
      assert.deepEqual(page({ pdfModule: bad, pdfWorker: bad }), { module: '', worker: '' }, String(bad));
    }
    assert.deepEqual(page(undefined), { module: '', worker: '' });
  } finally {
    global.document = saved;
  }
  // the shell names the pinned copy; the page script names no address of its own
  const template = fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8');
  assert.match(template, /<body data-pdf-module="\{% static 'studio\/lib\/pdfjs-6\.5\.438\/legacy\/build\/pdf\.min\.mjs' %\}" data-pdf-worker="\{% static 'studio\/lib\/pdfjs-6\.5\.438\/legacy\/build\/pdf\.worker\.min\.mjs' %\}" data-specialty="\{\{ specialty \}\}" data-idle-seconds="\{\{ idle_seconds \}\}" data-cap-seconds="\{\{ cap_seconds \}\}" data-warning-seconds="\{\{ warning_seconds \}\}" data-session="\{\{ session \}\}" data-session-json="\{\{ session_json \}\}">/);
  // release 2's shell seams (lane F): the session the page shell carries (R2-17; empty until the view fills it) and the
  // entrance a page load's first view plays (R2-14), on <main> until the page's first route after load
  assert.match(template, /<main id="main" tabindex="-1" data-entrance>/);
  const bundle = fs.readFileSync(BUNDLE, 'utf8');
  assert.ok(!/pdf(\.worker)?\.min\.mjs/.test(bundle), 'the bundle reads the addresses from the page');
  // the image decoders and standard fonts are the package's own folders, two up from the legacy worker
  assert.match(bundle, /wasmUrl: new URL\('\.\.\/\.\.\/wasm\/', worker\)\.href, standardFontDataUrl: new URL\('\.\.\/\.\.\/standard_fonts\/', worker\)\.href,/);
  // the viewer starts the worker itself as a module worker, waits for it to say it is ready, then hands it to the library as
  // its port and the document to that (A4): a worker that cannot start is told apart from a document the library refuses
  assert.match(bundle, /const thread = new Worker\(address, \{ type: 'module' \}\);/);
  assert.match(bundle, /data\.sourceName === 'worker' && data\.targetName === 'main' && data\.action === 'ready'/);
  assert.match(bundle, /viewer\.worker = new library\.PDFWorker\(\{ port: thread, verbosity: library\.VerbosityLevel\.ERRORS \}\);/);
  assert.match(bundle, /\n\s+worker: viewer\.worker,\n/);
  // the viewer downloads the view address itself (A5) and the library is opened on its bytes, with no eval, no WebAssembly,
  // no XFA and the page drawn on the main thread
  assert.match(bundle, /const headers = \{ \[POLL_HEADER\]: '1' \};\n  if \(held\) headers\['If-None-Match'\] = `"\$\{held\.tag\}"`;\n/);
  assert.match(bundle, /response = await fetch\(view, \{ credentials: 'same-origin', cache: 'no-store', signal, headers \}\);/);
  assert.match(bundle, /library\.getDocument\(\{\n\s+data, isEvalSupported: false, enableXfa: false, useWasm: false,/);
  assert.ok(!/getDocument\(\{[^}]*\burl:/.test(bundle), 'the library is given no address to fetch');
  assert.match(bundle, /disableWorkerRendering: true/);
  assert.ok(!/AnnotationLayer|XfaLayer|enableScripting/.test(bundle), 'no annotation or XFA layer, no document scripting');
});

test('the overview, the documents list and How it works speak of the coding review and the second check', () => {
  const how = dom(app.howItWorksView()).text;
  assert.match(how, /A second check then reviews every code on its own/);
  assert.match(how, /Licensed CPT descriptors are not shown/);
  assert.match(how, /no accuracy percentage or payment guarantee is claimed/);
  assert.doesNotMatch(how, /independent checks|coding validation|document review|Four plain/);
  const overview = dom(app.overviewView()).text;
  assert.match(overview, /Answer any questions about the document, then approve or reject each code/);
  assert.doesNotMatch(dom(app.documentsView('queue')).text, /a date to choose|a detail to answer/);
  const about = fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8');
  assert.match(about, /Every code read from the whole document and checked a second time/);
  assert.doesNotMatch(about, /independent checks and coding validation/);
});

test('the page drops a question only where the server also calls it blank', () => {
  // tests/fixtures/blank-question-characters.json: every code point trim() removes (ECMAScript WhiteSpace and
  // LineTerminator); the server's one blank test calls every text made of them blank (tests/test_question_ids.py)
  const listed = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'blank-question-characters.json'), 'utf8'))
    .code_points.map(point => parseInt(point, 16));
  const removed = [];
  for (let point = 0; point <= 0x10FFFF; point += 1) {
    if ((point < 0xD800 || point > 0xDFFF) && String.fromCodePoint(point).trim() === '') removed.push(point);
  }
  assert.deepEqual(removed, listed);
  const kept = text => app.questionsOf({ questions: [{ id: 'q-1', text, codes: [], lines: [] }] }).length;
  for (const point of listed) {
    assert.equal(kept(String.fromCodePoint(point)), 0, `U+${point.toString(16).toUpperCase()} alone is dropped`);
  }
  assert.equal(kept(listed.map(point => String.fromCodePoint(point)).join('')), 0);
  // a question with any other text is shown: U+FEFF before a word, U+200B and U+180E, which trim() keeps
  for (const text of ['\uFEFFWas a biopsy taken?', '\u200B', '\u180E', '?']) assert.equal(kept(text), 1, JSON.stringify(text));
});

// --- release 1: sign-in state (B4, B5, B6), the team (C4), limits (C5) and the Word download (C6) -----------------------

const opsSession = require('../../studio/static/studio/ops_session.js');
const opsSecondFactor = require('../../studio/static/studio/ops_second_factor.js');

// withPage, with the browser's location protocol and its cookies as given, and the idle timer's own state put back after
function withSignedInPage(options, fn, { protocol = 'http:', cookie = 'cptstudio_csrf=token123', hash = '' } = {}) {
  const idleBefore = { ...app.idle };
  return withPage(options, async page => {
    global.document.cookie = cookie;
    Object.assign(global.location, { protocol, hash });
    try {
      await fn(page);
    } finally {
      clearTimeout(app.idle.timer);
      Object.assign(app.idle, idleBefore);
    }
  });
}

test('B6: the CSRF cookie is read by its __Host- name under HTTPS only, so a stale cookie of the old name never wins', async () => {
  assert.equal(app.csrfCookieName('https:'), '__Host-cptstudio_csrf');
  assert.equal(app.csrfCookieName('http:'), 'cptstudio_csrf');
  assert.equal(app.csrfCookieName(undefined), 'cptstudio_csrf');
  const header = async (protocol, cookie) => {
    let sent = null;
    await withSignedInPage({}, async ({ calls }) => {
      await app.api('/api/encounters/x/stop', { method: 'POST', json: {} });
      sent = calls.find(call => call.method === 'POST').headers['X-CSRFToken'];
    }, { protocol, cookie });
    return sent;
  };
  assert.equal(await header('https:', 'cptstudio_csrf=stale; __Host-cptstudio_csrf=fresh'), 'fresh');
  assert.equal(await header('https:', '__Host-cptstudio_csrf=fresh; cptstudio_csrf=stale'), 'fresh');
  assert.equal(await header('https:', 'cptstudio_csrf=stale'), '', 'the old name is never read under HTTPS');
  assert.equal(await header('http:', 'cptstudio_csrf=plain; __Host-cptstudio_csrf=other'), 'plain');
});

test('B5: the document poll and the refresh on return carry X-CPT-Poll; a read the member asked for does not', async () => {
  assert.equal(app.POLL_HEADER, 'X-CPT-Poll');
  const doc = fixture('encounter-checking.json');
  await withSignedInPage({ answers: [{ match: (method, url) => url === `/api/encounters/${doc.id}`, status: 200, body: clone(doc) },
    { match: (method, url) => url === `/api/encounters/${doc.id}`, status: 200, body: clone(doc) },
    { match: (method, url) => url === `/api/encounters/${doc.id}`, status: 200, body: clone(doc) }] }, async ({ calls }) => {
    Object.assign(app.state, { doc, route: { name: 'doc', id: doc.id }, routeSerial: 7 });
    await app.loadDocument(doc.id, 7, true, true);  // what schedulePoll's timer calls
    app.refreshIfWaiting();  // the return to the tab
    await settle(() => calls.filter(call => call.url === `/api/encounters/${doc.id}`).length >= 2);
    await app.refreshDocument();  // the read after the member's own act
    const reads = calls.filter(call => call.url === `/api/encounters/${doc.id}`).map(call => call.headers['X-CPT-Poll'] ?? null);
    assert.deepEqual(reads, ['1', '1', null]);
  });
  const bundle = fs.readFileSync(BUNDLE, 'utf8');
  assert.match(bundle, /state\.poll\.timer = setTimeout\(\(\) => loadDocument\(id, serial, true, true\), delay\);/);
  assert.match(bundle, /refreshDocument\(\{ poll: true \}\)/);
  // the viewer's download of the document it shows - after a poll's redraw too - is the page's own: a poll
  // (refutation r2, finding 18)
  const view = `/api/encounters/${UUID}/original?view=1`;
  await withSignedInPage({ answers: [{ match: (method, url) => url === view, status: 200, type: 'application/pdf', body: {} }] }, async ({ calls }) => {
    await app.downloadDocument(view, undefined, () => {}).catch(() => {});
    const download = calls.find(call => call.url === view);
    assert.equal(download.headers['X-CPT-Poll'], '1');
  });
});

test('B5: the shared idle timer warns before the end, then signs out; its sentences and its reasons', () => {
  const minute = 60000;
  assert.deepEqual(app.idleStep(0, 2 * minute, 1000), { step: 'wait', in: null, left: null });
  assert.deepEqual(app.idleStep(15 * minute, 2 * minute, 0), { step: 'wait', in: 13 * minute, left: 15 * minute });
  assert.deepEqual(app.idleStep(15 * minute, 2 * minute, 13 * minute), { step: 'warn', in: 2 * minute, left: 2 * minute });
  assert.deepEqual(app.idleStep(15 * minute, 2 * minute, 15 * minute), { step: 'out', in: 0, left: 0 });
  assert.equal(app.idleWarningText(2 * minute), 'You will be signed out in 2 minutes');
  assert.equal(app.idleWarningText(90000), 'You will be signed out in 2 minutes');
  assert.equal(app.idleWarningText(59000), 'You will be signed out in 1 minute');
  assert.equal(app.signedOutReason({ error: 'signed_out', reason: 'idle' }), 'idle');
  for (const data of [{ error: 'signed_out', reason: 'expired' }, { error: 'Sign in to continue.' }, null, { error: 'signed_out', reason: 'x' }]) {
    assert.equal(app.signedOutReason(data), 'expired', JSON.stringify(data));
  }
  assert.equal(app.loginAddress('idle', '#doc/abc'), '/login/?reason=idle&next=%2F%23doc%2Fabc');
  // the console's own timer is the same rule
  assert.deepEqual(opsSession.step(15 * minute, 2 * minute, 13 * minute), app.idleStep(15 * minute, 2 * minute, 13 * minute));
  assert.equal(opsSession.warningText(2 * minute), app.idleWarningText(2 * minute));
  assert.equal(opsSession.reasonOf({ error: 'signed_out', reason: 'idle' }), 'idle');
  assert.equal(opsSession.reasonOf({}), 'expired');
});

test('B5: at the limit the viewer closes, #main and every dialog are emptied, and the sign-out form is sent with its reason', async () => {
  const main = fakeElement({ innerHTML: '<section>Synthetic document text ZZ-TEXT-MARKER</section>' });
  const dialog = fakeElement({ open: true, children: ['x'], replaceChildren() { this.children = []; } });
  const form = fakeElement({ submitted: 0, submit() { this.submitted += 1; } });
  await withSignedInPage({ elements: { main, signoutForm: form } }, async () => {
    global.document.querySelectorAll = selector => (selector === 'dialog' ? [dialog] : []);
    Object.assign(app.idle, { deadline: Date.now() - 1, gone: false, warningMs: 120000 });
    app.scheduleIdle();
    assert.equal(main.innerHTML, '');
    assert.deepEqual([dialog.open, dialog.children], [false, []]);
    assert.equal(form.submitted, 1);
    assert.equal(form.attributes.action, '/logout/?reason=idle');
    assert.equal(app.idle.gone, true);
    app.scheduleIdle();
    assert.equal(form.submitted, 1, 'once only');
  });
});

test('B5: a tab in use keeps the session signed in while another tab sits idle, and a sign-out reaches every tab', async () => {
  const form = fakeElement({ submitted: 0, submit() { this.submitted += 1; } });
  await withSignedInPage({ elements: { signoutForm: form } }, async ({ calls }) => {
    const now = Date.now();
    // this tab of session 'tag-a' has sat idle: its own deadline is about to pass
    Object.assign(app.idle, { deadline: now + 50, idleEnd: now + 50, capEnd: 0, gone: false, warningMs: 120000, session: 'tag-a' });
    // the tab in use pinged: its later deadline reaches this one, which adopts it and does not sign out
    app.receiveSession({ type: 'deadline', deadline: now + 15 * 60000, warningMs: 120000, session: 'tag-a' });
    assert.equal(app.idle.deadline, now + 15 * 60000);
    await new Promise(resolve => setTimeout(resolve, 80));
    app.scheduleIdle();
    assert.equal(form.submitted, 0);
    assert.equal(app.idle.gone, false);
    // an earlier deadline never shortens a tab's time
    app.receiveSession({ type: 'deadline', deadline: now + 1000, session: 'tag-a' });
    assert.equal(app.idle.deadline, now + 15 * 60000);
    // a tab that signed out takes this one to the sign-in page, its screen cleared first
    app.receiveSession({ type: 'signed-out', reason: 'idle', session: 'tag-a' });
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/login/?reason=idle&next=%2F' }]);
    assert.equal(form.submitted, 0, 'the other tab already sent the sign-out');
  });
});

test('B5: the ping is sent on input at most once a minute, and its answer is the timer', async () => {
  await withSignedInPage({ answers: [{ match: (method, url) => url === '/session/activity', status: 200, body: { idle_seconds: 900, cap_seconds: 28000, warning_seconds: 120 } }] }, async ({ calls }) => {
    Object.assign(app.idle, { deadline: 0, lastPing: 0, gone: false, pinging: null });
    const before = Date.now();
    app.noteInput();
    await app.idle.pinging;
    const pings = calls.filter(call => call.url === '/session/activity');
    assert.equal(pings.length, 1);
    assert.equal(pings[0].method, 'POST');
    assert.equal(pings[0].headers['X-CPT-Poll'], undefined, 'the ping is activity');
    assert.ok(app.idle.deadline >= before + 900000 && app.idle.deadline <= Date.now() + 900000);
    assert.equal(app.idle.warningMs, 120000);
    app.noteInput();
    app.noteInput();
    assert.equal(calls.filter(call => call.url === '/session/activity').length, 1, 'not again within the minute');
  });
});

test('B5: a 401 clears the screen before the sign-in page, with the reason the server gave', async () => {
  const main = fakeElement({ innerHTML: '<p>ZZ-TEXT-MARKER</p>' });
  await withSignedInPage({ elements: { main }, answers: [{ match: () => true, status: 401, body: { error: 'signed_out', reason: 'idle' } }] }, async ({ calls }) => {
    await assert.rejects(app.api('/api/encounters'), { status: 401 });
    assert.equal(main.innerHTML, '');
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/login/?reason=idle&next=%2F%23doc%2Fx' }]);
  }, { hash: '#doc/x' });
});

test('B4: a forced password change answers 403 and the page goes to the account page', async () => {
  await withSignedInPage({ answers: [{ match: () => true, status: 403, body: { error: 'password_change_required' } }] }, async ({ calls }) => {
    await assert.rejects(app.api('/api/encounters'), { status: 403 });
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/account/?required=1' }]);
  });
  // a code the server answers for the page is never shown as a sentence
  assert.equal(app.errorText(403, { error: 'password_change_required' }), app.errorText(403, null));
  assert.equal(app.errorText(409, { error: 'some_code' }), app.errorText(409, null));
});

test('C5: a limit is said in plain words, with the wait the server gives', () => {
  assert.equal(app.errorText(429, { error: 'rate_limited', retry_after: 600 }), 'Too many requests in a short time. Wait 10 minutes and try again.');
  assert.equal(app.errorText(429, { error: 'rate_limited', retry_after: 61 }), 'Too many requests in a short time. Wait 2 minutes and try again.');
  assert.equal(app.errorText(429, { error: 'rate_limited', retry_after: 30 }), 'Too many requests in a short time. Wait a minute and try again.');
  assert.equal(app.errorText(429, { error: 'rate_limited' }), 'Too many requests in a short time. Wait a moment and try again.');
  assert.equal(app.errorText(429, null), 'Too many requests in a short time. Wait a moment and try again.');
  assert.equal(app.errorText(429, { error: 'Wait before making another report.' }), 'Wait before making another report.');
  for (const status of [429]) assert.doesNotMatch(app.errorText(status, { error: 'rate_limited', retry_after: 9 }), /rate_limited|\d{3}/);
});

test('C4: the owners\' Team panel lists the practice and turns a person off, after asking, or on', async () => {
  const me = '6f2c1d8e-4b3a-4c5d-9e8f-0a1b2c3d4e5f';
  const them = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
  const bot = '1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d';
  const data = { members: [
    { id: me, label: 'Dr Owner', username: 'owner', role: 'owner', active: true, actor_kind: 'human', last_sign_in: '2026-11-24T08:00:00Z', password_change_required: false },
    { id: them, label: 'Dr Reviewer', username: 'reviewer', role: 'reviewer', active: true, actor_kind: 'human', last_sign_in: null, password_change_required: true },
    { id: bot, label: '<b>Reviewbot</b>', username: 'review-agent', role: 'reviewer', active: false, actor_kind: 'agent', last_sign_in: null, password_change_required: false },
    { id: 'not-an-id', label: 'Dropped', role: 'viewer', active: true }, null] };
  assert.deepEqual(app.teamMembers(data).map(member => member.id), [me, them, bot]);
  const page = dom(app.teamList(app.teamMembers(data), me));
  const rows = page.all('.team-row');
  assert.equal(rows.length, 3);
  assert.equal(rows[0].one('button'), null, 'nobody turns themself off');
  assert.match(rows[0].text, /Dr Owner.*Owner · Person · owner/);
  assert.match(rows[0].text, /24 Nov 2026, 08:00 UTC/);
  assert.deepEqual([rows[1].one('button').attr('data-member-access'), rows[1].one('button').attr('data-member')], ['off', them]);
  assert.match(rows[1].text, /Must choose a password/);
  assert.match(rows[1].text, /Never signed in/);
  assert.deepEqual([rows[2].one('button').attr('data-member-access'), rows[2].one('button').text], ['on', 'Turn on']);
  assert.match(rows[2].text, /Automated account/);
  assert.ok(!app.teamList(app.teamMembers(data), me).includes('<b>'), 'every value is escaped');
  assert.match(dom(app.teamView()).text, /Turning a person off ends their access to this practice only/);
  await withSignedInPage({ answers: [{ match: (method, url) => method === 'GET' && url === '/api/members', status: 200, body: data },
    { match: (method, url) => method === 'POST' && url === `/api/members/${them}/access`, status: 200, body: {} },
    { match: (method, url) => method === 'GET' && url === '/api/members', status: 200, body: data }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session: { ...fixture('session.json'), user: { ...fixture('session.json').user, id: me } }, route: { name: 'team' }, routeSerial: 3 });
    await app.showTeam(3);
    assert.match(element('#teamList').innerHTML, /Dr Reviewer/);
    // turning off asks first; Cancel sends nothing, Continue posts {active: false} and reads the team again
    click('[data-member-access]', { memberAccess: 'off', member: them, label: 'Dr Reviewer' });
    assert.equal(element('#confirmDialog').open, true);
    assert.match(element('#confirmTitle').textContent, /Turn off Dr Reviewer's access\?/);
    assert.deepEqual(posted(calls), []);
    app.confirmChosen();
    await settle(() => calls.filter(call => call.url === '/api/members').length === 2);
    assert.deepEqual(posted(calls), [{ url: `/api/members/${them}/access`, body: { active: false } }]);
    assert.equal(element('#confirmDialog').open, false);
  });
  await withSignedInPage({ answers: [{ match: () => true, status: 403, body: { error: 'Only an owner can do that.' } }] }, async ({ element }) => {
    Object.assign(app.state, { route: { name: 'team' }, routeSerial: 4 });
    await app.showTeam(4);
    assert.match(element('#teamList').innerHTML, /Only the practice&#x27;s owners see the team\./);
  });
  assert.equal(app.ROUTE_TITLES.team, 'Team');
});

test('C4: the session shows the Team link to an owner only', async () => {
  await withSignedInPage({}, async ({ element }) => {
    for (const [value, hidden] of [[true, false], [false, true], [undefined, true], ['yes', true], [1, true]]) {
      app.renderSession({ ...fixture('session.json'), can_manage_team: value });
      assert.equal(element('#teamNav').hidden, hidden, String(value));
    }
  });
});

test('C6: the Word file is downloaded only after its warning, as ?format=original', async () => {
  const address = `/api/encounters/${UUID}/original?format=original`;
  await withSignedInPage({}, async ({ calls, element }) => {
    click('[data-word-original]', { wordOriginal: address });
    assert.equal(element('#confirmDialog').open, true);
    assert.equal(element('#confirmText').textContent, app.WORD_ORIGINAL_TEXT);
    assert.equal(app.WORD_ORIGINAL_TEXT, 'The original Word file can contain links and embedded content. Download it anyway?');
    assert.deepEqual(calls.filter(call => call.download), [], 'nothing before the member chooses');
    app.confirmChosen();
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(calls.filter(call => call.url === address).map(call => call.method ?? 'GET'), ['GET'], 'fetched first');
    assert.deepEqual(calls.filter(call => call.download), [{ download: address, filename: 'download' }]);
    // an address of any other shape is never downloaded
    for (const bad of ['https://evil.test/x?format=original', `/api/encounters/${UUID}/original`, '/api/reports/x/download?format=original']) {
      element('#confirmDialog').open = false;
      app.askWordOriginal(bad);
      assert.equal(element('#confirmDialog').open, false, bad);
    }
  });
});

test('B2: the console\'s key script converts the options to bytes and the answer back to base64url', () => {
  const bytes = Uint8Array.from([0, 1, 2, 250, 251, 252, 253, 254, 255]);
  const text = opsSecondFactor.toText(bytes.buffer);
  assert.equal(text, Buffer.from(bytes).toString('base64url'));
  assert.deepEqual([...opsSecondFactor.toBytes(text)], [...bytes]);
  const request = opsSecondFactor.requestOptions({ challenge: text, rpId: 'admin.quillmd.com', allowCredentials: [{ id: 'AAEC', type: 'public-key' }] });
  assert.deepEqual([[...request.challenge], [...request.allowCredentials[0].id], request.rpId], [[...bytes], [0, 1, 2], 'admin.quillmd.com']);
  const creation = opsSecondFactor.creationOptions({ challenge: text, user: { id: 'AAEC', name: 'op' }, excludeCredentials: [] });
  assert.deepEqual([[...creation.user.id], creation.user.name], [[0, 1, 2], 'op']);
  const answered = opsSecondFactor.answer({ id: 'AAEC', rawId: Uint8Array.from([0, 1, 2]).buffer, type: 'public-key', authenticatorAttachment: 'cross-platform',
    response: { clientDataJSON: Uint8Array.from([123, 125]).buffer, authenticatorData: Uint8Array.from([1]).buffer, signature: Uint8Array.from([2]).buffer, userHandle: null } });
  assert.deepEqual(answered, { id: 'AAEC', rawId: 'AAEC', type: 'public-key', authenticatorAttachment: 'cross-platform',
    response: { clientDataJSON: 'e30', authenticatorData: 'AQ', signature: 'Ag', userHandle: null } });
  const registered = opsSecondFactor.answer({ id: 'AAEC', rawId: Uint8Array.from([0, 1, 2]).buffer, type: 'public-key',
    response: { clientDataJSON: Uint8Array.from([123, 125]).buffer, attestationObject: Uint8Array.from([3]).buffer, getTransports: () => ['usb'] } });
  assert.deepEqual(registered.response, { clientDataJSON: 'e30', attestationObject: 'Aw', transports: ['usb'] });
  for (const file of ['ops_session.js', 'ops_second_factor.js', 'session_news.js']) {
    const source = fs.readFileSync(path.join(ROOT, 'studio', 'static', 'studio', file), 'utf8');
    assert.ok(!/eval\(|new Function|innerHTML|document\.write/.test(source), file);
  }
});

// --- refutation r2: the timer armed at load (finding 13), the session's tabs (14), the cap (16) --------------------------

// withSignedInPage, with a page that can run startIdleWatch: the body's data-* as the server writes them, document and
// window listeners that do nothing, and no BroadcastChannel (the tabs' channel is the test's own where it needs one).
function withTimerPage(options, dataset, fn, extra) {
  const savedChannel = globalThis.BroadcastChannel;
  return withSignedInPage(options, async page => {
    Object.assign(global.document, { addEventListener() {}, body: { appendChild() {}, dataset } });
    global.window.addEventListener = () => {};
    globalThis.BroadcastChannel = undefined;
    Object.assign(app.idle, { deadline: 0, idleEnd: 0, capEnd: 0, warningMs: 120000, lastPing: 0, pinging: null, checking: null,
      channel: null, gone: false, started: false, session: '', capClosed: 0, returnFocus: null });
    try {
      await fn(page);
    } finally {
      globalThis.BroadcastChannel = savedChannel;
    }
  }, extra);
}

const PAGE_SECONDS = { idleSeconds: '900', capSeconds: '28800', warningSeconds: '120', session: 'tag-a' };

test('B5: the timer is armed from the page\'s own seconds at load, and a first ping that fails leaves it armed', async () => {
  const unavailable = { match: (method, url) => url === '/session/activity', status: 502, type: 'text/html', body: '<p>temporarily unavailable</p>' };
  await withTimerPage({ answers: [unavailable] }, PAGE_SECONDS, async ({ calls }) => {
    const before = Date.now();
    app.startIdleWatch();
    await app.idle.pinging;
    assert.equal(calls.filter(call => call.url === '/session/activity').length, 1);
    assert.ok(app.idle.deadline >= before + 900000 && app.idle.deadline <= Date.now() + 900000, 'armed from the page');
    assert.equal(app.idle.session, 'tag-a');
    // the failed ping is tried again on input, after RETRY_MS rather than a minute
    app.noteInput();
    assert.equal(calls.filter(call => call.url === '/session/activity').length, 1, 'not at once');
    app.idle.lastPing -= app.RETRY_MS;
    app.noteInput();
    await app.idle.pinging;
    assert.equal(calls.filter(call => call.url === '/session/activity').length, 2);
  });
  // a page with no seconds at all is armed at the doctors' limit: never unarmed
  await withTimerPage({ answers: [unavailable] }, {}, async () => {
    const before = Date.now();
    app.startIdleWatch();
    await app.idle.pinging;
    assert.ok(app.idle.deadline >= before + app.DEFAULT_IDLE_SECONDS * 1000);
  });
  assert.deepEqual(app.pageSession({ idleSeconds: '840', capSeconds: '', warningSeconds: 'x', session: 's' }),
    { idle: 840, cap: null, warning: null, session: 's' });
});

test('B5: the deadline is the earlier of the idle end and the cap, whose warning says so, and the page signs out as expired', async () => {
  const main = fakeElement({ innerHTML: '<section>ZZ-TEXT-MARKER</section>' });
  const form = fakeElement({ submitted: 0, submit() { this.submitted += 1; } });
  const dialog = fakeElement();
  await withTimerPage({ elements: { main, signoutForm: form, idleDialog: dialog } }, { ...PAGE_SECONDS, capSeconds: '120' }, async ({ element }) => {
    const now = Date.now();
    app.armFromPage(now);
    assert.equal(app.idle.deadline, now + 120000, 'the cap, two minutes away, comes before the idle end');
    assert.equal(app.capFirst(), true);
    app.scheduleIdle();  // inside the warning's lead
    assert.equal(dialog.open, true);
    assert.equal(element('#idleTitle').textContent, 'Your session ends in 2 minutes');
    assert.equal(element('#idleText').textContent, app.CAP_TEXT);
    assert.deepEqual([element('#idleStay').hidden, element('#idleClose').hidden], [true, false]);
    // a ping cannot move the cap: its answer brings it only closer
    app.applySessionAnswer({ idle_seconds: 900, cap_seconds: 200, warning_seconds: 120, session: 'tag-a' }, false);
    assert.equal(app.idle.deadline, now + 120000);
    app.applySessionAnswer({ idle_seconds: 900, cap_seconds: 60, warning_seconds: 120, session: 'tag-a' }, false);
    assert.ok(app.idle.deadline <= Date.now() + 60000);
    // read and closed, it stays closed until the end
    app.closeCapWarning();
    assert.equal(dialog.open, false);
    app.scheduleIdle();
    assert.equal(dialog.open, false);
    // at the cap the screen is cleared and the page signs out as expired
    Object.assign(app.idle, { deadline: Date.now() - 1, capEnd: Date.now() - 1 });
    app.scheduleIdle();
    assert.equal(main.innerHTML, '');
    assert.equal(form.submitted, 1);
    assert.equal(form.attributes.action, '/logout/?reason=expired');
  });
  // the idle warning keeps its own words and button
  await withTimerPage({ elements: { idleDialog: fakeElement() } }, PAGE_SECONDS, async ({ element }) => {
    app.armFromPage(Date.now() - (900 - 60) * 1000);  // a minute left of the idle time
    app.scheduleIdle();
    assert.equal(element('#idleTitle').textContent, 'You will be signed out in 1 minute');
    assert.equal(element('#idleText').textContent, app.IDLE_TEXT);
    assert.deepEqual([element('#idleStay').hidden, element('#idleClose').hidden], [false, true]);
  });
  const template = fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8');
  assert.ok(template.includes(`<p class="dialog-copy" id="idleText">${app.IDLE_TEXT}</p>`), 'the page script and the page say the same');
  assert.match(template, /<button type="button" class="button secondary" id="idleClose" data-action="idle-close" hidden>Close<\/button>/);
});

test('B5: a 401 is told to every tab of the session, and another session\'s news is never adopted', async () => {
  const posted = [];
  const channel = { postMessage(data) { posted.push(data); } };
  // a 401 in this tab: the session's other tabs are told, with its tag
  await withTimerPage({ answers: [{ match: () => true, status: 401, body: { error: 'signed_out', reason: 'expired' } }] }, PAGE_SECONDS, async ({ calls }) => {
    app.armFromPage();
    app.idle.channel = channel;
    await assert.rejects(app.api('/api/encounters'), { status: 401 });
    assert.deepEqual(posted.map(message => [message.type, message.reason, message.session]), [['signed-out', 'expired', 'tag-a']]);
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/login/?reason=expired&next=%2F' }]);
  });
  // news of another session: never adopted; the tab asks the server which session it is in, without counting as activity
  const theirs = { match: (method, url) => url === '/session/activity', status: 200, body: { idle_seconds: 900, cap_seconds: 28800, warning_seconds: 120, session: 'tag-b' } };
  await withTimerPage({ answers: [theirs] }, PAGE_SECONDS, async ({ calls }) => {
    const now = Date.now();
    app.armFromPage(now);
    const own = app.idle.deadline;
    app.receiveSession({ type: 'deadline', deadline: now + 3 * 3600000, cap: now + 8 * 3600000, warningMs: 120000, session: 'tag-b' });
    assert.equal(app.idle.deadline, own, 'another session\'s deadline is never this tab\'s');
    await app.idle.checking;
    const check = calls.find(call => call.url === '/session/activity');
    assert.equal(check.headers['X-CPT-Poll'], '1', 'the question is no activity');
    // the browser now holds the other session: this tab leaves, its screen cleared
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/login/?reason=expired&next=%2F' }]);
    assert.equal(app.idle.gone, true);
  });
  // a sign-out, or a message naming no session, is checked the same way; the tab whose session it still is stays
  const mine = { match: (method, url) => url === '/session/activity', status: 200, body: { idle_seconds: 600, cap_seconds: 28000, warning_seconds: 120, session: 'tag-a' } };
  await withTimerPage({ answers: [mine, { ...mine }] }, PAGE_SECONDS, async ({ calls }) => {
    app.armFromPage();
    app.receiveSession({ type: 'signed-out', reason: 'idle', session: 'tag-b' });
    await app.idle.checking;
    app.receiveSession({ type: 'deadline', deadline: Date.now() + 3600000 });
    await app.idle.checking;
    assert.equal(calls.filter(call => call.url === '/session/activity' && call.headers['X-CPT-Poll'] === '1').length, 2);
    assert.deepEqual(calls.filter(call => call.assign), []);
    assert.equal(app.idle.gone, false);
  });
  // the ping's own answer naming another session takes this tab out too
  await withTimerPage({ answers: [theirs] }, PAGE_SECONDS, async ({ calls }) => {
    app.armFromPage();
    await app.sendActivity();
    assert.deepEqual(calls.filter(call => call.assign), [{ assign: '/login/?reason=expired&next=%2F' }]);
  });
});

// --- the console's timer (ops_session.js), run in a context of its own per tab: a fake page, clock, fetch and channel ---

const OPS_SESSION = path.join(ROOT, 'studio', 'static', 'studio', 'ops_session.js');

function consoleTab({ dataset = {}, bus, answers, clock, name = 'tab' }) {
  const calls = [];
  const timers = clock.timers;
  const found = (node, id) => (node.id === id ? node : node.children.map(child => (typeof child === 'object' ? found(child, id) : null)).find(Boolean) || null);
  const element = tag => ({
    tag, id: '', className: '', hidden: false, open: false, textContent: '', attributes: {}, children: [], on: {},
    setAttribute(key, value) { this.attributes[key] = String(value); }, append(...items) { this.children.push(...items); },
    addEventListener(type, listener) { this.on[type] = listener; }, querySelector(selector) { return found(this, selector.slice(1)); },
    showModal() { this.open = true; }, close() { this.open = false; }, focus() {},
  });
  const dialogs = [];
  const form = { attributes: { action: '/logout/' }, submitted: 0, setAttribute(key, value) { this.attributes[key] = value; },
    submit() { this.submitted += 1; }, addEventListener() {}, querySelector: () => ({ value: 'form-token' }) };
  const main = { children: ['ZZ-PHI-MARKER'], replaceChildren() { this.children = []; } };
  const document = {
    body: { dataset, append(child) { if (child.tag === 'dialog') dialogs.push(child); } }, hidden: false, activeElement: null,
    querySelector: selector => (selector === 'form[action="/logout/"]' ? form : null),
    getElementById: id => (id === 'main' ? main : null), querySelectorAll: () => dialogs, createElement: element,
    addEventListener(type, listener) { (listeners[type] ||= []).push(listener); },
  };
  const listeners = {};
  class Channel {
    constructor() { bus.push(this); }
    postMessage(data) { for (const other of bus) if (other !== this && other.onmessage) other.onmessage({ data: JSON.parse(JSON.stringify(data)) }); }
  }
  const sandbox = {
    document, console, BroadcastChannel: Channel, FormData: class { append() {} },
    window: { location: { assign: url => calls.push({ assign: url }) }, addEventListener() {}, localStorage: undefined },
    Date: class extends Date { static now() { return clock.now; } },
    setTimeout: (run, ms) => { const timer = { at: clock.now + ms, run }; timers.push(timer); return timer; },
    clearTimeout: timer => { const index = timers.indexOf(timer); if (index >= 0) timers.splice(index, 1); },
    fetch: async (url, init) => {
      calls.push({ url, method: init.method, poll: init.headers['X-CPT-Poll'] || null, tab: name });
      const answer = answers.shift() || { status: 200, body: { idle_seconds: 600, cap_seconds: 28800, warning_seconds: 120, session: dataset.session } };
      return { status: answer.status, ok: answer.status >= 200 && answer.status < 300, json: async () => (answer.text ? JSON.parse(answer.text) : answer.body) };
    },
  };
  vm.runInNewContext(fs.readFileSync(OPS_SESSION, 'utf8'), sandbox);
  const press = () => (listeners.keydown || []).forEach(listener => listener({ type: 'keydown' }));
  return { calls, form, main, dialogs, press };
}

function consoleClock(start = Date.parse('2026-11-24T12:00:00Z')) {
  const clock = { now: start, timers: [] };
  clock.advance = async ms => {
    const end = clock.now + ms;
    for (;;) {
      await new Promise(resolve => setImmediate(resolve));
      const due = clock.timers.filter(timer => timer.at <= end).sort((a, b) => a.at - b.at)[0];
      if (!due) break;
      clock.timers.splice(clock.timers.indexOf(due), 1);
      clock.now = Math.max(clock.now, due.at);
      due.run();
    }
    clock.now = end;
    await new Promise(resolve => setImmediate(resolve));
  };
  return clock;
}

const CONSOLE_SECONDS = { idleSeconds: '600', capSeconds: '28800', warningSeconds: '120', session: 'op-a' };

test('B5: the console\'s timer is armed at load, and a first ping answered 502 still clears the screen at the limit', async () => {
  const clock = consoleClock();
  const tab = consoleTab({ dataset: CONSOLE_SECONDS, bus: [], answers: [{ status: 502, text: 'null' }], clock });
  await clock.advance(1000);
  assert.equal(tab.calls.filter(call => call.url === '/session/activity').length, 1);
  await clock.advance(478 * 1000);  // 479 s: no warning yet
  assert.equal(tab.dialogs.filter(dialog => dialog.open).length, 0);
  await clock.advance(2 * 1000);  // inside the two minutes
  assert.equal(tab.dialogs[0]?.open, true);
  assert.equal(tab.dialogs[0].querySelector('#idleTitle').textContent, 'You will be signed out in 2 minutes');
  await clock.advance(120 * 1000);  // 601 s
  assert.deepEqual([tab.form.submitted, tab.form.attributes.action, tab.main.children], [1, '/logout/?reason=idle', []]);
});

test('B5: a 401 in one console tab clears every tab of its session, and never adopts another session\'s deadline', async () => {
  const clock = consoleClock();
  const bus = [];
  const answersA = [];
  const a = consoleTab({ dataset: CONSOLE_SECONDS, bus, answers: answersA, clock, name: 'A' });
  const b = consoleTab({ dataset: CONSOLE_SECONDS, bus, answers: [], clock, name: 'B' });
  const otherAnswers = [];
  const other = consoleTab({ dataset: { ...CONSOLE_SECONDS, session: 'op-b' }, bus, answers: otherAnswers, clock, name: 'other' });
  await clock.advance(61 * 1000);
  const checks = other.calls.length;
  // the server ends op-a's session; a key pressed in tab A, a minute after its last ping, meets the 401
  answersA.push({ status: 401, body: { error: 'signed_out', reason: 'expired' } });
  otherAnswers.push({ status: 200, body: { idle_seconds: 600, cap_seconds: 28800, warning_seconds: 120, session: 'op-b' } });
  a.press();
  await clock.advance(10);
  assert.deepEqual(a.calls.filter(call => call.assign), [{ assign: '/login/?reason=expired' }]);
  assert.deepEqual(b.calls.filter(call => call.assign), [{ assign: '/login/?reason=expired' }], 'tab B of the same session leaves');
  assert.deepEqual(b.main.children, [], 'and its screen is cleared');
  // the tab of another session only asks which session it is in (a ping marked a poll), and stays
  const asked = other.calls.slice(checks).filter(call => call.url === '/session/activity');
  assert.deepEqual(asked.map(call => call.poll), ['1']);
  assert.deepEqual(other.calls.filter(call => call.assign), []);
  assert.deepEqual(other.main.children, ['ZZ-PHI-MARKER']);
});

test('B5: the console\'s deadline is the earlier of the idle end and the cap, which it signs out at as expired', async () => {
  const clock = consoleClock();
  const answers = [{ status: 200, body: { idle_seconds: 600, cap_seconds: 120, warning_seconds: 120, session: 'op-a' } }];
  const tab = consoleTab({ dataset: { ...CONSOLE_SECONDS, capSeconds: '120' }, bus: [], answers, clock });
  await clock.advance(1000);
  assert.equal(tab.dialogs[0]?.open, true, 'the cap is two minutes away: its warning at once');
  assert.equal(tab.dialogs[0].querySelector('#idleTitle').textContent, 'Your session ends in 2 minutes');
  assert.deepEqual([tab.dialogs[0].querySelector('#idleStay').hidden, tab.dialogs[0].querySelector('#idleClose').hidden], [true, false]);
  tab.press();  // activity: the idle end moves, the cap does not
  await clock.advance(120 * 1000);
  assert.deepEqual([tab.form.submitted, tab.form.attributes.action, tab.main.children], [1, '/logout/?reason=expired', []]);
  assert.equal(opsSession.capWarningText(60000), 'Your session ends in 1 minute');
  assert.deepEqual(opsSession.pageSession({ idleSeconds: '600', session: 'x' }), { idle: 600, cap: null, warning: null, session: 'x' });
});

test('B5: input inside the viewer\'s frame is the member\'s input, and the focus goes back into the frame when the warning closes', async () => {
  const answers = [{ match: (method, url) => url === '/session/activity', status: 200, body: { idle_seconds: 900, cap_seconds: 28800, warning_seconds: 120, session: 'tag-a' } }];
  await withTimerPage({ answers }, PAGE_SECONDS, async ({ calls }) => {
    // each document a frame loads gets the page's listeners (refutation r2, finding 15)
    const heard = {};
    const framed = { addEventListener(type, listener, options) { heard[type] = { listener, options }; } };
    const frame = { tagName: 'IFRAME', contentDocument: framed, dataset: {} };
    app.noteFrameLoad({ target: frame });
    assert.deepEqual(Object.keys(heard).sort(), [...app.ACTIVITY_INPUTS].sort());
    assert.deepEqual(heard.wheel.options, { capture: true, passive: true });
    Object.assign(app.idle, { lastPing: 0, pinging: null, session: 'tag-a' });
    heard.wheel.listener({ type: 'wheel' });  // the member scrolls the framed text
    await app.idle.pinging;
    assert.equal(calls.filter(call => call.url === '/session/activity' && call.method === 'POST').length, 1);
    // a frame this page cannot read gives nothing to listen to, and breaks nothing
    app.noteFrameLoad({ target: { tagName: 'IFRAME', get contentDocument() { throw new Error('cross-origin'); }, dataset: {} } });
    // the warning takes the focus from the frame, and gives it back when it closes
    const focused = [];
    const viewer = { tagName: 'IFRAME', isConnected: true, focus() { focused.push('frame'); }, contentWindow: { focus() { focused.push('frame document'); } } };
    global.document.activeElement = viewer;
    const dialog = fakeElement();
    const element = global.document.querySelector;
    global.document.querySelector = selector => (selector === '#idleDialog' ? dialog : element(selector));
    app.showIdleWarning(60000);
    assert.equal(dialog.open, true);
    app.hideIdleWarning();
    assert.equal(dialog.open, false);
    assert.deepEqual(focused, ['frame', 'frame document']);
  });
});

// --- refutation r2, finding 21: a refused download is seen and said ---------------------------------------------------

test('A download refused at the front door is said in plain words, and the export never says the file is downloading', async () => {
  const session = fixture('session.json');
  const reviewed = fixture('encounter-reviewed.json');
  const address = `/api/encounters/${reviewed.id}`;
  const report = { id: 'f6100000-0000-4000-8000-0000000000c1', kind: 'approved', fmt: 'pdf', filename: 'CPT-Studio-approved-r2-20261124T120000.pdf',
    generated_at: '2026-11-24T12:00:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000c1/download', current: true };
  const limited = { match: (method, url) => url === report.download_url, status: 429, type: 'text/html', body: '<html>429 Too Many Requests</html>', headers: { 'Retry-After': '120' } };
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: report }, limited] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 41, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => element('#exportError').textContent !== '');
    assert.equal(element('#exportError').textContent, 'Too many requests in a short time. Wait 2 minutes and try again.');
    assert.equal(element('#exportError').hidden, false);
    assert.deepEqual(calls.filter(call => call.download), [], 'nothing was handed to the browser\'s downloads');
    assert.equal(calls.filter(call => call.url === report.download_url).length, 1, 'fetched first');
    assert.notEqual(element('#exportStatus').textContent, app.readyText('pdf', report.filename));
    assert.doesNotMatch(element('#exportStatus').textContent, /Downloading/);
  });
  // the same file, answered: saved from its own bytes, and the status says it is downloading
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: report }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 42, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'pdf' });
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(calls.filter(call => call.download), [{ download: report.download_url, filename: report.filename }]);
    assert.equal(element('#exportStatus').textContent, app.readyText('pdf', report.filename));
    assert.equal(element('#exportError').hidden ?? true, true);
  });
});

test('A saved file is the answer\'s own bytes, under a page address the page lets go of; a link is fetched first too', async () => {
  const original = `/api/encounters/${UUID}/original`;
  await withPage({ answers: [{ match: (method, url) => url === original, status: 200, type: 'application/pdf', body: {}, headers: { 'Content-Disposition': 'attachment; filename="synthetic-original.pdf"' } }] }, async ({ calls }) => {
    URL.createObjectURL = blob => {
      assert.ok(blob instanceof Blob, 'the bytes are a Blob');
      return 'blob:https://cpt.test/0b6f6a2e';
    };
    await app.saveDownload(original, '');
    assert.deepEqual(calls.filter(call => call.download), [{ download: 'blob:https://cpt.test/0b6f6a2e', filename: 'synthetic-original.pdf' }]);
    assert.ok(app.state.objectUrls.has('blob:https://cpt.test/0b6f6a2e'), 'let go of when the page leaves');
  });
  // a link of the page - an earlier export, the original - is fetched first; a refusal is said
  const refused = { match: (method, url) => url === original, status: 404, body: { error: 'This document is not available.' } };
  await withPage({ answers: [refused] }, async ({ calls, element }) => {
    let prevented = false;
    const link = fakeElement({ getAttribute: name => ({ href: original, download: '' }[name] ?? null), closest: () => null });
    app.onClick({ target: { closest: wanted => (wanted === 'a[download]' ? link : null) }, preventDefault() { prevented = true; } });
    assert.equal(prevented, true, 'the browser does not download it unread');
    await settle(() => element('#toast').textContent !== '');
    assert.equal(element('#toast').textContent, 'This document is not available.');
    assert.deepEqual(calls.filter(call => call.download), []);
  });
  assert.equal(app.savedName(response({ headers: { 'Content-Disposition': "attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.pdf" } })), 'résumé.pdf');
  assert.equal(app.savedName(response({})), 'download');
});

test('The framed viewer of a PDF says when the server refused the document it was to show', () => {
  const marks = [];
  const note = fakeElement();
  const saved = global.document;
  try {
    global.document = { querySelector: selector => (selector === '#viewerMark' ? note : null) };
    const framed = status => ({ tagName: 'IFRAME', dataset: {}, contentDocument: null,
      contentWindow: { performance: { getEntriesByType: () => [{ responseStatus: status }] } } });
    const limited = framed(429);
    app.noteRefusedFrame(limited);
    marks.push(note.textContent);
    assert.equal(limited.dataset.refused, '429');
    note.textContent = '';
    app.noteRefusedFrame(framed(503));
    marks.push(note.textContent);
    note.textContent = '';
    app.noteRefusedFrame(framed(200));
    marks.push(note.textContent);
    assert.deepEqual(marks, [app.FRAME_LIMIT_TEXT, app.FRAME_REFUSED_TEXT, ''], 'an answer of 200 says nothing');
    assert.equal(note.classList.contains('is-missing'), true, 'said as the viewer says what it could not do');
    // R2-18: a 401 (the session ended) or a 403 (its password must change) at the frame's load, read here, is an end -
    // the kept copies overwritten and dropped, the hints gone; any other refusal keeps them. The site's own refusals
    // forbid framing, so a browser never lets them be read: the next test
    for (const status of [401, 403, 429, 503]) {
      const data = Uint8Array.from([37, 80]);
      app.keepView(OTHER_VIEW, 'abcdef00-0000-4000-8000-000000000000', data);
      app.state.viewHints = new Map([[OTHER_ID, true]]);
      note.textContent = '';
      app.noteRefusedFrame(framed(status));
      const end = status === 401 || status === 403;
      assert.deepEqual([note.textContent, app.state.keptViews.size, [...data], app.state.viewHints.size],
        [status === 429 ? app.FRAME_LIMIT_TEXT : app.FRAME_REFUSED_TEXT, end ? 0 : 1, end ? [0, 0] : [37, 80], end ? 0 : 1], `the frame answered ${status}`);
      app.forgetMemory();
    }
  } finally {
    global.document = saved;
  }
});

test('R2-18: a framed load whose answer cannot be read - the site\'s refusals forbid framing - asks the server for the session, as a poll: its 401 and a forced password change\'s 403 are ends; its 200 changes nothing', async () => {
  // the browser's blocked page in the frame (frame-ancestors 'none', X-Frame-Options DENY) cannot be read from the page:
  // reading it throws, as in Chromium (ops/test_viewer_speed.cjs V9b, with the site's own headers)
  const blocked = () => ({ tagName: 'IFRAME', dataset: {}, contentDocument: null,
    contentWindow: { get performance() { throw new DOMException('Blocked a frame from accessing a cross-origin frame.', 'SecurityError'); } } });
  for (const [what, answer, sent] of [
    ['a 401', { status: 401, body: { error: 'signed_out', reason: 'idle' } }, app.loginAddress('idle', '')],
    ['a forced password change', { status: 403, body: { error: 'password_change_required' } }, '/account/?required=1'],
    ['a 200', { status: 200, body: fixture('session.json') }, null]]) {
    await withSignedInPage({ answers: [{ match: (method, url) => method === 'GET' && url === '/api/session', ...answer }] }, async ({ calls, element }) => {
      const data = Uint8Array.from([37, 80]);
      app.keepView(OTHER_VIEW, 'abcdef00-0000-4000-8000-000000000000', data);
      app.state.viewHints = new Map([[OTHER_ID, true]]);
      const thread = { terminated: false, terminate() { this.terminated = true; } };
      app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
      app.state.leaving = false;
      const frame = blocked();
      try {
        app.noteRefusedFrame(frame);
        await settle(() => false);
        assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => [call.method ?? 'GET', call.headers[app.POLL_HEADER]]), [['GET', '1']],
          `${what}: the session asked once, as a poll (never the member's activity)`);
        const end = sent !== null;
        assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby === null, thread.terminated],
          end ? [0, [0, 0], 0, true, true] : [1, [37, 80], 1, false, false], `${what}: ${end ? 'an end: overwritten, dropped, the hints gone, the worker ended' : 'no end: all kept'}`);
        assert.deepEqual(calls.filter(call => call.assign).map(call => call.assign), end ? [sent] : [], `${what}: where the page goes`);
        assert.deepEqual([frame.dataset.refused, element('#viewerMark').textContent], [undefined, ''], `${what}: nothing said of an answer it cannot read`);
      } finally {
        app.forgetMemory();
      }
    });
  }
});

test('R2-18: the text viewer\'s frame, refused, is an end as the PDF viewer\'s is - an answer it cannot read asks the server for the session, as a poll (401, 403: ends; 200: nothing) - and what it holds it says itself, as in release 1', async () => {
  // the text viewer's frame is #documentViewer itself; the browser's blocked page in it cannot be read (Chromium V9c)
  const textFrame = timing => ({ tagName: 'IFRAME', id: 'documentViewer', dataset: {}, contentDocument: null, contentWindow: { get performance() { return timing(); } } });
  const blocked = () => textFrame(() => { throw new DOMException('Blocked a frame from accessing a cross-origin frame.', 'SecurityError'); });
  const readable = status => () => textFrame(() => ({ getEntriesByType: () => [{ responseStatus: status }] }));
  for (const [what, frameOf, answer, sent, end] of [
    ['blocked, the session ended', blocked, { status: 401, body: { error: 'signed_out', reason: 'idle' } }, app.loginAddress('idle', ''), true],
    ['blocked, a forced password change', blocked, { status: 403, body: { error: 'password_change_required' } }, '/account/?required=1', true],
    ['blocked, the session open', blocked, { status: 200, body: fixture('session.json') }, null, false],
    ['a readable 401', readable(401), null, null, true],
    ['a readable 503', readable(503), null, null, false]]) {
    await withSignedInPage({ answers: answer ? [{ match: (method, url) => method === 'GET' && url === '/api/session', ...answer }] : [] }, async ({ calls, element }) => {
      const viewer = app.state.viewer;
      const data = Uint8Array.from([37, 80]);
      app.keepView(OTHER_VIEW, 'abcdef00-0000-4000-8000-000000000000', data);
      app.state.viewHints = new Map([[OTHER_ID, true]]);
      const thread = { terminated: false, terminate() { this.terminated = true; } };
      app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
      Object.assign(app.state, { leaving: false, viewer: null });  // a text document: no PDF viewer
      const frame = frameOf();
      try {
        app.noteFrameLoad({ target: frame });
        await settle(() => false);
        assert.deepEqual(calls.filter(call => call.url === '/api/session').map(call => [call.method ?? 'GET', call.headers[app.POLL_HEADER]]), answer ? [['GET', '1']] : [],
          `${what}: ${answer ? 'the session asked once, as a poll' : 'an answer it can read asks nothing'}`);
        assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby === null, thread.terminated],
          end ? [0, [0, 0], 0, true, true] : [1, [37, 80], 1, false, false], `${what}: ${end ? 'an end: overwritten, dropped, the hints gone, the worker ended' : 'no end: all kept'}`);
        assert.deepEqual(calls.filter(call => call.assign).map(call => call.assign), sent ? [sent] : [], `${what}: where the page goes`);
        assert.deepEqual([frame.dataset.refused, element('#viewerMark').textContent], [undefined, ''], `${what}: the text viewer's own look, as in release 1`);
      } finally {
        app.state.viewer = viewer;
        app.forgetMemory();
      }
    });
  }
});

test('R2-18: a forced password change met at a download the page saves - the original, an earlier export, the Word file - overwrites the kept copies, clears the hints, ends the worker made ready ahead and saves nothing; any other refusal is no end', async () => {
  const original = `/api/encounters/${UUID}/original`;
  const keep = () => {
    const data = Uint8Array.from([37, 80, 68]);
    app.state.keptViews.clear();
    app.keepView(OTHER_VIEW, 'abcdef00-0000-4000-8000-000000000000', data);
    app.state.viewHints = new Map([[OTHER_ID, true]]);
    const standby = { ended: 0, thread: { terminate() { standby.ended += 1; } }, end() {} };
    app.state.pdfStandby = standby;
    return { data, standby };
  };
  for (const [what, address] of [['the original', original], ['an earlier export', `/api/reports/${UUID}/download`], ['the Word file', `${original}?format=original`]]) {
    await withPage({ answers: [{ match: (method, url) => url === address, status: 403, body: { error: 'password_change_required' } }] }, async ({ calls }) => {
      const { data, standby } = keep();
      await assert.rejects(app.saveDownload(address, ''), { status: 403 });
      assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, standby.ended, app.state.pdfStandby], [0, [0, 0, 0], 0, 1, null], `${what}: an end`);
      assert.deepEqual(calls.filter(call => call.download), [], `${what}: nothing saved`);
    });
  }
  const limited = { match: (method, url) => url === original, status: 429, type: 'text/html', body: '<html>429 Too Many Requests</html>', headers: { 'Retry-After': '60' } };
  await withPage({ answers: [limited] }, async () => {
    const { data, standby } = keep();
    try {
      await assert.rejects(app.saveDownload(original, ''), { status: 429 });
      assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, standby.ended, app.state.pdfStandby === standby], [1, [37, 80, 68], 1, 0, true], 'the front door\'s 429: no end');
    } finally {
      app.forgetMemory();
    }
  });
});

test('R2-18, R2-10: a forced password change met at a download the page saves holds: no worker is made ready ahead after it', async () => {
  const working = fakeLibrary();
  const original = `/api/encounters/${UUID}/original`;
  const refused = () => Promise.resolve({ ok: false, status: 403, redirected: false, url: `http://studio.test${original}`,
    headers: { get: name => (String(name).toLowerCase() === 'content-type' ? 'application/json' : null) },
    json: async () => ({ error: 'password_change_required' }) });
  await withPdfPage(() => Promise.resolve(working.library), async () => {
    await withStandby(async () => {
      app.startStandby();
      await settle(() => FakeWorker.made.length === 1 && app.state.pdfStarted);
      await app.state.pdfStandby.ready;
      assert.equal(FakeWorker.made.length, 1, 'a worker waits before the end');
      await assert.rejects(app.saveDownload(original, ''), { status: 403 });
      assert.equal(app.state.pdfStandby, null, 'the waiting worker ended at the end');
      // a page drawn after the end reschedules the standby (renderPage); its idle start is this call
      app.startStandby();
      await settle(() => FakeWorker.made.length > 1);
      assert.equal(FakeWorker.made.length, 1, 'no worker made ready ahead after the end');
    });
  }, refused);
});

// --- release 2: the page's speed (RELEASE-2-SPEC R2-10 to R2-18 and R2-22), on release 1's server answers too ------------

test('R2 V6: the entrance fade is a page load\'s first view\'s alone: the approved rule stands, the appended rule ends it after that view, and the review never fades', async () => {
  const css = fs.readFileSync(STYLES, 'utf8');
  assert.ok(css.slice(0, 32785).includes('.view-entrance{animation:enter .35s ease both}'), 'the approved rule, in the pinned prefix');
  assert.ok(css.slice(32785).includes('main:not([data-entrance])>.view-entrance{animation:none}'), 'the appended rule');
  assert.match(fs.readFileSync(path.join(TEMPLATES, 'index.html'), 'utf8'), /<main id="main" tabindex="-1" data-entrance>/);
  for (const name of ENCOUNTERS) assert.ok(!render(fixture(name)).includes('view-entrance'), `${name}: the review never fades`);
  // the page load's first route keeps the entrance; every route after it ends it
  const main = fakeElement({ attributes: { 'data-entrance': '' } });
  await withPage({ elements: { main } }, async () => {
    global.location.hash = '#how-it-works';
    app.state.route = null;
    app.route();
    assert.ok('data-entrance' in main.attributes, 'the first view fades in');
    assert.match(main.innerHTML, /^<section class="view-entrance">/);
    app.route();
    assert.ok(!('data-entrance' in main.attributes), 'a later view does not');
  });
  // a document the first route opened (its loading line was the first view): the review drawn ends the entrance too
  const first = fakeElement({ attributes: { 'data-entrance': '' } });
  await withPage({ elements: { main: first } }, async () => {
    const doc = fixture('encounter-ready.json');
    Object.assign(app.state, { route: { name: 'doc', id: doc.id }, routeSerial: 3 });
    app.renderDocument(doc, true);
    assert.ok(!('data-entrance' in first.attributes));
    assert.match(first.innerHTML, /^<section class="review-view">/);
  });
});

test('R2 V8: the page starts from the session its shell carries; it reads the session only where that is missing or unreadable, and on a document at most once a minute', async () => {
  const session = fixture('session.json');
  await withPage({}, async () => {
    for (const [value, expected] of [[JSON.stringify(session), session], [` ${JSON.stringify(session)} `, session], ['', null], ['null', null], ['{', null],
      ['[]', null], ['"x"', null], ['7', null], ['{"user":1}', null], ['{"user":{}}', null], ['{"user":{},"workspace":[]}', null], [undefined, null], [7, null]]) {
      global.document.body.dataset = { sessionJson: value };
      assert.deepEqual(app.shellSession(), expected, String(value));
    }
    global.document.body.dataset = undefined;
    assert.equal(app.shellSession(), null, 'no attribute at all');
  });
  // carried: drawn at once, with no session read before the first view
  await withPage({}, async ({ calls, element }) => {
    global.document.body.dataset = { sessionJson: JSON.stringify(session) };
    global.location.hash = '#how-it-works';
    Object.assign(app.state, { route: null, session: null, sessionReadAt: 0 });
    const routed = app.firstRoute();
    assert.equal(element('#breadcrumbCurrent').textContent, 'How it works', 'routed at once');
    await routed;
    assert.equal(calls.filter(call => call.url === '/api/session').length, 0, 'no session read');
    assert.deepEqual(app.state.session, session);
    assert.equal(element('#workspaceName').textContent, 'Gastroenterology', 'the carried session is drawn');
    assert.ok(Math.abs(Date.now() - app.state.sessionReadAt) < 5000, 'and its time noted');
  });
  // none the page can read (release 1's shell renders the attribute empty): the session is read first, then the route
  await withPage({}, async ({ calls, element }) => {
    global.document.body.dataset = { sessionJson: '' };
    global.location.hash = '#how-it-works';
    Object.assign(app.state, { route: null, session: null, sessionReadAt: 0 });
    const routed = app.firstRoute();
    assert.equal(element('#breadcrumbCurrent').textContent, '', 'not routed before the session is read');
    await routed;
    assert.equal(calls.filter(call => call.url === '/api/session').length, 1);
    assert.equal(element('#breadcrumbCurrent').textContent, 'How it works');
  });
  // a document's route reads it again only once it is a minute old, or missing
  await withPage({}, async ({ calls }) => {
    const reads = () => calls.filter(call => call.url === '/api/session').length;
    Object.assign(app.state, { session, sessionReadAt: Date.now() });
    app.refreshSession();
    app.state.sessionReadAt = Date.now() - app.SESSION_FRESH_MS + 2000;
    app.refreshSession();
    await settle(() => false);
    assert.equal(reads(), 0, 'read a moment ago, and 58 s ago: not again');
    app.state.sessionReadAt = Date.now() - app.SESSION_FRESH_MS;
    app.refreshSession();
    await settle(() => reads() === 1 && Math.abs(Date.now() - app.state.sessionReadAt) < 5000);
    assert.equal(reads(), 1, 'a minute ago: read again');
    assert.ok(Math.abs(Date.now() - app.state.sessionReadAt) < 5000, 'the new read is noted');
    app.state.session = null;
    app.refreshSession();
    await settle(() => reads() === 2);
    app.state.sessionReadAt = Date.now() + 3600000;  // the clock moved back an hour
    app.refreshSession();
    await settle(() => reads() === 3);
    assert.equal(reads(), 3, 'none held, or a read time the clock has moved away from: read');
  });
});

test('R2-14, R2-17: a document chosen in a list keeps the list in view until its review is drawn or 150 ms have passed; from anywhere else the loading line shows at once', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const doc = fixture('encounter-ready.json');
  const address = `/api/encounters/${doc.id}`;
  const LIST = '<section class="view-entrance">THE LIST</section>';
  for (const [before, keeps] of [[{ name: 'documents' }, true], [{ name: 'queue' }, true], [{ name: 'workspace' }, true],
    [{ name: 'doc', id: UUID }, false], [null, false], [{ name: 'how-it-works' }, false], [{ name: 'team' }, false]]) {
    const main = fakeElement({ innerHTML: LIST });
    await withPage({ elements: { main }, answers: [{ match: (method, url) => url === address, status: 200, body: clone(doc) }] }, async ({ calls }) => {
      const scrolls = [];
      global.window.scrollTo = options => scrolls.push(options.top);
      const holds = holdReads(address);
      global.location.hash = `#doc/${doc.id}`;
      Object.assign(app.state, { route: before, session: fixture('session.json'), sessionReadAt: Date.now() });
      app.route();
      const from = JSON.stringify(before);
      if (keeps) {
        assert.equal(main.innerHTML, LIST, `${from}: the list stays`);
        assert.deepEqual(scrolls, [], `${from}: the window is not scrolled`);
        t.mock.timers.tick(app.LOADING_AFTER_MS - 1);
        assert.equal(main.innerHTML, LIST);
        t.mock.timers.tick(1);
      }
      assert.match(main.innerHTML, /Loading the review…/, from);
      assert.deepEqual(scrolls, [0], `${from}: scrolled with the loading line`);
      holds[0]();
      await settle(() => app.state.doc?.id === doc.id);
      assert.match(main.innerHTML, /^<section class="review-view">/, from);
      assert.equal(calls.filter(call => call.url === '/api/session').length, 0, `${from}: the session, read a moment ago, is not read again`);
    });
  }
  // the review answering within the 150 ms replaces the list directly: no loading line, no blank page between
  const main = fakeElement({ innerHTML: LIST });
  await withPage({ elements: { main }, answers: [{ match: (method, url) => url === address, status: 200, body: clone(doc) }] }, async () => {
    const shown = [];
    let html = LIST;
    Object.defineProperty(main, 'innerHTML', { get: () => html, set: value => { html = value; shown.push(value.startsWith('<section class="review-view">') ? 'the review' : value); } });
    global.location.hash = `#doc/${doc.id}`;
    Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now() });
    app.route();
    await settle(() => app.state.doc?.id === doc.id);
    t.mock.timers.tick(1000);
    assert.deepEqual(shown, ['the review'], 'the list, then the review');
  });
  // an upload's acknowledgement shows at once, wherever it came from
  const acked = fakeElement({ innerHTML: LIST });
  await withPage({ elements: { main: acked } }, async () => {
    holdReads(address);
    global.location.hash = `#doc/${doc.id}`;
    Object.assign(app.state, { route: { name: 'documents' }, ack: { id: doc.id, at: Date.parse('2026-11-26T10:00:00Z') }, session: fixture('session.json'), sessionReadAt: Date.now() });
    app.route();
    assert.match(acked.innerHTML, /Uploaded\. The coding review starts shortly\./);
  });
});

// The viewer's worker made ready ahead, the download beside the library, page 1 at once (R2-10 to R2-13).

// A page that has booted (standbyOn), with the standby's state kept apart and every waiting worker ended after.
async function withStandby(fn) {
  try {
    Object.assign(app.state, { standbyOn: true, standbyFails: 0, pdfStandby: null });
    await fn();
  } finally {
    app.endStandby();
    Object.assign(app.state, { standbyOn: false, standbyFails: 0 });
  }
}

test('R2 V1: one worker is made ready ahead, holds no document, is taken by the next document as its own and ends with it; a failing one is dropped, two failures stop it, and the session\'s end ends it', async () => {
  const word = fixture('encounter-word.json');
  const working = fakeLibrary();
  await withPdfPage(() => Promise.resolve(working.library), async ({ element: find, loads }) => {
    app.startStandby();
    await settle(() => false);
    assert.equal(FakeWorker.made.length, 0, 'nothing on a page that has not booted');
    await withStandby(async () => {
      app.startStandby();
      app.startStandby();
      await settle(() => FakeWorker.made.length === 1 && app.state.pdfStarted);
      assert.equal(FakeWorker.made.length, 1, 'one, asked for twice');
      await app.state.pdfStandby.ready;
      app.startStandby();
      await settle(() => false);
      assert.equal(FakeWorker.made.length, 1, 'nor another once it is ready');
      assert.deepEqual([FakeWorker.made[0].url, FakeWorker.made[0].options], [PDF_WORKER, { type: 'module' }]);
      assert.equal(working.made.workers.length, 0, 'the library is handed no worker before a document takes it');
      assert.equal(working.made.tasks.length, 0, 'and it holds no document');
      // the next document takes it as its own, and starts none
      const first = FakeWorker.made[0];
      const viewer = await mount(word, find, () => working.made.tasks.length === 1);
      assert.equal(FakeWorker.made.length, 1, 'the document started no worker of its own');
      assert.equal(viewer.thread, first, 'the viewer\'s own, so closing the document ends it');
      assert.equal(app.state.pdfStandby, null, 'it is the document\'s now');
      assert.equal(working.made.workers[0].options.port, first);
      app.closeViewer();
      await settle(() => first.terminated);
      assert.ok(first.terminated, 'it ends with its document');
      // one that fails is dropped and ended, and the next document starts its own, as in release 1
      app.startStandby();
      await settle(() => FakeWorker.made.length === 2);
      await app.state.pdfStandby.ready;
      FakeWorker.made[1].emit('error', {});
      assert.equal(app.state.pdfStandby, null);
      assert.ok(FakeWorker.made[1].terminated);
      assert.deepEqual([app.state.standbyFails, app.state.standbyOn], [1, true], 'one failure is not the end of it');
      const second = await mount(word, find, () => working.made.tasks.length === 2);
      assert.equal(FakeWorker.made.length, 3);
      assert.equal(second.thread, FakeWorker.made[2]);
      app.closeViewer();
      // the session's end ends a waiting one, and its wait settles at once rather than at the time limit
      app.startStandby();
      await settle(() => FakeWorker.made.length === 4);
      const waiting = app.state.pdfStandby;
      app.forgetMemory();
      assert.equal(app.state.pdfStandby, null);
      assert.ok(FakeWorker.made[3].terminated);
      const outcome = await Promise.race([waiting.ready.then(() => 'ready', () => 'ended'), new Promise(resolve => setTimeout(() => resolve('still waiting'), 200))]);
      assert.equal(outcome, 'ended');
      assert.equal(loads.length, 1, 'the library was loaded once');
      // one made ready for an address no longer asked for (the library forgotten, ?attempt=2) is ended, never kept
      app.startStandby();
      await settle(() => FakeWorker.made.length === 5);
      await app.state.pdfStandby.ready;
      app.state.pdfLibrary = null;
      await mount(word, find, () => working.made.tasks.length === 3);
      assert.ok(FakeWorker.made[4].terminated, 'the stale one is ended');
      assert.match(FakeWorker.made[5].url, /\?attempt=2$/);
      app.closeViewer();
      // a second failure stops the warming: each document starts its own, as in release 1
      app.endStandby();
      app.startStandby();
      await settle(() => FakeWorker.made.length === 7);
      FakeWorker.made[6].emit('error', {});
      await settle(() => app.state.pdfStandby === null);
      assert.deepEqual([app.state.standbyFails, app.state.standbyOn], [2, false]);
      app.startStandby();
      await settle(() => false);
      assert.equal(FakeWorker.made.length, 7, 'none after two failures');
    });
    // none where the page is leaving or signed out, the member saves data, or the browser cannot draw a PDF
    for (const [what, set, unset] of [['leaving', () => { app.state.leaving = true; }, () => { app.state.leaving = false; }],
      ['signed out', () => { app.idle.gone = true; }, () => { app.idle.gone = false; }],
      ['saving data', () => { Object.defineProperty(global, 'navigator', { value: { connection: { saveData: true } }, configurable: true, writable: true }); },
        () => {}],
      ['no IntersectionObserver', () => { global.IntersectionObserver = undefined; }, () => { global.IntersectionObserver = function () { this.observe = () => {}; this.disconnect = () => {}; }; }]]) {
      const saved = Object.getOwnPropertyDescriptor(global, 'navigator');
      await withStandby(async () => {
        set();
        try {
          const before = FakeWorker.made.length;
          app.startStandby();
          await settle(() => false);
          assert.equal(FakeWorker.made.length, before, what);
          assert.equal(app.state.pdfStandby, null, what);
        } finally {
          unset();
          if (saved) Object.defineProperty(global, 'navigator', saved);
          else delete global.navigator;
        }
      });
    }
  });
});

test('R2 V1: the worker is made ready ahead when the browser is idle, after the delay asked for; boot asks 500 ms after its first route, a closed viewer or a drawn page 600 ms after', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const asked = [];
  const savedIdle = global.requestIdleCallback;
  global.requestIdleCallback = (fn, options) => asked.push({ fn, options });
  try {
    await withPdfPage(() => Promise.resolve(fakeLibrary().library), async () => {
      assert.deepEqual(app.PDF_STANDBY, { first: 500, next: 600, idle: 2000, fails: 2 });
      app.scheduleStandby(500);
      t.mock.timers.tick(10000);
      assert.equal(asked.length, 0, 'not on a page that has not booted');
      await withStandby(async () => {
        app.scheduleStandby(500);
        app.scheduleStandby(500);
        t.mock.timers.tick(499);
        assert.equal(asked.length, 0);
        t.mock.timers.tick(1);
        assert.equal(asked.length, 1, 'once, asked twice');
        assert.deepEqual(asked[0].options, { timeout: 2000 }, 'when the browser is idle, or 2 s at the latest');
        assert.equal(FakeWorker.made.length, 0, 'nothing before the browser says it is idle');
        asked[0].fn();
        await settle(() => FakeWorker.made.length === 1);
        assert.equal(FakeWorker.made.length, 1);
        // the session's end clears a pending one
        app.endStandby();
        app.scheduleStandby(600);
        app.forgetMemory();
        t.mock.timers.tick(10000);
        assert.equal(asked.length, 1, 'cleared');
        // where the browser cannot say it is idle, at once after the delay
        global.requestIdleCallback = undefined;
        app.scheduleStandby(600);
        t.mock.timers.tick(600);
        await settle(() => FakeWorker.made.length === 2);
        assert.equal(FakeWorker.made.length, 2);
      });
    });
  } finally {
    global.requestIdleCallback = savedIdle;
  }
  // boot: after its first route
  await withPage({}, async () => {
    global.document.body.dataset = { sessionJson: JSON.stringify(fixture('session.json')) };
    global.location.hash = '#how-it-works';
    Object.assign(app.state, { route: null, standbyOn: false });
    try {
      await app.firstRoute();
      assert.equal(app.state.standbyOn, true, 'on, from the page\'s first route');
      assert.ok(app.state.standbyTimer, 'and asked for');
    } finally {
      app.endStandby();
      app.state.standbyOn = false;
    }
  });
  const source = fs.readFileSync(BUNDLE, 'utf8');
  assert.match(source, /function closeViewer\(\) \{[^}]*stopPdf\(viewer\);\n  viewer\.mode = 'closed';\n  scheduleStandby\(PDF_STANDBY\.next\);\n\}/);
  assert.match(source, /    page\.drawn = key;\n    scheduleStandby\(PDF_STANDBY\.next\);\n/);
  assert.match(source, /window\.addEventListener\('pageshow', event => \{ if \(event\.persisted\) scheduleStandby\(PDF_STANDBY\.next\); \}\);/);
  // registered unconditionally, at boot's top level (Chromium's V10 and V10b, ops/test_viewer_speed.cjs, fire it): in
  // boot's own body, after no return, the line before it a whole statement (no brace-less if)
  const bootBody = /\nfunction boot\(\) \{\n([\s\S]*?)\n\}\n/.exec(source)[1];
  const aroundPagehide = `${bootBody}\n`.split("\n  window.addEventListener('pagehide', forgetMemory);\n");
  assert.equal(aroundPagehide.length, 2, 'the pagehide line stands once in boot\'s own body, at its top level');
  assert.doesNotMatch(aroundPagehide[0], /\breturn\b/, 'no return in boot before it');
  assert.match(aroundPagehide[0], /[;}]$/, 'the line before it is a whole statement');
});

test('R2 V1: leaving a document while its worker starts never makes the page forget a working library', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  const word = fixture('encounter-word.json');
  const working = fakeLibrary();
  await withPdfPage(() => Promise.resolve(working.library), async ({ element: find, loads }) => {
    FakeWorker.start = 'never';
    await mount(word, find, () => FakeWorker.made.length === 1);
    const kept = app.state.pdfLibrary;
    assert.ok(kept);
    app.closeViewer();
    t.mock.timers.tick(60000);
    await settle(() => false);
    assert.equal(app.state.pdfLibrary, kept, 'the library works: it stays');
    FakeWorker.start = 'ready';
    await mount(word, find, () => working.made.tasks.length === 1);
    assert.equal(loads.length, 1, 'the next document loads nothing again');
    assert.equal(FakeWorker.made.at(-1).url, PDF_WORKER, 'at the same address, never ?attempt=2');
    // an import that itself fails is still forgotten at once, with no viewer waiting on it
    app.closeViewer();
    app.state.pdfLibrary = null;
  });
  await withPdfPage(() => Promise.reject(new Error('404')), async ({ loads }) => {
    const failing = app.loadPdfLibrary();
    await failing.catch(() => {});
    await settle(() => app.state.pdfLibrary === null);
    assert.equal(app.state.pdfLibrary, null, 'a failed import is not kept');
    assert.equal(loads.length, 1);
  });
});

test('R2 V2: the document is asked for beside the library and its worker once both have started in the page; before that, after them; a refused download is said at once', async t => {
  const word = fixture('encounter-word.json');
  let arrive;
  const cold = fakeLibrary();
  await withPdfPage(() => new Promise(resolve => { arrive = resolve; }), async ({ element: find, fetches, loads }) => {
    FakeWorker.start = 'never';
    const viewer = await mount(word, find, () => loads.length === 1);
    assert.equal(fetches.length, 0, 'the page\'s first document: not while the library loads');
    arrive(cold.library);
    await settle(() => FakeWorker.made.length === 1);
    assert.equal(fetches.length, 0, 'nor while its worker starts');
    FakeWorker.made[0].emit('message', { data: { sourceName: 'worker', targetName: 'main', action: 'ready' } });
    await settle(() => cold.made.tasks.length === 1);
    assert.equal(fetches.length, 1, 'after them: release 1\'s order');
    assert.equal(app.state.pdfStarted, true, 'the library and a worker have started in this page');
    assert.equal(viewer.mode, 'loading');
    // the next document: asked for at once, its worker not started yet
    const next = await mount(word, find, () => fetches.length === 2);
    assert.equal(fetches.length, 2, 'beside them');
    assert.equal(FakeWorker.made.length, 2);
    assert.equal(cold.made.tasks.length, 1, 'its worker has not said it is ready');
    FakeWorker.made[1].emit('message', { data: { sourceName: 'worker', targetName: 'main', action: 'ready' } });
    await settle(() => cold.made.tasks.length === 2);
    assert.deepEqual([...cold.made.tasks[1].options.data], [37, 80, 68, 70, 45, 49, 46, 52], 'the bytes downloaded beside them');
    assert.notEqual(next.stallTimer, 0, 'the library reads them under the download\'s time limit, until the document opens');
    // a worker that fails once started: the library is asked for again at fresh addresses, so the order is the first one's
    FakeWorker.made[1].emit('error', {});
    assert.equal(app.state.pdfStarted, false, 'a forgotten library is fetched again: release 1\'s order');
    const third = await mount(word, find, () => loads.length === 2);
    assert.equal(fetches.length, 2, 'not before the library and its worker');
    assert.equal(third.mode, 'loading');
    app.closeViewer();
    arrive(cold.library);  // its wait on the library settles, so nothing is left waiting
    await settle(() => false);
  });
  // a refused download, on a page where they have started: said at once, the worker still starting
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ element: find }) => {
    app.state.pdfStarted = true;
    FakeWorker.start = 'never';
    const viewer = await mount(word, find, opened => opened.mode === 'frame');
    assert.equal(viewer.fallback, 'download', 'a refused download is said at once');
    await settle(() => FakeWorker.made.every(made => made.terminated));
    assert.ok(FakeWorker.made.every(made => made.terminated), 'and the worker starting for it is ended');
    t.mock.timers.tick(app.PDF_VIEW.limitMs);  // the closed viewer's wait on its worker gives up, concluding nothing
    await settle(() => false);
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'download']);
    assert.ok(app.state.pdfLibrary, 'and the library is kept');
  }, () => Promise.resolve(viewResponse({ status: 503, chunks: [] })));
});

test('R2 V2: a worker made ready ahead that says ready after the library was forgotten does not bring back the parallel order', async () => {
  const word = fixture('encounter-word.json');
  const working = fakeLibrary();
  let fresh = null;
  const load = specifier => (/\?attempt=2$/.test(specifier) ? new Promise(resolve => { fresh = resolve; }) : Promise.resolve(working.library));
  try {
    await withPdfPage(load, async ({ element: find, fetches, loads }) => {
      await withStandby(async () => {
        const viewer = await mount(word, find, () => fetches.length === 1);
        assert.equal(app.state.pdfStarted, true);
        // the worker made ready ahead (after a drawn page) is still starting
        FakeWorker.start = 'never';
        app.startStandby();
        await settle(() => FakeWorker.made.length === 2);
        // the document's own worker fails once started: the library is forgotten
        viewer.thread.emit('error', {});
        assert.equal(app.state.pdfStarted, false);
        // the waiting worker, of the forgotten library, says ready now
        FakeWorker.made[1].emit('message', { data: { sourceName: 'worker', targetName: 'main', action: 'ready' } });
        await settle(() => false);
        assert.equal(app.state.pdfStarted, false, 'a worker of a forgotten library says nothing about the next one\'s files');
        await mount(word, find, () => loads.length === 2);
        assert.match(loads[1], /\?attempt=2$/);
        assert.equal(fetches.length, 1, 'the next document waits for its fresh library and worker: release 1\'s order');
        app.closeViewer();
        fresh?.(fakeLibrary().library);
        await settle(() => false);
      });
    });
  } finally {
    FakeWorker.start = 'ready';
  }
});

test('R2 V2, R2-13: page 1 is asked for as the pages are built, and its text read beside its drawing; the two are shown together', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  const style = global.getComputedStyle;
  global.getComputedStyle = () => ({ paddingLeft: '12px', paddingRight: '12px' });
  const globals = { IntersectionObserver: global.IntersectionObserver, ResizeObserver: global.ResizeObserver };
  global.IntersectionObserver = function IntersectionObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  global.ResizeObserver = function ResizeObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  try {
    const element = viewerElement({ dataset: { viewUrl: word.document.view_url }, clientWidth: 636, clientHeight: 800, scrollTop: 0, scrollLeft: 0,
      scrollWidth: 636, addEventListener() {} });
    await withPage({ elements: { documentViewer: element } }, async () => {
      global.window.devicePixelRatio = 1;
      const made = () => ({ className: '', dataset: {}, style: { setProperty(name, value) { this[name] = value; } }, children: [],
        append(...nodes) { this.children.push(...nodes); }, setAttribute() {}, replaceChildren(...nodes) { this.children = nodes; }, querySelector: () => null });
      global.document.createElement = made;
      Object.assign(app.state, { doc: word, route: null });
      const order = [];
      let drawn;
      let read;
      const proxy = number => ({ getViewport: ({ scale }) => ({ width: 612 * scale, height: 792 * scale, scale, userUnit: 1 }),
        render: () => { order.push(`render ${number}`); return { promise: new Promise(resolve => { drawn = resolve; }), cancel() {} }; },
        getTextContent: () => { order.push(`text ${number}`); return new Promise(resolve => { read = resolve; }); }, cleanup() {} });
      const layers = [];
      const viewer = { element, view: word.document.view_url, name: 'x', mode: 'loading', pages: [], texts: new Map(), prepared: new Map(), mark: null,
        pending: null, chosen: null, markSerial: 0, reveal: 0, quoteScroll: null, frame: null, framePage: null, fallback: '', zoom: app.ZOOM_FIT,
        inputs: [], settleTimer: 0, library: { AnnotationMode: { ENABLE: 2 }, TextLayer: class {
          constructor(options) { layers.push(options); this.textDivs = []; this.textContentItemsStr = []; }

          render() { return Promise.resolve(); }

          cancel() {}
        } } };
      app.state.viewer = viewer;
      app.buildPages(viewer, [proxy(1), proxy(2)]);
      assert.deepEqual(order, ['render 1', 'text 1'], 'page 1 at once - its drawing and its text read together - before any observer answers');
      assert.equal(viewer.pages[0].near, true);
      const page = viewer.pages[0];
      read({ items: [] });
      await settle(() => false);
      assert.deepEqual(page.element.children, [], 'the text alone is not shown');
      drawn();
      await settle(() => page.drawn !== '');
      assert.equal(page.element.children.length, 2, 'canvas and text layer, shown together');
      assert.equal(layers.length, 1);
      app.closeViewer();
      // a quote chosen while the document opened is shown on its own page instead: page 1 is not asked for first
      order.length = 0;
      const waiting = { ...viewer, mode: 'loading', pages: [], texts: new Map(), prepared: new Map(), pending: { quote: { text: 'x', page: 2 }, key: 'L1#0' },
        watchdog: null };
      app.state.viewer = waiting;
      app.buildPages(waiting, [proxy(1), proxy(2)]);
      assert.ok(!order.includes('render 1'), 'not page 1 first');
      app.closeViewer();
    });
  } finally {
    global.getComputedStyle = style;
    Object.assign(global, globals);
    Object.assign(app.state, saved);
  }
});

// A re-open drawn from page memory after a recorded 304, the view asked for at the click, page memory wiped at every end
// (R2-15, R2-16, R2-18).

const VIEW_TAG_A = '"0f0e0d0c-0b0a-4908-8706-050403020100"';
// another document, whose copy and hint only an end wipes
const OTHER_ID = 'fe000000-0000-4000-8000-0000000000aa';  // no fixture's
const OTHER_VIEW = `/api/encounters/${OTHER_ID}/original?view=1`;
const VIEW_TAG_B = '"1f0e0d0c-0b0a-4908-8706-050403020100"';
// A view's answer with its headers: `tag` as the ETag the server sent, if any.
const taggedView = (status, chunks, tag) => Promise.resolve({ ...viewResponse({ status, chunks }), headers: { get: name => (name === 'ETag' && tag ? tag : null) } });

test('R2 V3: a re-open asks with the tag it holds and draws the kept bytes on a 304 alone; a changed 200 replaces them; any refusal or failure draws nothing and drops them; an untagged view is never kept', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });  // a refused re-open's viewer, closed, leaves its worker's wait to a time limit
  const word = fixture('encounter-word.json');
  const view = word.document.view_url;
  const opened = [];
  const library = fakeLibrary({ open: task => { opened.push([...task.options.data]); return Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }); } });
  let answer = () => taggedView(200, undefined, VIEW_TAG_A);
  app.state.keptViews.clear();
  try {
    await withPdfPage(() => Promise.resolve(library.library), async ({ element: find, fetches }) => {
      await mount(word, find, () => opened.length === 1 && app.state.keptViews.size === 1);
      assert.equal(fetches[0].init.headers['If-None-Match'], undefined, 'nothing held: nothing asked');
      assert.equal(fetches[0].init.cache, 'no-store');
      assert.equal(app.state.keptViews.get(view).tag, '0f0e0d0c-0b0a-4908-8706-050403020100');
      assert.ok(app.state.keptViews.get(view).data instanceof Uint8Array, 'bytes in page memory: never a Blob');
      app.closeViewer();
      answer = () => taggedView(304, [], VIEW_TAG_A);
      await mount(word, find, () => opened.length === 2);
      assert.equal(fetches[1].init.headers['If-None-Match'], VIEW_TAG_A, 'asked with its tag');
      assert.equal(fetches[1].init.headers['X-CPT-Poll'], '1', 'the page\'s own read: never the member\'s activity');
      assert.deepEqual(opened[1], opened[0], 'the same bytes, drawn from page memory');
      const kept = app.state.keptViews.get(view).data;
      assert.ok(library.made.tasks.every(task => task.options.data.buffer !== kept.buffer), 'the library takes the array it is given: never the kept one\'s buffer');
      assert.equal(app.state.keptViews.size, 1);
      app.closeViewer();
      // changed on the server: the new bytes are drawn, and kept in place of the old, which are overwritten
      answer = () => taggedView(200, [Uint8Array.from([37, 80, 68, 70, 45, 50])], VIEW_TAG_B);
      await mount(word, find, () => opened.length === 3);
      assert.deepEqual(opened[2], [37, 80, 68, 70, 45, 50]);
      await settle(() => app.state.keptViews.get(view)?.tag === VIEW_TAG_B.slice(1, -1));
      assert.deepEqual([...app.state.keptViews.get(view).data], [37, 80, 68, 70, 45, 50]);
      assert.ok(kept.every(byte => byte === 0), 'the copy replaced is overwritten');
      app.closeViewer();
      // refused, whatever the reason, or not reached: nothing is drawn from memory, and the copy goes
      for (const [what, refuse] of [['401', () => taggedView(401, [], '')], ['403', () => taggedView(403, [], '')], ['404', () => taggedView(404, [], '')],
        ['429', () => taggedView(429, [], '')], ['503', () => taggedView(503, [], '')], ['offline', () => Promise.reject(new TypeError('Failed to fetch'))]]) {
        const data = Uint8Array.from([37, 80]);
        app.keepView(view, 'abcdef00-0000-4000-8000-000000000000', data);
        // another document's copy and a hint: wiped at an end alone - a 401, or a forced password change's 403 (R2-18)
        const other = Uint8Array.from([37, 80, 68]);
        app.keepView(OTHER_VIEW, 'abcdef01-0000-4000-8000-000000000000', other);
        app.state.viewHints = new Map([[OTHER_ID, true]]);
        answer = refuse;
        const viewer = await mount(word, find, made => made.mode === 'frame');
        assert.equal(viewer.fallback, 'download', what);
        assert.equal(app.state.keptViews.has(view), false, `${what}: the copy is dropped`);
        assert.deepEqual([...data], [0, 0], `${what}: and overwritten`);
        const end = what === '401' || what === '403';
        assert.deepEqual([app.state.keptViews.size, [...other], app.state.viewHints.size], end ? [0, [0, 0, 0], 0] : [1, [37, 80, 68], 1],
          `${what}: ${end ? 'an end: the other copies overwritten and dropped, the hints gone' : 'no end: the other copies and the hints stay'}`);
        assert.equal(opened.length, 3, `${what}: nothing drawn`);
        app.closeViewer();
        app.forgetMemory();
        t.mock.timers.tick(app.PDF_VIEW.limitMs);  // that wait gives up, concluding nothing about the library
        await settle(() => false);
        assert.ok(app.state.pdfLibrary, `${what}: the library is kept`);
      }
      // a 304 nobody asked for (no copy held) is no document
      answer = () => taggedView(304, [], VIEW_TAG_A);
      const odd = await mount(word, find, made => made.mode === 'frame');
      assert.equal(odd.fallback, 'download');
      app.closeViewer();
      // a 200 with no tag, or a tag that is not a quoted UUID (a hash, say), is drawn and never kept
      for (const tag of ['', `"${'ab'.repeat(32)}"`, '0f0e0d0c-0b0a-4908-8706-050403020100', '"*"']) {
        const before = opened.length;
        answer = () => taggedView(200, undefined, tag);
        await mount(word, find, () => opened.length === before + 1);
        await settle(() => false);
        assert.equal(app.state.keptViews.size, 0, `tag ${tag || 'none'}: never kept`);
        app.closeViewer();
      }
      // the weak form of the server's tag is a tag
      answer = () => taggedView(200, undefined, `W/${VIEW_TAG_A}`);
      await mount(word, find, () => app.state.keptViews.size === 1);
      assert.equal(app.state.keptViews.get(view).tag, VIEW_TAG_A.slice(1, -1));
    }, (url, init) => answer(url, init));
  } finally {
    app.forgetMemory();
  }
});

test('R2 V3: a document that does not open is never kept, and a copy wiped while its re-open is answered, or while that answer\'s empty body is read, is never drawn', async () => {
  const word = fixture('encounter-word.json');
  const view = word.document.view_url;
  app.state.keptViews.clear();
  try {
    // the library refuses the bytes, or finds no page in them: nothing is kept
    for (const open of [() => Promise.reject(Object.assign(new Error('Invalid PDF structure.'), { name: 'InvalidPDFException' })),
      () => Promise.resolve({ numPages: 0, getPage: () => Promise.reject(new Error('none')) })]) {
      await withPdfPage(() => Promise.resolve(fakeLibrary({ open }).library), async ({ element: find }) => {
        const viewer = await mount(word, find, made => made.mode === 'frame');
        assert.equal(viewer.fallback, 'document');
        assert.equal(app.state.keptViews.size, 0, 'only a document that opened is kept');
      }, () => taggedView(200, undefined, VIEW_TAG_A));
    }
    // a copy wiped (the session ended, or evicted) while its 304 is on the way: no bytes are drawn
    const opened = [];
    let release;
    await withPdfPage(() => Promise.resolve(fakeLibrary({ open: task => { opened.push([...task.options.data]); return Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }); } }).library),
      async ({ element: find, fetches }) => {
        app.keepView(view, '0f0e0d0c-0b0a-4908-8706-050403020100', Uint8Array.from([37, 80, 68, 70]));
        const viewer = await mount(word, find, () => fetches.length === 1);
        assert.equal(fetches[0].init.headers['If-None-Match'], VIEW_TAG_A);
        app.state.keptViews.clear();  // wiped, as at an end
        release();
        await settle(() => viewer.mode === 'frame');
        assert.deepEqual([viewer.mode, viewer.fallback, opened.length], ['frame', 'download', 0]);
      }, () => new Promise(resolve => { release = () => resolve(taggedView(304, [], VIEW_TAG_A)); }));
    // ... or while that 304's empty body is read: the copy is checked after the read, not before it
    let reading = false;
    let releaseBody;
    await withPdfPage(() => Promise.resolve(fakeLibrary({ open: task => { opened.push([...task.options.data]); return Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }); } }).library),
      async ({ element: find }) => {
        app.keepView(view, '0f0e0d0c-0b0a-4908-8706-050403020100', Uint8Array.from([37, 80, 68, 70]));
        const viewer = await mount(word, find, () => reading);
        app.state.keptViews.clear();  // wiped while the body is read
        releaseBody();
        await settle(() => viewer.mode === 'frame');
        assert.deepEqual([viewer.mode, viewer.fallback, opened.length, app.state.keptViews.size], ['frame', 'download', 0, 0]);
      }, () => taggedView(304, [], VIEW_TAG_A).then(response => ({ ...response, arrayBuffer: () => {
        reading = true;
        return new Promise(resolve => { releaseBody = () => resolve(new ArrayBuffer(0)); });
      } })));
  } finally {
    app.forgetMemory();
  }
});

test('R2 V3: the kept copies are bounded - six documents, 24 MiB - the least recently viewed going first, and are overwritten as they go and at the session\'s end', () => {
  app.state.keptViews.clear();
  assert.deepEqual(app.KEPT_VIEWS, { documents: 6, bytes: 24 * 1024 * 1024 });
  const tag = 'abcdef00-0000-4000-8000-000000000000';
  const bytes = size => new Uint8Array(size).fill(7);
  const made = {};
  for (let n = 1; n <= 8; n += 1) app.keepView(`/v${n}`, tag, (made[n] = bytes(10)));
  assert.deepEqual([...app.state.keptViews.keys()], ['/v3', '/v4', '/v5', '/v6', '/v7', '/v8']);
  assert.ok(made[1].every(byte => byte === 0) && made[2].every(byte => byte === 0), 'the ones that went are overwritten');
  app.keepView('/v3', tag, app.state.keptViews.get('/v3').data);
  app.keepView('/v9', tag, bytes(10));
  assert.deepEqual([...app.state.keptViews.keys()], ['/v5', '/v6', '/v7', '/v8', '/v3', '/v9'], 'viewed again: kept longer');
  assert.ok(made[3].every(byte => byte === 7), 'a copy kept again is not overwritten');
  app.keepView('/big', tag, new Uint8Array(app.KEPT_VIEWS.bytes - 15));
  assert.deepEqual([...app.state.keptViews.keys()], ['/v9', '/big'], 'the bytes bound it too');
  app.keepView('/huge', tag, new Uint8Array(app.KEPT_VIEWS.bytes + 1));
  for (const bad of ['', 'not-a-uuid', `${'ab'.repeat(16)}`]) app.keepView(`/bad${bad}`, bad, bytes(10));
  app.keepView('/blob', tag, new Blob(['%PDF']));
  assert.deepEqual([...app.state.keptViews.keys()], ['/v9', '/big'], 'never more than the bound, an untagged view, or anything but bytes');
  const held = [...app.state.keptViews.values()].map(item => item.data);
  app.forgetMemory();
  assert.equal(app.state.keptViews.size, 0);
  assert.ok(held.every(data => data.every(byte => byte === 0)), 'overwritten, not only let go of');
});

test('R2 V3: a re-open answered 304 moves its copy to the end - the next copy kept lets the least recently viewed go, never the one just viewed again', async () => {
  const fetchBefore = global.fetch;
  const tag = 'abcdef00-0000-4000-8000-000000000000';
  app.state.keptViews.clear();
  try {
    for (let n = 1; n <= 6; n += 1) app.keepView(`/v${n}`, tag, new Uint8Array(4).fill(n));
    global.fetch = async () => ({ status: 304, ok: false, headers: { get: () => null }, arrayBuffer: async () => new ArrayBuffer(0) });
    const got = await app.downloadDocument('/v1', new AbortController().signal, () => {});
    assert.deepEqual([got.held, [...got.data]], [true, [1, 1, 1, 1]], 'the oldest copy re-opened from page memory');
    app.keepView('/v7', tag, new Uint8Array(4).fill(7));
    assert.deepEqual([...app.state.keptViews.keys()], ['/v3', '/v4', '/v5', '/v6', '/v1', '/v7'], 'viewed again through a 304: kept longer');
  } finally {
    global.fetch = fetchBefore;
    app.forgetMemory();
  }
});

test('R2 V3, R2-15: the page\'s own abort of a re-open - a route away, a second click - leaves the copy kept and whole; a request that fails drops it', async () => {
  const word = fixture('encounter-word.json');
  const view = `/api/encounters/${word.id}/original?view=1`;
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
    app.state.pdfStarted = true;
    const data = Uint8Array.from([37, 80, 68]);
    app.keepView(view, 'abcdef00-0000-4000-8000-000000000000', data);
    app.startEarly(word.id);
    assert.deepEqual(fetches.map(item => item.init.headers['If-None-Match']), ['"abcdef00-0000-4000-8000-000000000000"'], 'asked with its tag at the click');
    app.dropEarly();  // the member routes away before the answer
    await settle(() => false);
    assert.equal(fetches[0].init.signal.aborted, true);
    assert.deepEqual([app.state.keptViews.get(view)?.data === data, [...data]], [true, [37, 80, 68]], 'kept, the same bytes, not overwritten');
    app.forgetMemory();
  }, (url, init) => new Promise((resolve, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason))));
});

test('R2 V3, R2-18: the idle end, the cap, another tab\'s sign-out, a 401, a forced password change and the sign-out form each wipe page memory before the page leaves', async () => {
  const form = () => fakeElement({ submitted: 0, submit() { this.submitted += 1; } });
  const keep = () => {
    const data = Uint8Array.from([37, 80]);
    app.state.keptViews.clear();
    app.keepView('/api/encounters/x/original?view=1', 'abcdef00-0000-4000-8000-000000000000', data);
    app.state.viewHints = new Map([['x', true]]);
    return data;
  };
  for (const [what, end, answers] of [
    ['the idle end', () => { Object.assign(app.idle, { deadline: Date.now() - 1, gone: false }); app.scheduleIdle(); }],
    ['the cap', () => { Object.assign(app.idle, { deadline: Date.now() - 1, capEnd: Date.now() - 1, idleEnd: Date.now() + 60000, gone: false }); app.scheduleIdle(); }],
    ['another tab\'s sign-out', () => { Object.assign(app.idle, { gone: false, session: 'tag-a' }); app.receiveSession({ type: 'signed-out', reason: 'idle', session: 'tag-a' }); }],
    ['a 401', () => { app.idle.gone = false; return app.api('/api/encounters').catch(() => {}); }, [{ match: () => true, status: 401, body: { error: 'signed_out', reason: 'idle' } }]],
    ['a forced password change', () => app.api('/api/encounters').catch(() => {}), [{ match: () => true, status: 403, body: { error: 'password_change_required' } }]]]) {
    await withSignedInPage({ elements: { signoutForm: form() }, answers }, async () => {
      const data = keep();
      app.state.leaving = false;
      await end();
      assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size], [0, [0, 0], 0], what);
    });
  }
  // the sign-out form, sent by the member: its listener wipes page memory too
  await withTimerPage({}, PAGE_SECONDS, async ({ element }) => {
    const listeners = {};
    const signout = element('#signoutForm');
    signout.addEventListener = (type, fn) => { listeners[type] = fn; };
    app.startIdleWatch();
    const data = keep();
    listeners.submit();
    assert.deepEqual([app.state.keptViews.size, [...data]], [0, [0, 0]], 'the sign-out form');
  });
});

test('R2 V4: the view is asked for with the click only once the library has started, on a page not outdated or leaving, where the list said it opens as a PDF or the page keeps its bytes, and only of the document chosen', async () => {
  const word = fixture('encounter-word.json');
  const view = `/api/encounters/${word.id}/original?view=1`;
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
    app.state.viewHints = new Map([[word.id, false]]);
    app.state.pdfStarted = true;
    app.startEarly(word.id);
    assert.equal(fetches.length, 0, 'no hint and no copy: after the document\'s details, as before');
    app.state.viewHints.set(word.id, true);
    app.state.pdfStarted = false;
    app.startEarly(word.id);
    assert.equal(fetches.length, 0, 'not before the library and a worker have started in the page');
    app.state.pdfStarted = true;
    for (const stop of ['outdated', 'leaving']) {
      app.state[stop] = true;
      app.startEarly(word.id);
      app.state[stop] = false;
    }
    app.idle.gone = true;
    app.startEarly(word.id);
    app.idle.gone = false;
    global.IntersectionObserver = undefined;
    app.startEarly(word.id);
    global.IntersectionObserver = function IntersectionObserver() { this.observe = () => {}; this.disconnect = () => {}; };
    assert.equal(fetches.length, 0, 'nor on a page that is out of date, leaving or signed out, or cannot draw a PDF');
    app.startEarly(word.id);
    assert.deepEqual(fetches.map(item => [item.url, item.init.headers['X-CPT-Poll'], item.init.cache]), [[view, '1', 'no-store']], 'asked once, as the page\'s own read');
    const early = app.state.early;
    assert.equal(app.takeEarly(`/api/encounters/${UUID}/original?view=1`), null, 'never another document\'s');
    assert.equal(app.takeEarly(view), early, 'taken over for its own view');
    assert.equal(app.state.early, null);
    // a route, a first read that fails, and a document that is no PDF each drop it, aborted
    app.startEarly(word.id);
    app.dropEarly();
    assert.equal(fetches.at(-1).init.signal.aborted, true);
    assert.equal(app.state.early, null);
    app.state.viewHints = new Map();
    app.keepView(view, 'abcdef00-0000-4000-8000-000000000000', Uint8Array.from([37]));
    app.startEarly(word.id);
    assert.equal(fetches.length, 3, 'a kept copy is reason enough');
    assert.equal(fetches.at(-1).init.headers['If-None-Match'], '"abcdef00-0000-4000-8000-000000000000"');
    app.forgetMemory();
    assert.deepEqual([fetches.at(-1).init.signal.aborted, app.state.early], [true, null], 'an end (forgetMemory) drops the click\'s view, aborted');
  }, () => new Promise(() => {}));
  // through the page's own route: the click's route asks for the view beside the details; the next route aborts it
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
    const doc = fixture('encounter-ready.json');
    const address = `/api/encounters/${doc.id}`;
    Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), pdfStarted: true,
      viewHints: new Map([[doc.id, true]]) });
    global.location.hash = `#doc/${doc.id}`;
    app.route();
    assert.deepEqual(fetches.map(item => item.url), [`${address}/original?view=1`, address], 'the view asked for at the click, no later than the details');
    const { signal } = fetches[0].init;
    global.location.hash = '#how-it-works';
    app.route();
    assert.equal(signal.aborted, true, 'a route aborts it');
    assert.equal(app.state.early, null);
    app.forgetMemory();
  }, (url, init) => (url.endsWith('?view=1') ? new Promise(() => {}) : Promise.resolve(response({ status: 404, body: { error: 'Not found.' } }))));
  // a first read that fails drops it (refused as out of date too); a document that is not a PDF drops it
  for (const [what, detail] of [['a first read that fails', () => Promise.resolve(response({ status: 503, body: { error: 'Unavailable.' } }))],
    ['a first read refused as out of date', () => Promise.resolve(response({ status: 409, body: { error_code: 'client_outdated', error: 'Reload.' } }))],
    ['a text document', () => Promise.resolve(response({ status: 200, body: fixture('encounter-awaiting-answer.json') }))]]) {
    await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
      const doc = what === 'a text document' ? fixture('encounter-awaiting-answer.json') : fixture('encounter-ready.json');
      Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), pdfStarted: true,
        viewHints: new Map([[doc.id, true]]) });
      global.location.hash = `#doc/${doc.id}`;
      app.route();
      const { signal } = fetches.find(item => item.url.endsWith('?view=1')).init;
      await settle(() => signal.aborted);
      assert.equal(signal.aborted, true, what);
      assert.equal(app.state.early, null, what);
      app.forgetMemory();
      app.state.outdated = false;
    }, (url, init) => (url.endsWith('?view=1') ? new Promise(() => {}) : detail(url, init)));
  }
  // a superseded route's first read, refused as out of date after the next route's view was asked for, leaves that view
  let release = null;
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
    const first = fixture('encounter-ready.json');
    const next = fixture('encounter-same-code.json');
    Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), pdfStarted: true,
      viewHints: new Map([[first.id, true], [next.id, true]]) });
    global.location.hash = `#doc/${first.id}`;
    app.route();
    global.location.hash = `#doc/${next.id}`;
    app.route();
    const view = fetches.find(item => item.url === `/api/encounters/${next.id}/original?view=1`);
    await settle(() => release !== null);
    release(response({ status: 409, body: { error_code: 'client_outdated', error: 'Reload.' } }));
    await settle(() => false);
    assert.deepEqual([view.init.signal.aborted, app.state.early?.view], [false, `/api/encounters/${next.id}/original?view=1`], 'the next route\'s view stands');
    app.forgetMemory();
    app.state.outdated = false;
  }, url => (url.endsWith('?view=1') ? new Promise(() => {}) : url.endsWith('f5000000-0000-4000-8000-000000000001')
    ? new Promise(resolve => { release = resolve; }) : new Promise(() => {})));
});

test('I1-1, I1-16: a Word document a later round refused draws no copy the page keeps - its detail names no view: no viewer, no converted note, no "Download PDF"; the copy is dropped, overwritten, whichever answer comes first - the click\'s view answered 404, or the detail drawn first and the view aborted - and when the open page\'s poll brings the refusal; nothing is drawn', async () => {
  const word = fixture('encounter-word.json');
  const view = `/api/encounters/${word.id}/original?view=1`;
  const refused = clone(word);  // the server's detail once a later round refused the file (customer.shown_view)
  Object.assign(refused.document, { view_url: null, view_media_type: null, converted: false, view_conversion: null });
  const panel = dom(app.viewerPanel(refused)).one('section.viewer-panel');
  assert.deepEqual([panel.one('#documentViewer'), panel.one('.viewer-note'), panel.one('#downloadOriginal')], [null, null, null],
    'no viewer, no converted note, no "Download PDF"');
  assert.equal(panel.one('#downloadWord').attr('data-word-original'), `${refused.document.original_url}?format=original`, 'the Word file by name');
  const tag = 'abcdef00-0000-4000-8000-000000000000';
  // the page's fetch as a browser's: a request whose signal aborts is rejected with an AbortError (refutation viewer-2:
  // a stand-in that ignores the signal hid the detail-first order)
  const browserFetch = answer => (url, init = {}) => new Promise((resolve, reject) => {
    init.signal?.addEventListener('abort', () => reject(Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' })));
    answer(url).then(resolve, reject);
  });
  // I1-16 (viewer-2): both orders of the click's two answers
  for (const order of ['the view\'s 404 first', 'the detail first']) {
    const library = fakeLibrary();
    const answered = [];
    let viewDone = null;
    const viewSettled = new Promise(resolve => { viewDone = resolve; });
    await withPdfPage(() => Promise.resolve(library.library), async ({ fetches }) => {
      Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), pdfStarted: true });
      const data = Uint8Array.from([37, 80, 68, 70]);
      app.keepView(view, tag, data);  // kept from an open before the refusal
      global.location.hash = `#doc/${word.id}`;
      app.route();
      assert.deepEqual(fetches.filter(item => item.url === view).map(item => item.init.headers['If-None-Match']),
        [`"${tag}"`], `${order}: the click asks once, with the tag it holds`);
      await settle(() => app.state.doc?.id === word.id && !app.state.keptViews.has(view));
      assert.equal(app.state.doc?.document?.view_url, null, order);
      assert.deepEqual(answered, order === 'the detail first' ? ['detail'] : ['view', 'detail'], `${order}: the answers' order`);
      assert.equal(fetches.find(item => item.url === view).init.signal.aborted, true, `${order}: the click's view let go of`);
      assert.deepEqual([app.state.viewer, app.state.early], [null, null], `${order}: no viewer mounted, no view left asked for`);
      assert.deepEqual([app.state.keptViews.has(view), [...data]], [false, [0, 0, 0, 0]], `${order}: the copy dropped and overwritten`);
      assert.equal(library.made.tasks.length, 0, `${order}: nothing drawn`);
      app.forgetMemory();
    }, browserFetch(url => {
      if (url === view) {
        if (order === 'the detail first') return new Promise(() => {});  // answered only after the detail: aborted first
        return taggedView(404, [], '').then(answer => { answered.push('view'); viewDone(); return answer; });
      }
      if (url === `/api/encounters/${word.id}`) {
        const detail = () => { answered.push('detail'); return response({ status: 200, body: refused }); };
        return order === 'the detail first' ? Promise.resolve().then(detail) : viewSettled.then(detail);
      }
      return new Promise(() => {});
    }));
  }
  // ... and the open document's poll that brings the refusal (another viewer key: the page is redrawn whole), which asks
  // for no view at all
  const library = fakeLibrary();
  await withPdfPage(() => Promise.resolve(library.library), async ({ fetches }) => {
    const data = Uint8Array.from([37, 80, 68, 70]);
    app.keepView(view, tag, data);  // drawn and kept while round 1's view stood
    Object.assign(app.state, { doc: word, route: { name: 'doc', id: word.id }, docKey: 'drawn', viewerKey: app.viewerKey(word) });
    app.renderDocument(refused, false);
    assert.deepEqual(fetches.filter(item => item.url === view), [], 'the poll: no view asked');
    assert.deepEqual([app.state.viewer, app.state.keptViews.has(view), [...data]], [null, false, [0, 0, 0, 0]],
      'the poll: no viewer, the copy dropped and overwritten');
    assert.equal(library.made.tasks.length, 0, 'the poll: nothing drawn');
    app.forgetMemory();
  });
});

test('R2-18: a document the server refuses (404: another practice\'s, or access ended) wipes page memory - the copies, the hints and the worker made ready ahead', async () => {
  const id = 'f5000000-0000-4000-8000-0000000000ff';
  await withPage({ answers: [{ match: (method, url) => url === `/api/encounters/${id}`, status: 404, body: { error: 'Not found.' } }] }, async ({ element }) => {
    const data = Uint8Array.from([37, 80]);
    app.keepView('/api/encounters/f5000000-0000-4000-8000-000000000001/original?view=1', 'abcdef00-0000-4000-8000-000000000000', data);
    app.state.viewHints = new Map([['f5000000-0000-4000-8000-000000000001', true]]);
    const thread = { terminated: false, terminate() { this.terminated = true; } };
    app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
    Object.assign(app.state, { route: { name: 'doc', id }, routeSerial: 9 });
    await app.loadDocument(id, 9, false);
    assert.match(element('#main').innerHTML, /This document is not available\./);
    assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby, thread.terminated], [0, [0, 0], 0, null, true]);
  });
  // ... and a 404 on a poll of the open document, on a refresh of it, or on a first read of a page out of date
  const busy = fixture('encounter-reading.json');
  const done = fixture('encounter-ready.json');
  assert.deepEqual([app.shouldPoll(busy), app.shouldPoll(done)], [true, false]);
  for (const [what, doc, run] of [['a poll', busy, () => app.loadDocument(busy.id, 21, true, true)], ['a refresh', done, () => app.loadDocument(done.id, 21, true)],
    ['a first read, the page out of date', done, () => app.loadDocument(done.id, 21, false)]]) {
    await withPage({ answers: [{ match: (method, url) => url === `/api/encounters/${doc.id}`, status: 404, body: { error: 'Not found.' } }] }, async () => {
      const data = Uint8Array.from([37, 80]);
      app.keepView(`/api/encounters/${doc.id}/original?view=1`, 'abcdef00-0000-4000-8000-000000000000', data);
      app.state.viewHints = new Map([[doc.id, true]]);
      const thread = { terminated: false, terminate() { this.terminated = true; } };
      app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
      const outdated = what.endsWith('out of date');
      Object.assign(app.state, { route: { name: 'doc', id: doc.id }, routeSerial: 21, doc: outdated ? null : doc, outdated });
      try {
        await run();
        assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby, thread.terminated], [0, [0, 0], 0, null, true], what);
      } finally {
        clearTimeout(app.state.poll.timer);
        app.state.poll.errors = 0;
      }
    });
  }
  // ... and a 404 to a route already left is an end that spares the view the route shown is opening: its early download
  // and its copy stand (R2-15, R2-16)
  for (const [what, serial, ahead] of [['a route already left', 30, 0]]) {
    await withPage({ answers: [{ match: (method, url) => url === `/api/encounters/${id}`, status: 404, body: { error: 'Not found.' } }] }, async () => {
      const next = 'f5000000-0000-4000-8000-000000000001';
      const view = `/api/encounters/${next}/original?view=1`;
      const data = Uint8Array.from([37, 80]);
      app.keepView(view, 'abcdef00-0000-4000-8000-000000000000', data);
      app.state.viewHints = new Map([[next, true]]);
      const thread = { terminated: false, terminate() { this.terminated = true; } };
      app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
      const early = { view, abort: new AbortController(), moved: null, result: new Promise(() => {}) };
      const applied = app.state.reads.applied;
      Object.assign(app.state, { early, route: { name: 'doc', id: next }, routeSerial: 31 });
      app.state.reads.applied = app.state.reads.asked + ahead;
      try {
        await app.loadDocument(id, serial, false);
        assert.deepEqual([app.state.keptViews.get(view)?.data === data, [...data], early.abort.signal.aborted, app.state.early === early,
          app.state.viewHints.size, app.state.pdfStandby, thread.terminated], [true, [37, 80], false, true, 0, null, true], what);
      } finally {
        app.state.reads.applied = applied;
        app.forgetMemory();
      }
    });
  }
  // ... and a 404 to a read older than the one shown - under the route's own serial, so the open document's own - wipes
  // everything, that document's own copy too
  await withPage({ answers: [{ match: (method, url) => url === `/api/encounters/${id}`, status: 404, body: { error: 'Not found.' } }] }, async () => {
    const view = `/api/encounters/${id}/original?view=1`;
    const data = Uint8Array.from([37, 80]);
    app.keepView(view, 'abcdef00-0000-4000-8000-000000000000', data);
    app.state.viewHints = new Map([[id, true]]);
    const thread = { terminated: false, terminate() { this.terminated = true; } };
    app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
    const viewer = app.state.viewer;
    const applied = app.state.reads.applied;
    Object.assign(app.state, { viewer: { view }, early: null, route: { name: 'doc', id }, routeSerial: 31 });
    app.state.reads.applied = app.state.reads.asked + 2;
    try {
      await app.loadDocument(id, 31, true, true);
      assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby, thread.terminated], [0, [0, 0], 0, null, true],
        'a read older than the one shown: its own copy goes too');
    } finally {
      Object.assign(app.state, { viewer });
      app.state.reads.applied = applied;
      app.forgetMemory();
    }
  });
});

// A route to a document the server refuses, left for a PDF before that 404 comes, while the PDF opens. `end`: the late 404
// after its viewer has mounted ('after') or before ('before'), pagehide meanwhile ('pagehide'), or none. What the open kept,
// whether the end was counted, and how the open and the re-open were asked (their If-None-Match).
async function lateEndOpen({ end = '', keptBefore = false } = {}) {
  const word = fixture('encounter-word.json');
  const view = word.document.view_url;
  const refused = 'f5000000-0000-4000-8000-0000000000ff';
  let refuse = null;
  const views = [];
  const out = {};
  const turns = async () => { for (let turn = 0; turn < 4; turn += 1) await settle(() => false); };
  const opened = () => Promise.resolve(fakeLibrary({ open: () => Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }) }).library);
  await withPdfPage(opened, async ({ element: find }) => {
    app.state.keptViews.clear();
    app.state.viewHints = new Map();
    Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), early: null });
    const kept = keptBefore ? Uint8Array.from([37, 80, 68, 70]) : null;
    if (kept) app.keepView(view, VIEW_TAG_A.slice(1, -1), kept);
    global.location.hash = `#doc/${refused}`;
    app.route();
    await settle(() => refuse !== null);
    global.location.hash = `#doc/${word.id}`;  // no worker has started here: no early view
    app.route();
    const wipes = app.state.wipes;
    if (end === 'before') {
      refuse(response({ status: 404, body: { error: 'Not found.' } }));
      await turns();
    }
    await mount(word, find, () => views.length === 1);
    if (end === 'after') refuse(response({ status: 404, body: { error: 'Not found.' } }));
    if (end === 'pagehide') app.forgetMemory(new Event('pagehide'));  // as window's pagehide listener calls it
    await turns();
    Object.assign(out, { kept: kept ? [...kept] : null, counted: app.state.wipes - wipes, open: views[0].tag });
    views[0].release(views[0].tag ? taggedView(304, [], views[0].tag) : taggedView(200, undefined, VIEW_TAG_A));
    await turns();
    out.keptAfterOpen = [...app.state.keptViews.keys()];
    global.location.hash = '#how-it-works';
    app.route();
    global.location.hash = `#doc/${word.id}`;
    app.route();
    await mount(word, find, () => views.length === 2);
    out.reopen = views[1].tag;
    // answered as the server answers: a 304 only to a re-open asked with its tag (an untagged one answered 304 is refused,
    // and its viewer's worker would wait out its time limit after this test)
    views[1].release(views[1].tag ? taggedView(304, [], views[1].tag) : taggedView(200, undefined, VIEW_TAG_A));
    await turns();
    app.forgetMemory();
  }, (url, init) => {
    if (url === `/api/encounters/${refused}`) return new Promise(resolve => { refuse = resolve; });
    if (url === view) return new Promise(resolve => { views.push({ tag: init?.headers?.['If-None-Match'] || '', release: resolve }); });
    return new Promise(() => {});
  });
  return out;
}

test('R2-18, R2-15: a late 404 to a route already left spares the open the route shown makes - its copy kept, the re-open asked with its tag - and pagehide meanwhile is still an end that keeps none', async () => {
  const view = fixture('encounter-word.json').document.view_url;
  assert.deepEqual(await lateEndOpen(), { kept: null, counted: 0, open: '', keptAfterOpen: [view], reopen: VIEW_TAG_A }, 'no end: the open kept, the re-open tagged');
  assert.deepEqual(await lateEndOpen({ end: 'after' }), { kept: null, counted: 0, open: '', keptAfterOpen: [view], reopen: VIEW_TAG_A },
    'the late 404 while the document opens for the first time: spared, not counted, the copy kept');
  assert.deepEqual(await lateEndOpen({ end: 'before', keptBefore: true }), { kept: [37, 80, 68, 70], counted: 0, open: VIEW_TAG_A, keptAfterOpen: [view], reopen: VIEW_TAG_A },
    'before its viewer mounts, no early view: the route\'s own copy spared, the open asked with its tag');
  assert.deepEqual(await lateEndOpen({ end: 'pagehide' }), { kept: null, counted: 1, open: '', keptAfterOpen: [], reopen: '' },
    'pagehide while it opens: an end, counted, no copy kept, the re-open downloads');
});

test('R2-18: a late 404 for a document the member has opened again is that document\'s own end: its kept copy and its early view go, and it is counted', async () => {
  const word = fixture('encounter-word.json');
  const view = word.document.view_url;
  for (const pdfStarted of [false, true]) {
    const reads = [];
    await withPdfPage(() => Promise.resolve(fakeLibrary().library), async () => {
      const data = Uint8Array.from([37, 80, 68, 70]);
      app.keepView(view, VIEW_TAG_A.slice(1, -1), data);
      Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now(), early: null, pdfStarted });
      global.location.hash = `#doc/${word.id}`;  // its read held
      app.route();
      await settle(() => reads.length === 1);
      global.location.hash = '#documents';
      app.route();
      global.location.hash = `#doc/${word.id}`;  // opened again, its read held too
      app.route();
      await settle(() => reads.length === 2);
      const early = app.state.early;  // with a worker started here, the re-open's view asked for with the click
      const wipes = app.state.wipes;
      reads[0](response({ status: 404, body: { error: 'Not found.' } }));  // the first read's late 404
      await settle(() => false);
      assert.deepEqual([app.state.keptViews.has(view), [...data], app.state.wipes - wipes, early ? early.abort.signal.aborted : null],
        [false, [0, 0, 0, 0], 1, pdfStarted ? true : null], `pdfStarted ${pdfStarted}: its own late 404 is an end, counted`);
      reads[1](response({ status: 503, body: { error: 'The service is not available right now.' } }));  // its new read fails
      await settle(() => false);
      assert.equal(app.state.keptViews.has(view), false, `pdfStarted ${pdfStarted}: still gone`);
      app.forgetMemory();
    }, (url, init) => {
      if (url === `/api/encounters/${word.id}`) return new Promise(resolve => { reads.push(resolve); });
      if (url === view) return new Promise((resolve, reject) => init.signal?.addEventListener('abort', () => reject(new Error('aborted'))));
      return new Promise(() => {});
    });
  }
});

test('R2-18: a 404 on a refresh or a poll of the open document while its own view is on the way is an end: once the document opens, no copy of it is kept, and the copy made is overwritten', async () => {
  const word = fixture('encounter-word.json');
  const view = word.document.view_url;
  const sliceOf = Object.getPrototypeOf(Uint8Array.prototype).slice;
  for (const [what, refuse] of [['a refresh', () => app.refreshDocument()], ['a poll', () => app.loadDocument(word.id, 51, true, true)], ['no end (the control)', null]]) {
    const copies = [];
    const opened = [];
    let release = null;
    // every array sliced while the document opens, the copy it keeps among them (data.slice(0), the view's 8 bytes)
    Object.defineProperty(Uint8Array.prototype, 'slice', { configurable: true, writable: true, value(...args) {
      const made = sliceOf.apply(this, args);
      copies.push(made);
      return made;
    } });
    try {
      await withPdfPage(() => Promise.resolve(fakeLibrary({ open: task => { opened.push(task); return Promise.resolve({ numPages: 1, getPage: () => new Promise(() => {}) }); } }).library),
        async ({ element: find }) => {
          Object.assign(app.state, { route: { name: 'doc', id: word.id }, routeSerial: 51 });
          await mount(word, find, () => release !== null);  // its own view on the way
          if (refuse) await refuse();  // the document's read answered 404
          release();
          await settle(() => opened.length === 1);
          await settle(() => false);
          const made = copies.filter(copy => copy.length === 8);
          assert.deepEqual([opened.length, made.length], [1, 1], `${what}: the document opens, as in release 1, and one copy is made`);
          assert.deepEqual([app.state.keptViews.size, app.state.keptViews.get(view)?.data === made[0], made[0].every(byte => byte === 0)],
            refuse ? [0, false, true] : [1, true, false], `${what}: ${refuse ? 'an end came while it opened: nothing kept, the copy overwritten' : 'kept'}`);
        }, url => (url === view ? new Promise(resolve => { release = () => resolve(taggedView(200, undefined, VIEW_TAG_A)); })
          : Promise.resolve(response({ status: 404, body: { error: 'Not found.' } }))));
    } finally {
      delete Uint8Array.prototype.slice;
      app.forgetMemory();
    }
  }
});

test('R2-18: a 404 that comes after the member has left the document is an end too - the copies, the hints, the worker made ready ahead - sparing only the view the route shown is opening', async () => {
  const refused = 'f5000000-0000-4000-8000-0000000000ff';  // another practice's: its details answer 404
  const own = 'f5000000-0000-4000-8000-000000000001';
  const ownView = `/api/encounters/${own}/original?view=1`;
  const tag = '0f0e0d0c-0b0a-4908-8706-050403020100';
  const keep = () => {
    const a = Uint8Array.from([37, 80, 68, 70]);
    const b = Uint8Array.from([1, 2, 3]);
    app.keepView(ownView, tag, a);
    app.keepView(OTHER_VIEW, 'abcdef00-0000-4000-8000-000000000000', b);
    app.state.viewHints = new Map([[OTHER_ID, true]]);
    const thread = { terminated: false, terminate() { this.terminated = true; } };
    app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
    Object.assign(app.state, { route: { name: 'documents' }, session: fixture('session.json'), sessionReadAt: Date.now() });
    return { a, b, thread };
  };
  const notFound = () => response({ status: 404, body: { error: 'Not found.' } });
  // the member routes to the refused document, then on to How it works before its 404 comes: everything goes
  let refuse = null;
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async () => {
    const { a, b, thread } = keep();
    global.location.hash = `#doc/${refused}`;
    app.route();
    await settle(() => refuse !== null);
    global.location.hash = '#how-it-works';
    app.route();
    refuse(notFound());
    await settle(() => false);
    assert.deepEqual([app.state.keptViews.size, [...a], [...b], app.state.viewHints.size, app.state.pdfStandby, thread.terminated],
      [0, [0, 0, 0, 0], [0, 0, 0], 0, null, true], 'left before its 404: an end');
    app.forgetMemory();
  }, url => (url === `/api/encounters/${refused}` ? new Promise(resolve => { refuse = resolve; }) : new Promise(() => {})));
  // ... or on to a document whose copy the page keeps, its re-open asked for with the click: that view alone stands
  refuse = null;
  let answer304 = null;
  await withPdfPage(() => Promise.resolve(fakeLibrary().library), async ({ fetches }) => {
    const { a, b, thread } = keep();
    app.state.pdfStarted = true;
    global.location.hash = `#doc/${refused}`;
    app.route();
    await settle(() => refuse !== null);
    global.location.hash = `#doc/${own}`;
    app.route();
    const early = app.state.early;
    assert.deepEqual([early?.view, fetches.find(item => item.url === ownView)?.init.headers['If-None-Match']], [ownView, `"${tag}"`], 'its re-open, asked for with the click');
    refuse(notFound());
    await settle(() => false);
    assert.deepEqual([app.state.keptViews.get(ownView)?.data === a, [...a], app.state.keptViews.has(OTHER_VIEW), [...b], app.state.early === early,
      early.abort.signal.aborted, app.state.viewHints.size, app.state.pdfStandby, thread.terminated],
    [true, [37, 80, 68, 70], false, [0, 0, 0], true, false, 0, null, true], 'the late 404: an end that spares the view the route shown is opening');
    answer304();
    const got = await early.result;
    assert.deepEqual([got.held, [...got.data]], [true, [37, 80, 68, 70]], 'its 304 drawn from the copy kept');
    app.forgetMemory();
  }, (url, init) => (url === `/api/encounters/${refused}` ? new Promise(resolve => { refuse = resolve; })
    : url === ownView ? new Promise((resolve, reject) => {
      answer304 = () => resolve(taggedView(304, [], `"${tag}"`));
      init.signal?.addEventListener('abort', () => reject(new Error('aborted')));
    }) : new Promise(() => {})));
});

test('R2-15: the dev preview tags a PDF view as the server does - a quoted UUID bound to the document, never the file\'s hash - and reads If-None-Match as studio.api does', () => {
  const crypto = require('node:crypto');
  const { bytes } = preview.viewBytes('synthetic-egd-colonoscopy.pdf');
  const tag = preview.viewTag('f5000000-0000-4000-8000-000000000001', bytes);
  assert.match(tag, /^"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"$/);
  assert.notEqual(tag.replace(/[-"]/g, ''), crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 32), 'never the file\'s own hash');
  assert.notEqual(preview.viewTag('f4000000-0000-4000-8000-000000000001', bytes), tag, 'bound to the document');
  assert.equal(preview.viewTag('f5000000-0000-4000-8000-000000000001', bytes), tag, 'the same document, the same tag');
  for (const [header, held] of [[tag, true], [`W/${tag}`, true], [`"other", ${tag}`, true], ['*', false], ['', false], [undefined, false], [tag.slice(1, -1), false]]) {
    assert.equal(preview.namesTag(header, tag), held, String(header));
  }
});

// --- R2-22: the lists a page at a time, and the search (the critics' C2 and C7) -----------------------------------------

// `count` synthetic list rows, newest first: row n (from 1) is 'Synthetic polyp report n' where n is a multiple of 3, else
// 'Synthetic document n'; odd rows wait for approval (the queue's), even ones are reviewed; with `opensPdf`, odd rows say
// they open as a PDF.
function listRowsOf(count, { opensPdf = false } = {}) {
  return Array.from({ length: count }, (_, index) => {
    const n = index + 1;
    return { id: `f0000000-0000-4000-8000-${String(n).padStart(12, '0')}`, title: n % 3 === 0 ? `Synthetic polyp report ${n}` : `Synthetic document ${n}`,
      state: n % 2 ? 'ready' : 'reviewed', state_label: n % 2 ? 'Ready for approval' : 'Reviewed', service_date: '2026-11-02', insurance: 'medicare',
      created_at: new Date(Date.UTC(2026, 10, 20) - n * 60000).toISOString().replace('.000', ''), kind: 'upload', ...(opensPdf ? { opens_pdf: n % 2 === 1 } : {}) };
  });
}

// A row's text as the page's search reads it (release 1's rule: the row's own text, lower-cased).
const listText = row => dom(app.documentRow(row)).text.toLowerCase();

// A server that pages `rows` as release 2's does (R2-19, R2-20): pages of 50 (the queue's waiting rows; the Overview's
// recent 5); next is the last row's place ('c<index>' here: the page reads a cursor as a place only); total on a first
// page of the documents or the queue; the search answers the rows whose text holds the words, 50 at a time, total null.
// `release1`: the whole list, to any address. `refuse(method, url, body)` may answer instead.
function pagedServer(rows, { release1 = false, refuse = null } = {}) {
  const pageOf = (list, start, first) => ({ status: 200, body: { encounters: list.slice(start, start + 50), next: start + 50 < list.length ? `c${start + 50}` : null,
    total: first ? list.length : null } });
  return (method, url, body) => {
    const refused = refuse?.(method, url, body);
    if (refused) return refused;
    const where = new URL(url, 'http://studio.test');
    if (method === 'GET' && where.pathname === '/api/encounters') {
      if (release1) return { status: 200, body: { encounters: rows } };
      const which = where.searchParams.get('list') || 'documents';
      const before = where.searchParams.get('before');
      if (which === 'recent') return { status: 200, body: { encounters: rows.slice(0, 5), next: null, total: null } };
      const list = which === 'queue' ? rows.filter(row => ['awaiting_answer', 'needs_review', 'ready'].includes(row.state)) : rows;
      return pageOf(list, before ? Number(before.slice(1)) : 0, !before);
    }
    if (method === 'POST' && where.pathname === '/api/encounters/search') {
      const answer = pageOf(rows.filter(row => listText(row).includes(body.text.toLowerCase())), body.before ? Number(body.before.slice(1)) : 0, false);
      return answer;
    }
    return { status: 404, body: { error: 'Not found.' } };
  };
}

// A server's answers, some held until the test lets them through (holdWhen(method, url, body) says which).
function holding(answer) {
  const waiting = [];
  let hold = () => false;
  return {
    waiting,
    holdWhen(fn) { hold = fn; },
    answer: (method, url, body) => {
      const reply = answer(method, url, body);
      return hold(method, url, body) ? new Promise(resolve => waiting.push({ url, body, release: () => resolve(reply) })) : reply;
    },
  };
}

// A list view's page: #documentsTable holds the rows the page's markup draws (each {href, textContent, hidden}), takes the
// rows a template brings, and #searchEmpty once the page has added it; #listMore and the search box; an
// IntersectionObserver the test drives (near(): the list's end near the window, as the browser calls back); a fetch
// answered by `answer(method, url, body)` and recorded; Web Storage that records any use. fn gets them all.
async function withListPage(answer, fn, { observer = true } = {}) {
  const saved = { IntersectionObserver: global.IntersectionObserver, localStorage: Object.getOwnPropertyDescriptor(global, 'localStorage'),
    sessionStorage: Object.getOwnPropertyDescriptor(global, 'sessionStorage') };
  const observers = [];
  global.IntersectionObserver = observer ? class {
    constructor(callback, options) { Object.assign(this, { callback, options, targets: new Set(), disconnected: false }); observers.push(this); }

    observe(target) { this.targets.add(target); }

    unobserve(target) { this.targets.delete(target); }

    disconnect() { this.targets.clear(); this.disconnected = true; }
  } : undefined;
  const near = (on = true) => { for (const io of observers) if (!io.disconnected && io.targets.size) io.callback([...io.targets].map(target => ({ target, isIntersecting: on }))); };
  const storage = [];
  const recording = name => ({ getItem: key => { storage.push([name, 'get', key]); return null; }, setItem: key => storage.push([name, 'set', key]),
    removeItem: key => storage.push([name, 'remove', key]), clear: () => storage.push([name, 'clear']), key: () => null, length: 0 });
  Object.defineProperty(global, 'localStorage', { value: recording('localStorage'), configurable: true, writable: true });
  Object.defineProperty(global, 'sessionStorage', { value: recording('sessionStorage'), configurable: true, writable: true });
  try {
    await withPage({}, async page => {
      const calls = [];
      const rowsOf = html => dom(html).all('a.document-row').map(row => ({ href: row.attr('href'), textContent: row.text, hidden: false }));
      const empty = { id: '', className: '', textContent: '', attached: false, remove() { this.attached = false; } };
      let html = '';
      const table = {
        rows: [],
        get innerHTML() { return html; },
        set innerHTML(value) { html = value; this.rows = rowsOf(value); empty.attached = false; },
        append(content) { this.rows.push(...content.rows); },
        appendChild(node) { if (node === empty) empty.attached = true; },
      };
      const more = fakeElement({ innerHTML: '', hidden: true });
      const search = fakeElement({ id: 'documentSearch', value: '' });
      const own = { documentsTable: table, listMore: more, documentSearch: search };
      const element = page.element;
      global.document.querySelector = selector => {
        if (selector === '#searchEmpty') return empty.attached ? empty : null;
        const id = selector.startsWith('#') ? selector.slice(1) : '';
        return Object.hasOwn(own, id) ? own[id] : element(selector);
      };
      global.document.querySelectorAll = selector => (selector === '#documentsTable .document-row' ? table.rows : []);
      global.document.createElement = tag => (tag === 'template' ? { set innerHTML(value) { this.content = { rows: rowsOf(value) }; } } : tag === 'p' ? empty : fakeElement());
      global.fetch = async (url, init = {}) => {
        const method = init.method || 'GET';
        calls.push({ url, method, body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined, headers: init.headers });
        return response(await answer(method, url, typeof init.body === 'string' ? JSON.parse(init.body) : undefined));
      };
      const type = words => { search.value = words; app.onInput({ target: search }); };
      const shown = () => table.rows.filter(row => !row.hidden);
      await fn({ ...page, calls, table, more, search, empty, near, observers, type, shown, storage });
    });
  } finally {
    app.closeList();
    global.IntersectionObserver = saved.IntersectionObserver;
    for (const name of ['localStorage', 'sessionStorage']) {
      if (saved[name]) Object.defineProperty(global, name, saved[name]);
      else delete global[name];
    }
  }
}

const hrefOf = row => `#doc/${encodeURIComponent(row.id)}`;

test('R2-22: the list addresses; listPage reads either server\'s answer and refuses a bad one; the description counts the list', () => {
  assert.deepEqual(app.LIST_ADDRESS, { workspace: '/api/encounters?list=recent', documents: '/api/encounters?list=documents', queue: '/api/encounters?list=queue' });
  assert.deepEqual([app.SEARCH_URL, app.SEARCH_PAUSE_MS, app.AUTO_PAGES, app.LOCAL_SEARCH_MAX, app.MORE_TEXT], ['/api/encounters/search', 300, 3, 200, 'Show more documents']);
  const rows = fixture('encounters.json').encounters;
  assert.deepEqual(app.listPage({ encounters: rows }), { rows, next: null, total: null, workspace: null }, 'release 1\'s answer: one whole page');
  assert.deepEqual(app.listPage(rows), { rows, next: null, total: null, workspace: null }, 'a bare list too');
  assert.deepEqual(app.listPage({ encounters: rows.slice(0, 2), next: 'c2', total: 12, workspace: 'w-a' }), { rows: rows.slice(0, 2), next: 'c2', total: 12, workspace: 'w-a' },
    'the practice it was read in (I1-2)');
  assert.deepEqual(app.listPage({ encounters: [], next: null, total: 0 }), { rows: [], next: null, total: 0, workspace: null });
  assert.deepEqual(app.listPage({ encounters: [null, 7, 'x', rows[0]] }).rows, [rows[0]], 'a row that is no object is never drawn');
  for (const bad of [null, 7, {}, { encounters: {} }, { encounters: [], next: 7 }, { encounters: [], next: {} }, { encounters: [], total: -1 },
    { encounters: [], total: 1.5 }, { encounters: [], total: '12' }, { encounters: [], workspace: 7 }, { encounters: [], workspace: {} }]) {
    assert.throws(() => app.listPage(bad), { message: 'The server answered with a document list this page cannot read.' }, JSON.stringify(bad));
  }
  assert.equal(app.listDescription('queue', 6), '6 documents wait on you: questions to answer, or codes to review or approve.');
  assert.equal(app.listDescription('queue', 1), 'One document waits on you: questions to answer, or codes to review or approve.');
  assert.equal(app.listDescription('queue', 0), 'No document waits on you for an answer or a decision.');
  assert.equal(app.listDescription('documents', 117), '117 synthetic documents in this workspace.');
  assert.equal(app.listDescription('documents', 1), '1 synthetic document in this workspace.');
  assert.match(app.documentsView('documents'), /<\/div><div class="list-more" id="listMore" hidden><\/div><p class="checks-disclaimer">/, 'the list\'s end follows the table');
  const css = fs.readFileSync(STYLES, 'utf8').slice(32785);
  assert.match(css, /\.list-more\{[^}]*min-height:1px/, 'kept in the layout while empty, so it can be seen nearing the window');
});

test('R2-22: each list asks for its own first page; release 1\'s whole answer is drawn as before; a total sets the description and the list\'s own sidebar number', async () => {
  const rows = fixture('encounters.json').encounters;
  for (const [name, address, drawn, description] of [['documents', '/api/encounters?list=documents', 12, '12 synthetic documents in this workspace.'],
    ['queue', '/api/encounters?list=queue', 6, '6 documents wait on you: questions to answer, or codes to review or approve.'], ['workspace', '/api/encounters?list=recent', 5, null]]) {
    await withListPage(pagedServer(rows, { release1: true }), async ({ calls, table, more, observers, element }) => {
      app.state.routeSerial = 5;
      await app.showList(name, 5);
      assert.deepEqual(calls.map(call => call.url), [address], name);
      assert.equal(table.rows.length, drawn, name);
      if (description) assert.equal(element('#listDescription').textContent, description, name);
      assert.equal(more.hidden, true, `${name}: nothing more follows`);
      assert.equal(observers.length, 0, `${name}: nothing watched`);
      assert.deepEqual([element('#documentsCount').textContent, element('#queueCount').textContent], ['', ''], `${name}: the session's numbers stand`);
    });
  }
  const many = listRowsOf(117);
  await withListPage(pagedServer(many), async ({ calls, table, more, observers, element }) => {
    app.state.routeSerial = 6;
    await app.showList('documents', 6);
    assert.deepEqual(calls.map(call => call.url), ['/api/encounters?list=documents']);
    assert.deepEqual(table.rows.map(row => row.href), many.slice(0, 50).map(hrefOf));
    assert.equal(element('#listDescription').textContent, '117 synthetic documents in this workspace.');
    assert.equal(element('#documentsCount').textContent, '117', 'the list\'s own sidebar number');
    assert.equal(more.hidden, false, 'the end shows, empty, so it can be watched');
    assert.equal(more.innerHTML, '', 'no button while automatic loads remain');
    assert.equal(observers.length, 1);
    assert.deepEqual([[...observers[0].targets], observers[0].options], [[more], { rootMargin: '600px 0px' }]);
  });
  await withListPage(pagedServer(many), async ({ calls, element }) => {
    app.state.routeSerial = 7;
    await app.showList('queue', 7);
    assert.deepEqual(calls.map(call => call.url), ['/api/encounters?list=queue']);
    const waiting = many.filter(row => row.state === 'ready').length;
    assert.equal(element('#queueCount').textContent, String(waiting));
    assert.equal(element('#listDescription').textContent, `${waiting} documents wait on you: questions to answer, or codes to review or approve.`);
  });
});

test('R2-22, C7: up to three pages load as the list\'s end nears the window, the budget counted as each starts; then "Show more documents", while more rows follow', async () => {
  const rows = listRowsOf(260);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, table, more, near }) => {
    app.state.routeSerial = 8;
    await app.showList('documents', 8);
    const pages = () => calls.filter(call => call.url.includes('&before='));
    server.holdWhen((method, url) => url.includes('&before='));
    near(true);
    assert.deepEqual(pages().map(call => call.url), ['/api/encounters?list=documents&before=c50'], 'the end near: the next page');
    near(true);
    near(true);
    assert.equal(pages().length, 1, 'one at a time: the observer answering while a page loads starts nothing');
    assert.equal(app.state.list.browse.auto, 1, 'and costs no automatic load');
    server.waiting.shift().release();
    await settle(() => table.rows.length === 100);
    assert.deepEqual(table.rows.map(row => row.href), rows.slice(0, 100).map(hrefOf), 'appended in order');
    assert.equal(more.innerHTML, '', 'still no button: automatic loads remain');
    near(false);
    await settle(() => false);
    assert.equal(pages().length, 1, 'the end away from the window: nothing');
    for (const [expected, auto] of [[150, 2], [200, 3]]) {
      near(true);
      server.waiting.shift().release();
      await settle(() => table.rows.length === expected);
      assert.equal(app.state.list.browse.auto, auto);
      if (auto < 3) assert.equal(more.innerHTML, '', `${expected}: no button yet`);
    }
    assert.match(more.innerHTML, /<button type="button" class="button secondary" data-action="more-documents">Show more documents<\/button>/, 'the three used up and more follow: the button');
    near(true);
    await settle(() => false);
    assert.equal(pages().length, 3, 'from then on only the button loads more');
    server.holdWhen(() => false);
    click('[data-action]', { action: 'more-documents' });
    await settle(() => table.rows.length === 250);
    assert.match(more.innerHTML, /Show more documents/, 'more follow: it stays');
    click('[data-action]', { action: 'more-documents' });
    await settle(() => table.rows.length === 260);
    assert.deepEqual([more.innerHTML, more.hidden], ['', true], 'the end of the list: no button');
    assert.deepEqual(table.rows.map(row => row.href), rows.map(hrefOf), 'every row once, in order');
  });
  // exactly 200 documents: the three automatic pages bring the whole list, and no button is ever added
  await withListPage(pagedServer(listRowsOf(200)), async ({ table, more, near }) => {
    app.state.routeSerial = 9;
    await app.showList('documents', 9);
    for (const expected of [100, 150, 200]) {
      near(true);
      await settle(() => table.rows.length === expected);
    }
    assert.deepEqual([more.innerHTML, more.hidden], ['', true]);
  });
});

test('R2-22, C7: a failed automatic load says why under the list and adds the button; a failed button load leaves it; without IntersectionObserver, the button from 51 documents', async () => {
  let refusal = { status: 503, body: { error: 'The service is not available right now.' } };
  const server = pagedServer(listRowsOf(160), { refuse: (method, url) => (refusal && url.includes('&before=') ? refusal : null) });
  await withListPage(server, async ({ calls, table, more, near }) => {
    app.state.routeSerial = 10;
    await app.showList('documents', 10);
    near(true);
    await settle(() => /Show more documents/.test(more.innerHTML));
    assert.match(more.innerHTML, /<p class="empty-state" role="status">Documents could not be loaded\. The service is not available right now\.<\/p>/);
    assert.match(more.innerHTML, /Show more documents/, 'a failed automatic load adds the button');
    assert.equal(app.state.list.browse.auto, 1, 'though two automatic loads remained');
    const asked = calls.length;
    near(true);
    await settle(() => false);
    assert.equal(calls.length, asked, 'from then on only the button loads more');
    refusal = { status: 429, body: { error: 'rate_limited', retry_after: 30 } };
    click('[data-action]', { action: 'more-documents' });
    await settle(() => calls.length === asked + 1 && !app.state.list.loading);
    assert.match(more.innerHTML, /Documents could not be loaded\. Too many requests in a short time\. Wait a minute and try again\./, 'the limit in its own words');
    assert.match(more.innerHTML, /Show more documents/, 'a failed button load leaves it');
    refusal = null;
    click('[data-action]', { action: 'more-documents' });
    await settle(() => table.rows.length === 100);
    assert.doesNotMatch(more.innerHTML, /could not be loaded/, 'loaded: the sentence goes');
    assert.match(more.innerHTML, /Show more documents/, 'and the button stays while more follow');
  });
  await withListPage(pagedServer(listRowsOf(51)), async ({ table, more, observers }) => {
    app.state.routeSerial = 11;
    await app.showList('documents', 11);
    assert.equal(observers.length, 0, 'nothing is watched');
    assert.match(more.innerHTML, /Show more documents/, 'the button, from the first page');
    click('[data-action]', { action: 'more-documents' });
    await settle(() => table.rows.length === 51);
    assert.equal(more.innerHTML, '');
  }, { observer: false });
});

test('R2-22, C2: up to 200 documents the first input loads the rest of the list, one page at a time, each as a page; the search then runs in the page with release 1\'s rule, with no request per key', async () => {
  const rows = listRowsOf(200);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, table, empty, type, shown, storage }) => {
    app.state.routeSerial = 12;
    await app.showList('documents', 12);
    server.holdWhen((method, url) => url.includes('&before='));
    type('polyp report 19');
    const pages = () => calls.filter(call => call.url.includes('&before='));
    assert.deepEqual(pages().map(call => call.url), ['/api/encounters?list=documents&before=c50'], 'the first input: the next page not yet loaded');
    assert.equal(shown().length, 0, 'the rows on the page are filtered at once');
    assert.deepEqual([empty.attached, empty.textContent], [true, 'Loading documents…'], 'and nothing is said not to match while more may');
    for (const expected of [100, 150]) {
      server.waiting.shift().release();
      await settle(() => table.rows.length === expected && pages().length === expected / 50);
      assert.equal(pages().length, expected / 50, 'one at a time');
    }
    server.waiting.shift().release();
    await settle(() => table.rows.length === 200 && !app.state.list.loading);
    assert.deepEqual(pages().map(call => call.url), ['c50', 'c100', 'c150'].map(cursor => `/api/encounters?list=documents&before=${cursor}`), 'each later page, in order');
    assert.equal(calls.filter(call => call.url === app.SEARCH_URL).length, 0, 'no search request');
    const expect = words => rows.filter(row => listText(row).includes(words)).map(hrefOf);
    assert.deepEqual(shown().map(row => row.href), expect('polyp report 19'), 'the rows of a page that arrived later are filtered as they are added');
    assert.equal(empty.attached, false);
    const before = calls.length;
    for (const words of ['polyp report 99', 'POLYP', ' synthetic document 7 ', 'reviewed']) {
      type(words);
      assert.deepEqual(shown().map(row => row.href), expect(words.toLowerCase().trim()), words);
    }
    assert.equal(calls.length, before, 'no request per key');
    type('nothing like this');
    assert.deepEqual([empty.attached, empty.textContent], [true, 'No documents match your search.'], 'said once nothing more can match');
    type('');
    assert.equal(shown().length, 200, 'cleared: every row again, from page memory');
    assert.equal(empty.attached, false);
    assert.deepEqual(storage, [], 'nothing in the browser\'s storage');
  });
  // a server before release 2: its whole list is searched in the page, with no request at all
  await withListPage(pagedServer(listRowsOf(240), { release1: true }), async ({ calls, type, shown }) => {
    app.state.routeSerial = 13;
    await app.showList('documents', 13);
    type('polyp');
    await settle(() => false);
    assert.equal(calls.length, 1, 'the whole list was read once');
    assert.equal(shown().length, 80);
  });
});

test('R2-22, C2: above 200 documents the server is asked after a 300 ms pause, one search at a time, the newest words winning; a narrowing of a complete answer asks nothing; clearing shows the list again', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(260);
  const expect = words => rows.filter(row => listText(row).includes(words)).map(hrefOf);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, table, empty, type, shown, storage }) => {
    app.state.routeSerial = 14;
    await app.showList('documents', 14);
    const searches = () => calls.filter(call => call.url === app.SEARCH_URL);
    server.holdWhen(method => method === 'POST');
    type('polyp');
    assert.deepEqual(shown().map(row => row.href), rows.slice(0, 50).filter(row => listText(row).includes('polyp')).map(hrefOf), 'the rows on the page, filtered at once');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS - 1);
    assert.equal(searches().length, 0, 'nothing before the pause');
    t.mock.timers.tick(1);
    assert.equal(searches().length, 1);
    assert.deepEqual([searches()[0].method, searches()[0].body, searches()[0].headers['X-CSRFToken']], ['POST', { text: 'polyp', before: null }, 'token123'],
      'the words in a POST body, with the CSRF header');
    // words typed while it is asked: one search at a time, and its answer, theirs no more, is never drawn
    type('polyp report 2');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    assert.equal(searches().length, 1, 'one search at a time');
    server.waiting.shift().release();
    await settle(() => searches().length === 2);
    assert.deepEqual(searches()[1].body, { text: 'polyp report 2', before: null }, 'the newest words, asked at once: their pause has passed');
    assert.equal(app.state.list.found, null, 'the older answer was not taken');
    server.waiting.shift().release();
    await settle(() => app.state.list.found?.query === 'polyp report 2');
    assert.deepEqual(table.rows.map(row => row.href), expect('polyp report 2'), 'every match, from the server');
    // narrower words, every match on the page: nothing is asked
    type('polyp report 21');
    t.mock.timers.tick(1000);
    assert.equal(searches().length, 2, 'a narrowing of a complete answer asks nothing');
    assert.deepEqual(shown().map(row => row.href), expect('polyp report 21'));
    // other words: the list's own rows again at once, and the server asked after the pause
    type('nothing like this');
    assert.deepEqual(table.rows.map(row => row.href), rows.slice(0, 50).map(hrefOf), 'the list\'s rows again');
    assert.deepEqual([empty.attached, empty.textContent], [true, 'Loading documents…'], 'no match is said while more may lie beyond');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    server.waiting.shift().release();
    await settle(() => app.state.list.found?.query === 'nothing like this');
    assert.deepEqual([empty.attached, empty.textContent], [true, 'No documents match your search.'], 'said once nothing more can match');
    type('');
    t.mock.timers.tick(1000);
    assert.equal(shown().length, 50, 'cleared: the list\'s rows again, from page memory');
    assert.equal(searches().length, 3);
    // every form of the words typed - as typed, case-blind, percent- or plus-encoded, base64 or base64url at any byte
    // alignment - in no request's address and no request header (integrated refutation round 1, phileak-0)
    const typed = ['polyp', 'polyp report 2', 'polyp report 21', 'nothing like this'];
    assert.deepEqual(calls.flatMap(call => searchMarkerHits(`${call.url}\n${JSON.stringify(call.headers ?? {})}`, typed)), [],
      'the words are never in an address or a header');
    for (const form of searchMarkerForms('polyp report 2')) {  // the control: each form, in an address, is found
      assert.ok(searchMarkerHits(`/api/encounters?q=${encodeURIComponent(form)}`, ['polyp report 2']).length, form);
    }
    assert.deepEqual(storage, [], 'nothing in the browser\'s storage');
  });
});

// Every form of a typed word a no-leak guard looks for (integrated refutation round 1, phileak-0), as the bench's
// markerForms reads a marker (ops/bench/bench.cjs, records[4]): the word as typed and case-folded, and its base64 and
// base64url cores at the three byte alignments.
function searchMarkerForms(word) {
  const forms = new Set([word, word.toLowerCase()]);
  const bytes = Buffer.from(word, 'utf8');
  for (let pad = 0; pad < 3; pad += 1) {
    const b64 = Buffer.concat([Buffer.alloc(pad), bytes]).toString('base64');
    const core = b64.slice(Math.ceil(pad * 4 / 3), Math.floor((pad + bytes.length) * 4 / 3));
    forms.add(core);
    forms.add(core.replace(/\+/g, '-').replace(/\//g, '_'));
  }
  return [...forms];
}

// The forms of `words` in `text`, read as it is and percent- and plus-decoded: a word's own forms case-blind, a base64
// core as written (its case is its content).
function searchMarkerHits(text, words) {
  const raw = String(text);
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw.replace(/\+/g, ' '));
  } catch {
    // not percent-encoded text: read as it is
  }
  const readings = [raw, decoded];
  return words.flatMap(word => searchMarkerForms(word).filter(form => ([word, word.toLowerCase()].includes(form)
    ? readings.some(reading => reading.toLowerCase().includes(form.toLowerCase()))
    : readings.some(reading => reading.includes(form)))));
}

// Release 1's web after a switch-back has no search route: Django's own HTML 404, as measured on 816045c7 (rollback-0).
const RELEASE_1_NOT_FOUND = { status: 404, type: 'text/html; charset=utf-8', body: '\n<!doctype html>\n<html lang="en">\n<head>\n  <title>Not Found</title>\n</head>\n<body>\n  <h1>Not Found</h1><p>The requested resource was not found on this server.</p>\n</body>\n</html>\n' };

test('I1-3 (rollback-0): after a switch-back, release 1\'s HTML 404 to a search reads as an update - the notice, the list\'s rows kept, never "Not found" - while release 2\'s own JSON 404 and an HTML 404 elsewhere stay not found', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(260);
  let flipped = false;  // release 1's web takes over once the first page is drawn: 409 to every API call, its 404 to the search
  const server = pagedServer(rows, { refuse: (method, url) => (!flipped ? null : url === app.SEARCH_URL ? RELEASE_1_NOT_FOUND
    : { status: 409, body: { error_code: 'client_outdated', error: 'Reload.' } }) });
  await withListPage(server, async ({ calls, element, more, type, shown }) => {
    app.state.routeSerial = 31;
    await app.showList('documents', 31);
    assert.equal(app.state.list.local, false, 'above 200 documents: the server is asked');
    element('#updateNotice').hidden = true;
    flipped = true;
    type('polyp report 99');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.refused !== '');
    assert.deepEqual(calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body), [{ text: 'polyp report 99', before: null }]);
    assert.deepEqual([app.state.outdated, element('#updateNotice').hidden], [true, false], 'the update notice');
    assert.equal(app.state.list.refused, app.OUTDATED_TEXT);
    assert.ok(!more.innerHTML.includes('Not found'), 'never "Not found" about a document that is in the practice');
    assert.equal(shown().length, rows.slice(0, 50).filter(row => listText(row).includes('polyp report 99')).length, 'the page\'s own matches stay');
  });
  app.state.outdated = false;
  // the search's later page meets it the same way; release 2's own JSON 404, and an HTML 404 anywhere else, are not found
  for (const [what, path, answer, said] of [['a later page of the search', app.SEARCH_URL, RELEASE_1_NOT_FOUND, app.OUTDATED_TEXT],
    ['release 2\'s own 404 to the search', app.SEARCH_URL, { status: 404, body: { error: 'Not found.' } }, 'Not found.'],
    ['an HTML 404 to another address', '/api/encounters/x', RELEASE_1_NOT_FOUND, 'Not found, or not in your workspace.']]) {
    const outdated = said === app.OUTDATED_TEXT;
    await withPage({ elements: { updateNotice: fakeElement({ hidden: true }) }, answers: [{ match: () => true, ...answer }] }, async ({ element }) => {
      const method = path === app.SEARCH_URL ? 'POST' : 'GET';
      await assert.rejects(app.api(path, { method, json: method === 'POST' ? { text: 'x', before: 'c50' } : undefined }),
        { message: said }, what);
      assert.deepEqual([app.state.outdated, element('#updateNotice').hidden], [outdated, !outdated], what);
    });
    app.state.outdated = false;
  }
});

// Two practices a member is active in (exact-0): each answers as release 2's server does, naming the practice read, and
// `active` is the member's active practice at each request (the oldest active membership: A until A's owner turns the
// member's access to A off). A cursor is a position only, so A's cursor read in B pages B's rows.
function twoPractices(count) {
  const rows = { A: listRowsOf(count) };
  rows.B = rows.A.map(row => ({ ...row, id: row.id.replace(/^f0/, 'b0'), title: row.title.replace('Synthetic', 'Synthetic B') }));
  const ids = { A: 'fa000000-0000-4000-8000-0000000000a1', B: 'fa000000-0000-4000-8000-0000000000b1' };
  const servers = { A: pagedServer(rows.A), B: pagedServer(rows.B) };
  const practice = { active: 'A', rows, ids };
  practice.answer = (method, url, body) => {
    const session = fixture('session.json');
    if (url === '/api/session') return { status: 200, body: { ...session, workspace: { ...session.workspace, id: ids[practice.active] } } };
    const reply = servers[practice.active](method, url, body);
    return reply.status === 200 ? { ...reply, body: { ...reply.body, workspace: ids[practice.active] } } : reply;
  };
  return practice;
}

test('I1-2 (exact-0): a later page or a search that names another practice than the list\'s first page is never drawn - nothing appended or shown under it - and the route is read afresh, with the session', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ofB = row => row.href.startsWith('#doc/b0');
  // later pages of the list (110 documents: two more pages, each loaded as its end comes near)
  const later = twoPractices(110);
  await withListPage(later.answer, async ({ calls, table, near }) => {
    global.location.hash = '#documents';
    app.state.routeSerial = 41;
    await app.showList('documents', 41);
    const first = app.state.list;
    assert.deepEqual([first.workspace, table.rows.length, table.rows.some(ofB)], [later.ids.A, 50, false]);
    const appended = [];
    const append = table.append.bind(table);
    table.append = content => { appended.push(...content.rows); append(content); };
    near();  // a later page of A, named A: appended, as before
    await settle(() => appended.length === 50);
    assert.deepEqual(appended.map(row => row.href), later.rows.A.slice(50, 100).map(hrefOf), 'the list\'s own practice: appended');
    assert.equal(app.state.list, first);
    later.active = 'B';  // A's owner turns the member's access to A off: B is the member's active practice now
    const at = calls.length;
    near();
    await settle(() => app.state.list !== first && app.state.list?.loaded);
    assert.ok(calls.some(call => call.url === '/api/encounters?list=documents&before=c100'), 'the later page was asked, and answered by B');
    assert.equal(appended.length, 50, 'none of B\'s rows appended to A\'s list');
    assert.ok(calls.slice(at).some(call => call.url === '/api/session'), 'the session read again');
    assert.equal(app.state.list.workspace, later.ids.B, 'the route drawn afresh: B\'s own list');
    assert.deepEqual(table.rows.map(row => row.href), later.rows.B.slice(0, 50).map(hrefOf), 'B\'s first page, from its start');
    assert.equal(first.observer.disconnected, true, 'A\'s list closed');
  });
  // a search (above 200 documents, on the server): its first page, then a later page of an answer A gave
  for (const what of ['first', 'later']) {
    const search = twoPractices(260);
    await withListPage(search.answer, async ({ calls, table, type, near }) => {
      global.location.hash = '#documents';
      app.state.routeSerial = 42;
      await app.showList('documents', 42);
      const first = app.state.list;
      assert.equal(first.local, false);
      if (what === 'later') {  // A answers the search's first page; B its next
        type('Synthetic');
        t.mock.timers.tick(app.SEARCH_PAUSE_MS);
        await settle(() => first.found?.query === 'synthetic');
        assert.equal(first.found.next, 'c50');
      }
      const drawn = [];
      const own = Object.getOwnPropertyDescriptor(table, 'innerHTML');
      Object.defineProperty(table, 'innerHTML', { get: own.get, set(value) { drawn.push(value); own.set.call(this, value); }, configurable: true });
      const appended = [];
      const append = table.append.bind(table);
      table.append = content => { appended.push(...content.rows); append(content); };
      search.active = 'B';
      const at = calls.length;
      if (what === 'first') {
        type('polyp report 9');
        t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      } else {
        near();
      }
      await settle(() => app.state.list !== first && app.state.list?.loaded);
      const asked = calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body);
      assert.deepEqual(asked.at(-1), what === 'first' ? { text: 'polyp report 9', before: null } : { text: 'Synthetic', before: 'c50' }, what);
      assert.deepEqual(appended, [], `${what}: none of B's rows appended`);
      assert.equal(drawn.length, 1, `${what}: the table drawn once, by B's own list`);
      assert.deepEqual(dom(drawn[0]).all('a.document-row').map(row => row.attr('href')), search.rows.B.slice(0, 50).map(hrefOf), `${what}: B's first page`);
      assert.deepEqual([app.state.list.workspace, first.found?.rows?.some(row => row.id.startsWith('b0')) ?? false], [search.ids.B, false], what);
      assert.ok(calls.slice(at).some(call => call.url === '/api/session'), `${what}: the session read again`);
      app.state.list.observer?.disconnect();
    });
  }
});

test('R2-22, C2: above 200 documents, words in the box load no more of the list\'s pages, however near its end comes; a search\'s own pages and the list\'s, once cleared, do', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, table, near, type }) => {
    app.state.routeSerial = 20;
    await app.showList('documents', 20);
    const pages = () => calls.filter(call => call.url.includes('&before=')).length;
    server.holdWhen(method => method === 'POST');
    type('polyp');  // the rows it hides bring the end near the window
    near(true);
    await settle(() => false);
    assert.equal(pages(), 0, 'the list\'s rows hidden by the words: none loads by itself while the search is the server\'s');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    server.waiting.shift().release();
    await settle(() => app.state.list.found?.query === 'polyp');
    near(true);
    await settle(() => calls.some(call => call.url === app.SEARCH_URL && call.body.before));
    assert.deepEqual(calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body), [{ text: 'polyp', before: null }, { text: 'polyp', before: 'c50' }],
      'the search\'s own next page loads as its end nears');
    server.waiting.shift().release();
    await settle(() => table.rows.length === 100);
    type('');
    near(true);
    await settle(() => pages() === 1);
    assert.equal(pages(), 1, 'cleared: the list\'s own pages load again');
  });
});

test('R2-22, C2: at 200 documents the search stays in the page; at 201 it goes to the server', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const [count, local] of [[200, true], [201, false]]) {
    await withListPage(pagedServer(listRowsOf(count)), async ({ calls, type }) => {
      app.state.routeSerial = 15;
      await app.showList('documents', 15);
      type('polyp');
      t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      await settle(() => (local ? calls.filter(call => call.url.includes('&before=')).length === 3 && !app.state.list.loading : calls.some(call => call.url === app.SEARCH_URL)));
      assert.equal(app.state.list.local, local, String(count));
      assert.equal(calls.some(call => call.url === app.SEARCH_URL), !local, `${count}: ${local ? 'in the page' : 'on the server'}`);
      assert.equal(calls.filter(call => call.url.includes('&before=')).length, local ? 3 : 0, `${count}: the rest of the list loaded only for the page's own search`);
    });
  }
});

test('R2-22: a refused search (429) says why under the list, and never that nothing matches', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const server = pagedServer(listRowsOf(260), { refuse: method => (method === 'POST' ? { status: 429, body: { error: 'rate_limited', retry_after: 30 } } : null) });
  await withListPage(server, async ({ more, empty, type }) => {
    app.state.routeSerial = 16;
    await app.showList('documents', 16);
    type('nothing like this');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => /Too many requests/.test(more.innerHTML));
    assert.match(more.innerHTML, /<p class="empty-state" role="status">Too many requests in a short time\. Wait a minute and try again\.<\/p>/, 'rateLimitText\'s words');
    assert.ok(!(empty.attached && /No documents match/.test(empty.textContent)), 'a refusal never says no match');
    type('nothing like this at all');
    assert.doesNotMatch(more.innerHTML, /Too many requests/, 'the next words ask again');
  });
});

test('R2-22: a late answer - a page, a search - after a route or the screen cleared is dropped; the list goes with the route and at clearScreen', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(260);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ table, near, observers }) => {
    app.state.routeSerial = 17;
    await app.showList('documents', 17);
    server.holdWhen((method, url) => url.includes('&before='));
    near(true);
    global.location.hash = '#how-it-works';
    app.route();
    assert.equal(app.state.list, null, 'a route drops the list');
    assert.equal(observers[0].disconnected, true, 'and stops watching its end');
    table.innerHTML = '<p>another view</p>';
    server.waiting.shift().release();
    await settle(() => false);
    assert.equal(table.rows.length, 0, 'the late page is dropped');
  });
  // a search asked, then the screen cleared (an end): its answer, for the very words still in the box, is dropped - drawn
  // nowhere, and no hint comes back after the wipe
  const hinted = holding(pagedServer(listRowsOf(260, { opensPdf: true })));
  await withListPage(hinted.answer, async ({ table, type }) => {
    app.state.routeSerial = 18;
    await app.showList('documents', 18);
    hinted.holdWhen(method => method === 'POST');
    type('polyp');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    assert.equal(hinted.waiting.length, 1);
    app.clearScreen();
    assert.equal(app.state.list, null, 'the screen cleared drops the list');
    assert.equal(app.state.viewHints.size, 0);
    table.innerHTML = '<p>the sign-in page</p>';
    hinted.waiting.shift().release();
    await settle(() => false);
    assert.equal(table.rows.length, 0, 'the late answer is drawn nowhere');
    assert.equal(app.state.viewHints.size, 0, 'and brings no hint back');
  });
  // a search waiting for its pause when the screen is cleared is never asked
  await withListPage(server.answer, async ({ calls, type }) => {
    app.state.routeSerial = 19;
    await app.showList('documents', 19);
    type('polyp');
    app.clearScreen();
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => false);
    assert.equal(calls.filter(call => call.url === app.SEARCH_URL).length, 0, 'its pending search is never asked');
  });
});

test('R2-22, R2-16: the list\'s rows that say they open as a PDF, first page, later pages and searches, are the hints a click may start the view at once for', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(260, { opensPdf: true });
  await withListPage(pagedServer(rows), async ({ table, near, type }) => {
    app.state.viewHints = new Map([['stale', true]]);
    app.state.routeSerial = 19;
    await app.showList('documents', 19);
    const odd = list => list.filter(row => row.opens_pdf).map(row => row.id);
    assert.deepEqual([...app.state.viewHints.keys()], odd(rows.slice(0, 50)), 'the first page\'s, and no other list\'s');
    near(true);
    await settle(() => table.rows.length === 100);
    assert.deepEqual([...app.state.viewHints.keys()], odd(rows.slice(0, 100)), 'a later page adds its own');
    type('polyp report 25');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found);
    assert.ok(odd(rows.filter(row => listText(row).includes('polyp report 25'))).every(id => app.state.viewHints.get(id) === true), 'and so do a search\'s');
    assert.equal(app.state.viewHints.get(rows[1].id), undefined, 'a row that does not say so is no hint');
  });
});

test('R2-22, C2: above 200 documents, a key that leaves the words unchanged asks nothing and keeps the results loaded; narrower words still ask', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  await withListPage(pagedServer(rows), async ({ calls, table, near, type }) => {
    app.state.routeSerial = 77;
    await app.showList('documents', 77);
    const searches = () => calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body);
    type('synthetic');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'synthetic');
    for (let n = 1; n <= 3; n += 1) {
      near(true);
      await settle(() => table.rows.length === 50 + 50 * n && !app.state.list.loading);
    }
    assert.deepEqual([table.rows.length, app.state.list.found.auto, searches().length], [200, 3, 4], 'the answer and its three automatic pages');
    for (const words of ['synthetic ', 'Synthetic', ' synthetic  ']) {
      type(words);
      t.mock.timers.tick(1000);
      await settle(() => false);
    }
    type('synthetica');  // a letter typed and deleted inside the pause
    type('synthetic');
    t.mock.timers.tick(1000);
    await settle(() => false);
    assert.deepEqual(searches().slice(4), [], 'the words unchanged: nothing asked');
    assert.deepEqual([table.rows.length, app.state.list.found.rows.length, app.state.list.found.auto], [200, 200, 3], 'the results loaded stay');
    type('synthetic polyp');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'synthetic polyp');
    assert.deepEqual(searches().slice(4), [{ text: 'synthetic polyp', before: null }], 'narrower words, matches beyond the page: asked');
  });
});

test('R2-22, C2: the same words typed while their own search is answered ask nothing more', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, table, type }) => {
    app.state.routeSerial = 78;
    await app.showList('documents', 78);
    const searches = () => calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body);
    server.holdWhen(method => method === 'POST');
    type('synthetic');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    assert.equal(searches().length, 1);
    type('synthetic ');  // while it is asked
    server.waiting.shift().release();
    await settle(() => app.state.list.found?.query === 'synthetic');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => false);
    assert.deepEqual([searches().length, table.rows.length], [1, 50], 'answered for these very words: not asked again');
  });
});

test('R2-22, C2: the same words typed while their own search is asked, its answer hidden by the page\'s own rule (the server folds the dotted capital I): no loading line once the pause has passed', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const paged = pagedServer(listRowsOf(400));
  const server = holding((method, url, body) => paged(method, url, typeof body?.text === 'string' ? { ...body, text: body.text.replace(/İ/g, 'I') } : body));
  await withListPage(server.answer, async ({ calls, table, empty, type }) => {
    app.state.routeSerial = 92;
    await app.showList('documents', 92);
    server.holdWhen(method => method === 'POST');
    type('SYNTHETİC');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    type('SYNTHETİC ');  // while it is asked
    server.waiting.shift().release();
    await settle(() => app.state.list.found !== null && !app.state.list.searching);
    assert.deepEqual([table.rows.length, table.rows.filter(row => !row.hidden).length], [50, 0]);
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => false);
    assert.deepEqual([calls.filter(call => call.url === app.SEARCH_URL).length, app.state.list.loading, empty.attached ? empty.textContent : null],
      [1, false, null], 'nothing asked, nothing loading: no loading line');
  });
});

test('R2-22, C2: an answer that finds newer words typed waits for their pause still running; nothing is asked before it, nor twice', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, type }) => {
    app.state.routeSerial = 79;
    await app.showList('documents', 79);
    const searches = () => calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body.text);
    server.holdWhen(method => method === 'POST');
    type('polyp');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    assert.deepEqual(searches(), ['polyp'], 'the first search, held');
    type('polyp re');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);  // its pause passes while the first is out: it is due once that answers
    type('polyp rep');
    server.waiting.shift().release();  // the first answers before the last key's pause has passed
    await settle(() => !app.state.list.searching);
    assert.deepEqual(searches(), ['polyp'], 'nothing asked before the pause');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS - 1);
    assert.deepEqual(searches(), ['polyp']);
    t.mock.timers.tick(1);
    assert.deepEqual(searches(), ['polyp', 'polyp rep'], 'the newest words, once their pause has passed');
    server.waiting.shift().release();
    await settle(() => app.state.list.found?.query === 'polyp rep');
    t.mock.timers.tick(1000);
    await settle(() => false);
    assert.deepEqual(searches(), ['polyp', 'polyp rep'], 'never the same words twice');
  });
});

test('R2-22, C2: the words are sent as typed, trimmed, their case kept, by the search and by its later pages; the page\'s own rule reads them lower-cased', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  await withListPage(pagedServer(rows), async ({ calls, table, near, type, shown }) => {
    app.state.routeSerial = 80;
    await app.showList('documents', 80);
    const searches = () => calls.filter(call => call.url === app.SEARCH_URL).map(call => call.body);
    type('  Polyp ');
    assert.deepEqual(shown().map(row => row.href), rows.slice(0, 50).filter(row => listText(row).includes('polyp')).map(hrefOf), 'the rows on the page, by release 1\'s rule');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'polyp');
    type('Polyp report 2');  // narrower words inside their pause: the answer stays, its rows filtered in the page
    near(true);  // the rows they hide bring the end near: the answer's own next page, asked with its own words
    await settle(() => table.rows.length === 100 && !app.state.list.loading);
    assert.deepEqual(searches(), [{ text: 'Polyp', before: null }, { text: 'Polyp', before: 'c50' }], 'as typed, trimmed: its first page and its next, with the answer\'s words');
  });
});

test('R2-22, C7: a failure is said under the list it failed for: the list\'s failed page says nothing under a complete search answer, and is said again once the box is cleared', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(260);
  const server = pagedServer(rows, { refuse: (method, url) => (method === 'GET' && url.includes('&before=') ? { status: 503, body: { error: 'The service is not available right now.' } } : null) });
  await withListPage(server, async ({ calls, table, more, near, type }) => {
    app.state.routeSerial = 41;
    await app.showList('documents', 41);
    near(true);
    await settle(() => /could not be loaded/.test(more.innerHTML));
    assert.match(more.innerHTML, /Documents could not be loaded\. The service is not available right now\./, 'the list\'s own failure, under the list');
    type('polyp report 2');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'polyp report 2' && !app.state.list.searching);
    const found = app.state.list.found;
    const matches = rows.filter(row => listText(row).includes('polyp report 2')).length;
    assert.deepEqual([found.rows.length, found.next, table.rows.length], [matches, null, matches], 'a complete answer: every match, nothing beyond');
    near(true);
    await settle(() => false);
    assert.equal(calls.filter(call => call.url === app.SEARCH_URL).length, 1, 'nothing more is asked');
    assert.doesNotMatch(more.innerHTML, /could not be loaded/, `under the complete answer #listMore reads: ${JSON.stringify(more.innerHTML)}`);
    type('');
    assert.match(more.innerHTML, /Documents could not be loaded\. The service is not available right now\./, 'cleared: the list\'s own failure is said again');
    assert.match(more.innerHTML, /Show more documents/);
  });
});

test('R2-22, C7: the search\'s failed page is not said under the list once the box is cleared, its automatic loads used up or not', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const exhaust of [false, true]) {
    const rows = listRowsOf(400);
    const server = pagedServer(rows, { refuse: (method, url, body) => (method === 'POST' && body?.before ? { status: 503, body: { error: 'The service is not available right now.' } } : null) });
    await withListPage(server, async ({ calls, table, more, near, type }) => {
      app.state.routeSerial = 42;
      await app.showList('documents', 42);
      if (exhaust) {
        for (const expected of [100, 150, 200]) {
          near(true);
          await settle(() => table.rows.length === expected && !app.state.list.loading);
        }
        assert.match(more.innerHTML, /Show more documents/, 'the list\'s three automatic loads used up');
      }
      const listPages = calls.filter(call => call.url.includes('&before=')).length;
      type('synthetic');
      t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      await settle(() => app.state.list.found?.query === 'synthetic' && !app.state.list.searching);
      near(true);
      await settle(() => /could not be loaded/.test(more.innerHTML));
      assert.match(more.innerHTML, /Documents could not be loaded\. The service is not available right now\./, `exhaust=${exhaust}: the search's failure, under the search`);
      assert.equal(app.state.list.found.failed, true, 'the search\'s own page failed');
      type('');
      assert.equal(app.state.list.found, null);
      assert.equal(app.state.list.browse.failed, false, 'the list never failed');
      assert.equal(table.rows.length, exhaust ? 200 : 50);
      assert.equal(calls.filter(call => call.url.includes('&before=')).length, listPages, 'and nothing of it was asked since');
      assert.doesNotMatch(more.innerHTML, /could not be loaded/, `exhaust=${exhaust}: under the list #listMore reads: ${JSON.stringify(more.innerHTML)}`);
    });
  }
});

test('R2-22, C7: the search\'s failed page is said under the search; its next load clears it, and a load that succeeds leaves it gone', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let refusing = true;
  const server = holding(pagedServer(listRowsOf(400), { refuse: (method, url, body) => (refusing && method === 'POST' && body?.before ? { status: 503, body: { error: 'The service is not available right now.' } } : null) }));
  await withListPage(server.answer, async ({ table, more, near, type }) => {
    app.state.routeSerial = 44;
    await app.showList('documents', 44);
    type('synthetic');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'synthetic' && !app.state.list.searching);
    near(true);
    await settle(() => app.state.list.found.failed && !app.state.list.loading);
    assert.match(more.innerHTML, /Documents could not be loaded\. The service is not available right now\./, 'said under the search');
    refusing = false;
    server.holdWhen((method, url, body) => method === 'POST' && Boolean(body?.before));
    click('[data-action]', { action: 'more-documents' });
    await settle(() => server.waiting.length === 1);
    assert.doesNotMatch(more.innerHTML, /could not be loaded/, 'its next load started: the sentence goes');
    server.waiting.shift().release();
    await settle(() => table.rows.length === 100 && !app.state.list.loading);
    assert.doesNotMatch(more.innerHTML, /could not be loaded/, 'loaded: it stays gone');
    assert.match(more.innerHTML, /Show more documents/);
  });
});

test('R2-22, C2: the list\'s last page, come while a search answer is shown or while its words are asked or wait their pause, puts the whole list on the page and searches it there: narrower words ask nothing, and their match is shown', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(240);  // five pages: the fifth, rows 201-240, the button's
  const match = rows.find(row => row.title === 'Synthetic polyp report 234');
  for (const order of ['the answer, then the page', 'the page, then the answer', 'the page inside the narrower words\' pause']) {
    const server = holding(pagedServer(rows));
    await withListPage(server.answer, async ({ calls, table, empty, near, type, shown }) => {
      app.state.routeSerial = 93;
      await app.showList('documents', 93);
      const list = () => app.state.list;
      for (const expected of [100, 150, 200]) {
        near(true);
        await settle(() => table.rows.length === expected && !list().loading);
      }
      near(false);
      const isPage = (method, url) => method === 'GET' && url.includes('&before=');
      server.holdWhen(order === 'the page, then the answer' ? (method, url) => isPage(method, url) || method === 'POST' : isPage);
      app.moreDocuments();  // the button: the list's last page, held
      await settle(() => server.waiting.length === 1);
      type('synthetic');
      t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      let mark;
      if (order === 'the answer, then the page') {
        await settle(() => list().found?.query === 'synthetic' && !list().searching);
        server.holdWhen(() => false);
        server.waiting.shift().release();
        await settle(() => !list().loading);
        mark = calls.length;
        type('synthetic polyp report 234');
      } else if (order === 'the page, then the answer') {
        await settle(() => server.waiting.length === 2);
        server.holdWhen(() => false);
        server.waiting.shift().release();  // the list's last page first
        await settle(() => !list().loading && list().browse.next === null);
        server.waiting.shift().release();  // then the search's answer
        await settle(() => !list().searching);
        mark = calls.length;
        type('synthetic polyp report 234');
      } else {
        await settle(() => list().found?.query === 'synthetic' && !list().searching);
        mark = calls.length;
        type('synthetic polyp report 234');  // its pause starts; the list's last page comes inside it
        server.holdWhen(() => false);
        server.waiting.shift().release();
        await settle(() => !list().loading);
      }
      t.mock.timers.tick(1000);
      await settle(() => false);
      assert.deepEqual([list().browse.next, list().browse.rows.length], [null, 240], `${order}: the whole list in page memory`);
      assert.deepEqual(calls.slice(mark).filter(call => call.url === app.SEARCH_URL).map(call => call.body), [], `${order}: the whole list on the page: nothing asked`);
      assert.deepEqual([shown().map(row => row.href), empty.attached ? empty.textContent : null], [[hrefOf(match)], null],
        `${order}: its match shown, never "No documents match your search."`);
    });
  }
});

test('R2-22, C2: the narrowness of the last-page rule: a page of the list that is not its last, come while a search answer is shown, keeps the answer and every match of it', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);  // 'polyp report 2': 36 matches, three on the list's first two pages
  const matches = rows.filter(row => listText(row).includes('polyp report 2')).map(hrefOf);
  const server = holding(pagedServer(rows));
  await withListPage(server.answer, async ({ calls, empty, near, type, shown }) => {
    app.state.routeSerial = 94;
    await app.showList('documents', 94);
    const list = () => app.state.list;
    server.holdWhen((method, url) => method === 'GET' && url.includes('&before='));
    near(true);  // the list's second page (of eight), held
    await settle(() => server.waiting.length === 1);
    type('polyp report 2');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => list().found?.query === 'polyp report 2' && !list().searching);
    const mark = calls.length;
    server.holdWhen(() => false);
    server.waiting.shift().release();
    await settle(() => !list().loading && list().browse.rows.length === 100);
    t.mock.timers.tick(1000);
    await settle(() => false);
    assert.deepEqual([matches.length, list().browse.next !== null, list().found?.query ?? null], [36, true, 'polyp report 2'], 'the answer kept');
    assert.deepEqual([shown().map(row => row.href), empty.attached ? empty.textContent : null], [matches, null], 'every match of it shown');
    assert.deepEqual(calls.slice(mark).filter(call => call.url === app.SEARCH_URL), [], 'nothing asked');
  });
});

test('R2-22, C2: the narrowness of the last-page rule: a search answer\'s own last page keeps the whole answer', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);  // 'polyp': 133 matches, the answer's three pages (50, 50, 33)
  const matches = rows.filter(row => listText(row).includes('polyp')).map(hrefOf);
  await withListPage(pagedServer(rows), async ({ empty, near, type, shown }) => {
    app.state.routeSerial = 95;
    await app.showList('documents', 95);
    const list = () => app.state.list;
    type('polyp');
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => list().found?.query === 'polyp' && !list().searching);
    for (let page = 0; page < 2; page += 1) {
      const held = list().found?.rows.length;
      near(true);
      await settle(() => !list().loading && list().found?.rows.length !== held);
    }
    assert.deepEqual([matches.length, Boolean(list().found), list().found ? list().found.next : 'no answer'], [133, true, null], 'the whole answer, kept');
    assert.deepEqual([shown().map(row => row.href), empty.attached ? empty.textContent : null], [matches, null], 'all 133 shown, in order');
  });
});

// A server that pages along (created_at, id) descending, each later page strictly older than its cursor, and searches
// the practice as it stands when asked (lane S's paging.older_than and search_page): `live` changes it.
function keysetServer(initial) {
  const live = initial.map(row => ({ ...row }));
  const time = row => Date.parse(row.created_at);
  const order = (a, b) => (time(b) - time(a)) || (b.id > a.id ? 1 : b.id < a.id ? -1 : 0);
  const cursorOf = row => `${time(row)}~${row.id}`;
  const older = (list, cursor) => {
    const [t, id] = cursor.split('~');
    return list.filter(row => time(row) < Number(t) || (time(row) === Number(t) && row.id < id));
  };
  const pageOf = (list, before, first) => {
    const ordered = list.slice().sort(order);
    const from = before ? older(ordered, before) : ordered;
    const shown = from.slice(0, 50);
    return { status: 200, body: { encounters: shown.map(row => ({ ...row })), next: from.length > 50 ? cursorOf(shown[shown.length - 1]) : null,
      total: first ? ordered.length : null } };
  };
  return {
    live,
    answer: (method, url, body) => {
      const where = new URL(url, 'http://studio.test');
      if (method === 'GET' && where.pathname === '/api/encounters') {
        const before = where.searchParams.get('before');
        return pageOf(live, before, !before);
      }
      if (method === 'POST' && where.pathname === '/api/encounters/search') return pageOf(live.filter(row => listText(row).includes(body.text.toLowerCase())), body.before, false);
      return { status: 404, body: { error: 'Not found.' } };
    },
  };
}

// 230 documents, 'Synthetic visit note n', n = 7 'Synthetic pathology report'; odd rows ready, even ones reviewed.
function keysetRows() {
  return Array.from({ length: 230 }, (_, index) => {
    const n = index + 1;
    return { id: `a1000000-0000-4000-8000-${String(n).padStart(12, '0')}`, title: n === 7 ? 'Synthetic pathology report' : `Synthetic visit note ${n}`,
      state: n % 2 ? 'ready' : 'reviewed', state_label: n % 2 ? 'Ready for approval' : 'Reviewed', service_date: '2026-11-03', insurance: 'medicaid',
      created_at: new Date(Date.UTC(2026, 10, 21) - n * 60000).toISOString().replace('.000', ''), kind: 'paste' };
  });
}

test('R2-22, C2: the list\'s last page under a search answer keeps what the answer, asked later, showed: a document made since the list\'s first page, and a state changed since', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const [words, title, label] of [['discharge summary', 'Synthetic discharge summary (new)', 'Ready for approval'], ['pathology report', 'Synthetic pathology report', 'Reviewed']]) {
    const server = keysetServer(keysetRows());
    const held = holding(server.answer);
    await withListPage(held.answer, async ({ table, empty, near, type, shown }) => {
      app.state.routeSerial = 702;
      await app.showList('documents', 702);
      for (const expected of [100, 150, 200]) {
        near(true);
        await settle(() => table.rows.length === expected && !app.state.list.loading);
      }
      near(false);
      server.live.push({ id: 'a1000000-0000-4000-8000-999999999999', title: 'Synthetic discharge summary (new)', state: 'ready', state_label: 'Ready for approval',
        service_date: '2026-11-04', insurance: 'medicaid', created_at: '2026-11-21T01:00:00Z', kind: 'paste' });
      Object.assign(server.live.find(row => row.title === 'Synthetic pathology report'), { state: 'reviewed', state_label: 'Reviewed' });
      held.holdWhen((method, url) => method === 'GET' && url.includes('&before='));
      app.moreDocuments();
      await settle(() => held.waiting.length === 1);
      type(words);
      t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      await settle(() => app.state.list.found?.query === words && !app.state.list.searching);
      const seen = () => shown().map(row => row.textContent);
      assert.equal(seen().length, 1, `${words}: the answer`);
      held.holdWhen(() => false);
      held.waiting.shift().release();
      await settle(() => !app.state.list.loading && app.state.list.browse.next === null);
      assert.deepEqual([seen().length, seen()[0]?.includes(title), seen()[0]?.includes(label), empty.attached ? empty.textContent : null], [1, true, true, null],
        `${words}: the list's last page keeps the answer's row`);
      type('');  // cleared: the whole list, newest first - a document only the answer holds first
      assert.deepEqual([table.rows.length, table.rows[0]?.href], words === 'discharge summary' ? [231, '#doc/a1000000-0000-4000-8000-999999999999']
        : [230, hrefOf(keysetRows()[0])], `${words}: cleared, the list newest first`);
    });
  }
});

test('R2-22, C2: a search refused before the list\'s last page lands is not said under the whole list, which is searched in the page', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const [what, first, words, shownCount, said] of [['an answer shown, narrower words matching nothing', 'synthetic', 'synthetic polyp report 999', 0, 'No documents match your search.'],
    ['no answer shown', null, 'polyp report 23', 3, null]]) {
    const rows = listRowsOf(240);
    let refusing = false;
    const server = holding(pagedServer(rows, { refuse: method => (refusing && method === 'POST' ? { status: 429, body: { error: 'rate_limited', retry_after: 30 } } : null) }));
    await withListPage(server.answer, async ({ table, more, empty, near, type, shown }) => {
      app.state.routeSerial = 96;
      await app.showList('documents', 96);
      for (const expected of [100, 150, 200]) {
        near(true);
        await settle(() => table.rows.length === expected && !app.state.list.loading);
      }
      server.holdWhen((method, url) => method === 'GET' && url.includes('&before='));
      app.moreDocuments();  // the list's last page, held
      await settle(() => server.waiting.length === 1);
      if (first) {
        type(first);
        t.mock.timers.tick(app.SEARCH_PAUSE_MS);
        await settle(() => app.state.list.found?.query === first && !app.state.list.searching);
      }
      refusing = true;
      type(words);
      t.mock.timers.tick(app.SEARCH_PAUSE_MS);
      await settle(() => !app.state.list.searching && Boolean(app.state.list.refused));
      assert.match(more.innerHTML, /Too many requests/, `${what}: the refusal said while more could match`);
      server.waiting.shift().release();
      await settle(() => !app.state.list.loading && app.state.list.browse.next === null);
      assert.deepEqual([more.hidden, more.innerHTML, shown().length, empty.attached ? empty.textContent : null], [true, '', shownCount, said],
        `${what}: the whole list on the page, nothing more asked: the refusal goes`);
    });
  }
});

test('R2-22, C7: a page of the list that fails while a search answer is shown is said under the list once the box is cleared', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const rows = listRowsOf(400);
  const server = holding(pagedServer(rows, { refuse: (method, url) => (method === 'GET' && url.includes('&before=') ? { status: 503, body: { error: 'The service is not available right now.' } } : null) }));
  await withListPage(server.answer, async ({ more, near, type }) => {
    app.state.routeSerial = 43;
    await app.showList('documents', 43);
    server.holdWhen((method, url) => method === 'GET' && url.includes('&before='));
    near(true);
    await settle(() => server.waiting.length === 1);
    type('synthetic');  // while the list's next page is out
    t.mock.timers.tick(app.SEARCH_PAUSE_MS);
    await settle(() => app.state.list.found?.query === 'synthetic' && !app.state.list.searching);
    near(false);
    server.waiting.shift().release();  // the list's page fails, the search's answer shown
    await settle(() => !app.state.list.loading);
    assert.doesNotMatch(more.innerHTML, /could not be loaded/, 'not said under the search');
    type('');
    assert.match(more.innerHTML, /Documents could not be loaded\. The service is not available right now\./, 'said under its own list');
    assert.match(more.innerHTML, /Show more documents/);
  });
});

test('R2-19, R2-20, R2-24: the dev preview pages its list and answers the search as the server does', () => {
  const rows = listRowsOf(120).reverse();  // in any order: the preview orders them
  const [status, first] = preview.listAnswer(rows, 'documents', null);
  assert.equal(status, 200);
  assert.deepEqual(first.encounters.map(row => row.id), listRowsOf(50).map(row => row.id), 'newest first, 50 a page');
  const last = first.encounters[49];
  assert.equal(first.next, `${Date.parse(last.created_at) * 1000}~${last.id}`, 'the cursor: a time in UTC microseconds and an id');
  assert.equal(first.total, 120, 'the total, on a first page');
  const [, second] = preview.listAnswer(rows, 'documents', first.next);
  const [, third] = preview.listAnswer(rows, 'documents', second.next);
  assert.deepEqual([second.encounters.length, second.total, third.encounters.length, third.next, third.total], [50, null, 20, null, null]);
  assert.deepEqual([...first.encounters, ...second.encounters, ...third.encounters].map(row => row.id), listRowsOf(120).map(row => row.id), 'every row once');
  // two documents of one time, across a page edge: each once, the larger id first
  const tied = listRowsOf(52).map((row, index) => (index === 49 || index === 50 ? { ...row, created_at: '2026-11-19T00:00:00Z' } : row));
  const [, edge] = preview.listAnswer(tied, 'documents', null);
  const [, after] = preview.listAnswer(tied, 'documents', edge.next);
  assert.deepEqual([...edge.encounters, ...after.encounters].map(row => row.id).sort(), tied.map(row => row.id).sort());
  const [, recent] = preview.listAnswer(rows, 'recent', null);
  assert.deepEqual([recent.encounters.length, recent.next, recent.total], [5, null, null]);
  for (const bad of ['x', '12~not-an-id', `${Date.now()}`, `1~${UUID}~x`]) {
    assert.deepEqual(preview.listAnswer(rows, 'documents', bad), [400, { error: 'That part of the list could not be read. Open the list again.' }], bad);
  }
  // the search: the rows whose text holds the words (the page's own rule), 50 at a time, total null
  const many = listRowsOf(160);
  const matching = many.filter(row => listText(row).includes('polyp')).map(row => row.id);
  const [found, page] = preview.searchAnswer(many, { text: 'Polyp', before: null });
  assert.deepEqual([found, page.total, page.encounters.length, matching.length], [200, null, 50, 53]);
  assert.deepEqual(page.encounters.map(row => row.id), matching.slice(0, 50));
  const [, rest] = preview.searchAnswer(many, { text: 'Polyp', before: page.next });
  assert.deepEqual([rest.encounters.map(row => row.id), rest.next, rest.total], [matching.slice(50), null, null], 'the next page of matches, and the end');
  assert.equal(preview.rowText(many[2]), dom(app.documentRow(many[2])).text, 'the row\'s text is the page\'s own');
  for (const [body, answer] of [[{ text: '   ', before: null }, [400, { error: 'Type the words to search for.' }]], [{ text: 7 }, [400, { error: 'Type the words to search for.' }]],
    [null, [400, { error: 'Type the words to search for.' }]], [{ text: 'x'.repeat(241), before: null }, [200, { encounters: [], next: null, total: null }]],
    [{ text: 'polyp\u0000', before: null }, [200, { encounters: [], next: null, total: null }]], [{ text: 'polyp\ud800', before: null }, [200, { encounters: [], next: null, total: null }]],
    [{ text: 'polyp', before: 'garbage' }, [400, { error: 'That part of the list could not be read. Open the list again.' }]]]) {
    assert.deepEqual(preview.searchAnswer(many, body), answer, JSON.stringify(body));
  }
  assert.equal(preview.searchAnswer(many, { text: 'é'.repeat(240), before: null })[0], 200, '240 characters are words');
});

test('R2: the page script and the stylesheet stay 1% under section 8\'s static weight, an early warning (node\'s gzip is not WhiteNoise\'s byte for byte; the bench reads the .gz itself)', () => {
  // node bundles Chromium's zlib, whose level-9 deflate stream differs from Python's (WhiteNoise's compress_gzip):
  // measured -13..+3 B on styles.css and +148..+197 B on app.js, so a pass here is a pass there with 1% to spare
  const gzipped = file => zlib.gzipSync(fs.readFileSync(file), { level: 9 }).length;
  assert.ok(gzipped(BUNDLE) <= 79200, `app.js: ${gzipped(BUNDLE)} B gzipped by node, the early gate 79,200 (section 8: 80,000)`);
  assert.ok(gzipped(STYLES) <= 15840, `styles.css: ${gzipped(STYLES)} B gzipped by node, the early gate 15,840 (section 8: 16,000)`);
});

// --- I1-13 (session-0): the sign-in page and the account page tell this browser's app tabs they were reached
// (studio/static/studio/session_news.js), on the app's own channel and in the shapes the app already acts on ---------

const SESSION_NEWS = path.join(ROOT, 'studio', 'static', 'studio', 'session_news.js');

// session_news.js run on a page of its own (a vm context): the body's data-session (none on the sign-in page), the
// "Sign out everywhere" form where the page has one, and a BroadcastChannel that works, cannot be made, refuses to post
// or is not there (then the localStorage key, which may refuse too). It answers what was posted, what was stored and the
// form's submit.
function newsPage({ session, form = false, channel = 'works', storage = 'works', now = 1764000000000 } = {}) {
  const posted = [];
  const stored = [];
  const listeners = {};
  const everywhere = form ? { addEventListener(type, listener) { listeners[type] = listener; } } : null;
  class Channel {
    constructor(name) {
      if (channel === 'throws') throw new Error('no channel here');
      this.name = name;
    }
    postMessage(data) {
      if (channel === 'refuses') throw new Error('the channel refused it');
      posted.push({ name: this.name, data: JSON.parse(JSON.stringify(data)) });
    }
  }
  const sandbox = {
    document: { body: { dataset: session === undefined ? {} : { session } }, getElementById: id => (id === 'everywhereForm' ? everywhere : null) },
    Date: { now: () => now },
  };
  if (channel !== 'none') sandbox.BroadcastChannel = Channel;
  if (storage !== 'none') {
    sandbox.localStorage = { setItem(key, value) { if (storage === 'throws') throw new Error('no storage here'); stored.push({ key, data: JSON.parse(value) }); } };
  }
  vm.runInNewContext(fs.readFileSync(SESSION_NEWS, 'utf8'), sandbox);
  return { posted, stored, submit: () => listeners.submit?.({ type: 'submit' }) };
}

test('I1-13 (session-0): the sign-in page and the account page tell the app\'s tabs they were reached - on its own channel, in its own shapes: at load the page and its session (none on the sign-in page), and the account page\'s "Sign out everywhere" as its session signed out; with no channel, the storage key shareSession writes; a channel or storage that refuses throws nothing', () => {
  const now = 1764000000000;
  const page = { type: 'page', session: 'tag-a', at: now };
  const out = { type: 'signed-out', reason: 'expired', session: 'tag-a', at: now };
  // the sign-in page: one message, at load, naming no session; it has no everywhere form
  const login = newsPage({ now });
  assert.deepEqual([login.posted, login.stored], [[{ name: app.SESSION_CHANNEL, data: { type: 'page', session: '', at: now } }], []]);
  // the account page: its session at load; its everywhere form, sent, says that session signed out
  const account = newsPage({ session: 'tag-a', form: true, now });
  assert.deepEqual(account.posted, [{ name: app.SESSION_CHANNEL, data: page }]);
  account.submit();
  assert.deepEqual(account.posted.map(item => [item.name, item.data]), [[app.SESSION_CHANNEL, page], [app.SESSION_CHANNEL, out]]);
  assert.deepEqual(account.stored, [], 'the channel worked: nothing in storage');
  // no channel, one that cannot be made, or one that refuses: the storage key the app's storage events read
  for (const channel of ['none', 'throws', 'refuses']) {
    const fallback = newsPage({ session: 'tag-a', form: true, channel, now });
    fallback.submit();
    assert.deepEqual([fallback.posted, fallback.stored], [[], [{ key: app.SESSION_CHANNEL, data: page }, { key: app.SESSION_CHANNEL, data: out }]], channel);
  }
  // nowhere to say it: no error escapes the page
  for (const storage of ['none', 'throws']) assert.doesNotThrow(() => newsPage({ session: 'tag-a', form: true, channel: 'none', storage }).submit(), storage);
  // the shape is the app's own (shareSession): the message, the session and the time, nothing else
  const shared = [];
  const saved = { channel: app.idle.channel, session: app.idle.session };
  try {
    Object.assign(app.idle, { channel: { postMessage: data => shared.push(JSON.parse(JSON.stringify(data))) }, session: 'tag-a' });
    app.shareSession({ type: 'signed-out', reason: 'expired' });
  } finally {
    Object.assign(app.idle, saved);
  }
  assert.deepEqual(Object.keys(shared[0]).sort(), Object.keys(out).sort());
  assert.deepEqual({ ...shared[0], at: now }, out);
});

test('I1-13 (session-0): an app tab acts on what those pages say as on another tab\'s news - its own session\'s account page changes nothing; that page\'s "Sign out everywhere" takes it to the sign-in page at once; the sign-in page, or another member\'s account page, makes it ask the server (a poll), whose 401 or other session ends it - and every end wipes the kept copies, the hints and the waiting worker', async () => {
  const keep = () => {
    const data = Uint8Array.from([37, 80, 68, 70]);
    app.state.keptViews.clear();
    app.keepView('/api/encounters/x/original?view=1', 'abcdef00-0000-4000-8000-000000000000', data);
    app.state.viewHints = new Map([['x', true]]);
    const thread = { terminated: false, terminate() { this.terminated = true; } };
    app.state.pdfStandby = { thread, address: 'x', ready: Promise.resolve(thread), taken: false };
    return { data, thread };
  };
  const ping = (status, body) => ({ match: (method, url) => method === 'POST' && url === app.ACTIVITY_URL, status, body });
  const alive = session => ping(200, { idle_seconds: 900, cap_seconds: 28800, warning_seconds: 120, session });
  const cases = [
    // [what, the page's messages, the server's answer to a check, ends?, asks?]
    ['the account page of its own session', newsPage({ session: 'tag-a', form: true }).posted, null, false, false],
    ['that page\'s "Sign out everywhere"', (() => { const one = newsPage({ session: 'tag-a', form: true }); one.submit(); return one.posted; })(), null, true, false],
    ['the sign-in page after the sessions ended (401)', newsPage({}).posted, ping(401, { error: 'signed_out', reason: 'expired' }), true, true],
    ['the sign-in page while still signed in', newsPage({}).posted, alive('tag-a'), false, true],
    ['another member\'s account page (a forced change: their session)', newsPage({ session: 'tag-b', form: true }).posted, alive('tag-b'), true, true],
  ];
  for (const [what, messages, answer, ends, asks] of cases) {
    await withSignedInPage({ elements: { signoutForm: fakeElement({ submitted: 0, submit() { this.submitted += 1; } }) }, answers: answer ? [answer] : [] }, async ({ calls }) => {
      Object.assign(app.idle, { gone: false, session: 'tag-a', checking: null, deadline: Date.now() + 600000, idleEnd: Date.now() + 600000 });
      app.state.leaving = false;
      const { data, thread } = keep();
      for (const message of messages) app.receiveSession(message.data);
      await settle(() => !app.idle.checking);
      const checks = calls.filter(call => call.url === app.ACTIVITY_URL);
      assert.deepEqual(checks.map(call => [call.method, call.headers[app.POLL_HEADER]]), asks ? [['POST', '1']] : [], `${what}: asked the server (a poll, no one's activity)`);
      const left = calls.filter(call => call.assign).map(call => call.assign.split('?')[0]);
      assert.deepEqual(left, ends ? ['/login/'] : [], `${what}: where the tab went`);
      assert.deepEqual([app.state.keptViews.size, [...data], app.state.viewHints.size, app.state.pdfStandby, thread.terminated],
        ends ? [0, [0, 0, 0, 0], 0, null, true] : [1, [37, 80, 68, 70], 1, app.state.pdfStandby, false], `${what}: page memory`);
      if (!ends) assert.ok(app.state.pdfStandby, `${what}: the waiting worker stays`);
      app.forgetMemory();
    });
  }
});
