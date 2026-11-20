#!/usr/bin/env node
'use strict';
/*
 * The browser walk of the Fable coding build (DECISIONS D351-D353; the build specification, sections 6, 7 and 11): a
 * running CPT Studio (the deployed site or a local one) driven through the CUSTOMER page with synthetic documents, with
 * a separate PLATFORM-OPERATOR session beside it as the positive control of the operator gate. It replaces the
 * earlier browser verifier, which was bound to the earlier customer contract.
 *
 *   node ops/walk.cjs --base-url https://cpt.quillmd.com --credentials agent.json --operator-credentials ops-agent.json \
 *     --docs DIR_OR_FILE --out EVIDENCE_DIR [--deadline-seconds 1800] [--allow-live-provider] \
 *     [--service-date YYYY-MM-DD] [--insurance medicare|medicaid|commercial|unknown]
 *
 * --credentials and --operator-credentials each name a private JSON file (no group or other access, checked on the
 * descriptor that is read) holding a flat {"username", "password"}: the customer account (an agent reviewer of a
 * synthetic workspace) and a platform operator. They are read by path; no password is ever printed or written, also
 * where a server would echo it back. --docs names one synthetic document or a directory of them (.txt, .pdf, .docx, in
 * name order). Each upload carries a service date (--service-date, else the "Date of service:" or "Date of procedure:"
 * line of a .txt document's own text; a document with neither is refused before anything is uploaded) and an insurance
 * (--insurance, commercial when not given). The customer session serves no provider mode, so every upload may make paid
 * requests: the walk refuses to upload without --allow-live-provider.
 *
 * Per document, through the page: New document -> the file, the service date, the insurance and the synthetic
 * attestation -> Start; then GET /api/encounters/<id> is polled until progress.phase is done, failed or stopped (each
 * wait bounded by --deadline-seconds). On done: the JSON against the contract of section 6 (its keys, the code statuses,
 * each code's allowed actions by its status and decision, the context as uploaded); the page against the DOM contract
 * of section 7 (the progress panel and its steps, the questions panel, the code rows with their number, units,
 * modifiers, status badge, reason, second check, quotes and exactly the allowed buttons, the quotes panel - a quote
 * with a page moves the viewer to #page=N - the notes panel, the document viewer and its "Download original" link, the
 * export button); the first question, when there is
 * one, answered through the panel and the new round waited for and checked again; one READY code approved through
 * #reviewDialog with the session's acknowledgement (an agent-executed synthetic review); the draft and the approved TXT
 * exported through the export dialog as real browser downloads, each fetched again from its download_url and compared
 * byte for byte; a 390x844 viewport with no horizontal scroll; every /ops/ path 404 to the customer (GET, and POST with
 * a valid CSRF token for an encounter id that does not exist, so a broken gate changes nothing), never 200 to nobody
 * signed in, and 200 to the operator (the positive control: a broken instrument and a closed door read the same). Every
 * customer API body and header the page or the walk received, every DOM text node and wording attribute, and every
 * download are scanned with ops/verification/customer-denylist.json (vendor and model names, tokens, credits, sha256,
 * request ids, /ops/ links ...); a string that is the document's own text or one of its quotes is not scanned.
 *
 * Nothing is retried. A failure is recorded and the walk goes on with the next document. A file named STOP in the
 * evidence directory stops the walk before the next upload. Everything is written to EVIDENCE_DIR/evidence.json (schema
 * cpt-studio-walk-evidence@1): per document its result (pass or fail), the reasons of every failed check, and every
 * check. Exit 0 when every document and run check passed, 1 when anything failed, 2 on a usage error before any upload.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const PLAYWRIGHT = process.env.CPT_VERIFY_PLAYWRIGHT
  || '/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/browser-deps/node_modules/playwright';
const EVIDENCE_SCHEMA = 'cpt-studio-walk-evidence@1';
// studio/client_contract.py VERSION, with app.js and ops/verify_login.py (tests/test_cux_client_contract.py pins them).
const CLIENT_HEADERS = { 'X-CPT-Studio-Client': 'customer-2026-11-20' };
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } };
const UI_TIMEOUT_MS = 30000;
const POLL_MS = 3000;
const MAX_POLL_ERRORS = 3;
const DEFAULT_DEADLINE_SECONDS = 1800;
const MIN_DEADLINE_SECONDS = 60;
const SETTLED_PHASES = new Set(['done', 'failed', 'stopped']);
const PHASES = new Set(['queued', 'reading', 'checking', 'done', 'failed', 'stopped']);
const CODE_STATUSES = new Set(['ready', 'needs_answer', 'needs_review', 'not_supported']);
const STEPS = ['reading', 'checking', 'finished'];
const INSURANCE = ['medicare', 'medicaid', 'commercial', 'unknown'];
const DOCUMENT_TYPES = { '.txt': 'text/plain', '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
const ENCOUNTER_KEYS = ['id', 'title', 'created_at', 'updated_at', 'state', 'state_label', 'permissions', 'document',
  'context', 'progress', 'round', 'codes', 'questions', 'answers', 'notes', 'readiness', 'reports', 'activity'];
const CODE_KEYS = ['code', 'units', 'modifiers', 'status', 'status_label', 'reason', 'second_check', 'question', 'quotes',
  'decision', 'allowed_actions'];
const DECISION_WORDS = { approve: 'Approved', reject: 'Rejected' };
const QUESTIONS_HEADING = 'Questions for you';
const WALK_ANSWER = 'Not documented in this synthetic note.';
const WALK_NOTE = 'agent-executed synthetic review (walk)';
const DATE_LINE = /\bdate of (?:service|procedure)\s*:\s*(\d{4}-\d{2}-\d{2})\b/i;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const CSRF_COOKIE = 'cptstudio_csrf';  // cptstudio/settings.py CSRF_COOKIE_NAME; the page sends it as X-CSRFToken
// ops/verify_login.py MAX_CREDENTIALS_BYTES: a larger credentials file is refused.
const MAX_CREDENTIALS_BYTES = 64 * 1024;
// The Playwright debug logs that carry a call's parameters or the browser protocol, so a typed password.
const PASSWORD_LOGS = ['pw:api', 'pw:channel', 'pw:protocol', 'pw:server:channel'];
const WITHHELD = '[password withheld]';
// Response headers that carry no customer-facing wording (security policy, cookies, caching, dates).
const UNSCANNED_HEADERS = new Set(['set-cookie', 'date', 'etag', 'last-modified', 'content-length', 'content-security-policy',
  'content-security-policy-report-only', 'strict-transport-security', 'permissions-policy', 'report-to', 'nel', 'expires',
  'cache-control', 'vary', 'connection', 'keep-alive', 'transfer-encoding', 'content-encoding', 'accept-ranges', 'age',
  'content-disposition', 'x-frame-options', 'referrer-policy', 'cross-origin-opener-policy', 'x-content-type-options']);
const OPS_GET_PATHS = id => ['/ops/', '/ops/encounters/', `/ops/encounters/${id}`];
const OPS_POST_PATHS = id => [`/ops/encounters/${id}/retry`, `/ops/encounters/${id}/reconcile`, `/ops/holds/${id}/release`];
const DENYLIST_FILE = path.join(__dirname, 'verification', 'customer-denylist.json');
const USAGE = 'usage: walk.cjs --base-url URL --credentials FILE --operator-credentials FILE --docs DIR_OR_FILE --out DIR '
  + '[--deadline-seconds N] [--allow-live-provider] [--service-date YYYY-MM-DD] '
  + '[--insurance medicare|medicaid|commercial|unknown]';

class UsageError extends Error {}

// --- small pure helpers ------------------------------------------------------------------------------------------------

function camel(name) {
  return name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function collapse(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim();
}

function isoNow() {
  return new Date().toISOString();
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function pathnameOf(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return '';
  }
}

function safeName(name) {
  return String(name).replace(/[^A-Za-z0-9._-]+/g, '_').slice(0, 80) || 'document';
}

function isLoopback(host) {
  return host === 'localhost' || host === '[::1]' || host === '::1' || /^127\.\d+\.\d+\.\d+$/.test(host);
}

function validDate(value) {
  if (!ISO_DATE.test(value)) return false;
  const moment = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(moment.getTime()) && moment.toISOString().slice(0, 10) === value;
}

function check(id, ok, reason, data) {
  return { id, status: ok ? 'pass' : 'fail', reason, ...(data === undefined ? {} : { data }) };
}

function skip(id, reason) {
  return { id, status: 'skip', reason };
}

function warn(id, reason, data) {
  return { id, status: 'warn', reason, ...(data === undefined ? {} : { data }) };
}

function parseArgs(argv) {
  const flags = new Set(['allow-live-provider']);
  const values = new Set(['base-url', 'credentials', 'operator-credentials', 'docs', 'out', 'deadline-seconds',
    'service-date', 'insurance']);
  const opts = { deadlineSeconds: DEFAULT_DEADLINE_SECONDS, allowLiveProvider: false, serviceDate: null,
    insurance: 'commercial' };
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith('--')) throw new UsageError(`unexpected argument ${argv[i]}`);
    const [name, inline] = argv[i].slice(2).split(/=(.*)/s);
    if (flags.has(name)) {
      if (inline !== undefined) throw new UsageError(`--${name} takes no value`);
      opts[camel(name)] = true;
    } else if (values.has(name)) {
      const value = inline ?? argv[++i];
      if (value === undefined || value === '') throw new UsageError(`--${name} needs a value`);
      opts[camel(name)] = value;
    } else {
      throw new UsageError(`unknown option --${name}`);
    }
  }
  for (const name of ['baseUrl', 'credentials', 'operatorCredentials', 'docs', 'out']) {
    if (!opts[name]) throw new UsageError(`missing --${name.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`)}`);
  }
  let url;
  try {
    url = new URL(opts.baseUrl);
  } catch {
    throw new UsageError(`--base-url is not a URL: ${opts.baseUrl}`);
  }
  if (!['https:', 'http:'].includes(url.protocol)) throw new UsageError('--base-url must be http(s)');
  if (url.username || url.password) throw new UsageError('--base-url must not carry a user name or password');
  // a password is typed into the page: never over plain http off the loopback (ops/verify_login.py's rule)
  if (url.protocol === 'http:' && !isLoopback(url.hostname)) {
    throw new UsageError('--base-url may be plain http only on the loopback: the password would cross a network in clear');
  }
  opts.baseUrl = url.origin;
  opts.deadlineSeconds = Number(opts.deadlineSeconds);
  if (!Number.isInteger(opts.deadlineSeconds) || opts.deadlineSeconds < MIN_DEADLINE_SECONDS) {
    throw new UsageError(`--deadline-seconds must be an integer of at least ${MIN_DEADLINE_SECONDS}`);
  }
  if (opts.serviceDate !== null && !validDate(opts.serviceDate)) {
    throw new UsageError('--service-date must be a calendar date written YYYY-MM-DD');
  }
  if (!INSURANCE.includes(opts.insurance)) throw new UsageError(`--insurance must be one of ${INSURANCE.join(', ')}`);
  return opts;
}

// The service date a synthetic document states on its own "Date of service:" or "Date of procedure:" line, or null.
function serviceDateOf(text) {
  const match = DATE_LINE.exec(String(text ?? ''));
  return match && validDate(match[1]) ? match[1] : null;
}

// The documents --docs names, read whole: one file, or every .txt/.pdf/.docx regular file of a directory in name order.
function documentsOf(docsPath, opts) {
  let info;
  try {
    info = fs.statSync(docsPath);
  } catch (error) {
    throw new UsageError(`cannot read --docs ${docsPath}: ${String(error.message).split(',')[0]}`);
  }
  const files = info.isDirectory()
    ? fs.readdirSync(docsPath).sort().map(name => path.join(docsPath, name))
      .filter(file => fs.statSync(file).isFile() && DOCUMENT_TYPES[path.extname(file).toLowerCase()])
    : [docsPath];
  if (!files.length) throw new UsageError(`--docs ${docsPath} holds no .txt, .pdf or .docx document`);
  return files.map(file => {
    const ext = path.extname(file).toLowerCase();
    if (!DOCUMENT_TYPES[ext]) throw new UsageError(`${file} is not a .txt, .pdf or .docx document`);
    const data = fs.readFileSync(file);
    const text = ext === '.txt' ? data.toString('utf8') : '';
    const serviceDate = opts.serviceDate || serviceDateOf(text);
    if (!serviceDate) {
      throw new UsageError(`${file} states no "Date of service:" line the walk can read: give --service-date`);
    }
    return { file, name: path.basename(file), title: path.basename(file, ext), ext, mediaType: DOCUMENT_TYPES[ext], data,
      sha256: sha256(data), size: data.length, text, serviceDate, insurance: opts.insurance };
  });
}

// --- credentials ------------------------------------------------------------------------------------------------------

// ops/verify_login.py _read_private: the content and mode of a private regular file, checked on the descriptor that is
// read; a file a group or other user may read or write is refused before a byte of it is read. Its content is never quoted.
function readPrivate(file, what) {
  let fd;
  try {
    fd = fs.openSync(file, 'r');
  } catch (error) {
    throw new UsageError(`cannot open the ${what} ${file}: ${String(error.message).split(',')[0]}`);
  }
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile()) throw new UsageError(`the ${what} ${file} is not a regular file`);
    const mode = info.mode & 0o7777;
    if (mode & 0o077) {
      throw new UsageError(`the ${what} ${file} has mode ${mode.toString(8).padStart(4, '0')}: a group or other user may read `
        + 'or write it; make it private (chmod 600) and keep it so');
    }
    const chunks = [];
    let total = 0;
    for (;;) {
      const chunk = Buffer.alloc(65536);
      const read = fs.readSync(fd, chunk, 0, chunk.length, null);
      if (!read) break;
      total += read;
      if (total > MAX_CREDENTIALS_BYTES) throw new UsageError(`the ${what} ${file} is over ${MAX_CREDENTIALS_BYTES} bytes`);
      chunks.push(chunk.subarray(0, read));
    }
    return { content: Buffer.concat(chunks), mode };
  } finally {
    fs.closeSync(fd);
  }
}

// A private JSON file with a flat, non-empty "username" and "password".
function loadCredentials(file, what) {
  const { content, mode } = readPrivate(file, what);
  let data;
  try {
    data = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(content));
  } catch {
    throw new UsageError(`the ${what} ${file} is not a JSON object`);
  }
  if (!isObject(data) || typeof data.username !== 'string' || !data.username.trim() || typeof data.password !== 'string'
      || !data.password) {
    throw new UsageError(`the ${what} ${file} must hold a non-empty top-level "username" and "password"`);
  }
  return { username: data.username, password: data.password, mode: mode.toString(8).padStart(4, '0') };
}

// Whether DEBUG could turn on a Playwright log that carries the password (PASSWORD_LOGS); a name is read both as a glob
// and as a regular expression, an unreadable one counts, and a '-' exclusion is never relied on.
function debugMayLog(value) {
  const escape = text => text.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
  return String(value ?? '').split(/[\s,]+/).filter(name => name && !name.startsWith('-')).some(name => {
    const glob = new RegExp(`^${escape(name).replace(/\*/g, '.*')}$`);
    let regex;
    try {
      regex = new RegExp(`^${name.replace(/\*/g, '.*?')}$`);
    } catch {
      return true;
    }
    return PASSWORD_LOGS.some(log => glob.test(log) || regex.test(log));
  });
}

// Every form in which a password could reach an output - as typed, percent- and form-encoded, HTML-escaped, inside a
// JSON string - longest first (ops/verify_login.py Secret).
function secretForms(password) {
  const text = String(password);
  const html = quote => {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return quote ? escaped.replace(/"/g, '&quot;').replace(/'/g, '&#x27;') : escaped;
  };
  const json = JSON.stringify(text).slice(1, -1);
  const forms = new Set([text, html(true), html(false), json,
    json.replace(/[\u007f-￿]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`)]);
  try {
    const percent = encodeURIComponent(text);
    const strict = percent.replace(/[!'()*]/g, c => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
    for (const form of [percent, strict, strict.replace(/%20/g, '+')]) forms.add(form);
  } catch {
    // a lone surrogate has no percent-encoded form, and a UTF-8 credentials file cannot hold one
  }
  return [...forms].filter(Boolean).sort((a, b) => b.length - a.length);
}

// ``value`` (text, or a JSON value: keys and strings) with every form of a password replaced.
function scrubSecret(value, forms) {
  if (typeof value === 'string') return forms.reduce((text, form) => text.split(form).join(WITHHELD), value);
  if (Array.isArray(value)) return value.map(item => scrubSecret(item, forms));
  if (isObject(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [scrubSecret(key, forms), scrubSecret(item, forms)]));
  }
  return value;
}

