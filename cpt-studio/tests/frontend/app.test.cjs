'use strict';
// Unit tests for the customer page, studio/static/studio/app.js, over the customer contract customer-2026-11-22 (the
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

function response({ status = 200, body = {}, type = 'application/json', redirected = false, url = '/' } = {}) {
  return {
    status, ok: status >= 200 && status < 300, redirected, url: `http://studio.test${url}`,
    headers: { get: name => (name.toLowerCase() === 'content-type' ? type : null) },
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
    if (index >= 0) return response(answers.splice(index, 1)[0]);
    return response(session ? { status: 200, body: fixture('session.json') } : { status: 201, body: {} });
  };
  global.location = { hash: '', assign(url) { calls.push({ assign: url }); } };
  global.window = { scrollY: 0, scrollTo() {}, matchMedia: () => ({ matches: false }) };
  const kept = ['doc', 'session', 'route', 'routeSerial', 'review', 'answers', 'leaving', 'outdated', 'docKey', 'viewerKey', 'selectedQuote', 'clock', 'reconnecting', 'ack'];
  const before = Object.fromEntries(kept.map(key => [key, app.state[key]]));
  try {
    await fn({ calls, element });
  } finally {
    await new Promise(resolve => setImmediate(resolve));
    clearTimeout(app.state.toastTimer);
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
  assert.equal(app.CLIENT_VERSION, 'customer-2026-11-22');
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
    'planted.document: keys kind,media_type,name,original_url,preview_type,size,view_media_type,view_url are not converted,kind,media_type,name,original_url,size,view_media_type,view_url',
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
    'encounter-word.json': ['needs_review', 'done'],
  });
  // every document's view as the server builds it: a PDF or a text as uploaded, a pasted text as text, a Word file as
  // the PDF it was converted to - or, never converted (an earlier review), no view
  const views = Object.fromEntries(ENCOUNTERS.map(name => {
    const part = fixture(name).document;
    assert.deepEqual([part.view_media_type, part.converted], expectedView(part), name);
    assert.equal(part.view_url, part.view_media_type ? `/api/encounters/${fixture(name).id}/original?view=1` : null, name);
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
  assert.deepEqual(fixture('encounters-empty.json'), { encounters: [] });
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
    const download = page.one('#downloadOriginal');
    if (doc.document.original_url) assert.deepEqual([download.attr('href'), download.text, download.attr('download')], [doc.document.original_url, 'Download original', ''], name);
    else assert.equal(download, null, name);
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
  // the earlier review of a Word file the earlier version never converted: no viewer, the download only
  const earlier = dom(render(fixture('encounter-earlier.json')));
  assert.equal(earlier.all('iframe').length, 0);
  assert.equal(earlier.one('#downloadOriginal').attr('href'), fixture('encounter-earlier.json').document.original_url);
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
  assert.equal(panel.one('#downloadOriginal').attr('href'), doc.document.original_url, 'the download is the Word file itself');
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

test('the browser\'s own viewer says why it is shown: the browser, the library, a document the library cannot draw, a stalled download', async () => {
  const word = fixture('encounter-word.json');
  const saved = { viewer: app.state.viewer };
  // the four reasons, word for word; a reason the page does not name is read as the document's, never as the browser's
  assert.deepEqual(app.FRAME_REASONS, {
    browser: 'Marking needs a newer browser.',
    library: 'The marking tool did not work here, so nothing is marked.',
    document: 'This document cannot be drawn here, so nothing is marked.',
    slow: 'The document took too long to load here, so nothing is marked.',
  });
  const cases = [['browser', 'browser'], ['library', 'library'], ['document', 'document'], ['slow', 'slow'], ['toString', 'document'], [undefined, 'document']];
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

test('a read that changes the page never reloads the viewer: its mark stays, a new coding review clears it, a new document closes it', async () => {
  const word = fixture('encounter-word.json');
  const element = viewerElement({ dataset: { viewUrl: word.document.view_url } });
  const saved = { viewer: app.state.viewer };
  try {
    await withPage({ elements: { documentViewer: element } }, async ({ element: find }) => {
      const viewer = { element, view: word.document.view_url, name: 'x', mode: 'pdf', pages: [], texts: new Map(), markSerial: 0, reveal: 0, frame: null,
        mark: { key: 'L2#0', quote: word.codes[1].quotes[0], result: { status: 'marked', pages: [1], count: 1, marks: {} } }, pending: null };
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
      // a newer coding review of the same document: the passage chosen and its mark go, the viewer stays
      const newer = clone(decided);
      newer.round = { ...newer.round, number: newer.round.number + 1 };
      app.renderDocument(newer, false);
      assert.equal(app.state.viewer, viewer);
      assert.equal(viewer.mark, null);
      assert.equal(app.state.selectedQuote, '');
      assert.equal(find('#viewerMark').textContent, '');
      // another view of the document (another viewer key): the page is redrawn whole and the viewer closed
      const other = clone(newer);
      other.document.converted = false;
      app.renderDocument(other, false);
      assert.equal(viewer.mode, 'closed', 'the old viewer is closed');
      assert.notEqual(app.state.viewer, viewer);
    });
  } finally {
    Object.assign(app.state, saved);
  }
});

// The PDF library as a test stands it in: a module whose worker starts (`worker`: 'ready', 'fails' or 'never') and whose
// documents open as `open(task)` says (never, by default).
function fakeLibrary({ worker = 'ready', open = null } = {}) {
  const made = { workers: [], tasks: [] };
  const library = {
    GlobalWorkerOptions: { workerSrc: '' }, VerbosityLevel: { ERRORS: 0 }, AnnotationMode: { ENABLE: 2 },
    PDFWorker: class {
      constructor() {
        made.workers.push(this);
        this.destroyed = false;
        this.promise = worker === 'ready' ? Promise.resolve() : worker === 'fails' ? Promise.reject(new Error('no worker')) : new Promise(() => {});
        this.promise.catch(() => {});
      }

      destroy() { this.destroyed = true; }
    },
    getDocument(options) {
      const task = { options, onProgress: null, destroyed: false, destroy() { this.destroyed = true; return Promise.resolve(); } };
      task.promise = open ? open(task) : new Promise(() => {});
      task.promise.catch(() => {});
      made.tasks.push(task);
      return task;
    },
  };
  return { library, made };
}

const PDF_MODULE = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.min.0123456789ab.mjs';
const PDF_WORKER = '/static/studio/lib/pdfjs-6.5.438/legacy/build/pdf.worker.min.0123456789ab.mjs';

// Runs fn on a page that can draw a PDF (the observers a browser has), with the library's module loaded by `load` and the
// page's state kept apart.
async function withPdfPage(load, fn) {
  const saved = { viewer: app.state.viewer, pdfLibrary: app.state.pdfLibrary, pdfAttempt: app.state.pdfAttempt, framePassage: app.state.framePassage };
  const globals = { IntersectionObserver: global.IntersectionObserver, ResizeObserver: global.ResizeObserver };
  const loader = app.PDF_IMPORT.load;
  global.IntersectionObserver = function IntersectionObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  global.ResizeObserver = function ResizeObserver() { this.observe = () => {}; this.disconnect = () => {}; };
  const loads = [];
  app.PDF_IMPORT.load = specifier => { loads.push(specifier); return load(specifier); };
  try {
    await withPage({}, async page => {
      global.document.body.dataset = { pdfModule: PDF_MODULE, pdfWorker: PDF_WORKER };
      global.location.href = 'http://studio.test/';
      Object.assign(app.state, { pdfLibrary: null, pdfAttempt: 0, viewer: null });
      await fn({ ...page, loads });
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

test('L1: a library that fails to load is the library\'s note, and the next document tries again at fresh addresses', async () => {
  const word = fixture('encounter-word.json');
  let answer = () => Promise.reject(new Error('404'));
  await withPdfPage(specifier => answer(specifier), async ({ element: find, loads }) => {
    // the module does not load: the frame, and the note blames neither the browser nor the document
    const first = await mount(word, find, viewer => viewer.mode === 'frame');
    assert.deepEqual([first.fallback, first.element.dataset.fallback], ['library', 'library']);
    assert.deepEqual(loads, [PDF_MODULE], 'the first attempt asks for the address the page names');
    assert.equal(app.state.pdfLibrary, null, 'a failure is not kept');
    app.showQuote('L2#0');
    assert.equal(find('#viewerMark').textContent, 'The marking tool did not work here, so nothing is marked. The quote is on page 1.');
    assert.equal(first.mode, 'frame', 'the document that failed stays framed with the library\'s note');
    // the next document: fresh addresses for the module and its worker (the browser keeps a failed module by its
    // address for the life of the page); this time the worker does not start, which is the library's failure too
    const broken = fakeLibrary({ worker: 'fails' });
    answer = () => Promise.resolve(broken.library);
    const second = await mount(word, find, viewer => viewer.mode === 'frame');
    assert.equal(second.fallback, 'library');
    assert.deepEqual(loads, [PDF_MODULE, `${PDF_MODULE}?attempt=2`]);
    assert.equal(broken.library.GlobalWorkerOptions.workerSrc, `${PDF_WORKER}?attempt=2`);
    assert.equal(broken.made.workers.length, 1);
    assert.equal(app.state.pdfLibrary, null);
    // the third: the library and its worker start, and the document opens; a working library is kept for the next one
    const working = fakeLibrary({ worker: 'ready' });
    answer = () => Promise.resolve(working.library);
    const third = await mount(word, find, viewer => working.made.tasks.length === 1);
    assert.equal(third.mode, 'loading', 'opening the document');
    assert.deepEqual(loads.slice(2), [`${PDF_MODULE}?attempt=3`]);
    assert.equal(working.library.GlobalWorkerOptions.workerSrc, `${PDF_WORKER}?attempt=3`);
    assert.equal(working.made.tasks[0].options.worker, working.made.workers[0], 'the document is opened with the viewer\'s own worker');
    const kept = app.state.pdfLibrary;
    assert.ok(kept);
    await mount(word, find, () => working.made.tasks.length === 2);
    assert.equal(loads.length, 3, 'loaded once while it works');
    assert.equal(app.state.pdfLibrary, kept);
    app.closeViewer();
    await settle(() => working.made.workers.every(worker => worker.destroyed));
    assert.ok(working.made.workers.every(worker => worker.destroyed), 'closing a viewer lets its worker go');
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
    // the worker that never starts is given up the same way
    const stuck = fakeLibrary({ worker: 'never' });
    answer = () => Promise.resolve(stuck.library);
    const second = await mount(word, find, () => stuck.made.workers.length === 1);
    assert.equal(loads[1], `${PDF_MODULE}?attempt=2`);
    t.mock.timers.tick(20000);
    await settle(() => second.mode === 'frame');
    assert.deepEqual([second.mode, second.fallback], ['frame', 'library']);
    await settle(() => stuck.made.workers[0].destroyed);
    assert.ok(stuck.made.workers[0].destroyed, 'the worker given up is let go');
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

test('B3, B4: a document with no page, and a page\'s drawing or text that does not settle once it opened, give the frame', async t => {
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
  // that follows at 20 s is the library's, never "took too long to load"
  const stopped = fakeLibrary({ open: () => Promise.resolve({ numPages: 3, getPage: () => new Promise(() => {}) }) });
  await withPdfPage(() => Promise.resolve(stopped.library), async ({ element: find }) => {
    const viewer = await mount(word, find, () => stopped.made.tasks.length === 1 && stopped.made.tasks[0].onProgress === null);
    const task = stopped.made.tasks[0];
    assert.equal(task.onProgress, null, 'the download\'s progress no longer re-arms its timer');
    assert.equal(viewer.stallTimer, 0);
    t.mock.timers.tick(19999);
    await settle(() => false);
    assert.equal(viewer.mode, 'loading');
    t.mock.timers.tick(1);
    await settle(() => viewer.mode === 'frame');
    assert.deepEqual([viewer.mode, viewer.fallback], ['frame', 'library']);
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
        cleanup: () => cleaned.push(page.number) } });
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
      assert.deepEqual(app.state.framePassage, { passage: text.codes[0].quotes[0].text, key: 'L1#0' });
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
  const options = doc => dom(app.exportOptions(doc)).all('.export-option').map(option => [option.attr('data-export-kind'), option.attr('data-export-fmt'), option.attr('disabled') === null]);
  assert.deepEqual(options(fixture('encounter-ready.json')), [['draft', 'txt', true], ['draft', 'csv', true], ['approved', 'txt', false], ['approved', 'csv', false]]);
  assert.deepEqual(options(fixture('encounter-reviewed.json')), [['draft', 'txt', true], ['draft', 'csv', true], ['approved', 'txt', true], ['approved', 'csv', true]]);
  assert.deepEqual(options(fixture('encounter-reading.json')).map(option => option[2]), [false, false, false, false]);
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
  assert.match(reports[0].one('small').text, /^Approved codes · 20 Nov 2026, 07:55 UTC$/);
  assert.match(reports[1].one('small').text, /Earlier: made from an earlier coding review/);
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
  assert.equal(page.one('.review-readiness').text, 'You can download the codes as a draft. Approve codes to download them as approved.');
  assert.equal(page.one('.results-empty').text, 'The coding review found no CPT code to report for this document.');
  // the dialog it opens offers the draft, and the approved download stays closed until a code is approved
  assert.deepEqual(dom(app.exportOptions(doc)).all('.export-option').map(option => [option.attr('data-export-kind'), option.attr('data-export-fmt'), option.attr('disabled') === null]),
    [['draft', 'txt', true], ['draft', 'csv', true], ['approved', 'txt', false], ['approved', 'csv', false]]);
  // nothing the server allows and nothing made earlier: no button
  for (const name of ['encounter-reading.json', 'encounter-checking.json', 'encounter-failed.json', 'encounter-earlier.json']) {
    assert.equal(dom(render(fixture(name))).all('[data-action="export"]').length, 0, name);
  }
  // downloads made earlier are listed even while nothing new can be made
  const listed = clone(fixture('encounter-failed.json'));
  listed.reports = clone(fixture('encounter-reviewed.json').reports).map(report => ({ ...report, current: false }));
  assert.ok(dom(render(listed)).all('[data-action="export"]').length > 0);
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
  assert.deepEqual(queue, ['#doc/f3000000-0000-4000-8000-000000000001', '#doc/f4000000-0000-4000-8000-000000000001', '#doc/f5000000-0000-4000-8000-000000000001',
    '#doc/f9000000-0000-4000-8000-000000000001', '#doc/fc000000-0000-4000-8000-000000000001']);
  assert.match(app.listDescription('queue', rows), /^5 documents wait on you: questions to answer, or codes to review or approve\.$/);
  const earlier = page.all('a.document-row').find(row => row.attr('href') === '#doc/fb000000-0000-4000-8000-000000000001');
  assert.match(earlier.text, /Synthetic colonoscopy report, earlier reviewUploaded fileEarlier review9 Nov 2026/);
  assert.equal(app.listDescription('queue', []), 'No document waits on you for an answer or a decision.');
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
    app.listBody('queue', rows), `<p>${app.listDescription('queue', rows)}</p>`, app.inviteMarkup(rows), app.ackView({ id: rows[0].id, at: 0 }),
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
  for (const id of ['uploadDialog', 'reviewDialog', 'exportDialog', 'aboutDialog']) assert.ok(page.one(`dialog#${id}`), id);
  assert.equal(page.all('dialog').length, 4);
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
      ['token123', 'customer-2026-11-22', 'application/json', 'same-origin', 'no-store']);
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
  const report = { id: 'f6100000-0000-4000-8000-0000000000a1', kind: 'approved', fmt: 'txt', filename: 'CPT-Studio-approved-r2-20261120T090000.txt',
    generated_at: '2026-11-20T09:00:00Z', download_url: '/api/reports/f6100000-0000-4000-8000-0000000000a1/download', current: true };
  // the option posts {kind, fmt, round}: the number of the coding review the page shows; then the download starts
  await withPage({ answers: [{ match: (method, url) => method === 'POST' && url === `${address}/reports`, status: 201, body: report }] }, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: reviewed, route: { name: 'doc', id: reviewed.id }, routeSerial: 14, docKey: '', viewerKey: app.viewerKey(reviewed) });
    click('[data-action]', { action: 'export' });
    assert.equal(element('#exportDialog').open, true);
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'txt' });
    await settle(() => calls.some(call => call.download));
    assert.deepEqual(posted(calls), [{ url: `${address}/reports`, body: { kind: 'approved', fmt: 'txt', round: 2 } }]);
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
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'txt' });
    await settle(() => element('#toast').textContent === app.CHANGED_TEXT && app.state.doc.round.number === 2 && calls.some(call => call.method === 'GET'));
    assert.deepEqual(posted(calls).map(call => call.body), [{ kind: 'draft', fmt: 'txt', round: 1 }]);
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
    click('[data-export-kind]', { exportKind: 'approved', exportFmt: 'csv' });
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
    click('[data-export-kind]', { exportKind: 'draft', exportFmt: 'txt' });
    await settle(() => false);
    assert.deepEqual(posted(calls), []);
  });
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
  const [status, report] = preview.reportAnswer(reviewed, { kind: 'approved', fmt: 'txt', round: 2 });
  assert.equal(status, 201);
  assert.deepEqual([report.kind, report.fmt, report.current, app.safeDownloadUrl(report.download_url) === report.download_url], ['approved', 'txt', true, true]);
  for (const stale of [{ round: 1 }, { round: '2' }, { round: undefined }, { round: 3 }]) {
    assert.deepEqual(preview.reportAnswer(reviewed, { kind: 'draft', fmt: 'csv', ...stale }), [409, { error: preview.CHANGED, details: {} }], JSON.stringify(stale));
  }
  const ready = fixture('encounter-ready.json');
  assert.deepEqual(preview.reportAnswer(ready, { kind: 'approved', fmt: 'txt', round: 1 }),
    [409, { error: 'The approved download is not available yet.', details: { blockers: ['No code has been approved.'] } }]);
  assert.equal(preview.reportAnswer(ready, { kind: 'draft', fmt: 'txt', round: 1 })[0], 201);
  assert.equal(preview.reportAnswer(ready, { kind: 'zip', fmt: 'txt', round: 1 })[0], 400);
  const running = fixture('encounter-reading.json');
  assert.equal(preview.reportAnswer(running, { kind: 'draft', fmt: 'txt', round: 1 })[0], 409, 'nothing is exported while a review runs');
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
    assert.deepEqual(calls.pop(), { assign: '/login/?next=%2F' });
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
// dropped (R3); an occurrence is a stretch of it that begins and ends where one character ends and the next begins and
// NFKC of the whole text is cut cleanly, begins with a character that is not only white space, and whose NFKC, white space
// dropped, is the quote's; the first such stretch is the shortest. Where the quote's first character that is not white
// space begins with a letter or a digit, the code point just before the stretch is none of a letter, a digit or a mark,
// and where its last does, the code point just after it (R2; the text's start and end are edges); a stretch turned away
// takes nothing. They are taken left to right without overlap, exact-case first; returned in the given text's offsets.
function bruteOccurrences(given, quote) {
  const nfkc = value => value.normalize('NFKC');
  const fold = value => nfkc(value).replace(/\s+/gu, '');
  const boundsOf = value => {
    const whole = nfkc(value);
    return [...new Intl.Segmenter('en', { granularity: 'grapheme' }).segment(value)].map(segment => segment.index)
      .concat(value.length).filter(at => nfkc(value.slice(0, at)) + nfkc(value.slice(at)) === whole);
  };
  const { text, origin } = dropFormat(given);
  const bounds = boundsOf(text);
  const asked = dropFormat(quote).text;
  const want = fold(asked);
  const own = boundsOf(asked);
  const characters = own.slice(0, -1).map((at, index) => fold(asked.slice(at, own[index + 1]))).filter(Boolean);
  const keeps = character => Boolean(character) && /^[\p{L}\p{N}]/u.test(character);
  const edges = { start: keeps(characters[0]), end: keeps(characters[characters.length - 1]) };
  const joins = point => point !== undefined && /^[\p{L}\p{N}\p{M}]$/u.test(String.fromCodePoint(point));
  let turned = false;
  const scan = same => {
    const found = [];
    let from = 0;
    bounds.forEach((start, index) => {
      if (!want || start < from || index === bounds.length - 1 || !fold(text.slice(start, bounds[index + 1]))) return;
      for (let next = index + 1; next < bounds.length; next += 1) {
        if (same(fold(text.slice(start, bounds[next])))) {
          const end = bounds[next];
          if ((edges.start && joins([...text.slice(0, start)].pop()?.codePointAt(0))) || (edges.end && joins(text.codePointAt(end)))) {
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

test('the matcher agrees with the rule stated by brute force on pages of accents, jamo, kana, ligatures and emoji split into items', () => {
  const alphabet = ['a', 'e', 'E', 'q', ' ', '\n', '́', '̖', '̀', 'é', 'É', 'ﬁ', 'f', 'i', 'I', 'İ',
    'ᄒ', 'ᅡ', 'ᆫ', '하', '한', 'ㅎ', 'ㅏ', 'ㄳ', 'ｶ', 'ﾞ', 'カ', 'ガ', '\u{1F469}',
    '‍', '\u{1F4BB}', '\u{1F1FA}', '\u{1F1F8}', '¨', 'ß', 'S', 'k', 'K', 'क', '्', 'ष', 'େ',
    'ା', '½', '1', '⁄', '2', ' ', '　', '゛', 'か'];
  let seed = 20261120;
  const random = bound => {
    seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
    return (seed >>> 8) % bound;
  };
  let marked = 0;
  let turned = 0;
  for (let trial = 0; trial < 4000; trial += 1) {
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
    const expected = bruteOccurrences(text, quote);
    if (expected.turned) turned += 1;
    assert.deepEqual([...spans.keys()].sort((a, b) => a - b).map(key => spans.get(key)), expected.found, label);
    assert.equal(result.count, expected.found.length, label);
    if (expected.found.length) {
      assert.equal(result.caseBlind, expected.caseBlind, label);
      marked += 1;
    }
  }
  assert.ok(marked > 600, `the trials mark often enough to mean something (${marked})`);
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

// A text item as the PDF library reads it: its string, its transform (font size, origin) and whether a line ends after it.
function item(str, x = 0, y = 0, { size = 10, eol = false } = {}) {
  return { str, transform: [size, 0, 0, size, x, y], hasEOL: eol };
}

test('R1: text drawn again over itself to look bold is one occurrence, never marked, and does not break a passage that crosses it', () => {
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
  // what makes a copy, part by part
  const copies = items => [...app.overprintCopies(items)];
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51, 700)]), [1], 'within max(1, 0.2 x 10) = 2 units');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 52, 700)]), [1], 'exactly 2 units: within');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 52.01, 700)]), [], 'just beyond');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51.2, 701.5)]), [1], 'the distance is measured as a straight line (1.2, 1.5: 1.92)');
  assert.deepEqual(copies([item('Polyp', 50, 700), item('Polyp', 51.3, 701.6)]), [], '(1.3, 1.6: 2.06)');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 2 }), item('Polyp', 50.9, 700, { size: 2 })]), [1], 'a small font: at least 1 unit');
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 2 }), item('Polyp', 51.1, 700, { size: 2 })]), []);
  assert.deepEqual(copies([item('Polyp', 50, 700, { size: 30 }), item('Polyp', 55.9, 700, { size: 30 })]), [1], 'a large font: 0.2 x 30 = 6 units');
  // the font height is hypot(transform[2], transform[3]) of the later item: a rotated font has the same height
  assert.deepEqual(copies([item('Polyp', 50, 700), { str: 'Polyp', transform: [0, 10, -10, 0, 51.9, 700], hasEOL: false }]), [1]);
  assert.deepEqual(copies([item('Polyp', 50, 700), item('polyp', 50.3, 700)]), [], 'another case is another string');
  assert.deepEqual(copies([item('ﬁ', 50, 700), item('fi', 50.3, 700)]), [1], 'equal after NFKC');
  assert.deepEqual(copies([item(' ', 50, 700), item(' ', 50.3, 700)]), [], 'white space alone is never a copy');
  assert.deepEqual(copies([item('', 50, 700), item('', 50, 700)]), []);
  // the earlier item is one of the eight items before it
  const between = n => [item('Polyp', 50, 700), ...Array.from({ length: n }, (_, i) => item(`w${i}`, 100 + i * 20, 700)), item('Polyp', 50.3, 700)];
  assert.deepEqual(copies(between(7)), [8], 'seven items between: the original is the eighth before');
  assert.deepEqual(copies(between(8)), [], 'eight items between: the original is the ninth before');
  // bare strings carry no geometry: never a copy
  assert.deepEqual(copies(['Polyp', 'Polyp']), []);
  assert.deepEqual(copies([{ str: 'Polyp' }, { str: 'Polyp', transform: [10, 0, 0, 10, 0, 0] }]), []);
  // the same words drawn at another place are two occurrences
  const twice = app.locateQuote({ text: 'Polyp', page: 1 }, [[item('Polyp', 50, 700, { eol: true }), item('Polyp', 50, 600, { eol: true })]]);
  assert.equal(twice.count, 2);
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
  // what is read before and after: the items' strings in order, joined with nothing between them - two items with no
  // space between run their words together - and a line break after an item the library ends a line with
  assert.equal(count('polyp', [['the', 'polyp', 's']]), 0, 'no space between the items: inside a word');
  assert.equal(count('polyp', [[item('the', 0, 0, { eol: true }), item('polyp', 0, -12, { eol: true }), item('s', 0, -24)]]), 1, 'line breaks between them: a word');
  // a letter, a digit or a combining mark joins a word; another character does not
  assert.equal(count('polyp', [['xpolyp']]), 0);
  assert.equal(count('polyp', [['2polyp']]), 0);
  assert.equal(count('polyp', [['́polyp']]), 0, 'a mark before it');
  assert.equal(count('polyp', [['épolyp']]), 0, 'an accented letter before it');
  assert.equal(count('polyp', [['\u{1D49C}polyp']]), 0, 'an astral letter before it (read as one character, not half of one)');
  assert.equal(count('polyp', [['-polyp/']]), 1);
  assert.equal(count('polyp', [[' polyp ']]), 1, 'other spaces are edges');
  // an overprint copy is not read as the character before: what is read is the page's text, copies left out
  assert.equal(count('polyp', [[item('polyp', 10, 0), item('polyp', 10.3, 0)]]), 1, 'the copy right after it is not read');
  assert.equal(count('polyp', [[item('polyp', 10, 0), item('polyp', 30, 0)]]), 0, 'two drawings apart: one word "polyppolyp"');
  // a place turned away is passed over by one unit only, so a word right after it is still found
  assert.equal(count('aa', [['a aa']]), 1, 'not "a a" (inside "a aa"), but "aa"');
  assert.deepEqual(app.locateQuote({ text: 'aa', page: 1 }, [['a aa']]).marks, { 1: [{ item: 0, start: 2, end: 4, occurrence: 0 }] });
  assert.equal(count('aa', [['aaaa']]), 0, 'one word: none of it is these words');
  // case-blind keeps to the edges as exact case does
  assert.equal(app.locateQuote({ text: 'PAIN', page: 1 }, page).count, 1);
  // the quote's own first and last characters decide: a letter with its accent counts as a letter, a final mark too
  assert.equal(count('café', [['cafés']]), 0);
  assert.equal(count('café', [['café s']]), 1);
  assert.deepEqual(app.quoteEdges(app.pageText(['.polyp'])), { start: false, end: true });
  assert.deepEqual(app.quoteEdges(app.pageText(['q́'])), { start: true, end: true }, 'the last character is q with its accent');
  assert.deepEqual(app.quoteEdges(app.pageText([' (x) '])), { start: false, end: false });
  // continuation: the edges are read in the two pages - the start on the quote's page, the end on the next
  const pages = [['It ends with the start of a'], ['passage that runs on.']];
  assert.equal(app.locateQuote({ text: 'the start of a passage', page: 1 }, pages).scope, 'continued');
  assert.equal(app.locateQuote({ text: 'he start of a passage', page: 1 }, pages).status, 'not_found', 'its start is inside "the"');
  assert.equal(app.locateQuote({ text: 'the start of a passag', page: 1 }, pages).status, 'not_found', 'its end is inside "passage"');
  // a text document keeps its own rule (findPassages): no word edges there
  assert.deepEqual(app.findPassages('bathe ending', 'the end'), [[2, 9]]);
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
  assert.match(template, /<body data-pdf-module="\{% static 'studio\/lib\/pdfjs-6\.5\.438\/legacy\/build\/pdf\.min\.mjs' %\}" data-pdf-worker="\{% static 'studio\/lib\/pdfjs-6\.5\.438\/legacy\/build\/pdf\.worker\.min\.mjs' %\}">/);
  const bundle = fs.readFileSync(BUNDLE, 'utf8');
  assert.ok(!/pdf(\.worker)?\.min\.mjs/.test(bundle), 'the bundle reads the addresses from the page');
  // the image decoders and standard fonts are the package's own folders, two up from the legacy worker
  assert.match(bundle, /wasmUrl: new URL\('\.\.\/\.\.\/wasm\/', worker\)\.href, standardFontDataUrl: new URL\('\.\.\/\.\.\/standard_fonts\/', worker\)\.href,/);
  // the worker is started first and given to the document, so a worker that cannot start is told apart from a document
  // the library refuses (the note says which)
  assert.match(bundle, /viewer\.worker = new library\.PDFWorker\(\{ verbosity: library\.VerbosityLevel\.ERRORS \}\);\n\s+await viewer\.worker\.promise;/);
  assert.match(bundle, /\n\s+worker: viewer\.worker,\n/);
  // the library is opened with no eval, no WebAssembly, no XFA and the page drawn on the main thread, from the view address
  assert.match(bundle, /library\.getDocument\(\{\n\s+url: viewer\.view, withCredentials: false, isEvalSupported: false, enableXfa: false, useWasm: false,/);
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
