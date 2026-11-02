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

// gi2 'present': a payload that carries no queue_reasons (served before the field existed, as the older fixtures are)
// keeps the queue of the three states that always waited on a member. The harness@2 rows are the serializer's own
// (tests/test_frontend.py) and carry queue_reasons, so they are left out here.
test('without queue_reasons the queue lists the clarification, review and reconciliation states', () => {
  assert.deepEqual([...app.QUEUE_STATES].sort(), ['needs_clarification', 'provider_unknown', 'ready_for_review']);
  const all = fixture('encounters.json').encounters;
  const encounters = all.filter(item => !('queue_reasons' in item));
  assert.deepEqual(all.filter(item => 'queue_reasons' in item).map(item => item.id.slice(0, 3)), ['e2c', 'e2b', 'e2a']);
  assert.equal(encounters.length, 10);
  const body = app.listBody('queue', encounters);
  const expected = encounters.filter(item => app.QUEUE_STATES.has(item.state)).length;
  assert.equal(count(body, 'class="document-row"'), expected);
  assert.equal(count(app.listBody('documents', encounters), 'class="document-row"'), encounters.length);
  assert.equal(count(app.listBody('workspace', encounters), 'class="document-row"'), Math.min(5, encounters.length));
  assert.match(app.listBody('queue', []), /Nothing is waiting for review\./);
  assert.match(app.listDescription('queue', encounters), new RegExp(`^${expected} documents wait on a workspace member`));
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
  assert.ok(html.includes('Alternatives (never selectable)'));
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
  // Round 3, pipeline3:3: a stage the system cancelled is not a member's Stop; its recorded cause is shown.
  assert.ok(render(stopped).includes('Queued stages were cancelled'), 'a member Stop keeps its wording');
  const cause = 'The worker stopped while this stage was running; resume to run it again.';
  const swept = { ...stopped, pipeline: { ...stopped.pipeline, stopped_by_member: false,
    stages: stopped.pipeline.stages.map(stage => (stage.kind === 'predict' ? { ...stage, error: cause } : stage)) } };
  const sweptHtml = render(swept);
  assert.ok(sweptHtml.includes('Processing did<br>not finish.'));
  assert.ok(sweptHtml.includes(`Corti: request CPT proposals: ${cause}`));
  assert.equal(sweptHtml.includes('Queued stages were cancelled'), false);
  assert.equal(sweptHtml.includes('Processing was<br>stopped.'), false);
  assert.ok(sweptHtml.includes('data-action="resume"'));
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
  // gi2 'present': the card leads with the question itself; no code card repeats it inline
  assert.equal(count(render(listed), 'class="clarification-lead"'), 1);
  assert.equal(count(render(listed), 'class="clarification-question"'), 0);
  assert.equal(count(render(listed), app.escapeHtml(doc.clarifications[0].question)), 1);
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

// --- round 4: a documentation check's exclusion is a recommendation the reviewer confirms or reverses ---

function excludedDoc(overrides) {
  const doc = fixture('encounter-ready.json');
  const base = doc.assessment.proposals[0];
  const excluded = { ...base, id: UUID, code: '45378', bucket: 'excluded', status: 'excluded', reinstatable: true,
    exclusion_reason: 'Documented as planned, not as performed on the date of service.', decision: null,
    decision_state: 'undecided', reinstated_by: null, allowed_actions: ['reinstate', 'confirm'], ...overrides };
  return { ...doc, assessment: { ...doc.assessment, proposals: [...doc.assessment.proposals, excluded] } };
}

test('an undecided documentation exclusion offers confirm and reinstate and says it needs a decision', () => {
  const html = render(excludedDoc({}));
  assert.ok(html.includes(`data-decision="confirm" data-proposal="${UUID}"`), 'confirm offered');
  assert.ok(html.includes(`data-decision="reinstate" data-proposal="${UUID}"`), 'reinstate offered');
  assert.ok(html.includes('Needs your decision: confirm the exclusion or reinstate the code.'));
});

test('a reinstated exclusion can be approved or rejected in the candidate list', () => {
  const html = render(excludedDoc({ decision_state: 'reinstated', allowed_actions: ['approve', 'reject', 'revoke'],
    decision: { action: 'reinstate', reviewer: 'Reviewer One', reviewer_kind: 'human' } }));
  for (const action of ['approve', 'reject', 'revoke']) {
    assert.ok(html.includes(`data-decision="${action}" data-proposal="${UUID}"`), action);
  }
  assert.ok(html.includes('Reinstated for review by Reviewer One; approve or reject it.'));
});

test('a confirmed exclusion names its reviewer and offers only undo', () => {
  const proposal = { bucket: 'excluded', reinstatable: true, decision_state: 'exclusion_confirmed',
    decision: { action: 'confirm', reviewer: 'Reviewer One', reviewer_kind: 'human' } };
  assert.equal(app.candidateDecision(proposal), 'Exclusion confirmed by Reviewer One.');
  const html = render(excludedDoc({ ...proposal, allowed_actions: ['revoke'] }));
  assert.ok(html.includes(`data-decision="revoke" data-proposal="${UUID}"`));
  assert.equal(html.includes(`data-decision="confirm" data-proposal="${UUID}"`), false);
  assert.equal(app.candidateDecision({ bucket: 'excluded', reinstatable: false, decision_state: 'undecided' }), '');
});

test('the results page and the acknowledgement never claim that unrecognised wording is caught', () => {
  const html = render(fixture('encounter-ready.json'));
  assert.equal(html.includes('are not coded as performed'), false);
  assert.ok(html.includes('they can miss wording they do not recognise'));
  for (const text of [app.ACKNOWLEDGEMENTS.human, app.ACKNOWLEDGEMENTS.agent]) {
    assert.ok(text.includes('I read the whole source document, not only the cited passages'), text);
    assert.ok(text.includes('can miss wording they do not recognise'), text);
  }
});

test('a reinstated exclusion that cannot be approved says why and never asks for an approval', () => {
  // round 5, bypass:6: the server withholds approve until the reinstatement gate is met.
  const detail = 'If a reviewer reinstates this code, it can only be rejected until the documentation is completed (add it as an addendum): Which extent was reached?';
  const proposal = { bucket: 'excluded', reinstatable: true, decision_state: 'reinstated', allowed_actions: ['reject', 'revoke'],
    decision: { action: 'reinstate', reviewer: 'Reviewer One', reviewer_kind: 'human' }, approve_withheld_by: 'review.reinstatement',
    checks: [{ id: 'review.reinstatement', status: 'warn', detail }] };
  const sentence = app.candidateDecision(proposal);
  assert.equal(sentence.includes('approve or reject it'), false, sentence);
  assert.ok(sentence.startsWith('Reinstated for review by Reviewer One. It cannot be approved yet'), sentence);
  assert.ok(sentence.endsWith(detail), sentence);
  const em = { ...proposal, approve_withheld_by: 'em.same_day_if_reinstated',
    checks: [{ id: 'review.reinstatement', status: 'pass', detail: 'Clear.' }, { id: 'em.same_day_if_reinstated', status: 'warn', detail: 'Same-day gate.' }] };
  assert.ok(app.candidateDecision(em).endsWith('Same-day gate.'));
  const html = render(excludedDoc(proposal));
  assert.equal(html.includes(`data-decision="approve" data-proposal="${UUID}"`), false);
  assert.ok(html.includes(`data-decision="reject" data-proposal="${UUID}"`));
});

test('an encounter whose only proposals are documentation-check exclusions never says nothing was proposed', () => {
  const doc = excludedDoc({});
  const only = { ...doc, assessment: { ...doc.assessment, proposals: doc.assessment.proposals.filter(p => p.bucket === 'excluded') } };
  const html = render(only);
  assert.equal(html.includes('No CPT codes were proposed for this document.'), false);
  assert.ok(html.includes('One code that a documentation check excluded needs a reviewer&#x27;s decision under Excluded candidates below.'), html);
  assert.equal(app.emptySelectionCopy({ proposals: [] }), 'No CPT codes were proposed for this document.');
  assert.ok(app.emptySelectionCopy({ proposals: [{ bucket: 'alternative' }] }).startsWith('No code is selected for approval.'));
});

// round 7, bypass:1: a provider response refused whole was never read, so the panel never says nothing was proposed.
// refutation 7c8, reports-5: nor of a response the assessment never read at all (summary.provider_status unknown,
// failed or not_run), whatever its check's status - an unknown outcome is a 'warn'. Only a response that was read and
// selected nothing is "No CPT codes were proposed".
test('a provider check that failed, or a response never read, gives the panel its reason; a response read does not', () => {
  const detail = 'The response from corti (corti-coding@2) was not used, so there are no CPT proposals. This is not a finding that no codes apply.';
  const refused = { proposals: [], summary: { provider_status: 'succeeded' }, encounter_checks: [{ id: 'extraction.status', status: 'fail', detail: 'Other.' }, { id: 'provider.status', status: 'fail', detail }] };
  assert.equal(app.emptySelectionCopy(refused), detail);
  const html = render({ ...excludedDoc({}), assessment: { ...excludedDoc({}).assessment, ...refused } });
  assert.equal(html.includes('No CPT codes were proposed for this document.'), false);
  assert.ok(html.includes('was not used, so there are no CPT proposals'), html);
  for (const summary of [{ provider_status: 'succeeded' }, undefined]) {
    for (const status of ['warn', 'pass', 'not_verified']) {
      const read = { proposals: [], summary, encounter_checks: [{ id: 'provider.status', status, detail: 'Read.' }] };
      assert.equal(app.emptySelectionCopy(read), 'No CPT codes were proposed for this document.', status);
    }
  }
  assert.equal(app.emptySelectionCopy({ proposals: [], encounter_checks: [{ id: 'provider.status', status: 'fail' }] }), 'No CPT codes were proposed for this document.');
  const unknown = 'The proposal provider request was sent but its outcome is unknown, so there are no CPT proposals; a workspace member must reconcile it before any new attempt. This is not a finding that no codes apply.';
  for (const [provider_status, status, said] of [['unknown', 'warn', unknown], ['not_run', 'not_verified', 'The proposal provider was not run for this revision, so there are no CPT proposals.'], ['failed', 'fail', 'Did not return a usable result.']]) {
    const unread = { proposals: [], summary: { provider_status }, encounter_checks: [{ id: 'provider.status', status, detail: said }] };
    assert.equal(app.emptySelectionCopy(unread), said, provider_status);
    const page = render({ ...excludedDoc({}), assessment: { ...excludedDoc({}).assessment, ...unread } });
    assert.equal(page.includes('No CPT codes were proposed for this document.'), false, provider_status);
  }
  assert.equal(app.emptySelectionCopy({ proposals: [], summary: { provider_status: 'unknown' }, encounter_checks: [] }), 'No provider response was read for this revision, so there are no CPT proposals.');
});

// skeptic of refutation 7c8 reports-5: the second review made for the answer the assessment reads (second_review.run)
// whose response was not read (unknown, failed, not sent) or not used (refused whole) is stated after the panel's own
// wording, never left behind "No CPT codes were proposed"; one read and used, or none made, changes nothing.
test('a second review whose response was not read or not used is stated in the panel, never read as nothing proposed', () => {
  const ready = fixture('encounter-ready.json');
  const primary = 'corti (corti-coding@2) returned no selected CPT-labelled code (0 candidate or alternatives, which cannot be approved).';
  const assessment = { ...ready.assessment, proposals: [], summary: { provider_status: 'succeeded' }, encounter_checks: [{ id: 'provider.status', status: 'warn', detail: primary }] };
  const second = { ...ready.provider_runs[0], id: UUID, purpose: 'second_review', state: 'unknown', http_status: null, error: 'Read timed out after the request was sent.', reconciled: false, scope_items: ['colonoscopy (documented as performed) has no supported proposal'] };
  const asked = 'A second review was requested for: colonoscopy (documented as performed) has no supported proposal.';
  const none = 'This is not a finding that no codes apply.';
  const doc = (run, extra = {}) => ({ ...ready, provider_runs: [...ready.provider_runs, run], second_review: { available: false, reason: '', items: [], can_request: true, run: run.id }, assessment: { ...assessment, ...extra } });
  for (const [run, said] of [
    [second, 'It was sent, but its outcome is unknown: no response was recorded, so nothing from it was read.'],
    [{ ...second, reconciled: true }, 'It was sent, but its outcome is unknown: no response was recorded, so nothing from it was read. A member reconciled it.'],
    [{ ...second, state: 'failed', http_status: 500, error: 'HTTP 500 from the provider.' }, 'It failed: HTTP 500 from the provider. Nothing from it was used.'],
    [{ ...second, state: 'not_sent', error: 'The excerpt could not be sent' }, 'Nothing was sent for it: The excerpt could not be sent.'],
    [{ ...second, state: 'succeeded', error: '' }, 'Its response has not been read by this assessment.'],
  ]) {
    const page = doc(run);
    const expected = `${primary} ${asked} ${said} ${none}`;
    assert.equal(app.secondReviewUnread(page), `${asked} ${said} ${none}`, run.state);
    assert.equal(app.emptySelectionCopy(page.assessment, page), expected, run.state);
    const html = render(page);
    assert.equal(html.includes('No CPT codes were proposed for this document.'), false, run.state);
    assert.ok(html.includes(app.escapeHtml(expected)), run.state);
  }
  // refused whole: the review's own failed check, as the primary's refused response gives its own (round 7 bypass:1)
  const refused = 'A second review was requested for: colonoscopy. Its response was not used (it selects 65 codes, more than the 64 this adapter accepts).';
  const read = { ...second, state: 'succeeded', error: '' };
  const refusedDoc = doc(read, { second_run: UUID, encounter_checks: [...assessment.encounter_checks, { id: 'provider.second_review', status: 'fail', detail: refused }] });
  assert.equal(app.emptySelectionCopy(refusedDoc.assessment, refusedDoc), `${primary} ${refused}`);
  // a listed alternative keeps its wording, then the review's outcome
  const listed = doc(second, { proposals: [{ bucket: 'alternative' }] });
  assert.ok(app.emptySelectionCopy(listed.assessment, listed).startsWith('No code is selected for approval.'));
  assert.ok(app.emptySelectionCopy(listed.assessment, listed).endsWith(`${asked} It was sent, but its outcome is unknown: no response was recorded, so nothing from it was read. ${none}`));
  // controls: read and used (its check did not fail), no run named, or no second_review at all: nothing is added
  const used = doc(read, { second_run: UUID, encounter_checks: [...assessment.encounter_checks, { id: 'provider.second_review', status: 'warn', detail: 'Added no proposal.' }] });
  assert.equal(app.secondReviewUnread(used), '');
  assert.equal(app.emptySelectionCopy(used.assessment, used), 'No CPT codes were proposed for this document.');
  const unnamed = { ...doc(second), second_review: { available: false, reason: '', items: [], run: null } };
  assert.equal(app.emptySelectionCopy(unnamed.assessment, unnamed), 'No CPT codes were proposed for this document.');
  assert.equal(app.emptySelectionCopy(assessment), 'No CPT codes were proposed for this document.');
  assert.equal(app.emptySelectionCopy(assessment, ready), 'No CPT codes were proposed for this document.');
});

// round 6, bypass:3: whether a reinstated code can be approved is the code's own gate, never the member's action list.
test('a viewer is told a reinstated code is approvable by a reviewer, and is told it is withheld only by its gate', () => {
  const reinstated = { bucket: 'excluded', reinstatable: true, decision_state: 'reinstated', allowed_actions: [],
    decision: { action: 'reinstate', reviewer: 'Reviewer One', reviewer_kind: 'human' }, approve_withheld_by: null,
    checks: [{ id: 'review.reinstatement', status: 'pass', detail: 'Clear.' }] };
  const clear = app.candidateDecision(reinstated);
  assert.equal(clear, 'Reinstated for review by Reviewer One; a reviewer approves or rejects it.');
  assert.equal(clear.includes('cannot be approved yet'), false);
  const reviewer = app.candidateDecision({ ...reinstated, allowed_actions: ['approve', 'reject', 'revoke'] });
  assert.equal(reviewer, 'Reinstated for review by Reviewer One; approve or reject it.');
  const held = app.candidateDecision({ ...reinstated, approve_withheld_by: 'review.reinstatement',
    checks: [{ id: 'review.reinstatement', status: 'warn', detail: 'Which extent was reached?' }] });
  assert.ok(held.startsWith('Reinstated for review by Reviewer One. It cannot be approved yet'), held);
  assert.ok(held.endsWith('Which extent was reached?'), held);
});

// round 6, bypass:1: the copy that names the addendum path comes with the addendum control.
test('a reinstated code withheld by its gate offers an addendum that needs no clarification, to a member who can edit', () => {
  const withheld = { decision_state: 'reinstated', allowed_actions: ['reject', 'revoke'], approve_withheld_by: 'review.reinstatement',
    decision: { action: 'reinstate', reviewer: 'Reviewer One', reviewer_kind: 'human' },
    checks: [{ id: 'review.reinstatement', status: 'warn', detail: 'Which extent was reached?' }] };
  const addendum = '<button type="button" class="button secondary" data-action="addendum">Add the missing documentation (addendum)</button>';
  const html = render(excludedDoc(withheld));
  assert.ok(html.includes(addendum), 'no addendum control beside the copy that asks for one');
  assert.equal(render({ ...excludedDoc(withheld), permissions: { can_review: false } }).includes(addendum), false, 'a viewer was offered an addendum');
  assert.equal(render({ ...excludedDoc(withheld), pipeline: { ...excludedDoc(withheld).pipeline, busy: true } }).includes(addendum), false,
    'an addendum was offered while a stage runs');
  const clear = { ...withheld, approve_withheld_by: null, allowed_actions: ['approve', 'reject', 'revoke'] };
  assert.equal(render(excludedDoc(clear)).includes(addendum), false, 'an approvable code was told to add documentation');
});

// round 6, bypass:4: the empty-selection panel counts only the exclusions still waiting, as readiness does.
test('the empty-selection panel counts the exclusions still waiting and says when every one has a decision', () => {
  const excluded = (state, extra = {}) => ({ bucket: 'excluded', reinstatable: true, decision_state: state, ...extra });
  const copy = proposals => app.emptySelectionCopy({ proposals });
  assert.equal(copy([excluded('undecided'), excluded('reinstated')]),
    '2 codes that a documentation check excluded need a reviewer\'s decision under Excluded candidates below.');
  assert.equal(copy([excluded('exclusion_confirmed'), excluded('reinstated')]),
    'One code that a documentation check excluded needs a reviewer\'s decision under Excluded candidates below.');
  for (const decided of [[excluded('exclusion_confirmed'), excluded('approved')], [excluded('exclusion_confirmed'), excluded('exclusion_confirmed')],
    [excluded('rejected'), { bucket: 'excluded', reinstatable: false, decision_state: 'undecided' }]]) {
    const text = copy(decided);
    assert.equal(text, 'Every code that a documentation check excluded has a decision; see Excluded candidates below.', text);
  }
  assert.ok(copy([{ bucket: 'excluded', reinstatable: false, decision_state: 'undecided' }]).startsWith('No code is selected for approval.'));
});

test('the review dialog shows the attestation the server serves, and the built-in copy only before the session loads', () => {
  // round 5, bypass:4: the server accepts exactly its own attestation text.
  assert.equal(app.attestationText({ acknowledgement: 'Server attestation.', user: { actor_kind: 'agent' } }), 'Server attestation.');
  assert.equal(app.attestationText({ user: { actor_kind: 'agent' } }), app.ACKNOWLEDGEMENTS.agent);
  assert.equal(app.attestationText({ user: { actor_kind: 'human' } }), app.ACKNOWLEDGEMENTS.human);
  assert.equal(app.attestationText(null), app.ACKNOWLEDGEMENTS.human);
});

test('the review dialog takes its attestation from attestationText (the server enforces the same text)', () => {
  // The dialog itself needs a DOM; this pins its wiring, and the live walk posts what the dialog shows.
  const source = fs.readFileSync(path.join(__dirname, '..', '..', 'studio', 'static', 'studio', 'app.js'), 'utf8');
  assert.ok(source.includes("$('#reviewAckText').textContent = attestationText(state.session);"));
  assert.equal(source.split("$('#reviewAckText').textContent =").length - 1, 1, 'one writer of the attestation text');
});

test('the bounded second review is offered to a reviewer as a request, never shown as made', () => {
  const service = { id: 'S1', family: 'gi.colonoscopy', kind: 'colonoscopy', status: 'performed', acts: [] };
  const base = { assessment: { services: { services: [service] }, completeness: { unresolved_items: [
    { service: 'S1', label: 'forceps biopsy of the <b>lesion</b>', reason: 'not_covered', second_review: true }] } } };
  const offered = { available: true, reason: '', items: ['forceps biopsy of the <b>lesion</b>'], can_request: true };
  const reviewer = app.documentedServices({ ...base, permissions: { can_review: true }, second_review: offered });
  assert.equal(count(reviewer, 'data-action="second-review"'), 1);
  assert.ok(reviewer.includes('Second provider review available'));
  assert.ok(reviewer.includes('&lt;b&gt;lesion&lt;/b&gt;') && !reviewer.includes('<b>lesion</b>'));
  const viewer = app.documentedServices({ ...base, permissions: { can_review: false },
    second_review: { ...offered, can_request: false } });
  assert.equal(count(viewer, 'data-action="second-review"'), 0);
  const refused = app.documentedServices({ ...base, permissions: { can_review: true },
    second_review: { available: false, reason: 'A second review was already made for this document and date.',
      items: offered.items, can_request: true } });
  assert.equal(count(refused, 'data-action="second-review"'), 0);
  assert.ok(refused.includes('already made for this document and date'));
  const none = app.documentedServices({ ...base, permissions: { can_review: true },
    second_review: { available: false, reason: '', items: [], can_request: true } });
  assert.ok(!none.includes('Second provider review'));
});

// Repair round ec5 (REPORTRUNS): the page says which provider request each run was, and describes a second review a
// reviewer asked for until its own outcome is recorded (refutation r1 report-10; the 8985dde42 request re-checked).
test('provider runs name the second review and what it asked about, as both reports do', () => {
  const base = fixture('encounter-ready.json');
  const primary = { ...base.provider_runs[0], purpose: 'primary', scope_items: [] };
  const second = { ...primary, id: UUID, purpose: 'second_review', scope_items: ['forceps biopsy of the <b>lesion</b>'] };
  const timeline = render({ ...base, provider_runs: [primary, second] }, 'timeline');
  assert.equal(count(timeline, 'Second review'), 1);
  assert.ok(timeline.includes('<strong>Corti · live · Succeeded</strong>'));
  assert.ok(timeline.includes('<strong>Corti · live · Second review · Succeeded</strong>'));
  assert.ok(timeline.includes('<p>Asked about: forceps biopsy of the &lt;b&gt;lesion&lt;/b&gt;.</p>'));
  for (const [state, label] of [['not_sent', 'Not sent'], ['unknown', 'Outcome unknown']]) {
    const shown = render({ ...base, provider_runs: [primary, { ...second, state }] }, 'timeline');
    assert.ok(shown.includes(`<strong>Corti · live · Second review · ${label}</strong>`), state);
  }
  // a payload without a purpose (recorded before the second review existed) keeps its plain row
  assert.equal(count(render(base, 'timeline'), 'Second review'), 0);
});

test('the reconciliation card names an unknown second review', () => {
  const doc = fixture('encounter-provider-unknown.json');
  const unknown = { ...doc.provider_runs[0], purpose: 'second_review', scope_items: ['forceps biopsy'] };
  const answered = { ...doc.provider_runs[0], id: UUID, state: 'succeeded', purpose: 'primary', error: '' };
  const html = render({ ...doc, state: 'provider_unknown', provider_runs: [answered, unknown] });
  assert.ok(html.includes('<strong>Unreconciled request</strong><br>Second review · 23 Oct 2026, 14:02 UTC · Read timed out'));
  assert.ok(render(doc).includes('<strong>Unreconciled request</strong><br>23 Oct 2026, 14:02 UTC · Read timed out'));
});

test('a second review asked for is described until its outcome is recorded, and never offered again', () => {
  const service = { id: 'S1', family: 'gi.colonoscopy', kind: 'colonoscopy', status: 'performed', acts: [] };
  const assessment = { services: { services: [service] }, completeness: { unresolved_items: [
    { service: 'S1', label: 'forceps biopsy', reason: 'not_covered', second_review: true }] } };
  const done = ['extract', 'analyze', 'predict', 'assess'].map(kind => ({ kind, state: 'succeeded', error: '' }));
  const view = (review2, second, pipeline = {}) => app.documentedServices({
    assessment, permissions: { can_review: true }, pipeline: { stages: [...done, ...review2], ...pipeline },
    second_review: { items: ['forceps biopsy'], can_request: true, ...second } });
  const waiting = view([{ kind: 'review2', state: 'queued', error: '' }],
    { available: false, reason: 'Wait for processing to finish (or stop it) before asking for a second review.' });
  assert.ok(waiting.includes('<strong>Second provider review requested</strong><p>A reviewer asked for it; it is waiting to run, and nothing has been sent yet. Unresolved: forceps biopsy.</p>'));
  assert.ok(!waiting.includes('before asking'));
  assert.ok(view([{ kind: 'review2', state: 'running', error: '' }], { available: false }).includes('it is running now.'));
  // stopped or failed, its request is used: the page never offers it again, whatever availability says
  const stopped = view([{ kind: 'review2', state: 'cancelled', error: 'Stopped by a workspace member.' }],
    { available: true, reason: '' }, { can_resume: true });
  assert.ok(stopped.includes('<strong>Second provider review stopped</strong><p>It was stopped before anything was sent: Stopped by a workspace member. Resume processing runs it once. Unresolved: forceps biopsy.</p>'));
  assert.equal(count(stopped, 'data-action="second-review"'), 0);
  assert.ok(!view([{ kind: 'review2', state: 'cancelled', error: '' }], { available: true }).includes('Resume processing'));
  // Resume re-runs the latest stage: a later cancelled stage is what it would run, not this review
  const behind = view([{ kind: 'review2', state: 'cancelled', error: 'Stopped by a workspace member.' }, { kind: 'predict', state: 'cancelled', error: '' }],
    { available: true }, { can_resume: true });
  assert.ok(behind.includes('It was stopped before anything was sent: Stopped by a workspace member. Unresolved'));
  const failed = view([{ kind: 'review2', state: 'failed', error: 'Only an owner or reviewer of this workspace can start a live provider request.' }],
    { available: true, reason: '' });
  assert.ok(failed.includes('<strong>Second provider review did not complete</strong><p>It did not complete: Only an owner or reviewer of this workspace can start a live provider request. Unresolved: forceps biopsy.</p>'));
  assert.equal(count(failed, 'data-action="second-review"'), 0);
  // an assessment after it (the review ran and was read, or the context changed): the server's answer speaks again
  const later = view([{ kind: 'review2', state: 'cancelled', error: 'Stopped by a workspace member.' }, { kind: 'assess', state: 'succeeded', error: '' }],
    { available: true, reason: '' });
  assert.equal(count(later, 'data-action="second-review"'), 1);
  const answered = view([{ kind: 'review2', state: 'succeeded', error: '' }],
    { available: false, reason: 'The text that documents the unresolved services is a request the provider already answered, so a second review would ask nothing new.' });
  assert.ok(answered.includes('<strong>Second provider review</strong><p>The text that documents the unresolved services is a request the provider already answered'));
});

test('progress rows show the latest job of each stage, and the second review once one was asked for', () => {
  const processing = fixture('encounter-processing.json');
  assert.equal(render(processing).includes('Second provider review'), false);
  const stages = [...['extract', 'analyze', 'predict', 'assess'].map(kind => ({ kind, state: 'succeeded', error: '' })),
    { kind: 'review2', state: 'succeeded', error: '' }, { kind: 'assess', state: 'queued', error: '' }];
  const html = render({ ...processing, pipeline: { ...processing.pipeline, stages } });
  assert.ok(html.includes('<strong>Check proposals against references and reconcile</strong><p>Waiting</p>'));
  assert.ok(html.includes('<strong>Second provider review (asked for by a reviewer)</strong><p>Done</p>'));
  const redated = [...stages.slice(0, 4), { kind: 'predict', state: 'running', error: '' }];
  assert.ok(render({ ...processing, pipeline: { ...processing.pipeline, stages: redated } })
    .includes('<strong>Corti: request CPT proposals</strong><p>In progress</p>'));
});

test('the provider-not-run card gives the reason of the latest predict, not of one that ran before it', () => {
  const ready = fixture('encounter-ready.json');
  const stages = [...['extract', 'analyze', 'predict', 'assess'].map(kind => ({ kind, state: 'succeeded', error: '' })),
    { kind: 'predict', state: 'failed', error: 'Live provider calls are not authorized on this installation.' }];
  const html = render({ ...ready, state: 'provider_not_run', pipeline: { ...ready.pipeline, stages } });
  assert.ok(html.includes('<p>Live provider calls are not authorized on this installation.</p>'));
  assert.ok(!html.includes('did not run for this revision'));
});

test('the provider-failed card gives the reason of the run the state reads (state_run), never one picked by recency', () => {
  const ready = fixture('encounter-ready.json');
  const old = { ...ready.provider_runs[0], state: 'failed', http_status: 500, error: 'HTTP 500 from the provider.', purpose: 'primary' };
  const refused = { ...old, id: UUID, state: 'not_sent', http_status: null, error: 'The credentials could not be read; nothing was sent.' };
  const html = render({ ...ready, state: 'provider_failed', provider_runs: [old, refused], state_run: refused.id });
  assert.ok(html.includes('<p>Error: The credentials could not be read; nothing was sent.</p>'));
  assert.ok(!html.includes('<p>Error: HTTP 500 from the provider.</p>'));
  assert.ok(render({ ...ready, state: 'provider_failed', provider_runs: [old], state_run: old.id }).includes('<p>Error: HTTP 500 from the provider.</p>'));
  // a newer request a Stop cancelled (or the sweep settled) before sending is not the run the state reads
  const stopped = { ...old, id: '00000000-0000-4000-8000-000000000002', state: 'cancelled', http_status: null, error: 'Stopped before sending; nothing was sent.' };
  const back = render({ ...ready, state: 'provider_failed', provider_runs: [old, stopped], state_run: old.id });
  assert.ok(back.includes('<p>Error: HTTP 500 from the provider.</p>'));
  assert.ok(!back.includes('Stopped before sending'));
  // no run named: the card names none, never a guess
  const unnamed = render({ ...ready, state: 'provider_failed', provider_runs: [old, stopped], state_run: null });
  assert.ok(unnamed.includes('<p>The provider did not return proposals.</p>'));
  assert.ok(!unnamed.includes('<p>Error:'));
});

// skeptic of refutation 7c8 reports-5: a response refused whole is provider_failed reading that (succeeded) run; its card
// says the response was not used, with its own failed check - never "The provider request failed" nor "did not return".
test('the provider-failed card of a response refused whole says it was not used, with its own check', () => {
  const ready = fixture('encounter-ready.json');
  const refusedRun = { ...ready.provider_runs[0], id: UUID, state: 'succeeded', http_status: 200, error: '', purpose: 'primary' };
  const status = 'The response from corti (corti-coding@2) was not used, so there are no CPT proposals. This is not a finding that no codes apply.';
  const problems = '1 problem reading the provider response: The provider response was not used: it selects 65 codes, more than the 64 this adapter accepts';
  const checks = [{ id: 'provider.status', status: 'fail', detail: status }, { id: 'provider.problems', status: 'warn', detail: problems }];
  const html = render({ ...ready, state: 'provider_failed', provider_runs: [refusedRun], state_run: UUID, assessment: { ...ready.assessment, encounter_checks: checks } });
  assert.ok(html.includes('The provider response<br>was not used.'), html);
  assert.ok(html.includes(`<p>${app.escapeHtml(status)}</p>`));
  assert.ok(html.includes(`<p>${app.escapeHtml(problems)}</p>`));
  assert.ok(!html.includes('The provider request<br>failed.'));
  assert.ok(!html.includes('The provider did not return proposals.'));
  // the second review's refusal reads its own check, never the primary's
  const second = { ...refusedRun, purpose: 'second_review' };
  const own = 'A second review was requested for: colonoscopy. Its response was not used (it selects 65 codes, more than the 64 this adapter accepts).';
  const read = [{ id: 'provider.status', status: 'warn', detail: 'corti returned no selected CPT-labelled code.' }, { id: 'provider.second_review', status: 'fail', detail: own }];
  const page = render({ ...ready, state: 'provider_failed', provider_runs: [{ ...refusedRun, id: '00000000-0000-4000-8000-000000000003' }, second], state_run: UUID, assessment: { ...ready.assessment, encounter_checks: read } });
  assert.ok(page.includes('The provider response<br>was not used.'));
  assert.ok(page.includes(`<p>${app.escapeHtml(own)}</p>`));
  assert.ok(!page.includes('<p>corti returned no selected CPT-labelled code.</p>'));
});

// refutation 7c8, reports-4: a support that was not checked (not_applicable) keeps the documented service's passages as
// its source; they are never "passages that show the coded act" nor marked as evidence for the code, and its provider
// passages carry no check result either.
test('the passages of a support that was not checked are never shown as showing the coded act', () => {
  const ready = fixture('encounter-ready.json');
  const text = ready.revision.text;
  const { key, exact, ...heading } = cpSpan(text, 'UPPER ENDOSCOPY', 'x');
  const withSupport = support => {
    const proposals = ready.assessment.proposals.map((proposal, index) => (index ? proposal : { ...proposal, support }));
    return { ...ready, assessment: { ...ready.assessment, proposals } };
  };
  const notChecked = withSupport({ status: 'not_applicable', reason: 'act_missing', supporting: [], unrelated: [0], source: [heading],
    detail_support: 'Not checked: the documented service or act is not established as performed.' });
  const html = render(notChecked);
  assert.ok(!html.includes('Source passages that show the coded act'), 'never "passages that show the coded act"');
  assert.ok(html.includes('Passages of the documented service (not checked against the coded act)'));
  assert.ok(html.includes('“UPPER ENDOSCOPY” — selected from the source by CPT Studio; not checked against the coded act'));
  assert.ok(!html.includes('cited by the provider; does not show the coded act'), 'no check result for a passage not checked');
  assert.ok(html.includes('title="Passage of the documented service for 43239, not checked against the coded act">UPPER ENDOSCOPY</button>'));
  assert.ok(!html.includes('title="Evidence for 43239">UPPER ENDOSCOPY</button>'));
  // control: a checked support whose provider passage does not show the act still says so, and marks what does
  const checked = render(withSupport({ status: 'warn', supporting: [], unrelated: [0], source: [heading] }));
  assert.ok(checked.includes('Source passages that show the coded act'));
  assert.ok(checked.includes('cited by the provider; does not show the coded act'));
  assert.ok(checked.includes('title="Evidence for 43239">UPPER ENDOSCOPY</button>'));
  assert.ok(!checked.includes('not checked against the coded act'));
});

// --- repair round gi2, agent 'present' (investigations demo PR5/PR6/RC6-RC8 and occurrence R4 (i)) ------------------

function queueRow(n, state, extra = {}) {
  return { id: `c0000000-0000-4000-8000-0000000001${String(n).padStart(2, '0')}`, title: `Synthetic document ${n}`, state,
    state_label: state, service_date: '2026-10-21', service_date_conflict: false, families: [], source_kind: 'txt',
    open_clarifications: 0, created_at: '2026-10-23T14:00:00Z', ...extra };
}
const listedIds = html => [...html.matchAll(/href="#doc\/([0-9a-f-]{36})"/g)].map(match => match[1]);

// demo RC6 / PR5 (R9): ho-06 (no_codes, a second review available) and ho-09 (reviewed, a service unresolved) were off
// the queue, which listed three states only.
test('the review queue lists every row the server says waits on a member, whatever its state', () => {
  const rows = [
    queueRow(1, 'no_codes', { queue_reasons: ['incomplete', 'second_review'], coding_state: 'incomplete' }),
    queueRow(2, 'reviewed', { queue_reasons: ['incomplete', 'second_review'], coding_state: 'incomplete' }),
    queueRow(3, 'reviewed', { queue_reasons: [], coding_state: 'reviewed' }),
    queueRow(4, 'processing', { queue_reasons: [], coding_state: 'not_established' }),
    queueRow(5, 'provider_failed', { queue_reasons: ['incomplete'], coding_state: 'incomplete' }),
    queueRow(6, 'ready_for_review', { queue_reasons: ['state'], coding_state: 'pending_review' }),
    queueRow(7, 'stopped', { queue_reasons: ['decision'], coding_state: 'pending_review' }),
  ];
  const queued = [1, 2, 5, 6, 7].map(n => rows[n - 1].id);
  assert.deepEqual(listedIds(app.listBody('queue', rows)), queued);
  assert.equal(app.listDescription('queue', rows), '5 documents wait on a workspace member: a clarification, a review decision, a reconciliation, a second review that can be asked for, or coding left incomplete.');
  assert.equal(app.listDescription('queue', rows.slice(0, 1)), 'One document waits on a workspace member: a clarification, a review decision, a reconciliation, a second review that can be asked for, or coding left incomplete.');
  assert.equal(app.listDescription('queue', [rows[2]]), 'No document waits on a workspace member for a clarification, a review decision, a reconciliation, a second review or incomplete coding.');
  // the server's answer is the rule: a state that once queued is not listed when it says nothing waits ...
  assert.deepEqual(listedIds(app.listBody('queue', [queueRow(8, 'ready_for_review', { queue_reasons: [] })])), []);
  // ... and a row without the field (or with a malformed one) keeps the three states
  const old = rows.map(({ queue_reasons, ...rest }) => rest);
  assert.deepEqual(listedIds(app.listBody('queue', old)), [rows[5].id]);
  assert.deepEqual(listedIds(app.listBody('queue', [queueRow(9, 'needs_clarification', { queue_reasons: 'yes' })])), [queueRow(9, 'x').id]);
  // the documents list and the overview are unchanged by the queue rule
  assert.equal(count(app.listBody('documents', rows), 'class="document-row"'), rows.length);
});

test('a queued row says what it waits for, from the served reasons only, never twice', () => {
  const row = queueRow(1, 'ready_for_review', { open_clarifications: 2, queue_reasons: ['question', 'decision', 'reconciliation', 'incomplete', 'second_review', 'state', '<b>other</b>'] });
  const html = app.listBody('queue', [row]);
  assert.ok(html.includes('<small>TXT · Gastroenterology · 2 open questions · Decision needed · Provider outcome to reconcile · Coding incomplete · Second review available</small>'), html);
  assert.equal(html.includes('other'), false, 'an unknown reason is never printed');
  // the badge already says the coding is incomplete: the meta does not repeat it
  const reviewed = queueRow(2, 'reviewed', { state_label: 'Reviewed', coding_state: 'incomplete', queue_reasons: ['incomplete', 'second_review'] });
  const shown = app.listBody('queue', [reviewed]);
  assert.ok(shown.includes('<small>TXT · Gastroenterology · Second review available</small>'), shown);
  // the reasons belong to the queue: the documents list keeps its meta
  assert.ok(app.listBody('documents', [row]).includes('<small>TXT · Gastroenterology · 2 open questions</small>'));
});

// demo R10: "Reviewed" beside coding incomplete reads as done.
test('a reviewed row whose coding is incomplete reads "Reviewed · coding incomplete", never a bare green Reviewed', () => {
  const incomplete = queueRow(1, 'reviewed', { state_label: 'Reviewed', coding_state: 'incomplete', queue_reasons: ['incomplete'] });
  const row = app.documentRow(incomplete);
  assert.ok(row.includes('<span class="status amber">Reviewed · coding incomplete</span>'), row);
  assert.ok(row.includes('doc-file-icon amber'));
  assert.equal(row.includes('status green'), false);
  assert.ok(app.inviteMarkup([incomplete]).includes('Most recent · Reviewed · coding incomplete · 21 Oct 2026'));
  // controls: complete coding, an older payload without coding_state, another state with incomplete coding
  const complete = app.documentRow({ ...incomplete, coding_state: 'reviewed', queue_reasons: [] });
  assert.ok(complete.includes('status green') && complete.includes('Reviewed</span>') && !complete.includes('coding incomplete'), complete);
  const older = app.documentRow({ ...incomplete, coding_state: undefined });
  assert.ok(older.includes('Reviewed</span>') && !older.includes('coding incomplete'), older);
  const asked = app.documentRow(queueRow(2, 'needs_clarification', { state_label: 'Needs clarification', coding_state: 'incomplete' }));
  assert.ok(asked.includes('<span class="status amber">Needs clarification</span>'), asked);
  const hostile = app.documentRow({ ...incomplete, state_label: '<img src=x onerror="window.__xss=9">' });
  assert.equal(hostile.includes('<img'), false);
  assert.ok(hostile.includes('&lt;img src=x onerror=&quot;window.__xss=9&quot;&gt; · coding incomplete'));
});

// occurrence RC5 / R4 (i): the chip said "Not documented" beside a check quoting the date the reader kept as evidence.
test('a service date kept as evidence is quoted on the date chips, and said to be asked only when it is', () => {
  const doc = fixture('encounter-clarification.json');
  const kept = { value: null, origin: 'missing', note: 'A "Date:" line is kept as evidence.', member_conflict: false,
    evidence: [{ start: 70, end: 86, text: 'Date: 10/27/2026' }] };
  const asked = { ...doc, context: { ...doc.context, facts: { ...doc.context.facts, service_date: kept } } };
  assert.ok(doc.clarifications.some(item => item.fact === 'service_date' && item.state === 'open'));
  assert.equal(app.serviceDateChip(asked), 'Asked — “Date: 10/27/2026” is not read as the date of service');
  assert.equal(app.serviceDateMeta(asked), 'Service date asked — “Date: 10/27/2026” is not read as the date of service');
  const html = render(asked);
  assert.ok(html.includes('<span><b>SERVICE DATE</b>Asked — “Date: 10/27/2026” is not read as the date of service</span>'), html);
  assert.ok(html.includes('<span>Service date asked — “Date: 10/27/2026” is not read as the date of service</span>'));
  assert.equal(html.includes('Service date not documented'), false);
  // kept but not asked (no open question on the date, e.g. before the assessment ran): quoted, never "asked"
  const quiet = { ...asked, clarifications: asked.clarifications.map(item => ({ ...item, state: 'answered' })) };
  assert.equal(app.serviceDateChip(quiet), '“Date: 10/27/2026” is not read as the date of service');
  assert.equal(app.serviceDateMeta(quiet), 'Service date: “Date: 10/27/2026” is not read as the date of service');
  const proposalScoped = { ...asked, clarifications: asked.clarifications.map(item => ({ ...item, scope: 'proposal' })) };
  assert.equal(app.serviceDateChip(proposalScoped).startsWith('Asked'), false);
  // the quote is an excerpt: whitespace folded, long text cut with an ellipsis, markup escaped where it is drawn
  const long = { ...kept, evidence: [{ start: 0, end: 1, text: '   ' }, { start: 0, end: 1, text: `Colonoscopy  report\n<b>${'x'.repeat(200)}</b> 10/14/2026` }] };
  const chip = app.serviceDateChip({ ...asked, context: { facts: { service_date: long } } });
  assert.ok(chip.startsWith('Asked — “Colonoscopy report <b>xxx'), chip);
  const quoted = /“(.*)”/.exec(chip)[1];
  assert.ok(quoted.endsWith('…') && [...quoted].length === 80, quoted);
  assert.ok(chip.endsWith('…” is not read as the date of service'), chip);
  assert.equal(render({ ...asked, context: { facts: { service_date: long } } }).includes('<b>xxx'), false);
  // controls: nothing kept, a documented date, a conflict, a member's date, no fact
  assert.equal(app.serviceDateChip(doc), 'Not documented');
  assert.equal(app.serviceDateMeta(doc), 'Service date not documented');
  const facts = service_date => ({ ...doc, context: { facts: { service_date } } });
  assert.equal(app.serviceDateChip(facts({ value: '2026-10-21', origin: 'document', evidence: [{ start: 0, end: 4, text: 'Date' }] })), '21 October 2026');
  assert.equal(app.serviceDateMeta(facts({ value: '2026-10-21', origin: 'document', evidence: [] })), '21 Oct 2026');
  assert.equal(app.serviceDateChip(facts({ value: null, origin: 'conflict', member_conflict: false, evidence: kept.evidence })), 'Conflicting values documented');
  assert.equal(app.serviceDateMeta(facts({ value: null, origin: 'conflict', member_conflict: true, evidence: kept.evidence })), 'Service date: member entry differs from the document');
  assert.equal(app.serviceDateChip(facts({ value: '2026-10-21', origin: 'user', evidence: [] })), '21 October 2026 (entered)');
  assert.equal(app.serviceDateChip(facts(undefined)), 'Not documented');
  // the question a closing charge block asks is no conflict in the document (the sixth refutation, dates-n6-2)
  const dateAsked = { value: null, origin: 'conflict', member_conflict: false, date_asked: true, evidence: kept.evidence };
  assert.equal(app.serviceDateChip(facts(dateAsked)), 'Date asked');
  assert.equal(app.serviceDateMeta(facts(dateAsked)), 'Service date asked');
  const listed = app.documentRow(queueRow(2, 'needs_clarification', { state_label: 'Needs clarification', coding_state: 'incomplete',
    service_date: null, service_date_conflict: false, service_date_asked: true }));
  assert.equal(listed.includes('<span class="doc-row-date">Date asked</span>'), true);
  assert.equal(listed.includes('In conflict'), false);
});

// demo RC8 / PR7: the cards led with a slogan and printed the engine's cue strings as the doctor's text.
test('a clarification card leads with the question; the technical reason is behind a Details disclosure', () => {
  const doc = fixture('encounter-clarification.json');
  const reason = 'No documentation establishes it (cue “section: indication (Indications)”, negated: not; routing-era reading) <b>x</b>.';
  const question = 'Confirm the date of service for this encounter <i>now</i>?';
  const asked = { ...doc, clarifications: [{ ...doc.clarifications[0], question, reason }] };
  const html = render(asked);
  const card = html.slice(html.indexOf('<div class="clarification-card">'));
  const lead = card.indexOf(`<h3 class="clarification-lead">${app.escapeHtml(question)}</h3>`);
  const details = card.indexOf(`<details class="clarification-details"><summary>Details</summary><span class="clarification-reason">${app.escapeHtml(reason)}</span></details>`);
  assert.ok(lead > 0 && details > lead, card.slice(0, 900));
  assert.equal(count(html, app.escapeHtml(reason)), 1, 'the reason is said once, inside the disclosure');
  assert.equal(html.includes('A question is better'), false);
  assert.equal(html.includes('<b>x</b>') || html.includes('<i>now</i>'), false);
  assert.ok(card.indexOf('data-action="addendum"') > details, 'the answer follows the question and its details');
  assert.ok(card.includes('<span class="clarification-eyebrow">Clarification needed</span>'));
  // a family question names its family in the eyebrow, never in place of the question
  const family = { ...asked, clarifications: [{ ...asked.clarifications[0], family: 'gi.egd' }] };
  assert.ok(render(family).includes('<span class="clarification-eyebrow">Clarification needed · Upper GI endoscopy (EGD, esophagoscopy, POEM)</span><h3 class="clarification-lead">'));
  // no reason recorded: no empty disclosure
  const bare = render({ ...doc, clarifications: [{ ...doc.clarifications[0], reason: '' }] });
  assert.equal(bare.includes('<details class="clarification-details">'), false);
  // no question recorded (never expected): the reason is shown openly rather than hidden behind nothing
  const unasked = render({ ...doc, clarifications: [{ ...doc.clarifications[0], question: '', reason: 'Only a reason.' }] });
  assert.ok(unasked.includes('<h3 class="clarification-lead">Only a reason.</h3>'), unasked);
  // a viewer sees the question and its details, and no answer control
  const viewer = render({ ...asked, permissions: { can_review: false } });
  assert.ok(viewer.includes('<h3 class="clarification-lead">') && viewer.includes('<summary>Details</summary>'));
  assert.equal(viewer.includes('data-action="addendum" data-clarification'), false);
});

test('a question on a code card keeps the question first and its reason behind Details', () => {
  const doc = fixture('encounter-ready.json');
  const inline = doc.clarifications.find(item => item.scope === 'proposal' && item.state === 'open');
  const html = render(doc);
  const at = html.indexOf(`<div class="clarification-question"><strong>Clarification needed</strong><br>${app.escapeHtml(inline.question)}<details class="clarification-details"><summary>Details</summary><span class="clarification-reason">${app.escapeHtml(inline.reason)}</span></details>`);
  assert.ok(at > 0, html.slice(html.indexOf('clarification-question') - 50, html.indexOf('clarification-question') + 900));
  assert.ok(at < html.indexOf('data-action="addendum" data-clarification', at));
  assert.equal(count(html, app.escapeHtml(inline.reason)), 1);
});

// demo RC7 / PR6: every provider candidate was one flat list beside the same-family alternatives, without its passage.
function candidatesDoc() {
  const doc = fixture('encounter-ready.json');
  const text = doc.revision.text;
  const quote = 'UPPER ENDOSCOPY';
  const evidence = [cpSpan(text, quote, 'x')].map(({ key, ...span }) => span);
  const alternative = (id, code, family, extra = {}) => ({ id: `e0000000-0000-4000-8000-0000000002${id}`, key: `alt:${id}`, bucket: 'alternative', code,
    code_kind: 'cpt1', family, family_label: family, eyebrow: 'CPT', supported: family !== 'gi.unsupported', status: 'informational',
    status_label: 'Not selected', exclusion_reason: 'Provider candidate; not selected. Candidates and alternatives cannot be approved.',
    reinstatable: false, evidence: [], rationale: '', units: 1, checks: [{ id: 'scope.cpt', status: 'pass', label: 'CPT-only scope', detail: 'In scope.' }],
    modifier_considerations: [], support: {}, clarification_ids: [], decision: null, decision_state: 'undecided', reinstated_by: null,
    allowed_actions: [], approve_withheld_by: null, ...extra });
  const alternatives = [
    alternative(10, '45380', 'gi.colonoscopy', { evidence }),
    alternative(11, '19083', 'gi.unsupported', { evidence: [...evidence, ...evidence] }),
    alternative(12, '43235', 'gi.egd'),
    alternative(13, 'G0121', 'gi.colonoscopy', { code_kind: 'hcpcs', checks: [{ id: 'scope.cpt', status: 'fail', label: 'CPT-only scope', detail: 'HCPCS Level II code — CPT-only results.' }] }),
    alternative(14, '<img src=x>', 'gi.unsupported', { code_kind: 'invalid', evidence: [{ ...evidence[0], text: '<b>bold</b>' }] }),
  ];
  const services = { services: [{ id: 'S1', family: 'gi.colonoscopy', kind: 'colonoscopy', status: 'performed', acts: [] },
    { id: 'S2', family: 'gi.office_em', kind: 'office_visit', status: 'planned', acts: [] }] };
  const proposals = [...doc.assessment.proposals.filter(p => p.bucket !== 'alternative'), ...alternatives];
  return { ...doc, assessment: { ...doc.assessment, services, proposals } };
}

test('candidates of a documented service family lead; the others are collapsed with their count; none is dropped or selectable', () => {
  const doc = candidatesDoc();
  const html = render(doc);
  const start = html.indexOf('<h2>Alternatives (never selectable)</h2><span class="small-badge">5</span>');
  assert.ok(start > 0, 'the never-selectable heading and the total stay');
  const next = html.indexOf('<div class="section-heading">', start + 1);  // Excluded candidates follow
  assert.ok(html.slice(next).startsWith('<div class="section-heading"><h2>Excluded candidates</h2>'));
  const section = html.slice(start, next);
  const same = section.indexOf('Same GI family as a documented service · 1');
  const other = section.indexOf('<details class="check-list-card candidate-group"><summary>Outside the documented services or not a CPT code · 4</summary>');
  assert.ok(same > 0 && other > same, section.slice(0, 600));
  const first = section.slice(same, other);
  const rest = section.slice(other);
  assert.ok(first.includes('<strong>45380 · gi.colonoscopy</strong>'));
  for (const code of ['19083', '43235', 'G0121', '&lt;img src=x&gt;']) {
    assert.ok(rest.includes(`<strong>${code} · `), code);
    assert.equal(first.includes(`<strong>${code} · `), false, code);
  }
  // a HCPCS code of a documented family is not a CPT code; a family the document plans but does not do still counts
  assert.equal(count(section, '<strong>'), 5, 'every candidate listed exactly once');
  assert.equal(/<details[^>]* open/.test(section), false, 'collapsed by default');
  // each candidate's cited passage on expand, escaped; one that cites none says so
  assert.ok(first.includes('<details class="candidate-passages"><summary>Cited passage</summary><p>“UPPER ENDOSCOPY”</p></details>'));
  assert.ok(rest.includes('<summary>Cited passages (2)</summary><p>“UPPER ENDOSCOPY”</p><p>“UPPER ENDOSCOPY”</p>'));
  // a passage that is not at its position in the current revision is quoted and flagged, never passed off as found
  assert.ok(rest.includes('<p>“&lt;b&gt;bold&lt;/b&gt;” — not found at this position in the current revision</p>'), rest);
  assert.equal(rest.includes('<b>bold</b>'), false);
  assert.equal(count(section, 'not found at this position'), 1);
  assert.ok(rest.includes('<small class="check-source">No exact source passage is linked to this candidate.</small>'));
  // never selectable: no candidate gains a decision control
  for (const proposal of doc.assessment.proposals.filter(p => p.bucket === 'alternative')) {
    assert.equal(html.includes(`data-proposal="${proposal.id}"`), false, proposal.code);
  }
  assert.ok(section.includes('Candidates and alternatives cannot be approved.'));
});

test('candidate grouping reads only served fields, and keeps the flat list when no documented-service reading was recorded', () => {
  const doc = candidatesDoc();
  const groups = app.candidateGroups(doc.assessment);
  assert.deepEqual(groups.same.map(p => p.code), ['45380']);
  assert.deepEqual(groups.other.map(p => p.code), ['19083', '43235', 'G0121', '<img src=x>']);
  // a document read with no service: every candidate is outside the documented services
  const none = app.candidateGroups({ ...doc.assessment, services: { services: [] } });
  assert.deepEqual([none.same.length, none.other.length], [0, 5]);
  const noneHtml = render({ ...doc, assessment: { ...doc.assessment, services: { services: [] } } });
  assert.equal(noneHtml.includes('Same GI family as a documented service'), false);
  assert.ok(noneHtml.includes('Outside the documented services or not a CPT code · 5'));
  // an assessment from before the reading existed (no services list): the list is drawn as before, ungrouped
  for (const services of [undefined, null, {}]) {
    assert.equal(app.candidateGroups({ ...doc.assessment, services }), null);
    const flat = render({ ...doc, assessment: { ...doc.assessment, services } });
    assert.ok(flat.includes('<h2>Alternatives (never selectable)</h2><span class="small-badge">5</span>'));
    assert.equal(flat.includes('candidate-group') || flat.includes('Same GI family'), false);
    assert.equal(count(flat.slice(flat.indexOf('Alternatives (never selectable)')), 'class="check-item muted"') >= 5, true);
  }
  assert.equal(app.candidateGroups({ proposals: [] }), null);
  // excluded candidates are not regrouped
  assert.ok(render(excludedDoc({})).includes('Excluded candidates'));
});

// --- harness@1 (HARNESS.md 7): the Review participants card, a code card's three statuses, the owner's trace ---------

const HARNESS_READY = 'encounter-harness-ready.json';
const HARNESS_DEGRADED = 'encounter-harness-degraded.json';
const HARNESS_TRACE = 'trace-harness-ready.json';
const XSS = '<img src=x onerror="window.__xss=11">';
const XSS_ESCAPED = '&lt;img src=x onerror=&quot;window.__xss=11&quot;&gt;';
// Descriptor-like wording made up for these tests (never an AMA descriptor): the plural mark and "; with".
const DESCRIPTOR = 'Fixture endoscopy, flexible; with removal of lesion(s) by fixture technique';

// The Review participants card of a rendered page, from its opening tag to the first element after it.
function participantsCard(html) {
  const start = html.indexOf('<div class="check-list-card participants-card">');
  assert.ok(start >= 0, 'no Review participants card');
  const end = [html.indexOf('<div class="check-list-card progress-card"', start), html.indexOf('<div class="clarification-card">', start),
    html.indexOf('<div class="result-tabs"', start), html.indexOf('</section>', start)].filter(at => at > start);
  return html.slice(start, Math.min(...end));
}

// One row of the card: the check-item whose data-participant is key.
function harnessRow(html, key) {
  const card = participantsCard(html);
  const start = card.indexOf(`data-participant="${key}"`);
  assert.ok(start >= 0, `no ${key} row`);
  const from = card.lastIndexOf('<div class="check-item', start);
  const next = card.indexOf('<div class="check-item', start);
  return card.slice(from, next > 0 ? next : card.length);
}

function withParticipant(doc, name, fields) {
  const participants = doc.harness.participants.map(item => (item.name === name ? { ...item, ...fields } : item));
  return { ...doc, harness: { ...doc.harness, participants } };
}

function codeCardOf(html, code) {
  const cards = [...html.matchAll(/<article class="code-card"[\s\S]*?<\/article>/g)].map(match => match[0]);
  const card = cards.find(item => item.includes(`<strong class="code-number">${code}</strong>`));
  assert.ok(card, `no code card for ${code}`);
  return card;
}

const textOf = html => html.replace(/<[^>]*>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>').replace(/&amp;/g, '&');

test('the progress card names Corti\'s stage and each participant\'s, and says when a participant is not configured', () => {
  const processing = fixture('encounter-processing.json');
  const html = render(processing);
  const labels = ['Read the original document', 'Identify documented services and context', 'Corti: request CPT proposals',
    'Independent review: Astra (OpenAI GPT-6 Astra)', 'Independent review: Fable (Anthropic Claude Fable 5.1)',
    'Check proposals against references and reconcile'];
  assert.deepEqual(app.STAGES.map(([, label]) => label), labels);
  const at = labels.map(label => html.indexOf(`<strong>${label}</strong>`));
  assert.ok(at.every(index => index > 0) && at.every((index, i) => i === 0 || index > at[i - 1]), JSON.stringify(at));
  assert.ok(html.includes('<strong>Corti: request CPT proposals</strong><p>In progress</p>'));
  assert.ok(html.includes('<strong>Independent review: Astra (OpenAI GPT-6 Astra)</strong><p>Not started</p>'));
  // a participant not configured on this installation never reads "Not started"
  const off = withParticipant(processing, 'fable', { state: 'not_configured', detail: '' });
  assert.ok(render(off).includes('<strong>Independent review: Fable (Anthropic Claude Fable 5.1)</strong><p>Not configured on this installation</p>'));
  // the latest job of a participant stage is shown as any other stage's
  const running = { ...processing, pipeline: { ...processing.pipeline, stages: [...processing.pipeline.stages.slice(0, 2),
    { kind: 'predict', state: 'succeeded', error: '' }, { kind: 'astra', state: 'failed', error: 'HTTP 429 from OpenAI (synthetic).' }] } };
  assert.ok(render(running).includes('<strong>Independent review: Astra (OpenAI GPT-6 Astra)</strong><p>Failed — HTTP 429 from OpenAI (synthetic).</p>'));
  // a payload served before the harness has no participant rows, unless such a stage ran
  const { harness, ...legacy } = processing;
  assert.equal(render(legacy).includes('Independent review'), false);
  const legacyStage = { ...legacy, pipeline: { ...legacy.pipeline, stages: [...legacy.pipeline.stages, { kind: 'fable', state: 'queued', error: '' }] } };
  assert.ok(render(legacyStage).includes('<strong>Independent review: Fable (Anthropic Claude Fable 5.1)</strong><p>Waiting</p>'));
  assert.equal(render(legacyStage).includes('Independent review: Astra'), false);
});

test('the Review participants card heads the review column while processing, before any assessment', () => {
  const processing = fixture('encounter-processing.json');
  assert.equal(processing.assessment, null);
  const html = render(processing);
  const card = participantsCard(html);
  const column = html.indexOf('<section class="review-column"');
  assert.ok(column < html.indexOf(card) && html.indexOf(card) < html.indexOf('class="check-list-card progress-card"'), 'the card heads the column');
  assert.ok(card.includes('<h2>Review participants</h2>'));
  // the classes the walk and the other cards are found by are never the card's own
  for (const name of ['progress-card', 'clarification-card', 'card-empty']) assert.equal(card.includes(name), false, name);
  assert.deepEqual([...card.matchAll(/data-participant="([^"]+)" data-state="([^"]*)"/g)].map(match => [match[1], match[2]]),
    [['corti', 'running'], ['astra', 'waiting'], ['fable', 'waiting'], ['reference_validation', 'waiting'], ['clarification', 'waiting'], ['final', 'processing']]);
  assert.ok(harnessRow(html, 'corti').includes('<span class="status amber">In progress</span>'));
  assert.ok(harnessRow(html, 'astra').includes('<p>Waiting for its turn; nothing has been sent yet.</p>'));
  assert.ok(harnessRow(html, 'reference_validation').includes('Runs once the participants have answered'));
  assert.ok(harnessRow(html, 'clarification').includes('<span class="status gray">Waiting</span>'));
  assert.ok(harnessRow(html, 'final').includes('<span class="status gray">Processing</span>'));
  // persistent: the same card heads a finished review, a degraded one and a stopped one
  for (const doc of [fixture(HARNESS_READY), fixture(HARNESS_DEGRADED), { ...fixture(HARNESS_READY), state: 'stopped', pipeline: { ...fixture(HARNESS_READY).pipeline, can_resume: true } }]) {
    const page = render(doc);
    assert.equal(count(page, 'class="check-list-card participants-card"'), 1, doc.id);
    assert.ok(page.indexOf('participants-card') < page.indexOf('role="tablist"'), doc.id);
  }
});

test('every participant state has its label and plain sentence; the API\'s own sentence is kept, after the plain one only where it does not say it', () => {
  const ready = fixture(HARNESS_READY);
  const states = Object.entries(app.PARTICIPANT_STATES);
  assert.deepEqual(states.map(([name]) => name).sort(),
    ['blocked', 'done', 'failed', 'not_configured', 'not_sent', 'refused', 'running', 'stopped', 'unknown', 'waiting']);
  for (const [name, [[tone], label, plain, required]] of states) {
    const row = detail => harnessRow(render(withParticipant(ready, 'astra', { state: name, detail })), 'astra');
    const bare = row('');
    assert.ok(bare.includes(`data-state="${name}"`), name);
    assert.ok(bare.includes(`>${app.escapeHtml(label)}</span>`), `${name}: label`);
    assert.ok(bare.includes(`<p>${app.escapeHtml(plain)}</p>`), `${name}: plain sentence`);
    assert.ok(bare.startsWith(`<div class="check-item${tone ? ` ${tone}` : ''}"`), `${name}: tone`);
    const other = row('A sentence of the API\'s own.');
    assert.ok(other.includes('<p>A sentence of the API&#x27;s own.</p>'), name);
    assert.equal(other.includes(`<p>${app.escapeHtml(plain)}</p>`), Boolean(required), `${name}: plain kept only where it must be said`);
    if (required) assert.equal(row(`Something ${required} here.`).includes(`<p>${app.escapeHtml(plain)}</p>`), false, `${name}: said already`);
  }
  // the three the directive names, as they read
  const names = render(withParticipant(ready, 'fable', { state: 'not_configured', detail: '' }));
  assert.ok(harnessRow(names, 'fable').includes('<p>Not configured on this installation.</p>'));
  const unknown = harnessRow(render(withParticipant(ready, 'fable', { state: 'unknown', detail: 'Sent; no response was recorded.' })), 'fable');
  assert.ok(unknown.includes('<p>Outcome unknown — reconcile before sending again.</p><p>Sent; no response was recorded.</p>'), unknown);
  const refused = harnessRow(render(fixture(HARNESS_DEGRADED)), 'astra');
  assert.ok(refused.includes('<p>Answered; the reading was not used: the response was cut off at the output limit.</p>'), refused);
  assert.equal(count(refused, '<p>'), 1, 'said once');
  assert.ok(refused.includes('<span class="status amber">Reading not used</span>'));
  // a state the page does not know is never drawn as one it knows
  const odd = harnessRow(render(withParticipant(ready, 'astra', { state: 'exploded', detail: '' })), 'astra');
  assert.ok(odd.includes('State not recorded') && odd.includes('data-state="exploded"'));
});

// The note jobs.retrieval_failure records for a retrieval that raised (refutation round 1, parity-1), as served.
const RETRIEVAL_NOTE = 'Reference validation failed: CPT Studio could not retrieve the CMS facts and passages for this assessment\'s codes (RuntimeError, logged), so none is recorded here and no proposal was checked against them. Retrieval only informs the reviewer and decides no status, so the assessment stands as made.';

test('a failed retrieval is shown as failed - in the reference row, on each code card and in the owner\'s trace - never as not run or done', () => {
  const ready = fixture(HARNESS_READY);
  const failed = { ...ready.harness.reference_validation, state: 'failed', detail: RETRIEVAL_NOTE, codes_checked: 0, passages: 0, sources: [] };
  const doc = { ...ready, harness: { ...ready.harness, reference_validation: failed },
    assessment: { ...ready.assessment, proposals: ready.assessment.proposals.map(proposal => ({ ...proposal, retrieval: [] })) } };
  const html = render(doc);
  const [[tone], label, plain, required] = app.REFERENCE_STATES.failed;
  assert.equal(required, 'failed');
  const row = harnessRow(html, 'reference_validation');
  assert.ok(row.startsWith(`<div class="check-item ${tone}" data-participant="reference_validation" data-state="failed">`), row);
  assert.ok(row.includes(`<span class="status amber">${label}</span>`), row);
  assert.ok(row.includes(`<p>${app.escapeHtml(RETRIEVAL_NOTE)}</p>`), row);
  assert.equal(count(row, '<p>'), 1, 'said once: the API\'s own sentence says it failed');
  for (const other of ['Not run', 'Done', app.REFERENCE_STATES.not_run[2], 'checked against the CMS reference files;']) assert.equal(row.includes(other), false, other);
  assert.ok(row.includes('Not connected: NCCI procedure-to-procedure edits'), 'what is not connected is still listed');
  // a detail that does not say it failed follows the plain sentence; none at all (or a payload without it) is the plain one
  const said = detail => harnessRow(render({ ...doc, harness: { ...doc.harness, reference_validation: { ...failed, detail } } }), 'reference_validation');
  assert.ok(said('Synthetic reason.').includes(`<p>${app.escapeHtml(plain)}</p><p>Synthetic reason.</p>`), said('Synthetic reason.'));
  for (const detail of ['', '  ', undefined, null]) {
    const bare = said(detail);
    assert.ok(bare.includes(`<p>${app.escapeHtml(plain)}</p>`) && count(bare, '<p>') === 1 && bare.includes('data-state="failed"'), String(detail));
  }
  // a state other than failed never shows the detail, so a stray one cannot say failed for it
  const done = harnessRow(render({ ...ready, harness: { ...ready.harness, reference_validation: { ...ready.harness.reference_validation, detail: RETRIEVAL_NOTE } } }), 'reference_validation');
  assert.ok(done.includes('data-state="done"') && !done.includes('Reference validation failed'), done);
  // each code card says the retrieval failed, never that its own lookup found nothing
  for (const proposal of doc.assessment.proposals) {
    const card = codeCardOf(html, proposal.code);
    assert.ok(card.includes(`<p class="harness-note">${app.escapeHtml(app.RETRIEVAL_FAILED)}</p>`), proposal.code);
    assert.equal(card.includes('No CMS reference fact or passage was retrieved for this code.'), false, proposal.code);
  }
  assert.ok(app.retrievalSection({ retrieval: [] }, false, true).includes(app.escapeHtml(app.RETRIEVAL_FAILED)));
  // the owner's trace: the one failed entry (no code) is shown as failed with its note, never as a code with nothing found
  const trace = fixture(HARNESS_TRACE);
  const entry = { code: '', service_date: '2026-10-21', facts: [], passages: [], lookups: [], notes: [RETRIEVAL_NOTE], failed: true };
  const traced = app.traceView({ ...trace, retrieval: [entry] }, trace.encounter.id);
  assert.ok(traced.includes(`<div class="check-list-card"><div class="evidence-label">Reference validation failed</div><p class="harness-note">${app.escapeHtml(RETRIEVAL_NOTE)}</p></div>`), traced);
  for (const other of ['No fact was found for this code.', 'Code · service date', 'No retrieval trace is recorded']) assert.equal(traced.includes(other), false, other);
  const unnoted = app.traceView({ ...trace, retrieval: [{ ...entry, notes: [] }] }, trace.encounter.id);
  assert.ok(unnoted.includes(`<div class="evidence-label">Reference validation failed</div><p class="harness-note">${app.escapeHtml(plain)}</p>`), unnoted);
});

test('a participant row says what it proposed, its unfound quotes, a reused answer and the model asked for and the one that answered', () => {
  const ready = fixture(HARNESS_READY);
  const html = render(ready);
  assert.ok(harnessRow(html, 'corti').includes('<small class="check-source">Codes it proposed: 45385, 45380.</small>'));
  const astra = harnessRow(html, 'astra');
  assert.ok(astra.includes('1 quote it gave was not found in the document text, so never used as evidence.'));
  assert.ok(astra.includes('Model requested: gpt-6-astra; answered by gpt-6-astra.'));
  assert.equal(harnessRow(html, 'corti').includes('Model'), false, 'Corti\'s API names no model');
  const reused = harnessRow(render(withParticipant(ready, 'fable', { reused: true, unverified_quotes: 2 })), 'fable');
  assert.ok(reused.includes('Reused the stored answer to an identical request; nothing new was sent.'));
  assert.ok(reused.includes('2 quotes it gave were not found in the document text'));
  // codes are listed only for a reading that was used; a waiting participant names its model, not a request
  const refused = harnessRow(render(withParticipant(ready, 'astra', { state: 'refused', codes: ['45385'], returned_model: '' })), 'astra');
  assert.equal(refused.includes('Codes it proposed'), false);
  assert.ok(refused.includes('Model: gpt-6-astra.'));
  assert.ok(harnessRow(render(withParticipant(ready, 'fable', { state: 'done', codes: [] })), 'fable').includes('It proposed no code.'));
});

test('the reference validation, clarification and final status rows say what the API reports', () => {
  const ready = fixture(HARNESS_READY);
  const html = render(ready);
  const reference = harnessRow(html, 'reference_validation');
  assert.ok(reference.includes('<p>2 codes checked against the CMS reference files; 3 passages of verbatim CMS text retrieved.</p>'));
  assert.ok(reference.includes('CMS NCCI Policy Manual 2026, Chapter VI (fixture) (Revision 1/1/2026) · effective 1 Jan 2026 – 31 Dec 2026'));
  assert.ok(reference.includes('Not connected: NCCI procedure-to-procedure edits (AMA licence agreement not accepted); AMA CPT descriptors and guidelines (no licence); Payer policies.'));
  const notRun = harnessRow(render({ ...ready, harness: { ...ready.harness, reference_validation: { state: 'not_run' } } }), 'reference_validation');
  assert.ok(notRun.includes('<span class="status gray">Not run</span>') && notRun.includes('No proposal was checked against the CMS references for this revision.'));
  assert.ok(harnessRow(render({ ...ready, harness: { ...ready.harness, reference_validation: null } }), 'reference_validation').includes('data-state="not_run"'));
  // clarification: the API's count of open questions; with no assessment, waiting only while a stage runs
  assert.ok(harnessRow(html, 'clarification').includes('<span class="status green">None open</span>'));
  const failed = fixture('encounter-extraction-failed.json');
  const unread = harnessRow(render({ ...failed, harness: { ...ready.harness, reference_validation: { state: 'not_run' }, final: { state: failed.state, label: failed.state_label } } }), 'clarification');
  assert.ok(unread.includes('data-state="not_run"') && unread.includes('<span class="status gray">Not asked</span>'), unread);
  assert.ok(unread.includes('No question was asked: the proposals were not checked for this revision.'));
  assert.equal(unread.includes('Waiting'), false);
  const asked = harnessRow(render({ ...ready, harness: { ...ready.harness, clarification: { open: 2 } } }), 'clarification');
  assert.ok(asked.includes('<span class="status amber">2 open</span>') && asked.includes('2 questions need an answer before the reviewed report'));
  assert.ok(asked.includes('A participant&#x27;s own questions never hold the reviewed report.'));
  // final: the list's own label and tone, approval kept apart from agreement
  const final = harnessRow(html, 'final');
  assert.ok(final.includes('<span class="status green">Ready for review</span>'));
  assert.ok(final.includes('A code is approved only by a workspace member&#x27;s decision; agreement between participants approves nothing.'));
  assert.ok(harnessRow(render(fixture(HARNESS_DEGRADED)), 'final').includes('<span class="status amber">Provider outcome unknown</span>'));
  const reviewed = { ...ready, coding_state: 'incomplete', readiness: { draft: true, reviewed: true, blockers: [] },
    harness: { ...ready.harness, final: { state: 'reviewed', label: 'Reviewed' } },
    assessment: { ...ready.assessment, proposals: ready.assessment.proposals.map(p => ({ ...p, decision_state: 'approved', decision: { action: 'approve', reviewer: 'Review Agent', reviewer_kind: 'agent' } })) } };
  const done = harnessRow(render(reviewed), 'final');
  assert.ok(done.includes('<span class="status amber">Reviewed · coding incomplete</span>'), done);
  assert.ok(done.includes('Every selected code has a reviewer&#x27;s decision. Includes agent-executed synthetic review — not clinical approval.'));
});

test('the trace link is shown to the owner only, and a payload served before the harness draws no card', () => {
  const ready = fixture(HARNESS_READY);
  const link = `href="#/encounters/${ready.id}/trace"`;
  assert.equal(count(render(ready), link), 1);
  for (const permissions of [{ can_review: true, is_owner: false }, { can_review: true }, { can_review: false, is_owner: 'yes' }]) {
    assert.equal(render({ ...ready, permissions }).includes('/trace"'), false, JSON.stringify(permissions));
  }
  assert.equal(render(fixture(HARNESS_DEGRADED)).includes('/trace"'), false, 'a reviewer is not the owner');
  for (const name of ['encounter-ready.json', 'encounter-reviewed.json', 'encounter-clarification.json', 'encounter-adversarial.json', 'encounter-stopped.json']) {
    const html = render(fixture(name));
    assert.equal(html.includes('participants-card') || html.includes('data-participant='), false, name);
  }
  for (const harness of [null, {}, { participants: 'all' }]) assert.equal(app.participantsCard({ ...ready, harness }), '', JSON.stringify(harness));
});

test('a code card keeps who proposed it, the CMS reference checks and the reviewer decision as three separate lines', () => {
  const ready = fixture(HARNESS_READY);
  const html = render(ready);
  const snare = codeCardOf(html, '45385');
  const lines = /<ul class="code-status-lines" aria-label="Status of this code">([\s\S]*?)<\/ul>/.exec(snare);
  assert.ok(lines, snare.slice(0, 1500));
  assert.deepEqual([...lines[1].matchAll(/<li>([\s\S]*?)<\/li>/g)].map(match => textOf(match[1]).replace(/\s+/g, ' ').trim()), [
    'Proposed by: Corti, Astra, Fable',
    'CMS reference checks: passed — Present in the fee schedule for the service date; 1 unit is within the MUE. (NCCI procedure-to-procedure edits not verified: not connected)',
    'Reviewer decision: not decided yet',
  ]);
  assert.ok(codeCardOf(html, '45380').includes('<li><b>CMS reference checks:</b> needs attention — Shares the endoscopic base 45378'));
  // agreement of all three never approves: the badge and the actions are the code's own
  assert.ok(snare.includes('<span class="status green">Ready for review</span>') && snare.includes('data-decision="approve"'));
  const decided = (fields, check = {}) => app.codeStatusLines({ ...ready.assessment.proposals[0], ...fields, reference_check: { state: 'not_verified', ...check } });
  assert.ok(decided({}).includes('<li><b>CMS reference checks:</b> not verified (NCCI procedure-to-procedure edits not verified: not connected)</li>'));
  assert.ok(decided({ decision_state: 'approved', decision: { reviewer: 'Review Agent', reviewer_kind: 'agent' } })
    .includes('<li><b>Reviewer decision:</b> approved by Review Agent (agent-executed synthetic review — not clinical approval)</li>'));
  assert.ok(decided({ decision_state: 'reinstated', decision: { reviewer: 'Reviewer One', reviewer_kind: 'human' } })
    .includes('<li><b>Reviewer decision:</b> reinstated for review by Reviewer One; not approved</li>'));
  // a reviewer's name is text: never a replacement pattern, never markup
  const named = decided({ decision_state: 'rejected', decision: { reviewer: `$& $' ${XSS}`, reviewer_kind: 'human' } });
  assert.ok(named.includes(`rejected by $&amp; $&#x27; ${XSS_ESCAPED}</li>`), named);
  assert.ok(decided({ decision_state: 'undecided', decision: { reviewer: 'Stale' } }).includes('not decided yet</li>'));
  assert.equal(count(decided({}), '<li>'), 3);
  assert.ok(app.codeStatusLines({ proposed_by: [] }).includes('Proposed by:</b> not recorded'));
  // a proposal served before the harness keeps its card as it was
  assert.equal(app.codeStatusLines(fixture('encounter-ready.json').assessment.proposals[0]), '');
  assert.equal(render(fixture('encounter-ready.json')).includes('code-status-lines'), false);
});

test('a code card says what each participant said, with Fable\'s advice not to code and the passage it quoted', () => {
  const html = render(fixture(HARNESS_READY));
  const biopsy = codeCardOf(html, '45380');
  assert.ok(biopsy.includes('<div class="evidence-section participant-positions"><div class="evidence-label">What the participants said</div>'
    + '<p class="harness-note">Astra proposed it.</p><p class="harness-note">Fable advised not to code it: not performed at this encounter — '
    + '“Biopsies of the sigmoid colon are planned at the next colonoscopy.”</p></div>'), biopsy);
  // the contradiction is shown, never voted on: the code stays ready, with its warning check
  assert.ok(biopsy.includes('Ready for review') && biopsy.includes('A participant disagrees'));
  const degraded = codeCardOf(render(fixture(HARNESS_DEGRADED)), '43239');
  assert.ok(degraded.includes('<p class="harness-note">Astra gave no reading: Answered; the reading was not used: the response was cut off at the output limit.</p>'));
  assert.ok(degraded.includes('<p class="harness-note">Fable gave no reading: Outcome unknown — reconcile before sending again.</p>'));
  const positions = participant_positions => app.participantPositions({ participant_positions });
  assert.equal(positions({}), '', 'no participant configured');
  assert.equal(positions(undefined), '');
  const ordered = positions({ fable: { position: 'not_proposed', detail: '', quote: '' }, astra: { position: 'proposed', detail: '', quote: '' } });
  assert.ok(ordered.indexOf('Astra proposed it.') < ordered.indexOf('Fable did not propose it.'), ordered);
});

test('a code card lists the CMS facts and passages retrieved for it, each passage behind its own disclosure', () => {
  const html = render(fixture(HARNESS_READY));
  const snare = codeCardOf(html, '45385');
  assert.ok(snare.includes('<li><b>PFS status:</b> A<small class="check-source">cms-pfs-rvu26d · RVU26D</small></li>'));
  assert.ok(snare.includes('<li><b>Practitioner MUE:</b> 1 (MAI 2)<small class="check-source">cms-mue-practitioner-2026q4 · 2026-Q4</small></li>'));
  assert.ok(snare.includes('<details class="reference-passage"><summary>Multiple procedure indicator 3 · page 12</summary><p>SYNTHETIC FIXTURE TEXT, not CMS text:'));
  assert.ok(snare.includes('<small class="check-source">cms-ncci-policy-manual-2026-ch6 · Revision 1/1/2026 · Chapter VI, section C: Endoscopic Services · page VI-14</small></details>'));
  assert.equal(count(snare, '<details class="reference-passage">'), 2);
  assert.equal(/<details[^>]* open/.test(snare), false, 'collapsed by default');
  assert.ok(app.retrievalSection({ retrieval: [] }).includes('No CMS reference fact or passage was retrieved for this code.'));
  assert.equal(app.retrievalSection({}), '');
  // never marked in the source and never an evidence chip: the walk's DOM checks stay as they were
  const layout = app.documentLayout(fixture(HARNESS_READY));
  const keys = layout.pages.flatMap(page => page.paragraphs.flat()).filter(piece => piece.keys).flatMap(piece => piece.keys);
  assert.deepEqual(keys.sort(), ['d0000000-0000-4000-8000-000000000901:0', 'd0000000-0000-4000-8000-000000000902:0']);
  assert.equal(count(snare, 'evidence-chip'), 1);
  assert.equal(snare.includes('review-insight'), false, 'no decision line before a decision');
});

test('no descriptor-like text is rendered: not the provider\'s display, not a participant\'s free text that reads like a CPT descriptor', () => {
  assert.ok(app.DESCRIPTOR_LIKE.test(DESCRIPTOR));
  for (const plain of ['The rectal polyp was removed with a cold snare.', 'Answered; the reading was not used: the response was cut off at the output limit.',
    'Fable advised not to code it: not performed at this encounter', 'Multiple procedure indicator 3']) {
    assert.equal(app.DESCRIPTOR_LIKE.test(plain), false, plain);
  }
  const ready = fixture(HARNESS_READY);
  const proposals = ready.assessment.proposals.map((proposal, index) => ({ ...proposal, provider_display: `${DESCRIPTOR} ${index}`,
    participant_positions: { astra: { position: 'advised_not_to_code', detail: DESCRIPTOR, quote: '' },
      fable: { position: 'advised_not_to_code', detail: 'not performed at this encounter', quote: `${DESCRIPTOR}.` } } }));
  const doc = { ...ready, assessment: { ...ready.assessment, proposals } };
  const pages = ['codes', 'checks', 'timeline'].map(tab => render(doc, tab)).join('\n');
  assert.equal(pages.includes('lesion(s)') || pages.includes(app.escapeHtml(DESCRIPTOR)), false);
  assert.ok(pages.includes(`Astra advised not to code it: ${app.escapeHtml(app.DESCRIPTOR_WITHHELD)}`));
  assert.ok(pages.includes('Fable advised not to code it: not performed at this encounter — its quote is withheld: it reads like a CPT descriptor.'));
  assert.equal(count(pages, '<h3>Description withheld</h3>'), 2);
  // the trace: every free-text field of a reading, and an unlocated quote
  const trace = fixture(HARNESS_TRACE);
  const reading = trace.participants[1].runs[0].reading;
  const hostile = { ...reading,
    services: reading.services.map(service => ({ ...service, description: DESCRIPTOR, technique: DESCRIPTOR,
      lesions: [{ site: 'rectum', size: '', morphology: '', action: DESCRIPTOR, specimen: '' }] })),
    codes: reading.codes.map(code => ({ ...code, basis: DESCRIPTOR, evidence: [{ quote: DESCRIPTOR, spans: [], reason: 'not found' }] })),
    questions: [{ question: DESCRIPTOR, why: DESCRIPTOR, service_ids: [], evidence: [DESCRIPTOR] }],
    extraction_issues: [{ page: 1, issue: DESCRIPTOR }] };
  const shown = app.traceView({ ...trace, participants: [{ ...trace.participants[1], runs: [{ ...trace.participants[1].runs[0], reading: hostile }] }] }, ready.id);
  assert.equal(shown.includes('lesion(s)'), false, 'a participant\'s descriptor-like text reached the trace');
  assert.ok(count(shown, app.escapeHtml(app.DESCRIPTOR_WITHHELD)) >= 6, shown);
  assert.ok(shown.includes('(a quote withheld: it reads like a CPT descriptor) — unverified (not found); never used as evidence'));
  // every harness surface the fixtures draw: no descriptor-like text at all
  const surfaces = [HARNESS_READY, HARNESS_DEGRADED, 'encounter-processing.json'].flatMap(name => ['codes', 'checks', 'timeline'].map(tab => render(fixture(name), tab)));
  for (const html of [...surfaces, app.traceView(trace, ready.id)]) assert.equal(app.DESCRIPTOR_LIKE.test(textOf(html)), false, textOf(html).match(app.DESCRIPTOR_LIKE)?.[0]);
});

test('the owner\'s trace shows each request in full, each reading, the retrieval traces and the reconciliation', () => {
  const trace = fixture(HARNESS_TRACE);
  const id = trace.encounter.id;
  const html = app.traceView(trace, id);
  assert.ok(html.includes(`<a class="back-link" href="#doc/${id}">`));
  assert.ok(html.includes('<h1>Colonoscopy with polypectomy and biopsy</h1>') && html.includes('<span>Revision 1</span><span>Owner only</span>'));
  for (const field of ['<dt>Endpoint</dt><dd>https://api.openai.com/v1/responses</dd>', '<dt>Model requested</dt><dd>gpt-6-astra</dd>',
    '<dt>Model that answered</dt><dd>gpt-6-astra</dd>', '<dt>Vendor request id</dt><dd>req_fixture0102</dd>', '<dt>Response id</dt><dd>resp_fixture0102</dd>',
    '<dt>HTTP status</dt><dd>200</dd>', '<dt>Latency</dt><dd>41.3 s</dd>',
    '<dt>Usage</dt><dd>input_tokens 4120 · input_tokens_details.cached_tokens 0 · output_tokens 1630 · output_tokens_details.reasoning_tokens 910 · total_tokens 5750</dd>',
    '<dt>Estimated cost</dt><dd>$0.1227 (estimated from published rates, not reconciled to an invoice)</dd>',
    `<dt>Request sha256</dt><dd>${trace.participants[1].runs[0].request_sha256}</dd>`, `<dt>Response sha256</dt><dd>${trace.participants[1].runs[0].response_sha256}</dd>`,
    '<dt>Response bytes</dt><dd>6904</dd>', '<dt>Error</dt><dd>None</dd>', '<dt>Endpoint</dt><dd>https://api.anthropic.com/v1/messages</dd>',
    '<dt>Response id</dt><dd>msg_fixture0103</dd>', '<dt>Usage</dt><dd>creditsConsumed 0.0312</dd>', '<dt>Estimated cost</dt><dd>Not estimated</dd>',
    '<dt>Model requested</dt><dd>None named</dd>']) {
    assert.ok(html.includes(field), field);
  }
  // each normalized reading, its unverified quotes included
  assert.ok(html.includes('<dt>Unverified quotes</dt><dd>1 (never used as evidence)</dd>'));
  assert.ok(html.includes('<dt>Date of service as read</dt><dd>2026-10-28</dd>'));
  assert.ok(html.includes('<li><b>s1 · colonoscopy · performed</b><br>Description: Colonoscopy to the cecum, completed'));
  assert.ok(html.includes('<li><b>45380 · units 1 · confidence medium · services s1</b><br>Basis: The transverse colon lesion was sampled with biopsy forceps.'));
  assert.ok(html.includes('<li>“Two biopsies were taken from the lesion.” — unverified (not found in the document text); never used as evidence</li>'));
  assert.ok(html.includes('<li>“A 6 mm sessile polyp in the rectum was removed with a cold snare.” — found in the document (1 place)</li>'));
  assert.ok(html.includes('<li><b>45380 · not performed at this encounter · services s1</b>'));
  assert.ok(html.includes('<li><b>Was the transverse colon lesion sampled at this encounter, or is that planned too?</b><br>Why: '));
  assert.ok(html.includes('Extraction issues · 0') && html.includes('No participant reading is recorded for this request.'));
  // the retrieval traces
  assert.ok(html.includes('<div class="evidence-label">45385 · service date 28 Oct 2026</div>'));
  assert.ok(html.includes(`<li><b>mult_proc: 3</b><small class="check-source">cms-pfs-rvu26d · RVU26D · effective 1 Oct 2026 – 31 Dec 2026 · sha256 ${trace.retrieval[0].facts[0].sha256}</small></li>`));
  assert.ok(html.includes(' · mai 2</small>'), 'a field the trace adds is shown, not dropped');
  assert.ok(html.includes(`passage mult-proc-3 · topic pfs.mult_proc = 3 · sha256 ${trace.retrieval[0].passages[0].sha256}`));
  assert.ok(html.includes('<li>pfs 45385 2026-10-28</li>') && html.includes('<li>NCCI procedure-to-procedure edits are not connected, so code pairs are not verified.</li>'));
  // the reconciliation: four statements per code, never one
  const reconciliation = html.slice(html.indexOf('<h2>Reconciliation</h2>'));
  for (const line of ['<p>Proposed by: Corti, Astra</p>', '<p>Astra proposed it.</p>',
    '<p>Fable advised not to code it: not performed at this encounter — “Biopsies of the sigmoid colon are planned at the next colonoscopy.”</p>',
    '<p>CMS reference checks: needs attention — Shares the endoscopic base 45378', '<p>Reviewer approval: not approved</p>']) {
    assert.ok(reconciliation.includes(line), line);
  }
  const approved = app.traceView({ ...trace, reconciliation: [{ ...trace.reconciliation[0], approved: true, positions: { astra: 'proposed' }, reference_check: 'passed' }] }, id);
  assert.ok(approved.includes('<p>Reviewer approval: approved by a workspace member</p>') && approved.includes('<p>Astra proposed it</p>'));
  assert.ok(approved.includes('<p>CMS reference checks: passed (NCCI procedure-to-procedure edits not verified: not connected)</p>'));
  // a reading refused whole says so, with its problems
  const refused = { ...trace.participants[1].runs[0], reading: { refused: true, problems: ['The response was cut off at the output limit (max_output_tokens).'], unverified_quotes: 0 } };
  const shown = app.traceView({ ...trace, participants: [{ ...trace.participants[1], runs: [refused] }] }, id);
  assert.ok(shown.includes('<dt>Reading</dt><dd>Refused whole: none of it was read or used</dd>') && shown.includes('<li>The response was cut off at the output limit (max_output_tokens).</li>'));
  // whatever the payload, the page is drawn and says what is missing
  for (const payload of [{}, null, { participants: 'x', retrieval: {}, reconciliation: [null] }]) {
    const empty = app.traceView(payload, id);
    assert.ok(empty.includes('No retrieval trace is recorded for this assessment.') && empty.includes('No reconciliation is recorded for this assessment.'), JSON.stringify(payload));
  }
  assert.ok(app.traceView({ ...trace, participants: [{ ...trace.participants[2], runs: [] }] }, id).includes('No request is recorded for this participant on this revision.'));
});

test('every harness value the page draws is escaped', () => {
  const ready = fixture(HARNESS_READY);
  // a participant the page does not know is titled from what the API serves for it
  const stranger = { ...ready.harness.participants[1], name: XSS, label: XSS, vendor: XSS, state: XSS, detail: XSS, run_id: XSS };
  const harness = { ...ready.harness,
    participants: [...ready.harness.participants.map(item => ({ ...item, detail: XSS, model: XSS, returned_model: XSS, codes: [XSS], label: XSS, name: item.name })), stranger],
    reference_validation: { ...ready.harness.reference_validation, sources: [{ key: XSS, title: XSS, release: XSS, effective_start: XSS, effective_end: XSS }], not_connected: [XSS] },
    final: { state: XSS, label: XSS } };
  const proposals = ready.assessment.proposals.map(proposal => ({ ...proposal, proposed_by: [XSS, 'corti'],
    participant_positions: { [XSS]: { position: XSS, detail: XSS, quote: XSS } }, reference_check: { state: XSS, detail: XSS },
    retrieval: [{ kind: 'fact', source_key: XSS, release: XSS, label: XSS, value: XSS, page: XSS, section: XSS, text: XSS },
      { kind: 'passage', source_key: XSS, release: XSS, label: XSS, value: XSS, page: XSS, section: XSS, text: XSS }] }));
  const doc = { ...ready, id: XSS, harness, assessment: { ...ready.assessment, proposals }, provider_runs: ready.provider_runs.map(run => ({ ...run, requested_model: XSS, returned_model: XSS })) };
  const trace = fixture(HARNESS_TRACE);
  const run = { ...trace.participants[1].runs[0], endpoint: XSS, request_id: XSS, error: XSS, usage: { [XSS]: XSS } };
  const html = [render(doc, 'codes'), render(doc, 'timeline'),
    app.traceView({ encounter: { title: XSS }, revision: 1, participants: [{ name: XSS, label: XSS, vendor: XSS, model: XSS, runs: [run] }],
      retrieval: [{ code: XSS, service_date: XSS, facts: [{ field: XSS, value: XSS, [XSS]: XSS }], passages: [{ section: XSS, text: XSS, topic: XSS }], lookups: [XSS], notes: [XSS] }],
      reconciliation: [{ code: XSS, family: XSS, status: XSS, proposed_by: [XSS], positions: { [XSS]: XSS }, reference_check: { state: XSS, detail: XSS } }] }, XSS),
    app.traceFailure(XSS, { status: 500, message: XSS })].join('\n');
  assert.equal(html.includes('<img'), false);
  assert.ok(count(html, XSS_ESCAPED) > 20);
  assert.ok(render(doc).includes(`href="#/encounters/${app.escapeHtml(encodeURIComponent(XSS))}/trace"`));
});

test('the trace refuses plainly: a 403 says the trace is the owner\'s, with nothing to retry', async () => {
  const id = fixture(HARNESS_READY).id;
  const refused = app.traceFailure(id, { status: 403, message: 'The request was refused. Reload the page and try again.' });
  assert.ok(refused.includes('<strong>The trace is for the workspace owner.</strong><br>Only the owner of this workspace can open the trace of a document'));
  assert.ok(refused.includes(`href="#doc/${id}"`));
  assert.equal(refused.includes('data-action="retry"') || refused.includes('Reload the page'), false);
  assert.ok(app.traceFailure(id, { status: 404 }).includes('This document is not available.'));
  const broken = app.traceFailure(id, { status: 500, message: 'The request failed (HTTP 500).' });
  assert.ok(broken.includes('The request failed (HTTP 500).') && broken.includes('data-action="retry"'));
  // through the page's own api() client and route token, with a stubbed fetch and #main
  const main = { innerHTML: '' };
  const saved = { document: global.document, fetch: global.fetch };
  const reply = (status, body) => ({ status, ok: status >= 200 && status < 300, redirected: false, url: `http://127.0.0.1/api/encounters/${id}/trace`,
    headers: { get: () => 'application/json' }, json: async () => body });
  const asked = [];
  try {
    global.document = { querySelector: selector => (selector === '#main' ? main : null), cookie: '' };
    global.fetch = async (url, init) => { asked.push([url, init.method]); return reply(403, { error: 'Only the workspace owner can open the trace.' }); };
    app.state.routeToken = 41;
    await app.showTrace(id, 41);
    assert.deepEqual(asked, [[`/api/encounters/${id}/trace`, 'GET']]);
    assert.ok(main.innerHTML.includes('The trace is for the workspace owner.'), main.innerHTML);
    global.fetch = async () => reply(200, fixture(HARNESS_TRACE));
    await app.showTrace(id, 41);
    assert.ok(main.innerHTML.includes('<span class="eyebrow">TRACE · OWNER ONLY · SYNTHETIC</span>'));
    // a page the member left while the request was out is never drawn over
    let answer;
    global.fetch = () => new Promise(resolve => { answer = resolve; });
    const pending = app.showTrace(id, 41);
    app.state.routeToken = 42;
    main.innerHTML = 'another page';
    answer(reply(200, fixture(HARNESS_TRACE)));
    await pending;
    assert.equal(main.innerHTML, 'another page');
    await app.showTrace('not-a-document', 42);
    assert.ok(main.innerHTML.includes('The address does not name a document in this workspace.'));
  } finally {
    global.document = saved.document;
    global.fetch = saved.fetch;
    app.state.routeToken = 0;
  }
});

test('#/encounters/<id>/trace routes to the trace; any other path keeps the existing routes', () => {
  assert.deepEqual(app.parseRoute(`#/encounters/${UUID}/trace`), { name: 'trace', id: UUID });
  for (const hash of ['#trace', '#/encounters//trace', `#/encounters/${UUID}/trace/x`, `#encounters/${UUID}/trace`, `#/encounters/${UUID}`]) {
    assert.deepEqual(app.parseRoute(hash), { name: 'workspace' }, hash);
  }
  assert.deepEqual(app.parseRoute(`#doc/${UUID}`), { name: 'doc', id: UUID });
});

test('a participant\'s requests are named in the Activity tab with the tokens its vendor reported, and on the reconciliation card', () => {
  const degraded = fixture(HARNESS_DEGRADED);
  const timeline = render(degraded, 'timeline');
  assert.ok(timeline.includes('<strong>Corti · live · Succeeded</strong><p>HTTP 200 · 4.4 s · 0.0174 provider-reported credits (not USD)</p>'));
  assert.ok(timeline.includes('<strong>Astra · live · Independent review · Succeeded</strong><p>HTTP 200 · 118.2 s · 3876 input tokens, 16000 output tokens (vendor-reported; basis: vendor_reported_tokens)</p>'));
  assert.ok(timeline.includes('<strong>Fable · live · Independent review · Outcome unknown</strong><p>No HTTP response recorded · Usage not reported</p>'));
  const named = render({ ...degraded, provider_runs: degraded.provider_runs.map(run => ({ ...run, requested_model: run.provider === 'astra' ? 'gpt-6-astra' : '', returned_model: run.provider === 'astra' ? 'gpt-6-astra' : '' })) }, 'timeline');
  assert.equal(count(named, '<p>Model requested: gpt-6-astra; answered by gpt-6-astra.</p>'), 1);
  // the unknown outcome blocks every send for the encounter, and the card names whose it is
  const codes = render(degraded);
  assert.ok(codes.includes('<strong>Unreconciled request</strong><br>Fable (Anthropic Claude Fable 5.1) · 30 Oct 2026, 09:12 UTC · Read timed out after the request was sent.'));
  assert.ok(codes.includes(`id="reconcileForm" data-run="${degraded.provider_runs[2].id}"`));
});

// --- harness@2 (HARNESS.md 11-12): peer reviews, candidates and confirmations, references kept apart, the trace ------
//
// The harness@2 fixtures are the serializer's own output (tests/test_frontend.py generates them from the rows harness@2
// records): peer reviews running, after both peer reviews, and a confirmed finding read by a re-assessment.

const H2_PEER = 'encounter-harness2-peer.json';
const H2_FINAL = 'encounter-harness2-final.json';
const H2_CONFIRMED = 'encounter-harness2-confirmed.json';
const H2_TRACE = 'trace-harness2-final.json';
// HARNESS.md 11.3 and 12.5's attestation, written out here so a page that rebuilt or altered it cannot pass.
const ATTESTATION = value => `I read this passage in the source document; it documents ${value} for this encounter.`;

// One peer-review row of the Review participants card: the check-item whose data-peer is name.
function peerRowOf(html, name) {
  const card = participantsCard(html);
  const start = card.indexOf(`data-peer="${name}"`);
  assert.ok(start >= 0, `no peer-review row for ${name}`);
  const from = card.lastIndexOf('<div class="check-item', start);
  const next = card.indexOf('<div class="check-item', start);
  return card.slice(from, next > 0 ? next : card.length);
}

// One open question's candidate answers and confirmation, by the question's id.
function questionOf(html, id) {
  const start = html.indexOf(`<div class="candidate-answers" data-question="${id}"`);
  assert.ok(start >= 0, `no candidate answers for question ${id}`);
  const end = html.indexOf('<p class="harness-note">A candidate answers nothing', start);
  return html.slice(start, end);
}

const clarificationOf = (doc, fact) => doc.clarifications.find(item => item.fact === fact);

function withPeer(doc, name, peer, fields = {}) {
  return withParticipant(doc, name, { peer, ...fields });
}

test('the progress card shows each peer review and the second assessment after the first, from the current chain\'s jobs', () => {
  const html = render(fixture(H2_PEER));
  const labels = ['Read the original document', 'Identify documented services and context', 'Corti: request CPT proposals',
    'Independent review: Astra (OpenAI GPT-6 Astra)', 'Independent review: Fable (Anthropic Claude Fable 5.1)',
    'First assessment: check the frozen first readings against references', 'Peer review: Astra (OpenAI GPT-6 Astra)',
    'Peer review: Fable (Anthropic Claude Fable 5.1)', 'Second assessment: reconcile both phases (final)'];
  const card = html.slice(html.indexOf('class="check-list-card progress-card"'), html.indexOf('<div class="progress-actions">'));
  assert.deepEqual([...card.matchAll(/<strong>([^<]*)<\/strong><p>([^<]*)<\/p>/g)].map(match => [match[1], match[2]]),
    [...labels.slice(0, 6).map(label => [label, 'Done']), [labels[6], 'In progress'], [labels[7], 'Not started'], [labels[8], 'Not started']]);
  // which assess is which: a peer stage follows the first; the second follows the peer stages; a re-assessment after it
  const job = (kind, state = 'succeeded') => ({ kind, state, error: '', finished_at: null });
  const first = [job('extract'), job('analyze'), job('predict'), job('astra'), job('fable'), job('assess')];
  const final = [...first, job('astra_peer'), job('fable_peer'), job('assess', 'running')];
  assert.deepEqual(app.phasedJobs(final), { assess: final[5], assess2: final[8], astra_peer: final[6], fable_peer: final[7] });
  const again = [...final.slice(0, 8), job('assess'), job('assess', 'queued')];
  assert.equal(app.phasedJobs(again).assess2, again[9], 'a confirmation\'s re-assessment reads as the second');
  // a new chain: its first assessment's peer stages, never the earlier chain's, and no second assessment yet
  const context = [...final.slice(0, 8), job('assess'), job('assess'), job('astra_peer', 'queued')];
  assert.deepEqual(app.phasedJobs(context), { assess: context[9], assess2: null, astra_peer: context[10], fable_peer: null });
  const repredict = [...final.slice(0, 9), job('predict'), job('astra', 'running')];
  assert.deepEqual(app.phasedJobs(repredict), { assess: repredict[5], assess2: repredict[8], astra_peer: repredict[6], fable_peer: repredict[7] });
  assert.deepEqual(app.phasedJobs([]), { assess: null, assess2: null, astra_peer: null, fable_peer: null });
  // a participant not configured says so in its peer row too, never "Not started"
  const peer = fixture(H2_PEER);
  const off = withPeer({ ...peer, pipeline: { ...peer.pipeline, stages: peer.pipeline.stages.filter(stage => stage.kind !== 'fable') } }, 'fable', {}, { state: 'not_configured' });
  assert.ok(render(off).includes('<strong>Peer review: Fable (Anthropic Claude Fable 5.1)</strong><p>Not configured on this installation</p>'));
  // a Corti-only payload (phase 0) and one served before harness@2 have no such rows
  const corti = { ...peer, harness: { ...peer.harness, phase: 0, participants: peer.harness.participants.map(row => ({ ...row, peer: {} })) },
    pipeline: { ...peer.pipeline, stages: peer.pipeline.stages.filter(stage => stage.kind !== 'astra_peer') } };
  for (const doc of [corti, fixture('encounter-processing.json')]) {
    const page = render(doc);
    assert.equal(page.includes('Peer review:') || page.includes('Second assessment'), false, doc.id);
    assert.ok(page.includes('<strong>Check proposals against references and reconcile</strong>'), doc.id);
  }
});

test('the Review participants card shows each participant\'s first reading, then its peer review, in the state the API serves', () => {
  const peer = fixture(H2_PEER);
  const card = participantsCard(render(peer));
  assert.deepEqual([...card.matchAll(/data-(participant|peer)="([^"]+)" data-(?:peer-)?state="([^"]*)"/g)].map(match => [match[1], match[2], match[3]]),
    [['participant', 'corti', 'done'], ['participant', 'astra', 'done'], ['participant', 'fable', 'done'], ['peer', 'astra', 'running'],
      ['peer', 'fable', 'waiting'], ['participant', 'reference_validation', 'waiting'], ['participant', 'clarification', 'open'],
      ['participant', 'final', 'processing']]);
  assert.ok(peerRowOf(render(peer), 'astra').includes('<strong>Peer review: Astra (OpenAI GPT-6 Astra)</strong><span class="status amber">In progress</span>'));
  assert.ok(harnessRow(render(peer), 'astra').includes('Its own tool calls retrieved 1 reference; it says it used 2, 1 of them cited, not retrieved.'));
  const final = render(fixture(H2_FINAL));
  const astra = peerRowOf(final, 'astra');
  assert.ok(astra.includes('<span class="status green">Done</span>') && astra.includes('<p>Answered in peer review, after its first reading was frozen; the review was used.</p>'));
  assert.ok(astra.includes('Codes it proposed after peer review, never independent: 45381.'));
  assert.ok(astra.includes('Its own tool calls retrieved 1 reference; it says it used 2, 1 of them cited, not retrieved.'), 'its peer-review run\'s, not its first reading\'s');
  assert.ok(peerRowOf(final, 'fable').includes('Codes it proposed after peer review, never independent: 45380.'));
  assert.ok(harnessRow(final, 'final').includes('Assessed after peer review: both phases reconciled from source evidence and rules, never by counting agreement.'));
  // every served state has its label and plain sentence; the API's own sentence is kept, after the plain one only where
  // it does not say it
  const ready = fixture(H2_FINAL);
  assert.deepEqual(Object.keys(app.PEER_STATES).sort(), ['blocked', 'done', 'failed', 'not_configured', 'not_run', 'not_sent', 'refused', 'running', 'stopped', 'unknown', 'waiting']);
  for (const [name, [[tone], label, plain, required]] of Object.entries(app.PEER_STATES).filter(([name]) => name !== 'not_run')) {
    const row = detail => peerRowOf(render(withPeer(ready, 'astra', { state: name, detail, run_id: null, codes_added: [], unverified_quotes: 0 })), 'astra');
    const bare = row('');
    assert.ok(bare.includes(`data-peer="astra" data-peer-state="${name}"`), name);
    assert.ok(bare.includes(`>${app.escapeHtml(label)}</span>`) && bare.includes(`<p>${app.escapeHtml(plain)}</p>`), name);
    assert.ok(bare.startsWith(`<div class="check-item${tone ? ` ${tone}` : ''}"`), `${name}: tone`);
    assert.equal(row('Peer review: a sentence of the API\'s own.').includes(`<p>${app.escapeHtml(plain)}</p>`), Boolean(required), name);
  }
  const refused = peerRowOf(render(withPeer(ready, 'fable', { state: 'refused', detail: 'Peer review: answered; the review was not used: The peer review was not used: it was cut off.', run_id: null, codes_added: [], unverified_quotes: 0 })), 'fable');
  assert.ok(refused.includes('<span class="status amber">Review not used</span></span><p>Peer review: answered; the review was not used: The peer review was not used: it was cut off.</p>'), refused);
  // where the API serves none: not configured, waiting while processing reaches it, or not run with why
  const none = (fields, doc = ready) => peerRowOf(render(withPeer(doc, 'astra', {}, fields)), 'astra');
  assert.ok(none({ state: 'not_configured' }).includes('data-peer-state=""') && none({ state: 'not_configured' }).includes('<p>Not configured on this installation.</p>'));
  for (const first of ['refused', 'failed', 'unknown', 'not_sent', 'blocked', 'stopped']) {
    const row = none({ state: first });
    assert.ok(row.includes('<span class="status gray">Not run</span>') && row.includes(`<p>${app.escapeHtml(app.PEER_NOT_RUN)}</p>`), first);
  }
  assert.ok(none({ state: 'done' }, { ...ready, pipeline: { ...ready.pipeline, busy: true } }).includes('<span class="status gray">Waiting</span>'));
  const failedStage = { ...ready, harness: { ...ready.harness, phase: 1 }, pipeline: { ...ready.pipeline, stages: [...ready.pipeline.stages.slice(0, 6), { kind: 'astra_peer', state: 'failed', error: 'HTTP 529 (synthetic).', finished_at: null }] } };
  assert.ok(none({ state: 'done' }, failedStage).includes('<p>No peer review is recorded for this revision. Its peer-review stage: Failed — HTTP 529 (synthetic).</p>'));
  // a state the page does not know is never drawn as one it knows
  const odd = peerRowOf(render(withPeer(ready, 'astra', { state: 'exploded', detail: '' })), 'astra');
  assert.ok(odd.includes('State not recorded') && odd.includes('data-peer-state="exploded"'));
  // a Corti-only payload draws no peer row; nor does one served before harness@2
  const corti = { ...ready, harness: { ...ready.harness, phase: 0, participants: ready.harness.participants.map(row => ({ ...row, peer: {} })) } };
  for (const doc of [corti, fixture(HARNESS_READY), fixture(HARNESS_DEGRADED)]) assert.equal(render(doc).includes('data-peer='), false, doc.id);
});

test('each open question lists its candidate answers: the value, the passage quoted, who located it in which phase, verified or why not', () => {
  const doc = fixture(H2_FINAL);
  const html = render(doc);
  const extent = clarificationOf(doc, 'extent');
  const block = questionOf(html, extent.id);
  assert.deepEqual([...block.matchAll(/data-candidate="([0-9a-f]+)" data-verified="(true|false)"/g)].map(match => [match[1], match[2]]),
    extent.candidates.map(candidate => [candidate.id, String(candidate.verified)]));
  assert.ok(block.includes('<div class="evidence-label">Candidate answers from the participants&#x27; located passages · 2</div>'));
  const [verified, unverified] = extent.candidates;
  assert.ok(block.includes(`<span class="participant-head"><strong>cecum</strong><span class="status green">Verified</span></span><p class="candidate-quote">“The colonoscope was advanced to the cecum.” (page 1)</p><small class="check-source">Located by Astra and Fable in their independent first readings.</small>`), block);
  assert.ok(block.includes('<small class="check-source">Verified: its passage is an exact slice of the document, in no history, plan or indication section, and it names that landmark, which CPT Studio&#x27;s readers read neither as not reached nor as qualified (a negation, an attempt or a doubt). It is still only a candidate: read the passage before confirming it.</small>'));
  assert.ok(block.includes('<span class="status amber">Not verified</span>'));
  assert.ok(block.includes(`<small class="check-source">Not verified, so it cannot be confirmed: ${app.escapeHtml(unverified.why)}</small>`));
  assert.equal(count(block, 'data-action="confirm-finding"'), 1, 'only the verified candidate can be confirmed');
  assert.ok(block.includes(`data-confirm="${verified.id}"`) && !block.includes(`data-confirm="${unverified.id}"`));
  // a passage keeps its line breaks and page; one located after peer review says so
  const status = questionOf(html, clarificationOf(doc, 'performed_status').id);
  assert.ok(status.includes('<p class="candidate-quote">“A 6 mm sessile polyp in the ascending colon was removed with a cold snare and retrieved for\npathology.” (page 2)</p>'));
  assert.ok(status.includes('<small class="check-source">Located by Astra in peer review.</small>'));
  // what a status check established (refutation round 2, EV2-1): the readers read the code's own act, never the section
  // alone
  const statusCandidates = clarificationOf(doc, 'performed_status').candidates;
  assert.equal(count(status, 'CPT Studio&#x27;s readers read its whole sentence as stating that status for the act this code accounts for'),
    statusCandidates.filter(candidate => candidate.verified === true).length);
  assert.equal(status.includes('the check does not read whether it names this code'), false);
  // the date question is the encounter's own card; the others sit with their codes
  assert.ok(html.indexOf(`data-question="${clarificationOf(doc, 'service_date').id}"`) < html.indexOf('<article class="code-card"'));
  assert.ok(codeCardOf(html, '45385').includes(`data-question="${extent.id}"`) && codeCardOf(html, '45380').includes(`data-question="${clarificationOf(doc, 'performed_status').id}"`));
  // the clarification row says a verified candidate can answer a question; the first assessment's questions have none
  assert.ok(harnessRow(html, 'clarification').includes('each is answered with an addendum, or by a reviewer confirming a verified candidate answer.'));
  const peer = render(fixture(H2_PEER));
  assert.equal(peer.includes('candidate-answers') || peer.includes('confirm-finding'), false);
  // a passage that is not at its position in the current revision is flagged, never passed off as found or confirmable
  const moved = { ...doc, clarifications: doc.clarifications.map(item => (item.id === extent.id ? { ...item, candidates: [{ ...verified, spans: [{ ...verified.spans[0], start: verified.spans[0].start + 1 }] }] } : item)) };
  const flagged = questionOf(render(moved), extent.id);
  assert.ok(flagged.includes('” (page 1) — not found at this position in the current revision</p>') && !flagged.includes('confirm-finding'));
  // an unverified candidate whose value CPT Studio cannot state, with no passage, still says so plainly
  const empty = app.candidateAnswers({ id: 'q', candidates: [{ id: 'c', value: '', verified: false, why: 'The value names no landmark CPT Studio reads.', spans: [], located_by: ['fable'], phases: { fable: 'peer_review' } }] }, doc);
  assert.ok(empty.includes('<strong>No value CPT Studio can state</strong>') && empty.includes('<p class="candidate-quote">No passage is cited.</p>'));
  assert.ok(empty.includes('Located by Fable in peer review.') && empty.includes('The value names no landmark CPT Studio reads.'));
  assert.equal(app.candidateAnswers({ id: 'q', candidates: [], confirmation: null }, doc), '');
  assert.equal(app.candidateAnswers({ id: 'q' }, doc), '', 'a question served before harness@2');
});

test('a verified candidate\'s Confirm action shows its served attestation exactly, and only a member the API allows sees it', () => {
  const doc = fixture(H2_FINAL);
  const html = render(doc);
  for (const clarification of doc.clarifications) {
    for (const candidate of clarification.candidates.filter(item => item.verified)) {
      assert.equal(candidate.attestation, ATTESTATION(candidate.value), 'the fixture serves 12.5\'s sentence');
      const control = `<details class="confirm-finding"><summary>Confirm this answer</summary><label class="check-label"><input type="checkbox" data-attest><span>${app.escapeHtml(candidate.attestation)}</span></label><p class="form-error" role="alert" hidden></p><button type="button" class="button primary" data-action="confirm-finding" data-clarification="${clarification.id}" data-confirm="${candidate.id}" disabled>Record my confirmation`;
      assert.ok(html.includes(control), `${clarification.fact} ${candidate.id}`);
    }
  }
  assert.equal(count(html, 'data-action="confirm-finding"'), 5);
  // the served sentence is shown as served, never rebuilt from the value
  const extent = clarificationOf(doc, 'extent');
  const served = { ...doc, clarifications: doc.clarifications.map(item => (item.id === extent.id ? { ...item, candidates: [{ ...item.candidates[0], attestation: 'A sentence the server serves.' }] } : item)) };
  assert.ok(questionOf(render(served), extent.id).includes('<span>A sentence the server serves.</span>'));
  // hidden without can_confirm, while processing, once confirmed, and for a verified candidate served without one
  const variants = {
    viewer: { ...doc, permissions: { ...doc.permissions, can_confirm: false } },
    older: { ...doc, permissions: { can_review: true, is_owner: true } },
    truthy: { ...doc, permissions: { ...doc.permissions, can_confirm: 'yes' } },
    busy: { ...doc, pipeline: { ...doc.pipeline, busy: true } },
    unattested: { ...doc, clarifications: doc.clarifications.map(item => ({ ...item, candidates: item.candidates.map(candidate => ({ ...candidate, attestation: '' })) })) },
  };
  for (const [name, variant] of Object.entries(variants)) {
    const page = render(variant);
    assert.equal(page.includes('confirm-finding'), false, name);
    assert.equal(count(page, 'data-candidate='), 6, `${name}: the candidates are still listed`);
  }
});

test('confirming posts the candidate id and its served attestation once ticked, and shows the result', async () => {
  const doc = fixture(H2_FINAL);
  const extent = clarificationOf(doc, 'extent');
  const [candidate] = extent.candidates;
  const confirmation = fixture(H2_CONFIRMED).confirmations[0];
  const saved = { document: global.document, fetch: global.fetch };
  const toastEl = { textContent: '', classList: { add() {}, remove() {} } };
  const elements = new Map([['#toast', toastEl]]);  // any other element the page's session refresh writes to
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, { textContent: '', hidden: false, options: [{ textContent: '' }] });
    return elements.get(selector);
  };
  const error = { textContent: '', hidden: true };
  const checkbox = { checked: false };
  const box = { querySelector: selector => ({ '.form-error': error, 'input[data-attest]': checkbox }[selector] || null) };
  const attributes = new Set();
  const button = { dataset: { clarification: extent.id, confirm: candidate.id }, disabled: true, closest: () => box,
    toggleAttribute: (name, on) => (on ? attributes.add(name) : attributes.delete(name)), hasAttribute: name => attributes.has(name) };
  const asked = [];
  let answer = { status: 201, body: { ...confirmation, effect: 'reassessment' } };
  try {
    global.document = { querySelector: element, cookie: 'cptstudio_csrf=token123' };
    global.fetch = async (url, init) => {
      asked.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : null, csrf: init.headers['X-CSRFToken'] });
      const reply = url === '/api/session' ? { status: 200, body: fixture('session.json') } : answer;
      return { status: reply.status, ok: reply.status < 300, redirected: false, url: `http://127.0.0.1${url}`, headers: { get: () => 'application/json' }, json: async () => reply.body };
    };
    app.state.doc = doc;
    app.state.route = null;  // nothing is redrawn here: the page's refresh is the route's
    // the checkbox enables the action; nothing is sent until the attestation is ticked
    app.onChange({ target: { checked: true, matches: selector => selector === 'input[data-attest]', closest: () => ({ querySelector: () => button }) } });
    assert.equal(button.disabled, false);
    await app.confirmFinding(button);
    assert.deepEqual(asked, []);
    assert.equal(error.hidden, false);
    assert.equal(error.textContent, 'Tick the attestation first: confirm that you read this passage in the source document.');
    checkbox.checked = true;
    await app.confirmFinding(button);
    assert.deepEqual(asked[0], { url: `/api/encounters/${doc.id}/clarifications/${extent.id}/confirm`, method: 'POST',
      body: { candidate_id: candidate.id, attestation: ATTESTATION('cecum') }, csrf: 'token123' });
    assert.equal(toastEl.textContent, 'Confirmed: extent reached cecum. The codes are being re-checked with the confirmed finding; nothing was approved.');
    assert.equal(error.hidden, true);
    // what is sent is the sentence the API served, never one rebuilt from the value
    app.state.doc = { ...doc, clarifications: doc.clarifications.map(item => (item.id === extent.id ? { ...item, candidates: item.candidates.map(c => ({ ...c, attestation: `A sentence the server serves for ${c.value}.` })) } : item)) };
    asked.length = 0;
    await app.confirmFinding(button);
    assert.deepEqual(asked.filter(item => item.method === 'POST').map(item => item.body), [{ candidate_id: candidate.id, attestation: 'A sentence the server serves for cecum.' }]);
    app.state.doc = doc;
    // a refusal is shown where the member confirmed, and the action can be tried again
    answer = { status: 409, body: { error: 'That question was confirmed already; a question takes one confirmation.' } };
    asked.length = 0;
    await app.confirmFinding(button);
    assert.equal(asked.length, 1);
    assert.equal(error.textContent, 'That question was confirmed already; a question takes one confirmation.');
    assert.equal(button.disabled, false);
    // a candidate the page no longer serves as verified, or a member who may not confirm, sends nothing
    asked.length = 0;
    app.state.doc = { ...doc, permissions: { ...doc.permissions, can_confirm: false } };
    await app.confirmFinding(button);
    app.state.doc = { ...doc, clarifications: doc.clarifications.map(item => ({ ...item, candidates: item.candidates.map(c => ({ ...c, verified: false })) })) };
    await app.confirmFinding(button);
    assert.deepEqual(asked, []);
    assert.equal(error.textContent, 'This answer can no longer be confirmed here. Reload the page.');
  } finally {
    global.document = saved.document;
    global.fetch = saved.fetch;
    app.state.doc = null;
    app.state.session = null;
  }
  // the result says what happened, in both shapes the endpoint is described with
  assert.equal(app.confirmedMessage({ fact: 'service_date', value: '2026-10-21', effect: 'context' }),
    'Confirmed: date of service 2026-10-21 entered as your date, and the codes are being re-checked. Nothing was approved.');
  assert.equal(app.confirmedMessage({ confirmation: { fact: 'extent', value: 'cecum' }, effect: 'reassessment' }),
    'Confirmed: extent reached cecum. The codes are being re-checked with the confirmed finding; nothing was approved.');
  assert.equal(app.confirmedMessage({}), 'Confirmation recorded. Nothing was approved.');
});

