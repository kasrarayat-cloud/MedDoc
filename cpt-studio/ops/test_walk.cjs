'use strict';
/*
 * Unit tests for ops/walk.cjs's pure helpers: argument parsing, the documents and credentials it reads, the denylist
 * scan (every vector of ops/verification/customer-denylist.json, which ops/scan_customer.py
 * runs too, so the readers cannot drift apart), the JSON contract (ops/verification/customer-contract.json, held to
 * scan_customer.py's reader by ops/test_walk_contract.py) and DOM contract checks, the approval of one line on the round
 * shown, the walk's own judge of a chosen quote (DECISIONS D368 round 3: its own search with the rule's R1 overprint
 * copies, R2 word edges and R3 format characters over synthetic text layers, the notes N1-N4 character for character, a
 * marked page drawn, no mark inside a character) and the evidence's shape - synthetic values only; and the review dialog
 * and every quote of the dev preview's documents driven through the page itself (ops/dev_preview_server.cjs's mock, in
 * Chromium) where Playwright is installed (CPT_VERIFY_PLAYWRIGHT), skipped where it is not.
 *
 * LINE IDENTITY (FIX-SPEC section 1): the tests marked so build rows that carry `line`; the base fixture carries it
 * when customer-contract.json lists it (lane F1a), and the browser test checks the posted line once the page's fixtures
 * serve one (lane F1b).
 *
 * DECISION IDS (FIX-SPEC-2 section 5): a served decision carries its id when customer-contract.json lists one (lane G1),
 * and the tests marked so check that the walk's Undo - and the page's, in the browser - names it; the browser test also
 * checks that the page's download names the round shown.
 *
 *   node ops/test_walk.cjs            (or: node --test --test-reporter=tap ops/test_walk.cjs)
 */
const assert = require('node:assert/strict');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const walk = require('./walk.cjs');

const BASE = 'https://cpt.example.test';
const PASSWORD = 'Synthetic-walk pass&+%<>"\'é/=?-2026';
const REQUIRED = ['--base-url', BASE, '--credentials', 'c.json', '--operator-credentials', 'o.json', '--docs', 'docs',
  '--out', 'out'];
const DENYLIST = JSON.parse(fs.readFileSync(path.join(__dirname, 'verification', 'customer-denylist.json'), 'utf8'));
const CONTRACT = JSON.parse(fs.readFileSync(path.join(__dirname, 'verification', 'customer-contract.json'), 'utf8'));
// LINE IDENTITY: whether the contract on disk lists each code row's `line` (lane F1a adds it, FIX-SPEC section 1)
const LINES = Object.prototype.hasOwnProperty.call(CONTRACT.types.code.keys, 'line');
// and whether it lists each question's `lines`, the lines the question affects (lane F1a, FIX-SPEC section 3)
const QUESTION_LINES = Object.prototype.hasOwnProperty.call(CONTRACT.types.question.keys, 'lines');
// DECISION IDS (FIX-SPEC-2 section 5): whether the contract on disk gives a current decision its id (lane G1 adds it); a
// served decision carries it then, and an Undo names it
const DECISION_IDS = Object.prototype.hasOwnProperty.call(CONTRACT.types.decision.keys, 'id');
// A current decision as the server serves it: with its id when the contract lists one.
function decision(fields, id = 'f6200000-0000-4000-8000-000000000001') {
  return { ...(DECISION_IDS ? { id } : {}), ...fields };
}
const ACK = 'I reviewed this code against the document.';

function scratch() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cpt-walk-test-'));
  test.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function privateFile(dir, name, data, mode = 0o600) {
  const file = path.join(dir, name);
  fs.writeFileSync(file, typeof data === 'string' ? data : JSON.stringify(data), { mode });
  fs.chmodSync(file, mode);
  return file;
}

// One code row as the server serves it; with ``line``, the row carries its line (LINE IDENTITY, FIX-SPEC section 1).
function row(code, status, extra = {}) {
  const labels = { ready: 'Ready for approval', needs_answer: 'Needs your answer', needs_review: 'Needs your review',
    not_supported: 'Not supported' };
  return { code, units: 1, modifiers: [], status, status_label: labels[status], reason: `${code} is documented.`,
    second_check: { agrees: true, reason: 'Agreed.' }, question: null, quotes: [], decision: null,
    allowed_actions: ['ready', 'needs_review'].includes(status) ? ['approve', 'reject'] : [], ...extra };
}

function encounter(overrides = {}) {
  const line = index => (LINES ? { line: `L${index}` } : {});
  const codes = overrides.codes || [
    { ...line(1), code: '43239', units: 1, modifiers: [], status: 'ready', status_label: 'Ready for approval',
      reason: 'EGD with biopsy is documented.', second_check: { agrees: true, reason: 'The report states the biopsy.' },
      question: null, quotes: [{ text: 'Cold forceps biopsies were taken from the antrum.', page: 1 }], decision: null,
      allowed_actions: ['approve', 'reject'] },
    { ...line(2), code: '00731', units: 1, modifiers: ['P2'], status: 'needs_answer', status_label: 'Needs your answer',
      reason: 'Anesthesia time is not stated.', second_check: { agrees: null, reason: '' },
      question: 'How long was the anesthesia?', quotes: [], decision: null, allowed_actions: [] },
  ];
  return {
    id: 'e5c1d3a2-1111-4222-8333-944455556666', title: 'gi-02', created_at: '2026-11-20T10:00:00Z',
    updated_at: '2026-11-20T10:05:00Z', state: 'awaiting_answer', state_label: 'Questions for you',
    permissions: { can_review: true },
    document: { name: 'gi-02.txt', media_type: 'text/plain', size: 10, kind: 'upload',
      original_url: '/api/encounters/e5c1d3a2-1111-4222-8333-944455556666/original',
      view_url: '/api/encounters/e5c1d3a2-1111-4222-8333-944455556666/original?view=1', view_media_type: 'text/plain',
      converted: false },
    context: { service_date: '2026-10-14', insurance: 'medicare' },
    progress: { phase: 'done', busy: false, started_at: null, finished_at: null, server_time: '2026-11-20T10:05:30Z',
      message: '', can_stop: false, can_resume: false, can_retry: true, error: null },
    round: { number: 1, trigger: 'upload', finished_at: '2026-11-20T10:05:00Z' },
    codes,
    questions: [{ id: 'q1', text: 'How long was the anesthesia?', codes: ['00731'],
      ...(QUESTION_LINES ? { lines: ['L2'] } : {}) }],
    answers: [],
    notes: ['The indication is not stated.'], readiness: { draft: true, approved: false, blockers: ['No code is approved.'] },
    reports: [], activity: [],
    ...overrides,
  };
}

// The page as it draws ``enc`` (studio/static/studio/app.js): units "0 units" / "1 unit" / "2 units", or "Units not given";
// modifiers "No modifier" / "Modifier XS" / "Modifiers 25, 59"; each row with its line when served.
function domOf(enc) {
  const units = value => (value === null ? 'Units not given' : `${value} unit${value === 1 ? '' : 's'}`);
  const modifiers = list => (list.length ? `${list.length === 1 ? 'Modifier' : 'Modifiers'} ${list.join(', ')}` : 'No modifier');
  return {
    progress: { phase: enc.progress.phase, steps: ['reading', 'checking', 'finished'].map(step => ({ step, state: 'done' })) },
    questions: enc.questions.length ? { heading: 'Questions for you', send: true,
      rows: enc.questions.map(q => ({ id: q.id, text: `${q.text} Your answer`, textarea: true })) } : null,
    codes: enc.codes.map(code => ({ line: code.line ?? null, code: code.code, status: code.status, number: code.code,
      units: units(code.units), modifiers: modifiers(code.modifiers),
      badge: { status: code.status, text: code.decision ? 'Approved' : code.status_label },
      reason: code.reason, check: `Second check: ${code.second_check.reason}`, quotes: true,
      buttons: code.allowed_actions.map(decision => ({ decision, code: code.code })) })),
    quotesPanel: true,
    quotes: enc.codes.flatMap(code => code.quotes.map(quote => ({ code: code.code, page: quote.page === null ? '' : String(quote.page) }))),
    notes: `Documentation notes ${enc.notes.join(' ')}`,
    viewer: { view: enc.document.view_url, original: enc.document.original_url },
    exportButton: true,
  };
}

function failed(checks) {
  return checks.filter(item => item.status === 'fail').map(item => item.id);
}

// --- arguments ----------------------------------------------------------------------------------------------------------

test('parseArgs reads the options, with their defaults', () => {
  const opts = walk.parseArgs(REQUIRED);
  assert.equal(opts.baseUrl, BASE);
  assert.equal(opts.deadlineSeconds, 1800);
  assert.equal(opts.allowLiveProvider, false);
  assert.equal(opts.insurance, 'commercial');
  assert.equal(opts.serviceDate, null);
  const given = walk.parseArgs([...REQUIRED, '--deadline-seconds=600', '--allow-live-provider', '--service-date', '2026-10-14',
    '--insurance', 'medicare', '--base-url', 'https://cpt.example.test/some/path?x=1']);
  assert.equal(given.deadlineSeconds, 600);
  assert.equal(given.allowLiveProvider, true);
  assert.equal(given.serviceDate, '2026-10-14');
  assert.equal(given.insurance, 'medicare');
  assert.equal(given.baseUrl, BASE);  // the origin alone
  assert.equal(walk.parseArgs([...REQUIRED, '--base-url', 'http://127.0.0.1:8000']).baseUrl, 'http://127.0.0.1:8000');
  assert.equal(walk.parseArgs([...REQUIRED, '--base-url', 'http://localhost:8000']).baseUrl, 'http://localhost:8000');
});

test('parseArgs refuses what it cannot carry out, before anything is read', () => {
  const cases = [
    [[], /missing --base-url/],
    [REQUIRED.slice(0, -2), /missing --out/],
    [[...REQUIRED, '--only', 'x'], /unknown option --only/],
    [[...REQUIRED, 'stray'], /unexpected argument stray/],
    [[...REQUIRED, '--allow-live-provider=no'], /takes no value/],
    [[...REQUIRED, '--deadline-seconds'], /needs a value/],
    [[...REQUIRED, '--deadline-seconds', '59'], /at least 60/],
    [[...REQUIRED, '--deadline-seconds', '90.5'], /at least 60/],
    [[...REQUIRED, '--base-url', 'ftp://x.test'], /must be http\(s\)/],
    [[...REQUIRED, '--base-url', 'not a url'], /not a URL/],
    [[...REQUIRED, '--base-url', 'http://cpt.example.test'], /plain http only on the loopback/],
    [[...REQUIRED, '--base-url', 'https://user:pw@cpt.example.test'], /user name or password/],
    [[...REQUIRED, '--service-date', '2026-02-30'], /calendar date/],
    [[...REQUIRED, '--service-date', '10/14/2026'], /calendar date/],
    [[...REQUIRED, '--insurance', 'private'], /--insurance must be one of medicare, medicaid, commercial, unknown/],
  ];
  for (const [argv, said] of cases) {
    assert.throws(() => walk.parseArgs(argv), error => error instanceof walk.UsageError && said.test(error.message), argv.join(' '));
  }
});

test('main refuses a usage error with exit 2 before any browser is started', async () => {
  const written = [];
  const original = process.stderr.write;
  process.stderr.write = chunk => { written.push(String(chunk)); return true; };
  try {
    assert.equal(await walk.main([]), 2);
  } finally {
    process.stderr.write = original;
  }
  assert.match(written.join(''), /walk: missing --base-url/);
});

// --- documents and credentials ---------------------------------------------------------------------------------------

test('the service date is the document\'s own line, or none', () => {
  assert.equal(walk.serviceDateOf('Patient: x\nDate of service: 2026-10-21\n'), '2026-10-21');
  assert.equal(walk.serviceDateOf('DATE OF PROCEDURE:   2026-10-14'), '2026-10-14');
  assert.equal(walk.serviceDateOf('Scheduled for 2026-11-04.'), null);
  assert.equal(walk.serviceDateOf('Date of service: 2026-13-01'), null);
  assert.equal(walk.serviceDateOf(undefined), null);
});

