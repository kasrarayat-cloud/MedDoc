'use strict';
// Unit tests for the pure parts of the customer page, studio/static/studio/app.js, over the customer contract
// fixtures in tests/fixtures/customer (design section 7). Run: node --test tests/frontend/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const app = require('../../studio/static/studio/app.js');

const ROOT = path.join(__dirname, '..', '..');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'customer');
const BUNDLE = path.join(ROOT, 'studio', 'static', 'studio', 'app.js');
const fixture = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const ENCOUNTERS = fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort();
const UUID = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
const count = (haystack, needle) => haystack.split(needle).length - 1;
const clone = value => JSON.parse(JSON.stringify(value));

function cpSpan(source, needle, key, extra = {}) {
  const unit = source.indexOf(needle);
  assert.ok(unit >= 0, needle);
  const start = [...source.slice(0, unit)].length;
  return { key, start, end: start + [...needle].length, text: needle, exact: true, ...extra };
}

function ui(doc, extra = {}) {
  return { open: new Set(), answers: new Map(), ack: null, reconnecting: false, nowMs: Date.parse(doc?.progress?.server_time || '2026-11-03T00:00:00Z'), clock: 0, ...extra };
}

function render(doc, extra = {}) {
  return app.reviewView(doc, app.documentLayout(doc), ui(doc, extra));
}

// The markup's text nodes and attribute values, entities decoded - what a member can read or a tool can scrape.
const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' };
const decode = value => value.replace(/&(?:amp|lt|gt|quot|#x27|#x60);/g, entity => ENTITIES[entity]);
function parts(html) {
  const texts = [];
  const attributes = [];
  for (const piece of html.split(/(<[^>]*>)/)) {
    if (!piece) continue;
    if (piece.startsWith('<')) {
      for (const [, name, value] of piece.matchAll(/\s([\w:-]+)="([^"]*)"/g)) attributes.push([name, decode(value)]);
    } else {
      texts.push(decode(piece));
    }
  }
  return { texts, attributes };
}

// Internal machinery a customer must never read (design section 0.6): provider and model names, participants and peer
// review, usage, credits and tokens, request/response/run ids, hashes, trace links, rule ids and source keys, technical
// payloads.
const NAMES = /\b(?:corti|astra|fable|openai|anthropic|claude|gemini|google)\b|\bgpt-|\bclaude-|\bgemini-/i;
// (Clinical words stay out of this net: "diagnostic colonoscopy", "the operator", "with the exception of".)
const MACHINERY = /\b(?:participants?|peers?|providers?|vendors?|models?|tokens?|credits?|usage|traces?|tracing|harness|engine|pipeline|orchestrat\w*|replay|sha-?256|traceback|review2|(?:request|response|run|rule|check)[\s_-]?ids?|tool[\s_-]?calls?)\b|\bHTTP\s?\d{3}\b/i;
const RULE_IDS = /\b(?:confirmations|context|cpt|em|evidence|extraction|facts|mue|ncci|participants|pfs|provider|review|routing|scope|services?|units|gi)\.[a-z_]+\b|\bcms-[a-z]+(?:-[a-z0-9]+)*\b|\bcpt-studio:[a-z]+@|\b[a-z][\w-]*@(?:\d|cptstudio)|\b[0-9a-f]{40,64}\b/i;
function forbidden(value) {
  return [NAMES, MACHINERY, RULE_IDS].map(pattern => pattern.exec(value)?.[0]).filter(Boolean);
}

// Every forbidden word in a rendered page, text and attributes, leaving out only the document's own words (a text node
// that is a slice of the document's text: the member's own document is shown as it is).
function leaks(html, doc) {
  const own = String(doc?.document?.text || '');
  const { texts, attributes } = parts(html);
  const found = [];
  for (const value of texts) {
    const trimmed = value.trim();
    if (!trimmed || (own && own.includes(value))) continue;
    for (const word of forbidden(value)) found.push(`text "${word}" in ${JSON.stringify(trimmed.slice(0, 80))}`);
  }
  for (const [name, value] of attributes) for (const word of forbidden(value)) found.push(`${name}="${value.slice(0, 60)}" (${word})`);
  return found;
}

// Every piece of markup the customer page can draw for a document, in one string (the export status is plain text the
// page sets with textContent; the denylist scan reads it too, through everything()).
function markup(doc, extra = {}) {
  return [render(doc, extra), render(doc, { ...extra, open: new Set(['other-codes', 'activity', ...(doc.codes || []).map(code => `why:${code.id}`)]) }),
    app.exportOptions(doc), app.progressPanel(doc, ui(doc, { reconnecting: true, ack: { id: doc.id, at: Date.parse('2026-11-03T10:00:00Z') } }))].join('\n');
}

function everything(doc, extra = {}) {
  return `${markup(doc, extra)}\n<p>${app.escapeHtml(app.exportStatusText(doc))}</p>`;
}

// --- helpers kept from the earlier page -----------------------------------------------------------------------------

test('escapeHtml escapes every markup-significant character and tolerates empty values', () => {
  assert.equal(app.escapeHtml(`<a href="x" onclick='y'>&\`</a>`), '&lt;a href=&quot;x&quot; onclick=&#x27;y&#x27;&gt;&amp;&#x60;&lt;/a&gt;');
  assert.equal(app.escapeHtml(null), '');
  assert.equal(app.escapeHtml(undefined), '');
  assert.equal(app.escapeHtml(0), '0');
});

test('lookup only answers own keys, never prototype members', () => {
  assert.equal(app.lookup({ office: 'Office' }, 'office', 'x'), 'Office');
  assert.equal(app.lookup({ office: 'Office' }, 'constructor', 'fallback'), 'fallback');
  assert.equal(app.lookup({ office: 'Office' }, '__proto__', 'fallback'), 'fallback');
  assert.equal(app.lookup({ office: 'Office' }, 7, 'fallback'), 'fallback');
});

test('dates are formatted from their parts, so no time zone can shift the day', () => {
  assert.deepEqual(app.parseIsoDate('2026-10-21'), { year: 2026, month: 10, day: 21 });
  for (const bad of ['2026-02-30', '2026-13-01', '2026-1-01', '21/10/2026', '', null, undefined, '2026-10-21T00:00:00Z']) {
    assert.equal(app.parseIsoDate(bad), null, String(bad));
  }
  assert.equal(app.formatDate('2026-10-21'), '21 Oct 2026');
  assert.equal(app.formatDate('2026-10-01', true), '1 October 2026');
  assert.equal(app.formatDate('not a date'), '');
  assert.equal(app.formatTimestamp('2026-10-23T23:30:00Z'), '23 Oct 2026, 23:30 UTC');
  assert.equal(app.formatTimestamp('2026-10-23T23:30:00.123456+00:00'), '23 Oct 2026, 23:30 UTC');
  assert.equal(app.formatTimestamp('garbage'), '');
  assert.equal(app.formatTimestamp(null), '');
});

test('readCookie finds the named cookie only and survives malformed encoding', () => {
  const cookies = 'other=1; cptstudio_csrf=abc%3D123; cptstudio_csrf_x=no';
  assert.equal(app.readCookie(cookies, 'cptstudio_csrf'), 'abc=123');
  assert.equal(app.readCookie('a=1', 'cptstudio_csrf'), '');
  assert.equal(app.readCookie('cptstudio_csrf=%E0%A4%A', 'cptstudio_csrf'), '');
  assert.equal(app.readCookie('', 'cptstudio_csrf'), '');
});

test('safeDownloadUrl and safeOriginalUrl accept only same-origin paths of their own shape', () => {
  assert.equal(app.safeDownloadUrl(`/api/reports/${UUID}/download`), `/api/reports/${UUID}/download`);
  assert.equal(app.safeOriginalUrl(`/api/encounters/${UUID}/original`), `/api/encounters/${UUID}/original`);
  for (const bad of ['javascript:alert(1)', `//evil.example/api/reports/${UUID}/download`, `https://evil.example/api/reports/${UUID}/download`,
    `/api/reports/${UUID}/download?x=1`, '/api/reports/../session', `/api/reports/${UUID}/download/`, null, 42, `/api/encounters/${UUID}/original`]) {
    assert.equal(app.safeDownloadUrl(bad), '', String(bad));
  }
  for (const bad of [`/api/reports/${UUID}/download`, `/api/encounters/${UUID}/original?x`, 'javascript:alert(1)', null]) {
    assert.equal(app.safeOriginalUrl(bad), '', String(bad));
  }
});

test('polling starts at 2.5 s, backs off, and is bounded', () => {
  assert.equal(app.pollDelay(0, 0), 2500);
  assert.ok(app.pollDelay(1, 0) > 2500);
  assert.equal(app.pollDelay(50, 0), 15000);
  assert.equal(app.pollDelay(0, 1), 5000);
  assert.equal(app.pollDelay(0, 2), 10000);
  assert.equal(app.pollDelay(0, 12), 30000);
  for (let i = 1; i < 30; i += 1) assert.ok(app.pollDelay(i, 0) >= app.pollDelay(i - 1, 0));
});

test('routes resolve known views and fall back to the overview', () => {
  assert.deepEqual(app.parseRoute(''), { name: 'workspace' });
  assert.deepEqual(app.parseRoute('#documents'), { name: 'documents' });
  assert.deepEqual(app.parseRoute('#queue'), { name: 'queue' });
  assert.deepEqual(app.parseRoute('#how-it-works'), { name: 'how-it-works' });
  assert.deepEqual(app.parseRoute(`#doc/${UUID}`), { name: 'doc', id: UUID });
  assert.deepEqual(app.parseRoute('#doc'), { name: 'workspace' });
  assert.deepEqual(app.parseRoute('#main'), { name: 'workspace' });
  assert.deepEqual(app.parseRoute('#__proto__'), { name: 'workspace' });
  // the customer page has no diagnostics route
  assert.deepEqual(app.parseRoute(`#/encounters/${UUID}/trace`), { name: 'workspace' });
});

test('code-point offsets map onto UTF-16 units only when the text needs it', () => {
  assert.equal(app.codeUnitOffsets('plain ascii and é'), null);
  const offsets = app.codeUnitOffsets('a🩺b𝒳c');
  assert.deepEqual(offsets, [0, 1, 3, 4, 6, 7]);
});

test('overlapping spans merge into one mark carrying every key; touching spans stay apart', () => {
  const merged = app.mergeSpans([
    { key: 'b', start: 5, end: 9 }, { key: 'a', start: 0, end: 6 }, { key: 'c', start: 9, end: 12 },
    { key: 'd', start: 1, end: 2 }, { key: 'a', start: 3, end: 4 },
  ]);
  assert.deepEqual(merged, [{ start: 0, end: 9, keys: ['a', 'd', 'b'] }, { start: 9, end: 12, keys: ['c'] }]);
  assert.deepEqual(app.mergeSpans([]), []);
});

test('paragraphs split on blank lines, keep single newlines and drop no visible text', () => {
  const source = '\nFirst line\nsecond line\n\n  \n\nSecond paragraph\n\n\n';
  const ranges = app.paragraphRanges(source, 0, source.length);
  assert.deepEqual(ranges.map(([a, b]) => source.slice(a, b)), ['First line\nsecond line', 'Second paragraph']);
  assert.deepEqual(app.paragraphRanges('   \n\n  ', 0, 7), []);
});

test('layout marks exact spans by code point, across astral characters', () => {
  const source = '🩺 Header 𝒳\n\nThe colonoscope 🔬 was advanced to the cecum.';
  const span = cpSpan(source, 'was advanced to the cecum', 'p:0');
  const layout = app.layoutDocument(source, [{ page: 1, start: 0, end: [...source].length }], [span]);
  assert.deepEqual(layout.unlocated, []);
  const marks = layout.pages.flatMap(page => page.paragraphs.flat()).filter(piece => piece.keys);
  assert.deepEqual(marks.map(piece => [piece.text, piece.keys]), [['was advanced to the cecum', ['p:0']]]);
});

test('layout reports wrong, out-of-range, inexact and malformed spans as unlocated and never marks them', () => {
  const source = 'Alpha beta gamma.';
  const spans = [
    { key: 'wrong', start: 0, end: 5, text: 'Gamma', exact: true },
    { key: 'range', start: 10, end: 99, text: 'gamma.', exact: true },
    { key: 'flagged', start: 0, end: 5, text: 'Alpha', exact: false },
    { key: 'empty', start: 4, end: 4, text: '', exact: true },
    { key: 'float', start: 0.5, end: 5, text: 'Alpha', exact: true },
    { key: 'negative', start: -1, end: 5, text: 'Alpha', exact: true },
    { key: 'notext', start: 0, end: 5, exact: true },
    { key: 'good', start: 6, end: 10, text: 'beta', exact: true },
  ];
  const layout = app.layoutDocument(source, [], spans);
  assert.deepEqual(layout.unlocated, ['wrong', 'range', 'flagged', 'empty', 'float', 'negative', 'notext']);
  const marked = layout.pages[0].paragraphs.flat().filter(piece => piece.keys);
  assert.deepEqual(marked.map(piece => piece.text), ['beta']);
});

test('a span crossing paragraph and page boundaries is split per paragraph without the separators', () => {
  const pageOne = 'Page one ends here.\n\nNext paragraph starts';
  const pageTwo = 'page two continues.';
  const source = `${pageOne}\n\n${pageTwo}`;
  const pages = [{ page: 1, start: 0, end: pageOne.length }, { page: 2, start: pageOne.length + 2, end: source.length }];
  const crossParagraph = cpSpan(source, 'ends here.\n\nNext', 'x:0');
  const crossPage = cpSpan(source, 'starts\n\npage two', 'x:1');
  const layout = app.layoutDocument(source, pages, [crossParagraph, crossPage]);
  assert.equal(layout.pages.length, 2);
  const pieces = layout.pages.map(page => page.paragraphs.map(paragraph => paragraph.filter(piece => piece.keys).map(piece => piece.text)));
  assert.deepEqual(pieces, [[['ends here.'], ['Next', 'starts']], [['page two']]]);
  for (const page of layout.pages) for (const paragraph of page.paragraphs) {
    for (const piece of paragraph) assert.ok(!piece.text.includes('\n\n'));
  }
});

test('invalid page spans fall back to one page that keeps all of the text', () => {
  const source = 'One.\n\nTwo.\n\nThree.';
  for (const pages of [[{ page: 1, start: 5, end: 2 }], [{ page: 1, start: 0, end: 99 }], [{ page: 1, start: 0, end: 8 }, { page: 2, start: 4, end: 10 }], [{ page: '1', start: 0, end: 4 }], 'nope']) {
    const layout = app.layoutDocument(source, pages, []);
    assert.equal(layout.pages.length, 1, JSON.stringify(pages));
    assert.deepEqual(layout.pages[0].paragraphs.map(paragraph => paragraph.map(piece => piece.text).join('')), ['One.', 'Two.', 'Three.']);
  }
});

test('layout never inserts or loses visible text (seeded property check)', () => {
  let seed = 7;
  const random = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const alphabet = ['a', 'b', ' ', '\n', '\n\n', '🩺', 'é', '𝒳', '.', '\t', '<', '&'];
  for (let round = 0; round < 300; round += 1) {
    const source = Array.from({ length: 5 + Math.floor(random() * 60) }, () => alphabet[Math.floor(random() * alphabet.length)]).join('');
    const points = [...source];
    const spans = Array.from({ length: Math.floor(random() * 5) }, (_, i) => {
      const start = Math.floor(random() * points.length);
      const end = Math.min(points.length, start + 1 + Math.floor(random() * 12));
      return { key: `k:${i}`, start, end, text: points.slice(start, end).join(''), exact: true };
    });
    const cut = Math.floor(random() * points.length);
    const pages = [{ page: 1, start: 0, end: cut }, { page: 2, start: cut, end: points.length }];
    const layout = app.layoutDocument(source, pages, spans);
    const rendered = layout.pages.flatMap(page => page.paragraphs.map(paragraph => paragraph.map(piece => piece.text).join(''))).join('');
    assert.equal(rendered.replace(/\s/g, ''), source.replace(/\s/g, ''), JSON.stringify(source));
    assert.deepEqual(layout.unlocated, []);
    const offsets = app.codeUnitOffsets(source);
    const unit = point => (offsets ? offsets[point] : point);
    const covered = new Uint8Array(source.length);
    for (const span of spans) covered.fill(1, unit(span.start), unit(span.end));
    const ranges = app.pageRanges(pages, points.length, unit, source.length);
    layout.pages.forEach((page, index) => {
      const paragraphs = app.paragraphRanges(source, ranges[index].start, ranges[index].end);
      assert.equal(page.paragraphs.length, paragraphs.length);
      page.paragraphs.forEach((pieces, i) => {
        const [from, to] = paragraphs[i];
        assert.equal(pieces.map(piece => piece.text).join(''), source.slice(from, to));
        let cursor = from;
        for (const piece of pieces) {
          const marked = covered.subarray(cursor, cursor + piece.text.length);
          assert.ok(piece.keys ? marked.every(Boolean) : !marked.some(Boolean), JSON.stringify({ source, piece, cursor }));
          cursor += piece.text.length;
        }
      });
    });
  }
});

// --- the customer contract the fixtures follow (design section 7) ----------------------------------------------------

const CONTRACT = {
  // completion repair (2026-11-06, U11): 'earlier_answers', the answers no question asked now takes
  // FINAL-V2 amendment 1 (step 5d): 'update', 'earlier_codes', 'what_changed' and 'decision_history'
  top: ['id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'service_date', 'progress', 'checks', 'codes',
    'other_codes', 'not_separately_coded', 'details_needed', 'earlier_answers', 'unresolved', 'recheck', 'limitations', 'readiness', 'reports', 'activity',
    'update', 'earlier_codes', 'what_changed', 'decision_history'],
  update: ['pending', 'state', 'kind', 'restorable', 'changes', 'saved_by', 'saved_at', 'started_at', 'earlier'],
  update_earlier: ['made_at', 'revision', 'service_date', 'details'],
  what_changed: ['compared_with', 'details', 'codes', 'unchanged', 'decisions', 'answers'],
  history: ['code', 'action', 'by', 'by_kind', 'at', 'revision', 'why'],
  recheck: ['available', 'can_request'],
  document: ['kind', 'name', 'media_type', 'size', 'page_count', 'revision', 'text', 'pages', 'reading', 'original_url'],
  reading: ['status', 'label', 'messages'],
  service_date: ['value', 'source', 'document_value', 'document_quote', 'entered_value', 'conflict', 'can_use_document_date'],
  progress: ['phase', 'busy', 'steps', 'active_detail', 'started_at', 'finished_at', 'server_time', 'slow', 'message', 'can_stop', 'can_resume', 'can_leave', 'error'],
  step: ['key', 'label', 'state', 'started_at', 'finished_at'],
  check: ['key', 'label', 'state'],
  code: ['id', 'number', 'code', 'units', 'modifiers', 'modifier_review', 'status', 'status_label', 'sub_label', 'summary', 'why', 'detail_ids', 'allowed_actions', 'decision'],
  modifier_review: ['options', 'text', 'sources'],
  why: ['quotes', 'qualifications'],
  quote: ['text', 'start', 'end', 'page', 'exact'],
  decision: ['action', 'by', 'by_kind', 'at', 'note', 'modifiers'],
  // completion repair (2026-11-06, U10): the fact named, what CPT Studio could not confirm, the passages it concerns
  detail: ['id', 'fact', 'family_label', 'prompt', 'control', 'choices', 'allow', 'document_value', 'entered_value', 'quote', 'affects', 'saved', 'addendum_allowed',
    'missing', 'statement', 'passages'],
  passage: ['text', 'start', 'end', 'page'],
  earlier: ['answer_id', 'fact', 'family_label', 'prompt', 'affects', 'value', 'label', 'by', 'at', 'why', 'why_text'],
  saved: ['value', 'label', 'by', 'at', 'answer_id'],
  readiness: ['draft', 'approved', 'blockers'],
  report: ['id', 'kind', 'fmt', 'filename', 'generated_at', 'generated_by', 'download_url', 'current', 'revision'],
  activity: ['event', 'summary', 'actor', 'actor_kind', 'at'],
  session: ['user', 'workspace', 'role', 'can_review', 'acknowledgement', 'counts', 'synthetic_only'],
  row: ['id', 'title', 'state', 'state_label', 'service_date', 'date_conflict', 'open_details', 'created_at', 'kind', 'in_queue'],
};
const sorted = keys => [...keys].sort();

test('every customer fixture has exactly the keys of the customer contract (design section 7)', () => {
  assert.ok(ENCOUNTERS.length >= 10, ENCOUNTERS.join(' '));
  const states = new Set();
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const at = where => `${name}: ${where}`;
    assert.deepEqual(Object.keys(doc), CONTRACT.top, at('top'));
    assert.deepEqual(Object.keys(doc.permissions), ['can_review'], at('permissions'));
    assert.deepEqual(sorted(Object.keys(doc.document)), sorted(CONTRACT.document), at('document'));
    assert.deepEqual(sorted(Object.keys(doc.document.reading)), sorted(CONTRACT.reading), at('reading'));
    assert.deepEqual(sorted(Object.keys(doc.service_date)), sorted(CONTRACT.service_date), at('service_date'));
    assert.deepEqual(sorted(Object.keys(doc.progress)), sorted(CONTRACT.progress), at('progress'));
    assert.deepEqual(doc.progress.steps.map(step => step.key), app.STEP_KEYS, at('steps'));
    for (const step of doc.progress.steps) assert.deepEqual(sorted(Object.keys(step)), sorted(CONTRACT.step), at('step'));
    assert.deepEqual(doc.checks.map(check => check.key), app.CHECK_KEYS, at('checks'));
    for (const check of doc.checks) assert.deepEqual(sorted(Object.keys(check)), sorted(CONTRACT.check), at('check'));
    assert.ok(doc.progress.error === null || sorted(Object.keys(doc.progress.error)).join() === 'action,text', at('error'));
    for (const code of doc.codes) {
      assert.deepEqual(sorted(Object.keys(code)), sorted(CONTRACT.code), at(`code ${code.code}`));
      assert.deepEqual(sorted(Object.keys(code.why)), sorted(CONTRACT.why), at('why'));
      for (const quote of code.why.quotes) assert.deepEqual(sorted(Object.keys(quote)), sorted(CONTRACT.quote), at('quote'));
      if (code.modifier_review) assert.deepEqual(sorted(Object.keys(code.modifier_review)), sorted(CONTRACT.modifier_review), at('modifier_review'));
      if (code.decision) assert.deepEqual(sorted(Object.keys(code.decision)), sorted(CONTRACT.decision), at('decision'));
      assert.ok(['ready', 'needs_detail', 'approved', 'excluded'].includes(code.status), at(code.status));
    }
    for (const item of doc.other_codes) assert.deepEqual(sorted(Object.keys(item)), ['code', 'reason'], at('other_codes'));
    for (const item of doc.not_separately_coded) assert.deepEqual(sorted(Object.keys(item)), ['label', 'reason'], at('not_separately_coded'));
    for (const row of doc.details_needed) {
      assert.deepEqual(sorted(Object.keys(row)), sorted(CONTRACT.detail), at(`detail ${row.fact}`));
      if (row.saved) assert.deepEqual(sorted(Object.keys(row.saved)), sorted(CONTRACT.saved), at('saved'));
      assert.ok(['date', 'choice', 'confirm'].includes(row.control), at(row.control));
      for (const passage of row.passages) assert.deepEqual(sorted(Object.keys(passage)), sorted(CONTRACT.passage), at('passage'));
    }
    for (const item of doc.earlier_answers) assert.deepEqual(sorted(Object.keys(item)), sorted(CONTRACT.earlier), at('earlier'));
    assert.deepEqual(sorted(Object.keys(doc.readiness)), sorted(CONTRACT.readiness), at('readiness'));
    for (const report of doc.reports) assert.deepEqual(sorted(Object.keys(report)), sorted(CONTRACT.report), at('report'));
    for (const item of doc.activity) assert.deepEqual(sorted(Object.keys(item)), sorted(CONTRACT.activity), at('activity'));
    if (doc.update !== null) {
      assert.deepEqual(sorted(Object.keys(doc.update)), sorted(CONTRACT.update), at('update'));
      assert.deepEqual(sorted(Object.keys(doc.update.earlier)), sorted(CONTRACT.update_earlier), at('update.earlier'));
    }
    for (const code of doc.earlier_codes) assert.deepEqual(sorted(Object.keys(code)), sorted(CONTRACT.code), at(`earlier code ${code.code}`));
    if (doc.what_changed !== null) assert.deepEqual(sorted(Object.keys(doc.what_changed)), sorted(CONTRACT.what_changed), at('what_changed'));
    for (const item of doc.decision_history) assert.deepEqual(sorted(Object.keys(item)), sorted(CONTRACT.history), at('decision_history'));
    states.add(`${doc.state}/${doc.progress.phase}`);
  }
  // the states the design names, each drawn from a fixture
  for (const wanted of ['processing/processing', 'processing/queued', 'action_needed/action_needed', 'awaiting_detail/awaiting_detail', 'ready/completed',
    'reviewed/completed', 'ready/partial', 'failed/failed', 'stopped/stopped', 'being_confirmed/being_confirmed']) assert.ok(states.has(wanted), wanted);
  for (const name of ['session.json', 'session-agent.json']) assert.deepEqual(sorted(Object.keys(fixture(name))), sorted(CONTRACT.session), name);
  const rows = fixture('encounters.json').encounters;
  assert.deepEqual(sorted(rows.map(row => row.id)), sorted(ENCOUNTERS.map(name => fixture(name).id)));
  for (const row of rows) assert.deepEqual(sorted(Object.keys(row)), sorted(CONTRACT.row), row.id);
});

test('every quote in the customer fixtures is an exact code-point slice of its document, on its page', () => {
  let quotes = 0;
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const points = [...doc.document.text];
    const slice = span => points.slice(span.start, span.end).join('');
    for (const code of doc.codes) for (const quote of code.why.quotes) {
      assert.equal(slice(quote), quote.text, `${name} ${code.code}`);
      const page = doc.document.pages.find(item => quote.start >= item.start && quote.start < item.end);
      assert.equal(page?.page, quote.page, `${name} ${code.code} page`);
      quotes += 1;
    }
    if (doc.service_date.document_quote) assert.equal(slice(doc.service_date.document_quote), doc.service_date.document_quote.text, name);
    for (const row of doc.details_needed) if (row.quote) assert.equal(slice(row.quote), row.quote.text, name);
    for (const row of doc.details_needed) for (const passage of row.passages) assert.equal(slice(passage), passage.text, `${name} ${row.fact} passage`);
    assert.deepEqual(app.documentLayout(doc).unlocated, new Set(), name);
  }
  assert.ok(quotes >= 15, quotes);
});