// --- the negative scan (ops/verification/customer-denylist.json) ------------------------------------------------------

// The denylist compiled as its readers compile it: each pattern matched ASCII-only, case-insensitively unless it says
// "case_sensitive": true (JavaScript 'gi' or 'g', without 'u'), after every 'allowed' string is removed.
function compileDenylist(list) {
  if (!isObject(list) || !Array.isArray(list.patterns)) throw new UsageError('the denylist has no patterns');
  return {
    schema: list.schema,
    patterns: list.patterns.map(p => ({ id: p.id, severity: p.severity, surfaces: new Set(p.surfaces),
      regex: new RegExp(p.source, p.case_sensitive === true ? 'g' : 'gi') })),
    allowed: [...new Set(list.allowed || [])].filter(Boolean).sort((a, b) => b.length - a.length),
    forbiddenKeys: new Set(list.forbidden_keys || []),
  };
}

let DENYLIST_CACHE = null;
function denylist() {
  if (!DENYLIST_CACHE) DENYLIST_CACHE = compileDenylist(JSON.parse(fs.readFileSync(DENYLIST_FILE, 'utf8')));
  return DENYLIST_CACHE;
}

// documentText: the document's own text (a .txt upload); quotes: the document passages the encounter quotes (its codes'
// quotes, which the coding service cites from the document, never writes); allowed: more strings removed before the
// scan (the site's own host). A string that is a part of either is the document's, not the product's wording.
function scanContext({ documentText = '', quotes = [], allowed = [] } = {}, list = denylist()) {
  return { documentText: collapse(documentText), quotes: new Set(quotes.map(collapse).filter(Boolean)),
    allowed: [...new Set([...list.allowed, ...allowed].filter(Boolean))].sort((a, b) => b.length - a.length), list };
}

