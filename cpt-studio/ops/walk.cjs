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
 * wait bounded by --deadline-seconds). On done: the JSON against ops/verification/customer-contract.json, the contract
 * of section 6 that ops/scan_customer.py and the Django suite read too (every key it lists and no other, each value of
 * its type, at every depth - every customer JSON the page or the walk read on the session, list and encounter routes,
 * at every phase), and beside it the code statuses, each code's allowed actions by its status and decision, and the
 * context as uploaded; the page against the DOM contract of section 7 (the progress panel and its steps, the questions
 * panel, the code rows - by line, two lines of one code being two rows - with their number, units (a number shown as
 * that number, 0 included, units not given shown as "not given"), modifiers (each served one, and no other), status
 * badge, reason, second check, quotes and exactly the allowed buttons, the quotes panel, the notes panel, the document
 * viewer - its view address - and its "Download original" link, the export button); every quote chosen through the quotes
 * panel and judged by the walk's own search, apart from the page script (DECISIONS D368): the text of the pages it
 * searches read from the viewer's own text layer (an overprint copy left out only where its geometry bears the viewer's
 * flag out), the matching rule run on it (CORE-UX-DESIGN.md section 8), and the viewer's marks, count, pages and note
 * held to that - its occurrences exactly (count, place and case), a "not found" only where the walk finds none either,
 * nothing marked on another page or inside a character, every marked page drawn (its canvas holds drawn pixels) - counted;
 * the first
 * question, when there is one, answered through the panel and the new round waited for and checked again; one READY
 * line approved through #reviewDialog as the page draws it (the acknowledgement checkbox #reviewAckBox inside its label
 * #reviewAcknowledgement, which carries the session's acknowledgement; an agent-executed synthetic review), the page's
 * request naming the round shown, the line and its code, the line - that line only - decided, and the History naming the
 * line with its code ("L2 45380"); the draft and the approved TXT
 * exported through the export dialog as real browser downloads, the page's request naming the round shown ({kind, fmt,
 * round}), each fetched again from its download_url and compared byte for byte; that approval then undone through the
 * row's Undo, the page's request naming the round shown, the line, its code and the id of the decision it undoes (the
 * one the page showed), and the line - that line only - open again; a 390x844 viewport with no horizontal scroll; every
 * /ops/ path 404 to the customer (GET, and POST with
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
const CLIENT_HEADERS = { 'X-CPT-Studio-Client': 'customer-2026-11-22' };
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } };
const UI_TIMEOUT_MS = 30000;
const POLL_MS = 3000;
const MAX_POLL_ERRORS = 3;
const DEFAULT_DEADLINE_SECONDS = 1800;
const MIN_DEADLINE_SECONDS = 60;
const SETTLED_PHASES = new Set(['done', 'failed', 'stopped']);
const STEPS = ['reading', 'checking', 'finished'];
const INSURANCE = ['medicare', 'medicaid', 'commercial', 'unknown'];
const DOCUMENT_TYPES = { '.txt': 'text/plain', '.pdf': 'application/pdf',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
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
// The customer contract (BUILD-SPEC section 6): read by ops/scan_customer.py, the Django suite and this walk, so a key
// the server adds, drops or retypes fails all three until the file is consciously changed.
const CONTRACT_FILE = path.join(__dirname, 'verification', 'customer-contract.json');
const MAX_SHAPE_PROBLEMS = 60;  // ops/scan_customer.py shape_problems' bound
// The review dialog as the page draws it (studio/templates/studio/index.html): the acknowledgement is a checkbox inside
// a label that carries the session's acknowledgement; saving is offered once it is ticked (static/studio/app.js).
const REVIEW_DIALOG = { dialog: '#reviewDialog', label: '#reviewAcknowledgement', box: '#reviewAckBox',
  note: '#reviewNote', save: '#saveReview' };
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

// --- the contract (ops/verification/customer-contract.json) -------------------------------------------------------------

let CONTRACT_CACHE = null;
function contract() {
  if (!CONTRACT_CACHE) CONTRACT_CACHE = JSON.parse(fs.readFileSync(CONTRACT_FILE, 'utf8'));
  return CONTRACT_CACHE;
}

// json.dumps's rendering of a value (ASCII only, ', ' and ': ' between items), so a sentence reads as
// ops/scan_customer.py writes it.
function pyJson(value) {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return String(value).replace(/e([+-])(\d)$/, 'e$10$2');
  if (typeof value === 'string') {
    return JSON.stringify(value).replace(/[\u007f-\uffff]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
  }
  if (Array.isArray(value)) return `[${value.map(pyJson).join(', ')}]`;
  return `{${Object.entries(value).map(([key, item]) => `${pyJson(key)}: ${pyJson(item)}`).join(', ')}}`;
}

function kindOf(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return 'boolean';
  if (Array.isArray(value)) return 'a list';
  if (typeof value === 'object') return 'an object';
  return typeof value === 'number' ? 'number' : typeof value;
}

function scalarOk(base, value, spec) {
  switch (base) {
    case 'string': return typeof value === 'string';
    case 'integer': return Number.isInteger(value);  // JavaScript's JSON reads 1.0 as 1: the one reading Python's differs on
    case 'number': return typeof value === 'number';
    case 'boolean': return typeof value === 'boolean';
    case 'any': return true;
    case 'date': return typeof value === 'string' && new RegExp(spec.date_pattern).test(value);
    case 'iso': return typeof value === 'string' && new RegExp(spec.iso_pattern).test(value);
    default: return undefined;
  }
}

// ops/scan_customer.py shape_problems, read the same way and worded the same (ops/test_walk_contract.py holds the two
// readers to each other): the differences between a value and a contract node, each '<where>: <what>', at most 60 -
// a key the node does not list, a key it lists that is missing, a value of another type or outside its words.
function shapeProblems(value, node, where = '$', out = [], spec = contract()) {
  if (out.length >= MAX_SHAPE_PROBLEMS) return out;
  const types = spec.types;
  if (typeof node === 'string') {
    const nullable = node.endsWith('?');
    const base = nullable ? node.slice(0, -1) : node;
    const ok = scalarOk(base, value, spec);
    if (ok === undefined) out.push(`${where}: the contract names an unknown type ${base}`);
    else if (!(value === null && (nullable || base === 'any')) && !ok) out.push(`${where}: ${kindOf(value)} where the contract has ${node}`);
    return out;
  }
  if (!isObject(node)) {
    out.push(`${where}: the contract node is not understood`);
    return out;
  }
  if ('ref' in node) {
    if (value === null && node.nullable) return out;
    if (!Object.prototype.hasOwnProperty.call(types, node.ref)) {
      out.push(`${where}: the contract names an unknown type ${node.ref}`);
      return out;
    }
    return shapeProblems(value, types[node.ref], where, out, spec);
  }
  if (value === null && node.nullable) return out;
  if ('enum' in node) {
    if (typeof value === 'boolean' || !node.enum.includes(value)) {
      out.push(`${where}: ${pyJson(value)} is not one of ${node.enum.map(String).join('|')}`);
    }
    return out;
  }
  if ('items' in node) {
    if (!Array.isArray(value)) out.push(`${where}: ${kindOf(value)} where the contract has a list`);
    else value.forEach((item, index) => shapeProblems(item, node.items, `${where}[${index}]`, out, spec));
    return out;
  }
  if ('map' in node) {
    if (!isObject(value)) out.push(`${where}: ${kindOf(value)} where the contract has an object`);
    else for (const [key, item] of Object.entries(value)) shapeProblems(item, node.map, `${where}.${key}`, out, spec);
    return out;
  }
  if (isObject(node.keys)) {
    if (!isObject(value)) {
      out.push(`${where}: ${kindOf(value)} where the contract has an object`);
      return out;
    }
    for (const [key, child] of Object.entries(node.keys)) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) out.push(`${where}.${key}: missing (the contract lists it)`);
      else shapeProblems(value[key], child, `${where}.${key}`, out, spec);
    }
    for (const key of Object.keys(value)) {
      if (!Object.prototype.hasOwnProperty.call(node.keys, key)) out.push(`${where}.${key}: not in the customer contract`);
    }
    return out;
  }
  out.push(`${where}: the contract node is not understood`);
  return out;
}

