'use strict';
// Unit tests for the pure checks in ops/verify_browser.cjs. No server, no browser.
//   node --test ops/verification/test_verify_browser.cjs
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const vb = require('../verify_browser.cjs');
// the customer page itself: the walk's progress checks are held to the panel it really draws (the 2026-11-05 acceptance
// walk failed six checks written against hand-drawn panels no page draws)
const app = require('../../studio/static/studio/app.js');
const pageUi = enc => ({ open: new Set(), answers: new Map(), ack: null, reconnecting: false, clock: 0,
  nowMs: Date.parse(enc?.progress?.server_time || '2026-11-03T22:10:00+00:00') });

const ROOT = path.join(__dirname, '..', '..');
const TEXT = fs.readFileSync(path.join(__dirname, 'documents', 'gi-08-flexible-sigmoidoscopy-biopsy.txt'), 'utf8');
const AGENT = 'CPT Studio review agent (automated agent)';
const sha = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');

function at(passage, extra = {}) {
  const start = TEXT.indexOf(passage);
  assert.ok(start >= 0, `fixture passage not in the document: ${passage}`);
  return { context_index: 0, start, end: start + passage.length, text: passage, exact: true, page: 1, ...extra };
}

const BIOPSY = 'Cold forceps biopsies were taken from the rectum and from the normal-appearing descending colon at 40 cm, as listed below.';
const ACROSS = '2. Normal mucosa from 20 cm to 50 cm; biopsies taken at 40 cm.\n\nPlan';
const EXTENT = 'advanced under direct visualization to 50 cm from the anal verge';
const HISTORY = 'A colonoscopy two years ago was normal.';
const AGENT_REVIEW = 'Agent-executed synthetic review — not clinical approval';
const STATUS_WORDS = { ready: 'Ready for review', needs_detail: 'Needs a detail', approved: 'Approved', excluded: 'Excluded' };

// What the server states the customer page shows for a code - the operator view's "customer" (serializers.customer_codes:
// customer_api.code_rows' row, with the actions a member who may review is allowed) - which the walk judges the page by.
function statement(status, sub, actions, number = null) {
  return { number, status, status_label: STATUS_WORDS[status], sub_label: sub, reviewer_actions: actions };
}

// A selected, ready, undecided proposal is listed Ready for review with approve and reject (exact evidence assumed); any
// other is not listed unless a test says what the page shows for it (extra.customer).
function proposal(id, code, extra = {}) {
  const flex = code.startsWith('4533');
  const out = {
    id, key: id, bucket: 'selected', code, code_kind: 'cpt1', family: flex ? 'gi.flex_sig' : 'gi.colonoscopy',
    family_label: flex ? 'Flexible sigmoidoscopy' : 'Colonoscopy', eyebrow: flex ? 'FLEXIBLE SIGMOIDOSCOPY' : 'COLONOSCOPY',
    supported: true, profile_version: 'x@1', status: 'ready', status_label: 'Ready for review', exclusion_reason: '',
    reinstatable: false, descriptor: { status: 'withheld', label: 'Description withheld.' }, evidence: [], rationale: '',
    units: 1, checks: [], modifier_considerations: [], clarification_ids: [], decision: null, decision_state: 'undecided',
    allowed_actions: ['approve', 'reject'], overlay_reason: '', ...extra,
  };
  if (!('customer' in extra)) {
    out.customer = out.bucket === 'selected' && out.status === 'ready' && !out.decision ? statement('ready', '', ['approve', 'reject']) : null;
  }
  return out;
}

function encounter(overrides = {}) {
  return {
    id: 'enc-1', title: 'gi-08', state: 'ready_for_review', state_label: 'Ready for review',
    permissions: { can_review: true },
    revision: { id: 'rev-1', number: 1, kind: 'upload', text: TEXT, text_sha256: sha(TEXT), pages: [{ page: 1, start: 0, end: TEXT.length }],
      source_file: { name: 'gi-08.docx', sha256: 'a'.repeat(64), size: 100 },
      extraction: { status: 'ok', method: 'docx', messages: [], ocr_pages: [], page_count: 1 } },
    context: { facts: {
      service_date: { value: '2026-10-07', origin: 'document', evidence: [at('Date of procedure: 2026-10-07')], note: '' },
      setting: { value: 'office', origin: 'document', evidence: [], note: '' } }, user_values: {} },
    routing: { version: 'r', document_kind: 'procedure_report', families: [
      { family: 'gi.flex_sig', label: 'Flexible sigmoidoscopy', supported: true, status: 'performed',
        mentions: [{ status: 'performed', section: 'technique', cues: [], span: at(EXTENT) }],
        facts: [{ name: 'extent', value: '50 cm', origin: 'document', evidence: [at(EXTENT)], note: '' }], missing: [] },
      { family: 'gi.colonoscopy', label: 'Colonoscopy', supported: true, status: 'historical',
        mentions: [{ status: 'historical', section: 'indication', cues: [], span: at(HISTORY) }], facts: [], missing: [] }] },
    pipeline: { busy: false, can_stop: false, stages: [] },
    provider_runs: [],
    assessment: { id: 'asm-1', proposals: [
      proposal('p-flex', '45331', { evidence: [at(BIOPSY), at(ACROSS)] }),
      proposal('p-colo', '45380', { evidence: [at(BIOPSY.slice(0, 40))] }),
      proposal('p-alt', '45330', { bucket: 'alternative', status: 'informational', evidence: [at(EXTENT)], allowed_actions: [] }),
      proposal('p-hist', '45378', { bucket: 'excluded', status: 'excluded', evidence: [at(HISTORY)], allowed_actions: [] }),
    ], encounter_checks: [], unsupported: [], reference_sources: [], summary: {} },
    clarifications: [], decisions: { history: [] }, readiness: { draft: true, reviewed: false, blockers: ['45331 has no decision'] },
    reports: [], activity: [],
    ...overrides,
  };
}

function decided(enc, id, action, note) {
  const p = enc.assessment.proposals.find(item => item.id === id);
  p.decision = { id: `d-${id}`, proposal_id: id, code: p.code, action, note, reviewer: AGENT, reviewer_kind: 'agent',
    created_at: '2026-10-23T21:00:00Z', revision_number: 1 };
  p.decision_state = action === 'approve' ? 'approved' : 'rejected';
  p.allowed_actions = ['revoke'];
  p.customer = action === 'approve' ? statement('approved', AGENT_REVIEW, ['revoke']) : statement('excluded', 'Rejected in review', ['revoke']);
  enc.decisions.history.push({ ...p.decision, invalidated: null });
  return enc;
}

const statuses = (results, id) => results.filter(r => r.id === id).map(r => r.status);
const failures = results => results.filter(r => r.status === 'fail').map(r => r.id);

// --- arguments, helpers, session -----------------------------------------------------------

test('parseArgs requires every input and normalises the base URL', () => {
  const opts = vb.parseArgs(['--base-url', 'https://cpt.quillmd.com/x/', '--credentials', 'c.json', '--operator-credentials', 'op.json',
    '--docs', 'd', '--manifest', 'm.json', '--out=o', '--only=gi-01, gi-03', '--deadline-seconds', '60', '--stop-on-failure']);
  assert.equal(opts.baseUrl, 'https://cpt.quillmd.com');
  assert.deepEqual(opts.only, ['gi-01', 'gi-03']);
  assert.equal(opts.deadlineSeconds, 60);
  assert.equal(opts.stopOnFailure, true);
  assert.equal(opts.allowLiveProvider, false);
  assert.throws(() => vb.parseArgs(['--base-url', 'https://x']), /missing --credentials/);
  assert.throws(() => vb.parseArgs(['--base-url', 'not a url', '--credentials', 'c', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o']), vb.UsageError);
  assert.throws(() => vb.parseArgs(['--base-url', 'ftp://x', '--credentials', 'c', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o']), /http/);
  assert.throws(() => vb.parseArgs(['--base-url', 'https://x', '--credentials', 'c', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o', '--deadline-seconds', '5']), /at least 10/);
  // the operator session is not optional: every proof a customer may not be shown is read there
  assert.throws(() => vb.parseArgs(['--base-url', 'https://x', '--credentials', 'c', '--docs', 'd', '--manifest', 'm', '--out', 'o']), /missing --operator-credentials/);
  assert.equal(opts.noReloadWhileProcessing, false);
  assert.equal(vb.parseArgs(['--base-url', 'https://x', '--credentials', 'c', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o', '--no-reload-while-processing']).noReloadWhileProcessing, true);
  assert.throws(() => vb.parseArgs(['--retry']), /unknown option/);
  assert.throws(() => vb.parseArgs(['stray']), /unexpected argument/);
});

test('cpSlice counts Python code points, not UTF-16 units', () => {
  const points = Array.from('a\u{1F600}bc');
  assert.equal(vb.cpSlice(points, 1, 3), '\u{1F600}b');
  for (const [start, end] of [[2, 1], [-1, 2], [0, 9], ['0', 1], [1, 1]]) assert.equal(vb.cpSlice(points, start, end), null);
});

test('safeName keeps a download inside the evidence directory', () => {
  assert.equal(vb.safeName('../../etc/passwd'), 'passwd');
  assert.equal(vb.safeName('CPT Studio report (1).txt'), 'CPT_Studio_report_1_.txt');
  assert.equal(vb.safeName('...'), 'download');
});

test('sessionProblems refuses a human account, a disabled provider and an unacknowledged live provider', () => {
  const agent = { user: { actor_kind: 'agent' }, can_review: true, synthetic_only: true, provider_mode: 'replay' };
  assert.deepEqual(vb.sessionProblems(agent, {}), []);
  assert.equal(vb.sessionProblems({ ...agent, user: { actor_kind: 'human' } }, {}).length, 1);
  assert.equal(vb.sessionProblems({ ...agent, provider_mode: 'disabled' }, {}).length, 1);
  assert.match(vb.sessionProblems({ ...agent, provider_mode: 'live' }, {})[0], /--allow-live-provider/);
  assert.deepEqual(vb.sessionProblems({ ...agent, provider_mode: 'live' }, { allowLiveProvider: true }), []);
  assert.equal(vb.sessionProblems({ ...agent, can_review: false, synthetic_only: false }, {}).length, 2);
});

// --- encounter checks -----------------------------------------------------------------------

test('checkPipeline accepts only finished, reviewable states', () => {
  assert.deepEqual(statuses(vb.checkPipeline(encounter()), 'pipeline.outcome'), ['pass']);
  assert.deepEqual(statuses(vb.checkPipeline(encounter({ state: 'provider_failed' })), 'pipeline.outcome'), ['fail']);
  assert.deepEqual(statuses(vb.checkPipeline(encounter({ pipeline: { busy: true, stages: [] } })), 'pipeline.outcome'), ['fail']);
});

test('checkExtraction compares status, method, the text hash, the source text and the stored original', () => {
  const delivery = { format: 'docx', sha256: 'a'.repeat(64), size: 100 };
  const expected = { status_in: ['ok'], method_in: ['docx'], text_matches_source: 'exact' };
  assert.deepEqual(failures(vb.checkExtraction(expected, encounter(), delivery, `${TEXT}\n\n`)), []);
  const wrong = encounter();
  wrong.revision = { ...wrong.revision, extraction: { status: 'partial', method: 'pdf-text', messages: ['page 2 unreadable'] }, text_sha256: 'b'.repeat(64) };
  const results = vb.checkExtraction({ ...expected, ocr_pages_nonempty: true }, wrong, { ...delivery, sha256: 'c'.repeat(64) }, TEXT.replace('50 cm', '40 cm'));
  assert.deepEqual(failures(results).sort(), ['extraction.method', 'extraction.ocr', 'extraction.status', 'revision.source', 'revision.text_equals_source', 'revision.text_sha256']);
  assert.deepEqual(statuses(results, 'extraction.messages'), ['warn']);
  const paste = encounter();
  assert.deepEqual(statuses(vb.checkExtraction({}, paste, { format: 'paste' }, TEXT), 'revision.source'), ['fail']);
  paste.revision = { ...paste.revision, kind: 'paste', source_file: null };
  assert.deepEqual(statuses(vb.checkExtraction({}, paste, { format: 'paste' }, TEXT), 'revision.source'), ['pass']);
  assert.deepEqual(statuses(vb.checkExtraction({ text_matches_source: 'whitespace' }, encounter(), delivery, TEXT.replace(/\n/g, ' ')), 'revision.text_equals_source'), ['pass']);
});

test('checkContext requires the documented origin and value', () => {
  assert.deepEqual(failures(vb.checkContext({ service_date: { origin_in: ['document'], value_in: ['2026-10-07'] }, setting: { origin_in: ['document'], value_in: ['OFFICE'] } }, encounter())), []);
  assert.deepEqual(failures(vb.checkContext({ service_date: { origin_in: ['missing'] } }, encounter())), ['context.service_date']);
  assert.deepEqual(failures(vb.checkContext({ patient_status: { origin_in: ['missing'] } }, encounter())), ['context.patient_status']);
  const user = encounter();
  user.context.facts.service_date.origin = 'user';
  assert.deepEqual(failures(vb.checkContext({ service_date: { origin_in: ['document'], value_in: ['2026-10-07'] } }, user)), ['context.service_date']);
});

test('checkRouting reports every mismatch and never treats a performed mention as planned', () => {
  const expected = {
    families: {
      'gi.flex_sig': { presence: 'required', status_in: ['performed'], facts: { extent: { value_contains_any: ['50'] } }, missing_excludes: ['extent'] },
      'gi.colonoscopy': { presence: 'optional', status_in: ['historical'], informational: { mention_statuses_include: ['historical'] } },
      'gi.eus': { presence: 'optional', status_in: ['performed'] },
    },
    not_performed: ['gi.colonoscopy', 'gi.egd'],
  };
  const good = vb.checkRouting(expected, encounter());
  assert.deepEqual(failures(good), []);
  assert.deepEqual(statuses(good, 'routing.gi.eus.present'), ['skipped']);
  const bad = encounter();
  bad.routing.families[0].status = 'uncertain';
  bad.routing.families[0].facts[0].value = 'sigmoid';
  bad.routing.families[0].missing = ['extent'];
  bad.routing.families[1].mentions.push({ status: 'performed', section: 'plan', cues: [], span: at(HISTORY) });
  const results = vb.checkRouting({ ...expected, families: { ...expected.families, 'gi.ercp': { presence: 'required', status_in: ['performed'] } } }, bad);
  assert.deepEqual(failures(results).sort(), ['routing.gi.colonoscopy.not_performed', 'routing.gi.ercp.present', 'routing.gi.flex_sig.fact.extent', 'routing.gi.flex_sig.not_missing.extent', 'routing.gi.flex_sig.status']);
  assert.deepEqual(statuses(results, 'routing.gi.colonoscopy.info.mentions'), ['pass']);
  assert.deepEqual(failures(vb.checkRouting({}, encounter({ routing: null }))), ['routing.present']);
  const factOrigin = encounter();
  factOrigin.routing.families[0].facts[0].origin = 'missing';
  assert.deepEqual(failures(vb.checkRouting({ families: { 'gi.flex_sig': { presence: 'required', status_in: ['performed'], facts: { extent: {} } } } }, factOrigin)), ['routing.gi.flex_sig.fact.extent']);
});

test('checkRouting reports informational expectations as warnings only', () => {
  const results = vb.checkRouting({ families: { 'gi.flex_sig': { presence: 'required', status_in: ['performed'], informational: { facts: { intent: { value_contains_any: ['screening'] } }, mention_statuses_include: ['planned'] } } } }, encounter());
  assert.deepEqual(failures(results), []);
  assert.deepEqual(results.filter(r => r.status === 'warn').map(r => r.id).sort(), ['routing.gi.flex_sig.info.fact.intent', 'routing.gi.flex_sig.info.mentions']);
});

test('checkEvidenceExact verifies every span against revision.text in code points', () => {
  assert.deepEqual(failures(vb.checkEvidenceExact(encounter())), []);
  const bad = encounter();
  bad.assessment.proposals[0].evidence[0] = { ...bad.assessment.proposals[0].evidence[0], start: bad.assessment.proposals[0].evidence[0].start + 1 };
  bad.assessment.proposals[1].evidence = [at(BIOPSY.slice(0, 40), { text: 'not the source' })];
  bad.context.facts.service_date.evidence[0].end += 1;
  const results = vb.checkEvidenceExact(bad);
  assert.deepEqual(failures(results).sort(), ['evidence.context_and_routing_exact', 'evidence.exact', 'evidence.selected_have_exact']);
  const flagged = encounter();
  flagged.assessment.proposals[0].evidence[0].exact = false;
  assert.deepEqual(statuses(vb.checkEvidenceExact(flagged), 'evidence.exact_flag'), ['warn']);
  const emoji = '\u{1F600} Cold snare.';
  const astral = encounter({ revision: { ...encounter().revision, text: emoji } });
  astral.assessment.proposals = [proposal('p', '45385', { evidence: [{ start: 2, end: 13, text: 'Cold snare.', exact: true }] })];
  astral.context.facts = {};
  astral.routing.families = [];
  assert.deepEqual(failures(vb.checkEvidenceExact(astral)), []);
});

test('checkMustNotCode fails only on a READY selected proposal in the family', () => {
  const enc = encounter();
  assert.deepEqual(failures(vb.checkMustNotCode([{ family: 'gi.colonoscopy', reason: 'historical' }], enc)), ['must_not_code.gi.colonoscopy']);
  enc.assessment.proposals[1].status = 'needs_clarification';
  const held = vb.checkMustNotCode([{ family: 'gi.colonoscopy', reason: 'historical' }], enc);
  assert.deepEqual(failures(held), []);
  assert.deepEqual(statuses(held, 'must_not_code.gi.colonoscopy.held'), ['warn']);
  enc.assessment.proposals[1].bucket = 'excluded';
  assert.deepEqual(vb.checkMustNotCode([{ family: 'gi.colonoscopy', reason: 'historical' }], enc).map(r => r.status), ['pass']);
});

test('checkClarifications needs an open clarification for each fact, in scope', () => {
  const enc = encounter({ clarifications: [
    { id: 'c1', scope: 'encounter', fact: 'service_date', state: 'open', question: 'Date?' },
    { id: 'c2', scope: 'encounter', fact: 'setting', state: 'open', question: 'Setting?' },
    { id: 'c3', scope: 'service', fact: 'em_basis', state: 'answered', question: 'Basis?' }] });
  const results = vb.checkClarifications([{ fact: 'service_date', scope_in: ['encounter'] }, { fact: 'setting', scope_in: ['service', 'proposal'] }, { fact: 'em_basis' }], enc);
  assert.deepEqual(results.map(r => r.status), ['pass', 'fail', 'fail']);
  assert.match(results[1].reason, /only with scope encounter/);
  assert.deepEqual(vb.checkClarifications([], enc).map(r => r.status), ['warn']);
  assert.deepEqual(vb.checkClarifications([], encounter()), []);
});

test('checkIncomplete refuses a dropped or silently completed incomplete service', () => {
  const enc = encounter();
  const family = [{ family: 'gi.flex_sig' }];
  assert.deepEqual(failures(vb.checkIncomplete(family, enc)), ['incomplete.gi.flex_sig.not_auto_completed']);
  enc.assessment.proposals[0].modifier_considerations = ['53: discontinued procedure'];
  assert.deepEqual(failures(vb.checkIncomplete(family, enc)), []);
  enc.assessment.proposals[0].modifier_considerations = [];
  enc.assessment.proposals[0].checks = [{ id: 'service.status', label: 'Service status', status: 'warn', detail: 'Documented as incomplete.' }];
  assert.deepEqual(failures(vb.checkIncomplete(family, enc)), []);
  enc.assessment.proposals[0].checks = [{ id: 'service.status', label: 'Service status', status: 'pass', detail: 'incomplete' }];
  assert.deepEqual(failures(vb.checkIncomplete(family, enc)), ['incomplete.gi.flex_sig.not_auto_completed']);
  const dropped = encounter();
  dropped.assessment.proposals = dropped.assessment.proposals.filter(p => p.family !== 'gi.flex_sig');
  assert.deepEqual(failures(vb.checkIncomplete(family, dropped)), ['incomplete.gi.flex_sig.not_dropped']);
  dropped.clarifications = [{ id: 'c', scope: 'service', family: 'gi.flex_sig', fact: 'extent', state: 'open' }];
  assert.deepEqual(failures(vb.checkIncomplete(family, dropped)), []);
});

// --- decisions --------------------------------------------------------------------------------

const NOTES = { approve: 'Agent-executed synthetic verification review', reject: 'designated rejection' };

test('planDecisions approves every ready selected proposal except the designated rejection', () => {
  const enc = encounter();
  const plan = vb.planDecisions(enc, { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES);
  assert.deepEqual(plan.decisions.map(d => [d.code, d.action, d.designated, d.note]), [
    ['45331', 'approve', false, NOTES.approve], ['45380', 'reject', true, NOTES.reject]]);
  assert.equal(plan.designated_missing, false);
  const fallback = vb.planDecisions(enc, { reject: { family: 'gi.flex_sig', prefer_codes: ['99999'] } }, NOTES);
  assert.deepEqual(fallback.decisions.map(d => d.action), ['reject', 'approve']);
  const none = vb.planDecisions(enc, { reject: { family: 'gi.eus', prefer_codes: [] } }, NOTES);
  assert.equal(none.designated_missing, true);
  assert.deepEqual(none.decisions.map(d => d.action), ['approve', 'approve']);
  enc.assessment.proposals[0].status = 'needs_clarification';
  decided(enc, 'p-colo', 'approve', NOTES.approve);
  assert.deepEqual(vb.planDecisions(enc, { reject: null }, NOTES).decisions, []);
});

test('checkReadiness: undecided selected codes must block the reviewed report', () => {
  assert.deepEqual(failures(vb.checkReadiness(encounter())), []);
  assert.deepEqual(failures(vb.checkReadiness(encounter({ readiness: { draft: true, reviewed: true, blockers: [] } }))), ['readiness.reviewed_blocked']);
  const done = decided(decided(encounter(), 'p-flex', 'approve', 'n'), 'p-colo', 'reject', 'n');
  assert.deepEqual(vb.checkReadiness(done).map(r => r.status), ['pass', 'warn']);
  done.readiness = { draft: true, reviewed: true, blockers: [] };
  assert.deepEqual(vb.checkReadiness(done).map(r => r.status), ['pass', 'pass']);
});

test('checkPersistence: same revision and assessment, decisions persisted as agent review with their notes', () => {
  const before = encounter();
  const after = decided(decided(encounter(), 'p-flex', 'approve', NOTES.approve), 'p-colo', 'reject', NOTES.reject);
  const made = [{ proposal_id: 'p-flex', code: '45331', action: 'approve', note: NOTES.approve, http_status: 201 },
    { proposal_id: 'p-colo', code: '45380', action: 'reject', note: NOTES.reject, http_status: 201 }];
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, after)), []);
  const moved = JSON.parse(JSON.stringify(after));
  moved.revision.number = 2;
  moved.assessment.id = 'asm-2';
  moved.assessment.proposals[0].decision.note = 'edited';
  moved.assessment.proposals[1].decision_state = 'undecided';
  moved.decisions.history = [];
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, moved)).sort(), ['persist.assessment', 'persist.decision.45331', 'persist.decision.45380', 'persist.revision']);
  const human = JSON.parse(JSON.stringify(after));
  human.assessment.proposals[0].decision.reviewer_kind = 'human';
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, human)), ['persist.decision.45331']);
  const invalidated = JSON.parse(JSON.stringify(after));
  invalidated.decisions.history[0].invalidated = { reason: 'new revision' };
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, invalidated)), ['persist.decision.45331']);
});

// --- DOM, downloads ---------------------------------------------------------------------------

test('checkEvidenceMarks: every exact span of a selected proposal is marked, split marks re-join, nothing stray', () => {
  const enc = encounter();
  const [biopsy, across] = enc.assessment.proposals[0].evidence;
  const marks = [
    { keys: ['p-flex:0', 'p-colo:0'], text: biopsy.text.slice(0, 40) },
    { keys: ['p-flex:0'], text: biopsy.text.slice(40) },
    { keys: ['p-flex:1'], text: '2. Normal mucosa from 20 cm to 50 cm; biopsies taken at 40 cm.' },
    { keys: ['p-flex:1'], text: 'Plan' },
  ];
  assert.ok(across.text.includes('\n\n'));
  const cards = [{ id: 'card-p-flex', unlocated: 0 }, { id: 'card-p-colo', unlocated: 0 }];
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, cards)), []);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks.slice(0, 3), cards)), ['dom.marks.45331']);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, [...marks, { keys: ['p-alt:0'], text: EXTENT }], cards)), ['dom.marks.known']);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, [cards[0], { id: 'card-p-colo', unlocated: 1 }])), ['dom.unlocated.45380']);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, [cards[0]])), ['dom.card.45380']);
  enc.assessment.proposals[1].evidence[0].exact = false;
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, [cards[0], { id: 'card-p-colo', unlocated: 1 }])), ['dom.marks.known']);
});

// A source passage CPT Studio selected for a proposal (support.source), as the API serves it: offsets and text only.
function sourceSpan(passage) {
  const { start, end, text } = at(passage);
  return { start, end, text };
}

// refutation p2, reports2:4: app.js marks a selected proposal's exact support.source passages ('<id>:s<n>',
// documentLayout); the walk failed hard on them as "unknown or inexact spans". They are known; nothing else is.
test('checkEvidenceMarks: the exact support.source passages of a selected proposal are known marks, and only those', () => {
  const enc = encounter();
  const [biopsy] = enc.assessment.proposals[0].evidence;
  enc.assessment.proposals[1].support = { status: 'warn', source: [sourceSpan(EXTENT), sourceSpan(HISTORY)] };
  const marks = [
    { keys: ['p-flex:0', 'p-colo:0'], text: biopsy.text.slice(0, 40) },
    { keys: ['p-flex:0'], text: biopsy.text.slice(40) },
    { keys: ['p-flex:1'], text: '2. Normal mucosa from 20 cm to 50 cm; biopsies taken at 40 cm.' },
    { keys: ['p-flex:1'], text: 'Plan' },
    { keys: ['p-colo:s0'], text: EXTENT },
    { keys: ['p-colo:s1'], text: HISTORY },
  ];
  const cards = [{ id: 'card-p-flex', unlocated: 0 }, { id: 'card-p-colo', unlocated: 0 }];
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, cards)), []);
  // a passage that is not exact at its offsets stays unknown
  const inexact = JSON.parse(JSON.stringify(enc));
  inexact.assessment.proposals[1].support.source[1].text = 'not in the source';
  assert.deepEqual(failures(vb.checkEvidenceMarks(inexact, marks, cards)), ['dom.marks.known']);
  // so does one of a proposal that is not selected, and an index the proposal does not have
  const alternative = JSON.parse(JSON.stringify(enc));
  alternative.assessment.proposals[2].support = { status: 'warn', source: [sourceSpan(EXTENT)] };
  assert.deepEqual(failures(vb.checkEvidenceMarks(alternative, [...marks, { keys: ['p-alt:s0'], text: EXTENT }], cards)), ['dom.marks.known']);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, [...marks, { keys: ['p-colo:s2'], text: EXTENT }], cards)), ['dom.marks.known']);
});




test('documentResult fails on an error or a hard failure, never on warnings', () => {
  assert.equal(vb.documentResult({ error: null, assertions: [{ status: 'pass' }, { status: 'warn' }, { status: 'skipped' }] }), 'pass');
  assert.equal(vb.documentResult({ error: null, assertions: [{ status: 'fail' }] }), 'fail');
  assert.equal(vb.documentResult({ error: 'boom', assertions: [] }), 'fail');
});

test('summarize records the state without the revision text', () => {
  const summary = vb.summarize(encounter());
  assert.equal(summary.revision.characters, Array.from(TEXT).length);
  assert.equal(JSON.stringify(summary).includes(BIOPSY), false);
  assert.deepEqual(summary.proposals.map(p => [p.code, p.exact_evidence]), [['45331', 2], ['45380', 1], ['45330', 1], ['45378', 1]]);
});

// --- round 5: a confirmed exclusion has no code card (pipeline:3); the walk confirms only must_not_code (pipeline:5)

function withExcluded(enc, id, code, family, extra = {}) {
  const listed = extra.reinstatable !== false;  // an exclusion nobody may decide is not on the page
  enc.assessment.proposals.push(proposal(id, code, { bucket: 'excluded', status: 'excluded', family, reinstatable: true,
    exclusion_reason: 'Documented as planned, not as performed on the date of service.',
    allowed_actions: ['reinstate', 'confirm'],
    customer: listed ? statement('excluded', 'Excluded by a documentation check', ['reinstate', 'confirm']) : null, ...extra }));
  return enc;
}

function confirmed(enc, id) {
  const p = enc.assessment.proposals.find(item => item.id === id);
  p.decision = { id: `d-${id}`, proposal_id: id, code: p.code, action: 'confirm', note: 'n', reviewer: AGENT,
    reviewer_kind: 'agent', created_at: '2026-10-23T21:00:00Z', revision_number: 1 };
  p.decision_state = 'exclusion_confirmed';
  p.allowed_actions = ['revoke'];
  p.customer = statement('excluded', 'Exclusion confirmed in review', ['revoke']);
  return enc;
}


test('planConfirmations confirms only the families must_not_code names', () => {
  // pipeline:5's witness: a misread exclusion of the visit the author expects to be coded is never confirmed.
  const enc = withExcluded(withExcluded(encounter(), 'p-visit', '99213', 'gi.office_em'), 'p-plan', '45378', 'gi.colonoscopy');
  const plan = vb.planConfirmations(enc, [{ family: 'gi.colonoscopy' }], { confirm: 'Synthetic confirmation.' });
  assert.deepEqual(plan.map(d => [d.code, d.action, d.note]), [['45378', 'confirm', 'Synthetic confirmation.']]);
  assert.deepEqual(vb.planConfirmations(enc, [], {}), []);
  assert.deepEqual(vb.planConfirmations(enc, undefined, {}), []);
  for (const extra of [{ reinstatable: false }, { decision_state: 'reinstated', decision: { action: 'reinstate' } }]) {
    const other = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy', extra);
    assert.deepEqual(vb.planConfirmations(other, [{ family: 'gi.colonoscopy' }], {}), [], JSON.stringify(extra));
  }
  // refutation round 2, L3-5: the operator's own allowed_actions decide nothing - ops-agent reads with no membership and
  // is allowed none - while the walking member's permissions and the server's own gates do
  const opsAgent = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy', { allowed_actions: [] });
  assert.deepEqual(vb.planConfirmations(opsAgent, [{ family: 'gi.colonoscopy' }], {}).map(d => d.code), ['45378']);
  assert.deepEqual(vb.planConfirmations(opsAgent, [{ family: 'gi.colonoscopy' }], {}, false), []);
  // refutation round 3 (B-02, B-03): what the server states it accepts, and nothing else - none on an assessment that is
  // not the final one (review._allowed), none where the view states nothing
  const notFinal = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy',
    { customer: statement('excluded', 'Excluded by a documentation check', []) });
  assert.deepEqual(vb.planConfirmations(notFinal, [{ family: 'gi.colonoscopy' }], {}), []);
  const unstated = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy', { customer: undefined });
  assert.deepEqual(vb.planConfirmations(unstated, [{ family: 'gi.colonoscopy' }], {}), []);
});

