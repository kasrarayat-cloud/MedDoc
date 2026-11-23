'use strict';
/*
 * Unit tests for ops/walk.cjs's pure helpers: argument parsing, the documents and credentials it reads, the denylist
 * scan (every vector of ops/verification/customer-denylist.json, which ops/scan_customer.py
 * runs too, so the readers cannot drift apart), the JSON contract (ops/verification/customer-contract.json, held to
 * scan_customer.py's reader by ops/test_walk_contract.py) and DOM contract checks, the approval of one line on the round
 * shown, the walk's own reading of a PDF in Node with the pinned library and its judge of a chosen quote (DECISIONS D368
 * rounds 3 and 5: its own search with the rule's R1 overprint copies, R2 word edges with R2a numbers, R2b separate
 * drawings and R2c Han and hiragana, R3 format characters, the 22 shared examples of round 5, the notes N1-N4 character
 * for character; the viewer held to its reading - its page count, text layer, overprint flags both ways, marks in place,
 * pages drawn and seen, the last quote judged again after each redraw), the downloaded report (the physician PDF, the
 * only report made since 2026-11-21: read page by page, every page held to its synthetic line and status) and the
 * evidence's shape - synthetic values only; and the review dialog and every quote of the dev preview's documents and of
 * synthetic PDFs of every page shape driven through the page itself (ops/dev_preview_server.cjs's mock, in Chromium)
 * where Playwright is installed (CPT_VERIFY_PLAYWRIGHT), skipped where it is not. CPT_WALK_TEST_PORTS ('first-last')
 * keeps the preview's ports to a range. The browser test named "round 5 against the new viewer" needs the round-5 viewer
 * (Builder A's) and fails on the round-3 one by design.
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

test('scanFile reads a text line by line, its quoted lines set aside (a PDF report is scanned by ops/scan_customer.py)', () => {
  const ctx = walk.scanContext({});
  walk.addQuotes(ctx, { codes: [{ quotes: [{ text: 'Trace fluid in the pouch.', page: 1 },
    { text: 'Cold forceps biopsies were taken from the antrum, where trace fluid was seen.', page: 1 }] }] });
  // scanFile on a text laid out as a report's lines (it is the walk's reader for a text; the walk does not scan the PDF
  // reports it downloads - ops/scan_customer.py does): a quotation on a line of its own, or wrapped over two
  const text = ['QuillMD', 'C P T   S T U D I O', 'DRAFT · REVIEW REQUIRED', 'gi-02 · E5C1D3A2 · Coding review 1',
    'Synthetic data · Not for billing or claims   CPT-E5C1D3A2 · r1   /   01 of 01', '01   43239 / Ready for approval',
    '“Trace fluid in the pouch.”', 'Page 1', 'Reason: read by the model gpt-6', '02   00731 / Needs your answer',
    '“Cold forceps biopsies were taken from the antrum, where', 'trace fluid was seen.”', 'Page 1'].join('\n');
  const hits = walk.scanFile(text, ctx, 'draft.pdf');
  assert.deepEqual(hits.map(hit => [hit.id, hit.where]), [['model_id', 'draft.pdf line 9']]);
  // the control: the same lines, the quotations not the document's, are hits - so it is the setting aside that clears them
  assert.deepEqual(walk.scanFile(text, walk.scanContext({}), 'draft.pdf').map(hit => [hit.id, hit.where]),
    [['trace', 'draft.pdf line 7'], ['model_id', 'draft.pdf line 9'], ['trace', 'draft.pdf line 12']]);
  // checkScan turns hits into a failed check and soft hits into a warning, whatever surface it is given
  const checks = walk.checkScan('scan.text', [...hits, { id: 'provider_word', severity: 'soft', where: 'x', match: 'provider' }], 'a text');
  assert.deepEqual(checks.map(item => [item.id, item.status]), [['scan.text', 'fail'], ['scan.text.wording', 'warn']]);
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

// A synthetic PDF of raw content streams: each page a stream, or {stream, media, crop, rotate, userUnit}; the standard
// fonts Helvetica (/F1), Times-Roman (/F2) and Courier (/F3); and an image /Im1 where a page gives one ({width, height,
// gray: Buffer}, drawn by the stream with /Im1 Do).
function pdfOf(pages) {
  const objects = [];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
  objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>';
  objects[5] = '<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>';
  const kids = [];
  const binary = [];
  pages.forEach((spec, i) => {
    const page = typeof spec === 'string' ? { stream: spec } : spec;
    const id = 6 + i * 3;
    const box = [`/MediaBox [${(page.media || [0, 0, 612, 792]).join(' ')}]`, page.crop ? `/CropBox [${page.crop.join(' ')}]` : '',
      page.rotate ? `/Rotate ${page.rotate}` : '', page.userUnit ? `/UserUnit ${page.userUnit}` : ''].filter(Boolean).join(' ');
    const image = page.image ? ` /XObject << /Im1 ${id + 2} 0 R >>` : '';
    objects[id] = `<< /Type /Page /Parent 2 0 R ${box} /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >>${image} >> /Contents ${id + 1} 0 R >>`;
    objects[id + 1] = `<< /Length ${Buffer.byteLength(page.stream, 'latin1')} >>\nstream\n${page.stream}\nendstream`;
    if (page.image) {
      const data = require('node:zlib').deflateSync(page.image.gray);
      binary[id + 2] = data;
      objects[id + 2] = `<< /Type /XObject /Subtype /Image /Width ${page.image.width} /Height ${page.image.height} /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length ${data.length} >>`;
    }
    kids.push(`${id} 0 R`);
  });
  objects[2] = `<< /Type /Pages /Kids [${kids.join(' ')}] /Count ${pages.length} >>`;
  const parts = [Buffer.from('%PDF-1.4\n', 'latin1')];
  let size = parts[0].length;
  const offsets = [];
  for (let id = 1; id < objects.length; id += 1) {
    if (objects[id] === undefined) objects[id] = 'null';
    offsets[id] = size;
    const piece = binary[id]
      ? Buffer.concat([Buffer.from(`${id} 0 obj\n${objects[id]}\nstream\n`, 'latin1'), binary[id], Buffer.from('\nendstream\nendobj\n', 'latin1')])
      : Buffer.from(`${id} 0 obj\n${objects[id]}\nendobj\n`, 'latin1');
    parts.push(piece);
    size += piece.length;
  }
  parts.push(Buffer.from(`xref\n0 ${objects.length}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}`
    + `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${size}\n%%EOF\n`, 'latin1'));
  return Buffer.concat(parts);
}
const pdfText = value => value.replace(/[\\()]/g, ch => `\\${ch}`);
// One line of text at (x, y): its font and size, and a text matrix [a b c d] that turns it, when given.
const line = (x, y, words, { size = 11, font = 'F1', matrix = null, mode = 0 } = {}) => `BT ${mode ? `${mode} Tr ` : ''}/${font} ${size} Tf ${matrix
  ? `${matrix.join(' ')} ${x} ${y} Tm` : `${x} ${y} Td`} (${pdfText(words)}) Tj ET`;
const lines = (texts, { x = 56, top = 740, step = 14, size = 11, font = 'F1', mode = 0 } = {}) => texts.map((words, k) => line(x, top - k * step, words, { size, font, mode })).join('\n');


// --- the walk's own judge of a chosen quote (DECISIONS D368, rounds 3 and 5) ------------------------------------------
// The walk's own reading of a document, as readDocument gives it: one list of items per page. An item is a bare string
// (no geometry), or {str, transform, width, hasEOL} as the library gives it; EOL after an item marks it hasEOL.
const EOL = Symbol('hasEOL');
function items(...parts) {
  const list = [];
  for (const part of parts) {
    if (part !== EOL) {
      list.push(typeof part === 'string' ? part : { hasEOL: false, ...part });
    } else if (typeof list[list.length - 1] === 'string') {
      list[list.length - 1] = { str: list[list.length - 1], hasEOL: true };
    } else if (list.length) {
      list[list.length - 1].hasEOL = true;
    } else {
      list.push({ str: '', hasEOL: true });
    }
  }
  return list;
}

// An item drawn upright at (x, y) in size s, its advance `width` (all in PDF units), as the library gives it.
const at = (str, s, x, y, width, more = {}) => ({ str, transform: [s, 0, 0, s, x, y], width, hasEOL: false, ...more });

// A document as the walk reads it: pages of 612 x 792 PDF units, upright, each its list of items.
function documentOf(...pages) {
  return { pageCount: pages.length, pages: pages.map((list, index) => ({ number: index + 1, view: [0, 0, 612, 792], rotate: 0,
    userUnit: 1, items: list, styles: {} })) };
}

// Where the library's text layer puts an item's span on a page box `size` CSS px wide (its centre a half of the item's
// width along the item and (ascent - 0.5) x its height square to that, up the glyphs; the ascent 0.8), as readPdfPage
// reads its box.
function boxOf(item, page, size = [612, 792], ascent = 0.8) {
  const t = item.transform;
  const quarter = page.rotate % 180 === 90;
  const scale = size[0] / ((quarter ? page.view[3] - page.view[1] : page.view[2] - page.view[0]) * (page.userUnit || 1));
  const m = walk.viewportTransform(page.view, page.rotate, page.userUnit, scale);
  const unit = scale * (page.userUnit || 1);
  const point = (x, y) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
  const vector = (x, y) => [m[0] * x + m[2] * y, m[1] * x + m[3] * y];
  const height = Math.hypot(t[2], t[3]);
  const [ox, oy] = point(t[4], t[5]);
  const d = vector(t[0], t[1]);
  const u = [d[1], -d[0]];
  const [dl, ul] = [Math.hypot(...d), Math.hypot(...u)];
  const along = (item.width / 2) * unit;
  const across = height * (ascent - 0.5) * unit;
  const cx = ox + (d[0] / dl) * along + (u[0] / ul) * across;
  const cy = oy + (d[1] / dl) * along + (u[1] / ul) * across;
  return [cx - (item.width * unit) / 2, cy - (height * unit) / 2, item.width * unit, height * unit];
}

// The text layer a correct viewer draws for page `number` of a document, as readPdfPage reads it: a span for each item
// whose string is not '' (flagged where the walk's own copies are, placed where the library's text layer puts it; a bare
// string has no box), and a <br> after each item marked hasEOL.
function layerOf(document, number = 1, size = [612, 792]) {
  const page = document.pages[number - 1];
  const copies = walk.overprintCopies(page.items);
  const tokens = [];
  page.items.forEach((item, index) => {
    const str = typeof item === 'string' ? item : item.str;
    if (str) tokens.push({ kind: 'item', text: str, copy: copies.has(index), box: item.transform ? boxOf(item, page, size) : null, family: 'sans-serif' });
    if (typeof item === 'object' && item.hasEOL) tokens.push({ kind: 'br' });
  });
  return tokens;
}

// A page's canvas as readPdfPage measures a drawn one, and a page drawn with that canvas, its layer and these marks.
const DRAWN = { present: true, visible: true, pixels: 100000, opaque: 1, paper: 255, low: 40, threshold: 180, ink: 3000, markPixels: 100, markContent: 40 };
function drawn(number, tokens, marks = [], canvas = DRAWN) {
  return { number, drawn: true, size: [612, 792], tokens, marks, ascent: { 'sans-serif': 0.8 }, canvas };
}

// The marks of `words` (each [span, its text, occurrence], the n-th time that text is in that span counting from 0 as a
// fourth element) in a page's tokens, as readPdfPage gives them: the span and the offsets in its text.
function marked(tokens, ...words) {
  const spans = tokens.filter(token => token.kind === 'item');
  return words.map(([span, text, occurrence, nth = 0]) => {
    let start = -1;
    for (let k = 0; k <= nth; k += 1) start = spans[span].text.indexOf(text, start + 1);
    assert.ok(start >= 0, `${text} in span ${span}`);
    return { item: span, occurrence, start, end: start + text.length };
  });
}

// What the viewer showed for one chosen quote in a drawn PDF (chooseQuotes' reading): its state, the walk's own reading of
// the document, the pages read and how each page it requires drawn was seen (by default exactly as its canvas).
const SEEN = { blocks: 400, tiles: 1, paperBlocks: 300, paperDifference: 0, inkBlocks: 100, inkCanvas: 8000, inkScreen: 8000 };
function pdfReading(document, pages, fields = {}) {
  return { mode: 'pdf', fallback: '', marked: 'L1#0', status: 'marked', pages: [1], count: 1, note: 'Marked on page 1.',
    pageCount: document.pageCount, drawn: pages.map(item => item.number), document,
    pagesRead: new Map(pages.map(item => [item.number, item])), seen: new Map(pages.map(item => [item.number, SEEN])), ...fields };
}

// The walk's own search over a document: its result and the note it requires.
function search(quote, document) {
  const result = walk.ownSearch(quote, walk.documentModels(document), document.pageCount);
  return { ...result, note: walk.pdfQuoteNote(result) };
}
const find = (text, ...pages) => search({ text, page: 1 }, documentOf(...pages));

test('the walk reads a PDF itself, in Node, with the pinned library: the page count, each page\'s box and its items', async () => {
  // D368 round 5 (B2): the library the page draws with, in the walk's own process; no browser
  const { syntheticPdf, SYNTHETIC_DOCUMENTS } = require('./dev_preview_server.cjs');
  const source = SYNTHETIC_DOCUMENTS['synthetic-egd-colonoscopy.pdf'].pages;
  const read = await walk.readDocument(syntheticPdf(source));
  assert.equal(read.error, undefined);
  assert.equal(read.pageCount, 2);
  assert.deepEqual([read.pages[0].view, read.pages[0].rotate, read.pages[0].userUnit], [[0, 0, 612, 792], 0, 1]);
  // one item per drawn line, in order, each ending its line, at the line's origin (Helvetica 11 pt, 16 pt apart)
  assert.deepEqual(read.pages.map(page => page.items.map(item => item.str)), source);
  assert.deepEqual(read.pages[0].items.slice(0, 2).map(item => [item.transform, item.hasEOL]), [[[11, 0, 0, 11, 56, 740], true], [[11, 0, 0, 11, 56, 724], true]]);
  assert.ok(read.pages[0].items.every(item => item.width > 0 && typeof item.fontName === 'string'));
  // a page's box, rotation and user unit as the PDF gives them (a CropBox with its own origin, /Rotate 90, /UserUnit 2)
  const turned = await walk.readDocument(pdfOf([{ stream: line(90, 700, 'A line of a cropped page.'), crop: [50, 60, 562, 752] },
    { stream: line(56, 700, 'A line of a turned page.'), rotate: 90 }, { stream: line(28, 370, 'A line in user units.', { size: 5.5 }), media: [0, 0, 306, 396], userUnit: 2 }]));
  assert.deepEqual(turned.pages.map(page => [page.view, page.rotate, page.userUnit]),
    [[[50, 60, 562, 752], 0, 1], [[0, 0, 612, 792], 90, 1], [[0, 0, 306, 396], 0, 2]]);
  // what the library refuses is an error, not a reading
  assert.match((await walk.readDocument(Buffer.from('not a PDF at all'))).error, /refused it/);
  // the library's width for text whose matrix is turned 90 degrees is the advance along the text, as for upright text (R2b)
  const pain = await walk.readDocument(pdfOf([[line(56, 700, 'pain'), line(300, 100, 'pain', { matrix: [0, 1, -1, 0] })].join('\n')]));
  const [upright, rotated] = pain.pages[0].items.filter(item => item.str === 'pain');
  assert.deepEqual(rotated.transform, [0, 11, -11, 0, 300, 100]);
  assert.equal(rotated.width, upright.width);
});

test('the library\'s viewport, as the walk computes it, is the page\'s own: rotations, a box with its own origin, a user unit', async () => {
  const pdfjs = await import(require('node:url').pathToFileURL(path.join(walk.PDF_LIBRARY, 'legacy', 'build', 'pdf.min.mjs')).href);
  const pages = [{ stream: 'BT ET', rotate: 0 }, { stream: 'BT ET', rotate: 90 }, { stream: 'BT ET', rotate: 180 }, { stream: 'BT ET', rotate: 270 },
    { stream: 'BT ET', crop: [50, 60, 562, 752] }, { stream: 'BT ET', media: [0, 0, 306, 396], userUnit: 2, rotate: 90 }];
  const task = pdfjs.getDocument({ data: new Uint8Array(pdfOf(pages)), isEvalSupported: false, useWasm: false, verbosity: 0 });
  try {
    const document = await task.promise;
    for (let number = 1; number <= pages.length; number += 1) {
      const page = await document.getPage(number);
      for (const scale of [0.8, 1.5]) {
        assert.deepEqual(walk.viewportTransform(page.view, page.rotate, page.userUnit, scale).map(value => Math.round(value * 1e6) / 1e6),
          page.getViewport({ scale }).transform.map(value => Math.round(value * 1e6) / 1e6), `page ${number} at ${scale}`);
      }
    }
  } finally {
    await task.destroy();
  }
});

test('R1: an overprint copy is the same string at the same height, near an earlier item\'s origin; any earlier item, at linear cost', t => {
  const copies = list => [...walk.overprintCopies(list)];
  // fake bold: the same line drawn again 0.3 pt to the right
  assert.deepEqual(copies([at('DIAGNOSIS: TUBULAR ADENOMA.', 11, 56, 700, 160), at('DIAGNOSIS: TUBULAR ADENOMA.', 11, 56.3, 700, 160)]), [1]);
  // any earlier item: a line printer's overstrike of nine items is found item by item, beyond any window
  const nine = dx => ['IMPRESSION:', ' ', 'TWO', ' ', 'POLYPS', ' ', 'WERE', ' ', 'REMOVED.'].map((str, k) => at(str, 9, 56 + dx + k * 30, 700, str.length * 5.4));
  assert.deepEqual(copies([...nine(0), ...nine(0.2)]), [9, 11, 13, 15, 17], 'every copy with a character that is not white space');
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), ...Array(40).fill(at('x', 10, 300, 100, 5)), at('Polyp', 10, 50.5, 700, 26)]).filter(index => index > 40), [41]);
  // the heights agree within 1% of the larger: the same string at another size at the same place is no copy (verify-4 gap 1)
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 24, 50, 700, 62)]), []);
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 10.1, 50, 700, 26)]), [1], 'within 1%');
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 10.11, 50, 700, 26)]), [], 'beyond 1%');
  // within max(1, 0.2 x the later item's height), in a straight line
  assert.deepEqual(copies([at('Polyp', 4, 50, 700, 10), at('Polyp', 4, 50, 701, 10)]), [1], '1.0 at 4 pt: max(1, 0.8)');
  assert.deepEqual(copies([at('Polyp', 4, 50, 700, 10), at('Polyp', 4, 50.75, 700.75, 10)]), [], 'a straight line of 1.06, though each axis is within 1.0');
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 10, 50, 702, 26)]), [1], '2.0 at 10 pt: 0.2 x 10');
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 10, 50, 702.125, 26)]), [], 'beyond 2.0');
  assert.deepEqual(copies([at('Polyp', 10, 50, 700, 26), at('Polyp', 10, 51.5, 701.5, 26)]), [], 'a straight line of 2.12, though each axis is within 2.0');
  assert.deepEqual(copies([at('Polyp', 20, 50, 700, 52), at('Polyp', 20, 53.9, 700, 52)]), [1], '0.2 x 20 pt = 4');
  assert.deepEqual(copies([at('Polyp', 20, 50, 700, 52), at('Polyp', 20, 54.1, 700, 52)]), []);
  assert.deepEqual(copies([at('Polyp', 20, 50, 700, 52), at('Polyp', 19.9, 53.99, 700, 52)]), [], 'the later item\'s own height: 3.99 is past 0.2 x 19.9');
  // NFKC on both sides; white space alone is never a copy; a bare string has no geometry and is never one
  assert.deepEqual(copies([at('ﬁnding', 10, 50, 700, 26), at('finding', 10, 50.2, 700, 26)]), [1]);
  assert.deepEqual(copies([at('   ', 10, 50, 700, 9), at('   ', 10, 50, 700, 9)]), []);
  assert.deepEqual(copies(['Polyp', 'Polyp', at('Polyp', 10, 50, 700, 26)]), []);
  // a copy of a copy, and three drawings: every later one
  assert.deepEqual(copies([at('FINDINGS', 11, 56, 670, 50), at('FINDINGS', 11, 56.25, 670, 50), at('FINDINGS', 11, 56.5, 670, 50)]), [1, 2]);
  // cost (ROUND5 R1): a page of 20,000 items, 2,000 strings drawn 10 times each at distinct places, and a page of 20,000
  // identical strings at distinct places, each made ready in well under a second (bound: 1000 ms)
  const many = Array.from({ length: 20000 }, (_, k) => at(`term ${k % 2000}`, 10, 20 + (k % 100) * 5.5, 20 + Math.floor(k / 100) * 3.7, 30));
  const same = Array.from({ length: 20000 }, (_, k) => at('same words', 10, 20 + (k % 200) * 2.9, 20 + Math.floor(k / 200) * 7.3, 30));
  for (const [what, list] of [['2,000 strings x 10', many], ['20,000 identical strings', same]]) {
    const started = process.hrtime.bigint();
    const model = walk.pageModel(1, list);
    const ms = Number(process.hrtime.bigint() - started) / 1e6;
    assert.equal(model.copies.size, 0, what);
    assert.ok(ms < 1000, `${what}: ${ms.toFixed(0)} ms`);
    t.diagnostic(`R1 cost, ${what}: ${ms.toFixed(0)} ms`);
  }
});

test('R2a: the number separators are pinned, and are exactly what Unicode\'s word boundaries join between two digits', () => {
  const pinned = [0x0027, 0x002C, 0x002E, 0x003B, 0x037E, 0x0589, 0x060C, 0x060D, 0x066C, 0x07F8, 0x2018, 0x2019, 0x2024, 0x2044,
    0xFE50, 0xFE52, 0xFE54, 0xFF07, 0xFF0C, 0xFF0E, 0xFF1B];
  assert.deepEqual([...walk.NUMBER_SEPARATORS].sort((a, b) => a - b), pinned);
  const words = new Intl.Segmenter('en', { granularity: 'word' });
  const segments = text => [...words.segment(text)].length;
  const joins = cp => segments(`1${String.fromCodePoint(cp)}2`) === 1 && segments(`1${String.fromCodePoint(cp)}`) === 2 && segments(`${String.fromCodePoint(cp)}2`) === 2;
  for (const cp of pinned) assert.ok(joins(cp), `U+${cp.toString(16)}`);
  // and no other: letters, digits, marks, format characters, connectors and unassigned, private and surrogate code points
  // join for other reasons or never (word-break classes ALetter, Numeric, Extend, Format, ExtendNumLet, Other), so every
  // other code point is asked
  const skip = /[\p{L}\p{N}\p{M}\p{Cf}\p{Pc}\p{Cn}\p{Co}]/u;
  const found = [];
  for (let cp = 0; cp <= 0x10ffff; cp += 1) {
    if (cp >= 0xd800 && cp <= 0xdfff) continue;
    if (!skip.test(String.fromCodePoint(cp)) && joins(cp)) found.push(cp);
  }
  assert.deepEqual(found, pinned, `ICU ${process.versions.icu}, Unicode ${process.versions.unicode}`);
});

test('R2a: a number\'s separator between two digits keeps them one word, at either end of an occurrence', () => {
  assert.equal(find('1 cm lesion', items('A 2.1 cm lesion was excised.')).count, 0, '(start, a)');
  assert.equal(find('.5 mg', items('Take 2.5 mg daily.')).count, 0, '(start, b)');
  assert.equal(find('Hemoglobin 12', items('Hemoglobin 12.5 g/dL')).count, 0, '(end, a)');
  assert.equal(find('2.', items('Take 2.5 mg.')).count, 0, '(end, b)');
  assert.equal(find('2,500 units', items('Heparin 2,500 units IV')).count, 1);
  assert.equal(find('1990', items('the 1990’s')).count, 1, 'a letter after the separator');
  assert.equal(find('5 mg', items('Dose 2. 5 mg later')).count, 1, 'a space after the point');
  assert.equal(find('５ mg', items('１２．５ mg')).count, 0, 'the page\'s code points as written: a fullwidth point between fullwidth digits');
  assert.equal(find('٥٠٠ mL', items('Loss ١٬٥٠٠ mL')).count, 0, 'an Arabic thousands separator between Arabic-Indic digits');
  assert.equal(find('5 mg', items('Dose 2‧5 mg')).count, 1, 'a hyphenation point is no number separator');
  // reading stops at an edge R2b makes: a digit on the far side of a separate drawing is no code point
  assert.equal(find('5 mg', items(at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 96, 700, 25))).count, 0, 'the drawings continue each other');
  assert.equal(find('5 mg', items(at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 50, 700, 25))).count, 1, 'the second jumps back');
});

test('R2b: two drawings with nothing between them meet at a word edge unless the second visibly continues the first', () => {
  // a raised, smaller footnote marker glued to a word is an edge on both sides
  const marker = items(at('Assessment: type 2 diabetes mellitus', 11, 56, 700, 190), at('1', 7, 246, 704, 3.9), at(', well controlled.', 11, 249.9, 700, 85));
  assert.equal(find('type 2 diabetes mellitus', marker).count, 1);
  assert.equal(find('mellitus1', marker).count, 1);
  // a word drawn in two fonts, continuously, stays one word; the library's join after fake bold jumps back: an edge
  assert.equal(find('pain', items(at('pain', 11, 56, 700, 20.2), at('less', 11, 76.2, 700, 18.3))).count, 0);
  assert.equal(find('Chest pain', items(at('Diagnosis: Chest pain', 11, 56, 700, 107), at('Chest pain since this morning.', 11, 111.3, 700, 150))).count, 2);
  // the limits: heights within 5%, the next origin within 0.25 x height of the end along, 0.1 x height across
  const pair = (second, width = 20) => find('pain', items(at('pain', 10, 56, 700, width), second));
  assert.equal(pair(at('less', 10.5, 76, 700, 18)).count, 0, 'heights 5% apart continue');
  assert.equal(pair(at('less', 10.6, 76, 700, 18)).count, 1, 'beyond 5%');
  assert.equal(pair(at('less', 10, 78.5, 700, 18)).count, 0, '2.5 along past the end continues');
  assert.equal(pair(at('less', 10, 78.6, 700, 18)).count, 1);
  assert.equal(pair(at('less', 10, 76, 701, 18)).count, 0, '1.0 across continues');
  assert.equal(pair(at('less', 10, 76, 701.1, 18)).count, 1);
  assert.equal(pair(at('less', 10, 76, 700, 18), 0).count, 1, 'no width: no usable geometry');
  assert.equal(find('pain', items(at('pain', 10, 56, 700, 20), 'less')).count, 1, 'a bare string meets an edge on each side');
  assert.equal(find('polyp', items('the', 'polyp', 's')).count, 1);
  // the text direction of a turned line (the library's width is the advance along it)
  assert.equal(find('pain', items({ str: 'pain', transform: [0, 11, -11, 0, 300, 100], width: 20.2 }, { str: 'less', transform: [0, 11, -11, 0, 300, 120.2], width: 18.3 })).count, 0);
  assert.equal(find('pain', items({ str: 'pain', transform: [0, 11, -11, 0, 300, 100], width: 20.2 }, { str: 'less', transform: [0, 11, -11, 0, 320.2, 100], width: 18.3 })).count, 1);
  // a line break or white space between the drawings is no seam: R2 reads them as it always did
  assert.equal(find('removed', items('one polyp', EOL, 'removed today')).count, 1);
  assert.equal(find('polyp', items(at('polyp ', 10, 56, 700, 30), at('removed', 10, 86, 700, 40))).count, 1);
});

test('R2c: a Han ideograph or a hiragana character is a word of its own; katakana stays a word part', () => {
  const chinese = items('患者有糖尿病史和高血压');
  assert.deepEqual([find('糖尿病', chinese).count, find('高血压', chinese).count], [1, 1]);
  assert.equal(find('高血圧', items('高血圧の治療')).count, 1);
  assert.equal(find('血圧', items('高血圧の治療')).count, 1, 'Han beside Han');
  assert.equal(find('Ａ型', items('Ａ型インフルエンザ')).count, 1, 'a quote that ends in Han asks for no edge');
  assert.equal(find('インフル', items('インフルエンザ')).count, 0, 'katakana beside katakana is one word');
  assert.equal(find('pain', items('pain漢')).count, 1, 'a Han ideograph after a Latin word is an edge');
  assert.equal(find('pain', items('painの')).count, 1, 'and a hiragana character');
  assert.equal(find('pain', items('painカ')).count, 0, 'a katakana character is a word part');
});

test('the shared examples of round 5 (ROUND5.md), each as the table counts it', () => {
  const nine = dx => ['IMPRESSION:', ' ', 'TWO', ' ', 'POLYPS', ' ', 'WERE', ' ', 'REMOVED.'].reduce((list, str) => {
    const x = list.length ? list[list.length - 1].transform[4] + list[list.length - 1].width : 56 + dx;
    return [...list, at(str, 9, x, 700, str.length * 5.4)];
  }, []);
  const rows = [
    [1, items('A 2.1 cm lesion was excised.'), [['1 cm lesion', 0]]],
    [2, items('Lisinopril 2.5 mg daily.'), [['5 mg daily', 0], ['2.5 mg daily', 1]]],
    [3, items('Hemoglobin 12.5 g/dL'), [['Hemoglobin 12', 0]]],
    [4, items('Estimated blood loss 1,500 mL.'), [['500 mL', 0], ['1,500 mL', 1]]],
    [5, items('1. Hypokalemia, potassium 3.1.'), [['1.', 1]]],
    [6, items('Take 2.5 mg.'), [['2.', 0]]],
    [7, items('A 15 mm polyp; a 5 mm polyp.'), [['5 mm', 1]]],
    [8, items('Sections 3.1.2 and 4.'), [['3.1', 0], ['3.1.2', 1]]],
    [9, items('Dose 2. 5 mg later'), [['5 mg', 1]]],
    [10, items('１２．５ mg'), [['５ mg', 0]]],
    [11, items('the 1990’s'), [['1990', 1]]],
    [12, items(at('Assessment: type 2 diabetes mellitus', 11, 56, 700, 190), at('1', 7, 246, 704, 3.9), at(', well controlled.', 11, 249.9, 700, 85)),
      [['type 2 diabetes mellitus', 1], ['mellitus1', 1]]],
    [13, items(at('pain', 11, 56, 700, 20.2), at('less', 11, 76.2, 700, 18.3)), [['pain', 0], ['painless', 1]]],
    [14, items(at('Diagnosis: Chest pain', 11, 56, 700, 107), at('Chest pain since this morning.', 11, 111.3, 700, 150)),
      [['Diagnosis: Chest pain', 1], ['Chest pain since this morning.', 1], ['Chest pain', 2]]],
    [15, items('the', 'polyp', 's'), [['polyp', 1]]],
    [16, items(at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 96, 700, 25)), [['5 mg', 0]]],
    [17, items(at('Total 12', 10, 56, 700, 40), at('.5 mg', 10, 50, 700, 25)), [['5 mg', 1]]],
    [18, items('患者有糖尿病史和高血压'), [['糖尿病', 1], ['高血压', 1]]],
    [19, items('高血圧の治療'), [['高血圧', 1]]],
    [20, items({ str: 'pain', transform: [0, 11, -11, 0, 300, 100], width: 20.2 }, { str: 'less', transform: [0, 11, -11, 0, 300, 120.2], width: 18.3 }), [['pain', 0]]],
    [21, items(...nine(0), ...nine(0.2)), [['TWO POLYPS', 1], ['IMPRESSION: TWO POLYPS WERE REMOVED.', 1]]],
    [22, items(at('Polyp', 10, 50, 700, 26), at('Polyp', 24, 50, 700, 62)), [['Polyp', 2]]],
  ];
  assert.equal(rows.length, 22);
  for (const [row, page, quotes] of rows) {
    for (const [text, count] of quotes) assert.equal(find(text, page).count, count, `row ${row}: ${text}`);
  }
});

test('the walk\'s own search: white space and NFKC ignored, exact case first, every occurrence, the quote\'s page and the next, never another', () => {
  const page1 = items('Patchy erythema was seen in the gastric antrum.', EOL, 'Cold forceps biopsies were taken from the gastric antrum.', EOL);
  const page2 = items('Colonoscopy: The colonoscope was advanced to the cecum.', EOL, 'Impression: antral erythema.');
  const document = documentOf(page1, page2);
  const one = search({ text: 'Cold  forceps\nbiopsies were taken', page: 1 }, document);
  assert.deepEqual([one.status, one.scope, one.caseBlind, one.count, one.pages, one.note], ['marked', 'page', false, 1, [1], 'Marked on page 1.']);
  assert.equal(search({ text: 'Coldforcepsbiopsies', page: 1 }, document).count, 1, 'white space ignored entirely');
  assert.equal(find('ﬁ', items('the fi glyph')).count, 1, 'NFKC on both sides');
  const twice = search({ text: 'the gastric antrum.', page: 1 }, document);
  assert.deepEqual([twice.count, twice.note], [2, 'These words appear 2 times on page 1. Each is marked.']);
  const blind = search({ text: 'PATCHY ERYTHEMA WAS SEEN', page: 1 }, document);
  assert.deepEqual([blind.status, blind.caseBlind, blind.count], ['marked', true, 1]);
  assert.deepEqual([find('cold snare', items('cold snare and COLD SNARE')).count, find('cold snare', items('cold snare and COLD SNARE')).caseBlind], [1, false]);
  const run = search({ text: 'taken from the gastric antrum. Colonoscopy: The colonoscope was advanced', page: 1 }, document);
  assert.deepEqual([run.scope, run.count, run.pages, run.note], ['continued', 1, [1, 2], 'Marked on page 1, continuing onto page 2.']);
  const elsewhere = search({ text: 'Impression: antral erythema.', page: 1 }, document);
  assert.deepEqual([elsewhere.status, elsewhere.pages, elsewhere.note], ['not_found', [],
    'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.'], 'never another page');
  const anywhere = search({ text: 'antral erythema', page: null }, document);
  assert.deepEqual([anywhere.scope, anywhere.pages, anywhere.note], ['document', [2], 'Marked on page 2.']);
  assert.equal(search({ text: 'erythema', page: null }, document).note, 'These words appear 2 times, on pages 1 and 2. Each is marked.');
  assert.deepEqual([search({ text: 'x', page: 3 }, document).status, search({ text: 'x', page: 3 }, document).note],
    ['missing_page', 'This passage names page 3, but the document has 2 pages. Nothing is marked.']);
  assert.equal(search({ text: '  ​ ', page: 1 }, document).note, 'This passage has no words to mark.');
  // R2 kept: a letter, a digit or a mark beside an occurrence turns it away, read in the page's text as written
  const words = items('The patient was told to bathe ending the preparation at noon.', EOL, 'Findings: the end of the procedure was uneventful.', EOL,
    'Mild pain was reported; the abdomen was painless on palpation.', EOL, 'A 5 mm polyp was found; polypectomy was performed; no other polyps.');
  assert.deepEqual(['the end', 'pain', 'polyp'].map(text => find(text, words).count), [1, 1, 1]);
  assert.equal(find('not able', items('It was notable.')).count, 1, 'white space inside the quote stays ignored');
  assert.equal(find('.', items('a. b.')).count, 2, 'punctuation at both ends asks for no edge');
  assert.equal(find('clair', items('éclair')).status, 'not_found', 'a combining mark before');
  assert.equal(find('Botox', items('Botox™ was given.')).count, 1, 'a trade mark sign after it is an edge, though NFKC writes it "TM"');
  assert.equal(find('polyp', items('⑴polyp')).status, 'not_found', 'a parenthesised digit before is a digit');
  assert.equal(search({ text: 'antrum. Colon', page: 1 }, documentOf(items('the gastric antrum.'), items('Colonoscopy: advanced.'))).status, 'not_found');
  // R3: format characters are dropped from both sides
  for (const mark of ['­', '​', '‌', '‍', '⁠', '‎', '﻿']) {
    assert.equal(find(`alpha${mark}beta`, items('alphabeta was seen')).count, 1, `U+${mark.codePointAt(0).toString(16)}`);
  }
  assert.equal(find('alphabeta', items('alpha­beta')).count, 1);
  // R1 in the search: a copy is left out, its line break kept; a passage runs across it
  const bold = items(at('polyp', 10, 10, 700, 26), { ...at('polyp', 10, 10.3, 700, 26), hasEOL: true }, at('removed today', 10, 10, 686, 60));
  assert.deepEqual([find('polyp', bold).count, find('removed', bold).count, find('polyp removed', bold).count], [1, 1, 1]);
});

test('the notes when nothing is found: N1 where the page has searchable text, N2 where it has none, character for character', () => {
  const text = items('Bowel preparation was rated adequate.');
  assert.equal(search({ text: 'absent words', page: 1 }, documentOf(text)).note,
    'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.');
  assert.equal(search({ text: 'absent words', page: null }, documentOf(text)).note,
    'The exact words were not found in the searchable text of this document, so nothing is marked.');
  for (const page of [items(), items(' ', EOL, ' ')]) {
    assert.equal(search({ text: 'absent words', page: 1 }, documentOf(page, text)).note,
      'Page 1 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 1 is shown.');
  }
  assert.equal(search({ text: 'absent words', page: null }, documentOf(items(), items(' '))).note,
    'This document has no text the viewer can search (it may be a scanned image), so nothing is marked.');
  assert.equal(search({ text: 'absent words', page: null }, documentOf(items(), text)).note,
    'The exact words were not found in the searchable text of this document, so nothing is marked.');
});

test('a chosen quote is judged against the walk\'s own reading: the viewer\'s marks, count, pages and note held to it, never taken at its word', () => {
  const document = documentOf(items(at('Patchy erythema was seen in the gastric antrum.', 11, 56, 740, 240, { hasEOL: true }),
    at('Cold forceps biopsies were taken from the gastric antrum.', 11, 56, 724, 290, { hasEOL: true }), at('COLD FORCEPS BIOPSIES WERE TAKEN.', 11, 56, 708, 220)));
  const tokens = layerOf(document);
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken', page: 1 };
  const right = marked(tokens, [1, 'Cold forceps biopsies were taken', 0]);
  const judge = (marks, fields = {}, pages = [drawn(1, tokens, marks)]) => walk.judgeQuote(quote, pdfReading(document, pages, fields));
  assert.deepEqual(judge(right), { outcome: 'once', off_page: 0, mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0, no_text: false, pages: 0,
    layers: 0, misaligned: 0, unseen: 0, problems: [] });
  // "not found" passes only where the walk finds nothing either (FM-4 M1, RCW-2 a)
  const silent = judge([], { status: 'not_found', pages: [], count: 0, note: 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.' });
  assert.deepEqual([silent.outcome, silent.missed], ['unresolved', 1]);
  assert.match(silent.problems.join(), /the viewer says not_found, the walk's own search finds 1/);
  // the case, the count, other words, more than the words
  const capitals = judge([...right, ...marked(tokens, [2, 'COLD FORCEPS BIOPSIES WERE TAKEN', 1])], { count: 2, note: 'These words appear 2 times on page 1. Each is marked.' });
  assert.deepEqual([capitals.outcome, capitals.mismatched, capitals.missed], ['unresolved', 1, 0]);
  assert.equal(judge(marked(tokens, [2, 'COLD FORCEPS BIOPSIES WERE TAKEN', 0])).mismatched, 1);
  const twiceQuote = { ...quote, text: 'the gastric antrum.' };
  const both = marked(tokens, [0, 'the gastric antrum.', 0], [1, 'the gastric antrum.', 1]);
  assert.equal(walk.judgeQuote(twiceQuote, pdfReading(document, [drawn(1, tokens, both)], { count: 2, note: 'These words appear 2 times on page 1. Each is marked.' })).outcome, 'multi');
  const first = walk.judgeQuote(twiceQuote, pdfReading(document, [drawn(1, tokens, both.slice(0, 1))]));
  assert.deepEqual([first.outcome, first.missed], ['unresolved', 1]);
  assert.equal(judge(marked(tokens, [1, 'Cold forceps biopsies were', 0])).mismatched, 1);
  assert.equal(judge(marked(tokens, [1, 'Cold forceps biopsies were taken from', 0])).mismatched, 1);
  // the note, exactly
  assert.match(judge(right, { note: 'Marked.' }).problems.join(), /the note does not say what was done, as written/);
  // the reason names quotes by their line and page, never by their words
  assert.ok(!silent.problems.join().includes(quote.text));
  // the walk could not read the document: nothing it can hold the viewer to
  assert.match(walk.judgeQuote(quote, { ...pdfReading(document, [drawn(1, tokens, right)]), document: { error: 'the PDF library refused it (x)' } }).problems.join(),
    /could not read the PDF itself \(the PDF library refused it/);
});

test('B4: the viewer\'s page count, each drawn page\'s text layer and its overprint flags are held to the walk\'s own reading, both ways', () => {
  const document = documentOf(items(at('Cold forceps biopsies were taken.', 11, 56, 740, 170, { hasEOL: true }), at('Bowel preparation was adequate.', 11, 56, 724, 160)),
    items(at('A second page of the fictional report.', 11, 56, 740, 190)));
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const tokens = layerOf(document);
  const right = marked(tokens, [0, 'Cold forceps biopsies were taken.', 0]);
  const pages = [drawn(1, tokens, right), drawn(2, layerOf(document, 2))];
  assert.equal(walk.judgeQuote(quote, pdfReading(document, pages)).outcome, 'once');
  // the page count: a viewer that drops the last page (R3CS-4) or adds one
  for (const count of [1, 3]) {
    const judged = walk.judgeQuote(quote, pdfReading(document, pages, { pageCount: count }));
    assert.deepEqual([judged.outcome, judged.pages], ['unresolved', 1]);
    assert.match(judged.problems.join(), new RegExp(`the viewer shows ${count} page\\(s\\); the document has 2`));
  }
  // and the walk's search, its pages and its notes go by its own count (B3): a viewer one page short that says the
  // quote's page is missing is told the words are on that page
  const second = { ...quote, text: 'A second page of the fictional report.', page: 2 };
  const short = walk.judgeQuote(second, pdfReading(document, [drawn(1, tokens)], { pageCount: 1, status: 'missing_page', pages: [], count: 0,
    note: 'This passage names page 2, but the document has 1 page. Nothing is marked.' }));
  assert.match(short.problems.join(), /the viewer says missing_page, the walk's own search finds 1/);
  assert.match(short.problems.join(), /the note does not say what was done, as written/);
  // the text layer: each span the next item with text, in order - read from the next page, a span dropped, one changed
  const layer = edit => walk.judgeQuote(quote, pdfReading(document, [drawn(1, edit(structuredClone(tokens)), right), pages[1]]));
  for (const [what, edit] of [['the next page\'s text', () => layerOf(document, 2)], ['a span dropped', list => list.slice(1)],
    ['a span changed', list => { list[2].text = 'Bowel preparation was poor.'; return list; }], ['a span added', list => [...list, { kind: 'item', text: 'x', copy: false, box: [1, 1, 1, 1] }]]]) {
    const judged = layer(edit);
    assert.equal(judged.layers, 1, what);
    assert.match(judged.problems.join(), /the text layer of page 1 is not the document's text/, what);
  }
  // the overprint flags equal the walk's own copies, both ways: a flag on real text, and a copy without its flag (R3CS-5)
  const bold = documentOf(items(at('DIAGNOSIS: TUBULAR ADENOMA.', 11, 56, 700, 160), at('DIAGNOSIS: TUBULAR ADENOMA.', 11, 56.3, 700, 160, { hasEOL: true }),
    at('The procedure was uneventful.', 11, 56, 680, 140)));
  const boldTokens = layerOf(bold);
  assert.deepEqual(boldTokens.filter(token => token.kind === 'item').map(token => token.copy), [false, true, false]);
  const boldQuote = { ...quote, text: 'DIAGNOSIS: TUBULAR ADENOMA.' };
  const boldMarks = marked(boldTokens, [0, 'DIAGNOSIS: TUBULAR ADENOMA.', 0]);
  assert.equal(walk.judgeQuote(boldQuote, pdfReading(bold, [drawn(1, boldTokens, boldMarks)])).outcome, 'once');
  const unflagged = structuredClone(boldTokens);
  unflagged[1].copy = false;
  const missing = walk.judgeQuote(boldQuote, pdfReading(bold, [drawn(1, unflagged, boldMarks)]));
  assert.deepEqual([missing.outcome, missing.flags], ['unresolved', 1]);
  assert.match(missing.problems.join(), /1 overprint cop\(ies\) of page 1 are not flagged/);
  const extra = structuredClone(boldTokens);
  extra[3].copy = true;
  const flagged = walk.judgeQuote(boldQuote, pdfReading(bold, [drawn(1, extra, boldMarks)]));
  assert.match(flagged.problems.join(), /1 span\(s\) of page 1 are flagged as an overprint copy and are not one/);
  // the same string at another size at the same place is no copy (verify-4 gap 1): a viewer that does not flag it passes
  const sizes = documentOf(items(at('Polyp', 10, 50, 700, 26), at('Polyp', 24, 50, 700, 62)));
  const sizeTokens = layerOf(sizes);
  assert.equal(walk.judgeQuote({ ...quote, text: 'Polyp' }, pdfReading(sizes, [drawn(1, sizeTokens, marked(sizeTokens, [0, 'Polyp', 0], [1, 'Polyp', 1]))],
    { count: 2, note: 'These words appear 2 times on page 1. Each is marked.' })).outcome, 'multi');
  // a mark in a copy is refused
  const inCopy = walk.judgeQuote(boldQuote, pdfReading(bold, [drawn(1, boldTokens, [...boldMarks, ...marked(boldTokens, [1, 'DIAGNOSIS: TUBULAR ADENOMA.', 0])])]));
  assert.match(inCopy.problems.join(), /an overprint copy is marked/);
});

test('B4: every marked span lies where its item is drawn: shifted 8 pt or 22 px down, a line up or scaled 6% larger, it fails', () => {
  const lines = ['Indication: surveillance of a fictional polyp.', 'Cold forceps biopsies were taken from the antrum.', 'Impression: two small polyps were removed.'];
  const document = documentOf(items(...lines.map((text, k) => at(text, 11, 56, 500 - k * 14, text.length * 5.6, { hasEOL: true }))));
  const quote = { code: '43239', line: 'L1', text: lines[1], page: 1 };
  const tokens = layerOf(document);
  const marks = marked(tokens, [1, lines[1], 0]);
  const judge = move => {
    const moved = structuredClone(tokens);
    for (const token of moved) if (token.box) token.box = move(token.box);
    return walk.judgeQuote(quote, pdfReading(document, [drawn(1, moved, marks)]));
  };
  assert.equal(judge(box => box).outcome, 'once');
  assert.equal(judge(([x, y, w, h]) => [x + 2, y + 2, w, h]).outcome, 'once', '2 CSS px either way is within the tolerance');
  for (const [what, move] of [['8 pt down', ([x, y, w, h]) => [x, y + 8, w, h]], ['22 px down', ([x, y, w, h]) => [x, y + 22, w, h]],
    ['a line up', ([x, y, w, h]) => [x, y - 14, w, h]], ['scaled 6% larger', ([x, y, w, h]) => [x * 1.06, y * 1.06, w * 1.06, h * 1.06]],
    ['moved past the run', ([x, y, w, h]) => [x + w * 0.75, y, w, h]]]) {
    const judged = judge(move);
    assert.deepEqual([judged.outcome, judged.misaligned], ['unresolved', 1], what);
    assert.match(judged.problems.join(), /1 marked span\(s\) of page 1 do not lie where their words are drawn/, what);
  }
  // the place, computed on a turned page, a box with its own origin and a user unit, from the library's own geometry
  for (const page of [{ view: [0, 0, 612, 792], rotate: 90, userUnit: 1 }, { view: [50, 60, 562, 752], rotate: 180, userUnit: 1 },
    { view: [0, 0, 306, 396], rotate: 270, userUnit: 2 }]) {
    const item = at('Cold forceps biopsies were taken.', 11, 90, 300, 170);
    const size = page.rotate % 180 ? [792 * 0.7, 612 * 0.7] : [612 * 0.7, 792 * 0.7];
    const place = walk.spanPlacement(item, boxOf(item, page, size), page, size, 0.8);
    assert.ok(walk.placedRight(place), JSON.stringify(place));
    assert.ok(!walk.placedRight(walk.spanPlacement(item, boxOf({ ...item, transform: [11, 0, 0, 11, 90, 292] }, page, size), page, size, 0.8)), `8 pt off on ${page.rotate}`);
  }
  // a slanted font (the transform sheared, as a made-up italic): the text layer turns the span by the direction alone
  const italic = { str: 'Cold forceps biopsies were taken.', transform: [11, 0, 2.3, 11, 90, 300], width: 170, hasEOL: false };
  assert.ok(walk.placedRight(walk.spanPlacement(italic, boxOf(italic, document.pages[0]), document.pages[0], [612, 792], 0.8)));
  // a vertical font, or an item with no height, is not placed (and not counted)
  assert.equal(walk.spanPlacement(at('x', 0, 1, 1, 1), [0, 0, 1, 1], document.pages[0], [612, 792], 0.8), null);
  assert.equal(walk.spanPlacement({ ...at('x', 10, 1, 1, 5), fontName: 'v' }, [0, 0, 1, 1], { ...document.pages[0], styles: { v: { vertical: true } } }, [612, 792], 0.8), null);
});

test('S5: every run of an occurrence\'s marked text is read at both ends, so a cut inside a character is seen', () => {
  const quote = { code: '43239', line: 'L1', text: 'Jose Garcia', page: 1 };
  // RCW-3: the accent is an item of its own and left unmarked between two marked parts of one occurrence
  const document = documentOf(items('The patient ', 'Jose', '́', ' ', 'Garcia', ' was seen.'));
  const tokens = layerOf(document);
  const cut = walk.judgeQuote(quote, pdfReading(document, [drawn(1, tokens, marked(tokens, [1, 'Jose', 0], [4, 'Garcia', 0]))]));
  assert.equal(cut.cut, 1);
  assert.match(cut.problems.join(), /1 marked part\(s\) begin or end inside a character/);
  const whole = walk.judgeQuote({ ...quote, text: 'José Garcia' }, pdfReading(document, [drawn(1, tokens, marked(tokens, [1, 'Jose', 0], [2, '́', 0], [4, 'Garcia', 0]))]));
  assert.deepEqual([whole.outcome, whole.cut], ['once', 0]);
  const jamo = documentOf(items('가', 'ᆫ', ' and more'));
  const jamoTokens = layerOf(jamo);
  assert.equal(walk.judgeQuote({ ...quote, text: '간' }, pdfReading(jamo, [drawn(1, jamoTokens, marked(jamoTokens, [0, '가', 0]))])).cut, 1);
  assert.equal(walk.judgeQuote({ ...quote, text: '간' }, pdfReading(jamo, [drawn(1, jamoTokens, marked(jamoTokens, [0, '가', 0], [1, 'ᆫ', 0]))])).cut, 0);
});

test('S3, B5 and B6: a page the quote requires is drawn, shows ink where it has text and under its marks, and is seen as drawn', () => {
  const document = documentOf(items(at('Cold forceps biopsies were taken.', 11, 56, 740, 170)), items());
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const tokens = layerOf(document);
  const marks = marked(tokens, [0, 'Cold forceps biopsies were taken.', 0]);
  const withCanvas = (canvas, seen = SEEN) => walk.judgeQuote(quote, pdfReading(document, [drawn(1, tokens, marks, canvas), drawn(2, [])], { seen: new Map([[1, seen]]) }));
  assert.equal(withCanvas(DRAWN).outcome, 'once');
  for (const [canvas, said] of [[{ ...DRAWN, opaque: 0, ink: 0, markContent: 0 }, /its canvas is not drawn/], [{ ...DRAWN, visible: false }, /its canvas is not shown/],
    [{ present: false }, /it has no canvas/], [{ ...DRAWN, markContent: 4 }, /nothing is drawn under its marks/], [{ ...DRAWN, error: 'SecurityError' }, /could not be read/],
    [{ ...DRAWN, ink: 0, markContent: 0 }, /its canvas shows no ink, though the page has text/]]) {
    const judged = withCanvas(canvas);
    assert.deepEqual([judged.outcome, judged.blank], ['unresolved', 1], said.source);
    assert.match(judged.problems.join(), said);
  }
  assert.equal(walk.canvasProblem({ ...DRAWN, markContent: 5 }, true, true), '', `${walk.CANVAS_MARK_CONTENT_MIN} of the pixels under the marks`);
  assert.equal(walk.canvasProblem({ ...DRAWN, ink: 20 }, false, true), '', `${walk.INK_SHARE_MIN} of the canvas`);
  assert.match(walk.canvasProblem({ ...DRAWN, ink: 19 }, false, true), /no ink/);
  // seen (B5): what the member sees against the canvas, block by block outside the marks - its paper where the canvas
  // has no ink, and the canvas's ink where it has some
  for (const [seen, said] of [[{ ...SEEN, paperDifference: 2.1 * 300 }, /what the member sees of it is not its drawing/],
    [{ ...SEEN, inkScreen: 0.59 * 8000 }, /what the member sees of it is not its drawing/], [{ ...SEEN, blocks: 0 }, /none of it was in view/],
    [{ error: 'the page moved while it was looked at' }, /it could not be seen \(the page moved/], [null, /it was not looked at/]]) {
    const judged = withCanvas(DRAWN, seen);
    assert.deepEqual([judged.outcome, judged.unseen], ['unresolved', 1], said.source);
    assert.match(judged.problems.join(), said);
  }
  assert.equal(walk.seenProblem({ ...SEEN, paperDifference: walk.SEEN_PAPER_MAX * 300 }), '', `${walk.SEEN_PAPER_MAX} levels on the paper`);
  assert.equal(walk.seenProblem({ ...SEEN, inkScreen: walk.SEEN_INK_SHARE * 8000 }), '', `${walk.SEEN_INK_SHARE} of the ink`);
  // fewer than SEEN_INK_BLOCKS blocks of ink: the share is not asked
  assert.deepEqual(walk.seenMeasures({ ...SEEN, inkBlocks: walk.SEEN_INK_BLOCKS - 1, inkScreen: 0 }), { paper: 0, ink: null });
  assert.equal(walk.seenProblem({ ...SEEN, inkBlocks: walk.SEEN_INK_BLOCKS - 1, inkScreen: 0 }), '');
  // a quote not found: its page shown, drawn and seen; a page with no text needs no ink (a blank page), and no marks
  const n2 = 'Page 2 has no text the viewer can search (it may be a scanned image), so nothing is marked. Page 2 is shown.';
  const blankPaper = { ...DRAWN, ink: 0, low: 255, markPixels: 0, markContent: 0 };
  const shown = (canvas, seen = SEEN) => walk.judgeQuote({ ...quote, page: 2 }, pdfReading(document, [drawn(1, tokens), drawn(2, [], [], canvas)],
    { status: 'not_found', pages: [], count: 0, note: n2, seen: new Map([[2, seen]]) }));
  assert.equal(shown(blankPaper).outcome, 'not_found');
  assert.match(shown({ ...blankPaper, opaque: 0 }).problems.join(), /page 2 is shown, but its canvas is not drawn/);
  const gray = { blocks: 400, tiles: 1, paperBlocks: 400, paperDifference: 400 * 16.5, inkBlocks: 0, inkCanvas: 0, inkScreen: 0 };
  assert.match(shown(blankPaper, gray).problems.join(), /page 2 is shown, but what the member sees of it is not its drawing/);
  // the page of a quote not found that has text must show ink: the white canvas (R3CS-2)
  const n1 = 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.';
  const white = walk.judgeQuote({ ...quote, text: 'absent words' }, pdfReading(document, [drawn(1, tokens, [], { ...DRAWN, ink: 0, markPixels: 0, markContent: 0 }), drawn(2, [])],
    { status: 'not_found', pages: [], count: 0, note: n1 }));
  assert.match(white.problems.join(), /page 1 is shown, but its canvas shows no ink, though the page has text/);
  // the required pages: every page with an occurrence or a mark, and the page shown for a quote not found
  assert.deepEqual(walk.requiredPages({ page: 2 }, {}, { status: 'not_found', pageCount: 3, pages: [] }, []), [2]);
  assert.deepEqual(walk.requiredPages({ page: 1 }, {}, { status: 'marked', pageCount: 3, pages: [1, 2] }, [3]), [1, 2, 3]);
  assert.deepEqual(walk.requiredPages({ page: 4 }, {}, { status: 'missing_page', pageCount: 3, pages: [] }, []), []);
});

test('the browser\'s own viewer: unavailable, the note as N3 and N4 write it with its five reasons, and a frame that opens the quote\'s page', () => {
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 2 };
  const frame = (fields, frameFields = {}) => walk.judgeQuote(quote, { mode: 'frame', fallback: 'library', status: '', pages: [], count: 0,
    note: 'The marking tool did not work here, so nothing is marked. The quote is on page 2.', frame: { page: 2, previousPage: 1, replaced: true, ...frameFields }, ...fields });
  const plain = frame({});
  assert.deepEqual([plain.outcome, plain.problems.length], ['unavailable', 1]);
  assert.match(plain.problems[0], /browser's own viewer \(the marking tool did not work in the page\)/);
  for (const [reason, sentence] of Object.entries(walk.FRAME_REASONS)) {
    assert.equal(frame({ fallback: reason, note: `${sentence} The quote is on page 2.` }).problems.length, 1, reason);
  }
  assert.deepEqual(Object.keys(walk.FRAME_REASONS).sort(), ['browser', 'document', 'download', 'library', 'slow']);
  assert.deepEqual(Object.keys(walk.FALLBACK_WHY).sort(), Object.keys(walk.FRAME_REASONS).sort());
  // round 5 (A5): the viewer downloads the document itself; a download that fails has its own reason, character for character
  assert.equal(walk.FRAME_REASONS.download, 'The document could not be downloaded for marking, so nothing is marked.');
  assert.match(frame({ fallback: 'download', note: 'The document could not be downloaded for marking, so nothing is marked. The quote is on page 2.' }).problems[0],
    /\(the document could not be downloaded in the page\)/);
  assert.match(frame({ fallback: 'download', note: 'This document cannot be drawn here, so nothing is marked. The quote is on page 2.' }).problems.join(),
    /does not say why marking is unavailable, as written/);
  assert.match(frame({ note: 'The marking tool did not work here, so nothing is marked. Page 2 is shown.' }).problems.join(), /does not say why marking is unavailable, as written/);
  assert.equal(walk.judgeQuote({ ...quote, page: null }, { mode: 'frame', fallback: 'slow', note: 'The document took too long to load here, so nothing is marked.', frame: {} }).problems.length, 1);
  assert.match(frame({}, { replaced: false }).problems.join(), /keeps the element that showed page 1/);
  assert.match(frame({}, { previousPage: 2, replaced: true }).problems.join(), /opened again for page 2/);
  assert.equal(frame({}, { previousPage: 2, replaced: false }).problems.length, 1);
  assert.match(frame({}, { page: 1 }).problems.join(), /does not open page 2/);
  assert.match(frame({ fallback: 'toString' }).problems.join(), /\(no reason given\)/);
});

test('a text document keeps its own rule (findPassages), judged by the walk\'s own copy of it', () => {
  const source = 'Colonoscopy note (fictional)\nA 12 mm pedunculated polyp in the descending colon was removed.\nA 3 mm polyp in the rectum.';
  const quote = { code: '45385', line: 'L1', text: 'A 12 mm pedunculated polyp in the\ndescending colon', page: null };
  const start = source.indexOf('A 12 mm');
  const end = source.indexOf(' was removed');
  const text = (marks, fields = {}) => walk.judgeQuote(quote, { mode: 'text', status: 'marked', count: 1, note: 'Marked in the document.', pages: [],
    text: { source, marks }, ...fields });
  assert.equal(text([[start, end]]).outcome, 'once');
  assert.equal(text([[start, end - 1]]).mismatched, 1);
  assert.equal(text([], { status: 'not_found', count: 0, note: 'The exact words could not be found in the document, so nothing is marked.' }).missed, 1);
  assert.equal(walk.judgeQuote({ ...quote, text: 'not in it' }, { mode: 'text', status: 'not_found', count: 0, pages: [],
    note: 'The exact words could not be found in the document, so nothing is marked.', text: { source, marks: [] } }).outcome, 'not_found');
  assert.deepEqual(walk.findPassagesText('COLD FORCEPS', 'cold  forceps'), [[0, 12]]);
  // a frame the viewer found not to hold the document (the edge's own page while the app restarts): nothing searched,
  // a failure for the walk's documents, and the note must give the reason as written
  const absent = fields => walk.judgeQuote(quote, { mode: 'text', status: 'unavailable', fallback: 'download', count: 0, pages: [],
    note: walk.FRAME_REASONS.download, text: { source: 'CPT Studio is temporarily unavailable.\n', marks: [] }, ...fields });
  assert.equal(absent().outcome, 'unavailable');
  assert.deepEqual(absent().problems, ['quote L1: the text is not in the viewer\'s frame (the document could not be downloaded in the page), so nothing could be marked']);
  assert.match(absent({ note: 'The exact words could not be found in the document, so nothing is marked.' }).problems.join(), /does not say why marking is unavailable/);
  assert.match(absent({ fallback: 'toString' }).problems.join(), /\(no reason given\).*does not say why/);
  const checked = walk.quoteMarkChecks([{ quote, reading: { mode: 'text', status: 'unavailable', fallback: 'download', count: 0, pages: [], note: walk.FRAME_REASONS.download, text: { source: '', marks: [] } } }]);
  assert.deepEqual([checked.status, checked.data.unavailable], ['fail', 1]);
  // the walk's documents quote their own words: a text viewer that marks none of them fails, even when its frame (the
  // edge's page, say) agrees that nothing is there - the walk does not take the frame's word for the document
  const notThere = 'The exact words could not be found in the document, so nothing is marked.';
  const edge = { mode: 'text', status: 'not_found', count: 0, pages: [], note: notThere, text: { source: 'CPT Studio is temporarily unavailable.\n', marks: [] } };
  assert.equal(walk.judgeQuote(quote, edge).outcome, 'not_found');
  const none = walk.quoteMarkChecks([{ quote, reading: edge }, { quote, reading: edge }]);
  assert.deepEqual([none.status, none.data.not_found], ['fail', 2]);
  assert.match(none.reason, /2 quote\(s\) chosen in the text viewer and not one marked/);
  const some = walk.quoteMarkChecks([{ quote, reading: { mode: 'text', status: 'marked', count: 1, note: 'Marked in the document.', pages: [], text: { source, marks: [[start, end]] } } },
    { quote: { ...quote, text: 'not in it' }, reading: { mode: 'text', status: 'not_found', count: 0, pages: [], note: notThere, text: { source, marks: [] } } }]);
  assert.equal(some.status, 'pass', some.reason);
});

test('every quote chosen is counted, the last one marked judged again after each redraw, and the check fails on anything refused', () => {
  const document = documentOf(items(at('Cold forceps biopsies were taken.', 11, 56, 740, 170, { hasEOL: true }), at('Bowel preparation was rated adequate.', 11, 56, 724, 180)));
  const tokens = layerOf(document);
  const quote = { code: '43239', line: 'L1', text: 'Cold forceps biopsies were taken.', page: 1 };
  const good = { quote, reading: pdfReading(document, [drawn(1, tokens, marked(tokens, [0, quote.text, 0]))]) };
  const n1 = 'The exact words were not found in the searchable text of page 1, so nothing is marked. Page 1 is shown.';
  const absent = { quote: { ...quote, text: 'absent words' }, reading: pdfReading(document, [drawn(1, tokens)], { status: 'not_found', pages: [], count: 0, note: n1 }) };
  const made = walk.quoteMarkChecks([good, good, absent]);
  assert.equal(made.status, 'pass', made.reason);
  assert.deepEqual(made.data, { quotes: 3, marked_once: 2, marked_multi: 0, not_found: 1, no_text: 0, unavailable: 0, unresolved: 0, off_page: 0,
    mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0, pages: 0, layers: 0, misaligned: 0, unseen: 0, redraws: 0, redraw_failed: 0 });
  assert.equal(made.reason, '3 quote(s) chosen: 2 marked once, 0 marked more than once, 1 not found (the walk\'s own search agrees; 0 on a page with no '
    + 'searchable text), 0 mark(s) off the quote\'s page, 0 marked other than the walk\'s own, 0 found by the walk and not marked, 0 beginning or '
    + 'ending inside a character, 0 required page(s) not drawn, 0 not seen as drawn, 0 marked span(s) out of place, 0 overprint flag(s) other than '
    + 'the walk\'s copies, 0 text layer(s) not the document\'s, the page count the document\'s, 0 of 0 redraw(s) judged as before');
  const lying = walk.quoteMarkChecks([good, { quote, reading: pdfReading(document, [drawn(1, tokens)], { status: 'not_found', pages: [], count: 0, note: n1 }) }]);
  assert.deepEqual([lying.status, lying.data.missed, lying.data.unresolved], ['fail', 1, 1]);
  assert.equal(walk.quoteMarkChecks([{ quote, reading: { mode: 'frame', fallback: 'browser', note: '', frame: {} } }]).status, 'fail', 'no marking at all is a failure');
  assert.equal(walk.quoteMarkChecks([]).status, 'fail');
  assert.ok(!lying.reason.includes(quote.text), 'the reason names quotes by their line and page, never by their words');
  // a viewer that marks not one quote fails, though a quote not found alone is allowed
  const none = walk.quoteMarkChecks([absent, absent]);
  assert.equal(none.status, 'fail');
  assert.match(none.reason, /; 2 quote\(s\) chosen in the PDF viewer and not one marked$/);
  // the redraws (B7): judged again as before after Zoom in and Fit width; a page not drawn again, or its marks lost, fails
  const redrawn = (step, reading, more = {}) => ({ step, quote, key: 'L1#0', page: 1, redrawn: true, reading, ...more });
  const withRedraws = steps => walk.quoteMarkChecks(Object.assign([good], { redraws: steps }));
  const kept = withRedraws([redrawn('Zoom in', good.reading), redrawn('Fit width', good.reading)]);
  assert.equal(kept.status, 'pass', kept.reason);
  assert.deepEqual([kept.data.redraws, kept.data.redraw_failed], [2, 0]);
  const lost = withRedraws([redrawn('Zoom in', pdfReading(document, [drawn(1, tokens)])), redrawn('Fit width', good.reading)]);
  assert.deepEqual([lost.status, lost.data.redraw_failed], ['fail', 1]);
  assert.match(lost.reason, /after Zoom in, quote L1 \(page 1\): 1 occurrence\(s\) the walk found are not marked/);
  assert.match(withRedraws([redrawn('Zoom in', good.reading, { redrawn: false })]).reason, /after Zoom in: page 1 was not drawn again at the new scale/);
  assert.match(withRedraws([{ step: 'Zoom in', page: 1, error: 'the viewer\'s Zoom in could not be pressed' }]).reason, /after Zoom in: the viewer's Zoom in could not be pressed/);
  // the served quotes, and what a mark's text is compared with
  assert.deepEqual(walk.servedQuotes(encounter()).map(item => [item.code, item.page]), [['43239', 1]]);
  assert.equal(walk.foldMarked(' The ﬁnding\nwas  made. '), 'Thefindingwasmade.');
  // pages read: every page of a short document (by the walk's own count); a long one on its searched, found, claimed and drawn pages
  assert.deepEqual(walk.pagesToRead({ page: 2 }, { pageCount: 3, pages: [], drawn: [] }), [1, 2, 3]);
  assert.deepEqual(walk.pagesToRead({ page: 2 }, { pageCount: 2, document: { pageCount: 3 }, pages: [], drawn: [] }), [1, 2, 3]);
  assert.deepEqual(walk.pagesToRead({ page: 20 }, { pageCount: 40, pages: [20, 21], drawn: [19, 20, 21] }, { pages: [30] }), [19, 20, 21, 30]);
  assert.deepEqual(walk.pagesToRead({ page: null }, { pageCount: 40, pages: [], drawn: [] }).length, 40);
});

test('a screenshot is read by the walk\'s own PNG reader, every filter, and reduced to blocks', () => {
  // an 6 x 3 RGB image, one row per filter kind and an RGBA one, built here: the reader gives back the pixels
  const zlib = require('node:zlib');
  const chunk = (type, data) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    return Buffer.concat([length, Buffer.from(type, 'latin1'), data, Buffer.alloc(4)]);
  };
  const make = (width, rows, channels, filters) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(rows.length, 4);
    header[8] = 8;
    header[9] = { 3: 2, 4: 6 }[channels];
    const stride = width * channels;
    const raw = [];
    rows.forEach((row, y) => {
      const filter = filters[y];
      raw.push(filter);
      for (let x = 0; x < stride; x += 1) {
        const a = x >= channels ? row[x - channels] : 0;
        const b = y > 0 ? rows[y - 1][x] : 0;
        const c = x >= channels && y > 0 ? rows[y - 1][x - channels] : 0;
        const p = a + b - c;
        const paeth = Math.abs(p - a) <= Math.abs(p - b) && Math.abs(p - a) <= Math.abs(p - c) ? a : Math.abs(p - b) <= Math.abs(p - c) ? b : c;
        const predicted = [0, a, b, (a + b) >> 1, paeth][filter];
        raw.push((row[x] - predicted) & 0xff);
      }
    });
    return Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), chunk('IHDR', header), chunk('IDAT', zlib.deflateSync(Buffer.from(raw))), chunk('IEND', Buffer.alloc(0))]);
  };
  const rows = Array.from({ length: 5 }, (_, y) => Array.from({ length: 18 }, (_, x) => (x * 37 + y * 91) % 256));
  const image = walk.decodePng(make(6, rows, 3, [0, 1, 2, 3, 4]));
  assert.deepEqual([image.width, image.height, image.channels], [6, 5, 3]);
  assert.deepEqual([...image.data], rows.flat());
  const rgba = walk.decodePng(make(2, [[10, 20, 30, 255, 40, 50, 60, 255]], 4, [4]));
  assert.deepEqual([rgba.channels, ...rgba.data], [4, 10, 20, 30, 255, 40, 50, 60, 255]);
  assert.throws(() => walk.decodePng(Buffer.from('not a png')), /not a PNG/);
  const blocks = walk.pngBlocks({ width: 4, height: 2, channels: 3, data: Buffer.from([0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255,
    0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255]) }, 2);
  assert.deepEqual([blocks.cols, blocks.rows, blocks.means.map(Math.round)], [2, 1, [0, 255]]);
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
  // the draft PDF report through the export dialog, as the walk downloads it: the page's request names the round shown
  await t.test('the page\'s download names the round shown', async () => {
    await page.goto(`${base}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(count => document.querySelectorAll('ol#codesList > li.code-row').length === count, enc.codes.length, { timeout: 15000 });
    const out = scratch();
    const download = await walk.exportPdf(page, { base, out }, enc, 'draft', out);
    assert.equal(download.status, 201);
    assert.deepEqual(walk.exportRequestProblems(download.body, enc, 'draft'), []);
    // the preview's file is a one-page mock PDF (not the server's report: no synthetic line, no status, no codes): only
    // what the page and the download did is held here
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

// A faint scanned page, made here: a 150 dpi gray image of paper 240 with each line's words as bars of ink 190 (light
// noise over it), and the same lines as invisible text (3 Tr, Helvetica 11 pt) on the bars' baselines, as an OCR layer.
function faintScan(texts) {
  const dpi = 150;
  const [width, height] = [Math.round(8.5 * dpi), Math.round(11 * dpi)];
  const gray = Buffer.alloc(width * height, 240);
  const px = value => Math.round((value * dpi) / 72);
  texts.forEach((text, k) => {
    const baseline = 700 - k * 18;
    const [x0, x1] = [px(56), px(56 + text.length * 6.2)];
    const [y0, y1] = [px(792 - baseline - 7.9), px(792 - baseline)];
    for (let y = y0; y < y1; y += 1) for (let x = x0; x < x1; x += 1) gray[y * width + x] = 190;
  });
  let seed = 11;
  for (let at = 0; at < gray.length; at += 1) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    gray[at] = Math.max(0, Math.min(255, gray[at] + (seed % 7) - 3));
  }
  return pdfOf([{ stream: `q 612 0 0 792 0 0 cm /Im1 Do Q\n${lines(texts, { top: 700, step: 18, mode: 3 })}`, image: { width, height, gray } }]);
}

// The browser tests' common ground: the dev preview on a free port (freePort), Chromium, the served encounters, a page
// opened on one (with routes set up first), and the ready fixture with its quotes and, when given, its view replaced.
async function browserKit(t) {
  const { chromium } = require(walk.PLAYWRIGHT);
  const port = await freePort();
  const server = childProcess.spawn(process.execPath, [path.join(__dirname, 'dev_preview_server.cjs'), `--port=${port}`], { stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => server.kill('SIGTERM'));
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the preview server did not start')), 15000);
    server.stdout.on('data', chunk => { if (String(chunk).includes('CPT Studio dev preview')) { clearTimeout(timer); resolve(); } });
    server.once('exit', code => reject(new Error(`the preview server exited ${code}`)));
  });
  const base = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ headless: true });
  t.after(() => browser.close());
  const served = async id => {
    const context = await browser.newContext();
    try {
      return await (await context.request.get(`${base}/api/encounters/${id}`, { headers: walk.CLIENT_HEADERS })).json();
    } finally {
      await context.close();
    }
  };
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
  const crafted = async (quotes, pdf = null, setup = null) => {
    const enc = await served(READY_ID);
    enc.codes[0].quotes = quotes;
    for (const code of enc.codes.slice(1)) code.quotes = [];
    const opened = await open(READY_ID, enc, async item => {
      await item.route(`**/api/encounters/${READY_ID}`, route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(enc) }));
      if (pdf) await item.route(url => url.pathname === `/api/encounters/${READY_ID}/original`, route => route.fulfill({ status: 200, contentType: 'application/pdf', body: pdf }));
      if (setup) await setup(item);
    });
    return { enc, ...opened };
  };
  return { base, browser, served, open, crafted };
}
const READY_ID = 'f5000000-0000-4000-8000-000000000001';  // tests/fixtures/customer/encounter-ready.json: the two-page PDF
const WORD_ID = 'f9000000-0000-4000-8000-000000000001';  // encounter-word.json: a Word file viewed as its PDF
const TEXT_ID = 'f3000000-0000-4000-8000-000000000001';  // encounter-awaiting-answer.json: a text document
const playwrightMissing = () => !fs.existsSync(path.join(walk.PLAYWRIGHT, 'package.json'));

// Synthetic report lines (invented), and the PDFs of every page shape the round-5 checks must pass.
const REPORT = ['SYNTHETIC REPORT - FICTIONAL PATIENT', 'Indication: surveillance of a fictional polyp.', 'Cold forceps biopsies were taken from the antrum.',
  'Impression: two small polyps were removed.', 'Plan: repeat the fictional colonoscopy in five years.'];
const DENSE = Array.from({ length: 26 }, (_, k) => `Line ${k + 1} of a dense fictional report: the synthetic findings were recorded here.`);
const LONG = [1, 2, 3, 4].map(n => Array.from({ length: 30 }, (_, k) => `Page ${n}, line ${k + 1}: the fictional record goes on with synthetic words.`));
const SHAPES = {
  'rotated 90': { pdf: () => pdfOf([{ stream: lines(REPORT), rotate: 90 }, { stream: lines(REPORT.slice(1)), rotate: 90 }]),
    quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[3], page: 1 }, { text: REPORT[4], page: 2 }] },
  'rotated 180': { pdf: () => pdfOf([{ stream: lines(REPORT), rotate: 180 }]), quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[4], page: 1 }] },
  'rotated 270': { pdf: () => pdfOf([{ stream: lines(REPORT), rotate: 270 }]), quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[4], page: 1 }] },
  'turned text': { pdf: () => pdfOf([[line(56, 740, REPORT[0]), line(300, 200, 'Turned line: the fictional margin note reads upward.', { matrix: [0, 1, -1, 0] }),
    line(150, 400, 'Slanted line: a fictional stamp at forty five degrees.', { matrix: [0.7071, 0.7071, -0.7071, 0.7071] }), line(56, 700, REPORT[2])].join('\n')]),
  quotes: [{ text: 'Turned line: the fictional margin note reads upward.', page: 1 }, { text: 'Slanted line: a fictional stamp at forty five degrees.', page: 1 }, { text: REPORT[2], page: 1 }] },
  'a CropBox with its own origin': { pdf: () => pdfOf([{ stream: lines(REPORT, { x: 90, top: 700 }), crop: [50, 60, 562, 752] }]),
    quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[4], page: 1 }] },
  '/UserUnit 2': { pdf: () => pdfOf([{ stream: lines(REPORT, { x: 28, top: 370, step: 7, size: 5.5 }), media: [0, 0, 306, 396], userUnit: 2 }]),
    quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[4], page: 1 }] },
  'Times and Courier': { pdf: () => pdfOf([`${lines(REPORT, { font: 'F2', size: 10 })}\n${line(56, 600, 'COURIER LINE: TWO POLYPS WERE REMOVED.', { font: 'F3', size: 9 })}`]),
    quotes: [{ text: REPORT[2], page: 1 }, { text: 'COURIER LINE: TWO POLYPS WERE REMOVED.', page: 1 }] },
  'a blank page': { pdf: () => pdfOf([lines(REPORT), '']), quotes: [{ text: REPORT[2], page: 1 }, { text: 'Words of a page that has none.', page: 2 }] },
  'a faint scan': { pdf: () => faintScan(REPORT), quotes: [{ text: REPORT[2], page: 1 }, { text: REPORT[3], page: 1 }] },
  // the viewer draws only the pages near what it shows and lets the others go: reading the fourth page lets the first go
  'four pages, the first let go while the last is read': { pdf: () => pdfOf(LONG.map(texts => lines(texts))),
    quotes: [{ text: LONG[0][6], page: 1 }, { text: LONG[3][9], page: 4 }, { text: LONG[1][3], page: 2 }, { text: LONG[0][20], page: 1 }] },
};

test('every quote is chosen and judged by the walk\'s own reading through the page itself, in a browser', async t => {
  // D368 in a real browser: the dev preview's synthetic PDF and text documents, the shipped page and its PDF viewer, the
  // walk's own reading and judge. Skipped where Playwright is not installed (CPT_VERIFY_PLAYWRIGHT).
  if (playwrightMissing()) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { browser, served, open, crafted } = await browserKit(t);
  const { syntheticPdf } = require('./dev_preview_server.cjs');
  for (const id of [READY_ID, WORD_ID, TEXT_ID]) {
    await t.test(`the fixture ${id}: every quote marked once, as the walk's own reading finds it, and again after each redraw`, async () => {
      const enc = await served(id);
      const { page, context, violations } = await open(id, enc);
      const chosen = await walk.chooseQuotes(page, enc);
      const made = walk.quoteMarkChecks(chosen);
      assert.equal(made.status, 'pass', made.reason);
      const count = walk.servedQuotes(enc).length;
      assert.deepEqual([made.data.quotes, made.data.marked_once, made.data.off_page, made.data.mismatched, made.data.missed, made.data.blank, made.data.unseen,
        made.data.misaligned, made.data.layers, made.data.flags, made.data.pages], [count, count, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
      assert.deepEqual([made.data.redraws, made.data.redraw_failed], [id === TEXT_ID ? 0 : 2, 0]);
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
    // the walk read the PDF itself (the view address, fetched in the page), every page of it for each quote, every marked
    // page drawn and seen
    assert.equal(chosen[0].reading.document.pageCount, 2);
    assert.ok(chosen.every(item => [...item.reading.pagesRead.values()].every(read => read.drawn && read.canvas.opaque === 1)));
    assert.ok(chosen.every(item => [...item.reading.seen.values()].every(seen => seen.blocks > 0 && walk.seenProblem(seen) === '')));
    // the selected quote stays selected; the page's own text layer is the document's, never scanned as its wording
    assert.equal(await page.getAttribute('#quotesPanel .quote.selected', 'data-quote'), chosen[3].key);
    const strings = (await page.evaluate(walk.collectDomStrings)).map(([, value]) => value);
    assert.ok(strings.includes('Marked on page 1.'), 'the note is read');
    assert.ok(!strings.some(value => value.includes('Endoscopy report (fictional)')), 'the text layer is not read');
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('#documentViewer .pdf-text span')].some(span => span.textContent.includes('Endoscopy report (fictional)'))),
      'though the text layer holds it');
    assert.deepEqual(violations, []);
    assert.equal(await page.evaluate(() => typeof window.innerWidth), 'number');
    await context.close();
  });
  await t.test('readPdfPage reads a drawn page apart from the page script: its items, line breaks, flags, boxes, families, marks and canvas', async () => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const span = (inner, extra = '') => `<span${extra}>${inner}</span>`;
    const mark = (occurrence, inner) => `<span class="pdf-mark" data-occurrence="${occurrence}">${inner}</span>`;
    const placed = (left, top) => ` style="position:absolute;left:${left}px;top:${top}px;font-size:10px;line-height:1;font-family:sans-serif"`;
    await page.setContent(`<div id="documentViewer" data-mode="pdf" data-mark-status="marked" data-mark-pages="1" data-mark-count="2">
      <div class="pdf-page" data-page="1" style="position:relative;width:300px;height:200px"><canvas width="300" height="200" style="position:absolute;inset:0"></canvas>
      <div class="pdf-text" style="position:absolute;inset:0">${span(`The patient ${mark(0, 'Jose')}`, placed(10, 10))}${span('́', placed(80, 10))}${span(' ', placed(90, 10))}${span(`${mark(0, 'Garcia')} was seen.`, placed(100, 10))}<br>`
      + `${span('Impression:', placed(10, 40))}${span('Impression:', `${placed(10.3, 40)} data-overprint="1"`)}${span(`${mark(1, 'two')} polyps`, placed(70, 40))}</div></div>
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
    const read = await page.evaluate(walk.readPdfPage, { number: 1, ink: walk.INK_RULE });
    assert.deepEqual(read.tokens.map(token => (token.kind === 'br' ? 'BR' : `${token.text}${token.copy ? ' (copy)' : ''}`)),
      ['The patient Jose', '́', ' ', 'Garcia was seen.', 'BR', 'Impression:', 'Impression: (copy)', 'two polyps']);
    assert.deepEqual(read.marks, [{ item: 0, occurrence: 0, start: 12, end: 16 }, { item: 3, occurrence: 0, start: 0, end: 6 }, { item: 6, occurrence: 1, start: 0, end: 3 }]);
    assert.deepEqual([read.tokens[6].box[0], read.tokens[6].box[1]].map(value => Math.round(value * 10) / 10), [10.3, 40]);
    assert.equal(read.tokens[6].family, 'sans-serif');
    assert.deepEqual(read.size, [300, 200]);
    assert.ok(read.ascent['sans-serif'] > 0.5 && read.ascent['sans-serif'] < 1, `the ascent ${read.ascent['sans-serif']}`);
    // the canvas: shown, painted, its paper white, the bar its ink (B6: darker than the paper by a share of its contrast)
    assert.deepEqual([read.canvas.present, read.canvas.visible, read.canvas.opaque, read.canvas.paper, read.canvas.ink], [true, true, 1, 255, 2000]);
    assert.ok(read.canvas.markPixels > 0 && read.canvas.markContent > 0);
    assert.equal((await page.evaluate(walk.readPdfPage, { number: 2, ink: walk.INK_RULE })).drawn, false);
    // the canvas's blocks over a clip of the screen, with the blocks the marks touch
    const blocks = await page.evaluate(walk.canvasBlocks, { number: 1, clip: { x: 8, y: 8, width: 300, height: 200 }, block: 4 });
    assert.deepEqual([blocks.cols, blocks.rows, blocks.means[0], blocks.masked.some(Boolean)], [75, 50, 255, true]);
    // S5 apart from the page script: the first occurrence's run 'Jose' ends inside the character the accent completes
    const document = { pageCount: 2, pages: [{ number: 1, view: [0, 0, 300, 200], rotate: 0, userUnit: 1, styles: {}, items: items('The patient Jose', '́', ' ',
      'Garcia was seen.', EOL, at('Impression:', 10, 10, 150, 50), at('Impression:', 10, 10.3, 150, 50), 'two polyps') }, { number: 2, view: [0, 0, 300, 200], rotate: 0, userUnit: 1, styles: {}, items: [] }] };
    const reading = { ...(await page.evaluate(walk.readViewer)), document, seen: new Map(),
      pagesRead: new Map([[1, read], [2, { number: 2, drawn: true, size: [300, 200], tokens: [], marks: [], canvas: read.canvas }]]) };
    const judged = walk.judgeQuote({ code: '43239', line: 'L1', text: 'x', page: null }, reading);
    assert.deepEqual([judged.cut, judged.flags, judged.layers], [1, 0, 0]);
    // a canvas that was never drawn reads as not painted
    await page.evaluate(() => { document.querySelector('canvas').replaceWith(Object.assign(document.createElement('canvas'), { width: 300, height: 200 })); });
    assert.equal((await page.evaluate(walk.readPdfPage, { number: 1, ink: walk.INK_RULE })).canvas.opaque, 0);
    await context.close();
  });
  await t.test('where the PDF library cannot load, the browser\'s own viewer is framed: nothing is marked and the check fails', async inner => {
    const enc = await served(WORD_ID);
    const { page, context } = await open(WORD_ID, enc, item => item.route(url => /\/pdf\.min\.mjs$/.test(url.pathname), route => route.abort()));
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
      for (const item of chosen) assert.deepEqual(walk.judgeQuote(item.quote, item.reading).problems.length, 1, item.reading.note);
      assert.match(made.reason, /browser's own viewer \(the marking tool did not work in the page\)/);
    });
    await context.close();
  });
  await t.test('where the library runs but cannot draw the document, the browser\'s own viewer is framed and the check fails', async inner => {
    const enc = await served(READY_ID);
    // the view address answers with bytes that are no PDF: the library refuses the document, the browser is not at fault
    const { page, context, violations } = await open(READY_ID, enc, item => item.route(url => url.pathname === `/api/encounters/${READY_ID}/original`,
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
  await t.test('round 3: words not found (N1), words of another page, inside a word (R2), a format character (R3)', async () => {
    const pdf = syntheticPdf([['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'The patient was told to bathe ending the preparation.',
      'Findings: the end of the procedure was uneventful.', 'Mild pain was reported; the abdomen was painless.'],
    ['Bowel preparation quality was not recorded.']]);
    const { enc, page, context, violations } = await crafted([{ text: 'A passage that is in no page of this document.', page: 2 },
      { text: 'Bowel preparation quality was not recorded.', page: 1 }, { text: 'the end', page: 1 }, { text: 'pain', page: 1 },
      { text: 'Mild pain was re­ported', page: 1 }], pdf);
    const chosen = await walk.chooseQuotes(page, enc, { bytes: pdf });
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
  await t.test('round 3: an overprinted line (R1) counts once and is flagged as the walk\'s own copy; a page with no text (N2)', async () => {
    const pdf = pdfOf([[line(56, 700, 'DIAGNOSIS: TUBULAR ADENOMA.'), line(56.3, 700, 'DIAGNOSIS: TUBULAR ADENOMA.'), line(56, 680, 'The procedure was uneventful.')].join('\n'),
      '0 0 0 rg 56 600 200 50 re f']);
    const { enc, page, context, violations } = await crafted([{ text: 'DIAGNOSIS: TUBULAR ADENOMA.', page: 1 }, { text: 'Any words at all', page: 2 }], pdf);
    const chosen = await walk.chooseQuotes(page, enc, { bytes: pdf });
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

// Runs in the page: the pinned library's reading of a PDF (base64), in the page, with the options the viewer gives it.
function libraryReading(request) {
  const root = '/static/studio/lib/pdfjs-6.5.438/';
  return import(`${root}legacy/build/pdf.min.mjs`).then(async library => {
    const worker = new URL(`${root}legacy/build/pdf.worker.min.mjs`, location.href);
    library.GlobalWorkerOptions.workerSrc = worker.href;
    const binary = atob(request.data);
    const data = new Uint8Array(binary.length);
    for (let at = 0; at < binary.length; at += 1) data[at] = binary.charCodeAt(at);
    const task = library.getDocument({ data, withCredentials: false, isEvalSupported: false, enableXfa: false, useWasm: false,
      wasmUrl: new URL('../../wasm/', worker).href, standardFontDataUrl: new URL('../../standard_fonts/', worker).href, useSystemFonts: true,
      disableWorkerRendering: true, stopAtErrors: false, verbosity: library.VerbosityLevel.ERRORS });
    try {
      const pdf = await task.promise;
      const pages = [];
      for (let number = 1; number <= pdf.numPages; number += 1) {
        const page = await pdf.getPage(number);
        const content = await page.getTextContent();
        pages.push({ number, view: Array.from(page.view), rotate: page.rotate, userUnit: page.userUnit, items: content.items.filter(item => typeof item.str === 'string')
          .map(item => ({ str: item.str, transform: Array.from(item.transform), width: item.width, hasEOL: item.hasEOL === true, fontName: item.fontName })) });
      }
      return { pageCount: pdf.numPages, pages };
    } finally {
      await task.destroy();
    }
  });
}

test('the walk\'s own reading of every fixture, in Node, is what the library reads of it in the page', async t => {
  // B2: the items (str, transform, width, hasEOL, fontName - its document number aside, which counts the documents each
  // copy of the library has opened), the page count and each page's box, rotation and user unit, equal
  if (playwrightMissing()) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { base, browser } = await browserKit(t);
  const { viewBytes } = require('./dev_preview_server.cjs');
  const fixtures = {
    'the ready fixture\'s PDF': viewBytes('synthetic-egd-colonoscopy.pdf').bytes,
    'the Word fixture\'s PDF': viewBytes('synthetic-colonoscopy-report.docx').bytes,
    ...Object.fromEntries(Object.entries(SHAPES).map(([name, shape]) => [name, shape.pdf()])),
    'an overprinted line and a page with no text': pdfOf([[line(56, 700, 'DIAGNOSIS: TUBULAR ADENOMA.'), line(56.3, 700, 'DIAGNOSIS: TUBULAR ADENOMA.')].join('\n'), '0 0 0 rg 56 600 200 50 re f']),
    'round 5 shapes': ROUND5_SHAPES(),
  };
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${base}/login/`, { waitUntil: 'domcontentloaded' });
  const shape = reading => ({ pageCount: reading.pageCount, pages: reading.pages.map(item => ({ number: item.number, view: item.view, rotate: item.rotate,
    userUnit: item.userUnit, items: item.items.map(entry => ({ str: entry.str, transform: entry.transform, width: entry.width, hasEOL: entry.hasEOL,
      fontName: String(entry.fontName).replace(/^g_d\d+_/, 'g_d_') })) })) });
  for (const [name, bytes] of Object.entries(fixtures)) {
    const node = await walk.readDocument(bytes);
    const inPage = await page.evaluate(libraryReading, { data: Buffer.from(bytes).toString('base64') });
    assert.ok(node.pages.some(item => item.items.length), name);
    assert.deepEqual(shape(node), shape(inPage), name);
  }
  await context.close();
});