// --- status ----------------------------------------------------------------------------------------------------------
// The fixtures are hand-made to the contract now and regenerated from the real serializer at integration, so what the
// server writes (summaries, prompts, reasons, messages) is read from the fixture; what the page writes is pinned here.

const esc = app.escapeHtml;
// One result row's markup: from its own tag to the next row or the end of the list (a row holds nested lists).
const rowOf = (html, id) => {
  const at = html.indexOf(`id="card-${id}"`);
  assert.ok(at >= 0, `no row for ${id}`);
  const ends = [html.indexOf('<li class="result-row"', at), html.indexOf('</ol>', at)].filter(index => index > at);
  return html.slice(at, Math.min(...ends));
};
const words = items => (items.length <= 2 ? items.join(' and ') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`);
const STEP_TEXT = { done: 'Done', active: 'In progress', waiting: 'Waiting to start', not_started: 'Not started', failed: 'Did not finish', stopped: 'Stopped', skipped: 'Not needed' };

test('status mapping: the four statuses keep their fixed labels and tones; anything else is never shown as reviewable', () => {
  assert.deepEqual(app.codeStatus({ status: 'ready' }), { key: 'ready', label: 'Ready for review', tone: 'green', icon: '' });
  assert.deepEqual(app.codeStatus({ status: 'needs_detail' }), { key: 'needs_detail', label: 'Needs a detail', tone: 'amber', icon: 'info' });
  assert.deepEqual(app.codeStatus({ status: 'approved' }), { key: 'approved', label: 'Approved', tone: 'green', icon: 'check' });
  assert.deepEqual(app.codeStatus({ status: 'excluded' }), { key: 'excluded', label: 'Excluded', tone: 'gray', icon: '' });
  // the label is the page's own, whatever label the server sends beside a known status
  assert.equal(app.codeStatus({ status: 'ready', status_label: 'Approved' }).label, 'Ready for review');
  assert.deepEqual(app.codeStatus({ status: 'weird', status_label: 'Something' }), { key: 'weird', label: 'Something', tone: 'gray', icon: '' });
  assert.deepEqual(app.codeStatus({}), { key: 'unknown', label: 'Not reviewable', tone: 'gray', icon: '' });
  assert.equal(app.codeStatus({ status: '__proto__' }).label, 'Not reviewable');
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const html = render(doc);
    for (const code of doc.codes) {
      const status = app.codeStatus(code);
      const svg = status.icon ? `<svg class="" aria-hidden="true"><use href="#i-${status.icon}"/></svg>` : '';
      assert.ok(rowOf(html, code.id).includes(`<span class="status ${status.tone}" data-status="${code.status}">${svg}${status.label}</span>`), `${name} ${code.code}`);
    }
  }
});

test('an agent approval labels the row and the approved download as agent-executed synthetic review', () => {
  const doc = fixture('encounter-reviewed.json');
  const html = render(doc);
  const approved = doc.codes.filter(code => code.status === 'approved' && code.decision?.by_kind === 'agent');
  assert.ok(approved.length >= 1 && doc.readiness.approved === true, 'the scenario: agent approvals, every decision made');
  for (const code of approved) {
    const row = rowOf(html, code.id);
    assert.ok(row.includes('<p class="result-sub">Agent-executed synthetic review — not clinical approval</p>'), code.code);
    assert.ok(row.includes(`<strong>Approved by ${esc(code.decision.by)}</strong>`), code.code);
    assert.equal(count(row, 'gent-executed synthetic review — not clinical approval'), 1, `${code.code}: said once per row`);
  }
  // the label holds even when the server's line under the code says something else, or nothing
  for (const sub of ['', 'Approved in review.']) {
    const bare = clone(doc);
    const first = bare.codes.find(code => code.id === approved[0].id);
    first.sub_label = sub;
    assert.equal(app.rowSubLabel(first), app.AGENT_REVIEW);
    assert.ok(rowOf(render(bare), first.id).includes('<p class="result-sub">Agent-executed synthetic review — not clinical approval</p>'), JSON.stringify(sub));
  }
  // an agent's other decisions say it on their decision line, the line under the code being the server's
  const confirmed = { ...clone(approved[0]), status: 'excluded', sub_label: 'Exclusion confirmed in review.' };
  confirmed.decision.action = 'confirm';
  assert.match(app.decisionLine(confirmed), /Exclusion confirmed by .* · agent-executed synthetic review — not clinical approval/);
  // the approved download's wording in the export dialog
  assert.match(app.exportStatusText(doc), /Includes agent-executed synthetic review — not clinical approval\.$/);
  const human = clone(doc);
  for (const code of human.codes) if (code.decision) code.decision = { ...code.decision, by: 'Synthetic Reviewer', by_kind: 'human' };
  assert.doesNotMatch(app.exportStatusText(human), /agent/);
  assert.equal(app.hasAgentDecision(human), false);
});

test('a rejection says it was rejected in review; a human approval carries no agent label', () => {
  const doc = fixture('encounter-ready.json');
  const rejected = { ...doc.codes[0], status: 'excluded', sub_label: '', decision: { action: 'reject', by: 'Synthetic Reviewer', by_kind: 'human', at: '2026-10-29T10:00:00Z', note: '', modifiers: [] } };
  assert.equal(app.rowSubLabel(rejected), 'Rejected in review');
  assert.equal(app.rowSubLabel({ ...rejected, sub_label: 'Rejected in review.' }), 'Rejected in review.');
  const approved = { ...doc.codes[0], status: 'approved', sub_label: '', decision: { action: 'approve', by: 'Synthetic Reviewer', by_kind: 'human', at: '2026-10-29T10:00:00Z', note: 'Read it.', modifiers: [] } };
  assert.equal(app.rowSubLabel(approved), '');
  const line = app.decisionLine(approved);
  assert.match(line, /<strong>Approved by Synthetic Reviewer<\/strong><p>29 Oct 2026, 10:00 UTC · synthetic review — not clinical approval<\/p><p>Note: Read it\.<\/p>/);
  assert.doesNotMatch(line, /agent/);
});

// --- the codes-first list ----------------------------------------------------------------------------------------------

test('the result list is numbered in the served order, one row per code, with the hooks the walk reads', () => {
  const doc = fixture('encounter-mara.json');
  assert.deepEqual(doc.codes.map(code => code.code), ['43239', '45380', '45385'], 'the Mara scenario');
  const html = render(doc);
  assert.equal(count(html, '<ol class="result-list" aria-label="Suggested CPT codes">'), 1);
  const rows = [...html.matchAll(/<li class="result-row" id="card-([^"]+)" tabindex="-1" data-proposal="([^"]+)" data-code="([^"]+)" data-status="([^"]+)" data-units="(\d*)" data-modifiers="([^"]*)">/g)];
  assert.deepEqual(rows.map(match => match.slice(1)), doc.codes.map(code => [code.id, code.id, code.code, code.status, String(code.units), code.modifiers.join(' ')]));
  assert.deepEqual([...html.matchAll(/<span class="result-number">(\d+)<\/span><span class="result-code">([^<]+)<\/span>/g)].map(match => [Number(match[1]), match[2]]),
    doc.codes.map(code => [code.number, code.code]));
  for (const code of doc.codes) assert.ok(rowOf(html, code.id).includes(`<p class="result-summary">${esc(code.summary)}</p>`), code.code);
  for (const hook of ['result-units', 'result-modifiers', 'result-sub', 'result-summary', 'result-foot']) assert.equal(count(html, `class="${hook}"`), doc.codes.length, hook);
  // the order is the server's, never sorted here
  const reversed = clone(doc);
  reversed.codes.reverse();
  assert.deepEqual([...render(reversed).matchAll(/data-code="([^"]+)"/g)].map(match => match[1]), reversed.codes.map(code => code.code));
  // a missing number falls back to the position
  const numberless = clone(doc);
  for (const code of numberless.codes) code.number = null;
  assert.deepEqual([...render(numberless).matchAll(/<span class="result-number">(\d+)<\/span>/g)].map(match => Number(match[1])), numberless.codes.map((_, index) => index + 1));
});

test('only the served allowed actions are drawn, each with its proposal id', () => {
  // in the page's own fixed order (approve, reject, reinstate, confirm, undo), whatever order the server lists them in
  const order = ['approve', 'reject', 'reinstate', 'confirm', 'revoke'];
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const html = render(doc);
    for (const code of doc.codes) {
      const drawn = [...html.matchAll(new RegExp(`data-decision="(\\w+)" data-proposal="${code.id}"`, 'g'))].map(match => match[1]);
      assert.deepEqual(drawn, order.filter(action => code.allowed_actions.includes(action)), `${name} ${code.code}`);
    }
  }
  const doc = fixture('encounter-ready.json');
  const none = clone(doc);
  for (const code of none.codes) code.allowed_actions = [];
  assert.equal(count(render(none), 'data-decision='), 0);
  const odd = clone(doc);
  odd.codes[0].allowed_actions = ['approve', 'delete', '__proto__'];
  assert.deepEqual([...rowOf(render(odd), odd.codes[0].id).matchAll(/data-decision="(\w+)"/g)].map(match => match[1]), ['approve']);
});

test('units and modifiers: units always stated, a chosen modifier named, a modifier review said as such', () => {
  assert.equal(app.unitsLabel(1), '1 unit');
  assert.equal(app.unitsLabel(3), '3 units');
  for (const bad of [0, -1, 1.5, '2', null]) assert.equal(app.unitsLabel(bad), '', String(bad));
  const review = { options: ['59', 'XS'], text: 'Separate lesions.', sources: ['CMS claims manual Pub. 100-04 ch. 12'] };
  assert.equal(app.modifierLabel({ status: 'ready', modifiers: [], modifier_review: review }), 'Modifier review');
  assert.equal(app.modifierLabel({ status: 'approved', modifiers: [], modifier_review: review }), 'No modifier');
  assert.equal(app.modifierLabel({ status: 'approved', modifiers: ['XS'], modifier_review: review }), 'Modifier XS');
  assert.equal(app.modifierLabel({ status: 'ready', modifiers: [], modifier_review: null }), '');
  const doc = fixture('encounter-reviewed.json');
  const chosen = doc.codes.find(code => code.modifiers.length);
  assert.ok(chosen, 'the scenario: an approval with a modifier');
  const row = rowOf(render(doc), chosen.id);
  assert.ok(row.includes(`data-modifiers="${esc(chosen.modifiers.join(' '))}">`), 'the row carries the modifier');
  assert.ok(row.includes(`<span class="result-code">${esc(chosen.code)}</span><span class="result-units">${app.unitsLabel(chosen.units)}</span><span class="result-modifiers">Modifier ${esc(chosen.modifiers.join(', '))}</span>`));
  const units = clone(doc);
  units.codes[0].units = 2;
  assert.ok(rowOf(render(units), units.codes[0].id).includes('<span class="result-units">2 units</span>'));
});

test('other codes sit behind a closed disclosure; "Not separately coded" and the limitations are listed', () => {
  const doc = fixture('encounter-mara.json');
  assert.ok(doc.other_codes.length && doc.not_separately_coded.length && doc.limitations.length, 'the scenario');
  const html = render(doc);
  assert.match(html, /<details class="other-codes" data-key="other-codes"><summary>Other codes considered \(not suggested\)<\/summary>/);
  for (const item of doc.other_codes) {
    assert.ok(html.includes(`<span class="other-code">${esc(item.code)}</span><span>${esc(item.reason)}</span>`), item.code);
    assert.equal(count(html, `data-code="${esc(item.code)}"`), 0, `${item.code}: an alternative is never a result row`);
  }
  assert.match(render(doc, { open: new Set(['other-codes']) }), /<details class="other-codes" data-key="other-codes" open>/);
  assert.ok(html.includes(`<h3>Not separately coded</h3><ul>${doc.not_separately_coded.map(item => `<li><strong>${esc(item.label)}</strong><span>${esc(item.reason)}</span></li>`).join('')}</ul>`));
  assert.ok(html.includes(`<h3>Limitations</h3><ul class="limitation-list">${doc.limitations.map(item => `<li>${esc(item)}</li>`).join('')}</ul>`));
  const bare = clone(doc);
  bare.other_codes = [];
  bare.not_separately_coded = [];
  bare.limitations = [];
  bare.unresolved = ['One documented service could not be matched to a code.'];
  const plain = render(bare);
  assert.doesNotMatch(plain, /other-codes|Not separately coded|<h3>Limitations/);
  assert.match(plain, /<h3>Still open<\/h3><ul class="unresolved-list"><li>One documented service could not be matched to a code\.<\/li>/);
});

// --- "Why this code?" --------------------------------------------------------------------------------------------------

test('"Why this code?" is a closed disclosure holding the exact quotes with their offsets and pages, and the qualifications', () => {
  // the first fixture holding a code with several quotes and a qualification (the serializer's Mara holds none: each of
  // its codes has several quotes or a qualification, not both)
  const rich = item => item.why.quotes.length >= 2 && item.why.qualifications.length;
  const doc = ['encounter-mara.json', ...ENCOUNTERS].map(fixture).find(item => item.codes.some(rich));
  assert.ok(doc, 'the scenario: a code with quotes and a qualification');
  const layout = app.documentLayout(doc);
  const code = doc.codes.find(rich);
  const why = app.whyThisCode(code, layout, ui(doc));
  assert.ok(why.startsWith(`<details class="why-code" data-key="why:${code.id}"><summary>Why this code?</summary>`));
  const quotes = [...why.matchAll(/<button type="button" class="why-quote" data-evidence="([^"]+)" data-start="(\d+)" data-end="(\d+)" data-page="(\d+)" title="Show this passage in the document">([^<]*)<\/button>/g)];
  assert.equal(quotes.length, code.why.quotes.length);
  const points = [...doc.document.text];
  quotes.forEach((match, index) => {
    assert.equal(match[1], `${code.id}:q${index}`);
    const [start, end, page] = [Number(match[2]), Number(match[3]), Number(match[4])];
    assert.equal(esc(points.slice(start, end).join('')), match[5], 'the button text is the exact slice');
    assert.equal(page, code.why.quotes[index].page);
  });
  for (const item of code.why.qualifications) assert.ok(why.includes(`<li class="why-qualification">${esc(item)}</li>`), item);
  assert.match(app.whyThisCode(code, layout, ui(doc, { open: new Set([`why:${code.id}`]) })), /^<details class="why-code" data-key="why:[^"]+" open>/);
  // every row has one, and none is open unless the member opened it
  const page = render(doc);
  assert.equal(count(page, '<details class="why-code"'), doc.codes.length);
  assert.equal(count(page, '" open><summary>Why this code?'), 0);
  const quiet = clone(code);
  quiet.why = { quotes: [], qualifications: [] };
  assert.match(app.whyThisCode(quiet, layout, ui(doc)), /No passage of the document is quoted for this code\./);
});

test('a quote that is not at its offsets is shown as not found and never highlighted', () => {
  const doc = clone(fixture('encounter-ready.json'));
  const code = doc.codes.find(item => item.why.quotes.length >= 2);
  code.why.quotes[0].start += 1;
  code.why.quotes[1].exact = false;
  const layout = app.documentLayout(doc);
  assert.deepEqual([...layout.unlocated], [`${code.id}:q0`, `${code.id}:q1`]);
  const why = app.whyThisCode(code, layout, ui(doc));
  assert.equal(count(why, '<span class="why-quote unlocated"'), 2);
  assert.equal(count(why, 'Not found at this place in the document.'), 2);
  assert.equal(count(why, `data-evidence="${code.id}:q`), 0);
  assert.equal(count(app.sourcePanel(doc, layout), `${code.id}:q`), 0);
});

