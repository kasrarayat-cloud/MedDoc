'use strict';
// Local visual-check server for the CPT Studio customer page. NOT used in production.
//
// Serves studio/templates/studio/*.html rendered as plain HTML (only the template tags those files use are supported;
// anything else fails loudly), the files in studio/static/studio/, and a mock of the customer JSON API (client contract
// customer-2026-11-20) backed by the hand-made customer fixtures in tests/fixtures/customer/. Binds 127.0.0.1 on the
// port given as --port=N, else on the first free port in 9170-9179.
//
// Request headers understood by the mock: "X-Preview-Session: agent" serves the agent session;
// "X-Preview-Encounters: empty" serves an empty document list.
// A new upload answers 201 with the reading fixture's id and plays it forward on each read: reading, then checking,
// then questions for you; sending answers plays a second coding review forward to ready for approval. The same
// client_key from the same session answers with the same id and creates nothing. Every other change (decisions, stop,
// resume, retry, downloads) answers as the real server does on success and never changes a fixture.
// The original document of every fixture is a synthetic one made here (SYNTHETIC_DOCUMENTS): a two-page PDF or plain
// text. GET .../original downloads it; GET .../original?view=1 serves it inline, framable by this origin only, for the
// page's viewer. The fixtures quote these documents exactly, on the pages given (tests/frontend/app.test.cjs).
// POST /__preview__/reset restarts the uploads; POST /__preview__/outdated makes every API call answer 409
// {"error_code": "client_outdated"} until the next reset; POST /__preview__/offline makes reads of a document fail
// (503) until the next reset, which shows the page's reconnecting line.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const TEMPLATES = path.join(ROOT, 'studio', 'templates', 'studio');
const STATIC = path.join(ROOT, 'studio', 'static', 'studio');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'customer');
const HOST = '127.0.0.1';
const PORTS = Array.from({ length: 10 }, (_, i) => 9170 + i);
const MAX_BODY = 16 * 1024 * 1024;
const MAX_ANSWER_CHARS = 2000;
const CSRF = crypto.randomBytes(16).toString('hex');
const STATIC_TYPES = { 'styles.css': 'text/css; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'favicon.svg': 'image/svg+xml' };
// The page's policy, as studio.access.SecurityHeadersMiddleware sends it, with the viewer's frame allowed from this
// origin only, so violations surface here.
const CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'";
// The in-page view of an original: framable by this origin only.
const VIEW_CSP = "frame-ancestors 'self'";
const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const ACTIONS = new Set(['approve', 'reject', 'revoke']);
const UPLOAD_TYPES = { pdf: 'application/pdf', txt: 'text/plain', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
const INSURANCE = new Set(['medicare', 'medicaid', 'commercial', 'unknown']);

// The synthetic documents the fixtures' quotes come from: invented, no real patient.
const SYNTHETIC_DOCUMENTS = {
  'synthetic-egd-colonoscopy.pdf': {
    type: 'application/pdf',
    pages: [
      ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Endoscopy report (fictional)',
        'Patient: Riley Synthetic. Date of service: 2026-11-02.', 'Procedures: upper endoscopy (EGD) and colonoscopy.',
        'EGD: The endoscope was passed to the second part of the duodenum.', 'Patchy erythema was seen in the gastric antrum.',
        'Cold forceps biopsies were taken from the gastric antrum.'],
      ['Colonoscopy: The colonoscope was advanced to the cecum.', 'The appendiceal orifice and the ileocecal valve were identified.',
        'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.', 'A 4 mm polyp in the ascending colon was removed with cold forceps.',
        'Bowel preparation quality was not recorded.', 'Impression: antral erythema; two colon polyps removed.'],
    ],
  },
  'synthetic-colonoscopy-note.txt': {
    type: 'text/plain',
    pages: [['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Colonoscopy note (fictional)',
      'Patient: Jordan Synthetic. Date of service: 2026-11-05.', 'The colonoscope was advanced to the cecum.',
      'A 12 mm pedunculated polyp in the descending colon was removed.', 'A 3 mm polyp in the rectum was seen and left in place.',
      'Upper endoscopy was planned but is not recorded as performed.']],
  },
  'pasted-cancelled-colonoscopy': {
    type: 'text/plain',
    pages: [['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Procedure note (fictional)',
      'Patient: Casey Synthetic. Date of service: 2026-11-06.', 'The patient arrived for colonoscopy.',
      'The procedure was cancelled before sedation because the patient had eaten that morning.', 'No scope was inserted.']],
  },
};

function pdfText(value) {
  return value.replace(/[\\()]/g, ch => `\\${ch}`);
}

// A minimal, valid PDF of plain text pages (Helvetica 11 pt), so the viewer has real pages to open at #page=N.
function syntheticPdf(pages) {
  const objects = [];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${pages.map((_, i) => `${4 + i * 2} 0 R`).join(' ')}] /Count ${pages.length} >>`;
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';
  pages.forEach((lines, i) => {
    const stream = ['BT', '/F1 11 Tf', '16 TL', '56 740 Td', ...lines.flatMap(line => [`(${pdfText(line)}) Tj`, 'T*']), 'ET'].join('\n');
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

// One synthetic document's bytes and type: a PDF of its pages, or its lines as plain text.
function documentBytes(name) {
  const source = SYNTHETIC_DOCUMENTS[name] || SYNTHETIC_DOCUMENTS['synthetic-colonoscopy-note.txt'];
  if (source.type === 'application/pdf') return { bytes: syntheticPdf(source.pages), type: source.type };
  return { bytes: Buffer.from(`${source.pages.flat().join('\n')}\n`, 'utf8'), type: 'text/plain; charset=utf-8' };
}

// The synthetic document a fixture's original stands for: by its name, a pasted text by its own key.
function documentFor(doc) {
  const name = doc?.document?.name;
  if (typeof name === 'string' && Object.hasOwn(SYNTHETIC_DOCUMENTS, name)) return name;
  if (doc?.document?.kind === 'paste') return 'pasted-cancelled-colonoscopy';
  return doc?.document?.media_type === 'application/pdf' ? 'synthetic-egd-colonoscopy.pdf' : 'synthetic-colonoscopy-note.txt';
}

// The fixtures, read when the server starts (requiring this file for its documents reads nothing). The played
// stages are named by file, never by which fixture a directory listing happens to give first.
let fixtures = null;

function loadFixtures() {
  const readJson = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
  return {
    session: readJson('session.json'),
    agent: readJson('session-agent.json'),
    encounters: readJson('encounters.json'),
    empty: readJson('encounters-empty.json'),
    byId: new Map(fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort().map(name => {
      const doc = readJson(name);
      return [doc.id, doc];
    })),
    reading: readJson('encounter-reading.json'),
    checking: readJson('encounter-checking.json'),
    asking: readJson('encounter-awaiting-answer.json'),
    results: readJson('encounter-ready.json'),
  };
}

const uploads = new Map();  // '<session> <client_key>' -> encounter id
const plays = new Map();    // encounter id -> {reads, at, answered, title, name, context, answers}
const reports = new Map();
const flags = { outdated: false, offline: false };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[ch]));
}

function renderTemplate(name, context = {}) {
  const html = fs.readFileSync(path.join(TEMPLATES, name), 'utf8')
    .replace(/\{%\s*load\s+static\s*%\}/g, '')
    .replace(/\{%\s*static\s+'([^']+)'\s*%\}/g, (_, file) => `/static/${file}`)
    .replace(/\{%\s*csrf_token\s*%\}/g, `<input type="hidden" name="csrfmiddlewaretoken" value="${CSRF}">`)
    .replace(/\{%\s*if\s+(\w+)\s*%\}([\s\S]*?)\{%\s*endif\s*%\}/g, (_, key, body) => (context[key] ? body : ''))
    .replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key) => escapeHtml(context[key]));
  if (/\{[%{]/.test(html)) throw new Error(`${name}: template syntax the preview renderer does not support`);
  return html;
}

function send(res, status, body, headers = {}) {
  res.writeHead(status, {
    'Content-Security-Policy': CSP, 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store', ...headers,
  });
  res.end(body);
}

const json = (res, status, data) => send(res, status, JSON.stringify(data), { 'Content-Type': 'application/json' });
const apiError = (res, status, message, details = {}) => json(res, status, { error: message, details });

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(new Error('body too large'));
        req.destroy();
      } else {
        chunks.push(chunk);
      }
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function parseJson(buffer) {
  try {
    const value = JSON.parse(buffer.toString('utf8') || '{}');
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

// One multipart field's text value (the mock reads only the small text fields it needs).
function formField(body, name) {
  const match = new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)\\r\\n`).exec(body);
  return match ? match[1] : '';
}