test('a confirmed question names whose located passage and which reviewer; agreement is never shown as confirmation', () => {
  const doc = fixture(H2_FINAL);
  const confirmation = fixture(H2_CONFIRMED).confirmations[0];
  const extent = clarificationOf(doc, 'extent');
  // agreement: both participants located the cecum passage, and nothing reads as confirmed
  assert.equal(render(doc).includes('Confirmed from') || render(doc).includes('confirmed-answer'), false);
  const confirmed = { ...doc, clarifications: doc.clarifications.map(item => (item.id === extent.id ? { ...item, confirmation: { ...confirmation, clarification_id: extent.id } } : item)) };
  const block = questionOf(render(confirmed), extent.id);
  assert.ok(block.startsWith(`<div class="candidate-answers" data-question="${extent.id}" data-confirmation="${confirmation.id}">`), block.slice(0, 200));
  assert.ok(block.includes('<strong>Confirmed from Astra&#x27;s and Fable&#x27;s located passage by Synthetic Reviewer: cecum</strong>'));
  assert.ok(block.includes('<p>“The colonoscope was advanced to the cecum.” (page 1)</p>'));
  assert.ok(block.includes(`<p>Attestation recorded: ${app.escapeHtml(ATTESTATION('cecum'))}</p>`));
  assert.ok(block.includes('1 Nov 2026, 09:00 UTC · A confirmed finding is not a decision: each code still needs its own.'));
  assert.equal(block.includes('confirm-finding'), false, 'a question takes one confirmation');
  assert.equal(count(block, 'data-candidate='), 2, 'its candidates are still listed');
  // as the engine words it, whoever located it
  assert.equal(app.confirmedFrom({ located_by: ['fable'], confirmed_by: 'Reviewer One' }), 'Confirmed from Fable\'s located passage by Reviewer One');
  assert.equal(app.confirmedFrom({ located_by: ['fable', 'astra'], confirmed_by: '' }), 'Confirmed from Astra\'s and Fable\'s located passage by a reviewer whose name was not recorded');
  const agent = questionOf(render({ ...confirmed, clarifications: confirmed.clarifications.map(item => (item.id === extent.id ? { ...item, confirmation: { ...item.confirmation, confirmed_by_kind: 'agent' } } : item)) }), extent.id);
  assert.ok(agent.includes('agent-executed synthetic review — not clinical approval'));
});