test('a STOP file in the evidence directory stops the batch before the next upload', () => {
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'cpt-verify-stop-'));
  try {
    assert.equal(vb.stopRequested(dir), false);
    fs.writeFileSync(path.join(dir, 'STOP'), '');
    assert.equal(vb.stopRequested(dir), true);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// --- round gi2 (ops): the member's upload date, the context edit, labelled decisions, --no-auto-approve ---------------
//
// Request hashes below were computed by the server's own studio.providers.corti.build_coding_request (adapter
// corti-coding-v2@cptstudio-1) for this module's gi-08 TEXT, never by the function under test.
const GI08_REQUEST = {
  '2026-10-07': '561a5130f8e9fad308fb30c30086946e40f2631291d151da8b89bba3cd6cc7c8',  // the documented date
  '2026-10-08': '658ce35622517460b847eccb84a8efc524409c324be124cb21d33eaec3acbbfc',  // a member date one day later
  none: '6a2cf0891c7628d13ba7226b808b7e44ddb10708c4e30a977cec4e394c525053',  // no date
};
// studio/jobs.py MEMBER_DATE_CONFLICT_MESSAGE, written out here so a wrong constant in the module cannot pass.
const HOLD_MESSAGE = 'Nothing was sent: the service date entered as encounter metadata differs from the documented one. '
  + 'Correct or clear the metadata (or add an addendum), and the request is made for the agreed date.';
const DOCUMENTED = '2026-10-07';
const MEMBER = '2026-10-08';

function run(id, extra = {}) {
  return { id, provider: 'corti', mode: 'live', state: 'succeeded', http_status: 200, latency_ms: 900,
    usage: { creditsConsumed: 0.03 }, usage_basis: 'provider_reported_credits_not_usd', request_sha256: GI08_REQUEST[DOCUMENTED],
    response_sha256: 'f'.repeat(64), reused_from: null, error: '', reconciled: false, created_at: '2026-10-28T20:00:00Z',
    purpose: 'primary', scope_items: [], ...extra };
}

function hold(id = 'run-hold') {
  return run(id, { state: 'not_sent', http_status: null, latency_ms: null, usage: {}, usage_basis: '', request_sha256: '',
    response_sha256: '', error: HOLD_MESSAGE });
}

// The encounter after processing a document uploaded with a member date that differs from the documented one: the
// conflict is held, one not-sent hold run records it, nothing was requested and no code was proposed.
function heldEncounter(member = MEMBER) {
  const enc = encounter({ state: 'no_codes', provider_runs: [hold()],
    clarifications: [{ id: 'c-date', scope: 'encounter', fact: 'service_date', state: 'open', question: 'Which date?' }] });
  enc.context = { facts: {
    // the note studio/gi/context.py merge_user_values writes for it (USER_CONFLICT_NOTE)
    service_date: { value: null, origin: 'conflict', member_conflict: true, evidence: [at('Date of procedure: 2026-10-07')],
      note: `Encounter metadata entered by a workspace member gives ${member}; the document gives ${DOCUMENTED}. Both are `
        + 'kept and neither is used until they agree: correct the metadata, clear it, or add an addendum to the document.' },
    setting: { value: 'office', origin: 'document', evidence: [], note: '', member_conflict: false } }, user_values: { service_date: member } };
  enc.assessment = { ...enc.assessment, id: 'asm-held', proposals: [] };
  enc.readiness = { draft: true, reviewed: false, blockers: [] };
  return enc;
}

// The same encounter once a context save settled the conflict and its one request was answered.
function editedEncounter(before, { date = DOCUMENTED, origin = 'user', userValue = DOCUMENTED, runs = null } = {}) {
  const enc = encounter({ provider_runs: runs || [...before.provider_runs, run('run-sent', { request_sha256: GI08_REQUEST[date || 'none'] })] });
  enc.context = { facts: {
    service_date: { value: date, origin: date ? origin : 'missing', member_conflict: false, evidence: [], note: '' },
    setting: { value: 'office', origin: 'document', evidence: [], note: '', member_conflict: false } },
    user_values: userValue ? { service_date: userValue } : {} };
  return enc;
}

const EDIT_OK = { http_status: 201, error: null, posted: { answers: [{ id: 'detail-date', fact: 'service_date', value: DOCUMENTED }] },
  identical: { via: 'api', http_status: 201, error: null, panel_asks_again: false } };
const SERVICE_DATE_PLAN = { service_date: DOCUMENTED, clear_member_date: false };
const CLEAR_PLAN = { service_date: '', clear_member_date: true };
const clone = value => JSON.parse(JSON.stringify(value));
const hardFailures = results => results.filter(r => r.severity === 'hard' && r.status === 'fail').map(r => r.id);

test('parseArgs: --no-auto-approve is an option, off by default', () => {
  const base = ['--base-url', 'https://x', '--credentials', 'c', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o'];
  assert.equal(vb.parseArgs(base).noAutoApprove, false);
  assert.equal(vb.parseArgs([...base, '--no-auto-approve']).noAutoApprove, true);
  assert.throws(() => vb.parseArgs([...base, '--no-auto-approve=yes']), vb.UsageError);
});

test('primaryRequestSha256 is the server\'s canonical request hash (vectors from build_coding_request)', () => {
  const vectors = [
    ['Date of procedure: 2026-10-07\nColonoscopy to the cecum.\n', '2026-10-07', '9165b5094a547781f268c21f16ad97e81f6cff963536cc62acbe7ddc5705cc84'],
    ['Colonoscopy to the cecum.\n', null, '554e6f5af2eb9b422a002f008eeb4fb3733621774cc082b92d8aacc24cb6f6e6'],
    ['He said "no" \\ then\ttabbed\r\nend', '2026-10-23', '088ee1dc1d27bef5b664178c96702eac0fdba1d3f90a9e3574384f92ac6bbf94'],
    ['a\u0001b\u001fc\u007fd\u000be\ff\bg', '2026-10-24', '7ac40e8c919d01a4bc33d93b9086a51f0a1c1b77ee8f7b484f7fd6e0f00c5006'],
    ['Café — µg ≥ 5 °C “quoted”', '2026-10-23', 'ddc40e6edcfb208e1232326b28cf41f37d1701f1a96b56592d33bf9673db0f82'],
    ['emoji 😀 line para end ﻿bom', '2026-01-02', '704a1728dfd12a575957ec3843461af2ff86aa0a648780ec1bba52da3eec5500'],
    [TEXT, DOCUMENTED, GI08_REQUEST[DOCUMENTED]], [TEXT, MEMBER, GI08_REQUEST[MEMBER]], [TEXT, null, GI08_REQUEST.none],
  ];
  for (const [text, date, want] of vectors) assert.equal(vb.primaryRequestSha256(text, date), want, JSON.stringify([text.slice(0, 30), date]));
});

test('the pinned request shape and hold message are the server\'s own (studio/providers, studio/jobs.py)', () => {
  const corti = fs.readFileSync(path.join(ROOT, 'studio', 'providers', 'corti.py'), 'utf8');
  const base = fs.readFileSync(path.join(ROOT, 'studio', 'providers', 'base.py'), 'utf8');
  const jobs = fs.readFileSync(path.join(ROOT, 'studio', 'jobs.py'), 'utf8');
  const systems = /^SYSTEMS = \(([^)]*)\)/m.exec(corti);
  assert.ok(systems, 'SYSTEMS not found in corti.py');
  assert.deepEqual([...systems[1].matchAll(/'([^']*)'/g)].map(m => m[1]), vb.PROVIDER_SYSTEMS);
  assert.ok(corti.includes("(text, f'Date of service: {service_date.isoformat()}')"), 'the date context line changed');
  assert.ok(corti.includes("body = {'system': list(SYSTEMS), 'context': [{'type': 'text', 'text': item} for item in contexts]}"), 'the request body changed');
  assert.ok(base.includes("json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()"), 'canonical_body changed');
  const message = /^MEMBER_DATE_CONFLICT_MESSAGE = \(((?:\s*'[^']*')+)\)/m.exec(jobs);
  assert.ok(message, 'MEMBER_DATE_CONFLICT_MESSAGE not found in jobs.py');
  assert.equal([...message[1].matchAll(/'([^']*)'/g)].map(m => m[1]).join(''), vb.MEMBER_DATE_HOLD_MESSAGE);
  assert.equal(vb.MEMBER_DATE_HOLD_MESSAGE, HOLD_MESSAGE);
  // jobs._member_date_hold is the one writer of that message, and it always records scope {'held': ...}
  assert.equal(jobs.split('error=MEMBER_DATE_CONFLICT_MESSAGE').length - 1, 1);
});

test('isMemberDateHold reads the served hold run, and nothing else', () => {
  assert.equal(vb.isMemberDateHold(hold()), true);
  for (const extra of [{ request_sha256: GI08_REQUEST.none }, { error: 'No recorded response for this request.' },
    { purpose: 'second_review' }, { state: 'succeeded' }, { state: 'cancelled' }]) {
    assert.equal(vb.isMemberDateHold({ ...hold(), ...extra }), false, JSON.stringify(extra));
  }
});

test('checkContextEdit: a settled member conflict sends one request for the edited date, keeps the hold, and an identical save sends nothing', () => {
  const before = heldEncounter();
  const after = editedEncounter(before);
  const results = vb.checkContextEdit(before, after, clone(after), SERVICE_DATE_PLAN, EDIT_OK, MEMBER);
  assert.deepEqual(results.filter(r => r.status !== 'pass').map(r => `${r.id}:${r.status}`), []);
  assert.deepEqual(results.filter(r => r.severity === 'hard').map(r => r.id), ['context_edit.held_before', 'context_edit.nothing_sent_before',
    'context_edit.request', 'context_edit.date_after', 'context_edit.one_request', 'context_edit.sent_at_most_once', 'context_edit.hold_kept',
    'context_edit.identical_save']);
  assert.match(results.find(r => r.id === 'context_edit.one_request').reason, /2026-10-07/);
  // clearing the member's date: the request carries the documented date
  const cleared = editedEncounter(before, { origin: 'document', userValue: null });
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, cleared, clone(cleared), CLEAR_PLAN, { ...EDIT_OK, posted: { service_date: '', setting: '', billing_context: '' } }, MEMBER)), []);
});

test('checkContextEdit: the request is proven by its hash, so a wrong or missing date fails and is named', () => {
  const before = heldEncounter();
  const wrong = editedEncounter(before);
  wrong.provider_runs[1].request_sha256 = GI08_REQUEST[MEMBER];  // the member's conflicting date went out
  const results = vb.checkContextEdit(before, wrong, clone(wrong), SERVICE_DATE_PLAN, EDIT_OK, MEMBER);
  assert.deepEqual(hardFailures(results), ['context_edit.one_request', 'context_edit.sent_at_most_once']);
  assert.match(results.find(r => r.id === 'context_edit.one_request').reason, /2026-10-08/);
  const dateless = editedEncounter(before);
  dateless.provider_runs[1].request_sha256 = GI08_REQUEST.none;
  assert.match(vb.checkContextEdit(before, dateless, clone(dateless), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)
    .find(r => r.id === 'context_edit.one_request').reason, /no date/);
  // the context does not state the edited date
  const other = editedEncounter(before, { date: '2026-10-09', userValue: '2026-10-09' });
  assert.ok(hardFailures(vb.checkContextEdit(before, other, clone(other), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.date_after'));
  // a clear that left the member's value in place
  const kept = editedEncounter(before, { origin: 'document', userValue: MEMBER });
  assert.ok(hardFailures(vb.checkContextEdit(before, kept, clone(kept), CLEAR_PLAN, EDIT_OK, MEMBER)).includes('context_edit.date_after'));
});

test('checkContextEdit: each hard check fails on the defect it exists for', () => {
  const before = heldEncounter();
  const after = editedEncounter(before);
  // the conflict was not held: the member value agreed, or no hold was recorded, or another member value is stored
  const agreed = clone(before);
  agreed.context.facts.service_date = { value: MEMBER, origin: 'user', member_conflict: false, evidence: [], note: '' };
  assert.ok(hardFailures(vb.checkContextEdit(agreed, after, clone(after), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.held_before'));
  const unheld = clone(before);
  unheld.provider_runs = [];
  assert.ok(hardFailures(vb.checkContextEdit(unheld, editedEncounter(unheld), null, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.held_before'));
  assert.ok(hardFailures(vb.checkContextEdit(before, after, clone(after), SERVICE_DATE_PLAN, EDIT_OK, '2026-10-30')).includes('context_edit.held_before'));
  // a request went out while the conflict held
  const leaked = clone(before);
  leaked.provider_runs.push(run('run-leak', { request_sha256: GI08_REQUEST.none }));
  assert.ok(hardFailures(vb.checkContextEdit(leaked, editedEncounter(leaked), null, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.nothing_sent_before'));
  // the save was refused: nothing after it is judged
  const refused = vb.checkContextEdit(before, null, null, SERVICE_DATE_PLAN, { ...EDIT_OK, http_status: 409, error: 'Wait for processing to finish' }, MEMBER);
  assert.deepEqual(refused.map(r => `${r.id}:${r.status}`), ['context_edit.held_before:pass', 'context_edit.nothing_sent_before:pass', 'context_edit.request:fail']);
  // two requests sent, or none, or a second hold instead of a request
  const twice = editedEncounter(before, { runs: [hold(), run('run-a'), run('run-b')] });
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, twice, clone(twice), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.one_request', 'context_edit.sent_at_most_once']);
  const none = editedEncounter(before, { runs: [hold()] });
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, none, clone(none), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.one_request']);
  const heldAgain = editedEncounter(before, { runs: [hold(), hold('run-hold-2')] });
  assert.ok(hardFailures(vb.checkContextEdit(before, heldAgain, clone(heldAgain), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.one_request'));
  // a request that was not sent (refused before it left) is not the one request the edit owes
  const unsent = editedEncounter(before, { runs: [hold(), run('run-x', { state: 'not_sent', usage: {}, error: 'Corti refused the token request; nothing was sent.' })] });
  assert.ok(hardFailures(vb.checkContextEdit(before, unsent, clone(unsent), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.one_request'));
  // the hold was removed or rewritten
  const dropped = editedEncounter(before, { runs: [run('run-sent')] });
  assert.ok(hardFailures(vb.checkContextEdit(before, dropped, clone(dropped), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.hold_kept'));
  const rewritten = clone(after);
  rewritten.provider_runs[0].error = 'Nothing was sent.';
  assert.ok(hardFailures(vb.checkContextEdit(before, rewritten, clone(rewritten), SERVICE_DATE_PLAN, EDIT_OK, MEMBER)).includes('context_edit.hold_kept'));
  // the identical save sent the request again, held again, was refused, or was never made
  const resent = clone(after);
  resent.provider_runs.push(run('run-again'));
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, resent, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.identical_save']);
  const reheld = clone(after);
  reheld.provider_runs.push(hold('run-hold-3'));
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, reheld, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.identical_save']);
  const changed = clone(after);
  changed.provider_runs[1].usage = {};
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, changed, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.identical_save']);
  const refusedAgain = { ...EDIT_OK, identical: { ...EDIT_OK.identical, http_status: 409, error: 'Wait for processing to finish' } };
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, null, SERVICE_DATE_PLAN, refusedAgain, MEMBER)), ['context_edit.identical_save']);
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, null, SERVICE_DATE_PLAN, EDIT_OK, MEMBER)), ['context_edit.identical_save']);
});

test('checkContextEdit: a reused answer sends nothing and passes; the soft checks record what is unusual', () => {
  const before = heldEncounter();
  const reused = editedEncounter(before, { runs: [hold(), run('run-reused', { reused_from: 'run-elsewhere', usage: {}, http_status: null })] });
  const results = vb.checkContextEdit(before, reused, clone(reused), SERVICE_DATE_PLAN, EDIT_OK, MEMBER);
  assert.deepEqual(hardFailures(results), []);
  assert.match(results.find(r => r.id === 'context_edit.one_request').reason, /reused/);
  const after = editedEncounter(before);
  // the identical save re-assessed through a reused run instead of re-checking: nothing sent, but not a pure re-check
  const viaReuse = clone(after);
  viaReuse.provider_runs.push(run('run-again', { reused_from: 'run-sent', usage: {} }));
  const soft = vb.checkContextEdit(before, after, viaReuse, SERVICE_DATE_PLAN, EDIT_OK, MEMBER);
  assert.deepEqual(hardFailures(soft), []);
  assert.deepEqual(statuses(soft, 'context_edit.identical_save_rechecks'), ['warn']);
  // after the save and a reload the details panel still asks the answered question (the server then judged the repeat)
  const asked = { ...EDIT_OK, identical: { ...EDIT_OK.identical, panel_asks_again: true } };
  assert.deepEqual(statuses(vb.checkContextEdit(before, after, clone(after), SERVICE_DATE_PLAN, asked, MEMBER), 'context_edit.panel_shows_saved'), ['warn']);
  // the details endpoint may answer any 2xx; a 4xx is no save
  assert.deepEqual(hardFailures(vb.checkContextEdit(before, after, clone(after), SERVICE_DATE_PLAN, { ...EDIT_OK, http_status: 200, identical: { ...EDIT_OK.identical, http_status: 204 } }, MEMBER)), []);
  // an unknown outcome is the operator's to reconcile: soft
  const unknown = editedEncounter(before, { runs: [hold(), run('run-u', { state: 'unknown', http_status: null, usage: {}, response_sha256: '' })] });
  const outcome = vb.checkContextEdit(before, unknown, clone(unknown), SERVICE_DATE_PLAN, EDIT_OK, MEMBER);
  assert.deepEqual(hardFailures(outcome), []);
  assert.deepEqual(statuses(outcome, 'context_edit.outcome'), ['warn']);
});

test('checkUploadDate: the member date the manifest asked for reached the encounter', () => {
  const enc = heldEncounter();
  assert.deepEqual(vb.checkUploadDate(MEMBER, enc).map(r => r.status), ['pass']);
  assert.deepEqual(vb.checkUploadDate('2026-10-09', enc).map(r => r.status), ['fail']);
  assert.deepEqual(vb.checkUploadDate(MEMBER, encounter()).map(r => r.status), ['fail']);
  assert.deepEqual(vb.checkUploadDate(null, encounter()), []);
});

test('planProblems: refuses a malformed context_edit, approve_codes, upload date or unlabelled note before anything is uploaded', () => {
  const notes = { approve: 'Agent-executed synthetic verification review', reject: 'Agent-executed synthetic verification review - designated rejection' };
  const doc = (reviewPlan, upload = { service_date: MEMBER }) => ({ id: 'h', upload, review_plan: reviewPlan });
  assert.deepEqual(vb.planProblems(doc({ reject: null }, { service_date: null }), notes), []);
  assert.deepEqual(vb.planProblems(doc({ context_edit: { service_date: DOCUMENTED } }), notes), []);
  assert.deepEqual(vb.planProblems(doc({ context_edit: { clear_member_date: true }, approve_codes: ['43276'] }), notes), []);
  // round gi3: without a member date entered at upload, a date answers the encounter's open date question
  assert.deepEqual(vb.planProblems(doc({ context_edit: { service_date: DOCUMENTED } }, { service_date: null }), notes), []);
  const bad = [
    doc({ context_edit: { clear_member_date: true } }, { service_date: null }),  // no member date to clear
    doc({ context_edit: { service_date: DOCUMENTED, clear_member_date: true } }),
    doc({ context_edit: {} }),
    doc({ context_edit: { clear_member_date: false } }),
    doc({ context_edit: { service_date: '2026-02-30' } }),
    doc({ context_edit: { service_date: '10/07/2026' } }),
    doc({ context_edit: { service_date: MEMBER } }),  // the same date: no change to save
    doc({ context_edit: { servicedate: DOCUMENTED } }),
    doc({ context_edit: 'clear' }),
    doc({ approve_codes: '43276' }),
    doc({ approve_codes: ['43276', ''] }),
    doc({ approve_codes: ['43276', '43276'] }),
    doc({ reject: null }, { service_date: '2026-13-01' }),
  ];
  for (const item of bad) assert.equal(vb.planProblems(item, notes).length, 1, JSON.stringify(item));
  assert.equal(vb.planProblems(doc({ reject: null }), { approve: 'Synthetic verification review' }).length, 1);
  assert.equal(vb.planProblems(doc({ reject: { family: 'gi.egd' } }), { approve: notes.approve }).length, 1);
  assert.equal(vb.planProblems(doc({ second_review: { ask: true } }), { ...notes, second_review_approve: 'approved' }).length, 1);
});

const MUST_NOT = [{ family: 'gi.colonoscopy', reason: 'historical' }];

test('planDecisions never approves a code of a must_not_code family, and says so', () => {
  const plan = vb.planDecisions(encounter(), { reject: null }, NOTES, { mustNotCode: MUST_NOT });
  assert.deepEqual(plan.decisions.map(d => [d.code, d.action]), [['45331', 'approve']]);
  assert.deepEqual(plan.must_not_code_held, ['45380']);
  // a designated rejection may still fall in that family: rejecting is not approving
  const reject = vb.planDecisions(encounter(), { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES, { mustNotCode: MUST_NOT });
  assert.deepEqual(reject.decisions.map(d => [d.code, d.action]), [['45331', 'approve'], ['45380', 'reject']]);
  assert.deepEqual(reject.must_not_code_held, []);
  // without options, as before
  assert.deepEqual(vb.planDecisions(encounter(), { reject: null }, NOTES).decisions.map(d => d.action), ['approve', 'approve']);
});

test('planDecisions --no-auto-approve: no approval at all except the codes review_plan.approve_codes names', () => {
  const none = vb.planDecisions(encounter(), { reject: null }, NOTES, { noAutoApprove: true });
  assert.deepEqual(none.decisions, []);
  assert.deepEqual(none.not_in_approve_codes, ['45331', '45380']);
  const listed = vb.planDecisions(encounter(), { reject: null, approve_codes: ['45331', '45378', '99999'] }, NOTES, { noAutoApprove: true });
  assert.deepEqual(listed.decisions.map(d => [d.code, d.action, d.note]), [['45331', 'approve', NOTES.approve]]);
  assert.deepEqual(listed.not_in_approve_codes, ['45380']);
  assert.deepEqual(listed.approve_codes_unmatched, ['45378 (excluded)', '99999 (not proposed)']);
  // an explicit list is honoured without the option too, and the designated rejection never takes a listed code
  const both = vb.planDecisions(encounter(), { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] }, approve_codes: ['45380'] }, NOTES);
  assert.deepEqual(both.decisions.map(d => [d.code, d.action]), [['45380', 'approve']]);
  assert.equal(both.designated_missing, true);
  // a listed code of a must_not_code family is never approved: the plan contradicts the manifest
  const conflict = vb.planDecisions(encounter(), { reject: null, approve_codes: ['45380'] }, NOTES, { noAutoApprove: true, mustNotCode: MUST_NOT });
  assert.deepEqual(conflict.decisions, []);
  assert.deepEqual(conflict.plan_conflicts, ['45380 (gi.colonoscopy)']);
  // a second-review code still needs second_review.approve_codes
  const second = encounter();
  second.assessment.proposals[1].support = { origin: 'second_review', service: 'S1' };
  const secondPlan = vb.planDecisions(second, { reject: null, approve_codes: ['45331', '45380'] }, NOTES, { noAutoApprove: true });
  assert.deepEqual(secondPlan.decisions.map(d => d.code), ['45331']);
  assert.deepEqual(secondPlan.second_review_held, ['45380']);
});

test('planDecisions reports every ready code it leaves undecided exactly once', () => {
  const buckets = plan => [...plan.must_not_code_held, ...plan.plan_conflicts.map(c => c.split(' ')[0]), ...plan.not_in_approve_codes];
  // a second-review code the plan names, in a must_not_code family: a conflict, not also held
  const second = encounter();
  second.assessment.proposals[1].support = { origin: 'second_review', service: 'S1' };
  const named = vb.planDecisions(second, { reject: null, second_review: { approve_codes: ['45380'] } }, NOTES, { mustNotCode: MUST_NOT });
  assert.deepEqual(named.decisions.map(d => d.code), ['45331']);
  assert.deepEqual([named.plan_conflicts, named.must_not_code_held], [['45380 (gi.colonoscopy)'], []]);
  // under an explicit list, a code of a must_not_code family the list does not name is held, not lost
  const unnamed = vb.planDecisions(encounter(), { reject: null, approve_codes: ['45331'] }, NOTES, { mustNotCode: MUST_NOT });
  assert.deepEqual(unnamed.decisions.map(d => d.code), ['45331']);
  assert.deepEqual(buckets(unnamed), ['45380']);
  for (const plan of [named, unnamed, vb.planDecisions(encounter(), { reject: null }, NOTES, { noAutoApprove: true, mustNotCode: MUST_NOT })]) {
    const left = buckets(plan);
    assert.equal(new Set(left).size, left.length, JSON.stringify(plan));
  }
});

test('checkDecisionLabels: every decision made carries the agent label and its labelled note; none approved a must_not_code family', () => {
  const ack = 'I am an automated agent. ... This agent-executed synthetic review is not clinical approval or billing advice.';
  const LABELLED = { approve: NOTES.approve, reject: 'Agent-executed synthetic verification review - designated rejection' };
  const enc = decided(decided(encounter(), 'p-flex', 'approve', NOTES.approve), 'p-colo', 'reject', LABELLED.reject);
  enc.decisions.history.forEach(h => { h.acknowledgement = h.action === 'approve' ? ack : ''; });
  enc.assessment.proposals.forEach(p => { if (p.decision) p.decision.acknowledgement = p.decision.action === 'approve' ? ack : ''; });
  const made = [{ proposal_id: 'p-flex', code: '45331', family: 'gi.flex_sig', action: 'approve', note: NOTES.approve, http_status: 201, decision_id: 'd-p-flex' },
    { proposal_id: 'p-colo', code: '45380', family: 'gi.colonoscopy', action: 'reject', note: LABELLED.reject, http_status: 201, decision_id: 'd-p-colo' }];
  const good = vb.checkDecisionLabels(made, enc, MUST_NOT);
  assert.deepEqual(good.checks.map(r => `${r.id}:${r.status}`), ['decisions.labelled:pass', 'decisions.never_approved_must_not_code:pass']);
  assert.deepEqual(good.labels.map(l => [l.code, l.agent, l.note_kept, l.note_labelled, l.acknowledgement_labelled]),
    [['45331', true, true, true, true], ['45380', true, true, true, null]]);
  const human = clone(enc);
  human.decisions.history[0].reviewer_kind = 'human';
  assert.deepEqual(failures(vb.checkDecisionLabels(made, human, MUST_NOT).checks), ['decisions.labelled']);
  const edited = clone(enc);
  edited.decisions.history[1].note = 'rejected';
  assert.deepEqual(failures(vb.checkDecisionLabels(made, edited, MUST_NOT).checks), ['decisions.labelled']);
  const unacknowledged = clone(enc);
  unacknowledged.decisions.history[0].acknowledgement = 'I read the whole source document.';
  assert.deepEqual(failures(vb.checkDecisionLabels(made, unacknowledged, MUST_NOT).checks), ['decisions.labelled']);
  const unlabelled = [{ ...made[0], note: 'approved' }];
  const plain = clone(enc);
  plain.decisions.history[0].note = 'approved';
  assert.deepEqual(failures(vb.checkDecisionLabels(unlabelled, plain, MUST_NOT).checks), ['decisions.labelled']);
  assert.deepEqual(failures(vb.checkDecisionLabels([made[0]], decided(encounter(), 'p-flex', 'approve', NOTES.approve), MUST_NOT).checks), ['decisions.labelled']);
  const approvedMustNot = [{ ...made[1], action: 'approve', note: NOTES.approve }];
  const wrong = decided(encounter(), 'p-colo', 'approve', NOTES.approve);
  wrong.decisions.history[0].acknowledgement = ack;
  assert.deepEqual(failures(vb.checkDecisionLabels(approvedMustNot, wrong, MUST_NOT).checks), ['decisions.never_approved_must_not_code']);
  assert.deepEqual(vb.checkDecisionLabels([], encounter(), MUST_NOT).checks.map(r => r.status), ['pass', 'pass']);
});


// --- fix round gi2, agent 'truth' (refutation lens 'ops') ------------------------------------------------------------
//
// ops-1: clearing the member's date was judged against the server's OWN post-edit context, so a server that sent the
// cleared member date (mutant A), no date (B) or a date the document never states (C) passed with no hard failure.
// The date a clear must send is now named BEFORE the edit, from the encounter the walk saw: the document's own read
// date, which the member conflict's note names and its evidence quotes (none where the document gives no usable date),
// and the manifest's documented_date when it gives one; the edit is made only when that date is named.
// ops-2: --encounter attached a paste document to an encounter whose original is an uploaded file, or whose text had
// other line breaks (whitespace was collapsed); a paste document now attaches only to a pasted revision with no stored
// original whose text has the document's lines (only trailing whitespace and line-ending style normalised).

// studio/gi/context.py USER_CONFLICT_NOTE and USER_ELSEWHERE_NOTE, written out here so a wrong constant cannot pass.
const CONFLICT_NOTE = (user, document) => `Encounter metadata entered by a workspace member gives ${user}; the document `
  + `gives ${document}. Both are kept and neither is used until they agree: correct the metadata, clear it, or add an `
  + 'addendum to the document.';
const ELSEWHERE_NOTE = (user, document) => `Encounter metadata entered by a workspace member gives ${user}; this service `
  + 'reads that date in the document as another occurrence\'s or another document\'s date, or as possibly one '
  + `(${document}), and not as this encounter's date of service. Both are kept and neither is used: correct the metadata, `
  + 'clear it, or add an addendum to the document.';
// A date the gi-08 document never states, and the request for it: studio.providers.corti.build_coding_request (adapter
// corti-coding-v2@cptstudio-1) over this module's TEXT - the same builder reproduces GI08_REQUEST's three hashes.
const NEVER_STATED = '2026-10-09';
const NEVER_STATED_REQUEST = '8552d6e0d7df0ae7d3361b1b6e8b6d1b41f7145e805795a2d1899d6355aef8d5';
const CLEAR_POSTED = { ...EDIT_OK, posted: { service_date: '', setting: '', billing_context: '' } };
const REQUESTS = { ...GI08_REQUEST, [NEVER_STATED]: NEVER_STATED_REQUEST };

// The encounter once the member's date was cleared and the save's one request answered: the context states ``date``
// (null: none) and the request was made for ``sent`` (default: the stated date).
function clearedEncounter(before, { date = DOCUMENTED, origin = 'document', sent } = {}) {
  const enc = editedEncounter(before, { date, origin, userValue: null });
  enc.provider_runs[1].request_sha256 = REQUESTS[(sent === undefined ? date : sent) || 'none'];
  return enc;
}

function withServiceDate(enc, changes) {
  const out = clone(enc);
  out.context.facts.service_date = { ...out.context.facts.service_date, ...changes };
  return out;
}

const named = enc => (({ ok, date }) => ({ ok, date }))(vb.documentedServiceDate(enc));

test('the member-conflict notes and the date forms the walk reads are the server\'s own (studio/gi/context.py)', () => {
  const context = fs.readFileSync(path.join(ROOT, 'studio', 'gi', 'context.py'), 'utf8');
  const note = /^USER_CONFLICT_NOTE = \(((?:\s*'[^']*')+)\)/m.exec(context);
  assert.ok(note, 'USER_CONFLICT_NOTE not found in context.py');
  assert.equal([...note[1].matchAll(/'([^']*)'/g)].map(m => m[1]).join(''), vb.USER_CONFLICT_NOTE);
  assert.equal(vb.USER_CONFLICT_NOTE, CONFLICT_NOTE('{user}', '{document}'));
  const elsewhere = /^USER_ELSEWHERE_NOTE = \(_USER_CONFLICT_PREFIX \+ ((?:\s*(?:'[^']*'|"[^"]*"))+)\)/m.exec(context);
  assert.ok(elsewhere, 'USER_ELSEWHERE_NOTE not found in context.py');
  const prefix = vb.USER_CONFLICT_NOTE.split('{', 1)[0];
  assert.equal(prefix + [...elsewhere[1].matchAll(/'([^']*)'|"([^"]*)"/g)].map(m => m[1] ?? m[2]).join(''), vb.USER_ELSEWHERE_NOTE);
  assert.equal(vb.USER_ELSEWHERE_NOTE, ELSEWHERE_NOTE('{user}', '{document}'));
  // merge_user_values names the document's value itself only where the document gives one date of its own
  assert.equal(context.split('USER_CONFLICT_NOTE.format(user=value, document=documented.value))').length - 1, 1);
  assert.ok(context.includes("if documented is not None and documented.origin == 'document' and documented.value \\"));
  // the four full-date forms a documented date of service is read in (_FULL_DATE), and their month names
  for (const line of [
    "_MONTH = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?'",
    "          r'|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')",
    "_FULL_DATE = (r'(?P<iy>\\d{4})-(?P<im>\\d{2})-(?P<id>\\d{2})'",
    "              r'|(?P<um>\\d{1,2})/(?P<ud>\\d{1,2})/(?P<uy>\\d{4})'",
    "              r'|(?P<lm>' + _MONTH + r')\\.?[ \\t]+(?P<ld>\\d{1,2})(?:st|nd|rd|th)?,?[ \\t]+(?P<ly>\\d{4})'",
    "              r'|(?P<dd>\\d{1,2})(?:st|nd|rd|th)?(?:[ \\t]+|-)(?P<dm>' + _MONTH + r')\\.?(?:,?[ \\t]+|-)(?P<dy>\\d{4})')",
    "FULL_DATE = cues.rx(r'(?<![\\w/-])(?:' + _FULL_DATE + r')(?![\\w/-])')",
  ]) assert.ok(context.includes(`\n${line}\n`), line);
  const cues = fs.readFileSync(path.join(ROOT, 'studio', 'gi', 'cues.py'), 'utf8');
  assert.ok(cues.includes('\nFLAGS = re.A | re.I\n'), 'cues.rx flags changed (ASCII \\w, case-insensitive)');
});

test('quotedDates reads the four full-date forms, as calendar dates, and nothing else', () => {
  const read = text => [...vb.quotedDates(text)];
  assert.deepEqual(read('Date of service: 2026-10-07'), ['2026-10-07']);
  assert.deepEqual(read('DOS: 10/7/2026'), ['2026-10-07']);
  assert.deepEqual(read('Procedure date: Oct. 7th, 2026'), ['2026-10-07']);
  assert.deepEqual(read('Visit date: 7 October 2026'), ['2026-10-07']);
  assert.deepEqual(read('Date of service: 07-OCT-2026'), ['2026-10-07']);
  assert.deepEqual(read('DOS: 10/07/2026 and 2026-10-08'), ['2026-10-07', '2026-10-08']);
  for (const text of ['Date: 2026-02-30', 'DOS: 10/07/26', 'DOS: 2026/10/07', 'Date: 13/01/2026', 'x2026-10-07', '2026-10-07a',
    '1/2026-10-07', 'Date of service: Octember 7, 2026']) {
    assert.deepEqual(read(text), [], text);
  }
});

test('documentedServiceDate: the date clearing the member\'s leaves is named before the edit (ops-1)', () => {
  const before = heldEncounter();
  assert.deepEqual(named(before), { ok: true, date: DOCUMENTED });
  assert.match(vb.documentedServiceDate(before).reason, /2026-10-07/);
  // a document-internal conflict, a labelled date the reader cannot use, or one it reads as another occurrence's: the
  // document gives no date a request carries, so clearing the member's leaves a request with no date
  for (const note of [CONFLICT_NOTE(MEMBER, `${DOCUMENTED} or 2026-10-05`), CONFLICT_NOTE(MEMBER, '“Date of procedure: 2026-10-07”'),
    ELSEWHERE_NOTE(MEMBER, '“Date of procedure: 2026-10-07”')]) {
    assert.deepEqual(named(withServiceDate(before, { note })), { ok: true, date: null }, note);
  }
  // nothing a clear could be judged against: the walk names why and makes no edit
  const unnamed = [
    withServiceDate(before, { evidence: [at(BIOPSY)] }),  // the note's date is not quoted
    withServiceDate(before, { evidence: [] }),
    withServiceDate(before, { evidence: [{ ...at('Date of procedure: 2026-10-07'), start: 0, end: 29 }] }),  // inexact
    withServiceDate(before, { note: CONFLICT_NOTE(MEMBER, MEMBER) }),  // the member's own date
    withServiceDate(before, { note: CONFLICT_NOTE('2026-10-30', DOCUMENTED) }),  // another member value than stored
    withServiceDate(before, { note: `A member entered ${MEMBER}; the document states ${DOCUMENTED}.` }),  // unrecognised
    withServiceDate(before, { origin: 'document', value: DOCUMENTED, member_conflict: false, note: '' }),  // no conflict
  ];
  for (const enc of unnamed) assert.deepEqual(named(enc), { ok: false, date: null }, JSON.stringify(enc.context.facts.service_date));
  // the manifest's documented_date must be the date named before the edit
  assert.deepEqual(named(before), { ok: true, date: DOCUMENTED });
  assert.equal(vb.documentedServiceDate(before, { documented_date: DOCUMENTED }).ok, true);
  assert.equal(vb.documentedServiceDate(before, { documented_date: NEVER_STATED }).ok, false);
  assert.equal(vb.documentedServiceDate(withServiceDate(before, { note: CONFLICT_NOTE(MEMBER, '“DOS: 2026-10-07”') }), { documented_date: DOCUMENTED }).ok, false);
});

test('checkContextEdit: a cleared member date must send the date named before the edit, so mutants A, B and C fail (ops-1)', () => {
  const before = heldEncounter();
  const judge = after => hardFailures(vb.checkContextEdit(before, after, clone(after), CLEAR_PLAN, CLEAR_POSTED, MEMBER));
  const control = clearedEncounter(before);
  const results = vb.checkContextEdit(before, control, clone(control), CLEAR_PLAN, CLEAR_POSTED, MEMBER);
  assert.deepEqual(hardFailures(results), []);
  assert.deepEqual(results.filter(r => r.severity === 'hard').map(r => r.id), ['context_edit.held_before', 'context_edit.nothing_sent_before',
    'context_edit.documented_date', 'context_edit.request', 'context_edit.date_after', 'context_edit.one_request',
    'context_edit.sent_at_most_once', 'context_edit.hold_kept', 'context_edit.identical_save']);
  assert.match(results.find(r => r.id === 'context_edit.one_request').reason, /2026-10-07/);
  const wrong = ['context_edit.date_after', 'context_edit.one_request', 'context_edit.sent_at_most_once'];
  // A: the cleared member date is stated as the document's and sent
  assert.deepEqual(judge(clearedEncounter(before, { date: MEMBER })), wrong);
  // A2: the cleared member date stays the context's date (origin user) and is sent
  assert.deepEqual(judge(clearedEncounter(before, { date: MEMBER, origin: 'user' })), wrong);
  // B: no date is stated and the request is sent without one
  assert.deepEqual(judge(clearedEncounter(before, { date: null })), wrong);
  // C: a date the document never states is stated and sent
  assert.deepEqual(judge(clearedEncounter(before, { date: NEVER_STATED })), wrong);
  const result = vb.checkContextEdit(before, clearedEncounter(before, { date: NEVER_STATED }), null, CLEAR_PLAN, CLEAR_POSTED, MEMBER);
  assert.match(result.find(r => r.id === 'context_edit.one_request').reason, /2026-10-09, not the one for 2026-10-07/);
  // D (control): the context states the documented date, the request carries the member's
  assert.deepEqual(judge(clearedEncounter(before, { sent: MEMBER })), ['context_edit.one_request', 'context_edit.sent_at_most_once']);
});

test('checkContextEdit: where the document gives no date a request carries, a clear must send none (ops-1)', () => {
  const before = withServiceDate(heldEncounter(), { note: CONFLICT_NOTE(MEMBER, '“Date of procedure: 2026-10-07”') });
  const judge = after => hardFailures(vb.checkContextEdit(before, after, clone(after), CLEAR_PLAN, CLEAR_POSTED, MEMBER));
  assert.deepEqual(judge(clearedEncounter(before, { date: null })), []);
  assert.deepEqual(judge(clearedEncounter(before, { date: MEMBER })), ['context_edit.date_after', 'context_edit.one_request', 'context_edit.sent_at_most_once']);
  assert.deepEqual(judge(clearedEncounter(before)), ['context_edit.date_after', 'context_edit.one_request', 'context_edit.sent_at_most_once']);
});

test('the clear is made only on a date named before the edit, and the manifest\'s documented_date must be it (ops-1)', () => {
  const before = heldEncounter();
  const pre = (enc, plan) => vb.contextEditPreconditions(enc, MEMBER, plan).filter(r => r.status === 'fail').map(r => r.id);
  assert.deepEqual(pre(before, CLEAR_PLAN), []);
  assert.deepEqual(pre(before, { ...CLEAR_PLAN, documented_date: DOCUMENTED }), []);
  assert.deepEqual(pre(before, { ...CLEAR_PLAN, documented_date: NEVER_STATED }), ['context_edit.documented_date']);
  assert.deepEqual(pre(withServiceDate(before, { evidence: [at(BIOPSY)] }), CLEAR_PLAN), ['context_edit.documented_date']);
  // an edited date names its own date: nothing is added to that plan's preconditions
  assert.deepEqual(vb.contextEditPreconditions(before, MEMBER, SERVICE_DATE_PLAN).map(r => r.id), ['context_edit.held_before', 'context_edit.nothing_sent_before']);
  assert.deepEqual(vb.contextEditPreconditions(before, MEMBER).map(r => r.id), ['context_edit.held_before', 'context_edit.nothing_sent_before']);
  // judged without the date named, nothing after the save passes for it
  const unnamed = withServiceDate(before, { evidence: [at(BIOPSY)] });
  const control = clearedEncounter(unnamed);
  assert.ok(hardFailures(vb.checkContextEdit(unnamed, control, clone(control), CLEAR_PLAN, CLEAR_POSTED, MEMBER)).includes('context_edit.documented_date'));
  // the manifest names it, and the plan carries it
  assert.deepEqual(vb.contextEditPlan({ review_plan: { context_edit: { clear_member_date: true, documented_date: DOCUMENTED } } }),
    { clear_member_date: true, service_date: '', documented_date: DOCUMENTED });
  assert.deepEqual(vb.contextEditPlan({ review_plan: { context_edit: { clear_member_date: true } } }),
    { clear_member_date: true, service_date: '', documented_date: null });
  const notes = { approve: 'Agent-executed synthetic verification review' };
  const doc = edit => ({ id: 'h', upload: { service_date: MEMBER }, review_plan: { context_edit: edit } });
  assert.deepEqual(vb.planProblems(doc({ clear_member_date: true, documented_date: DOCUMENTED }), notes), []);
  for (const edit of [{ service_date: DOCUMENTED, documented_date: DOCUMENTED }, { documented_date: DOCUMENTED },
    { clear_member_date: true, documented_date: '10/07/2026' }, { clear_member_date: true, documented_date: null },
    { clear_member_date: true, documented_date: MEMBER }]) {
    assert.equal(vb.planProblems(doc(edit), notes).length, 1, JSON.stringify(edit));
  }
});

// The encounter() fixture is an UPLOAD (stored original gi-08.docx, 'a' x 64, 100 bytes); a pasted one has none.
function pastedEncounter(text = TEXT) {
  const enc = encounter();
  enc.revision = { ...enc.revision, kind: 'paste', source_file: null, text, text_sha256: sha(text),
    extraction: { ...enc.revision.extraction, method: 'paste' } };
  return enc;
}

function pasteItem(sourceText) {
  return { doc: { source: 'documents/gi-08-flexible-sigmoidoscopy-biopsy.txt', delivery: { file: 'gi-08.paste.txt' } }, sourceText,
    delivery: { format: 'paste', file: 'gi-08.paste.txt', sha256: sha(sourceText), size: Buffer.byteLength(sourceText) } };
}

function fileItem(sha256, size, sourceText = TEXT) {
  return { doc: { source: 'documents/gi-08-flexible-sigmoidoscopy-biopsy.txt', delivery: { file: 'gi-08.docx' } }, sourceText,
    delivery: { format: 'docx', file: 'gi-08.docx', sha256, size } };
}

test('attachedProblems: a paste document attaches only to a pasted revision with no stored original (ops-2 (1), (2))', () => {
  const uploaded = encounter();
  // (1) the same text delivered as a paste, on an encounter whose original is an uploaded file
  const same = vb.attachedProblems(uploaded, pasteItem(TEXT));
  assert.equal(same.length, 1, JSON.stringify(same));
  assert.match(same[0], /stored original/);
  // (2) the same, with its lines joined into one
  const joined = TEXT.replace(/\n/g, ' ');
  assert.equal(vb.attachedProblems(uploaded, pasteItem(joined)).length, 2);
  // the walk's own extraction checks fail on exactly what the gate now refuses before anything is done
  assert.deepEqual(failures(vb.checkExtraction({ text_matches_source: 'exact' }, uploaded, pasteItem(TEXT).delivery, TEXT)), ['revision.source']);
  assert.deepEqual(failures(vb.checkExtraction({ text_matches_source: 'exact' }, pastedEncounter(), pasteItem(joined).delivery, joined)), ['revision.text_equals_source']);
});

test('attachedProblems: a paste document\'s text keeps its lines; only trailing whitespace and line endings are normalised (ops-2 (2))', () => {
  const pasted = pastedEncounter();
  assert.deepEqual(vb.attachedProblems(pasted, pasteItem(TEXT)), []);
  assert.deepEqual(vb.attachedProblems(pasted, pasteItem(TEXT.replace(/\n/g, '\r\n'))), []);
  assert.deepEqual(vb.attachedProblems(pasted, pasteItem(TEXT.replace(/\n/g, '\r'))), []);
  assert.deepEqual(vb.attachedProblems(pasted, pasteItem(`${TEXT.trimEnd()}\n\n \t`)), []);
  assert.deepEqual(vb.attachedProblems(pastedEncounter(`${TEXT.trimEnd()}  `), pasteItem(TEXT)), []);
  for (const other of [
    TEXT.replace(/\n/g, ' '),  // every line joined
    TEXT.replace('\nDate of procedure: 2026-10-07', ' Date of procedure: 2026-10-07'),  // one line joined to the last
    TEXT.replace('Date of procedure: 2026-10-07', 'Date of procedure:\n2026-10-07'),  // a field's value moved to a line of its own
    TEXT.replace('Date of procedure: 2026-10-07', 'Date of procedure:   2026-10-07'),  // a field break the reader reads
    TEXT.replace('Date of procedure: 2026-10-07', 'Date of procedure: 2026-10-07  '),  // spaces ending a line, not the text
    ` ${TEXT}`,
  ]) {
    const problems = vb.attachedProblems(pasted, pasteItem(other));
    assert.equal(problems.length, 1, JSON.stringify(other.slice(0, 80)));
    assert.match(problems[0], /text is not the text of/);
  }
});

test('attachedProblems controls: another date and another file are refused; an uploaded original is matched by its bytes (ops-2 (3), (4))', () => {
  // (3) a paste with one date changed
  const otherDate = TEXT.replace('2026-10-07', '2026-10-06');
  assert.equal(vb.attachedProblems(pastedEncounter(), pasteItem(otherDate)).length, 1);
  assert.equal(vb.attachedProblems(encounter(), pasteItem(otherDate)).length, 2);
  // (4) a file document with other bytes; the same bytes attach
  assert.match(vb.attachedProblems(encounter(), fileItem('b'.repeat(64), 100))[0], /stored original/);
  assert.equal(vb.attachedProblems(encounter(), fileItem('a'.repeat(64), 101)).length, 1);
  assert.deepEqual(vb.attachedProblems(encounter(), fileItem('a'.repeat(64), 100)), []);
  // an uploaded document is identified by its stored original's bytes; its extracted text may space lines otherwise
  const extracted = encounter();
  extracted.revision.text = TEXT.replace(/\n/g, '\n\n');
  assert.deepEqual(vb.attachedProblems(extracted, fileItem('a'.repeat(64), 100)), []);
  const addendum = encounter();
  addendum.revision.text = `${TEXT}\nAddendum: signed later (fictional).`;
  assert.equal(vb.attachedProblems(addendum, fileItem('a'.repeat(64), 100)).length, 1);
  // a file document never attaches to a pasted encounter
  assert.match(vb.attachedProblems(pastedEncounter(), fileItem('a'.repeat(64), 100))[0], /stored original/);
});

test('verifyDocument refuses an attached encounter the gate rejects before it edits, asks or decides anything (ops-2)', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'verify_browser.cjs'), 'utf8');
  const body = source.slice(source.indexOf('async function verifyDocument('));
  const refusal = body.indexOf('if (foreign.length) throw new Error(`refusing to act on encounter');
  assert.ok(refusal > 0, 'the attach refusal is not in verifyDocument');
  assert.ok(body.indexOf('const foreign = record.attached ? attachedProblems(opView, item) : [];') < refusal);
  for (const act of ['await editContext(', 'await saveDetails(', 'await decide(']) {
    const at = body.indexOf(act);
    assert.ok(at > refusal, `${act} comes before the attach refusal`);
  }
});

// --- round gi3 (ops): the documented date question ------------------------------------------------------------------
//
// A document with NO upload.service_date whose review_plan.context_edit is {"service_date": ...} answers the
// encounter's open date question: its own dates conflict (or it states none the reader reads), so its primary request
// went without a "Date of service" line. The fixture is gi-08 with a second labelled date in its header, which the
// server's reader reads as a document-internal conflict ("Conflicting documented values: 2026-10-07, 2026-10-08.").
// Its request hashes were computed by studio.providers.corti.build_coding_request over QUESTION_TEXT (the builder that
// gives GI08_REQUEST's), and the encounter shapes below are the ones the server served for this text in a contract run
// of the real API (disposable database, in-process provider): the dateless request before; after the member's answer,
// one new primary run for the answered date and no date question; the same save made again adding no run.
const QUESTION_TEXT = TEXT.replace('Date of procedure: 2026-10-07\n', 'Date of procedure: 2026-10-07\nDate of service: 2026-10-08\n');
const QUESTION_REQUEST = {
  none: '603ebb17c53dc971b6e7a9eb4eccfb9f188dac2eb9665bacbddfeb66a7a246de',
  '2026-10-07': 'ca2f62e386788b20b503e81e6a5fe233ed79dfbd489a4cff11cf70844e19d620',
  '2026-10-08': '22360f3669b3064dc456a198262e2890baa21ba2f9f9bdc75a24b8d191fcfd84',
  '2026-10-09': '4f82b73078745bd4a6591fcf815dc2f692c5fdc69bc738910ad9d20505ddf2b7',
};
const ANSWER = '2026-10-08';
const QUESTION_PLAN = { clear_member_date: false, service_date: ANSWER, answers_question: true };
// studio/validation/checks.py service_date_clarification, as the server served it for QUESTION_TEXT
const DATE_QUESTION = { id: 'c-date', scope: 'encounter', proposal_id: null, family: '', fact: 'service_date', state: 'open',
  question: 'Confirm the date of service for this encounter.',
  reason: 'Conflicting dates of service are documented (“Date of procedure: 2026-10-07”, “Date of service: 2026-10-08”); '
    + 'every service and every dated reference check depends on it.' };
const USER_NOTE = 'Supplied by a workspace member as encounter metadata; not clinical documentation.';
const ANSWER_EDIT = { http_status: 201, error: null, posted: { answers: [{ id: 'detail-date', fact: 'service_date', value: ANSWER }] },
  identical: { via: 'api', http_status: 201, error: null, panel_asks_again: false } };
const QUESTION_HARD = ['context_edit.question_open', 'context_edit.date_unestablished', 'context_edit.dateless_before',
  'context_edit.request', 'context_edit.date_after', 'context_edit.one_request', 'context_edit.sent_at_most_once',
  'context_edit.earlier_runs_kept', 'context_edit.question_closed', 'context_edit.identical_save'];

function inQuestion(passage) {
  const start = QUESTION_TEXT.indexOf(passage);
  assert.ok(start >= 0, `fixture passage not in the document: ${passage}`);
  return { start, end: start + passage.length, text: passage };
}

// The encounter once processing finished: the document's own dates conflict, the date is asked at the encounter, and
// its one primary request was made, and answered, without a date line. A pasted revision, as the walk attaches one.
function questionEncounter() {
  const enc = encounter({ state: 'needs_clarification', provider_runs: [run('run-dateless', { request_sha256: QUESTION_REQUEST.none })],
    clarifications: [clone(DATE_QUESTION)], readiness: { draft: false, reviewed: false, blockers: [] } });
  enc.revision = { ...enc.revision, kind: 'paste', source_file: null, text: QUESTION_TEXT, text_sha256: sha(QUESTION_TEXT),
    pages: [{ page: 1, start: 0, end: QUESTION_TEXT.length }], extraction: { ...enc.revision.extraction, method: 'paste' } };
  enc.context = { facts: {
    service_date: { name: 'service_date', value: null, origin: 'conflict', member_conflict: false,
      note: 'Conflicting documented values: 2026-10-07, 2026-10-08.',
      evidence: [inQuestion('Date of procedure: 2026-10-07'), inQuestion('Date of service: 2026-10-08')] },
    setting: { name: 'setting', value: 'office', origin: 'document', member_conflict: false, note: '',
      evidence: [inQuestion('Place of service: Office')] } }, user_values: {} };
  enc.routing = { ...enc.routing, families: [] };  // encounter()'s routing spans are at the plain gi-08 text's offsets
  enc.assessment = { ...enc.assessment, id: 'asm-question', proposals: [] };
  return enc;
}

// The encounter once the member's answer was saved and its processing settled: the context states ``date`` (with
// ``origin``) and the member value ``userValue``; the one new run carries the request for ``sent``; ``questions`` are
// the new assessment's questions (none: the question closed).
function answeredEncounter(before, { date = ANSWER, origin = 'user', userValue = ANSWER, sent = date, runs = null, questions = [] } = {}) {
  const enc = clone(before);
  enc.state = 'no_codes';
  enc.provider_runs = runs || [...clone(before.provider_runs), run('run-answer', { request_sha256: QUESTION_REQUEST[sent || 'none'] })];
  enc.context.facts.service_date = { name: 'service_date', value: date, origin, member_conflict: false, note: USER_NOTE, evidence: [] };
  enc.context.user_values = userValue ? { service_date: userValue } : {};
  enc.clarifications = questions;
  enc.assessment = { ...enc.assessment, id: 'asm-answered' };
  return enc;
}

test('planProblems and contextEditPlan: without upload.service_date a date answers the open date question; clear_member_date needs a member date', () => {
  const notes = { approve: 'Agent-executed synthetic verification review' };
  const doc = (edit, upload) => ({ id: 'q', upload, review_plan: { context_edit: edit } });
  for (const upload of [{ service_date: null }, { service_date: '' }, {}, undefined]) {
    assert.deepEqual(vb.planProblems(doc({ service_date: ANSWER }, upload), notes), [], JSON.stringify(upload));
    assert.deepEqual(vb.contextEditPlan(doc({ service_date: ANSWER }, upload)), QUESTION_PLAN, JSON.stringify(upload));
  }
  // a member date entered at upload: the member-conflict plans, exactly as before
  assert.deepEqual(vb.contextEditPlan(doc({ service_date: DOCUMENTED }, { service_date: MEMBER })), { clear_member_date: false, service_date: DOCUMENTED });
  assert.deepEqual(vb.contextEditPlan(doc({ clear_member_date: true }, { service_date: MEMBER })),
    { clear_member_date: true, service_date: '', documented_date: null });
  for (const edit of [{ clear_member_date: true }, { clear_member_date: true, documented_date: DOCUMENTED },
    { service_date: ANSWER, documented_date: ANSWER }, { service_date: '2026-02-30' }, { service_date: '10/08/2026' },
    { service_date: ANSWER, clear_member_date: true }, {}, { answer: ANSWER }]) {
    const problems = vb.planProblems(doc(edit, { service_date: null }), notes);
    assert.equal(problems.length, 1, JSON.stringify([edit, problems]));
  }
  assert.match(vb.planProblems(doc({ clear_member_date: true }, { service_date: null }), notes)[0],
    /clear_member_date clears the member's date entered at upload, but upload\.service_date gives none/);
});

test('the documented date question: the answer makes one request for the answered date, closes the question, and the same save sends nothing', () => {
  const before = questionEncounter();
  const after = answeredEncounter(before);
  const results = vb.checkContextEdit(before, after, clone(after), QUESTION_PLAN, ANSWER_EDIT, null);
  assert.deepEqual(results.filter(r => r.status !== 'pass').map(r => `${r.id}:${r.status}`), []);
  assert.deepEqual(results.filter(r => r.severity === 'hard').map(r => r.id), QUESTION_HARD);
  assert.match(results.find(r => r.id === 'context_edit.one_request').reason,
    /1 new run\(s\): primary\/succeeded; one request sent; its request is the request for the revision text and 2026-10-08/);
  assert.match(results.find(r => r.id === 'context_edit.dateless_before').reason, /each the request for the revision text with no date/);
  // the walk's gate is the same three preconditions
  assert.deepEqual(vb.contextEditPreconditions(before, null, QUESTION_PLAN).map(r => `${r.id}:${r.status}`),
    ['context_edit.question_open:pass', 'context_edit.date_unestablished:pass', 'context_edit.dateless_before:pass']);
  // a retained identical answer reused for the answered date: nothing sent, and it passes
  const reused = answeredEncounter(before, { runs: [...clone(before.provider_runs),
    run('run-answer', { request_sha256: QUESTION_REQUEST[ANSWER], reused_from: 'run-elsewhere', usage: {}, http_status: null })] });
  const reuse = vb.checkContextEdit(before, reused, clone(reused), QUESTION_PLAN, ANSWER_EDIT, null);
  assert.deepEqual(hardFailures(reuse), []);
  assert.match(reuse.find(r => r.id === 'context_edit.one_request').reason, /a retained answer was reused \(nothing sent\)/);
  // ... and where the dateless request itself was a reuse of a retained answer
  const reusedBefore = questionEncounter();
  reusedBefore.provider_runs = [run('run-dateless', { request_sha256: QUESTION_REQUEST.none, reused_from: 'run-first', usage: {} })];
  const afterReuse = answeredEncounter(reusedBefore);
  assert.deepEqual(hardFailures(vb.checkContextEdit(reusedBefore, afterReuse, clone(afterReuse), QUESTION_PLAN, ANSWER_EDIT, null)), []);
  // the shape the server serves for a document that states no date at all: missing, with nothing quoted
  const undated = questionEncounter();
  undated.context.facts.service_date = { name: 'service_date', value: null, origin: 'missing', member_conflict: false,
    note: 'No labelled date of service is documented.', evidence: [] };
  undated.clarifications[0].reason = 'No date of service is documented; every service and every dated reference check depends on it.';
  const afterUndated = answeredEncounter(undated);
  assert.deepEqual(hardFailures(vb.checkContextEdit(undated, afterUndated, clone(afterUndated), QUESTION_PLAN, ANSWER_EDIT, null)), []);
});

test('the documented date question: the edit is made only on an open question, an unestablished date and a dateless request', () => {
  const pre = enc => vb.contextEditPreconditions(enc, null, QUESTION_PLAN).filter(r => r.status === 'fail').map(r => r.id);
  const changed = change => {
    const enc = questionEncounter();
    change(enc);
    return enc;
  };
  assert.deepEqual(pre(questionEncounter()), []);
  // no open encounter question: none, answered, withdrawn, about another fact, or asked only of a proposal or service
  for (const [label, change] of [
    ['none', enc => { enc.clarifications = []; }],
    ['answered', enc => { enc.clarifications[0].state = 'answered'; }],
    ['withdrawn', enc => { enc.clarifications[0].state = 'withdrawn'; }],
    ['another fact', enc => { enc.clarifications[0].fact = 'setting'; }],
    ['a proposal\'s', enc => { Object.assign(enc.clarifications[0], { scope: 'proposal', proposal_id: 'p-1' }); }],
    ['an encounter question held by a proposal', enc => { enc.clarifications[0].proposal_id = 'p-1'; }],
    ['a service\'s', enc => { enc.clarifications[0].scope = 'service'; }],
  ]) assert.deepEqual(pre(changed(change)), ['context_edit.question_open'], label);
  assert.match(vb.contextEditPreconditions(changed(enc => { enc.clarifications[0].scope = 'service'; }), null, QUESTION_PLAN)[0].reason,
    /no open encounter-scope service_date question.*open elsewhere: service "Confirm the date of service/);
  // a service date established: documented, in use as a member's, a member value stored, or a member conflict
  for (const [label, change] of [
    ['documented', enc => { enc.context.facts.service_date = { name: 'service_date', value: DOCUMENTED, origin: 'document',
      member_conflict: false, note: '', evidence: [inQuestion('Date of procedure: 2026-10-07')] }; }],
    ['a member\'s date in use', enc => { enc.context.facts.service_date = { name: 'service_date', value: MEMBER, origin: 'user',
      member_conflict: false, note: USER_NOTE, evidence: [] }; enc.context.user_values = { service_date: MEMBER }; }],
    ['a member value stored', enc => { enc.context.user_values = { service_date: ANSWER }; }],
    ['a member conflict', enc => { Object.assign(enc.context.facts.service_date, { member_conflict: true,
      note: CONFLICT_NOTE(MEMBER, '2026-10-07 or 2026-10-08') }); enc.context.user_values = { service_date: MEMBER }; }],
  ]) assert.deepEqual(pre(changed(change)), ['context_edit.date_unestablished'], label);
  // a primary request carried a date (or another text), or none was answered: proven from the request hashes
  const dated = changed(enc => { enc.provider_runs[0].request_sha256 = QUESTION_REQUEST['2026-10-07']; });
  assert.deepEqual(pre(dated), ['context_edit.dateless_before']);
  assert.match(vb.contextEditPreconditions(dated, null, QUESTION_PLAN)[2].reason, /carries the request for 2026-10-07/);
  assert.deepEqual(pre(changed(enc => { enc.provider_runs.push(run('run-dated', { request_sha256: QUESTION_REQUEST[ANSWER] })); })),
    ['context_edit.dateless_before']);
  const otherText = changed(enc => { enc.provider_runs[0].request_sha256 = GI08_REQUEST.none; });
  assert.match(vb.contextEditPreconditions(otherText, null, QUESTION_PLAN)[2].reason,
    /carries none of the requests for no date, 2026-10-07, 2026-10-08/);
  for (const [label, runs] of [
    ['no run', []],
    ['only a hold', [hold()]],
    ['not sent', [run('run-x', { state: 'not_sent', usage: {}, http_status: null, request_sha256: QUESTION_REQUEST.none,
      error: 'Corti refused the token request; nothing was sent.' })]],
    ['cancelled', [run('run-x', { state: 'cancelled', usage: {}, http_status: null, request_sha256: QUESTION_REQUEST.none,
      error: 'Stopped before sending; nothing was sent.' })]],
    ['a second review only', [run('run-2', { purpose: 'second_review', request_sha256: 'e'.repeat(64) })]],
  ]) assert.deepEqual(pre(changed(enc => { enc.provider_runs = runs; })), ['context_edit.dateless_before'], label);
  // judged without an edit (the walk's refusal), nothing after the gate is judged and the request it did not make fails
  const notMade = vb.checkContextEdit(changed(enc => { enc.clarifications = []; }), null, null, QUESTION_PLAN,
    { http_status: null, error: 'not made: context_edit.question_open failed, so the edit has nothing verified to answer' }, null);
  assert.deepEqual(notMade.map(r => `${r.id}:${r.status}`), ['context_edit.question_open:fail', 'context_edit.date_unestablished:pass',
    'context_edit.dateless_before:pass', 'context_edit.request:fail']);
});

test('the documented date question: each check after the edit fails on the broken server shape it exists for', () => {
  const before = questionEncounter();
  const after = answeredEncounter(before);
  const judge = (shape, settled = clone(shape), edit = ANSWER_EDIT) => hardFailures(vb.checkContextEdit(before, shape, settled, QUESTION_PLAN, edit, null));
  const wrongRequest = ['context_edit.one_request', 'context_edit.sent_at_most_once'];
  assert.deepEqual(judge(after), []);
  // the answer was not taken: held as a member conflict, re-checked with the dateless run, the question still open
  const held = answeredEncounter(before, { runs: clone(before.provider_runs), questions: [{ ...clone(DATE_QUESTION),
    reason: `The date of service is in conflict. ${CONFLICT_NOTE(ANSWER, '2026-10-07 or 2026-10-08')}` }] });
  held.context.facts.service_date = { name: 'service_date', value: null, origin: 'conflict', member_conflict: true,
    evidence: clone(before.context.facts.service_date.evidence), note: CONFLICT_NOTE(ANSWER, '2026-10-07 or 2026-10-08') };
  assert.deepEqual(judge(held), ['context_edit.date_after', 'context_edit.one_request', 'context_edit.question_closed']);
  // the context states the answer but not as the member's, another member value is stored, or another date is stated
  assert.deepEqual(judge(answeredEncounter(before, { origin: 'document' })), ['context_edit.date_after']);
  assert.deepEqual(judge(answeredEncounter(before, { userValue: '2026-10-07' })), ['context_edit.date_after']);
  assert.deepEqual(judge(answeredEncounter(before, { date: '2026-10-07', userValue: '2026-10-07', sent: ANSWER })), ['context_edit.date_after']);
  // nothing requested for the answer; the dateless request sent again; a request for another date; two requests
  assert.deepEqual(judge(answeredEncounter(before, { runs: clone(before.provider_runs) })), ['context_edit.one_request']);
  const resent = answeredEncounter(before, { sent: null });
  assert.deepEqual(judge(resent), wrongRequest);
  assert.match(vb.checkContextEdit(before, resent, clone(resent), QUESTION_PLAN, ANSWER_EDIT, null)
    .find(r => r.id === 'context_edit.one_request').reason, /its request is the request for no date, not the one for 2026-10-08/);
  assert.deepEqual(judge(answeredEncounter(before, { sent: '2026-10-07' })), wrongRequest);
  assert.deepEqual(judge(answeredEncounter(before, { sent: '2026-10-09' })), wrongRequest);
  assert.deepEqual(judge(answeredEncounter(before, { runs: [...clone(before.provider_runs), run('run-a', { request_sha256: QUESTION_REQUEST[ANSWER] }),
    run('run-b', { request_sha256: QUESTION_REQUEST[ANSWER] })] })), wrongRequest);
  // a hold, a request not sent, a cancelled one, or a second review in place of the primary request
  for (const [label, extra] of [
    ['a hold', hold('run-hold-q')],
    ['not sent', run('run-x', { state: 'not_sent', usage: {}, http_status: null, request_sha256: QUESTION_REQUEST[ANSWER],
      error: 'Corti refused the token request; nothing was sent.' })],
    ['cancelled', run('run-x', { state: 'cancelled', usage: {}, http_status: null, request_sha256: QUESTION_REQUEST[ANSWER],
      error: 'Stopped before sending; nothing was sent.' })],
    ['a second review', run('run-x', { purpose: 'second_review', request_sha256: QUESTION_REQUEST[ANSWER] })],
  ]) assert.deepEqual(judge(answeredEncounter(before, { runs: [...clone(before.provider_runs), extra] })), ['context_edit.one_request'], label);
  // an earlier run changed, or went missing
  const rewritten = clone(after);
  rewritten.provider_runs[0].usage = {};
  assert.deepEqual(judge(rewritten), ['context_edit.earlier_runs_kept']);
  assert.deepEqual(judge(answeredEncounter(before, { runs: [run('run-answer', { request_sha256: QUESTION_REQUEST[ANSWER] })] })),
    ['context_edit.earlier_runs_kept']);
  // the date question still open after the save (at any scope), or open again after the same save made again
  assert.deepEqual(judge(answeredEncounter(before, { questions: [clone(DATE_QUESTION)] })), ['context_edit.question_closed']);
  assert.deepEqual(judge(answeredEncounter(before, { questions: [{ ...clone(DATE_QUESTION), scope: 'proposal', proposal_id: 'p-1' }] })),
    ['context_edit.question_closed']);
  assert.deepEqual(judge(after, answeredEncounter(before, { questions: [clone(DATE_QUESTION)] })), ['context_edit.question_closed']);
  // the same save made again sent the request again, held, changed a run, was refused, or was never made
  const resentAgain = clone(after);
  resentAgain.provider_runs.push(run('run-again', { request_sha256: QUESTION_REQUEST[ANSWER] }));
  assert.deepEqual(judge(after, resentAgain), ['context_edit.identical_save']);
  const heldAgain = clone(after);
  heldAgain.provider_runs.push(hold('run-hold-again'));
  assert.deepEqual(judge(after, heldAgain), ['context_edit.identical_save']);
  const changedAgain = clone(after);
  changedAgain.provider_runs[1].usage = {};
  assert.deepEqual(judge(after, changedAgain), ['context_edit.identical_save']);
  assert.deepEqual(judge(after, null), ['context_edit.identical_save']);
  assert.deepEqual(judge(after, clone(after), { ...ANSWER_EDIT, identical: { ...ANSWER_EDIT.identical, http_status: 409, error: 'Wait for processing to finish' } }),
    ['context_edit.identical_save']);
  // the save was refused: nothing after it is judged
  const refused = vb.checkContextEdit(before, null, null, QUESTION_PLAN, { ...ANSWER_EDIT, http_status: 409, error: 'Wait for processing to finish' }, null);
  assert.deepEqual(refused.map(r => `${r.id}:${r.status}`), ['context_edit.question_open:pass', 'context_edit.date_unestablished:pass',
    'context_edit.dateless_before:pass', 'context_edit.request:fail']);
  // an unknown outcome is the operator's to reconcile: soft, as for a member conflict's request
  const unknown = answeredEncounter(before, { runs: [...clone(before.provider_runs), run('run-u', { state: 'unknown', http_status: null,
    usage: {}, response_sha256: '', request_sha256: QUESTION_REQUEST[ANSWER] })] });
  const outcome = vb.checkContextEdit(before, unknown, clone(unknown), QUESTION_PLAN, ANSWER_EDIT, null);
  assert.deepEqual(hardFailures(outcome), []);
  assert.deepEqual(statuses(outcome, 'context_edit.outcome'), ['warn']);
});

test('the date question, the dateless request and the answer the walk reads are the server\'s own', () => {
  const read = (...parts) => fs.readFileSync(path.join(ROOT, ...parts), 'utf8');
  const corti = read('studio', 'providers', 'corti.py');
  assert.ok(corti.includes("    contexts = (text,) if service_date is None else (text, f'Date of service: {service_date.isoformat()}')"),
    'the dateless request (no date context line) changed');
  for (const [date, want] of Object.entries(QUESTION_REQUEST)) {
    assert.equal(vb.primaryRequestSha256(QUESTION_TEXT, date === 'none' ? null : date), want, date);
  }
  assert.ok(read('studio', 'validation', 'checks.py').includes("    return ClarificationSpec(scope='encounter', fact='service_date',\n"
    + "                             question='Confirm the date of service for this encounter.',"), 'the date question changed');
  const serializers = read('studio', 'serializers.py');
  assert.ok(serializers.includes("    return {'id': str(clarification.pk), 'scope': clarification.scope,\n"
    + "            'proposal_id': str(clarification.proposal_id) if clarification.proposal_id else None,\n"
    + "            'family': clarification.family, 'fact': clarification.fact, 'question': clarification.question,\n"
    + "            'reason': clarification.reason, 'state': clarification.state}"), 'the served clarification changed');
  // only the current assessment's questions are served, so an answered question is not open after the save
  assert.ok(serializers.includes('    clarifications = list(assessment.clarifications.all())'));
  // a member date that settles the question is stated as the member's (origin 'user')
  assert.ok(read('studio', 'gi', 'context.py').includes("        merged[name] = Fact(name, value, 'user', (), USER_NOTE)\n    return merged"));
  // the save makes a request unless the run in use answers the answered context's request; a re-check never queues the
  // second review
  const jobs = read('studio', 'jobs.py');
  assert.ok(jobs.includes('        if _run_answers(last_run, revision, context) and not owed:'));
  assert.ok(jobs.includes('    # The bounded second review is never queued here: a workspace owner or reviewer asks for it'));
});





// --- the ordinary-reviewer acceptance mode (CPT Studio GI interpretation 63) ------------------------------------------
//
// --acceptance-reviewer signs the ordinary reviewer account in with --password-file and --username (as
// ops/verify_login.py takes them), makes approvals only - of the codes review_plan.approve_codes names - and checks after
// the reload that each is recorded as that human reviewer's with its labelled note kept verbatim. What the app stores for
// a human approval is read from its own source here, never written out as the walk's expectation.

const ACC_LABEL = 'session-made synthetic acceptance-test approval, not a human review';
const ACC_NOTE = 'Session-made synthetic acceptance-test approval, not a human review - CPT Studio GI round 4, owner item 5';
const ACC_NOTES = { approve: ACC_NOTE };
const AGENT_NOTES = { approve: 'Agent-executed synthetic verification review',
  reject: 'Agent-executed synthetic verification review - designated rejection',
  confirm: 'Agent-executed synthetic verification review - confirms an exclusion the author marked as not coded' };
const REVIEW_PY = fs.readFileSync(path.join(ROOT, 'studio', 'review.py'), 'utf8');

// studio/review.py ACKNOWLEDGEMENTS: the attestation an approval must carry for each actor kind, which the app stores.
function attestation(kind) {
  const found = new RegExp(`^ {4}'${kind}': \\(((?:\\s*'[^']*')+)\\),$`, 'm').exec(REVIEW_PY);
  assert.ok(found, `ACKNOWLEDGEMENTS['${kind}'] not found in studio/review.py`);
  return [...found[1].matchAll(/'([^']*)'/g)].map(m => m[1]).join('');
}

// The ordinary reviewer as /api/session serves them (serializers.session_json), and the walk's account taken from it.
const HUMAN_SESSION = {
  user: { id: 'u-1', username: 'demo-reviewer', label: 'Demo Reviewer', actor_kind: 'human', initials: 'DR' },
  workspace: { id: 'w-1', name: 'Gastroenterology', subtitle: 'Synthetic demonstration workspace',
    category: { slug: 'gastroenterology', name: 'Gastroenterology', profiles_version: 'gi@1' } },
  role: 'reviewer', can_review: true, acknowledgement: attestation('human'), counts: { documents: 0, queue: 0 },
  synthetic_only: true, provider_mode: 'replay', release: 'x' };
const ACCOUNT = vb.reviewerAccount(HUMAN_SESSION);
const AGENT_ACCOUNT = { username: 'review-agent', label: AGENT, actor_kind: 'agent', acknowledgement: attestation('agent') };
const DECIDED_STATES = { approve: 'approved', reject: 'rejected', confirm: 'exclusion_confirmed' };

// ``id`` decided as studio/review.py record_decision records it and serializers._decision_json serves it, by ``account``.
function decidedBy(enc, id, action, note, account = ACCOUNT) {
  const p = enc.assessment.proposals.find(item => item.id === id);
  p.decision = { id: `d-${id}`, proposal_id: id, code: p.code, action, note, reviewer: account.label, reviewer_kind: account.actor_kind,
    created_at: '2026-11-01T21:00:00Z', decided_at: '2026-11-01T21:00:00Z', carried_at: null,
    acknowledgement: action === 'approve' ? account.acknowledgement : '', carried_from: null, invalidated: null, revision_number: 1 };
  p.decision_state = DECIDED_STATES[action];
  p.allowed_actions = ['revoke'];
  p.customer = { approve: statement('approved', account.actor_kind === 'agent' ? AGENT_REVIEW : '', ['revoke']),
    reject: statement('excluded', 'Rejected in review', ['revoke']),
    confirm: statement('excluded', 'Exclusion confirmed in review', ['revoke']) }[action] || p.customer;
  enc.decisions.history.push(clone(p.decision));
  return enc;
}

function privateDir() {
  return fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'cpt-verify-acceptance-'));
}

function writeFile(dir, name, content, mode = 0o600) {
  const file = path.join(dir, name);
  fs.rmSync(file, { force: true });  // a file left read-only (0400) by the last write is replaced, not rewritten
  fs.writeFileSync(file, content);
  fs.chmodSync(file, mode);
  return file;
}

const SIGN_IN = ['--base-url', 'https://x', '--operator-credentials', 'op', '--docs', 'd', '--manifest', 'm', '--out', 'o'];

test('a human approval as the app records it: the account\'s actor kind, its label, the human attestation the session serves', () => {
  const human = attestation('human');
  assert.notEqual(human, attestation('agent'));
  assert.ok(REVIEW_PY.includes('        if action == APPROVE and acknowledgement != ACKNOWLEDGEMENTS.get(user.actor_kind):\n'),
    'an approval no longer has to carry the attestation of its own actor kind');
  assert.ok(REVIEW_PY.includes('            note=note, reviewer=user, reviewer_kind=user.actor_kind, acknowledgement=acknowledgement,\n'),
    'a decision no longer records the account and its actor kind');
  assert.ok(REVIEW_PY.includes("        note, acknowledgement = (note or '').strip(), (acknowledgement or '').strip()\n"));
  const serializers = fs.readFileSync(path.join(ROOT, 'studio', 'serializers.py'), 'utf8');
  assert.ok(serializers.includes("        'action': decision.action, 'note': decision.note, 'reviewer': decision.reviewer.label(),\n"
    + "        'reviewer_kind': decision.reviewer_kind,"), 'the served decision changed');
  assert.ok(serializers.includes("        'acknowledgement': review.ACKNOWLEDGEMENTS.get(user.actor_kind, ''),\n"), 'the session\'s attestation changed');
  assert.ok(serializers.includes("    return {'id': str(user.pk), 'username': user.get_username(), 'label': user.label(),\n"));
  // a human's label is their own name: the reviewer a decision names is the session's label
  const models = fs.readFileSync(path.join(ROOT, 'studio', 'models.py'), 'utf8');
  assert.ok(models.includes("        name = self.display_name or self.get_username()\n        if self.actor_kind == self.AGENT:\n"
    + "            return f'{name} (automated agent)'\n        return name\n"), 'User.label changed');
  assert.deepEqual(ACCOUNT, { username: 'demo-reviewer', label: 'Demo Reviewer', actor_kind: 'human', acknowledgement: human });
});

test('parseArgs: --password-file with --username signs in instead of --credentials, never both (as verify_login.py)', () => {
  const pw = vb.parseArgs([...SIGN_IN, '--password-file', 'reviewer.password', '--username', 'demo-reviewer']);
  assert.deepEqual([pw.passwordFile, pw.username, pw.credentials, pw.acceptanceReviewer, pw.noAutoApprove],
    ['reviewer.password', 'demo-reviewer', undefined, false, false]);
  assert.equal(vb.parseArgs([...SIGN_IN, '--password-file=p', '--username=u']).passwordFile, 'p');
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--credentials', 'c.json', '--password-file', 'p', '--username', 'u']), /mutually exclusive/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--password-file', 'p']), /--password-file needs --username/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--password-file', 'p', '--username', '  ']), /--password-file needs --username/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--password-file', 'p', '--username', '']), /--username needs a value/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--password-file', '', '--username', 'u']), /--password-file needs a value/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--credentials', 'c.json', '--username', 'u']), /--username goes with --password-file/);
  assert.throws(() => vb.parseArgs(SIGN_IN), /missing --credentials \(or --password-file with --username\)/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--username', 'u']), /missing --credentials/);
  // a credentials file, as before: no account is named and nothing else changes
  const agent = vb.parseArgs([...SIGN_IN, '--credentials', 'agent.json']);
  assert.deepEqual([agent.credentials, agent.passwordFile, agent.username, agent.acceptanceReviewer, agent.noAutoApprove],
    ['agent.json', undefined, undefined, false, false]);
});

test('parseArgs: --expect-harness is a flag, off by default, that takes no value', () => {
  assert.equal(vb.parseArgs([...SIGN_IN, '--credentials', 'c.json']).expectHarness, false);
  assert.equal(vb.parseArgs([...SIGN_IN, '--credentials', 'c.json', '--expect-harness']).expectHarness, true);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--credentials', 'c.json', '--expect-harness=no']), /--expect-harness takes no value/);
});

test('parseArgs: --acceptance-reviewer is a flag that implies --no-auto-approve and signs in only with a password file', () => {
  const acc = vb.parseArgs([...SIGN_IN, '--password-file', 'p', '--username', 'demo-reviewer', '--acceptance-reviewer']);
  assert.deepEqual([acc.acceptanceReviewer, acc.noAutoApprove], [true, true]);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--credentials', 'c.json', '--acceptance-reviewer']),
    /--acceptance-reviewer signs the reviewer in with --password-file and --username/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--password-file', 'p', '--username', 'u', '--acceptance-reviewer=yes']), /takes no value/);
  assert.throws(() => vb.parseArgs([...SIGN_IN, '--acceptance-reviewer']), /missing --credentials/);
});

test('loadPasswordFile: a private file holding only the password; one trailing line break is not part of it', () => {
  const dir = privateDir();
  try {
    const read = (content, mode) => vb.loadPasswordFile(writeFile(dir, 'pw', content, mode), 'demo-reviewer');
    assert.deepEqual(read('correct horse ✓ battery\n'), { username: 'demo-reviewer', password: 'correct horse ✓ battery', source: 'password_file', mode: 0o600 });
    assert.equal(read('s3cret\r\n').password, 's3cret');
    assert.equal(read('s3cret').password, 's3cret');
    assert.equal(read('  s3cret \t\n').password, '  s3cret \t', 'only the line break goes; spaces are the password\'s');
    assert.equal(read('\ufeffs3cret\n').password, '\ufeffs3cret', 'a byte-order mark is read as text, as Python reads UTF-8');
    assert.equal(read('s3cret\n', 0o400).mode, 0o400);
    assert.equal(read('s3cret\n', 0o700).mode, 0o700);
    // only ONE trailing line break is not part of it, and the file holds one line
    for (const content of ['s3cret\n\n', 's3cret\r\n\r\n', 'line one\nline two\n', 's3c\rret', 's3cret\r', '\n', '\r\n', '']) {
      assert.throws(() => read(content), /must hold one non-empty line/, JSON.stringify(content));
    }
    assert.throws(() => read(Buffer.from([0x73, 0xff, 0x0a])), /is not UTF-8 text/);
    assert.throws(() => read('x'.repeat(64 * 1024 + 1)), /is over 65536 bytes/);
    assert.equal(read('x'.repeat(64 * 1024)).password.length, 64 * 1024);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('loadPasswordFile refuses a file a group or other user may read or write, a directory and a missing file, quoting nothing', () => {
  const dir = privateDir();
  const secret = 'Unquotable-p4ss';
  try {
    for (const mode of [0o640, 0o604, 0o620, 0o602, 0o610, 0o601, 0o660, 0o644, 0o666]) {
      const file = writeFile(dir, `pw-${mode.toString(8)}`, `${secret}\n`, mode);
      assert.throws(() => vb.loadPasswordFile(file, 'u'), error => error instanceof vb.UsageError
        && error.message.includes(`has mode 0${mode.toString(8)}: a group or other user may read or write it`)
        && !error.message.includes(secret), mode.toString(8));
    }
    assert.throws(() => vb.loadPasswordFile(dir, 'u'), /is not a regular file/);
    assert.throws(() => vb.loadPasswordFile(path.join(dir, 'absent'), 'u'), /cannot open the password file .*absent: ENOENT/);
    for (const content of [`${secret}\n\n`, Buffer.concat([Buffer.from(secret), Buffer.from([0xff])])]) {
      const file = writeFile(dir, 'bad', content);
      assert.throws(() => vb.loadPasswordFile(file, 'u'), error => error instanceof vb.UsageError && !error.message.includes(secret));
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('the evidence records a password-file sign-in by its account and mode only; a credentials file\'s record is as before', () => {
  assert.deepEqual(vb.credentialsRecord({ username: 'demo-reviewer', password: 'p4ss', source: 'password_file', mode: 0o600 }),
    { username: 'demo-reviewer', source: 'password_file', file_mode: '0600' });
  assert.deepEqual(vb.credentialsRecord({ username: 'agent', password: 'p4ss', groupOrOtherReadable: true }),
    { username: 'agent', file_group_or_other_readable: true });
});

test('a DEBUG that would turn on a Playwright log carrying the password is recognised, however it is spelled', () => {
  for (const value of ['pw:api', 'pw:channel', 'pw:protocol', 'pw:server:channel', 'pw:*', '*', 'pw:p*', 'pw*', 'p*', '*:channel',
    'pw:channel*', 'express:*,pw:protocol', 'express:* pw:protocol', '*,-pw:api', '-pw:api,*', 'pw:ap.', 'pw:(api', 'pw:[']) {
    assert.equal(vb.debugMayLog(value), true, value);
  }
  for (const value of [undefined, '', 'pw:browser', 'pw:install,pw:download', 'express:*', '-pw:*', 'pw:browser*', 'pw:error']) {
    assert.equal(vb.debugMayLog(value), false, String(value));
  }
});

// main() with process.env.DEBUG set and stderr captured; every invocation here ends in a usage error before Playwright.
async function runMain(args, debug) {
  const saved = { write: process.stderr.write, debug: process.env.DEBUG };
  let err = '';
  process.stderr.write = chunk => { err += chunk; return true; };
  if (debug === undefined) delete process.env.DEBUG;
  else process.env.DEBUG = debug;
  try {
    return { code: await vb.main(args), err };
  } finally {
    process.stderr.write = saved.write;
    if (saved.debug === undefined) delete process.env.DEBUG;
    else process.env.DEBUG = saved.debug;
  }
}

test('main refuses any run under such a DEBUG before reading anything: every run types the operator\'s password', async () => {
  const dir = privateDir();
  try {
    const missing = [ '--base-url', 'https://x', '--operator-credentials', path.join(dir, 'ops.json'), '--docs', path.join(dir, 'docs'),
      '--manifest', path.join(dir, 'no-manifest.json'), '--out', path.join(dir, 'out')];
    const pwArgs = [...missing, '--password-file', path.join(dir, 'no-password-file'), '--username', 'demo-reviewer'];
    const refused = await runMain(pwArgs, 'pw:protocol');
    assert.equal(refused.code, 2);
    assert.match(refused.err, /^verify_browser: refusing to run with DEBUG=pw:protocol: a Playwright call, channel or protocol log would carry the password\n/);
    assert.match((await runMain([...pwArgs, '--acceptance-reviewer'], 'pw:channel')).err, /refusing to run with DEBUG=pw:channel/);
    // the DEBUG=pw:api refusal stays, for every run
    for (const args of [pwArgs, [...missing, '--credentials', path.join(dir, 'agent.json')]]) {
      assert.match((await runMain(args, 'pw:api')).err, /^verify_browser: refusing to run with DEBUG=pw:api: Playwright would log the password\n/);
    }
    // a credentials run is refused too: the operator's password is typed into the sign-in form in every run
    const agent = await runMain([...missing, '--credentials', path.join(dir, 'agent.json')], 'pw:protocol');
    assert.equal(agent.code, 2);
    assert.match(agent.err, /^verify_browser: refusing to run with DEBUG=pw:protocol: a Playwright call, channel or protocol log would carry the password\n/);
    // without DEBUG a credentials run reads its inputs first: the manifest
    assert.match((await runMain([...missing, '--credentials', path.join(dir, 'agent.json')], undefined)).err, /^verify_browser: cannot read manifest /);
    // without DEBUG the password-file run reads its inputs first: the manifest, then the password file
    assert.match((await runMain(pwArgs, undefined)).err, /^verify_browser: cannot read manifest /);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('the evidence of a password-file run is scrubbed of the password in every form, and not written where a form survives', () => {
  const password = 'p&ss "w<o>rd" ✓ / 100%';
  const forms = vb.secretForms(password);
  for (const form of [password, encodeURIComponent(password), 'p%26ss+%22w%3Co%3Erd%22+%E2%9C%93+%2F+100%25',
    'p&amp;ss &quot;w&lt;o&gt;rd&quot; ✓ / 100%', JSON.stringify(password).slice(1, -1)]) {
    assert.ok(forms.includes(form), form);
  }
  assert.deepEqual(vb.scrubSecret({ [password]: [`sign-in failed: ${password}`, 3, null], nested: { text: encodeURIComponent(password) } }, forms),
    { '[password withheld]': ['sign-in failed: [password withheld]', 3, null], nested: { text: '[password withheld]' } });
  const dir = privateDir();
  try {
    const evidence = { schema: 'cpt-studio-browser-evidence@1', run_id: 'verify-1', base_url: 'https://x',
      run_error: `sign-in failed: the page said ${password}`, documents: [{ console_errors: [{ text: JSON.stringify({ password }) }] }] };
    const file = path.join(dir, 'evidence.json');
    vb.writeEvidence(file, evidence, forms);
    const text = fs.readFileSync(file, 'utf8');
    assert.equal(forms.some(form => text.includes(form)), false, text);
    assert.equal(JSON.parse(text).run_error, 'sign-in failed: the page said [password withheld]');
    // a password the scrub cannot see through (it spans the JSON's own syntax): nothing that holds it is written
    const spanning = 'l": "h';
    vb.writeEvidence(file, evidence, vb.secretForms(spanning));
    assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')),
      { schema: evidence.schema, run_id: 'verify-1', run_error: 'the evidence would have held the password; it was not written' });
    // without a password file the evidence is written as before
    vb.writeEvidence(file, evidence);
    assert.equal(fs.readFileSync(file, 'utf8'), `${JSON.stringify(evidence, null, 2)}\n`);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('sessionProblems --acceptance-reviewer: the named human account in an active reviewer membership; never an agent', () => {
  const acc = { acceptanceReviewer: true, username: 'demo-reviewer' };
  assert.deepEqual(vb.sessionProblems(HUMAN_SESSION, acc), []);
  const agentSession = { ...HUMAN_SESSION, user: { ...HUMAN_SESSION.user, actor_kind: 'agent' } };
  assert.deepEqual(vb.sessionProblems(agentSession, acc),
    ['the account\'s actor kind is "agent": the acceptance test is made through the ordinary (human) reviewer account']);
  assert.match(vb.sessionProblems(HUMAN_SESSION, { ...acc, username: 'other-reviewer' })[0], /not the named account "other-reviewer"'s/);
  assert.match(vb.sessionProblems(HUMAN_SESSION, { acceptanceReviewer: true })[0], /no account was named/);
  assert.match(vb.sessionProblems({ ...HUMAN_SESSION, role: 'owner' }, acc)[0], /role in this workspace is "owner"/);
  assert.equal(vb.sessionProblems({ ...HUMAN_SESSION, role: 'viewer', can_review: false }, acc).length, 2);
  assert.deepEqual(vb.sessionProblems({ ...HUMAN_SESSION, can_review: false }, acc), ['the account cannot review in this workspace']);
  assert.equal(vb.sessionProblems({ ...HUMAN_SESSION, synthetic_only: false }, acc).length, 1);
  assert.match(vb.sessionProblems({ ...HUMAN_SESSION, provider_mode: 'live' }, acc)[0], /--allow-live-provider/);
  // agent mode, as today: the human account is refused, the agent account passes
  assert.deepEqual(vb.sessionProblems(HUMAN_SESSION, {}), ['the account is a human account; decisions must be recorded as agent review']);
  assert.deepEqual(vb.sessionProblems(agentSession, {}), []);
  // an agent signed in with a password file: the session must be the account it names
  assert.deepEqual(vb.sessionProblems(agentSession, { username: 'demo-reviewer' }), []);
  assert.equal(vb.sessionProblems(agentSession, { username: 'someone-else' }).length, 1);
});

test('planDecisions --acceptance-reviewer: approvals only, of the ready selected codes review_plan.approve_codes names', () => {
  const plan = { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] }, approve_codes: ['45331'], second_review: { ask: true, approve_codes: ['45380'] } };
  const acc = vb.planDecisions(encounter(), plan, ACC_NOTES, { acceptanceReviewer: true });
  assert.deepEqual(acc.decisions.map(d => [d.code, d.action, d.designated, d.note]), [['45331', 'approve', false, ACC_NOTE]]);
  assert.deepEqual([acc.designated_missing, acc.not_in_approve_codes, acc.plan_conflicts], [false, ['45380'], []]);
  // the same plan, walked as the agent, also rejects the designated code
  assert.deepEqual(vb.planDecisions(encounter(), plan, AGENT_NOTES).decisions.map(d => [d.code, d.action]), [['45331', 'approve'], ['45380', 'reject']]);
  // nothing named, nothing approved (the option is implied)
  const none = vb.planDecisions(encounter(), { reject: null }, ACC_NOTES, { acceptanceReviewer: true });
  assert.deepEqual([none.decisions, none.not_in_approve_codes], [[], ['45331', '45380']]);
  // never a code of a must_not_code family: a named one is a plan conflict, left undecided
  const conflict = vb.planDecisions(encounter(), { approve_codes: ['45331', '45380'] }, ACC_NOTES, { acceptanceReviewer: true, mustNotCode: MUST_NOT });
  assert.deepEqual([conflict.decisions.map(d => d.code), conflict.plan_conflicts], [['45331'], ['45380 (gi.colonoscopy)']]);
  // never a code a second review added, whatever second_review.approve_codes or approve_codes names
  const second = encounter();
  second.assessment.proposals[1].support = { origin: 'second_review', service: 'S1' };
  const held = vb.planDecisions(second, { approve_codes: ['45331', '45380'], second_review: { approve_codes: ['45380'] } }, ACC_NOTES, { acceptanceReviewer: true });
  assert.deepEqual([held.decisions.map(d => d.code), held.second_review_held], [['45331'], ['45380']]);
  assert.deepEqual(held.approve_codes_unmatched, ['45380 (second review: the acceptance reviewer decides no code a second review added)']);
  // only ready, selected, undecided codes the screen offers to approve
  const offered = encounter();
  offered.assessment.proposals[0].status = 'needs_clarification';
  decidedBy(offered, 'p-colo', 'approve', ACC_NOTE);
  const unmatched = vb.planDecisions(offered, { approve_codes: ['45331', '45380', '45330', '45378'] }, ACC_NOTES, { acceptanceReviewer: true });
  assert.deepEqual(unmatched.decisions, []);
  assert.deepEqual(unmatched.approve_codes_unmatched, ['45331 (needs_clarification)', '45380 (approved)', '45330 (alternative)', '45378 (excluded)']);
});

test('planProblems --acceptance-reviewer: review_notes.approve must carry the acceptance-test label, checked before any upload', () => {
  const doc = { id: 'acc-1', upload: { service_date: null }, review_plan: { reject: { family: 'gi.egd' }, approve_codes: ['43239'] } };
  const acc = { acceptanceReviewer: true };
  assert.deepEqual(vb.planProblems(doc, ACC_NOTES, acc), []);
  assert.deepEqual(vb.planProblems(doc, { approve: ACC_LABEL.toUpperCase() }, acc), [], 'the label is matched as agent mode matches its own, in any case');
  const wanted = `review_notes approve must say "${ACC_LABEL}" (acc-1 would write it on every approval)`;
  for (const notes of [AGENT_NOTES, {}, { approve: ['x'] }, { approve: 'Synthetic acceptance-test approval' },
    { approve: 'session-made synthetic acceptance-test approval' }, { approve: 'session-made synthetic acceptance-test approval; not a human review' }]) {
    assert.deepEqual(vb.planProblems(doc, notes, acc), [wanted], JSON.stringify(notes));
  }
  // no rejection, confirmation or second-review note is written, so none is needed or checked
  assert.deepEqual(vb.planProblems({ ...doc, review_plan: { ...doc.review_plan, second_review: { ask: true } } },
    { ...ACC_NOTES, reject: 'x', confirm: 'y', second_review_approve: 'z' }, acc), []);
  // the plan's own checks still apply
  assert.equal(vb.planProblems({ ...doc, review_plan: { approve_codes: '43239' } }, ACC_NOTES, acc).length, 1);
  // and agent mode refuses the acceptance note, which does not say agent-executed synthetic
  assert.match(vb.planProblems(doc, ACC_NOTES)[0], /must say "agent-executed synthetic"/);
});

test('the reload check: each approval is the human reviewer\'s with its note kept verbatim; the acknowledgement and card are recorded', () => {
  const made = [{ proposal_id: 'p-flex', code: '45331', family: 'gi.flex_sig', action: 'approve', note: ACC_NOTE, http_status: 201, decision_id: 'd-p-flex' }];
  const enc = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE);
  const cards = [{ id: 'card-p-flex', badge: 'Approved', insight: `Approved by Demo Reviewer ... Note: ${ACC_NOTE}`, unlocated: 0 }];
  const good = vb.checkAcceptanceDecisions(made, enc, MUST_NOT, ACCOUNT, cards);
  assert.deepEqual(good.checks.map(r => `${r.id}:${r.status}`), ['decisions.labelled:pass', 'decisions.never_approved_must_not_code:pass']);
  assert.deepEqual(good.labels, [{ code: '45331', action: 'approve', decision_id: 'd-p-flex', recorded: true, approval: true, human: true,
    reviewer: 'Demo Reviewer', reviewer_is_account: true, note_kept: true, note_labelled: true, acknowledgement: attestation('human'),
    acknowledgement_is_session_attestation: true, card_badge: 'Approved', card_insight: cards[0].insight }]);
  const judge = (shape, decisions = made, account = ACCOUNT) => failures(vb.checkAcceptanceDecisions(decisions, shape, MUST_NOT, account, cards).checks);
  const changed = change => { const shape = clone(enc); change(shape.decisions.history[0]); return shape; };
  // recorded as an agent's, as another reviewer's, with another note, or not at all
  assert.deepEqual(judge(changed(h => { h.reviewer_kind = 'agent'; })), ['decisions.labelled']);
  assert.deepEqual(judge(changed(h => { h.reviewer = 'Another Reviewer'; })), ['decisions.labelled']);
  assert.deepEqual(judge(enc, made, { ...ACCOUNT, label: null }), ['decisions.labelled']);
  assert.deepEqual(judge(changed(h => { h.note = ACC_NOTE.trim().replace(' - ', ' — '); })), ['decisions.labelled']);
  assert.deepEqual(judge(changed(h => { h.id = 'd-other'; })), ['decisions.labelled']);
  assert.match(vb.checkAcceptanceDecisions(made, changed(h => { h.reviewer_kind = 'agent'; }), MUST_NOT, ACCOUNT, cards).checks[0].reason,
    /45331 approve \(human\)/);
  // a note without the label, kept verbatim, is still not an acceptance-test approval's
  const plain = decidedBy(encounter(), 'p-flex', 'approve', 'approved');
  assert.deepEqual(judge(plain, [{ ...made[0], note: 'approved' }]), ['decisions.labelled']);
  // any decision but an approval fails; an approval of a must_not_code family fails
  const rejected = decidedBy(encounter(), 'p-flex', 'reject', ACC_NOTE);
  assert.deepEqual(judge(rejected, [{ ...made[0], action: 'reject' }]), ['decisions.labelled']);
  const colo = decidedBy(encounter(), 'p-colo', 'approve', ACC_NOTE);
  assert.deepEqual(judge(colo, [{ ...made[0], proposal_id: 'p-colo', code: '45380', family: 'gi.colonoscopy', decision_id: 'd-p-colo' }]),
    ['decisions.never_approved_must_not_code']);
  // what the app stored is recorded, not judged: another acknowledgement is kept as it is
  const other = changed(h => { h.acknowledgement = 'something else'; });
  const recorded = vb.checkAcceptanceDecisions(made, other, MUST_NOT, ACCOUNT, []);
  assert.deepEqual(failures(recorded.checks), []);
  assert.deepEqual([recorded.labels[0].acknowledgement, recorded.labels[0].acknowledgement_is_session_attestation, recorded.labels[0].card_badge],
    ['something else', false, null]);
  assert.deepEqual(vb.checkAcceptanceDecisions([], encounter(), MUST_NOT, ACCOUNT).checks.map(r => r.status), ['pass', 'pass']);
});

test('checkPersistence holds a human approval to the acceptance mode, and an agent\'s to agent mode', () => {
  const before = encounter();
  const after = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE);
  const made = [{ proposal_id: 'p-flex', code: '45331', action: 'approve', note: ACC_NOTE, http_status: 201 }];
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, after, 'human')), []);
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, after)), ['persist.decision.45331']);
  const agentAfter = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE, AGENT_ACCOUNT);
  assert.deepEqual(failures(vb.checkPersistence(made, before, agentAfter, agentAfter, 'human')), ['persist.decision.45331']);
  // the row on the customer page: Approved, never labelled as an agent's for the acceptance reviewer; an agent's must be
  const row = sub => ({ rows: [{ proposal: 'p-flex', status: 'approved', status_text: 'Approved', sub, modifiers: '' }] });
  assert.deepEqual(failures(vb.checkDecisionRows(made, null, row(''), { acceptance: true })), []);
  assert.deepEqual(failures(vb.checkDecisionRows(made, null, row('Agent-executed synthetic review — not clinical approval'), { acceptance: true })), ['dom.decision.45331']);
  assert.deepEqual(failures(vb.checkDecisionRows(made, null, row(''))), ['dom.decision.45331']);
  assert.deepEqual(failures(vb.checkDecisionRows(made, null, { rows: [] }, { acceptance: true })), ['dom.decision.45331']);
});









// The planner makes approvals only under --acceptance-reviewer (its tests above), so no fixture reaches the walk's own
// approvals-only refusal; it is held in place by position, as the attach refusal is (ops-2): before any decision is made.
test('verifyDocument refuses anything but an approval under --acceptance-reviewer before it decides anything', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'verify_browser.cjs'), 'utf8');
  const body = source.slice(source.indexOf('async function verifyDocument('));
  // each line must be there (indexOf answers -1 for a missing one, which would read as "before")
  const at = text => {
    const index = body.indexOf(text);
    assert.ok(index > 0, `not in verifyDocument: ${text}`);
    return index;
  };
  const refusal = at('if (other.length) throw new Error(`refusing to decide: the acceptance reviewer makes approvals only');
  assert.ok(at('const deciding = [...decisionPlan.decisions, ...confirmations];') < refusal);
  assert.ok(at("const other = deciding.filter(d => d.action !== 'approve');") < refusal);
  assert.ok(refusal < at('await decide('), 'a decision is made before the approvals-only refusal');
  assert.ok(at('for (const [index, decision] of deciding.entries()) {') > refusal);
});

test('planProblems --acceptance-reviewer: an approval note the screen or the server would change is refused before any upload', () => {
  const doc = { id: 'acc-1', upload: { service_date: null }, review_plan: { approve_codes: ['43239'] } };
  const problemsFor = note => vb.planProblems(doc, { approve: note }, { acceptanceReviewer: true });
  const ch = String.fromCharCode;
  assert.deepEqual(problemsFor(`${ACC_NOTE}\nA second line, kept as written.`), []);
  assert.deepEqual(problemsFor(`${ACC_NOTE} ${'x'.repeat(vb.REVIEW_NOTE_MAX - ACC_NOTE.length - 1)}`), [], 'exactly the field\'s length');
  assert.deepEqual(problemsFor(`${ACC_NOTE} ${String.fromCodePoint(0x1f600)} kept`), [], 'an astral character is not a lone surrogate');
  for (const [note, reason] of [
    [` ${ACC_NOTE}`, /begins or ends with whitespace/],
    [`${ACC_NOTE}\n`, /begins or ends with whitespace/],
    [`${ACC_NOTE}${ch(0xfeff)}`, /begins or ends with whitespace/],  // the page's trim takes it; Python's strip would not
    [`${ACC_NOTE}${ch(0x1c)}`, /begins or ends with whitespace/],  // Python's strip takes it; the page's trim would not
    [`${ch(0x85)}${ACC_NOTE}`, /begins or ends with whitespace/],
    [`${ACC_NOTE} ${'x'.repeat(vb.REVIEW_NOTE_MAX - ACC_NOTE.length)}`, /longer than the 600 characters the note field takes/],
    [`${ACC_NOTE}\r\nA second line.`, /carriage return/],
    [`${ACC_NOTE} ${ch(0)} x`, /NUL or a lone surrogate/],
    [`${ACC_NOTE} ${ch(0xd800)} x`, /NUL or a lone surrogate/],
  ]) {
    const problems = problemsFor(note);
    assert.equal(problems.length, 1, JSON.stringify(note.slice(-16)));
    assert.match(problems[0], /^review_notes approve could not be kept verbatim through the review screen: /);
    assert.match(problems[0], reason, JSON.stringify(note.slice(-16)));
  }
  // the note field's length is the template's
  const page = fs.readFileSync(path.join(ROOT, 'studio', 'templates', 'studio', 'index.html'), 'utf8');
  const field = /<textarea id="reviewNote"[^>]*\smaxlength="(\d+)"/.exec(page);
  assert.ok(field, 'the review note field has no maxlength');
  assert.equal(Number(field[1]), vb.REVIEW_NOTE_MAX);
  // agent mode does not check it (unchanged)
  assert.deepEqual(vb.planProblems(doc, { approve: ` ${AGENT_NOTES.approve}` }), []);
});

// --- the operator view's summary (HARNESS.md 7): which participants ran, with which models ------------------------------
//
// The walk reads these from the OPERATOR view (/ops/api/encounters/<id>, today's full encounter view, whose shape these
// fixtures are); the customer page shows none of it.

const API_FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'api');
const apiFixture = name => JSON.parse(fs.readFileSync(path.join(API_FIXTURES, name), 'utf8'));




test('summarize records which participants ran and what reference validation retrieved, never a participant\'s sentence', () => {
  const enc = apiFixture('encounter-harness-degraded.json');
  const summary = vb.summarize(enc);
  assert.deepEqual(summary.harness.participants.map(p => [p.name, p.state, p.model, p.returned_model, p.estimated_cost_usd]),
    [['corti', 'done', '', '', null], ['astra', 'refused', 'gpt-6-astra', 'gpt-6-astra', '0.8388'], ['fable', 'unknown', 'claude-fable-5-1', '', null]]);
  assert.deepEqual(summary.harness.reference_validation, { state: 'done', codes_checked: 1, passages: 1,
    sources: ['cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4', 'cms-ncci-policy-manual-2026-ch6'] });
  assert.equal(summary.harness.final, 'provider_unknown');
  const text = JSON.stringify(summary);
  for (const sentence of enc.harness.participants.map(p => p.detail).filter(Boolean)) assert.equal(text.includes(sentence), false, sentence);
  assert.equal(text.includes('Cold forceps biopsies of the gastric antrum were taken.'), false);
  assert.equal(vb.summarize(encounter()).harness, null);
});

// --- harness@2 in the operator view's summary (HARNESS.md 11.1, 12.5, 12.6); the walk never confirms anything -----------

// encounter-harness2-dormant.json: the final scenario as the dormant confirmation path serves it (HARNESS.md 12.10: this
// release offers no confirmation, so the final fixture serves its candidates unchecked and can_confirm false)
const H2 = ['encounter-harness2-peer.json', 'encounter-harness2-final.json', 'encounter-harness2-confirmed.json',
  'encounter-harness2-dormant.json'];




test('the walk never confirms a finding: it posts to no confirmation endpoint and clicks no Confirm action', () => {
  const source = fs.readFileSync(path.join(ROOT, 'ops', 'verify_browser.cjs'), 'utf8');
  assert.equal(/clarifications\//.test(source), false, 'the confirmation endpoint is never addressed');
  assert.equal(source.includes('confirm-finding'), false, 'the customer page offers no finding confirmation, and the walk reads none');
  assert.equal(/data-attest|data-confirm[="\]]/.test(source), false, 'no candidate is selected and no attestation ticked');
});

test('summarize records the phase, the peer reviews, the candidates and the confirmations, never a passage or sentence', () => {
  const enc = apiFixture(H2[2]);
  const summary = vb.summarize(enc);
  assert.equal(summary.harness.phase, 2);
  // moved by refutation round 5 (R5-ACCOUNT, the session's D12): Astra's 45381 quotes a sentence in no document, so its
  // peer review listed it and proposed no code there; codes_added held it
  assert.deepEqual(summary.harness.participants.map(p => [p.name, p.peer?.state, p.peer?.codes_added]),
    [['corti', undefined, undefined], ['astra', 'done', []], ['fable', 'done', ['45380']]]);
  assert.deepEqual(summary.harness.participants[1].references, { retrieved: 1, used: 2, cited_not_retrieved: 1 });
  // moved by refutation round 3 (falsegreen-11): the fixtures' rows are the engine's - 45380's status (no candidate
  // verifies on a biopsy the readers leave in doubt) and extent, and the date, stay open after 45385's extent is confirmed
  assert.deepEqual(summary.clarifications.map(c => [c.fact, c.candidates.map(x => [x.value, x.verified]), c.confirmation]),
    [['performed_status', [['performed', false], ['performed', false], ['performed', false]], null],
      ['extent', [['cecum', true], ['cecum', false]], null], ['service_date', [['2026-10-21', true]], null]]);
  assert.deepEqual(summary.confirmations.map(c => [c.fact, c.value, c.located_by, c.confirmed_by]), [['extent', 'cecum', ['astra', 'fable'], 'Synthetic Reviewer']]);
  const text = JSON.stringify(summary);
  for (const passage of ['Landmarks photographed: appendiceal orifice and ileocecal valve.', 'Date of service: 2026-10-21', 'I read this passage', 'The endoscopic base']) {
    assert.equal(text.includes(passage), false, passage);
  }
  // a payload served before harness@2 records as before
  const older = vb.summarize(apiFixture('encounter-harness-degraded.json'));
  assert.equal('phase' in older.harness || 'confirmations' in older || older.harness.participants.some(p => 'peer' in p), false);
});

// --- the customer surface (CORE-UX-DESIGN 5-8) ---------------------------------------------------------------------------
//
// Over the synthetic samples ops/verification/samples/make_samples.py writes to the contract (one two-lesion colonoscopy as
// the operator view, the customer API, the customer page and its reports serve it). Each check passes on the samples and
// fails on the defect it exists for.

const SAMPLES = path.join(__dirname, 'samples');
const sample = name => fs.readFileSync(path.join(SAMPLES, name), 'utf8');
const sampleJson = name => JSON.parse(sample(name));
const { fakeDocument } = require('./fake_dom.cjs');
const domOf = html => vb.readCustomerDom(fakeDocument(html));
const OP = () => sampleJson('operator-encounter.json');
const TRACE = () => sampleJson('operator-trace.json');
const CUST = () => sampleJson('customer-encounter.json');
const DETAILS = () => sampleJson('customer-encounter-details.json');
const SUB = 'Agent-executed synthetic review — not clinical approval';
const SAMPLE_AGENT = 'CPT Studio review agent (automated agent)';
const ids = results => results.map(r => `${r.id}:${r.status}`);
const failed = results => results.filter(r => r.status === 'fail').map(r => r.id);
const hitIds = hits => [...new Set(hits.map(h => h.id))].sort();

test('the denylist vectors hold in this reader (ops/verify_downloads.py and ops/scan_customer.py run the same vectors)', () => {
  const ctx = vb.scanContext();
  assert.ok(vb.DENYLIST.vectors.length >= 30);
  for (const vector of vb.DENYLIST.vectors) {
    assert.deepEqual(hitIds(vb.scanText(vector.text, ctx, vector.surface)), vector.hits, `${vector.surface}: ${vector.text}`);
  }
  // every pattern compiles the same in both languages' common subset: no flag is inline, no named group, no \p
  for (const p of vb.DENYLIST.patterns) assert.equal(/\(\?[a-z]|\(\?<\w|\\p\{/i.test(p.source), false, p.id);
});

test('shapeProblems: the customer samples hold to the contract; an extra key, a missing key, a wrong type and a wrong enum are each named', () => {
  assert.deepEqual(vb.shapeProblems(CUST(), vb.CONTRACT.encounter), []);
  assert.deepEqual(vb.shapeProblems(DETAILS(), vb.CONTRACT.encounter), []);
  assert.deepEqual(vb.shapeProblems(sampleJson('customer-session.json'), vb.CONTRACT.session), []);
  const cases = [
    [enc => { enc.codes[0].vendor = 'OpenAI'; }, '$.codes[0].vendor: not in the customer contract'],
    [enc => { delete enc.codes[1].why; }, '$.codes[1].why: missing (the contract lists it)'],
    [enc => { enc.codes[0].units = '1'; }, '$.codes[0].units: string where the contract has integer'],
    [enc => { enc.state = 'needs_clarification'; }, '$.state: "needs_clarification" is not one of'],
    [enc => { enc.progress.started_at = 'yesterday'; }, '$.progress.started_at: string where the contract has iso?'],
    [enc => { enc.codes[0].decision.modifiers = 'XS'; }, '$.codes[0].decision.modifiers: string where the contract has a list'],
    [enc => { enc.provider_runs = []; }, '$.provider_runs: not in the customer contract'],
    [enc => { enc.service_date.document_value = '11/03/2026'; }, '$.service_date.document_value: string where the contract has date?'],
  ];
  for (const [mutate, want] of cases) {
    const enc = CUST();
    mutate(enc);
    const problems = vb.shapeProblems(enc, vb.CONTRACT.encounter);
    assert.ok(problems.some(problem => problem.startsWith(want)), `${want}: ${problems.join(' | ')}`);
  }
  // null where the contract allows it, never where it does not
  const nulls = CUST();
  nulls.codes[0].modifier_review = null;
  nulls.codes[0].decision = null;
  nulls.progress.error = null;
  assert.deepEqual(vb.shapeProblems(nulls, vb.CONTRACT.encounter), []);
  nulls.codes[0].why = null;
  assert.ok(vb.shapeProblems(nulls, vb.CONTRACT.encounter).some(problem => problem.startsWith('$.codes[0].why: null where')));
  assert.deepEqual(failed(vb.checkCustomerContract({ ...sampleJson('customer-session.json'), provider_mode: 'live' }, 'session', 'session.contract')), ['session.contract']);
});

test('checkCustomerVocabulary: the contract\'s words for states, statuses, checks, steps and details controls', () => {
  assert.deepEqual(failed(vb.checkCustomerVocabulary(CUST())), []);
  assert.deepEqual(failed(vb.checkCustomerVocabulary(DETAILS())), []);
  for (const mutate of [
    enc => { enc.state_label = 'Ready'; },
    enc => { enc.codes[0].status_label = 'Ready for review'; },
    enc => { enc.checks.reverse(); },
    enc => { enc.checks[1].label = 'Astra and Fable'; },
    enc => { enc.progress.steps[0].label = 'Reading'; },
    enc => { enc.details_needed = [{ ...DETAILS().details_needed[1], control: 'date' }]; },
    enc => { enc.details_needed = [{ ...DETAILS().details_needed[1], choices: [{ value: 'cecum', label: 'Cecum' }] }]; },
    enc => { enc.details_needed = [{ ...DETAILS().details_needed[1], allow: [] }]; },
  ]) {
    const enc = CUST();
    mutate(enc);
    assert.deepEqual(failed(vb.checkCustomerVocabulary(enc)), ['customer.vocabulary'], mutate.toString());
  }
});

test('denyValuesFrom harvests the operator view\'s identifiers, never a plain word', () => {
  const values = vb.denyValuesFrom(OP(), TRACE());
  for (const want of ['c0ffee00-0001-4a5b-8c6d-7e8f9a0b1c2d', 'gpt-6-astra', 'claude-fable-5-1', 'gpt-6-astra-2026-10-01', 'evidence.exact',
    'cpt-studio:provider@1', 'gi.colonoscopy@3', 'engine-2026.11.03@1', 'req_astra0123456789', 'call_fable55555555', OP().revision.text_sha256,
    OP().provider_runs[0].request_sha256, OP().assessment.id, OP().revision.id]) {
    assert.ok(values.includes(want), want);
  }
  for (const word of ['OpenAI', 'Anthropic', 'Corti', 'reviewed', 'Colonoscopy', 'units']) assert.equal(values.includes(word), false, word);
  assert.deepEqual(vb.harvest({ a: [{ b: ['x1', 'y2'] }, { b: ['z3'] }] }, 'a[].b[]'), ['x1', 'y2', 'z3']);
  assert.deepEqual(vb.harvest({ frozen: [['name', 'hash-1'], ['other', 'hash-2']] }, 'frozen[].1'), ['hash-1', 'hash-2']);
  assert.deepEqual(vb.harvest({ a: 3 }, 'a'), []);
});

test('scanJson: the customer sample is clean against every operator identifier; a leak of each kind is a hit; a quotation of the document is not', () => {
  const op = OP();
  const ctx = vb.scanContext({ documentText: op.revision.text, denyValues: vb.denyValuesFrom(op, TRACE()) });
  assert.deepEqual(vb.scanJson(CUST(), ctx), []);
  assert.deepEqual(vb.scanJson(DETAILS(), ctx), []);
  assert.deepEqual(vb.scanJson(sampleJson('customer-session.json'), ctx), []);
  // the operator view itself, served to a customer, is a flood of hits
  const flood = hitIds(vb.scanJson(op, ctx));
  for (const id of ['forbidden_key', 'provider_name', 'model_id', 'long_hex', 'deny_value', 'rule_id']) assert.ok(flood.includes(id), id);
  const leaks = [
    [enc => { enc.codes[0].vendor = 'OpenAI'; }, ['forbidden_key', 'provider_name', 'vendor']],
    [enc => { enc.codes[0].summary = `Read by ${op.provider_runs[1].requested_model}.`; }, ['deny_value', 'model_id', 'provider_name']],
    [enc => { enc.limitations.push(`Request ${op.provider_runs[0].request_sha256}`); }, ['deny_value', 'long_hex']],
    [enc => { enc.activity[0].summary = 'Fable response recorded (HTTP 200)'; }, ['http_status', 'provider_name']],
    [enc => { enc.codes[0].why.qualifications.push('evidence.exact passed'); }, ['deny_value', 'rule_id']],
    [enc => { enc.unresolved.push(`run ${op.provider_runs[2].id}`); }, ['deny_value']],
    [enc => { enc.progress.message = 'Waiting for the peer reviews of the participants'; }, ['participant', 'peer_review']],
  ];
  for (const [mutate, want] of leaks) {
    const enc = CUST();
    mutate(enc);
    assert.deepEqual(hitIds(vb.scanJson(enc, ctx)), want, mutate.toString());
  }
  // a document that names a patient Claude: its quotation is the document's own text, never a hit; the same name in a
  // server sentence is one
  const text = `${op.revision.text}Referred by Dr Claude Fable (fictional).\n`;
  const named = vb.scanContext({ documentText: text });
  assert.deepEqual(vb.scanJson({ why: { quotes: [{ text: 'Referred by Dr Claude Fable (fictional).' }] } }, named), []);
  assert.deepEqual(hitIds(vb.scanJson({ summary: 'Dr Claude Fable reviewed the codes.' }, named)), ['provider_name']);
  // the site's own host is no rule id
  assert.deepEqual(vb.scanText('Questions: support@cpt.quillmd.com', vb.scanContext({ allowed: ['cpt.quillmd.com'] }), 'dom'), []);
});

test('scanFile and scanHeaders: a customer report quoting the document is clean; a provider line, a hash or X-Content-SHA256 is a hit', () => {
  const op = OP();
  const ctx = vb.scanContext({ documentText: op.revision.text, denyValues: vb.denyValuesFrom(op, TRACE()) });
  for (const [name, fmt] of [['customer-report-approved.txt', 'txt'], ['customer-report-draft.txt', 'txt'], ['customer-report-approved.csv', 'csv'], ['customer-report-draft.csv', 'csv']]) {
    assert.deepEqual(vb.scanFile(sample(name), ctx, name, fmt), [], name);
  }
  const report = sample('customer-report-approved.txt');
  assert.equal(report.split('\nLimitations').length, 2);
  const txt = report.replace('\nLimitations', `\nPROVIDER USAGE\n  corti · ${op.provider_runs[0].request_sha256}\n\nLimitations`);
  assert.deepEqual(hitIds(vb.scanFile(txt, ctx, 'approved.txt', 'txt')), ['deny_value', 'long_hex', 'provider_machinery', 'provider_name', 'provider_word']);
  const approvedCsv = sample('customer-report-approved.csv');
  assert.equal(approvedCsv.split('"approved","CPT Studio').length, 3);  // studio/reports.py's bytes: every cell quoted
  const csv = approvedCsv.replace('"approved","CPT Studio', '"approved (gpt-6-astra)","CPT Studio');
  assert.deepEqual(hitIds(vb.scanFile(csv, ctx, 'approved.csv', 'csv')), ['deny_value', 'model_id', 'provider_name']);
  assert.deepEqual(vb.csvRows('a,"b ""c"", d"\r\n1,2\n'), [['a', 'b "c", d'], ['1', '2']]);
  assert.deepEqual(vb.scanHeaders({ 'content-type': 'text/plain', 'content-security-policy': "script-src 'sha256-abc'", 'set-cookie': 'x=1' }, ctx, 'GET /'), []);
  assert.deepEqual(hitIds(vb.scanHeaders({ 'x-content-sha256': 'ab'.repeat(32) }, ctx, 'GET /api/reports/x/download')), ['long_hex', 'sha256']);
});

test('expectedCustomerStatus and expectedCodeRows: the status is the server\'s statement of the page, and the contract\'s order', () => {
  // refutation round 3 (B-02, B-03): the status and sub label are what the operator view states the page shows
  // (serializers.customer_codes), never re-derived from the overlay's facts - which read a reinstated code whose detail a
  // member answered unavailable as ready; whatever the facts say, the statement is the answer
  const reinstated = { bucket: 'excluded', status: 'excluded', decision: { action: 'reinstate' }, overlay_reason: 'detail_unavailable' };
  const cases = [
    [{ ...reinstated, customer: statement('excluded', 'A needed detail is not documented', ['revoke']) }, { status: 'excluded', sub: 'A needed detail is not documented' }],
    [{ ...reinstated, status: 'needs_clarification', overlay_reason: '', customer: statement('needs_detail', 'Reinstated in review', ['reject', 'revoke']) },
      { status: 'needs_detail', sub: 'Reinstated in review' }],
    [{ bucket: 'selected', status: 'ready', decision: { action: 'approve', reviewer_kind: 'agent' }, customer: statement('approved', SUB, ['revoke']) }, { status: 'approved', sub: SUB }],
    [{ bucket: 'selected', status: 'ready', decision: { action: 'approve', reviewer_kind: 'human' }, customer: statement('approved', '', ['revoke']) }, { status: 'approved', sub: '' }],
    [{ bucket: 'selected', status: 'ready', decision: null, customer: statement('ready', '', ['approve', 'reject']) }, { status: 'ready', sub: '' }],
  ];
  for (const [p, want] of cases) assert.deepEqual(vb.expectedCustomerStatus(p), want, JSON.stringify(p));
  // no statement, or none in the contract's shape: nothing to judge against (cannot verify)
  const ready = statement('ready', '', ['approve', 'reject']);
  for (const customer of [undefined, null, 'ready', {}, { ...ready, status: 'Ready for review' }, { ...ready, status: 'needs_clarification' },
    { ...ready, sub_label: null }, { ...ready, reviewer_actions: 'approve' }, { ...ready, reviewer_actions: [1] }]) {
    assert.equal(vb.expectedCustomerStatus({ bucket: 'selected', status: 'ready', decision: null, customer }), null, JSON.stringify(customer));
    assert.equal(vb.serverCustomer({ customer }), null, JSON.stringify(customer));
  }
  assert.equal(vb.expectedCustomerStatus(null), null);
  const op = { assessment: { proposals: [
    { id: 'x-excl', bucket: 'excluded', reinstatable: true, decision: null },
    { id: 'a-sel', bucket: 'selected', decision: null },
    { id: 'alt', bucket: 'alternative', decision: null },
    { id: 'b-rein', bucket: 'excluded', reinstatable: true, decision: { action: 'reinstate' } },
    { id: 'hist', bucket: 'excluded', reinstatable: false, decision: null },
    { id: 'conf', bucket: 'excluded', reinstatable: false, decision: { action: 'confirm' } },
    { id: 'c-sel', bucket: 'selected', decision: { action: 'approve' } },
  ] } };
  assert.deepEqual(vb.expectedCodeRows(op).map(p => p.id), ['a-sel', 'b-rein', 'c-sel', 'x-excl', 'conf']);
  // the walk round (finding 6): a code a member's answer excluded is listed where its selected code was (U11), exactly
  // when its support records an unavailable answer to a named fact (questions.answered_away)
  const answered = value => ({ fact: 'extent', value, answers: ['a1'] });
  const op2 = { assessment: { proposals: [
    { id: 'sel', bucket: 'selected', decision: null },
    { id: 'away', bucket: 'excluded', reinstatable: false, decision: null, support: { answered: answered('not_documented') } },
    { id: 'away2', bucket: 'excluded', reinstatable: false, decision: null, support: { answered: answered('cannot_confirm') } },
    { id: 'other', bucket: 'excluded', reinstatable: false, decision: null, support: { answered: answered('documented') } },
    { id: 'nofact', bucket: 'excluded', reinstatable: false, decision: null, support: { answered: { fact: '', value: 'not_documented' } } },
    { id: 'plain', bucket: 'excluded', reinstatable: false, decision: null, support: {} },
  ] } };
  assert.deepEqual(vb.expectedCodeRows(op2).map(p => p.id), ['sel', 'away', 'away2']);
  for (const support of [null, 'answered', { answered: null }, { answered: 'not_documented' }, { answered: { value: 'not_documented' } }]) {
    assert.equal(vb.answeredAway({ bucket: 'excluded', support }), false, JSON.stringify(support));
  }
});

test('checkCustomerVsOperator: the samples agree; each disagreement with the operator view is named', () => {
  assert.deepEqual(failed(vb.checkCustomerVsOperator(CUST(), OP())), []);
  const cases = [
    ['customer.document', enc => { enc.document.text += ' '; }],
    ['customer.document', enc => { enc.document.revision = 2; }],
    ['customer.codes.listed', enc => { enc.codes.reverse(); enc.codes.forEach((code, i) => { code.number = i + 1; }); }],
    ['customer.codes.listed', enc => { enc.codes[1].number = 3; }],
    ['customer.codes.status', enc => { enc.codes[0].status = 'ready'; enc.codes[0].status_label = 'Ready for review'; }],
    ['customer.codes.status', enc => { enc.codes[0].sub_label = ''; }],
    ['customer.codes.units_modifiers', enc => { enc.codes[0].units = 2; }],
    ['customer.codes.units_modifiers', enc => { enc.codes[1].modifiers = ['59', 'XS']; }],
    ['customer.codes.decision', enc => { enc.codes[1].decision.modifiers = ['59', 'XS']; }],
    ['customer.codes.decision', enc => { enc.codes[0].decision.by = 'Somebody else'; }],
    ['customer.codes.decision', enc => { enc.codes[0].decision.at = '2026-11-03T23:00:00+00:00'; }],
    ['customer.codes.actions', enc => { enc.codes[0].allowed_actions = ['approve', 'reject']; }],
    [['customer.why.exact', 'customer.why.supports'], enc => { enc.codes[0].why.quotes[0].start += 1; }],  // no passage held there either
    ['customer.why.exact', enc => { enc.codes[0].why.quotes[0].page = 2; }],
    ['customer.why.supports', enc => { const cecum = OP().routing.families[0].mentions[0].span; enc.codes[0].why.quotes = [{ text: cecum.text, start: cecum.start, end: cecum.end, page: 1, exact: true }]; }],
    ['customer.service_date', enc => { enc.service_date.value = '2026-11-02'; }],
    ['customer.service_date', enc => { enc.service_date.conflict = true; }],
    ['customer.readiness', enc => { enc.readiness.approved = false; }],
    ['customer.details.asked_once', enc => { enc.details_needed = [DETAILS().details_needed[1], DETAILS().details_needed[1]]; }],
    ['customer.details.affects', enc => { enc.details_needed = [{ ...DETAILS().details_needed[1], affects: ['99213'] }]; }],
  ];
  for (const [id, mutate] of cases) {
    const enc = CUST();
    mutate(enc);
    assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, OP())), [].concat(id), `${id}: ${mutate.toString()}`);
  }
  // an alternative listed as a code: listed wrongly (and judged as a code it is not)
  const alternative = CUST();
  alternative.codes.push({ ...alternative.codes[0], id: 'a1f0b2c3-0003-4d5e-8f60-718293a4b5c6', code: '45378', number: 3 });
  const listed = vb.checkCustomerVsOperator(alternative, OP()).find(r => r.id === 'customer.codes.listed');
  assert.equal(listed.status, 'fail');
  assert.match(listed.reason, /an alternative is listed as a code/);
  // a quotation of a passage CPT Studio found unrelated is never one
  const op = OP();
  op.assessment.proposals[0].support.unrelated = [0];
  op.assessment.proposals[0].support.supporting = [];
  op.assessment.proposals[0].support.source = [];
  const unrelated = vb.checkCustomerVsOperator(CUST(), op).find(r => r.id === 'customer.why.supports');
  assert.equal(unrelated.status, 'fail');
  assert.match(unrelated.reason, /a passage CPT Studio found unrelated/);
});

// the wiring report's item 1 (2026-11-04): the customer page quotes CPT Studio's own evidence for the matched act first
// (customer_api._quotes), so the walk holds it as support - only for an act the code's support names, stored performed or
// incomplete, and exact at its offsets
test('checkCustomerVsOperator: the evidence CPT Studio recorded for the matched act is support while that act is performed or incomplete', () => {
  const op = OP();
  const text = op.revision.text;
  const passage = 'Procedure: Colonoscopy with polyp removal.';
  const start = text.indexOf(passage);
  assert.ok(start > 0);
  const span = { text: passage, start, end: start + passage.length };
  op.assessment.services = { services: [{ id: 'S1', family: 'colonoscopy', acts: [{ id: 'act-1', kind: 'removal', status: 'performed', evidence: [span] }] }] };
  const cust = CUST();
  cust.codes[0].why.quotes.unshift({ ...span, page: 1, exact: true });
  const supports = o => vb.checkCustomerVsOperator(cust, o).find(r => r.id === 'customer.why.supports');
  assert.equal(supports(op).status, 'pass', supports(op).reason);
  for (const status of ['incomplete']) {
    const other = JSON.parse(JSON.stringify(op));
    other.assessment.services.services[0].acts[0].status = status;
    assert.equal(supports(other).status, 'pass', status);
  }
  for (const status of ['not_performed', 'planned', 'historical', undefined]) {
    const other = JSON.parse(JSON.stringify(op));
    other.assessment.services.services[0].acts[0].status = status;
    assert.equal(supports(other).status, 'fail', String(status));
  }
  assert.equal(supports(OP()).status, 'fail');  // no recorded reading: none CPT Studio holds as support
  const otherAct = JSON.parse(JSON.stringify(op));
  otherAct.assessment.services.services[0].acts[0].id = 'act-2';  // an act the code's support does not name
  assert.equal(supports(otherAct).status, 'fail');
  const inexact = JSON.parse(JSON.stringify(op));
  inexact.assessment.services.services[0].acts[0].evidence[0].text = 'Procedure: colonoscopy with polyp removal.';
  assert.equal(supports(inexact).status, 'fail');
  assert.deepEqual([...vb.actIndex(op).keys()], ['act-1']);
  assert.deepEqual([...vb.actIndex({ assessment: { services: { services: 'x' } } }).keys()], []);
});

// --- refutation round 2 (2026-11-04): the walk judges the real site (L3-3, L3-5, L3-6, L3-7, L3-9, L3-10) ---------------

const checkOf = (results, id) => results.find(r => r.id === id);

// The operator view the walk reads is ops-agent's: a grant and no membership, so its own allowed_actions are always [].
test('the operator sample is what ops-agent reads: no membership, no action of its own', () => {
  const op = OP();
  assert.deepEqual(op.permissions, { can_review: false, is_owner: false, can_confirm: false });
  assert.deepEqual(op.assessment.proposals.map(p => p.allowed_actions), [[], [], [], []]);
});

test('serverActions: what the server states a reviewing member may record, never the operator\'s own actions (L3-5, B-02, B-03)', () => {
  const op = OP();
  const [p80, p85, p78, p39] = op.assessment.proposals;
  assert.deepEqual([vb.serverActions(p80), vb.serverActions(p85)], [['revoke'], ['revoke']]);  // approved
  assert.deepEqual([p78.customer, p39.customer], [null, null]);  // an alternative; an exclusion nobody may decide: not on the page
  assert.deepEqual([vb.serverActions(p78), vb.serverActions(p39)], [null, null]);
  // refutation round 3: the statement is the answer, whatever the facts beside it would have suggested - a reinstated
  // code whose detail a member answered unavailable (status excluded, nothing withholding approve) accepts revoke only
  // (B-02), and one still waiting on its detail (status needs_clarification) accepts reject and revoke (B-03)
  const answered = { ...p39, reinstatable: true, decision: { action: 'reinstate' }, approve_withheld_by: null, overlay_reason: 'detail_unavailable',
    customer: statement('excluded', 'A needed detail is not documented', ['revoke']) };
  assert.deepEqual(vb.serverActions(answered), ['revoke']);
  const waiting = { ...answered, status: 'needs_clarification', approve_withheld_by: 'review.reinstatement', overlay_reason: '',
    customer: statement('needs_detail', 'Reinstated in review', ['reject', 'revoke']) };
  assert.deepEqual(vb.serverActions(waiting), ['reject', 'revoke']);
  assert.deepEqual(vb.serverActions(waiting, false), []);  // a member who may not review is allowed nothing
  // the operator's own allowed_actions are never read
  assert.deepEqual(vb.serverActions({ ...waiting, allowed_actions: ['approve', 'reject', 'revoke'] }), ['reject', 'revoke']);
  assert.deepEqual(vb.serverActions({ ...waiting, customer: null, allowed_actions: ['revoke'] }), null);
  // no statement: cannot verify (null), except for a member who may not review, who is allowed nothing anyway
  assert.equal(vb.serverActions({ ...p80, customer: undefined }), null);
  assert.deepEqual(vb.serverActions({ ...p80, customer: undefined }, false), []);
  assert.deepEqual(vb.serverActions(null), []);
  // a copy: changing what the walk was told never changes the statement
  const told = vb.serverActions(p80);
  told.push('approve');
  assert.deepEqual(p80.customer.reviewer_actions, ['revoke']);
});

test('checkCustomerVsOperator judges the offered actions by what the server accepts from the customer (L3-5)', () => {
  // the samples: ops-agent's view allows nothing of its own; the customer is offered revoke on each approval
  assert.equal(checkOf(vb.checkCustomerVsOperator(CUST(), OP()), 'customer.codes.actions').status, 'pass');
  const cases = [
    [enc => { enc.codes[0].allowed_actions = ['revoke', 'approve']; }, 'fail'],  // an approval offered approve again
    [enc => { enc.codes[1].allowed_actions = ['reject']; }, 'fail'],
    [enc => { enc.permissions.can_review = false; }, 'fail'],  // a member who may not review offered revoke
    [enc => { enc.permissions.can_review = false; enc.codes.forEach(code => { code.allowed_actions = []; }); }, 'pass'],
    [enc => { enc.codes.forEach(code => { code.allowed_actions = []; }); }, 'pass'],  // offering less is no wrong offer
  ];
  for (const [mutate, want] of cases) {
    const enc = CUST();
    mutate(enc);
    assert.equal(checkOf(vb.checkCustomerVsOperator(enc, OP()), 'customer.codes.actions').status, want, mutate.toString());
  }
  // before any decision: approve and reject are what the server accepts; reinstate never is on a selected code
  const op = OP();
  const enc = CUST();
  for (const p of op.assessment.proposals) {
    if (p.bucket === 'selected') Object.assign(p, { decision: null, decision_state: 'undecided', customer: statement('ready', '', ['approve', 'reject'], p.customer.number) });
  }
  op.decisions.history = [];
  op.readiness = { draft: true, reviewed: false, blockers: ['45380 has no decision'] };
  enc.codes.forEach(code => Object.assign(code, { status: 'ready', status_label: 'Ready for review', sub_label: '', modifiers: [], decision: null,
    allowed_actions: ['approve', 'reject'] }));
  enc.readiness = { draft: true, approved: false, blockers: ['45380 has no decision.'] };
  assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, op)), []);
  enc.codes[0].allowed_actions = ['approve', 'reject', 'reinstate'];
  assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, op)), ['customer.codes.actions']);
  assert.match(checkOf(vb.checkCustomerVsOperator(enc, op), 'customer.codes.actions').reason, /45380 offers reinstate \(the server accepts approve, reject from this member\)/);
});

// --- refutation round 3 (2026-11-04): the page is judged against the server's statement of it (B-02, B-03) -----------

// 45385 as a reinstated code (a reviewer brought back a documentation check's exclusion), in the operator view the walk
// reads and on the genuine customer page, with what the server states the page shows for it.
function reinstated45385(customerStatement, page, facts = {}) {
  const op = OP();
  const p = op.assessment.proposals[1];
  const reinstate = { ...p.decision, id: 'd-85-reinstate', action: 'reinstate', note: 'Synthetic reinstatement.', acknowledgement: '', modifiers: [] };
  Object.assign(p, { bucket: 'excluded', status: 'excluded', reinstatable: true, decision: reinstate, decision_state: 'reinstated',
    approve_withheld_by: null, overlay_reason: '', customer: customerStatement, ...facts });
  op.decisions.history[1] = clone(reinstate);
  const cust = CUST();
  Object.assign(cust.codes[1], { status: customerStatement.status, status_label: customerStatement.status_label, sub_label: customerStatement.sub_label,
    modifiers: [], allowed_actions: [...customerStatement.reviewer_actions],
    decision: { action: 'reinstate', by: reinstate.reviewer, by_kind: reinstate.reviewer_kind, at: reinstate.decided_at, note: reinstate.note, modifiers: [] },
    ...page });
  return { op, cust };
}

test('B-02: a reinstated code whose needed detail a member answered unavailable - Excluded, revoke only - passes genuine and fails forged', () => {
  // the server: Excluded, "A needed detail is not documented", revoke only; the facts beside it (bucket excluded, status
  // excluded, a reinstate decision, nothing withholding approve) are what a re-derivation read as ready with approve
  const answered = statement('excluded', 'A needed detail is not documented', ['revoke'], 2);
  const { op, cust } = reinstated45385(answered, { why: { quotes: [], qualifications: [] } }, { overlay_reason: 'detail_unavailable' });
  assert.deepEqual(failed(vb.checkCustomerVsOperator(cust, op)), []);
  // forged: shown ready and offering approve (the server refuses approve with 409)
  const forged = clone(cust);
  Object.assign(forged.codes[1], { status: 'ready', status_label: 'Ready for review', sub_label: 'Reinstated in review', allowed_actions: ['approve', 'reject', 'revoke'] });
  const results = vb.checkCustomerVsOperator(forged, op);
  assert.deepEqual(failed(results), ['customer.codes.status', 'customer.codes.actions']);
  assert.match(checkOf(results, 'customer.codes.status').reason, /45385 ready \(the server shows excluded\)/);
  assert.match(checkOf(results, 'customer.codes.actions').reason, /45385 offers approve, reject \(the server accepts revoke from this member\)/);
  // each half alone fails alone: approve offered on the right status; the right actions under another reason
  const offer = clone(cust);
  offer.codes[1].allowed_actions = ['approve', 'revoke'];
  assert.deepEqual(failed(vb.checkCustomerVsOperator(offer, op)), ['customer.codes.actions']);
  const relabelled = clone(cust);
  relabelled.codes[1].sub_label = 'Excluded by a documentation check';
  assert.deepEqual(failed(vb.checkCustomerVsOperator(relabelled, op)), ['customer.codes.status']);
});

test('B-03: a reinstated code still waiting on its detail - Needs a detail, reject and revoke - passes genuine and fails forged', () => {
  // the server: Needs a detail ("Reinstated in review"), reject and revoke; a re-derivation read revoke only, because the
  // overlay serves the code as needs_clarification while the server's rule reads the stored exclusion
  const waiting = statement('needs_detail', 'Reinstated in review', ['reject', 'revoke'], 2);
  const { op, cust } = reinstated45385(waiting, {}, { status: 'needs_clarification', approve_withheld_by: 'review.reinstatement' });
  assert.deepEqual(failed(vb.checkCustomerVsOperator(cust, op)), []);
  const forged = clone(cust);
  forged.codes[1].allowed_actions = ['approve', 'reject', 'revoke'];
  const results = vb.checkCustomerVsOperator(forged, op);
  assert.deepEqual(failed(results), ['customer.codes.actions']);
  assert.match(checkOf(results, 'customer.codes.actions').reason, /45385 offers approve \(the server accepts reject, revoke from this member\)/);
  const viewer = clone(cust);
  viewer.permissions.can_review = false;  // offered to a member who may not review: the server accepts nothing from them
  assert.deepEqual(failed(vb.checkCustomerVsOperator(viewer, op)), ['customer.codes.actions']);
  viewer.codes.forEach(code => { code.allowed_actions = []; });
  assert.deepEqual(failed(vb.checkCustomerVsOperator(viewer, op)), []);
});

test('an operator view that does not state the page cannot verify a status or an action, and never passes the page', () => {
  for (const strip of [p => { delete p.customer; }, p => { p.customer = null; }, p => { p.customer = { ...p.customer, status: 'approve' }; },
    p => { p.customer = { ...p.customer, reviewer_actions: undefined }; }]) {
    const op = OP();
    strip(op.assessment.proposals[0]);
    const results = vb.checkCustomerVsOperator(CUST(), op);
    assert.deepEqual(failed(results), ['customer.codes.status', 'customer.codes.actions'], strip.toString());
    for (const id of ['customer.codes.status', 'customer.codes.actions']) {
      assert.match(checkOf(results, id).reason, /^cannot verify: the operator view does not state .* for 45380$/, `${strip}: ${id}`);
    }
  }
  // a member who may not review is allowed nothing whatever the view states: offered nothing, that is verified
  const op = OP();
  delete op.assessment.proposals[0].customer;
  const viewer = CUST();
  viewer.permissions.can_review = false;
  viewer.codes.forEach(code => { code.allowed_actions = []; });
  assert.deepEqual(failed(vb.checkCustomerVsOperator(viewer, op)), ['customer.codes.status']);
});

test('checkCustomerVsOperator never reads a missing modifier as none: the comparison could not run (L3-3)', () => {
  const bare = OP();
  for (const p of bare.assessment.proposals) if (p.decision) delete p.decision.modifiers;
  const dropped = CUST();
  dropped.codes[1].modifiers = [];
  dropped.codes[1].decision.modifiers = [];
  for (const enc of [CUST(), dropped]) {  // neither the right page nor the wrong one passes against a view that does not say
    const results = vb.checkCustomerVsOperator(enc, bare);
    assert.deepEqual(failed(results), ['customer.codes.units_modifiers']);
    assert.match(checkOf(results, 'customer.codes.units_modifiers').reason, /cannot verify: the operator view's decision carries no "modifiers" list/);
  }
  assert.deepEqual(failed(vb.checkCustomerVsOperator(dropped, OP())), ['customer.codes.units_modifiers', 'customer.codes.decision']);
  assert.deepEqual(failed(vb.checkCustomerVsOperator(CUST(), OP())), []);
  assert.deepEqual([vb.decidedModifiers(null), vb.decidedModifiers({ action: 'approve' }), vb.decidedModifiers({ modifiers: ['XS'] })], [[], null, ['XS']]);
});

test('checkCustomerVsOperator accepts the one documented readiness difference: nothing approved, approved export withheld (L3-9)', () => {
  // every code rejected: the review is complete, and the approved export - approved codes only - has nothing to list
  const op = OP();
  for (const p of op.assessment.proposals) {
    if (!p.decision) continue;
    Object.assign(p.decision, { action: 'reject', modifiers: [] });
    p.customer = statement('excluded', 'Rejected in review', ['revoke'], p.customer.number);
  }
  op.readiness = { draft: true, reviewed: true, blockers: [] };
  const enc = CUST();
  enc.codes.forEach(code => Object.assign(code, { status: 'excluded', status_label: 'Excluded', sub_label: 'Rejected in review', modifiers: [],
    why: { ...code.why, quotes: [] } }));
  enc.codes.forEach(code => Object.assign(code.decision, { action: 'reject', modifiers: [] }));
  enc.readiness = { draft: true, approved: false, blockers: [vb.NONE_APPROVED_BLOCKER] };
  assert.equal(vb.NONE_APPROVED_BLOCKER, 'No code has been approved.');
  assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, op)), []);
  for (const [mutate, why] of [[r => { r.blockers = []; }, 'withheld without saying why'], [r => { r.approved = true; }, 'offered with nothing to list'],
    [r => { r.blockers = ['The review is not complete yet.']; }, 'withheld for another reason']]) {
    const other = JSON.parse(JSON.stringify(enc));
    mutate(other.readiness);
    assert.deepEqual(failed(vb.checkCustomerVsOperator(other, op)), ['customer.readiness'], why);
  }
  // with an approval to list, the approved export is the reviewed one: withheld is still wrong
  const withheld = CUST();
  withheld.readiness = { draft: true, approved: false, blockers: [vb.NONE_APPROVED_BLOCKER] };
  assert.deepEqual(failed(vb.checkCustomerVsOperator(withheld, OP())), ['customer.readiness']);
});

test('checkCustomerVsOperator accepts exactly the passages the server\'s one rule shows (L3-7, L3-10)', () => {
  const op = OP();
  const text = op.revision.text;
  const cecum = 'The colonoscope was advanced to the cecum.';
  const start = text.indexOf(cecum);
  const located = { start, end: start + cecum.length, text: cecum };
  const supports = (enc, o) => checkOf(vb.checkCustomerVsOperator(enc, o), 'customer.why.supports').status;
  // no support reading: no passage was shown to support the code, so none may be quoted
  const unread = OP();
  unread.assessment.proposals[0].support = {};
  assert.equal(supports(CUST(), unread), 'fail');
  const quoteless = CUST();
  quoteless.codes[0].why.quotes = [];
  assert.equal(supports(quoteless, unread), 'pass');
  // CPT Studio's located passages only where the reading records the act as shown ('pass' or 'warn': review.SHOWN_SUPPORT,
  // the rule review.evidence_spans quotes by), never a 'not_applicable' or 'fail' one's
  const located80 = CUST();
  located80.codes[0].why.quotes = [{ ...located, page: 1, exact: true }];
  for (const [reading, want] of [['warn', 'pass'], ['not_applicable', 'fail'], ['fail', 'fail'], ['pass', 'pass']]) {
    const o = OP();
    Object.assign(o.assessment.proposals[0].support, { status: reading, supporting: [], unrelated: [0], source: [located] });
    assert.equal(supports(located80, o), want, reading);
  }
  // an excluded code quotes nothing, whatever its reading holds
  const p = vb.allowedPassages(op.assessment.proposals[0], Array.from(text), new Map(), 'excluded');
  assert.deepEqual(p, { allowed: [], unrelated: [] });
  assert.deepEqual(vb.allowedPassages(op.assessment.proposals[0], Array.from(text)).allowed.map(span => span.start), [256]);
});

// customer_api.agent_approval (refutation round 2, L3-6): an approval is labelled agent review exactly when its approver
// is an agent - a person's approval of a code an agent reinstated is the person's, with no label
test('checkCustomerVsOperator holds the agent label to the server\'s statement: an agent\'s approval only, never a person\'s approval of an agent\'s reinstatement (L3-6)', () => {
  // customer_api.agent_approval: labelled agent review exactly when the approver is an agent; the operator view states
  // the label the page shows (serializers.customer_codes), and the walk judges the page by it
  const op = OP();
  Object.assign(op.assessment.proposals[1], { reinstated_by: { reviewer: SAMPLE_AGENT, reviewer_kind: 'agent', decided_at: '2026-11-03T22:04:00+00:00' },
    customer: statement('approved', '', ['revoke'], 2) });
  Object.assign(op.assessment.proposals[1].decision, { reviewer: 'Reviewer Four', reviewer_kind: 'human' });
  const enc = CUST();
  Object.assign(enc.codes[1].decision, { by: 'Reviewer Four', by_kind: 'human' });
  enc.codes[1].sub_label = '';
  assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, op)), []);
  enc.codes[1].sub_label = SUB;  // the person's approval labelled an agent's
  assert.deepEqual(failed(vb.checkCustomerVsOperator(enc, op)), ['customer.codes.status']);
  assert.match(checkOf(vb.checkCustomerVsOperator(enc, op), 'customer.codes.status').reason, /45385 sub label "Agent-executed synthetic review — not clinical approval" \(the server shows ""\)/);
  // the agent's approval unlabelled fails the same way
  const unlabelled = CUST();
  unlabelled.codes[0].sub_label = '';
  assert.match(checkOf(vb.checkCustomerVsOperator(unlabelled, OP()), 'customer.codes.status').reason, /45380 sub label "" \(the server shows "Agent-executed/);
});

test('planDecisions plans from the actions the server accepts from the walking member, not the operator\'s own (L3-5)', () => {
  const enc = encounter();
  for (const p of enc.assessment.proposals) p.allowed_actions = [];  // the operator view of an operator with no membership
  const plan = vb.planDecisions(enc, { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES);
  assert.deepEqual(plan.decisions.map(d => [d.code, d.action]), [['45331', 'approve'], ['45380', 'reject']]);
  assert.deepEqual(vb.planDecisions(enc, { reject: null }, NOTES, { canReview: false }).decisions, []);
  // refutation round 3 (B-02, B-03): only what the server states it accepts - none on an assessment that is not the
  // final one (review._allowed: the statement then allows nothing), none where the view states nothing
  const notFinal = encounter();
  for (const p of notFinal.assessment.proposals) if (p.customer) p.customer.reviewer_actions = [];
  assert.deepEqual(vb.planDecisions(notFinal, { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES).decisions, []);
  const unstated = encounter();
  for (const p of unstated.assessment.proposals) delete p.customer;
  assert.deepEqual(vb.planDecisions(unstated, { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES).decisions, []);
  // reject only (approve withheld): such a code is not one the screen offers to approve, so it is neither approved nor
  // taken as the designated rejection
  const withheld = encounter();
  for (const p of withheld.assessment.proposals) if (p.customer) p.customer.reviewer_actions = ['reject'];
  assert.deepEqual(vb.planDecisions(withheld, { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] } }, NOTES).decisions.map(d => [d.code, d.action]), []);
});

test('readCustomerDom reads the DOM contract\'s hooks, and checkResultList holds each row to the API', () => {
  const html = sample('customer-page.html');
  const dom = domOf(html);
  assert.equal(dom.list, true);
  assert.deepEqual(dom.rows.map(row => [row.code, row.status, row.status_text, row.number, row.units, row.modifiers]),
    [['45380', 'approved', 'Approved', '1.', '1 unit', ''], ['45385', 'approved', 'Approved', '2.', '1 unit', 'Modifier XS']]);
  assert.deepEqual(dom.rows[0].why.quotes.map(q => [q.start, q.end, q.page]), [['256', '329', '1']]);
  assert.deepEqual(dom.checks.map(c => [c.key, c.state]), [['document_review', 'done'], ['independent_checks', 'done'], ['coding_validation', 'done']]);
  assert.equal(dom.progress.phase, 'completed');
  assert.deepEqual(dom.export.options.map(o => `${o.kind}.${o.fmt}:${o.disabled}`), ['draft.txt:false', 'draft.csv:false', 'approved.txt:false', 'approved.csv:false']);
  const cust = CUST();
  assert.deepEqual(failed(vb.checkResultList(cust, dom)), []);
  assert.deepEqual(failed(vb.checkChecksPanel(cust, dom)), []);
  assert.deepEqual(failed(vb.checkDetailsPanel(cust, dom)), []);
  const broken = [
    ['dom.result_list', h => h.replace(/<li class="result-row"[\s\S]*?<\/li>/, '')],
    ['dom.row.45380', h => h.replace('<span class="status" data-status="approved">Approved</span>', '<span class="status" data-status="approved">Approved · agent</span>')],
    ['dom.row.45380', h => h.replace('data-start="256"', 'data-start="255"')],
    ['dom.row.45380', h => h.replace('</div></li>', `<button type="button" data-decision="approve" data-proposal="${cust.codes[0].id}">Approve</button></div></li>`)],
    ['dom.row.45385', h => h.replace('Modifier XS', '')],
    ['dom.row.45380', h => h.replace(`<span class="result-sub">${SUB}</span>`, '<span class="result-sub"></span>')],
    ['dom.row.45380', h => h.replace('<summary>Why this code?</summary>', '<summary>Details</summary>')],
    ['dom.row.45380', h => h.replace(/<details class="why-code">[\s\S]*?<\/details>/, '')],
  ];
  for (const [id, mutate] of broken) {
    const mutated = mutate(html);
    assert.notEqual(mutated, html, `${id}: the mutation did not apply`);
    assert.ok(failed(vb.checkResultList(cust, domOf(mutated))).includes(id), `${id}: ${mutate.toString()}`);
  }
  // the units element may stay empty for a single unit; a code of 2 units must say so
  const two = CUST();
  two.codes[0].units = 2;
  assert.deepEqual(failed(vb.checkResultList(two, dom)), ['dom.row.45380']);
  assert.deepEqual(failed(vb.checkResultList(cust, domOf(html.replace('<span class="result-units">1 unit</span>', '<span class="result-units"></span>')))), []);
  // the checks panel in another order or state
  assert.deepEqual(failed(vb.checkChecksPanel(cust, domOf(html.replace('data-check="coding_validation" data-state="done"', 'data-check="coding_validation" data-state="running"')))), ['dom.checks_panel']);
});

test('checkDetailsPanel: a date row with "Use document date" beside both dates, a confirmation with "Not documented" and "Cannot confirm", Save', () => {
  const html = sample('customer-page-details.html');
  const enc = DETAILS();
  const dom = domOf(html);
  assert.equal(dom.details.heading, 'A few details needed');
  assert.deepEqual(dom.details.rows.map(row => [row.id, row.fact, row.date_input, row.use_document, row.choices]),
    [['detail-service-date', 'service_date', true, true, []], ['detail-extent', 'extent', false, false, ['not_documented', 'cannot_confirm']]]);
  assert.deepEqual(failed(vb.checkDetailsPanel(enc, dom)), []);
  assert.deepEqual(failed(vb.checkResultList(enc, dom)), []);
  const broken = [
    h => h.replace('<button type="button" data-action="use-document-date">Use document date</button>', ''),
    h => h.replace('<button type="button" data-detail-choice="cannot_confirm">Cannot confirm</button>', ''),
    h => h.replace('<button type="button" data-action="save-details">Save details</button>', ''),
    h => h.replace('<h2>A few details needed</h2>', '<h2>Clarifications</h2>'),
    h => h.replace('<p class="detail-entered-date">You entered: 2026-11-02</p>', ''),
    h => h.replace('<p class="detail-affects">Affects 45385</p>', '<label><input type="radio" name="detail-detail-extent" value="cecum"> Cecum</label>'),
    h => h.replace(/<section class="details-panel">[\s\S]*?<\/section>/, ''),
  ];
  for (const mutate of broken) {
    const mutated = mutate(html);
    assert.notEqual(mutated, html, mutate.toString());
    assert.deepEqual(failed(vb.checkDetailsPanel(enc, domOf(mutated))), ['dom.details_panel'], mutate.toString());
  }
  // "Use document date" only where the API allows it
  const disallowed = DETAILS();
  disallowed.service_date.can_use_document_date = false;
  assert.deepEqual(failed(vb.checkDetailsPanel(disallowed, dom)), ['dom.details_panel']);
  // a panel where nothing is asked
  assert.deepEqual(failed(vb.checkDetailsPanel(CUST(), dom)), ['dom.details_panel']);
});

test('checkNoEmQuestions: no office E/M question when no separate E/M service is documented, in either view', () => {
  assert.deepEqual(failed(vb.checkNoEmQuestions(CUST(), OP())), []);
  assert.deepEqual(failed(vb.checkNoEmQuestions(DETAILS(), OP())), []);
  const op = OP();
  op.clarifications = [{ id: 'c1', scope: 'service', family: 'gi.office_em', fact: 'setting', state: 'open', question: 'Which setting?' }];
  assert.deepEqual(failed(vb.checkNoEmQuestions(CUST(), op)), ['details.no_em_question']);
  op.clarifications[0].state = 'answered';
  assert.deepEqual(failed(vb.checkNoEmQuestions(CUST(), op)), []);
  for (const row of [{ fact: 'patient_status', family_label: 'Office visit', prompt: 'New or established?' },
    { fact: 'setting', family_label: 'Encounter', prompt: 'Where did the office visit take place?' },
    { fact: 'em_basis', family_label: 'Visit', prompt: 'Which basis?' }]) {
    const enc = CUST();
    enc.details_needed = [{ ...DETAILS().details_needed[1], ...row }];
    assert.deepEqual(failed(vb.checkNoEmQuestions(enc, OP())), ['details.no_em_question'], row.fact);
  }
});

// A processing encounter and the panel the page draws for it.
function busyCustomer(phase = 'processing', step = 'checking') {
  const enc = CUST();
  const states = { failed: ['failed', 'Could not finish'], stopped: ['stopped', 'Stopped'] };
  [enc.state, enc.state_label] = states[phase] || ['processing', 'Processing'];
  const order = ['reading', 'identifying', 'checking', 'preparing'];
  enc.progress = { ...enc.progress, phase, busy: !['failed', 'stopped'].includes(phase), finished_at: null, can_stop: true, can_resume: false,
    message: 'Checking the suggested codes.', active_detail: 'Independent checks',
    steps: enc.progress.steps.map(s => ({ ...s, state: order.indexOf(s.key) < order.indexOf(step) ? 'done' : s.key === step ? (phase === 'failed' ? 'failed' : phase === 'stopped' ? 'stopped' : 'active') : 'not_started', finished_at: order.indexOf(s.key) < order.indexOf(step) ? s.finished_at : null })) };
  if (['failed', 'stopped'].includes(phase)) Object.assign(enc.progress, { can_stop: false, can_resume: true, message: phase === 'failed' ? 'The check could not finish.' : 'Processing was stopped.' });
  return enc;
}

function panelHtml(enc, { extra = '', card = enc.progress.busy, elapsed = '1 min 04 s' } = {}) {
  const p = enc.progress;
  const steps = p.steps.map(s => `<li class="progress-step" data-step="${s.key}" data-state="${s.state}">${s.label}</li>`).join('');
  return `<html><body><section class="progress-panel${card ? ' progress-card' : ''}" data-phase="${p.phase}" role="status"><ol>${steps}</ol>`
    + `<p>Elapsed <span data-elapsed>${elapsed}</span></p><p class="progress-message">${p.message}</p>`
    + `<p class="leave-note">You can leave this page.</p>${p.can_stop ? '<button data-action="stop">Stop</button>' : ''}`
    + `${p.can_resume ? '<button data-action="resume">Resume</button>' : ''}${extra}</section></body></html>`;
}

test('checkProgressDom: the served phase and steps, elapsed time, no percentage or ETA, the busy card, Stop, Resume, and stillness once failed or stopped', () => {
  const busy = busyCustomer();
  assert.deepEqual(failed(vb.checkProgressDom(busy, domOf(panelHtml(busy)))), []);
  assert.ok(ids(vb.checkProgressDom(busy, domOf(panelHtml(busy)))).includes('progress.dom.stop:pass'));
  const cases = [
    ['progress.dom.phase', panelHtml(busy).replace('data-phase="processing"', 'data-phase="queued"')],
    ['progress.dom.steps', panelHtml(busy).replace('data-step="checking" data-state="active"', 'data-step="checking" data-state="done"')],
    ['progress.dom.elapsed', panelHtml(busy, { elapsed: '' })],
    ['progress.dom.no_percentage_or_eta', panelHtml(busy, { extra: '<p>42% complete</p>' })],
    ['progress.dom.no_percentage_or_eta', panelHtml(busy, { extra: '<p>About 3 minutes remaining</p>' })],
    ['progress.dom.no_percentage_or_eta', panelHtml(busy, { extra: '<progress value="3" max="4"></progress>' })],
    ['progress.dom.card_while_busy', panelHtml(busy, { card: false })],
    ['progress.dom.stop', panelHtml(busy).replace('<button data-action="stop">Stop</button>', '')],
    ['progress.dom.message', panelHtml(busy).replace('Checking the suggested codes.', 'Astra is reading the document.')],
  ];
  for (const [id, html] of cases) assert.deepEqual(failed(vb.checkProgressDom(busy, domOf(html))), [id], id);
  for (const phase of ['failed', 'stopped']) {
    const settled = busyCustomer(phase);
    assert.deepEqual(failed(vb.checkProgressDom(settled, domOf(panelHtml(settled)), [])), [], phase);
    assert.deepEqual(failed(vb.checkProgressDom(settled, domOf(panelHtml(settled)), ['li.progress-step (pulse)'])), ['progress.dom.settled_still'], phase);
    assert.ok(failed(vb.checkProgressDom(settled, domOf(panelHtml(settled).replace(/data-state="(failed|stopped)"/, 'data-state="active"')), [])).includes('progress.dom.settled_still'), phase);
    assert.deepEqual(failed(vb.checkProgressDom(settled, domOf(panelHtml(settled).replace('<button data-action="resume">Resume</button>', '')), [])), ['progress.dom.resume'], phase);
  }
  // not processing: no panel is fine, a leftover progress card is not
  assert.deepEqual(failed(vb.checkProgressDom(CUST(), domOf('<html><body></body></html>'))), []);
  assert.deepEqual(failed(vb.checkProgressDom(busy, domOf('<html><body></body></html>'))), ['progress.dom.panel']);
  assert.ok(failed(vb.checkProgressDom(CUST(), domOf(panelHtml(CUST(), { card: true })))).includes('progress.dom.card_while_busy'));
});

// refutation round 3, C-R3-5 and the progress owner's request: a finished stage gives its step the outcome the operator
// view serves (step_outcome, by progress._step_outcome), folded as the page folds them - a stop or an outcome still being
// confirmed outranks a failure, and a failure outranks done; an operator view with no step_outcome falls back to the state
test('foldedSteps reads each finished stage by the outcome the operator view serves, with the page\'s precedence', () => {
  const at = (kind, state, step_outcome) => (step_outcome === 'absent' ? { kind, state, error: '', finished_at: null }
    : { kind, state, error: '', finished_at: null, step_outcome });
  const fold = stages => vb.foldedSteps({ pipeline: { stages } });
  const head = [at('extract', 'succeeded', 'done'), at('analyze', 'succeeded', 'done')];
  // a document review whose job succeeded but whose request failed (or was not sent): the step failed, never done
  assert.equal(fold([...head, at('predict', 'succeeded', 'failed')]).checking, 'failed');
  // one whose outcome is unknown, or a send an unknown outcome blocked: stopped, never done and never failed
  assert.equal(fold([...head, at('predict', 'succeeded', 'stopped')]).checking, 'stopped');
  // a stop outranks a failure in one step
  assert.equal(fold([...head, at('predict', 'succeeded', 'failed'), at('astra', 'succeeded', 'stopped')]).checking, 'stopped');
  // a stage that did nothing for its step (a skip, a held send) does not count
  assert.equal(fold([...head, at('predict', 'succeeded', null)]).checking, 'none');
  assert.equal(fold([...head, at('predict', 'succeeded', null), at('astra', 'succeeded', 'done')]).checking, 'done');
  // no step_outcome served: the job's own state, as before
  assert.equal(fold([...head, at('predict', 'succeeded', 'absent')]).checking, 'done');
  assert.equal(fold([...head, at('predict', 'running', 'done')]).checking, 'active');
  // the walk fails a page that calls a failed document review done
  const enc = CUST();
  const op = { pipeline: { stages: [...head, at('predict', 'succeeded', 'failed'), at('assess', 'succeeded', 'done')] } };
  enc.progress.steps[2].state = 'done';
  assert.deepEqual(failed(vb.checkProgressFold(enc, op)), ['progress.backend_stage']);
  enc.progress.steps[2].state = 'failed';
  assert.deepEqual(failed(vb.checkProgressFold(enc, op)), []);
});

test('foldedSteps and checkProgressFold: the served steps are the jobs\' own state, folded as P5 folds them', () => {
  const op = OP();
  assert.deepEqual(vb.foldedSteps(op), { reading: 'done', identifying: 'done', checking: 'done', preparing: 'done' });
  assert.deepEqual(failed(vb.checkProgressFold(CUST(), op)), []);
  const stages = kinds => kinds.map(([kind, state]) => ({ kind, state, error: '', finished_at: null }));
  const fold = kinds => vb.foldedSteps({ pipeline: { stages: stages(kinds) } });
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'running']]), { reading: 'done', identifying: 'active', checking: 'none', preparing: 'none' });
  // the first assess, with peer reviews after it, is still checking; the last one prepares the results
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'succeeded'], ['astra', 'succeeded'], ['fable', 'succeeded'],
    ['assess', 'succeeded'], ['astra_peer', 'running'], ['fable_peer', 'queued']]), { reading: 'done', identifying: 'done', checking: 'active', preparing: 'none' });
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'failed']]).checking, 'failed');
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'cancelled']]).checking, 'stopped');
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'unknown']]).checking, 'unknown');
  const confirming = CUST();
  confirming.progress.steps[2].state = 'waiting';
  confirming.progress.steps[3].state = 'not_started';
  assert.deepEqual(failed(vb.checkProgressFold(confirming, { pipeline: { stages: stages([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'unknown']]) } })), []);
  confirming.progress.steps[2].state = 'done';
  assert.deepEqual(failed(vb.checkProgressFold(confirming, { pipeline: { stages: stages([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'unknown']]) } })), ['progress.backend_stage']);
  // a resumed stage: the last job of the kind is what counts
  assert.deepEqual(fold([['extract', 'succeeded'], ['analyze', 'succeeded'], ['predict', 'cancelled'], ['predict', 'succeeded'], ['assess', 'succeeded']]),
    { reading: 'done', identifying: 'done', checking: 'done', preparing: 'done' });
  const served = CUST();
  served.progress.steps[3].state = 'active';
  assert.deepEqual(failed(vb.checkProgressFold(served, op)), ['progress.backend_stage']);
});