// Round 5's new shapes, a page for each rule: (1) R1 - a Courier line overstruck as nine items, the same words at two
// sizes in one place; (2) R2b - a raised marker glued to a word, a fake-bold run the library joins to the text after it;
// (3) R2a - numbers with points and commas.
function ROUND5_SHAPES() {
  return pdfOf([[line(56, 740, 'IMPRESSION: TWO POLYPS WERE REMOVED.', { font: 'F3', size: 9 }), line(56.2, 740, 'IMPRESSION: TWO POLYPS WERE REMOVED.', { font: 'F3', size: 9 }),
    line(56, 690, 'IMPRESSION: NORMAL MUCOSA'), line(56, 690, 'IMPRESSION: NORMAL MUCOSA', { size: 22 })].join('\n'),
  [line(56, 740, 'Assessment: type 2 diabetes mellitus', { font: 'F3' }), line(293.6, 744, '1', { font: 'F3', size: 7 }), line(297.8, 740, ', well controlled.', { font: 'F3' }),
    line(56, 700, 'Diagnosis: Chest pain'), line(110.706, 700, 'Chest pain'), line(163.286, 700, ' since this morning.')].join('\n'),
  line(56, 740, '1. Hypokalemia, potassium 3.1. Lisinopril 2.5 mg daily. Estimated blood loss 1,500 mL.')]);
}

