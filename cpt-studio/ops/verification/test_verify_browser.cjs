'use strict';
// Unit tests for the pure checks in ops/verify_browser.cjs. No server, no browser.
//   node --test ops/verification/test_verify_browser.cjs
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const vb = require('../verify_browser.cjs');

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

function proposal(id, code, extra = {}) {
  const flex = code.startsWith('4533');
  return {
    id, key: id, bucket: 'selected', code, code_kind: 'cpt1', family: flex ? 'gi.flex_sig' : 'gi.colonoscopy',
    family_label: flex ? 'Flexible sigmoidoscopy' : 'Colonoscopy', eyebrow: flex ? 'FLEXIBLE SIGMOIDOSCOPY' : 'COLONOSCOPY',
    supported: true, profile_version: 'x@1', status: 'ready', status_label: 'Ready for review', exclusion_reason: '',
    reinstatable: false, descriptor: { status: 'withheld', label: 'Description withheld.' }, evidence: [], rationale: '',
    units: 1, checks: [], modifier_considerations: [], clarification_ids: [], decision: null, decision_state: 'undecided',
    allowed_actions: ['approve', 'reject'], ...extra,
  };
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
  enc.decisions.history.push({ ...p.decision, invalidated: null });
  return enc;
}

const statuses = (results, id) => results.filter(r => r.id === id).map(r => r.status);
const failures = results => results.filter(r => r.status === 'fail').map(r => r.id);

// --- arguments, helpers, session -----------------------------------------------------------

test('parseArgs requires every input and normalises the base URL', () => {
  const opts = vb.parseArgs(['--base-url', 'https://cpt.quillmd.com/x/', '--credentials', 'c.json', '--docs', 'd', '--manifest',
    'm.json', '--out=o', '--only=gi-01, gi-03', '--deadline-seconds', '60', '--stop-on-failure']);
  assert.equal(opts.baseUrl, 'https://cpt.quillmd.com');
  assert.deepEqual(opts.only, ['gi-01', 'gi-03']);
  assert.equal(opts.deadlineSeconds, 60);
  assert.equal(opts.stopOnFailure, true);
  assert.equal(opts.allowLiveProvider, false);
  assert.throws(() => vb.parseArgs(['--base-url', 'https://x']), /missing --credentials/);
  assert.throws(() => vb.parseArgs(['--base-url', 'not a url', '--credentials', 'c', '--docs', 'd', '--manifest', 'm', '--out', 'o']), vb.UsageError);
  assert.throws(() => vb.parseArgs(['--base-url', 'ftp://x', '--credentials', 'c', '--docs', 'd', '--manifest', 'm', '--out', 'o']), /http/);
  assert.throws(() => vb.parseArgs(['--base-url', 'https://x', '--credentials', 'c', '--docs', 'd', '--manifest', 'm', '--out', 'o', '--deadline-seconds', '5']), /at least 10/);
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

test('checkDecisionDom requires the decided badge, the reviewer and the agent label', () => {
  const enc = decided(decided(encounter(), 'p-flex', 'approve', 'n'), 'p-colo', 'reject', 'n');
  const made = [{ proposal_id: 'p-flex', code: '45331', action: 'approve', http_status: 201 }, { proposal_id: 'p-colo', code: '45380', action: 'reject', http_status: 201 }];
  const insight = `Approved by ${AGENT} 23 Oct 2026 · agent-executed synthetic review — not clinical approval`;
  const cards = [{ id: 'card-p-flex', badge: 'Approved · agent', insight }, { id: 'card-p-colo', badge: 'Rejected', insight: insight.replace('Approved', 'Rejected') }];
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, cards)), []);
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, [{ ...cards[0], badge: 'Approved' }, { ...cards[1], insight: 'Rejected by someone' }])), ['dom.decision.45331', 'dom.decision.45380']);
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, [])), ['dom.decision.45331', 'dom.decision.45380']);
  assert.deepEqual(vb.checkDecisionDom([{ ...made[0], http_status: 409 }], enc, []), []);
});

test('checkDownloads: every expected report downloaded with matching hashes; reviewed withheld until ready', () => {
  const file = { http_status: 201, size: 10, sha256: 'a', api_sha256: 'a', refetch_sha256: 'a', header_sha256: 'a', report_id: 'r' };
  const ready = { draft: true, reviewed: true };
  const all = ['draft', 'reviewed'].flatMap(kind => ['txt', 'csv'].map(fmt => ({ ...file, kind, fmt })));
  assert.deepEqual(failures(vb.checkDownloads(all, ready, null)), []);
  assert.deepEqual(failures(vb.checkDownloads([{ ...all[0], api_sha256: 'b' }, ...all.slice(1)], ready, null)), ['download.draft.txt']);
  assert.deepEqual(failures(vb.checkDownloads([{ ...all[0], refetch_sha256: 'b' }, ...all.slice(1)], ready, null)), ['download.draft.txt']);
  assert.deepEqual(failures(vb.checkDownloads(all.slice(0, 3), ready, null)), ['download.reviewed.csv']);
  assert.deepEqual(failures(vb.checkDownloads([{ ...all[1], error: 'download failed: canceled' }, all[0]], { draft: true, reviewed: false }, { offered: false })), ['download.draft.csv']);
  assert.deepEqual(failures(vb.checkDownloads(all.slice(0, 2), { draft: true, reviewed: false }, { offered: true })), ['download.reviewed_withheld']);
  assert.deepEqual(failures(vb.checkDownloads(all.slice(0, 2), { draft: true, reviewed: false }, { offered: false })), []);
  assert.deepEqual(vb.expectedDownloads({ draft: false, reviewed: false }), []);
});

