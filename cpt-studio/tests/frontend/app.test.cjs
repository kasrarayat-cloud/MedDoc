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
const NAMES = /\b(?:corti|astra|fable|openai|anthropic|claude)\b|\bgpt-|\bclaude-/i;
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
  top: ['id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'service_date', 'progress', 'checks', 'codes',
    'other_codes', 'not_separately_coded', 'details_needed', 'unresolved', 'limitations', 'readiness', 'reports', 'activity'],
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
  detail: ['id', 'fact', 'family_label', 'prompt', 'control', 'choices', 'allow', 'document_value', 'entered_value', 'quote', 'affects', 'saved', 'addendum_allowed'],
  saved: ['value', 'label', 'by', 'at', 'answer_id'],
  readiness: ['draft', 'approved', 'blockers'],
  report: ['id', 'kind', 'fmt', 'filename', 'generated_at', 'generated_by', 'download_url', 'current'],
  activity: ['event', 'summary', 'actor', 'actor_kind', 'at'],
  session: ['user', 'workspace', 'role', 'can_review', 'acknowledgement', 'counts', 'synthetic_only'],
  row: ['id', 'title', 'state', 'state_label', 'service_date', 'date_conflict', 'open_details', 'created_at', 'kind'],
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
    }
    assert.deepEqual(sorted(Object.keys(doc.readiness)), sorted(CONTRACT.readiness), at('readiness'));
    for (const report of doc.reports) assert.deepEqual(sorted(Object.keys(report)), sorted(CONTRACT.report), at('report'));
    for (const item of doc.activity) assert.deepEqual(sorted(Object.keys(item)), sorted(CONTRACT.activity), at('activity'));
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
    assert.deepEqual(app.documentLayout(doc).unlocated, new Set(), name);
  }
  assert.ok(quotes >= 15, quotes);
});

// --- status ----------------------------------------------------------------------------------------------------------

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
  const html = render(fixture('encounter-awaiting-detail.json'));
  assert.match(html, /<span class="status amber" data-status="needs_detail">.*?Needs a detail<\/span>/);
  assert.match(html, /<span class="status green" data-status="ready">Ready for review<\/span>/);
});

test('an agent approval labels the row and the approved download as agent-executed synthetic review', () => {
  const doc = fixture('encounter-reviewed.json');
  const html = render(doc);
  for (const code of doc.codes.filter(item => item.status === 'approved')) {
    const row = html.slice(html.indexOf(`id="card-${code.id}"`), html.indexOf('</li>', html.indexOf(`id="card-${code.id}"`)));
    assert.match(row, /<p class="result-sub">Agent-executed synthetic review — not clinical approval<\/p>/, code.code);
    assert.match(row, /Approved by CPT Studio review agent \(automated agent\)/, code.code);
    assert.equal(count(row, 'gent-executed synthetic review — not clinical approval'), 1, `${code.code}: said once per row`);
  }
  // the label holds even when the server's line under the code is empty
  const bare = clone(doc);
  bare.codes[0].sub_label = '';
  assert.equal(app.rowSubLabel(bare.codes[0]), app.AGENT_REVIEW);
  assert.match(render(bare), /<p class="result-sub">Agent-executed synthetic review — not clinical approval<\/p>/);
  // the agent-confirmed exclusion says it on its decision line, its own line under the code being the server's
  const excluded = doc.codes.find(item => item.status === 'excluded');
  assert.match(app.decisionLine(excluded), /agent-executed synthetic review — not clinical approval/);
  // the approved download's wording in the export dialog
  assert.match(app.exportStatusText(doc), /Includes agent-executed synthetic review — not clinical approval\.$/);
  const human = clone(doc);
  for (const code of human.codes) code.decision = { ...code.decision, by: 'Synthetic Reviewer', by_kind: 'human' };
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
  assert.match(line, /Approved by Synthetic Reviewer/);
  assert.match(line, /synthetic review — not clinical approval/);
  assert.doesNotMatch(line, /agent/);
  assert.match(line, /Note: Read it\./);
});

// --- the codes-first list ----------------------------------------------------------------------------------------------