function addQuotes(ctx, enc) {
  for (const code of Array.isArray(enc?.codes) ? enc.codes : []) {
    for (const quote of Array.isArray(code?.quotes) ? code.quotes : []) {
      if (typeof quote?.text === 'string' && collapse(quote.text)) ctx.quotes.add(collapse(quote.text));
    }
  }
}

function excerpt(text, at, length) {
  const from = Math.max(0, at - 24);
  return `${from > 0 ? '…' : ''}${text.slice(from, at + length + 24).replace(/\s+/g, ' ')}${at + length + 24 < text.length ? '…' : ''}`;
}

// What of ``text`` is the product's own wording: '' when the whole of it is the document's (a part of its text or of a
// quote), else the text with every quote set aside.
function ownWording(text, ctx) {
  const folded = collapse(text);
  if (!folded) return '';
  if (ctx.documentText && ctx.documentText.includes(folded)) return '';
  const quotes = [...ctx.quotes].sort((a, b) => b.length - a.length);
  if (quotes.some(quote => quote.includes(folded))) return '';
  let rest = folded;
  for (const quote of quotes) rest = rest.split(quote).join(' ');
  return rest;
}

// The hits of one string on one surface: {id, severity, surface, where, match}.
function scanText(text, ctx, surface, where = '', hits = []) {
  let cleaned = ownWording(typeof text === 'string' ? text : String(text ?? ''), ctx);
  if (!cleaned.trim()) return hits;
  for (const allowed of ctx.allowed) cleaned = cleaned.split(allowed).join(' ');
  for (const pattern of ctx.list.patterns) {
    if (!pattern.surfaces.has(surface)) continue;
    for (const match of cleaned.matchAll(pattern.regex)) {
      hits.push({ id: pattern.id, severity: pattern.severity, surface, where, match: excerpt(cleaned, match.index, match[0].length) });
    }
  }
  return hits;
}

// A JSON value: every string value and every key (a forbidden key is a hit by itself).
function scanJson(value, ctx, where = '$', hits = []) {
  if (typeof value === 'string') return scanText(value, ctx, 'json', where, hits);
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanJson(item, ctx, `${where}[${index}]`, hits));
  } else if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      if (ctx.list.forbiddenKeys.has(key)) hits.push({ id: 'forbidden_key', severity: 'hard', surface: 'json', where: `${where}.${key}`, match: key });
      scanText(key, ctx, 'json', `${where}.${key} (key)`, hits);
      scanJson(item, ctx, `${where}.${key}`, hits);
    }
  }
  return hits;
}