test('the walk holds the viewer to its own reading on every page shape and after each redraw; marks out of place or a page not seen as drawn fail', async t => {
  // B4-B7 against the viewer: turned pages, turned text, a box with its own origin, a user unit, other fonts, a blank page
  // and a faint scan all pass; the round-4 mutants of the page's look (R3CS-1, R3CS-2), appended to its styles, each fail
  if (playwrightMissing()) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { crafted } = await browserKit(t);
  for (const [name, shape] of Object.entries(SHAPES)) {
    await t.test(`${name}: every quote judged as the walk's reading says, its marks where its words are drawn, seen as drawn, and again after each redraw`, async () => {
      const pdf = shape.pdf();
      const { enc, page, context, violations } = await crafted(shape.quotes, pdf);
      const chosen = await walk.chooseQuotes(page, enc, { bytes: pdf });
      const made = walk.quoteMarkChecks(chosen);
      assert.equal(made.status, 'pass', made.reason);
      assert.deepEqual([made.data.misaligned, made.data.unseen, made.data.blank, made.data.layers, made.data.flags, made.data.pages, made.data.redraws, made.data.redraw_failed],
        [0, 0, 0, 0, 0, 0, 2, 0]);
      assert.deepEqual(violations, []);
      await context.close();
    });
  }
  const dense = pdfOf([lines(DENSE)]);
  const quotes = [{ text: DENSE[12], page: 1 }];
  for (const [name, rule, counter] of [
    ['the text layer 8 pt down', '.pdf-text{translate:0 calc(var(--total-scale-factor) * 8px)}', 'misaligned'],
    ['the text layer 22 px down', '.pdf-text{translate:0 22px}', 'misaligned'],
    ['the text layer a line up', '.pdf-text{translate:0 calc(var(--total-scale-factor) * -14px)}', 'misaligned'],
    ['the text layer 6% larger', '.pdf-text{scale:1.06}', 'misaligned'],
    ['the canvas at opacity .04', '.pdf-page>canvas{opacity:.04}', 'unseen'],
    ['the canvas at opacity .02', '.pdf-page>canvas{opacity:.02}', 'unseen'],
    ['the canvas screened', '.pdf-page>canvas{mix-blend-mode:screen}', 'unseen'],
    ['the canvas lightened', '.pdf-page>canvas{mix-blend-mode:lighten}', 'unseen'],
    ['the canvas filtered to opacity 0', '.pdf-page>canvas{filter:opacity(0)}', 'unseen'],
    ['the pages at opacity .03', '.pdf-pages{opacity:.03}', 'unseen'],
    ['an opaque text layer over the canvas', '.pdf-text{z-index:2;background:#fff}', 'unseen']]) {
    await t.test(`it fails ${name}`, async () => {
      const { enc, page, context } = await crafted(quotes, dense);
      await page.addStyleTag({ content: rule });
      const chosen = await walk.chooseQuotes(page, enc, { bytes: dense });
      const made = walk.quoteMarkChecks(chosen);
      assert.equal(made.status, 'fail', name);
      assert.ok(made.data[counter] > 0, `${name}: ${made.reason}`);
      await context.close();
    });
  }
});