// The uploaded file's name, if the upload carried a file.
function formFileName(body) {
  const match = /name="file"; filename="([^"\r\n]*)"/.exec(body);
  return match ? match[1] : '';
}

const iso = ms => new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z');
const clone = value => JSON.parse(JSON.stringify(value));

// The just-uploaded document, played forward one read at a time, with its times taken from the upload.
function played(id) {
  const play = plays.get(id);
  play.reads += 1;
  const now = Date.now();
  const { reading, checking, asking, results } = fixtures;
  const stages = play.answered ? [[2, reading], [4, checking], [Infinity, results]] : [[2, reading], [5, checking], [Infinity, asking]];
  const base = clone(stages.find(([limit]) => play.reads <= limit)[1]);
  const round = play.answered ? 2 : 1;
  const done = !base.progress.busy;
  return {
    ...base, id, title: play.title, created_at: iso(play.at), updated_at: iso(now), context: play.context,
    document: {
      ...base.document, name: play.name, kind: play.kind, media_type: play.mediaType, size: play.size,
      original_url: play.kind === 'paste' ? null : `/api/encounters/${id}/original`, view_url: `/api/encounters/${id}/original?view=1`,
    },
    progress: { ...base.progress, started_at: iso(play.started), server_time: iso(now), finished_at: done ? iso(now - 1000) : null },
    round: { number: round, trigger: play.answered ? 'answers' : 'upload', finished_at: done ? iso(now - 1000) : null },
    answers: play.answers,
  };
}