test('checkListing: every downloaded report is listed on the encounter with its sha256', () => {
  const downloads = [{ kind: 'draft', fmt: 'txt', report_id: 'r1', sha256: 'a' }, { kind: 'draft', fmt: 'csv', report_id: 'r2', sha256: 'b' }];
  const enc = encounter({ reports: [{ id: 'r1', kind: 'draft', fmt: 'txt', sha256: 'a' }, { id: 'r2', kind: 'draft', fmt: 'csv', sha256: 'c' }] });
  assert.deepEqual(vb.checkListing(downloads, enc).map(r => r.status), ['pass', 'fail']);
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

// --- the live frontend's markup ---------------------------------------------------------------

const APP = path.join(ROOT, 'studio', 'static', 'studio', 'app.js');
const UNESCAPE = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' };
const unescape = text => text.replace(/&(amp|lt|gt|quot|#x27|#x60);/g, m => UNESCAPE[m]);
const textOf = html => unescape(html.replace(/<[^>]*>/g, ''));

function elements(html, tag, className) {
  const out = [];
  for (const match of html.matchAll(new RegExp(`<${tag}\\b([^>]*)>([\\s\\S]*?)</${tag}>`, 'g'))) {
    const classes = (/\bclass="([^"]*)"/.exec(match[1]) || [])[1] || '';
    if (classes.split(' ').includes(className)) out.push({ attrs: match[1], inner: match[2] });
  }
  return out;
}

function attr(attrs, name) {
  return unescape((new RegExp(`\\b${name}="([^"]*)"`).exec(attrs) || [])[1] || '');
}

function parseReview(html) {
  const marks = elements(html, 'button', 'evidence-mark').map(el => ({ keys: (attr(el.attrs, 'data-keys') || attr(el.attrs, 'data-evidence')).split(' ').filter(Boolean), text: textOf(el.inner) }));
  const cards = elements(html, 'article', 'code-card').map(el => ({
    id: attr(el.attrs, 'id'),
    badge: textOf((/<div class="code-card-top">[\s\S]*?(<span class="status[^"]*">[\s\S]*?<\/span>)/.exec(el.inner) || [])[1] || '').trim(),
    insight: textOf((/<div class="review-insight">([\s\S]*?)<\/div><\/div>/.exec(el.inner) || [])[1] || '').replace(/\s+/g, ' ').trim(),
    unlocated: (el.inner.match(/class="evidence-chip unlocated"/g) || []).length,
  }));
  return { marks, cards };
}

test('the DOM checks agree with the markup the live app.js renders', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, () => {
  const app = require(APP);
  const enc = decided(decided(encounter(), 'p-flex', 'approve', NOTES.approve), 'p-colo', 'reject', NOTES.reject);
  enc.assessment.proposals[0].evidence.push(at(EXTENT, { text: 'not in the source' }));
  const html = app.reviewView(enc, app.documentLayout(enc), 'codes', false);
  const { marks, cards } = parseReview(html);
  // The overlapping biopsy spans share one mark; the span across a blank line is split in two.
  assert.deepEqual(marks.map(m => m.keys), [['p-colo:0', 'p-flex:0'], ['p-flex:1'], ['p-flex:1']]);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, cards)), []);
  assert.equal(cards.find(c => c.id === 'card-p-flex').unlocated, 1);
  const made = [{ proposal_id: 'p-flex', code: '45331', action: 'approve', http_status: 201 }, { proposal_id: 'p-colo', code: '45380', action: 'reject', http_status: 201 }];
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, cards)), []);
  assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks.filter(m => !m.keys.includes('p-flex:1')), cards)), ['dom.marks.45331']);
  const options = app.exportOptions({ draft: true, reviewed: false });
  assert.ok(options.includes('data-export-kind="draft" data-export-fmt="txt"') && options.includes('data-export-kind="draft" data-export-fmt="csv"'));
  assert.equal(options.includes('data-export-kind="reviewed"'), false);
});

// refutation p2, reports2:4: the support.source marks the live app.js renders - for a support that was checked and for
// one that was not (not_applicable: the documented service's passages) - are read as known exact spans.
test('the DOM checks read the support.source marks the live app.js renders as known', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, () => {
  const app = require(APP);
  for (const status of ['warn', 'not_applicable']) {
    const enc = encounter();
    enc.assessment.proposals[1].support = { status, source: [sourceSpan(EXTENT), sourceSpan(HISTORY)] };
    const html = app.reviewView(enc, app.documentLayout(enc), 'codes', false);
    const { marks, cards } = parseReview(html);
    assert.ok(marks.some(m => m.keys.includes('p-colo:s0')) && marks.some(m => m.keys.includes('p-colo:s1')), status);
    assert.deepEqual(failures(vb.checkEvidenceMarks(enc, marks, cards)), [], status);
  }
});

// --- round 5: a confirmed exclusion has no code card (pipeline:3); the walk confirms only must_not_code (pipeline:5)

function withExcluded(enc, id, code, family, extra = {}) {
  enc.assessment.proposals.push(proposal(id, code, { bucket: 'excluded', status: 'excluded', family, reinstatable: true,
    exclusion_reason: 'Documented as planned, not as performed on the date of service.',
    allowed_actions: ['reinstate', 'confirm'], ...extra }));
  return enc;
}

function confirmed(enc, id) {
  const p = enc.assessment.proposals.find(item => item.id === id);
  p.decision = { id: `d-${id}`, proposal_id: id, code: p.code, action: 'confirm', note: 'n', reviewer: AGENT,
    reviewer_kind: 'agent', created_at: '2026-10-23T21:00:00Z', revision_number: 1 };
  p.decision_state = 'exclusion_confirmed';
  p.allowed_actions = ['revoke'];
  return enc;
}

test('checkDecisionDom reads a confirmed exclusion from its candidate row, not from a code card', () => {
  const enc = confirmed(withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy'), 'p-plan');
  const made = [{ proposal_id: 'p-plan', code: '45378', action: 'confirm', http_status: 201 }];
  const row = { proposal: 'p-plan', text: `45378 · Colonoscopy Documented as planned, not as performed on the date of service. Exclusion confirmed by ${AGENT}. Undo decision` };
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, [], [row])), []);
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, [], [])), ['dom.decision.45378']);
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, [], [{ ...row, text: 'Exclusion confirmed by someone else.' }])), ['dom.decision.45378']);
  const undone = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy');
  assert.deepEqual(failures(vb.checkDecisionDom(made, undone, [], [row])), ['dom.decision.45378']);
});