test('the modifier review states its dated source and that nothing is added automatically', () => {
  const doc = fixture('encounter-mara.json');
  const layout = app.documentLayout(doc);
  const reviewed = doc.codes.filter(code => code.modifier_review);
  assert.ok(reviewed.length >= 2, 'the Mara scenario: two lesions treated separately');
  for (const code of reviewed) {
    const why = app.whyThisCode(code, layout, ui(doc));
    assert.ok(why.includes(`<div class="why-modifier"><strong>Modifier review</strong><p>${esc(code.modifier_review.text)}</p><p class="why-sources">${esc(`Source: ${code.modifier_review.sources.join('; ')}`)}</p>`), code.code);
    assert.ok(why.includes('No modifier is added automatically; the reviewer may choose one when approving.'), code.code);
    assert.match(code.modifier_review.sources.join(' '), /\d{4}-\d{2}-\d{2}/, `${code.code}: the source is dated`);
  }
  for (const code of doc.codes.filter(item => !item.modifier_review)) assert.doesNotMatch(app.whyThisCode(code, layout, ui(doc)), /why-modifier/);
});

test('source marks title the codes they are cited for and the document date', () => {
  const doc = fixture('encounter-mara.json');
  const html = app.sourcePanel(doc, app.documentLayout(doc));
  const date = doc.service_date.document_quote;
  assert.ok(html.includes(`<button type="button" class="evidence-mark" data-evidence="date:document" data-keys="date:document" title="Date of service in the document">${esc(date.text)}</button>`));
  for (const code of doc.codes) assert.ok(html.includes(`title="Cited for ${esc(code.code)}">`), code.code);
  assert.ok(html.includes(`<a href="${esc(doc.document.original_url)}" download>`));
  const pasted = fixture('encounter-stopped.json');
  assert.equal(pasted.document.original_url, null);
  assert.doesNotMatch(app.sourcePanel(pasted, app.documentLayout(pasted)), /Download original/);
});

// --- "A few details needed" -------------------------------------------------------------------------------------------

test('the details panel: one row per detail with its family, prompt and the codes it affects; one save for all rows', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  assert.match(html, /^<section class="details-panel" aria-labelledby="detailsTitle">.*<h2 id="detailsTitle">A few details needed<\/h2>/);
  assert.deepEqual([...html.matchAll(/class="detail-row[^"]*" data-detail="([^"]+)" data-fact="([^"]+)"/g)].map(match => [match[1], match[2]]), doc.details_needed.map(row => [row.id, row.fact]));
  for (const row of doc.details_needed) {
    assert.ok(html.includes(`<span class="detail-family">${esc(row.family_label)}</span><span class="detail-prompt">${esc(row.prompt)}</span>`), row.fact);
    if (row.affects.length) assert.ok(html.includes(`<p class="detail-affects">Affects ${esc(words(row.affects))}</p>`), row.fact);
  }
  assert.equal(count(html, 'data-action="save-details"'), 1);
  const open = doc.details_needed.filter(row => !row.saved).length;
  assert.ok(html.includes(`${open === 1 ? '1 detail is' : `${open} details are`} needed. Answer what you can; codes that do not depend on them stay reviewable.`));
  assert.equal(app.detailsPanel({ ...doc, details_needed: [] }, ui(doc)), '');
  // a supported, independent code stays reviewable while others wait
  const page = render(doc);
  const ready = doc.codes.find(code => code.status === 'ready');
  const waiting = doc.codes.filter(code => code.status === 'needs_detail');
  assert.ok(ready && waiting.length, 'the scenario: one code reviewable while others wait');
  assert.ok(page.includes(`data-decision="approve" data-proposal="${ready.id}"`));
  for (const code of waiting) assert.ok(!page.includes(`data-decision="approve" data-proposal="${code.id}"`), code.code);
});

test('a date conflict shows the document date and the entered date side by side, with "Use document date"; the input is never prefilled', () => {
  const doc = fixture('encounter-action-needed.json');
  const row = doc.details_needed.find(item => item.control === 'date');
  assert.ok(row && row.document_value && row.entered_value && row.document_value !== row.entered_value, 'the scenario: two different dates');
  const html = app.detailsPanel(doc, ui(doc));
  assert.ok(html.includes(`<div class="detail-document-date"><span class="detail-date-label">Document</span><strong>${app.formatDate(row.document_value, true)}</strong><q class="detail-quote">${esc(row.quote.text)}</q></div>`));
  assert.ok(html.includes(`<div class="detail-entered-date"><span class="detail-date-label">You entered</span><strong>${app.formatDate(row.entered_value, true)}</strong></div>`));
  assert.ok(html.includes(`<button type="button" class="button secondary detail-choice" id="detail-${row.id}-use_document" data-action="use-document-date" data-detail="${row.id}" aria-pressed="false">Use document date</button>`));
  assert.ok(html.includes(`<input type="date" id="detail-${row.id}-date" data-detail-input data-detail="${row.id}">`), 'no value attribute');
  assert.match(html, /Choose the date of service\. Nothing is checked until you do\./);
  // the member's own pending entry is kept across a refresh, never a date from the server
  const typed = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: '2026-10-27' }]]) }));
  assert.ok(typed.includes(`data-detail-input data-detail="${row.id}" value="2026-10-27">`));
  const chosen = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: 'use_document' }]]) }));
  assert.ok(chosen.includes(`data-action="use-document-date" data-detail="${row.id}" aria-pressed="true">`));
  assert.ok(!chosen.includes(`value="${row.document_value}"`) && !chosen.includes(`value="${row.entered_value}"`));
  // the page says Action needed at once, and nothing is checked
  const page = render(doc);
  assert.match(page, /<section class="progress-panel" data-phase="action_needed"/);
  assert.match(page, /<h2 id="progressTitle">Action needed<\/h2>/);
  assert.doesNotMatch(page, /progress-card|is-animated|data-state="active"/);
  assert.match(page, /Nothing has been checked yet\. Choose the date of service to continue\./);
});

test('"Use document date" is offered only when the document states a date', () => {
  const doc = clone(fixture('encounter-action-needed.json'));
  const row = doc.details_needed.find(item => item.control === 'date');
  row.document_value = null;
  row.quote = null;
  const html = app.detailsPanel(doc, ui(doc));
  assert.doesNotMatch(html, /use-document-date/);
  assert.match(html, /<strong>Not stated<\/strong>/);
  assert.match(html, /data-detail-input/);
});

test('choices are radios named per detail; "Not documented" and "Cannot confirm" only where allowed; a confirm row asks for no clinical fact', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  const choice = doc.details_needed.find(row => row.control === 'choice' && !row.saved);
  const confirm = doc.details_needed.find(row => row.control === 'confirm' && !row.saved);
  assert.ok(choice && confirm, 'the scenario: a choice and a confirmation');
  assert.equal(count(html, `<input type="radio" name="detail-${choice.id}"`), choice.choices.length);
  for (const option of choice.choices) assert.ok(html.includes(`value="${esc(option.value)}" data-detail="${choice.id}"><span>${esc(option.label)}</span>`), option.value);
  // a radio group is named by its legend, which comes first and holds the family and the prompt
  assert.ok(html.includes(`<fieldset class="detail-row" data-detail="${choice.id}" data-fact="${choice.fact}"><legend class="detail-lead"><span class="detail-family">${esc(choice.family_label)}</span><span class="detail-prompt">${esc(choice.prompt)}</span></legend>`));
  assert.ok(html.includes(`<div class="detail-row" data-detail="${confirm.id}" data-fact="${confirm.fact}"><div class="detail-lead"><span class="detail-family">`));
  for (const row of [choice, confirm]) {
    for (const value of ['not_documented', 'cannot_confirm']) {
      assert.equal(html.includes(`id="detail-${row.id}-${value}" data-detail-choice="${value}" data-detail="${row.id}" aria-pressed="false">`), row.allow.includes(value), `${row.fact} ${value}`);
    }
  }
  const confirmRow = html.slice(html.indexOf(`data-detail="${confirm.id}" data-fact="${confirm.fact}"`), html.indexOf('</div>', html.indexOf(`data-detail="${confirm.id}" data-fact="${confirm.fact}"`) + 400));
  assert.doesNotMatch(confirmRow, /type="radio"|type="date"|<textarea|type="text"/);
  assert.equal(count(html, 'data-action="addendum"'), doc.details_needed.filter(row => row.addendum_allowed && !row.saved).length, 'only where the server allows the physician path');
  if (confirm.addendum_allowed) assert.ok(html.includes(`<button type="button" class="button subtle detail-addendum" data-action="addendum" data-detail="${confirm.id}">Add to the documentation (physician)</button>`));
  const pending = app.detailsPanel(doc, ui(doc, { answers: new Map([[choice.id, { fact: choice.fact, value: choice.choices[1].value }], [confirm.id, { fact: confirm.fact, value: confirm.allow[confirm.allow.length - 1] }]]) }));
  assert.ok(pending.includes(`value="${esc(choice.choices[1].value)}" data-detail="${choice.id}" checked>`));
  assert.ok(pending.includes(`data-detail-choice="${confirm.allow[confirm.allow.length - 1]}" data-detail="${confirm.id}" aria-pressed="true">`));
});

// completion repair (2026-11-06, U10): a clinical question says what CPT Studio could not confirm and shows the passages it
// concerns, as exact slices of the document with their page, beside the concise control; nothing else is asked for
test('a clinical question shows what CPT Studio could not confirm and the passages it concerns, beside the concise control', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  const rows = doc.details_needed.filter(row => row.control === 'confirm' && row.statement);
  assert.ok(rows.length && rows.some(row => row.passages.length), 'the scenario: a question with its passages');
  for (const row of rows) {
    const part = app.questionPassages(row);
    assert.ok(html.includes(part), row.fact);
    assert.ok(part.includes(`<p class="detail-statement">${esc(row.statement)}</p>`), row.fact);
    for (const passage of row.passages) {
      assert.ok(part.includes(`<q class="detail-quote">${esc(passage.text)}</q>`), passage.text);
      if (passage.page) assert.ok(part.includes(`<span class="detail-page">Page ${passage.page}</span>`));
    }
    assert.doesNotMatch(row.statement, /is not documented/);
  }
  assert.equal(app.questionPassages({ statement: '', passages: [] }), '');
  const one = app.questionPassages({ statement: 'From the document, CPT Studio could not confirm how far the instrument was advanced.',
    passages: [{ text: 'The colonoscope was advanced.', start: 0, end: 29, page: 1 }] });
  assert.match(one, /The passage this question concerns/);
  assert.doesNotMatch(one, /<textarea|type="text"/);
});

// completion repair (2026-11-06, U11): an answer saved for a question no longer asked, or now asked differently, is listed as an
// earlier answer - kept, never applied - with the server's own sentence for why, and can be withdrawn
test('earlier answers are listed as such, with why, and can be withdrawn by a reviewer', () => {
  const doc = clone(fixture('encounter-awaiting-detail.json'));
  doc.earlier_answers = [{ answer_id: '11111111-1111-4111-8111-111111111111', fact: 'extent', family_label: 'Colonoscopy',
    prompt: 'How far was the instrument advanced?', affects: ['45385'], value: 'not_documented', label: 'Not documented',
    by: 'Synthetic Reviewer', at: '2026-11-05T20:12:09Z', why: 'earlier_form',
    why_text: 'This answer was saved before each question showed the passages it concerns, and the question is now asked in other words, so it is not applied; answer the question as it is asked now.' }];
  const html = app.detailsPanel(doc, ui(doc));
  assert.match(html, /<h3>Earlier answers, not applied<\/h3>/);
  const listed = doc.earlier_answers[0];
  assert.ok(html.includes(`<span class="earlier-why">${esc(listed.why_text)}</span>`));
  assert.ok(html.includes(`Saved: <strong>Not documented</strong> for 45385 — Synthetic Reviewer, ${app.formatTimestamp(listed.at)}`));
  assert.ok(html.includes(`data-action="revoke-detail" data-answer="${listed.answer_id}"`));
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.earlierAnswers(viewer), /revoke-detail/);
  // a document with nothing left to ask still lists its earlier answers
  const none = { ...doc, details_needed: [] };
  assert.match(app.detailsPanel(none, ui(none)), /No detail is needed now\..*Earlier answers, not applied/s);
  // refutation cycle 1 (answers F7): headed for what it lists, never "A few details needed" above "No detail is needed now."
  assert.match(app.detailsPanel(none, ui(none)), /<h2 id="detailsTitle">Earlier answers<\/h2>/);
  assert.doesNotMatch(app.detailsPanel(none, ui(none)), /A few details needed/);
  assert.match(app.detailsPanel(doc, ui(doc)), /<h2 id="detailsTitle">A few details needed<\/h2>/);
  assert.equal(app.earlierAnswers({ ...doc, earlier_answers: [] }), '');
});

test('a saved answer is shown with who and when, and can be changed; only open rows count', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  const saved = doc.details_needed.find(row => row.saved);
  assert.ok(saved, 'the scenario: an answer already saved');
  assert.ok(html.includes(`<span>Saved: <strong>${esc(saved.saved.label)}</strong> — ${esc(saved.saved.by)}, ${app.formatTimestamp(saved.saved.at)}</span>`));
  assert.ok(html.includes(`data-action="revoke-detail" data-answer="${saved.saved.answer_id}"`));
  assert.ok(!html.includes(`name="detail-${saved.id}"`), 'a saved row is not asked again');
  const all = clone(doc);
  for (const row of all.details_needed) row.saved = { value: 'not_documented', label: '', by: 'Synthetic Reviewer', at: '2026-10-30T15:20:00Z', answer_id: saved.saved.answer_id };
  const done = app.detailsPanel(all, ui(all));
  assert.match(done, /Every detail has an answer\. You can change an answer below\./);
  assert.equal(count(done, 'save-details'), 0);
  assert.equal(count(done, 'Saved: <strong>Not documented</strong>'), all.details_needed.length);
});

test('pending answers survive a refresh; a viewer gets no controls; a busy document keeps its context rows only', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const choice = doc.details_needed.find(row => row.control === 'choice' && !row.saved);
  const answers = new Map([[choice.id, { fact: choice.fact, value: choice.choices[0].value }]]);
  assert.ok(render(doc, { answers }).includes(`value="${esc(choice.choices[0].value)}" data-detail="${choice.id}" checked>`));
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  const seen = app.detailsPanel(viewer, ui(viewer));
  assert.doesNotMatch(seen, /type="radio"|data-detail-choice|save-details|revoke-detail|data-action="addendum"/);
  assert.match(seen, /Answers can be saved once processing has finished\./);
  // FINAL-V2 amendment 1 (A1, 1.4, 5.1): a context save is accepted while processing runs, so the choice rows keep their
  // radios and the one save; a row that takes "Not documented" or "Cannot confirm" offers no answer while it runs
  const busy = clone(doc);
  busy.progress.busy = true;
  const running = app.detailsPanel(busy, ui(busy));
  assert.match(running, /type="radio"/);
  assert.equal(count(running, 'data-action="save-details"'), 1);
  assert.doesNotMatch(running, /data-detail-choice|revoke-detail/);
  assert.match(running, /Answers can be saved once processing has finished\./);
});

// --- the date row after refutation r2 (L7-02, L7-03, L7-05, L7-07) -------------------------------------------------------

// The action-needed fixture's date row, varied as the server serves its other states (studio/answers.py _date_row).
function dateDoc(overrides, docOverrides = {}) {
  const doc = clone(fixture('encounter-action-needed.json'));
  const row = doc.details_needed.find(item => item.control === 'date');
  Object.assign(row, overrides);
  Object.assign(doc, docOverrides);
  return { doc, row };
}
const STATED = [{ value: '2026-10-20', label: '20 October 2026 (stated in the document)' }, { value: '2026-10-21', label: '21 October 2026 (stated in the document)' }];
const CLEAR = [{ value: 'clear', label: 'Remove the entered date' }];

test('the document\'s own dates are drawn as choices beside the date entered, never "Not stated" (L7-07)', () => {
  const { doc, row } = dateDoc({ document_value: null, quote: null, choices: STATED, entered_value: '1998-01-01' });
  const html = app.detailsPanel(doc, ui(doc));
  assert.ok(html.includes('<div class="detail-document-date"><span class="detail-date-label">Document</span><strong>20 October 2026 and 21 October 2026</strong></div>'));
  assert.ok(html.includes('<div class="detail-entered-date"><span class="detail-date-label">You entered</span><strong>1 January 1998</strong></div>'));
  assert.doesNotMatch(html, /Not stated|use-document-date|clear-date|data-action="addendum"/);
  for (const choice of STATED) {
    assert.ok(html.includes(`<input type="radio" name="detail-${row.id}" id="detail-${row.id}-${choice.value}" value="${choice.value}" data-detail="${row.id}"><span>${esc(choice.label)}</span>`), choice.value);
  }
  assert.ok(html.includes(`Or enter another date<input type="date" id="detail-${row.id}-date" data-detail-input data-detail="${row.id}">`), 'never prefilled');
  assert.ok(html.includes(`<fieldset class="detail-row" data-detail="${row.id}" data-fact="service_date"><legend class="detail-lead">`), 'a radio group named by its legend');
  // the member's pick survives a refresh; the date field stays empty
  const picked = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: '2026-10-21' }]]) }));
  assert.ok(picked.includes(`value="2026-10-21" data-detail="${row.id}" checked>`));
  assert.ok(picked.includes(`data-detail-input data-detail="${row.id}">`));
  // the document's own conflict with nothing entered, and an entered date to confirm against both (L7-02)
  for (const entered of [null, '2026-10-21']) {
    const asked = dateDoc({ document_value: null, quote: null, choices: STATED, entered_value: entered });
    const askedHtml = app.detailsPanel(asked.doc, ui(asked.doc));
    assert.ok(askedHtml.includes('<strong>20 October 2026 and 21 October 2026</strong>'), String(entered));
    assert.ok(askedHtml.includes(`<strong>${entered ? '21 October 2026' : 'Nothing entered'}</strong>`), String(entered));
    assert.equal(count(askedHtml, `name="detail-${asked.row.id}"`), 2);
  }
});

