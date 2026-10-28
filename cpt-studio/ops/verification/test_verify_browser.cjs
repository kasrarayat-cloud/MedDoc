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
    service_date: { value: null, origin: 'conflict', member_conflict: true, evidence: [at('Date of procedure: 2026-10-07')],
      note: `A member entered ${member}; the document states ${DOCUMENTED}.` },
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
  const bad = [
    doc({ context_edit: { service_date: DOCUMENTED } }, { service_date: null }),  // nothing for the edit to settle
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