// A downloaded file, line by line: a line that is the document's own text, or a quote, after its bullet and quotation
// marks is set aside (an export quotes the document).
function scanFile(text, ctx, name, hits = []) {
  String(text).split(/\r?\n/).forEach((line, index) => {
    const bare = line.replace(/^[\s>*•·-]+/, '').replace(/^["“']+|["”']+$/g, '');
    if (!ownWording(bare, ctx)) return;
    scanText(line, ctx, 'file', `${name} line ${index + 1}`, hits);
  });
  return hits;
}

function scanHeaders(headers, ctx, where, hits = []) {
  for (const [name, value] of Object.entries(headers || {})) {
    if (UNSCANNED_HEADERS.has(name.toLowerCase())) continue;
    scanText(String(value), ctx, 'header', `${where} header ${name}`, hits);
  }
  return hits;
}

function describeHits(hits) {
  const shown = hits.slice(0, 6).map(hit => `${hit.id} at ${hit.where}: ${JSON.stringify(hit.match)}`);
  return `${shown.join('; ')}${hits.length > shown.length ? `; and ${hits.length - shown.length} more` : ''}`;
}

// One surface's hits as checks: a hard hit fails it; a soft hit (wording a clinician may use) is a warning. A hit the
// polls met again (the same pattern on the same words) is counted once, at the first place it was met.
function checkScan(id, hits, what) {
  const seen = new Set();
  const distinct = hits.filter(hit => {
    const key = `${hit.id}\u0000${hit.match}`;
    return !seen.has(key) && seen.add(key);
  });
  const hard = distinct.filter(hit => hit.severity === 'hard');
  const soft = distinct.filter(hit => hit.severity !== 'hard');
  const out = [check(id, hard.length === 0, hard.length ? `${hard.length} hit(s) in ${what}: ${describeHits(hard)}`
    : `${what}: no vendor or model name, usage, id, hash or operator wording`, hard.length ? { hits: hard.slice(0, 40) } : undefined)];
  if (soft.length) out.push(warn(`${id}.wording`, `${soft.length} soft hit(s) in ${what}: ${describeHits(soft)}`, { hits: soft.slice(0, 40) }));
  return out;
}

// --- the JSON contract (section 6) and the page against it (section 7) ------------------------------------------------

// The actions a code offers by the contract: a current decision -> revoke; ready and needs_review -> approve, reject;
// needs_answer and not_supported -> none.
function expectedActions(code) {
  if (isObject(code?.decision)) return ['revoke'];
  return ['ready', 'needs_review'].includes(code?.status) ? ['approve', 'reject'] : [];
}

function sorted(list) {
  return [...(Array.isArray(list) ? list : [])].map(String).sort();
}

function sameList(a, b) {
  return JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
}

function jsonChecks(enc, doc) {
  const out = [];
  const missing = ENCOUNTER_KEYS.filter(key => !Object.prototype.hasOwnProperty.call(enc || {}, key));
  out.push(check('json.keys', missing.length === 0, missing.length ? `the encounter lacks ${missing.join(', ')}`
    : 'every key of the encounter contract is served'));
  const codes = Array.isArray(enc?.codes) ? enc.codes : [];
  const shapes = codes.flatMap(code => CODE_KEYS.filter(key => !Object.prototype.hasOwnProperty.call(code || {}, key))
    .map(key => `${code?.code}: no ${key}`));
  out.push(check('json.codes.keys', shapes.length === 0, shapes.length ? shapes.slice(0, 8).join('; ') : `${codes.length} code(s), each in its shape`));
  const statuses = codes.filter(code => !CODE_STATUSES.has(code?.status)).map(code => `${code?.code}: ${code?.status}`);
  out.push(check('json.codes.status', statuses.length === 0, statuses.length ? `unknown statuses: ${statuses.join(', ')}`
    : 'every status is ready, needs_answer, needs_review or not_supported'));
  const actions = codes.filter(code => !sameList(code?.allowed_actions, expectedActions(code)))
    .map(code => `${code?.code} (${code?.status}${isObject(code?.decision) ? `, ${code.decision.action}` : ''}) offers [${sorted(code?.allowed_actions)}], not [${expectedActions(code)}]`);
  out.push(check('json.codes.actions', actions.length === 0, actions.length ? actions.join('; ')
    : 'every code offers exactly the actions its status and decision allow'));
  const context = enc?.context || {};
  out.push(check('json.context', context.service_date === doc.serviceDate && context.insurance === doc.insurance,
    `the encounter's context is ${JSON.stringify(context)}; uploaded ${doc.serviceDate}, ${doc.insurance}`));
  out.push(check('json.progress.phase', PHASES.has(enc?.progress?.phase), `progress.phase is ${JSON.stringify(enc?.progress?.phase)}`));
  return out;
}

// Runs in the page: what the encounter view shows, by the DOM contract's selectors.
function readEncounterDom() {
  const text = el => (el ? el.textContent : '').replace(/\s+/g, ' ').trim();
  const panel = document.querySelector('section.progress-panel');
  const questions = document.querySelector('section#questionsPanel');
  const viewer = document.querySelector('#documentViewer');
  const frame = viewer ? (viewer.tagName === 'IFRAME' ? viewer : viewer.querySelector('iframe')) : null;
  const original = Array.from(document.querySelectorAll('a')).find(a => /download original/i.test(a.textContent || ''));
  const notes = document.querySelector('section#notesPanel');
  return {
    progress: panel ? { phase: panel.getAttribute('data-phase'), steps: Array.from(panel.querySelectorAll('.progress-step'))
      .map(step => ({ step: step.getAttribute('data-step'), state: step.getAttribute('data-state') })) } : null,
    questions: questions ? { heading: text(questions.querySelector('h1, h2, h3, h4')), send: Boolean(document.querySelector('#sendAnswers')),
      rows: Array.from(questions.querySelectorAll('.question-row')).map(row => ({ id: row.getAttribute('data-question'),
        text: text(row), textarea: Boolean(row.querySelector('textarea')) })) } : null,
    codes: Array.from(document.querySelectorAll('ol#codesList > li.code-row')).map(li => {
      const badge = li.querySelector('.status');
      return { code: li.getAttribute('data-code'), status: li.getAttribute('data-status'),
        number: li.querySelector('.code-number') ? text(li.querySelector('.code-number')) : null,
        units: li.querySelector('.code-units') ? text(li.querySelector('.code-units')) : null,
        modifiers: li.querySelector('.code-modifiers') ? text(li.querySelector('.code-modifiers')) : null,
        badge: badge ? { status: badge.getAttribute('data-status'), text: text(badge) } : null,
        reason: li.querySelector('.code-reason') ? text(li.querySelector('.code-reason')) : null,
        check: li.querySelector('.code-check') ? text(li.querySelector('.code-check')) : null,
        quotes: Boolean(li.querySelector('.code-quotes')),
        buttons: Array.from(li.querySelectorAll('button[data-decision]')).map(b => ({ decision: b.getAttribute('data-decision'),
          code: b.getAttribute('data-code') })) };
    }),
    quotesPanel: Boolean(document.querySelector('#quotesPanel')),
    quotes: Array.from(document.querySelectorAll('#quotesPanel .quote')).map(q => ({ code: q.getAttribute('data-code'),
      page: q.getAttribute('data-page') })),
    notes: notes ? text(notes) : null,
    viewer: viewer ? { src: frame ? frame.getAttribute('src') : null, original: original ? original.getAttribute('href') : null } : null,
    exportButton: Boolean(document.querySelector('[data-action="export"]')),
  };
}

function sameTarget(href, url, base) {
  if (typeof href !== 'string' || typeof url !== 'string' || !href || !url) return false;
  try {
    const a = new URL(href, base);
    const b = new URL(url, base);
    return a.origin === b.origin && a.pathname === b.pathname && a.search === b.search;
  } catch {
    return false;
  }
}

function quoteKey(code, page) {
  return `${code}|${page === null || page === undefined ? '' : String(page)}`;
}

// The page against the encounter it was served (the DOM contract of section 7), one check per part of the view.
function domChecks(enc, dom, base) {
  const out = [];
  const codes = Array.isArray(enc?.codes) ? enc.codes : [];
  const phase = enc?.progress?.phase;
  out.push(check('dom.progress.phase', dom?.progress?.phase === phase,
    `section.progress-panel[data-phase] is ${JSON.stringify(dom?.progress?.phase ?? null)}; the encounter's phase is ${phase}`));
  const steps = dom?.progress?.steps || [];
  const stepProblems = STEPS.filter(step => steps.filter(item => item.step === step && item.state).length !== 1);
  out.push(check('dom.progress.steps', !!dom?.progress && stepProblems.length === 0, stepProblems.length
    ? `no single .progress-step with a data-state for ${stepProblems.join(', ')}` : 'reading, checking and finished each shown with its state'));
  const rows = dom?.codes || [];
  const order = JSON.stringify(rows.map(row => [row.code, row.status])) === JSON.stringify(codes.map(code => [code.code, code.status]));
  out.push(check('dom.codes.rows', order, order ? `${rows.length} code row(s), in order, each with its status`
    : `rows ${JSON.stringify(rows.map(row => [row.code, row.status]))}; served ${JSON.stringify(codes.map(code => [code.code, code.status]))}`));
  const cells = [];
  const badges = [];
  const buttons = [];
  codes.forEach((code, index) => {
    const row = rows[index];
    if (!row || row.code !== code.code) return;
    if (!(row.number || '').includes(String(code.code))) cells.push(`${code.code}: .code-number ${JSON.stringify(row.number)}`);
    if (!(row.units || '').includes(String(code.units))) cells.push(`${code.code}: .code-units ${JSON.stringify(row.units)}`);
    const modifiers = Array.isArray(code.modifiers) ? code.modifiers : [];
    if (row.modifiers === null || modifiers.some(modifier => !row.modifiers.includes(String(modifier)))) {
      cells.push(`${code.code}: .code-modifiers ${JSON.stringify(row.modifiers)} for ${JSON.stringify(modifiers)}`);
    }
    if (row.reason === null || (collapse(code.reason) && !row.reason.includes(collapse(code.reason)))) cells.push(`${code.code}: .code-reason`);
    const second = collapse(code.second_check?.reason);
    if (row.check === null || (second && !row.check.includes(second))) cells.push(`${code.code}: .code-check`);
    if (!row.quotes) cells.push(`${code.code}: no .code-quotes`);
    const decided = isObject(code.decision) ? DECISION_WORDS[code.decision.action] : null;
    if (!row.badge) {
      badges.push(`${code.code}: no .status badge`);
    } else if (decided) {
      if (!row.badge.text.includes(decided)) badges.push(`${code.code}: the badge reads ${JSON.stringify(row.badge.text)}, not ${decided}`);
    } else if (row.badge.status !== code.status || !row.badge.text.includes(collapse(code.status_label))) {
      badges.push(`${code.code}: the badge is ${JSON.stringify(row.badge)}; served ${code.status} "${code.status_label}"`);
    }
    const shown = row.buttons.map(button => button.decision);
    if (!sameList(shown, code.allowed_actions) || row.buttons.some(button => button.code !== code.code)) {
      buttons.push(`${code.code}: buttons [${sorted(shown)}], allowed [${sorted(code.allowed_actions)}]`);
    }
  });
  out.push(check('dom.codes.cells', cells.length === 0, cells.length ? cells.slice(0, 10).join('; ')
    : 'each row shows its number, units, modifiers, reason, second check and quotes'));
  out.push(check('dom.codes.badges', badges.length === 0, badges.length ? badges.slice(0, 10).join('; ')
    : 'each badge states the status served, or the decision made'));
  out.push(check('dom.codes.actions', buttons.length === 0, buttons.length ? buttons.slice(0, 10).join('; ')
    : 'each row offers exactly the actions allowed, and no other'));
  const served = codes.flatMap(code => (Array.isArray(code.quotes) ? code.quotes : []).map(quote => quoteKey(code.code, quote?.page))).sort();
  const listed = (dom?.quotes || []).map(quote => quoteKey(quote.code, quote.page === '' ? null : quote.page)).sort();
  out.push(check('dom.quotes', (served.length === 0 || dom?.quotesPanel) && JSON.stringify(served) === JSON.stringify(listed),
    `#quotesPanel lists ${listed.length} quote(s); the codes carry ${served.length}`));
  const questions = Array.isArray(enc?.questions) ? enc.questions : [];
  const qrows = dom?.questions?.rows || [];
  let questionsOk;
  let questionsWhy;
  if (!questions.length) {
    questionsOk = qrows.length === 0;
    questionsWhy = questionsOk ? 'no question, and no question row' : `${qrows.length} question row(s) for no question`;
  } else {
    const problems = [];
    if (!dom?.questions) problems.push('no section#questionsPanel');
    else if (!collapse(dom.questions.heading).includes(QUESTIONS_HEADING)) problems.push(`its heading is ${JSON.stringify(dom.questions.heading)}`);
    if (JSON.stringify(qrows.map(row => row.id)) !== JSON.stringify(questions.map(item => String(item.id)))) {
      problems.push(`rows ${JSON.stringify(qrows.map(row => row.id))} for questions ${JSON.stringify(questions.map(item => item.id))}`);
    }
    questions.forEach((item, index) => {
      if (qrows[index] && !qrows[index].textarea) problems.push(`question ${item.id} has no textarea`);
      if (qrows[index] && collapse(item.text) && !qrows[index].text.includes(collapse(item.text))) problems.push(`question ${item.id}'s text is not shown`);
    });
    if (dom?.questions && !dom.questions.send) problems.push('no #sendAnswers');
    questionsOk = problems.length === 0;
    questionsWhy = questionsOk ? `${questions.length} question(s), each with its textarea, and #sendAnswers` : problems.join('; ');
  }
  out.push(check('dom.questions', questionsOk, questionsWhy));
  const notes = (Array.isArray(enc?.notes) ? enc.notes : []).map(note => collapse(typeof note === 'string' ? note : note?.text)).filter(Boolean);
  const unshown = notes.filter(note => !(dom?.notes || '').includes(note));
  out.push(check('dom.notes', unshown.length === 0, unshown.length ? `${unshown.length} documentation note(s) not shown in section#notesPanel`
    : `${notes.length} documentation note(s) shown`));
  const documentPart = enc?.document || {};
  out.push(check('dom.viewer', !!dom?.viewer && sameTarget(dom.viewer.src, documentPart.view_url, base)
    && sameTarget(dom.viewer.original, documentPart.original_url, base),
  `#documentViewer frame ${JSON.stringify(dom?.viewer?.src ?? null)} and "Download original" ${JSON.stringify(dom?.viewer?.original ?? null)}; served ${documentPart.view_url} and ${documentPart.original_url}`));
  if (enc?.readiness?.draft === true) out.push(check('dom.export', !!dom?.exportButton, 'the export button is offered while a draft can be made'));
  return out;
}

// What the evidence keeps of an encounter: no document text, only the shape the walk judged.
function summarize(enc) {
  return {
    state: enc?.state ?? null, phase: enc?.progress?.phase ?? null, round: enc?.round ?? null,
    codes: (enc?.codes || []).map(code => ({ code: code.code, units: code.units, modifiers: code.modifiers, status: code.status,
      quotes: (code.quotes || []).length, decision: code.decision ? code.decision.action : null, allowed_actions: code.allowed_actions })),
    questions: (enc?.questions || []).length, answers: (enc?.answers || []).length, notes: (enc?.notes || []).length,
    readiness: enc?.readiness ?? null, reports: (enc?.reports || []).map(r => ({ kind: r.kind, fmt: r.fmt, current: r.current })),
  };
}

function documentResult(record) {
  const failed = record.checks.filter(item => item.status === 'fail');
  const reasons = failed.map(item => `${item.id}: ${item.reason}`);
  if (record.error) reasons.unshift(`error: ${record.error}`);
  return { result: reasons.length ? 'fail' : 'pass', reasons };
}

// What is wrong with an evidence object's shape (schema cpt-studio-walk-evidence@1): [] when it is whole.
function evidenceProblems(evidence) {
  const problems = [];
  if (!isObject(evidence)) return ['the evidence is not an object'];
  if (evidence.schema !== EVIDENCE_SCHEMA) problems.push(`schema is ${JSON.stringify(evidence.schema)}`);
  for (const key of ['run_id', 'started_at', 'base_url']) if (typeof evidence[key] !== 'string' || !evidence[key]) problems.push(`no ${key}`);
  if (!Array.isArray(evidence.run_checks)) problems.push('run_checks is not a list');
  if (!Array.isArray(evidence.documents)) return [...problems, 'documents is not a list'];
  const statuses = new Set(['pass', 'fail', 'warn', 'skip']);
  evidence.documents.forEach((doc, index) => {
    if (!isObject(doc)) {
      problems.push(`documents[${index}] is not an object`);
      return;
    }
    if (typeof doc.file !== 'string') problems.push(`documents[${index}] names no file`);
    if (!['pass', 'fail'].includes(doc.result)) problems.push(`documents[${index}].result is ${JSON.stringify(doc.result)}`);
    if (!Array.isArray(doc.reasons) || doc.reasons.some(reason => typeof reason !== 'string')) problems.push(`documents[${index}].reasons is not a list of strings`);
    if (!Array.isArray(doc.checks) || doc.checks.some(item => !isObject(item) || typeof item.id !== 'string'
        || !statuses.has(item.status) || typeof item.reason !== 'string')) {
      problems.push(`documents[${index}].checks is not a list of {id, status, reason}`);
    } else if ((doc.result === 'pass') !== (doc.reasons.length === 0)) {
      problems.push(`documents[${index}] says ${doc.result} with ${doc.reasons.length} reason(s)`);
    }
  });
  const summary = evidence.summary;
  if (summary !== null && summary !== undefined) {
    const passed = evidence.documents.filter(doc => doc.result === 'pass').length;
    if (summary.documents !== evidence.documents.length || summary.passed !== passed
        || summary.failed !== evidence.documents.length - passed) {
      problems.push('the summary does not count the documents');
    }
  }
  return problems;
}

// forms (secretForms of every password the run read): the evidence is scrubbed of them, and where a form survives the
// scrub (it spans the JSON's own syntax) nothing that holds it is written (ops/verify_login.py write_evidence).
function writeEvidence(file, evidence, forms = []) {
  let text = `${JSON.stringify(forms.length ? scrubSecret(evidence, forms) : evidence, null, 2)}\n`;
  if (forms.some(form => text.includes(form))) {
    text = `${JSON.stringify({ schema: evidence.schema, run_id: evidence.run_id,
      run_error: 'the evidence would have held a password; it was not written' }, null, 2)}\n`;
  }
  fs.writeFileSync(file, text, { mode: 0o600 });
}

function stopRequested(outDir) {
  return fs.existsSync(path.join(outDir, 'STOP'));
}

// --- browser steps -----------------------------------------------------------------------------------------------------

// Runs in the page: every text node and the wording attributes of every element (scripts, styles and templates aside;
// the CSRF field's token is no wording), for the negative scan.
function collectDomStrings() {
  const out = [];
  const keep = /^(?:aria-[\w-]+|data-[\w-]+|title|alt|placeholder|value|label|href|src|action|download|content)$/i;
  const ignore = el => Boolean(el && el.closest && el.closest('script, style, template, noscript'));
  const csrf = el => el.getAttribute && el.getAttribute('name') === 'csrfmiddlewaretoken';
  const describe = el => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}`;
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let node = walker.currentNode; node; node = walker.nextNode()) {
    if (node.nodeType === Node.TEXT_NODE) {
      const parent = node.parentElement;
      if (node.nodeValue && node.nodeValue.trim() && parent && !ignore(parent)) out.push([`text ${describe(parent)}`, node.nodeValue]);
    } else if (node.nodeType === Node.ELEMENT_NODE && !ignore(node) && !csrf(node)) {
      const secret = node.tagName === 'INPUT' && String(node.type).toLowerCase() === 'password';  // never read a password
      for (const attribute of Array.from(node.attributes)) {
        if (keep.test(attribute.name) && !(secret && attribute.name.toLowerCase() === 'value')) {
          out.push([`attr ${describe(node)}@${attribute.name}`, attribute.value]);
        }
      }
      if (/^(?:INPUT|TEXTAREA|SELECT)$/.test(node.tagName) && node.type !== 'hidden' && node.type !== 'password' && node.value) {
        out.push([`value ${describe(node)}`, String(node.value)]);
      }
    }
    if (out.length >= 20000) break;
  }
  out.push(['title', document.title]);
  return out;
}

function measureViewport() {
  const doc = document.documentElement;
  window.scrollTo(0, 0);
  return { width: window.innerWidth, client_width: doc.clientWidth,
    scroll_width: Math.max(doc.scrollWidth, document.body ? document.body.scrollWidth : 0) };
}

// Every open dialog closed (Escape closes a modal dialog), at most three, so the next step meets the page itself.
async function closeDialogs(page) {
  for (let i = 0; i < 3; i += 1) {
    const open = await page.locator('dialog[open]').count().catch(() => 0);
    if (!open) return;
    await page.keyboard.press('Escape').catch(() => {});
  }
}

async function signIn(page, base, creds) {
  await page.goto(`${base}/login/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.fill('input[name="username"]', creds.username);
  await page.fill('input[name="password"]', creds.password);
  await page.click('form.login-form button[type="submit"]');
  const outcome = await Promise.race([
    page.waitForURL(url => !new URL(url).pathname.startsWith('/login'), { timeout: UI_TIMEOUT_MS }).then(() => 'in'),
    page.locator('.form-error').first().waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS }).then(() => 'refused'),
  ]).catch(() => 'timeout');
  if (outcome !== 'in') throw new Error('sign-in failed: still on the sign-in page');
  return pathnameOf(page.url());
}