test('where the document gives no date the page may show, its own wording is quoted; a held date can be removed, or settled by the physician (L7-03, L7-07)', () => {
  const quote = { text: 'Next procedure date: 11/04/2026', start: 10, end: 41 };
  const { doc, row } = dateDoc({ document_value: null, quote, choices: CLEAR, entered_value: '2026-10-20', addendum_allowed: true });
  const html = app.detailsPanel(doc, ui(doc));
  assert.ok(html.includes('<span class="detail-date-label">Document</span><strong><q>Next procedure date: 11/04/2026</q></strong></div>'));
  assert.doesNotMatch(html, /Not stated|use-document-date|type="radio"/);
  assert.ok(html.includes(`<button type="button" class="button secondary detail-choice" id="detail-${row.id}-clear" data-action="clear-date" data-detail="${row.id}" aria-pressed="false">Remove the entered date</button>`));
  assert.ok(html.includes(`<button type="button" class="button subtle detail-addendum" data-action="addendum" data-detail="${row.id}">Add to the documentation (physician)</button>`));
  assert.ok(html.includes(`<input type="date" id="detail-${row.id}-date" data-detail-input data-detail="${row.id}">`));
  // the walk reads data-detail-choice as an answer the server allows (row.allow): none is drawn for a date
  assert.doesNotMatch(html, /data-detail-choice=/);
  const chosen = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: 'clear' }]]) }));
  assert.ok(chosen.includes(`data-action="clear-date" data-detail="${row.id}" aria-pressed="true">`));
  // without the server's offer neither is drawn; a viewer gets no control at all
  const plain = dateDoc({ document_value: null, quote, choices: [], entered_value: null, addendum_allowed: false });
  assert.doesNotMatch(app.detailsPanel(plain.doc, ui(plain.doc)), /clear-date|data-action="addendum"/);
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.detailsPanel(viewer, ui(viewer)), /clear-date|data-action="addendum"|data-detail-input/);
});

test('a saved date the member entered shows who and when, and the same row corrects or removes it in the one save (L7-05)', () => {
  const saved = { value: '2026-10-02', label: '2 October 2026', by: 'Synthetic Reviewer', at: '2026-11-04T10:01:00Z', answer_id: '' };
  const ready = fixture('encounter-ready.json');
  const { doc, row } = dateDoc({ document_value: null, quote: null, choices: CLEAR, entered_value: '2026-10-02', saved }, { state: 'ready', progress: clone(ready.progress) });
  const html = app.detailsPanel(doc, ui(doc));
  assert.ok(html.includes(`<span>Saved: <strong>2 October 2026</strong> — Synthetic Reviewer, ${app.formatTimestamp(saved.at)}</span></p>`));
  assert.doesNotMatch(html, /revoke-detail/, 'no answer to withdraw: the row itself changes it');
  assert.ok(html.includes(`<input type="date" id="detail-${row.id}-date" data-detail-input data-detail="${row.id}">`));
  assert.ok(html.includes(`data-action="clear-date" data-detail="${row.id}"`));
  assert.match(html, /Every detail has an answer\. You can change an answer below\./);
  assert.equal(count(html, 'data-action="save-details"'), 1);
  assert.equal(app.answerable(row), true);
  assert.equal(app.answerable({ ...row, control: 'confirm', saved: { ...saved, answer_id: UUID } }), false);
  assert.equal(app.answerable({ ...row, saved: { ...saved, answer_id: UUID } }), false);
  // the one save sends the correction made in that row, as for an open row
  const kept = app.state.answers;
  app.state.answers = new Map([[row.id, { fact: 'service_date', value: '2026-10-20' }]]);
  try {
    assert.deepEqual(app.detailAnswers(doc), [{ id: row.id, fact: 'service_date', value: '2026-10-20' }]);
  } finally {
    app.state.answers = kept;
  }
  // a viewer reads the saved date only; a busy document keeps the date's own controls - a context save is accepted
  // while processing runs (FINAL-V2 amendment 1, A1)
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  const seen = app.detailsPanel(viewer, ui(viewer));
  assert.match(seen, /Saved: <strong>2 October 2026<\/strong>/);
  assert.doesNotMatch(seen, /data-detail-input|clear-date|save-details/);
  const busy = clone(doc);
  busy.progress.busy = true;
  const running = app.detailsPanel(busy, ui(busy));
  assert.match(running, /data-detail-input/);
  assert.equal(count(running, 'data-action="save-details"'), 1);
  assert.doesNotMatch(running, /revoke-detail/);
});

test('"Nothing is checked until you do" only while the member\'s date holds the document', () => {
  const { doc } = dateDoc({});
  assert.match(app.detailsPanel(doc, ui(doc)), /Choose the date of service\. Nothing is checked until you do\./);
  const asked = clone(doc);
  asked.state = 'awaiting_detail';
  asked.progress.phase = 'awaiting_detail';
  const html = app.detailsPanel(asked, ui(asked));
  assert.doesNotMatch(html, /Nothing is checked/);
  assert.match(html, /1 detail is needed\. Answer what you can; codes that do not depend on them stay reviewable\./);
});

// --- progress ----------------------------------------------------------------------------------------------------------

test('the progress panel folds to four plain stages with their states, the active check named under the active stage', () => {
  const doc = fixture('encounter-processing.json');
  const html = app.progressPanel(doc, ui(doc));
  assert.match(html, /^<section class="progress-panel progress-card" data-phase="processing" aria-labelledby="progressTitle">/);
  const steps = [...html.matchAll(/<li class="progress-step( is-animated)?" data-step="(\w+)" data-state="(\w+)">.*?<strong>([^<]+)<\/strong><small>([^<]+)<\/small>/g)];
  const labels = { reading: 'Reading your document', identifying: 'Identifying procedures', checking: 'Checking suggested codes', preparing: 'Preparing your results' };
  assert.ok(doc.progress.steps.some(step => step.state === 'active') && doc.progress.active_detail, 'the scenario: a check running');
  assert.deepEqual(steps.map(match => [match[2], match[3], match[4], match[5], Boolean(match[1])]), doc.progress.steps.map(step => [
    step.key, step.state, labels[step.key], `${STEP_TEXT[step.state]}${step.state === 'active' ? ` · ${doc.progress.active_detail}` : ''}`, step.state === 'active']));
  assert.match(html, /<p class="leave-note">You can leave this page — processing continues, and the document stays in Documents\.<\/p>/);
  assert.match(html, /<button type="button" class="button secondary" data-action="stop">/);
  assert.doesNotMatch(html, /data-action="resume"/);
  // a step the server leaves out, or with a state it does not know, is drawn as not started; the labels are the page's
  const odd = clone(doc);
  odd.progress.steps = [{ key: 'checking', label: 'Astra', state: 'whatever' }];
  const oddHtml = app.progressPanel(odd, ui(odd));
  assert.equal(count(oddHtml, 'data-state="not_started"'), 4);
  assert.doesNotMatch(oddHtml, /Astra/);
  // the checks: three functional labels with their states
  const checkText = { done: 'Done', running: 'In progress', waiting: 'Waiting', unavailable: 'Unavailable', not_run: 'Not run' };
  const checkLabels = { document_review: 'Document review', independent_checks: 'Independent checks', coding_validation: 'Coding validation' };
  assert.deepEqual([...app.checksPanel(doc).matchAll(/<li class="check-step" data-check="(\w+)" data-state="(\w+)">.*?<strong>([^<]+)<\/strong><small>([^<]+)<\/small>/g)].map(match => match.slice(1)),
    doc.checks.map(check => [check.key, check.state, checkLabels[check.key], checkText[check.state]]));
});

test('while busy the panel shows elapsed time that ticks; a finished one states the total; never a percentage or a forecast', () => {
  const doc = fixture('encounter-processing.json');
  const now = Date.parse(doc.progress.server_time);
  const elapsed = app.durationText(now - Date.parse(doc.progress.started_at));
  assert.ok(app.progressPanel(doc, ui(doc, { nowMs: now })).includes(`<p class="progress-time">Elapsed <span data-elapsed data-since="${doc.progress.started_at}">${elapsed}</span></p>`));
  // the server's clock, not the browser's: a browser five minutes behind says the same
  assert.ok(app.progressPanel(doc, ui(doc, { nowMs: now - 300000, clock: 300000 })).includes(`>${elapsed}<`));
  const finished = fixture('encounter-ready.json');
  const took = app.durationText(Date.parse(finished.progress.finished_at) - Date.parse(finished.progress.started_at));
  const done = app.progressPanel(finished, ui(finished));
  assert.match(done, /^<section class="progress-panel progress-done" data-phase="completed"/);
  assert.ok(done.includes(`<strong>Results ready</strong> · finished in <span data-elapsed data-since="${finished.progress.started_at}" data-until="${finished.progress.finished_at}">${took}</span>`));
  const failed = fixture('encounter-failed.json');
  assert.ok(app.progressPanel(failed, ui(failed)).includes(`Ran for <span data-elapsed data-since="${failed.progress.started_at}" data-until="${failed.progress.finished_at}">${app.durationText(Date.parse(failed.progress.finished_at) - Date.parse(failed.progress.started_at))}</span>`));
  for (const name of ENCOUNTERS) {
    const page = everything(fixture(name));
    assert.doesNotMatch(page, /\d\s?%|percent|\bETA\b|estimated time|minutes? (?:left|remaining)|about \d+ min/i, name);
  }
});

test('no step or icon is animated when processing failed, stopped or waits on the member, even if the server says busy', () => {
  for (const name of ['encounter-failed.json', 'encounter-stopped.json', 'encounter-action-needed.json', 'encounter-being-confirmed.json']) {
    const doc = fixture(name);
    for (const busy of [false, true]) {
      const forced = clone(doc);
      forced.progress.busy = busy;
      forced.progress.steps[2].state = 'active';
      const html = app.progressPanel(forced, ui(forced));
      assert.doesNotMatch(html, /is-animated/, `${name} busy=${busy}`);
      assert.doesNotMatch(html, /data-elapsed data-since="[^"]+">/, `${name}: no ticking time`);
    }
  }
  const processing = fixture('encounter-processing.json');
  assert.equal(count(app.progressPanel(processing, ui(processing)), 'is-animated'), 2, 'the active step and the panel icon');
  const idle = clone(processing);
  idle.progress.busy = false;
  assert.doesNotMatch(app.progressPanel(idle, ui(idle)), /is-animated|progress-card/);
});

test('every full progress panel says whether the member can leave the page, a stopped and a failed one included', () => {
  // the 2026-11-05 acceptance walk on cpt.quillmd.com: the stopped panel told nobody they could leave (directive 5:
  // "Make it clear when the user can leave the page and return"); a failed one did not either
  const notes = {
    // never "nothing runs until it is resumed": a detail saved on a stopped document restarts it (jobs.change_context)
    'encounter-stopped.json': 'You can leave this page — the document stays in Documents.',
    'encounter-failed.json': 'You can leave this page — the document stays in Documents.',
  };
  const drawn = [];
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    const html = app.progressPanel(doc, ui(doc));
    if (html.includes('progress-done')) continue;  // results are ready: one compact line, nothing left to wait for
    drawn.push(doc.progress.phase);
    assert.equal(doc.progress.can_leave, true, `${name}: the scenario`);
    assert.equal(count(html, '<p class="leave-note">'), 1, `${name}: one leave note`);
    if (notes[name]) assert.ok(html.includes(`<p class="leave-note">${notes[name]}</p>`), name);
    const kept = clone(doc);
    kept.progress.can_leave = false;
    assert.doesNotMatch(app.progressPanel(kept, ui(kept)), /leave-note/, `${name}: no note where the server says the member cannot leave`);
  }
  for (const phase of ['processing', 'queued', 'action_needed', 'being_confirmed', 'failed', 'stopped']) assert.ok(drawn.includes(phase), phase);
});

test('failed: the plain error and its action; stopped: Resume; being confirmed: no Stop and the settling message', () => {
  const failedDoc = fixture('encounter-failed.json');
  const failed = app.progressPanel(failedDoc, ui(failedDoc));
  assert.match(failed, /<section class="progress-panel" data-phase="failed"/);
  assert.match(failed, /<h2 id="progressTitle">Processing could not finish<\/h2>/);
  const action = { new_document: 'data-action="upload">Upload a new document', resume: 'data-action="resume">Resume processing' }[failedDoc.progress.error.action];
  assert.ok(failed.includes(`<div class="progress-error" role="alert">`) && failed.includes(`<p>${esc(failedDoc.progress.error.text)}</p>${action ? `<button type="button" class="button secondary" ${action}</button>` : ''}`));
  for (const step of failedDoc.progress.steps) assert.ok(failed.includes(`data-step="${step.key}" data-state="${step.state}"`), step.key);
  const resumable = clone(failedDoc);
  resumable.progress.error.action = 'resume';
  assert.match(app.progressPanel(resumable, ui(resumable)), /data-action="resume">Resume processing<\/button>/);
  resumable.progress.error.action = 'none';
  assert.doesNotMatch(app.progressPanel(resumable, ui(resumable)), /progress-error[^]*data-action/);
  const stoppedDoc = fixture('encounter-stopped.json');
  assert.ok(stoppedDoc.progress.can_resume, 'the scenario: a stop that can be resumed');
  const stopped = app.progressPanel(stoppedDoc, ui(stoppedDoc));
  assert.match(stopped, /<section class="progress-panel" data-phase="stopped"/);
  assert.match(stopped, /data-state="stopped"/);
  assert.match(stopped, /<button type="button" class="button primary" data-action="resume">Resume processing/);
  assert.doesNotMatch(stopped, /data-action="stop"/);
  const viewer = clone(stoppedDoc);
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.progressPanel(viewer, ui(viewer)), /data-action="resume"/);
  const confirmingDoc = fixture('encounter-being-confirmed.json');
  const confirming = app.progressPanel(confirmingDoc, ui(confirmingDoc));
  assert.ok(confirming.includes(`<p class="progress-message">${esc(confirmingDoc.progress.message)}</p>`));
  assert.doesNotMatch(confirming, /data-action="stop"|data-action="resume"|progress-card/);
});

test('the reconnecting line is hidden until a poll fails, and only shown while the page polls', () => {
  const doc = fixture('encounter-processing.json');
  assert.match(app.progressPanel(doc, ui(doc)), /<p class="progress-reconnecting" role="status" hidden>Reconnecting…<\/p>/);
  assert.match(app.progressPanel(doc, ui(doc, { reconnecting: true })), /<p class="progress-reconnecting" role="status">Reconnecting…<\/p>/);
  const stopped = fixture('encounter-stopped.json');
  assert.match(app.progressPanel(stopped, ui(stopped, { reconnecting: true })), /progress-reconnecting" role="status" hidden>/);
});

test('polling follows the server: busy, queued and being confirmed poll; results, action needed, failed and stopped do not', () => {
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    assert.equal(app.shouldPoll(doc), doc.progress.busy === true || ['queued', 'processing', 'being_confirmed'].includes(doc.progress.phase), name);
  }
  assert.deepEqual(ENCOUNTERS.filter(name => app.shouldPoll(fixture(name))).sort(), ['encounter-being-confirmed.json', 'encounter-processing.json', 'encounter-queued.json']);
  assert.equal(app.shouldPoll(null), false);
  assert.equal(app.shouldPoll({ progress: { busy: true, phase: 'completed' } }), true);
  assert.equal(app.progressPhase({ state: 'failed' }), 'failed');
  assert.equal(app.progressPhase({ state: 'ready' }), 'completed');
  assert.equal(app.progressPhase({ state: 'ready', progress: { phase: 'nonsense' } }), 'completed');
  assert.equal(app.progressPhase(fixture('encounter-ready.json'), { uploading: true }), 'uploading');
});

test('elapsed and duration text: seconds, minutes and hours, never negative', () => {
  assert.equal(app.durationText(0), '0 s');
  assert.equal(app.durationText(59999), '59 s');
  assert.equal(app.durationText(60000), '1 min 00 s');
  assert.equal(app.durationText(125000), '2 min 05 s');
  assert.equal(app.durationText(3600000 + 120000), '1 h 02 min');
  for (const bad of [-5000, NaN, Infinity, undefined]) assert.equal(app.durationText(bad), '0 s', String(bad));
  assert.equal(app.elapsedText('2026-11-02T14:00:00Z', Date.parse('2026-11-02T14:01:30Z')), '1 min 30 s');
  assert.equal(app.elapsedText('not a time', Date.parse('2026-11-02T14:01:30Z')), '0 s');
  assert.equal(app.clockOffset('2026-11-02T14:01:30Z', Date.parse('2026-11-02T14:00:30Z')), 60000);
  assert.equal(app.clockOffset('garbage', 1000), 0);
});

// --- upload ------------------------------------------------------------------------------------------------------------

test('the upload is acknowledged from the 201 before the first read, and stays in the panel while processing', () => {
  const queued = fixture('encounter-queued.json');
  const at = Date.parse('2026-11-02T14:20:00Z');
  const ack = { id: queued.id, at };
  const placeholder = app.ackView(ack);
  assert.match(placeholder, /<div class="upload-ack" role="status">.*<strong>Uploaded\. Reading your document…<\/strong><p>Received 2 Nov 2026, 14:20 UTC\. You can leave this page; the document stays in Documents\.<\/p>/);
  const panel = app.progressPanel(queued, ui(queued, { ack }));
  assert.match(panel, /data-phase="queued"/);
  assert.match(panel, /<div class="upload-ack" role="status">.*<strong>Uploaded\. Reading your document…<\/strong>/);
  assert.match(panel, /data-step="reading" data-state="waiting"/);
  assert.doesNotMatch(app.progressPanel(queued, ui(queued, { ack: { ...ack, id: 'another' } })), /upload-ack/);
  // once the document has been read, the stages say what is happening; the acknowledgement no longer says reading
  const checking = { ...fixture('encounter-processing.json'), id: ack.id };
  assert.match(app.progressPanel(checking, ui(checking, { ack })), /<div class="upload-ack" role="status">.*<strong>Uploaded\.<\/strong><p>Received 2 Nov 2026, 14:20 UTC\.<\/p>/);
  const ready = fixture('encounter-ready.json');
  assert.doesNotMatch(app.progressPanel(ready, ui(ready, { ack: { ...ack, id: ready.id } })), /upload-ack/);
  assert.equal(app.uploadAck(null), '');
});