test('a code card says who proposed it in which phase, 11.4\'s sentence, the confirmed finding, and three separate reference lists', () => {
  const final = fixture(H2_FINAL);
  const html = render(final);
  const biopsy = codeCardOf(html, '45380');
  assert.ok(biopsy.includes('<li><b>Proposed by:</b> Astra (independent reading), Fable (after peer review); Corti did not propose this code.</li>'), biopsy);
  assert.ok(codeCardOf(html, '45385').includes('<li><b>Proposed by:</b> Corti, Astra (independent reading), Fable (independent reading)</li>'));
  assert.equal(html.includes('<span class="small-badge">Proposed after peer review</span>'), false, 'no selected code was first proposed after peer review');
  // a code first proposed after peer review says so and is never called independent; 11.4 holds without phases too
  const peerOnly = { ...final, assessment: { ...final.assessment, proposals: final.assessment.proposals.map(p => (p.code === '45380' ? { ...p, phases: { astra: 'peer_review', fable: 'peer_review' } } : p)) } };
  const later = codeCardOf(render(peerOnly), '45380');
  assert.ok(later.includes('<span class="small-badge">Proposed after peer review</span>') && !later.includes('independent reading'));
  assert.ok(app.codeStatusLines({ proposed_by: ['fable'], reference_check: { state: 'passed' } }).includes('<li><b>Proposed by:</b> Fable; Corti did not propose this code.</li>'));
  assert.ok(html.includes('<strong>45381 · Colonoscopy · proposed after peer review</strong>'), 'the alternative a peer review proposed');
  // the first readings' positions are named as such
  assert.ok(biopsy.includes('<div class="evidence-label">What the participants said in their first readings</div>'));
  // the three kinds of references, apart, in this order
  const at = ['References the participants retrieved (their own tool calls)', 'References the participants say they used', 'CMS reference facts and passages retrieved by the reconciliation']
    .map(label => codeCardOf(html, '45385').indexOf(`<div class="evidence-label">${label}</div>`));
  assert.ok(at.every(index => index > 0) && at[0] < at[1] && at[1] < at[2], JSON.stringify(at));
  const snare = codeCardOf(html, '45385');
  assert.ok(snare.includes('<li><b>Astra · first reading:</b> fact:cms-pfs-rvu26d:45385:mult_proc<small class="check-source">cms_code_facts · cms-pfs-rvu26d · RVU26D · effective 1 Oct 2026 – 31 Dec 2026</small></li>'));
  assert.ok(snare.includes('<li><b>Astra · first reading:</b> ncci-2026-ch6-c-1 — cited, not retrieved: its own tool calls in this run never returned it<small class="check-source">Its use: “A rule this run never retrieved.”</small></li>'));
  assert.ok(snare.includes('<li><b>Astra · peer review:</b> fact:cms-pfs-rvu26d:45385:mult_proc — cited, not retrieved: its own tool calls in this run never returned it'), 'one phase\'s retrieval never counts for another\'s');
  assert.ok(snare.includes('<li><b>Astra · peer review:</b> ncci-2026-ch6-c-1 — retrieved by its own tool calls in this run'));
  // a fact names its code: 45385's fact is not on 45380's card; a policy passage names none
  assert.equal(biopsy.includes('fact:cms-pfs-rvu26d:45385'), false);
  assert.ok(biopsy.includes('ncci-2026-ch6-c-1 (a policy passage, not tied to one code)'));
  const bare = { ...final, harness: { ...final.harness, participants: final.harness.participants.map(row => ({ ...row, references: { retrieved: [], used: [] }, peer_references: { retrieved: [], used: [] } })) } };
  const nothing = codeCardOf(render(bare), '45380');
  assert.ok(nothing.includes('No participant retrieved a reference for this code.') && nothing.includes('No participant cites a reference for this code.'));
  assert.equal(count(nothing, '<details class="reference-passage">'), 1, 'the reconciliation\'s passage stays listed');
  // the confirmed finding the re-assessment read: a fact, never a decision
  const confirmedDoc = fixture(H2_CONFIRMED);
  const confirmedCard = codeCardOf(render(confirmedDoc), '45385');
  assert.ok(confirmedCard.includes('<div class="confirmed-fact">') && confirmedCard.includes('<strong>Confirmed finding, not a decision</strong><br>Extent reached: cecum — confirmed from Astra&#x27;s and Fable&#x27;s located passage by Synthetic Reviewer · “The colonoscope was advanced to the cecum.” (page 1)</span>'), confirmedCard);
  assert.ok(confirmedCard.includes('<li><b>Reviewer decision:</b> not decided yet</li>') && confirmedCard.includes('data-decision="approve"'));
  const unknown = { ...confirmedDoc, confirmations: [] };
  assert.ok(codeCardOf(render(unknown), '45385').includes(`A confirmed finding that is not listed for this revision (${confirmedDoc.confirmations[0].id}).`));
  // a Corti-only payload (phase 0) keeps its cards as harness@1 drew them
  const corti = { ...final, harness: { ...final.harness, phase: 0, participants: final.harness.participants.map(row => ({ ...row, peer: {} })) } };
  const plain = render(corti);
  assert.equal(plain.includes('reference-lists') || plain.includes('in their first readings') || plain.includes('retrieved by the reconciliation'), false);
});