// The customer API, as the page calls it (the client header names the current page build); each body is scanned.
async function getJson(page, ctx, where) {
  const response = await page.request.get(`${ctx.base}${where}`, { headers: { Accept: 'application/json', ...CLIENT_HEADERS }, timeout: UI_TIMEOUT_MS, maxRedirects: 0 });
  const body = await response.text();
  let json = null;
  try {
    json = JSON.parse(body);
  } catch {
    json = null;
  }
  remember(ctx, `GET ${where}`, response.headers(), json, body);
  return { status: response.status(), json };
}

// One customer API answer, scanned: its quotes are the document's (set aside), then its body and headers.
function remember(ctx, where, headers, json, body) {
  if (!ctx.scan) return;
  if (json !== null) {
    addQuotes(ctx.scan, json);
    scanJson(json, ctx.scan, where, ctx.hits.json);
  } else if (body) {
    scanText(body.slice(0, 200000), ctx.scan, 'json', where, ctx.hits.json);
  }
  scanHeaders(headers, ctx.scan, where, ctx.hits.header);
}

async function captureResponse(response, ctx) {
  const where = pathnameOf(response.url());
  if (!ctx.scan || !where.startsWith('/api/') || !response.url().startsWith(ctx.base)) return;
  if (/\/download$|\/original$/.test(where)) return;  // a download is scanned as the saved file; an original is the document
  const type = String(response.headers()['content-type'] || '');
  if (!type.includes('json')) return;
  const body = await response.text().catch(() => '');
  let json = null;
  try {
    json = JSON.parse(body);
  } catch {
    json = null;
  }
  remember(ctx, `${response.request().method()} ${where} (page)`, response.headers(), json, body);
}