test('checkUploadAck: the acknowledgement is on screen when the page first asks for the new encounter, and only after the 201', () => {
  const id = 'e0000000-0000-4000-8000-000000000001';
  const watch = {
    requests: [{ method: 'POST', path: '/api/encounters', t: 10, status: 201, t_end: 120 }, { method: 'GET', path: `/api/encounters/${id}`, t: 140, status: 200, t_end: 180 }],
    gets: [{ path: `/api/encounters/${id}`, t: 140, ack_present: true, ack_visible: true, ack_text: 'Uploaded. Reading your document…' }],
    ack: { t: 125, text: 'Uploaded. Reading your document…' },
  };
  assert.deepEqual(ids(vb.checkUploadAck(watch, id)), ['upload.acknowledged:pass', 'upload.ack_after_created:pass', 'upload.ack_wording:pass']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, gets: [{ ...watch.gets[0], ack_present: false, ack_visible: false }] }, id)), ['upload.acknowledged']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, gets: [{ ...watch.gets[0], ack_visible: false }] }, id)), ['upload.acknowledged']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, gets: [] }, id)), ['upload.acknowledged']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, ack: { ...watch.ack, t: 60 } }, id)), ['upload.ack_after_created']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, ack: null }, id)), ['upload.ack_after_created']);
  assert.deepEqual(failed(vb.checkUploadAck({ ...watch, requests: watch.requests.slice(1) }, id)), ['upload.ack_after_created']);
  assert.deepEqual(vb.checkUploadAck({ ...watch, ack: { t: 125, text: 'Working…' } }, id).map(r => r.status), ['pass', 'pass', 'warn']);
});