test('the result list is numbered in the served order, one row per code, with the hooks the walk reads', () => {
  const doc = fixture('encounter-mara.json');
  const html = render(doc);
  assert.equal(count(html, '<ol class="result-list" aria-label="Suggested CPT codes">'), 1);
  const rows = [...html.matchAll(/<li class="result-row" id="card-([^"]+)" tabindex="-1" data-proposal="([^"]+)" data-code="([^"]+)" data-status="([^"]+)" data-units="(\d*)" data-modifiers="([^"]*)">/g)];
  assert.deepEqual(rows.map(match => [match[1] === match[2], match[3], match[4]]), [[true, '43239', 'ready'], [true, '45380', 'ready'], [true, '45385', 'ready']]);
  assert.deepEqual([...html.matchAll(/<span class="result-number">(\d+)<\/span><span class="result-code">(\d{5})<\/span>/g)].map(match => [match[1], match[2]]), [['1', '43239'], ['2', '45380'], ['3', '45385']]);
  for (const hook of ['result-units', 'result-modifiers', 'result-sub', 'result-summary']) assert.equal(count(html, `class="${hook}"`), 3, hook);
  // the order is the server's, never sorted here
  const reversed = clone(doc);
  reversed.codes.reverse();
  assert.deepEqual([...render(reversed).matchAll(/data-code="(\d{5})"/g)].map(match => match[1]), ['45385', '45380', '43239']);
  // a missing number falls back to the position
  const numberless = clone(doc);
  for (const code of numberless.codes) code.number = null;
  assert.deepEqual([...render(numberless).matchAll(/<span class="result-number">(\d+)<\/span>/g)].map(match => match[1]), ['1', '2', '3']);
});

test('only the served allowed actions are drawn, each with its proposal id', () => {
  const doc = fixture('encounter-ready.json');
  const html = render(doc);
  // in the page's own fixed order (approve, reject, reinstate, confirm, undo), whatever order the server lists them in
  const order = ['approve', 'reject', 'reinstate', 'confirm', 'revoke'];
  for (const code of doc.codes) {
    const drawn = [...html.matchAll(new RegExp(`data-decision="(\\w+)" data-proposal="${code.id}"`, 'g'))].map(match => match[1]);
    assert.deepEqual(drawn, order.filter(action => code.allowed_actions.includes(action)), code.code);
  }
  const none = clone(doc);
  for (const code of none.codes) code.allowed_actions = [];
  assert.equal(count(render(none), 'data-decision='), 0);
  const odd = clone(doc);
  odd.codes[0].allowed_actions = ['approve', 'delete', '__proto__'];
  assert.deepEqual([...render(odd).matchAll(/data-decision="(\w+)"/g)].map(match => match[1]), ['approve', 'reinstate', 'confirm']);
  assert.equal(count(render(fixture('encounter-reviewed.json')), 'data-decision="revoke"'), 3);
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
  const html = render(doc);
  assert.match(html, /data-code="45380" data-status="approved" data-units="1" data-modifiers="XS">/);
  assert.match(html, /<span class="result-code">45380<\/span><span class="result-units">1 unit<\/span><span class="result-modifiers">Modifier XS<\/span>/);
  const units = clone(doc);
  units.codes[0].units = 2;
  assert.match(render(units), /<span class="result-units">2 units<\/span>/);
});