async function readDom(page, ctx) {
  for (const [where, value] of await page.evaluate(collectDomStrings)) scanText(value, ctx.scan, 'dom', where, ctx.hits.dom);
  return page.evaluate(readEncounterDom);
}

async function uploadDocument(page, ctx, doc) {
  await page.goto(`${ctx.base}/`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-action="upload"]:visible').first().click();
  await page.locator('#uploadDialog[open]').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  await page.setInputFiles('#uploadFile', doc.file);
  await page.fill('#serviceDate', doc.serviceDate);
  await page.selectOption('#insurance', doc.insurance);
  await page.check('#syntheticAttestation');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === '/api/encounters', { timeout: 120000 }),
    page.click('#startReview'),
  ]);
  let json = null;
  try {
    json = await response.json();
  } catch {
    json = null;
  }
  return { status: response.status(), id: typeof json?.id === 'string' ? json.id : null };
}

// Poll the encounter until its phase settles (done, failed or stopped) - for a round after ``after`` when it is given.
async function waitForRound(page, ctx, id, record, after = null) {
  const deadlineAt = Date.now() + ctx.deadlineSeconds * 1000;
  let errors = 0;
  for (;;) {
    let answer;
    try {
      answer = await getJson(page, ctx, `/api/encounters/${encodeURIComponent(id)}`);
    } catch (error) {
      answer = { status: 0, json: null, error: String(error.message || error) };
    }
    if (answer.status === 200 && isObject(answer.json)) {
      errors = 0;
      const enc = answer.json;
      const phase = enc.progress?.phase;
      if (record.phases[record.phases.length - 1] !== phase) record.phases.push(phase);
      const number = Number.isInteger(enc.round?.number) ? enc.round.number : null;
      if (SETTLED_PHASES.has(phase) && (after === null || (number !== null && number > after))) return enc;
    } else if (++errors >= MAX_POLL_ERRORS) {
      throw new Error(`GET /api/encounters/${id} answered ${answer.status || answer.error} ${MAX_POLL_ERRORS} times`);
    }
    if (Date.now() > deadlineAt) throw new Error(`the round did not finish within ${ctx.deadlineSeconds} s (phases ${record.phases.join(' > ')})`);
    await new Promise(resolve => setTimeout(resolve, POLL_MS));
  }
}