test('planConfirmations confirms only the families must_not_code names', () => {
  // pipeline:5's witness: a misread exclusion of the visit the author expects to be coded is never confirmed.
  const enc = withExcluded(withExcluded(encounter(), 'p-visit', '99213', 'gi.office_em'), 'p-plan', '45378', 'gi.colonoscopy');
  const plan = vb.planConfirmations(enc, [{ family: 'gi.colonoscopy' }], { confirm: 'Synthetic confirmation.' });
  assert.deepEqual(plan.map(d => [d.code, d.action, d.note]), [['45378', 'confirm', 'Synthetic confirmation.']]);
  assert.deepEqual(vb.planConfirmations(enc, [], {}), []);
  assert.deepEqual(vb.planConfirmations(enc, undefined, {}), []);
  for (const extra of [{ reinstatable: false }, { decision_state: 'reinstated' }, { allowed_actions: ['reinstate'] }]) {
    const other = withExcluded(encounter(), 'p-plan', '45378', 'gi.colonoscopy', extra);
    assert.deepEqual(vb.planConfirmations(other, [{ family: 'gi.colonoscopy' }], {}), [], JSON.stringify(extra));
  }
});

// --- round 6, pipeline:3: readDom's candidate rows, over the markup the live app renders -----------------------------
//
// A minimal DOM for readDom's own selectors (tag, .class, [attr="value"], compound and descendant), so the unit suite
// runs the same $$eval callbacks the real walk runs in Chromium. Dropping the candidate rows from readDom must fail here.

