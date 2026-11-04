'use strict';
// Local visual-check server for the CPT Studio customer page. NOT used in production.
//
// Serves studio/templates/studio/*.html rendered as plain HTML (only the template tags those files use are supported;
// anything else fails loudly), the files in studio/static/studio/, and a mock of the customer JSON API backed by the
// hand-made customer fixtures in tests/fixtures/customer/ (design section 7). Binds 127.0.0.1 on the first free port
// in 9170-9179.
//
// Request headers understood by the mock: "X-Preview-Session: agent" serves the agent session;
// "X-Preview-Encounters: empty" serves an empty document list.
// A new upload answers 201 with the "just uploaded" fixture's id and plays it forward on each read: waiting to start,
// then the checks running, then results (or "Action needed" when the upload entered a date of service that differs
// from the document's). The same client_key from the same session answers with the same id and creates nothing.
// Every other mutation (decisions, details, answer revocation, stop, resume, addenda, downloads) answers as the real
// API does on success and never changes a fixture.
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
const CSRF = crypto.randomBytes(16).toString('hex');
const STATIC_TYPES = { 'styles.css': 'text/css; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'favicon.svg': 'image/svg+xml' };
// Same policy as studio.access.SecurityHeadersMiddleware, so violations surface here.
const CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'";
const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const ACTIONS = new Set(['approve', 'reject', 'reinstate', 'confirm', 'revoke']);
const MODIFIERS = new Set(['59', 'XS']);
const DETAIL_VALUES = new Set(['not_documented', 'cannot_confirm', 'use_document']);
// This release offers no reviewer confirmation of a located answer; the server refuses it with this sentence.
const CONFIRMATIONS_NOT_OFFERED = 'This release offers no reviewer confirmation, so nothing was recorded.';

const readJson = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const fixtures = {
  session: readJson('session.json'),
  agent: readJson('session-agent.json'),
  encounters: readJson('encounters.json'),
  empty: readJson('encounters-empty.json'),
  byId: new Map(fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort().map(name => {
    const doc = readJson(name);
    return [doc.id, doc];
  })),
};
// Named by file, never by which fixture a directory listing happens to give first.
const uploaded = readJson('encounter-queued.json');
const checking = readJson('encounter-processing.json');
const results = readJson('encounter-ready.json');
const dateHold = readJson('encounter-action-needed.json');
const uploads = new Map();  // '<session> <client_key>' -> encounter id
const plays = new Map();    // encounter id -> {reads, at, held}
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

const iso = ms => new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z');

// The just-uploaded document, played forward one read at a time, with its times taken from the upload.
function played(id) {
  const play = plays.get(id);
  play.reads += 1;
  const now = Date.now();
  const shift = doc => ({
    ...doc, id, title: uploaded.title, created_at: iso(play.at),
    progress: { ...doc.progress, started_at: iso(play.at + 1000), server_time: iso(now), finished_at: doc.progress.finished_at ? iso(now - 1000) : null },
  });
  if (play.reads <= 2) return shift(uploaded);
  if (play.held) return { ...shift(dateHold), document: { ...dateHold.document, original_url: `/api/encounters/${id}/original` } };
  if (play.reads <= 6) return { ...shift(checking), document: { ...checking.document, original_url: `/api/encounters/${id}/original` } };
  return { ...shift(results), document: { ...results.document, original_url: `/api/encounters/${id}/original` } };
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
  if (method === 'GET' && route === '/api/session') return json(res, 200, agent ? fixtures.agent : fixtures.session);
  if (method === 'GET' && route === '/api/encounters') {
    return json(res, 200, req.headers['x-preview-encounters'] === 'empty' ? fixtures.empty : fixtures.encounters);
  }
  if (method === 'POST' && route === '/api/encounters') {
    const body = (await readBody(req)).toString('latin1');
    if (!/^multipart\/form-data/.test(req.headers['content-type'] || '')) return apiError(res, 400, 'Send the document as a file or as pasted text.');
    if (formField(body, 'synthetic_attestation') !== 'yes') return apiError(res, 400, 'Confirm that the document is synthetic.');
    if (!/name="(file|text)"/.test(body)) return apiError(res, 400, 'Attach a file or paste the text.');
    const key = formField(body, 'client_key');
    if (!new RegExp(`^${UUID}$`).test(key)) return apiError(res, 400, 'This upload could not be identified. Reload the page and try again.');
    const seen = uploads.get(`${agent ? 'agent' : 'human'} ${key}`);
    if (seen) return json(res, 201, { id: seen });
    const id = uploaded.id;
    const date = formField(body, 'service_date');
    uploads.set(`${agent ? 'agent' : 'human'} ${key}`, id);
    plays.set(id, { reads: 0, at: Date.now(), held: Boolean(date) && date !== results.service_date.document_value });
    return json(res, 201, { id });
  }
  let match = new RegExp(`^/api/encounters/(${UUID})$`).exec(route);
  if (match && method === 'GET') {
    if (flags.offline) return apiError(res, 503, 'The service is not available right now.');
    const doc = encounterFor(match[1]);
    return doc ? json(res, 200, doc) : apiError(res, 404, 'Not found.');
  }
  match = new RegExp(`^/api/encounters/(${UUID})/clarifications/(${UUID})/confirm$`).exec(route);
  if (match) return apiError(res, 409, CONFIRMATIONS_NOT_OFFERED);
  match = new RegExp(`^/api/encounters/(${UUID})/details/(${UUID})/revoke$`).exec(route);
  if (match) {
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    const known = (doc.details_needed || []).some(row => row.saved && row.saved.answer_id === match[2]);
    return known ? json(res, 201, { revoked: true }) : apiError(res, 404, 'That answer is not part of this document.');
  }
  match = new RegExp(`^/api/encounters/(${UUID})/(decisions|details|addenda|stop|resume|reports|original)$`).exec(route);
  if (match) {
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    const [, , action] = match;
    if (action === 'original' && method === 'GET') {
      if (!doc.document.original_url) return apiError(res, 404, 'This document was pasted, so there is no original file.');
      return send(res, 200, 'Synthetic preview placeholder: the original file is served by the real API.\n', {
        'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="synthetic-original-placeholder.bin"',
      });
    }
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const body = parseJson(await readBody(req));
    if (!body) return apiError(res, 400, 'This could not be saved. Reload the page and try again.');
    return handleMutation(res, doc, action, body);
  }
  match = new RegExp(`^/api/reports/(${UUID})/download$`).exec(route);
  if (match && method === 'GET') {
    const report = reports.get(match[1]);
    if (!report) return apiError(res, 404, 'Not found.');
    return send(res, 200, report.content, { 'Content-Type': report.type, 'Content-Disposition': `attachment; filename="${report.filename}"` });
  }
  return apiError(res, 404, 'Not found.');
}

function handleMutation(res, doc, action, body) {
  if (action === 'decisions') {
    const code = (doc.codes || []).find(item => item.id === body.proposal_id);
    if (!code || !ACTIONS.has(body.action)) return apiError(res, 400, 'That code or action is not part of this document.');
    if (!code.allowed_actions.includes(body.action)) return apiError(res, 409, 'This action is not available for this code right now.');
    if (body.action === 'approve' && !String(body.acknowledgement || '').trim()) return apiError(res, 400, 'An approval needs the confirmation that you read the document.');
    const modifiers = Array.isArray(body.modifiers) ? body.modifiers : [];
    if (modifiers.length > 1 || modifiers.some(item => !MODIFIERS.has(item)) || (modifiers.length && !(code.modifier_review?.options || []).includes(modifiers[0]))) {
      return apiError(res, 400, 'Choose one modifier the review offers, or none.');
    }
    return json(res, 201, { decision: { id: crypto.randomUUID(), proposal_id: code.id, action: body.action, note: body.note || '', modifiers } });
  }
  if (action === 'details') {
    const answers = Array.isArray(body.answers) ? body.answers : [];
    if (!answers.length) return apiError(res, 400, 'Choose an answer for at least one detail.');
    const rows = new Map((doc.details_needed || []).map(row => [row.id, row]));
    for (const answer of answers) {
      const row = rows.get(answer?.id);
      if (!row || row.fact !== answer.fact || row.saved) return apiError(res, 409, 'A detail was already answered or is no longer asked. Reload the page.');
      const allowed = DETAIL_VALUES.has(answer.value) ? (answer.value === 'use_document' ? row.control === 'date' && Boolean(row.document_value) : row.allow.includes(answer.value))
        : row.control === 'choice' ? row.choices.some(choice => choice.value === answer.value) : row.control === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(answer.value);
      if (!allowed) return apiError(res, 400, 'One of the answers is not one of the choices offered.');
    }
    return json(res, 201, { saved: answers.length });
  }
  if (action === 'addenda') {
    if (!String(body.text || '').trim() || body.synthetic_attestation !== 'yes') return apiError(res, 400, 'Write the addendum and confirm that it is synthetic.');
    return json(res, 201, { revision: (doc.document?.revision || 1) + 1 });
  }
  if (action === 'stop') return doc.progress?.can_stop ? json(res, 200, { stopped: true }) : apiError(res, 409, 'Nothing is running for this document.');
  if (action === 'resume') return doc.progress?.can_resume ? json(res, 200, { resumed: true }) : apiError(res, 409, 'There is nothing to resume for this document.');
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
  return json(res, 201, { id, kind: body.kind, fmt: body.fmt, filename, download_url: `/api/reports/${id}/download` });
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
  const [port, ...rest] = ports;
  if (port === undefined) {
    process.stderr.write('No free port in 9170-9179.\n');
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

listen(PORTS);