test('other codes sit behind a closed disclosure; "Not separately coded" and the limitations are listed', () => {
  const doc = fixture('encounter-mara.json');
  const html = render(doc);
  assert.match(html, /<details class="other-codes" data-key="other-codes"><summary>Other codes considered \(not suggested\)<\/summary>/);
  assert.match(html, /<span class="other-code">99204<\/span><span>No separate office evaluation and management visit is documented on this date\.<\/span>/);
  assert.equal(count(html, 'data-code="99204"'), 0, 'an alternative is never a result row');
  assert.match(render(doc, { open: new Set(['other-codes']) }), /<details class="other-codes" data-key="other-codes" open>/);
  assert.match(html, /<h3>Not separately coded<\/h3><ul><li><strong>Clip placement at the COL-2 resection site<\/strong><span>A clip placed to prevent bleeding/);
  assert.match(html, /<h3>Limitations<\/h3><ul class="limitation-list"><li>CPT descriptors are not shown: no licensed CPT content is connected\.<\/li>/);
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
  const doc = fixture('encounter-mara.json');
  const layout = app.documentLayout(doc);
  const code = doc.codes[1];
  const why = app.whyThisCode(code, layout, ui(doc));
  assert.match(why, new RegExp(`^<details class="why-code" data-key="why:${code.id}"><summary>Why this code\\?</summary>`));
  const quotes = [...why.matchAll(/<button type="button" class="why-quote" data-evidence="([^"]+)" data-start="(\d+)" data-end="(\d+)" data-page="(\d+)" title="Show this passage in the document">([^<]*)<\/button>/g)];
  assert.equal(quotes.length, code.why.quotes.length);
  const points = [...doc.document.text];
  quotes.forEach((match, index) => {
    assert.equal(match[1], `${code.id}:q${index}`);
    const [start, end, page] = [Number(match[2]), Number(match[3]), Number(match[4])];
    assert.equal(app.escapeHtml(points.slice(start, end).join('')), match[5], 'the button text is the exact slice');
    assert.equal(page, code.why.quotes[index].page);
  });
  assert.match(why, /<li class="why-qualification">COL-1 and COL-2 are documented as different lesions at separate colonic sites\.<\/li>/);
  assert.match(app.whyThisCode(code, layout, ui(doc, { open: new Set([`why:${code.id}`]) })), /<details class="why-code" data-key="why:[^"]+" open>/);
  // every row has one, and none is open unless the member opened it
  assert.equal(count(render(doc), '<details class="why-code"'), 3);
  assert.equal(count(render(doc), '<details class="why-code" data-key="why:c1a00000-0000-4000-8000-000000000011" open>'), 0);
  const quiet = clone(code);
  quiet.why = { quotes: [], qualifications: [] };
  assert.match(app.whyThisCode(quiet, layout, ui(doc)), /No passage of the document is quoted for this code\./);
});

test('a quote that is not at its offsets is shown as not found and never highlighted', () => {
  const doc = clone(fixture('encounter-ready.json'));
  doc.codes[0].why.quotes[0].start += 1;
  doc.codes[0].why.quotes[1].exact = false;
  const layout = app.documentLayout(doc);
  assert.deepEqual([...layout.unlocated], [`${doc.codes[0].id}:q0`, `${doc.codes[0].id}:q1`]);
  const why = app.whyThisCode(doc.codes[0], layout, ui(doc));
  assert.equal(count(why, '<span class="why-quote unlocated"'), 2);
  assert.equal(count(why, 'Not found at this place in the document.'), 2);
  assert.equal(count(why, `data-evidence="${doc.codes[0].id}:q`), 0);
  assert.equal(count(app.sourcePanel(doc, layout), `${doc.codes[0].id}:q`), 0);
});

test('the modifier review states its dated source and that nothing is added automatically', () => {
  const doc = fixture('encounter-mara.json');
  const why = app.whyThisCode(doc.codes[2], app.documentLayout(doc), ui(doc));
  assert.match(why, /<div class="why-modifier"><strong>Modifier review<\/strong><p>COL-1 \(ascending colon\) and COL-2 \(sigmoid colon\)/);
  assert.match(why, /<p class="why-sources">Source: CMS claims manual Pub\. 100-04 ch\. 12 \(Rev\. 13753, 2026-05-07\)<\/p>/);
  assert.match(why, /No modifier is added automatically; the reviewer may choose one when approving\./);
  assert.doesNotMatch(app.whyThisCode(doc.codes[0], app.documentLayout(doc), ui(doc)), /why-modifier/);
});

test('source marks title the codes they are cited for and the document date', () => {
  const doc = fixture('encounter-mara.json');
  const html = app.sourcePanel(doc, app.documentLayout(doc));
  assert.match(html, /<button type="button" class="evidence-mark" data-evidence="date:document" data-keys="date:document" title="Date of service in the document">Date of service 2026-11-03<\/button>/);
  assert.match(html, /title="Cited for 43239">Biopsies/);
  assert.match(html, /title="Cited for 45385">COL-2 - sigmoid colon/);
  assert.match(html, /<a href="\/api\/encounters\/c1000000-0000-4000-8000-000000000010\/original" download>/);
  const pasted = fixture('encounter-stopped.json');
  assert.doesNotMatch(app.sourcePanel(pasted, app.documentLayout(pasted)), /Download original/);
});

// --- "A few details needed" -------------------------------------------------------------------------------------------