// The encounter view, once it shows the phase and the codes it was served (the page polls on its own).
async function viewFor(page, ctx, enc) {
  const hash = `#doc/${enc.id}`;
  if (!page.url().endsWith(hash)) await page.goto(`${ctx.base}/${hash}`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(([phase, count]) => {
    const panel = document.querySelector('section.progress-panel');
    return panel && panel.getAttribute('data-phase') === phase
      && document.querySelectorAll('ol#codesList > li.code-row').length === count;
  }, [enc.progress?.phase, (enc.codes || []).length], { timeout: 90000 }).catch(() => null);
  return readDom(page, ctx);
}

async function answerFirstQuestion(page, ctx, enc) {
  const question = enc.questions[0];
  const row = page.locator(`section#questionsPanel .question-row[data-question="${String(question.id).replace(/"/g, '\\"')}"]`);
  await row.locator('textarea').fill(WALK_ANSWER);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${enc.id}/answers`, { timeout: 60000 }),
    page.click('#sendAnswers'),
  ]);
  return { status: response.status(), question };
}

async function approve(page, ctx, enc, code) {
  const selector = value => String(value).replace(/"/g, '\\"');
  await page.locator(`ol#codesList > li.code-row[data-code="${selector(code.code)}"] button[data-decision="approve"][data-code="${selector(code.code)}"]`).click();
  await page.locator('#reviewDialog[open]').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  const ack = page.locator('#reviewAcknowledgement');
  const shown = collapse(await ack.evaluate(el => {
    const label = el.closest('label') || document.querySelector(`label[for="${el.id}"]`);
    return label ? label.textContent : el.getAttribute('aria-label') || '';
  }));
  const kind = await ack.evaluate(el => (el.tagName === 'INPUT' ? el.type : el.tagName.toLowerCase()));
  if (kind === 'checkbox') await ack.check();
  else await ack.fill(ctx.session.acknowledgement);
  await page.fill('#reviewNote', WALK_NOTE);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${enc.id}/decisions`, { timeout: 60000 }),
    page.click('#saveReview'),
  ]);
  return { status: response.status(), shown, kind };
}

async function exportTxt(page, ctx, enc, kind, outDir) {
  await page.locator('[data-action="export"]').first().click();
  await page.locator('#exportDialog[open]').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  const option = page.locator(`#exportOptions .export-option[data-export-kind="${kind}"][data-export-fmt="txt"]`);
  if (await option.isDisabled()) {
    await page.keyboard.press('Escape');
    return { kind, error: 'the export option is disabled' };
  }
  const [download, response] = await Promise.all([
    page.waitForEvent('download', { timeout: 120000 }),
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${enc.id}/reports`, { timeout: 120000 }),
    option.click(),
  ]);
  const report = await response.json().catch(() => null);
  const file = path.join(outDir, `${safeName(enc.id)}-${kind}.txt`);
  await download.saveAs(file);
  const bytes = fs.readFileSync(file);
  await page.keyboard.press('Escape');
  const result = { kind, fmt: 'txt', status: response.status(), filename: report?.filename ?? null,
    suggested: download.suggestedFilename(), path: path.relative(ctx.out, file), sha256: sha256(bytes), size: bytes.length,
    text: bytes.toString('utf8') };
  if (typeof report?.download_url === 'string') {
    const again = await page.request.get(new URL(report.download_url, ctx.base).href, { headers: { ...CLIENT_HEADERS }, timeout: UI_TIMEOUT_MS });
    const second = await again.body();
    result.refetch = { status: again.status(), sha256: sha256(second), size: second.length };
  }
  return result;
}

async function probeOps(page, ctx, operator, anonymous, enc) {
  const probes = [];
  const fake = crypto.randomUUID();  // POSTs name an encounter that does not exist: a broken gate changes nothing
  const token = ((await page.context().cookies(ctx.base)).find(cookie => cookie.name === CSRF_COOKIE) || {}).value || '';
  for (const where of OPS_GET_PATHS(enc.id)) {
    const customer = await page.request.get(`${ctx.base}${where}`, { maxRedirects: 0, timeout: UI_TIMEOUT_MS });
    const nobody = await anonymous.get(`${ctx.base}${where}`, { maxRedirects: 0, timeout: UI_TIMEOUT_MS });
    probes.push({ method: 'GET', path: where.replace(enc.id, '<id>'), customer: customer.status(), anonymous: nobody.status() });
  }
  for (const where of OPS_POST_PATHS(fake)) {
    const customer = await page.request.post(`${ctx.base}${where}`, { form: { note: 'walk probe of the operator gate' }, maxRedirects: 0,
      timeout: UI_TIMEOUT_MS, headers: { 'X-CSRFToken': token, Origin: ctx.base, Referer: `${ctx.base}/` } });
    probes.push({ method: 'POST', path: where.replace(fake, '<unknown id>'), customer: customer.status() });
  }
  const view = await operator.request.get(`${ctx.base}/ops/encounters/${enc.id}`, { maxRedirects: 0, timeout: UI_TIMEOUT_MS });
  const html = await view.text();
  return { probes, operator: { status: view.status(), names: html.includes(enc.id) || html.includes(enc.title || '\u0000') } };
}

function opsChecks(found) {
  const open = found.probes.filter(probe => probe.customer !== 404).map(probe => `${probe.method} ${probe.path} -> ${probe.customer}`);
  const anonymous = found.probes.filter(probe => probe.anonymous === 200).map(probe => `${probe.method} ${probe.path}`);
  return [
    check('ops.customer_404', open.length === 0, open.length ? `answered the customer: ${open.join('; ')}` : `${found.probes.length} /ops/ probe(s), each 404`),
    check('ops.anonymous_not_200', anonymous.length === 0, anonymous.length ? `answered 200 to nobody signed in: ${anonymous.join('; ')}` : 'no /ops/ path answers 200 to nobody signed in'),
    check('ops.operator_view', found.operator.status === 200 && found.operator.names,
      `GET /ops/encounters/<id> answered the operator ${found.operator.status}${found.operator.names ? ', naming the encounter' : ', not naming the encounter'}`),
  ];
}

function exportChecks(item, enc, label) {
  if (item.error) return [check(`export.${label}`, false, item.error)];
  const lines = item.text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const out = [
    check(`export.${label}`, item.status === 201 && item.size > 0 && /\.txt$/i.test(item.filename || item.suggested || ''),
      `POST answered ${item.status}; ${item.size} bytes saved as ${item.suggested}`),
    check(`export.${label}.same_bytes`, item.refetch?.status === 200 && item.refetch.sha256 === item.sha256,
      item.refetch ? `the second download answered ${item.refetch.status}, ${item.refetch.size} bytes, ${item.refetch.sha256 === item.sha256 ? 'the same bytes' : 'other bytes'}`
        : 'the report named no download_url to fetch again'),
    check(`export.${label}.synthetic`, lines.length > 1 && /SYNTHETIC/.test(lines[0]) && /SYNTHETIC/.test(lines[lines.length - 1]),
      'the SYNTHETIC banner opens and closes the file'),
  ];
  const codes = label === 'approved' ? (enc.codes || []).filter(code => code.decision?.action === 'approve') : enc.codes || [];
  const absent = codes.filter(code => !item.text.includes(String(code.code))).map(code => code.code);
  out.push(check(`export.${label}.codes`, absent.length === 0, absent.length ? `missing ${absent.join(', ')}` : `names its ${codes.length} code(s)`));
  return out;
}

// One document through the page. The upload and its first round must work for anything after them to mean something;
// every later step (the answer, the approval, each export, the viewport, the operator gate) is its own: one that throws
// is recorded as its own failed check and the walk goes on with the next step, so one run gathers all it can.
async function verifyDocument(page, ctx, sessions, doc) {
  const record = { file: doc.name, format: doc.ext.slice(1), sha256: doc.sha256, size: doc.size, service_date: doc.serviceDate,
    insurance: doc.insurance, encounter_id: null, result: null, reasons: [], checks: [], phases: [], rounds: [],
    answered: null, approved: null, downloads: [], viewport: null, encounter: null, error: null, started_at: isoNow(),
    finished_at: null };
  const add = (...items) => record.checks.push(...items);
  const step = async (name, run) => {
    try {
      await run();
    } catch (error) {
      add(check(`${name}.completed`, false, `the step stopped: ${String(error && error.message || error).split('\n')[0]}`));
    } finally {
      await closeDialogs(page);  // a dialog a failed step left open would make the rest of the page inert
    }
  };
  ctx.scan = scanContext({ documentText: doc.text, allowed: [new URL(ctx.base).host] });
  ctx.hits = { json: [], header: [], dom: [], file: [] };
  let enc = null;
  try {
    const uploaded = await uploadDocument(page, ctx, doc);
    record.encounter_id = uploaded.id;
    add(check('upload.created', uploaded.status === 201 && !!uploaded.id, `POST /api/encounters answered ${uploaded.status}`));
    if (!uploaded.id) throw new Error('no encounter was created');
    enc = await waitForRound(page, ctx, uploaded.id, record);
    record.rounds.push(enc.round || null);
    add(check('progress.done', enc.progress?.phase === 'done', `the first round ended ${enc.progress?.phase}`
      + (enc.progress?.error?.text ? `: ${enc.progress.error.text}` : '')));
    add(...jsonChecks(enc, doc));
    add(...domChecks(enc, await viewFor(page, ctx, enc), ctx.base));
  } catch (error) {
    record.error = String(error && error.message || error).split('\n')[0];
  }
  if (enc) {
    await step('quotes', async () => {
      // clicking a quote moves the viewer to its page (#page=N): one quote with a page, through the page itself. Only a
      // PDF view has pages to move to; a text view finds the passage instead, so the check applies to PDF views only.
      if ((enc.document || {}).view_media_type !== 'application/pdf') {
        add(skip('quotes.jump', 'the document is not viewed as a PDF'));
        return;
      }
      const paged = (enc.codes || []).flatMap(code => (code.quotes || []).map(quote => ({ code: code.code, page: quote?.page })))
        .find(quote => Number.isInteger(quote.page));
      if (!paged) {
        add(skip('quotes.jump', 'no quote names a page'));
        return;
      }
      await page.locator(`#quotesPanel .quote[data-code="${String(paged.code).replace(/"/g, '\\"')}"][data-page="${paged.page}"]`).first().click();
      const src = await page.waitForFunction(wanted => {
        const viewer = document.querySelector('#documentViewer');
        const frame = viewer && (viewer.tagName === 'IFRAME' ? viewer : viewer.querySelector('iframe'));
        const value = frame ? frame.getAttribute('src') || '' : '';
        return value.endsWith(`#page=${wanted}`) ? value : false;
      }, paged.page, { timeout: 5000 }).then(handle => handle.jsonValue()).catch(() => null);
      add(check('quotes.jump', !!src, `a quote of ${paged.code} on page ${paged.page} ${src ? 'moved' : 'did not move'} the viewer to #page=${paged.page}`));
    });
    await step('answers', async () => {
      if (enc.progress?.phase !== 'done' || !(enc.questions || []).length) {
        add(skip('answers', enc.progress?.phase === 'done' ? 'no question was asked' : 'the round did not finish'));
        return;
      }
      const before = enc.round?.number ?? 0;
      const answered = await answerFirstQuestion(page, ctx, enc);
      record.answered = { question: answered.question.id, status: answered.status };
      add(check('answers.sent', answered.status === 201, `POST answers answered ${answered.status}`));
      enc = await waitForRound(page, ctx, enc.id, record, before);
      record.rounds.push(enc.round || null);
      add(check('answers.new_round', enc.round?.number > before && enc.round?.trigger === 'answers',
        `round ${enc.round?.number} (${enc.round?.trigger}) after round ${before}; it ended ${enc.progress?.phase}`));
      add(check('answers.recorded', (enc.answers || []).some(item => collapse(item.answer) === WALK_ANSWER
        && collapse(item.question) === collapse(answered.question.text)), 'the answer is listed with its question'));
      add(...jsonChecks(enc, doc).map(item => ({ ...item, id: `round2.${item.id}` })));
      add(...domChecks(enc, await viewFor(page, ctx, enc), ctx.base).map(item => ({ ...item, id: `round2.${item.id}` })));
    });
    await step('approve', async () => {
      const ready = enc.progress?.phase === 'done'
        ? (enc.codes || []).find(code => code.status === 'ready' && !code.decision && (code.allowed_actions || []).includes('approve'))
        : null;
      if (!ready) {
        add(skip('approve', 'no READY code to approve'));
        return;
      }
      const made = await approve(page, ctx, enc, ready);
      add(check('approve.acknowledgement', made.shown.includes(collapse(ctx.session.acknowledgement)),
        `#reviewAcknowledgement (${made.kind}) is labelled with the session's acknowledgement`));
      add(check('approve.saved', made.status === 201, `POST decisions answered ${made.status}`));
      const after = await getJson(page, ctx, `/api/encounters/${encodeURIComponent(enc.id)}`);
      enc = isObject(after.json) ? after.json : enc;
      const decided = (enc.codes || []).find(code => code.code === ready.code);
      record.approved = decided?.decision?.action === 'approve' ? ready.code : null;
      add(check('approve.recorded', decided?.decision?.action === 'approve' && sameList(decided.allowed_actions, ['revoke'])
        && enc.readiness?.approved === true, `${ready.code}: decision ${JSON.stringify(decided?.decision?.action ?? null)}, `
        + `actions [${sorted(decided?.allowed_actions)}], approved export ${enc.readiness?.approved}`));
      add(...domChecks(enc, await viewFor(page, ctx, enc), ctx.base).filter(item => item.id.startsWith('dom.codes'))
        .map(item => ({ ...item, id: `approved.${item.id}` })));
    });
    for (const kind of ['draft', 'approved']) {
      await step(`export.${kind}`, async () => {
        const possible = kind === 'draft' ? enc.readiness?.draft === true : !!record.approved && enc.readiness?.approved === true;
        if (!possible) {
          add(skip(`export.${kind}`, kind === 'draft' ? 'no draft can be made' : 'no code was approved'));
          return;
        }
        const made = await exportTxt(page, ctx, enc, kind, ctx.docDir);
        record.downloads.push({ ...made, text: undefined });
        add(...exportChecks(made, enc, kind));
        if (made.text) scanFile(made.text, ctx.scan, `${kind}.txt`, ctx.hits.file);
      });
    }
    await step('viewport', async () => {
      await page.setViewportSize(VIEWPORTS.mobile);
      try {
        await page.waitForTimeout(500);
        record.viewport = await page.evaluate(measureViewport);
        await readDom(page, ctx);
      } finally {
        await page.setViewportSize(VIEWPORTS.desktop);
      }
      add(check('viewport.390', record.viewport.scroll_width <= record.viewport.client_width + 1,
        `at 390x844 the page is ${record.viewport.scroll_width} px wide in a ${record.viewport.client_width} px viewport`));
    });
    await step('ops', async () => add(...opsChecks(await probeOps(page, ctx, sessions.operator, sessions.anonymous, enc))));
    record.encounter = summarize(enc);
  }
  add(...checkScan('scan.json', [...ctx.hits.json, ...ctx.hits.header], 'the customer API bodies and headers'),
    ...checkScan('scan.dom', ctx.hits.dom, 'the page'), ...checkScan('scan.files', ctx.hits.file, 'the downloads'));
  ctx.scan = null;
  Object.assign(record, documentResult(record), { finished_at: isoNow() });
  return record;
}