function encounterFor(id) {
  if (plays.has(id)) return played(id);
  return fixtures.byId.get(id) || null;
}

async function handleApi(req, res, url) {
  const method = req.method;
  const route = url.pathname;
  if (method === 'POST' && req.headers['x-csrftoken'] !== CSRF) {
    return send(res, 403, '<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>', { 'Content-Type': 'text/html; charset=utf-8' });
  }
  if (flags.outdated) return json(res, 409, { error: 'CPT Studio was updated. Reload the page.', error_code: 'client_outdated' });
  const agent = req.headers['x-preview-session'] === 'agent';
  const session = agent ? fixtures.agent : fixtures.session;
  if (method === 'GET' && route === '/api/session') return json(res, 200, session);
  if (method === 'GET' && route === '/api/encounters') {
    return json(res, 200, req.headers['x-preview-encounters'] === 'empty' ? fixtures.empty : fixtures.encounters);
  }
  if (method === 'POST' && route === '/api/encounters') {
    const body = (await readBody(req)).toString('latin1');
    if (!/^multipart\/form-data/.test(req.headers['content-type'] || '')) return apiError(res, 400, 'Send the document as a file or as pasted text.');
    if (formField(body, 'synthetic_attestation') !== 'yes') return apiError(res, 400, 'Confirm that the document is synthetic.');
    if (!/name="(file|text)"/.test(body)) return apiError(res, 400, 'Attach a file or paste the text.');
    const insurance = formField(body, 'insurance') || 'unknown';
    if (!INSURANCE.has(insurance)) return apiError(res, 400, 'Choose the insurance, or Not sure.');
    const key = formField(body, 'client_key');
    if (!new RegExp(`^${UUID}$`).test(key)) return apiError(res, 400, 'This upload could not be identified. Reload the page and try again.');
    const seen = uploads.get(`${agent ? 'agent' : 'human'} ${key}`);
    if (seen) return json(res, 201, { id: seen });
    const id = fixtures.reading.id;
    const file = formFileName(body);
    const date = formField(body, 'service_date');
    // the played document keeps one type and size from the upload on, as a real one does
    const mediaType = file ? UPLOAD_TYPES[(/\.(pdf|docx|txt)$/i.exec(file) || [])[1]?.toLowerCase()] || 'text/plain' : 'text/plain';
    const shown = documentFor({ document: { name: file, kind: file ? 'upload' : 'paste', media_type: mediaType } });
    uploads.set(`${agent ? 'agent' : 'human'} ${key}`, id);
    plays.set(id, {
      reads: 0, at: Date.now(), started: Date.now() + 1000, answered: false, answers: [],
      title: file ? file.replace(/\.(pdf|docx|txt)$/i, '') : 'Pasted clinical text', name: file || null, kind: file ? 'upload' : 'paste',
      mediaType, size: documentBytes(shown).bytes.length,
      context: { service_date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null, insurance },
    });
    return json(res, 201, { id });
  }
  let match = new RegExp(`^/api/encounters/(${UUID})$`).exec(route);
  if (match && method === 'GET') {
    if (flags.offline) return apiError(res, 503, 'The service is not available right now.');
    const doc = encounterFor(match[1]);
    return doc ? json(res, 200, doc) : apiError(res, 404, 'Not found.');
  }
  match = new RegExp(`^/api/encounters/(${UUID})/original$`).exec(route);
  if (match && method === 'GET') {
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    const view = url.searchParams.get('view') === '1';
    if (!view && !doc.document.original_url) return apiError(res, 404, 'This document was pasted, so there is no original file.');
    const name = documentFor(doc);
    const { bytes, type } = documentBytes(name);
    const filename = doc.document.name || 'pasted-text.txt';
    if (!view) return send(res, 200, bytes, { 'Content-Type': type, 'Content-Disposition': `attachment; filename="${filename}"` });
    return send(res, 200, bytes, {
      'Content-Type': type, 'Content-Disposition': `inline; filename="${filename}"`, 'X-Frame-Options': 'SAMEORIGIN', 'Content-Security-Policy': VIEW_CSP,
    });
  }
  match = new RegExp(`^/api/encounters/(${UUID})/(answers|decisions|stop|resume|retry|reports)$`).exec(route);
  if (match) {
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const body = parseJson(await readBody(req));
    if (!body) return apiError(res, 400, 'This could not be saved. Reload the page and try again.');
    return handleChange(res, doc, match[2], body, session);
  }
  match = new RegExp(`^/api/reports/(${UUID})/download$`).exec(route);
  if (match && method === 'GET') {
    const report = reports.get(match[1]);
    if (!report) return apiError(res, 404, 'Not found.');
    return send(res, 200, report.content, { 'Content-Type': report.type, 'Content-Disposition': `attachment; filename="${report.filename}"` });
  }
  return apiError(res, 404, 'Not found.');
}

