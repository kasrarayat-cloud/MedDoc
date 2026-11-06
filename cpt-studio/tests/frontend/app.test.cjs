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
  // completion repair (2026-11-06, U11): 'earlier_answers', the answers no question asked now takes
  top: ['id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document', 'service_date', 'progress', 'checks', 'codes',
    'other_codes', 'not_separately_coded', 'details_needed', 'earlier_answers', 'unresolved', 'recheck', 'limitations', 'readiness', 'reports', 'activity'],
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
  report: ['id', 'kind', 'fmt', 'filename', 'generated_at', 'generated_by', 'download_url', 'current'],
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
    why_text: 'This answer was saved before each question showed the passages it concerns, so it is not applied; answer the question as it is asked now.' }];
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

test('pending answers survive a refresh; a viewer, or a busy document, gets no controls', () => {
  const doc = fixture('encounter-awaiting-detail.json');
  const choice = doc.details_needed.find(row => row.control === 'choice' && !row.saved);
  const answers = new Map([[choice.id, { fact: choice.fact, value: choice.choices[0].value }]]);
  assert.ok(render(doc, { answers }).includes(`value="${esc(choice.choices[0].value)}" data-detail="${choice.id}" checked>`));
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  const seen = app.detailsPanel(viewer, ui(viewer));
  assert.doesNotMatch(seen, /type="radio"|data-detail-choice|save-details|revoke-detail|data-action="addendum"/);
  assert.match(seen, /Answers can be saved once processing has finished\./);
  const busy = clone(doc);
  busy.progress.busy = true;
  assert.doesNotMatch(app.detailsPanel(busy, ui(busy)), /type="radio"|save-details/);
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
  // a viewer, or a busy document, reads the saved date only
  const viewer = clone(doc);
  viewer.permissions.can_review = false;
  const seen = app.detailsPanel(viewer, ui(viewer));
  assert.match(seen, /Saved: <strong>2 October 2026<\/strong>/);
  assert.doesNotMatch(seen, /data-detail-input|clear-date|save-details/);
  const busy = clone(doc);
  busy.progress.busy = true;
  assert.doesNotMatch(app.detailsPanel(busy, ui(busy)), /data-detail-input|save-details/);
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

test('earlier downloads link only while they match the saved decisions', () => {
  const doc = fixture('encounter-reviewed.json');
  const current = doc.reports.filter(report => report.current === true);
  const stale = doc.reports.filter(report => report.current !== true);
  assert.ok(current.length && stale.length, 'the scenario: a current and a stale download');
  const html = app.exportOptions(doc);
  for (const report of current) assert.ok(html.includes(`<li class="report-item"><a href="${esc(report.download_url)}" download>${esc(report.filename)}</a><small>`), report.filename);
  for (const report of stale) {
    assert.ok(html.includes(`<li class="report-item stale"><span>${esc(report.filename)}</span><small>`), report.filename);
    assert.ok(html.includes('No longer matches the saved decisions; create a new download.'));
    assert.equal(count(html, report.download_url), 0, report.filename);
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
  const terms = /corti|astra|fable|openai|anthropic|claude|gpt|participant|peer|provider|vendor|model|trace|usage|credit|token|sha256|sha-256|harness|pipeline|engine|orchestrat|diagnostic|operator|replay|request[\s_-]?id|requestid|rule[\s_-]?id|ruleid|response[\s_-]?id|tool[\s_-]?call|cms-|ncci\.|pfs\.|mue\./gi;
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