function sent(id, extra = {}) {
  return { id, provider: 'astra', purpose: 'independent', state: 'succeeded', request_sha256: 'a'.repeat(64), response_sha256: 'b'.repeat(64),
    reused_from: null, reconciled: false, usage: { input_tokens: 1 }, created_at: `2026-11-03T22:00:0${id.slice(-1)}+00:00`, error: '', ...extra };
}

test('duplicateSends: a request sent again after an answer or an unreconciled unknown outcome is a duplicate paid request; a retry after a failure is not', () => {
  assert.deepEqual(failed(vb.checkNoDuplicateSends(OP())), []);
  const runs = list => ({ provider_runs: list });
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1'), sent('r2')]))), ['pipeline.no_duplicate_send']);
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1', { state: 'failed' }), sent('r2')]))), []);
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1', { state: 'unknown' }), sent('r2')]))), ['pipeline.no_duplicate_send']);
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1', { state: 'unknown', reconciled: true }), sent('r2')]))), []);
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1'), sent('r2', { reused_from: 'r1', state: 'succeeded' })]))), [], 'a reuse sends nothing');
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1'), sent('r2', { purpose: 'peer_review' })]))), [], 'another purpose is another request');
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1'), sent('r2', { request_sha256: 'c'.repeat(64) })]))), []);
  assert.deepEqual(failed(vb.checkNoDuplicateSends(runs([sent('r1'), sent('r2', { state: 'not_sent' })]))), [], 'a not-sent run is no request');
});