function handleChange(res, doc, action, body, session) {
  if (action === 'answers') {
    const answers = Array.isArray(body.answers) ? body.answers : [];
    if (!answers.length) return apiError(res, 400, 'Write an answer to at least one question.');
    const questions = new Map((doc.questions || []).map(question => [question.id, question]));
    for (const answer of answers) {
      if (!questions.has(answer?.question_id)) return apiError(res, 409, 'A question is no longer asked. Reload the page.');
      const value = typeof answer.text === 'string' ? answer.text.trim() : '';
      if (!value || [...value].length > MAX_ANSWER_CHARS) return apiError(res, 400, 'Each answer needs text, up to 2,000 characters.');
    }
    const play = plays.get(doc.id);
    if (play) {
      play.answered = true;
      play.reads = 0;
      play.started = Date.now() + 1000;
      play.answers = answers.map(answer => ({ question: questions.get(answer.question_id).text, answer: answer.text.trim(), by: session.user.label, at: iso(Date.now()) }));
    }
    return json(res, 201, { round: (doc.round?.number || 1) + 1 });
  }
  if (action === 'decisions') {
    const code = (doc.codes || []).find(item => item.code === body.code);
    if (!code || !ACTIONS.has(body.action)) return apiError(res, 400, 'That code or action is not part of this document.');
    if (!code.allowed_actions.includes(body.action)) return apiError(res, 409, 'This action is not available for this code right now.');
    if (body.action === 'approve' && body.acknowledgement !== session.acknowledgement) return apiError(res, 400, 'An approval needs the exact confirmation statement.');
    return json(res, 201, { decision: { code: code.code, action: body.action, note: typeof body.note === 'string' ? body.note : '' } });
  }
  if (action === 'stop') return doc.progress?.can_stop ? json(res, 200, { stopped: true }) : apiError(res, 409, 'Nothing is running for this document.');
  if (action === 'resume') return doc.progress?.can_resume ? json(res, 200, { resumed: true }) : apiError(res, 409, 'There is nothing to resume for this document.');
  if (action === 'retry') return doc.progress?.can_retry ? json(res, 201, { round: (doc.round?.number || 1) + 1 }) : apiError(res, 409, 'This document cannot be retried right now.');
  if (!['draft', 'approved'].includes(body.kind) || !['txt', 'csv'].includes(body.fmt)) return apiError(res, 400, 'Choose a download.');
  if (body.kind === 'approved' && doc.readiness?.approved !== true) {
    return apiError(res, 409, 'The approved download is not available yet.', { blockers: doc.readiness?.blockers || [] });
  }
  if (body.kind === 'draft' && doc.readiness?.draft !== true) return apiError(res, 409, 'Nothing can be downloaded yet.', { blockers: doc.readiness?.blockers || [] });
  const id = crypto.randomUUID();
  const filename = `cpt-studio-preview-${body.kind}.${body.fmt}`;
  const content = body.fmt === 'csv'
    ? 'notice,kind\r\n"SYNTHETIC — NOT FOR BILLING","preview mock"\r\n'
    : `SYNTHETIC — NOT FOR BILLING\nCPT Studio preview mock download (${body.kind}).\nThe real download is built by the server from the saved decisions.\n`;
  reports.set(id, { content, filename, type: body.fmt === 'csv' ? 'text/csv; charset=utf-8' : 'text/plain; charset=utf-8' });
  return json(res, 201, { id, kind: body.kind, fmt: body.fmt, filename, generated_at: iso(Date.now()), download_url: `/api/reports/${id}/download`, current: true });
}