test('round 5 against the new viewer: R1 past eight items and at another size, R2a numbers, R2b separate drawings, R2c Han and hiragana, the download reason', async t => {
  // These hold the viewer to round 5's rules (ROUND5.md R1, R2a, R2b, R2c) and its 'download' reason (A5): they need the
  // round-5 viewer, and fail on the round-3 one by design, its rules being round 3's.
  if (playwrightMissing()) {
    t.skip(`no Playwright at ${walk.PLAYWRIGHT}`);
    return;
  }
  const { browser, served, open, crafted } = await browserKit(t);
  const judged = async (quotes, pdf) => {
    const { enc, page, context, violations } = await crafted(quotes, pdf);
    const chosen = await walk.chooseQuotes(page, enc, { bytes: pdf });
    const made = walk.quoteMarkChecks(chosen);
    await context.close();
    return { made, chosen, violations };
  };
  const shapes = ROUND5_SHAPES();
  await t.test('R1: a Courier line overstruck as nine items counts once; the same words at another size in one place are no copy', async () => {
    const { made, chosen } = await judged([{ text: 'TWO POLYPS', page: 1 }, { text: 'IMPRESSION: TWO POLYPS WERE REMOVED.', page: 1 }, { text: 'NORMAL MUCOSA', page: 1 }], shapes);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual(chosen.map(item => item.reading.note), ['Marked on page 1.', 'Marked on page 1.', 'These words appear 2 times on page 1. Each is marked.']);
  });
  await t.test('R2a: a number\'s point or comma keeps it one word', async () => {
    const { made } = await judged(['5 mg daily', '2.5 mg daily', '500 mL', '1,500 mL', '1.', '2.'].map(text => ({ text, page: 3 })), shapes);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual([made.data.marked_once, made.data.marked_multi, made.data.not_found], [3, 0, 3]);
  });
  await t.test('R2b: a raised marker glued to a word, and a fake-bold run the library joins to the text after it, meet at word edges', async () => {
    const { made, chosen } = await judged(['type 2 diabetes mellitus', 'Diagnosis: Chest pain', 'Chest pain since this morning.', 'Chest pain'].map(text => ({ text, page: 2 })), shapes);
    assert.equal(made.status, 'pass', made.reason);
    assert.deepEqual(chosen.map(item => item.reading.count), [1, 1, 1, 2]);
  });
  await t.test('R2c: Han and hiragana characters are words of their own (a page printed by Chromium)', async () => {
    const printer = await browser.newPage();
    await printer.setContent('<p style="font-size:14px">患者有糖尿病史和高血压</p><p style="font-size:14px">高血圧の治療</p>');
    const pdf = await printer.pdf({ format: 'Letter' });
    await printer.close();
    const { made } = await judged(['糖尿病', '高血压', '高血圧'].map(text => ({ text, page: 1 })), pdf);
    assert.equal(made.status, 'pass', made.reason);
    assert.equal(made.data.marked_once, 3);
  });
  await t.test('the download reason (A5): a view request that fails is not blamed on the document', async () => {
    const enc = await served(READY_ID);
    let failed = false;
    const { page, context } = await open(READY_ID, enc, item => item.route(url => url.pathname === `/api/encounters/${READY_ID}/original` && url.searchParams.get('view') === '1',
      route => {
        if (failed) return route.continue();
        failed = true;
        return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error": "The service is not available right now.", "details": {}}' });
      }));
    await page.waitForSelector('#documentViewer[data-mode="frame"]', { timeout: 30000 });
    const chosen = await walk.chooseQuotes(page, enc);
    const last = walk.servedQuotes(enc).at(-1);
    assert.equal(chosen.at(-1).reading.fallback, 'download');
    assert.equal(chosen.at(-1).reading.note, `The document could not be downloaded for marking, so nothing is marked. The quote is on page ${last.page}.`);
    for (const item of chosen) assert.equal(walk.judgeQuote(item.quote, item.reading).problems.length, 1, item.reading.note);
    await context.close();
  });
});