// The contract a customer JSON read is held to, by its route: GET /api/session, GET /api/encounters and
// GET /api/encounters/<id> (an answer of the page or of the walk), or null for any other.
function contractFor(where) {
  const match = /^GET (\/api\/[^ ?#]*)/.exec(String(where));
  if (!match) return null;
  if (match[1] === '/api/session') return 'session';
  if (match[1] === '/api/encounters') return 'list';
  return /^\/api\/encounters\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(match[1]) ? 'encounter' : null;
}

function describeProblems(problems, limit = 10) {
  return `${problems.slice(0, limit).join('; ')}${problems.length > limit ? `; and ${problems.length - limit} more` : ''}`;
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

// A JSON value that is never a passage of the document: a code line's modifier is part of the code line the coding
// review returned, so it is scanned whole even when a quote holds the same words (SEC-S4: a modifier "Claude" beside a
// cited "Dr. Claude Example ..." was set aside as a part of the quote). ops/scan_customer.py reads the same paths.
const NEVER_QUOTED = /\.modifiers\[\d+\]$/;

// The hits of one string on one surface: {id, severity, surface, where, match}; a string that is not ``quotable``
// (NEVER_QUOTED) is scanned whole, nothing of it set aside as the document's.
function scanText(text, ctx, surface, where = '', hits = [], quotable = true) {
  const raw = typeof text === 'string' ? text : String(text ?? '');
  let cleaned = quotable ? ownWording(raw, ctx) : collapse(raw);
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

// A JSON value: every string value and every key (a forbidden key is a hit by itself); a value at a NEVER_QUOTED path is
// scanned whole.
function scanJson(value, ctx, where = '$', hits = []) {
  if (typeof value === 'string') return scanText(value, ctx, 'json', where, hits, !NEVER_QUOTED.test(where));
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
  const spec = contract();
  const problems = shapeProblems(enc, spec.encounter);
  out.push(check('json.contract', problems.length === 0, problems.length
    ? `${problems.length} difference(s) from customer-contract.json: ${describeProblems(problems)}`
    : 'every key customer-contract.json lists, of its type, and no other, at every depth'));
  const missing = Object.keys(spec.encounter.keys).filter(key => !Object.prototype.hasOwnProperty.call(enc || {}, key));
  out.push(check('json.keys', missing.length === 0, missing.length ? `the encounter lacks ${missing.join(', ')}`
    : 'every key of the encounter contract is served'));
  const codes = Array.isArray(enc?.codes) ? enc.codes : [];
  const shapes = codes.flatMap(code => Object.keys(spec.types.code.keys)
    .filter(key => !Object.prototype.hasOwnProperty.call(code || {}, key)).map(key => `${code?.code}: no ${key}`));
  out.push(check('json.codes.keys', shapes.length === 0, shapes.length ? shapes.slice(0, 8).join('; ') : `${codes.length} code(s), each in its shape`));
  const known = spec.types.code.keys.status.enum;
  const statuses = codes.filter(code => !known.includes(code?.status)).map(code => `${code?.code}: ${code?.status}`);
  out.push(check('json.codes.status', statuses.length === 0, statuses.length ? `unknown statuses: ${statuses.join(', ')}`
    : `every status is one of ${known.join(', ')}`));
  const actions = codes.filter(code => !sameList(code?.allowed_actions, expectedActions(code)))
    .map(code => `${code?.code} (${code?.status}${isObject(code?.decision) ? `, ${code.decision.action}` : ''}) offers [${sorted(code?.allowed_actions)}], not [${expectedActions(code)}]`);
  out.push(check('json.codes.actions', actions.length === 0, actions.length ? actions.join('; ')
    : 'every code offers exactly the actions its status and decision allow'));
  const context = enc?.context || {};
  out.push(check('json.context', context.service_date === doc.serviceDate && context.insurance === doc.insurance,
    `the encounter's context is ${JSON.stringify(context)}; uploaded ${doc.serviceDate}, ${doc.insurance}`));
  out.push(check('json.progress.phase', spec.encounter.keys.progress.keys.phase.enum.includes(enc?.progress?.phase),
    `progress.phase is ${JSON.stringify(enc?.progress?.phase)}`));
  return out;
}

// Runs in the page: what the encounter view shows, by the DOM contract's selectors.
function readEncounterDom() {
  const text = el => (el ? el.textContent : '').replace(/\s+/g, ' ').trim();
  const panel = document.querySelector('section.progress-panel');
  const questions = document.querySelector('section#questionsPanel');
  // the viewer keeps the view address on its element (data-view-url): the PDF region the page draws in, or the text's frame;
  // a viewer without it is read by its frame's address
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
      return { line: li.getAttribute('data-line'), code: li.getAttribute('data-code'), status: li.getAttribute('data-status'),
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
    viewer: viewer ? { view: viewer.getAttribute('data-view-url') || (frame ? frame.getAttribute('src') : null),
      original: original ? original.getAttribute('href') : null } : null,
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

// --- the quoted words marked in the viewer (DECISIONS D368) -------------------------------------------------------------
// The walk is the viewer's independent judge (round 3). It reads the text of every page it searches from the viewer's
// own text layer, runs its own search with the matching rule (CORE-UX-DESIGN.md section 8, "Marking a quoted passage":
// R1 overprint copies, R2 word edges, R3 format characters, and the rule's white space, NFKC, whole characters, exact
// case first and pages), and holds the viewer's marks, count, pages and note to its own result: it never takes the
// viewer's word. It also requires every marked page to be drawn (its canvas holds drawn pixels) and no mark to begin or
// end inside a character. The page's text is read into the walk's memory to be searched and is never written to the
// evidence: the evidence keeps counts, page numbers and reasons that name a quote by its line and page, never its words.

// The quotes the page lists, in its order: {code, line, text, page} of every quote of every code that has words.
function servedQuotes(enc) {
  return (Array.isArray(enc?.codes) ? enc.codes : []).flatMap(code => (Array.isArray(code?.quotes) ? code.quotes : [])
    .filter(quote => typeof quote?.text === 'string' && quote.text.trim())
    .map(quote => ({ code: code.code, line: code.line ?? null, text: quote.text.trim(), page: Number.isInteger(quote.page) && quote.page > 0 ? quote.page : null })));
}

// Text as the marks are compared with their quote: NFKC, white space ignored entirely.
function foldMarked(text) {
  return String(text ?? '').normalize('NFKC').replace(/\s+/gu, '');
}

// Why the page framed the browser's own viewer instead of drawing the PDF (the viewer element's data-fallback), as the
// walk's reason names it, and the note's reason sentence for each (ROUND3 N3, character for character).
const FALLBACK_WHY = { browser: 'marking needs a newer browser', library: 'the marking tool did not work in the page',
  document: 'the document cannot be drawn in the page', slow: 'the document took too long to load' };
const FRAME_REASONS = { browser: 'Marking needs a newer browser.',
  library: 'The marking tool did not work here, so nothing is marked.',
  document: 'This document cannot be drawn here, so nothing is marked.',
  slow: 'The document took too long to load here, so nothing is marked.' };
// Overprint copies (R1): the walk reads the viewer's flag (data-overprint="1" on the copy's span) and holds it to the
// span's geometry - its text equals that of one of the OVERPRINT_WINDOW spans before it, and its box's origin lies within
// max(OVERPRINT_MIN_PX, OVERPRINT_SHARE x its height) of that span's - so the viewer cannot hide text by flagging it.
const OVERPRINT_WINDOW = 8;
const OVERPRINT_MIN_PX = 1.5;
const OVERPRINT_SHARE = 0.2;
// A marked page is drawn (S3) when its canvas is shown, at least CANVAS_OPAQUE_MIN of its pixels are painted, and at
// least CANVAS_MARK_CONTENT_MIN of the pixels under its marks differ from the page's paper (its most common colour) by
// two steps of 16 in a channel: the marked words are drawn where they are marked. Measured (D368 round 3) on the dev
// preview's PDF fixtures and the walk's gi-02 in Chromium at 1440x1000: every drawn page was fully painted (1.0), and the
// share under the marks was 0.350 to 0.461 over 33 marked pages; the threshold is about a seventh of the lowest, and a
// canvas that was never drawn is 0 painted. A page shown for a quote that was not found must be painted and shown (a
// blank page with no text has nothing under any mark).
const CANVAS_OPAQUE_MIN = 0.99;
const CANVAS_MARK_CONTENT_MIN = 0.05;
// A document of at most this many pages is read whole for every quote, so a mark on any page is seen; a longer one is
// read on the searched pages, the pages the viewer says it marked and the pages it has drawn.
const FULL_READ_PAGES = 12;

const FORMAT_CHARACTER = /\p{Cf}/u;
const WORD_START = /^[\p{L}\p{N}]/u;
const JOINS_A_WORD = /[\p{L}\p{N}\p{M}]/u;

let graphemeCutter;
// Where each character of a text begins and ends, as [start, end] offsets covering the whole text: its extended grapheme
// clusters (Intl.Segmenter), else a character with the marks that follow it.
function graphemeSpans(value) {
  if (graphemeCutter === undefined) {
    graphemeCutter = typeof Intl === 'object' && typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('en', { granularity: 'grapheme' }) : null;
  }
  if (graphemeCutter) return Array.from(graphemeCutter.segment(value), ({ index, segment }) => [index, index + segment.length]);
  return Array.from(value.matchAll(/\P{M}\p{M}*|\p{M}+/gu), match => [match.index, match.index + match[0].length]);
}

// The characters of a text, as the rule cuts them: its grapheme clusters, joined again wherever NFKC combines two of them
// (so NFKC of the text is exactly its characters' NFKC, in order). Each is {start, end, nfkc}; together they cover the text.
function cutCharacters(value) {
  const nfkc = text => text.normalize('NFKC');
  const cuts = [];
  for (const span of graphemeSpans(value)) {
    const last = cuts[cuts.length - 1];
    if (last && value.codePointAt(span[0]) >= 0x300) {
      const before = value.slice(last[0], last[1]);
      const after = value.slice(span[0], span[1]);
      if (nfkc(before + after) !== nfkc(before) + nfkc(after)) {
        last[1] = span[1];
        continue;
      }
    }
    cuts.push([span[0], span[1]]);
  }
  const whole = nfkc(value);
  const parts = cuts.map(([start, end]) => nfkc(value.slice(start, end)));
  while (cuts.length > 1 && parts.join('') !== whole) {
    let at = 0;
    let index = 0;
    while (index < parts.length - 1 && whole.startsWith(parts[index], at)) {
      at += parts[index].length;
      index += 1;
    }
    const from = Math.max(0, index - 1);
    const to = Math.min(cuts.length - 1, index + 1);
    cuts.splice(from, to - from + 1, [cuts[from][0], cuts[to][1]]);
    parts.splice(from, to - from + 1, nfkc(value.slice(cuts[from][0], cuts[from][1])));
  }
  return cuts.map(([start, end], index) => ({ start, end, nfkc: parts[index] }));
}

const firstCodePoint = text => (text ? String.fromCodePoint(text.codePointAt(0)) : null);
const lastCodePoint = text => (text ? Array.from(text).pop() : null);
// R2: the start or end of the page, or a character that is not a letter, a digit or a combining mark, is a word edge.
const wordEdge = codePoint => codePoint === null || !JOINS_A_WORD.test(codePoint);

// One page's text as the rule reads it, from the text layer the walk read (readPdfPage's tokens): the item strings in
// order, an overprint copy's string left out (R1), a line break where the layer has one (<br>: an item the library marks
// hasEOL, a copy's included), format characters dropped (R3). {number, items, clean, posOf, units, starts}: posOf maps
// "<item> <offset in its string>" to the place in `clean`; units are the characters that are not white space, each with
// its NFKC (`folded`, white space dropped) and the code points just before and after it in the page's text as the page
// writes it, not after NFKC (null at the page's start or end), which R2 reads, as the viewer does: "Botox™" is "Botox"
// and a sign, though NFKC writes the sign "TM"; starts are the places a character begins (and the text's end).
function pageModel(number, tokens) {
  const items = [];
  const posOf = new Map();
  let clean = '';
  for (const token of Array.isArray(tokens) ? tokens : []) {
    if (token?.kind === 'br') {
      clean += '\n';
      continue;
    }
    const item = items.length;
    items.push(token || {});
    if (token?.copy) continue;
    let offset = 0;
    for (const ch of typeof token?.text === 'string' ? token.text : '') {
      if (!FORMAT_CHARACTER.test(ch)) {
        for (let k = 0; k < ch.length; k += 1) posOf.set(`${item} ${offset + k}`, clean.length + k);
        clean += ch;
      }
      offset += ch.length;
    }
  }
  const characters = cutCharacters(clean);
  const units = [];
  characters.forEach((character, index) => {
    const folded = character.nfkc.replace(/\s+/gu, '');
    if (!folded) return;
    units.push({ page: number, start: character.start, end: character.end, folded,
      before: index > 0 ? lastCodePoint(clean.slice(characters[index - 1].start, characters[index - 1].end)) : null,
      after: index + 1 < characters.length ? firstCodePoint(clean.slice(characters[index + 1].start, characters[index + 1].end)) : null });
  });
  const starts = new Set(characters.map(character => character.start));
  starts.add(clean.length);
  return { number, items, clean, posOf, units, starts };
}

// A quote as the rule reads it: format characters dropped, cut into characters, NFKC, white space dropped; exact and
// lower-cased (each character on its own, as the page's are); whether its first and its last character are a letter or a
// digit (R2: only then is a word edge asked for at that end).
function foldQuote(text) {
  const clean = String(text ?? '').replace(/\p{Cf}/gu, '');
  const units = cutCharacters(clean).map(character => character.nfkc.replace(/\s+/gu, '')).filter(Boolean);
  return { exact: units.join(''), blind: units.map(unit => unit.toLowerCase()).join(''),
    start: units.length > 0 && WORD_START.test(units[0]), end: units.length > 0 && WORD_START.test(units[units.length - 1]) };
}

// Every occurrence of a folded quote in the joined text of `numbers` pages (left to right, without overlap, whole
// characters only, word edges as R2 asks), exact case first and case-blind only where there is none; `keep` then filters
// them, as the viewer's rule does (the quote's page and the next: a passage that starts on the one and ends on the other).
// {units, found: [[first unit, last unit]], caseBlind}, or null.
function searchPages(models, numbers, wanted, keep) {
  const units = numbers.flatMap(number => models.get(number).units);
  for (const caseBlind of [false, true]) {
    let hay = '';
    const owner = [];
    units.forEach((unit, index) => {
      const value = caseBlind ? unit.folded.toLowerCase() : unit.folded;
      hay += value;
      for (let k = 0; k < value.length; k += 1) owner.push(index);
    });
    const needle = caseBlind ? wanted.blind : wanted.exact;
    const found = [];
    let from = 0;
    for (let at = hay.indexOf(needle); at >= 0; at = hay.indexOf(needle, from)) {
      const end = at + needle.length;
      const whole = (at === 0 || owner[at - 1] !== owner[at]) && (end === hay.length || owner[end - 1] !== owner[end]);
      const edges = whole && (!wanted.start || wordEdge(units[owner[at]].before)) && (!wanted.end || wordEdge(units[owner[end - 1]].after));
      if (edges) {
        found.push([owner[at], owner[end - 1]]);
        from = end;
      } else {
        from = at + 1;
      }
    }
    const kept = found.filter(([first, last]) => keep(units[first], units[last]));
    if (kept.length) return { units, found: kept, caseBlind };
  }
  return null;
}

// The places (`<page>:<place in its clean text>`, white space aside) a run of units covers.
function unitPlaces(models, units, first, last) {
  const keys = [];
  for (let index = first; index <= last; index += 1) {
    const unit = units[index];
    const { clean } = models.get(unit.page);
    for (let at = unit.start; at < unit.end; at += 1) if (!/\s/u.test(clean[at])) keys.push(`${unit.page}:${at}`);
  }
  return keys;
}

// The walk's own search for one quote over the pages it read (models: page number -> pageModel) of a document of
// pageCount pages: {page, pageCount, status, scope, caseBlind, count, pages, occurrences, empty, unread}. status:
// 'marked', 'not_found', 'missing_page', 'empty' (nothing to look for) or 'unread' (a page it must search was not read);
// occurrences: each {keys (its places, joined), pages}; empty: the quote's page (or, with no page, every page) has no
// searchable character (N2).
function ownSearch(quote, models, pageCount) {
  const page = Number.isInteger(quote?.page) && quote.page > 0 ? quote.page : null;
  const result = { page, pageCount, status: 'not_found', scope: page ? 'page' : 'document', caseBlind: false, count: 0,
    pages: [], occurrences: [], empty: false, unread: [] };
  const wanted = foldQuote(quote?.text);
  if (!wanted.exact) return { ...result, status: 'empty' };
  if (page && page > pageCount) return { ...result, status: 'missing_page' };
  const every = Array.from({ length: pageCount }, (_, index) => index + 1);
  const numbers = page ? [page, page + 1].filter(number => number <= pageCount) : every;
  const unread = numbers.filter(number => !models.has(number));
  if (unread.length) return { ...result, status: 'unread', unread };
  let hit;
  if (!page) {
    hit = searchPages(models, every, wanted, () => true);
  } else {
    hit = searchPages(models, [page], wanted, () => true);
    if (!hit && page < pageCount) {
      hit = searchPages(models, [page, page + 1], wanted, (first, last) => first.page === page && last.page === page + 1);
      if (hit) result.scope = 'continued';
    }
  }
  if (!hit) {
    result.empty = (page ? [page] : every).every(number => models.get(number).units.length === 0);
    return result;
  }
  const occurrences = hit.found.map(([first, last]) => {
    const keys = unitPlaces(models, hit.units, first, last);
    return { keys: keys.join(' '), pages: [...new Set(keys.map(key => Number(key.split(':')[0])))] };
  });
  const pages = [...new Set(occurrences.flatMap(item => item.pages))].sort((a, b) => a - b);
  return { ...result, status: 'marked', caseBlind: hit.caseBlind, count: occurrences.length, pages, occurrences };
}

function joinWords(items) {
  return items.length <= 2 ? items.join(' and ') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

// The note the viewer must show for one quote chosen in a drawn PDF, from the walk's own result, character for character
// (ROUND3's notes: the marked sentences unchanged, N1 and N2 when nothing is found).
function pdfQuoteNote(result) {
  const { page, status, scope, count, pages, pageCount, empty } = result;
  const named = list => (list.length === 1 ? `page ${list[0]}` : `pages ${joinWords(list.map(String))}`);
  if (status === 'marked') {
    if (scope === 'continued') {
      return count === 1 ? `Marked on page ${page}, continuing onto page ${page + 1}.`
        : `These words appear ${count} times, starting on page ${page} and continuing onto page ${page + 1}. Each is marked.`;
    }
    if (scope === 'page') return count === 1 ? `Marked on page ${page}.` : `These words appear ${count} times on page ${page}. Each is marked.`;
    return count === 1 ? `Marked on ${named(pages)}.` : `These words appear ${count} times, on ${named(pages)}. Each is marked.`;
  }
  if (status === 'missing_page') return `This passage names page ${page}, but the document has ${pageCount} ${pageCount === 1 ? 'page' : 'pages'}. Nothing is marked.`;
  if (status === 'empty') return 'This passage has no words to mark.';
  if (page) {
    return empty ? `Page ${page} has no text the viewer can search (it may be a scanned image), so nothing is marked. Page ${page} is shown.`
      : `The exact words were not found in the searchable text of page ${page}, so nothing is marked. Page ${page} is shown.`;
  }
  return empty ? 'This document has no text the viewer can search (it may be a scanned image), so nothing is marked.'
    : 'The exact words were not found in the searchable text of this document, so nothing is marked.';
}

// The overprint flags of one page the walk read that its geometry does not bear out (R1, S4): a span flagged
// data-overprint whose text (NFKC, holding a character that is not white space) equals none of the OVERPRINT_WINDOW spans
// before it whose box origin lies within max(OVERPRINT_MIN_PX, OVERPRINT_SHARE x the flagged span's height) of its own.
function unbornFlags(tokens) {
  const items = (Array.isArray(tokens) ? tokens : []).filter(token => token?.kind !== 'br');
  let count = 0;
  items.forEach((token, index) => {
    if (!token?.copy) return;
    const text = String(token.text ?? '').normalize('NFKC');
    const box = Array.isArray(token.box) ? token.box : null;
    const borne = box && /\S/u.test(text) && items.slice(Math.max(0, index - OVERPRINT_WINDOW), index).some(earlier => {
      const other = Array.isArray(earlier?.box) ? earlier.box : null;
      return other && String(earlier.text ?? '').normalize('NFKC') === text
        && Math.hypot(box[0] - other[0], box[1] - other[1]) <= Math.max(OVERPRINT_MIN_PX, OVERPRINT_SHARE * box[2]);
    });
    if (!borne) count += 1;
  });
  return count;
}

// What the viewer marked on the pages the walk read, each occurrence as its places in the walk's own text (white space and
// format characters aside): {occurrences: Map(occurrence -> {keys, pages}), inCopies (marked characters of an overprint
// copy), cut (an occurrence's marked run on a page that begins or ends inside a character, S5: every run of adjacent
// marked text is read at both ends, so a letter marked without the accent beside it is seen)}.
function viewerMarks(models, pagesRead) {
  const occurrences = new Map();
  let inCopies = 0;
  let cut = 0;
  for (const [number, read] of pagesRead) {
    const model = models.get(number);
    if (!model) continue;
    const runs = new Map();
    for (const mark of Array.isArray(read?.marks) ? read.marks : []) {
      const occurrence = String(mark.occurrence);
      if (!occurrences.has(occurrence)) occurrences.set(occurrence, { keys: [], pages: new Set() });
      const entry = occurrences.get(occurrence);
      entry.pages.add(number);
      if (!runs.has(occurrence)) runs.set(occurrence, new Set());
      for (let offset = mark.start; offset < mark.end; offset += 1) {
        const at = model.posOf.get(`${mark.item} ${offset}`);
        if (at === undefined) {
          if (model.items[mark.item]?.copy) inCopies += 1;
          continue;
        }
        runs.get(occurrence).add(at);
        if (!/\s/u.test(model.clean[at])) entry.keys.push(`${number}:${at}`);
      }
    }
    for (const places of runs.values()) {
      const sorted = [...places].sort((a, b) => a - b);
      let cutHere = false;
      sorted.forEach((at, index) => {
        if (index === 0 || sorted[index - 1] !== at - 1) cutHere ||= !model.starts.has(at);
        if (index === sorted.length - 1 || sorted[index + 1] !== at + 1) cutHere ||= !model.starts.has(at + 1);
      });
      if (cutHere) cut += 1;
    }
  }
  for (const entry of occurrences.values()) {
    entry.keys = [...new Set(entry.keys)].sort((a, b) => {
      const [pa, xa] = a.split(':').map(Number);
      const [pb, xb] = b.split(':').map(Number);
      return pa - pb || xa - xb;
    }).join(' ');
  }
  return { occurrences, inCopies, cut };
}

// Whether a page's canvas, as readPdfPage measured it in the page, is drawn: shown and painted, and - for a page the
// viewer marked - with its marked words drawn under the marks (S3); '' when it is, else why not.
function canvasProblem(canvas, underMarks) {
  if (!canvas || !canvas.present) return 'it has no canvas';
  if (canvas.error) return `its canvas could not be read (${canvas.error})`;
  if (!canvas.visible) return 'its canvas is not shown';
  if (!(canvas.opaque >= CANVAS_OPAQUE_MIN)) return 'its canvas is not drawn';
  if (underMarks && !(canvas.markPixels > 0 && canvas.markContent / canvas.markPixels >= CANVAS_MARK_CONTENT_MIN)) {
    return 'nothing is drawn under its marks';
  }
  return '';
}

// The text rule of a text document (the page's findPassages, kept: runs of white space count as one space, exact case
// before case-blind), the walk's own copy: every place the passage occurs, as [start, end] in the text's own offsets.
function collapseSpaceText(source) {
  const chars = [];
  const map = [];
  let space = false;
  for (let index = 0; index < source.length; index += 1) {
    const ch = source[index];
    if (/\s/.test(ch)) {
      if (!space && chars.length) {
        chars.push(' ');
        map.push(index);
      }
      space = true;
    } else {
      chars.push(ch);
      map.push(index);
      space = false;
    }
  }
  return { flat: chars.join(''), map };
}

function lowerUnitsText(value) {
  return value.replace(/[\s\S]/g, unit => {
    const lower = unit.toLowerCase();
    return lower.length === 1 ? lower : unit;
  });
}

function findPassagesText(source, passage) {
  const hay = collapseSpaceText(String(source ?? ''));
  const want = collapseSpaceText(String(passage ?? '')).flat.trim();
  if (!want) return [];
  const places = (flat, needle) => {
    const found = [];
    for (let at = flat.indexOf(needle); at >= 0; at = flat.indexOf(needle, at + needle.length)) found.push(at);
    return found;
  };
  let found = places(hay.flat, want);
  if (!found.length) found = places(lowerUnitsText(hay.flat), lowerUnitsText(want));
  return found.map(at => [hay.map[at], hay.map[at + want.length - 1] + 1]);
}

function textNote(count) {
  if (!count) return 'The exact words could not be found in the document, so nothing is marked.';
  return count === 1 ? 'Marked in the document.' : `These words appear ${count} times in the document. Each is marked.`;
}

// One chosen quote judged against what the viewer showed (chooseQuotes' reading), by the walk's own search:
// {outcome, off_page, mismatched, missed, cut, blank, flags, no_text, problems}. outcome: 'once' or 'multi' (the viewer
// marked exactly the walk's own occurrences - their count, places and case - and said so), 'not_found' (the walk's own
// search finds nothing either, and the note says so exactly: N1, N2 when the page has no searchable text, the missing
// page or the empty passage), 'unavailable' (the browser's own viewer is shown: no marking; the problem says why, as the
// viewer keeps it in data-fallback) or 'unresolved'. off_page counts marks on a page that is neither the quote's nor,
// for an occurrence that starts on it, the next; mismatched the viewer's occurrences that are not the walk's; missed the
// walk's occurrences the viewer did not mark; cut the occurrences' marked runs that begin or end inside a character
// (S5); blank the marked pages not drawn (S3); flags the overprint flags their geometry does not bear out (R1).
function judgeQuote(quote, reading) {
  const out = { outcome: 'unresolved', off_page: 0, mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0, no_text: false, problems: [] };
  const name = `quote ${quote?.line || quote?.code || '?'}${quote?.page ? ` (page ${quote.page})` : ''}`;
  const problem = text => out.problems.push(`${name}: ${text}`);
  if (!quote || !reading) {
    problem('the viewer did not answer');
    return out;
  }
  const note = String(reading.note ?? '').trim();
  const page = Number.isInteger(quote.page) && quote.page > 0 ? quote.page : null;
  if (reading.mode === 'frame') {
    out.outcome = 'unavailable';
    const own = map => (Object.prototype.hasOwnProperty.call(map, reading.fallback) ? map[reading.fallback] : null);
    problem(`the PDF is shown by the browser's own viewer (${own(FALLBACK_WHY) || 'no reason given'}), so nothing could be marked`);
    const reason = own(FRAME_REASONS);
    if (!reason || note !== (page ? `${reason} The quote is on page ${page}.` : reason)) problem('the note does not say why marking is unavailable, as written');
    const frame = reading.frame || {};
    if (page && frame.page !== page) problem(`the frame does not open page ${page}`);
    if (page && frame.previousPage !== null && frame.previousPage !== undefined && frame.replaced !== null && frame.replaced !== undefined) {
      if (frame.previousPage !== page && !frame.replaced) problem(`the frame keeps the element that showed page ${frame.previousPage}, so the browser's viewer does not move to page ${page}`);
      if (frame.previousPage === page && frame.replaced) problem(`the frame was opened again for page ${page}, which it already showed`);
    }
    return out;
  }
  if (reading.mode === 'text') {
    const text = reading.text || {};
    if (typeof text.source !== 'string') {
      problem('the text could not be read');
      return out;
    }
    const expected = findPassagesText(text.source, quote.text).map(([start, end]) => `${start}-${end}`);
    const shown = (Array.isArray(text.marks) ? text.marks : []).map(([start, end]) => `${start}-${end}`);
    const left = [...expected];
    for (const item of shown) {
      const at = left.indexOf(item);
      if (at >= 0) left.splice(at, 1);
      else out.mismatched += 1;
    }
    out.missed = left.length;
    if (out.mismatched) problem(`${out.mismatched} marked passage(s) are not the walk's own`);
    if (out.missed) problem(`${out.missed} passage(s) the walk found are not marked`);
    if ((reading.status === 'marked') !== (expected.length > 0)) problem(`the viewer says ${reading.status || 'nothing'}, the walk's own search finds ${expected.length}`);
    if (Number(reading.count || 0) !== expected.length) problem(`the viewer counts ${Number(reading.count || 0)}, the walk's own search ${expected.length}`);
    if (note !== textNote(expected.length)) problem('the note does not say what was marked, as written');
    if (!out.problems.length) out.outcome = expected.length === 0 ? 'not_found' : expected.length === 1 ? 'once' : 'multi';
    return out;
  }
  if (reading.mode !== 'pdf') {
    problem(`the viewer is ${reading.mode || 'not shown'}`);
    return out;
  }
  const pagesRead = reading.pagesRead instanceof Map ? reading.pagesRead : new Map();
  const models = new Map();
  for (const [number, read] of pagesRead) {
    if (!read?.drawn) continue;
    models.set(number, pageModel(number, read.tokens));
    out.flags += unbornFlags(read.tokens);
  }
  if (out.flags) problem(`${out.flags} span(s) flagged as an overprint copy are not one (their text or place differs from every span before them)`);
  const result = ownSearch(quote, models, Number(reading.pageCount) || 0);
  if (result.status === 'unread') {
    problem(`page(s) ${result.unread.join(', ')} could not be read`);
    return out;
  }
  const shown = viewerMarks(models, pagesRead);
  out.cut = shown.cut;
  if (out.cut) problem(`${out.cut} marked part(s) begin or end inside a character`);
  if (shown.inCopies) problem('an overprint copy is marked');
  // the pages: a mark (or a page the viewer says it marked) that is neither the quote's page nor the next beside it
  if (page) {
    for (const entry of shown.occurrences.values()) {
      const starts = entry.pages.has(page);
      for (const number of entry.pages) if (!(number === page || (starts && number === page + 1))) out.off_page += 1;
    }
    const claimed = Array.isArray(reading.pages) ? reading.pages : [];
    out.off_page += claimed.filter(number => number !== page && !(number === page + 1 && claimed.includes(page))).length;
    if (out.off_page) problem(`${out.off_page} mark(s) on another page`);
  }
  // the occurrences: the viewer's against the walk's own, by their places (so by count, place and case)
  const expected = new Map();
  for (const item of result.occurrences) expected.set(item.keys, (expected.get(item.keys) || 0) + 1);
  for (const entry of shown.occurrences.values()) {
    if (expected.get(entry.keys)) expected.set(entry.keys, expected.get(entry.keys) - 1);
    else out.mismatched += 1;
  }
  out.missed = [...expected.values()].reduce((sum, value) => sum + value, 0);
  if (out.mismatched) problem(`${out.mismatched} marked occurrence(s) are not the walk's own (other words, another case or another place)`);
  if (out.missed) problem(`${out.missed} occurrence(s) the walk found are not marked`);
  const marked = result.status === 'marked';
  if (marked !== (reading.status === 'marked')) problem(`the viewer says ${reading.status || 'nothing'}, the walk's own search ${marked ? `finds ${result.count}` : 'finds none'}`);
  if (Number(reading.count || 0) !== result.count) problem(`the viewer counts ${Number(reading.count || 0)}, the walk's own search ${result.count}`);
  const claimed = (Array.isArray(reading.pages) ? reading.pages : []).join(' ');
  if (claimed !== result.pages.join(' ')) problem(`the viewer names page(s) [${claimed}], the walk's own search [${result.pages.join(' ')}]`);
  if (note !== pdfQuoteNote(result)) problem('the note does not say what was done, as written');
  // drawn (S3): every page holding a mark (the words under the viewer's marks drawn), and the page shown for a quote
  // not found
  const viewerPages = new Set([...shown.occurrences.values()].flatMap(entry => [...entry.pages]));
  const markedPages = new Set([...result.pages, ...viewerPages]);
  for (const number of markedPages) {
    const why = canvasProblem(pagesRead.get(number)?.canvas, viewerPages.has(number));
    if (why) {
      out.blank += 1;
      problem(`page ${number} is marked, but ${why}`);
    }
  }
  if (!marked && page && pagesRead.has(page)) {
    const why = canvasProblem(pagesRead.get(page)?.canvas, false);
    if (why) {
      out.blank += 1;
      problem(`page ${page} is shown, but ${why}`);
    }
  }
  out.no_text = !marked && result.empty;
  if (!out.problems.length) out.outcome = marked ? (result.count === 1 ? 'once' : 'multi') : 'not_found';
  return out;
}

// The check over every quote chosen ({quote, reading}), counted: how many were marked once, more than once, not found
// (the walk's own search agreeing; and of them, on a page with no searchable text), unavailable, marked off their page,
// marked as other than the walk's occurrences, not marked where the walk found them, cut inside a character, marked on a
// page not drawn, and the overprint flags not borne out. It passes when every quote was judged as the walk's own search
// says and nothing was marked on another page - and, where the PDF viewer drew the document, when at least one of its
// quotes was marked: a quote not found is allowed, but a viewer that marks nothing at all does not pass on the walk's
// own documents, whose quotes are their own words.
function quoteMarkChecks(chosen) {
  const data = { quotes: chosen.length, marked_once: 0, marked_multi: 0, not_found: 0, no_text: 0, unavailable: 0, unresolved: 0,
    off_page: 0, mismatched: 0, missed: 0, cut: 0, blank: 0, flags: 0 };
  const problems = [];
  const inPdf = { chosen: 0, marked: 0 };
  for (const { quote, reading } of chosen) {
    const judged = judgeQuote(quote, reading);
    data[{ once: 'marked_once', multi: 'marked_multi', not_found: 'not_found', unavailable: 'unavailable' }[judged.outcome] || 'unresolved'] += 1;
    if (judged.outcome === 'not_found' && judged.no_text) data.no_text += 1;
    for (const key of ['off_page', 'mismatched', 'missed', 'cut', 'blank', 'flags']) data[key] += judged[key];
    problems.push(...judged.problems);
    if (reading?.mode === 'pdf') {
      inPdf.chosen += 1;
      if (judged.outcome === 'once' || judged.outcome === 'multi') inPdf.marked += 1;
    }
  }
  // first among the problems, so the reason always shows it
  if (inPdf.chosen && !inPdf.marked) problems.unshift(`${inPdf.chosen} quote(s) chosen in the PDF viewer and not one marked`);
  const summary = `${data.quotes} quote(s) chosen: ${data.marked_once} marked once, ${data.marked_multi} marked more than once, `
    + `${data.not_found} not found (the walk's own search agrees; ${data.no_text} on a page with no searchable text), `
    + `${data.off_page} mark(s) off the quote's page, ${data.mismatched} marked other than the walk's own, `
    + `${data.missed} found by the walk and not marked, ${data.cut} beginning or ending inside a character, `
    + `${data.blank} marked page(s) not drawn, ${data.flags} overprint flag(s) not borne out`;
  return check('quotes.marks', chosen.length > 0 && problems.length === 0 && data.off_page === 0, problems.length ? `${summary}; ${problems.slice(0, 8).join('; ')}` : summary, data);
}

// Runs in the page: what the viewer shows of the quote chosen last - its mode, why it framed the browser's own viewer,
// what it says it marked (the data-mark-* state it keeps on #documentViewer), the note, how many pages it has and which
// are drawn.
function readViewer() {
  const viewer = document.querySelector('#documentViewer');
  if (!viewer) return null;
  const note = document.querySelector('#viewerMark');
  return { mode: viewer.tagName === 'IFRAME' ? 'text' : viewer.getAttribute('data-mode') || 'loading',
    fallback: viewer.getAttribute('data-fallback') || '',
    marked: viewer.getAttribute('data-marked') || '', status: viewer.getAttribute('data-mark-status') || '',
    pages: (viewer.getAttribute('data-mark-pages') || '').split(' ').filter(Boolean).map(Number),
    count: Number(viewer.getAttribute('data-mark-count') || 0), note: note ? note.textContent : '',
    pageCount: viewer.querySelectorAll('.pdf-page').length,
    drawn: Array.from(viewer.querySelectorAll('.pdf-page')).filter(item => item.querySelector('.pdf-text')).map(item => Number(item.getAttribute('data-page'))) };
}

// Runs in the page: one drawn page of the PDF viewer as the walk judges it - its text layer in order (each item's span:
// its text, whether the viewer flags it as an overprint copy, its box [left, top, height] in CSS px from the page's
// corner; and each <br>), every mark (.pdf-mark, or a mark element, with data-occurrence) as the item and the offsets in
// that item's string it covers, and the page's canvas measured where it is drawn: whether it is shown, the share of its
// pixels painted and the share that differ from its dominant colour. Pixels never leave the page.
function readPdfPage(number) {
  const item = document.querySelector(`#documentViewer .pdf-page[data-page="${number}"]`);
  const layer = item ? item.querySelector('.pdf-text') : null;
  if (!item || !layer) return { number, drawn: false };
  const origin = item.getBoundingClientRect();
  const tokens = [];
  const marks = [];
  let items = 0;
  const visit = parent => {
    for (const node of Array.from(parent.childNodes)) {
      if (node.nodeType === 1 && node.tagName === 'BR') {
        tokens.push({ kind: 'br' });
        continue;
      }
      if (node.nodeType === 1 && node.classList.contains('markedContent')) {
        visit(node);
        continue;
      }
      if (node.nodeType !== 1 && node.nodeType !== 3) continue;
      const index = items;
      items += 1;
      const token = { kind: 'item', text: node.textContent, copy: node.nodeType === 1 && node.getAttribute('data-overprint') === '1', box: null };
      if (node.nodeType === 1) {
        const box = node.getBoundingClientRect();
        token.box = [box.left - origin.left, box.top - origin.top, box.height];
        let offset = 0;
        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
        for (let text = walker.nextNode(); text; text = walker.nextNode()) {
          const mark = text.parentElement ? text.parentElement.closest('.pdf-mark, mark') : null;
          if (mark && mark !== node && node.contains(mark)) {
            marks.push({ item: index, occurrence: mark.getAttribute('data-occurrence'), start: offset, end: offset + text.data.length });
          }
          offset += text.data.length;
        }
      }
      tokens.push(token);
    }
  };
  visit(layer);
  for (const mark of marks) mark.occurrence = /^\d+$/.test(String(mark.occurrence)) ? Number(mark.occurrence) : `?${mark.occurrence}`;
  const canvas = item.querySelector('canvas');
  const measured = { present: Boolean(canvas) };
  if (canvas) {
    const style = getComputedStyle(canvas);
    const shown = getComputedStyle(item);
    const box = canvas.getBoundingClientRect();
    measured.visible = style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) > 0
      && shown.visibility === 'visible' && Number(shown.opacity) > 0 && box.width >= origin.width * 0.5 && box.height >= origin.height * 0.5;
    try {
      const { width, height } = canvas;
      const { data } = canvas.getContext('2d').getImageData(0, 0, width, height);
      // the paper: the most common colour among the painted pixels, in steps of 16 per channel
      const bins = new Uint32Array(4096);
      let opaque = 0;
      for (let at = 0; at < data.length; at += 4) {
        if (data[at + 3] !== 255) continue;
        opaque += 1;
        bins[((data[at] >> 4) << 8) | ((data[at + 1] >> 4) << 4) | (data[at + 2] >> 4)] += 1;
      }
      let paper = 0;
      for (let bin = 1; bin < bins.length; bin += 1) if (bins[bin] > bins[paper]) paper = bin;
      const drawnAt = at => data[at + 3] === 255 && Math.max(Math.abs((data[at] >> 4) - (paper >> 8)),
        Math.abs((data[at + 1] >> 4) - ((paper >> 4) & 15)), Math.abs((data[at + 2] >> 4) - (paper & 15))) >= 2;
      // what is drawn under the marks: each mark's box, in the canvas's pixels
      const scaleX = width / Math.max(1, box.width);
      const scaleY = height / Math.max(1, box.height);
      let markPixels = 0;
      let markContent = 0;
      for (const mark of item.querySelectorAll('.pdf-text .pdf-mark, .pdf-text mark')) {
        const area = mark.getBoundingClientRect();
        const x0 = Math.max(0, Math.floor((area.left - box.left) * scaleX));
        const x1 = Math.min(width, Math.ceil((area.right - box.left) * scaleX));
        const y0 = Math.max(0, Math.floor((area.top - box.top) * scaleY));
        const y1 = Math.min(height, Math.ceil((area.bottom - box.top) * scaleY));
        for (let y = y0; y < y1; y += 1) {
          for (let x = x0; x < x1; x += 1) {
            markPixels += 1;
            if (drawnAt((y * width + x) * 4)) markContent += 1;
          }
        }
      }
      const total = Math.max(1, width * height);
      Object.assign(measured, { pixels: total, opaque: opaque / total, markPixels, markContent });
    } catch (error) {
      measured.error = String(error && error.name || error);
    }
  }
  return { number, drawn: true, tokens, marks, canvas: measured };
}

// Runs in the page: a text document's frame - its text (every text node of its body, joined in order, as the page reads
// it to mark it) and every mark (mark[data-quote-mark]) as [start, end] in that text.
function readTextFrame() {
  const viewer = document.querySelector('#documentViewer');
  try {
    const page = viewer.contentDocument;
    const walker = page.createTreeWalker(page.body, 4);
    let source = '';
    const marks = new Map();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const mark = node.parentElement ? node.parentElement.closest('mark[data-quote-mark]') : null;
      if (mark) {
        const at = marks.get(mark) || [source.length, source.length];
        at[1] = source.length + node.nodeValue.length;
        marks.set(mark, at);
      }
      source += node.nodeValue;
    }
    return { source, marks: [...marks.values()] };
  } catch {
    return { source: null, marks: [] };
  }
}

// The pages to read for one quote in a drawn PDF: every page of a short document, else the searched pages (the quote's
// and the next; every page for a quote with no page), the pages the viewer says it marked and the pages it has drawn.
function pagesToRead(quote, reading) {
  const count = Number(reading?.pageCount) || 0;
  const every = Array.from({ length: count }, (_, index) => index + 1);
  if (count <= FULL_READ_PAGES) return every;
  const page = Number.isInteger(quote?.page) && quote.page > 0 ? quote.page : null;
  const wanted = new Set(page ? [page, page + 1] : every);
  for (const number of [...(reading?.pages || []), ...(reading?.drawn || [])]) wanted.add(number);
  return [...wanted].filter(number => number >= 1 && number <= count).sort((a, b) => a - b);
}

// Waits in the page until the viewer has stopped scrolling (a smooth scroll to the quote), at most 3 s.
async function settleViewer(page) {
  await page.evaluate(() => new Promise(resolve => {
    const viewer = document.querySelector('#documentViewer');
    const until = performance.now() + 3000;
    let last = -1;
    let still = 0;
    const step = () => {
      const top = viewer ? viewer.scrollTop : 0;
      still = top === last ? still + 1 : 0;
      last = top;
      if (still >= 3 || performance.now() > until) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  })).catch(() => null);
}

// One page of the PDF viewer read (readPdfPage) once it is drawn: scrolled to when it is not (the viewer draws the pages
// near the visible area only), its text layer waited for, then two frames so the library has filled it and the viewer
// painted its marks.
async function readDrawnPage(page, number) {
  await page.evaluate(wanted => {
    const target = document.querySelector(`#documentViewer .pdf-page[data-page="${wanted}"]`);
    if (target && !target.querySelector('.pdf-text')) target.scrollIntoView({ block: 'center' });
  }, number);
  await page.waitForFunction(wanted => Boolean(document.querySelector(`#documentViewer .pdf-page[data-page="${wanted}"] .pdf-text`)),
    number, { timeout: UI_TIMEOUT_MS }).catch(() => null);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 50)))));
  return page.evaluate(readPdfPage, number);
}

// The browser's own viewer as framed now: its element (a handle, so the walk can tell a new frame from the old one
// without changing the page) and the page its address opens (#page=N).
async function frameState(page) {
  const handle = await page.$('#documentViewer[data-mode="frame"] iframe');
  if (!handle) return null;
  const match = /#page=(\d+)$/.exec((await handle.getAttribute('src')) || '');
  return { handle, page: match ? Number(match[1]) : null };
}

// Chooses every quote in the quotes panel, in order, and reads what the viewer did for each ({quote, key, reading}): in
// a drawn PDF, every page to judge it by (pagesToRead), each scrolled to and read once drawn; in the browser's own viewer,
// the page its frame opens and whether that frame is a new one; in a text document, its text and marks.
async function chooseQuotes(page, enc) {
  const served = servedQuotes(enc);
  const buttons = page.locator('#quotesPanel .quote');
  const total = await buttons.count();
  const chosen = [];
  for (let index = 0; index < total; index += 1) {
    const button = buttons.nth(index);
    const key = await button.getAttribute('data-quote');
    const quote = served[index] || null;
    const before = await frameState(page);
    await button.click();
    const ready = await page.waitForFunction(wanted => {
      const viewer = document.querySelector('#documentViewer');
      return Boolean(viewer) && (viewer.getAttribute('data-marked') === wanted || viewer.getAttribute('data-mode') === 'frame');
    }, key, { timeout: UI_TIMEOUT_MS }).then(() => true).catch(() => false);
    let reading = ready ? await page.evaluate(readViewer) : null;
    if (reading && reading.mode === 'pdf') {
      await settleViewer(page);
      reading = await page.evaluate(readViewer);
      reading.pagesRead = new Map();
      for (const number of pagesToRead(quote, reading)) reading.pagesRead.set(number, await readDrawnPage(page, number));
    } else if (reading && reading.mode === 'frame') {
      const after = await frameState(page);
      const replaced = before && after ? !(await page.evaluate(([a, b]) => a === b, [before.handle, after.handle])) : null;
      reading.frame = { page: after ? after.page : null, previousPage: before ? before.page : null, replaced };
      await after?.handle.dispose();
    } else if (reading && reading.mode === 'text') {
      reading.text = await page.evaluate(readTextFrame);
    }
    await before?.handle.dispose();
    chosen.push({ quote, key, reading });
  }
  return chosen;
}

// Whether ``text`` shows ``token`` as a whole word - not inside a longer run of letters and digits: 45385 in
// "45385", never in "453851"; 2 in "2 units", never in "12 units".
function showsToken(text, token) {
  const escaped = String(token).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|[^A-Za-z0-9])${escaped}(?:$|[^A-Za-z0-9])`).test(String(text ?? ''));
}

// The units cell against the units served, which are a whole number as the coding review wrote it (0 included: it
// writes 0 on a code it does not support; FIX-SPEC-2 section 2, read losslessly) or null: a number is shown as that
// number, null as "not given"; '' when the cell shows them.
function unitsProblem(cell, units) {
  if (units === null) return /\bnot given\b/i.test(cell || '') ? '' : `.code-units ${JSON.stringify(cell)} for units not given`;
  if (Number.isInteger(units) && units >= 0) return showsToken(cell, units) ? '' : `.code-units ${JSON.stringify(cell)} for ${units}`;
  return `units ${JSON.stringify(units)} are neither a whole number nor null`;
}

// The modifiers cell against the modifiers served: each served one shown as a word, and no other modifier-shaped word
// (two capital letters or digits); '' when it shows exactly them.
function modifiersProblem(cell, modifiers) {
  const served = (Array.isArray(modifiers) ? modifiers : []).map(String);
  if (cell === null || cell === undefined) return `no .code-modifiers for ${JSON.stringify(served)}`;
  const extra = String(cell).match(/(?<![A-Za-z0-9])[A-Z0-9]{2}(?![A-Za-z0-9])/g) || [];
  for (const modifier of served) {
    const at = extra.indexOf(modifier);
    if (at >= 0) extra.splice(at, 1);
  }
  const missing = served.filter(modifier => !showsToken(cell, modifier));
  return missing.length || extra.length ? `.code-modifiers ${JSON.stringify(cell)} for ${JSON.stringify(served)}` : '';
}

// One code row as the evidence names it: its code, and its line when the round serves lines.
function rowName(code) {
  return typeof code?.line === 'string' ? `${code.code} (${code.line})` : String(code?.code);
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
  // a round that serves lines (FIX-SPEC section 1) is drawn row by line: two lines of one code are two rows
  const lined = codes.some(code => typeof code?.line === 'string');
  const shape = (line, code, status) => (lined ? [line ?? null, code, status] : [code, status]);
  const drawn = rows.map(row => shape(row.line, row.code, row.status));
  const served = codes.map(code => shape(code.line, code.code, code.status));
  const order = JSON.stringify(drawn) === JSON.stringify(served);
  out.push(check('dom.codes.rows', order, order ? `${rows.length} code row(s), in order, each with its ${lined ? 'line and ' : ''}status`
    : `rows ${JSON.stringify(drawn)}; served ${JSON.stringify(served)}`));
  const cells = [];
  const badges = [];
  const buttons = [];
  codes.forEach((code, index) => {
    const row = rows[index];
    if (!row || row.code !== code.code || (lined && row.line !== code.line)) return;
    const name = rowName(code);
    if (!showsToken(row.number, code.code)) cells.push(`${name}: .code-number ${JSON.stringify(row.number)}`);
    const units = unitsProblem(row.units, code.units);
    if (units) cells.push(`${name}: ${units}`);
    const modifiers = modifiersProblem(row.modifiers, code.modifiers);
    if (modifiers) cells.push(`${name}: ${modifiers}`);
    if (row.reason === null || (collapse(code.reason) && !row.reason.includes(collapse(code.reason)))) cells.push(`${name}: .code-reason`);
    const second = collapse(code.second_check?.reason);
    if (row.check === null || (second && !row.check.includes(second))) cells.push(`${name}: .code-check`);
    if (!row.quotes) cells.push(`${name}: no .code-quotes`);
    const decided = isObject(code.decision) ? DECISION_WORDS[code.decision.action] : null;
    if (!row.badge) {
      badges.push(`${name}: no .status badge`);
    } else if (decided) {
      if (!row.badge.text.includes(decided)) badges.push(`${name}: the badge reads ${JSON.stringify(row.badge.text)}, not ${decided}`);
    } else if (row.badge.status !== code.status || !row.badge.text.includes(collapse(code.status_label))) {
      badges.push(`${name}: the badge is ${JSON.stringify(row.badge)}; served ${code.status} "${code.status_label}"`);
    }
    const shown = row.buttons.map(button => button.decision);
    if (!sameList(shown, code.allowed_actions) || row.buttons.some(button => button.code !== code.code)) {
      buttons.push(`${name}: buttons [${sorted(shown)}], allowed [${sorted(code.allowed_actions)}]`);
    }
  });
  out.push(check('dom.codes.cells', cells.length === 0, cells.length ? cells.slice(0, 10).join('; ')
    : 'each row shows its number, units, modifiers, reason, second check and quotes'));
  out.push(check('dom.codes.badges', badges.length === 0, badges.length ? badges.slice(0, 10).join('; ')
    : 'each badge states the status served, or the decision made'));
  out.push(check('dom.codes.actions', buttons.length === 0, buttons.length ? buttons.slice(0, 10).join('; ')
    : 'each row offers exactly the actions allowed, and no other'));
  const quoted = codes.flatMap(code => (Array.isArray(code.quotes) ? code.quotes : []).map(quote => quoteKey(code.code, quote?.page))).sort();
  const listed = (dom?.quotes || []).map(quote => quoteKey(quote.code, quote.page === '' ? null : quote.page)).sort();
  out.push(check('dom.quotes', (quoted.length === 0 || dom?.quotesPanel) && JSON.stringify(quoted) === JSON.stringify(listed),
    `#quotesPanel lists ${listed.length} quote(s); the codes carry ${quoted.length}`));
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
  out.push(check('dom.viewer', !!dom?.viewer && sameTarget(dom.viewer.view, documentPart.view_url, base)
    && sameTarget(dom.viewer.original, documentPart.original_url, base),
  `#documentViewer views ${JSON.stringify(dom?.viewer?.view ?? null)} and "Download original" ${JSON.stringify(dom?.viewer?.original ?? null)}; served ${documentPart.view_url} and ${documentPart.original_url}`));
  if (enc?.readiness?.draft === true) out.push(check('dom.export', !!dom?.exportButton, 'the export button is offered while a draft can be made'));
  return out;
}