async function handle(req, res) {
  let url;
  try {
    url = new URL(req.url, `http://${HOST}`);
  } catch {
    return send(res, 400, 'Bad request');
  }
  if (url.pathname.startsWith('/api/')) return handleApi(req, res, url);
  if (req.method === 'POST' && url.pathname === '/__preview__/reset') {
    uploads.clear();
    plays.clear();
    flags.outdated = false;
    flags.offline = false;
    return send(res, 204, '');
  }
  if (req.method === 'POST' && url.pathname === '/__preview__/outdated') {
    flags.outdated = true;
    return send(res, 204, '');
  }
  if (req.method === 'POST' && url.pathname === '/__preview__/offline') {
    flags.offline = true;
    return send(res, 204, '');
  }
  if (req.method === 'GET' && url.pathname === '/') {
    return send(res, 200, renderTemplate('index.html'), {
      'Content-Type': 'text/html; charset=utf-8', 'Set-Cookie': `cptstudio_csrf=${CSRF}; Path=/; SameSite=Strict`,
    });
  }
  if (url.pathname === '/login/') {
    if (req.method === 'POST') return send(res, 302, '', { Location: '/' });
    const context = { error: url.searchParams.has('error') ? 'The username or password is not correct.' : '', username: url.searchParams.get('username') || '', next: url.searchParams.get('next') || '' };
    return send(res, 200, renderTemplate('login.html', context), {
      'Content-Type': 'text/html; charset=utf-8', 'Set-Cookie': `cptstudio_csrf=${CSRF}; Path=/; SameSite=Strict`,
    });
  }
  if (req.method === 'POST' && url.pathname === '/logout/') return send(res, 302, '', { Location: '/login/' });
  const name = url.pathname.startsWith('/static/studio/') ? url.pathname.slice('/static/studio/'.length) : '';
  if (req.method === 'GET' && Object.hasOwn(STATIC_TYPES, name)) {
    return send(res, 200, fs.readFileSync(path.join(STATIC, name)), { 'Content-Type': STATIC_TYPES[name] });
  }
  return send(res, 404, 'Not found', { 'Content-Type': 'text/plain; charset=utf-8' });
}

function listen(ports) {
  fixtures = fixtures || loadFixtures();
  const [port, ...rest] = ports;
  if (port === undefined) {
    process.stderr.write('No free port.\n');
    process.exit(1);
  }
  const server = http.createServer((req, res) => {
    handle(req, res).catch(error => {
      process.stderr.write(`${req.method} ${req.url} failed: ${error.message}\n`);
      if (!res.headersSent) send(res, 500, 'Preview server error', { 'Content-Type': 'text/plain; charset=utf-8' });
    });
  });
  server.once('error', error => {
    if (error.code === 'EADDRINUSE') listen(rest);
    else throw error;
  });
  server.listen(port, HOST, () => {
    process.stdout.write(`CPT Studio dev preview (mock API, not production): http://${HOST}:${port}/ pid ${process.pid}\n`);
  });
  const stop = () => {
    server.closeAllConnections();
    server.close(() => process.exit(0));
  };
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
}

if (require.main === module) {
  const asked = process.argv.map(arg => /^--port=(\d{2,5})$/.exec(arg)).find(Boolean);
  listen(asked ? [Number(asked[1])] : PORTS);
}

module.exports = { SYNTHETIC_DOCUMENTS, syntheticPdf, documentBytes, documentFor };