// A free port on the loopback: the first free one of CPT_WALK_TEST_PORTS ('first-last') where it is set, so a run can be
// kept to the ports it was given, else one the system gives.
function freePort() {
  const listen = port => new Promise(resolve => {
    const probe = net.createServer();
    probe.once('error', () => resolve(null));
    probe.listen(port, '127.0.0.1', () => {
      const { port: got } = probe.address();
      probe.close(() => resolve(got));
    });
  });
  const range = /^(\d+)-(\d+)$/.exec(process.env.CPT_WALK_TEST_PORTS || '');
  return (async () => {
    if (!range) return (await listen(0)) ?? Promise.reject(new Error('no free port'));
    for (let port = Number(range[1]); port <= Number(range[2]); port += 1) {
      const got = await listen(port);
      if (got) return got;
    }
    throw new Error(`no free port in ${process.env.CPT_WALK_TEST_PORTS}`);
  })();
}

test('the readers that run in the page are self-contained functions', () => {
  for (const reader of [walk.readEncounterDom, walk.collectDomStrings, walk.readViewer, walk.readPdfPage, walk.readTextFrame, walk.canvasBlocks,
    walk.seenGeometry, walk.scrollViewerTo, walk.fetchView, walk.pageScale, libraryReading]) {
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
  const ownIds = { session: 200, probed: 4 };
  assert.deepEqual(failed(walk.opsChecks({ probes, ownIds, operator: { status: 200, names: true } })), []);
  assert.deepEqual(failed(walk.opsChecks({ probes: [{ ...probes[0], customer: 200 }], ownIds, operator: { status: 200, names: true } })),
    ['ops.customer_404']);
  assert.deepEqual(failed(walk.opsChecks({ probes: [{ ...probes[0], anonymous: 200 }], ownIds, operator: { status: 200, names: true } })),
    ['ops.anonymous_not_200']);
  assert.deepEqual(failed(walk.opsChecks({ probes, ownIds, operator: { status: 404, names: false } })), ['ops.operator_view']);
  // the probes by the member's own ids must have run: a failed session read fails the check (refutation r3, r3-10)
  for (const broken of [{ session: 409, probed: 0 }, { session: 200, probed: 1 }, { session: 500, probed: 4 }, undefined]) {
    assert.deepEqual(failed(walk.opsChecks({ probes, ownIds: broken, operator: { status: 200, names: true } })), ['ops.own_ids_probed']);
  }
});

// The physician PDF report - the only report CPT Studio makes (owner direction 2026-11-21) - as exportPdf reads it
// (readDocument, then pdfPageLines, each page's lines joined): every page opens with the running header the server's
// report draws, its status and the synthetic line, then the page's own lines. The pages and their wording are the
// server's: this file's encounter (its first line approved) made through the API as a draft and an approved report and
// read by the walk's own reading - abridged, trailing spaces aside.
const REPORT_HEADS = { draft: 'DRAFT · REVIEW REQUIRED', approved: 'APPROVED CODES' };
function reportPages(kind, bodies) {
  return bodies.map((body, index) => ['QuillMD', 'C P T   S T U D I O', REPORT_HEADS[kind], 'gi-02 · E5C1D3A2 · Coding review 1',
    `Synthetic data · Not for billing or claims   CPT-E5C1D3A2 · r1   /   0${index + 1} of 0${bodies.length}`, ...body].join('\n'));
}
const DRAFT_PAGES = reportPages('draft', [
  ['CPT coding summary', 'CPT SUGGESTIONS   Status and saved decision of each line', '01   43239', 'CPT suggestion',
    'Ready for approval', 'Line L1 · Modifiers: none', 'Approved by Coder1 · 20 Nov 2026, 10:06 UTC', 'UNITS', '1   Approved',
    'Evidence 01', '02   00731', 'CPT suggestion', 'Needs your answer', 'Line L2 · Modifiers: P2', 'UNITS', '1   Answer needed',
    'No excerpt', 'What still needs your decision', 'Question: How long was the anesthesia?', 'REVIEWER   APPROVAL RECORD',
    'Coder1   1 approved · 0 rejected'],
  ['THE REASONS, IN THE RECORD', 'The evidence for each code.', '01   43239 / Ready for approval',
    '“Cold forceps biopsies were taken from the antrum.”', 'Page 1',
    'Reason: EGD with biopsy is documented. Second check: agrees. The report states the biopsy.', '02   00731 / Needs your answer',
    'No excerpt from the document was saved for this code.',
    'Reason: Anesthesia time is not stated. Second check: no verdict. The second check did not review this code.',
    'Question: How long was the anesthesia?', 'DOCUMENTATION NOTES', '–   The indication is not stated.'],
  ['REVIEW SCOPE', 'Report format   PDF · cpt-studio-customer-export@3', 'Prepared for a professional decision.']]);
const APPROVED_PAGES = reportPages('approved', [
  ['Approved CPT codes', 'APPROVED CODES   Only codes with a current saved approval', '01   43239', 'Approved code',
    'Approved by Coder1', '20 Nov 2026, 10:06 UTC', 'Line L1 · Modifiers: none', 'UNITS', '1   Approved', 'Evidence 01',
    'APPROVED BY   APPROVAL RECORD', 'Coder1   1 code approved · latest 20 Nov 2026, 10:06 UTC'],
  ['THE REASONS, IN THE RECORD', 'Every approved code has a source.', '01   43239 / Approved by Coder1',
    '“Cold forceps biopsies were taken from the antrum.”', 'Page 1', 'Reason: EGD with biopsy is documented.', 'REVIEW SCOPE',
    'Report format   PDF · cpt-studio-customer-export@3', 'A record of saved approvals.']]);

// A report of ``kind`` as exportPdf gives it: made (201), saved as a .pdf, posted for round 1, the same bytes fetched
// again, and read as ``pages``.
function downloaded(kind, pages) {
  const filename = `CPT-Studio-${kind}-r1-20261120T100600.pdf`;
  return { kind, fmt: 'pdf', status: 201, filename, suggested: filename, size: 57686, sha256: 'a'.repeat(64),
    refetch: { status: 200, sha256: 'a'.repeat(64), size: 57686 }, body: { kind, fmt: 'pdf', round: 1 },
    pages, text: pages.join('\n'), read_error: null };
}

test('an export is a .pdf read page by page, every page marked synthetic with its status, the same bytes twice, naming its codes', () => {
  const enc = encounter();
  enc.codes[0].decision = { action: 'approve' };
  const item = downloaded('approved', APPROVED_PAGES);
  assert.deepEqual(failed(walk.exportChecks(item, enc, 'approved')), []);
  assert.deepEqual(failed(walk.exportChecks(downloaded('draft', DRAFT_PAGES), enc, 'draft')), []);
  // the page's request names the kind, the format - the PDF, the only one made - and the round shown (FIX-SPEC-2 section 5)
  for (const body of [{ kind: 'approved', fmt: 'pdf' }, { kind: 'approved', fmt: 'pdf', round: 2 }, { kind: 'approved', fmt: 'pdf', round: '1' },
    { kind: 'draft', fmt: 'pdf', round: 1 }, { kind: 'approved', fmt: 'txt', round: 1 }, { kind: 'approved', fmt: 'csv', round: 1 }, null]) {
    assert.deepEqual(failed(walk.exportChecks({ ...item, body }, enc, 'approved')), ['export.approved.request'], JSON.stringify(body));
  }
  assert.match(walk.exportRequestProblems({ kind: 'approved', fmt: 'pdf', round: 2 }, enc, 'approved').join(), /round 2, not the round shown \(1\)/);
  assert.deepEqual(walk.exportRequestProblems({ kind: 'approved', fmt: 'txt', round: 1 }, enc, 'approved'), ['fmt "txt", not "pdf"']);
  assert.deepEqual(walk.exportRequestProblems(null, enc, 'draft'), ['the page posted no JSON object']);
  // made, and a .pdf: a refusal, an empty file or a download that is not a PDF fails the export itself
  for (const change of [{ status: 400 }, { size: 0 }, { filename: 'gi-02-approved.txt', suggested: 'gi-02-approved.txt' }]) {
    assert.deepEqual(failed(walk.exportChecks({ ...item, ...change }, enc, 'approved')), ['export.approved'], JSON.stringify(change));
  }
  assert.deepEqual(failed(walk.exportChecks({ ...item, refetch: { ...item.refetch, sha256: 'b'.repeat(64) } }, enc, 'approved')),
    ['export.approved.same_bytes']);
  // a file the walk's PDF reading refused: no page read, so nothing the report must show is shown
  assert.deepEqual(failed(walk.exportChecks({ ...item, pages: [], text: '', read_error: 'the PDF library refused it' }, enc, 'approved')),
    ['export.approved.read', 'export.approved.synthetic', 'export.approved.codes']);
  // every page - the last as well as the first - is marked synthetic and not for billing, with the report's own status
  const unmarked = [APPROVED_PAGES[0], APPROVED_PAGES[1].replace('Synthetic data · Not for billing or claims', '')];
  assert.deepEqual(failed(walk.exportChecks({ ...item, pages: unmarked, text: unmarked.join('\n') }, enc, 'approved')),
    ['export.approved.synthetic']);
  const mixed = [APPROVED_PAGES[0], APPROVED_PAGES[1].replace('APPROVED CODES', 'DRAFT · REVIEW REQUIRED')];
  assert.deepEqual(failed(walk.exportChecks({ ...item, pages: mixed, text: mixed.join('\n') }, enc, 'approved')),
    ['export.approved.synthetic']);
  // the status is read in each page's running block, never in its body: page 1's codes heading 'APPROVED CODES' does not
  // stand in for a running header that says otherwise (refutation round 4, R4-1-3)
  const firstWrong = [APPROVED_PAGES[0].replace('APPROVED CODES', 'DRAFT · REVIEW REQUIRED'), APPROVED_PAGES[1]];
  assert.ok(firstWrong[0].includes('APPROVED CODES   Only codes with a current saved approval'));
  assert.deepEqual(failed(walk.exportChecks({ ...item, pages: firstWrong, text: firstWrong.join('\n') }, enc, 'approved')),
    ['export.approved.synthetic']);
  // the draft names every code
  const short = DRAFT_PAGES.map(text => text.split('\n').filter(line => !line.includes('00731')).join('\n'));
  assert.deepEqual(failed(walk.exportChecks(downloaded('draft', short), enc, 'draft')), ['export.draft.codes']);
  assert.deepEqual(failed(walk.exportChecks({ kind: 'draft', error: 'the export option is disabled' }, enc, 'draft')), ['export.draft']);
});

test('a downloaded PDF is read as each page\'s lines, held to the status and synthetic words the server\'s report draws', async () => {
  // pdfPageLines: an item the library marks as ending its line ends it, any other is joined to the next by a space; a
  // last line is kept unless it is blank; a reading with no pages (one the library refused) has no lines
  const reading = { pages: [
    { items: [{ str: 'QuillMD', hasEOL: false }, { str: '', hasEOL: true }, { str: '01', hasEOL: false }, { str: '43239', hasEOL: true },
      { str: 'Page 1', hasEOL: false }] },
    { items: [{ str: 'Reason: EGD with biopsy is documented.', hasEOL: true }, { str: ' ', hasEOL: false }] },
    { items: [] }] };
  assert.deepEqual(walk.pdfPageLines(reading), [['QuillMD ', '01 43239', 'Page 1 '], ['Reason: EGD with biopsy is documented.'], []]);
  assert.deepEqual(walk.pdfPageLines({ error: 'the PDF library refused it' }), []);
  assert.deepEqual(walk.pdfPageLines(null), []);
  // with the pinned library, in Node: the dev preview's one-page mock download, line by line; what it refuses, no lines
  const { syntheticPdf } = require('./dev_preview_server.cjs');
  const mock = ['SYNTHETIC - NOT FOR BILLING', 'CPT Studio preview mock download (draft).', 'The real download is built by the server from the saved decisions.'];
  assert.deepEqual(walk.pdfPageLines(await walk.readDocument(syntheticPdf([mock]))).map(page => page.map(text => text.trim())), [mock]);
  assert.deepEqual(walk.pdfPageLines(await walk.readDocument(Buffer.from('not a PDF at all'))), []);
  // the words every page of a downloaded report is held to are the ones the server's report draws (studio/physician_report.py)
  assert.deepEqual(walk.REPORT_STATUS, REPORT_HEADS);
  const report = fs.readFileSync(path.join(__dirname, '..', 'studio', 'physician_report.py'), 'utf8');
  for (const words of [...Object.values(walk.REPORT_STATUS), 'Synthetic data · Not for billing or claims']) {
    assert.ok(report.includes(`'${words}'`), `studio/physician_report.py draws ${words}`);
  }
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

test('with --workspace the walk stops on a session in another workspace (owner direction 2026-11-22, D390)', () => {
  const session = { can_review: true, acknowledgement: 'I reviewed this code against the document.',
    workspace: { id: 'w1', name: 'Neurosurgery' } };
  assert.deepEqual(walk.sessionProblems(session, { allowLiveProvider: true, workspace: 'Neurosurgery' }), []);
  assert.deepEqual(walk.sessionProblems(session, { allowLiveProvider: true, workspace: null }), []);
  assert.match(walk.sessionProblems(session, { allowLiveProvider: true, workspace: 'Orthopedic Surgery' }).join(),
    /signed in to the workspace "Neurosurgery", not "Orthopedic Surgery"/);
  assert.match(walk.sessionProblems({ ...session, workspace: undefined }, { allowLiveProvider: true, workspace: 'Neurosurgery' }).join(),
    /signed in to the workspace null/);
  const REQUIRED_ARGS = ['--base-url', 'https://cpt.quillmd.com', '--credentials', 'a.json', '--operator-credentials', 'o.json',
    '--docs', 'd', '--out', 'o'];
  assert.equal(walk.parseArgs([...REQUIRED_ARGS, '--workspace', 'Orthopedic Surgery']).workspace, 'Orthopedic Surgery');
  assert.equal(walk.parseArgs(REQUIRED_ARGS).workspace, null);
});

test('the walk evidence names the workspace and specialty the session served, with or without --workspace (N1-3-4)', () => {
  const source = fs.readFileSync(path.join(__dirname, 'walk.cjs'), 'utf8');
  assert.ok(source.includes('evidence.session = ctx.session ? { workspace: ctx.session.workspace?.name ?? null,'));
  assert.ok(source.includes('specialty: ctx.session.workspace?.specialty ?? null,'));
});