test('the confirmed findings list every confirmation of the revision, after its question has gone, and none is a decision', () => {
  const doc = fixture(H2_CONFIRMED);
  const html = render(doc);
  const section = html.slice(html.indexOf('<h2>Confirmed findings (not decisions)</h2>'), html.indexOf('<h2>Documented services</h2>'));
  assert.ok(section.includes('<strong>Extent reached: cecum</strong><p>Confirmed from Astra&#x27;s and Fable&#x27;s located passage by Synthetic Reviewer · 1 Nov 2026, 09:00 UTC · revision 1</p>'), section);
  assert.ok(section.includes(`<p>Attestation recorded: ${app.escapeHtml(ATTESTATION('cecum'))}</p>`));
  assert.ok(section.includes('<p>The assessment reads it as documented by this passage; it decides no code.</p>'));
  assert.equal(html.includes(`data-question="${doc.confirmations[0].clarification_id}"`), false, 'its question was answered and is gone');
  const date = app.confirmedFindings({ ...doc, confirmations: [{ ...doc.confirmations[0], fact: 'service_date', value: '2026-10-21', spans: [] }] });
  assert.ok(date.includes('<strong>Date of service: 2026-10-21</strong>') && date.includes('It entered as the member&#x27;s date of service, through the encounter context.'));
  assert.equal(app.confirmedFindings(fixture(H2_FINAL)), '');
  assert.equal(app.confirmedFindings(fixture(HARNESS_READY)), '');
});