test('documentsOf reads every document of a directory in name order, each with its date and insurance', () => {
  const dir = scratch();
  fs.writeFileSync(path.join(dir, 'b-note.txt'), 'SYNTHETIC\nDate of service: 2026-10-21\n');
  fs.writeFileSync(path.join(dir, 'a-report.pdf'), '%PDF-1.4 synthetic');
  fs.writeFileSync(path.join(dir, 'notes.md'), 'not a document');
  fs.mkdirSync(path.join(dir, 'nested.txt'));
  assert.throws(() => walk.documentsOf(dir, { serviceDate: null, insurance: 'commercial' }),
    error => error instanceof walk.UsageError && /a-report\.pdf states no "Date of service:" line/.test(error.message));
  const docs = walk.documentsOf(dir, { serviceDate: '2026-10-14', insurance: 'medicaid' });
  assert.deepEqual(docs.map(doc => [doc.name, doc.serviceDate, doc.insurance, doc.mediaType]), [
    ['a-report.pdf', '2026-10-14', 'medicaid', 'application/pdf'], ['b-note.txt', '2026-10-14', 'medicaid', 'text/plain']]);
  const one = walk.documentsOf(path.join(dir, 'b-note.txt'), { serviceDate: null, insurance: 'commercial' });
  assert.deepEqual(one.map(doc => [doc.title, doc.serviceDate, doc.text.includes('SYNTHETIC')]), [['b-note', '2026-10-21', true]]);
  assert.equal(one[0].sha256.length, 64);
  const empty = scratch();
  assert.throws(() => walk.documentsOf(empty, { serviceDate: null, insurance: 'commercial' }), /holds no \.txt, \.pdf or \.docx/);
  assert.throws(() => walk.documentsOf(path.join(dir, 'notes.md'), { serviceDate: '2026-10-14', insurance: 'commercial' }),
    /is not a \.txt, \.pdf or \.docx document/);
});

test('a credentials file is read only when private, and its content is never quoted', () => {
  const dir = scratch();
  const good = privateFile(dir, 'agent.json', { username: 'review-agent', password: PASSWORD });
  assert.deepEqual(walk.loadCredentials(good, 'credentials file'), { username: 'review-agent', password: PASSWORD, mode: '0600' });
  const cases = [
    [privateFile(dir, 'open.json', { username: 'a', password: PASSWORD }, 0o644), /mode 0644: a group or other user may read/],
    [privateFile(dir, 'text.json', `not json ${PASSWORD}`), /is not a JSON object/],
    [privateFile(dir, 'nopw.json', { username: 'a', secret: PASSWORD }), /non-empty top-level "username" and "password"/],
    [privateFile(dir, 'nested.json', { account: { username: 'a', password: PASSWORD } }), /non-empty top-level/],
    [path.join(dir, 'missing.json'), /cannot open the credentials file/],
  ];
  for (const [file, said] of cases) {
    assert.throws(() => walk.loadCredentials(file, 'credentials file'), error => {
      assert.ok(error instanceof walk.UsageError);
      assert.match(error.message, said);
      assert.ok(!error.message.includes(PASSWORD));
      return true;
    });
  }
});

test('the password is withheld in every form it could reach the evidence in, or nothing is written', () => {
  const dir = scratch();
  const forms = walk.secretForms(PASSWORD);
  assert.ok(forms.includes(PASSWORD) && forms.includes(encodeURIComponent(PASSWORD)) && forms.includes(JSON.stringify(PASSWORD).slice(1, -1)));
  const file = path.join(dir, 'evidence.json');
  walk.writeEvidence(file, { schema: walk.EVIDENCE_SCHEMA, run_id: 'r', echoed: `you typed ${PASSWORD}`,
    [`key ${encodeURIComponent(PASSWORD)}`]: 1 }, forms);
  const text = fs.readFileSync(file, 'utf8');
  for (const form of forms) assert.ok(!text.includes(form), form);
  assert.match(text, /\[password withheld\]/);
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  assert.equal(walk.debugMayLog('pw:api'), true);
  assert.equal(walk.debugMayLog('pw:*'), true);
  assert.equal(walk.debugMayLog('*'), true);
  assert.equal(walk.debugMayLog('express:*,-pw:api'), false);
  assert.equal(walk.debugMayLog(''), false);
});

// --- the denylist scan --------------------------------------------------------------------------------------------------

test('the denylist scan finds exactly what every vector of customer-denylist.json says, as its other readers do', () => {
  const list = walk.compileDenylist(DENYLIST);
  assert.ok(DENYLIST.vectors.length > 20);
  for (const vector of DENYLIST.vectors) {
    const ctx = walk.scanContext({}, list);
    const ids = [...new Set(walk.scanText(vector.text, ctx, vector.surface).map(hit => hit.id))].sort();
    assert.deepEqual(ids, [...vector.hits].sort(), `${vector.surface}: ${vector.text}`);
  }
});

test('the walk reads the one denylist file, and names a vendor or a model anywhere in a JSON body', () => {
  assert.equal(walk.denylist().schema, DENYLIST.schema);
  const ctx = walk.scanContext({ allowed: ['cpt.example.test'] });
  const hits = walk.scanJson({ codes: [{ reason: 'The model claude-fable-5-2 read it.', provider: 'x' }],
    link: 'https://cpt.example.test/ops/', note: 'GeminiTimeout' }, ctx, '$');
  const ids = [...new Set(hits.map(hit => hit.id))].sort();
  for (const id of ['forbidden_key', 'interpreter_model', 'model_id', 'operator_url', 'provider_name', 'provider_name_joined']) {
    assert.ok(ids.includes(id), `${id} in ${ids}`);
  }
  assert.ok(hits.some(hit => hit.where === '$.codes[0].provider' && hit.id === 'forbidden_key'));
  // the site's own host is allowed; a clinical word that begins with a name is not a name
  assert.deepEqual(walk.scanText('https://cpt.example.test/ corticosteroid cortical', ctx, 'dom'), []);
});

test('the document\'s own text and its quotes are never scanned, and a quote is set aside inside a longer string', () => {
  const quote = 'Patient Claude Astra (fictional) tolerated the procedure; trace blood was seen.';
  const ctx = walk.scanContext({ documentText: `Header\n${quote.replace('; ', ';\n')}\nEnd` });
  assert.deepEqual(walk.scanText(quote, ctx, 'json'), []);
  assert.deepEqual(walk.scanText('trace blood was seen', ctx, 'dom'), []);
  const pdf = walk.scanContext({});  // a PDF: no text, but the encounter's quotes are the document's
  walk.addQuotes(pdf, { codes: [{ quotes: [{ text: quote, page: 2 }] }] });
  assert.deepEqual(walk.scanText(quote, pdf, 'json'), []);
  assert.deepEqual(walk.scanText(`"${quote}" (page 2)`, pdf, 'dom'), []);
  assert.deepEqual(walk.scanText(`${quote} Read by claude.`, pdf, 'dom').map(hit => hit.id), ['provider_name']);
  assert.deepEqual(walk.scanText('The trace of the reading', pdf, 'dom').map(hit => hit.id), ['trace']);
});

test('a modifier is scanned whole in the JSON, even where a quote holds the same word (SEC-S4)', () => {
  // the re-check's case: modifiers ["Claude"] on a line whose cited passage is "Dr. Claude Example removed the polyp"
  const enc = encounter();
  enc.codes[0].quotes = [{ text: 'Dr. Claude Example removed the polyp.', page: 1 }];
  enc.codes[0].modifiers = ['Claude'];
  const ctx = walk.scanContext({});
  walk.addQuotes(ctx, enc);
  assert.deepEqual(walk.scanJson(enc, ctx).map(hit => [hit.id, hit.where]), [['provider_name', '$.codes[0].modifiers[0]']]);
  // the quote itself stays the document's, and a clean modifier is no hit
  enc.codes[0].modifiers = ['PT'];
  assert.deepEqual(walk.scanJson(enc, ctx), []);
  assert.ok(walk.NEVER_QUOTED.test('$.codes[3].modifiers[12]'));
  assert.ok(!walk.NEVER_QUOTED.test('$.codes[0].quotes[0].text'));
});

test('a download is scanned line by line, its quoted lines set aside', () => {
  const ctx = walk.scanContext({});
  walk.addQuotes(ctx, { codes: [{ quotes: [{ text: 'Trace fluid in the pouch.', page: 1 }] }] });
  const text = 'SYNTHETIC - NOT FOR BILLING\n43239 Ready for approval\n  - "Trace fluid in the pouch." (page 1)\n'
    + 'Reason: read by the model gpt-6\nSYNTHETIC - NOT FOR BILLING\n';
  const hits = walk.scanFile(text, ctx, 'draft.txt');
  assert.deepEqual(hits.map(hit => [hit.id, hit.where]), [['model_id', 'draft.txt line 4']]);
  const checks = walk.checkScan('scan.files', [...hits, { id: 'provider_word', severity: 'soft', where: 'x', match: 'provider' }], 'the downloads');
  assert.deepEqual(checks.map(item => [item.id, item.status]), [['scan.files', 'fail'], ['scan.files.wording', 'warn']]);
  assert.deepEqual(walk.checkScan('scan.dom', [], 'the page').map(item => item.status), ['pass']);
  assert.deepEqual(walk.scanHeaders({ 'content-security-policy': 'claude', 'x-served-by': 'anthropic' }, ctx, 'GET /x')
    .map(hit => hit.where), ['GET /x header x-served-by']);
});

// --- the JSON and DOM contracts -----------------------------------------------------------------------------------------

test('the encounter JSON is held to the contract: its keys, statuses, actions and context', () => {
  const doc = { serviceDate: '2026-10-14', insurance: 'medicare' };
  assert.deepEqual(failed(walk.jsonChecks(encounter(), doc)), []);
  assert.deepEqual(walk.expectedActions({ status: 'ready', decision: null }), ['approve', 'reject']);
  assert.deepEqual(walk.expectedActions({ status: 'needs_review' }), ['approve', 'reject']);
  assert.deepEqual(walk.expectedActions({ status: 'needs_answer' }), []);
  assert.deepEqual(walk.expectedActions({ status: 'not_supported' }), []);
  assert.deepEqual(walk.expectedActions({ status: 'ready', decision: { action: 'approve' } }), ['revoke']);
  const offered = encounter();
  offered.codes[1].allowed_actions = ['approve'];  // a code that needs an answer offers no approval
  assert.deepEqual(failed(walk.jsonChecks(offered, doc)), ['json.codes.actions']);
  const { activity, ...missing } = encounter();
  assert.ok(Array.isArray(activity));
  assert.deepEqual(failed(walk.jsonChecks(missing, doc)), ['json.contract', 'json.keys']);
  assert.deepEqual(failed(walk.jsonChecks(encounter(), { serviceDate: '2026-10-15', insurance: 'medicare' })), ['json.context']);
  const unknown = encounter();
  unknown.codes[0].status = 'held';
  unknown.codes[0].allowed_actions = [];
  assert.deepEqual(failed(walk.jsonChecks(unknown, doc)), ['json.contract', 'json.codes.status']);
});

test('the page is held to the JSON it was served, part by part', () => {
  const enc = encounter();
  assert.deepEqual(failed(walk.domChecks(enc, domOf(enc), BASE)), []);
  const mutations = {
    'dom.progress.phase': dom => { dom.progress.phase = 'checking'; },
    'dom.progress.steps': dom => { dom.progress.steps.pop(); },
    'dom.codes.rows': dom => { dom.codes.reverse(); },
    'dom.codes.cells': dom => { dom.codes[1].modifiers = ''; },
    'dom.codes.badges': dom => { dom.codes[0].badge = { status: 'ready', text: 'Needs your review' }; },
    'dom.codes.actions': dom => { dom.codes[1].buttons.push({ decision: 'approve', code: '00731' }); },
    'dom.quotes': dom => { dom.quotes[0].page = '2'; },
    'dom.questions': dom => { dom.questions.rows[0].textarea = false; },
    'dom.notes': dom => { dom.notes = 'Documentation notes'; },
    'dom.viewer': dom => { dom.viewer.view = '/api/encounters/another/original?view=1'; },
    'dom.export': dom => { dom.exportButton = false; },
  };
  for (const [id, mutate] of Object.entries(mutations)) {
    const dom = domOf(enc);
    mutate(dom);
    assert.deepEqual(failed(walk.domChecks(enc, dom, BASE)), [id], id);
  }
  // a decided code's badge states the decision, and the row offers only the undo
  const decided = encounter();
  decided.codes[0] = { ...decided.codes[0], decision: { action: 'approve', by: 'Review agent', at: 'x', note: '' }, allowed_actions: ['revoke'] };
  const dom = domOf(decided);
  assert.deepEqual(failed(walk.domChecks(decided, dom, BASE)), []);
  dom.codes[0].badge.text = 'Ready for approval';
  assert.deepEqual(failed(walk.domChecks(decided, dom, BASE)), ['dom.codes.badges']);
  // no question: no question row may be shown
  const quiet = encounter({ questions: [] });
  const quietDom = domOf(quiet);
  assert.deepEqual(failed(walk.domChecks(quiet, quietDom, BASE)), []);
  quietDom.questions = { heading: 'Questions for you', send: true, rows: [{ id: 'q9', text: 'x', textarea: true }] };
  assert.deepEqual(failed(walk.domChecks(quiet, quietDom, BASE)), ['dom.questions']);
});