// What the evidence keeps of an encounter: no document text, only the shape the walk judged.
function summarize(enc) {
  return {
    state: enc?.state ?? null, phase: enc?.progress?.phase ?? null, round: enc?.round ?? null,
    codes: (enc?.codes || []).map(code => ({ line: code.line ?? null, code: code.code, units: code.units, modifiers: code.modifiers, status: code.status,
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
// the CSRF field's token is no wording), for the negative scan. The PDF viewer's text layers (.pdf-text) are aside too:
// they hold the document's own text, which the PDF library put there, as the framed viewer's content was never read -
// the original is the customer's own document; the viewer's note and labels around them are read.
function collectDomStrings() {
  const out = [];
  const keep = /^(?:aria-[\w-]+|data-[\w-]+|title|alt|placeholder|value|label|href|src|action|download|content)$/i;
  const ignore = el => Boolean(el && el.closest && el.closest('script, style, template, noscript, #documentViewer .pdf-text'));
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
  remember(ctx, `GET ${where}`, response.headers(), json, body, response.status());
  return { status: response.status(), json };
}

// One customer API answer, scanned: its quotes are the document's (set aside), then its body and headers; an answer
// of the session, list or encounter route (200) is held to customer-contract.json too, its differences gathered.
function remember(ctx, where, headers, json, body, status = 200) {
  if (!ctx.scan) return;
  if (json !== null) {
    addQuotes(ctx.scan, json);
    scanJson(json, ctx.scan, where, ctx.hits.json);
    const schema = status === 200 ? contractFor(where) : null;
    if (schema && ctx.contract) {
      for (const problem of shapeProblems(json, contract()[schema])) ctx.contract.add(`${where.replace(/[0-9a-f-]{36}/g, '<id>')} ${problem}`);
    }
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
  remember(ctx, `${response.request().method()} ${where} (page)`, response.headers(), json, body, response.status());
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

// Approves one served code row through the page: its row's Approve button (the row of its line, when the round serves
// lines), then the review dialog as the page draws it - the acknowledgement checkbox (REVIEW_DIALOG.box) ticked inside
// its label (REVIEW_DIALOG.label, which shows the acknowledgement), the walk's note, Save. {status, shown, kind, body}:
// the decision POST's status, the label's text, the box's input type and the JSON the page posted.
async function approve(page, ctx, enc, code) {
  const selector = value => String(value).replace(/"/g, '\\"');
  const row = typeof code.line === 'string'
    ? `ol#codesList > li.code-row[data-line="${selector(code.line)}"]`
    : `ol#codesList > li.code-row[data-code="${selector(code.code)}"]`;
  await page.locator(`${row} button[data-decision="approve"][data-code="${selector(code.code)}"]`).click();
  await page.locator(`${REVIEW_DIALOG.dialog}[open]`).waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  const box = page.locator(`${REVIEW_DIALOG.dialog} ${REVIEW_DIALOG.box}`);
  const kind = await box.evaluate(el => (el.tagName === 'INPUT' ? el.type : el.tagName.toLowerCase()));
  if (kind !== 'checkbox') throw new Error(`${REVIEW_DIALOG.box} is ${kind}, not the acknowledgement checkbox the page draws`);
  const shown = collapse(await page.locator(`${REVIEW_DIALOG.dialog} ${REVIEW_DIALOG.label}`).textContent());
  await box.check();
  await page.fill(REVIEW_DIALOG.note, WALK_NOTE);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${enc.id}/decisions`, { timeout: 60000 }),
    page.click(REVIEW_DIALOG.save),
  ]);
  let body = null;
  try {
    body = response.request().postDataJSON();
  } catch {
    body = null;
  }
  return { status: response.status(), shown, kind, body };
}

// The served code row ``wanted`` names in ``codes``: by its line when the round serves lines (FIX-SPEC section 1),
// else by its code.
function servedRow(codes, wanted) {
  const list = Array.isArray(codes) ? codes : [];
  return typeof wanted?.line === 'string' ? list.find(code => code?.line === wanted.line) : list.find(code => code?.code === wanted?.code);
}

// What is wrong with the JSON the page posted to approve ``code`` of ``enc`` (FIX-SPEC section 1: the round number
// shown, the line, its code, the action and the session's acknowledgement exactly); [] when nothing is.
function decisionRequestProblems(body, enc, code, acknowledgement) {
  if (!isObject(body)) return ['the page posted no JSON object'];
  const problems = [];
  if (body.action !== 'approve') problems.push(`action ${JSON.stringify(body.action)}, not "approve"`);
  if (body.code !== code?.code) problems.push(`code ${JSON.stringify(body.code)}, not ${JSON.stringify(code?.code)}`);
  if (typeof code?.line !== 'string') problems.push(`the served row of ${code?.code} names no line`);
  else if (body.line !== code.line) problems.push(`line ${JSON.stringify(body.line)}, not ${JSON.stringify(code.line)}`);
  if (!Number.isInteger(enc?.round?.number) || body.round !== enc.round.number) {
    problems.push(`round ${JSON.stringify(body.round)}, not the round shown (${JSON.stringify(enc?.round?.number ?? null)})`);
  }
  if (body.acknowledgement !== acknowledgement) problems.push('the acknowledgement is not the session\'s, exactly');
  return problems;
}

// What is wrong after one approval of ``code`` (``before`` and ``after``: the encounter read before and after it): that
// row decided approve and offering only the undo, on the same round, the approved export offered - and no other row's
// decision changed (two lines of one code are two decisions); [] when nothing is.
function approvalProblems(before, after, code) {
  const problems = [];
  const decided = servedRow(after?.codes, code);
  if (decided?.decision?.action !== 'approve') problems.push(`${rowName(code)}: decision ${JSON.stringify(decided?.decision?.action ?? null)}`);
  if (!sameList(decided?.allowed_actions, ['revoke'])) problems.push(`${rowName(code)}: actions [${sorted(decided?.allowed_actions)}]`);
  if (after?.round?.number !== before?.round?.number) problems.push(`round ${after?.round?.number} after round ${before?.round?.number}`);
  if (after?.readiness?.approved !== true) problems.push('the approved export is not offered');
  const lined = typeof code?.line === 'string';
  (Array.isArray(before?.codes) ? before.codes : []).forEach((other, index) => {
    if (lined ? other?.line === code.line : other?.code === code?.code) return;
    const now = lined ? servedRow(after?.codes, other) : (after?.codes || [])[index];
    if ((now?.decision?.action ?? null) !== (other?.decision?.action ?? null)) {
      problems.push(`${rowName(other)}: decision ${JSON.stringify(other?.decision?.action ?? null)} became ${JSON.stringify(now?.decision?.action ?? null)}`);
    }
  });
  return problems;
}

// Undoes one decided served row through the page: its row's Undo button (button[data-decision="revoke"] in the row of its
// line), which posts at once. {status, body}: the decision POST's status and the JSON the page posted.
async function undo(page, ctx, enc, code) {
  const selector = value => String(value).replace(/"/g, '\\"');
  const row = `ol#codesList > li.code-row[data-line="${selector(code.line)}"]`;
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${enc.id}/decisions`, { timeout: 60000 }),
    page.locator(`${row} button[data-decision="revoke"][data-code="${selector(code.code)}"]`).click(),
  ]);
  let body = null;
  try {
    body = response.request().postDataJSON();
  } catch {
    body = null;
  }
  return { status: response.status(), body };
}

// What is wrong with the JSON the page posted to undo the decision on ``code`` of ``enc`` (FIX-SPEC-2 section 5: the round
// number shown, the line, its code, the action, and the id of the decision the page showed on that line - so the server
// can refuse to undo one the member never saw); [] when nothing is.
function undoRequestProblems(body, enc, code) {
  if (!isObject(body)) return ['the page posted no JSON object'];
  const problems = [];
  if (body.action !== 'revoke') problems.push(`action ${JSON.stringify(body.action)}, not "revoke"`);
  if (body.code !== code?.code) problems.push(`code ${JSON.stringify(body.code)}, not ${JSON.stringify(code?.code)}`);
  if (typeof code?.line !== 'string') problems.push(`the served row of ${code?.code} names no line`);
  else if (body.line !== code.line) problems.push(`line ${JSON.stringify(body.line)}, not ${JSON.stringify(code.line)}`);
  if (!Number.isInteger(enc?.round?.number) || body.round !== enc.round.number) {
    problems.push(`round ${JSON.stringify(body.round)}, not the round shown (${JSON.stringify(enc?.round?.number ?? null)})`);
  }
  const shown = isObject(code?.decision) ? code.decision.id : undefined;
  if (typeof shown !== 'string' || !shown) problems.push(`the served decision of ${rowName(code)} names no id`);
  else if (body.decision !== shown) problems.push(`decision ${JSON.stringify(body.decision)}, not the one shown (${JSON.stringify(shown)})`);
  return problems;
}

// What is wrong after one Undo of the decision on ``code`` (``before`` and ``after``: the encounter read before and after
// it): that row no longer decided and offering what its status allows, on the same round - and no other row's decision
// changed; [] when nothing is.
function undoProblems(before, after, code) {
  const problems = [];
  const undone = servedRow(after?.codes, code);
  if (!undone) {
    problems.push(`${rowName(code)}: not served after the undo`);
  } else {
    if (isObject(undone.decision)) problems.push(`${rowName(code)}: decision ${JSON.stringify(undone.decision.action ?? null)} still stands`);
    if (!sameList(undone.allowed_actions, expectedActions(undone))) {
      problems.push(`${rowName(code)}: actions [${sorted(undone.allowed_actions)}], not [${expectedActions(undone)}]`);
    }
  }
  if (after?.round?.number !== before?.round?.number) problems.push(`round ${after?.round?.number} after round ${before?.round?.number}`);
  (Array.isArray(before?.codes) ? before.codes : []).forEach(other => {
    if (other?.line === code?.line) return;
    const now = servedRow(after?.codes, other);
    if ((now?.decision?.action ?? null) !== (other?.decision?.action ?? null)) {
      problems.push(`${rowName(other)}: decision ${JSON.stringify(other?.decision?.action ?? null)} became ${JSON.stringify(now?.decision?.action ?? null)}`);
    }
  });
  return problems;
}

// What is wrong with the JSON the page posted for a download of ``kind`` (FIX-SPEC-2 section 5: {kind, fmt, round}, the
// round the page shows - so the server can refuse one made from a coding review the member never saw); [] when nothing is.
function exportRequestProblems(body, enc, kind, fmt = 'txt') {
  if (!isObject(body)) return ['the page posted no JSON object'];
  const problems = [];
  if (body.kind !== kind) problems.push(`kind ${JSON.stringify(body.kind)}, not ${JSON.stringify(kind)}`);
  if (body.fmt !== fmt) problems.push(`fmt ${JSON.stringify(body.fmt)}, not ${JSON.stringify(fmt)}`);
  if (!Number.isInteger(enc?.round?.number) || body.round !== enc.round.number) {
    problems.push(`round ${JSON.stringify(body.round)}, not the round shown (${JSON.stringify(enc?.round?.number ?? null)})`);
  }
  return problems;
}

// The History entries of ``enc`` that name the decided line ``code`` as the activity names a decision (FIX-SPEC-2 section
// 5): its line with its code ("L2 45380"), as a whole phrase.
function activityNaming(enc, code) {
  const named = `${code?.line} ${code?.code}`;
  return (Array.isArray(enc?.activity) ? enc.activity : [])
    .filter(item => typeof item?.text === 'string' && showsToken(item.text, named)).map(item => item.text);
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
  let body = null;
  try {
    body = response.request().postDataJSON();
  } catch {
    body = null;
  }
  const file = path.join(outDir, `${safeName(enc.id)}-${kind}.txt`);
  await download.saveAs(file);
  const bytes = fs.readFileSync(file);
  await page.keyboard.press('Escape');
  const result = { kind, fmt: 'txt', status: response.status(), filename: report?.filename ?? null, body,
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
  const asked = exportRequestProblems(item.body, enc, label);
  const out = [
    check(`export.${label}`, item.status === 201 && item.size > 0 && /\.txt$/i.test(item.filename || item.suggested || ''),
      `POST answered ${item.status}; ${item.size} bytes saved as ${item.suggested}`),
    check(`export.${label}.request`, asked.length === 0, asked.length ? `the page posted ${asked.join('; ')}`
      : `the page posted ${label}, txt, round ${enc?.round?.number}`),
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
  ctx.contract = new Set();
  let enc = null;
  let approvedRow = null;  // the row the approve step decided: the undo step undoes it
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
      // every quote chosen through the page: its words marked on its page (or, from it, onto the next), or the note says
      // they could not be found; nothing marked on another page (quoteMarkChecks)
      const view = (enc.document || {}).view_media_type;
      if (view !== 'application/pdf' && view !== 'text/plain') {
        add(skip('quotes.marks', 'the document has no view'));
        return;
      }
      if (!servedQuotes(enc).length) {
        add(skip('quotes.marks', 'no passage is quoted'));
        return;
      }
      await viewFor(page, ctx, enc);
      const chosen = await chooseQuotes(page, enc);
      const made = quoteMarkChecks(chosen);
      record.quote_marks = made.data;
      add(made);
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
        `${REVIEW_DIALOG.label} (the label of the ${made.kind} ${REVIEW_DIALOG.box}) shows the session's acknowledgement`));
      const asked = decisionRequestProblems(made.body, enc, ready, ctx.session.acknowledgement);
      add(check('approve.request', asked.length === 0, asked.length ? `the page posted ${asked.join('; ')}`
        : `the page posted round ${enc.round?.number}, line ${ready.line}, ${ready.code}, approve, with the acknowledgement`));
      add(check('approve.saved', made.status === 201, `POST decisions answered ${made.status}`));
      const before = enc;
      const after = await getJson(page, ctx, `/api/encounters/${encodeURIComponent(enc.id)}`);
      enc = isObject(after.json) ? after.json : enc;
      const decided = servedRow(enc.codes, ready);
      record.approved = decided?.decision?.action === 'approve' ? rowName(ready) : null;
      approvedRow = record.approved ? ready : null;
      const wrong = approvalProblems(before, enc, ready);
      add(check('approve.recorded', wrong.length === 0, wrong.length ? wrong.join('; ')
        : `${rowName(ready)} approved on round ${enc.round?.number}, only the undo offered, the approved export offered, no other row changed`));
      const named = activityNaming(enc, ready);
      add(check('approve.activity', named.length > 0, named.length ? `the History names ${ready.line} ${ready.code}: ${JSON.stringify(named[named.length - 1])}`
        : `no History entry names ${ready.line} ${ready.code} (the line with its code)`));
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
    await step('undo', async () => {
      const decided = approvedRow ? servedRow(enc.codes, approvedRow) : null;
      if (!decided || !isObject(decided.decision)) {
        add(skip('undo', 'no approval was made to undo'));
        return;
      }
      await viewFor(page, ctx, enc);
      const made = await undo(page, ctx, enc, decided);
      const asked = undoRequestProblems(made.body, enc, decided);
      add(check('undo.request', asked.length === 0, asked.length ? `the page posted ${asked.join('; ')}`
        : `the page posted round ${enc.round?.number}, line ${decided.line}, ${decided.code}, revoke, naming the decision shown`));
      add(check('undo.saved', made.status === 201, `POST decisions answered ${made.status}`));
      const before = enc;
      const after = await getJson(page, ctx, `/api/encounters/${encodeURIComponent(enc.id)}`);
      enc = isObject(after.json) ? after.json : enc;
      const wrong = undoProblems(before, enc, decided);
      add(check('undo.recorded', wrong.length === 0, wrong.length ? wrong.join('; ')
        : `${rowName(decided)}'s approval undone on round ${enc.round?.number}, the line open again, no other row changed`));
    });
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
  const unlisted = [...ctx.contract];
  add(check('contract.reads', unlisted.length === 0, unlisted.length
    ? `${unlisted.length} difference(s) from customer-contract.json in what the page and the walk read: ${describeProblems(unlisted)}`
    : 'every session, list and encounter answer read was held to customer-contract.json'));
  ctx.scan = null;
  ctx.contract = null;
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
    contract();
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
      denylist: denylist().schema, contract: contract().schema },
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
    const sessionShape = shapeProblems(ctx.session, contract().session);
    evidence.run_checks.push(check('contract.session', sessionShape.length === 0, sessionShape.length
      ? `${sessionShape.length} difference(s) from customer-contract.json: ${describeProblems(sessionShape)}`
      : 'GET /api/session carries every key customer-contract.json lists and nothing else'));
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
  EVIDENCE_SCHEMA, CLIENT_HEADERS, PLAYWRIGHT, REVIEW_DIALOG, UsageError, parseArgs, serviceDateOf, documentsOf,
  readPrivate, loadCredentials, debugMayLog, secretForms, scrubSecret, compileDenylist, denylist, contract, shapeProblems,
  contractFor, scanContext, addQuotes, ownWording, NEVER_QUOTED, scanText, scanJson, scanFile, scanHeaders, checkScan,
  expectedActions,
  jsonChecks, showsToken, unitsProblem, modifiersProblem, domChecks, readEncounterDom, collectDomStrings, approve,
  servedQuotes, foldMarked, FALLBACK_WHY, FRAME_REASONS, OVERPRINT_WINDOW, OVERPRINT_MIN_PX, OVERPRINT_SHARE,
  CANVAS_OPAQUE_MIN, CANVAS_MARK_CONTENT_MIN, FULL_READ_PAGES, cutCharacters, pageModel, foldQuote, ownSearch, pdfQuoteNote,
  unbornFlags, viewerMarks, canvasProblem, findPassagesText, textNote, judgeQuote, quoteMarkChecks, readViewer,
  readPdfPage, readTextFrame, pagesToRead, chooseQuotes,
  servedRow, decisionRequestProblems, approvalProblems, undo, undoRequestProblems, undoProblems, exportTxt,
  exportRequestProblems, activityNaming, opsChecks, exportChecks, summarize, documentResult,
  evidenceProblems, writeEvidence, sessionProblems, stopRequested, main,
};

if (require.main === module) {
  main(process.argv.slice(2)).then(code => { process.exitCode = code; }, error => {
    process.stderr.write(`walk: ${error && error.stack || error}\n`);
    process.exitCode = 1;
  });
}