test('checkReloadIdentity: a reload while processing keeps the encounter, its jobs and its runs, sends nothing twice and brings the screen back', () => {
  const id = OP().id;
  const busy = busyCustomer();
  const op = OP();
  op.pipeline.stages = op.pipeline.stages.slice(0, 4).map((s, i) => (i === 3 ? { ...s, state: 'running', finished_at: null } : s));
  op.provider_runs = op.provider_runs.slice(0, 1);
  const before = { url: `https://x/#doc/${id}`, ids: [id, 'other'], op, cust: busy };
  const later = clone(op);
  later.pipeline.stages.push({ kind: 'fable', state: 'queued', error: '', finished_at: null });
  later.provider_runs.push(OP().provider_runs[1]);
  const after = { url: `https://x/#doc/${id}`, ids: [id, 'other'], op: later, cust: busy, dom: domOf(panelHtml(busy)) };
  assert.deepEqual(failed(vb.checkReloadIdentity(id, before, after)), []);
  const broken = [
    ['reload.same_encounter', a => { a.url = 'https://x/#documents'; }],
    ['reload.same_encounter', a => { a.ids = [...a.ids, 'new-encounter']; }],
    ['reload.jobs_kept', a => { a.op.pipeline.stages.splice(1, 1); }],
    ['reload.jobs_kept', a => { a.op.pipeline.stages[0].finished_at = '2026-11-03T23:59:00+00:00'; }],
    ['reload.runs_kept', a => { a.op.provider_runs.shift(); }],
    ['reload.runs_kept', a => { a.op.provider_runs[0].usage = {}; }],
    ['reload.no_duplicate_send', a => { a.op.provider_runs.push({ ...a.op.provider_runs[0], id: 'again', created_at: '2026-11-03T23:00:00+00:00' }); }],
    ['reload.progress_restored', a => { a.dom = domOf('<html><body></body></html>'); }],
    ['reload.progress_restored', a => { a.dom = domOf(panelHtml(busy).replace('data-phase="processing"', 'data-phase="completed"')); }],
  ];
  for (const [id2, mutate] of broken) {
    const a = { ...after, op: clone(after.op), ids: [...after.ids] };
    mutate(a);
    assert.deepEqual(failed(vb.checkReloadIdentity(id, before, a)), [id2], `${id2}: ${mutate.toString()}`);
  }
});