test('the viewer is read by the view address it keeps, whether the page draws the PDF or frames it', () => {
  const enc = encounter();
  const dom = domOf(enc);
  dom.viewer.view = `${enc.document.view_url}#page=2`;  // the browser's own viewer, framed where the page cannot draw
  assert.deepEqual(failed(walk.domChecks(enc, dom, BASE)), []);
  dom.viewer.view = null;
  assert.deepEqual(failed(walk.domChecks(enc, dom, BASE)), ['dom.viewer']);
});

// --- the walk's own judge of a chosen quote (DECISIONS D368, round 3) ------------------------------------------------
// Synthetic text layers, as readPdfPage reads them: a string is an item's span, '\n' a <br> (an item the PDF library
// marks hasEOL), an object an item with its own fields (text, copy: the viewer's overprint flag, box: [left, top, height]).
function layer(...parts) {
  return parts.map(part => (part === '\n' ? { kind: 'br' } : { kind: 'item', ...(typeof part === 'string' ? { text: part } : part) }));
}

// A page's canvas as readPdfPage measures a drawn one, and a page drawn with that canvas and these marks.
const DRAWN = { present: true, visible: true, pixels: 1000, opaque: 1, markPixels: 100, markContent: 40 };
function drawn(number, tokens, marks = [], canvas = DRAWN) {
  return { number, drawn: true, tokens, marks, canvas };
}

// The marks of `words` (each [item, its text, occurrence], the n-th time that text is in that item counting from 0 as
// a fourth element) in a page's tokens, as readPdfPage gives them: the item and the offsets in its string.
function marked(tokens, ...words) {
  const items = tokens.filter(token => token.kind === 'item');
  return words.map(([item, text, occurrence, nth = 0]) => {
    let start = -1;
    for (let k = 0; k <= nth; k += 1) start = items[item].text.indexOf(text, start + 1);
    assert.ok(start >= 0, `${text} in item ${item}`);
    return { item, occurrence, start, end: start + text.length };
  });
}

// What the viewer showed for one chosen quote in a drawn PDF (chooseQuotes' reading): its state and the pages read.
function pdfReading(pages, fields = {}) {
  return { mode: 'pdf', fallback: '', marked: 'L1#0', status: 'marked', pages: [1], count: 1, note: 'Marked on page 1.',
    pageCount: pages.length, drawn: pages.map(item => item.number), pagesRead: new Map(pages.map(item => [item.number, item])), ...fields };
}

// The walk's own search over synthetic pages (each a list of tokens): its result and the note it requires.
function search(quote, ...pages) {
  const models = new Map(pages.map((tokens, index) => [index + 1, walk.pageModel(index + 1, tokens)]));
  const result = walk.ownSearch(quote, models, pages.length);
  return { ...result, note: walk.pdfQuoteNote(result) };
}

test('the walk\'s own search: white space and NFKC ignored, exact case first, every occurrence, the quote\'s page and the next, never another', () => {
  const page1 = layer('Patchy erythema was seen in the gastric antrum.', '\n', 'Cold forceps biopsies were taken from the gastric antrum.', '\n');
  const page2 = layer('Colonoscopy: The colonoscope was advanced to the cecum.', '\n', 'Impression: antral erythema.');
  const one = search({ text: 'Cold  forceps\nbiopsies were taken', page: 1 }, page1, page2);
  assert.deepEqual([one.status, one.scope, one.caseBlind, one.count, one.pages, one.note], ['marked', 'page', false, 1, [1], 'Marked on page 1.']);
  assert.equal(search({ text: 'Coldforcepsbiopsies', page: 1 }, page1, page2).count, 1, 'white space ignored entirely');
  assert.equal(search({ text: 'ﬁ', page: 1 }, layer('the fi glyph')).count, 1, 'NFKC on both sides');
  const twice = search({ text: 'the gastric antrum.', page: 1 }, page1, page2);
  assert.deepEqual([twice.count, twice.note], [2, 'These words appear 2 times on page 1. Each is marked.']);
  const blind = search({ text: 'PATCHY ERYTHEMA WAS SEEN', page: 1 }, page1, page2);
  assert.deepEqual([blind.status, blind.caseBlind, blind.count], ['marked', true, 1]);
  // case-blind only where there is no exact-case occurrence: the capitals are not counted beside an exact one
  assert.deepEqual([search({ text: 'cold snare', page: 1 }, layer('cold snare and COLD SNARE')).count,
    search({ text: 'cold snare', page: 1 }, layer('cold snare and COLD SNARE')).caseBlind], [1, false]);
  const run = search({ text: 'taken from the gastric antrum. Colonoscopy: The colonoscope was advanced', page: 1 }, page1, page2);
  assert.deepEqual([run.scope, run.count, run.pages, run.note], ['continued', 1, [1, 2], 'Marked on page 1, continuing onto page 2.']);
  const elsewhere = search({ text: 'Impression: antral erythema.', page: 1 }, page1, page2);
  assert.deepEqual([elsewhere.status, elsewhere.pages, elsewhere.note], ['not_found', [],
    'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.'], 'never another page');
  const anywhere = search({ text: 'antral erythema', page: null }, page1, page2);
  assert.deepEqual([anywhere.scope, anywhere.pages, anywhere.note], ['document', [2], 'Marked on page 2.']);
  assert.equal(search({ text: 'erythema', page: null }, page1, page2).note, 'These words appear 2 times, on pages 1 and 2. Each is marked.');
  assert.deepEqual([search({ text: 'x', page: 3 }, page1, page2).status, search({ text: 'x', page: 3 }, page1, page2).note],
    ['missing_page', 'This passage names page 3, but the document has 2 pages. Nothing is marked.']);
  assert.equal(search({ text: '  \u200b ', page: 1 }, page1).note, 'This passage has no words to mark.');
  assert.equal(search({ text: 'x', page: 1 }, page1, page2).status, 'not_found');
});

test('R1: an overprint copy the viewer flags, where its geometry bears the flag out, is left out of the text and counts once', () => {
  // fake bold: the same line drawn twice 0.3 pt apart; the second copy flagged by the viewer
  const bold = layer({ text: 'DIAGNOSIS: TUBULAR ADENOMA.', box: [46.56, 76.2, 10] }, { text: 'DIAGNOSIS: TUBULAR ADENOMA.', copy: true, box: [46.88, 76.2, 10] }, '\n',
    'The procedure was uneventful.', { text: 'Impression:', box: [46.6, 90, 10] }, { text: 'Impression:', copy: true, box: [46.9, 90, 10] }, ' ', 'two polyps were removed.');
  assert.equal(walk.unbornFlags(bold), 0);
  assert.deepEqual([search({ text: 'DIAGNOSIS: TUBULAR ADENOMA.', page: 1 }, bold).count, search({ text: 'DIAGNOSIS: TUBULAR ADENOMA.', page: 1 }, bold).note],
    [1, 'Marked on page 1.']);
  assert.equal(search({ text: 'The procedure was uneventful. Impression: two polyps were removed.', page: 1 }, bold).count, 1, 'a passage across the copy');
  // a flag the geometry does not bear out: other text, too far, or no span among the 8 before it
  const lie = (copy, before = [{ text: 'Impression:', box: [46.6, 90, 10] }]) => walk.unbornFlags(layer(...before, { copy: true, ...copy }));
  assert.equal(lie({ text: 'Impression:', box: [46.9, 90, 10] }), 0);
  assert.equal(lie({ text: 'Impressions', box: [46.9, 90, 10] }), 1, 'other text');
  assert.equal(lie({ text: 'Impression:', box: [49, 90, 10] }), 1, 'more than max(1.5, 0.2 x height) away');
  assert.equal(lie({ text: 'Impression:', box: [47.9, 90, 5] }), 0, 'within 1.5 px');
  assert.equal(lie({ text: 'Impression:', box: [48.4, 90, 10] }), 0, 'beyond 1.5 px, within 0.2 x its height (2 px)');
  assert.equal(lie({ text: 'Impression:', box: [48.4, 90, 5] }), 1, 'beyond 1.5 px for a 5 px span');
  assert.equal(lie({ text: '   ', box: [46.6, 90, 10] }, [{ text: '   ', box: [46.6, 90, 10] }]), 1, 'white space only is never a copy');
  assert.equal(lie({ text: 'Impression:', box: [46.6, 90, 10] }, [{ text: 'Impression:', box: [46.6, 90, 10] }, ...Array(8).fill({ text: 'x', box: [0, 0, 10] })]), 1,
    'not among the 8 spans before it');
  assert.equal(lie({ text: 'Impression:' }), 1, 'a flagged span with no box');
  // in the judge: a flag not borne out fails the quote, whatever the viewer marked
  const page = layer('Bowel preparation was rated adequate.', { text: 'A 4 mm polyp was removed.', copy: true, box: [10, 10, 10] });
  const judged = walk.judgeQuote({ code: '45380', line: 'L1', text: 'Bowel preparation was rated adequate.', page: 1 },
    pdfReading([drawn(1, page, marked(page, [0, 'Bowel preparation was rated adequate.', 0]))]));
  assert.deepEqual([judged.outcome, judged.flags], ['unresolved', 1]);
  assert.match(judged.problems.join(), /1 span\(s\) flagged as an overprint copy are not one/);
});

test('R2: an occurrence is accepted only between word edges, read in the page\'s joined text', () => {
  const page = layer('The patient was told to bathe ending the preparation at noon.', '\n', 'Findings: the end of the procedure was uneventful.', '\n',
    'Mild pain was reported; the abdomen was painless on palpation.', '\n', 'A 5 mm polyp was found; polypectomy was performed; no other polyps.');
  assert.equal(search({ text: 'the end', page: 1 }, page).count, 1, 'not inside "bathe ending"');
  assert.equal(search({ text: 'pain', page: 1 }, page).count, 1, 'not inside "painless"');
  assert.equal(search({ text: 'polyp', page: 1 }, page).count, 1, 'not inside "polypectomy" or "polyps"');
  assert.equal(search({ text: 'not able', page: 1 }, layer('It was notable.')).count, 1, 'white space inside the quote stays ignored: only its ends are edges');
  assert.equal(search({ text: '5 mm', page: 1 }, layer('A 15 mm polyp; a 5 mm polyp.')).count, 1, 'a digit is not an edge');
  assert.equal(search({ text: '.', page: 1 }, layer('a. b.')).count, 2, 'a quote that starts and ends with punctuation asks for no edge');
  // the start and the end of the page are edges; a line break of an item the library marks hasEOL is one, a copy's too
  assert.equal(search({ text: 'polyp', page: 1 }, layer('polyp')).count, 1);
  assert.equal(search({ text: 'removed', page: 1 }, layer('one polyp', '\n', 'removed today')).count, 1);
  assert.equal(search({ text: 'removed', page: 1 }, layer('one polyp', 'removed today')).status, 'not_found', 'no break, no space: one word');
  const bold = layer({ text: 'polyp', box: [10, 10, 10] }, { text: 'polyp', copy: true, box: [10.3, 10, 10] }, '\n', 'removed');
  assert.deepEqual([search({ text: 'polyp', page: 1 }, bold).count, search({ text: 'removed', page: 1 }, bold).count], [1, 1],
    'the copy\'s line break stays when its string is left out');
  // a letter, a digit or a combining mark just before is no edge (an accent drawn after its letter)
  assert.equal(search({ text: 'clair', page: 1 }, layer('e\u0301clair')).status, 'not_found');
  // the characters before and after are read as the page writes them, not after NFKC, as the viewer reads them
  assert.equal(search({ text: 'Botox', page: 1 }, layer('Botox\u2122 was given.')).count, 1, 'a trade mark sign after it is an edge, though NFKC writes it "TM"');
  assert.equal(search({ text: '5', page: 1 }, layer('5\u338f dose')).count, 1, 'a unit sign after it is an edge, though NFKC writes it "kg"');
  assert.equal(search({ text: 'polyp', page: 1 }, layer('\u2474polyp')).status, 'not_found', 'a parenthesised digit before it is a digit, though NFKC writes it "(1)"');
  // the continuation's edges are read across the two pages' text
  assert.equal(search({ text: 'gastric antrum. Colonoscopy', page: 1 }, layer('the gastric antrum.'), layer('Colonoscopy: advanced.')).scope, 'continued');
  assert.equal(search({ text: 'antrum. Colon', page: 1 }, layer('the gastric antrum.'), layer('Colonoscopy: advanced.')).status, 'not_found');
  // case-blind keeps the edges too
  assert.equal(search({ text: 'THE END', page: 1 }, layer('bathe ending; the end.')).count, 1);
});

