#!/usr/bin/env node
'use strict';
/*
 * Browser verification of a running CPT Studio (the deployed site or a local one)
 * with the synthetic documents from ops/verification.
 *
 *   node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials agent.json \
 *     --docs OUT_FROM_GENERATE --manifest ops/verification/manifest.json --out EVIDENCE_DIR \
 *     [--only gi-01,gi-03] [--deadline-seconds 300] [--stop-on-failure] [--allow-live-provider]
 *     [--encounter ENCOUNTER_ID] [--no-auto-approve]
 *
 * --encounter attaches to an EXISTING encounter instead of uploading (with exactly one --only id): nothing is uploaded,
 * and nothing is done to it until it is shown to be that manifest document's - an uploaded document by its stored
 * original, byte for byte, and its text; a pasted one by a pasted revision with no stored original whose text has the
 * document's lines (only trailing whitespace and line-ending style may differ).
 *
 * --no-auto-approve: nothing is approved except the codes a document's review_plan.approve_codes names (a labelled
 * synthetic review that mirrors a human reading). An approve_codes list is honoured without the option too; the option
 * only removes the default of approving every ready selected code. Designated rejections and must_not_code
 * confirmations are made as before. With or without it, a code of a family the document's must_not_code lists is never
 * approved, and every decision made is checked to carry the agent label and its labelled note.
 *
 * A manifest upload.service_date is entered in the upload dialog as the member's date, and checked to be stored. A
 * review_plan.context_edit, {"service_date": "YYYY-MM-DD"} or {"clear_member_date": true} (optionally with
 * "documented_date": "YYYY-MM-DD"), settles the member date conflict that date makes, through the screen's own context
 * form, once processing is done: nothing may have been sent while the conflict held (a not-sent hold run records it);
 * the save sends exactly one request, for the edited date - for a cleared date, the date named BEFORE the edit: the
 * document's own read date that the member conflict's note names and its evidence quotes from the revision text (none,
 * where the document gives no date of its own a request carries), which documented_date, when given, must be; no edit
 * is made when that date cannot be named - proven by its request hash; the hold run stays as it was; and the same save
 * made again - the form refuses it, so it is sent as a stale page or a repeated request sends it, through the page's own
 * api() client - sends nothing. The coding checks are then judged on the encounter after the edit.
 *
 * The documented date question: a document with NO upload.service_date whose review_plan.context_edit is
 * {"service_date": "YYYY-MM-DD"} answers the encounter's open date question (its own dates conflict, or it states none
 * the reader reads, so the primary request went without a "Date of service" line), through the same form. The edit is
 * made only once the walk has seen, before it: an open encounter-scope service_date question; no service date
 * established (none a request carries, no member date, no member conflict); and every primary run carrying a request
 * made for the revision text with no date, at least one of them answered (sent, or a retained answer reused) - proven
 * by its request hash. Otherwise nothing is saved and the run says why. After the save: the context states the
 * answered date as the member's; exactly one new run, a primary run for the revision text and that date (proven by its
 * request hash), sent or reusing a retained identical answer; every earlier run unchanged; no service_date question
 * open; and the same save made again sends nothing, as above. clear_member_date needs a member date entered at upload.
 *
 * A document whose manifest review_plan carries "second_review": {"ask": true, "approve_codes": [...]} has the bounded
 * second review asked for once, through the screen's own button, when the encounter offers it (ARCHITECTURE 5.11):
 * its request is recorded, processing is awaited (read-only polling; never a Stop, never a second ask), and the
 * encounter before and after is compared: one new run, purpose second_review, about the offered items; at most that one
 * request sent; every earlier run unchanged; a code it added only for an offered service; no alternative promoted.
 * A code the second review added is approved only when approve_codes names it; any other is left undecided.
 *
 * --credentials names a JSON file {"username": ..., "password": ...} for an AGENT account
 * (actor_kind "agent"), so every decision is recorded and labelled as agent review. The
 * password is never printed or written. TLS is verified normally.
 *
 * Per document, through the ordinary UI: New document -> upload the file (or paste the
 * text) -> tick the synthetic attestation -> submit; wait for processing by polling
 * GET /api/encounters/<id> with the page's own session, within the deadline; check
 * extraction, context, routing, exact evidence, clarifications, must-not-code services and
 * incomplete services against the manifest (mismatches are recorded, never fail-fast);
 * check the evidence marks in the DOM; approve every ready selected proposal except the
 * manifest's designated rejection; reload and check that the decisions and the revision
 * persisted (JSON and DOM); download the draft TXT + CSV, and the reviewed TXT + CSV when
 * ready, as real browser downloads, hashing each file against the API's sha256; take
 * desktop (1440x1000) and mobile (390x844) screenshots of the review screen.
 *
 * Nothing is retried: a failure is recorded and the run continues with the next document
 * (or stops with --stop-on-failure). A file named STOP in EVIDENCE_DIR stops the run before
 * the next upload (the batch's Stop path; a document already uploaded finishes as the
 * application processes it, and its own Stop is the encounter's Stop button). Everything is written to EVIDENCE_DIR/evidence.json,
 * which ops/verify_downloads.py then re-checks file by file. Exit 0 when every document
 * passed, 1 when anything failed, 2 on a usage error before any upload.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const PLAYWRIGHT = process.env.CPT_VERIFY_PLAYWRIGHT
  || '/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/browser-deps/node_modules/playwright';
const EVIDENCE_SCHEMA = 'cpt-studio-browser-evidence@1';
const DONE_STATES = new Set(['ready_for_review', 'needs_clarification', 'no_codes', 'reviewed']);
const PERFORMED = new Set(['performed', 'incomplete']);
const DECIDED = new Set(['approved', 'rejected']);
const DECISION_STATES = { approve: 'approved', reject: 'rejected', confirm: 'exclusion_confirmed' };
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } };
const UI_TIMEOUT_MS = 30000;
const POLL_MS = 2000;
const MAX_POLL_ERRORS = 3;
const INCOMPLETE_SIGNAL = /incomplete|discontinu|reduced|\b5[23]\b/i;
const AGENT_LABEL = 'agent-executed synthetic review';
// Every note the walk writes on a decision says what made it (review_notes are checked before anything is uploaded).
const NOTE_LABEL = /agent-executed synthetic/i;
const USAGE = 'usage: verify_browser.cjs --base-url URL --credentials FILE --docs DIR --manifest FILE --out DIR '
  + '[--only IDS] [--deadline-seconds N] [--stop-on-failure] [--allow-live-provider] [--encounter ID] [--no-auto-approve]';
const ENCOUNTER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const ISO_DATE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
// studio/jobs.py MEMBER_DATE_CONFLICT_MESSAGE: the error of the not-sent run jobs._member_date_hold records for a member
// date conflict (scope {'held': 'member_date_conflict'}). The API serves no scope, but only that function writes this
// message, so it names the hold; the unit tests hold the two equal.
const MEMBER_DATE_HOLD_MESSAGE = 'Nothing was sent: the service date entered as encounter metadata differs from the '
  + 'documented one. Correct or clear the metadata (or add an addendum), and the request is made for the agreed date.';
// studio/providers/corti.py build_coding_request (adapter corti-coding-v2@cptstudio-1) over studio/providers/base.py
// canonical_body: a primary run's request_sha256 is the hash of this body for the revision text and its date. Recomputed
// here it proves which date a request carried; the unit tests hold the shape to the source.
const PROVIDER_SYSTEMS = ['icd10cm-outpatient', 'cpt'];
const CONTEXT_EDIT_KEYS = new Set(['service_date', 'clear_member_date', 'documented_date']);
const IDENTICAL_REFUSAL = 'No context change to save.';  // app.js submitContext, for a save that changes nothing
// studio/gi/context.py USER_CONFLICT_NOTE and USER_ELSEWHERE_NOTE: the notes merge_user_values writes on a member's date
// held against the document's. {document} is the document's own read date - an ISO date - only where the document gives
// one date of its own (documented.value); a document-internal conflict lists its dates joined by " or ", and a labelled
// date the reader cannot use, or reads as another occurrence's, is quoted. The unit tests hold both to the source.
const USER_CONFLICT_NOTE = 'Encounter metadata entered by a workspace member gives {user}; the document gives {document}. '
  + 'Both are kept and neither is used until they agree: correct the metadata, clear it, or add an addendum to the document.';
const USER_ELSEWHERE_NOTE = 'Encounter metadata entered by a workspace member gives {user}; this service reads that date in '
  + 'the document as another occurrence\'s or another document\'s date, or as possibly one ({document}), and not as this '
  + 'encounter\'s date of service. Both are kept and neither is used: correct the metadata, clear it, or add an addendum to '
  + 'the document.';
// studio/gi/context.py FULL_DATE (cues.rx: ASCII \w, case-insensitive): the four forms a documented date of service is
// read in - ISO, M/D/YYYY, "Month D, YYYY" and "D Month YYYY" - a closed grammar, mirrored so the walk reads the date a
// quoted passage states itself; the unit tests hold it to the source.
const MONTH_NAME = '(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?'
  + '|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)';
const FULL_DATE = new RegExp('(?<![\\w/-])(?:(\\d{4})-(\\d{2})-(\\d{2})|(\\d{1,2})/(\\d{1,2})/(\\d{4})'
  + `|(${MONTH_NAME})\\.?[ \\t]+(\\d{1,2})(?:st|nd|rd|th)?,?[ \\t]+(\\d{4})`
  + `|(\\d{1,2})(?:st|nd|rd|th)?(?:[ \\t]+|-)(${MONTH_NAME})\\.?(?:,?[ \\t]+|-)(\\d{4}))(?![\\w/-])`, 'gi');
const MONTH_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

// --- small pure helpers ----------------------------------------------------------------

class UsageError extends Error {}

function parseArgs(argv) {
  const flags = new Set(['stop-on-failure', 'allow-live-provider', 'no-auto-approve']);
  const values = new Set(['base-url', 'credentials', 'docs', 'manifest', 'out', 'only', 'deadline-seconds', 'encounter']);
  const opts = { only: null, deadlineSeconds: 300, stopOnFailure: false, allowLiveProvider: false, noAutoApprove: false };
  for (let i = 0; i < argv.length; i += 1) {
    const [name, inline] = argv[i].replace(/^--/, '').split(/=(.*)/s);
    if (!argv[i].startsWith('--')) throw new UsageError(`unexpected argument ${argv[i]}`);
    if (flags.has(name)) {
      // a value was ignored, so '--no-auto-approve=false' (or '--allow-live-provider=no') switched the option ON
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
  for (const name of ['baseUrl', 'credentials', 'docs', 'manifest', 'out']) {
    if (!opts[name]) throw new UsageError(`missing --${name.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`)}`);
  }
  let url;
  try {
    url = new URL(opts.baseUrl);
  } catch {
    throw new UsageError(`--base-url is not a URL: ${opts.baseUrl}`);
  }
  if (!['https:', 'http:'].includes(url.protocol)) throw new UsageError('--base-url must be http(s)');
  opts.baseUrl = url.origin;
  opts.deadlineSeconds = Number(opts.deadlineSeconds);
  if (!Number.isInteger(opts.deadlineSeconds) || opts.deadlineSeconds < 10) {
    throw new UsageError('--deadline-seconds must be an integer of at least 10');
  }
  opts.only = opts.only ? opts.only.split(',').map(s => s.trim()).filter(Boolean) : null;
  if (opts.encounter !== undefined) {
    if (!ENCOUNTER_ID.test(opts.encounter)) throw new UsageError('--encounter must be an encounter id (a lowercase UUID)');
    if (!opts.only || opts.only.length !== 1) throw new UsageError('--encounter needs --only naming exactly one document');
  }
  return opts;
}

function camel(name) {
  return name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

// API offsets are Python code points; JavaScript strings index UTF-16 units.
function cpSlice(points, start, end) {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || start >= end || end > points.length) return null;
  return points.slice(start, end).join('');
}

function stripSpace(text) {
  return String(text).replace(/\s+/g, '');
}

function collapse(text) {
  return String(text).replace(/\s+/g, ' ').trim();
}

// A text as its lines read: only line-ending style (studio/ingest/text.py canonicalize turns CRLF and CR into LF) and
// trailing whitespace (as the walk's exact source check) are not differences. Line breaks and spacing are kept: the
// reader reads sections, labels and fields by them.
function lineText(text) {
  return String(text ?? '').replace(/\r\n?/g, '\n').replace(/\s+$/, '');
}

// A pasted revision: text a member pasted, with no stored original.
function isPastedRevision(rev) {
  return rev?.kind === 'paste' && !rev.source_file;
}

function safeName(name) {
  const base = path.basename(String(name || 'download')).replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^\.+/, '');
  return base.slice(0, 120) || 'download';
}

function pathnameOf(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return '';
  }
}

function isoNow() {
  return new Date().toISOString();
}

// A calendar date in the one form the API takes (api._parse_date: YYYY-MM-DD, a real day of a year from 1).
function isoDate(value) {
  if (typeof value !== 'string' || !ISO_DATE.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  return year >= 1 && date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

// studio/providers/base.py canonical_body: json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False), UTF-8.
function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

// The request_sha256 of the primary request for this text and date (or none): build_coding_request's body.
function primaryRequestSha256(text, serviceDate) {
  const contexts = serviceDate ? [text, `Date of service: ${serviceDate}`] : [text];
  const body = { system: PROVIDER_SYSTEMS, context: contexts.map(item => ({ type: 'text', text: item })) };
  return sha256(Buffer.from(canonicalJson(body), 'utf8'));
}

// --- assertions --------------------------------------------------------------------------

function check(id, severity, ok, reason, data) {
  const status = ok ? 'pass' : severity === 'hard' ? 'fail' : 'warn';
  return data === undefined ? { id, severity, status, reason } : { id, severity, status, reason, data };
}

function skip(id, reason) {
  return { id, severity: 'info', status: 'skipped', reason };
}

function proposalsOf(enc) {
  return enc?.assessment?.proposals || [];
}

function isExcluded(p) {
  return p.bucket === 'excluded' || p.status === 'excluded';
}

function exactSpans(p, points) {
  return (p.evidence || []).map((span, index) => ({ span, index }))
    .filter(({ span }) => (span.context_index ?? 0) === 0 && cpSlice(points, span.start, span.end) === span.text);
}

// The UI marks a span only when it is exact and not flagged exact:false.
function markableSpans(p, points) {
  return exactSpans(p, points).filter(({ span }) => span.exact !== false);
}

// The source passages CPT Studio selected for a proposal (support.source), exact at their offsets: app.js marks each as
// '<id>:s<n>' (documentLayout), whether its support was checked or not (refutation p2, reports2:4: the walk failed
// hard on them as "unknown or inexact spans").
function markableSourceSpans(p, points) {
  return (p.support?.source || []).map((span, index) => ({ span, index }))
    .filter(({ span }) => span && (span.context_index ?? 0) === 0 && span.exact !== false
      && cpSlice(points, span.start, span.end) === span.text);
}

function settle(promise) {
  promise.catch(() => {});
  return promise;
}

function checkPipeline(enc) {
  const stages = (enc.pipeline?.stages || []).map(s => `${s.kind}:${s.state}${s.error ? ` (${s.error})` : ''}`);
  return [check('pipeline.outcome', 'hard', DONE_STATES.has(enc.state) && !enc.pipeline?.busy,
    `state ${enc.state}${stages.length ? `; stages ${stages.join(', ')}` : ''}`)];
}

function checkExtraction(expected, enc, delivery, sourceText) {
  const rev = enc.revision || {};
  const ex = rev.extraction || {};
  const out = [];
  if (expected.status_in) out.push(check('extraction.status', 'hard', expected.status_in.includes(ex.status), `${ex.status} (expected ${expected.status_in.join('|')})`));
  if (expected.method_in) out.push(check('extraction.method', 'hard', expected.method_in.includes(ex.method), `${ex.method} (expected ${expected.method_in.join('|')})`));
  if (expected.ocr_pages_nonempty) out.push(check('extraction.ocr', 'hard', Array.isArray(ex.ocr_pages) && ex.ocr_pages.length > 0, `ocr_pages ${JSON.stringify(ex.ocr_pages)}`));
  if ((ex.messages || []).length) out.push(check('extraction.messages', 'soft', false, ex.messages.join(' | ')));
  const text = typeof rev.text === 'string' ? rev.text : '';
  out.push(check('revision.text_sha256', 'hard', sha256(Buffer.from(text, 'utf8')) === rev.text_sha256,
    `sha256 of revision.text vs text_sha256 ${rev.text_sha256}`));
  if (expected.text_matches_source === 'exact') {
    out.push(check('revision.text_equals_source', 'hard', text.replace(/\s+$/, '') === sourceText.replace(/\s+$/, ''),
      'canonical text equals the source (trailing whitespace ignored)'));
  } else if (expected.text_matches_source === 'whitespace') {
    out.push(check('revision.text_equals_source', 'soft', collapse(text) === collapse(sourceText),
      'canonical text equals the source once whitespace is collapsed'));
  }
  if (delivery.format === 'paste') {
    out.push(check('revision.source', 'hard', isPastedRevision(rev), `kind ${rev.kind}, source_file ${JSON.stringify(rev.source_file)}`));
  } else {
    const file = rev.source_file || {};
    out.push(check('revision.source', 'hard', file.sha256 === delivery.sha256 && file.size === delivery.size,
      `stored original ${file.sha256} (${file.size} bytes) vs uploaded ${delivery.sha256} (${delivery.size} bytes)`));
  }
  return out;
}

function checkContext(expected, enc) {
  const facts = enc.context?.facts || {};
  return Object.entries(expected || {}).flatMap(([name, want]) => {
    const fact = facts[name];
    if (!fact) return [check(`context.${name}`, 'hard', false, 'fact not reported')];
    const origin = !want.origin_in || want.origin_in.includes(fact.origin);
    const value = !want.value_in || want.value_in.map(v => v.toLowerCase()).includes(String(fact.value ?? '').toLowerCase());
    return [check(`context.${name}`, 'hard', origin && value,
      `value ${JSON.stringify(fact.value)} origin ${fact.origin} (expected origin ${want.origin_in?.join('|') ?? 'any'}${want.value_in ? `, value ${want.value_in.join('|')}` : ''})`)];
  });
}

function familyFact(family, name) {
  return (family.facts || []).find(f => f.name === name && f.origin === 'document' && f.value !== null && f.value !== undefined && String(f.value).trim() !== '');
}

function containsAny(value, needles) {
  const text = String(value ?? '').toLowerCase();
  return needles.some(n => text.includes(n.toLowerCase()));
}

function checkRouting(expected, enc) {
  const routing = enc.routing;
  if (!routing) return [check('routing.present', 'hard', false, 'no routing in the encounter JSON')];
  const families = routing.families || [];
  const out = [];
  for (const [slug, want] of Object.entries(expected.families || {})) {
    const family = families.find(f => f.family === slug);
    const id = `routing.${slug}`;
    if (!family) {
      out.push(want.presence === 'required' ? check(`${id}.present`, 'hard', false, 'family not reported') : skip(`${id}.present`, 'optional family not reported'));
      continue;
    }
    out.push(check(`${id}.status`, 'hard', (want.status_in || []).includes(family.status), `${family.status} (expected ${(want.status_in || []).join('|')})`));
    for (const [name, rule] of Object.entries(want.facts || {})) {
      const fact = familyFact(family, name);
      const ok = Boolean(fact) && (!rule.value_contains_any || containsAny(fact.value, rule.value_contains_any));
      out.push(check(`${id}.fact.${name}`, 'hard', ok, fact ? `value ${JSON.stringify(fact.value)}${rule.value_contains_any ? ` (expected one of ${rule.value_contains_any.join('|')})` : ''}` : 'no documented fact'));
    }
    const missing = family.missing || [];
    for (const name of want.missing_includes || []) out.push(check(`${id}.missing.${name}`, 'hard', missing.includes(name), `missing ${JSON.stringify(missing)}`));
    for (const name of want.missing_excludes || []) out.push(check(`${id}.not_missing.${name}`, 'hard', !missing.includes(name), `missing ${JSON.stringify(missing)}`));
    const info = want.informational || {};
    for (const [name, rule] of Object.entries(info.facts || {})) {
      const fact = familyFact(family, name);
      out.push(check(`${id}.info.fact.${name}`, 'soft', Boolean(fact) && containsAny(fact.value, rule.value_contains_any || ['']), fact ? `value ${JSON.stringify(fact.value)}` : 'no documented fact'));
    }
    if (info.mention_statuses_include) {
      const seen = new Set((family.mentions || []).map(m => m.status));
      out.push(check(`${id}.info.mentions`, 'soft', info.mention_statuses_include.every(s => seen.has(s)), `mention statuses ${JSON.stringify([...seen])}`));
    }
  }
  for (const slug of expected.not_performed || []) {
    const family = families.find(f => f.family === slug);
    if (!family) continue;
    const statuses = [family.status, ...(family.mentions || []).map(m => m.status)];
    out.push(check(`routing.${slug}.not_performed`, 'hard', !statuses.some(s => PERFORMED.has(s)), `aggregate ${family.status}; mentions ${JSON.stringify(statuses.slice(1))}`));
  }
  return out;
}

function checkEvidenceExact(enc) {
  const points = Array.from(enc.revision?.text || '');
  const wrong = [];
  const flagged = [];
  const withoutExact = [];
  for (const p of proposalsOf(enc)) {
    for (const span of p.evidence || []) {
      if ((span.context_index ?? 0) !== 0) continue;
      const actual = cpSlice(points, span.start, span.end) === span.text;
      if (span.exact !== false && !actual) wrong.push(`${p.code}[${span.start}:${span.end}]`);
      if (span.exact === false && actual) flagged.push(`${p.code}[${span.start}:${span.end}]`);
    }
    if (p.bucket === 'selected' && !isExcluded(p) && exactSpans(p, points).length === 0) withoutExact.push(p.code);
  }
  const spans = [];
  for (const [name, fact] of Object.entries(enc.context?.facts || {})) for (const s of fact.evidence || []) spans.push([`context.${name}`, s]);
  for (const family of enc.routing?.families || []) {
    for (const m of family.mentions || []) if (m.span && m.span.end > m.span.start) spans.push([`mention.${family.family}`, m.span]);
    for (const f of family.facts || []) for (const s of f.evidence || []) spans.push([`fact.${family.family}.${f.name}`, s]);
  }
  const wrongOther = spans.filter(([, s]) => cpSlice(points, s.start, s.end) !== s.text).map(([where, s]) => `${where}[${s.start}:${s.end}]`);
  return [
    check('evidence.exact', 'hard', wrong.length === 0, wrong.length ? `spans claimed exact but not equal to revision.text: ${wrong.join(', ')}` : 'every proposal span claimed exact equals revision.text'),
    check('evidence.selected_have_exact', 'hard', withoutExact.length === 0, withoutExact.length ? `selected, non-excluded proposals without an exact span: ${withoutExact.join(', ')}` : 'yes'),
    check('evidence.context_and_routing_exact', 'hard', wrongOther.length === 0, wrongOther.length ? `not exact: ${wrongOther.join(', ')}` : `${spans.length} span(s) exact`),
    check('evidence.exact_flag', 'soft', flagged.length === 0, flagged.length ? `spans marked not exact that do match: ${flagged.join(', ')}` : 'consistent'),
  ];
}

function checkMustNotCode(list, enc) {
  return (list || []).flatMap(({ family, reason }) => {
    const selected = proposalsOf(enc).filter(p => p.family === family && p.bucket === 'selected' && !isExcluded(p));
    const ready = selected.filter(p => p.status === 'ready');
    const out = [check(`must_not_code.${family}`, 'hard', ready.length === 0,
      ready.length ? `READY selected proposal(s) ${ready.map(p => p.code).join(', ')} — ${reason}` : `no ready selected proposal — ${reason}`)];
    if (selected.length > ready.length) out.push(check(`must_not_code.${family}.held`, 'soft', false, `selected but not ready: ${selected.filter(p => p.status !== 'ready').map(p => `${p.code} (${p.status})`).join(', ')}`));
    return out;
  });
}

function checkClarifications(expected, enc) {
  const open = (enc.clarifications || []).filter(c => c.state === 'open');
  const out = (expected || []).map(({ fact, scope_in: scopes }) => {
    const any = open.filter(c => c.fact === fact);
    const hit = any.find(c => !scopes || scopes.includes(c.scope));
    return check(`clarification.${fact}`, 'hard', Boolean(hit),
      hit ? `open ${hit.scope} clarification: ${hit.question}` : any.length ? `open only with scope ${any.map(c => c.scope).join('|')} (expected ${scopes.join('|')})` : 'no open clarification for this fact');
  });
  if (!(expected || []).length && open.length) {
    out.push(check('clarification.unexpected', 'soft', false, `open clarifications: ${open.map(c => `${c.fact} (${c.scope})`).join(', ')}`));
  }
  return out;
}

function checkIncomplete(list, enc) {
  const proposals = proposalsOf(enc);
  return (list || []).flatMap(({ family }) => {
    const label = (enc.routing?.families || []).find(f => f.family === family)?.label || family;
    const active = proposals.filter(p => p.family === family && p.bucket === 'selected' && !isExcluded(p));
    const reviewable = active.length > 0
      || proposals.some(p => p.family === family && isExcluded(p) && p.reinstatable)
      || (enc.clarifications || []).some(c => c.state === 'open' && c.family === family)
      || (enc.assessment?.encounter_checks || []).some(c => c.status !== 'pass' && (`${c.detail} ${c.label}`.includes(family) || `${c.detail} ${c.label}`.includes(label)));
    const unsignalled = active.filter(p => p.status === 'ready' && !(p.checks || []).some(c => c.status !== 'pass' && INCOMPLETE_SIGNAL.test(`${c.id} ${c.label} ${c.detail}`))
      && !(p.modifier_considerations || []).some(m => INCOMPLETE_SIGNAL.test(m)));
    return [
      check(`incomplete.${family}.not_dropped`, 'hard', reviewable, reviewable ? 'routed to review' : 'no proposal, reinstatable exclusion, clarification or encounter check covers it'),
      check(`incomplete.${family}.not_auto_completed`, 'hard', unsignalled.length === 0, unsignalled.length ? `ready without an incompleteness check or modifier consideration: ${unsignalled.map(p => p.code).join(', ')}` : 'every ready proposal carries an incompleteness signal'),
    ];
  });
}

// Round 4: a documentation check's exclusion (reinstatable) needs a reviewer decision. The walk confirms one only
// where the document's independent author expectations say the family must not be coded; any other is left
// undecided, so the reviewed report stays blocked and the run records it.
function planConfirmations(enc, mustNotCode, notes) {
  const families = new Set((mustNotCode || []).map(item => item.family));
  return proposalsOf(enc).filter(p => p.bucket === 'excluded' && p.reinstatable && p.decision_state === 'undecided'
    && (p.allowed_actions || []).includes('confirm') && families.has(p.family))
    .map(p => ({ proposal_id: p.id, code: p.code, family: p.family, action: 'confirm', designated: false,
                 note: notes.confirm || 'Agent-executed synthetic verification review - confirms an exclusion the document author marked as not coded; not a clinical judgement' }));
}

function fromSecondReview(p) {
  return p?.support?.origin === 'second_review';
}

// A code the bounded second review added is decided only when review_plan.second_review.approve_codes names it; any
// other is left undecided (second_review_held), so the reviewed report stays withheld and the run records it.
// options.mustNotCode: a code of a family the document's must_not_code lists is never approved (must_not_code_held; a
// list naming one is a plan_conflict). An explicit review_plan.approve_codes list, or options.noAutoApprove without one,
// limits approvals to the codes it names (not_in_approve_codes, approve_codes_unmatched); the designated rejection never
// takes a code the list names.
function planDecisions(enc, reviewPlan, notes, options = {}) {
  const approveSecond = new Set((reviewPlan?.second_review?.approve_codes || []).map(String));
  const listed = Array.isArray(reviewPlan?.approve_codes) ? reviewPlan.approve_codes.map(String) : null;
  const explicit = Boolean(options.noAutoApprove) || listed !== null;
  const named = new Set(listed || []);
  const mustNot = new Set((options.mustNotCode || []).map(item => item.family));
  const ready = proposalsOf(enc).filter(p => p.bucket === 'selected' && p.status === 'ready' && p.decision_state === 'undecided'
    && (p.allowed_actions || []).includes('approve') && (!fromSecondReview(p) || approveSecond.has(p.code)));
  const namedPrimary = p => explicit && !fromSecondReview(p) && named.has(p.code);
  const rule = reviewPlan?.reject;
  let designated = null;
  if (rule) {
    const family = ready.filter(p => p.family === rule.family && (p.allowed_actions || []).includes('reject') && !namedPrimary(p));
    designated = family.find(p => (rule.prefer_codes || []).includes(p.code)) || family[family.length - 1] || null;
  }
  const wanted = p => fromSecondReview(p) || !explicit || named.has(p.code);
  const decisions = ready.filter(p => p === designated || (wanted(p) && !mustNot.has(p.family))).map(p => ({
    proposal_id: p.id, code: p.code, family: p.family, action: p === designated ? 'reject' : 'approve',
    designated: p === designated,
    note: p === designated ? notes.reject : fromSecondReview(p) ? (notes.second_review_approve || notes.approve) : notes.approve,
  }));
  const held = proposalsOf(enc).filter(p => fromSecondReview(p) && p.bucket === 'selected' && p.decision_state === 'undecided'
    && !approveSecond.has(p.code)).map(p => p.code);
  // Every ready code left undecided is reported once: a list naming a code of a must_not_code family is a conflict;
  // any other code of such a family is held; under an explicit list, any other code is not named.
  const open = ready.filter(p => p !== designated);
  const conflict = p => mustNot.has(p.family) && (namedPrimary(p) || (fromSecondReview(p) && approveSecond.has(p.code)));
  const describe = code => {
    const p = proposalsOf(enc).find(item => item.code === code);
    if (!p) return `${code} (not proposed)`;
    if (fromSecondReview(p)) return `${code} (second review: needs review_plan.second_review.approve_codes)`;
    if (p.bucket !== 'selected') return `${code} (${p.bucket})`;
    return `${code} (${p.decision_state !== 'undecided' ? p.decision_state : p.status})`;
  };
  return {
    decisions, designated_missing: Boolean(rule) && !designated, second_review_held: held,
    must_not_code_held: open.filter(p => mustNot.has(p.family) && !conflict(p)).map(p => p.code),
    plan_conflicts: open.filter(conflict).map(p => `${p.code} (${p.family})`),
    not_in_approve_codes: explicit ? open.filter(p => !fromSecondReview(p) && !named.has(p.code) && !mustNot.has(p.family)).map(p => p.code) : [],
    approve_codes_unmatched: [...named].filter(code => !ready.some(p => p.code === code && !fromSecondReview(p))).map(describe),
  };
}

// Every decision this run made, as the reloaded encounter records it: an agent's, with the note the walk wrote (which
// names the agent-executed synthetic review), and an approval with the agent attestation; and none approved a code of a
// family must_not_code lists.
function checkDecisionLabels(made, enc, mustNotCode) {
  const history = enc?.decisions?.history || [];
  const mustNot = new Set((mustNotCode || []).map(item => item.family));
  const familyOf = d => d.family || proposalsOf(enc).find(p => p.id === d.proposal_id)?.family;
  const recorded = made.filter(d => d.http_status === 201);
  const labels = recorded.map(d => {
    const entry = history.find(h => (d.decision_id ? h.id === d.decision_id : h.proposal_id === d.proposal_id && h.action === d.action && !h.invalidated)) || null;
    return {
      code: d.code, action: d.action, decision_id: d.decision_id || null, recorded: Boolean(entry),
      agent: entry?.reviewer_kind === 'agent', note_kept: Boolean(entry) && entry.note === d.note,
      note_labelled: Boolean(entry) && NOTE_LABEL.test(entry.note || ''),
      acknowledgement_labelled: d.action === 'approve' ? Boolean(entry) && String(entry.acknowledgement || '').includes(AGENT_LABEL) : null,
    };
  });
  const unlabelled = labels.filter(l => !(l.recorded && l.agent && l.note_kept && l.note_labelled && l.acknowledgement_labelled !== false));
  const approved = recorded.filter(d => d.action === 'approve' && mustNot.has(familyOf(d)));
  return {
    labels,
    checks: [
      check('decisions.labelled', 'hard', unlabelled.length === 0, !labels.length ? 'no decision was made'
        : unlabelled.length ? `not recorded as labelled agent review: ${unlabelled.map(l => `${l.code} ${l.action} (${Object.entries(l).filter(([k, v]) => v === false && k !== 'code').map(([k]) => k).join(', ')})`).join('; ')}`
          : `${labels.length} decision(s), each an agent's with its labelled note${labels.some(l => l.action === 'approve') ? '; each approval with the agent attestation' : ''}`),
      check('decisions.never_approved_must_not_code', 'hard', approved.length === 0, approved.length
        ? `approved a code of a must_not_code family: ${approved.map(d => `${d.code} (${familyOf(d)})`).join(', ')}`
        : `no approval of a code in ${mustNot.size ? [...mustNot].join(', ') : 'a must_not_code family (none listed)'}`),
    ],
  };
}

// Before any upload: the manifest's plan for a document can be carried out as written, and every note it would write
// says what made the decision.
function planProblems(doc, notes = {}) {
  const problems = [];
  const id = doc?.id ?? '?';
  const plan = doc?.review_plan || {};
  const upload = doc?.upload?.service_date;
  const uploadSet = upload !== null && upload !== undefined && upload !== '';
  if (uploadSet && !isoDate(upload)) problems.push(`${id}: upload.service_date ${JSON.stringify(upload)} is not a YYYY-MM-DD date`);
  if (plan.context_edit !== undefined && plan.context_edit !== null) {
    const edit = plan.context_edit;
    const keys = edit && typeof edit === 'object' && !Array.isArray(edit) ? Object.keys(edit) : null;
    const acts = (keys || []).filter(key => key !== 'documented_date');
    const declared = Boolean(keys) && keys.includes('documented_date');
    const where = `${id}: review_plan.context_edit`;
    if (!keys) problems.push(`${where} must be an object`);
    else if (keys.some(key => !CONTEXT_EDIT_KEYS.has(key))) problems.push(`${where} has an unknown key: ${keys.filter(key => !CONTEXT_EDIT_KEYS.has(key)).join(', ')}`);
    else if (acts.length !== 1) problems.push(`${where} must give exactly one of service_date or clear_member_date`);
    else if (acts[0] === 'clear_member_date' && edit.clear_member_date !== true) problems.push(`${where}.clear_member_date must be true`);
    else if (acts[0] === 'service_date' && !isoDate(edit.service_date)) problems.push(`${where}.service_date ${JSON.stringify(edit.service_date)} is not a YYYY-MM-DD date`);
    else if (acts[0] === 'service_date' && edit.service_date === upload) problems.push(`${where}.service_date is the date entered at upload: there is no change to save`);
    // the date the document states, which clearing the member's must send: only with clear_member_date
    else if (declared && acts[0] !== 'clear_member_date') problems.push(`${where}.documented_date names the date a cleared member date leaves, so it goes only with clear_member_date`);
    else if (declared && !isoDate(edit.documented_date)) problems.push(`${where}.documented_date ${JSON.stringify(edit.documented_date)} is not a YYYY-MM-DD date`);
    else if (declared && edit.documented_date === upload) problems.push(`${where}.documented_date is the member's date entered at upload: clearing it leaves no conflict settled`);
    // Without a member date entered at upload there is no member conflict to settle: {"service_date": ...} answers the
    // encounter's open date question (contextEditPlan), and there is no member date to clear.
    else if (!uploadSet && acts[0] === 'clear_member_date') problems.push(`${where}.clear_member_date clears the member's date entered at upload, but upload.service_date gives none: an open date question is answered with {"service_date": "YYYY-MM-DD"}`);
  }
  if (plan.approve_codes !== undefined) {
    const codes = plan.approve_codes;
    if (!Array.isArray(codes) || codes.some(code => typeof code !== 'string' || !code.trim()) || new Set(codes).size !== codes.length) {
      problems.push(`${id}: review_plan.approve_codes must be a list of distinct, non-empty codes`);
    }
  }
  // confirm and second_review_approve have labelled fallbacks (planConfirmations' own note, notes.approve): checked if given
  const unlabelled = [['approve', true], ['reject', Boolean(plan.reject)], ['confirm', false], ['second_review_approve', false]]
    .filter(([name, needed]) => (needed || notes[name] !== undefined) && !(typeof notes[name] === 'string' && NOTE_LABEL.test(notes[name])))
    .map(([name]) => name);
  if (unlabelled.length) problems.push(`review_notes ${unlabelled.join(', ')} must say "agent-executed synthetic" (${id} would write ${unlabelled.length === 1 ? 'it' : 'them'})`);
  return problems;
}

// --- the reviewer-requested second review (ARCHITECTURE 5.11) ---------------------------------------------------------

function secondReviewPlan(doc) {
  const plan = doc?.review_plan?.second_review;
  return plan && plan.ask === true ? { ask: true, approve_codes: (plan.approve_codes || []).map(String) } : null;
}

// The API serves no 'sent' flag: a run was sent unless it reused a retained result, or was not sent or cancelled.
function sentRun(run) {
  return !run.reused_from && ['succeeded', 'failed', 'unknown'].includes(run.state);
}

function runFacts(run) {
  return JSON.stringify([run.purpose, run.state, run.request_sha256, run.response_sha256, run.usage, run.reused_from, run.reconciled]);
}

// before: the encounter when the second review was offered; after: once its processing settled (null if never asked).
function checkSecondReview(before, after, ask) {
  const offered = before?.second_review || {};
  const out = [check('second_review.offered', 'hard', offered.available === true && offered.can_request === true,
    `available ${offered.available}, can_request ${offered.can_request}${offered.reason ? `, reason: ${offered.reason}` : ''}; items ${JSON.stringify(offered.items || [])}`)];
  if (!ask || ask.http_status === null || ask.http_status === undefined) return out;
  out.push(check('second_review.request', 'hard', ask.http_status === 201, `POST second-review answered HTTP ${ask.http_status}${ask.error ? `: ${ask.error}` : ''}`));
  if (ask.http_status !== 201 || !after) return out;
  const earlier = new Map((before.provider_runs || []).map(run => [run.id, run]));
  const fresh = (after.provider_runs || []).filter(run => !earlier.has(run.id));
  const second = fresh.filter(run => run.purpose === 'second_review');
  const asked = second.length === 1 && JSON.stringify(second[0].scope_items || []) === JSON.stringify(offered.items || []);
  out.push(check('second_review.one_run', 'hard', fresh.length === 1 && asked,
    `${fresh.length} new run(s): ${fresh.map(run => `${run.purpose}/${run.state}${run.reused_from ? '/reused' : ''}`).join(', ') || 'none'}; asked about ${JSON.stringify(second[0]?.scope_items || [])}`));
  const sent = fresh.filter(sentRun);
  out.push(check('second_review.sent_at_most_once', 'hard', sent.length <= 1 && sent.every(run => run.purpose === 'second_review'),
    `${sent.length} new request(s) sent${sent.length ? `: ${sent.map(run => `${run.purpose}/${run.state}`).join(', ')}` : ''}`));
  const kept = new Map((after.provider_runs || []).map(run => [run.id, run]));
  const changed = [...earlier.values()].filter(run => !kept.has(run.id) || runFacts(kept.get(run.id)) !== runFacts(run));
  out.push(check('second_review.earlier_runs_kept', 'hard', changed.length === 0,
    changed.length ? `changed or missing: ${changed.map(run => run.id).join(', ')}` : `${earlier.size} earlier run(s) unchanged (state, hashes, usage, reuse, reconciliation)`));
  const services = new Set((before.assessment?.completeness?.unresolved_items || []).filter(item => item.second_review === true).map(item => item.service));
  const added = proposalsOf(after).filter(p => fromSecondReview(p) && p.bucket === 'selected');
  const stray = added.filter(p => !services.has(p.support?.service));
  out.push(check('second_review.fills_only_offered', 'hard', stray.length === 0,
    stray.length ? `added outside the offered services: ${stray.map(p => `${p.code} (${p.support?.service || 'no service'})`).join(', ')}` : `${added.length} code(s) added (${added.map(p => `${p.code} for ${p.support?.service}`).join(', ') || 'none'}), each for an offered service`));
  const primary = enc => proposalsOf(enc).filter(p => !fromSecondReview(p)).map(p => `${p.code}:${p.bucket}`).sort();
  const actionable = proposalsOf(after).filter(p => fromSecondReview(p) && p.bucket === 'alternative' && (p.allowed_actions || []).length);
  const same = JSON.stringify(primary(before)) === JSON.stringify(primary(after));
  out.push(check('second_review.no_promotion', 'hard', same && actionable.length === 0,
    `${same ? 'primary proposals unchanged' : `primary proposals ${JSON.stringify(primary(before))} -> ${JSON.stringify(primary(after))}`}; second-review alternatives with an action: ${actionable.map(p => p.code).join(', ') || 'none'}`));
  const run = second[0];
  const merged = (after.assessment?.encounter_checks || []).find(item => item.id === 'provider.second_review');
  // soft: an unknown, failed or refused answer is a recorded outcome for the operator, not a defect of the walk
  out.push(check('second_review.outcome', 'soft', run?.state === 'succeeded' && after.assessment?.second_run === run?.id
    && merged?.status !== 'fail',
    `run ${run?.state}${run?.reused_from ? ' (reused, nothing sent)' : ''}; usage ${JSON.stringify(run?.usage || {})}; read by the assessment ${after.assessment?.second_run === run?.id}; check ${merged ? `${merged.status}: ${merged.detail}` : 'absent'}; state ${after.state}`));
  return out;
}

// --- the member's date and the context edit (review_plan.context_edit) ------------------------------------------------

function contextEditPlan(doc) {
  const plan = doc?.review_plan?.context_edit;
  if (plan === undefined || plan === null) return null;
  const upload = doc?.upload?.service_date;
  if (plan.clear_member_date !== true && (upload === null || upload === undefined || upload === '')) {
    // no member date entered at upload: the date answers the encounter's open date question (planProblems)
    return { clear_member_date: false, service_date: plan.service_date, answers_question: true };
  }
  return plan.clear_member_date === true
    ? { clear_member_date: true, service_date: '', documented_date: isoDate(plan.documented_date) ? plan.documented_date : null }
    : { clear_member_date: false, service_date: plan.service_date };
}

function isMemberDateHold(run) {
  return Boolean(run) && run.purpose === 'primary' && run.state === 'not_sent' && !run.request_sha256
    && run.error === MEMBER_DATE_HOLD_MESSAGE;
}

// jobs._service_date_of: the date a request for the encounter's current context carries (a documented or member date).
function contextRequestDate(enc) {
  const fact = enc?.context?.facts?.service_date || {};
  return ['document', 'user'].includes(fact.origin) && isoDate(String(fact.value ?? '')) ? String(fact.value) : null;
}

// The calendar dates a passage states in the four forms (ISO strings), as the server's date_from_match reads them.
function quotedDates(text) {
  const dates = new Set();
  for (const m of String(text ?? '').matchAll(FULL_DATE)) {
    const month = name => MONTH_KEYS.indexOf(name.slice(0, 3).toLowerCase()) + 1;
    const [year, mon, day] = m[1] ? [m[1], m[2], m[3]] : m[6] ? [m[6], m[4], m[5]]
      : m[9] ? [m[9], month(m[7]), m[8]] : [m[12], month(m[11]), m[10]];
    const iso = `${year}-${String(Number(mon)).padStart(2, '0')}-${String(Number(day)).padStart(2, '0')}`;
    if (isoDate(iso)) dates.add(iso);
  }
  return dates;
}

// The {user} and {document} of a note written from ``template``, or null when it is not.
function noteParts(template, note) {
  const [head, rest] = template.split('{user}');
  const [middle, tail] = rest.split('{document}');
  const text = String(note ?? '');
  if (text.length < head.length + middle.length + tail.length || !text.startsWith(head) || !text.endsWith(tail)) return null;
  const body = text.slice(head.length, text.length - tail.length);
  const at = body.indexOf(middle);
  return at < 0 ? null : { user: body.slice(0, at), document: body.slice(at + middle.length) };
}

// The date a request must carry once the member's date is cleared, named from the encounter BEFORE the edit - never from
// the server's state after it, which is what the edit's checks judge (fix round gi2, ops-1: a server that sent the cleared
// member date, no date, or a date the document never states passed, judged by its own post-edit context). The member
// conflict's note says what the document gives (USER_CONFLICT_NOTE): its own read date where it gives one, which a
// passage its evidence quotes - exactly as the revision text has it - must state; else no date a request carries (a
// document-internal conflict, or a labelled date the reader cannot use or reads as another occurrence's: the request
// goes without one, and the date is asked). The manifest's documented_date, when given, must be that date.
// {ok, date, reason}: ok false when no date can be named, and the walk then makes no edit (contextEditPreconditions).
function documentedServiceDate(enc, plan = null) {
  const fact = enc?.context?.facts?.service_date || {};
  const member = enc?.context?.user_values?.service_date ?? null;
  const declared = plan?.documented_date ?? null;
  const refuse = reason => ({ ok: false, date: null, reason: `no date named before the edit: ${reason}` });
  if (fact.origin !== 'conflict' || fact.member_conflict !== true) {
    return refuse(`the service date is ${fact.origin || 'not reported'}, not a member's date held against the document's`);
  }
  const conflict = noteParts(USER_CONFLICT_NOTE, fact.note);
  const parts = conflict || noteParts(USER_ELSEWHERE_NOTE, fact.note);
  if (!parts) return refuse(`its note is not one the walk reads (${JSON.stringify(String(fact.note ?? '').slice(0, 120))})`);
  if (parts.user !== member) return refuse(`its note holds the member's ${parts.user}, but the member's stored date is ${JSON.stringify(member)}`);
  let date = null;
  const excerpt = text => (text.length > 60 ? `${text.slice(0, 59)}…` : text);
  let said = `the document gives no date of its own a request carries (${conflict ? 'it gives' : 'it reads that date as another occurrence\'s'}: ${excerpt(parts.document)})`;
  if (conflict && isoDate(parts.document)) {
    date = parts.document;
    const points = Array.from(String(enc?.revision?.text ?? ''));
    const quoting = (Array.isArray(fact.evidence) ? fact.evidence : []).filter(span => span && typeof span.text === 'string'
      && cpSlice(points, span.start, span.end) === span.text && quotedDates(span.text).has(date));
    if (!quoting.length) return refuse(`its note says the document gives ${date}, but no passage its evidence quotes from the revision text states it`);
    if (date === member) return refuse(`its note says the document gives the member's own ${date}`);
    said = `the document gives ${date} (quoted: ${JSON.stringify(excerpt(quoting[0].text))})`;
  }
  if (declared !== null && declared !== date) return refuse(`${said}, not the manifest's documented_date ${declared}`);
  return { ok: true, date, reason: `before the edit ${said}${declared ? ', as the manifest\'s documented_date says' : ''}; `
    + `clearing the member's ${member} must send ${date ? `a request for ${date}` : 'a request with no date'}` };
}

function describeRun(run) {
  return `${run.purpose}/${run.state}${run.reused_from ? '/reused' : ''}${isMemberDateHold(run) ? '/hold' : ''}`;
}

// Everything a run records that must not change once recorded (runFacts, and the error a hold is named by).
function runRecord(run) {
  return JSON.stringify([runFacts(run), run.error ?? null]);
}

// Which of these dates (null: none) a run's request was made for, read from its request hash alone.
function requestDateOf(run, text, dates) {
  const named = [...new Set(dates)].find(date => primaryRequestSha256(text, date) === run.request_sha256);
  return named === undefined ? `none of the requests for ${[...new Set(dates)].map(date => date || 'no date').join(', ')}`
    : `the request for ${named || 'no date'}`;
}

function checkUploadDate(uploadDate, enc) {
  if (uploadDate === null || uploadDate === undefined || uploadDate === '') return [];
  const stored = enc?.context?.user_values?.service_date ?? null;
  return [check('upload.service_date', 'hard', stored === uploadDate,
    `the member's date entered at upload ${JSON.stringify(uploadDate)}; stored as encounter metadata ${JSON.stringify(stored)}`)];
}

// What the edit settles, before it is made: the member's date is held as a conflict with the documented one, a not-sent
// hold run records it, nothing was built, reused or sent, and - for a clear - the date it must then send is named
// (documentedServiceDate). The walk saves nothing unless every one holds.
function contextEditPreconditions(before, uploadDate, plan = null) {
  if (plan?.answers_question) return questionEditPreconditions(before);
  const fact = before?.context?.facts?.service_date || {};
  const member = before?.context?.user_values?.service_date ?? null;
  const earlier = before?.provider_runs || [];
  const holds = earlier.filter(isMemberDateHold);
  const conflict = fact.origin === 'conflict' && fact.member_conflict === true;
  const sameMember = !uploadDate || member === uploadDate;
  const built = earlier.filter(run => run.request_sha256 || run.reused_from || sentRun(run));
  const out = [
    check('context_edit.held_before', 'hard', conflict && holds.length > 0 && sameMember,
      `service date ${fact.origin}${conflict ? ' (the member value differs from the documented one)' : ''}; member value `
        + `${JSON.stringify(member)}${uploadDate ? ` (entered at upload: ${uploadDate})` : ''}; ${holds.length} not-sent hold run(s)`),
    check('context_edit.nothing_sent_before', 'hard', built.length === 0, built.length
      ? `while the conflict held: ${built.map(describeRun).join(', ')}` : `${earlier.length} run(s), none sent, built or reused`),
  ];
  if (plan?.clear_member_date) {
    const named = documentedServiceDate(before, plan);
    out.push(check('context_edit.documented_date', 'hard', named.ok, named.reason));
  }
  return out;
}

// before: the encounter once processing finished (the member conflict held); after: once the edit's processing settled;
// settled: once the identical second save's settled (null if it was not made); edit: what the walk did (editContext).
function checkContextEdit(before, after, settled, plan, edit, uploadDate) {
  if (plan?.answers_question) return checkQuestionEdit(before, after, settled, plan, edit);
  const member = before?.context?.user_values?.service_date ?? null;
  const earlier = before?.provider_runs || [];
  const holds = earlier.filter(isMemberDateHold);
  const out = contextEditPreconditions(before, uploadDate, plan);
  out.push(check('context_edit.request', 'hard', edit?.http_status === 201,
    `POST context answered HTTP ${edit?.http_status ?? 'none'}${edit?.error ? `: ${edit.error}` : ''}; the form sent ${JSON.stringify(edit?.posted ?? null)}`));
  if (edit?.http_status !== 201 || !after) return out;

  // The edited date, or for a cleared member date the date named BEFORE the edit (documentedServiceDate) - never the
  // date the server states after it, which is what these checks judge (fix round gi2, ops-1). Nothing named, nothing
  // passes for it.
  const named = plan.clear_member_date ? documentedServiceDate(before, plan) : { ok: true, date: plan.service_date };
  const wanted = named.date;
  const wantedLabel = named.ok ? wanted || 'no date' : 'a date named before the edit (none was)';
  const factAfter = after.context?.facts?.service_date || {};
  const value = after.context?.user_values?.service_date ?? null;
  const stated = contextRequestDate(after);
  const dateOk = factAfter.member_conflict !== true && named.ok && stated === wanted
    && (plan.clear_member_date ? !value : value === plan.service_date);
  out.push(check('context_edit.date_after', 'hard', dateOk,
    `member value ${JSON.stringify(value)}; service date ${JSON.stringify(factAfter.value ?? null)} (${factAfter.origin})`
      + `${factAfter.member_conflict === true ? ', still a member conflict' : ''}; a request for this context carries ${stated || 'no date'}`
      + (plan.clear_member_date ? ` (the member date was cleared; it must carry ${wantedLabel})` : ` (edited to ${plan.service_date})`)));

  const text = after.revision?.text || '';
  const want = named.ok ? primaryRequestSha256(text, wanted) : null;
  const seen = new Set(earlier.map(run => run.id));
  const fresh = (after.provider_runs || []).filter(run => !seen.has(run.id));
  const heldAgain = fresh.filter(isMemberDateHold);
  const others = fresh.filter(run => !isMemberDateHold(run));
  const one = others.length === 1 ? others[0] : null;
  const answered = Boolean(one) && (sentRun(one) || (one.state === 'succeeded' && Boolean(one.reused_from)));
  const carries = Boolean(one) && want !== null && one.request_sha256 === want;
  out.push(check('context_edit.one_request', 'hard', heldAgain.length === 0 && Boolean(one) && one.purpose === 'primary' && answered && carries,
    `${fresh.length} new run(s): ${fresh.map(describeRun).join(', ') || 'none'}`
      + (one ? `; ${one.reused_from ? 'a retained answer was reused (nothing sent)' : sentRun(one) ? 'one request sent' : 'no request sent'}; `
        + `its request is ${carries ? `the request for the revision text and ${wantedLabel}`
          : `${requestDateOf(one, text, [wanted, stated, uploadDate || null, member, null])}, not the one for ${wantedLabel}`}` : '')));
  const sent = fresh.filter(sentRun);
  out.push(check('context_edit.sent_at_most_once', 'hard', sent.length <= 1 && sent.every(run => want !== null && run.request_sha256 === want),
    `${sent.length} new request(s) sent${sent.length ? `: ${sent.map(run => `${describeRun(run)} ${want !== null && run.request_sha256 === want ? 'for' : 'NOT for'} ${wantedLabel}`).join(', ')}` : ''}`));
  const kept = new Map((after.provider_runs || []).map(run => [run.id, run]));
  const changed = earlier.filter(run => !kept.has(run.id) || runRecord(kept.get(run.id)) !== runRecord(run));
  out.push(check('context_edit.hold_kept', 'hard', changed.length === 0, changed.length
    ? `changed or missing: ${changed.map(run => `${run.id} (${describeRun(run)})`).join(', ')}`
    : `${holds.length} hold run(s) and ${earlier.length - holds.length} other earlier run(s) unchanged (state, hashes, usage, error)`));

  out.push(...identicalSaveChecks(after, settled, edit.identical || {}));
  out.push(check('context_edit.outcome', 'soft', one?.state === 'succeeded',
    `run ${one ? describeRun(one) : 'none'}; usage ${JSON.stringify(one?.usage || {})}; state ${after.state}`));
  return out;
}

// The same values saved again, once the save's processing settled (after: then; settled: once the second save's
// processing settled, or null): nothing sent or held, every run unchanged, and - soft - only a re-check, which the
// screen's form refuses to send itself (editContext sends it through the page's api() client).
function identicalSaveChecks(after, settled, identical) {
  const out = [];
  let rechecked = null;
  if (identical.http_status !== 201 || !settled) {
    out.push(check('context_edit.identical_save', 'hard', false, `the identical save ${identical.http_status === null || identical.http_status === undefined
      ? 'was not made' : `answered HTTP ${identical.http_status}`}${identical.error ? `: ${identical.error}` : ''}${identical.http_status === 201 ? '; its processing was not seen to settle' : ''}`));
  } else {
    const before2 = new Set((after.provider_runs || []).map(run => run.id));
    const fresh2 = (settled.provider_runs || []).filter(run => !before2.has(run.id));
    const kept2 = new Map((settled.provider_runs || []).map(run => [run.id, run]));
    const changed2 = (after.provider_runs || []).filter(run => !kept2.has(run.id) || runRecord(kept2.get(run.id)) !== runRecord(run));
    const sent2 = fresh2.filter(run => sentRun(run) || isMemberDateHold(run));
    out.push(check('context_edit.identical_save', 'hard', sent2.length === 0 && changed2.length === 0,
      `the same values saved again (${identical.via}): ${fresh2.length} new run(s)${fresh2.length ? ` (${fresh2.map(describeRun).join(', ')})` : ''}; `
        + `${sent2.length} sent or held; ${changed2.length ? `changed or missing: ${changed2.map(run => run.id).join(', ')}` : 'every run unchanged'}`));
    rechecked = fresh2;
  }
  if (rechecked) {
    out.push(check('context_edit.identical_save_rechecks', 'soft', rechecked.length === 0,
      rechecked.length ? `it recorded ${rechecked.map(describeRun).join(', ')} instead of only re-checking` : 'it only re-checked with the run in use'));
  }
  out.push(check('context_edit.form_refuses_identical', 'soft', identical.form_posted === false && identical.form_toast === IDENTICAL_REFUSAL,
    identical.form_posted ? 'the screen\'s form sent the identical save' : `the screen's form sent nothing and said ${JSON.stringify(identical.form_toast ?? '')}`));
  return out;
}

// --- the documented date question (review_plan.context_edit {"service_date": ...} without upload.service_date) -------
//
// A document whose own dates conflict, or that states none the reader reads, leaves the encounter's date question open
// (studio/validation/checks.py service_date_clarification: scope encounter, fact service_date) and its primary request
// without a "Date of service" line (studio/providers/corti.py build_coding_request). A member's date answers it through
// the screen's form: the answered context asks for another request than the run in use carries, so the save makes that
// one request - or reuses a retained identical answer - (jobs.change_context, stage_predict), and the same save made
// again only re-checks with it. A date the document's own reading cannot agree with is a member conflict instead
// (context.merge_user_values): nothing is taken, and the checks below fail and say so.

// The open service_date questions of the encounter's current assessment: any scope, or (encounterOnly) the encounter's
// own question, which no proposal holds.
function openDateQuestions(enc, encounterOnly = false) {
  return (enc?.clarifications || []).filter(c => Boolean(c) && c.state === 'open' && c.fact === 'service_date'
    && (!encounterOnly || (c.scope === 'encounter' && !c.proposal_id)));
}

function describeQuestion(c) {
  const reason = String(c.reason ?? '');
  return `${c.scope}${c.proposal_id ? ` (proposal ${c.proposal_id})` : ''} "${c.question}"`
    + `${reason ? ` (${reason.length > 140 ? `${reason.slice(0, 139)}…` : reason})` : ''}`;
}

// A run that answered its request: sent, or a retained identical answer reused (nothing sent).
function answeredRun(run) {
  return sentRun(run) || (run.state === 'succeeded' && Boolean(run.reused_from));
}

// The dates a request of this encounter could have been made for, to name the one a run's hash proves: none, the one
// the context states, and every date the service-date fact's evidence quotes.
function candidateDates(enc) {
  const fact = enc?.context?.facts?.service_date || {};
  const quoted = (Array.isArray(fact.evidence) ? fact.evidence : []).flatMap(span => [...quotedDates(span?.text)]);
  return [null, contextRequestDate(enc), ...quoted];
}

// What the answer settles, before it is made: the encounter's date question is open; no service date is established
// (none a request carries, no member date, no member conflict); every primary run that carries a request carries the
// request for the revision text with no date, and at least one such request was answered. The walk saves nothing
// unless every one holds.
function questionEditPreconditions(before) {
  const fact = before?.context?.facts?.service_date || {};
  const member = before?.context?.user_values?.service_date ?? null;
  const asked = openDateQuestions(before, true);
  const elsewhere = openDateQuestions(before).filter(c => !asked.includes(c));
  const stated = contextRequestDate(before);
  const text = typeof before?.revision?.text === 'string' ? before.revision.text : '';
  const dateless = primaryRequestSha256(text, null);
  const carrying = (before?.provider_runs || []).filter(run => run.purpose === 'primary' && run.request_sha256);
  const answered = carrying.filter(answeredRun);
  const dated = carrying.filter(run => run.request_sha256 !== dateless);
  const unestablished = stated === null && fact.member_conflict !== true && (member === null || member === '');
  return [
    check('context_edit.question_open', 'hard', asked.length > 0, asked.length
      ? `open encounter date question: ${describeQuestion(asked[0])}`
      : `no open encounter-scope service_date question, so there is nothing for the date to answer${elsewhere.length
        ? ` (open elsewhere: ${elsewhere.map(describeQuestion).join('; ')})` : ''}`),
    check('context_edit.date_unestablished', 'hard', unestablished,
      `service date ${JSON.stringify(fact.value ?? null)} (${fact.origin || 'not reported'})`
        + `${fact.member_conflict === true ? ', a member conflict' : ''}; member value ${JSON.stringify(member)}; `
        + `a request for this context carries ${stated || 'no date'}`),
    check('context_edit.dateless_before', 'hard', answered.length > 0 && dated.length === 0, dated.length
      ? `a primary request was not the dateless one for the revision text: ${dated.map(run => `${run.id} (${describeRun(run)}) `
        + `carries ${requestDateOf(run, text, candidateDates(before))}`).join('; ')}`
      : answered.length
        ? `${carrying.length} primary run(s) carrying a request, each the request for the revision text with no date; answered: `
          + `${answered.map(describeRun).join(', ')}`
        : `no primary request was answered (sent, or a retained answer reused) before the edit: ${carrying.map(describeRun).join(', ')
          || 'no primary run carries a request'}`),
  ];
}

// before: the encounter once processing finished (the date question open); after: once the save's processing settled;
// settled: once the same save made again settled (null if it was not); edit: what the walk did (editContext).
function checkQuestionEdit(before, after, settled, plan, edit) {
  const out = questionEditPreconditions(before);
  out.push(check('context_edit.request', 'hard', edit?.http_status === 201,
    `POST context answered HTTP ${edit?.http_status ?? 'none'}${edit?.error ? `: ${edit.error}` : ''}; the form sent ${JSON.stringify(edit?.posted ?? null)}`));
  if (edit?.http_status !== 201 || !after) return out;

  const wanted = plan.service_date;
  const factAfter = after.context?.facts?.service_date || {};
  const value = after.context?.user_values?.service_date ?? null;
  const stated = contextRequestDate(after);
  out.push(check('context_edit.date_after', 'hard',
    factAfter.member_conflict !== true && factAfter.origin === 'user' && stated === wanted && value === wanted,
    `member value ${JSON.stringify(value)}; service date ${JSON.stringify(factAfter.value ?? null)} (${factAfter.origin})`
      + `${factAfter.member_conflict === true ? ', a member conflict: the answer was held against the document, not taken' : ''}`
      + `; a request for this context carries ${stated || 'no date'} (answered: ${wanted}, as the member's date)`));

  const earlier = before?.provider_runs || [];
  const text = after.revision?.text || '';
  const want = primaryRequestSha256(text, wanted);
  const seen = new Set(earlier.map(run => run.id));
  const fresh = (after.provider_runs || []).filter(run => !seen.has(run.id));
  const one = fresh.length === 1 ? fresh[0] : null;
  const carries = Boolean(one) && one.request_sha256 === want;
  out.push(check('context_edit.one_request', 'hard', Boolean(one) && one.purpose === 'primary' && answeredRun(one) && carries,
    `${fresh.length} new run(s): ${fresh.map(describeRun).join(', ') || 'none'}`
      + (one ? `; ${one.reused_from ? 'a retained answer was reused (nothing sent)' : sentRun(one) ? 'one request sent' : 'no request sent'}; `
        + `its request is ${carries ? `the request for the revision text and ${wanted}`
          : `${requestDateOf(one, text, [wanted, ...candidateDates(before)])}, not the one for ${wanted}`}` : '')));
  const sent = fresh.filter(sentRun);
  out.push(check('context_edit.sent_at_most_once', 'hard', sent.length <= 1 && sent.every(run => run.request_sha256 === want),
    `${sent.length} new request(s) sent${sent.length ? `: ${sent.map(run => `${describeRun(run)} ${run.request_sha256 === want ? 'for' : 'NOT for'} ${wanted}`).join(', ')}` : ''}`));
  const kept = new Map((after.provider_runs || []).map(run => [run.id, run]));
  const changed = earlier.filter(run => !kept.has(run.id) || runRecord(kept.get(run.id)) !== runRecord(run));
  out.push(check('context_edit.earlier_runs_kept', 'hard', changed.length === 0, changed.length
    ? `changed or missing: ${changed.map(run => `${run.id} (${describeRun(run)})`).join(', ')}`
    : `${earlier.length} earlier run(s) unchanged (state, hashes, usage, reuse, reconciliation, error)`));
  const openAfter = openDateQuestions(after);
  const openSettled = settled ? openDateQuestions(settled) : [];
  out.push(check('context_edit.question_closed', 'hard', openAfter.length === 0 && openSettled.length === 0,
    openAfter.length ? `still open after the save: ${openAfter.map(describeQuestion).join('; ')}`
      : openSettled.length ? `open again after the same save made again: ${openSettled.map(describeQuestion).join('; ')}`
        : `no service_date question open after the save${settled ? ' or after the same save made again' : ''}`));

  out.push(...identicalSaveChecks(after, settled, edit.identical || {}));
  out.push(check('context_edit.outcome', 'soft', one?.state === 'succeeded',
    `run ${one ? describeRun(one) : 'none'}; usage ${JSON.stringify(one?.usage || {})}; state ${after.state}`));
  return out;
}

// Before anything is done to an attached encounter: it must be this manifest document's. An uploaded document is its
// stored original, byte for byte, and its text (whitespace aside: an extraction may space lines otherwise). A paste has
// no stored original, so its text alone identifies it: a pasted revision with no stored original - as the walk's own
// revision.source check demands - whose text has the document's lines, only trailing whitespace and line-ending style
// aside (fix round gi2, ops-2: a paste document attached to an uploaded file's encounter, and to text whose line breaks
// differ, which changes how the reader reads sections, labels and fields; the walk then decided codes there).
function attachedProblems(enc, item) {
  const problems = [];
  const rev = enc?.revision || {};
  if (item.delivery.format === 'paste') {
    if (!isPastedRevision(rev)) {
      const file = rev.source_file;
      problems.push(`its revision ${rev.number} is ${rev.kind}${file ? `, with a stored original ${file.name} (${file.sha256}, ${file.size} bytes)` : ''}`
        + `: not a pasted revision without a stored original, as ${item.doc.delivery.file} is delivered`);
    }
    if (lineText(rev.text) !== lineText(item.sourceText)) {
      problems.push(`its revision ${rev.number} text is not the text of ${item.doc.source}, line for line (only trailing whitespace and line endings may differ)`);
    }
    return problems;
  }
  const file = rev.source_file || {};
  if (file.sha256 !== item.delivery.sha256 || file.size !== item.delivery.size) {
    problems.push(`its stored original ${file.sha256} (${file.size} bytes) is not ${item.doc.delivery.file} (${item.delivery.sha256}, ${item.delivery.size} bytes)`);
  }
  if (collapse(rev.text || '') !== collapse(item.sourceText)) problems.push(`its revision ${rev.number} text is not the text of ${item.doc.source}`);
  return problems;
}

function checkReadiness(enc) {
  // Selected proposals need approve/reject; a reinstatable exclusion needs a confirmation or a reinstated decision.
  const active = proposalsOf(enc).filter(p => (p.bucket === 'selected' && !isExcluded(p)) || (p.bucket === 'excluded' && p.reinstatable));
  const decided = active.every(p => DECIDED.has(p.decision_state) || p.decision_state === 'exclusion_confirmed');
  const readiness = enc.readiness || {};
  const out = [check('readiness.draft', 'soft', readiness.draft === true, `draft ${readiness.draft}`)];
  if (!decided) {
    out.push(check('readiness.reviewed_blocked', 'hard', readiness.reviewed === false,
      `undecided: ${active.filter(p => !DECIDED.has(p.decision_state)).map(p => `${p.code} (${p.status})`).join(', ')}; reviewed ${readiness.reviewed}; blockers ${JSON.stringify(readiness.blockers || [])}`));
  } else {
    out.push(check('readiness.reviewed_available', 'soft', readiness.reviewed === true, `every selected proposal decided; reviewed ${readiness.reviewed}; blockers ${JSON.stringify(readiness.blockers || [])}`));
  }
  return out;
}

function checkPersistence(decisions, before, after, reloaded) {
  const out = [
    check('persist.revision', 'hard', [after, reloaded].every(e => e.revision?.id === before.revision?.id && e.revision?.number === before.revision?.number),
      `revision ${before.revision?.number} (${before.revision?.id}) -> ${after.revision?.number} -> ${reloaded.revision?.number} after reload`),
    check('persist.assessment', 'hard', [after, reloaded].every(e => e.assessment?.id === before.assessment?.id), `assessment ${before.assessment?.id} -> ${reloaded.assessment?.id}`),
  ];
  const history = reloaded.decisions?.history || [];
  for (const d of decisions.filter(item => item.http_status === 201)) {
    const p = proposalsOf(reloaded).find(item => item.id === d.proposal_id);
    const want = DECISION_STATES[d.action];
    const entry = history.find(h => h.proposal_id === d.proposal_id && h.action === d.action && !h.invalidated);
    const ok = p?.decision_state === want && p.decision?.reviewer_kind === 'agent' && p.decision?.note === d.note && Boolean(entry);
    out.push(check(`persist.decision.${d.code}`, 'hard', ok,
      `state ${p?.decision_state} (want ${want}), reviewer_kind ${p?.decision?.reviewer_kind}, note ${p?.decision?.note === d.note ? 'kept' : 'changed'}, history ${entry ? 'yes' : 'missing'}`));
  }
  return out;
}

function checkEvidenceMarks(enc, marks, cards) {
  const points = Array.from(enc.revision?.text || '');
  const out = [];
  const known = new Set();
  for (const p of proposalsOf(enc).filter(item => item.bucket === 'selected')) {
    const exact = markableSpans(p, points);
    exact.forEach(({ index }) => known.add(`${p.id}:${index}`));
    markableSourceSpans(p, points).forEach(({ index }) => known.add(`${p.id}:s${index}`));
    const card = cards.find(c => c.id === `card-${p.id}`);
    out.push(check(`dom.card.${p.code}`, 'hard', Boolean(card), card ? 'code card shown' : 'no code card'));
    if (card) {
      const expectedUnlocated = (p.evidence || []).length - exact.length;
      out.push(check(`dom.unlocated.${p.code}`, 'hard', card.unlocated === expectedUnlocated, `${card.unlocated} unlocated chip(s), ${expectedUnlocated} expected`));
    }
    if (!exact.length) {
      out.push(skip(`dom.marks.${p.code}`, 'no exact evidence span to mark'));
      continue;
    }
    const missing = exact.filter(({ span, index }) => {
      const keyed = marks.filter(m => m.keys.includes(`${p.id}:${index}`));
      return !keyed.length || !stripSpace(keyed.map(m => m.text).join('')).includes(stripSpace(span.text));
    }).map(({ span }) => `[${span.start}:${span.end}]`);
    out.push(check(`dom.marks.${p.code}`, 'hard', missing.length === 0, missing.length ? `no .evidence-mark covering ${missing.join(', ')}` : `${exact.length} span(s) marked`));
  }
  const stray = marks.flatMap(m => m.keys).filter(key => !known.has(key));
  out.push(check('dom.marks.known', 'hard', stray.length === 0, stray.length ? `marks for unknown or inexact spans: ${[...new Set(stray)].join(', ')}` : `${marks.length} mark(s), all for exact spans of selected proposals`));
  return out;
}

function checkDecisionDom(decisions, enc, cards, candidates = []) {
  return decisions.filter(d => d.http_status === 201).map(d => {
    const proposal = proposalsOf(enc).find(p => p.id === d.proposal_id);
    const reviewer = proposal?.decision?.reviewer || '';
    if (d.action === 'confirm') {
      // A confirmed exclusion stays an excluded candidate, which has no code card: its candidate row carries the
      // decision line and the undo button (round 5, pipeline:3).
      const row = candidates.find(c => c.proposal === d.proposal_id);
      const stateOk = proposal?.decision_state === 'exclusion_confirmed';
      const rowOk = Boolean(row) && Boolean(reviewer) && row.text.includes(`Exclusion confirmed by ${reviewer}`);
      return check(`dom.decision.${d.code}`, 'hard', stateOk && rowOk,
        row ? `decision state ${proposal?.decision_state || 'missing'}; candidate row ${rowOk ? 'names the confirming reviewer' : 'lacks "Exclusion confirmed by" and the reviewer'}` : 'no candidate row with an undo button after reload');
    }
    const card = cards.find(c => c.id === `card-${d.proposal_id}`);
    const badgeOk = card && (d.action === 'approve' ? /^Approved/.test(card.badge) && /agent/i.test(card.badge) : card.badge === 'Rejected');
    const insightOk = card && card.insight.includes(AGENT_LABEL) && Boolean(reviewer) && card.insight.includes(reviewer);
    return check(`dom.decision.${d.code}`, 'hard', Boolean(badgeOk && insightOk),
      card ? `badge "${card.badge}"; decision line ${insightOk ? 'names the agent reviewer and the agent label' : `lacks the reviewer or "${AGENT_LABEL}"`}` : 'no code card after reload');
  });
}

function expectedDownloads(readiness) {
  const kinds = [];
  if (readiness.draft === true) kinds.push('draft');
  if (readiness.reviewed === true) kinds.push('reviewed');
  return kinds.flatMap(kind => ['txt', 'csv'].map(fmt => `${kind}.${fmt}`));
}

function checkDownloads(downloads, readiness, withheld) {
  const out = [];
  for (const want of expectedDownloads(readiness)) {
    const d = downloads.find(item => `${item.kind}.${item.fmt}` === want);
    if (!d || d.error) {
      out.push(check(`download.${want}`, 'hard', false, d ? d.error : 'not downloaded'));
      continue;
    }
    const hashes = [d.api_sha256, d.refetch_sha256, ...(d.header_sha256 ? [d.header_sha256] : [])];
    out.push(check(`download.${want}`, 'hard', d.http_status === 201 && d.size > 0 && hashes.every(h => h === d.sha256),
      `HTTP ${d.http_status}; ${d.size} bytes; file ${d.sha256}; API ${d.api_sha256}; re-fetch ${d.refetch_sha256}; header ${d.header_sha256 ?? 'not sent'}`));
  }
  if (readiness.reviewed !== true) {
    out.push(check('download.reviewed_withheld', 'hard', withheld?.offered === false, withheld?.offered ? 'the UI offered a reviewed report before the review was complete' : `reviewed report not offered (review incomplete: ${(readiness.blockers || []).join('; ')})`));
  }
  return out;
}

function checkListing(downloads, enc) {
  const reports = enc.reports || [];
  return downloads.filter(d => d.report_id).map(d => {
    const r = reports.find(item => item.id === d.report_id);
    return check(`listing.${d.kind}.${d.fmt}`, 'hard', Boolean(r) && r.sha256 === d.sha256 && r.kind === d.kind && r.fmt === d.fmt,
      r ? `listed ${r.kind}/${r.fmt} ${r.sha256}` : 'report not listed on the encounter');
  });
}

function summarize(enc) {
  const points = Array.from(enc.revision?.text || '');
  return {
    title: enc.title, state: enc.state,
    revision: enc.revision && { id: enc.revision.id, number: enc.revision.number, kind: enc.revision.kind, text_sha256: enc.revision.text_sha256, characters: points.length, extraction: enc.revision.extraction, source_file: enc.revision.source_file },
    context: Object.fromEntries(Object.entries(enc.context?.facts || {}).map(([k, f]) => [k, { value: f.value, origin: f.origin }])),
    families: (enc.routing?.families || []).map(f => ({ family: f.family, status: f.status, supported: f.supported, missing: f.missing, facts: (f.facts || []).map(x => ({ name: x.name, value: x.value, origin: x.origin })), mention_statuses: (f.mentions || []).map(m => m.status) })),
    proposals: proposalsOf(enc).map(p => ({ id: p.id, code: p.code, bucket: p.bucket, family: p.family, status: p.status, decision_state: p.decision_state, evidence: (p.evidence || []).length, exact_evidence: exactSpans(p, points).length, allowed_actions: p.allowed_actions })),
    clarifications: (enc.clarifications || []).map(c => ({ fact: c.fact, scope: c.scope, family: c.family, state: c.state })),
    provider_runs: (enc.provider_runs || []).map(r => ({ provider: r.provider, mode: r.mode, state: r.state, http_status: r.http_status, usage: r.usage, usage_basis: r.usage_basis, reused_from: r.reused_from, latency_ms: r.latency_ms, purpose: r.purpose, scope_items: r.scope_items, request_sha256: r.request_sha256, member_date_hold: isMemberDateHold(r) })),
    user_values: enc.context?.user_values || {},
    readiness: enc.readiness,
  };
}

function documentResult(record) {
  return record.error || record.assertions.some(a => a.status === 'fail') ? 'fail' : 'pass';
}

// --- files ------------------------------------------------------------------------------

function readJson(file, what) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    throw new UsageError(`cannot read ${what} ${file}: ${error.message}`);
  }
}

function loadCredentials(file) {
  const creds = readJson(file, 'credentials');
  if (typeof creds.username !== 'string' || !creds.username || typeof creds.password !== 'string' || !creds.password) {
    throw new UsageError(`credentials file ${file} must hold a non-empty "username" and "password"`);
  }
  const mode = fs.statSync(file).mode & 0o077;
  return { username: creds.username, password: creds.password, groupOrOtherReadable: mode !== 0 };
}

function loadInputs(opts) {
  const manifest = readJson(opts.manifest, 'manifest');
  const generated = readJson(path.join(opts.docs, 'generated.json'), 'generated index');
  const manifestSha = sha256(fs.readFileSync(opts.manifest));
  if (generated.manifest_sha256 !== manifestSha) {
    throw new UsageError(`${opts.docs} was generated from a different manifest (${generated.manifest_sha256} != ${manifestSha}); regenerate it`);
  }
  const known = new Set(manifest.documents.map(d => d.id));
  const unknown = (opts.only || []).filter(id => !known.has(id));
  if (unknown.length) throw new UsageError(`unknown document ids: ${unknown.join(', ')}`);
  const selected = manifest.documents.filter(d => !opts.only || opts.only.includes(d.id));
  const problems = [...new Set(selected.flatMap(doc => planProblems(doc, manifest.review_notes || {})))];
  if (problems.length) throw new UsageError(`the manifest cannot be carried out as written: ${problems.join('; ')}`);
  const documents = selected.map(doc => {
    const file = path.join(opts.docs, doc.delivery.file);
    const data = fs.readFileSync(file);
    const listed = generated.documents.find(g => g.id === doc.id);
    if (!listed || listed.sha256 !== sha256(data)) throw new UsageError(`${file} does not match generated.json; regenerate the documents`);
    const sourceText = fs.readFileSync(path.join(path.dirname(opts.manifest), doc.source), 'utf8');
    return { doc, file, data, sourceText, delivery: { format: doc.delivery.format, file: doc.delivery.file, sha256: listed.sha256, size: data.length } };
  });
  return { manifest, manifestSha, documents };
}

// --- browser steps --------------------------------------------------------------------------

async function fetchEncounter(page, base, id) {
  const response = await page.request.get(`${base}/api/encounters/${id}`, { headers: { Accept: 'application/json' }, timeout: UI_TIMEOUT_MS });
  if (!response.ok()) throw new Error(`GET /api/encounters/${id} answered HTTP ${response.status()}`);
  return response.json();
}

async function login(page, base, creds) {
  await page.goto(`${base}/login/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.fill('input[name="username"]', creds.username);
  await page.fill('input[name="password"]', creds.password);
  await page.click('form.login-form button[type="submit"]');
  const outcome = await Promise.race([
    settle(page.waitForURL(url => !new URL(url).pathname.startsWith('/login'), { timeout: UI_TIMEOUT_MS })).then(() => 'in'),
    settle(page.locator('.form-error').first().waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS })).then(() => 'refused'),
  ]).catch(() => 'timeout');
  if (outcome !== 'in') {
    const error = await page.locator('.form-error').first().textContent({ timeout: 1000 }).catch(() => '');
    throw new Error(`sign-in failed: ${collapse(error) || 'still on the sign-in page'}`);
  }
  const response = await page.request.get(`${base}/api/session`, { headers: { Accept: 'application/json' } });
  if (!response.ok()) throw new Error(`GET /api/session answered HTTP ${response.status()}`);
  return response.json();
}

function sessionProblems(session, opts) {
  const problems = [];
  if (session.user?.actor_kind !== 'agent') problems.push(`the account is a ${session.user?.actor_kind} account; decisions must be recorded as agent review`);
  if (session.can_review !== true) problems.push('the account cannot review in this workspace');
  if (session.synthetic_only !== true) problems.push('the workspace does not report synthetic_only');
  if (session.provider_mode === 'disabled') problems.push('provider_mode is disabled, so no proposals would be produced');
  if (session.provider_mode === 'live' && !opts.allowLiveProvider) problems.push('provider_mode is live: each new document may make a provider request with real usage; re-run with --allow-live-provider to accept');
  return problems;
}

async function uploadDocument(page, base, item, timings) {
  const { doc, file, delivery } = item;
  await page.getByRole('button', { name: /new document/i }).first().click({ timeout: UI_TIMEOUT_MS });
  await page.locator('#uploadDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  if (delivery.format === 'paste') {
    await page.click('#pasteToggle');
    await page.fill('#pasteText', item.data.toString('utf8'));
  } else {
    await page.setInputFiles('#uploadFile', file);
    await page.locator('#selectedFile').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  }
  await page.fill('#serviceDate', doc.upload?.service_date || '');
  await page.check('#syntheticAttestation');
  const created = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === '/api/encounters', { timeout: 120000 }));
  timings.upload_submitted_at = isoNow();
  await page.click('#startReview');
  const response = await created;
  const body = await response.json().catch(() => ({}));
  if (response.status() !== 201 || !body.id) throw new Error(`upload answered HTTP ${response.status()}: ${body.error || 'no id'}`);
  timings.encounter_created_at = isoNow();
  return body.id;
}

// Read-only polling: a failed GET is recorded and polled again (at most MAX_POLL_ERRORS in a row);
// nothing is ever re-submitted.
async function waitForProcessing(page, base, id, deadlineAt, history) {
  let errors = 0;
  for (;;) {
    let enc;
    try {
      enc = await fetchEncounter(page, base, id);
      errors = 0;
    } catch (error) {
      errors += 1;
      history.push({ at: isoNow(), error: String(error.message || error) });
      if (errors >= MAX_POLL_ERRORS || Date.now() + POLL_MS > deadlineAt) throw error;
      await page.waitForTimeout(POLL_MS);
      continue;
    }
    const last = history.filter(h => !h.error).pop();
    if (!last || last.state !== enc.state || last.busy !== Boolean(enc.pipeline?.busy)) {
      history.push({ at: isoNow(), state: enc.state, busy: Boolean(enc.pipeline?.busy) });
    }
    if (!enc.pipeline?.busy && enc.state !== 'processing') return { enc, timedOut: false };
    if (Date.now() + POLL_MS > deadlineAt) return { enc, timedOut: true };
    await page.waitForTimeout(POLL_MS);
  }
}

async function waitForReviewScreen(page) {
  await page.waitForFunction(() => document.querySelector('.review-layout') && !document.querySelector('.progress-card'), null, { timeout: UI_TIMEOUT_MS });
}

async function readDom(page) {
  const marks = await page.$$eval('.evidence-mark', els => els.map(el => ({ keys: (el.dataset.keys || el.dataset.evidence || '').split(' ').filter(Boolean), text: el.textContent })));
  const cards = await page.$$eval('article.code-card', els => els.map(el => ({
    id: el.id,
    badge: (el.querySelector('.code-card-top .status')?.textContent || '').trim(),
    insight: (el.querySelector('.review-insight')?.textContent || '').replace(/\s+/g, ' ').trim(),
    unlocated: el.querySelectorAll('.evidence-chip.unlocated').length,
  })));
  // Excluded and alternative candidates are listed outside the code cards; a decided one shows an undo button.
  const candidates = await page.$$eval('button[data-decision="revoke"]', els => els.filter(el => !el.closest('article.code-card')).map(el => ({
    proposal: el.dataset.proposal,
    text: (el.closest('.check-item')?.textContent || '').replace(/\s+/g, ' ').trim(),
  })));
  return { marks, cards, candidates };
}

async function decide(page, encounterId, decision) {
  const record = { ...decision, http_status: null, decision_id: null, error: null, at: isoNow() };
  const button = page.locator(`button[data-decision="${decision.action}"][data-proposal="${decision.proposal_id}"]`);
  if (await button.count() === 0) return { ...record, error: `no ${decision.action} button for ${decision.code}` };
  await button.first().click({ timeout: UI_TIMEOUT_MS });
  await page.locator('#reviewDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  if (decision.action === 'approve') await page.check('#reviewAcknowledgement');
  await page.fill('#reviewNote', decision.note);
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${encounterId}/decisions`, { timeout: UI_TIMEOUT_MS }));
  await page.click('#saveReview');
  const response = await posted;
  const body = await response.json().catch(() => ({}));
  record.http_status = response.status();
  record.decision_id = body.id || null;
  record.reviewer_kind = body.reviewer_kind || null;
  if (record.http_status !== 201) return { ...record, error: body.error || `HTTP ${record.http_status}` };
  await page.locator('#reviewDialog').waitFor({ state: 'hidden', timeout: UI_TIMEOUT_MS });
  const shown = await page.waitForFunction(([id, action]) => {
    if (action === 'confirm') {  // an excluded candidate has no card: its undo button appears once confirmed
      return Boolean(document.querySelector(`button[data-decision="revoke"][data-proposal="${id}"]`));
    }
    const badge = document.querySelector(`[id="card-${id}"] .code-card-top .status`);
    const text = badge ? badge.textContent.trim() : '';
    return action === 'approve' ? /^Approved/.test(text) : text === 'Rejected';
  }, [decision.proposal_id, decision.action], { timeout: UI_TIMEOUT_MS }).then(() => true, () => false);
  return { ...record, ui_updated: shown };
}

// One ask, through the screen's own button: never repeated, never stopped, never reconciled here. Processing is then
// awaited by read-only polling; an unknown outcome is recorded for the operator to reconcile.
async function askSecondReview(page, base, id, enc, deadlineAt, history) {
  const offered = enc.second_review || null;
  const out = { offered, asked_at: null, http_status: null, error: null, timed_out: false, after: null };
  if (!(offered?.available === true && offered?.can_request === true)) return { ...out, error: `not offered: ${offered?.reason || 'no unresolved item to ask about'}` };
  const button = page.locator('button[data-action="second-review"]');
  const count = await button.count();
  if (count !== 1) return { ...out, error: `expected one "Ask the provider once more" button, found ${count}` };
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${id}/second-review`, { timeout: UI_TIMEOUT_MS }));
  out.asked_at = isoNow();
  await button.click({ timeout: UI_TIMEOUT_MS });
  const response = await posted;
  const body = await response.json().catch(() => ({}));
  out.http_status = response.status();
  if (out.http_status !== 201) return { ...out, error: body.error || `HTTP ${out.http_status}` };
  const { enc: after, timedOut } = await waitForProcessing(page, base, id, deadlineAt, history);
  return { ...out, after, timed_out: timedOut };
}

// The screen's own context form: Edit context -> the service date field -> Save context, with the setting and billing
// fields as the form fills them. Returns the request it sent and its answer, or that it sent none (the screen refuses a
// save that changes nothing, with a toast).
async function submitContextForm(page, id, value) {
  const out = { buttons: 0, prefilled: null, posted: null, http_status: null, context_id: null, error: null, toast: null };
  const button = page.locator('button[data-action="edit-context"]');
  out.buttons = await button.count();
  if (out.buttons !== 1) return { ...out, error: `expected one "Edit context" button, found ${out.buttons}` };
  await button.click({ timeout: UI_TIMEOUT_MS });
  await page.locator('#contextDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  out.prefilled = { service_date: await page.inputValue('#contextServiceDate'), setting: await page.inputValue('#contextSetting'),
                    billing_context: await page.inputValue('#contextBilling') };
  await page.fill('#contextServiceDate', value);
  const target = `/api/encounters/${id}/context`;
  const requested = settle(page.waitForRequest(r => r.method() === 'POST' && pathnameOf(r.url()) === target, { timeout: UI_TIMEOUT_MS }));
  const closed = settle(page.locator('#contextDialog').waitFor({ state: 'hidden', timeout: UI_TIMEOUT_MS }));
  await page.click('#saveContext');
  // A save that sends closes the dialog only once answered; a refused one closes it at once and sends nothing.
  const first = await Promise.race([requested.then(request => ({ request }), () => ({})), closed.then(() => ({ closed: true }), () => ({}))]);
  const request = first.request || (first.closed
    ? await Promise.race([requested.catch(() => null), page.waitForTimeout(1500).then(() => null)]) : null);
  if (!request) {
    out.toast = collapse(await page.locator('#toast').textContent({ timeout: 1000 }).catch(() => '') || '');
    if (!first.closed) out.error = 'the form neither sent a request nor closed';
    return out;
  }
  try {
    out.posted = request.postDataJSON();
  } catch {
    out.posted = null;
  }
  const response = await request.response();
  out.http_status = response ? response.status() : null;
  const body = response ? await response.json().catch(() => ({})) : {};
  if (out.http_status !== 201) {
    const shown = await page.locator('#contextError').textContent({ timeout: 1000 }).catch(() => '');
    out.error = body.error || collapse(shown || '') || `HTTP ${out.http_status}`;
    await page.keyboard.press('Escape');
    return out;
  }
  out.context_id = body.context_id || null;
  await closed.catch(() => {});
  return out;
}

// review_plan.context_edit: one save through the form, its processing awaited by read-only polling; then the same values
// saved again. The reloaded form holds the saved values and refuses that save without sending it, so it is sent as a
// stale page or a repeated request would send it: through the page's own api() client, with the body the form sent.
async function editContext(page, base, id, plan, deadlineAt, history) {
  const value = plan.clear_member_date ? '' : plan.service_date;
  const out = { asked_at: isoNow(), form: null, posted: null, http_status: null, error: null, timed_out: false, after: null,
    identical: { via: null, form_posted: null, form_toast: null, http_status: null, error: null, timed_out: false }, settled: null };
  const form = await submitContextForm(page, id, value);
  out.form = { buttons: form.buttons, prefilled: form.prefilled, context_id: form.context_id };
  Object.assign(out, { posted: form.posted, http_status: form.http_status, error: form.error || (form.http_status === null ? `the form sent no request (it said ${JSON.stringify(form.toast)})` : null) });
  if (form.http_status !== 201) return out;
  const first = await waitForProcessing(page, base, id, deadlineAt, history);
  out.after = first.enc;
  if (first.timedOut) return { ...out, timed_out: true };

  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForReviewScreen(page);
  const again = await submitContextForm(page, id, value);
  out.identical.form_posted = again.http_status !== null;
  out.identical.form_toast = again.toast;
  if (again.error && again.http_status === null) out.identical.error = again.error;
  if (out.identical.form_posted) {
    Object.assign(out.identical, { via: 'form', http_status: again.http_status, error: again.error });
  } else if (!again.error) {
    const body = form.posted || { service_date: value, setting: form.prefilled?.setting || '', billing_context: form.prefilled?.billing_context || '' };
    const target = `/api/encounters/${id}/context`;
    const answered = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === target, { timeout: UI_TIMEOUT_MS }));
    const failure = await page.evaluate(async ([encounterId, json]) => {
      try {
        await api(`/api/encounters/${encodeURIComponent(encounterId)}/context`, { method: 'POST', json });  // eslint-disable-line no-undef
        return null;
      } catch (error) {
        return String((error && error.message) || error);
      }
    }, [id, body]);
    const response = await answered.catch(() => null);
    Object.assign(out.identical, { via: 'api', http_status: response ? response.status() : null, error: failure });
  }
  if (out.identical.http_status === 201) {
    const second = await waitForProcessing(page, base, id, deadlineAt, history);
    out.identical_view = second.enc;  // snapshot only: a view still processing is never judged as settled
    out.settled = second.timedOut ? null : second.enc;
    out.identical.timed_out = second.timedOut;
  }
  await page.reload({ waitUntil: 'domcontentloaded' });
  return out;
}

async function openExport(page) {
  if (await page.locator('#exportDialog[open]').count()) return;
  await page.locator('.review-heading [data-action="export"]').first().click({ timeout: UI_TIMEOUT_MS });
  await page.locator('#exportDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
}

async function downloadReport(page, base, encounterId, kind, fmt, docDir, outDir) {
  const record = { kind, fmt, offered: false, error: null };
  await openExport(page);
  const option = page.locator(`#exportOptions button.export-option[data-export-kind="${kind}"][data-export-fmt="${fmt}"]`);
  if (await option.count() === 0) return { ...record, error: 'the export dialog does not offer this report' };
  record.offered = true;
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${encounterId}/reports`, { timeout: UI_TIMEOUT_MS }));
  const downloaded = settle(page.waitForEvent('download', { timeout: 60000 }));
  await option.first().click({ timeout: UI_TIMEOUT_MS });
  const response = await posted;
  const body = await response.json().catch(() => ({}));
  Object.assign(record, { http_status: response.status(), report_id: body.id || null, filename: body.filename || null, api_sha256: body.sha256 || null });
  if (record.http_status !== 201) return { ...record, error: body.error || `HTTP ${record.http_status}` };
  const download = await downloaded;
  const failure = await download.failure();
  if (failure) return { ...record, error: `download failed: ${failure}` };
  const name = `${kind}-${fmt}-${safeName(download.suggestedFilename())}`;
  const target = path.join(docDir, name);
  await download.saveAs(target);
  const bytes = fs.readFileSync(target);
  const again = await page.request.get(`${base}${body.download_url}`, { timeout: UI_TIMEOUT_MS });
  Object.assign(record, {
    suggested_filename: download.suggestedFilename(), path: path.relative(outDir, target), size: bytes.length, sha256: sha256(bytes),
    refetch_status: again.status(), refetch_sha256: sha256(await again.body()), header_sha256: again.headers()['x-content-sha256'] || null,
  });
  return record;
}

async function screenshots(page, docDir, outDir) {
  const shots = [];
  for (const [name, size] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(size);
    await page.waitForTimeout(300);
    const file = path.join(docDir, `review-${name}-${size.width}x${size.height}.png`);
    await page.screenshot({ path: file, fullPage: true });
    shots.push({ viewport: name, ...size, path: path.relative(outDir, file) });
  }
  await page.setViewportSize(VIEWPORTS.desktop);
  return shots;
}

function saveSnapshot(record, docDir, outDir, name, enc) {
  const file = path.join(docDir, `api-${name.replace(/_/g, '-')}.json`);
  fs.writeFileSync(file, `${JSON.stringify(enc, null, 2)}\n`);
  record.api_snapshots[name] = path.relative(outDir, file);
}

async function verifyDocument(page, opts, manifest, item, sink) {
  const { doc } = item;
  const docDir = path.join(opts.out, doc.id);
  fs.mkdirSync(docDir, { recursive: true });
  const started = Date.now();
  const record = {
    id: doc.id, title: doc.title, delivery: item.delivery, encounter_id: null, review_url: null,
    timings: { started_at: isoNow() }, state_history: [], summary: null, decisions: [], designated_rejection: null,
    downloads: [], reviewed_withheld: null, screenshots: [], api_snapshots: {}, assertions: [], console_errors: sink.splice(0),
    error: null, result: null,
  };
  const add = items => record.assertions.push(...items);
  try {
    await page.goto(`${opts.baseUrl}/`, { waitUntil: 'domcontentloaded' });
    let id;
    if (opts.encounter) {  // attached: nothing is uploaded
      id = opts.encounter;
      record.attached = true;
      record.timings.encounter_created_at = record.timings.attached_at = isoNow();
      await page.goto(`${opts.baseUrl}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
    } else {
      id = await uploadDocument(page, opts.baseUrl, item, record.timings);
    }
    record.encounter_id = id;
    await page.waitForURL(url => new URL(url).hash === `#doc/${id}`, { timeout: UI_TIMEOUT_MS });
    record.review_url = page.url();
    const { enc, timedOut } = await waitForProcessing(page, opts.baseUrl, id, started + opts.deadlineSeconds * 1000, record.state_history);
    record.timings.processing_done_at = isoNow();
    record.timings.processing_seconds = (Date.parse(record.timings.processing_done_at) - Date.parse(record.timings.encounter_created_at)) / 1000;
    saveSnapshot(record, docDir, opts.out, 'after_processing', enc);
    if (timedOut) throw new Error(`processing did not finish within ${opts.deadlineSeconds}s (state ${enc.state}); no Stop was issued and nothing is retried`);
    const foreign = record.attached ? attachedProblems(enc, item) : [];
    if (foreign.length) throw new Error(`refusing to act on encounter ${id}: ${foreign.join('; ')}`);
    const editPlan = contextEditPlan(doc);
    // the edit is made only on a precondition seen to hold; until then nothing is requested, so coding is judged after it
    const unmet = editPlan ? contextEditPreconditions(enc, doc.upload?.service_date || null, editPlan).filter(a => a.status === 'fail') : [];
    const editing = Boolean(editPlan) && unmet.length === 0;
    add(checkPipeline(enc));
    add(checkExtraction(doc.expected_extraction || {}, enc, item.delivery, item.sourceText));
    if (!record.attached) add(checkUploadDate(doc.upload?.service_date, enc));
    add(checkContext(doc.expected_context, enc));
    add(checkRouting(doc.expected_routing || {}, enc));
    add(checkEvidenceExact(enc));
    if (editing) {
      add([skip('must_not_code', 'judged after the context edit'), skip('incomplete', 'judged after the context edit')]);
    } else {
      add(checkMustNotCode(doc.must_not_code, enc));
    }
    add(checkClarifications(doc.expected_clarifications, enc));
    if (!editing) add(checkIncomplete(doc.incomplete_services, enc));
    add([await checkOriginal(page, opts.baseUrl, id, item.delivery)]);
    await waitForReviewScreen(page).catch(async () => {
      add([check('ui.refreshed_itself', 'soft', false, 'the review did not leave the processing view on its own within 30 s; reloaded')]);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await waitForReviewScreen(page);
    });
    const before = await readDom(page);
    add(checkEvidenceMarks(enc, before.marks, before.cards));

    let current = enc;
    if (editPlan && !editing) {  // nothing is saved, so nothing is sent, on a precondition the walk did not see hold
      const edit = { http_status: null, error: `not made: ${unmet.map(a => a.id).join(' and ')} failed, so the edit has nothing verified to ${editPlan.answers_question ? 'answer' : 'settle'}` };
      record.context_edit = { plan: doc.review_plan.context_edit, ...(editPlan.answers_question ? { answers_question: true } : {}), http_status: null, error: edit.error };
      add(checkContextEdit(enc, null, null, editPlan, edit, doc.upload?.service_date || null));
    } else if (editing) {
      if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; the context was not edited');
      const edit = await editContext(page, opts.baseUrl, id, editPlan, started + opts.deadlineSeconds * 1000, record.state_history);
      // the date named before the edit (a clear) or the edited one: what the request must carry, never read back from it
      const wanted = edit.after ? (editPlan.clear_member_date ? documentedServiceDate(enc, editPlan).date : editPlan.service_date) : null;
      record.context_edit = {
        plan: doc.review_plan.context_edit, ...(editPlan.answers_question ? { answers_question: true } : {}),
        asked_at: edit.asked_at, form: edit.form, posted: edit.posted, http_status: edit.http_status,
        error: edit.error, timed_out: edit.timed_out, identical: edit.identical,
        request_date: edit.after ? wanted : null,
        expected_request_sha256: edit.after ? primaryRequestSha256(edit.after.revision?.text || '', wanted) : null,
      };
      if (edit.after) saveSnapshot(record, docDir, opts.out, 'after_context_edit', edit.after);
      if (edit.identical_view) saveSnapshot(record, docDir, opts.out, 'after_identical_context_save', edit.identical_view);
      add(checkContextEdit(enc, edit.timed_out ? null : edit.after, edit.settled, editPlan, edit, doc.upload?.service_date || null));
      if (edit.timed_out || edit.identical.timed_out) throw new Error(`processing after the context ${edit.timed_out ? 'edit' : 'save made again'} did not finish within ${opts.deadlineSeconds}s; no Stop was issued, nothing is retried and no decision was recorded`);
      if (edit.after) {
        current = edit.settled || edit.after;
        await waitForReviewScreen(page).catch(async () => {
          await page.reload({ waitUntil: 'domcontentloaded' });
          await waitForReviewScreen(page);
        });
        const dom = await readDom(page);
        add([...checkPipeline(current), ...checkEvidenceExact(current), ...checkMustNotCode(doc.must_not_code, current),
          ...checkIncomplete(doc.incomplete_services, current), ...checkEvidenceMarks(current, dom.marks, dom.cards)]
          .map(a => ({ ...a, id: `after_context_edit.${a.id}` })));
      }
    }
    const secondPlan = secondReviewPlan(doc);
    if (secondPlan) {
      if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; the second review was not asked for');
      const ask = await askSecondReview(page, opts.baseUrl, id, current, started + opts.deadlineSeconds * 1000, record.state_history);
      record.second_review = { offered: ask.offered, asked_at: ask.asked_at, http_status: ask.http_status, error: ask.error, timed_out: ask.timed_out };
      if (ask.after) saveSnapshot(record, docDir, opts.out, 'after_second_review', ask.after);
      add(checkSecondReview(current, ask.after, ask));
      if (ask.timed_out) throw new Error(`the second review did not finish within ${opts.deadlineSeconds}s (state ${ask.after?.state}); no Stop was issued, nothing is retried and no decision was recorded`);
      if (ask.after) {
        current = ask.after;
        await waitForReviewScreen(page).catch(async () => {
          await page.reload({ waitUntil: 'domcontentloaded' });
          await waitForReviewScreen(page);
        });
        const dom = await readDom(page);
        add([...checkEvidenceExact(current), ...checkEvidenceMarks(current, dom.marks, dom.cards)]
          .map(a => ({ ...a, id: `after_second_review.${a.id}` })));
      }
    }
    const plan = planDecisions(current, doc.review_plan, manifest.review_notes, { mustNotCode: doc.must_not_code, noAutoApprove: opts.noAutoApprove });
    if (plan.second_review_held.length) add([check('decisions.second_review_held', 'soft', false, `left undecided (not in review_plan.second_review.approve_codes): ${plan.second_review_held.join(', ')}`)]);
    if (plan.must_not_code_held.length) add([check('decisions.must_not_code_held', 'soft', false, `left undecided, never approved (the manifest's must_not_code lists their family): ${plan.must_not_code_held.join(', ')}`)]);
    if (plan.plan_conflicts.length) add([check('decisions.plan_conflict', 'hard', false, `approve_codes names a code of a family must_not_code lists; not approved: ${plan.plan_conflicts.join(', ')}`)]);
    if (plan.not_in_approve_codes.length) add([check('decisions.not_in_approve_codes', 'soft', false, `left undecided (not named in review_plan.approve_codes${opts.noAutoApprove ? '; --no-auto-approve' : ''}): ${plan.not_in_approve_codes.join(', ')}`)]);
    if (plan.approve_codes_unmatched.length) add([check('decisions.approve_codes_unmatched', 'soft', false, `named in review_plan.approve_codes but not a ready selected code: ${plan.approve_codes_unmatched.join(', ')}`)]);
    record.designated_rejection = plan.decisions.find(d => d.designated)?.code || null;
    if (plan.designated_missing) add([check('decisions.designated_rejection', 'soft', false, `no ready selected proposal in ${doc.review_plan.reject.family} to reject`)]);
    const confirmations = planConfirmations(current, doc.must_not_code, manifest.review_notes);
    for (const decision of [...plan.decisions, ...confirmations]) record.decisions.push(await decide(page, id, decision));
    record.timings.decisions_done_at = isoNow();
    add(record.decisions.map(d => check(`decision.${d.action}.${d.code}`, 'hard', d.http_status === 201 && !d.error, d.error || `HTTP ${d.http_status}${d.ui_updated === false ? '; the card did not update within 30 s' : ''}`)));
    const afterDecisions = await fetchEncounter(page, opts.baseUrl, id);
    saveSnapshot(record, docDir, opts.out, 'after_decisions', afterDecisions);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForReviewScreen(page);
    record.timings.reload_done_at = isoNow();
    const reloaded = await fetchEncounter(page, opts.baseUrl, id);
    saveSnapshot(record, docDir, opts.out, 'after_reload', reloaded);
    const after = await readDom(page);
    add(checkPersistence(record.decisions, current, afterDecisions, reloaded));
    add(checkDecisionDom(record.decisions, reloaded, after.cards, after.candidates));
    const labels = checkDecisionLabels(record.decisions, reloaded, doc.must_not_code);
    record.decision_labels = labels.labels;
    add(labels.checks);
    add(checkReadiness(reloaded));

    const readiness = reloaded.readiness || {};
    for (const want of expectedDownloads(readiness)) {
      const [kind, fmt] = want.split('.');
      record.downloads.push(await downloadReport(page, opts.baseUrl, id, kind, fmt, docDir, opts.out));
    }
    if (readiness.reviewed !== true) {
      let offered = 0;
      if (reloaded.assessment) {
        await openExport(page);
        offered = await page.locator('#exportOptions button.export-option[data-export-kind="reviewed"]').count();
      }
      record.reviewed_withheld = { offered: offered > 0, export_available: Boolean(reloaded.assessment), blockers: readiness.blockers || [] };
    }
    await page.keyboard.press('Escape');
    record.timings.downloads_done_at = isoNow();
    add(checkDownloads(record.downloads, readiness, record.reviewed_withheld));
    const final = await fetchEncounter(page, opts.baseUrl, id);
    saveSnapshot(record, docDir, opts.out, 'final', final);
    add(checkListing(record.downloads, final));
    record.summary = summarize(final);
    record.screenshots = await screenshots(page, docDir, opts.out);
  } catch (error) {
    record.error = String(error && error.message || error).split('\n')[0];
    record.screenshots = await screenshots(page, docDir, opts.out).catch(() => []);
  }
  record.console_errors.push(...sink.splice(0));
  record.assertions.push(check('console.errors', 'soft', record.console_errors.length === 0, `${record.console_errors.length} console/page error(s)`));
  record.timings.finished_at = isoNow();
  record.timings.total_seconds = (Date.now() - started) / 1000;
  record.result = documentResult(record);
  return record;
}

async function checkOriginal(page, base, id, delivery) {
  const response = await page.request.get(`${base}/api/encounters/${id}/original`, { timeout: UI_TIMEOUT_MS });
  if (delivery.format === 'paste') return check('original.preserved', 'hard', response.status() === 404, `pasted text: GET original answered ${response.status()} (404 expected)`);
  const digest = response.ok() ? sha256(await response.body()) : null;
  return check('original.preserved', 'hard', digest === delivery.sha256, `GET original answered ${response.status()}; sha256 ${digest} vs uploaded ${delivery.sha256}`);
}

function writeEvidence(file, evidence) {
  fs.writeFileSync(file, `${JSON.stringify(evidence, null, 2)}\n`);
}

async function main(argv) {
  let opts;
  let inputs;
  let creds;
  try {
    opts = parseArgs(argv);
    if (/pw:(api|\*)|(^|,)\*($|,)/.test(process.env.DEBUG || '')) throw new UsageError('refusing to run with DEBUG=pw:api: Playwright would log the password');
    inputs = loadInputs(opts);
    creds = loadCredentials(opts.credentials);
    if (fs.existsSync(path.join(opts.out, 'evidence.json'))) throw new UsageError(`${opts.out} already holds evidence.json; use a fresh --out directory`);
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`verify_browser: ${error.message}\n${USAGE}\n`);
    return 2;
  }
  fs.mkdirSync(opts.out, { recursive: true });
  const evidenceFile = path.join(opts.out, 'evidence.json');
  const { chromium } = require(PLAYWRIGHT);
  const evidence = {
    schema: EVIDENCE_SCHEMA, run_id: `verify-${isoNow().replace(/[-:.]/g, '')}-${crypto.randomBytes(4).toString('hex')}`,
    started_at: isoNow(), finished_at: null, base_url: opts.baseUrl, synthetic_only: true,
    manifest: { path: path.resolve(opts.manifest), sha256: inputs.manifestSha }, docs_dir: path.resolve(opts.docs),
    options: { only: opts.only, deadline_seconds: opts.deadlineSeconds, stop_on_failure: opts.stopOnFailure, allow_live_provider: opts.allowLiveProvider,
               encounter: opts.encounter || null, no_auto_approve: opts.noAutoApprove },
    environment: { node: process.version, playwright: require(path.join(PLAYWRIGHT, 'package.json')).version, browser: null },
    credentials: { username: creds.username, file_group_or_other_readable: creds.groupOrOtherReadable },
    session: null, documents: [], summary: null, run_error: null,
  };
  const browser = await chromium.launch({ headless: true });
  evidence.environment.browser = browser.version();
  const context = await browser.newContext({ acceptDownloads: true, viewport: VIEWPORTS.desktop });
  const page = await context.newPage();
  page.setDefaultTimeout(UI_TIMEOUT_MS);
  const sink = [];
  page.on('console', msg => { if (msg.type() === 'error') sink.push({ at: isoNow(), kind: 'console', text: msg.text().slice(0, 500) }); });
  page.on('pageerror', error => sink.push({ at: isoNow(), kind: 'pageerror', text: String(error.message).slice(0, 500) }));
  page.on('requestfailed', request => {
    const failure = request.failure()?.errorText || '';
    if (!/ERR_ABORTED/.test(failure)) sink.push({ at: isoNow(), kind: 'requestfailed', text: `${request.method()} ${pathnameOf(request.url())}: ${failure}` });
  });
  page.on('response', response => {
    if (response.status() >= 400 && pathnameOf(response.url()).startsWith('/api/')) sink.push({ at: isoNow(), kind: 'http', text: `${response.request().method()} ${pathnameOf(response.url())} -> ${response.status()}` });
  });
  try {
    evidence.session = await login(page, opts.baseUrl, creds);
    const problems = sessionProblems(evidence.session, opts);
    if (problems.length) throw new Error(`refusing to upload: ${problems.join('; ')}`);
    for (const item of inputs.documents) {
      if (stopRequested(opts.out)) {
        evidence.run_error = 'stopped: a STOP file is present in the evidence directory; no further upload was made';
        process.stdout.write(`${evidence.run_error}\n`);
        break;
      }
      process.stdout.write(`${item.doc.id} ${item.delivery.format} ... `);
      const record = await verifyDocument(page, opts, inputs.manifest, item, sink);
      evidence.documents.push(record);
      writeEvidence(evidenceFile, evidence);
      const failed = record.assertions.filter(a => a.status === 'fail').map(a => a.id);
      process.stdout.write(`${record.result}${record.error ? ` (${record.error})` : ''}${failed.length ? ` [${failed.join(', ')}]` : ''}\n`);
      if (record.result === 'fail' && opts.stopOnFailure) break;
    }
  } catch (error) {
    evidence.run_error = String(error && error.message || error).split('\n')[0];
    process.stdout.write(`run stopped: ${evidence.run_error}\n`);
  } finally {
    await browser.close();
    evidence.finished_at = isoNow();
    const passed = evidence.documents.filter(d => d.result === 'pass').length;
    evidence.summary = { selected: inputs.documents.length, verified: evidence.documents.length, passed, failed: evidence.documents.length - passed };
    writeEvidence(evidenceFile, evidence);
  }
  process.stdout.write(`evidence: ${evidenceFile}\n${JSON.stringify(evidence.summary)}\n`);
  const complete = !evidence.run_error && evidence.summary.verified === evidence.summary.selected;
  return complete && evidence.summary.failed === 0 ? 0 : 1;
}

function stopRequested(outDir) {
  return fs.existsSync(path.join(outDir, 'STOP'));
}

module.exports = {
  stopRequested, parseArgs, UsageError, cpSlice, safeName, sessionProblems, checkPipeline, checkExtraction, checkContext, checkRouting,
  checkEvidenceExact, checkMustNotCode, checkClarifications, checkIncomplete, planDecisions, planConfirmations, checkReadiness,
  checkPersistence, checkEvidenceMarks, checkDecisionDom, expectedDownloads, checkDownloads, checkListing, summarize,
  documentResult, readDom, secondReviewPlan, checkSecondReview, attachedProblems, sentRun,
  contextEditPlan, isMemberDateHold, contextRequestDate, primaryRequestSha256, checkUploadDate, checkContextEdit, contextEditPreconditions,
  checkDecisionLabels, planProblems, MEMBER_DATE_HOLD_MESSAGE, PROVIDER_SYSTEMS,
  documentedServiceDate, quotedDates, USER_CONFLICT_NOTE, USER_ELSEWHERE_NOTE,
  checkQuestionEdit, questionEditPreconditions, openDateQuestions, identicalSaveChecks, verifyDocument,
};

if (require.main === module) {
  main(process.argv.slice(2)).then(code => { process.exitCode = code; }, error => {
    process.stderr.write(`verify_browser: ${error && error.stack || error}\n`);
    process.exitCode = 1;
  });
}