test('the trace shows each run\'s exchanges and tool calls, each peer review in full, and every assessment\'s frozen list', () => {
  const trace = fixture(H2_TRACE);
  const html = app.traceView(trace, trace.encounter.id);
  const astra = trace.participants.find(item => item.name === 'astra');
  const [first, peer] = astra.runs;
  assert.ok(html.includes('<div class="evidence-label">Peer review · Succeeded</div>') && html.includes('<dt>Purpose</dt><dd>Peer review</dd>'));
  assert.ok(html.includes(`<dt>Run identity (client request id)</dt><dd>${first.run_identity}</dd>`) && html.includes('<dt>Mode</dt><dd>REPLAY — recorded response, not live output</dd>'));
  assert.equal(count(html, '<div class="evidence-label">Exchanges · 2</div>'), 2);
  assert.ok(html.includes('<div class="evidence-label">Exchanges · 1</div>'));
  const call = first.exchanges[0].tool_calls[0];
  assert.ok(html.includes(`<li><b>cms_code_facts (call_1_1)</b><br>Arguments: {&quot;codes&quot;:[&quot;45385&quot;],&quot;date_of_service&quot;:&quot;&quot;}<br>Refs returned: fact:cms-pfs-rvu26d:45385:mult_proc<small class="check-source">result sha256 ${call.result_sha256} · executed 1 Nov 2026, 09:00 UTC</small></li>`));
  assert.ok(html.includes(`<dt>Response sha256</dt><dd>${first.exchanges[1].response_sha256}</dd>`) && html.includes('<dt>Vendor request id</dt><dd>req_astra_2</dd>'));
  assert.ok(html.includes('<p class="harness-note">No tool call in this exchange.</p>'));
  // the peer review: the frozen inputs it was shown, its answers by question id, positions, codes after peer review
  for (const [name, digest] of peer.review.frozen_inputs) assert.ok(html.includes(`<dt>${name}</dt><dd>${digest}</dd>`), name);
  assert.ok(html.includes(`<li><b>Question ${peer.review.answers[0].question_id}</b><br>Answer: cecum<ul class="trace-quotes"><li>“The colonoscope was advanced to the cecum.” — found in the document (1 place)</li></ul></li>`));
  assert.ok(html.includes('<li><b>45380 · supports it</b><br>Why: Participant wording.'));
  assert.ok(html.includes('<li><b>45381 · units 1 · confidence low · services s1 · proposed after peer review, never independent</b>'));
  assert.ok(html.includes('<li><b>fact:cms-pfs-rvu26d:45385:mult_proc — cited, not retrieved</b><br>Its use: Retrieved only by its first reading.</li>'));
  assert.ok(html.includes('<li><b>Question ' + trace.participants[2].runs[1].review.answers[0].question_id + '</b><br>Answer: Cecum, appendiceal orifice seen'), 'the participant\'s own words, in the trace');
  // a first reading's references used, checked against its own run
  assert.ok(html.includes('<li><b>ncci-2026-ch6-c-1 — cited, not retrieved</b><br>Its use: A rule this run never retrieved.</li>'));
  // each assessment of the revision with the frozen phase-1 outputs it recorded
  const assessments = html.slice(html.indexOf('<h2>Assessments of this revision</h2>'), html.indexOf('<h2>Reference retrieval</h2>'));
  assert.ok(assessments.includes('<div class="evidence-label">Phase 1: the frozen first readings · not final</div>'));
  assert.ok(assessments.includes('<div class="evidence-label">Phase 2: after peer review · final · current</div>'));
  for (const [name, digest] of trace.assessments[1].frozen) assert.ok(assessments.includes(`<dt>${name}</dt><dd>${digest}</dd>`), name);
  assert.ok(app.traceView({ ...trace, assessments: [] }, trace.encounter.id).includes('No assessment is recorded for this revision.'));
  // a peer run without its review, a refused review, and a Corti run (no exchanges) say what they are
  const runOf = (fields, base = peer) => app.traceView({ ...trace, participants: [{ ...astra, runs: [{ ...base, ...fields }] }], assessments: undefined }, trace.encounter.id);
  assert.ok(runOf({ review: null }).includes('No peer review is recorded for this request.'));
  assert.ok(runOf({ review: { refused: true, problems: ['The stored response no longer matches its recorded hash; it was not read.'] } }).includes('<dt>Peer review</dt><dd>Refused whole: none of it was read or used</dd>'));
  assert.equal(runOf({}, trace.participants[0].runs[0]).includes('Exchanges ·'), false);
  assert.equal(runOf({ review: null }).includes('Assessments of this revision'), false, 'a trace served without assessments has no such section');
  // a model's free text in a review that reads like a CPT descriptor is withheld
  const hostile = runOf({ review: { ...peer.review, answers: [{ question_id: 'q', settled: true, value: DESCRIPTOR, evidence: [] }],
    positions: [{ code: '45380', position: 'disputes', reason: DESCRIPTOR, evidence: [] }], additional_codes: [{ code: '45381', basis: DESCRIPTOR, evidence: [{ quote: DESCRIPTOR, spans: [], reason: 'not found' }] }],
    references_used: [{ ref: 'x', use: DESCRIPTOR, retrieved: false }] }, exchanges: [{ ...peer.exchanges[0], tool_calls: [{ ...peer.exchanges[0].tool_calls[0], arguments: { topic: DESCRIPTOR } }] }] });
  assert.equal(hostile.includes('lesion(s)'), false);
  assert.ok(count(hostile, app.escapeHtml(app.DESCRIPTOR_WITHHELD)) >= 5, hostile);
});