test('R3: format characters are dropped from both sides before matching', () => {
  const page = layer('alphabeta was seen', '\n', 'soft-hyphen');
  for (const mark of ['\u00ad', '\u200b', '\u200c', '\u200d', '\u2060', '\u200e', '\ufeff']) {
    assert.equal(search({ text: `alpha${mark}beta`, page: 1 }, page).count, 1, `U+${mark.codePointAt(0).toString(16)}`);
  }
  assert.equal(search({ text: 'alphabeta', page: 1 }, layer('alpha\u00adbeta')).count, 1, 'a format character on the page side too');
  assert.equal(search({ text: '\u00ad', page: 1 }, page).status, 'empty');
});

test('the notes when nothing is found: N1 where the page has searchable text, N2 where it has none, character for character', () => {
  const text = layer('Bowel preparation was rated adequate.');
  assert.equal(search({ text: 'absent words', page: 1 }, text).note,
    'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.');
  assert.equal(search({ text: 'absent words', page: null }, text).note,
    'The exact words were not found in the searchable text of this document, so nothing is marked.');
  // no searchable character: an empty layer, white space only, or only a flagged copy's text left out (whatever the next page holds)
  for (const page of [layer(), layer(' ', '\n', ' ')]) {
    assert.equal(search({ text: 'absent words', page: 1 }, page, text).note,
      'Page 1 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 1 is shown.');
  }
  assert.equal(search({ text: 'absent words', page: null }, layer(), layer(' ')).note,
    'This document has no text the viewer can search (it may be a scanned image), so nothing is marked.');
  assert.equal(search({ text: 'absent words', page: null }, layer(), text).note,
    'The exact words were not found in the searchable text of this document, so nothing is marked.');
});

