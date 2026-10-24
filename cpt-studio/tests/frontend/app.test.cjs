'use strict';
// Unit tests for the pure parts of studio/static/studio/app.js. Run: node --test tests/frontend/
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const app = require('../../studio/static/studio/app.js');

const FIXTURES = path.join(__dirname, '..', 'fixtures', 'api');
const fixture = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const UUID = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
const count = (haystack, needle) => haystack.split(needle).length - 1;

function cpSpan(text, needle, key, extra = {}) {
  const unit = text.indexOf(needle);
  assert.ok(unit >= 0, needle);
  const start = [...text.slice(0, unit)].length;
  return { key, start, end: start + [...needle].length, text: needle, exact: true, ...extra };
}

function render(doc, tab = 'codes') {
  return app.reviewView(doc, app.documentLayout(doc), tab, true);
}

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

test('safeDownloadUrl accepts only same-origin report download paths', () => {
  assert.equal(app.safeDownloadUrl(`/api/reports/${UUID}/download`), `/api/reports/${UUID}/download`);
  for (const bad of ['javascript:alert(1)', `//evil.example/api/reports/${UUID}/download`, `https://evil.example/api/reports/${UUID}/download`,
    `/api/reports/${UUID}/download?x=1`, '/api/reports/../session', `/api/reports/${UUID}/download/`, null, 42]) {
    assert.equal(app.safeDownloadUrl(bad), '', String(bad));
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
  const text = '\nFirst line\nsecond line\n\n  \n\nSecond paragraph\n\n\n';
  const ranges = app.paragraphRanges(text, 0, text.length);
  assert.deepEqual(ranges.map(([a, b]) => text.slice(a, b)), ['First line\nsecond line', 'Second paragraph']);
  assert.deepEqual(app.paragraphRanges('   \n\n  ', 0, 7), []);
});

test('layout marks exact spans by code point, across astral characters', () => {
  const text = '🩺 Header 𝒳\n\nThe colonoscope 🔬 was advanced to the cecum.';
  const span = cpSpan(text, 'was advanced to the cecum', 'p:0');
  const layout = app.layoutDocument(text, [{ page: 1, start: 0, end: [...text].length }], [span]);
  assert.deepEqual(layout.unlocated, []);
  const marks = layout.pages.flatMap(page => page.paragraphs.flat()).filter(piece => piece.keys);
  assert.deepEqual(marks.map(piece => [piece.text, piece.keys]), [['was advanced to the cecum', ['p:0']]]);
});

test('layout reports wrong, out-of-range, inexact and malformed spans as unlocated and never marks them', () => {
  const text = 'Alpha beta gamma.';
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
  const layout = app.layoutDocument(text, [], spans);
  assert.deepEqual(layout.unlocated, ['wrong', 'range', 'flagged', 'empty', 'float', 'negative', 'notext']);
  const marked = layout.pages[0].paragraphs.flat().filter(piece => piece.keys);
  assert.deepEqual(marked.map(piece => piece.text), ['beta']);
});

test('a span crossing paragraph and page boundaries is split per paragraph without the separators', () => {
  const pageOne = 'Page one ends here.\n\nNext paragraph starts';
  const pageTwo = 'page two continues.';
  const text = `${pageOne}\n\n${pageTwo}`;
  const pages = [{ page: 1, start: 0, end: pageOne.length }, { page: 2, start: pageOne.length + 2, end: text.length }];
  const crossParagraph = cpSpan(text, 'ends here.\n\nNext', 'x:0');
  const crossPage = cpSpan(text, 'starts\n\npage two', 'x:1');
  const layout = app.layoutDocument(text, pages, [crossParagraph, crossPage]);
  assert.equal(layout.pages.length, 2);
  const pieces = layout.pages.map(page => page.paragraphs.map(paragraph => paragraph.filter(piece => piece.keys).map(piece => piece.text)));
  assert.deepEqual(pieces, [[['ends here.'], ['Next', 'starts']], [['page two']]]);
  for (const page of layout.pages) for (const paragraph of page.paragraphs) {
    for (const piece of paragraph) assert.ok(!piece.text.includes('\n\n'));
  }
});

test('invalid page spans fall back to one page that keeps all of the text', () => {
  const text = 'One.\n\nTwo.\n\nThree.';
  for (const pages of [[{ page: 1, start: 5, end: 2 }], [{ page: 1, start: 0, end: 99 }], [{ page: 1, start: 0, end: 8 }, { page: 2, start: 4, end: 10 }], [{ page: '1', start: 0, end: 4 }], 'nope']) {
    const layout = app.layoutDocument(text, pages, []);
    assert.equal(layout.pages.length, 1, JSON.stringify(pages));
    assert.deepEqual(layout.pages[0].paragraphs.map(paragraph => paragraph.map(piece => piece.text).join('')), ['One.', 'Two.', 'Three.']);
  }
});

test('layout never inserts or loses visible text (seeded property check)', () => {
  let seed = 7;
  const random = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const alphabet = ['a', 'b', ' ', '\n', '\n\n', '🩺', 'é', '𝒳', '.', '\t', '<', '&'];
  for (let round = 0; round < 300; round += 1) {
    const text = Array.from({ length: 5 + Math.floor(random() * 60) }, () => alphabet[Math.floor(random() * alphabet.length)]).join('');
    const points = [...text];
    const spans = Array.from({ length: Math.floor(random() * 5) }, (_, i) => {
      const start = Math.floor(random() * points.length);
      const end = Math.min(points.length, start + 1 + Math.floor(random() * 12));
      return { key: `k:${i}`, start, end, text: points.slice(start, end).join(''), exact: true };
    });
    const cut = Math.floor(random() * points.length);
    const pages = [{ page: 1, start: 0, end: cut }, { page: 2, start: cut, end: points.length }];
    const layout = app.layoutDocument(text, pages, spans);
    const rendered = layout.pages.flatMap(page => page.paragraphs.map(paragraph => paragraph.map(piece => piece.text).join(''))).join('');
    assert.equal(rendered.replace(/\s/g, ''), text.replace(/\s/g, ''), JSON.stringify(text));
    assert.deepEqual(layout.unlocated, []);
    const offsets = app.codeUnitOffsets(text);
    const unit = point => (offsets ? offsets[point] : point);
    const covered = new Uint8Array(text.length);
    for (const span of spans) covered.fill(1, unit(span.start), unit(span.end));
    const ranges = app.pageRanges(pages, points.length, unit, text.length);
    layout.pages.forEach((page, index) => {
      const paragraphs = app.paragraphRanges(text, ranges[index].start, ranges[index].end);
      assert.equal(page.paragraphs.length, paragraphs.length);
      page.paragraphs.forEach((pieces, i) => {
        const [from, to] = paragraphs[i];
        assert.equal(pieces.map(piece => piece.text).join(''), text.slice(from, to));
        let cursor = from;
        for (const piece of pieces) {
          const marked = covered.subarray(cursor, cursor + piece.text.length);
          assert.ok(piece.keys ? marked.every(Boolean) : !marked.some(Boolean), JSON.stringify({ text, piece, cursor }));
          cursor += piece.text.length;
        }
      });
    });
  }
});

test('fact values never invent a value for missing or conflicting facts', () => {
  assert.equal(app.factValue(null), 'Not documented');
  assert.equal(app.factValue({ value: null, origin: 'missing' }), 'Not documented');
  assert.equal(app.factValue({ value: 'not_documented', origin: 'missing' }, { professional: 'Professional' }), 'Not documented');
  assert.equal(app.factValue({ value: 'facility', origin: 'conflict' }, { facility: 'Facility' }), 'Conflicting values documented');
  assert.equal(app.factValue({ value: 'asc', origin: 'document' }, { asc: 'Ambulatory surgery center' }), 'Ambulatory surgery center');
  assert.equal(app.factValue({ value: 'office', origin: 'user' }, { office: 'Office' }), 'Office (entered)');
  assert.equal(app.factValue({ value: '2026-10-21', origin: 'document' }, null, true), '21 October 2026');
  assert.equal(app.metaFact({ value: null, origin: 'missing' }, null, 'Service date', true), 'Service date not documented');
  assert.equal(app.metaFact({ value: 'x', origin: 'conflict' }, {}, 'Setting'), 'Setting conflict');
});

test('the queue lists clarification, review and reconciliation states only', () => {
  assert.deepEqual([...app.QUEUE_STATES].sort(), ['needs_clarification', 'provider_unknown', 'ready_for_review']);
  const { encounters } = fixture('encounters.json');
  const body = app.listBody('queue', encounters);
  const expected = encounters.filter(item => app.QUEUE_STATES.has(item.state)).length;
  assert.equal(count(body, 'class="document-row"'), expected);
  assert.equal(count(app.listBody('documents', encounters), 'class="document-row"'), encounters.length);
  assert.equal(count(app.listBody('workspace', encounters), 'class="document-row"'), Math.min(5, encounters.length));
  assert.match(app.listBody('queue', []), /Nothing is waiting for review\./);
  assert.match(app.listDescription('queue', encounters), new RegExp(`^${expected} documents need`));
});

test('adversarial fixture: every injected string is rendered escaped, in every tab and list', () => {
  const doc = fixture('encounter-adversarial.json');
  const { encounters } = fixture('encounters.json');
  const html = [render(doc, 'codes'), render(doc, 'checks'), render(doc, 'timeline'),
    app.listBody('documents', encounters), app.inviteMarkup(encounters.filter(item => item.id === doc.id)),
    app.exportOptions(doc.readiness)].join('\n');
  for (const raw of ['<img', '<script', '<svg onload', '<b>tags', '<b>Family', 'onerror="window', 'onload="window']) {
    assert.equal(html.includes(raw), false, raw);
  }
  assert.ok(html.includes('&lt;img src=x onerror=&quot;window.__xss=1&quot;&gt;'));
  assert.ok(html.includes('&lt;script&gt;window.__xss=2&lt;/script&gt;'));
});

test('adversarial fixture: only exact spans are highlighted; the rest are flagged, not hidden', () => {
  const doc = fixture('encounter-adversarial.json');
  const html = render(doc, 'codes');
  assert.equal(count(html, 'class="evidence-chip unlocated"'), 3);
  assert.equal(count(html, 'class="evidence-chip" data-evidence='), 4);
  const layout = app.documentLayout(doc);
  const keys = layout.pages.flatMap(page => page.paragraphs.flat()).filter(piece => piece.keys).map(piece => piece.keys);
  const proposalsIn = group => new Set(group.map(key => key.split(':')[0])).size;
  assert.ok(keys.some(group => proposalsIn(group) === 2), 'overlapping spans of two proposals share one mark');
  assert.equal(layout.pages.length, 2);
});

test('ready fixture: one combined list of selected codes, separate alternatives and exclusions', () => {
  const doc = fixture('encounter-ready.json');
  const html = render(doc, 'codes');
  assert.equal(count(html, 'class="code-card"'), 3);
  for (const eyebrow of ['UPPER GI ENDOSCOPY', 'COLONOSCOPY', 'EVALUATION &amp; MANAGEMENT']) assert.ok(html.includes(eyebrow), eyebrow);
  assert.equal(count(html, 'data-decision="approve"'), 2);
  assert.equal(count(html, 'data-decision="reject"'), 3);
  assert.ok(html.includes('Alternatives (not selected)'));
  assert.ok(html.includes('Excluded candidates'));
  assert.equal(count(html, 'class="check-item muted"'), 4);
  assert.equal(count(html, '<h3>Description withheld</h3>'), 3);
  assert.ok(html.includes('data-action="addendum"'));
  assert.ok(html.includes('Not verified: CPT code-set membership for the service date; NCCI procedure-to-procedure edits.'));
  assert.ok(html.includes('Modifier considerations, never assigned automatically'));
  assert.equal(count(html, 'class="source-paper"'), 2);
  assert.ok(html.includes('Page 1 of 2'));
  assert.ok(html.includes('Download original'));
  for (const proposal of doc.assessment.proposals) assert.equal(html.includes(proposal.provider_display || '\u0000'), false);
  const checks = render(doc, 'checks');
  assert.ok(checks.includes('Applies to this service date'));
  assert.ok(checks.includes('Not verified — No licensed CPT edition is connected'));
  const timeline = render(doc, 'timeline');
  assert.ok(timeline.includes('0.0281 provider-reported credits (not USD)'));
  assert.ok(timeline.includes('No decisions recorded yet.'));
});

test('reviewed fixture: invalidated decisions are struck, agent review is labelled everywhere', () => {
  const doc = fixture('encounter-reviewed.json');
  const timeline = render(doc, 'timeline');
  assert.ok(timeline.includes('<s>Approved 45380</s>'));
  assert.ok(timeline.includes('Invalidated: Source changed: revision 2 (addendum) replaced revision 1.'));
  const codes = render(doc, 'codes');
  assert.ok(codes.includes('Approved · agent'));
  assert.ok(codes.includes('agent-executed synthetic review — not clinical approval'));
  assert.equal(count(codes, 'data-decision="revoke"'), 2);
  assert.equal(codes.includes('data-decision="approve"'), false);
  assert.match(app.exportStatusText(doc), /^Reviewed — .*agent-executed synthetic review/);
  assert.equal(count(app.exportOptions(doc.readiness), 'class="export-option"'), 4);
  assert.ok(codes.includes('Revision 2 appends an addendum'));
});

test('state fixtures: processing, provider_unknown and extraction_failed show their own next step', () => {
  const processing = fixture('encounter-processing.json');
  const busy = render(processing);
  assert.ok(busy.includes('Processing this document'));
  assert.ok(busy.includes('data-action="stop"'));
  assert.equal(busy.includes('role="tablist"'), false);
  assert.equal(busy.includes('data-action="export"'), false);
  const unknown = render(fixture('encounter-provider-unknown.json'));
  assert.ok(unknown.includes('id="reconcileForm" data-run="e0000000-0000-4000-8000-000000000004"'));
  const failed = fixture('encounter-extraction-failed.json');
  const failedHtml = render(failed);
  assert.ok(failedHtml.includes('The text could not<br>be read.'));
  assert.ok(failedHtml.includes('No text extracted'));
  assert.ok(failedHtml.includes('Pages 1–3 have no text layer'));
  assert.equal(count(app.exportOptions(failed.readiness), 'export-option'), 0);
  const viewer = { ...processing, permissions: { can_review: false } };
  assert.equal(render(viewer).includes('data-action="stop"'), false);
  const stopped = fixture('encounter-stopped.json');
  assert.ok(render(stopped).includes('data-action="resume"'));
  assert.equal(render({ ...stopped, pipeline: { ...stopped.pipeline, can_resume: false } }).includes('data-action="resume"'), false);
  assert.equal(busy.includes('data-action="edit-context"'), false, 'context is not editable while a stage runs');
  assert.ok(render(fixture('encounter-ready.json')).includes('data-action="edit-context"'));
  assert.equal(failedHtml.includes('data-action="edit-context"'), false, 'no context edits without extracted text');
});

test('clarification fixture: encounter question first, planned service excluded but reinstatable', () => {
  const doc = fixture('encounter-clarification.json');
  const html = render(doc);
  const card = html.indexOf('class="clarification-card"');
  assert.ok(card >= 0 && card < html.indexOf('class="code-card"'));
  assert.equal(count(html, 'class="clarification-card"'), 1);
  const listed = { ...doc, assessment: { ...doc.assessment, proposals: doc.assessment.proposals.map(p => ({ ...p, clarification_ids: [doc.clarifications[0].id] })) } };
  assert.equal(count(render(listed), 'class="clarification-card"'), 1, 'an encounter question stays a card even if a proposal lists it');
  assert.equal(count(render(listed), 'class="clarification-question"'), 1);
  assert.ok(html.includes('data-decision="reinstate"'));
  assert.equal(html.includes('data-decision="approve"'), false);
  assert.ok(html.includes('Services outside the GI profiles'));
  assert.ok(html.includes('Service date not documented'));
  assert.match(app.exportStatusText(doc), /^Draft — not reviewed\. Still needed: Open clarification: service date; 99213 has no decision\.$/);
});

test('export status never claims a review that the server did not report', () => {
  assert.equal(app.exportStatusText({ readiness: { draft: true, reviewed: false, blockers: [] } }), 'Draft — not reviewed.');
  assert.equal(app.exportStatusText({ readiness: { draft: false, reviewed: false, blockers: ['x'] } }), 'No report can be generated yet. Still needed: x.');
  assert.equal(app.exportStatusText({ readiness: { draft: true, reviewed: 'yes', blockers: [] } }), 'Draft — not reviewed.');
  assert.equal(app.exportOptions({ draft: true, reviewed: 'true' }).includes('data-export-kind="reviewed"'), false);
  assert.equal(app.exportStatusText({}), 'No report can be generated yet.');
});

test('a carried decision shows the reviewer time and the carry separately', () => {
  const proposal = {decision_state: 'approved', decision: {action: 'approve', reviewer: 'Reviewer One', reviewer_kind: 'human',
    created_at: '2026-10-24T03:13:07Z', decided_at: '2026-10-24T00:13:07Z', carried_at: '2026-10-24T03:13:07Z',
    carried_from: UUID, revision_number: 1}};
  const html = app.decisionLine(proposal);
  assert.ok(html.includes(app.formatTimestamp('2026-10-24T00:13:07Z')), html);
  assert.ok(html.includes(`carried to this assessment ${app.formatTimestamp('2026-10-24T03:13:07Z')}`), html);
});

test('an agent reinstatement behind a human decision labels the reviewed export as agent review', () => {
  const doc = {readiness: {reviewed: true}, assessment: {proposals: [
    {bucket: 'excluded', decision_state: 'approved', decision: {action: 'approve', reviewer_kind: 'human'},
     reinstated_by: {reviewer: 'Reviewbot (automated agent)', reviewer_kind: 'agent'}}]}};
  assert.equal(app.hasAgentDecision(doc), true);
  assert.ok(app.exportStatusText(doc).includes('agent-executed synthetic review'));
  doc.assessment.proposals[0].reinstated_by.reviewer_kind = 'human';
  assert.equal(app.hasAgentDecision(doc), false);
});
