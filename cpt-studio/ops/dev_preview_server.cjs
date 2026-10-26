'use strict';
// Local visual-check server for the CPT Studio frontend. NOT used in production.
//
// Serves studio/templates/studio/*.html rendered as plain HTML (only the template
// tags those files use are supported; anything else fails loudly), the files in
// studio/static/studio/, and a mock of the JSON API in API.md backed by the
// synthetic fixtures in tests/fixtures/api/. Binds 127.0.0.1 on the first free
// port in 9170-9179.
//
// Request headers understood by the mock: "X-Preview-Session: agent" serves the
// agent session; "X-Preview-Encounters: empty" serves an empty document list.
// POST /__preview__/reset restarts the processing fixture, which turns into the
// ready fixture after two polls.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const TEMPLATES = path.join(ROOT, 'studio', 'templates', 'studio');
const STATIC = path.join(ROOT, 'studio', 'static', 'studio');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'api');
const HOST = '127.0.0.1';
const PORTS = Array.from({ length: 10 }, (_, i) => 9170 + i);
const MAX_BODY = 16 * 1024 * 1024;
const CSRF = crypto.randomBytes(16).toString('hex');
const PROCESSING_POLLS = 2;
const STATIC_TYPES = { 'styles.css': 'text/css; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'favicon.svg': 'image/svg+xml' };
// Same policy as studio.access.SecurityHeadersMiddleware, so violations surface here.
const CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'";
const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const ACTIONS = new Set(['approve', 'reject', 'reinstate', 'revoke']);

const readJson = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
const fixtures = {
  session: readJson('session.json'),
  agent: readJson('session-agent.json'),
  encounters: readJson('encounters.json'),
  empty: readJson('encounters-empty.json'),
  byId: new Map(fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).map(name => {
    const doc = readJson(name);
    return [doc.id, doc];
  })),
};
const ready = [...fixtures.byId.values()].find(doc => doc.title === 'Bidirectional endoscopy report');
const processing = [...fixtures.byId.values()].find(doc => doc.state === 'processing');
const polls = new Map();
const reports = new Map();

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

function encounterFor(id) {
  if (id === processing.id) {
    const seen = (polls.get(id) || 0) + 1;
    polls.set(id, seen);
    if (seen > PROCESSING_POLLS) return { ...ready, id, title: processing.title };
  }
  return fixtures.byId.get(id) || null;
}

async function handleApi(req, res, url) {
  const method = req.method;
  const route = url.pathname;
  if (method === 'POST' && req.headers['x-csrftoken'] !== CSRF) {
    return send(res, 403, '<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>', { 'Content-Type': 'text/html; charset=utf-8' });
  }
  if (method === 'GET' && route === '/api/session') {
    return json(res, 200, req.headers['x-preview-session'] === 'agent' ? fixtures.agent : fixtures.session);
  }
  if (method === 'GET' && route === '/api/encounters') {
    return json(res, 200, req.headers['x-preview-encounters'] === 'empty' ? fixtures.empty : fixtures.encounters);
  }
  if (method === 'POST' && route === '/api/encounters') {
    const body = (await readBody(req)).toString('latin1');
    if (!/^multipart\/form-data/.test(req.headers['content-type'] || '')) return apiError(res, 400, 'Send the document as multipart form data.');
    if (!/name="synthetic_attestation"\r\n\r\nyes\r\n/.test(body)) return apiError(res, 400, 'Confirm that the document is synthetic.');
    if (!/name="(file|text)"/.test(body)) return apiError(res, 400, 'Attach a file or paste the text.');
    polls.delete(processing.id);
    return json(res, 201, { id: processing.id });
  }
  let match = new RegExp(`^/api/encounters/(${UUID})$`).exec(route);
  if (match && method === 'GET') {
    const doc = encounterFor(match[1]);
    return doc ? json(res, 200, doc) : apiError(res, 404, 'Not found.');
  }
  match = new RegExp(`^/api/encounters/(${UUID})/(decisions|context|addenda|stop|reconcile|reports|original)$`).exec(route);
  if (match) {
    const doc = fixtures.byId.get(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    const [, , action] = match;
    if (action === 'original' && method === 'GET') {
      if (!doc.revision.source_file) return apiError(res, 404, 'This revision has no uploaded file.');
      return send(res, 200, 'Synthetic preview placeholder: the original bytes are served by the real API.\n', {
        'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="synthetic-original-placeholder.bin"',
      });
    }
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const body = action === 'stop' ? {} : parseJson(await readBody(req));
    if (!body) return apiError(res, 400, 'Send a JSON object.');
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
    const proposal = (doc.assessment?.proposals || []).find(item => item.id === body.proposal_id);
    if (!proposal || !ACTIONS.has(body.action)) return apiError(res, 400, 'Unknown proposal or action.');
    if (!proposal.allowed_actions.includes(body.action)) return apiError(res, 409, 'This action is not allowed for this proposal now.');
    if (body.action === 'approve' && !String(body.acknowledgement || '').trim()) return apiError(res, 400, 'Approval requires an acknowledgement.');
    return json(res, 201, { decision: { id: crypto.randomUUID(), proposal_id: proposal.id, action: body.action, note: body.note || '' } });
  }
  if (action === 'context') return json(res, 201, { context_id: crypto.randomUUID() });
  if (action === 'addenda') {
    if (!String(body.text || '').trim() || body.synthetic_attestation !== 'yes') return apiError(res, 400, 'Addendum text and synthetic attestation are required.');
    return json(res, 201, { revision_id: crypto.randomUUID() });
  }
  if (action === 'stop') return json(res, 200, { stopped: true });
  if (action === 'reconcile') {
    if (!String(body.note || '').trim()) return apiError(res, 400, 'A reconciliation note is required.');
    return json(res, 201, { reconciled: true });
  }
  if (!['draft', 'reviewed'].includes(body.kind) || !['txt', 'csv'].includes(body.fmt)) return apiError(res, 400, 'Unknown report kind or format.');
  if (body.kind === 'reviewed' && doc.readiness?.reviewed !== true) {
    return apiError(res, 409, 'A reviewed report is not ready.', { blockers: doc.readiness?.blockers || [] });
  }
  const id = crypto.randomUUID();
  const filename = `cpt-studio-preview-${body.kind}.${body.fmt}`;
  const content = body.fmt === 'csv'
    ? 'notice,kind\r\n"SYNTHETIC — NOT FOR BILLING","preview mock"\r\n'
    : `SYNTHETIC — NOT FOR BILLING\nCPT Studio preview mock report (${body.kind}).\nThe real report is built by the server from persisted decisions.\n`;
  reports.set(id, { content, filename, type: body.fmt === 'csv' ? 'text/csv; charset=utf-8' : 'text/plain; charset=utf-8' });
  return json(res, 201, { id, filename, sha256: crypto.createHash('sha256').update(content).digest('hex'), download_url: `/api/reports/${id}/download` });
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
    polls.clear();
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