test('the details panel: one row per detail with its family, prompt and the codes it affects; one save for all rows', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  assert.match(html, /^<section class="details-panel" aria-labelledby="detailsTitle">.*<h2 id="detailsTitle">A few details needed<\/h2>/);
  assert.deepEqual([...html.matchAll(/class="detail-row[^"]*" data-detail="([^"]+)" data-fact="([^"]+)"/g)].map(match => match[2]), ['patient_status', 'extent', 'setting']);
  assert.match(html, /<p class="detail-affects">Affects 45385<\/p>/);
  assert.equal(count(html, 'data-action="save-details"'), 1);
  assert.match(html, /2 details are needed\. Answer what you can; codes that do not depend on them stay reviewable\./);
  assert.equal(app.detailsPanel({ ...doc, details_needed: [] }, ui(doc)), '');
  // a supported, independent code stays reviewable while others wait
  const page = render(doc);
  assert.match(page, /data-code="43239" data-status="ready"/);
  assert.match(page, /data-decision="approve" data-proposal="c1a00000-0000-4000-8000-000000000001"/);
  assert.doesNotMatch(page, /data-decision="approve" data-proposal="c1a00000-0000-4000-8000-000000000002"/);
});

test('a date conflict shows the document date and the entered date side by side, with "Use document date"; the input is never prefilled', () => {
  const doc = fixture('encounter-action-needed.json');
  const html = app.detailsPanel(doc, ui(doc));
  const row = doc.details_needed[0];
  assert.match(html, /<div class="detail-document-date"><span class="detail-date-label">Document<\/span><strong>28 October 2026<\/strong><q class="detail-quote">Date of service: 2026-10-28<\/q><\/div>/);
  assert.match(html, /<div class="detail-entered-date"><span class="detail-date-label">You entered<\/span><strong>21 October 2026<\/strong><\/div>/);
  assert.match(html, new RegExp(`<button type="button" class="button secondary detail-choice" id="detail-${row.id}-use_document" data-action="use-document-date" data-detail="${row.id}" aria-pressed="false">Use document date</button>`));
  assert.match(html, new RegExp(`<input type="date" id="detail-${row.id}-date" data-detail-input data-detail="${row.id}">`), 'no value attribute');
  assert.match(html, /Choose the date of service\. Nothing is checked until you do\./);
  // the member's own pending entry is kept across a refresh, never a date from the server
  const typed = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: '2026-10-27' }]]) }));
  assert.match(typed, /data-detail-input data-detail="[^"]+" value="2026-10-27">/);
  const chosen = app.detailsPanel(doc, ui(doc, { answers: new Map([[row.id, { fact: 'service_date', value: 'use_document' }]]) }));
  assert.match(chosen, /data-action="use-document-date" data-detail="[^"]+" aria-pressed="true">/);
  assert.doesNotMatch(chosen, /value="2026-10-2[18]"/);
  // the page says Action needed at once, and nothing is checked
  const page = render(doc);
  assert.match(page, /<section class="progress-panel" data-phase="action_needed"/);
  assert.match(page, /<h2 id="progressTitle">Action needed<\/h2>/);
  assert.doesNotMatch(page, /progress-card|is-animated|data-state="active"/);
  assert.match(page, /Nothing has been checked yet\. Choose the date of service to continue\./);
});

test('"Use document date" is offered only when the document states a date', () => {
  const doc = clone(fixture('encounter-action-needed.json'));
  doc.details_needed[0].document_value = null;
  doc.details_needed[0].quote = null;
  const html = app.detailsPanel(doc, ui(doc));
  assert.doesNotMatch(html, /use-document-date/);
  assert.match(html, /<strong>Not stated<\/strong>/);
  assert.match(html, /data-detail-input/);
});