function sessionProblems(session, opts) {
  const problems = [];
  if (!isObject(session)) return ['GET /api/session served no object'];
  if (session.can_review !== true) problems.push('the account cannot review in this workspace');
  if (typeof session.acknowledgement !== 'string' || !session.acknowledgement.trim()) problems.push('the session serves no acknowledgement to approve with');
  if (!opts.allowLiveProvider) {
    problems.push('the customer session serves no provider mode, so each upload may make paid requests: re-run with --allow-live-provider to accept');
  }
  return problems;
}

async function main(argv) {
  let opts;
  let docs;
  let creds;
  let operator;
  try {
    opts = parseArgs(argv);
    if (debugMayLog(process.env.DEBUG)) {
      throw new UsageError(`refusing to run with DEBUG=${process.env.DEBUG}: a Playwright log would carry the password`);
    }
    docs = documentsOf(opts.docs, opts);
    creds = loadCredentials(opts.credentials, 'credentials file');
    operator = loadCredentials(opts.operatorCredentials, 'operator credentials file');
    if (operator.username === creds.username) throw new UsageError('the operator account must not be the customer account');
    if (fs.existsSync(path.join(opts.out, 'evidence.json'))) throw new UsageError(`${opts.out} already holds evidence.json; use a fresh --out directory`);
    denylist();
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`walk: ${error.message}\n${USAGE}\n`);
    return 2;
  }
  fs.mkdirSync(opts.out, { recursive: true });
  const evidenceFile = path.join(opts.out, 'evidence.json');
  const forms = [...new Set([...secretForms(creds.password), ...secretForms(operator.password)])].sort((a, b) => b.length - a.length);
  const print = text => process.stdout.write(scrubSecret(text, forms));
  const { chromium, request: playwrightRequest } = require(PLAYWRIGHT);
  const evidence = {
    schema: EVIDENCE_SCHEMA, run_id: `walk-${isoNow().replace(/[-:.]/g, '')}-${crypto.randomBytes(4).toString('hex')}`,
    started_at: isoNow(), finished_at: null, base_url: opts.baseUrl, synthetic_only: true,
    options: { deadline_seconds: opts.deadlineSeconds, allow_live_provider: opts.allowLiveProvider, service_date: opts.serviceDate,
      insurance: opts.insurance, docs: path.resolve(opts.docs) },
    environment: { node: process.version, playwright: require(path.join(PLAYWRIGHT, 'package.json')).version, browser: null,
      denylist: denylist().schema },
    credentials: { username: creds.username, file_mode: creds.mode },
    operator_credentials: { username: operator.username, file_mode: operator.mode },
    session: null, run_checks: [], documents: [], summary: null, run_error: null,
  };
  const browser = await chromium.launch({ headless: true });
  evidence.environment.browser = browser.version();
  const context = await browser.newContext({ acceptDownloads: true, viewport: VIEWPORTS.desktop });
  const page = await context.newPage();
  page.setDefaultTimeout(UI_TIMEOUT_MS);
  const ctx = { base: opts.baseUrl, out: opts.out, deadlineSeconds: opts.deadlineSeconds, scan: null, hits: null, session: null };
  page.on('response', response => { captureResponse(response, ctx).catch(() => {}); });
  const operatorContext = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const anonymous = await playwrightRequest.newContext();
  try {
    await signIn(page, opts.baseUrl, creds);
    const session = await page.request.get(`${opts.baseUrl}/api/session`, { headers: { Accept: 'application/json', ...CLIENT_HEADERS } });
    ctx.session = session.ok() ? await session.json() : null;
    evidence.session = ctx.session ? { can_review: ctx.session.can_review ?? null, role: ctx.session.role ?? null,
      acknowledgement: ctx.session.acknowledgement ?? null } : { status: session.status() };
    const problems = sessionProblems(ctx.session, opts);
    if (problems.length) throw new Error(`refusing to upload: ${problems.join('; ')}`);
    const runScan = scanContext({ allowed: [new URL(opts.baseUrl).host] });
    evidence.run_checks.push(...checkScan('scan.session', scanJson(ctx.session, runScan, 'GET /api/session'), 'the customer session'));
    const operatorPage = await operatorContext.newPage();
    await signIn(operatorPage, opts.baseUrl, operator);
    const control = await operatorContext.request.get(`${opts.baseUrl}/ops/`, { maxRedirects: 0, timeout: UI_TIMEOUT_MS });
    evidence.run_checks.push(check('ops.operator_control', control.status() === 200, `GET /ops/ answered the operator ${control.status()}`));
    if (control.status() !== 200) throw new Error('refusing to upload: the operator session cannot read /ops/, so no 404 the customer is answered there could be believed');
    for (const doc of docs) {
      if (stopRequested(opts.out)) {
        evidence.run_error = 'stopped: a STOP file is present in the evidence directory; no further upload was made';
        print(`${evidence.run_error}\n`);
        break;
      }
      ctx.docDir = path.join(opts.out, safeName(doc.title));
      fs.mkdirSync(ctx.docDir, { recursive: true });
      print(`${doc.name} ... `);
      const record = await verifyDocument(page, ctx, { operator: { request: operatorContext.request }, anonymous }, doc);
      evidence.documents.push(record);
      writeEvidence(evidenceFile, evidence, forms);
      print(`${record.result}${record.reasons.length ? ` [${record.reasons.slice(0, 4).join(' | ')}]` : ''}\n`);
    }
  } catch (error) {
    evidence.run_error = String(error && error.message || error).split('\n')[0];
    print(`run stopped: ${evidence.run_error}\n`);
  } finally {
    await anonymous.dispose().catch(() => {});
    await browser.close();
    evidence.finished_at = isoNow();
    const passed = evidence.documents.filter(doc => doc.result === 'pass').length;
    evidence.summary = { documents: evidence.documents.length, selected: docs.length, passed,
      failed: evidence.documents.length - passed, run_checks_failed: evidence.run_checks.filter(item => item.status === 'fail').map(item => item.id) };
    writeEvidence(evidenceFile, evidence, forms);
  }
  print(`evidence: ${evidenceFile}\n${JSON.stringify(evidence.summary)}\n`);
  const complete = !evidence.run_error && evidence.summary.documents === evidence.summary.selected;
  return complete && evidence.summary.failed === 0 && evidence.summary.run_checks_failed.length === 0 ? 0 : 1;
}

module.exports = {
  EVIDENCE_SCHEMA, CLIENT_HEADERS, UsageError, parseArgs, serviceDateOf, documentsOf, readPrivate, loadCredentials,
  debugMayLog, secretForms, scrubSecret, compileDenylist, denylist, scanContext, addQuotes, ownWording, scanText, scanJson,
  scanFile, scanHeaders, checkScan, expectedActions, jsonChecks, domChecks, readEncounterDom, collectDomStrings, opsChecks,
  exportChecks, summarize, documentResult, evidenceProblems, writeEvidence, sessionProblems, stopRequested, main,
};

if (require.main === module) {
  main(process.argv.slice(2)).then(code => { process.exitCode = code; }, error => {
    process.stderr.write(`walk: ${error && error.stack || error}\n`);
    process.exitCode = 1;
  });
}