function parseHtml(html) {
  const decode = text => text.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
    .replace(/&#x60;/g, '`').replace(/&amp;/g, '&');
  const VOID = new Set(['area', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
  const root = { tag: '#root', attrs: {}, children: [], parent: null };
  let node = root;
  const token = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
  for (const m of html.matchAll(token)) {
    if (m[5] !== undefined) { node.children.push({ text: decode(m[5]) }); continue; }
    if (!m[2]) continue;
    const tag = m[2].toLowerCase();
    if (m[1]) {
      let open = node;
      while (open && open.tag !== tag) open = open.parent;
      if (open && open.parent) node = open.parent;
      continue;
    }
    const attrs = {};
    for (const a of m[3].matchAll(/([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) attrs[a[1].toLowerCase()] = decode(a[2] ?? a[3] ?? a[4] ?? '');
    const element = { tag, attrs, children: [], parent: node };
    node.children.push(element);
    if (!VOID.has(tag) && !m[4]) node = element;
  }
  return root;
}

function compoundMatches(node, compound) {
  if (!node || !node.tag || node.tag === '#root') return false;
  const tag = compound.match(/^[a-z][a-z0-9-]*/i);
  if (tag && node.tag !== tag[0].toLowerCase()) return false;
  const classes = (node.attrs.class || '').split(/\s+/);
  for (const [, name] of compound.matchAll(/\.([\w-]+)/g)) if (!classes.includes(name)) return false;
  for (const [, name, value] of compound.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
    if (!(name in node.attrs) || (value !== undefined && node.attrs[name] !== value)) return false;
  }
  return true;
}

function selectorMatches(node, selector) {
  const parts = selector.trim().split(/\s+/);
  if (!compoundMatches(node, parts.pop())) return false;
  let ancestor = node.parent;
  while (parts.length) {
    while (ancestor && !compoundMatches(ancestor, parts[parts.length - 1])) ancestor = ancestor.parent;
    if (!ancestor) return false;
    parts.pop();
    ancestor = ancestor.parent;
  }
  return true;
}

function wrap(node) {
  const descendants = function* walk(n) { for (const child of n.children || []) { if (child.tag) { yield child; yield* walk(child); } } };
  const text = n => (n.text !== undefined ? n.text : (n.children || []).map(text).join(''));
  const dataset = {};
  for (const [name, value] of Object.entries(node.attrs || {})) {
    if (name.startsWith('data-')) dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
  }
  return {
    id: node.attrs.id || '', dataset, textContent: text(node),
    closest(selector) {
      for (let n = node; n && n.tag !== '#root'; n = n.parent) if (selectorMatches(n, selector)) return wrap(n);
      return null;
    },
    querySelector(selector) { for (const d of descendants(node)) if (selectorMatches(d, selector)) return wrap(d); return null; },
    querySelectorAll(selector) { return [...descendants(node)].filter(d => selectorMatches(d, selector)).map(wrap); },
  };
}

function fakePage(html) {
  const root = parseHtml(html);
  root.attrs = {};
  const top = wrap(root);
  return { $$eval: async (selector, fn) => fn(top.querySelectorAll(selector)) };
}

test('readDom reads a confirmed exclusion from its candidate row in the rendered page, and the decision check passes', async () => {
  const app = require('../../studio/static/studio/app.js');
  const doc = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'tests', 'fixtures', 'api', 'encounter-ready.json'), 'utf8'));
  const id = '0b6f6a2e-3c1d-4f7a-9e2b-5d8c7a6b4e3f';
  const excluded = { ...doc.assessment.proposals[0], id, code: '45378', bucket: 'excluded', status: 'excluded', reinstatable: true,
    exclusion_reason: 'Documented as planned, not as performed on the date of service.', reinstated_by: null,
    decision: { action: 'confirm', reviewer: 'Review Agent One', reviewer_kind: 'agent' }, decision_state: 'exclusion_confirmed',
    allowed_actions: ['revoke'], approve_withheld_by: null };
  // A decided selected code shows its own undo button inside its code card: that one is not a candidate row.
  const [first, ...rest] = doc.assessment.proposals;
  const approved = { ...first, decision: { action: 'approve', reviewer: 'Review Agent One', reviewer_kind: 'agent' },
    decision_state: 'approved', allowed_actions: ['revoke'] };
  const enc = { ...doc, assessment: { ...doc.assessment, proposals: [approved, ...rest, excluded] } };
  const html = app.reviewView(enc, app.documentLayout(enc), 'codes', true);
  assert.ok(html.includes(`data-decision="revoke" data-proposal="${approved.id}"`), 'the code card has no undo button: the filter is untested');
  const dom = await vb.readDom(fakePage(html));
  assert.ok(Array.isArray(dom.candidates), 'readDom returned no candidate rows');
  assert.deepEqual(dom.candidates.map(c => c.proposal), [id]);
  assert.ok(dom.candidates[0].text.includes('Exclusion confirmed by Review Agent One'), dom.candidates[0].text);
  assert.ok(dom.cards.length >= 1, 'the code cards were not read: the fake page proves nothing');
  const made = [{ http_status: 201, action: 'confirm', proposal_id: id, code: '45378' }];
  assert.deepEqual(vb.checkDecisionDom(made, enc, dom.cards, dom.candidates).map(r => r.status), ['pass']);
  // and the same check fails when the row is missing, as it did when readDom dropped the rows
  assert.deepEqual(vb.checkDecisionDom(made, enc, dom.cards, []).map(r => r.status), ['fail']);
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

const EDIT_OK = { http_status: 201, error: null, posted: { service_date: DOCUMENTED, setting: '', billing_context: '' },
  identical: { via: 'api', form_posted: false, form_toast: 'No context change to save.', http_status: 201, error: null } };
const SERVICE_DATE_PLAN = { service_date: DOCUMENTED, clear_member_date: false };
const CLEAR_PLAN = { service_date: '', clear_member_date: true };
const clone = value => JSON.parse(JSON.stringify(value));
const hardFailures = results => results.filter(r => r.severity === 'hard' && r.status === 'fail').map(r => r.id);

test('parseArgs: --no-auto-approve is an option, off by default', () => {
  const base = ['--base-url', 'https://x', '--credentials', 'c', '--docs', 'd', '--manifest', 'm', '--out', 'o'];
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
  // the screen posted an identical save instead of refusing it (the server then judged it)
  const posted = { ...EDIT_OK, identical: { via: 'form', form_posted: true, form_toast: '', http_status: 201, error: null } };
  assert.deepEqual(statuses(vb.checkContextEdit(before, after, clone(after), SERVICE_DATE_PLAN, posted, MEMBER), 'context_edit.form_refuses_identical'), ['warn']);
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

test('the context step\'s selectors and the screen behaviour it relies on are the live frontend\'s', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, () => {
  const app = require(APP);
  const source = fs.readFileSync(APP, 'utf8');
  const page = fs.readFileSync(path.join(ROOT, 'studio', 'templates', 'studio', 'index.html'), 'utf8');
  for (const id of ['contextDialog', 'contextForm', 'contextServiceDate', 'contextSetting', 'contextBilling', 'saveContext', 'serviceDate', 'toast']) {
    assert.ok(page.includes(`id="${id}"`), id);
  }
  const idle = encounter();
  assert.ok(app.reviewView(idle, app.documentLayout(idle), 'codes', false).includes('data-action="edit-context"'));
  const busy = encounter({ pipeline: { busy: true, can_stop: true, stages: [] } });
  assert.equal(app.reviewView(busy, app.documentLayout(busy), 'codes', false).includes('data-action="edit-context"'), false);
  assert.ok(source.includes("toast('No context change to save.')"), 'the screen no longer refuses an identical save with that message');
  assert.ok(/\nasync function api\(path, \{ method = 'GET', json, form \} = \{\}\)/.test(source), 'the page\'s api() client changed');
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
  assert.ok(body.indexOf('const foreign = record.attached ? attachedProblems(enc, item) : [];') < refusal);
  for (const act of ['await editContext(', 'await askSecondReview(', 'await decide(']) {
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
const ANSWER_EDIT = { http_status: 201, error: null, posted: { service_date: ANSWER, setting: '', billing_context: '' },
  identical: { via: 'api', form_posted: false, form_toast: 'No context change to save.', http_status: 201, error: null } };
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

// A scripted page for verifyDocument's attached walk (--encounter): GET /api/encounters/<id> serves the encounter of
// the stage reached; the context form behaves as app.js's openContext and submitContext do (prefilled from the
// member's values; a save that changes nothing closes with a toast and sends nothing); page.evaluate is the page's
// api() client. Every act is recorded; anything else the walk asks of it is not a function, so a step the walk was not
// expected to take ends it with an error.
function walkPage(id, states) {
  const base = 'https://cpt.example';
  const target = `/api/encounters/${id}/context`;
  const acts = [];
  const posts = [];
  let current = states[0];
  let url = 'about:blank';
  let dialog = null;
  let toast = '';
  let pendingRequest = null;
  let pendingResponse = null;
  const serve = body => {
    posts.push(body);
    current = states[Math.min(posts.length, states.length - 1)];
    return { status: () => 201, json: async () => ({ context_id: `ctx-${posts.length}` }) };
  };
  const answered = response => ({ status: () => response.status(), json: response.json, url: () => `${base}${target}`,
    request: () => ({ method: () => 'POST' }) });
  const deferred = () => {
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    return { promise, resolve };
  };
  const locator = selector => {
    const self = {
      first: () => self,
      count: async () => (selector === 'button[data-action="edit-context"]' || selector === '#exportDialog[open]' ? 1 : 0),
      click: async () => {
        if (selector !== 'button[data-action="edit-context"]') throw new Error(`unexpected click on ${selector}`);
        acts.push('open the context form');
        dialog = { value: current.context.user_values.service_date || '', closed: deferred() };
      },
      waitFor: async ({ state } = {}) => {
        if (selector !== '#contextDialog') throw new Error(`unexpected wait for ${selector}`);
        if (state === 'visible' && !dialog) throw new Error('the context dialog is not open');
        if (state === 'hidden' && dialog) await dialog.closed.promise;
      },
      textContent: async () => (selector === '#toast' ? toast : ''),
    };
    return self;
  };
  const page = {
    acts, posts,
    goto: async next => { url = next; },
    url: () => url,
    waitForURL: async predicate => { if (!predicate(new URL(url))) throw new Error(`not at ${url}`); },
    request: { get: async address => {
      const where = new URL(address).pathname;
      if (where === `/api/encounters/${id}`) return { ok: () => true, status: () => 200, json: async () => clone(current) };
      if (where === `/api/encounters/${id}/original`) return { ok: () => false, status: () => 404, body: async () => Buffer.alloc(0) };
      throw new Error(`unexpected GET ${where}`);
    } },
    waitForFunction: async () => true,
    $$eval: async () => [],
    locator,
    inputValue: async selector => (selector === '#contextServiceDate' ? dialog.value : ''),
    fill: async (selector, value) => {
      if (selector !== '#contextServiceDate') throw new Error(`unexpected fill of ${selector}`);
      acts.push(`fill the service date with ${JSON.stringify(value)}`);
      dialog.value = value;
    },
    waitForRequest: () => { pendingRequest = deferred(); return pendingRequest.promise; },
    waitForResponse: () => { pendingResponse = deferred(); return pendingResponse.promise; },
    click: async selector => {
      if (selector !== '#saveContext') throw new Error(`unexpected click on ${selector}`);
      const values = current.context.user_values;
      const body = { service_date: dialog.value, setting: values.setting || '', billing_context: values.billing_context || '' };
      const closing = dialog.closed;
      dialog = null;
      if (Object.keys(body).every(name => body[name] === (values[name] || ''))) {  // app.js submitContext
        acts.push('the form refused an identical save');
        toast = 'No context change to save.';
        closing.resolve();
        return;
      }
      acts.push('the form posted');
      const response = serve(body);
      pendingRequest?.resolve({ method: () => 'POST', url: () => `${base}${target}`, postDataJSON: () => body, response: async () => response });
      pendingResponse?.resolve(answered(response));
      setTimeout(() => closing.resolve(), 5);
    },
    evaluate: async (fn, [encounterId, json]) => {
      assert.equal(encounterId, id);
      acts.push('the page api() posted');
      pendingResponse?.resolve(answered(serve(json)));
      return null;
    },
    reload: async () => { acts.push('reload'); dialog = null; },
    keyboard: { press: async () => {} },
    setViewportSize: async () => {},
    waitForTimeout: async () => {},
    screenshot: async () => {},
  };
  return page;
}

// extra: options for the walk (opts) and the manifest's review_notes (notes), for the acceptance reviewer's walk
async function walkQuestion(states, expectedClarifications = [], extra = {}) {
  const id = '0b9e3f7a-1c2d-4e5f-8a9b-0c1d2e3f4a5b';
  const out = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'cpt-verify-question-'));
  try {
    const doc = { id: 'gi3-question', title: 'documented date question', source: 'documents/gi3-question.txt',
      delivery: { format: 'paste', file: 'gi3-question.paste.txt' }, upload: { service_date: null }, expected_extraction: {},
      expected_context: {}, expected_routing: {}, expected_clarifications: expectedClarifications, must_not_code: [],
      incomplete_services: [], review_plan: { reject: null, context_edit: { service_date: ANSWER } } };
    const item = { doc, sourceText: QUESTION_TEXT,
      delivery: { format: 'paste', file: doc.delivery.file, sha256: sha(QUESTION_TEXT), size: Buffer.byteLength(QUESTION_TEXT) } };
    const page = walkPage(id, states.map(state => ({ ...clone(state), id })));
    const opts = { out, baseUrl: 'https://cpt.example', encounter: id, deadlineSeconds: 60, noAutoApprove: false, ...extra.opts };
    const notes = extra.notes || { approve: 'Agent-executed synthetic verification review' };
    const record = await vb.verifyDocument(page, opts, { review_notes: notes }, item, []);
    return { record, acts: page.acts, posts: page.posts };
  } finally {
    fs.rmSync(out, { recursive: true, force: true });
  }
}

test('the walk answers an open date question through the form once, repeats it through api(), and judges both', async () => {
  const before = questionEncounter();
  const after = answeredEncounter(before);
  const { record, acts, posts } = await walkQuestion([before, after, clone(after)], [{ fact: 'service_date', scope_in: ['encounter'] }]);
  assert.equal(record.error, null);
  assert.deepEqual(acts, ['open the context form', 'fill the service date with "2026-10-08"', 'the form posted', 'reload',
    'open the context form', 'fill the service date with "2026-10-08"', 'the form refused an identical save', 'the page api() posted', 'reload',
    'reload']);
  assert.deepEqual(posts, [ANSWER_EDIT.posted, ANSWER_EDIT.posted]);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => a.id), []);
  assert.deepEqual(record.assertions.filter(a => a.id.startsWith('context_edit.') && a.severity === 'hard').map(a => `${a.id}:${a.status}`),
    QUESTION_HARD.map(id => `${id}:pass`));
  assert.equal(record.result, 'pass');
  assert.deepEqual([record.context_edit.answers_question, record.context_edit.http_status, record.context_edit.request_date,
    record.context_edit.expected_request_sha256, record.context_edit.identical.via, record.context_edit.identical.form_toast],
  [true, 201, ANSWER, QUESTION_REQUEST[ANSWER], 'api', 'No context change to save.']);
});

test('the walk makes no edit when the date question is not open: nothing is posted, and the run fails saying why', async () => {
  for (const [label, change] of [
    ['no question', enc => { enc.clarifications = []; }],
    ['a dated request already sent', enc => { enc.provider_runs[0].request_sha256 = QUESTION_REQUEST['2026-10-07']; }],
    ['a service date established', enc => { enc.context.facts.service_date = { name: 'service_date', value: DOCUMENTED, origin: 'document',
      member_conflict: false, note: '', evidence: [inQuestion('Date of procedure: 2026-10-07')] }; }],
  ]) {
    const before = questionEncounter();
    change(before);
    const { record, acts, posts } = await walkQuestion([before, answeredEncounter(before)]);
    assert.equal(record.error, null, label);
    assert.deepEqual([acts.filter(act => act !== 'reload'), posts], [[], []], label);
    assert.equal(record.context_edit.http_status, null, label);
    assert.match(record.context_edit.error, /^not made: context_edit\.\w+ failed, so the edit has nothing verified to answer$/, label);
    const failed = record.assertions.filter(a => a.status === 'fail').map(a => a.id);
    assert.equal(failed.includes('context_edit.request'), true, label);
    assert.equal(failed.filter(id => ['context_edit.question_open', 'context_edit.date_unestablished', 'context_edit.dateless_before'].includes(id)).length, 1, label);
    assert.equal(record.result, 'fail', label);
  }
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

const SIGN_IN = ['--base-url', 'https://x', '--docs', 'd', '--manifest', 'm', '--out', 'o'];

test('a human approval as the app records it: the account\'s actor kind, its label, the human attestation the session serves', () => {
  const app = require(APP);
  const human = attestation('human');
  assert.equal(human, app.ACKNOWLEDGEMENTS.human, 'studio/review.py and app.js hold different human attestations');
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

test('main refuses a password-file run under such a DEBUG before reading anything; a credentials run is refused as before', async () => {
  const dir = privateDir();
  try {
    const missing = [ '--base-url', 'https://x', '--docs', path.join(dir, 'docs'), '--manifest', path.join(dir, 'no-manifest.json'),
      '--out', path.join(dir, 'out')];
    const pwArgs = [...missing, '--password-file', path.join(dir, 'no-password-file'), '--username', 'demo-reviewer'];
    const refused = await runMain(pwArgs, 'pw:protocol');
    assert.equal(refused.code, 2);
    assert.match(refused.err, /^verify_browser: refusing to run with DEBUG=pw:protocol: a Playwright call, channel or protocol log would carry the password\n/);
    assert.match((await runMain([...pwArgs, '--acceptance-reviewer'], 'pw:channel')).err, /refusing to run with DEBUG=pw:channel/);
    // the DEBUG=pw:api refusal stays, for every run
    for (const args of [pwArgs, [...missing, '--credentials', path.join(dir, 'agent.json')]]) {
      assert.match((await runMain(args, 'pw:api')).err, /^verify_browser: refusing to run with DEBUG=pw:api: Playwright would log the password\n/);
    }
    // a credentials run under pw:protocol is not refused for it (unchanged): it stops on the missing manifest instead
    const agent = await runMain([...missing, '--credentials', path.join(dir, 'agent.json')], 'pw:protocol');
    assert.equal(agent.code, 2);
    assert.match(agent.err, /^verify_browser: cannot read manifest /);
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

test('checkPersistence and checkDecisionDom hold a human approval to the acceptance mode, and an agent\'s to agent mode', () => {
  const before = encounter();
  const after = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE);
  const made = [{ proposal_id: 'p-flex', code: '45331', action: 'approve', note: ACC_NOTE, http_status: 201 }];
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, after, 'human')), []);
  assert.deepEqual(failures(vb.checkPersistence(made, before, after, after)), ['persist.decision.45331']);
  const agentAfter = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE, AGENT_ACCOUNT);
  assert.deepEqual(failures(vb.checkPersistence(made, before, agentAfter, agentAfter, 'human')), ['persist.decision.45331']);
  const card = { id: 'card-p-flex', badge: 'Approved', insight: `Approved by Demo Reviewer 1 Nov 2026 · revision 1 · Note: ${ACC_NOTE}` };
  const dom = (cards, decisions = made, shape = after) => vb.checkDecisionDom(decisions, shape, cards, [], { acceptance: true });
  assert.deepEqual(dom([card]).map(r => `${r.id}:${r.status}`), ['dom.decision.45331:pass']);
  assert.deepEqual(failures(dom([{ ...card, badge: 'Approved · agent' }])), ['dom.decision.45331']);
  assert.deepEqual(failures(dom([{ ...card, badge: 'Ready for review' }])), ['dom.decision.45331']);
  assert.deepEqual(failures(dom([{ ...card, insight: 'Approved by someone' }])), ['dom.decision.45331']);
  assert.deepEqual(failures(dom([])), ['dom.decision.45331']);
  assert.match(dom([], [{ ...made[0], action: 'reject' }])[0].reason, /the acceptance reviewer makes approvals only/);
  // agent mode is unchanged: the same human card fails it (no agent label)
  assert.deepEqual(failures(vb.checkDecisionDom(made, after, [card], [])), ['dom.decision.45331']);
});

test('the acceptance checks agree with the markup the live app.js renders for a human approval, and record it verbatim', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, () => {
  const app = require(APP);
  const enc = decidedBy(encounter(), 'p-flex', 'approve', ACC_NOTE);
  const { cards } = parseReview(app.reviewView(enc, app.documentLayout(enc), 'codes', false));
  const card = cards.find(c => c.id === 'card-p-flex');
  assert.ok(card, 'no code card for the approved code');
  const made = [{ proposal_id: 'p-flex', code: '45331', family: 'gi.flex_sig', action: 'approve', note: ACC_NOTE, http_status: 201, decision_id: 'd-p-flex' }];
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, cards, [], { acceptance: true })), []);
  const result = vb.checkAcceptanceDecisions(made, enc, MUST_NOT, ACCOUNT, cards);
  assert.deepEqual(failures(result.checks), []);
  assert.deepEqual([result.labels[0].card_badge, result.labels[0].card_insight], [card.badge, card.insight]);
  // what the app shows for it: approved, not as an agent's, by the reviewer, with the labelled note
  assert.equal(card.badge, 'Approved');
  assert.ok(card.insight.startsWith('Approved by Demo Reviewer'), card.insight);
  assert.ok(card.insight.includes(`Note: ${ACC_NOTE}`) && !/agent/i.test(card.insight), card.insight);
  // and agent mode fails the same card
  assert.deepEqual(failures(vb.checkDecisionDom(made, enc, cards, [])), ['dom.decision.45331']);
});

// A scripted review page for verifyDocument's decisions (an attached, pasted encounter). GET /api/encounters/<id> serves
// the encounter as decided so far; the page is the live app.js's reviewView of it, read through readDom's own selectors
// (parseHtml, wrap); a decision is made only as the screen makes one - its button, the review dialog, the acknowledgement
// box for an approval, the note, Save - and recorded as studio/review.py records it for ``account`` (app.js submitReview
// posts the trimmed note and, for an approval, the session's attestation). Every act is recorded; anything else the
// walk asks of the page ends it with an error.
function reviewPage(id, start, account) {
  const app = require(APP);
  const acts = [];
  const posts = [];
  let current = clone(start);
  let url = 'about:blank';
  let dialog = null;
  let pending = null;
  const dom = () => {
    const root = parseHtml(app.reviewView(current, app.documentLayout(current), 'codes', false));
    root.attrs = {};
    return wrap(root);
  };
  const locator = selector => {
    const self = {
      first: () => self,
      count: async () => {
        if (selector === '#exportDialog[open]') return 1;  // read as open: the walk only asks it what it offers
        if (selector.startsWith('#exportOptions ')) return 0;  // nothing is ready to export (readiness says none)
        if (selector.startsWith('button[data-decision=')) return dom().querySelectorAll(selector).length;
        throw new Error(`unexpected count of ${selector}`);
      },
      click: async () => {
        const match = /^button\[data-decision="(\w+)"\]\[data-proposal="([^"]+)"\]$/.exec(selector);
        if (!match || !dom().querySelectorAll(selector).length) throw new Error(`unexpected click on ${selector}`);
        dialog = { action: match[1], proposal: match[2], acknowledged: false, note: '' };
        acts.push(`open the ${match[1]} dialog for ${match[2]}`);
      },
      waitFor: async ({ state } = {}) => {
        if (selector !== '#reviewDialog') throw new Error(`unexpected wait for ${selector}`);
        if ((state === 'visible') !== Boolean(dialog)) throw new Error(`the review dialog is not ${state}`);
      },
    };
    return self;
  };
  return {
    acts, posts, current: () => current,
    goto: async next => { url = next; },
    url: () => url,
    waitForURL: async predicate => { if (!predicate(new URL(url))) throw new Error(`not at ${url}`); },
    request: { get: async address => {
      const where = new URL(address).pathname;
      if (where === `/api/encounters/${id}`) return { ok: () => true, status: () => 200, json: async () => clone(current) };
      if (where === `/api/encounters/${id}/original`) return { ok: () => false, status: () => 404, body: async () => Buffer.alloc(0) };
      throw new Error(`unexpected GET ${where}`);
    } },
    waitForFunction: async () => true,
    $$eval: async (selector, fn) => fn(dom().querySelectorAll(selector)),
    locator,
    check: async selector => {
      if (selector !== '#reviewAcknowledgement' || !dialog) throw new Error(`unexpected check of ${selector}`);
      dialog.acknowledged = true;
    },
    fill: async (selector, value) => {
      if (selector !== '#reviewNote' || !dialog) throw new Error(`unexpected fill of ${selector}`);
      dialog.note = value;
    },
    waitForResponse: () => {
      let resolve;
      const promise = new Promise(done => { resolve = done; });
      pending = { promise, resolve };
      return promise;
    },
    click: async selector => {
      if (selector !== '#saveReview' || !dialog) throw new Error(`unexpected click on ${selector}`);
      if (dialog.action === 'approve' && !dialog.acknowledged) throw new Error('the screen refuses an approval without its acknowledgement');
      const body = { proposal_id: dialog.proposal, action: dialog.action, note: dialog.note.trim(),
        acknowledgement: dialog.action === 'approve' ? account.acknowledgement : '' };
      posts.push(body);
      decidedBy(current, body.proposal_id, body.action, body.note, account);
      const decision = current.assessment.proposals.find(p => p.id === body.proposal_id).decision;
      acts.push(`${body.action} ${decision.code}`);
      dialog = null;
      pending.resolve({ status: () => 201, json: async () => clone(decision) });
    },
    reload: async () => { acts.push('reload'); },
    keyboard: { press: async () => {} },
    setViewportSize: async () => {},
    waitForTimeout: async () => {},
    screenshot: async () => {},
  };
}

// gi-08 pasted, its two codes ready, an exclusion of a must_not_code family to confirm and a second review on offer: an
// agent walk would approve, reject, confirm and ask; the acceptance walk only approves.
function acceptanceEncounter() {
  const enc = withExcluded(pastedEncounter(), 'p-plan', '43260', 'gi.ercp');
  enc.second_review = { available: true, can_request: true, items: ['Service S1'], reason: '' };
  enc.readiness = { draft: false, reviewed: false, blockers: ['Every selected code needs a decision.'] };
  return enc;
}

async function walkDecisions({ opts = {}, notes, account, reviewPlan }) {
  const id = '6c1f0e9a-2b3d-4c5e-8f9a-0b1c2d3e4f5a';
  const out = privateDir();
  try {
    const doc = { id: 'acceptance-walk', title: 'acceptance walk', source: 'documents/gi-08-flexible-sigmoidoscopy-biopsy.txt',
      delivery: { format: 'paste', file: 'gi-08.paste.txt' }, upload: { service_date: null }, expected_extraction: {},
      expected_context: {}, expected_routing: {}, expected_clarifications: [], incomplete_services: [],
      must_not_code: [{ family: 'gi.ercp', reason: 'documented as planned, not performed' }], review_plan: reviewPlan };
    const item = { doc, sourceText: TEXT, delivery: { format: 'paste', file: doc.delivery.file, sha256: sha(TEXT), size: Buffer.byteLength(TEXT) } };
    const page = reviewPage(id, { ...acceptanceEncounter(), id }, account);
    const record = await vb.verifyDocument(page, { out, baseUrl: 'https://cpt.example', encounter: id, deadlineSeconds: 60,
      noAutoApprove: false, ...opts }, { review_notes: notes }, item, []);
    return { record, acts: page.acts, posts: page.posts, final: page.current() };
  } finally {
    fs.rmSync(out, { recursive: true, force: true });
  }
}

const ACCEPTANCE_PLAN = { reject: { family: 'gi.colonoscopy', prefer_codes: ['45380'] }, approve_codes: ['45331'],
  second_review: { ask: true, approve_codes: ['45380'] } };

test('the acceptance walk approves only the named code, through the screen, as the human reviewer, and records what it did not do', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, async () => {
  const { record, acts, posts, final } = await walkDecisions({ opts: { acceptanceReviewer: true, noAutoApprove: true, account: ACCOUNT },
    notes: { ...ACC_NOTES, reject: AGENT_NOTES.reject }, account: ACCOUNT, reviewPlan: ACCEPTANCE_PLAN });
  assert.equal(record.error, null);
  assert.deepEqual(acts, ['open the approve dialog for p-flex', 'approve 45331', 'reload']);
  assert.deepEqual(posts, [{ proposal_id: 'p-flex', action: 'approve', note: ACC_NOTE, acknowledgement: attestation('human') }]);
  assert.deepEqual(record.decisions.map(d => [d.code, d.action, d.http_status, d.reviewer_kind, d.note]), [['45331', 'approve', 201, 'human', ACC_NOTE]]);
  assert.deepEqual(final.assessment.proposals.map(p => `${p.code}:${p.decision_state}`),
    ['45331:approved', '45380:undecided', '45330:undecided', '45378:undecided', '43260:undecided']);
  const card = record.decision_labels[0].card_insight;
  assert.deepEqual({ ...record.decision_labels[0], card_insight: undefined }, { code: '45331', action: 'approve', decision_id: 'd-p-flex',
    recorded: true, approval: true, human: true, reviewer: 'Demo Reviewer', reviewer_is_account: true, note_kept: true, note_labelled: true,
    acknowledgement: attestation('human'), acknowledgement_is_session_attestation: true, card_badge: 'Approved', card_insight: undefined });
  assert.ok(card.startsWith('Approved by Demo Reviewer') && card.includes(`Note: ${ACC_NOTE}`), card);
  const by = Object.fromEntries(record.assertions.map(a => [a.id, a]));
  for (const id of ['second_review.asked', 'decisions.rejection', 'decisions.confirmations']) assert.equal(by[id]?.status, 'skipped', id);
  assert.match(by['decisions.confirmations'].reason, /left undecided: 43260$/);
  assert.match(by['decisions.not_in_approve_codes'].reason, /--acceptance-reviewer\): 45380$/);
  for (const id of ['persist.decision.45331', 'dom.decision.45331', 'decisions.labelled', 'decisions.never_approved_must_not_code',
    'readiness.reviewed_blocked']) assert.equal(by[id]?.status, 'pass', id);
  assert.equal(record.designated_rejection, null);
  assert.equal(record.second_review, undefined);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => a.id), []);
  assert.equal(record.result, 'pass');
});

test('the agent walk on the same page and plan still approves, rejects the designated code and confirms the exclusion', { skip: !fs.existsSync(APP) && 'studio/static/studio/app.js is not present' }, async () => {
  const { second_review: _asked, ...plan } = ACCEPTANCE_PLAN;  // the scripted page does not answer a second review
  const { record, acts, posts } = await walkDecisions({ notes: AGENT_NOTES, account: AGENT_ACCOUNT, reviewPlan: plan });
  assert.equal(record.error, null);
  assert.deepEqual(acts, ['open the approve dialog for p-flex', 'approve 45331', 'open the reject dialog for p-colo', 'reject 45380',
    'open the confirm dialog for p-plan', 'confirm 43260', 'reload']);
  assert.deepEqual(posts.map(p => [p.action, p.acknowledgement]), [['approve', attestation('agent')], ['reject', ''], ['confirm', '']]);
  assert.equal(record.designated_rejection, '45380');
  assert.deepEqual(record.decision_labels.map(l => [l.code, l.agent, l.note_kept, l.note_labelled, l.acknowledgement_labelled]),
    [['45331', true, true, true, true], ['45380', true, true, true, null], ['43260', true, true, true, null]]);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => a.id), []);
  assert.equal(record.result, 'pass');
  // the same agent walk with the acceptance reviewer's note is refused before anything is uploaded
  assert.match(vb.planProblems({ id: 'acceptance-walk', review_plan: plan }, ACC_NOTES)[0], /must say "agent-executed synthetic"/);
});