test('every upload attempt carries a version-4 client key; the same attempt keeps it', () => {
  let n = 0;
  const bytes = size => Uint8Array.from({ length: size }, () => (n += 37) % 256);
  const key = app.newClientKey(bytes);
  assert.match(key, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.notEqual(app.newClientKey(bytes), key);
  assert.equal(app.newClientKey(() => new Uint8Array(16).fill(255)), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
  const form = app.uploadForm({ paste: true, text: 'SYNTHETIC TEST DOCUMENT', file: null, serviceDate: '2026-11-02', attested: true }, key);
  assert.ok(form instanceof FormData);
  assert.deepEqual([...form.entries()], [['text', 'SYNTHETIC TEST DOCUMENT'], ['service_date', '2026-11-02'], ['synthetic_attestation', 'yes'], ['client_key', key]]);
  const again = app.uploadForm({ paste: true, text: 'SYNTHETIC TEST DOCUMENT', file: null, serviceDate: '2026-11-02', attested: true }, key);
  assert.equal(again.get('client_key'), key, 'a retry of the same attempt sends the same key');
  const file = new Blob(['%PDF-1.4 synthetic'], { type: 'application/pdf' });
  file.name = 'synthetic.pdf';
  const upload = app.uploadForm({ paste: false, text: '', file, serviceDate: '', attested: true }, key);
  assert.deepEqual([...upload.keys()], ['file', 'synthetic_attestation', 'client_key']);
  assert.equal(upload.get('file').name, 'synthetic.pdf');
});

test('the upload form refuses what the server would refuse, before anything is sent', () => {
  const key = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
  const base = { paste: true, text: 'SYNTHETIC TEST DOCUMENT', file: null, serviceDate: '', attested: true };
  assert.equal(app.uploadForm({ ...base, text: '   ' }, key), 'Paste the clinical text, or switch back to uploading a file.');
  assert.equal(app.uploadForm({ ...base, text: 'x'.repeat(400001) }, key), 'The pasted text is longer than 400,000 characters. Upload it as a file instead.');
  assert.equal(app.uploadForm({ ...base, paste: false }, key), 'Choose a PDF, DOCX or TXT document, or paste the text instead.');
  assert.equal(app.uploadForm({ ...base, serviceDate: '2026-02-30' }, key), 'Enter the service date as a valid date, or leave it blank.');
  assert.equal(app.uploadForm({ ...base, attested: false }, key), 'Confirm that the document is synthetic and contains no real patient information.');
});

// --- review and download -----------------------------------------------------------------------------------------------

test('the export dialog offers the draft as suggestions, and the approved download only when every decision is made, listing what is missing', () => {
  const ready = fixture('encounter-mara.json');
  assert.ok(ready.readiness.draft === true && ready.readiness.approved === false && ready.readiness.blockers.length, 'the scenario: a draft with decisions to make');
  const html = app.exportOptions(ready);
  assert.match(html, /<div class="evidence-label">Suggested codes — not approved<\/div><button type="button" class="export-option" data-export-kind="draft" data-export-fmt="txt">/);
  assert.match(html, /data-export-kind="draft" data-export-fmt="csv">/);
  assert.match(html, /data-export-kind="approved" data-export-fmt="txt" disabled>/);
  assert.match(html, /data-export-kind="approved" data-export-fmt="csv" disabled>/);
  assert.ok(html.includes(`<div class="export-blockers"><p>Not available yet:</p><ul>${ready.readiness.blockers.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>`));
  const reviewed = app.exportOptions(fixture('encounter-reviewed.json'));
  assert.match(reviewed, /data-export-kind="approved" data-export-fmt="txt">/);
  assert.doesNotMatch(reviewed, /export-blockers/);
  const nothing = app.exportOptions(fixture('encounter-processing.json'));
  assert.equal(count(nothing, ' disabled>'), 4);
  const page = render(ready);
  assert.match(page, /<button type="button" class="button secondary" data-action="export">.*Review and download<\/button>/);
  assert.match(page, /<div class="heading-actions">.*data-action="export"/);
  assert.doesNotMatch(render(fixture('encounter-processing.json')), /data-action="export"/);
});

test('earlier downloads stay linked, labelled as earlier, once they no longer match (FINAL-V2 amendment 1, 8.3)', () => {
  const doc = fixture('encounter-reviewed.json');
  const current = doc.reports.filter(report => report.current === true);
  const stale = doc.reports.filter(report => report.current !== true);
  assert.ok(current.length && stale.length, 'the scenario: a current and a stale download');
  const html = app.exportOptions(doc);
  for (const report of current) assert.ok(html.includes(`<li class="report-item"><a href="${esc(report.download_url)}" download>${esc(report.filename)}</a><small>`), report.filename);
  for (const report of stale) {
    // A9: an export that is not current downloads with its EARLIER banner - linked, never dropped (the 409 is gone)
    assert.ok(html.includes(`<li class="report-item earlier"><a href="${esc(report.download_url)}" download>${esc(report.filename)}</a><small>`), report.filename);
    assert.ok(html.includes(esc(`Earlier — made on revision ${report.revision}; it may not show the current codes`)));
    assert.doesNotMatch(html, /No longer matches the saved decisions/);
  }
  const bad = clone(doc);
  bad.reports[0].download_url = 'javascript:alert(1)';
  assert.doesNotMatch(app.exportOptions(bad), /javascript:/);
});

test('the export status never claims an approval the server did not report', () => {
  const doc = fixture('encounter-ready.json');
  assert.equal(app.exportStatusText(doc), `Draft only: the codes are suggestions, not approvals. Before the approved download: ${doc.readiness.blockers.join(' ')}`);
  assert.equal(app.exportStatusText({ readiness: { draft: false, approved: false, blockers: [] } }), 'Nothing can be downloaded yet.');
  assert.equal(app.exportStatusText({ readiness: { draft: true, approved: 'yes', blockers: [] } }), 'Draft only: the codes are suggestions, not approvals.');
  assert.equal(app.exportStatusText({ readiness: { approved: true, blockers: [] }, codes: [] }), 'Every suggested code has a decision. The approved download lists only approved codes.');
  for (const name of ENCOUNTERS) {
    const doc2 = fixture(name);
    const tally = { approved: 0, ready: 0, needs_detail: 0, excluded: 0 };
    for (const code of doc2.codes) tally[code.status] += 1;
    const expected = [tally.approved ? `${tally.approved} approved` : '', tally.ready ? `${tally.ready} ready for review` : '',
      tally.needs_detail ? `${tally.needs_detail} ${tally.needs_detail === 1 ? 'needs' : 'need'} a detail` : '', tally.excluded ? `${tally.excluded} excluded` : ''].filter(Boolean).join(' · ') || 'No codes yet';
    assert.equal(app.tallyText(doc2), expected, name);
  }
});

test('the review dialog offers none, 59 or XS only for a code with a modifier review, never prefilled', () => {
  const mara = fixture('encounter-mara.json');
  for (const code of mara.codes) {
    assert.deepEqual(app.reviewModifierOptions(code), code.modifier_review ? [['', 'No modifier'], ...['59', 'XS'].filter(choice => code.modifier_review.options.includes(choice)).map(choice => [choice, choice])] : [], code.code);
  }
  assert.ok(mara.codes.some(code => code.modifier_review) && mara.codes.some(code => !code.modifier_review), 'the scenario');
  assert.deepEqual(app.reviewModifierOptions({ modifier_review: { options: ['XS', '59', '25', 'XU'] } }), [['', 'No modifier'], ['59', '59'], ['XS', 'XS']]);
  assert.deepEqual(app.reviewModifierOptions({ modifier_review: { options: ['25'] } }), []);
  assert.deepEqual(app.reviewModifierOptions({ modifier_review: 'yes' }), []);
  assert.deepEqual(app.MODIFIER_CHOICES, ['59', 'XS']);
  const index = fs.readFileSync(path.join(ROOT, 'studio', 'templates', 'studio', 'index.html'), 'utf8');
  assert.match(index, /<label class="field-label review-modifier" id="reviewModifierField" hidden>.*<select id="reviewModifier"><option value="">No modifier<\/option><option value="59">59<\/option><option value="XS">XS<\/option><\/select>/);
  assert.match(index, /<div class="update-notice" id="updateNotice" role="alert" hidden>/);
  assert.equal(count(index, '<script'), 1);
});

test('the review dialog takes its attestation from the session; the built-in copy only before the session loads', () => {
  const human = fixture('session.json');
  const agent = fixture('session-agent.json');
  assert.equal(app.attestationText(human), human.acknowledgement);
  assert.equal(app.attestationText(agent), agent.acknowledgement);
  assert.equal(human.acknowledgement, app.ACKNOWLEDGEMENTS.human);
  assert.equal(agent.acknowledgement, app.ACKNOWLEDGEMENTS.agent);
  assert.equal(app.attestationText(null), app.ACKNOWLEDGEMENTS.human);
  assert.equal(app.attestationText({ user: { actor_kind: 'agent' } }), app.ACKNOWLEDGEMENTS.agent);
});

// --- errors and the update notice -------------------------------------------------------------------------------------

test('a 409 with error_code client_outdated is the update notice; any other answer is not', () => {
  assert.equal(app.isClientOutdated(409, { error_code: 'client_outdated' }), true);
  assert.equal(app.isClientOutdated(409, { error: 'x', error_code: 'client_outdated', details: {} }), true);
  for (const [status, data] of [[409, {}], [409, null], [409, { error_code: 'other' }], [400, { error_code: 'client_outdated' }], [200, { error_code: 'client_outdated' }], [409, 'client_outdated']]) {
    assert.equal(app.isClientOutdated(status, data), false, JSON.stringify([status, data]));
  }
  assert.equal(app.OUTDATED_TEXT, 'CPT Studio was updated — reload the page to continue.');
  assert.equal(app.CLIENT_HEADER, 'X-CPT-Studio-Client');
  assert.match(app.CLIENT_VERSION, /^customer-\d{4}-\d{2}-\d{2}$/);
});

test('error text is plain: the server sentence when it sends one, a fixed sentence per status otherwise, never a status code', () => {
  assert.equal(app.errorText(409, { error: 'This action is not available for this code right now.' }), 'This action is not available for this code right now.');
  for (const status of [0, 400, 403, 404, 409, 413, 429, 500, 502, 503]) {
    const sentence = app.errorText(status, null);
    assert.ok(sentence && !/\d{3}|HTTP|error code/i.test(sentence), `${status}: ${sentence}`);
  }
  assert.equal(app.errorText(500, { error: '   ' }), app.errorText(500, null));
});

// --- escaping and the denylist -----------------------------------------------------------------------------------------

test('every server string is escaped, in text and attributes, in every component', () => {
  const payload = '<img src=x onerror=alert(1)>"\'`&';
  const poison = value => {
    if (typeof value === 'string') return `${value}${payload}`;
    if (Array.isArray(value)) return value.map(poison);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, poison(item)]));
    return value;
  };
  for (const name of ENCOUNTERS) {
    const doc = poison(fixture(name));
    const html = [markup(doc), app.detailsPanel(doc, ui(doc)), app.listBody('documents', [poison(fixture('encounters.json').encounters[0])]),
      app.inviteMarkup([poison(fixture('encounters.json').encounters[0])])].join('\n');
    assert.doesNotMatch(html, /<img/i, name);
    assert.doesNotMatch(html, /\son\w+="/i, `${name}: no handler attribute`);
    assert.doesNotMatch(html, /="[^"]*"[^\s>/]/, `${name}: no attribute breakout`);
    assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;&quot;&#x27;&#x60;&amp;/, name);
  }
});

test('the customer bundle names no internal machinery, not even in comments', () => {
  const source = fs.readFileSync(BUNDLE, 'utf8');
  // the only exception: the protocol names Django's CSRF protection requires
  const scanned = source.replaceAll('X-CSRFToken', 'X-CSRF').replaceAll('csrfmiddlewaretoken', 'csrfmiddleware');
  const terms = /corti|astra|fable|openai|anthropic|claude|gpt|gemini|google|participant|peer|provider|vendor|model|trace|usage|credit|token|sha256|sha-256|harness|pipeline|engine|orchestrat|diagnostic|operator|replay|request[\s_-]?id|requestid|rule[\s_-]?id|ruleid|response[\s_-]?id|tool[\s_-]?call|cms-|ncci\.|pfs\.|mue\./gi;
  const hits = [...scanned.matchAll(terms)].map(match => `${match[0]} @${scanned.slice(0, match.index).split('\n').length}`);
  assert.deepEqual(hits, []);
  assert.equal(count(source, 'X-CSRFToken'), 1);
  // and the same scan finds a planted word, so a clean result means something
  assert.ok([...`${scanned}\n// Astra`.matchAll(terms)].length === 1);
});

// refutation r2, L4-1: the shipped denylist's bundle scan (ops/verification/customer-denylist.json, by the walk's own
// reader ops/verify_browser.cjs) passes on the customer bundle - a developer comment naming an HTTP status failed it
// while the narrower nets above passed
test('the customer bundle passes the shipped bundle scan, comments included', () => {
  const walk = require('../../ops/verify_browser.cjs');
  const ctx = walk.scanContext({ allowed: ['cpt.quillmd.com'] });
  for (const file of [BUNDLE, path.join(ROOT, 'studio', 'static', 'studio', 'styles.css')]) {
    assert.deepEqual(walk.scanText(fs.readFileSync(file, 'utf8'), ctx, 'bundle', path.basename(file)), [], file);
  }
  const planted = walk.scanText('// HTTP 409 with {"error_code": "client_outdated"}', ctx, 'bundle', 'planted');
  assert.deepEqual(planted.map(hit => [hit.id, hit.severity]), [['http_status', 'hard']], 'a clean result means something');
});

test('no customer page names internal machinery, in text or attributes, and the scan catches a planted word', () => {
  for (const name of ENCOUNTERS) {
    const doc = fixture(name);
    assert.deepEqual(leaks(everything(doc), doc), [], name);
  }
  const rows = fixture('encounters.json').encounters;
  const lists = [app.overviewView(), app.documentsView('documents'), app.documentsView('queue'), app.howItWorksView(), app.listBody('documents', rows),
    app.listBody('queue', rows), app.listDescription('queue', rows), app.inviteMarkup(rows), app.ackView({ id: rows[0].id, at: 0 })].join('\n');
  assert.deepEqual(leaks(lists, null), []);
  // positive controls: a planted provider name in a server string, a model id in an attribute, a rule id, a hash
  const planted = clone(fixture('encounter-mara.json'));
  planted.codes[0].summary = 'Selected by corti.';
  planted.codes[1].id = 'gpt-6-astra';
  planted.limitations.push('Check ncci.ptp is not verified.');
  planted.activity.push({ event: 'x', summary: 'sha 81406f7fbb8b3de67555092acc83efa4c56a46fb7b9316b3abcb01d76a3fa551', actor: '', actor_kind: 'human', at: '' });
  const found = leaks(everything(planted), planted).join('\n');
  for (const word of ['corti', 'gpt-', 'ncci.ptp', '81406f7f']) assert.match(found, new RegExp(word, 'i'), word);
  // the document's own words are the member's document, shown as it is: a synthetic patient named Claude is not a leak
  const own = clone(fixture('encounter-ready.json'));
  own.document.text = own.document.text.replace(/Patient: \w+/, 'Patient: Claude');
  assert.ok(own.document.text.includes('Patient: Claude'), 'the control plants the name');
  assert.deepEqual(leaks(app.sourcePanel(own, app.documentLayout(own)), own), []);
});

test('the stylesheet and the templates carry no internal-machinery words either', () => {
  const terms = /corti|astra|fable|openai|anthropic|claude|participant|peer|provider|vendor|model|trace|usage|credit|token|sha256|harness/gi;
  const css = fs.readFileSync(path.join(ROOT, 'studio', 'static', 'studio', 'styles.css'), 'utf8');
  assert.deepEqual([...css.matchAll(terms)].map(match => match[0]), []);
  for (const name of ['index.html', 'login.html']) {
    const html = fs.readFileSync(path.join(ROOT, 'studio', 'templates', 'studio', name), 'utf8').replace(/\{%\s*csrf_token\s*%\}/g, '');
    assert.deepEqual([...html.matchAll(terms)].map(match => match[0]), [], name);
  }
});

// --- lists ---------------------------------------------------------------------------------------------------------------

// session decision (n), 2026-11-04: the bounded re-check of what is still open (the installed page's second review),
// offered only where the server says this member can ask for it now
test('the re-check of what is still open is offered only when the server says this member can ask for it', () => {
  const base = fixture('encounter-reviewed.json');
  const open = ['Colonoscopy: biopsy: no supported code was found for it.'];
  const offered = { ...base, unresolved: open, recheck: { available: true, can_request: true } };
  const html = app.notesSection(offered);
  assert.equal(count(html, 'data-action="recheck"'), 1);
  assert.ok(html.includes(`<button type="button" class="button secondary" data-action="recheck">${app.RECHECK_LABEL}</button>`));
  assert.ok(html.includes(`<p class="recheck-note">${app.RECHECK_NOTE}</p>`));
  assert.ok(html.indexOf('<h3>Still open</h3>') < html.indexOf('data-action="recheck"'));
  assert.match(html, /<li>Colonoscopy: biopsy: no supported code was found for it\.<\/li>/);
  for (const recheck of [{ available: true, can_request: false }, { available: false, can_request: false },
    { available: true, can_request: 'true' }, undefined, null]) {
    assert.equal(count(app.notesSection({ ...offered, recheck }), 'data-action="recheck"'), 0, JSON.stringify(recheck));
  }
  // offered with nothing listed as open still says where it is; never a section with nothing in it
  const bare = app.notesSection({ ...base, unresolved: [], limitations: [], recheck: { available: true, can_request: true } });
  assert.match(bare, /<h3>Still open<\/h3><div class="recheck-offer">/);
  assert.equal(app.notesSection({ ...base, unresolved: [], limitations: [], recheck: { available: false, can_request: false } }), '');
  for (const word of ['Corti', 'provider', 'Astra', 'Fable', 'second review']) {
    assert.ok(!html.toLowerCase().includes(word.toLowerCase()), word);
  }
});

test('list rows show the plain state, the kind, the details needed and the date; the queue lists what waits on the member', () => {
  const rows = fixture('encounters.json').encounters;
  const kinds = { upload: 'Uploaded file', paste: 'Pasted text', addendum: 'Document with addendum' };
  for (const row of rows) {
    const html = app.documentRow(row);
    assert.ok(html.startsWith(`<a class="document-row" href="#doc/${row.id}">`), row.id);
    const open = row.open_details > 0 ? `${row.open_details} ${row.open_details === 1 ? 'detail' : 'details'} needed` : '';
    assert.ok(html.includes(`<small>${[kinds[row.kind], open].filter(Boolean).join(' · ')}</small>`), row.id);
    assert.ok(html.includes(`>${esc(app.formatDate(row.service_date) || (row.date_conflict ? 'Date to choose' : 'Not documented'))}</span>`), row.id);
  }
  const action = rows.find(row => row.state === 'action_needed');
  assert.match(app.documentRow(action), /<span class="status amber">Action needed<\/span>/);
  assert.match(app.documentRow({ ...action, state: 'mystery', state_label: '', date_conflict: false, service_date: '2026-10-28' }), /<span class="status gray">Unknown<\/span>.*28 Oct 2026/);
  const queued = rows.filter(app.inQueue);
  assert.deepEqual(queued, rows.filter(row => row.in_queue === true));
  for (const row of rows.filter(row => app.QUEUE_STATES.has(row.state))) assert.equal(row.in_queue, true, row.id);
  assert.ok(queued.some(row => !app.QUEUE_STATES.has(row.state)), 'a row the review queue\'s rule holds beyond the three states');
  assert.equal(count(app.listBody('queue', rows), 'class="document-row"'), queued.length);
  assert.equal(app.inQueue({ ...rows[0], in_queue: 'true' }), false);
  assert.equal(count(app.listBody('workspace', rows), 'class="document-row"'), Math.min(5, rows.length));
  assert.match(app.listBody('queue', []), /Nothing is waiting for you\./);
  assert.equal(app.listDescription('documents', rows), `${rows.length} synthetic documents in this workspace.`);
  // the badge is the server's count of the rows the queue lists (session decision (o), 2026-11-04: customer_api.in_queue,
  // one predicate for both) - never more and never fewer than the page lists
  const counted = fixture('session.json').counts.queue;
  assert.equal(counted, queued.length, `${counted} counted, ${queued.length} listed`);
  assert.equal(app.listDescription('queue', rows), `${queued.length} documents wait on you: a date to choose, a detail to answer, codes to review, or something still open.`);
});