test('choices are radios named per detail; "Not documented" and "Cannot confirm" only where allowed; a confirm row asks for no clinical fact', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  const [status, extent] = doc.details_needed;
  assert.equal(count(html, `<input type="radio" name="detail-${status.id}"`), 2);
  assert.match(html, new RegExp(`<fieldset class="detail-row" data-detail="${status.id}" data-fact="patient_status"><span class="detail-family">Office visit</span><legend class="detail-prompt">`));
  assert.match(html, new RegExp(`id="detail-${status.id}-not_documented" data-detail-choice="not_documented" data-detail="${status.id}" aria-pressed="false">Not documented</button>`));
  assert.doesNotMatch(html, new RegExp(`detail-${status.id}-cannot_confirm`));
  const extentRow = html.slice(html.indexOf(`data-detail="${extent.id}" data-fact="extent"`), html.indexOf('</div>', html.indexOf(`data-detail="${extent.id}" data-fact="extent"`) + 400));
  assert.match(extentRow, /data-detail-choice="not_documented"/);
  assert.match(extentRow, /data-detail-choice="cannot_confirm"/);
  assert.doesNotMatch(extentRow, /type="radio"|type="date"|<textarea|type="text"/);
  assert.match(html, new RegExp(`<button type="button" class="button subtle detail-addendum" data-action="addendum" data-detail="${extent.id}">Add to the documentation \\(physician\\)</button>`));
  assert.equal(count(html, 'data-action="addendum"'), 1, 'only where the server allows the physician path');
  const pending = app.detailsPanel(doc, ui(doc, { answers: new Map([[status.id, { fact: 'patient_status', value: 'established' }], [extent.id, { fact: 'extent', value: 'cannot_confirm' }]]) }));
  assert.match(pending, /value="established" data-detail="[^"]+" checked>/);
  assert.match(pending, new RegExp(`id="detail-${extent.id}-cannot_confirm" data-detail-choice="cannot_confirm" data-detail="${extent.id}" aria-pressed="true">`));
});

test('a saved answer is shown with who and when, and can be changed; only open rows count', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const html = app.detailsPanel(doc, ui(doc));
  const saved = doc.details_needed[2];
  assert.match(html, /<p class="detail-saved"><svg[^>]*><use href="#i-check"\/><\/svg><span>Saved: <strong>Office<\/strong> — Synthetic Reviewer, 30 Oct 2026, 15:12 UTC<\/span>/);
  assert.match(html, new RegExp(`data-action="revoke-detail" data-answer="${saved.saved.answer_id}"`));
  assert.doesNotMatch(html, new RegExp(`name="detail-${saved.id}"`), 'a saved row is not asked again');
  const all = clone(doc);
  for (const row of all.details_needed) row.saved = { value: 'not_documented', label: '', by: 'Synthetic Reviewer', at: '2026-10-30T15:20:00Z', answer_id: saved.saved.answer_id };
  const done = app.detailsPanel(all, ui(all));
  assert.match(done, /Every detail has an answer\. You can change an answer below\./);
  assert.equal(count(done, 'save-details'), 0);
  assert.equal(count(done, 'Saved: <strong>Not documented</strong>'), 3);
  assert.equal(app.listBody('documents', [{ ...fixture('encounters.json').encounters[0], open_details: 2 }]).includes('2 details needed'), true);
});

test('pending answers survive a refresh; a viewer, or a busy document, gets no controls', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const answers = new Map([[doc.details_needed[0].id, { fact: 'patient_status', value: 'new' }]]);
  assert.match(render(doc, { answers }), /value="new" data-detail="[^"]+" checked>/);
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  const seen = app.detailsPanel(viewer, ui(viewer));
  assert.doesNotMatch(seen, /type="radio"|data-detail-choice|save-details|revoke-detail|data-action="addendum"/);
  assert.match(seen, /Answers can be saved once processing has finished\./);
  const busy = clone(doc);
  busy.progress.busy = true;
  assert.doesNotMatch(app.detailsPanel(busy, ui(busy)), /type="radio"|save-details/);
});

// --- progress ----------------------------------------------------------------------------------------------------------

test('the progress panel folds to four plain stages with their states, the active check named under the active stage', () => {
  const doc = fixture('encounter-processing.json');
  const html = app.progressPanel(doc, ui(doc));
  assert.match(html, /^<section class="progress-panel progress-card" data-phase="processing" aria-labelledby="progressTitle">/);
  const steps = [...html.matchAll(/<li class="progress-step( is-animated)?" data-step="(\w+)" data-state="(\w+)">.*?<strong>([^<]+)<\/strong><small>([^<]+)<\/small>/g)];
  assert.deepEqual(steps.map(match => [match[2], match[3], match[4], match[5], Boolean(match[1])]), [
    ['reading', 'done', 'Reading your document', 'Done', false],
    ['identifying', 'done', 'Identifying procedures', 'Done', false],
    ['checking', 'active', 'Checking suggested codes', 'In progress · Independent checks', true],
    ['preparing', 'not_started', 'Preparing your results', 'Not started', false],
  ]);
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
  assert.deepEqual([...app.checksPanel(doc).matchAll(/<li class="check-step" data-check="(\w+)" data-state="(\w+)">.*?<strong>([^<]+)<\/strong><small>([^<]+)<\/small>/g)].map(match => match.slice(1)),
    [['document_review', 'done', 'Document review', 'Done'], ['independent_checks', 'running', 'Independent checks', 'In progress'], ['coding_validation', 'waiting', 'Coding validation', 'Waiting']]);
});

