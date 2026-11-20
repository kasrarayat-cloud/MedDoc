'use strict';
// Unit tests for the customer page, studio/static/studio/app.js, over the customer contract customer-2026-11-20 (the
// build specification, sections 6 and 7) and its fixtures in tests/fixtures/customer. Run: node --test tests/frontend/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const app = require('../../studio/static/studio/app.js');
const preview = require('../../ops/dev_preview_server.cjs');

const ROOT = path.join(__dirname, '..', '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'customer');
const BUNDLE = path.join(ROOT, 'studio', 'static', 'studio', 'app.js');
const STYLES = path.join(ROOT, 'studio', 'static', 'studio', 'styles.css');
const TEMPLATES = path.join(ROOT, 'studio', 'templates', 'studio');
const DENYLIST = path.join(ROOT, 'ops', 'verification', 'customer-denylist.json');
const fixture = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const ENCOUNTERS = fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort();
const clone = value => JSON.parse(JSON.stringify(value));
const UUID = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';

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
// with the session fixture, and anything else with 201 {}. Work the page leaves running finishes before the page goes.
async function withPage({ elements = {}, answers = [] } = {}, fn) {
  const saved = { document: global.document, fetch: global.fetch, location: global.location };
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
  const before = { doc: app.state.doc, session: app.state.session, route: app.state.route, review: app.state.review, answers: app.state.answers, leaving: app.state.leaving, outdated: app.state.outdated };
  try {
    await fn({ calls, element });
  } finally {
    await new Promise(resolve => setImmediate(resolve));
    clearTimeout(app.state.toastTimer);
    Object.assign(global, saved);
    Object.assign(app.state, before, { pending: new Set() });
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
  assert.equal(app.CLIENT_VERSION, 'customer-2026-11-20');
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

const KEYS = {
  encounter: ['id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'context', 'progress', 'round', 'codes', 'questions', 'answers', 'notes', 'readiness', 'reports', 'activity'],
  permissions: ['can_review'],
  document: ['name', 'media_type', 'size', 'kind', 'original_url', 'view_url'],
  context: ['service_date', 'insurance'],
  progress: ['phase', 'busy', 'started_at', 'finished_at', 'server_time', 'message', 'can_stop', 'can_resume', 'can_retry', 'error'],
  error: ['text'],
  round: ['number', 'trigger', 'finished_at'],
  code: ['code', 'units', 'modifiers', 'status', 'status_label', 'reason', 'second_check', 'question', 'quotes', 'decision', 'allowed_actions'],
  second_check: ['agrees', 'reason'],
  quote: ['text', 'page'],
  decision: ['action', 'by', 'at', 'note'],
  question: ['id', 'text', 'codes'],
  answer: ['question', 'answer', 'by', 'at'],
  readiness: ['draft', 'approved', 'blockers'],
  report: ['id', 'kind', 'fmt', 'filename', 'generated_at', 'download_url', 'current'],
  activity: ['at', 'text'],
  session: ['user', 'workspace', 'role', 'can_review', 'acknowledgement', 'counts'],
  row: ['id', 'title', 'state', 'state_label', 'service_date', 'insurance', 'created_at', 'kind'],
};
const keysOf = value => Object.keys(value).sort();
const same = (value, name, where) => assert.deepEqual(keysOf(value), [...KEYS[name]].sort(), `${where}: ${name}`);

test('every customer fixture has exactly the keys of the customer contract (section 6)', () => {
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    same(doc, 'encounter', name);
    same(doc.permissions, 'permissions', name);
    same(doc.document, 'document', name);
    same(doc.context, 'context', name);
    same(doc.progress, 'progress', name);
    assert.ok(app.PHASES.includes(doc.progress.phase), name);
    if (doc.progress.error !== null) same(doc.progress.error, 'error', name);
    if (doc.round !== null) same(doc.round, 'round', name);
    same(doc.readiness, 'readiness', name);
    assert.equal(doc.state_label, app.STATE_LABELS[doc.state], name);
    assert.ok(['medicare', 'medicaid', 'commercial', 'unknown'].includes(doc.context.insurance), name);
    for (const code of doc.codes) {
      same(code, 'code', `${name} ${code.code}`);
      same(code.second_check, 'second_check', `${name} ${code.code}`);
      assert.ok(Object.hasOwn(app.CODE_STATUSES, code.status), `${name} ${code.code}`);
      assert.equal(code.status_label, app.CODE_STATUSES[code.status][0], `${name} ${code.code}`);
      for (const quote of code.quotes) same(quote, 'quote', `${name} ${code.code}`);
      if (code.decision !== null) same(code.decision, 'decision', `${name} ${code.code}`);
      // section 6: ready and needs_review take approve and reject; needs_answer and not_supported none; a decision, revoke
      const expected = code.decision ? ['revoke'] : ['ready', 'needs_review'].includes(code.status) ? ['approve', 'reject'] : [];
      assert.deepEqual(code.allowed_actions, expected, `${name} ${code.code}`);
    }
    for (const question of doc.questions) same(question, 'question', name);
    for (const answer of doc.answers) same(answer, 'answer', name);
    for (const report of doc.reports) same(report, 'report', name);
    for (const item of doc.activity) same(item, 'activity', name);
    assert.ok(doc.notes.every(note => typeof note === 'string'), name);
  }
  for (const name of ['session.json', 'session-agent.json']) same(fixture(name), 'session', name);
  for (const row of fixture('encounters.json').encounters) same(row, 'row', row.id);
});

test('the fixtures cover every state the page draws, and the list matches them', () => {
  const states = Object.fromEntries(ENCOUNTERS.map(name => [name, [fixture(name).state, fixture(name).progress.phase]]));
  assert.deepEqual(states, {
    'encounter-awaiting-answer.json': ['awaiting_answer', 'done'], 'encounter-checking.json': ['processing', 'checking'],
    'encounter-failed.json': ['failed', 'failed'], 'encounter-needs-review.json': ['needs_review', 'done'],
    'encounter-no-codes.json': ['no_codes', 'done'], 'encounter-reading.json': ['processing', 'reading'],
    'encounter-ready.json': ['ready', 'done'], 'encounter-reviewed.json': ['reviewed', 'done'],
  });
  const rows = fixture('encounters.json').encounters;
  assert.equal(rows.length, ENCOUNTERS.length);
  for (const row of rows) {
    const doc = ENCOUNTERS.map(fixture).find(item => item.id === row.id);
    assert.ok(doc, row.id);
    assert.deepEqual([row.title, row.state, row.state_label, row.service_date, row.insurance, row.kind],
      [doc.title, doc.state, doc.state_label, doc.context.service_date, doc.context.insurance, doc.document.kind]);
  }
  assert.equal(fixture('session.json').counts.queue, rows.filter(app.inQueue).length);
  assert.deepEqual(fixture('encounters-empty.json'), { encounters: [] });
});

test('every quote in the fixtures is the synthetic document\'s own text, on the page it names', () => {
  let checked = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const source = preview.SYNTHETIC_DOCUMENTS[preview.documentFor(doc)];
    assert.ok(source, name);
    assert.match(source.pages[0][0], /^SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT/, name);
    const pdf = source.type === 'application/pdf';
    assert.equal(doc.document.media_type, source.type, name);
    for (const code of doc.codes) {
      for (const quote of code.quotes) {
        if (pdf) assert.ok(source.pages[quote.page - 1]?.includes(quote.text), `${name} ${code.code}: ${quote.text}`);
        else assert.ok(quote.page === null && source.pages.flat().includes(quote.text), `${name} ${code.code}: ${quote.text}`);
        checked += 1;
      }
    }
    assert.match(doc.title, /^Synthetic /, name);
  }
  assert.ok(checked >= 15, checked);
});

test('the preview server\'s synthetic originals are a real two-page PDF and plain text', () => {
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
  const note = preview.documentBytes('synthetic-colonoscopy-note.txt');
  assert.match(note.type, /^text\/plain/);
  assert.match(note.bytes.toString('utf8'), /descending colon was removed\./);
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
    ready: 'Ready for approval', reviewed: 'Reviewed', no_codes: 'No codes found',
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
    // the original: an iframe of view_url, and the download of the original when there is one
    const viewer = page.one('#documentViewer');
    assert.ok(viewer && viewer.tag === 'iframe', name);
    assert.equal(viewer.attr('src'), doc.document.view_url, name);
    assert.ok(viewer.attr('title'), name);
    const download = page.one('#downloadOriginal');
    if (doc.document.original_url) assert.deepEqual([download.attr('href'), download.text, download.attr('download')], [doc.document.original_url, 'Download original', ''], name);
    else assert.equal(download, null, name);
    // every quote, once, in the quotes panel
    const quotes = page.all('#quotesPanel .quote[data-code][data-page]');
    assert.deepEqual(quotes.map(quote => [quote.attr('data-code'), quote.attr('data-page')]),
      doc.codes.flatMap(code => code.quotes.map(quote => [code.code, quote.page === null ? '' : String(quote.page)])), name);
    assert.equal(page.all('.quote').length, quotes.length, `${name}: .quote is the quotes panel's only`);
    // progress: the phase and the three steps
    const panel = page.one('section.progress-panel[data-phase]');
    assert.equal(panel.attr('data-phase'), doc.progress.phase, name);
    assert.deepEqual(panel.all('.progress-step[data-step][data-state]').map(step => step.attr('data-step')), ['reading', 'checking', 'finished'], name);
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
    // the codes, in the served order, with the hooks the walk reads
    const rows = page.all('ol#codesList > li.code-row[data-code][data-status]');
    assert.deepEqual(rows.map(row => [row.attr('data-code'), row.attr('data-status')]), doc.codes.map(code => [code.code, code.status]), name);
    rows.forEach((row, index) => {
      const code = doc.codes[index];
      for (const hook of ['.code-number', '.code-units', '.code-modifiers', '.status[data-status]', '.code-reason', '.code-check', '.code-quotes']) {
        assert.ok(row.one(hook), `${name} ${code.code} ${hook}`);
      }
      assert.equal(row.one('.code-number').text, code.code);
      assert.equal(row.one('.code-units').text, code.units === 1 ? '1 unit' : `${code.units} units`);
      assert.equal(row.one('.code-reason').text, code.reason);
      assert.match(row.one('.code-check').text, code.second_check.agrees ? /^Second check: agrees\./ : /^Second check: disagrees\./);
      assert.ok(row.one('.code-check').text.endsWith(code.second_check.reason));
    });
    // documentation notes once the review is done; earlier answers under the questions
    assert.equal(Boolean(page.one('section#notesPanel')), doc.progress.phase === 'done' || doc.notes.length > 0, name);
    assert.deepEqual(page.all('#notesPanel .notes-list li').map(item => item.text), doc.notes, name);
    assert.deepEqual(page.all('#answersPanel .answer-item .answer-text').map(item => item.text), doc.answers.map(item => item.answer), name);
    // the export button
    assert.equal(page.all('[data-action="export"]').length > 0, doc.codes.length > 0 || doc.reports.length > 0, name);
  }
});

test('only the actions in allowed_actions are drawn, as button[data-decision][data-code], and only for a reviewer', () => {
  let drawn = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const page = dom(render(doc));
    for (const code of doc.codes) {
      const row = page.one(`li.code-row[data-code="${code.code}"]`);
      const buttons = row.all('button[data-decision][data-code]');
      assert.deepEqual(buttons.map(button => [button.attr('data-decision'), button.attr('data-code')]), code.allowed_actions.map(action => [action, code.code]), `${name} ${code.code}`);
      drawn += buttons.length;
      for (const button of buttons) assert.equal(button.text.trim(), { approve: 'Approve', reject: 'Reject', revoke: 'Undo' }[button.attr('data-decision')]);
    }
    // a member who may not review gets none, whatever the server lists
    const viewer = clone(doc);
    viewer.permissions.can_review = false;
    assert.equal(dom(render(viewer)).all('button[data-decision]').length, 0, name);
  }
  assert.ok(drawn >= 15, drawn);
  // an action the page does not know is never drawn, and the order is fixed
  const code = { code: '45385', status: 'ready', allowed_actions: ['confirm', 'reject', 'approve', 'reinstate'] };
  assert.deepEqual(app.allowedActions(code, { permissions: { can_review: true } }), ['approve', 'reject']);
  assert.deepEqual(app.allowedActions(code, { permissions: {} }), []);
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
  assert.equal(app.unitsLabel(0), '');
  assert.equal(app.secondCheck({ second_check: { agrees: null, reason: '' } }).label, 'Second check: no verdict.');
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
  assert.deepEqual(panel.slice(0, 3), ['43239#0', '43239#1', '45385#0']);
  assert.deepEqual(page.all('li.code-row .code-quote').map(quote => quote.attr('data-view-page')), ['1', '1', '2', '2', '2']);
  assert.equal(page.one('#quotesPanel .quote').one('.quote-page').text, 'Page 1');
  assert.match(page.one('#quotesPanel .quotes-lead').text, /open its page/);
  // a text document's quotes carry no page, and the panel says they are found in the document
  const text = dom(render(fixture('encounter-awaiting-answer.json')));
  assert.deepEqual(text.all('#quotesPanel .quote').map(quote => quote.attr('data-page')), ['', '', '']);
  assert.match(text.one('#quotesPanel .quotes-lead').text, /find it in the document/);
});

