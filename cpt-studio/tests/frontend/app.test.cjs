'use strict';
// Unit tests for the customer page, studio/static/studio/app.js, over the customer contract customer-2026-11-21 (the
// build specification, sections 6 and 7, with the fix pass's line identity: every code row is named by its line, and a
// decision names the line and the coding review the page shows) and its fixtures in tests/fixtures/customer.
// Run: node --test tests/frontend/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
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
// the second check's own sentences where it gave no verdict (studio/customer.py ADDED_BY_CHECK, NOT_CHECKED)
const ADDED_BY_CHECK = 'The second check found this code; it needs your review.';
const NOT_CHECKED = 'The second check did not review this code.';

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
  global.document = { cookie: 'cptstudio_csrf=token123', querySelector: element, querySelectorAll: () => [], activeElement: null, hidden: false };
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
  assert.equal(app.CLIENT_VERSION, 'customer-2026-11-21');
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
      // the second check's reason without a verdict is one of the server's two sentences, and a code it gave none is
      // one that needs review
      if (code.second_check.agrees === null) {
        assert.ok([ADDED_BY_CHECK, NOT_CHECKED].includes(code.second_check.reason), `${name} ${code.code}`);
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
    doc.codes.forEach(code => assert.equal(code.line.startsWith('M'), code.second_check.reason === ADDED_BY_CHECK, `${name} ${code.line}`));
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
    // the original: an iframe of view_url when the server names a view type, else no viewer at all; the note under a
    // converted Word document's PDF; the download of the original when there is one
    const viewer = page.one('#documentViewer');
    if (doc.document.view_media_type) {
      assert.ok(viewer && viewer.tag === 'iframe', name);
      assert.equal(viewer.attr('src'), doc.document.view_url, name);
      assert.ok(viewer.attr('title'), name);
    } else {
      assert.equal(viewer, null, name);
      assert.equal(page.all('iframe').length, 0, name);
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
  // the contract's units are a positive integer or null; anything else is not a count the page can state
  for (const value of [null, undefined, 0, -1, 1.5, '2', NaN]) assert.equal(app.unitsLabel(value), 'Units not given', String(value));
  assert.equal(app.UNITS_NOT_GIVEN, 'Units not given');
  const doc = fixture('encounter-same-code.json');
  const row = dom(render(doc)).one('li.code-row[data-line="M1"]');
  assert.equal(doc.codes.find(code => code.line === 'M1').units, null);
  assert.deepEqual([row.one('.code-units').text, row.attr('data-units')], ['Units not given', '']);
  assert.equal(dom(render(doc)).one('li.code-row[data-line="L3"] .code-units').text, '1 unit');
});

test('quote page links: a page opens the viewer at view_url#page=N; a text quote has no page', () => {
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
  assert.match(page.one('#quotesPanel .quotes-lead').text, /open its page/);
  // a text document's quotes carry no page, and the panel says they are found in the document
  const text = dom(render(fixture('encounter-awaiting-answer.json')));
  assert.deepEqual(text.all('#quotesPanel .quote').map(quote => quote.attr('data-page')), ['', '', '']);
  assert.match(text.one('#quotesPanel .quotes-lead').text, /find it in the document/);
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
  assert.deepEqual(children, ['viewer-toolbar', 'viewer-frame', 'viewer-note', 'viewer-bottom'], 'the note sits under the viewer');
  assert.equal(panel.one('iframe#documentViewer').attr('src'), doc.document.view_url);
  assert.equal(panel.one('.viewer-note').text, app.CONVERTED_NOTE);
  assert.equal(panel.one('.viewer-name').text, 'synthetic-colonoscopy-report.docx');
  assert.equal(panel.one('#downloadOriginal').attr('href'), doc.document.original_url, 'the download is the Word file itself');
  // its quotes open their pages: the PDF's pages are the pages the quotes name
  const page = dom(render(doc));
  assert.match(page.one('#quotesPanel .quotes-lead').text, /open its page/);
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
  assert.deepEqual([check('45381').attr('data-check'), check('45381').text], ['none', ADDED_BY_CHECK]);
  assert.deepEqual(app.secondCheck({ second_check: { agrees: null, reason: ` ${ADDED_BY_CHECK} ` } }), { verdict: 'none', label: ADDED_BY_CHECK, reason: '' });
  // a verdict with no reason, or no verdict and no sentence: the verdict alone
  assert.deepEqual(app.secondCheck({ second_check: { agrees: false, reason: null } }), { verdict: 'disagrees', label: 'Second check: disagrees.', reason: '' });
  assert.deepEqual(app.secondCheck({ second_check: { agrees: null, reason: null } }), { verdict: 'none', label: 'Second check: no verdict.', reason: '' });
  assert.deepEqual(app.secondCheck({}), { verdict: 'none', label: 'Second check: no verdict.', reason: '' });
  assert.equal(app.tallyText(doc), '1 ready for approval · 2 need your review');
});

test('a quote opens its page in the PDF viewer; in the text viewer the passage is found instead', async () => {
  const frame = () => fakeElement({ src: 'unchanged', scrollIntoView() {} });
  const word = fixture('encounter-word.json');
  await withPage({ elements: { documentViewer: frame() } }, async ({ element }) => {
    Object.assign(app.state, { doc: word, route: null });
    app.showQuote('L2#0');
    assert.equal(element('#documentViewer').src, `${word.document.view_url}#page=1`);
    assert.equal(app.state.selectedQuote, 'L2#0');
    app.showQuote('M1#0');
    assert.equal(element('#documentViewer').src, `${word.document.view_url}#page=2`);
    app.showQuote('L9#0');
    app.showQuote('45381#0');
    assert.equal(app.state.selectedQuote, 'M1#0', 'a quote the page does not hold changes nothing');
  });
  // a text has no pages: even a quote that names one is looked for in the text, and the viewer is not moved
  const text = clone(fixture('encounter-awaiting-answer.json'));
  text.codes[0].quotes[0].page = 1;
  await withPage({ elements: { documentViewer: frame() } }, async ({ element }) => {
    Object.assign(app.state, { doc: text, route: null });
    app.showQuote('L1#0');
    assert.equal(element('#documentViewer').src, 'unchanged');
    assert.equal(app.state.selectedQuote, 'L1#0');
  });
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
      ['token123', 'customer-2026-11-21', 'application/json', 'same-origin', 'no-store']);
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
    assert.deepEqual(posted(calls).pop().body, { round: 2, line: 'L1', code: '43239', action: 'revoke', acknowledgement: '', note: '' });
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
    assert.deepEqual(posted(calls).pop().body, { round: 2, line: 'L3', code: '45380', action: 'revoke', acknowledgement: '', note: '' });
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
    assert.deepEqual(posted(calls).map(call => call.body), [{ round: 2, line: 'L2', code: '45385', action: 'revoke', acknowledgement: '', note: '' }]);
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
  assert.equal(preview.decisionAnswer(doc, body({ line: 'L3', action: 'revoke', acknowledgement: '' }), session)[0], 201);
  assert.equal(preview.decisionAnswer(doc, body({ acknowledgement: 'yes' }), session)[0], 400);
  const running = fixture('encounter-reading.json');
  assert.equal(preview.decisionAnswer(running, body({ round: 1 }), session)[0], 409, 'nothing is decided while a review runs');
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
