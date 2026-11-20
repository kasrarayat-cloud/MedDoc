'use strict';
/*
 * Unit tests for ops/walk.cjs's pure helpers: argument parsing, the documents and credentials it reads, the denylist
 * scan (every vector of ops/verification/customer-denylist.json, which ops/verify_downloads.py and ops/scan_customer.py
 * run too, so the readers cannot drift apart), the JSON and DOM contract checks, and the evidence's shape. No browser,
 * network or server: synthetic values only.
 *
 *   node ops/test_walk.cjs            (or: node --test --test-reporter=tap ops/test_walk.cjs)
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const walk = require('./walk.cjs');

const BASE = 'https://cpt.example.test';
const PASSWORD = 'Synthetic-walk pass&+%<>"\'é/=?-2026';
const REQUIRED = ['--base-url', BASE, '--credentials', 'c.json', '--operator-credentials', 'o.json', '--docs', 'docs',
  '--out', 'out'];
const DENYLIST = JSON.parse(fs.readFileSync(path.join(__dirname, 'verification', 'customer-denylist.json'), 'utf8'));

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

function encounter(overrides = {}) {
  const codes = overrides.codes || [
    { code: '43239', units: 1, modifiers: [], status: 'ready', status_label: 'Ready for approval',
      reason: 'EGD with biopsy is documented.', second_check: { agrees: true, reason: 'The report states the biopsy.' },
      question: null, quotes: [{ text: 'Cold forceps biopsies were taken from the antrum.', page: 1 }], decision: null,
      allowed_actions: ['approve', 'reject'] },
    { code: '00731', units: 1, modifiers: ['P2'], status: 'needs_answer', status_label: 'Needs your answer',
      reason: 'Anesthesia time is not stated.', second_check: { agrees: null, reason: '' },
      question: 'How long was the anesthesia?', quotes: [], decision: null, allowed_actions: [] },
  ];
  return {
    id: 'e5c1d3a2-1111-4222-8333-944455556666', title: 'gi-02', created_at: '2026-11-20T10:00:00Z',
    updated_at: '2026-11-20T10:05:00Z', state: 'awaiting_answer', state_label: 'Questions for you',
    permissions: { can_review: true },
    document: { name: 'gi-02.txt', media_type: 'text/plain', size: 10, kind: 'txt',
      original_url: '/api/encounters/e5c1d3a2-1111-4222-8333-944455556666/original',
      view_url: '/api/encounters/e5c1d3a2-1111-4222-8333-944455556666/original?view=1' },
    context: { service_date: '2026-10-14', insurance: 'medicare' },
    progress: { phase: 'done', busy: false, started_at: null, finished_at: null, server_time: null, message: '', can_stop: false,
      can_resume: false, can_retry: true, error: null },
    round: { number: 1, trigger: 'upload', finished_at: '2026-11-20T10:05:00Z' },
    codes,
    questions: [{ id: 'q1', text: 'How long was the anesthesia?', codes: ['00731'] }], answers: [],
    notes: ['The indication is not stated.'], readiness: { draft: true, approved: false, blockers: ['No code is approved.'] },
    reports: [], activity: [],
    ...overrides,
  };
}

function domOf(enc) {
  return {
    progress: { phase: enc.progress.phase, steps: ['reading', 'checking', 'finished'].map(step => ({ step, state: 'done' })) },
    questions: enc.questions.length ? { heading: 'Questions for you', send: true,
      rows: enc.questions.map(q => ({ id: q.id, text: `${q.text} Your answer`, textarea: true })) } : null,
    codes: enc.codes.map(code => ({ code: code.code, status: code.status, number: code.code, units: `× ${code.units}`,
      modifiers: code.modifiers.join(' '), badge: { status: code.status, text: code.decision ? 'Approved' : code.status_label },
      reason: code.reason, check: `Second check: ${code.second_check.reason}`, quotes: true,
      buttons: code.allowed_actions.map(decision => ({ decision, code: code.code })) })),
    quotesPanel: true,
    quotes: enc.codes.flatMap(code => code.quotes.map(quote => ({ code: code.code, page: quote.page === null ? '' : String(quote.page) }))),
    notes: `Documentation notes ${enc.notes.join(' ')}`,
    viewer: { src: `${enc.document.view_url}#page=1`, original: enc.document.original_url },
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
  assert.deepEqual(failed(walk.jsonChecks(missing, doc)), ['json.keys']);
  assert.deepEqual(failed(walk.jsonChecks(encounter(), { serviceDate: '2026-10-15', insurance: 'medicare' })), ['json.context']);
  const unknown = encounter();
  unknown.codes[0].status = 'held';
  unknown.codes[0].allowed_actions = [];
  assert.deepEqual(failed(walk.jsonChecks(unknown, doc)), ['json.codes.status']);
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
    'dom.viewer': dom => { dom.viewer.src = '/api/encounters/another/original?view=1'; },
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

test('the readers that run in the page are self-contained functions', () => {
  for (const reader of [walk.readEncounterDom, walk.collectDomStrings]) {
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
    sha256: 'a'.repeat(64), text, refetch: { status: 200, sha256: 'a'.repeat(64), size: text.length } };
  assert.deepEqual(failed(walk.exportChecks(item, enc, 'approved')), []);
  assert.deepEqual(failed(walk.exportChecks({ ...item, refetch: { ...item.refetch, sha256: 'b'.repeat(64) } }, enc, 'approved')),
    ['export.approved.same_bytes']);
  assert.deepEqual(failed(walk.exportChecks({ ...item, text: text.replace(/SYNTHETIC - NOT FOR BILLING\n$/, '') }, enc, 'approved')),
    ['export.approved.synthetic']);
  assert.deepEqual(failed(walk.exportChecks(item, enc, 'draft')), ['export.draft.codes']);  // the draft names every code
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
  assert.deepEqual(walk.CLIENT_HEADERS, { 'X-CPT-Studio-Client': 'customer-2026-11-20' });
  const source = fs.readFileSync(path.join(__dirname, 'walk.cjs'), 'utf8');
  assert.ok(source.includes("const CLIENT_HEADERS = { 'X-CPT-Studio-Client': 'customer-2026-11-20' };"));
  assert.ok(source.includes('chromium.launch({ headless: true })'));
  const session = { can_review: true, acknowledgement: 'I reviewed this code against the document.' };
  assert.deepEqual(walk.sessionProblems(session, { allowLiveProvider: true }), []);
  assert.match(walk.sessionProblems(session, { allowLiveProvider: false }).join(), /--allow-live-provider/);
  assert.match(walk.sessionProblems({ ...session, can_review: false }, { allowLiveProvider: true }).join(), /cannot review/);
  assert.match(walk.sessionProblems({ ...session, acknowledgement: ' ' }, { allowLiveProvider: true }).join(), /no acknowledgement/);
  assert.equal(walk.summarize(encounter()).codes[0].quotes, 1);  // the evidence keeps counts, never the document's text
  assert.ok(!JSON.stringify(walk.summarize(encounter())).includes('antrum'));
});