test('every participant- or document-written harness@2 value the page draws is escaped', () => {
  const doc = fixture(H2_CONFIRMED);
  const final = fixture(H2_FINAL);
  const span = { start: 0, end: 5, text: XSS, page: XSS };
  const exact = { ...final.clarifications[0].candidates[0].spans[0], page: XSS };  // a verified candidate is offered for confirmation
  const candidate = { id: XSS, clarification_id: XSS, fact: XSS, value: XSS, located_by: [XSS, 'astra'], phase: XSS, phases: { [XSS]: XSS, astra: XSS },
    runs: [XSS], spans: [exact], verified: true, why: XSS, attestation: XSS };
  const unverified = { ...candidate, spans: [span], verified: false };
  const confirmation = { ...doc.confirmations[0], id: XSS, fact: XSS, value: XSS, spans: [span], located_by: [XSS], confirmed_by: XSS, attestation: XSS, created_at: XSS, revision_number: XSS };
  const references = { retrieved: [{ ref: XSS, kind: XSS, source_key: XSS, release: XSS, effective_start: XSS, effective_end: XSS, tool: XSS }], used: [{ ref: XSS, use: XSS, retrieved: XSS }] };
  const harness = { ...final.harness, participants: final.harness.participants.map(row => ({ ...row, references, peer_references: references,
    peer: row.name === 'corti' ? {} : { state: XSS, detail: XSS, run_id: XSS, codes_added: [XSS], unverified_quotes: 3 } })) };
  const clarifications = final.clarifications.map(item => ({ ...item, id: XSS, candidates: [candidate, unverified], confirmation: null }));
  const proposals = final.assessment.proposals.map(p => ({ ...p, proposed_by: [XSS, 'astra'], phases: { [XSS]: XSS, astra: XSS }, confirmed: [XSS] }));
  const hostile = { ...final, id: XSS, harness, clarifications, confirmations: [confirmation], assessment: { ...final.assessment, proposals } };
  const confirmed = { ...hostile, clarifications: clarifications.map(item => ({ ...item, confirmation })) };
  const trace = fixture(H2_TRACE);
  const run = trace.participants[1].runs[1];
  const exchange = { turn: XSS, state: XSS, http_status: XSS, latency_ms: XSS, usage: { [XSS]: XSS }, request_sha256: XSS, response_sha256: XSS, provider_request_id: XSS,
    response_id: XSS, error: XSS, tool_calls: [{ call_id: XSS, tool: XSS, arguments: { [XSS]: XSS }, refs: [XSS], result_sha256: XSS, executed_at: XSS }] };
  const review = { ...run.review, review_version: XSS, frozen_inputs: [[XSS, XSS]], problems: [XSS], answers: [{ question_id: XSS, settled: true, value: XSS, evidence: [XSS] }],
    positions: [{ code: XSS, position: XSS, reason: XSS, evidence: [{ quote: XSS, spans: [], reason: XSS }] }], additional_codes: [{ code: XSS, basis: XSS, modifiers: [XSS], service_ids: [XSS], confidence: XSS, evidence: [] }],
    references_used: [{ ref: XSS, use: XSS, retrieved: true }] };
  const pages = [render(hostile, 'codes'), render(confirmed, 'codes'), render({ ...hostile, pipeline: { ...hostile.pipeline, busy: true, stages: [{ kind: XSS, state: XSS, error: XSS }] } }),
    app.traceView({ ...trace, participants: [{ ...trace.participants[1], runs: [{ ...run, mode: XSS, run_identity: XSS, requested_by: XSS, authorization_ref: XSS, exchanges: [exchange], review }] }],
      assessments: [{ id: XSS, created_at: XSS, phase: XSS, final: XSS, current: XSS, frozen: [[XSS, XSS]] }] }, XSS)].join('\n');
  assert.equal(pages.includes('<img'), false);
  assert.ok(count(pages, XSS_ESCAPED) > 60, String(count(pages, XSS_ESCAPED)));
  // the action names its candidate and question escaped, and sends what the API served
  assert.ok(pages.includes(`data-clarification="${XSS_ESCAPED}" data-confirm="${XSS_ESCAPED}"`));
});