test('the acceptance walk answers the clarification the document needs once, records it as a clarification answer, and saves nothing else', async () => {
  const before = questionEncounter();
  const after = answeredEncounter(before);
  const { record, acts, posts } = await walkQuestion([before, after], [{ fact: 'service_date', scope_in: ['encounter'] }],
    { opts: { acceptanceReviewer: true, noAutoApprove: true, account: ACCOUNT }, notes: ACC_NOTES });
  assert.equal(record.error, null);
  assert.deepEqual(acts, ['open the context form', 'fill the service date with "2026-10-08"', 'the form posted', 'reload', 'reload']);
  assert.deepEqual(posts, [ANSWER_EDIT.posted]);
  assert.deepEqual([record.context_edit.clarification_answer, record.context_edit.coding_decision, record.context_edit.http_status,
    record.context_edit.request_date, record.context_edit.identical.via], [true, false, 201, ANSWER, null]);
  assert.match(record.context_edit.identical.skipped, /answers the clarification once/);
  const hard = record.assertions.filter(a => a.id.startsWith('context_edit.') && (a.severity === 'hard' || a.status === 'skipped'));
  assert.deepEqual(hard.map(a => `${a.id}:${a.status}`), QUESTION_HARD.map(id => `${id}:${id === 'context_edit.identical_save' ? 'skipped' : 'pass'}`));
  assert.deepEqual(record.decisions, []);
  assert.deepEqual(record.assertions.filter(a => a.status === 'fail').map(a => a.id), []);
  assert.equal(record.result, 'pass');
  // the agent walk of the same question still makes the same save again and judges it (unchanged)
  const agent = await walkQuestion([before, after, clone(after)], [{ fact: 'service_date', scope_in: ['encounter'] }]);
  assert.equal(agent.record.context_edit.clarification_answer, undefined);
  assert.equal(agent.record.context_edit.identical.via, 'api');
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
  assert.ok(at('const deciding = [...plan.decisions, ...confirmations];') < refusal);
  assert.ok(at("const other = deciding.filter(d => d.action !== 'approve');") < refusal);
  assert.ok(refusal < at('await decide('), 'a decision is made before the approvals-only refusal');
  assert.ok(at('for (const decision of deciding) record.decisions.push(await decide(page, id, decision));') > refusal);
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