test('the viewer shows a PDF or a text in the page, never a Word file, and a missing view says so', () => {
  const base = { view_url: `/api/encounters/${UUID}/original?view=1`, original_url: `/api/encounters/${UUID}/original`, kind: 'upload' };
  assert.equal(app.viewerKind({ ...base, media_type: 'application/pdf' }), 'pdf');
  assert.equal(app.viewerKind({ ...base, media_type: 'text/plain; charset=utf-8' }), 'text');
  assert.equal(app.viewerKind({ ...base, media_type: '', name: 'x.pdf' }), 'pdf');
  assert.equal(app.viewerKind({ ...base, media_type: null, kind: 'paste' }), 'text');
  assert.equal(app.viewerKind({ ...base, media_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', name: 'x.docx' }), 'other');
  assert.equal(app.viewerKind({ ...base, view_url: null, media_type: 'application/pdf' }), 'none');
  const word = clone(fixture('encounter-ready.json'));
  word.document = { ...word.document, name: 'synthetic.docx', media_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
  const page = dom(render(word));
  assert.equal(page.one('iframe'), null);
  assert.match(page.one('.viewer-empty').text, /cannot be shown on this page\. Download the original/);
  assert.equal(page.one('#downloadOriginal').attr('href'), word.document.original_url);
  const gone = clone(word);
  gone.document.view_url = 'https://evil.test/x';
  gone.document.original_url = 'javascript:alert(1)';
  const empty = dom(render(gone));
  assert.equal(empty.one('iframe'), null);
  assert.equal(empty.one('#downloadOriginal'), null);
  // a passage promises to be shown only where a viewer can show it
  assert.equal(page.one('#quotesPanel .quote').attr('title'), null);
  assert.equal(page.one('.code-quote').attr('title'), null);
  assert.equal(dom(render(fixture('encounter-ready.json'))).one('#quotesPanel .quote').attr('title'), 'Show this passage in the document');
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

test('polling follows the review: queued, reading and checking poll; finished, failed and stopped do not', () => {
  assert.equal(app.shouldPoll(fixture('encounter-reading.json')), true);
  assert.equal(app.shouldPoll(fixture('encounter-checking.json')), true);
  for (const name of ['encounter-ready.json', 'encounter-failed.json', 'encounter-no-codes.json', 'encounter-awaiting-answer.json']) assert.equal(app.shouldPoll(fixture(name)), false, name);
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
  assert.equal(dom(render(fixture('encounter-reading.json'))).one('#notesPanel'), null);
});

test('empty code lists say why, in the review\'s own state', () => {
  assert.equal(app.emptyCodesText(fixture('encounter-reading.json')), 'Codes appear here when the coding review finishes.');
  assert.equal(app.emptyCodesText(fixture('encounter-failed.json')), 'No codes: the coding review could not finish.');
  assert.equal(app.emptyCodesText(fixture('encounter-no-codes.json')), 'The coding review found no CPT code to report for this document.');
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
  assert.equal(app.tallyText(fixture('encounter-no-codes.json')), 'No codes yet');
  const options = doc => dom(app.exportOptions(doc)).all('.export-option').map(option => [option.attr('data-export-kind'), option.attr('data-export-fmt'), option.attr('disabled') === null]);
  assert.deepEqual(options(fixture('encounter-ready.json')), [['draft', 'txt', true], ['draft', 'csv', true], ['approved', 'txt', false], ['approved', 'csv', false]]);
  assert.deepEqual(options(fixture('encounter-reviewed.json')), [['draft', 'txt', true], ['draft', 'csv', true], ['approved', 'txt', true], ['approved', 'csv', true]]);
  assert.deepEqual(options(fixture('encounter-reading.json')).map(option => option[2]), [false, false, false, false]);
  assert.deepEqual(dom(app.exportOptions(fixture('encounter-ready.json'))).all('.export-blockers li').map(item => item.text), ['No code has been approved.']);
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    if (doc.readiness.approved !== true) assert.doesNotMatch(app.exportStatusText(doc), /is approved/, name);
  }
  // an export from an earlier coding review is still linked, and says so
  const reports = dom(app.exportOptions(fixture('encounter-reviewed.json'))).all('.report-item');
  assert.deepEqual(reports.map(item => [item.attr('class'), item.one('a').attr('href')]), [
    ['report-item earlier', '/api/reports/f6100000-0000-4000-8000-000000000001/download'], ['report-item', '/api/reports/f6100000-0000-4000-8000-000000000002/download']]);
  assert.match(reports[0].one('small').text, /Earlier: made from an earlier coding review/);
  assert.equal(dom(app.reportItem({ filename: 'x.txt', download_url: 'javascript:alert(1)', current: true })).one('a'), null);
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
  assert.deepEqual(queue, ['#doc/f3000000-0000-4000-8000-000000000001', '#doc/f4000000-0000-4000-8000-000000000001', '#doc/f5000000-0000-4000-8000-000000000001']);
  assert.match(app.listDescription('queue', rows), /^3 documents wait on you: questions to answer, or codes to review or approve\.$/);
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
    // keep the structure the page needs to draw everything: statuses, actions, phase and the addresses
    doc.codes.forEach((code, index) => Object.assign(code, { status: plain.codes[index].status, allowed_actions: plain.codes[index].allowed_actions, decision: code.decision && { ...code.decision, action: plain.codes[index].decision.action } }));
    Object.assign(doc.progress, { phase: plain.progress.phase });
    Object.assign(doc.document, { view_url: plain.document.view_url, original_url: plain.document.original_url, media_type: plain.document.media_type, kind: plain.document.kind });
    const html = [markup(doc), app.listBody('documents', [poison(fixture('encounters.json').encounters[0])]), app.inviteMarkup([poison(fixture('encounters.json').encounters[0])])].join('\n');
    assert.doesNotMatch(html, /<img/i, name);
    assert.doesNotMatch(html, /\son\w+="/i, `${name}: no handler attribute`);
    assert.doesNotMatch(html, /="[^"]*"[^\s>/]/, `${name}: no attribute breakout`);
    assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;&quot;&#x27;&#x60;&amp;/, name);
    // the model's own words are shown as written, once decoded
    const page = dom(render(doc));
    for (const code of doc.codes) {
      const row = page.all('li.code-row').find(item => item.attr('data-code') === code.code);
      assert.ok(row, `${name} ${code.code}`);
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
  assert.ok(page.one('dialog#reviewDialog textarea#reviewNote'));
  assert.ok(page.one('dialog#reviewDialog button#saveReview[type="submit"]'));
  for (const id of ['uploadDialog', 'reviewDialog', 'exportDialog', 'aboutDialog']) assert.ok(page.one(`dialog#${id}`), id);
  assert.equal(page.all('dialog').length, 4);
});

test('Approve opens the dialog with the session\'s statement; the approval posts {code, action, acknowledgement, note}', async () => {
  const session = fixture('session.json');
  const doc = fixture('encounter-ready.json');
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc, route: null });
    await app.handleDecision('approve', '45385', fakeElement());
    assert.equal(element('#reviewAckText').textContent, session.acknowledgement);
    assert.equal(element('#reviewAcknowledgement').hidden, false);
    assert.equal(element('#reviewAckBox').checked, false);
    assert.equal(element('#saveReview').disabled, true, 'no approval until the statement is confirmed');
    assert.equal(element('#reviewCode').textContent, '45385');
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
    assert.deepEqual(sent, { url: `/api/encounters/${doc.id}/decisions`, body: { code: '45385', action: 'approve', acknowledgement: session.acknowledgement, note: 'Read page 2.' } });
    const call = calls.find(item => item.method === 'POST');
    assert.deepEqual([call.headers['X-CSRFToken'], call.headers['X-CPT-Studio-Client'], call.headers['Content-Type'], call.credentials, call.cache],
      ['token123', 'customer-2026-11-20', 'application/json', 'same-origin', 'no-store']);
    assert.equal(element('#reviewDialog').open, false);
  });
});

test('Reject asks only for an optional note; Undo posts revoke; an action the server does not allow does nothing', async () => {
  const session = fixture('session-agent.json');
  await withPage({}, async ({ calls, element }) => {
    Object.assign(app.state, { session, doc: fixture('encounter-needs-review.json'), route: null });
    await app.handleDecision('reject', '45380', fakeElement());
    assert.equal(element('#reviewAcknowledgement').hidden, true);
    assert.equal(element('#reviewAckText').textContent, '');
    assert.equal(element('#saveReview').disabled, false);
    await app.submitReview({ preventDefault() {} });
    assert.deepEqual(posted(calls).pop().body, { code: '45380', action: 'reject', acknowledgement: '', note: '' });
    Object.assign(app.state, { doc: fixture('encounter-reviewed.json') });
    await app.handleDecision('revoke', '43239', fakeElement());
    assert.deepEqual(posted(calls).pop().body, { code: '43239', action: 'revoke', acknowledgement: '', note: '' });
    const before = calls.length;
    element('#reviewDialog').open = false;
    await app.handleDecision('approve', '43239', fakeElement());
    await app.handleDecision('revoke', '99999', fakeElement());
    assert.equal(calls.length, before);
    assert.equal(element('#reviewDialog').open, false);
  });
  // the agent's approval dialog says it is an agent-executed review, with the agent's own statement
  await withPage({}, async ({ element }) => {
    Object.assign(app.state, { session, doc: fixture('encounter-ready.json'), route: null });
    await app.handleDecision('approve', '43239', fakeElement());
    assert.equal(element('#reviewAckText').textContent, session.acknowledgement);
    assert.match(element('#reviewCopy').textContent, /agent-executed synthetic review/);
  });
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