test('older payloads draw exactly as they did before harness@2: every review tab and the harness@1 trace', () => {
  // sha256 of what the app.js of harness@2 part A drew (the base this package builds on) for each payload served before
  // harness@2. A deliberate change to an older payload's page updates its digest here, with the reason in the commit.
  const crypto = require('node:crypto');
  const sha = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
  const BASE = {
    'encounter-adversarial.json': ['c1c6968adb5e69c275a469e4ba16e17259d0b46a2d011d2bbf40a7e267e3cad8', '4d23591a4ed51cb05f5cbf3a51c71c72f196c08c5d4b218220491cbf95cff20f', '8054c9b72f4eac6939be2bdb1154d0b43109533de080493537b110631d86d7ca'],
    'encounter-clarification.json': ['d26a56230607d07bea0abbc08f940a8ed17dcf882e76924bbe88492fc4b8936e', '550b184b8e67c4129f6bc5be16802d02d89bdf806e10d85a816c5a91a233607f', '786ca5d90bf962a397091523e34cb6ee8bc831a486c7a883ee05f1dc59ed97f7'],
    'encounter-extraction-failed.json': ['dec9f487032d382e09d7e9892acc210888d1074ea9a4d72d48e38891fbe909f3', 'dec9f487032d382e09d7e9892acc210888d1074ea9a4d72d48e38891fbe909f3', 'dec9f487032d382e09d7e9892acc210888d1074ea9a4d72d48e38891fbe909f3'],
    'encounter-harness-degraded.json': ['6f31d8b0c1de0dc67235cb3605d517368032548b926022d85551c4b52e9cf79f', 'ebe5e7a4ef1ffdf16e134a10868996da2bd2aa4687deadd8dc683ab93923b2bb', '193c71f5bb476cec76e30ebc57b7b4609555f17efcaff9bf04e091085ccfe48b'],
    'encounter-harness-ready.json': ['2365f76677a896e042b0f938c1b4a27c2c333d771d8fc1d5c300f7b90b3513a7', '2690efc65889389b8cf26b91fd85e9d8e9f381a647b4aa1a019fbd1eb549fdf9', 'c105f3237d5c889dfbc0ecbffadd6786dc5f267df09b1cc4a04bea4c6cca4df9'],
    'encounter-processing.json': ['f117e044458c55d0e50c5b896de82d6be036bedea258f804767872b990ff0666', 'f117e044458c55d0e50c5b896de82d6be036bedea258f804767872b990ff0666', 'f117e044458c55d0e50c5b896de82d6be036bedea258f804767872b990ff0666'],
    'encounter-provider-unknown.json': ['b7710405a9bc62f0136928b4b6f7d3d89ad7ef2fcc2797ac8ed194c13b69b6e8', 'b7710405a9bc62f0136928b4b6f7d3d89ad7ef2fcc2797ac8ed194c13b69b6e8', 'b7710405a9bc62f0136928b4b6f7d3d89ad7ef2fcc2797ac8ed194c13b69b6e8'],
    'encounter-ready.json': ['fa983aa9544d162a3697d8ad6aab958828787a922ef9ceefd5bce4ac278f39f1', '0f4fde31a4556cb5863f9d2ff873a578e3f99ba03ebe3edd217853af49f3fdae', '71120acb2819c38cbfbe9dd8c1cca32eea38d43d2ed67b7b083d736bda27a995'],
    'encounter-reviewed.json': ['dbd38e960eb1702f26e3a403d9443174deeb581416a93efe2cac4307c635cd88', '8b5da0ab20b901454ad99fa22bff335af621a1565b9ec77c5e0f4f77fadf0072', 'aa78da5dcb8954782068517d14e240fe20a322edf80d7a469cfd0b70cd4fac5f'],
    'encounter-stopped.json': ['5f814f885ab54b2d71b289dd46e99ba2d6923003e968dda87fcc612ee9cbe1c1', '5f814f885ab54b2d71b289dd46e99ba2d6923003e968dda87fcc612ee9cbe1c1', '5f814f885ab54b2d71b289dd46e99ba2d6923003e968dda87fcc612ee9cbe1c1'],
  };
  const older = fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name) && !name.startsWith('encounter-harness2-')).sort();
  assert.deepEqual(older, Object.keys(BASE).sort(), 'every older payload is checked');
  for (const name of older) {
    const doc = fixture(name);
    assert.deepEqual(['codes', 'checks', 'timeline'].map(tab => sha(render(doc, tab))), BASE[name], name);
  }
  const trace = fixture(HARNESS_TRACE);
  assert.equal(sha(app.traceView(trace, trace.encounter.id)), '40ec4c58e45d6275e9714bb44ec02ebb83e28611d68b7d8671a04bdefbb2f5de');
});