// --- the Gemini migration (S13): the retry of a failed reading, the paused copy, the new facts ---
//
// What the server serves (studio/progress.py INTERPRETATION_ERRORS and the interpreter's paused phase; studio/answers.py
// PROMPTS for the new path's facts; interpretation/wording.py MISSING) is read from the source, so a fixture here is the
// server's own wording, never one written for the test.
const SERVER = name => fs.readFileSync(path.join(ROOT, 'studio', ...name.split('/')), 'utf8');
const pyString = (source, name) => {
  const found = new RegExp(`^${name} = \\(?((?:\\s*'[^']*')+)\\)?$`, 'm').exec(source);
  assert.ok(found, `${name} not found`);
  return [...found[1].matchAll(/'([^']*)'/g)].map(match => match[1]).join('');
};
const PAUSED = pyString(SERVER('interpretation/holds.py'), 'PAUSED_MESSAGE');
const READING_FAILED = (() => {
  const found = /'failed': \('([^']*)'\s*\n\s*'([^']*)', 'retry_reading'\)/.exec(SERVER('progress.py'));
  assert.ok(found, 'INTERPRETATION_ERRORS failed not found');
  return found[1] + found[2];
})();

// a document whose reading could not be completed, as progress.encounter_progress serves it (FINAL 6.11, 11.3)
function failedReading(action = 'retry_reading') {
  const doc = clone(fixture('encounter-failed.json'));
  doc.progress.steps = doc.progress.steps.map(step => ({ ...step, state: step.key === 'reading' ? 'done' : step.key === 'identifying' ? 'failed' : 'not_started' }));
  doc.progress.message = READING_FAILED;
  doc.progress.error = { text: READING_FAILED, action };
  return doc;
}

// a document whose reading the interpreter's pause ended (FINAL 11.2): the existing stopped state, the paused phase
function pausedReading() {
  const doc = clone(fixture('encounter-stopped.json'));
  doc.progress.phase = 'paused';
  doc.progress.steps = doc.progress.steps.map(step => ({ ...step, state: step.key === 'reading' ? 'done' : step.key === 'identifying' ? 'stopped' : 'not_started' }));
  doc.progress.message = PAUSED;
  doc.progress.error = { text: PAUSED, action: 'resume' };
  return doc;
}

test('a reading that could not be completed offers "Try reading again"; too long, or a viewer, is never offered it', () => {
  assert.ok(READING_FAILED.startsWith('Reading the documented procedures could not be completed'), READING_FAILED);
  const doc = failedReading();
  const html = app.progressPanel(doc, ui(doc));
  assert.match(html, /<section class="progress-panel" data-phase="failed"/);
  assert.ok(html.includes('<div class="progress-error" role="alert">'));
  assert.ok(html.includes(`<p>${esc(READING_FAILED)}</p><button type="button" class="button secondary" data-action="retry-reading">Try reading again</button>`), html);
  assert.equal(count(html, 'data-action="retry-reading"'), 1);
  assert.equal(count(html, READING_FAILED), 1, 'the head does not repeat the notice');
  // a member who may not act is served 'none' (customer_api.progress_block), and even served the action sees no button
  const viewer = failedReading();
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.progressPanel(viewer, ui(viewer)), /data-action="retry-reading"/);
  assert.doesNotMatch(app.progressPanel(failedReading('none'), ui(doc)), /data-action="retry-reading"/);
  // a document too long to be read in one piece is never offered a retry (C5): the server says to upload it again
  const long = failedReading('new_document');
  assert.match(app.progressPanel(long, ui(long)), /data-action="upload">Upload a new document<\/button>/);
  assert.doesNotMatch(app.progressPanel(long, ui(long)), /retry-reading/);
  // every action the server serves has its button, and no button the server never asks for
  const contract = JSON.parse(fs.readFileSync(path.join(ROOT, 'ops', 'verification', 'customer-contract.json'), 'utf8'));
  const served = contract.encounter.keys.progress.keys.error.keys.action.enum.filter(action => action !== 'none');
  assert.deepEqual(Object.keys(app.ERROR_ACTIONS).sort(), [...served].sort());
  // the actions of progress.py's two error tables (ERRORS, INTERPRETATION_ERRORS) and Resume beside them
  const progress = SERVER('progress.py');
  const tables = ['ERRORS', 'INTERPRETATION_ERRORS'].map(name => {
    const at = progress.indexOf(`\n${name} = {\n`);
    assert.ok(at >= 0, `${name} not found in progress.py`);
    return progress.slice(at, progress.indexOf('\n}\n', at));
  });
  const actions = new Set(tables.flatMap(table => [...table.matchAll(/, '([a-z_]+)'\),?$/gm)].map(match => match[1])));
  assert.ok(actions.has('retry_reading') && actions.has('new_document'), [...actions].join(', '));
  assert.ok(progress.includes("'action': 'resume' if review.can_resume(encounter) else 'none'"));
  for (const action of actions) assert.ok(action === 'none' || Object.hasOwn(app.ERROR_ACTIONS, action), `progress.py serves ${action}`);
  // FINAL-V2 amendment 1, 7.1: during an update the notice's action is the row's of customer_api.UPDATE_TEXTS (step 3c's
  // table, which progress.update_error serves) - every one has its button, "Try updating again" among them
  const updateActions = new Set([...SERVER('customer_api.py').matchAll(/^\s+'(failed|paused|stopped|being_confirmed)', '([a-z_]+)'\),$/gm)].map(match => match[2]));
  assert.deepEqual([...updateActions].sort(), ['none', 'resume', 'retry_reading', 'retry_update']);
  for (const action of updateActions) assert.ok(action === 'none' || Object.hasOwn(app.ERROR_ACTIONS, action), `UPDATE_TEXTS serves ${action}`);
  assert.deepEqual(app.ERROR_ACTIONS.retry_update, ['retry-update', 'Try updating again']);
});

test('the paused copy: a reading paused on the installation reads as paused with Resume, ran for its time and is still', () => {
  assert.ok(SERVER('progress.py').includes("PHASES = ('queued', 'processing', 'action_needed', 'awaiting_detail', 'completed', 'partial', 'failed', 'stopped',\n          'being_confirmed', 'paused', 'updating')"));
  const doc = pausedReading();
  const html = app.progressPanel(doc, ui(doc));
  assert.match(html, /^<section class="progress-panel" data-phase="paused" aria-labelledby="progressTitle">/);
  assert.match(html, /<h2 id="progressTitle">Processing paused<\/h2>/);
  assert.ok(html.includes('<use href="#i-info"/>'), 'the paused head is informational, never an alarm or a clock');
  assert.equal(count(html, esc(PAUSED)), 1, 'the paused sentence once, in the notice');
  assert.ok(html.includes(`<div class="progress-error" role="alert"><svg class="" aria-hidden="true"><use href="#i-info"/></svg><div><p>${esc(PAUSED)}</p></div></div>`), html);
  assert.match(html, /<button type="button" class="button primary" data-action="resume">Resume processing/);
  assert.equal(count(html, 'data-action="resume"'), 1, 'Resume once: the panel\'s own');
  assert.doesNotMatch(html, /data-action="stop"|is-animated|progress-card/);
  assert.ok(html.includes('<p class="leave-note">You can leave this page — your document is saved.</p>'));
  assert.ok(html.includes(`<p class="progress-time">Ran for <span data-elapsed data-since="${doc.progress.started_at}" data-until="${doc.progress.finished_at}">`), 'paused before it finished: it ran, it did not finish');
  assert.equal(app.shouldPoll(doc), false, 'nothing runs until Resume');
  assert.equal(app.emptyResults(doc, ui(doc)), 'Processing is paused, so no codes have been suggested yet. Suggested codes appear here once processing resumes.');
  // the earlier pause (decision (j): a silent worker while the document is busy) keeps its own copy: no time, it polls
  const silent = clone(fixture('encounter-processing.json'));
  silent.progress.phase = 'paused';
  silent.progress.message = 'Processing is paused: the processing service is not responding right now. Your document is saved, and this page shows the next step once the service is back.';
  const busy = app.progressPanel(silent, ui(silent));
  assert.ok(busy.includes(`<p class="progress-message">${esc(silent.progress.message)}</p>`));
  assert.doesNotMatch(busy, /is-animated|Ran for|Finished in|Elapsed/);
  assert.equal(app.shouldPoll(silent), true);
  // the stopped and failed panels keep their copy
  const stopped = fixture('encounter-stopped.json');
  assert.ok(app.progressPanel(stopped, ui(stopped)).includes('<h2 id="progressTitle">Processing stopped</h2>'));
  assert.equal(app.emptyResults(stopped, ui(stopped)), 'Processing stopped before codes were suggested.');
  for (const page of [html, busy]) assert.deepEqual(leaks(page, doc), []);
});

test('"Try reading again" asks the server once, with the page\'s headers; a refusal says why in the server\'s words', async () => {
  const doc = failedReading();
  const saved = { document: global.document, fetch: global.fetch };
  const toastEl = { textContent: '', classList: { add() {}, remove() {} } };
  const elements = new Map([['#toast', toastEl]]);
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, { textContent: '', hidden: false });
    return elements.get(selector);
  };
  const attributes = new Set();
  const button = { dataset: { action: 'retry-reading' }, disabled: false, toggleAttribute: (name, on) => (on ? attributes.add(name) : attributes.delete(name)) };
  const asked = [];
  let answer = { status: 201, body: { retrying: true } };
  try {
    global.document = { querySelector: element, querySelectorAll: () => [], cookie: 'cptstudio_csrf=token123' };
    global.fetch = async (url, init) => {
      asked.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : null, csrf: init.headers['X-CSRFToken'], client: init.headers[app.CLIENT_HEADER] });
      const reply = url === '/api/session' ? { status: 200, body: fixture('session.json') } : answer;
      return { status: reply.status, ok: reply.status < 300, redirected: false, url: `http://127.0.0.1${url}`, headers: { get: () => 'application/json' }, json: async () => reply.body };
    };
    app.state.doc = doc;
    app.state.route = null;  // nothing is redrawn here: the page's refresh is the route's
    // the notice's button, clicked: the page's own click handler takes it
    const target = { closest: selector => (selector === '[data-action]' ? button : null) };
    await app.onClick({ target });
    await new Promise(resolve => setImmediate(resolve));
    const posts = () => asked.filter(item => item.method === 'POST');
    assert.deepEqual(posts(), [{ url: `/api/encounters/${doc.id}/retry-reading`, method: 'POST', body: {}, csrf: 'token123', client: app.CLIENT_VERSION }]);
    assert.equal(toastEl.textContent, app.RETRY_ASKED);
    assert.equal(app.RETRY_ASKED, 'Asked. The documented procedures are being read again.');
    // a refusal (409, the member's words: customer_api.KNOWN_ERRORS) is said, and the button can be used again
    asked.length = 0;
    answer = { status: 409, body: { error: 'Reading documented procedures is paused on this installation; resume processing once it is available again.' } };
    await app.retryReading(button);
    assert.deepEqual(posts().map(item => item.url), [`/api/encounters/${doc.id}/retry-reading`]);
    assert.equal(toastEl.textContent, answer.body.error);
    assert.equal(button.disabled, false);
    // nothing is asked without a document on the page
    asked.length = 0;
    app.state.doc = null;
    await app.retryReading(button);
    assert.deepEqual(asked, []);
  } finally {
    global.document = saved.document;
    global.fetch = saved.fetch;
    app.state.doc = null;
    clearTimeout(app.state.toastTimer);
  }
});