test('checkStopResume: Stop answers, the encounter reads stopped and still, nothing is sent while stopped, Resume continues the same jobs', () => {
  const id = OP().id;
  const op = OP();
  const stoppedCust = busyCustomer('stopped');
  const record = {
    stop_status: 201, before: { ids: [id], op }, stopped: { cust: stoppedCust, op, dom: domOf(panelHtml(stoppedCust)), animating: [] },
    quiet: { op: clone(op) }, resume_status: 201,
    resumed: { url: `https://x/#doc/${id}`, ids: [id], op: clone(op), cust: CUST(), dom: domOf(sample('customer-page.html')) },
  };
  assert.deepEqual(failed(vb.checkStopResume(id, record)), []);
  const broken = [
    ['stop.request', r => { r.stop_status = 409; }],
    ['stop.state', r => { r.stopped.cust = busyCustomer(); }],
    ['stop.settled_still', r => { r.stopped.animating = ['li.progress-step.is-running (pulse)']; }],
    ['stop.nothing_sent_while_stopped', r => { r.quiet.op.provider_runs.push({ ...sent('r9'), id: 'while-stopped' }); }],
    ['resume.request', r => { r.resume_status = null; r.resume_error = 'expected one Resume in the progress panel, found 0'; }],
    ['resume.no_duplicate_send', r => { r.resumed.op.provider_runs.push({ ...op.provider_runs[1], id: 'resent', created_at: '2026-11-03T23:00:00+00:00' }); }],
    ['resume.jobs_kept', r => { r.resumed.op.pipeline.stages.shift(); }],
    ['resume.finished', r => { r.resumed.cust = busyCustomer('stopped'); }],
  ];
  for (const [want, mutate] of broken) {
    const r = clone({ ...record, stopped: { ...record.stopped, dom: null }, resumed: { ...record.resumed, dom: null } });
    r.stopped.dom = record.stopped.dom;
    r.resumed.dom = record.resumed.dom;
    mutate(r);
    assert.ok(failed(vb.checkStopResume(id, r)).includes(want), `${want}: ${failed(vb.checkStopResume(id, r)).join(', ')}`);
  }
});

test('checkProvenance: the operator view keeps the participants, models, request hashes, usage, reuse and the trace', () => {
  assert.deepEqual(failed(vb.checkProvenance(OP(), TRACE(), { expectHarness: true })), []);
  assert.deepEqual(vb.checkProvenance({ provider_runs: [] }, undefined).map(r => `${r.id}:${r.status}`)[0], 'provenance.participants:skipped');
  assert.deepEqual(failed(vb.checkProvenance({ provider_runs: [] }, undefined, { expectHarness: true })), ['provenance.participants']);
  const cases = [
    ['provenance.participants', op => { op.harness.participants.pop(); }],
    ['provenance.models', op => { op.harness.participants[1].model = ''; }],
    ['provenance.peer_reviews', op => { delete op.harness.participants[2].peer; }],
    ['provenance.request_hashes', op => { op.provider_runs[0].request_sha256 = ''; }],
    ['provenance.request_hashes', op => { op.provider_runs[1].response_sha256 = null; }],
    ['provenance.reuse', op => { op.provider_runs[2].reused_from = op.provider_runs[1].id; }],  // a reuse that bills usage of its own
  ];
  for (const [id, mutate] of cases) {
    const op = OP();
    mutate(op);
    assert.ok(failed(vb.checkProvenance(op, TRACE(), { expectHarness: true })).includes(id), id);
  }
  const bare = TRACE();
  delete bare.participants[1].runs[0].endpoint;
  assert.deepEqual(failed(vb.checkProvenance(OP(), bare)), ['provenance.trace']);
  assert.deepEqual(failed(vb.checkProvenance(OP(), null)), ['provenance.trace']);
  const unmetered = OP();
  unmetered.provider_runs[0].usage = {};
  assert.deepEqual(vb.checkProvenance(unmetered, TRACE()).find(r => r.id === 'provenance.usage').status, 'warn');
});

test('checkAuthorization: every /ops/ URL is 404 to the customer, the old trace is gone for everyone, nobody signed in reads nothing, the operator reads all', () => {
  const id = OP().id;
  const probes = [
    ...vb.OPS_GET_PATHS(id).map(p => ({ who: 'customer', method: 'GET', path: p, status: 404 })),
    ...vb.OPS_POST_PATHS(id).map(p => ({ who: 'customer', method: 'POST', path: p, status: 404 })),
    ...vb.REMOVED_PATHS(id).map(p => ({ who: 'customer', method: 'GET', path: p, status: 404 })),
    { who: 'anonymous', method: 'GET', path: `/ops/api/encounters/${id}`, status: 404 },
    { who: 'anonymous', method: 'GET', path: '/ops/', status: 302, location: '/login/?next=/ops/' },
    ...vb.OPS_GET_PATHS(id).map(p => ({ who: 'operator', method: 'GET', path: p, status: 200 })),
    ...vb.REMOVED_PATHS(id).map(p => ({ who: 'operator', method: 'GET', path: p, status: 404 })),
  ];
  assert.deepEqual(failed(vb.checkAuthorization(probes)), []);
  const change = (index, fields) => probes.map((p, i) => (i === index ? { ...p, ...fields } : p));
  const at = (who, where) => probes.findIndex(p => p.who === who && p.path === where);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('customer', `/ops/api/encounters/${id}`), { status: 200 }))), ['authorization.customer_ops_404']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('customer', '/ops/'), { status: 403 }))), ['authorization.customer_ops_404'], 'never 403');
  assert.deepEqual(failed(vb.checkAuthorization(change(probes.findIndex(p => p.who === 'customer' && p.method === 'POST'), { status: 400 }))), ['authorization.customer_ops_404']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('customer', `/api/encounters/${id}/trace`), { status: 200 }))), ['authorization.trace_removed']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('operator', `/api/encounters/${id}/trace`), { status: 200 }))), ['authorization.trace_removed']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('anonymous', `/ops/api/encounters/${id}`), { status: 200 }))), ['authorization.anonymous']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('anonymous', '/ops/'), { location: 'https://elsewhere.example/' }))), ['authorization.anonymous']);
  assert.deepEqual(failed(vb.checkAuthorization(change(at('operator', `/ops/api/encounters/${id}/trace`), { status: 404 }))), ['authorization.operator_reads']);
  assert.deepEqual(failed(vb.checkAuthorization(probes.filter(p => p.who !== 'customer'))), ['authorization.customer_ops_404', 'authorization.trace_removed']);
  assert.deepEqual(vb.checkArtifactsHidden(probes).map(r => r.status), ['skipped']);
  const artifacts = [...probes, { who: 'customer', method: 'GET', path: '/api/reports/r1/download', status: 404, artifact: true }];
  assert.deepEqual(failed(vb.checkArtifactsHidden(artifacts)), []);
  assert.deepEqual(failed(vb.checkArtifactsHidden(artifacts.map(p => (p.artifact ? { ...p, status: 200 } : p)))), ['authorization.operator_artifacts_hidden']);
});

function metrics(width, extra = {}) {
  const item = { left: 16, right: width - 16, width: width - 32, height: 60, shown: true, hit: true, enabled: true };
  return { width, height: 844, scroll_width: width, rows: [{ proposal: 'p1', ...item }],
    actions: [{ action: 'approve', proposal: 'p1', ...item, width: 120, height: 48 }], controls: [], offenders: [], ...extra };
}

test('checkViewport: no horizontal scroll, rows on screen, actions and details controls operable, touch targets of 44 px', () => {
  assert.deepEqual(failed(vb.checkViewport('mobile', metrics(390))), []);
  const m = metrics(390);
  const cases = [
    ['viewport.mobile.no_horizontal_scroll', { scroll_width: 520, offenders: ['table.code-table (right 520)'] }],
    ['viewport.mobile.rows_visible', { rows: [{ ...m.rows[0], right: 520 }] }],
    ['viewport.mobile.actions_operable', { actions: [{ ...m.actions[0], hit: false }] }],
    ['viewport.mobile.actions_operable', { actions: [{ ...m.actions[0], enabled: false }] }],
    ['viewport.mobile.actions_operable', { actions: [{ ...m.actions[0], shown: false }] }],
    ['viewport.mobile.details_operable', { controls: [{ control: 'save-details', ...m.actions[0], hit: false }] }],
  ];
  for (const [id, extra] of cases) assert.deepEqual(failed(vb.checkViewport('mobile', metrics(390, extra))), [id], id);
  const small = vb.checkViewport('mobile', metrics(390, { actions: [{ ...m.actions[0], height: 32 }] }));
  assert.deepEqual(small.find(r => r.id === 'viewport.mobile.touch_targets').status, 'warn');
});

test('checkDecisionRows and checkCustomerDecisions: an agent approval is Approved and labelled as agent review, a rejection Excluded, the modifier shown', () => {
  const cust = CUST();
  const dom = domOf(sample('customer-page.html'));
  const made = [
    { proposal_id: cust.codes[0].id, code: '45380', action: 'approve', note: 'Agent-executed synthetic verification review', http_status: 201, modifier: null },
    { proposal_id: cust.codes[1].id, code: '45385', action: 'approve', note: 'Agent-executed synthetic verification review', http_status: 201, modifier: 'XS' },
  ];
  const account = { label: SAMPLE_AGENT };
  assert.deepEqual(failed(vb.checkDecisionRows(made, cust, dom)), []);
  assert.deepEqual(failed(vb.checkCustomerDecisions(made, cust, account)), []);
  // the acceptance reviewer's approval must never read as an agent's
  assert.deepEqual(failed(vb.checkDecisionRows(made, cust, dom, { acceptance: true })), ['dom.decision.45380', 'dom.decision.45385']);
  assert.deepEqual(failed(vb.checkCustomerDecisions(made, cust, account, 'human')), ['customer.decision.45380', 'customer.decision.45385']);
  const html = sample('customer-page.html');
  assert.deepEqual(failed(vb.checkDecisionRows(made, cust, domOf(html.replace('Modifier XS', '')))), ['dom.decision.45385']);
  assert.deepEqual(failed(vb.checkDecisionRows(made, cust, domOf(html.replace(`data-code="45380" data-status="approved"`, 'data-code="45380" data-status="ready"')))), ['dom.decision.45380']);
  const other = clone(cust);
  other.codes[1].decision.modifiers = [];
  other.codes[1].modifiers = [];
  assert.deepEqual(failed(vb.checkCustomerDecisions(made, other, account)), ['customer.decision.45385']);
  assert.deepEqual(failed(vb.checkCustomerDecisions(made, cust, { label: 'Someone else' })), ['customer.decision.45380', 'customer.decision.45385']);
  // a rejection reads Excluded, "Rejected in review"
  const rejected = clone(cust);
  Object.assign(rejected.codes[0], { status: 'excluded', status_label: 'Excluded', sub_label: 'Rejected in review', modifiers: [] });
  rejected.codes[0].decision = { ...rejected.codes[0].decision, action: 'reject', modifiers: [] };
  const rejectHtml = html.replace('data-code="45380" data-status="approved"><span class="result-number">1.</span> <span class="result-code">45380</span> <span class="result-units">1 unit</span> <span class="result-modifiers"></span> <span class="status" data-status="approved">Approved</span> <span class="result-sub">Agent-executed synthetic review — not clinical approval</span>',
    'data-code="45380" data-status="excluded"><span class="result-number">1.</span> <span class="result-code">45380</span> <span class="result-units">1 unit</span> <span class="result-modifiers"></span> <span class="status" data-status="excluded">Excluded</span> <span class="result-sub">Rejected in review</span>');
  assert.notEqual(rejectHtml, html);
  const rejection = [{ ...made[0], action: 'reject' }];
  assert.deepEqual(failed(vb.checkDecisionRows(rejection, rejected, domOf(rejectHtml))), []);
  assert.deepEqual(failed(vb.checkCustomerDecisions(rejection, rejected, account)), []);
});

test('checkModifierDialogs: the choice is shown exactly where the code has a modifier review, with "", 59 and XS, never prefilled, and the chosen one posted', () => {
  const cust = CUST();
  const ok = { proposal_id: cust.codes[1].id, code: '45385', action: 'approve', http_status: 201, modifier: 'XS', modifier_offered: true,
    modifier_options: ['', '59', 'XS'], modifier_prefilled: '', posted: { modifiers: ['XS'] } };
  assert.deepEqual(failed(vb.checkModifierDialogs([ok], cust)), []);
  assert.deepEqual(failed(vb.checkModifierDialogs([{ ...ok, modifier: null, posted: {} }], cust)), [], 'no modifier chosen, none posted');
  for (const change of [{ modifier_prefilled: 'XS' }, { modifier_options: ['59', 'XS', '59 and XS'] }, { posted: { modifiers: ['59', 'XS'] } },
    { modifier: null, posted: { modifiers: ['XS'] } }, { modifier_offered: false }]) {
    assert.deepEqual(failed(vb.checkModifierDialogs([{ ...ok, ...change }], cust)), ['decision.modifier.45385'], JSON.stringify(change));
  }
  const unreviewed = clone(cust);
  unreviewed.codes[1].modifier_review = null;
  assert.deepEqual(failed(vb.checkModifierDialogs([ok], unreviewed)), ['decision.modifier.45385'], 'offered where no modifier review is served');
  assert.equal(vb.modifierFor({ modifiers: { 45385: 'XS' } }, { code: '45385', action: 'approve' }), 'XS');
  assert.equal(vb.modifierFor({ modifiers: { 45385: 'XS' } }, { code: '45385', action: 'reject' }), null);
  assert.equal(vb.modifierFor({ modifiers: { 45385: ['59', 'XS'] } }, { code: '45385', action: 'approve' }), null);
});

function download(kind, fmt, extra = {}) {
  const hash = crypto.createHash('sha256').update(`${kind}.${fmt}`).digest('hex');
  return { kind, fmt, audience: 'customer', viewport: 'desktop', offered: true, error: null, http_status: 201, report_id: `r-${kind}-${fmt}`, size: 120,
    sha256: hash, refetch_sha256: hash, header_sha256: null, operator_sha256: hash, operator_audience: 'customer', operator_download_sha256: hash,
    operator_header_sha256: hash, path: `${kind}.${fmt}`, ...extra };
}

test('checkCustomerDownloads and checkCustomerListing: each owed download re-fetched and held by the operator byte for byte, one at mobile width', () => {
  const readiness = { draft: true, approved: true, blockers: [] };
  const all = [download('draft', 'txt', { viewport: 'mobile' }), download('draft', 'csv'), download('approved', 'txt'), download('approved', 'csv')];
  assert.deepEqual(vb.expectedCustomerDownloads(readiness), ['draft.txt', 'draft.csv', 'approved.txt', 'approved.csv']);
  assert.deepEqual(failed(vb.checkCustomerDownloads(all, readiness, null)), []);
  const swap = (index, fields) => all.map((d, i) => (i === index ? { ...d, ...fields } : d));
  for (const [fields, id] of [[{ header_sha256: 'f'.repeat(64) }, 'download.draft.csv'], [{ refetch_sha256: 'e'.repeat(64) }, 'download.draft.csv'],
    [{ operator_sha256: null }, 'download.draft.csv'], [{ operator_audience: 'operator' }, 'download.draft.csv'],
    [{ operator_download_sha256: 'd'.repeat(64) }, 'download.draft.csv'], [{ error: 'the export dialog does not offer this report' }, 'download.draft.csv']]) {
    assert.deepEqual(failed(vb.checkCustomerDownloads(swap(1, fields), readiness, null)), [id], JSON.stringify(fields));
  }
  assert.deepEqual(failed(vb.checkCustomerDownloads(all.map(d => ({ ...d, viewport: 'desktop' })), readiness, null)), ['download.mobile']);
  // the approved export withheld until the review is complete: offered disabled, every blocker listed
  const pending = { draft: true, approved: false, blockers: ['45380 has no decision.'] };
  const withheld = { options: [{ kind: 'approved', fmt: 'txt', disabled: true }, { kind: 'approved', fmt: 'csv', disabled: true }], text: 'Approved codes (TXT) 45380 has no decision.' };
  const drafts = all.slice(0, 2);
  assert.deepEqual(failed(vb.checkCustomerDownloads(drafts, pending, withheld)), []);
  assert.deepEqual(failed(vb.checkCustomerDownloads(drafts, pending, { ...withheld, options: [{ kind: 'approved', fmt: 'txt', disabled: false }] })), ['download.approved_withheld']);
  assert.deepEqual(failed(vb.checkCustomerDownloads(drafts, pending, { ...withheld, text: 'Approved codes (TXT)' })), ['download.approved_withheld']);
  assert.deepEqual(failed(vb.checkCustomerDownloads(drafts, pending, { options: [], text: '' })), ['download.approved_withheld']);
  const cust = { reports: all.map(d => ({ id: d.report_id, kind: d.kind, fmt: d.fmt, current: true })) };
  assert.deepEqual(failed(vb.checkCustomerListing(all, cust)), []);
  assert.deepEqual(failed(vb.checkCustomerListing(all, { reports: cust.reports.map((r, i) => (i === 2 ? { ...r, current: false } : r)) })), ['listing.approved.txt']);
  assert.deepEqual(failed(vb.checkCustomerListing(all, { reports: cust.reports.slice(1) })), ['listing.draft.txt']);
});