test('a chosen quote is judged by the walk\'s own search: the viewer\'s marks, count, pages and note are held to it, never taken at its word', () => {
  const page = layer('Patchy erythema was seen in the gastric antrum.', '\n', 'Cold forceps biopsies were taken from the gastric antrum.',
    '\n', 'COLD FORCEPS BIOPSIES WERE TAKEN.');
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken', page: 1 };
  const right = marked(page, [1, 'Cold forceps biopsies were taken', 0]);
  const judge = (marks, fields = {}, pages = [drawn(1, page, marks)]) => walk.judgeQuote(quote, pdfReading(pages, fields));
  assert.deepEqual(judge(right), { outcome: 'once', off_page: 0, mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0, no_text: false, problems: [] });
  // the marked text split across items is one occurrence; its parts are read together
  const split = layer('Cold forceps bio', 'psies were taken from the antrum.');
  assert.equal(walk.judgeQuote(quote, pdfReading([drawn(1, split, marked(split, [0, 'Cold forceps bio', 0], [1, 'psies were taken', 0]))])).outcome, 'once');
  // "not found" passes only where the walk finds nothing either (FM-4 M1, RCW-2 a)
  const silent = judge([], { status: 'not_found', pages: [], count: 0, note: 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.' });
  assert.deepEqual([silent.outcome, silent.missed], ['unresolved', 1]);
  assert.match(silent.problems.join(), /the viewer says not_found, the walk's own search finds 1/);
  // the case: the capitals marked where an exact-case occurrence exists (FM-4 M2, RCW-2 c)
  const capitals = judge([...right, ...marked(page, [2, 'COLD FORCEPS BIOPSIES WERE TAKEN', 1])], { count: 2, note: 'These words appear 2 times on page 1. Each is marked.' });
  assert.deepEqual([capitals.outcome, capitals.mismatched, capitals.missed], ['unresolved', 1, 0]);
  assert.equal(judge(marked(page, [2, 'COLD FORCEPS BIOPSIES WERE TAKEN', 0])).mismatched, 1, 'the capitals instead of the exact words');
  // the count: one of two occurrences marked (FM-4 M3, RCW-2 b)
  const twiceQuote = { ...quote, text: 'the gastric antrum.' };
  const both = marked(page, [0, 'the gastric antrum.', 0], [1, 'the gastric antrum.', 1]);
  assert.equal(walk.judgeQuote(twiceQuote, pdfReading([drawn(1, page, both)], { count: 2, note: 'These words appear 2 times on page 1. Each is marked.' })).outcome, 'multi');
  const first = walk.judgeQuote(twiceQuote, pdfReading([drawn(1, page, both.slice(0, 1))]));
  assert.deepEqual([first.outcome, first.missed], ['unresolved', 1]);
  assert.match(first.problems.join(), /the viewer counts 1, the walk's own search 2/);
  // other words, part of the words, more than the words, another place
  assert.equal(judge(marked(page, [1, 'Cold forceps biopsies were', 0])).mismatched, 1);
  assert.equal(judge(marked(page, [1, 'Cold forceps biopsies were taken from', 0])).mismatched, 1);
  // the pages: a mark on another page, and pages the viewer names that its own search does not
  const page2 = layer('Cold forceps biopsies were taken twice.');
  const off = judge([], { pages: [1, 3] }, [drawn(1, page, right), drawn(2, page2, marked(page2, [0, 'Cold forceps biopsies were taken', 1])), drawn(3, layer('x'))]);
  assert.equal(off.off_page, 2, 'the mark on page 2 starts no occurrence on page 1; page 3 is claimed');
  // the note, exactly: an N2 note where the page has searchable text, and N1 where it has none
  assert.match(judge(right, { note: 'Marked.' }).problems.join(), /the note does not say what was done, as written/);
  const absent = { ...quote, text: 'absent words' };
  const n2 = 'Page 1 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 1 is shown.';
  const n1 = 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.';
  assert.equal(walk.judgeQuote(absent, pdfReading([drawn(1, page)], { status: 'not_found', pages: [], count: 0, note: n1 })).outcome, 'not_found');
  assert.equal(walk.judgeQuote(absent, pdfReading([drawn(1, page)], { status: 'not_found', pages: [], count: 0, note: n2 })).outcome, 'unresolved');
  const scanned = walk.judgeQuote(absent, pdfReading([drawn(1, layer())], { status: 'not_found', pages: [], count: 0, note: n2 }));
  assert.deepEqual([scanned.outcome, scanned.no_text], ['not_found', true]);
  assert.equal(walk.judgeQuote(absent, pdfReading([drawn(1, layer())], { status: 'not_found', pages: [], count: 0, note: n1 })).outcome, 'unresolved');
  // a page it must search that it could not read leaves the quote unresolved, and the viewer's marks in a copy are refused
  const unread = walk.judgeQuote(quote, pdfReading([drawn(1, page, right), { number: 2, drawn: false }]));
  assert.match(unread.problems.join(), /page\(s\) 2 could not be read/);
  const bold = layer({ text: 'Cold forceps biopsies were taken', box: [10, 10, 10] }, { text: 'Cold forceps biopsies were taken', copy: true, box: [10.3, 10, 10] });
  const inCopy = walk.judgeQuote(quote, pdfReading([drawn(1, bold, marked(bold, [0, 'Cold forceps biopsies were taken', 0], [1, 'Cold forceps biopsies were taken', 0]))]));
  assert.match(inCopy.problems.join(), /an overprint copy is marked/);
  // the reason names quotes by their line and page, never by their words
  assert.ok(!silent.problems.join().includes(quote.text));
});

test('S5: every run of an occurrence\'s marked text is read at both ends, so a cut inside a character is seen', () => {
  const quote = { code: '43239', line: 'L1', text: 'Jose Garcia', page: 1 };
  // RCW-3: the accent is an item of its own and left unmarked between two marked parts of one occurrence
  const page = layer('The patient ', 'Jose', '\u0301', ' ', 'Garcia', ' was seen.');
  const cut = walk.judgeQuote(quote, pdfReading([drawn(1, page, marked(page, [1, 'Jose', 0], [4, 'Garcia', 0]))]));
  assert.equal(cut.cut, 1);
  assert.match(cut.problems.join(), /1 marked part\(s\) begin or end inside a character/);
  // the accent marked with its letter, in two items, is whole; so is a syllable written as jamo marked whole
  const accent = { ...quote, text: 'Jose\u0301 Garcia' };
  const whole = walk.judgeQuote(accent, pdfReading([drawn(1, page, marked(page, [1, 'Jose', 0], [2, '\u0301', 0], [4, 'Garcia', 0]))]));
  assert.deepEqual([whole.outcome, whole.cut], ['once', 0]);
  const jamo = layer('\u1100\u1161', '\u11ab', ' and more');
  assert.equal(walk.judgeQuote({ ...quote, text: '\u1100\u1161\u11ab' }, pdfReading([drawn(1, jamo, marked(jamo, [0, '\u1100\u1161', 0]))])).cut, 1);
  assert.equal(walk.judgeQuote({ ...quote, text: '\u1100\u1161\u11ab' }, pdfReading([drawn(1, jamo, marked(jamo, [0, '\u1100\u1161', 0], [1, '\u11ab', 0]))])).cut, 0);
});

test('S3: a marked page must be drawn, its marked words drawn under the marks; a page shown for a quote not found must be painted', () => {
  const page = layer('Cold forceps biopsies were taken.');
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const marks = marked(page, [0, 'Cold forceps biopsies were taken.', 0]);
  const with_ = canvas => walk.judgeQuote(quote, pdfReading([drawn(1, page, marks, canvas)]));
  assert.equal(with_(DRAWN).outcome, 'once');
  // the no-drawing mutant (a canvas never drawn reads transparent), a hidden canvas, none at all, nothing under the marks
  for (const [canvas, said] of [[{ ...DRAWN, opaque: 0, markContent: 0 }, /its canvas is not drawn/], [{ ...DRAWN, visible: false }, /its canvas is not shown/],
    [{ present: false }, /it has no canvas/], [{ ...DRAWN, markContent: 4 }, /nothing is drawn under its marks/], [{ ...DRAWN, error: 'SecurityError' }, /could not be read/]]) {
    const judged = with_(canvas);
    assert.deepEqual([judged.outcome, judged.blank], ['unresolved', 1], said.source);
    assert.match(judged.problems.join(), said);
  }
  assert.equal(walk.canvasProblem({ ...DRAWN, markContent: 5 }, true), '', `${walk.CANVAS_MARK_CONTENT_MIN} of the pixels under the marks`);
  // a quote not found: its page shown painted, nothing under any mark asked for (a blank page with no text)
  const n2 = 'Page 1 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 1 is shown.';
  const blankPaper = { ...DRAWN, markPixels: 0, markContent: 0 };
  assert.equal(walk.judgeQuote(quote, pdfReading([drawn(1, layer(), [], blankPaper)], { status: 'not_found', pages: [], count: 0, note: n2 })).outcome, 'not_found');
  assert.equal(walk.judgeQuote(quote, pdfReading([drawn(1, layer(), [], { ...blankPaper, opaque: 0 })], { status: 'not_found', pages: [], count: 0, note: n2 })).blank, 1);
});

test('the browser\'s own viewer: unavailable, the note as N3 and N4 write it, and a frame that really opens the quote\'s page', () => {
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 2 };
  const frame = (fields, frameFields = {}) => walk.judgeQuote(quote, { mode: 'frame', fallback: 'library', status: '', pages: [], count: 0,
    note: 'The marking tool did not work here, so nothing is marked. The quote is on page 2.', frame: { page: 2, previousPage: 1, replaced: true, ...frameFields }, ...fields });
  const plain = frame({});
  assert.deepEqual([plain.outcome, plain.problems.length], ['unavailable', 1]);
  assert.match(plain.problems[0], /browser's own viewer \(the marking tool did not work in the page\)/);
  for (const [reason, sentence] of Object.entries(walk.FRAME_REASONS)) {
    assert.equal(frame({ fallback: reason, note: `${sentence} The quote is on page 2.` }).problems.length, 1, reason);
  }
  assert.deepEqual(Object.keys(walk.FRAME_REASONS).sort(), ['browser', 'document', 'library', 'slow']);
  // the note never says what the frame shows; without a page it is the reason alone
  assert.match(frame({ note: 'The marking tool did not work here, so nothing is marked. Page 2 is shown.' }).problems.join(), /does not say why marking is unavailable, as written/);
  assert.equal(walk.judgeQuote({ ...quote, page: null }, { mode: 'frame', fallback: 'slow', note: 'The document took too long to load here, so nothing is marked.', frame: {} }).problems.length, 1);
  // N3: a new frame for a new page (the old element only re-addressed does not move the browser's viewer); none for the same page
  assert.match(frame({}, { replaced: false }).problems.join(), /keeps the element that showed page 1/);
  assert.match(frame({}, { previousPage: 2, replaced: true }).problems.join(), /opened again for page 2/);
  assert.equal(frame({}, { previousPage: 2, replaced: false }).problems.length, 1);
  assert.match(frame({}, { page: 1 }).problems.join(), /does not open page 2/);
  assert.match(frame({ fallback: 'toString' }).problems.join(), /\(no reason given\)/);
});

test('a text document keeps its own rule (findPassages), judged by the walk\'s own copy of it', () => {
  const source = 'Colonoscopy note (fictional)\nA 12 mm pedunculated polyp in the descending colon was removed.\nA 3 mm polyp in the rectum.';
  const quote = { code: '45385', line: 'L1', text: 'A 12 mm pedunculated polyp in the\ndescending colon', page: null };
  const at = source.indexOf('A 12 mm');
  const end = source.indexOf(' was removed');
  const text = (marks, fields = {}) => walk.judgeQuote(quote, { mode: 'text', status: 'marked', count: 1, note: 'Marked in the document.', pages: [],
    text: { source, marks }, ...fields });
  assert.equal(text([[at, end]]).outcome, 'once');
  assert.equal(text([[at, end - 1]]).mismatched, 1);
  assert.equal(text([], { status: 'not_found', count: 0, note: 'The exact words could not be found in the document, so nothing is marked.' }).missed, 1);
  assert.equal(walk.judgeQuote({ ...quote, text: 'not in it' }, { mode: 'text', status: 'not_found', count: 0, pages: [],
    note: 'The exact words could not be found in the document, so nothing is marked.', text: { source, marks: [] } }).outcome, 'not_found');
  assert.deepEqual(walk.findPassagesText('COLD FORCEPS', 'cold  forceps'), [[0, 12]]);
});

test('every quote chosen is counted, and the check fails on anything the walk\'s own judgement refuses', () => {
  const page = layer('Cold forceps biopsies were taken.', '\n', 'Bowel preparation was rated adequate.');
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const good = { quote, reading: pdfReading([drawn(1, page, marked(page, [0, quote.text, 0]))]) };
  const absent = { quote: { ...quote, text: 'absent words' }, reading: pdfReading([drawn(1, page)], { status: 'not_found', pages: [], count: 0,
    note: 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.' }) };
  const made = walk.quoteMarkChecks([good, good, absent]);
  assert.equal(made.status, 'pass', made.reason);
  assert.deepEqual(made.data, { quotes: 3, marked_once: 2, marked_multi: 0, not_found: 1, no_text: 0, unavailable: 0, unresolved: 0, off_page: 0,
    mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0 });
  assert.equal(made.reason, '3 quote(s) chosen: 2 marked once, 0 marked more than once, 1 not found (the walk\'s own search agrees; 0 on a page with no '
    + 'searchable text), 0 mark(s) off the quote\'s page, 0 marked other than the walk\'s own, 0 found by the walk and not marked, 0 beginning or '
    + 'ending inside a character, 0 marked page(s) not drawn, 0 overprint flag(s) not borne out');
  const lying = walk.quoteMarkChecks([good, { quote, reading: pdfReading([drawn(1, page)], { status: 'not_found', pages: [], count: 0,
    note: 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.' }) }]);
  assert.deepEqual([lying.status, lying.data.missed, lying.data.unresolved], ['fail', 1, 1]);
  assert.equal(walk.quoteMarkChecks([{ quote, reading: { mode: 'frame', fallback: 'browser', note: '', frame: {} } }]).status, 'fail', 'no marking at all is a failure');
  assert.equal(walk.quoteMarkChecks([]).status, 'fail');
  assert.ok(!lying.reason.includes(quote.text), 'the reason names quotes by their line and page, never by their words');
  assert.deepEqual(walk.servedQuotes(encounter()).map(item => [item.code, item.page]), [['43239', 1]]);
  assert.equal(walk.foldMarked(' The ﬁnding\nwas  made. '), 'Thefindingwasmade.');
  // pages read: every page of a short document; a long one on its searched, claimed and drawn pages
  assert.deepEqual(walk.pagesToRead({ page: 2 }, { pageCount: 3, pages: [], drawn: [] }), [1, 2, 3]);
  assert.deepEqual(walk.pagesToRead({ page: 20 }, { pageCount: 40, pages: [20, 21], drawn: [19, 20, 21] }), [19, 20, 21]);
  assert.deepEqual(walk.pagesToRead({ page: null }, { pageCount: 40, pages: [], drawn: [] }).length, 40);
});

test('a PDF viewer that marks not one quote fails the check, though a quote not found alone is allowed', () => {
  // the walk's own documents quote their own words: a viewer that marks nothing fails even where the walk agrees
  const page = layer('Cold forceps biopsies were taken.');
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const good = { quote, reading: pdfReading([drawn(1, page, marked(page, [0, quote.text, 0]))]) };
  const missing = { quote: { ...quote, text: 'absent words' }, reading: pdfReading([drawn(1, page)], { status: 'not_found', pages: [], count: 0,
    note: 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.' }) };
  const none = walk.quoteMarkChecks([missing, missing, missing]);
  assert.equal(none.status, 'fail');
  assert.equal(none.data.not_found, 3);
  assert.match(none.reason, /; 3 quote\(s\) chosen in the PDF viewer and not one marked$/);
  assert.equal(walk.quoteMarkChecks([missing]).status, 'fail', 'one quote, not found: nothing was marked');
  assert.equal(walk.quoteMarkChecks([missing, good, missing]).status, 'pass');
  // the text viewer and the frame are not the PDF viewer
  const textMissing = { quote: { ...quote, text: 'absent words' }, reading: { mode: 'text', status: 'not_found', count: 0, pages: [],
    note: 'The exact words could not be found in the document, so nothing is marked.', text: { source: 'x', marks: [] } } };
  assert.equal(walk.quoteMarkChecks([textMissing]).status, 'pass');
  const framed = walk.quoteMarkChecks([{ quote, reading: { mode: 'frame', fallback: 'browser', note: '', frame: {} } }]);
  assert.equal(framed.status, 'fail');
  assert.doesNotMatch(framed.reason, /not one marked/);
});

test('the encounter JSON is held to customer-contract.json: every key it lists, of its type, and no other, at every depth', () => {
  // FG-E: the walk reads the contract file itself (as ops/scan_customer.py and the Django suite do), not a key list of its own
  assert.equal(walk.contract().schema, CONTRACT.schema);
  const doc = { serviceDate: '2026-10-14', insurance: 'medicare' };
  assert.deepEqual(walk.shapeProblems(encounter(), CONTRACT.encounter), []);
  assert.deepEqual(failed(walk.jsonChecks(encounter(), doc)), []);
  const decided = encounter();
  decided.codes[0] = { ...decided.codes[0], decision: decision({ action: 'approve', by: 'Review agent', at: '2026-11-20T10:06:00Z', note: '' }),
    allowed_actions: ['revoke'] };
  assert.deepEqual(walk.shapeProblems(decided, CONTRACT.encounter), []);
  const mutations = [
    [enc => { enc.internal_round_id = 'x'; }, '$.internal_round_id: not in the customer contract'],
    [enc => { enc.document.storage_hint = 'x'; }, '$.document.storage_hint: not in the customer contract'],
    [enc => { enc.progress.phase_detail = 'x'; }, '$.progress.phase_detail: not in the customer contract'],
    [enc => { enc.codes[0].decision = decision({ action: 'approve', by: 'R', at: '2026-11-20T10:06:00Z', note: '', acknowledgement: 'x' });
      enc.codes[0].allowed_actions = ['revoke']; }, '$.codes[0].decision.acknowledgement: not in the customer contract'],
    [enc => { delete enc.document.view_media_type; }, '$.document.view_media_type: missing (the contract lists it)'],
    [enc => { enc.document.kind = 'txt'; }, '$.document.kind: "txt" is not one of upload|paste'],
    [enc => { enc.progress.server_time = null; }, '$.progress.server_time: null where the contract has iso'],
    [enc => { enc.codes[0].quotes[0].page = 'one'; }, '$.codes[0].quotes[0].page: string where the contract has integer?'],
    [enc => { enc.codes[0].second_check = 'agrees'; }, '$.codes[0].second_check: string where the contract has an object'],
    [enc => { enc.readiness.draft = 'yes'; }, '$.readiness.draft: string where the contract has boolean'],
    [enc => { enc.codes[1].units = 1.5; }, '$.codes[1].units: number where the contract has integer?'],
  ];
  for (const [mutate, said] of mutations) {
    const enc = encounter();
    mutate(enc);
    assert.deepEqual(walk.shapeProblems(enc, CONTRACT.encounter), [said], said);
    assert.ok(failed(walk.jsonChecks(enc, doc)).includes('json.contract'), said);
  }
  // the session and the list are held to theirs; a read is matched to its contract by its route
  assert.deepEqual(walk.shapeProblems({ encounters: [] }, CONTRACT.list), []);
  assert.deepEqual(walk.shapeProblems({ encounters: [{ id: 'x' }] }, CONTRACT.list).length, 7);
  assert.deepEqual(['GET /api/session', 'GET /api/encounters (page)', 'GET /api/encounters/e5c1d3a2-1111-4222-8333-944455556666',
    'GET /api/encounters/e5c1d3a2-1111-4222-8333-944455556666/original', 'POST /api/encounters (page)'].map(walk.contractFor),
  ['session', 'list', 'encounter', null, null]);
});

test('units: a number is shown as that number and units not given as "not given"', () => {
  // FG-D: the contract serves units as a whole number (0 included, as written) or null; the page draws null as "not given"
  const doc = encounter();
  doc.codes[0].units = null;
  doc.codes[1].units = 2;
  const dom = domOf(doc);
  assert.equal(dom.codes[0].units, 'Units not given');
  assert.deepEqual(failed(walk.domChecks(doc, dom, BASE)), []);
  for (const [index, shown] of [[0, ''], [0, 'null'], [1, '12 units'], [1, '22 units'], [1, '1 unit']]) {
    const wrong = domOf(doc);
    wrong.codes[index].units = shown;
    assert.deepEqual(failed(walk.domChecks(doc, wrong, BASE)), ['dom.codes.cells'], `${index}: ${shown}`);
  }
  assert.equal(walk.unitsProblem('2 units', 2), '');
  assert.equal(walk.unitsProblem('Units not given', null), '');
  // 0 is a number the coding review wrote (on a code it does not support): shown as "0 units", never as not given
  assert.equal(walk.unitsProblem('0 units', 0), '');
  for (const shown of ['Units not given', '', '10 units']) assert.match(walk.unitsProblem(shown, 0), /\.code-units .* for 0$/, shown);
  const zero = encounter();
  zero.codes[1].units = 0;
  assert.equal(domOf(zero).codes[1].units, '0 units');
  assert.deepEqual(failed(walk.domChecks(zero, domOf(zero), BASE)), []);
  for (const units of [-1, 1.5, '2']) assert.match(walk.unitsProblem('', units), /neither a whole number nor null/, String(units));
  // the code number is a whole word too: 45385 is not shown by 453851
  const number = encounter();
  const numberDom = domOf(number);
  numberDom.codes[0].number = `${number.codes[0].code}1`;
  assert.deepEqual(failed(walk.domChecks(number, numberDom, BASE)), ['dom.codes.cells']);
});

test('modifiers: each served modifier is shown, and no other', () => {
  assert.equal(walk.modifiersProblem('No modifier', []), '');
  assert.equal(walk.modifiersProblem('Modifiers 25, 59', ['25', '59']), '');
  assert.notEqual(walk.modifiersProblem('Modifier XS', []), '');  // a row showing another row's modifier
  assert.notEqual(walk.modifiersProblem('Modifier 59', ['25']), '');
  assert.notEqual(walk.modifiersProblem('Modifiers 25, 59', ['25']), '');
  assert.notEqual(walk.modifiersProblem(null, []), '');
});

test('LINE IDENTITY: rows are drawn by line, two lines of one code being two rows', () => {
  const twice = encounter({ codes: [row('20610', 'ready', { line: 'L1', modifiers: ['RT'] }),
    row('20610', 'needs_review', { line: 'L2', modifiers: ['LT'] })], questions: [] });
  assert.deepEqual(failed(walk.domChecks(twice, domOf(twice), BASE)), []);
  const swapped = domOf(twice);
  [swapped.codes[0].line, swapped.codes[1].line] = ['L2', 'L1'];
  assert.deepEqual(failed(walk.domChecks(twice, swapped, BASE)), ['dom.codes.rows']);
  const crossed = domOf(twice);  // the L2 row drawn with the L1 row's modifier
  crossed.codes[1].modifiers = 'Modifier RT';
  assert.deepEqual(failed(walk.domChecks(twice, crossed, BASE)), ['dom.codes.cells']);
  const unlined = domOf(twice);
  unlined.codes.forEach(item => { item.line = null; });
  assert.deepEqual(failed(walk.domChecks(twice, unlined, BASE)), ['dom.codes.rows']);
  assert.equal(walk.servedRow(twice.codes, { line: 'L2', code: '20610' }), twice.codes[1]);
  assert.equal(walk.servedRow(encounter({ codes: [row('45385', 'ready')] }).codes, { code: '45385' }).code, '45385');
});

test('LINE IDENTITY: an approval posts the round shown, the line, its code and the acknowledgement exactly', () => {
  const enc = encounter({ codes: [row('20610', 'ready', { line: 'L1' }), row('20610', 'ready', { line: 'L2', modifiers: ['LT'] })] });
  const code = enc.codes[1];
  const body = { round: 1, line: 'L2', code: '20610', action: 'approve', acknowledgement: ACK, note: 'x' };
  assert.deepEqual(walk.decisionRequestProblems(body, enc, code, ACK), []);
  const wrong = [
    [{ ...body, line: 'L1' }, /line "L1", not "L2"/],
    [{ ...body, line: undefined }, /line undefined, not "L2"/],
    [{ ...body, round: 2 }, /round 2, not the round shown \(1\)/],
    [{ ...body, round: undefined }, /round undefined/],
    [{ ...body, code: '20611' }, /code "20611"/],
    [{ ...body, acknowledgement: `${ACK} ` }, /acknowledgement/],
    [{ ...body, action: 'reject' }, /action "reject"/],
  ];
  for (const [posted, said] of wrong) assert.match(walk.decisionRequestProblems(posted, enc, code, ACK).join('; '), said);
  assert.deepEqual(walk.decisionRequestProblems(null, enc, code, ACK), ['the page posted no JSON object']);
  // a round whose rows carry no line cannot be approved by line
  const unlined = encounter({ codes: [row('45385', 'ready')] });
  assert.match(walk.decisionRequestProblems({ ...body, code: '45385' }, unlined, unlined.codes[0], ACK).join(), /names no line/);
});

test('LINE IDENTITY: one approval decides one line, on the round it was made on', () => {
  const before = encounter({ codes: [row('20610', 'ready', { line: 'L1' }), row('20610', 'ready', { line: 'L2', modifiers: ['LT'] })] });
  const approved = { action: 'approve', by: 'Review agent', at: '2026-11-20T10:06:00Z', note: '' };
  const after = structuredClone(before);
  after.codes[1] = { ...after.codes[1], decision: approved, allowed_actions: ['revoke'] };
  after.readiness = { ...after.readiness, approved: true };
  assert.deepEqual(walk.approvalProblems(before, after, before.codes[1]), []);
  const both = structuredClone(after);  // one approval written on every row of the code
  both.codes[0] = { ...both.codes[0], decision: approved, allowed_actions: ['revoke'] };
  assert.match(walk.approvalProblems(before, both, before.codes[1]).join(), /20610 \(L1\): decision null became "approve"/);
  const moved = structuredClone(after);
  moved.round = { ...moved.round, number: 2 };
  assert.match(walk.approvalProblems(before, moved, before.codes[1]).join(), /round 2 after round 1/);
  assert.match(walk.approvalProblems(before, before, before.codes[1]).join(), /20610 \(L2\): decision null/);
});

test('DECISION IDS: an Undo posts the round shown, the line, its code and the id of the decision it undoes', () => {
  const approved = decision({ action: 'approve', by: 'Review agent', at: '2026-11-20T10:06:00Z', note: '' },
    'f6200000-0000-4000-8000-0000000000a2');
  const enc = encounter({ codes: [row('20610', 'ready', { line: 'L1' }),
    row('20610', 'ready', { line: 'L2', modifiers: ['LT'], decision: { ...approved, id: 'f6200000-0000-4000-8000-0000000000a2' }, allowed_actions: ['revoke'] })] });
  const code = enc.codes[1];
  const body = { round: 1, line: 'L2', code: '20610', action: 'revoke', acknowledgement: '', note: '', decision: 'f6200000-0000-4000-8000-0000000000a2' };
  assert.deepEqual(walk.undoRequestProblems(body, enc, code), []);
  const wrong = [
    [{ ...body, decision: undefined }, /decision undefined, not the one shown \("f6200000-0000-4000-8000-0000000000a2"\)/],
    [{ ...body, decision: 'f6200000-0000-4000-8000-0000000000a9' }, /decision "f6200000-0000-4000-8000-0000000000a9", not the one shown/],
    [{ ...body, line: 'L1' }, /line "L1", not "L2"/],
    [{ ...body, round: 2 }, /round 2, not the round shown \(1\)/],
    [{ ...body, code: '20611' }, /code "20611"/],
    [{ ...body, action: 'reject' }, /action "reject", not "revoke"/],
  ];
  for (const [posted, said] of wrong) assert.match(walk.undoRequestProblems(posted, enc, code).join('; '), said);
  assert.deepEqual(walk.undoRequestProblems(null, enc, code), ['the page posted no JSON object']);
  // a served decision with no id cannot be named, so no Undo of it can be right
  const unnamed = structuredClone(enc);
  delete unnamed.codes[1].decision.id;
  assert.match(walk.undoRequestProblems(body, unnamed, unnamed.codes[1]).join(), /names no id/);
});

test('the History names a decided line with its code ("L2 45380"), as a whole phrase', () => {
  const enc = encounter({ activity: [{ at: '2026-11-20T10:06:00Z', text: 'Review agent approved L2 20610.' },
    { at: '2026-11-20T10:07:00Z', text: 'Review agent approved L12 20610.' }] });
  assert.deepEqual(walk.activityNaming(enc, { line: 'L2', code: '20610' }), ['Review agent approved L2 20610.']);
  assert.deepEqual(walk.activityNaming(enc, { line: 'L1', code: '20610' }), [], 'L12 is not L1');
  assert.deepEqual(walk.activityNaming(encounter({ activity: [{ at: '2026-11-20T10:06:00Z', text: 'Review agent approved 20610.' }] }),
    { line: 'L2', code: '20610' }), [], 'the code alone does not name the line');
  assert.deepEqual(walk.activityNaming({}, { line: 'L2', code: '20610' }), []);
});

test('DECISION IDS: one Undo clears one line\'s decision, on the round it was made on', () => {
  const approved = decision({ action: 'approve', by: 'Review agent', at: '2026-11-20T10:06:00Z', note: '' });
  const before = encounter({ codes: [row('20610', 'ready', { line: 'L1', decision: approved, allowed_actions: ['revoke'] }),
    row('20610', 'ready', { line: 'L2', modifiers: ['LT'], decision: approved, allowed_actions: ['revoke'] })] });
  const after = structuredClone(before);
  after.codes[1] = { ...after.codes[1], decision: null, allowed_actions: ['approve', 'reject'] };
  assert.deepEqual(walk.undoProblems(before, after, before.codes[1]), []);
  const both = structuredClone(after);  // one Undo clearing every row of the code
  both.codes[0] = { ...both.codes[0], decision: null, allowed_actions: ['approve', 'reject'] };
  assert.match(walk.undoProblems(before, both, before.codes[1]).join(), /20610 \(L1\): decision "approve" became null/);
  assert.match(walk.undoProblems(before, before, before.codes[1]).join(), /20610 \(L2\): decision "approve" still stands/);
  const closed = structuredClone(after);
  closed.codes[1].allowed_actions = [];
  assert.match(walk.undoProblems(before, closed, before.codes[1]).join(), /20610 \(L2\): actions \[\], not \[approve,reject\]/);
  const moved = structuredClone(after);
  moved.round = { ...moved.round, number: 2 };
  assert.match(walk.undoProblems(before, moved, before.codes[1]).join(), /round 2 after round 1/);
});

test('the review dialog is driven as the page draws it', () => {
  // FG-A: studio/templates/studio/index.html draws the acknowledgement as a checkbox inside the label that carries it
  const html = fs.readFileSync(path.join(__dirname, '..', 'studio', 'templates', 'studio', 'index.html'), 'utf8');
  const dialog = /<dialog id="reviewDialog"[\s\S]*?<\/dialog>/.exec(html)[0];
  const id = selector => selector.replace(/^#/, '');
  const label = new RegExp(`<label[^>]*\\bid="${id(walk.REVIEW_DIALOG.label)}"[^>]*>([\\s\\S]*?)</label>`).exec(dialog);
  assert.ok(label, `${walk.REVIEW_DIALOG.label} is a label of the review dialog`);
  assert.match(label[1], new RegExp(`<input[^>]*\\bid="${id(walk.REVIEW_DIALOG.box)}"[^>]*\\btype="checkbox"`));
  assert.match(dialog, new RegExp(`<textarea[^>]*\\bid="${id(walk.REVIEW_DIALOG.note)}"`));
  assert.match(html, new RegExp(`<button[^>]*\\bid="${id(walk.REVIEW_DIALOG.save)}"`));
  const app = fs.readFileSync(path.join(__dirname, '..', 'studio', 'static', 'studio', 'app.js'), 'utf8');
  assert.ok(app.includes(`$('${walk.REVIEW_DIALOG.box}').addEventListener('change'`), 'saving is offered once the box is ticked');
});

test('the review dialog is driven through the page itself, in a browser', async t => {
  // FG-A in a real browser: ops/dev_preview_server.cjs's mock serves the shipped page and fixtures; walk.approve() ticks
  // the box the page draws and saves. Skipped where Playwright is not installed (CPT_VERIFY_PLAYWRIGHT).
  if (!fs.existsSync(path.join(walk.PLAYWRIGHT, 'package.json'))) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { chromium } = require(walk.PLAYWRIGHT);
  const port = await freePort();
  const server = childProcess.spawn(process.execPath, [path.join(__dirname, 'dev_preview_server.cjs'), `--port=${port}`],
    { stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => server.kill('SIGTERM'));
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the preview server did not start')), 15000);
    server.stdout.on('data', chunk => { if (String(chunk).includes('CPT Studio dev preview')) { clearTimeout(timer); resolve(); } });
    server.once('exit', code => reject(new Error(`the preview server exited ${code}`)));
  });
  const base = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ headless: true });
  t.after(() => browser.close());
  const page = await (await browser.newContext()).newPage();
  const session = await (await page.request.get(`${base}/api/session`, { headers: walk.CLIENT_HEADERS })).json();
  const id = 'f5000000-0000-4000-8000-000000000001';  // tests/fixtures/customer/encounter-ready.json
  const enc = await (await page.request.get(`${base}/api/encounters/${id}`, { headers: walk.CLIENT_HEADERS })).json();
  const code = enc.codes.find(item => item.status === 'ready' && !item.decision && item.allowed_actions.includes('approve'));
  assert.ok(code, 'the ready fixture offers a code to approve');
  await page.goto(`${base}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(count => document.querySelectorAll('ol#codesList > li.code-row').length === count,
    enc.codes.length, { timeout: 15000 });
  const made = await walk.approve(page, { base, session }, enc, code);
  assert.equal(made.kind, 'checkbox');
  assert.equal(made.status, 201);
  assert.ok(made.shown.includes(session.acknowledgement.replace(/\s+/g, ' ').trim()), made.shown);
  assert.equal(made.body.acknowledgement, session.acknowledgement);
  await t.test('LINE IDENTITY: the page posts the round shown and the line', {
    skip: typeof code.line !== 'string' && 'the page\'s fixtures serve no line yet (FIX-SPEC section 1, lane F1b)',
  }, () => {
    assert.deepEqual(walk.decisionRequestProblems(made.body, enc, code, session.acknowledgement), []);
  });
  // the draft download through the export dialog, as the walk makes it: the page's request names the round shown
  await t.test('the page\'s download names the round shown', async () => {
    await page.goto(`${base}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(count => document.querySelectorAll('ol#codesList > li.code-row').length === count, enc.codes.length, { timeout: 15000 });
    const out = scratch();
    const download = await walk.exportTxt(page, { base, out }, enc, 'draft', out);
    assert.equal(download.status, 201);
    assert.deepEqual(walk.exportRequestProblems(download.body, enc, 'draft'), []);
    // the preview's file is a mock (no banner at its end, no codes): only what the page and the download did is held here
    const checks = Object.fromEntries(walk.exportChecks(download, enc, 'draft').map(item => [item.id, item.status]));
    assert.deepEqual([checks['export.draft'], checks['export.draft.request'], checks['export.draft.same_bytes']], ['pass', 'pass', 'pass']);
  });
  // the Undo of a decided line through the page (tests/fixtures/customer/encounter-reviewed.json): its request names the
  // decision the page shows, and the preview, as the server, accepts only that one
  await t.test('DECISION IDS: the page\'s Undo names the decision it undoes', async () => {
    const reviewedId = 'f6000000-0000-4000-8000-000000000001';
    const reviewed = await (await page.request.get(`${base}/api/encounters/${reviewedId}`, { headers: walk.CLIENT_HEADERS })).json();
    const decided = reviewed.codes.find(item => item.decision && item.allowed_actions.includes('revoke'));
    assert.ok(decided && typeof decided.decision.id === 'string', 'the reviewed fixture serves a decided line with its id');
    await page.goto(`${base}/#doc/${reviewedId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(count => document.querySelectorAll('ol#codesList > li.code-row').length === count, reviewed.codes.length, { timeout: 15000 });
    const undone = await walk.undo(page, { base, session }, reviewed, decided);
    assert.equal(undone.status, 201);
    assert.deepEqual(walk.undoRequestProblems(undone.body, reviewed, decided), []);
  });
});

// A one-page synthetic PDF of raw content streams (Helvetica as /F1), for the overprint and no-text pages.
function rawPdf(streams) {
  const objects = [];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${streams.map((_, i) => `${4 + i * 2} 0 R`).join(' ')}] /Count ${streams.length} >>`;
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';
  streams.forEach((stream, i) => {
    objects[4 + i * 2] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + i * 2} 0 R >>`;
    objects[5 + i * 2] = `<< /Length ${Buffer.byteLength(stream, 'latin1')} >>\nstream\n${stream}\nendstream`;
  });
  let body = '%PDF-1.4\n';
  const offsets = [];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(body, 'latin1');
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`;
  }
  const xref = Buffer.byteLength(body, 'latin1');
  body += `xref\n0 ${objects.length}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}`;
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, 'latin1');
}

test('every quote is chosen and judged by the walk\'s own search through the page itself, in a browser', async t => {
  // D368 in a real browser: the dev preview's synthetic PDF and text documents, the shipped page and its PDF viewer, the
  // walk's own judge. Skipped where Playwright is not installed (CPT_VERIFY_PLAYWRIGHT).
  if (!fs.existsSync(path.join(walk.PLAYWRIGHT, 'package.json'))) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { chromium } = require(walk.PLAYWRIGHT);
  const { syntheticPdf } = require('./dev_preview_server.cjs');
  const port = await freePort();
  const server = childProcess.spawn(process.execPath, [path.join(__dirname, 'dev_preview_server.cjs'), `--port=${port}`],
    { stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => server.kill('SIGTERM'));
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the preview server did not start')), 15000);
    server.stdout.on('data', chunk => { if (String(chunk).includes('CPT Studio dev preview')) { clearTimeout(timer); resolve(); } });
    server.once('exit', code => reject(new Error(`the preview server exited ${code}`)));
  });
  const base = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ headless: true });
  t.after(() => browser.close());
  const open = async (id, enc, setup) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    const violations = [];
    page.on('console', message => { if (message.type() === 'error') violations.push(message.text()); });
    await page.addInitScript(() => document.addEventListener('securitypolicyviolation', event => console.error(`policy: ${event.violatedDirective}`)));
    if (setup) await setup(page);
    await page.goto(`${base}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(count => document.querySelectorAll('ol#codesList > li.code-row').length === count, enc.codes.length, { timeout: 15000 });
    return { page, context, violations };
  };
  const served = async id => (await (await browser.newContext()).request.get(`${base}/api/encounters/${id}`, { headers: walk.CLIENT_HEADERS })).json();
  const ready = 'f5000000-0000-4000-8000-000000000001';  // tests/fixtures/customer/encounter-ready.json: the two-page PDF
  const word = 'f9000000-0000-4000-8000-000000000001';  // encounter-word.json: a Word file viewed as its PDF
  const text = 'f3000000-0000-4000-8000-000000000001';  // encounter-awaiting-answer.json: a text document
  // the ready fixture with its quotes replaced (the first code carries them) and, when given, another view
  const crafted = async (quotes, pdf = null) => {
    const enc = await served(ready);
    enc.codes[0].quotes = quotes;
    for (const code of enc.codes.slice(1)) code.quotes = [];
    const opened = await open(ready, enc, async item => {
      await item.route(`**/api/encounters/${ready}`, route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(enc) }));
      if (pdf) await item.route(url => url.pathname === `/api/encounters/${ready}/original`, route => route.fulfill({ status: 200, contentType: 'application/pdf', body: pdf }));
    });
    return { enc, ...opened };
  };
  for (const id of [ready, word, text]) {
    await t.test(`the fixture ${id}: every quote marked once, as the walk's own search finds it`, async () => {
      const enc = await served(id);
      const { page, context, violations } = await open(id, enc);
      const chosen = await walk.chooseQuotes(page, enc);
      const made = walk.quoteMarkChecks(chosen);
      assert.equal(made.status, 'pass', made.reason);
      assert.deepEqual([made.data.quotes, made.data.marked_once, made.data.off_page, made.data.mismatched, made.data.missed, made.data.blank],
        [walk.servedQuotes(enc).length, walk.servedQuotes(enc).length, 0, 0, 0, 0]);
      assert.deepEqual(violations, [], 'no policy violation and no error in the page');
      await context.close();
    });
  }
  await t.test('crafted quotes: a duplicate, a passage running onto the next page, no page, another case', async () => {
    const { enc, page, context, violations } = await crafted([{ text: 'the gastric antrum.', page: 1 },
      { text: 'taken from the gastric antrum. Colonoscopy: The colonoscope was advanced', page: 1 },
      { text: 'Impression: antral erythema', page: null }, { text: 'PATCHY ERYTHEMA WAS SEEN', page: 1 }]);
    const chosen = await walk.chooseQuotes(page, enc);
    const made = walk.quoteMarkChecks(chosen);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual([made.data.quotes, made.data.marked_once, made.data.marked_multi, made.data.not_found], [4, 3, 1, 0]);
    assert.deepEqual(chosen.map(item => item.reading.note), ['These words appear 2 times on page 1. Each is marked.',
      'Marked on page 1, continuing onto page 2.', 'Marked on page 2.', 'Marked on page 1.']);
    assert.deepEqual(chosen[1].reading.pages, [1, 2]);
    // every page of the document was read for each quote, and every marked page was drawn
    assert.ok(chosen.every(item => [...item.reading.pagesRead.values()].every(read => read.drawn && read.canvas.opaque === 1)));
    // the selected quote stays selected; the page's own text layer is the document's, never scanned as its wording
    assert.equal(await page.getAttribute('#quotesPanel .quote.selected', 'data-quote'), chosen[3].key);
    const strings = (await page.evaluate(walk.collectDomStrings)).map(([, value]) => value);
    assert.ok(strings.includes('Marked on page 1.'), 'the note is read');
    assert.ok(!strings.some(value => value.includes('Endoscopy report (fictional)')), 'the text layer is not read');
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('#documentViewer .pdf-text span')].some(span => span.textContent.includes('Endoscopy report (fictional)'))),
      'though the text layer holds it');
    assert.deepEqual(violations, []);
    // the page script leaves window's own properties alone (the walk's viewport check reads window.innerWidth)
    assert.equal(await page.evaluate(() => typeof window.innerWidth), 'number');
    await context.close();
  });
  await t.test('readPdfPage reads a drawn page apart from the page script: its items and line breaks, flags and boxes, marks, and canvas', async () => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const span = (inner, extra = '') => `<span${extra}>${inner}</span>`;
    const mark = (occurrence, inner) => `<span class="pdf-mark" data-occurrence="${occurrence}">${inner}</span>`;
    const at = (left, top) => ` style="position:absolute;left:${left}px;top:${top}px;font-size:10px;line-height:1"`;
    await page.setContent(`<div id="documentViewer" data-mode="pdf" data-mark-status="marked" data-mark-pages="1" data-mark-count="2">
      <div class="pdf-page" data-page="1" style="position:relative;width:300px;height:200px"><canvas width="300" height="200" style="position:absolute;inset:0"></canvas>
      <div class="pdf-text" style="position:absolute;inset:0">${span(`The patient ${mark(0, 'Jose')}`, at(10, 10))}${span('\u0301', at(80, 10))}${span(' ', at(90, 10))}${span(`${mark(0, 'Garcia')} was seen.`, at(100, 10))}<br>`
      + `${span('Impression:', at(10, 40))}${span('Impression:', `${at(10.3, 40)} data-overprint="1"`)}${span(`${mark(1, 'two')} polyps`, at(70, 40))}</div></div>
      <div class="pdf-page" data-page="2" style="width:300px;height:200px"></div>
    </div><p id="viewerMark">These words appear 2 times on page 1. Each is marked.</p>`);
    // the canvas drawn: white paper with a dark bar under the first line
    await page.evaluate(() => {
      const ctx = document.querySelector('canvas').getContext('2d');
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, 300, 200);
      ctx.fillStyle = 'black';
      ctx.fillRect(10, 10, 200, 10);
    });
    const read = await page.evaluate(walk.readPdfPage, 1);
    assert.deepEqual(read.tokens.map(token => (token.kind === 'br' ? 'BR' : `${token.text}${token.copy ? ' (copy)' : ''}`)),
      ['The patient Jose', '\u0301', ' ', 'Garcia was seen.', 'BR', 'Impression:', 'Impression: (copy)', 'two polyps']);
    assert.deepEqual(read.marks, [{ item: 0, occurrence: 0, start: 12, end: 16 }, { item: 3, occurrence: 0, start: 0, end: 6 }, { item: 6, occurrence: 1, start: 0, end: 3 }]);
    assert.deepEqual(read.tokens[6].box.map(value => Math.round(value * 10) / 10), [10.3, 40, 10]);
    assert.equal(walk.unbornFlags(read.tokens), 0, 'the flagged copy lies 0.3 px from the span it copies');
    assert.deepEqual([read.canvas.present, read.canvas.visible, read.canvas.opaque, read.canvas.markPixels > 0], [true, true, 1, true]);
    assert.equal((await page.evaluate(walk.readPdfPage, 2)).drawn, false);
    // S5 apart from the page script: the first occurrence's run 'Jose' ends inside the character the accent completes
    const reading = { ...(await page.evaluate(walk.readViewer)), pagesRead: new Map([[1, read], [2, { number: 2, drawn: true, tokens: [], marks: [], canvas: read.canvas }]]) };
    assert.equal(walk.judgeQuote({ code: '43239', line: 'L1', text: 'x', page: null }, reading).cut, 1);
    // a canvas that was never drawn reads as not painted
    await page.evaluate(() => { document.querySelector('canvas').replaceWith(Object.assign(document.createElement('canvas'), { width: 300, height: 200 })); });
    assert.equal((await page.evaluate(walk.readPdfPage, 1)).canvas.opaque, 0);
    await context.close();
  });
  await t.test('where the PDF library cannot load, the browser\'s own viewer is framed: nothing is marked and the check fails', async inner => {
    const enc = await served(word);
    const { page, context } = await open(word, enc, item => item.route(url => /\/pdf\.min\.mjs$/.test(url.pathname), route => route.abort()));
    await page.waitForSelector('#documentViewer[data-mode="frame"] iframe.viewer-fallback', { timeout: 30000 });
    const chosen = await walk.chooseQuotes(page, enc);
    const made = walk.quoteMarkChecks(chosen);
    assert.equal(made.status, 'fail');
    assert.equal(made.data.unavailable, chosen.length);
    const last = walk.servedQuotes(enc).at(-1);
    assert.match(await page.getAttribute('#documentViewer iframe', 'src'), new RegExp(`#page=${last.page}$`));
    await inner.test('round 3: the library note (N3), a new frame for each new page', () => {
      assert.equal(chosen.at(-1).reading.fallback, 'library');
      assert.equal(chosen.at(-1).reading.note, `The marking tool did not work here, so nothing is marked. The quote is on page ${last.page}.`);
      // each quote judged unavailable and nothing else: the note as written and the frame really opening its page
      for (const item of chosen) assert.deepEqual(walk.judgeQuote(item.quote, item.reading).problems.length, 1, item.reading.note);
      assert.match(made.reason, /browser's own viewer \(the marking tool did not work in the page\)/);
    });
    await context.close();
  });
  await t.test('where the library runs but cannot draw the document, the browser\'s own viewer is framed and the check fails', async inner => {
    const enc = await served(ready);
    // the view address answers with bytes that are no PDF: the library refuses the document, the browser is not at fault
    const { page, context, violations } = await open(ready, enc, item => item.route(url => url.pathname === `/api/encounters/${ready}/original`,
      route => route.fulfill({ status: 200, contentType: 'application/pdf', body: 'not a PDF at all' })));
    await page.waitForSelector('#documentViewer[data-mode="frame"] iframe.viewer-fallback', { timeout: 30000 });
    const chosen = await walk.chooseQuotes(page, enc);
    const made = walk.quoteMarkChecks(chosen);
    assert.equal(made.status, 'fail');
    assert.equal(chosen.at(-1).reading.fallback, 'document');
    assert.match(made.reason, /\(the document cannot be drawn in the page\)/);
    assert.deepEqual(violations, []);
    await inner.test('round 3: the document note (N3) names the quote\'s page', () => {
      const last = walk.servedQuotes(enc).at(-1);
      assert.equal(chosen.at(-1).reading.note, `This document cannot be drawn here, so nothing is marked. The quote is on page ${last.page}.`);
      for (const item of chosen) assert.deepEqual(walk.judgeQuote(item.quote, item.reading).problems.length, 1, item.reading.note);
    });
    await context.close();
  });
  await t.test('round 3: words not found (N1), words of another page, inside a word (R2), a format character (R3), against the new viewer', async () => {
    const pdf = syntheticPdf([['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'The patient was told to bathe ending the preparation.',
      'Findings: the end of the procedure was uneventful.', 'Mild pain was reported; the abdomen was painless.'],
    ['Bowel preparation quality was not recorded.']]);
    const { enc, page, context, violations } = await crafted([{ text: 'A passage that is in no page of this document.', page: 2 },
      { text: 'Bowel preparation quality was not recorded.', page: 1 }, { text: 'the end', page: 1 }, { text: 'pain', page: 1 },
      { text: 'Mild pain was re\u00adported', page: 1 }], pdf);
    const chosen = await walk.chooseQuotes(page, enc);
    const made = walk.quoteMarkChecks(chosen);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual([made.data.marked_once, made.data.not_found, made.data.no_text], [3, 2, 0]);
    assert.deepEqual(chosen.map(item => item.reading.note), [
      'The exact words were not found in the searchable text of page 2, so nothing is marked. Page 2 is shown.',
      'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.',
      'Marked on page 1.', 'Marked on page 1.', 'Marked on page 1.']);
    assert.deepEqual(violations, []);
    await context.close();
  });
  await t.test('round 3: an overprint copy (R1) counts once and is flagged where its geometry bears the flag out; a page with no text (N2)', async () => {
    const line = (x, y, words) => `BT /F1 11 Tf ${x} ${y} Td (${words}) Tj ET`;
    const pdf = rawPdf([[line(56, 700, 'DIAGNOSIS: TUBULAR ADENOMA.'), line(56.3, 700, 'DIAGNOSIS: TUBULAR ADENOMA.'),
      line(56, 680, 'The procedure was uneventful.')].join('\n'), '0 0 0 rg 56 600 200 50 re f']);
    const { enc, page, context, violations } = await crafted([{ text: 'DIAGNOSIS: TUBULAR ADENOMA.', page: 1 },
      { text: 'Any words at all', page: 2 }], pdf);
    const chosen = await walk.chooseQuotes(page, enc);
    const made = walk.quoteMarkChecks(chosen);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual([made.data.marked_once, made.data.not_found, made.data.no_text, made.data.flags], [1, 1, 1, 0]);
    assert.equal(chosen[0].reading.note, 'Marked on page 1.');
    assert.equal(chosen[1].reading.note, 'Page 2 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 2 is shown.');
    assert.ok([...chosen[0].reading.pagesRead.get(1).tokens].some(token => token.copy), 'the viewer flags the copy');
    assert.deepEqual(violations, []);
    await context.close();
  });
});

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

test('the readers that run in the page are self-contained functions', () => {
  for (const reader of [walk.readEncounterDom, walk.collectDomStrings, walk.readViewer, walk.readPdfPage, walk.readTextFrame]) {
    const source = reader.toString();
    assert.match(source, /^function /);
    for (const outer of [/\bwalk\./, /\bcollapse\(/, /\bCLIENT_HEADERS\b/, /\brequire\(/, /\bisObject\(/, /\bSTEPS\b/]) {
      assert.doesNotMatch(source, outer, `${reader.name} uses ${outer}`);
    }
  }
});

// --- the operator gate and the exports -----------------------------------------------------------------------------------

test('every /ops/ path is 404 to the customer and never 200 to nobody, and the operator reads the encounter', () => {
  const probes = [{ method: 'GET', path: '/ops/', customer: 404, anonymous: 302 }, { method: 'POST', path: '/ops/x', customer: 404 }];
  assert.deepEqual(failed(walk.opsChecks({ probes, operator: { status: 200, names: true } })), []);
  assert.deepEqual(failed(walk.opsChecks({ probes: [{ ...probes[0], customer: 200 }], operator: { status: 200, names: true } })),
    ['ops.customer_404']);
  assert.deepEqual(failed(walk.opsChecks({ probes: [{ ...probes[0], anonymous: 200 }], operator: { status: 200, names: true } })),
    ['ops.anonymous_not_200']);
  assert.deepEqual(failed(walk.opsChecks({ probes, operator: { status: 404, names: false } })), ['ops.operator_view']);
});

test('an export is a .txt between SYNTHETIC banners, the same bytes twice, naming its codes', () => {
  const enc = encounter();
  enc.codes[0].decision = { action: 'approve' };
  const text = 'SYNTHETIC - NOT FOR BILLING\nApproved codes\n43239 approved by Review agent\nSYNTHETIC - NOT FOR BILLING\n';
  const item = { kind: 'approved', status: 201, filename: 'gi-02-approved.txt', suggested: 'gi-02-approved.txt', size: text.length,
    sha256: 'a'.repeat(64), text, refetch: { status: 200, sha256: 'a'.repeat(64), size: text.length },
    body: { kind: 'approved', fmt: 'txt', round: 1 } };
  assert.deepEqual(failed(walk.exportChecks(item, enc, 'approved')), []);
  // the page's request names the kind, the format and the round shown (FIX-SPEC-2 section 5)
  for (const body of [{ kind: 'approved', fmt: 'txt' }, { kind: 'approved', fmt: 'txt', round: 2 }, { kind: 'approved', fmt: 'txt', round: '1' },
    { kind: 'draft', fmt: 'txt', round: 1 }, { kind: 'approved', fmt: 'csv', round: 1 }, null]) {
    assert.deepEqual(failed(walk.exportChecks({ ...item, body }, enc, 'approved')), ['export.approved.request'], JSON.stringify(body));
  }
  assert.match(walk.exportRequestProblems({ kind: 'approved', fmt: 'txt', round: 2 }, enc, 'approved').join(), /round 2, not the round shown \(1\)/);
  assert.deepEqual(walk.exportRequestProblems(null, enc, 'draft'), ['the page posted no JSON object']);
  assert.deepEqual(failed(walk.exportChecks({ ...item, refetch: { ...item.refetch, sha256: 'b'.repeat(64) } }, enc, 'approved')),
    ['export.approved.same_bytes']);
  assert.deepEqual(failed(walk.exportChecks({ ...item, text: text.replace(/SYNTHETIC - NOT FOR BILLING\n$/, '') }, enc, 'approved')),
    ['export.approved.synthetic']);
  assert.deepEqual(failed(walk.exportChecks({ ...item, body: { ...item.body, kind: 'draft' } }, enc, 'draft')), ['export.draft.codes']);  // the draft names every code
  assert.deepEqual(failed(walk.exportChecks({ kind: 'draft', error: 'the export option is disabled' }, enc, 'draft')), ['export.draft']);
});

// --- the evidence --------------------------------------------------------------------------------------------------------

test('the evidence says per document pass or fail with the reasons of every failed check, in its schema', () => {
  const record = { file: 'gi-02.txt', checks: [walk.parseArgs(REQUIRED) && { id: 'upload.created', status: 'pass', reason: 'ok' }],
    error: null };
  Object.assign(record, walk.documentResult(record));
  assert.deepEqual([record.result, record.reasons], ['pass', []]);
  const bad = { file: 'gi-03.pdf', checks: [{ id: 'dom.quotes', status: 'fail', reason: 'two quotes missing' },
    { id: 'answers', status: 'skip', reason: 'no question' }, { id: 'scan.dom.wording', status: 'warn', reason: 'soft' }], error: 'boom' };
  Object.assign(bad, walk.documentResult(bad));
  assert.deepEqual([bad.result, bad.reasons], ['fail', ['error: boom', 'dom.quotes: two quotes missing']]);
  const evidence = { schema: walk.EVIDENCE_SCHEMA, run_id: 'walk-1', started_at: '2026-11-20T10:00:00Z', base_url: BASE,
    run_checks: [], documents: [record, bad], summary: { documents: 2, passed: 1, failed: 1 } };
  assert.deepEqual(walk.evidenceProblems(evidence), []);
  assert.deepEqual(walk.evidenceProblems({ ...evidence, schema: 'cpt-studio-browser-evidence@2' }), ['schema is "cpt-studio-browser-evidence@2"']);
  assert.deepEqual(walk.evidenceProblems({ ...evidence, summary: { documents: 2, passed: 2, failed: 0 } }),
    ['the summary does not count the documents']);
  assert.deepEqual(walk.evidenceProblems({ ...evidence, documents: [{ ...record, reasons: ['x'] }], summary: null }),
    ['documents[0] says pass with 1 reason(s)']);
  assert.deepEqual(walk.evidenceProblems({ ...evidence, documents: [{ ...bad, checks: [{ id: 'x', status: 'maybe', reason: '' }] }], summary: null }),
    ['documents[0].checks is not a list of {id, status, reason}']);
});

test('the walk names the current customer build and refuses to upload unless paid requests are accepted', () => {
  assert.deepEqual(walk.CLIENT_HEADERS, { 'X-CPT-Studio-Client': 'customer-2026-11-22' });
  const source = fs.readFileSync(path.join(__dirname, 'walk.cjs'), 'utf8');
  assert.ok(source.includes("const CLIENT_HEADERS = { 'X-CPT-Studio-Client': 'customer-2026-11-22' };"));
  assert.ok(source.includes('chromium.launch({ headless: true })'));
  const session = { can_review: true, acknowledgement: 'I reviewed this code against the document.' };
  assert.deepEqual(walk.sessionProblems(session, { allowLiveProvider: true }), []);
  assert.match(walk.sessionProblems(session, { allowLiveProvider: false }).join(), /--allow-live-provider/);
  assert.match(walk.sessionProblems({ ...session, can_review: false }, { allowLiveProvider: true }).join(), /cannot review/);
  assert.match(walk.sessionProblems({ ...session, acknowledgement: ' ' }, { allowLiveProvider: true }).join(), /no acknowledgement/);
  assert.equal(walk.summarize(encounter()).codes[0].quotes, 1);  // the evidence keeps counts, never the document's text
  assert.ok(!JSON.stringify(walk.summarize(encounter())).includes('antrum'));
});