test('the new path\'s facts are drawn in the server\'s words, answerable only as not documented or cannot confirm', () => {
  const answers = SERVER('answers.py');
  const wording = SERVER('interpretation/wording.py');
  const missing = /^MISSING = \{\n((?:    '[a-z_]+': '[^']*',\n)+)\}/m.exec(wording);
  assert.ok(missing, 'interpretation.wording.MISSING not found');
  const facts = [...missing[1].matchAll(/^    '([a-z_]+)': '([^']*)',$/gm)].map(match => [match[1], match[2]]);
  assert.deepEqual(facts.map(([fact]) => fact), ['event_time', 'event_performer', 'act_target', 'technique', 'statement_scope', 'act_method', 'procedure',
    'event_entry', 'exam_stations', 'act_yield', 'act_cause', 'act_part']);
  const passage = 'The colonoscope was advanced to the cecum.';
  for (const [fact, what] of facts) {
    const prompt = new RegExp(`^    '${fact}': '([^']*)',$`, 'm').exec(answers);
    assert.ok(prompt, `answers.PROMPTS has no ${fact}`);
    const row = { id: `d-${fact}`, fact, family_label: 'Colonoscopy', prompt: prompt[1], control: 'confirm', choices: [], allow: ['not_documented', 'cannot_confirm'],
      document_value: null, entered_value: null, quote: null, affects: ['45378'], saved: null, addendum_allowed: false, missing: what,
      statement: `CPT Studio could not confirm ${what}.`, passages: [{ text: passage, start: 0, end: passage.length, page: 1 }] };
    const doc = clone(fixture('encounter-needs-detail.json'));
    doc.details_needed = [row];
    const html = app.detailRow(row, doc, ui(doc));
    assert.ok(html.includes(`<span class="detail-prompt">${esc(prompt[1])}</span>`), fact);
    assert.ok(html.includes(`<p class="detail-statement">${esc(row.statement)}</p>`), fact);
    assert.ok(html.includes(`<q class="detail-quote">${esc(passage)}</q><span class="detail-page">Page 1</span>`), fact);
    // a confirmation: the two answers a member may give, as buttons, and no choice of a clinical value (answers.py:
    // the allowed answers stay "Not documented" and "Cannot confirm")
    const offered = [...html.matchAll(/data-detail-choice="([^"]*)"/g)].map(match => match[1]);
    assert.deepEqual(offered, ['not_documented', 'cannot_confirm'], fact);
    assert.ok(html.includes('>Not documented</button>') && html.includes('>Cannot confirm</button>'), fact);
    assert.doesNotMatch(html, /type="radio"|type="date"/, fact);
    assert.deepEqual(leaks(html, doc), [], fact);
    assert.doesNotMatch(prompt[1] + what, /gemini|google|argon|interpreter|model/i, fact);
  }
});

test('the net names the interpreter\'s vendor and model; argon plasma coagulation in the document is no leak', () => {
  const doc = clone(fixture('encounter-ready.json'));
  const planted = clone(doc);
  planted.codes[0].summary = 'Read by Gemini.';
  planted.limitations.push('The interpretation came from gemini-4-argon.');
  planted.activity.push({ event: 'x', summary: 'Google answered', actor: '', actor_kind: 'human', at: '' });
  const found = leaks(everything(planted), planted).join('\n');
  for (const word of ['Gemini', 'gemini-', 'Google']) assert.match(found, new RegExp(word), word);
  // the document's own words are the member's document: an argon plasma coagulation it documents is drawn as it is
  const own = clone(doc);
  own.document.text = `${own.document.text}\nHemostasis: argon plasma coagulation was applied to the angioectasia.\n`;
  assert.deepEqual(leaks(app.sourcePanel(own, app.documentLayout(own)), own), []);
  // and "argon" alone is clinical wording, never a name
  assert.deepEqual(forbidden('Argon plasma coagulation (APC) was applied.'), []);
});

// --- FINAL-V2 amendment 1 (step 5d): the codes are updated automatically after a save ---------------------------------
//
// The page while an update is pending (5.1), what changed (6.2), earlier decisions and downloads (5.4, 8.3), "Try updating
// again" (7.2), and typing that sends nothing until Save (11.1 U2). The server's sentences are read from
// studio/customer_api.py (step 3c's constants), so every text drawn here is the server's own; the copies app.js holds are
// held equal to them here and in tests/v2/test_update_api.py.

const CUSTOMER_API = SERVER('customer_api.py');
// A Python string constant of customer_api (adjacent single-quoted literals, a trailing comment allowed).
const pyText = name => {
  const found = new RegExp(`^${name} = \\(?((?:\\s*'[^']*')+)\\)?(?:\\s*#.*)?$`, 'm').exec(CUSTOMER_API);
  assert.ok(found, `${name} not found`);
  return [...found[1].matchAll(/'([^']*)'/g)].map(match => match[1]).join('');
};
// One customer_api.UPDATE_TEXTS row's four forms (details, no_restore, documentation, check) and its phase and action,
// read from the source: the literals between `'<situation>': _update_row(` and the row's close.
function updateRow(situation) {
  const at = CUSTOMER_API.indexOf(`    '${situation}': _update_row(`);
  assert.ok(at >= 0, `UPDATE_TEXTS has no ${situation}`);
  const body = CUSTOMER_API.slice(at + situation.length + 20, CUSTOMER_API.indexOf('),\n', at));
  const args = [''];
  for (const match of body.matchAll(/'((?:[^'\\]|\\.)*)'|,/g)) {
    if (match[0] === ',') args.push('');
    else args[args.length - 1] += match[1].replace(/\\'/g, "'");
  }
  const [details, noRestore, documentation, check, phase, action] = args.map(item => item.trim());
  return { details, no_restore: noRestore, documentation, check, phase, action };
}
// update_text's choice (customer_api.update_text): case C for 'documentation', the check form for 'check', else the
// restore form only when restorable
function updateText(situation, kind, restorable) {
  const row = updateRow(situation);
  return kind === 'documentation' ? row.documentation : kind === 'check' ? row.check : restorable ? row.details : row.no_restore;
}
const SAVED_LINES = {
  unfinished: { updating: pyText('SAVED_CHANGES_UNFINISHED'), other: pyText('SAVED_CHANGES_UNFINISHED_OTHER') },
  same_details: { updating: pyText('SAVED_CHANGES_SAME_DETAILS'), other: pyText('SAVED_CHANGES_SAME_DETAILS_OTHER') },
  check: { updating: pyText('SAVED_CHANGES_CHECK'), other: pyText('SAVED_CHANGES_CHECK_OTHER') },
};
// the situations progress.update_error serves for each update state (7.1), one each for the page walk below
const STATE_SITUATIONS = { failed: 'review_failed', stopped: 'stopped_by_member', paused: 'interpreter_paused', being_confirmed: 'being_confirmed' };
const PHASE_OF = { updating: 'updating', failed: 'failed', stopped: 'stopped', paused: 'paused', being_confirmed: 'being_confirmed' };

// A pending update as GET /api/encounters/<id> serves it (customer_api.encounter_json, step 5d): the ready fixture's codes
// become the earlier codes (read-only, no allowed action), every other assessment-derived section stays theirs, and the
// progress panel, readiness and update block are the update's in ``state`` of ``kind``.
function updateDoc(state, kind = 'details', { earlier = true, restorable = kind === 'details', changes } = {}) {
  const doc = clone(fixture('encounter-ready.json'));
  const running = state === 'updating';
  doc.earlier_codes = earlier ? doc.codes.map(code => ({ ...code, allowed_actions: [] })) : [];
  doc.codes = [];
  doc.state = running ? 'updating' : { failed: 'failed', stopped: 'stopped', paused: 'stopped', being_confirmed: 'being_confirmed' }[state];
  doc.state_label = app.STATE_LABELS[doc.state];
  doc.progress = { ...doc.progress, phase: PHASE_OF[state], busy: running, can_stop: running, can_resume: ['stopped', 'paused'].includes(state),
    started_at: '2026-11-13T10:00:00Z', finished_at: running ? null : '2026-11-13T10:02:00Z', server_time: '2026-11-13T10:03:00Z',
    message: running ? 'Working on your document. This page updates by itself.' : '',
    active_detail: running ? 'Coding validation' : '',
    steps: doc.progress.steps.map(step => ({ ...step, state: ['reading', 'identifying'].includes(step.key) ? 'skipped' : step.key === 'checking' ? (running ? 'active' : 'done') : 'not_started' })) };
  if (!running) {
    const row = updateRow(STATE_SITUATIONS[state]);
    doc.progress.error = { text: updateText(STATE_SITUATIONS[state], kind, restorable), action: row.action };
    doc.progress.message = doc.progress.error.text;
  } else {
    doc.progress.error = null;
  }
  const form = running ? 'updating' : 'other';
  const blocker = { 'updating/details': 'The codes are being updated after your change.', 'other/details': 'The codes have not been updated after your change yet.',
    'updating/check': 'The codes are being updated.', 'other/check': 'The codes have not been updated yet.' }[`${form}/${kind === 'check' ? 'check' : 'details'}`];
  doc.readiness = { draft: false, approved: false, blockers: [blocker] };
  doc.recheck = { available: false, can_request: false };
  doc.reports = doc.reports.map(report => ({ ...report, current: false, revision: 1 }));
  const saved = kind === 'check' ? [SAVED_LINES.check[form]] : ['Place of service: Hospital outpatient department'];
  doc.update = { pending: true, state, kind, restorable, changes: changes || (kind === 'documentation' ? ['Documentation added (revision 2)'] : saved),
    saved_by: kind === 'check' ? null : 'Synthetic Reviewer', saved_at: kind === 'check' ? null : '2026-11-13T10:00:00Z', started_at: '2026-11-13T10:00:00Z',
    earlier: { made_at: '2026-11-12T09:30:00Z', revision: 1, service_date: '2 November 2026',
      details: ['Date of service: 2 November 2026', 'Place of service: not documented', 'Patient: not documented', 'Claim: not documented'] } };
  doc.what_changed = null;
  doc.decision_history = [];
  return doc;
}

// The texts the page itself draws for a document (the server's notice and the document's own words left out): what a
// member reads that the page chose.
function pageTexts(doc, html) {
  const served = [text(doc.progress?.error?.text), text(doc.progress?.message), ...strings(doc.update?.changes)];
  return parts(html).texts.map(item => item.trim()).filter(item => item && !served.includes(item) && !String(doc.document?.text || '').includes(item));
}
function text(value) { return typeof value === 'string' ? value.trim() : ''; }
function strings(value) { return (Array.isArray(value) ? value : []).map(text).filter(Boolean); }

test('the page holds the server\'s update sentences verbatim (customer_api, step 3c)', () => {
  for (const name of ['UPDATE_TITLE', 'UPDATE_TITLE_CHECK', 'CHANGE_SAVED_BY', 'EARLIER_CODES_HEADING', 'EARLIER_CODES_HEADING_CHECK', 'EARLIER_CODES_MADE',
    'EARLIER_CODES_MADE_CHECK', 'ANSWER_AFTER_UPDATE', 'RESULTS_UPDATING', 'RESULTS_NOT_UPDATED', 'RESULTS_EARLIER_SHOWN', 'RESULTS_NO_EARLIER_CODE', 'TALLY_BEFORE',
    'TALLY_NO_EARLIER_CODE', 'RESULTS_UPDATING_CHECK', 'RESULTS_NOT_UPDATED_CHECK', 'RESULTS_EARLIER_SHOWN_CHECK', 'RESULTS_NO_EARLIER_CODE_CHECK', 'TALLY_BEFORE_CHECK',
    'TALLY_NO_EARLIER_CODE_CHECK', 'RESTORED_TOAST', 'WHAT_CHANGED_COMPARED', 'WHAT_CHANGED_UNCHANGED', 'WHAT_CHANGED_UNCHANGED_ONE', 'EARLIER_DOWNLOAD',
    'RETRY_UPDATE_ASKED']) {
    assert.equal(app.TEXTS[name], pyText(name), name);
  }
  assert.equal(app.RETRY_UPDATE_ASKED, app.TEXTS.RETRY_UPDATE_ASKED);
  const notes = name => Object.fromEntries([...new RegExp(`^${name} = \\{\\n((?:.|\\n)*?)^\\}`, 'm').exec(CUSTOMER_API)[1]
    .matchAll(/'(updating|other)': \(?((?:\s*'[^']*')+)\)?,?/g)].map(match => [match[1], [...match[2].matchAll(/'([^']*)'/g)].map(item => item[1]).join('')]));
  assert.deepEqual(app.TEXTS.UPDATE_EXPORT_NOTE, notes('UPDATE_EXPORT_NOTE'));
  assert.deepEqual(app.TEXTS.UPDATE_EXPORT_NOTE_CHECK, notes('UPDATE_EXPORT_NOTE_CHECK'));
  assert.equal(app.STATE_LABELS.updating, /'updating': '([^']*)'/.exec(CUSTOMER_API)[1]);
  assert.deepEqual(app.UPDATE_STATES, ['updating', 'failed', 'stopped', 'paused', 'being_confirmed']);
  assert.ok(app.PHASES.includes('updating'));
});

test('U21: an update in every state and kind - the panel, the results, the earlier codes and the exports say what is true', () => {
  for (const kind of ['details', 'documentation', 'check']) {
    for (const state of app.UPDATE_STATES) {
      const doc = updateDoc(state, kind);
      const at = `${kind}/${state}`;
      const html = render(doc);
      const running = state === 'updating';
      const check = kind === 'check';
      // the panel: titled by the update only while it runs; what was saved under the title; nothing animated unless it runs
      const panel = app.progressPanel(doc, ui(doc));
      if (running) assert.ok(panel.includes(`<h2 id="progressTitle">${esc(check ? app.TEXTS.UPDATE_TITLE_CHECK : app.TEXTS.UPDATE_TITLE)}</h2>`), at);
      else assert.doesNotMatch(panel, /updating codes/i, at);
      for (const line of doc.update.changes) assert.ok(panel.includes(`<li>${esc(line)}</li>`), at);
      if (check) assert.doesNotMatch(panel, /Saved by/, at);
      else assert.ok(panel.includes(esc(`Saved by Synthetic Reviewer, ${app.formatTimestamp('2026-11-13T10:00:00Z')}`)), at);
      assert.equal(/is-animated/.test(panel), running, at);
      // the results section and the tally: never "no codes were suggested" nor "No codes yet" while earlier codes exist
      const results = app.resultsSection(doc, app.documentLayout(doc), ui(doc));
      const expected = running ? (check ? app.TEXTS.RESULTS_UPDATING_CHECK : app.TEXTS.RESULTS_UPDATING) : (check ? app.TEXTS.RESULTS_NOT_UPDATED_CHECK : app.TEXTS.RESULTS_NOT_UPDATED);
      assert.ok(results.includes(`<p class="results-empty">${esc(expected)}</p>`), `${at}: ${results}`);
      assert.doesNotMatch(results, /No CPT codes were suggested|No codes were suggested|before codes were suggested|no codes have been suggested/, at);
      assert.equal(app.tallyText(doc), `${check ? app.TEXTS.TALLY_BEFORE_CHECK : app.TEXTS.TALLY_BEFORE}${doc.earlier_codes.length} ready for review`, at);
      // "being updated" only while the update runs, in every string the page draws for it
      const drawn = [html, app.exportOptions(doc), app.exportStatusText(doc)].join('\n');
      assert.equal(/being updated/.test(drawn), running, `${at}: ${drawn.match(/[^<>]*being updated[^<>]*/)}`);
      // the earlier codes: their own section, read-only, with when they were made; their other sections inside it
      const earlier = app.earlierCodesSection(doc, ui(doc));
      assert.ok(earlier.includes(`<h2 id="earlierTitle">${esc(check ? app.TEXTS.EARLIER_CODES_HEADING_CHECK : app.TEXTS.EARLIER_CODES_HEADING)}</h2>`), at);
      const made = (check ? app.TEXTS.EARLIER_CODES_MADE_CHECK : app.TEXTS.EARLIER_CODES_MADE).replace('{time}', app.formatTimestamp('2026-11-12T09:30:00Z')).replace('{date}', '2 November 2026');
      assert.ok(earlier.includes(`<p class="earlier-made">${esc(made)}</p>`), at);
      // their own hooks, never the current codes' (CORE-UX-DESIGN 8: the walk reads ol.result-list > li.result-row)
      assert.equal(count(earlier, '<li class="earlier-row" '), doc.earlier_codes.length, at);
      assert.equal(count(earlier, '<ol class="earlier-list" '), doc.earlier_codes.length ? 1 : 0, at);
      assert.doesNotMatch(earlier, /result-row|result-list/, at);
      assert.doesNotMatch(earlier, /data-decision=|data-evidence=/, `${at}: no decision button, no passage button`);
      assert.doesNotMatch(html, /data-decision=/, at);
      for (const section of ['class="result-notes not-coded"', 'class="other-codes"', 'class="result-notes limitations"']) {
        if (!html.includes(section)) continue;
        assert.equal(count(html, section), count(earlier, section), `${at}: ${section} only inside the earlier codes`);
      }
      assert.doesNotMatch(html, /data-action="recheck"/, `${at}: the re-check is never offered on the earlier codes`);
      // the exports: both kinds disabled, the note by the update's state; earlier downloads linked and labelled
      const options = app.exportOptions(doc);
      assert.equal(count(options, ' disabled>'), 4, at);
      const note = (check ? app.TEXTS.UPDATE_EXPORT_NOTE_CHECK : app.TEXTS.UPDATE_EXPORT_NOTE)[running ? 'updating' : 'other'];
      assert.ok(options.includes(`<p>${esc(note)}</p>`), at);
      assert.equal(app.exportStatusText(doc), note, at);
      for (const report of doc.reports) {
        assert.ok(options.includes(`<a href="${report.download_url}" download>${esc(report.filename)}</a>`), at);
        assert.ok(options.includes(esc(app.TEXTS.EARLIER_DOWNLOAD.replace('{n}', '1'))), at);
      }
      // a check update names no change of the member's anywhere the page chooses the words
      if (check) for (const item of pageTexts(doc, drawn)) assert.doesNotMatch(item, /your change|your latest change|Changes saved/i, `${at}: ${item}`);
      // case C and the check: no restore offered in any text
      if (kind !== 'details') assert.doesNotMatch(drawn, /restore/i, at);
      // nothing names a provider, a model or the machinery
      assert.deepEqual(leaks(html, doc), [], at);
      assert.deepEqual(leaks(options, doc), [], at);
    }
  }
});

test('U21: earlier codes that listed none - the results and the tally say none was suggested before the change', () => {
  for (const kind of ['details', 'check']) {
    for (const state of ['updating', 'failed']) {
      const doc = updateDoc(state, kind, { earlier: false });
      const check = kind === 'check';
      const results = app.emptyResults(doc, ui(doc));
      assert.ok(results.endsWith(check ? app.TEXTS.RESULTS_NO_EARLIER_CODE_CHECK : app.TEXTS.RESULTS_NO_EARLIER_CODE), results);
      assert.ok(!results.includes(check ? app.TEXTS.RESULTS_EARLIER_SHOWN_CHECK : app.TEXTS.RESULTS_EARLIER_SHOWN), results);
      assert.equal(app.tallyText(doc), check ? app.TEXTS.TALLY_NO_EARLIER_CODE_CHECK : app.TEXTS.TALLY_NO_EARLIER_CODE);
      assert.ok(app.earlierCodesSection(doc, ui(doc)).includes(esc(check ? app.TEXTS.RESULTS_NO_EARLIER_CODE_CHECK : app.TEXTS.RESULTS_NO_EARLIER_CODE)));
    }
  }
});

test('U21: the fixed line in place of an empty saved-changes list, in the form of the update\'s state', () => {
  for (const reason of ['unfinished', 'same_details', 'check']) {
    for (const state of app.UPDATE_STATES) {
      const form = state === 'updating' ? 'updating' : 'other';
      const doc = updateDoc(state, reason === 'check' ? 'check' : 'details', { changes: [SAVED_LINES[reason][form]], restorable: false });
      const panel = app.progressPanel(doc, ui(doc));
      assert.ok(panel.includes(`<ul class="update-changes"><li>${esc(SAVED_LINES[reason][form])}</li></ul>`), `${reason}/${state}`);
      if (state !== 'updating') assert.doesNotMatch(panel, /being (?:finished|made|read|updated)/, `${reason}/${state}: the "other" forms never say it is being done`);
    }
  }
});

test('U21: the details panel while an update is pending - context rows editable, answers wait, Withdraw hidden, saved values shown', () => {
  const doc = updateDoc('updating');
  const base = fixture('encounter-awaiting-detail.json');
  doc.details_needed = clone(base.details_needed);
  doc.earlier_answers = [{ answer_id: UUID, fact: 'units', family_label: 'Colonoscopy', prompt: 'How many units were performed?', affects: ['45378'], value: 'not_documented',
    label: 'Not documented', by: 'Synthetic Reviewer', at: '2026-11-12T09:00:00Z', why: 'no_longer_asked', why_text: 'This question is no longer asked, so this answer is not applied.' }];
  const choice = doc.details_needed.find(row => row.control === 'choice' && !row.saved);
  choice.entered_value = choice.choices[1].value;
  const confirm = doc.details_needed.find(row => row.control === 'confirm' && !row.saved);
  const saved = doc.details_needed.find(row => row.saved && row.saved.answer_id);
  const panel = app.detailsPanel(doc, ui(doc));
  assert.ok(panel.includes(`name="detail-${choice.id}"`), 'a choice row stays editable');
  assert.ok(panel.includes(`<p class="detail-saved-value">Saved: <strong>${esc(choice.choices[1].label)}</strong></p>`), 'the saved value is shown');
  const confirmHtml = app.detailRow(confirm, doc, ui(doc));
  assert.ok(confirmHtml.includes(`<p class="detail-wait">${esc(app.TEXTS.ANSWER_AFTER_UPDATE)}</p>`), confirmHtml);
  assert.doesNotMatch(confirmHtml, /data-detail-choice|data-action="addendum"/);
  if (saved) assert.doesNotMatch(app.detailRow(saved, doc, ui(doc)), /revoke-detail/, 'a saved answer is not withdrawn while an update is pending');
  assert.doesNotMatch(panel, /revoke-detail/, 'Withdraw hidden on earlier answers too');
  assert.equal(count(panel, 'data-action="save-details"'), 1, 'the one save, for the context rows');
  assert.doesNotMatch(panel, /stay reviewable/, 'no code is reviewable during an update');
  // the save sends context values only: an answer chosen before the update began is never sent while it is pending
  const kept = app.state.answers;
  app.state.answers = new Map([[choice.id, { fact: choice.fact, value: choice.choices[0].value }], [confirm.id, { fact: confirm.fact, value: 'not_documented' }]]);
  try {
    assert.deepEqual(app.detailAnswers(doc), [{ id: choice.id, fact: choice.fact, value: choice.choices[0].value }]);
  } finally {
    app.state.answers = kept;
  }
});

test('"What changed" stands above the codes once they are updated, in the server\'s order; "Earlier decisions" lists why', () => {
  const doc = clone(fixture('encounter-ready.json'));
  doc.update = null;
  doc.earlier_codes = [];
  doc.what_changed = { compared_with: { made_at: '2026-11-12T09:30:00Z', revision: 1 },
    details: ['Place of service: not documented → Hospital outpatient department'],
    codes: [{ code: '45380', change: 'added', text: '45380 is now suggested (Ready for review)' }, { code: '45385', change: 'removed', text: '45385 is no longer suggested' }],
    unchanged: 2, decisions: [{ code: '45378', action: 'Approval', outcome: 'kept_then_changed', text: 'Approval of 45378 was kept by the update, then changed by a reviewer.' }],
    answers: pyText('WHAT_CHANGED_ANSWERS') };
  doc.decision_history = [{ code: '45385', action: 'Approval', by: 'Synthetic Reviewer', by_kind: 'human', at: '2026-11-12T09:40:00Z', revision: 1,
    why: pyText('CLEARED_DETAILS_CHANGED') }, { code: '45378', action: 'Rejection', by: 'Review agent', by_kind: 'agent', at: '2026-11-12T09:41:00Z', revision: 1,
    why: pyText('CLEARED_NEW_READING') }];
  const html = render(doc, { open: new Set(['earlier-decisions']) });
  const section = app.whatChangedSection(doc);
  const ordered = ['Place of service: not documented → Hospital outpatient department', '45380 is now suggested (Ready for review)', '45385 is no longer suggested', '2 codes unchanged',
    'Approval of 45378 was kept by the update, then changed by a reviewer.', doc.what_changed.answers];
  let cursor = 0;
  for (const line of ordered) {
    const at = section.indexOf(esc(line), cursor);
    assert.ok(at >= cursor, line);
    cursor = at;
  }
  assert.ok(section.includes(esc(app.TEXTS.WHAT_CHANGED_COMPARED.replace('{time}', app.formatTimestamp('2026-11-12T09:30:00Z')))));
  assert.ok(html.indexOf('class="what-changed"') < html.indexOf('class="result-list"'), 'above the codes');
  doc.what_changed.unchanged = 1;
  assert.ok(app.whatChangedSection(doc).includes(`<li>${app.TEXTS.WHAT_CHANGED_UNCHANGED_ONE}</li>`));
  const decisions = app.earlierDecisions(doc, ui(doc, { open: new Set(['earlier-decisions']) }));
  assert.match(decisions, /<summary>Earlier decisions<\/summary>/);
  assert.ok(decisions.includes(`<strong>Approval of 45385</strong><small>Synthetic Reviewer · ${app.formatTimestamp('2026-11-12T09:40:00Z')} · revision 1</small><p>${esc(doc.decision_history[0].why)}</p>`), decisions);
  assert.ok(decisions.includes('Review agent (automated agent)'));
  // while an update is pending what changed is not drawn (the server serves none then)
  const pending = updateDoc('updating');
  pending.what_changed = doc.what_changed;
  assert.equal(app.whatChangedSection(pending), '');
  assert.deepEqual(leaks(html, doc), []);
});

test('earlier downloads: linked and labelled as earlier; a current one as before', () => {
  const report = { id: UUID, kind: 'approved', fmt: 'txt', filename: 'CPT-Studio-approved-r1-20261112T093000.txt', generated_at: '2026-11-12T09:30:00Z',
    generated_by: 'Synthetic Reviewer', download_url: `/api/reports/${UUID}/download`, current: false, revision: 1 };
  const earlier = app.reportItem(report);
  assert.ok(earlier.startsWith('<li class="report-item earlier"><a href="'), earlier);
  assert.ok(earlier.includes(esc('Earlier — made on revision 1; it may not show the current codes')));
  const current = app.reportItem({ ...report, current: true });
  assert.ok(current.startsWith(`<li class="report-item"><a href="/api/reports/${UUID}/download" download>`));
  assert.doesNotMatch(current, /Earlier/);
  // an export the server served with no revision (an older server) keeps the earlier page's unlinked line
  assert.match(app.reportItem({ ...report, revision: undefined }), /class="report-item stale"/);
});

test('"Try updating again" asks the server once, with the page\'s headers; a refusal says why in the server\'s words', async () => {
  const doc = updateDoc('failed');
  assert.equal(doc.progress.error.action, 'retry_update');
  const panel = app.progressPanel(doc, ui(doc));
  assert.ok(panel.includes(`<p>${esc(doc.progress.error.text)}</p><button type="button" class="button secondary" data-action="retry-update">Try updating again</button>`), panel);
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.progressPanel(viewer, ui(viewer)), /retry-update/);
  const saved = { document: global.document, fetch: global.fetch };
  const toastEl = { textContent: '', classList: { add() {}, remove() {} } };
  const element = selector => (selector === '#toast' ? toastEl : { textContent: '', hidden: false });
  const button = { dataset: { action: 'retry-update' }, disabled: false, toggleAttribute() {} };
  const asked = [];
  let answer = { status: 201, body: { retrying: true } };
  try {
    global.document = { querySelector: element, querySelectorAll: () => [], cookie: 'cptstudio_csrf=token123' };
    global.fetch = async (url, init) => {
      asked.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : null, client: init.headers[app.CLIENT_HEADER] });
      const reply = url === '/api/session' ? { status: 200, body: fixture('session.json') } : answer;
      return { status: reply.status, ok: reply.status < 300, redirected: false, url: `http://127.0.0.1${url}`, headers: { get: () => 'application/json' }, json: async () => reply.body };
    };
    app.state.doc = doc;
    app.state.route = null;
    await app.onClick({ target: { closest: selector => (selector === '[data-action]' ? button : null) } });
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(asked.filter(item => item.method === 'POST'), [{ url: `/api/encounters/${doc.id}/retry-update`, method: 'POST', body: {}, client: app.CLIENT_VERSION }]);
    assert.equal(toastEl.textContent, app.RETRY_UPDATE_ASKED);
    asked.length = 0;
    answer = { status: 409, body: { error: pyText('RETRY_UPDATE_NOTHING') } };
    await app.retryUpdate(button);
    assert.equal(toastEl.textContent, answer.body.error);
    assert.equal(button.disabled, false);
  } finally {
    global.document = saved.document;
    global.fetch = saved.fetch;
    app.state.doc = null;
    clearTimeout(app.state.toastTimer);
  }
});