test('a Corti-only encounter served with harness@2\'s empty fields draws exactly as the same payload without them (I1)', () => {
  // the additions the API serves when no model participant is configured (API.md: phase 0, {} and [] everywhere)
  for (const name of [HARNESS_READY, HARNESS_DEGRADED, 'encounter-processing.json', 'encounter-ready.json']) {
    const doc = fixture(name);
    const empty = { retrieved: [], used: [] };
    const served = { ...doc, permissions: { ...doc.permissions, can_confirm: doc.permissions?.can_review === true },
      ...(doc.harness ? { harness: { ...doc.harness, phase: 0, participants: doc.harness.participants.map(row => ({ ...row, peer: {}, references: empty, peer_references: empty })) } } : {}),
      clarifications: (doc.clarifications || []).map(item => ({ ...item, candidates: [], confirmation: null })), confirmations: [],
      assessment: doc.assessment && { ...doc.assessment, proposals: doc.assessment.proposals.map(p => ({ ...p, phases: {}, confirmed: [] })) } };
    for (const tab of ['codes', 'checks', 'timeline']) assert.equal(render(served, tab), render(doc, tab), `${name} ${tab}`);
  }
});

test('a reference or a tool a participant names itself is withheld where it reads like a CPT descriptor', () => {
  const final = fixture(H2_FINAL);
  const cited = { ...final, harness: { ...final.harness, participants: final.harness.participants.map(row => (row.name === 'astra'
    ? { ...row, references: { ...row.references, used: [...row.references.used, { ref: DESCRIPTOR, use: 'Its reason.', retrieved: false }] } } : row)) } };
  const card = codeCardOf(render(cited), '45385');
  assert.equal(card.includes('lesion(s)'), false);
  assert.ok(card.includes(`<li><b>Astra · first reading:</b> ${app.escapeHtml(app.DESCRIPTOR_WITHHELD)} — cited, not retrieved`), card);
  const trace = fixture(H2_TRACE);
  const astra = trace.participants[1];
  const [first] = astra.runs;
  const named = { ...first, reading: { ...first.reading, references_used: [{ ref: DESCRIPTOR, use: '', retrieved: false }] },
    exchanges: [{ ...first.exchanges[0], tool_calls: [{ ...first.exchanges[0].tool_calls[0], tool: DESCRIPTOR }] }] };
  const html = app.traceView({ ...trace, participants: [{ ...astra, runs: [named] }] }, trace.encounter.id);
  assert.equal(html.includes('lesion(s)'), false);
  assert.ok(html.includes(`<li><b>${app.escapeHtml(app.DESCRIPTOR_WITHHELD)} — cited, not retrieved</b></li>`) && html.includes(`<li><b>${app.escapeHtml(app.DESCRIPTOR_WITHHELD)} (call_1_1)</b>`));
});

test('a peer-review run is named as one in the Activity tab, on the reconciliation card and when it stopped processing', () => {
  const final = fixture(H2_FINAL);
  const timeline = render(final, 'timeline');
  assert.equal(count(timeline, '<strong>Astra · REPLAY — recorded response, not live output · Peer review · Succeeded</strong>'), 1);
  assert.equal(count(timeline, '<strong>Astra · REPLAY — recorded response, not live output · Independent review · Succeeded</strong>'), 1);
  // an unknown outcome of a peer review blocks every send, and the card says whose and which
  const peerRun = final.provider_runs.find(run => run.purpose === 'peer_review' && run.provider === 'fable');
  const unknown = { ...final, state: 'provider_unknown', provider_runs: final.provider_runs.map(run => (run.id === peerRun.id ? { ...run, state: 'unknown', error: 'Read timed out (synthetic).' } : run)) };
  assert.ok(render(unknown).includes('<strong>Unreconciled request</strong><br>Fable (Anthropic Claude Fable 5.1) · Peer review · 1 Nov 2026, 09:00 UTC · Read timed out (synthetic).'));
  // a peer stage the system cancelled is named when processing did not finish
  const stages = [...final.pipeline.stages.slice(0, 6), { kind: 'astra_peer', state: 'cancelled', error: 'The worker stopped before this stage finished (synthetic).', finished_at: null }];
  const stopped = { ...final, state: 'stopped', pipeline: { ...final.pipeline, stopped_by_member: false, can_resume: true, stages } };
  assert.ok(render(stopped).includes('<p>Peer review: Astra (OpenAI GPT-6 Astra): The worker stopped before this stage finished (synthetic).</p>'));
});

// refutation round 2, R2-EV
// A candidate's whole sentence (HARNESS.md 12.5, EV2-1): a span that is a slice of a longer sentence is shown with that
// sentence, so a hedge around it is never hidden behind a Verified badge; and each fact's Verified note says what its
// check established - a status, on the act the code accounts for, never on the section alone.

function r2evCandidate(doc, quote, sentence, extra = {}) {
  const text = doc.revision.text;
  const span = cpSpan(text, quote, 'span');
  const whole = sentence === null ? null : cpSpan(text, sentence, 'sentence');
  return {
    id: 'c0ffee00c0ffee00', clarification_id: 'q', fact: 'extent', value: 'cecum', located_by: ['astra'],
    phase: 'peer_review', phases: { astra: 'peer_review' }, runs: [UUID],
    spans: [{ start: span.start, end: span.end, text: span.text, page: 1 }],
    ...(whole === null ? {} : { sentences: [{ start: whole.start, end: whole.end, text: whole.text }] }),
    verified: true, why: '', attestation: ATTESTATION('cecum'), ...extra,
  };
}

function r2evAnswers(doc, candidate) {
  return app.candidateAnswers({ id: 'q', candidates: [candidate], confirmation: null }, doc);
}

test('a candidate span that is a slice of a longer sentence is shown with that whole sentence, and its whole sentence alone is shown as it is', () => {
  const doc = fixture(H2_FINAL);
  const slice = 'The colonoscope was advanced to the cecum.';
  const sentence = 'Technique: The colonoscope was advanced to the cecum.';
  const html = r2evAnswers(doc, r2evCandidate(doc, slice, sentence));
  assert.ok(html.includes(`<p class="candidate-quote">“${slice}” (page 1) — a part of the sentence “${sentence}”</p>`), html);
  assert.equal(count(html, 'data-action="confirm-finding"'), 1, 'a slice shown with its sentence can be confirmed');
  // a span that is its whole sentence is quoted as it is
  const whole = r2evAnswers(doc, r2evCandidate(doc, sentence, sentence));
  assert.ok(whole.includes(`<p class="candidate-quote">“${sentence}” (page 1)</p>`) && !whole.includes('a part of the sentence'), whole);
});

test('a candidate whose served sentence cannot be shown as its span\'s is marked so and is never confirmed from the page', () => {
  const doc = fixture(H2_FINAL);
  const slice = 'The colonoscope was advanced to the cecum.';
  const good = r2evCandidate(doc, slice, 'Technique: The colonoscope was advanced to the cecum.');
  const elsewhere = { ...good, sentences: [{ ...good.sentences[0], start: good.sentences[0].start + 1 }] };  // not exact
  const apart = { ...good, sentences: [r2evCandidate(doc, slice, 'Bowel preparation was good.').sentences[0]] };  // not holding it
  const missing = { ...good, sentences: [] };
  for (const candidate of [elsewhere, apart, missing]) {
    const html = r2evAnswers(doc, candidate);
    assert.ok(html.includes(`“${slice}” (page 1) — its whole sentence is not shown: read it in the document before confirming</p>`), html);
    assert.equal(html.includes('data-action="confirm-finding"'), false, 'fail closed: no Confirm without the sentence');
  }
  // a payload served before candidates carried sentences is quoted as before
  const { sentences, ...older } = good;
  const before = r2evAnswers(doc, older);
  assert.ok(before.includes(`<p class="candidate-quote">“${slice}” (page 1)</p>`) && count(before, 'data-action="confirm-finding"') === 1);
});

test('each fact\'s Verified note says what its check established: the section rule for every fact, a status on the code\'s own act', () => {
  const doc = fixture(H2_FINAL);
  const sentence = 'Technique: The colonoscope was advanced to the cecum.';
  const said = {
    extent: 'it names that landmark, which CPT Studio&#x27;s readers read neither as not reached nor as qualified (a negation, an attempt or a doubt)',
    performed_status: 'CPT Studio&#x27;s readers read its whole sentence as stating that status for the act this code accounts for (for a code of the whole service, for that service)',
    service_date: 'it states that calendar date, which CPT Studio&#x27;s readers do not read as a date of birth',
    target: 'it names that structure, which CPT Studio&#x27;s readers read neither as not seen nor as qualified (a negation, an attempt or a doubt)',
  };
  for (const [fact, words] of Object.entries(said)) {
    const html = r2evAnswers(doc, r2evCandidate(doc, sentence, sentence, { fact }));
    assert.ok(html.includes(`Verified: its passage is an exact slice of the document, in no history, plan or indication section, and ${words}. It is still only a candidate: read the passage before confirming it.`), `${fact}: ${html}`);
    assert.equal(html.includes('the check does not read whether it names this code'), false, fact);
  }
});

// refutation round 2, R2-TRUTH

test('R2-TRUTH truth-3: reference validation that no CMS reference file applied to says no code was checked, never done', () => {
  const ready = fixture(HARNESS_READY);
  const detail = 'No code was checked against the CMS reference files: no service date is established for this encounter, so no dated CMS reference file applies.';
  const served = { ...ready.harness.reference_validation, state: 'not_verified', detail, codes_checked: 0, passages: 0, sources: [] };
  const rowOf = reference => harnessRow(render({ ...ready, harness: { ...ready.harness, reference_validation: reference } }), 'reference_validation');
  const row = rowOf(served);
  assert.ok(row.includes('<span class="status amber">Not verified</span>'), row);
  const [[tone], label, plain, required] = app.REFERENCE_STATES.not_verified;
  assert.equal(required, 'no code was checked');
  assert.ok(row.startsWith(`<div class="check-item ${tone}" data-participant="reference_validation" data-state="not_verified">`), row);
  assert.equal(label, 'Not verified');
  assert.ok(row.includes(`<p>${app.escapeHtml(detail)}</p>`) && count(row, '<p>') === 1, 'the API\'s own sentence, once');
  for (const other of ['Done', 'checked against the CMS reference files;', 'Not run']) assert.equal(row.includes(other), false, other);
  assert.ok(row.includes('Not connected: NCCI procedure-to-procedure edits'), 'what is not connected is still listed');
  // a detail that does not say no code was checked follows the plain sentence; none is the plain sentence alone
  assert.ok(rowOf({ ...served, detail: 'Synthetic reason.' }).includes(`<p>${app.escapeHtml(plain)}</p><p>Synthetic reason.</p>`));
  const bare = rowOf({ ...served, detail: '' });
  assert.ok(bare.includes(`<p>${app.escapeHtml(plain)}</p>`) && count(bare, '<p>') === 1, bare);
  // 'done' still counts its codes, and never shows a detail
  const done = rowOf({ ...ready.harness.reference_validation, detail });
  assert.ok(done.includes('<p>2 codes checked against the CMS reference files; 3 passages of verbatim CMS text retrieved.</p>') && !done.includes(app.escapeHtml(detail)), done);
});

test('R2-TRUTH truth-4: a failed retrieval says what failed and that each code\'s CMS checks stand, never that no proposal was checked', () => {
  // the plan's shared wording (jobs.RETRIEVAL_FAILED), as the API serves it for a passage load that raised
  const note = 'Reference validation failed: CPT Studio could not record which CMS reference facts and passages it retrieved for this assessment\'s codes (ValueError, logged), so none is listed here. Each code\'s checks read the CMS facts before that and stand as shown; retrieval only informs the reviewer and decides no status, so the assessment stands as made.';
  for (const said of [app.REFERENCE_STATES.failed[2], app.RETRIEVAL_FAILED]) {
    assert.equal(/no proposal was checked|no CMS reference fact or passage was retrieved/.test(said), false, said);
    assert.ok(said.includes('could not record which CMS reference facts and passages it retrieved') && said.includes('stand as shown'), said);
  }
  const ready = fixture(HARNESS_READY);
  const failed = { ...ready.harness.reference_validation, state: 'failed', detail: note, codes_checked: 0, passages: 0, sources: [] };
  const doc = { ...ready, harness: { ...ready.harness, reference_validation: failed },
    assessment: { ...ready.assessment, proposals: ready.assessment.proposals.map(proposal => ({ ...proposal, retrieval: [] })) } };
  const html = render(doc);
  const row = harnessRow(html, 'reference_validation');
  assert.ok(row.includes(`<p>${app.escapeHtml(note)}</p>`) && count(row, '<p>') === 1, row);
  // the card's own CMS reference checks line and its retrieval note agree: the checks ran and stand
  const snare = codeCardOf(html, '45385');
  assert.ok(snare.includes('<li><b>CMS reference checks:</b> passed') && snare.includes(`<p class="harness-note">${app.escapeHtml(app.RETRIEVAL_FAILED)}</p>`), snare);
});

test('R2-TRUTH truth-5: the confirmed findings say what the current assessment made of each confirmation, as the API states it', () => {
  const doc = fixture(H2_CONFIRMED);
  const [confirmation] = doc.confirmations;
  const why = 'the proposal it was made for is not in this assessment (no proposal of its code reads the same passages under the same context), so it answers nothing here; it is never read for the proposal that holds its key now';
  const section = current_effect => app.confirmedFindings({ ...doc, confirmations: [{ ...confirmation, current_effect }] });
  const ignored = section({ state: 'not_read', detail: `not read by this assessment: ${why}` });
  assert.ok(ignored.includes(`<p>${app.escapeHtml(`Effect: not read by this assessment: ${why}.`)} It decides no code.</p>`), ignored);
  assert.equal(ignored.includes('reads it as documented'), false, 'a confirmation it does not read is never said to be read');
  const before = section({ state: 'not_read', detail: 'not read by this assessment, which was made before it' });
  assert.ok(before.includes('<p>Effect: not read by this assessment, which was made before it. It decides no code.</p>'), before);
  // read: as before; nothing served: never assumed either way
  assert.ok(section({ state: 'read', detail: 'read by this assessment' }).includes('<p>The assessment reads it as documented by this passage; it decides no code.</p>'));
  for (const unserved of [undefined, null, 'read', []]) {
    const html = section(unserved);
    assert.ok(html.includes('Whether this assessment reads it is not recorded here') && !html.includes('reads it as documented'), String(unserved));
  }
  // a date of service: it entered through the context; a context that no longer carries it says so
  const date = { ...confirmation, fact: 'service_date', value: '2026-10-21', spans: [],
    current_effect: { state: 'not_read', detail: 'entered as the member\'s service date through the encounter context; this assessment\'s context does not carry it (made before it, or with another member date)' } };
  const dated = app.confirmedFindings({ ...doc, confirmations: [date] });
  assert.ok(dated.includes('It entered as the member&#x27;s date of service, through the encounter context. Effect: entered as the member&#x27;s service date through the encounter context; this assessment&#x27;s context does not carry it (made before it, or with another member date).'), dated);
});

test('R2-TRUTH truth-12: a run whose sent exchange reported no usage shows no estimate, and says why', () => {
  const trace = fixture(H2_TRACE);
  const astra = trace.participants.find(item => item.name === 'astra');
  const [first] = astra.runs;
  const [one, two] = first.exchanges;
  const runOf = (run) => app.traceView({ ...trace, participants: [{ ...astra, runs: [run] }] }, trace.encounter.id);
  const unknown = { ...first, state: 'unknown', estimated_cost_usd: null, exchanges: [one, { ...two, state: 'unknown', usage: {}, http_status: null }] };
  assert.ok(runOf(unknown).includes('<dt>Estimated cost</dt><dd>Not estimated: exchange 2 (outcome unknown) reported no usage and may have been billed, so the cost of this run cannot be estimated from published rates</dd>'), runOf(unknown));
  // an exchange recorded not sent cost nothing; a run the API prices keeps its estimate
  const unsent = { ...unknown, exchanges: [one, { ...two, state: 'not_sent', usage: {} }] };
  assert.ok(runOf(unsent).includes('<dt>Estimated cost</dt><dd>Not estimated</dd>'));
  assert.ok(runOf(first).includes(`<dt>Estimated cost</dt><dd>$${first.estimated_cost_usd} (estimated from published rates, not reconciled to an invoice)</dd>`));
});

test('R2-TRUTH truth-13: a reuse\'s references are said to be the retained run\'s tool calls\', never its own', () => {
  const final = fixture(H2_FINAL);
  const reused = { ...final, harness: { ...final.harness, participants: final.harness.participants.map(row => (row.name === 'astra'
    ? { ...row, reused: true, references: { ...row.references, reused_from: UUID } } : row)) } };
  const html = render(reused);
  const row = harnessRow(html, 'astra');
  assert.ok(row.includes('This run made no tool call: the retained run it reuses retrieved 1 reference with its own tool calls; it says it used 2, 1 of them cited, not retrieved.'), row);
  assert.equal(row.includes('Its own tool calls retrieved'), false);
  const snare = codeCardOf(html, '45385');
  assert.ok(snare.includes('<li><b>Astra · first reading (the retained run it reuses):</b> fact:cms-pfs-rvu26d:45385:mult_proc<small class="check-source">'), snare);
  assert.ok(snare.includes('<li><b>Astra · first reading (the retained run it reuses):</b> ncci-2026-ch6-c-1 — cited, not retrieved: the tool calls of the retained run this run reuses never returned it'), snare);
  assert.ok(snare.includes('<li><b>Astra · first reading (the retained run it reuses):</b> fact:cms-pfs-rvu26d:45385:mult_proc — retrieved by the tool calls of the retained run this run reuses'), snare);
  assert.equal(snare.includes('Astra · first reading:</b> ncci-2026-ch6-c-1 — cited, not retrieved: its own tool calls in this run'), false, 'its own first reading is the reuse');
  // a run's own tool calls read as before
  assert.ok(harnessRow(render(final), 'astra').includes('Its own tool calls retrieved 1 reference; it says it used 2, 1 of them cited, not retrieved.'));
  // the owner's trace: each reference used names the retained run it was checked against
  const trace = fixture(H2_TRACE);
  const astra = trace.participants.find(item => item.name === 'astra');
  const [first] = astra.runs;
  const reuse = { ...first, reused_from: UUID, exchanges: [], reading: { ...first.reading, references_used: first.reading.references_used.map(item => ({ ...item, reused_from: UUID })) } };
  const traced = app.traceView({ ...trace, participants: [{ ...astra, runs: [reuse] }] }, trace.encounter.id);
  assert.ok(traced.includes(`<li><b>fact:cms-pfs-rvu26d:45385:mult_proc — retrieved by the tool calls of the retained run this run reuses (${UUID})</b>`), traced);
  assert.ok(traced.includes(`<li><b>ncci-2026-ch6-c-1 — cited, not retrieved by the retained run this run reuses (${UUID})</b>`), traced);
  assert.equal(traced.includes('retrieved by its own tool calls in this run'), false);
});