test('while busy the panel shows elapsed time that ticks; a finished one states the total; never a percentage or a forecast', () => {
  const doc = fixture('encounter-processing.json');
  const now = Date.parse(doc.progress.server_time);
  const html = app.progressPanel(doc, ui(doc, { nowMs: now }));
  assert.match(html, /<p class="progress-time">Elapsed <span data-elapsed data-since="2026-11-02T14:00:04Z">1 min 06 s<\/span><\/p>/);
  // the server's clock, not the browser's: a browser five minutes behind still says 1 min 06 s
  assert.match(app.progressPanel(doc, ui(doc, { nowMs: now - 300000, clock: 300000 })), />1 min 06 s</);
  const finished = fixture('encounter-ready.json');
  const done = app.progressPanel(finished, ui(finished));
  assert.match(done, /^<section class="progress-panel progress-done" data-phase="completed"/);
  assert.match(done, /<strong>Results ready<\/strong> · finished in <span data-elapsed data-since="2026-10-29T09:30:04Z" data-until="2026-10-29T09:32:52Z">2 min 48 s<\/span>/);
  assert.match(app.progressPanel(fixture('encounter-failed.json'), ui(fixture('encounter-failed.json'))), /Ran for <span data-elapsed[^>]*data-until=[^>]*>36 s<\/span>/);
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

test('failed: the plain error and its action; stopped: Resume; being confirmed: no Stop and the settling message', () => {
  const failed = app.progressPanel(fixture('encounter-failed.json'), ui(fixture('encounter-failed.json')));
  assert.match(failed, /<section class="progress-panel" data-phase="failed"/);
  assert.match(failed, /<h2 id="progressTitle">Processing could not finish<\/h2>/);
  assert.match(failed, /<div class="progress-error" role="alert">.*<p>No text could be read from this file\. Upload a copy with a text layer, or paste the text\.<\/p><button type="button" class="button secondary" data-action="upload">Upload a new document<\/button>/);
  assert.match(failed, /data-step="reading" data-state="failed"/);
  const resumable = clone(fixture('encounter-failed.json'));
  resumable.progress.error.action = 'resume';
  assert.match(app.progressPanel(resumable, ui(resumable)), /data-action="resume">Resume processing<\/button>/);
  resumable.progress.error.action = 'none';
  assert.doesNotMatch(app.progressPanel(resumable, ui(resumable)), /progress-error[^]*data-action/);
  const stopped = app.progressPanel(fixture('encounter-stopped.json'), ui(fixture('encounter-stopped.json')));
  assert.match(stopped, /<section class="progress-panel" data-phase="stopped"/);
  assert.match(stopped, /data-step="checking" data-state="stopped"/);
  assert.match(stopped, /<button type="button" class="button primary" data-action="resume">Resume processing/);
  assert.doesNotMatch(stopped, /data-action="stop"/);
  const viewer = clone(fixture('encounter-stopped.json'));
  viewer.permissions.can_review = false;
  assert.doesNotMatch(app.progressPanel(viewer, ui(viewer)), /data-action="resume"/);
  const confirming = app.progressPanel(fixture('encounter-being-confirmed.json'), ui(fixture('encounter-being-confirmed.json')));
  assert.match(confirming, /We are confirming whether an earlier check completed\. Nothing will be sent again until that is settled\./);
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
  const polls = Object.fromEntries(ENCOUNTERS.map(name => [name, app.shouldPoll(fixture(name))]));
  assert.deepEqual(Object.keys(polls).filter(name => polls[name]).sort(), ['encounter-being-confirmed.json', 'encounter-processing.json', 'encounter-queued.json']);
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
  const at = Date.parse('2026-11-02T14:20:00Z');
  const ack = { id: 'c1000000-0000-4000-8000-000000000011', at };
  const placeholder = app.ackView(ack);
  assert.match(placeholder, /<div class="upload-ack" role="status">.*<strong>Uploaded\. Reading your document…<\/strong><p>Received 2 Nov 2026, 14:20 UTC\. You can leave this page; the document stays in Documents\.<\/p>/);
  const queued = fixture('encounter-queued.json');
  const panel = app.progressPanel(queued, ui(queued, { ack }));
  assert.match(panel, /data-phase="queued"/);
  assert.match(panel, /<div class="upload-ack" role="status">/);
  assert.match(panel, /data-step="reading" data-state="waiting"/);
  assert.doesNotMatch(app.progressPanel(queued, ui(queued, { ack: { ...ack, id: 'another' } })), /upload-ack/);
  // once the document has been read, the stages say what is happening; the acknowledgement no longer says reading
  const checking = { ...fixture('encounter-processing.json'), id: ack.id };
  assert.match(app.progressPanel(checking, ui(checking, { ack })), /<div class="upload-ack" role="status">.*<strong>Uploaded\.<\/strong><p>Received 2 Nov 2026, 14:20 UTC\.<\/p>/);
  assert.doesNotMatch(app.progressPanel(fixture('encounter-ready.json'), ui(fixture('encounter-ready.json'), { ack: { ...ack, id: fixture('encounter-ready.json').id } })), /upload-ack/);
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
  const html = app.exportOptions(ready);
  assert.match(html, /<div class="evidence-label">Suggested codes — not approved<\/div><button type="button" class="export-option" data-export-kind="draft" data-export-fmt="txt">/);
  assert.match(html, /data-export-kind="draft" data-export-fmt="csv">/);
  assert.match(html, /data-export-kind="approved" data-export-fmt="txt" disabled>/);
  assert.match(html, /data-export-kind="approved" data-export-fmt="csv" disabled>/);
  assert.match(html, /<div class="export-blockers"><p>Not available yet:<\/p><ul><li>43239, 45380 and 45385 are waiting for a review decision\.<\/li><\/ul><\/div>/);
  const reviewed = app.exportOptions(fixture('encounter-reviewed.json'));
  assert.match(reviewed, /data-export-kind="approved" data-export-fmt="txt">/);
  assert.doesNotMatch(reviewed, /export-blockers/);
  const nothing = app.exportOptions(fixture('encounter-processing.json'));
  assert.equal(count(nothing, ' disabled>'), 4);
  assert.match(render(ready), /<button type="button" class="button secondary" data-action="export">.*Review and download<\/button>/);
  assert.match(render(ready), /<div class="heading-actions">.*data-action="export"/);
  assert.doesNotMatch(render(fixture('encounter-processing.json')), /data-action="export"/);
});

test('earlier downloads link only while they match the saved decisions', () => {
  const html = app.exportOptions(fixture('encounter-reviewed.json'));
  assert.match(html, /<li class="report-item"><a href="\/api\/reports\/c1e00000-0000-4000-8000-000000000001\/download" download>cpt-studio-approved-colonoscopy-two-lesions\.txt<\/a><small>Approved codes · 27 Oct 2026, 08:31 UTC · CPT Studio review agent \(automated agent\)<\/small><\/li>/);
  assert.match(html, /<li class="report-item stale"><span>cpt-studio-draft-colonoscopy-two-lesions\.csv<\/span><small>Suggested codes \(draft\) · .* · No longer matches the saved decisions; create a new download\.<\/small><\/li>/);
  assert.equal(count(html, '/api/reports/c1e00000-0000-4000-8000-000000000002/download'), 0);
  const bad = clone(fixture('encounter-reviewed.json'));
  bad.reports[0].download_url = 'javascript:alert(1)';
  assert.doesNotMatch(app.exportOptions(bad), /javascript:|href="javascript/);
});

test('the export status never claims an approval the server did not report', () => {
  const doc = fixture('encounter-ready.json');
  assert.match(app.exportStatusText(doc), /^Draft only: the codes are suggestions, not approvals\. Before the approved download: 45385 is waiting/);
  assert.equal(app.exportStatusText({ readiness: { draft: false, approved: false, blockers: [] } }), 'Nothing can be downloaded yet.');
  assert.equal(app.exportStatusText({ readiness: { draft: true, approved: 'yes', blockers: [] } }), 'Draft only: the codes are suggestions, not approvals.');
  assert.match(app.exportStatusText({ readiness: { approved: true, blockers: [] }, codes: [] }), /^Every suggested code has a decision\. The approved download lists only approved codes\.$/);
  assert.equal(app.tallyText(fixture('encounter-awaiting-detail.json')), '1 ready for review · 2 need a detail');
  assert.equal(app.tallyText(fixture('encounter-reviewed.json')), '2 approved · 1 excluded');
  assert.equal(app.tallyText(fixture('encounter-processing.json')), 'No codes yet');
});

test('the review dialog offers none, 59 or XS only for a code with a modifier review, never prefilled', () => {
  const mara = fixture('encounter-mara.json');
  assert.deepEqual(app.reviewModifierOptions(mara.codes[1]), [['', 'No modifier'], ['59', '59'], ['XS', 'XS']]);
  assert.deepEqual(app.reviewModifierOptions(mara.codes[0]), []);
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
  const words = /corti|astra|fable|openai|anthropic|claude|gpt|participant|peer|provider|vendor|model|trace|usage|credit|token|sha256|sha-256|harness|pipeline|engine|orchestrat|diagnostic|operator|replay|request[\s_-]?id|requestid|rule[\s_-]?id|ruleid|response[\s_-]?id|tool[\s_-]?call|cms-|ncci\.|pfs\.|mue\./gi;
  const hits = [...scanned.matchAll(words)].map(match => `${match[0]} @${scanned.slice(0, match.index).split('\n').length}`);
  assert.deepEqual(hits, []);
  assert.equal(count(source, 'X-CSRFToken'), 1);
  // and the same scan finds a planted word, so a clean result means something
  assert.ok([...`${scanned}\n// Astra`.matchAll(words)].length === 1);
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
  own.document.text = own.document.text.replace('Lena Ortiz', 'Claude Ortiz');
  assert.deepEqual(leaks(app.sourcePanel(own, app.documentLayout(own)), own), []);
});

test('the stylesheet and the templates carry no internal-machinery words either', () => {
  const words = /corti|astra|fable|openai|anthropic|claude|participant|peer|provider|vendor|model|trace|usage|credit|token|sha256|harness/gi;
  const css = fs.readFileSync(path.join(ROOT, 'studio', 'static', 'studio', 'styles.css'), 'utf8');
  assert.deepEqual([...css.matchAll(words)].map(match => match[0]), []);
  for (const name of ['index.html', 'login.html']) {
    const html = fs.readFileSync(path.join(ROOT, 'studio', 'templates', 'studio', name), 'utf8').replace(/\{%\s*csrf_token\s*%\}/g, '');
    assert.deepEqual([...html.matchAll(words)].map(match => match[0]), [], name);
  }
});

// --- lists ---------------------------------------------------------------------------------------------------------------

test('list rows show the plain state, the kind, the details needed and the date; the queue lists what waits on the member', () => {
  const rows = fixture('encounters.json').encounters;
  const action = rows.find(row => row.state === 'action_needed');
  const html = app.documentRow(action);
  assert.match(html, /<a class="document-row" href="#doc\/c1000000-0000-4000-8000-000000000002">/);
  assert.match(html, /<small>Uploaded file · 1 detail needed<\/small>/);
  assert.match(html, /<span class="status amber">Action needed<\/span>/);
  assert.match(html, /<span class="doc-row-date">Date to choose<\/span>/);
  assert.match(app.documentRow({ ...action, state: 'mystery', state_label: '', date_conflict: false, service_date: '2026-10-28' }), /<span class="status gray">Unknown<\/span>.*28 Oct 2026/);
  const queued = rows.filter(app.inQueue).map(row => row.state);
  assert.deepEqual([...new Set(queued)].sort(), ['action_needed', 'awaiting_detail', 'ready']);
  assert.equal(count(app.listBody('queue', rows), 'class="document-row"'), queued.length);
  assert.equal(count(app.listBody('workspace', rows), 'class="document-row"'), 5);
  assert.match(app.listBody('queue', []), /Nothing is waiting for you\./);
  assert.equal(app.listDescription('documents', rows), `${rows.length} synthetic documents in this workspace.`);
  assert.equal(fixture('session.json').counts.queue, queued.length);
});