// --- a small live DOM over ops/verification/fake_dom.cjs (the walk's own parser), for the page's event handlers ---------
const { fakeDocument, Node: FakeNode } = require('../../ops/verification/fake_dom.cjs');

class LiveNode extends FakeNode {
  get dataset() {
    const out = {};
    for (const [name, value] of Object.entries(this.attrs)) {
      if (name.startsWith('data-')) out[name.slice(5).replace(/-([a-z])/g, (match, letter) => letter.toUpperCase())] = value;
    }
    return out;
  }

  setAttribute(name, value) { this.attrs[name] = String(value); }

  removeAttribute(name) { delete this.attrs[name]; }

  toggleAttribute(name, on) {
    if (on) this.attrs[name] = '';
    else delete this.attrs[name];
    return Boolean(on);
  }

  get value() { return super.value; }

  set value(next) { this.attrs.value = String(next); }

  get checked() { return super.checked; }

  set checked(on) { this.toggleAttribute('checked', on); }

  get disabled() { return super.disabled; }

  set disabled(on) { this.toggleAttribute('disabled', on); }

  get hidden() { return this.hasAttribute('hidden'); }

  set hidden(on) { this.toggleAttribute('hidden', on); }

  get textContent() { return super.textContent; }

  set textContent(next) { this.childNodes = [{ text: String(next) }]; }

  get classList() {
    const node = this;
    const names = () => (node.attrs.class || '').split(/\s+/).filter(Boolean);
    return {
      add: name => { node.attrs.class = [...new Set([...names(), name])].join(' '); },
      remove: name => { node.attrs.class = names().filter(item => item !== name).join(' '); },
      contains: name => names().includes(name),
    };
  }

  focus() {}
}

function liveDocument(html) {
  const doc = fakeDocument(html);
  const live = node => {
    if (!(node instanceof FakeNode)) return;
    Object.setPrototypeOf(node, LiveNode.prototype);
    node.childNodes.forEach(live);
  };
  live(doc.root);
  doc.cookie = 'cptstudio_csrf=token123';
  return doc;
}

// The page drawn for ``doc`` in a live DOM, with the page's globals wired to it and a fetch that records every request.
async function onLivePage(doc, drive) {
  const saved = { document: global.document, fetch: global.fetch };
  const requests = [];
  try {
    // the shell's session fields too: the session read a save starts (afterChange) draws into them while the page is live
    const shell = ['workspaceName', 'workspaceSubtitle', 'workspaceAvatar', 'profileAvatar', 'topAvatar', 'profileName',
      'profileRole', 'documentsCount', 'queueCount'].map(id => `<span id="${id}"></span>`).join('');
    global.document = liveDocument(`<header>${shell}</header><main id="main">${render(doc)}</main><div id="toast" class="toast"></div>`);
    global.fetch = async (url, init) => {
      requests.push({ url, method: init.method || 'GET', body: init.body ? JSON.parse(init.body) : null });
      const body = url === '/api/session' ? fixture('session.json') : url.endsWith('/details') ? { saved: 2, unchanged: 0, answer_ids: [], reassessing: true, restored: false } : doc;
      return { status: url.endsWith('/details') ? 201 : 200, ok: true, redirected: false, url: `http://127.0.0.1${url}`, headers: { get: () => 'application/json' }, json: async () => body };
    };
    app.state.doc = doc;
    app.state.route = null;  // the refresh after a save is the route's; nothing is redrawn here
    app.state.answers = new Map();
    await drive(global.document, requests);
  } finally {
    global.document = saved.document;
    global.fetch = saved.fetch;
    app.state.doc = null;
    app.state.answers = new Map();
    clearTimeout(app.state.toastTimer);
  }
}

// A document with a date row and a choice row (the setting), as the details panel draws them.
function typingDoc(update) {
  const doc = update ? updateDoc('updating') : clone(fixture('encounter-awaiting-detail.json'));
  const base = fixture('encounter-awaiting-detail.json');
  const choice = clone(base.details_needed.find(row => row.control === 'choice' && row.fact === 'setting' && !row.saved));
  const date = clone(fixture('encounter-action-needed.json').details_needed.find(row => row.control === 'date'));
  date.choices = [];
  doc.details_needed = [date, choice];
  doc.earlier_answers = [];
  return { doc, date, choice };
}

test('U2: typing a date and choosing a setting sends nothing; the one Save sends exactly one POST /details', async () => {
  for (const update of [false, true]) {
    const { doc, date, choice } = typingDoc(update);
    await onLivePage(doc, async (page, requests) => {
      const input = page.querySelector(`input[data-detail-input][data-detail="${date.id}"]`);
      assert.ok(input, 'the date field is drawn');
      for (const typed of ['2', '2026-1', '2026-11-1', '2026-11-10']) {  // keystroke by keystroke, as the browser fires input
        input.value = typed;
        app.onInput({ target: input });
      }
      app.onChange({ target: input });
      const radio = page.querySelector(`input[type="radio"][data-detail="${choice.id}"][value="hospital_outpatient"]`);
      assert.ok(radio, 'the setting radio is drawn');
      radio.checked = true;
      app.onChange({ target: radio });
      await new Promise(resolve => setImmediate(resolve));
      assert.deepEqual(requests, [], `update ${update}: no request while typing and choosing`);
      assert.deepEqual([...app.state.answers.keys()].sort(), [date.id, choice.id].sort());
      const save = page.querySelector('[data-action="save-details"]');
      assert.ok(save, 'the one save is drawn');
      await app.onClick({ target: save });
      await new Promise(resolve => setImmediate(resolve));
      const posts = requests.filter(item => item.method === 'POST');
      assert.deepEqual(posts, [{ url: `/api/encounters/${doc.id}/details`, method: 'POST',
        body: { answers: [{ id: date.id, fact: 'service_date', value: '2026-11-10' }, { id: choice.id, fact: 'setting', value: 'hospital_outpatient' }] } }], `update ${update}`);
      assert.ok(requests.every(item => item.method === 'POST' || item.url === '/api/session'), 'nothing else but the session read after the save');
    });
  }
});

test('a save that restored the earlier codes says so; one that queued an update says the results are being updated', async () => {
  const { doc, choice } = typingDoc(false);
  for (const [reply, message] of [[{ saved: 1, unchanged: 0, answer_ids: [], reassessing: false, restored: true }, app.TEXTS.RESTORED_TOAST],
    [{ saved: 1, unchanged: 0, answer_ids: [], reassessing: true, restored: false }, 'Answer saved. The results are being updated.'],
    [{ saved: 1, unchanged: 0, answer_ids: [], reassessing: false, restored: false }, 'Answer saved.']]) {
    await onLivePage(doc, async page => {
      const realFetch = global.fetch;
      global.fetch = async (url, init) => (url.endsWith('/details')
        ? { status: 201, ok: true, redirected: false, url: `http://127.0.0.1${url}`, headers: { get: () => 'application/json' }, json: async () => reply }
        : realFetch(url, init));
      app.state.answers.set(choice.id, { fact: choice.fact, value: 'office' });
      await app.saveDetails(page.querySelector('[data-action="save-details"]'));
      await new Promise(resolve => setImmediate(resolve));  // the session read the save starts ends on this page
      assert.equal(page.querySelector('#toast').textContent, message);
    });
  }
});

test('the live page in every update state and kind: what a member can read and press, through the walk\'s own DOM', async () => {
  for (const kind of ['details', 'documentation', 'check']) {
    for (const state of app.UPDATE_STATES) {
      const doc = updateDoc(state, kind);
      doc.details_needed = clone(fixture('encounter-awaiting-detail.json').details_needed);
      const at = `${kind}/${state}`;
      await onLivePage(doc, async (page, requests) => {
        const title = page.querySelector('#progressTitle').textContent;
        assert.equal(title === app.TEXTS.UPDATE_TITLE || title === app.TEXTS.UPDATE_TITLE_CHECK, state === 'updating', `${at}: ${title}`);
        if (kind === 'check') assert.notEqual(title, app.TEXTS.UPDATE_TITLE, at);
        assert.deepEqual(page.querySelectorAll('[data-decision]'), [], `${at}: no decision button anywhere`);
        assert.equal(page.querySelectorAll('ol.earlier-list > li.earlier-row').length, doc.earlier_codes.length, at);
        assert.deepEqual(page.querySelectorAll('.result-row'), [], `${at}: no current code row`);
        assert.deepEqual(page.querySelectorAll('ol.result-list'), [], `${at}: no current code list`);
        assert.equal(page.querySelector('#earlierTitle').textContent, kind === 'check' ? app.TEXTS.EARLIER_CODES_HEADING_CHECK : app.TEXTS.EARLIER_CODES_HEADING, at);
        assert.ok(page.querySelector('[data-action="save-details"]'), `${at}: the context rows keep the one save`);
        assert.deepEqual(page.querySelectorAll('[data-detail-choice]'), [], `${at}: no answer button while the update is pending`);
        assert.deepEqual(page.querySelectorAll('[data-action="revoke-detail"]'), [], `${at}: no withdrawal while the update is pending`);
        const retry = page.querySelector('[data-action="retry-update"]');
        assert.equal(Boolean(retry), doc.progress.error?.action === 'retry_update', at);
        const stop = page.querySelector('[data-action="stop"]');
        assert.equal(Boolean(stop), state === 'updating', `${at}: Stop only while it runs`);
        const text = page.querySelector('main').textContent;
        assert.equal(/being updated/.test(text), state === 'updating', at);
        assert.doesNotMatch(text, /No codes yet|No CPT codes were suggested|no codes have been suggested/, at);
        if (kind !== 'details') assert.doesNotMatch(text, /restore/i, at);
        assert.deepEqual(requests, [], `${at}: drawing the page sends nothing`);
      });
    }
  }
});

// --- step 5d, round 2 (refute-5d-r1 P1, P5, P6) -----------------------------------------------------------------------

// P1: the walk (ops/verify_browser.cjs) reads ol.result-list > li.result-row as the codes the API serves (CORE-UX-DESIGN
// 8). While an update is pending the API serves no code: the earlier codes are drawn under hooks of their own, so the
// walk's own reader finds no current row in any update state and kind, and its result-list check passes on a correct page.
test('the walk\'s own DOM reader never reads the earlier codes as the current codes, in any update state or kind', () => {
  const vb = require('../../ops/verify_browser.cjs');
  for (const kind of ['details', 'documentation', 'check']) {
    for (const state of app.UPDATE_STATES) {
      const doc = updateDoc(state, kind);
      const at = `${kind}/${state}`;
      const page = fakeDocument(`<main>${render(doc)}</main>`);
      const dom = vb.readCustomerDom(page);
      assert.equal(dom.list, false, `${at}: no ol.result-list while the API serves no code`);
      assert.deepEqual(dom.rows, [], at);
      assert.deepEqual(vb.checkResultList(doc, dom).map(item => [item.id, item.status]), [['dom.result_list', 'pass']], at);
      const rows = page.querySelectorAll('section.earlier-codes > ol.earlier-list > li.earlier-row');
      assert.equal(rows.length, doc.earlier_codes.length, at);
      assert.deepEqual(rows.map(row => row.getAttribute('data-code')), doc.earlier_codes.map(code => code.code), at);
      assert.ok(rows.every(row => row.getAttribute('data-proposal') === null), `${at}: an earlier row names no proposal to decide`);
      assert.deepEqual(page.querySelectorAll('li.result-row, ol.result-list, [data-proposal]'), [], at);
    }
  }
  // the control: once the codes are fresh the walk reads the current list as before
  const fresh = fixture('encounter-ready.json');
  const dom = vb.readCustomerDom(fakeDocument(`<main>${render(fresh)}</main>`));
  assert.equal(dom.rows.length, fresh.codes.length);
  assert.ok(vb.checkResultList(fresh, dom).every(item => item.status === 'pass'));
});

// P5: a choice row saved "Not documented" while an update is pending: "Change this answer" is hidden (1.4), but the row
// still takes one of its values - a context save the server accepts during an update (A1, 5.1(3); A19 names it), which
// replaces the answer and records none (answers._save_details) - so the page draws the values and the one save. While
// processing runs outside an update the row keeps only its saved line, as before (the stage is most often that
// answer's own recompute, during which a context save is refused: A18).
function savedChoiceRow() {
  const row = clone(fixture('encounter-awaiting-detail.json').details_needed.find(item => item.control === 'choice' && item.fact === 'setting'));
  row.saved = { value: 'not_documented', label: 'Not documented', by: 'Synthetic Reviewer', at: '2026-11-12T09:00:00Z', answer_id: UUID };
  return row;
}

test('a choice row saved "Not documented" takes one of its values while an update is pending, and its answer is not withdrawn then', async () => {
  const row = savedChoiceRow();
  const radios = html => count(html, `name="detail-${row.id}"`);
  // answers open (nothing runs, no update): the saved answer with "Change this answer", as before
  const open = clone(fixture('encounter-awaiting-detail.json'));
  open.details_needed = [clone(row)];
  const openHtml = app.detailsPanel(open, ui(open));
  assert.equal(radios(openHtml), 0);
  assert.match(openHtml, /data-action="revoke-detail"/);
  assert.equal(app.valueOverAnswer(row, open), false);
  assert.equal(app.rowEditable(row, open), false);
  // processing outside an update: the saved line only, as before - no withdrawal, no value, no save
  const busy = clone(fixture('encounter-awaiting-detail.json'));
  busy.progress = { ...busy.progress, phase: 'processing', busy: true, can_stop: true };
  busy.details_needed = [clone(row)];
  const busyHtml = app.detailsPanel(busy, ui(busy));
  assert.equal(radios(busyHtml), 0);
  assert.doesNotMatch(busyHtml, /data-action="revoke-detail"|data-action="save-details"/);
  assert.ok(busyHtml.includes('Saved: <strong>Not documented</strong>'));
  assert.equal(app.valueOverAnswer(row, busy), false);
  assert.equal(app.rowEditable(row, busy), false);
  // an update pending, in each state: the values, no withdrawal, the one save
  const waiting = app.UPDATE_STATES.map(state => [`update ${state}`, updateDoc(state)]);
  for (const [at, doc] of waiting) {
    doc.details_needed = [clone(row)];
    const html = app.detailsPanel(doc, ui(doc));
    assert.equal(radios(html), row.choices.length, at);
    assert.doesNotMatch(html, /data-action="revoke-detail"/, `${at}: the answer is not withdrawn while an update is pending`);
    assert.doesNotMatch(html, /data-detail-choice=/, `${at}: no answer button while an update is pending`);
    assert.ok(html.includes('Saved: <strong>Not documented</strong>'), `${at}: the saved answer stays shown`);
    assert.equal(count(html, 'data-action="save-details"'), 1, at);
    assert.ok(html.includes(`<fieldset class="detail-row is-saved" data-detail="${row.id}"`), `${at}: a radio group named by its legend`);
    assert.equal(app.valueOverAnswer(row, doc), true, at);
    assert.equal(app.rowEditable(row, doc), true, at);
  }
  // a viewer is offered nothing
  const viewer = updateDoc('failed');
  viewer.permissions.can_review = false;
  viewer.details_needed = [clone(row)];
  assert.equal(radios(app.detailsPanel(viewer, ui(viewer))), 0);
  assert.equal(app.rowEditable(row, viewer), false);
  // the live page: choosing a value and pressing Save sends that value, and nothing is sent before Save
  const doc = updateDoc('failed');
  doc.details_needed = [clone(row)];
  await onLivePage(doc, async (page, requests) => {
    const radio = page.querySelector(`input[type="radio"][data-detail="${row.id}"][value="office"]`);
    assert.ok(radio, 'the value is offered');
    radio.checked = true;
    app.onChange({ target: radio });
    assert.deepEqual(requests, []);
    await app.onClick({ target: page.querySelector('[data-action="save-details"]') });
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(requests.filter(item => item.method === 'POST'), [{ url: `/api/encounters/${doc.id}/details`, method: 'POST',
      body: { answers: [{ id: row.id, fact: 'setting', value: 'office' }] } }]);
  });
});

// P6: a poll that brings nothing new but the server's clock never redraws the page (a date being typed in a native date
// field holds no value until it is whole, so a redraw empties it); a poll that brings a change redraws as before.
test('a read that brings only the server\'s clock does not redraw the page; a read that brings a change does', async () => {
  const doc = updateDoc('updating');
  doc.details_needed = clone(fixture('encounter-awaiting-detail.json').details_needed);
  const later = clone(doc);
  later.progress.server_time = '2026-11-13T10:03:02Z';
  const moved = clone(later);
  moved.progress.steps = moved.progress.steps.map(step => (step.key === 'checking' ? { ...step, state: 'done' } : step));
  assert.equal(app.renderKey(later), app.renderKey(doc));
  assert.notEqual(app.renderKey(moved), app.renderKey(doc));
  assert.notEqual(app.renderKey({ ...later, update: { ...later.update, state: 'failed' } }), app.renderKey(doc));
  assert.equal(app.renderKey({ id: 'no-progress' }), JSON.stringify({ id: 'no-progress' }));
  const saved = { window: global.window };
  try {
    await onLivePage(doc, async page => {
      global.window = { scrollY: 0, scrollTo() {} };
      const main = page.querySelector('#main');
      let draws = 0;
      Object.defineProperty(main, 'innerHTML', { configurable: true, set() { draws += 1; }, get() { return ''; } });
      app.renderDocument(doc, true);  // the route's first draw
      assert.equal(draws, 1);
      app.renderDocument(later, false);  // a poll: only the server's clock moved
      assert.equal(draws, 1, 'the page under the member is not redrawn');
      assert.equal(app.state.doc, later, 'the newest read is kept');
      app.renderDocument(moved, false);  // a poll that brings a change
      assert.equal(draws, 2);
    });
  } finally {
    global.window = saved.window;
    app.state.docKey = '';
  }
});

// Found in round 2's own review: "You can change an answer below" is said only where an answer can be changed now - while
// an update is pending a saved answer is not withdrawn (1.4), so with every row answered and none taking a value the lead
// says only that every detail has an answer (D225: every customer sentence true for its state).
test('with every detail answered, the panel says an answer can be changed only where one can be changed now', () => {
  const answered = doc => {
    for (const row of doc.details_needed) row.saved = { value: 'not_documented', label: 'Not documented', by: 'Synthetic Reviewer', at: '2026-11-12T09:00:00Z', answer_id: UUID };
    return doc;
  };
  const confirmOnly = doc => { doc.details_needed = clone(fixture('encounter-awaiting-detail.json').details_needed).filter(row => row.control === 'confirm'); return answered(doc); };
  const open = confirmOnly(clone(fixture('encounter-awaiting-detail.json')));
  assert.match(app.detailsPanel(open, ui(open)), /Every detail has an answer\. You can change an answer below\./);
  for (const state of app.UPDATE_STATES) {
    const pending = confirmOnly(updateDoc(state));
    const html = app.detailsPanel(pending, ui(pending));
    assert.ok(html.includes('<p>Every detail has an answer.</p>'), state);
    assert.doesNotMatch(html, /You can change an answer below|revoke-detail|save-details/, state);
  }
  // a choice row saved "Not documented" still takes a value while the update is pending: the sentence holds
  const withChoice = answered(updateDoc('failed'));
  withChoice.details_needed = [savedChoiceRow(), ...confirmOnly(updateDoc('failed')).details_needed];
  assert.match(app.detailsPanel(withChoice, ui(withChoice)), /Every detail has an answer\. You can change an answer below\./);
});