test('detailsPlan and planProblems: the details, modifiers and Stop the 2026-11-03 walk carries out, each refused when malformed', () => {
  const doc = (plan, extra = {}) => ({ id: 'd1', upload: { service_date: null }, review_plan: plan, ...extra });
  const notes = { approve: 'Agent-executed synthetic verification review' };
  assert.deepEqual(vb.detailsPlan(doc({ details: [{ fact: 'extent', value: 'not_documented', code: '45385' }] })), [{ fact: 'extent', value: 'not_documented', code: '45385' }]);
  assert.deepEqual(vb.detailsPlan(doc({ context_edit: { clear_member_date: true } }, { upload: { service_date: '2026-11-02' } })),
    [{ fact: 'service_date', value: 'use_document', context_edit: true }]);
  assert.deepEqual(vb.detailsPlan(doc({ context_edit: { service_date: '2026-11-03' } })), [{ fact: 'service_date', value: '2026-11-03', context_edit: true }]);
  assert.deepEqual(vb.planProblems(doc({ details: [{ fact: 'extent', value: 'not_documented', code: '45385' }], modifiers: { 45385: 'XS' }, stop_and_resume: true }), notes), []);
  assert.deepEqual(vb.planProblems(doc({}, { expected_no_em_questions: true }), notes), []);
  for (const [plan, extra, want] of [
    [{ detail: [] }, {}, /unknown key: detail/],
    [{ details: [] }, {}, /must be a non-empty list/],
    [{ details: [{ fact: 'extent' }] }, {}, /needs a non-empty fact and value/],
    [{ details: [{ fact: 'extent', value: 'x', why: 'y' }] }, {}, /must hold only fact, value and code/],
    [{ details: [{ fact: 'service_date', value: 'yesterday' }] }, {}, /YYYY-MM-DD date or "use_document"/],
    [{ details: [{ fact: 'extent', value: '2026-11-03' }] }, {}, /only the service date/],
    [{ details: [{ fact: 'service_date', value: 'use_document' }], context_edit: { service_date: '2026-11-03' } }, {}, /context_edit's, never answered twice/],
    [{ details: [{ fact: 'extent', value: 'not_documented' }, { fact: 'extent', value: 'cannot_confirm' }] }, {}, /answered twice/],
    [{ modifiers: { 45385: ['59', 'XS'] } }, {}, /one modifier, "59" or "XS"/],
    [{ modifiers: { 45385: 'XU' } }, {}, /one modifier/],
    [{ stop_and_resume: 'yes' }, {}, /stop_and_resume must be true or false/],
    [{}, { expected_no_em_questions: 'yes' }, /expected_no_em_questions must be true or false/],
  ]) {
    const problems = vb.planProblems(doc(plan, extra), notes);
    assert.equal(problems.length, 1, `${JSON.stringify(plan)}: ${problems.join(' | ')}`);
    assert.match(problems[0], want);
  }
});

test('checkDetailsSave: answers held as the member\'s context with attribution, never a revision, asked once, kept after a reload', () => {
  const op = OP();
  const before = { cust: DETAILS(), op };
  const answers = [{ fact: 'service_date', value: 'use_document' }, { fact: 'extent', value: 'not_documented', code: '45385' }];
  const saveOk = { requests: 1, http_status: 200, error: null, rows: { service_date: 'detail-service-date', extent45385: 'detail-extent' },
    posted: { answers: [{ id: 'detail-service-date', fact: 'service_date', value: 'use_document' }, { id: 'detail-extent', fact: 'extent', value: 'not_documented' }] } };
  const answered = () => {
    const cust = DETAILS();
    cust.service_date = { ...CUST().service_date };
    cust.details_needed = [{ ...cust.details_needed[1], saved: { value: 'not_documented', label: 'Not documented', by: SAMPLE_AGENT, at: '2026-11-03T22:06:00+00:00', answer_id: 'ans-1' } }];
    return cust;
  };
  const after = { cust: answered(), op };
  // the reloaded page as the page itself draws a saved row (app.js detailsPanel), never a hand-made one (walk 2, 2026-11-05)
  const reloaded = { cust: answered(), op, dom: domOf(`<html><body>${app.detailsPanel(answered(), pageUi(answered()))}</body></html>`) };
  const account = { label: SAMPLE_AGENT };
  assert.deepEqual(failed(vb.checkDetailsSave(answers, before, after, saveOk, reloaded, account)), []);
  const cases = [
    ['details.request', s => { s.save.requests = 2; }],
    ['details.request', s => { s.save.posted = { answers: [saveOk.posted.answers[0]] }; }],
    ['details.request', s => { s.save.http_status = 409; }],
    ['details.not_a_revision', s => { s.after.op = clone(op); s.after.op.revision.number = 2; s.after.op.revision.revisions_total = 2; }],
    ['details.member_context', s => { s.after.op = clone(op); s.after.op.context.user_values = { service_date: '2026-11-02' }; }],
    ['details.member_context', s => { s.after.cust.details_needed[0].saved.by = 'Someone else'; }],
    ['details.member_context', s => { s.after.cust.details_needed[0].saved.answer_id = ''; }],
    ['details.member_context', s => { s.after.cust.service_date = DETAILS().service_date; }],
    ['details.persist_after_reload', s => { s.reloaded.dom = domOf(sample('customer-page-details.html')); }],
    ['details.persist_after_reload', s => { s.reloaded.cust.details_needed[0].saved = null; }],
    ['details.asked_once', s => { s.reloaded.cust.details_needed.push({ ...DETAILS().details_needed[1], id: 'again' }); }],
  ];
  for (const [want, mutate] of cases) {
    const s = { save: clone(saveOk), after: { cust: answered(), op }, reloaded: { ...reloaded, cust: answered() } };
    mutate(s);
    const got = failed(vb.checkDetailsSave(answers, before, s.after, s.save, s.reloaded, account));
    assert.ok(got.includes(want), `${want}: ${got.join(', ')}`);
  }
  // a save of "not documented" answers alone sends nothing
  const only = [answers[1]];
  const onlySave = { ...saveOk, posted: { answers: [saveOk.posted.answers[1]] } };
  const sentOp = clone(op);
  sentOp.provider_runs.push({ ...op.provider_runs[0], id: 'after-answer', created_at: '2026-11-03T23:00:00+00:00' });
  assert.deepEqual(failed(vb.checkDetailsSave(only, before, { cust: answered(), op: sentOp }, onlySave, { ...reloaded, op: sentOp }, account)), ['details.member_answer_sends_nothing']);
});

test('sessionProblems on the customer session: no username and no provider mode served, so the live provider is accepted only by --allow-live-provider', () => {
  const session = sampleJson('customer-session.json');
  assert.match(vb.sessionProblems(session, {})[0], /serves no provider mode .* --allow-live-provider/);
  assert.deepEqual(vb.sessionProblems(session, { allowLiveProvider: true }), []);
  assert.deepEqual(vb.sessionProblems(session, { allowLiveProvider: true, username: 'review-agent' }), [], 'no username served: the fresh sign-in is the account');
  const human = { ...session, user: { ...session.user, actor_kind: 'human', label: 'Demo Reviewer' } };
  assert.deepEqual(vb.sessionProblems(human, { allowLiveProvider: true, acceptanceReviewer: true, username: 'demo-reviewer' }), []);
  assert.equal(vb.sessionProblems(human, { allowLiveProvider: true }).length, 1, 'agent mode needs an agent account');
});

test('mergeSamples keeps the first failure of any sample; checkBundle wants one script, none inline, nothing foreign and a clean bundle', () => {
  const merged = vb.mergeSamples([{ results: [{ id: 'progress.dom.phase', severity: 'hard', status: 'pass', reason: 'a' }] },
    { results: [{ id: 'progress.dom.phase', severity: 'hard', status: 'fail', reason: 'b' }] }, { results: [{ id: 'progress.dom.phase', severity: 'hard', status: 'pass', reason: 'c' }] }]);
  assert.deepEqual(merged.map(r => [r.id, r.status, r.reason]), [['progress.sampled.phase', 'fail', 'b (3 sample(s))']]);
  const bundle = { files: [{ path: '/', status: 200 }, { path: '/static/studio/app.js', status: 200 }], hits: [], scripts: 1, inline: 0 };
  assert.deepEqual(failed(vb.checkBundle(bundle)), []);
  assert.deepEqual(failed(vb.checkBundle({ ...bundle, scripts: 2 })), ['bundle.one_script']);
  assert.deepEqual(failed(vb.checkBundle({ ...bundle, inline: 1 })), ['bundle.one_script']);
  assert.deepEqual(failed(vb.checkBundle({ ...bundle, files: [...bundle.files, { path: 'https://cdn.example/x.js', foreign: true }] })), ['bundle.one_script']);
  assert.deepEqual(failed(vb.checkBundle({ ...bundle, files: [...bundle.files, { path: '/static/studio/ops.js', status: 404 }] })), ['bundle.read']);
  const hits = vb.scanText("const RUN_PROVIDERS = { corti: 'Corti' }; location.hash = '#trace/1';", vb.scanContext(), 'bundle', '/static/studio/app.js');
  assert.deepEqual(failed(vb.checkBundle({ ...bundle, hits })), ['scan.bundle']);
});

test('scanDocument: every body, header, page string, toast and file is scanned, and a scan over nothing fails rather than passes', () => {
  const op = OP();
  const sc = vb.scanContext({ documentText: op.revision.text, denyValues: vb.denyValuesFrom(op, TRACE()) });
  const record = { downloads: [] };
  const empty = { bodies: [], domStrings: new Map(), toasts: new Set() };
  assert.deepEqual(failed(vb.scanDocument(empty, sc, record, '/nowhere')).sort(), ['scan.dom', 'scan.header', 'scan.json']);
  const ctx = { bodies: [{ method: 'GET', path: '/api/encounters/x', status: 200, headers: { 'content-type': 'application/json' }, body: sample('customer-encounter.json') }],
    domStrings: new Map([['Ready for review', 'text span.status']]), toasts: new Set(['Saved.']) };
  assert.deepEqual(failed(vb.scanDocument(ctx, sc, record, '/nowhere')), []);
  ctx.toasts.add('Fable request failed (HTTP 529)');
  ctx.bodies.push({ method: 'POST', path: '/api/encounters/x/reports', status: 409, headers: { 'x-content-sha256': 'ab'.repeat(32) }, body: '{"error": "Astra is busy"}' });
  assert.deepEqual(failed(vb.scanDocument(ctx, sc, record, '/nowhere')).sort(), ['scan.dom', 'scan.header', 'scan.json']);
  assert.deepEqual(record.scans.hits.dom > 0 && record.scans.hits.json > 0 && record.scans.hits.header > 0, true);
});

test('sampleProgress compares the panel with what the PAGE was served, reads a mismatch twice, and fails when it saw no served read', async () => {
  const busy = busyCustomer();
  let html = panelHtml(busy);
  let reads = 0;
  const page = {
    evaluate: async fn => {
      if (fn === vb.readCustomerDom) { reads += 1; return vb.readCustomerDom(fakeDocument(html)); }
      if (fn.name === 'collectDomStrings' || fn.name === 'readAnimations') return [];
      return [];
    },
    waitForTimeout: async () => { html = panelHtml(busy); },
  };
  const ctx = { lastServed: new Map([['enc', { json: busy }]]), domStrings: new Map(), toasts: new Set() };
  assert.deepEqual(failed((await vb.sampleProgress(page, ctx, 'enc')).results), []);
  // the page drew an older phase on the first read and caught up 900 ms later: no failure, two reads
  reads = 0;
  html = panelHtml(busy).replace('data-phase="processing"', 'data-phase="queued"');
  assert.deepEqual(failed((await vb.sampleProgress(page, ctx, 'enc')).results), []);
  assert.equal(reads, 2);
  // the page never caught up: the mismatch stands
  page.waitForTimeout = async () => {};
  html = panelHtml(busy).replace('data-phase="processing"', 'data-phase="queued"');
  assert.deepEqual(failed((await vb.sampleProgress(page, ctx, 'enc')).results), ['progress.dom.phase']);
  // nothing the page was served was seen: no comparison is no pass
  assert.deepEqual(failed((await vb.sampleProgress(page, { ...ctx, lastServed: new Map() }, 'enc')).results), ['progress.dom.served']);
});

test('loadOperatorCredentials: a private JSON file with a top-level username and password, its content never quoted', () => {
  const dir = privateDir();
  try {
    const good = writeFile(dir, 'ops.json', JSON.stringify({ username: 'ops-agent', password: 'synthetic-operator-password' }));
    assert.deepEqual(vb.loadOperatorCredentials(good), { username: 'ops-agent', password: 'synthetic-operator-password', source: 'operator_credentials', mode: 0o600 });
    const open = writeFile(dir, 'open.json', JSON.stringify({ username: 'ops-agent', password: 'synthetic-operator-password' }), 0o644);
    assert.throws(() => vb.loadOperatorCredentials(open), /mode 0644: a group or other user may read/);
    const nested = writeFile(dir, 'nested.json', JSON.stringify({ service: 'cpt-studio', accounts: [{ username: 'ops-agent', password: 'x' }] }));
    assert.throws(() => vb.loadOperatorCredentials(nested), /must hold a non-empty top-level "username" and "password"/);
    const broken = writeFile(dir, 'broken.json', '{"username": "ops-agent", "password": "s3cret-not-json');
    assert.throws(() => vb.loadOperatorCredentials(broken), error => /is not a JSON object/.test(error.message) && !error.message.includes('s3cret'));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('main refuses an operator account that is the customer account, before Playwright', async () => {
  const dir = privateDir();
  try {
    const manifest = path.join(dir, 'manifest.json');
    fs.writeFileSync(manifest, JSON.stringify({ documents: [], review_notes: {} }));
    fs.mkdirSync(path.join(dir, 'docs'));
    fs.writeFileSync(path.join(dir, 'docs', 'generated.json'), JSON.stringify({ manifest_sha256: sha(fs.readFileSync(manifest, 'utf8')), documents: [] }));
    const creds = writeFile(dir, 'agent.json', JSON.stringify({ username: 'review-agent', password: 'synthetic-a' }));
    const same = writeFile(dir, 'same.json', JSON.stringify({ username: 'review-agent', password: 'synthetic-b' }));
    const args = ['--base-url', 'https://x', '--credentials', creds, '--operator-credentials', same, '--docs', path.join(dir, 'docs'), '--manifest', manifest, '--out', path.join(dir, 'out')];
    const refused = await runMain(args, undefined);
    assert.equal(refused.code, 2);
    assert.match(refused.err, /^verify_browser: the operator account must not be the customer account/);
    assert.equal(refused.err.includes('synthetic-a') || refused.err.includes('synthetic-b'), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// --- the walk itself, over a scripted site (no server, no browser) ---------------------------------------------------------
//
// fakeSite serves the customer API and the customer page (markup written to the DOM contract from the customer state, read
// by the walk's own readCustomerDom through fake_dom.cjs), the operator API beside it, and answers the decisions, details
// and report POSTs as the contract says the server does, keeping the operator view in step. Every act is recorded; a step
// the walk was not expected to take ends it with an error. leak: switches for each broken shape the walk must catch.

const BASE = 'https://cpt.example';

function pendingCustomer() {
  const enc = CUST();
  enc.state = 'ready';
  enc.state_label = 'Ready for review';
  enc.codes.forEach(code => Object.assign(code, { status: 'ready', status_label: 'Ready for review', sub_label: '', modifiers: [], decision: null,
    allowed_actions: ['approve', 'reject'] }));
  enc.readiness = { draft: true, approved: false, blockers: ['45380 has no decision.', '45385 has no decision.'] };
  enc.reports = [];
  enc.activity = [];
  return enc;
}

// The operator view as ops-agent reads it: a grant and no membership, so the view allows it no action of its own
// (studio.operator.ReadOnlyAccess) - the walk must take the actions the server accepts from the customer from the facts
function pendingOperator() {
  const op = OP();
  op.state = 'ready_for_review';
  op.state_label = 'Ready for review';
  assert.equal(op.permissions.can_review, false);
  for (const p of op.assessment.proposals) {
    if (p.bucket !== 'selected') continue;
    Object.assign(p, { decision: null, decision_state: 'undecided', allowed_actions: [],
      customer: statement('ready', '', ['approve', 'reject'], p.customer.number) });  // what the page shows a reviewer
  }
  op.decisions.history = [];
  op.readiness = { draft: true, reviewed: false, blockers: ['45380 has no decision.'] };
  op.reports = [];
  return op;
}

function rowHtml(code) {
  const quotes = code.why.quotes.map(q => `<blockquote class="why-quote" data-start="${q.start}" data-end="${q.end}" data-page="${q.page}">“${q.text}”</blockquote>`).join('');
  const quals = code.why.qualifications.map(q => `<p class="why-qualification">${q}</p>`).join('');
  const buttons = code.allowed_actions.map(a => `<button type="button" data-decision="${a}" data-proposal="${code.id}">${a}</button>`).join('');
  return `<li class="result-row" id="card-${code.id}" data-proposal="${code.id}" data-code="${code.code}" data-status="${code.status}">`
    + `<span class="result-number">${code.number}.</span><span class="result-code">${code.code}</span><span class="result-units">${code.units} unit</span>`
    + `<span class="result-modifiers">${code.modifiers.length ? `Modifier ${code.modifiers.join(', ')}` : ''}</span>`
    + `<span class="status" data-status="${code.status}">${code.status_label}</span><span class="result-sub">${code.sub_label}</span>`
    + `<p class="result-summary">${code.summary}</p><details class="why-code"${code.whyOpen ? ' open' : ''}><summary>Why this code?</summary>${quotes}${quals}</details>${buttons}</li>`;
}

function fakeSite({ leak = {} } = {}) {
  const state = { customer: pendingCustomer(), operator: pendingOperator(), trace: TRACE(), url: 'about:blank', dialog: null, exportOpen: false,
    whyOpen: false, viewport: 'desktop', acts: [], posts: [], gets: [], files: new Map(), listing: [], legacy: leak.legacyArtifact ? [{ id: 'legacy-1', audience: 'operator', kind: 'reviewed', fmt: 'txt', sha256: 'f'.repeat(64) }] : [] };
  const id = state.customer.id;
  const waiters = [];
  const downloads = [];
  const requestListeners = new Set();
  const json = (status, body, headers = {}) => ({ ok: () => status >= 200 && status < 300, status: () => status, json: async () => clone(body),
    text: async () => JSON.stringify(body), body: async () => Buffer.from(JSON.stringify(body)), headers: () => ({ 'content-type': 'application/json', ...headers }) });
  const bytes = (status, data, headers = {}) => ({ ok: () => status === 200, status: () => status, body: async () => Buffer.from(data), text: async () => String(data),
    json: async () => JSON.parse(String(data)), headers: () => headers });
  const html = () => {
    const c = state.customer;
    const rows = c.codes.map(code => rowHtml({ ...code, whyOpen: state.whyOpen && code === c.codes[0] })).join('');
    const options = ['draft', 'approved'].flatMap(kind => ['txt', 'csv'].map(fmt => `<button type="button" class="export-option" data-export-kind="${kind}" data-export-fmt="${fmt}"${c.readiness[kind] ? '' : ' disabled'}>${kind} ${fmt}</button>`)).join('');
    const dialog = state.dialog;
    const code = dialog ? c.codes.find(item => item.id === dialog.proposal) : null;
    const select = code && code.modifier_review ? `<select id="reviewModifier"><option value=""${dialog.modifier ? '' : ' selected'}></option>${['59', 'XS'].map(v => `<option value="${v}"${dialog.modifier === v ? ' selected' : ''}>${v}</option>`).join('')}</select>` : '';
    return `<html><head><title>CPT Studio</title></head><body><main><h1>${c.title}</h1>${leak.toast ? `<div id="toast" role="status">${leak.toast}</div>` : ''}`
      + app.progressPanel(c, pageUi(c))
      + `<ul class="checks-panel">${c.checks.map(k => `<li class="check-step" data-check="${k.key}" data-state="${k.state}">${k.label}</li>`).join('')}</ul>`
      + `<ol class="result-list">${rows}</ol><button type="button" data-action="export"${leak.exportAria ? ` aria-label="${leak.exportAria}"` : ''}>Download</button></main>`
      + `${dialog ? `<dialog id="reviewDialog" open><input type="checkbox" id="reviewAcknowledgement">${select}<textarea id="reviewNote"></textarea><button id="saveReview">Save</button></dialog>` : ''}`
      + `<dialog id="exportDialog"${state.exportOpen ? ' open' : ''}><div id="exportOptions">${options}</div><ul>${c.readiness.blockers.map(b => `<li>${b}</li>`).join('')}</ul></dialog></body></html>`;
  };
  const doc = () => fakeDocument(html());
  const resolve = response => {
    const index = waiters.findIndex(w => w.predicate(response));
    if (index >= 0) waiters.splice(index, 1)[0].resolve(response);
  };
  const posted = (where, body, status, answer) => {
    const request = { method: () => 'POST', url: () => `${BASE}${where}`, postDataJSON: () => clone(body) };
    const response = { ...json(status, answer), url: () => `${BASE}${where}`, request: () => request };
    request.response = async () => response;
    for (const listen of requestListeners) listen(request);
    state.posts.push({ path: where, body: clone(body) });
    resolve(response);
    return response;
  };
  const readiness = () => {
    const c = state.customer;
    const undecided = c.codes.filter(code => !code.decision);
    c.readiness = { draft: true, approved: undecided.length === 0, blockers: undecided.map(code => `${code.code} has no decision.`) };
    state.operator.readiness = { draft: true, reviewed: undecided.length === 0, blockers: c.readiness.blockers };
    if (!undecided.length) { c.state = 'reviewed'; c.state_label = 'Reviewed'; state.operator.state = 'reviewed'; }
  };
  const decideOn = body => {
    const c = state.customer;
    const code = c.codes.find(item => item.id === body.proposal_id);
    const p = state.operator.assessment.proposals.find(item => item.id === body.proposal_id);
    const at = '2026-11-03T22:05:00+00:00';
    const modifiers = leak.dropModifier ? [] : (body.modifiers || []);
    const by = leak.wrongReviewer ? 'Somebody else' : SAMPLE_AGENT;
    p.decision = { id: `d-${p.id}`, proposal_id: p.id, code: p.code, action: body.action, note: body.note, reviewer: by, reviewer_kind: 'agent',
      created_at: at, decided_at: at, carried_at: null, acknowledgement: body.acknowledgement, carried_from: null, invalidated: null, revision_number: 1, modifiers };
    p.decision_state = body.action === 'approve' ? 'approved' : 'rejected';
    p.allowed_actions = [];  // ops-agent's own: none
    p.customer = body.action === 'approve' ? statement('approved', SUB, ['revoke'], p.customer.number)
      : statement('excluded', 'Rejected in review', ['revoke'], p.customer.number);
    state.operator.decisions.history.push(clone(p.decision));
    Object.assign(code, body.action === 'approve'
      ? { status: 'approved', status_label: 'Approved', sub_label: SUB } : { status: 'excluded', status_label: 'Excluded', sub_label: 'Rejected in review' });
    Object.assign(code, { modifiers, allowed_actions: ['revoke'], decision: { action: body.action, by, by_kind: 'agent', at, note: body.note, modifiers } });
    readiness();
    return { id: p.decision.id, reviewer_kind: 'agent' };
  };
  const reportOn = body => {
    const n = state.listing.length + 1;
    const rid = `b0b0b0b0-00${String(n).padStart(2, '0')}-4c4c-8d8d-9e9e9e9e9e${String(n).padStart(2, '0')}`;
    const text = sample(`customer-report-${body.kind}.${body.fmt}`);
    const data = leak.reportLine ? text.replace('\nLimitations', `\n${leak.reportLine}\n\nLimitations`) : text;
    if (leak.reportLine && body.fmt === 'txt') assert.notEqual(data, text, 'the report leak did not apply');
    state.files.set(rid, data);
    const hash = crypto.createHash('sha256').update(data).digest('hex');
    state.listing.push({ id: rid, audience: leak.operatorAudience || 'customer', kind: body.kind === 'approved' ? 'reviewed' : 'draft', fmt: body.fmt, sha256: hash });
    const row = { id: rid, kind: body.kind, fmt: body.fmt, filename: `CPT-Studio-${body.kind}.${body.fmt}`, generated_at: '2026-11-03T22:10:00+00:00',
      generated_by: SAMPLE_AGENT, download_url: `/api/reports/${rid}/download`, current: true };
    state.customer.reports.push(row);
    for (const d of downloads.splice(0)) {
      d.resolve({ suggestedFilename: () => row.filename, failure: async () => null, saveAs: async target => fs.writeFileSync(target, data) });
    }
    return row;
  };
  const customerGet = where => {
    state.gets.push(where);
    if (where === '/api/encounters') return json(200, { encounters: [{ id, title: state.customer.title, state: state.customer.state, state_label: state.customer.state_label,
      service_date: '2026-11-03', date_conflict: false, open_details: 0, created_at: state.customer.created_at, kind: 'paste',
      in_queue: ['action_needed', 'awaiting_detail', 'ready'].includes(state.customer.state) }] });
    if (where === `/api/encounters/${id}`) {
      const body = clone(state.customer);
      if (leak.vendorKey) body.codes[0].vendor = 'OpenAI';
      return json(200, body);
    }
    if (where === `/api/encounters/${id}/original`) return json(404, { error: 'Not found.' });
    const report = /^\/api\/reports\/([^/]+)\/download$/.exec(where);
    if (report && state.files.has(report[1])) return bytes(200, state.files.get(report[1]), { 'content-type': 'text/plain', ...(leak.customerHash ? { 'x-content-sha256': crypto.createHash('sha256').update(state.files.get(report[1])).digest('hex') } : {}) });
    if (report && state.legacy.some(item => item.id === report[1])) return bytes(leak.legacyVisible ? 200 : 404, 'legacy', {});
    if (where.startsWith('/ops/')) return leak.opsOpen && where === `/ops/api/encounters/${id}` ? json(200, state.operator) : json(404, { error: 'Not found.' });
    if (where === `/api/encounters/${id}/trace`) return json(404, { error: 'Not found.' });
    throw new Error(`unexpected customer GET ${where}`);
  };
  const operatorGet = where => {
    if (where === '/ops/api/encounters') return json(200, { encounters: [{ id }] });
    if (where === `/ops/api/encounters/${id}`) return json(200, state.operator);
    if (where === `/ops/api/encounters/${id}/trace`) return json(200, state.trace);
    if (where === `/ops/api/encounters/${id}/reports`) return json(200, { reports: [...state.listing, ...state.legacy] });
    if (where === '/ops/' || where === '/ops/assets/ops.js') return bytes(200, 'operator page', { 'content-type': 'text/html' });
    const report = /^\/ops\/api\/reports\/([^/]+)\/download$/.exec(where);
    if (report && state.files.has(report[1])) {
      const data = state.files.get(report[1]);
      return bytes(200, data, { 'x-content-sha256': crypto.createHash('sha256').update(data).digest('hex') });
    }
    if (where === `/api/encounters/${id}/trace`) return json(404, { error: 'Not found.' });
    throw new Error(`unexpected operator GET ${where}`);
  };
  const strings = () => {
    const out = [];
    const walk = node => {
      for (const child of node.childNodes) {
        if (child.text !== undefined) { if (child.text.trim()) out.push(['text', node.tag, child.text]); continue; }
        for (const [name, value] of Object.entries(child.attrs)) if (/^(aria-|data-|title$|alt$|placeholder$|value$)/.test(name)) out.push(['attr', `${child.tag}@${name}`, value]);
        walk(child);
      }
    };
    walk(doc().root);
    return out;
  };
  const measure = () => {
    const width = state.viewport === 'mobile' ? 390 : 1440;
    const item = { left: 16, right: width - 16, width: width - 32, height: 60, shown: true, hit: true, enabled: true };
    const rows = state.customer.codes.map(code => ({ proposal: code.id, ...item }));
    const actions = state.customer.codes.flatMap(code => code.allowed_actions.map(action => ({ action, proposal: code.id, ...item, width: 120, height: 48 })));
    return { width, height: state.viewport === 'mobile' ? 844 : 1000, scroll_width: leak.overflowMobile && state.viewport === 'mobile' ? 640 : width, rows, actions, controls: [], offenders: [] };
  };
  const clickOn = (selector, index = 0) => {
    const nodes = doc().querySelectorAll(selector);
    const node = nodes[index];
    if (!node) throw new Error(`nothing to click at ${selector}`);
    const decision = node.getAttribute('data-decision');
    if (decision) {
      state.dialog = { action: decision, proposal: node.getAttribute('data-proposal'), ack: false, note: '', modifier: '' };
      state.acts.push(`open ${decision} ${state.customer.codes.find(c => c.id === state.dialog.proposal).code}`);
      return;
    }
    if (node.getAttribute('data-action') === 'export') { state.exportOpen = true; state.acts.push('open export'); return; }
    if (node.tag === 'summary') { state.whyOpen = true; state.acts.push('open why'); return; }
    if (node.attrs.class === 'export-option') {
      const body = { kind: node.getAttribute('data-export-kind'), fmt: node.getAttribute('data-export-fmt') };
      state.acts.push(`export ${body.kind}.${body.fmt} at ${state.viewport}`);
      const row = reportOn(body);
      posted(`/api/encounters/${id}/reports`, body, 201, row);
      return;
    }
    throw new Error(`unexpected click on ${selector}`);
  };
  const locator = (selector, index = null) => {
    const at = () => (index === null ? 0 : index);
    const self = {
      first: () => locator(selector, 0), nth: i => locator(selector, i), locator: sub => locator(`${selector} ${sub}`, null),
      count: async () => doc().querySelectorAll(selector).length,
      click: async () => clickOn(selector, at()),
      isVisible: async () => doc().querySelectorAll(selector).length > at(),
      isDisabled: async () => Boolean(doc().querySelectorAll(selector)[at()]?.disabled),
      waitFor: async ({ state: wanted } = {}) => {
        const present = doc().querySelectorAll(selector).length > 0;
        if ((wanted || 'visible') === 'visible' && !present && selector !== '#exportDialog') throw new Error(`${selector} is not visible`);
      },
      inputValue: async () => (selector.includes('reviewModifier') ? state.dialog.modifier : ''),
      selectOption: async value => { state.dialog.modifier = value; state.acts.push(`modifier ${value}`); },
      evaluate: async fn => fn(doc().querySelectorAll(selector)[at()]),
      evaluateAll: async fn => fn(doc().querySelectorAll(selector)),
      textContent: async () => doc().querySelectorAll(selector)[at()]?.textContent || '',
    };
    return self;
  };
  const page = {
    goto: async next => { state.url = next; },
    url: () => state.url,
    waitForURL: async predicate => { if (!predicate(new URL(state.url))) throw new Error(`not at ${state.url}`); },
    request: {
      get: async address => customerGet(new URL(address).pathname),
      post: async (address, { data } = {}) => {
        const where = new URL(address).pathname;
        if (where.startsWith('/ops/')) return json(leak.opsPostOpen ? 400 : 404, { error: leak.opsPostOpen ? 'Choose a report.' : 'Not found.' });
        if (where === `/api/encounters/${id}/details`) { state.acts.push('details posted again'); state.posts.push({ path: where, body: clone(data) }); return json(200, { saved: true }); }
        throw new Error(`unexpected customer POST ${where}`);
      },
    },
    context: () => ({ cookies: async () => [{ name: 'cptstudio_csrf', value: 'synthetic-csrf' }] }),
    evaluate: async (fn) => {
      if (fn === vb.readCustomerDom) return vb.readCustomerDom(doc());
      const source = String(fn);
      if (fn.name === 'collectDomStrings') return strings();
      if (fn.name === 'readAnimations') return [];
      if (fn.name === 'measureViewport') return measure();
      if (source.includes('toasts.slice')) return leak.toast ? [leak.toast] : [];
      throw new Error(`unexpected evaluate: ${source.slice(0, 80)}`);
    },
    waitForFunction: async () => true,
    waitForTimeout: async () => {},
    reload: async () => { state.acts.push('reload'); state.dialog = null; state.exportOpen = false; state.whyOpen = false; },
    screenshot: async ({ path: file }) => fs.writeFileSync(file, 'png'),
    setViewportSize: async size => { state.viewport = size.width === 390 ? 'mobile' : 'desktop'; },
    locator,
    check: async selector => {
      if (selector === '#reviewAcknowledgement' && state.dialog) { state.dialog.ack = true; return; }
      throw new Error(`unexpected check of ${selector}`);
    },
    fill: async (selector, value) => {
      if (selector === '#reviewNote' && state.dialog) { state.dialog.note = value; return; }
      throw new Error(`unexpected fill of ${selector}`);
    },
    click: async selector => {
      if (selector === '#saveReview' && state.dialog) {
        const dialog = state.dialog;
        if (dialog.action === 'approve' && !dialog.ack) throw new Error('the screen refuses an approval without its acknowledgement');
        const body = { proposal_id: dialog.proposal, action: dialog.action, note: dialog.note.trim(),
          acknowledgement: dialog.action === 'approve' ? sampleJson('customer-session.json').acknowledgement : '', ...(dialog.modifier ? { modifiers: [dialog.modifier] } : {}) };
        state.acts.push(`${dialog.action} ${state.customer.codes.find(c => c.id === dialog.proposal).code} at ${state.viewport}`);
        state.dialog = null;
        posted(`/api/encounters/${id}/decisions`, body, 201, decideOn(body));
        return;
      }
      clickOn(selector);
    },
    waitForResponse: predicate => new Promise(done => { waiters.push({ predicate, resolve: done }); }),
    waitForEvent: kind => {
      if (kind !== 'download') throw new Error(`unexpected event ${kind}`);
      return new Promise(done => { downloads.push({ resolve: done }); });
    },
    on: (kind, listen) => { if (kind === 'request') requestListeners.add(listen); },
    off: (kind, listen) => { requestListeners.delete(listen); },
    once: () => {},
    keyboard: { press: async () => { state.dialog = null; state.exportOpen = false; } },
  };
  const op = { request: { get: async address => operatorGet(new URL(address).pathname) } };
  const anonymous = { get: async address => (new URL(address).pathname.startsWith('/ops/') ? json(leak.anonymousOpen ? 200 : 404, {}) : json(401, {})) };
  return { page, op, anonymous, state, id };
}

async function walkSite(site, { plan = {}, notes = AGENT_NOTES, opts = {}, doc: extra = {} } = {}) {
  const out = privateDir();
  try {
    const text = OP().revision.text;
    const doc = { id: 'cux-01', title: 'customer walk', source: 'documents/cux-01.txt', delivery: { format: 'paste', file: 'cux-01.paste.txt' },
      upload: { service_date: null }, expected_extraction: {}, expected_context: {}, expected_routing: {}, expected_clarifications: [], incomplete_services: [],
      must_not_code: [{ family: 'gi.egd', reason: 'planned, not performed' }], review_plan: plan, ...extra };
    const item = { doc, sourceText: text, delivery: { format: 'paste', file: doc.delivery.file, sha256: sha(text), size: Buffer.byteLength(text) } };
    const watch = { current: null };
    const account = { username: null, label: SAMPLE_AGENT, actor_kind: 'agent', acknowledgement: sampleJson('customer-session.json').acknowledgement };
    const record = await vb.verifyDocument(site.page, { out, baseUrl: BASE, encounter: site.id, deadlineSeconds: 60, noAutoApprove: false, account, ...opts },
      { review_notes: notes }, item, [], { op: site.op, anonymous: site.anonymous, watch, account });
    return { record, out: null };
  } finally {
    fs.rmSync(out, { recursive: true, force: true });
  }
}

test('the walk decides, reloads, downloads and probes through the customer page with the operator view beside it, and passes on a consistent site', async () => {
  const site = fakeSite();
  const { record } = await walkSite(site, { plan: { modifiers: { 45385: 'XS' } } });
  assert.equal(record.error, null);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => `${a.id}: ${a.reason}`), []);
  assert.equal(record.result, 'pass');
  assert.deepEqual(site.state.acts, ['open why', 'open approve 45380', 'approve 45380 at mobile', 'open approve 45385', 'modifier XS', 'approve 45385 at desktop', 'reload',
    'open export', 'export draft.txt at mobile', 'open export', 'export draft.csv at desktop', 'open export', 'export approved.txt at desktop', 'open export',
    'export approved.csv at desktop']);
  assert.deepEqual(site.state.posts.filter(p => p.path.endsWith('/decisions')).map(p => [p.body.action, p.body.modifiers || []]), [['approve', []], ['approve', ['XS']]]);
  const by = Object.fromEntries(record.assertions.map(a => [a.id, a.status]));
  for (const id of ['customer.contract', 'customer.vocabulary', 'customer.codes.listed', 'customer.why.exact', 'customer.why.supports', 'provenance.participants',
    'provenance.trace', 'pipeline.no_duplicate_send', 'dom.row.45380', 'dom.checks_panel', 'dom.why_opens', 'viewport.desktop.no_horizontal_scroll',
    'viewport.mobile.no_horizontal_scroll', 'decision.mobile', 'decision.modifier.45385', 'persist.decision.45385', 'dom.decision.45385', 'customer.decision.45385',
    'decisions.labelled', 'download.draft.txt', 'download.approved.csv', 'download.mobile', 'listing.approved.txt', 'authorization.customer_ops_404',
    'authorization.trace_removed', 'authorization.anonymous', 'authorization.operator_reads', 'scan.json', 'scan.header', 'scan.dom', 'scan.file',
    'after_reload.customer.contract', 'final.no_duplicate_send']) {
    assert.equal(by[id], 'pass', id);
  }
  assert.equal(by['reload.same_encounter'], 'skipped', 'nothing was busy, so no reload while processing was due');
  assert.deepEqual(record.downloads.map(d => [d.kind, d.fmt, d.viewport, d.operator_audience]), [['draft', 'txt', 'mobile', 'customer'], ['draft', 'csv', 'desktop', 'customer'],
    ['approved', 'txt', 'desktop', 'customer'], ['approved', 'csv', 'desktop', 'customer']]);
  assert.ok(record.screenshots.some(s => s.name === 'review-dialog' && s.viewport === 'mobile'));
  assert.ok(Object.keys(record.operator_snapshots).includes('final') && Object.keys(record.customer_snapshots).includes('final'));
  // the customer probes never touched an operator view with the customer session
  assert.ok(site.state.gets.filter(g => g.startsWith('/ops/')).length >= 6);
});

test('the walk catches each leak and each broken promise of the customer surface', async () => {
  const cases = [
    [{ vendorKey: true }, ['customer.contract', 'scan.json']],
    [{ opsOpen: true }, ['authorization.customer_ops_404', 'scan.json']],
    [{ opsPostOpen: true }, ['authorization.customer_ops_404']],
    [{ anonymousOpen: true }, ['authorization.anonymous']],
    [{ customerHash: true }, ['download.draft.txt', 'download.draft.csv', 'download.approved.txt', 'download.approved.csv', 'scan.header']],
    [{ toast: 'Fable request failed (HTTP 529)' }, ['scan.dom']],
    [{ exportAria: 'Download the trace' }, ['scan.dom']],
    [{ reportLine: 'Provider usage: corti 3 credits' }, ['scan.file']],
    [{ operatorAudience: 'operator' }, ['download.draft.txt', 'download.draft.csv', 'download.approved.txt', 'download.approved.csv']],
    // the page posted XS (decision.modifier passes); the server dropped it: the row and the served decision say so
    [{ dropModifier: true }, ['dom.decision.45385', 'customer.decision.45385']],
    [{ wrongReviewer: true }, ['customer.decision.45380', 'customer.decision.45385']],
    [{ overflowMobile: true }, ['viewport.mobile.no_horizontal_scroll']],
    [{ legacyArtifact: true, legacyVisible: true }, ['authorization.operator_artifacts_hidden']],
  ];
  for (const [leak, wanted] of cases) {
    const { record } = await walkSite(fakeSite({ leak }), { plan: { modifiers: { 45385: 'XS' } } });
    const got = record.assertions.filter(a => a.status === 'fail').map(a => a.id);
    for (const id of wanted) assert.ok(got.includes(id), `${JSON.stringify(leak)}: ${id} not failed (failed: ${got.join(', ')}${record.error ? `; error ${record.error}` : ''})`);
    assert.equal(record.result, 'fail', JSON.stringify(leak));
  }
  // a legacy artifact the customer cannot reach is a pass
  const { record } = await walkSite(fakeSite({ leak: { legacyArtifact: true } }), { plan: { modifiers: { 45385: 'XS' } } });
  assert.equal(record.assertions.find(a => a.id === 'authorization.operator_artifacts_hidden').status, 'pass');
  assert.equal(record.result, 'pass');
});

test('the walk without a modifier plan chooses none, and the acceptance reviewer\'s approvals are refused as an agent site\'s', async () => {
  const site = fakeSite();
  const { record } = await walkSite(site);
  assert.deepEqual(site.state.posts.filter(p => p.path.endsWith('/decisions')).map(p => p.body.modifiers || []), [[], []]);
  assert.equal(record.result, 'pass');
  // the acceptance reviewer records HUMAN approvals: a site that records them as an agent's fails the reload checks
  const human = { username: 'demo-reviewer', label: SAMPLE_AGENT, actor_kind: 'human', acknowledgement: 'x' };
  const accepted = await walkSite(fakeSite(), { notes: ACC_NOTES, plan: { approve_codes: ['45380'] }, opts: { acceptanceReviewer: true, noAutoApprove: true, account: human } });
  const got = accepted.record.assertions.filter(a => a.status === 'fail').map(a => a.id);
  for (const id of ['persist.decision.45380', 'dom.decision.45380', 'customer.decision.45380', 'decisions.labelled']) assert.ok(got.includes(id), `${id}: ${got.join(', ')}`);
});

// --- the 2026-11-05 acceptance walk's corrections ------------------------------------------------------------------------
// The live walk of 24c49a50 failed six checks that were wrong about the page (the compact line held to the whole panel's
// contract, a message read from the head that the page says in its notice, a model asked of Corti, whose API names
// none) and missed the upload's client key; and the stopped panel told nobody they could leave, which was the page's.
// Each check is held here to what the real page draws and the real operator view serves, and to the shape it must fail.

const CUSTOMER_FIXTURES_DIR = path.join(ROOT, 'tests', 'fixtures', 'customer');
const customerFixture = name => JSON.parse(fs.readFileSync(path.join(CUSTOMER_FIXTURES_DIR, name), 'utf8'));
const CUSTOMER_FIXTURES = fs.readdirSync(CUSTOMER_FIXTURES_DIR).filter(name => /^encounter-.+\.json$/.test(name)).sort();
const pageHtml = enc => app.progressPanel(enc, pageUi(enc));
const pageDom = (enc, edit = html => html) => domOf(`<html><body>${edit(pageHtml(enc))}</body></html>`);

test('checkProgressDom passes on the panel the real page draws for every served state, the compact line included', () => {
  const kinds = new Set();
  for (const name of CUSTOMER_FIXTURES) {
    const enc = customerFixture(name);
    assert.deepEqual(failed(vb.checkProgressDom(enc, pageDom(enc), [])), [], name);
    kinds.add(vb.PANEL_PHASES.has(enc.progress.phase) ? 'panel' : 'compact');
  }
  assert.deepEqual([...kinds].sort(), ['compact', 'panel']);
  // what the walk failed on, each read where the page draws it
  const stopped = customerFixture('encounter-stopped.json');
  const stoppedIds = ids(vb.checkProgressDom(stopped, pageDom(stopped), []));
  for (const id of ['progress.dom.whole_panel:pass', 'progress.dom.message:pass', 'progress.dom.error:pass', 'progress.dom.leave_note:pass', 'progress.dom.resume:pass']) {
    assert.ok(stoppedIds.includes(id), id);
  }
  const ready = customerFixture('encounter-ready.json');
  const readyIds = ids(vb.checkProgressDom(ready, pageDom(ready), []));
  for (const id of ['progress.dom.compact:pass', 'progress.dom.took:pass', 'progress.dom.still:pass']) assert.ok(readyIds.includes(id), id);
  assert.ok(!readyIds.some(id => /^progress\.dom\.(steps|leave_note):/.test(id)), 'a finished line has no steps or leave note to hold it to');
});

test('checkProgressDom fails a waiting, stopped or failed panel folded into the compact line, a finished one drawn whole, and each missing part', () => {
  const stopped = customerFixture('encounter-stopped.json');
  const ready = customerFixture('encounter-ready.json');
  // the stopped document drawn as if finished: one compact line
  const folded = domOf(`<html><body>${pageHtml(ready).replace('data-phase="completed"', 'data-phase="stopped"')}</body></html>`);
  assert.ok(failed(vb.checkProgressDom(stopped, folded, [])).includes('progress.dom.whole_panel'));
  // a finished document drawn as the whole panel
  const whole = domOf(`<html><body>${pageHtml(stopped).replace('data-phase="stopped"', 'data-phase="completed"')}</body></html>`);
  assert.ok(failed(vb.checkProgressDom(ready, whole, [])).includes('progress.dom.compact'));
  // the compact line without the time it took, or still animating
  assert.deepEqual(failed(vb.checkProgressDom(ready, pageDom(ready, html => html.replace(/ · finished in <span[^>]*>[^<]*<\/span>/, '')), [])), ['progress.dom.took']);
  assert.deepEqual(failed(vb.checkProgressDom(ready, pageDom(ready), ['svg.icon (spin)'])), ['progress.dom.still']);
  // the stopped notice gone: its sentence is said nowhere
  const noNotice = pageDom(stopped, html => html.replace(/<div class="progress-error"[\s\S]*?<\/div><\/div>/, ''));
  assert.deepEqual(failed(vb.checkProgressDom(stopped, noNotice, [])).sort(), ['progress.dom.error', 'progress.dom.message']);
  // the stopped panel the 2026-11-05 walk met: no leave note
  assert.deepEqual(failed(vb.checkProgressDom(stopped, pageDom(stopped, html => html.replace(/<p class="leave-note">[^<]*<\/p>/, '')), [])), ['progress.dom.leave_note']);
});

test('the sample pages draw the progress panel as the page does for their encounters', () => {
  const fields = p => p && { phase: p.phase, compact: p.compact, summary: p.summary.replace(/finished in .*$/, 'finished in'), steps: p.steps.length,
    message: p.message, leave: p.leave, stop: p.stop, resume: p.resume, notice: p.notice, elapsed_present: p.elapsed_present };
  for (const [page, enc] of [['customer-page.html', CUST()], ['customer-page-details.html', DETAILS()]]) {
    assert.deepEqual(fields(domOf(sample(page)).progress), fields(pageDom(enc).progress), page);
  }
});

test('checkProvenance: Corti names no model - its runs stand on endpoint, adapter version and identity - and every other participant still names its models', () => {
  const op = OP();
  assert.equal(op.harness.participants[0].model, '', 'the sample serves Corti as the live operator view does');
  assert.deepEqual(failed(vb.checkProvenance(op, TRACE(), { expectHarness: true })), []);
  assert.equal(vb.checkProvenance(op, TRACE()).find(r => r.id === 'provenance.returned_models').status, 'pass');
  for (const [label, mutate] of [['Astra without its model', o => { o.harness.participants[1].model = ''; }],
    ['Corti without its vendor', o => { o.harness.participants[0].vendor = ''; }]]) {
    const o = OP();
    mutate(o);
    assert.deepEqual(failed(vb.checkProvenance(o, TRACE())), ['provenance.models'], label);
  }
  const unanswered = OP();
  unanswered.harness.participants[2].returned_model = '';
  assert.equal(vb.checkProvenance(unanswered, TRACE()).find(r => r.id === 'provenance.returned_models').status, 'warn');
  const corti = TRACE().participants[0].runs;
  assert.ok(corti.length === 1 && corti[0].requested_model === '' && corti[0].adapter_version, 'the sample traces Corti\'s run as the live trace does');
  for (const [label, mutate] of [['Corti without its adapter version', t => { t.participants[0].runs[0].adapter_version = ''; }],
    ['Corti without its endpoint', t => { t.participants[0].runs[0].endpoint = ''; }],
    ['Corti without its identity', t => { t.participants[0].runs[0].run_identity = ''; }],
    ['Astra without its model', t => { t.participants[1].runs[0].requested_model = ''; }]]) {
    const t = TRACE();
    mutate(t);
    assert.deepEqual(failed(vb.checkProvenance(OP(), t)), ['provenance.trace'], label);
  }
});

test('uploadCarriedClientKey reads the form the page sent, since Playwright serves no body that holds a file', () => {
  const watch = (keys, uuid = true) => ({ requests: [{ method: 'GET', path: '/api/encounters' },
    { method: 'POST', path: '/api/encounters', ...(keys ? { form_keys: keys, client_key_uuid: uuid } : {}) }] });
  assert.equal(vb.uploadCarriedClientKey(watch(['file', 'service_date', 'synthetic_attestation', 'client_key'])), true);
  // an empty or malformed key is no key to the server (api._client_key), so it is not carried (refutation, 2026-11-05)
  assert.equal(vb.uploadCarriedClientKey(watch(['file', 'synthetic_attestation', 'client_key'], false)), false);
  assert.equal(vb.uploadCarriedClientKey(watch(['file', 'synthetic_attestation'])), false);
  assert.equal(vb.uploadCarriedClientKey(watch(null), ''), false, 'no form seen and no body: not carried');
  assert.equal(vb.uploadCarriedClientKey(watch(null), 'Content-Disposition: form-data; name="client_key"'), true, 'a text body Playwright did serve');
  assert.equal(vb.uploadCarriedClientKey(null, ''), false);
});

test('planProblems: a document expected to fail names a failed state, carries no plan and is walked in agent mode', () => {
  const notes = { approve: 'Approved in an agent-executed synthetic review.' };
  const base = { id: 'x-fail', expected_failure: 'extraction_failed' };
  assert.deepEqual(vb.planProblems(base, notes), []);
  for (const [label, doc] of [['not a failed state', { ...base, expected_failure: 'failed' }], ['with a plan', { ...base, review_plan: { stop_and_resume: true } }],
    ['with questions expected', { ...base, expected_no_em_questions: true }],
    ['with an extraction its walk never checks', { ...base, expected_extraction: { status_in: ['ok'] } }],
    ['with codes its walk never checks', { ...base, author_expected_cpt: ['45378'], must_not_code: [] }]]) {
    assert.equal(vb.planProblems(doc, notes).length, 1, label);
  }
  assert.ok(vb.planProblems(base, { approve: vb.ACCEPTANCE_LABEL }, { acceptanceReviewer: true }).some(p => /agent mode only/.test(p)));
});

test('checkFailure: the failed panel the page draws, the named state, nothing sent and no code; each broken promise fails', () => {
  const enc = customerFixture('encounter-failed.json');
  const op = { state: 'extraction_failed', provider_runs: [] };
  assert.equal(enc.progress.error.action, 'new_document', 'the scenario: the page offers "Upload a new document"');
  assert.deepEqual(failed(vb.checkFailure(enc, op, pageDom(enc), 'extraction_failed', [])), []);
  assert.ok(ids(vb.checkFailure(enc, op, pageDom(enc), 'extraction_failed', [])).includes('failure.action:pass'));
  const sent = { id: 'r1', provider: 'corti', purpose: 'primary', state: 'succeeded', sent: true };
  // the operator view's own run shape (serializers._provider_run_json): no `sent` key at all (refutation, 2026-11-05)
  const live = OP().provider_runs[0];
  assert.ok(!('sent' in live), 'the sample serves runs as the operator view does');
  const cases = [
    ['failure.state', [enc, { ...op, state: 'provider_failed' }, pageDom(enc)]],
    ['failure.nothing_sent', [enc, { ...op, provider_runs: [sent] }, pageDom(enc)]],
    ['failure.nothing_sent', [enc, { ...op, provider_runs: [live] }, pageDom(enc)]],
    ['failure.nothing_sent', [enc, { ...op, provider_runs: [{ ...live, state: 'not_sent' }] }, pageDom(enc)]],
    ['progress.dom.panel', [enc, op, domOf('<html><body></body></html>')]],
    ['failure.no_codes', [{ ...clone(enc), codes: [{ code: '45378' }] }, op, pageDom(enc)]],
    ['failure.customer', [{ ...clone(enc), state: 'ready' }, op, pageDom(enc)]],
    ['failure.action', [enc, op, pageDom(enc, html => html.replace(/<button type="button" class="button secondary" data-action="upload">[^<]*<\/button>/, ''))]],
    ['progress.dom.leave_note', [enc, op, pageDom(enc, html => html.replace(/<p class="leave-note">[^<]*<\/p>/, ''))]],
  ];
  for (const [id, [c, o, d]] of cases) assert.ok(failed(vb.checkFailure(c, o, d, 'extraction_failed', [])).includes(id), id);
});

test('checkProgressDom: a waiting, stopped or failed document with no panel fails, busy or not; a finished one may have none', () => {
  // the review page always draws its panel (app.js reviewView); refutation 2026-11-05: none passed whenever nothing was busy
  for (const name of ['encounter-stopped.json', 'encounter-failed.json', 'encounter-action-needed.json', 'encounter-being-confirmed.json']) {
    const enc = customerFixture(name);
    assert.equal(enc.progress.busy, false, `${name}: the scenario`);
    assert.deepEqual(failed(vb.checkProgressDom(enc, domOf('<html><body></body></html>'), [])), ['progress.dom.panel'], name);
  }
  assert.deepEqual(failed(vb.checkProgressDom(customerFixture('encounter-ready.json'), domOf('<html><body></body></html>'), [])), []);
});

test('checkProgressDom asks the time elapsed only of a busy queued or processing panel, as the page shows it', () => {
  // refutation 2026-11-05: a paused document (decision (j)) and a date hold being re-checked are busy and show no time
  const paused = customerFixture('encounter-processing.json');
  paused.progress.phase = 'paused';
  const held = customerFixture('encounter-action-needed.json');
  held.progress.busy = true;
  for (const enc of [paused, held]) {
    const results = vb.checkProgressDom(enc, pageDom(enc), []);
    assert.deepEqual(failed(results), [], enc.progress.phase);
    assert.ok(!ids(results).some(id => id.startsWith('progress.dom.elapsed')), enc.progress.phase);
  }
  const processing = customerFixture('encounter-processing.json');
  assert.deepEqual(failed(vb.checkProgressDom(processing, pageDom(processing, html => html.replace(/<p class="progress-time">[\s\S]*?<\/p>/, '')), [])), ['progress.dom.elapsed']);
});

test('checkCompactProgress holds the compact line to its own phase\'s title', () => {
  // refutation 2026-11-05: any non-empty line passed
  const ready = customerFixture('encounter-ready.json');
  const partial = customerFixture('encounter-partial.json');
  assert.deepEqual(failed(vb.checkProgressDom(partial, pageDom(partial), [])), []);
  assert.deepEqual(failed(vb.checkProgressDom(ready, pageDom(ready, html => html.replace('<strong>Results ready</strong>', '<strong>Processing could not finish</strong>')), [])), ['progress.dom.compact']);
  assert.deepEqual(failed(vb.checkProgressDom(partial, pageDom(partial, html => html.replace('<strong>Results ready, with a limitation</strong>', '<strong>Results ready</strong>')), [])), ['progress.dom.compact']);
  const unknown = { ...clone(ready), progress: { ...clone(ready).progress, phase: 'archived' } };
  assert.ok(failed(vb.checkProgressDom(unknown, pageDom(ready, html => html.replace('data-phase="completed"', 'data-phase="archived"')), [])).includes('progress.dom.compact'));
});

// The walk of a document that must fail, end to end on the fake site (the refutation's harness, 2026-11-05): a failed
// encounter served as the operator and customer views serve one.
function failedSite({ runs = 'none' } = {}) {
  const site = fakeSite();
  const f = customerFixture('encounter-failed.json');
  f.id = site.id;
  f.state = 'failed'; f.state_label = 'Could not finish'; f.codes = []; f.other_codes = []; f.details_needed = [];
  f.progress.error = { text: 'We could not read the text of this document. Upload a clearer copy, or paste the text instead.', action: 'new_document' };
  f.progress.message = f.progress.error.text;
  f.reports = []; f.readiness = { draft: false, approved: false, blockers: [] };
  site.state.customer = f;
  site.state.operator.state = 'extraction_failed';
  if (runs === 'none') site.state.operator.provider_runs = [];
  return site;
}

test('the walk of a document that must fail passes a failed encounter that sent nothing, list contract and probes included', async () => {
  const { record } = await walkSite(failedSite(), { plan: {}, doc: { expected_failure: 'extraction_failed' } });
  assert.equal(record.error, null);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => `${a.id}: ${a.reason}`), []);
  assert.equal(record.result, 'pass');
  assert.equal(record.failure.provider_runs, 0);
  for (const id of ['failure.state', 'failure.nothing_sent', 'failure.action', 'progress.dom.leave_note', 'customer.list_contract', 'scan.json']) {
    assert.ok(record.assertions.some(a => a.id === id && a.status === 'pass'), id);
  }
});

test('the walk of a document that must fail fails one that sent requests, one that did not fail, and refuses a foreign attached paste', async () => {
  const sent = (await walkSite(failedSite({ runs: 'sample' }), { plan: {}, doc: { expected_failure: 'extraction_failed' } })).record;
  assert.equal(sent.result, 'fail');
  assert.ok(sent.assertions.some(a => a.id === 'failure.nothing_sent' && a.status === 'fail'));
  const succeeded = (await walkSite(fakeSite(), { plan: {}, doc: { expected_failure: 'extraction_failed' } })).record;
  assert.equal(succeeded.result, 'fail');
  for (const id of ['failure.state', 'failure.customer']) assert.ok(succeeded.assertions.some(a => a.id === id && a.status === 'fail'), id);
  const foreign = failedSite();
  foreign.state.operator.revision.text = 'SYNTHETIC TEST DOCUMENT - a different document altogether\n';
  const refused = (await walkSite(foreign, { plan: {}, doc: { expected_failure: 'extraction_failed' } })).record;
  assert.match(String(refused.error), /^refusing to act on encounter /);
  assert.notEqual(refused.result, 'pass');
});

test('checkDetailsPanel holds a saved row to its saved answer and a way to change it, an open row to its offers, as the page draws each', () => {
  // walk 2 on cpt.quillmd.com (2026-11-05): the saved extent row showed "Saved: Not documented" and "Change this answer",
  // as app.js savedAnswer draws it, and the walk failed it for not offering the open row's answer buttons
  const open = DETAILS();
  const saved = DETAILS();
  saved.details_needed = [saved.details_needed[0], { ...saved.details_needed[1],
    saved: { value: 'not_documented', label: 'Not documented', by: SAMPLE_AGENT, at: '2026-11-05T04:12:00+00:00', answer_id: 'ans-1' } }];
  const drawn = (enc, edit = html => html) => domOf(`<html><body>${edit(app.detailsPanel(enc, pageUi(enc)))}</body></html>`);
  assert.deepEqual(failed(vb.checkDetailsPanel(open, drawn(open))), []);
  assert.deepEqual(failed(vb.checkDetailsPanel(saved, drawn(saved))), []);
  const savedRow = drawn(saved).details.rows[1];
  assert.ok(savedRow.saved && savedRow.revoke && savedRow.choices.length === 0, 'the scenario: the page draws the saved row without answer buttons');
  const reasons = (enc, edit) => vb.checkDetailsPanel(enc, drawn(enc, edit)).filter(r => r.status === 'fail').map(r => r.reason).join(' | ');
  assert.match(reasons(saved, html => html.replace(/<p class="detail-saved">[\s\S]*?<\/p>/, '')), /does not show its saved answer/);
  assert.match(reasons(saved, html => html.replace(/<button[^>]*data-action="revoke-detail"[^>]*>[^<]*<\/button>/, '')), /offers no way to change its saved answer/);
  assert.match(reasons(open, html => html.replace(/<button[^>]*data-detail-choice="cannot_confirm"[^>]*>[^<]*<\/button>/, '')), /does not offer cannot_confirm/);
  // a busy document draws no change control, and is not failed for it
  const busy = clone(saved);
  busy.progress.busy = true;
  assert.ok(!/offers no way to change/.test(reasons(busy, html => html)));
});

test('review_plan.addendum is validated, and checkAddendum holds the addendum to a new revision with nothing carried', () => {
  const doc = plan => ({ id: 'c1c', review_plan: plan });
  const notes = { approve: 'Agent-executed synthetic verification review' };
  assert.deepEqual(vb.planProblems(doc({ addendum: { fact: 'extent', code: '45338', text: 'Advanced to 40 cm.', expect_ready: ['45338'] } }), notes), []);
  const problems = plan => vb.planProblems(doc({ addendum: plan }), notes).join(' | ');
  assert.match(problems('extent'), /must be an object/);
  assert.match(problems({ text: 'x' }), /\.fact must name/);
  assert.match(problems({ fact: 'extent', text: '  ' }), /\.text must be/);
  assert.match(problems({ fact: 'extent', text: 'x', code: '4533' }), /\.code must be a five-digit code/);
  assert.match(problems({ fact: 'extent', text: 'x', expect_ready: '45338' }), /expect_ready must be a list/);
  assert.match(problems({ fact: 'extent', text: 'x', answer: 'yes' }), /unknown key: answer/);
  const plan = { fact: 'extent', code: '45338', text: 'Advanced to 40 cm.', expect_ready: ['45338'] };
  const after = (status = 'ready', saved = null) => ({
    op: { assessment: { proposals: [{ code: '45338', bucket: 'selected', status }] } },
    cust: { details_needed: saved ? [{ fact: 'extent', affects: ['45338'], saved }] : [] } });
  const step = (over = {}) => ({ error: null, after: after(), ...over,
    record: { requests: 1, http_status: 201, withdrew: 'ans-1', revision: { before: { id: 'r1', number: 1, total: 1, kind: 'upload' },
      after: { id: 'r2', number: 2, total: 2, kind: 'addendum' } }, ...(over.record || {}) } });
  const bad = s => vb.checkAddendum(plan, s).filter(r => r.status === 'fail').map(r => r.id);
  assert.deepEqual(bad(step()), []);
  assert.deepEqual(bad(step({ record: { requests: 2 } })), ['addendum.added']);
  assert.deepEqual(bad(step({ error: 'expected one open extent row that offers the addendum, found 0', after: null })), ['addendum.added']);
  assert.deepEqual(bad(step({ record: { revision: { before: { id: 'r1', number: 1, total: 1, kind: 'upload' },
    after: { id: 'r1', number: 1, total: 1, kind: 'upload' } } } })), ['addendum.new_revision']);
  assert.deepEqual(bad(step({ after: after('ready', { value: 'not_documented', answer_id: 'ans-1' }) })), ['addendum.earlier_answer_not_applied']);
  assert.deepEqual(bad(step({ after: after('needs_clarification') })), ['addendum.ready.45338']);
});

test('expected_codes: validated, and checkExpectedCodes fails an omitted supported code, an unsupported READY code, a second unit and an incompleteness signal', () => {
  const doc = codes => ({ id: 'c1a', review_plan: {}, expected_codes: codes });
  const notes = { approve: 'Agent-executed synthetic verification review' };
  const good = { ready: ['45385', '45380'], not_ready: ['45378', '43239'], units: { 45385: 1 }, complete: ['gi.colonoscopy'] };
  assert.deepEqual(vb.planProblems(doc(good), notes), []);
  const problems = codes => vb.planProblems(doc(codes), notes).join(' | ');
  assert.match(problems(['45385']), /must be an object/);
  assert.match(problems({ ready: ['4538'] }), /ready must be a list of distinct five-digit codes/);
  assert.match(problems({ not_ready: ['45378', '45378'] }), /not_ready must be a list of distinct/);
  assert.match(problems({ ready: ['45385'], not_ready: ['45385'] }), /both ready and not_ready/);
  assert.match(problems({ units: { 45385: 0 } }), /units must map/);
  assert.match(problems({ complete: 'gi.colonoscopy' }), /complete must be a list of families/);
  assert.match(problems({ readyy: [] }), /unknown key: readyy/);
  assert.match(vb.planProblems({ id: 'f', review_plan: {}, expected_failure: 'extraction_failed', expected_codes: good }, notes).join(' | '), /carries expected_codes, which its walk never checks/);
  // the sample operator view: 45380 and 45385 selected READY, 45378 an alternative, 43239 excluded
  const bad = (codes, op = OP()) => vb.checkExpectedCodes(codes, op).filter(r => r.status === 'fail').map(r => r.id);
  assert.deepEqual(bad(good), []);
  assert.deepEqual(vb.checkExpectedCodes(good, OP()).map(r => r.id), ['codes.ready.45385', 'codes.ready.45380', 'codes.not_ready.45378',
    'codes.not_ready.43239', 'codes.units.45385', 'codes.complete.gi.colonoscopy']);
  assert.deepEqual(bad({ ready: ['45381'] }), ['codes.ready.45381']);           // an omitted supported service
  assert.deepEqual(bad({ not_ready: ['45380'] }), ['codes.not_ready.45380']);   // an unsupported addition
  const held = OP();
  held.assessment.proposals.find(p => p.code === '45385').status = 'needs_clarification';
  assert.deepEqual(bad({ ready: ['45385'], not_ready: ['45385'].slice(1) }, held), ['codes.ready.45385']);
  const twice = OP();
  twice.assessment.proposals.push({ ...clone(twice.assessment.proposals.find(p => p.code === '45385')), id: 'second-45385' });
  assert.deepEqual(bad({ units: { 45385: 1 } }, twice), ['codes.units.45385']);
  const two = OP();
  two.assessment.proposals.find(p => p.code === '45385').units = 2;
  assert.deepEqual(bad({ units: { 45385: 1 } }, two), ['codes.units.45385']);
  const reduced = OP();
  reduced.assessment.proposals.find(p => p.code === '45380').modifier_considerations = ['The examination did not reach the cecum: modifier 53 may apply.'];
  assert.deepEqual(bad({ complete: ['gi.colonoscopy'] }, reduced), ['codes.complete.gi.colonoscopy']);
  const failing = OP();
  failing.assessment.proposals.find(p => p.code === '45385').checks.push({ id: 'procedure.complete', label: 'Procedure completion', status: 'warn', detail: 'The procedure was incomplete.' });
  assert.deepEqual(bad({ complete: ['gi.colonoscopy'] }, failing), ['codes.complete.gi.colonoscopy']);
  // an excluded or alternative proposal of the code is not READY; a passing check that names completion is no signal
  const passing = OP();
  passing.assessment.proposals.find(p => p.code === '45385').checks.push({ id: 'procedure.complete', label: 'Incomplete procedure', status: 'pass', detail: 'Not incomplete.' });
  assert.deepEqual(bad({ not_ready: ['43239', '45378'], complete: ['gi.colonoscopy'] }, passing), []);
  const odd = OP();  // only a selected, non-excluded proposal is READY, whatever status another bucket's row carries
  odd.assessment.proposals.find(p => p.code === '43239').status = 'ready';
  odd.assessment.proposals.find(p => p.code === '45378').status = 'ready';
  assert.deepEqual(bad({ not_ready: ['43239', '45378'] }, odd), []);
  const dropped = OP();  // a selected row excluded since (status excluded) carries no signal for the codes still live
  Object.assign(dropped.assessment.proposals.find(p => p.code === '45380'), { status: 'excluded', modifier_considerations: ['Reduced services: modifier 52 may apply.'] });
  assert.deepEqual(bad({ complete: ['gi.colonoscopy'] }, dropped), []);
  assert.deepEqual(vb.checkExpectedCodes(undefined, OP()), []);
  assert.deepEqual(vb.checkExpectedCodes({ not_ready: ['45380'] }, OP(), 'after_addendum.codes').map(r => r.id), ['after_addendum.codes.not_ready.45380']);
});

test('checkClarifications: a performed-status expectation is met by a conflict question about the act, and by nothing else', () => {
  const enc = facts => ({ clarifications: facts.map(([fact, scope, state = 'open']) => ({ fact, scope, state, question: `${fact}?` })) });
  const bad = (expected, e) => vb.checkClarifications(expected, e).filter(r => r.status === 'fail').map(r => r.id);
  const want = [{ fact: 'performed_status', scope_in: ['service', 'proposal'] }];
  assert.deepEqual(bad(want, enc([['performed_status', 'proposal']])), []);
  assert.deepEqual(bad(want, enc([['conflict:removal', 'proposal']])), []);
  assert.deepEqual(bad(want, enc([['conflict:removal', 'proposal', 'answered']])), ['clarification.performed_status']);
  assert.deepEqual(bad(want, enc([['conflict:removal', 'encounter']])), ['clarification.performed_status']);
  assert.deepEqual(bad(want, enc([['extent', 'proposal']])), ['clarification.performed_status']);
  // no other fact takes the alias
  assert.deepEqual(bad([{ fact: 'extent', scope_in: ['proposal'] }], enc([['conflict:extent', 'proposal']])), ['clarification.extent']);
});

test('checkMemberAnswers: a "Not documented" answer for a code leaves it excluded by that answer, its question closed', () => {
  const answers = [{ fact: 'service_date', value: 'use_document' }, { fact: 'extent', value: 'not_documented', code: '45385' }];
  const member = { id: 'member.answer', label: 'Member answer', status: 'fail', source: 'cpt-studio:member-answer@1',
    detail: 'The member answered "Not documented" to how far the examination reached; this code is excluded by that answer until it is withdrawn.' };
  const recomputed = () => {
    const op = OP();
    const p = op.assessment.proposals.find(item => item.code === '45385');
    Object.assign(p, { bucket: 'excluded', status: 'excluded', checks: [...p.checks, clone(member)] });
    op.clarifications = [{ id: 'q1', scope: 'proposal', proposal_id: p.id, family: 'gi.colonoscopy', fact: 'extent', state: 'answered' }];
    return op;
  };
  const bad = op => vb.checkMemberAnswers(answers, { op }).filter(r => r.status === 'fail').map(r => r.id);
  assert.deepEqual(bad(recomputed()), []);
  assert.deepEqual(vb.checkMemberAnswers(answers, { op: recomputed() }).map(r => r.id),
    ['details.member_answer.45385.excluded', 'details.member_answer.45385.question_closed']);
  // the code still READY (the answer never recomputed), excluded for another reason, or gone; the question still open
  assert.deepEqual(bad(OP()), ['details.member_answer.45385.excluded']);
  const other = recomputed();
  other.assessment.proposals.find(item => item.code === '45385').checks.pop();
  assert.deepEqual(bad(other), ['details.member_answer.45385.excluded']);
  const cannot = recomputed();
  cannot.assessment.proposals.find(item => item.code === '45385').checks.at(-1).detail = member.detail.replace('Not documented', 'Cannot confirm');
  assert.deepEqual(bad(cannot), ['details.member_answer.45385.excluded']);
  const gone = recomputed();
  gone.assessment.proposals = gone.assessment.proposals.filter(item => item.code !== '45385');
  assert.deepEqual(bad(gone), ['details.member_answer.45385.excluded']);
  const open = recomputed();
  open.clarifications[0].state = 'open';
  assert.deepEqual(bad(open), ['details.member_answer.45385.question_closed']);
  // a question of another code, or of another fact, stays open without failing this answer
  const elsewhere = recomputed();
  elsewhere.clarifications.push({ id: 'q2', scope: 'proposal', proposal_id: 'a1f0b2c3-0001-4d5e-8f60-718293a4b5c6', family: 'gi.colonoscopy', fact: 'extent', state: 'open' },
    { id: 'q3', scope: 'proposal', proposal_id: elsewhere.assessment.proposals.find(item => item.code === '45385').id, family: 'gi.colonoscopy', fact: 'setting', state: 'open' });
  assert.deepEqual(bad(elsewhere), []);
  // an answer with no code, a context answer, or no settled view checks nothing here
  assert.deepEqual(vb.checkMemberAnswers([{ fact: 'extent', value: 'not_documented' }], { op: OP() }), []);
  assert.deepEqual(vb.checkMemberAnswers(answers, null), []);
});

test('withdrawalTookEffect waits for the withdrawn answer itself, not for the page to read idle (the walk round c1c race)', () => {
  const row = (extra = {}) => ({ id: 'd1', fact: 'extent', affects: ['45338'], saved: null, addendum_allowed: true, ...extra });
  const savedRow = row({ saved: { answer_id: 'ans-1', answer: 'not_documented' }, addendum_allowed: false });
  // the pre-withdrawal snapshot (what c1c read): the answer still saved, so the withdrawal has NOT taken effect
  assert.equal(vb.withdrawalTookEffect({ details_needed: [savedRow] }, 'extent', '45338', 'ans-1'), false);
  assert.equal(vb.withdrawalTookEffect({ details_needed: [savedRow] }, 'extent', null, 'ans-1'), false);
  // the reopened row: no saved answer
  assert.equal(vb.withdrawalTookEffect({ details_needed: [row()] }, 'extent', '45338', 'ans-1'), true);
  // another answer saved on the row (a later save) is not the withdrawn one
  assert.equal(vb.withdrawalTookEffect({ details_needed: [row({ saved: { answer_id: 'ans-2' } })] }, 'extent', '45338', 'ans-1'), true);
  // a saved answer of another fact or another code is not this row's
  assert.equal(vb.withdrawalTookEffect({ details_needed: [savedRow, row({ id: 'd2', fact: 'setting', saved: { answer_id: 'ans-1' } })] },
    'setting', null, 'ans-9'), true);
  // no row of THIS code is served (the saved row is another code's): absent, so not yet taken effect
  assert.equal(vb.withdrawalTookEffect({ details_needed: [savedRow] }, 'extent', '45380', 'ans-1'), false);
  // nothing served, or no row of the fact and code served, is NOT the target state: the row is briefly absent while the
  // withdrawal's recompute runs (the recall round's c1c walk, 2026-11-08), and the walk keeps waiting for it to return
  assert.equal(vb.withdrawalTookEffect(null, 'extent', '45338', 'ans-1'), false);
  assert.equal(vb.withdrawalTookEffect({ details_needed: [] }, 'extent', '45338', 'ans-1'), false);
  assert.equal(vb.withdrawalTookEffect({ details_needed: [row({ id: 'd3', affects: ['45380'] })] }, 'extent', '45338', 'ans-1'), false);
  // the row served again, unsaved and offering the addendum: taken effect
  assert.equal(vb.withdrawalTookEffect({ details_needed: [row({ id: 'd3', affects: ['45380'] }), row()] }, 'extent', '45338', 'ans-1'), true);
});
