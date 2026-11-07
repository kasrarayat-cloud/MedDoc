#!/usr/bin/env node
'use strict';
/*
 * Browser verification of a running CPT Studio (the deployed site or a local one) with the synthetic documents from
 * ops/verification, through the CUSTOMER interface of the 2026-11-03 core repair (cpt-studio/CORE-UX-DESIGN.md
 * sections 5-8: the codes-first result list, "Why this code?", the "A few details needed" panel, the compact progress
 * panel and the customer reports), with a second, PLATFORM-OPERATOR session beside it for everything a customer must
 * no longer be shown.
 *
 *   node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials agent.json \
 *     --operator-credentials ops-agent.json --docs OUT_FROM_GENERATE --manifest ops/verification/manifest.json \
 *     --out EVIDENCE_DIR [--only gi-01,gi-03] [--deadline-seconds 300] [--stop-on-failure] [--allow-live-provider]
 *     [--encounter ENCOUNTER_ID] [--no-auto-approve] [--expect-harness] [--no-reload-while-processing]
 *   node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --password-file PASSWORD_FILE --username NAME \
 *     --operator-credentials ops-agent.json --acceptance-reviewer --docs ... --manifest ... --out ...
 *
 * Two sessions, never mixed:
 *   the CUSTOMER session (--credentials, or --password-file with --username) drives the ordinary page in a browser
 *     context of its own: upload, progress, details, decisions, downloads. Everything it is served is scanned.
 *   the OPERATOR session (--operator-credentials FILE: a private JSON file, top-level "username" and "password", mode
 *     0600 or stricter; required) signs in through the same login page in a SEPARATE browser context and reads only
 *     /ops/: GET /ops/api/encounters/<id> (today's full encounter view: provider runs, harness participants, models,
 *     usage, request hashes, reuse, jobs), /ops/api/encounters/<id>/trace and /ops/api/encounters/<id>/reports. Every
 *     check that needs those facts reads them there, never from the customer API: the provenance checks, the request
 *     hashes that prove which date a request carried, and every "no duplicate paid request" proof (reload, Stop and
 *     Resume, a details save made twice). The walk refuses to start unless the operator session answers
 *     /ops/api/encounters (a positive control: a broken instrument and an empty surface read the same).
 *
 * Per document (agent mode, the default: every decision is the agent account's, labelled agent-executed synthetic
 * review): New document -> upload the file or paste the text -> tick the synthetic attestation -> submit; the upload
 * acknowledgement (.upload-ack) must be on screen when the page first asks for the new encounter; while it processes,
 * the progress panel is sampled (its phase and steps equal what the page was served, elapsed time shown, no percentage
 * or ETA, Stop offered while busy, no running animation once failed or stopped) and the page is reloaded once (same
 * encounter, same jobs, no new encounter and no duplicate provider request: --no-reload-while-processing skips it);
 * review_plan.stop_and_resume stops it through the panel's Stop and resumes it (nothing sent while stopped, the same
 * jobs kept, no duplicate request). Then: extraction, context, routing, exact evidence, clarifications, must-not-code
 * and incomplete services against the manifest, on the OPERATOR view; the customer encounter against the customer
 * contract (ops/verification/customer-contract.json: every key listed, nothing else) and against the operator view
 * (the same document text, the codes in the contract's order, each with the status, sub label and actions the operator
 * view states the page shows for it - serializers.customer_codes, never re-derived - units, modifiers and
 * decisions, every "Why this code?" quotation an exact slice of the document and a passage CPT Studio holds as support
 * for that code); the page against the DOM contract (ol.result-list rows, .status labels, "Why this code?", only the
 * allowed actions, the checks panel, the details panel); then review_plan.details / review_plan.context_edit answered
 * through the details panel in one save (stored as member context with attribution, never a revision, asked once,
 * kept after a reload; the old date proofs still hold, read from the operator view); the decisions through the
 * review dialog (a modifier only where review_plan.modifiers names one, never prefilled, never both 59 and XS); a
 * reload and every decision checked as persisted (operator and customer views, and the row); the suggested-codes
 * (draft) and approved downloads as real browser downloads, each re-fetched, each compared with the operator listing's
 * sha256 and the operator's stored bytes, the approved option withheld with its blockers listed until the review is
 * complete. One decision and one download are made at 390x844; both viewports are measured (no horizontal scroll;
 * rows, actions and the details panel on screen and operable) and photographed.
 *
 * Negative scans (ops/verification/customer-denylist.json, the same list ops/verify_downloads.py and
 * ops/scan_customer.py read): every customer API body and header the page or the walk received, every error body,
 * every DOM text node and attribute (aria-*, data-*, title, alt, ...), every toast or alert, every downloaded file and
 * the served page and bundle - for provider and model names, model ids, usage/token/credit wording, request and
 * response ids, sha256-like hex, trace links, retrieval logs, rule ids, orchestration wording, forbidden JSON keys, and
 * every identifier the operator view holds for this encounter (run ids, request hashes, models, check ids ...). A
 * string that quotes the document itself is not scanned. Direct-URL authorization: every /ops/ URL answers 404 to the
 * customer session (GET, and POST with a body the operator views would refuse, so a broken gate creates nothing) and
 * to nobody signed in never 200; the old /api/encounters/<id>/trace answers 404 to everyone; the operator reads them.
 *
 * Manifest review_plan keys read here (besides reject, approve_codes, context_edit and second_review, as before):
 *   details: [{"fact": F, "value": V, "code"?: C}]   answers made through the details panel in one save: V is a date
 *       (YYYY-MM-DD), "use_document", "not_documented", "cannot_confirm" or a choice value; "code" picks the row whose
 *       affects lists C when one fact is asked for more than one code
 *   modifiers: {"45385": "XS"}   the modifier chosen in the review dialog when that code is approved: "59" or "XS"
 *   stop_and_resume: true        Stop the document while it processes, check the stopped state, then Resume it
 *   addendum: {"fact": F, "code"?: C, "text": T, "expect_ready"?: [codes]}   the physician's addendum, added after the
 *       details save through the panel's own control (a saved answer of the row withdrawn first by "Change this answer",
 *       since the panel offers the addendum only on an open row): a new revision, read by the providers again, with no
 *       earlier answer applied to it and expect_ready READY on it (completion repair 2026-11-06)
 * and the document-level key expected_no_em_questions: true (no office E/M question may be asked: no separate E/M
 * service is documented), and expected_codes: {"ready": [...], "not_ready": [...], "units": {code: n}, "complete":
 * [families]} (completion repair 2026-11-06): written from sealed expectations, judged hard on the first assessment and,
 * for not_ready, again after an addendum (checkExpectedCodes). review_plan.second_review is not carried out: it spends one bounded paid request, and the
 * walk holds the contract's `recheck` offer to its keys only (session decision (n), 2026-11-04).
 *
 * The document-level key expected_failure: "extraction_failed" (or another failed state: FAILED_STATES) walks a document
 * that must fail before anything is sent (directive section 5, "failure ... states work"): its failed panel against what
 * the page was served (the plain error in its notice with the error's action, no step active, nothing animating, the
 * leave note), the operator state, no code, no provider request, the original still served, both viewports, the scans and
 * the direct-URL probes. Such a document has no review_plan: there is nothing to decide.
 *
 * --acceptance-reviewer (CPT Studio GI interpretation 63) is kept as before: a human reviewer account, approvals only,
 * each recorded as that reviewer's. It records HUMAN approvals: the 2026-11-03 directive labels every test approval an
 * agent-executed synthetic review, so its walks use agent mode.
 *
 * Nothing is retried. A failure is recorded and the run continues with the next document (or stops with
 * --stop-on-failure). A file named STOP in EVIDENCE_DIR stops the run before the next upload, details save, Stop or
 * decision. Everything is written to EVIDENCE_DIR/evidence.json (schema cpt-studio-browser-evidence@2), which
 * ops/verify_downloads.py then re-checks file by file against the operator snapshots it names (or --api-dir). No
 * password is ever printed or written. Exit 0 when every document and run check passed, 1 when anything failed, 2 on a
 * usage error before any upload.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const PLAYWRIGHT = process.env.CPT_VERIFY_PLAYWRIGHT
  || '/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/browser-deps/node_modules/playwright';
const EVIDENCE_SCHEMA = 'cpt-studio-browser-evidence@2';
const DONE_STATES = new Set(['ready_for_review', 'needs_clarification', 'no_codes', 'reviewed']);
const PERFORMED = new Set(['performed', 'incomplete']);
const DECIDED = new Set(['approved', 'rejected']);
const DECISION_STATES = { approve: 'approved', reject: 'rejected', confirm: 'exclusion_confirmed' };
const VIEWPORTS = { desktop: { width: 1440, height: 1000 }, mobile: { width: 390, height: 844 } };
const UI_TIMEOUT_MS = 30000;
// Decision (l) (2026-11-03; studio/client_contract.py): a direct customer API call names the current page build, as
// the page itself does (static/studio/app.js api()); a call without it is answered 409 client_outdated.
const CLIENT_HEADERS = { 'X-CPT-Studio-Client': 'customer-2026-11-03' };
const POLL_MS = 2000;
const MAX_POLL_ERRORS = 3;
const INCOMPLETE_SIGNAL = /incomplete|discontinu|reduced|\b5[23]\b/i;
const AGENT_LABEL = 'agent-executed synthetic review';
// Every note the walk writes on a decision says what made it (review_notes are checked before anything is uploaded).
const NOTE_LABEL = /agent-executed synthetic/i;
// --acceptance-reviewer (CPT Studio GI interpretation 63): what every acceptance-test approval's note says, checked in
// review_notes before anything is uploaded and on every decision after the reload.
const ACCEPTANCE_LABEL = 'session-made synthetic acceptance-test approval, not a human review';
const ACCEPTANCE_NOTE_LABEL = new RegExp(ACCEPTANCE_LABEL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
// studio/templates/studio/index.html #reviewNote maxlength: Playwright's fill types into the field, which cuts a longer
// note; the unit tests hold it to the template.
const REVIEW_NOTE_MAX = 600;
// Python's str.strip also strips these, which JavaScript's trim keeps (studio/review.py record_decision strips the note).
const PYTHON_ONLY_SPACE = new Set([0x1c, 0x1d, 0x1e, 0x1f, 0x85]);
// ops/verify_login.py MAX_CREDENTIALS_BYTES: a larger password file is refused.
const MAX_PASSWORD_FILE_BYTES = 64 * 1024;
// The Playwright debug logs that carry a call's parameters or the browser protocol, so a typed password
// (playwright-core: the api call log records fill("<value>"), channel every command, protocol every CDP message,
// server:channel the server's side of the channel).
const PASSWORD_LOGS = ['pw:api', 'pw:channel', 'pw:protocol', 'pw:server:channel'];
const WITHHELD = '[password withheld]';
const USAGE = 'usage: verify_browser.cjs --base-url URL (--credentials FILE | --password-file FILE --username NAME) '
  + '--operator-credentials FILE --docs DIR --manifest FILE --out DIR [--only IDS] [--deadline-seconds N] [--stop-on-failure] '
  + '[--allow-live-provider] [--encounter ID] [--no-auto-approve] [--acceptance-reviewer] [--expect-harness] '
  + '[--no-reload-while-processing]';
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

// --- the customer surface (cpt-studio/CORE-UX-DESIGN.md sections 5-8) ------------------------------------------------
//
// One copy of the customer contract and one denylist, read by this walk, ops/verify_downloads.py and
// ops/scan_customer.py alike (their tests run the same vectors), so the three readers cannot drift apart.
const VERIFICATION_DIR = path.join(__dirname, 'verification');
const CONTRACT = JSON.parse(fs.readFileSync(path.join(VERIFICATION_DIR, 'customer-contract.json'), 'utf8'));
const DENYLIST = JSON.parse(fs.readFileSync(path.join(VERIFICATION_DIR, 'customer-denylist.json'), 'utf8'));
const VOCAB = CONTRACT.vocabulary;
const ISO_TIMESTAMP = new RegExp(CONTRACT.iso_pattern);
const DATE_ONLY = new RegExp(CONTRACT.date_pattern);
const AGENT_SUB_LABEL = VOCAB.agent_sub_label;
const REJECTED_SUB_LABEL = VOCAB.rejected_sub_label;
const DETAILS_HEADING = VOCAB.details_heading;
const NONE_APPROVED_BLOCKER = VOCAB.none_approved_blocker;  // customer_api.NONE_APPROVED (session decision (f))
const CODE_STATUSES = new Set(Object.keys(VOCAB.code_statuses));  // customer_api.STATUS_LABELS
// The customer states and progress phases in which processing has finished and the result can be read.
const CUSTOMER_DONE_STATES = new Set(['awaiting_detail', 'ready', 'reviewed', 'no_codes', 'action_needed']);
const SETTLED_PHASES = new Set(['failed', 'stopped']);
// The served phases whose progress panel shows its steps (CORE-UX-DESIGN 6; directive section 5: the active stage, the
// completed ones and a truthful status while a member waits, must act, or reads why processing ended). The walk's own
// expectation, never read from the page: the page draws every other phase - results ready, a detail asked, a limitation
// - as one compact line with its title and the time it took (app.js PANEL_PHASES), and a page that folded one of these
// phases into that line fails. The 2026-11-05 acceptance walk held the compact line to the whole panel's contract.
const PANEL_PHASES = new Set(['queued', 'processing', 'action_needed', 'failed', 'stopped', 'being_confirmed', 'paused']);
// The compact line says the server's message only where it adds to the title: a detail asked, a limitation.
const COMPACT_MESSAGE_PHASES = new Set(['awaiting_detail', 'partial']);
// The compact line's title for each phase that draws it (app.js PHASE_TITLES): a finished document read under another
// phase's title, or a limitation read as plain "Results ready", is a page saying the wrong thing (refutation, 2026-11-05).
const COMPACT_TITLES = { completed: 'Results ready', awaiting_detail: 'Results ready', partial: 'Results ready, with a limitation' };
// The busy phases whose panel shows the time elapsed (app.js progressTime: an animated phase while busy). A paused
// document's worker is silent (decision (j): never drawn as working) and a date hold being re-checked waits on the
// member, so neither shows a running time (refutation, 2026-11-05: the walk once demanded one of every busy panel).
const ELAPSED_PHASES = new Set(['queued', 'processing']);
// The operator states a document fails in (progress.FAILED_STATES), each read by the customer as failed; the button the
// failed notice offers for each served error action (app.js ERROR_ACTIONS: "Upload a new document", "Resume processing").
const FAILED_STATES = new Set(['extraction_failed', 'processing_failed', 'provider_failed', 'provider_not_run']);
const ERROR_ACTION_BUTTONS = { new_document: 'upload', resume: 'resume' };
// The operator state each customer state is read from (CORE-UX-DESIGN 7; the hold of a member date conflict is the
// customer's action_needed, whatever operator state it records).
const CUSTOMER_STATE_OF = { ready_for_review: 'ready', needs_clarification: 'awaiting_detail', reviewed: 'reviewed',
  no_codes: 'no_codes', stopped: 'stopped', provider_unknown: 'being_confirmed', processing: 'processing',
  provider_failed: 'failed', extraction_failed: 'failed', processing_failed: 'failed', provider_not_run: 'failed' };
// P5's fold of the current revision's jobs into the four customer steps; an assess job is the "checking" step while a
// peer review follows it, the "preparing" step otherwise (the final assessment).
const STEP_OF_KIND = { extract: 'reading', analyze: 'identifying', predict: 'checking', astra: 'checking', fable: 'checking',
  astra_peer: 'checking', fable_peer: 'checking', review2: 'checking' };
const PEER_KINDS = new Set(['astra_peer', 'fable_peer']);
// The customer step states a job state may be drawn as (queued may read as the active step or a waiting one).
// An outcome left unknown is being confirmed (CORE-UX-DESIGN 6): its step may read failed, waiting or active, never done.
const STEP_STATES_FOR = { done: ['done', 'skipped'], active: ['active', 'waiting'], failed: ['failed'], unknown: ['failed', 'waiting', 'active'],
  stopped: ['stopped', 'failed'], none: ['not_started', 'waiting', 'skipped'] };
// An office E/M question (directive section 4: none when no separate E/M service is documented).
const EM_FACTS = new Set(['patient_status', 'em_basis', 'em_level', 'em_time', 'visit_level', 'em_code']);
const EM_WORDING = /\b(?:office visit|office-visit|evaluation and management|E\/M|new or established|new\/established)\b/i;
// A percentage or an ETA in the progress panel (directive section 5: never without reliable measurements).
const PERCENT_OR_ETA = /\d\s*%|\bETA\b|\b(?:about|approximately|around|roughly|~)\s*\d+\s*(?:s|secs?|seconds?|mins?|minutes?|h|hours?)\b|\b\d+\s*(?:s|secs?|seconds?|mins?|minutes?|h|hours?)\s+(?:left|remaining|to go)\b|\b(?:estimated|remaining)\s+(?:time|wait)\b|\btime\s+(?:left|remaining)\b/i;
const MODIFIER_CHOICES = new Set(['59', 'XS']);
const MODIFIER_OPTIONS = ['', '59', 'XS'];  // select#reviewModifier (CORE-UX-DESIGN 8): none, 59 or XS; never both, never prefilled
const DETAIL_VALUES = new Set(['use_document', 'not_documented', 'cannot_confirm']);
const PLAN_KEYS = new Set(['reject', 'approve_codes', 'context_edit', 'second_review', 'details', 'modifiers', 'stop_and_resume', 'addendum']);
// A modifier-shaped token a row might show although none is assigned.
const MODIFIER_TOKEN = /\b(?:59|X[ESPU]|25|33|PT|5[23]|7[6-9])\b/;
// The /ops/ surface (CORE-UX-DESIGN 5): every URL answers 404 to anyone who is not a platform operator.
const OPS_GET_PATHS = id => ['/ops/', '/ops/assets/ops.js', '/ops/api/encounters', `/ops/api/encounters/${id}`,
  `/ops/api/encounters/${id}/trace`, `/ops/api/encounters/${id}/reports`];
const OPS_POST_PATHS = id => [`/ops/api/encounters/${id}/reports`, `/ops/api/encounters/${id}/reconcile`];
// A body the operator views refuse (an unknown report kind, a run that is no run): a gate that answered anything but
// 404 to a customer would still create nothing.
const OPS_POST_BODY = { kind: '__verify_unknown_kind__', fmt: '__none__', run: '__not_a_run__' };
const REMOVED_PATHS = id => [`/api/encounters/${id}/trace`];
// Response headers that carry no customer-facing wording (security policy, cookies, caching, dates).
const UNSCANNED_HEADERS = new Set(['set-cookie', 'date', 'etag', 'last-modified', 'content-length', 'content-security-policy',
  'content-security-policy-report-only', 'strict-transport-security', 'permissions-policy', 'report-to', 'nel', 'expires',
  'cache-control', 'vary', 'connection', 'keep-alive', 'transfer-encoding', 'content-encoding', 'accept-ranges', 'age']);
const MAX_PROGRESS_SAMPLES = 8;
const QUIET_SECONDS_WHILE_STOPPED = 6;
const CSRF_COOKIE = 'cptstudio_csrf';  // cptstudio/settings.py CSRF_COOKIE_NAME; the page sends it as X-CSRFToken

// --- small pure helpers ----------------------------------------------------------------

class UsageError extends Error {}

function parseArgs(argv) {
  const flags = new Set(['stop-on-failure', 'allow-live-provider', 'no-auto-approve', 'acceptance-reviewer', 'expect-harness',
    'no-reload-while-processing']);
  const values = new Set(['base-url', 'credentials', 'password-file', 'username', 'docs', 'manifest', 'out', 'only',
    'deadline-seconds', 'encounter', 'operator-credentials']);
  const opts = { only: null, deadlineSeconds: 300, stopOnFailure: false, allowLiveProvider: false, noAutoApprove: false,
    acceptanceReviewer: false, expectHarness: false, noReloadWhileProcessing: false };
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
  for (const name of ['baseUrl', 'credentials', 'operatorCredentials', 'docs', 'manifest', 'out']) {
    if (name === 'credentials' && opts.passwordFile !== undefined) continue;  // a password file signs in instead
    if (!opts[name]) {
      throw new UsageError(`missing --${name.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`)}${name === 'credentials' ? ' (or --password-file with --username)' : ''}`);
    }
  }
  // ops/verify_login.py's two ways to sign in: a credentials file, or a password file for the account --username names
  if (opts.passwordFile !== undefined) {
    if (opts.credentials !== undefined) throw new UsageError('--credentials and --password-file are mutually exclusive: give one way to sign in');
    if (!String(opts.username ?? '').trim()) throw new UsageError('--password-file needs --username, the account it signs in');
  } else if (opts.username !== undefined) {
    throw new UsageError('--username goes with --password-file; a --credentials file names its own account');
  }
  if (opts.acceptanceReviewer) {
    // the reviewer's password is read only as a private password file, never through the credentials reader
    if (opts.passwordFile === undefined) throw new UsageError('--acceptance-reviewer signs the reviewer in with --password-file and --username, not a --credentials file');
    opts.noAutoApprove = true;  // implied: nothing is approved that review_plan.approve_codes does not name
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

// Completion repair (2026-11-06, item 7: "check omitted supported services and unsupported additions"): the document-level
// key expected_codes {"ready": [codes], "not_ready": [codes], "units": {code: n}, "complete": [families]}, written from the
// sealed expectations, judged HARD: each code of ready is a selected READY proposal (an omitted supported service fails);
// no code of not_ready is (an unsupported addition fails); a code of units is READY at most once, with exactly that many
// units; no selected proposal of a family in complete carries an incompleteness signal (a failing check or a modifier
// consideration that reads incomplete, reduced, discontinued, 52 or 53). Read on the first assessment, and after an
// addendum (prefix) for the not_ready codes its expect_ready does not name.
function checkExpectedCodes(expected, enc, prefix = 'codes') {
  if (!expected) return [];
  const live = proposalsOf(enc).filter(p => p.bucket === 'selected' && !isExcluded(p));
  const ready = code => live.filter(p => p.code === code && p.status === 'ready');
  const shown = code => proposalsOf(enc).filter(p => p.code === code).map(p => `${p.bucket}/${p.status}`).join(', ') || 'not proposed';
  const out = [];
  for (const code of expected.ready || []) out.push(check(`${prefix}.ready.${code}`, 'hard', ready(code).length > 0, `${code}: ${shown(code)}`));
  for (const code of expected.not_ready || []) out.push(check(`${prefix}.not_ready.${code}`, 'hard', ready(code).length === 0, `${code}: ${shown(code)}`));
  for (const [code, units] of Object.entries(expected.units || {})) {
    const rows = ready(code);
    out.push(check(`${prefix}.units.${code}`, 'hard', rows.length <= 1 && rows.every(p => p.units === units),
      `${rows.length} READY proposal(s) of ${code}, units ${JSON.stringify(rows.map(p => p.units))} (expected at most one, with ${units} unit(s))`));
  }
  for (const family of expected.complete || []) {
    const flagged = live.filter(p => p.family === family
      && ((p.checks || []).some(c => c.status !== 'pass' && INCOMPLETE_SIGNAL.test(`${c.id} ${c.label} ${c.detail}`))
        || (p.modifier_considerations || []).some(m => INCOMPLETE_SIGNAL.test(m))));
    out.push(check(`${prefix}.complete.${family}`, 'hard', flagged.length === 0,
      flagged.length ? `incompleteness signalled on ${flagged.map(p => p.code).join(', ')}` : `no incompleteness signal in ${family}`));
  }
  return out;
}

// An expected fact and the open questions that ask it: the engine asks whether an act was performed as
// 'performed_status', or as 'conflict:<act>' when two of its passages disagree about it (engine: an uncertain reconcile
// match with a conflict), which asks the same fact (completion repair 2026-11-06, for expectations written blind).
function asksFact(question, fact) {
  return question.fact === fact || (fact === 'performed_status' && typeof question.fact === 'string' && question.fact.startsWith('conflict:'));
}

function checkClarifications(expected, enc) {
  const open = (enc.clarifications || []).filter(c => c.state === 'open');
  const out = (expected || []).map(({ fact, scope_in: scopes }) => {
    const any = open.filter(c => asksFact(c, fact));
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
// canReview: the walking member's own permissions (the customer view's permissions.can_review): the actions planned are
// the ones the server accepts from that member (serverActions), never the operator view's own allowed_actions - the
// operator account reads with no membership and is allowed none (refutation round 2, L3-5).
function planConfirmations(enc, mustNotCode, notes, canReview = true) {
  const families = new Set((mustNotCode || []).map(item => item.family));
  return proposalsOf(enc).filter(p => p.bucket === 'excluded' && p.reinstatable && p.decision_state === 'undecided'
    && (serverActions(p, canReview) || []).includes('confirm') && families.has(p.family))
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
// takes a code the list names. options.acceptanceReviewer: approvals only, of the codes review_plan.approve_codes names
// (implying the explicit list); no designated rejection, and no code a second review added is decided (second_review_held),
// whatever review_plan.second_review.approve_codes says. options.canReview: the walking member's own permissions; the
// actions planned are the ones the server accepts from that member (serverActions), never the operator view's own.
function planDecisions(enc, reviewPlan, notes, options = {}) {
  const acceptance = Boolean(options.acceptanceReviewer);
  const canReview = options.canReview !== false;
  const accepted = p => serverActions(p, canReview) || [];  // a view that does not say: nothing is planned
  const approveSecond = new Set(acceptance ? [] : (reviewPlan?.second_review?.approve_codes || []).map(String));
  const listed = Array.isArray(reviewPlan?.approve_codes) ? reviewPlan.approve_codes.map(String) : null;
  const explicit = acceptance || Boolean(options.noAutoApprove) || listed !== null;
  const named = new Set(listed || []);
  const mustNot = new Set((options.mustNotCode || []).map(item => item.family));
  const ready = proposalsOf(enc).filter(p => p.bucket === 'selected' && p.status === 'ready' && p.decision_state === 'undecided'
    && accepted(p).includes('approve') && (!fromSecondReview(p) || approveSecond.has(p.code)));
  const namedPrimary = p => explicit && !fromSecondReview(p) && named.has(p.code);
  const rule = acceptance ? null : reviewPlan?.reject;
  let designated = null;
  if (rule) {
    const family = ready.filter(p => p.family === rule.family && accepted(p).includes('reject') && !namedPrimary(p));
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
    if (fromSecondReview(p)) {
      return `${code} (second review: ${acceptance ? 'the acceptance reviewer decides no code a second review added' : 'needs review_plan.second_review.approve_codes'})`;
    }
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

// --acceptance-reviewer: every decision this run made, as the reloaded encounter records it - an approval, the signed-in
// reviewer's (``account``: their label, reviewer_kind human), with the note the walk wrote kept verbatim and saying it
// is a session-made synthetic acceptance-test approval; and none approved a code of a family must_not_code lists. The
// acknowledgement the app stored and the code card's badge and decision line are recorded as the app holds and shows
// them - never judged against a text of the walk's own.
function checkAcceptanceDecisions(made, enc, mustNotCode, account, cards = []) {
  const history = enc?.decisions?.history || [];
  const mustNot = new Set((mustNotCode || []).map(item => item.family));
  const familyOf = d => d.family || proposalsOf(enc).find(p => p.id === d.proposal_id)?.family;
  const label = account?.label;
  const recorded = made.filter(d => d.http_status === 201);
  const labels = recorded.map(d => {
    const entry = history.find(h => (d.decision_id ? h.id === d.decision_id : h.proposal_id === d.proposal_id && h.action === d.action && !h.invalidated)) || null;
    const card = cards.find(c => c.id === `card-${d.proposal_id}`) || null;
    return {
      code: d.code, action: d.action, decision_id: d.decision_id || null, recorded: Boolean(entry), approval: d.action === 'approve',
      human: entry?.reviewer_kind === 'human', reviewer: entry ? entry.reviewer ?? null : null,
      reviewer_is_account: Boolean(entry) && typeof label === 'string' && Boolean(label) && entry.reviewer === label,
      note_kept: Boolean(entry) && entry.note === d.note, note_labelled: Boolean(entry) && ACCEPTANCE_NOTE_LABEL.test(entry.note || ''),
      acknowledgement: entry ? entry.acknowledgement ?? null : null,
      acknowledgement_is_session_attestation: Boolean(entry) && typeof account?.acknowledgement === 'string'
        && entry.acknowledgement === account.acknowledgement,
      card_badge: card ? card.badge : null, card_insight: card ? card.insight : null,
    };
  });
  const required = ['recorded', 'approval', 'human', 'reviewer_is_account', 'note_kept', 'note_labelled'];
  const wrong = labels.filter(l => required.some(key => !l[key]));
  const approved = recorded.filter(d => d.action === 'approve' && mustNot.has(familyOf(d)));
  return {
    labels,
    checks: [
      check('decisions.labelled', 'hard', wrong.length === 0, !labels.length ? 'no decision was made'
        : wrong.length ? `not recorded as the reviewer's labelled acceptance-test approval: ${wrong.map(l => `${l.code} ${l.action} (${required.filter(key => !l[key]).join(', ')})`).join('; ')}`
          : `${labels.length} approval(s), each recorded as ${JSON.stringify(label)}'s (human) with its note kept verbatim, saying "${ACCEPTANCE_LABEL}"`),
      check('decisions.never_approved_must_not_code', 'hard', approved.length === 0, approved.length
        ? `approved a code of a must_not_code family: ${approved.map(d => `${d.code} (${familyOf(d)})`).join(', ')}`
        : `no approval of a code in ${mustNot.size ? [...mustNot].join(', ') : 'a must_not_code family (none listed)'}`),
    ],
  };
}

// Why a note the walk writes through the review screen would not be recorded exactly as written (null when it would):
// app.js submitReview trims it and record_decision strips it, the note field takes REVIEW_NOTE_MAX characters and reads
// a carriage return as a line feed, and the API refuses a NUL or a lone surrogate (api.py UNSTORABLE).
function noteNotVerbatim(note) {
  const units = [...note].map(char => char.codePointAt(0));
  if (note !== note.trim() || PYTHON_ONLY_SPACE.has(units[0]) || PYTHON_ONLY_SPACE.has(units[units.length - 1])) {
    return 'it begins or ends with whitespace, which the page trims and the server strips';
  }
  if (note.length > REVIEW_NOTE_MAX) return `it is longer than the ${REVIEW_NOTE_MAX} characters the note field takes`;
  if (note.includes('\r')) return 'it holds a carriage return, which the note field reads as a line feed';
  if (units.some(point => point === 0 || (point >= 0xd800 && point <= 0xdfff))) return 'it holds a NUL or a lone surrogate, which the server refuses';
  return null;
}

// Before any upload: the manifest's plan for a document can be carried out as written, and every note it would write
// says what made the decision. options.acceptanceReviewer: the walk writes approvals only, so the one note it writes,
// review_notes.approve, must say it is a session-made synthetic acceptance-test approval and be one the screen and the
// server keep verbatim.
function planProblems(doc, notes = {}, options = {}) {
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
  // the 2026-11-03 customer flow: details answered through the panel, a modifier per approval, Stop and Resume
  const unknownKeys = Object.keys(plan).filter(key => !PLAN_KEYS.has(key));
  if (unknownKeys.length) problems.push(`${id}: review_plan has an unknown key: ${unknownKeys.join(', ')} (a misspelt plan is never carried out silently)`);
  if (plan.details !== undefined) {
    const details = plan.details;
    const where = `${id}: review_plan.details`;
    if (!Array.isArray(details) || !details.length) problems.push(`${where} must be a non-empty list of {"fact", "value"[, "code"]}`);
    else {
      const seen = new Set();
      for (const [index, item] of details.entries()) {
        const at = `${where}[${index}]`;
        const keys = item && typeof item === 'object' && !Array.isArray(item) ? Object.keys(item) : null;
        if (!keys || keys.some(key => !['fact', 'value', 'code'].includes(key))) problems.push(`${at} must hold only fact, value and code`);
        else if (typeof item.fact !== 'string' || !item.fact.trim() || typeof item.value !== 'string' || !item.value.trim()) problems.push(`${at} needs a non-empty fact and value`);
        else if (item.code !== undefined && (typeof item.code !== 'string' || !item.code.trim())) problems.push(`${at}.code must be a non-empty code`);
        else if (item.fact === 'service_date' && !(item.value === 'use_document' || isoDate(item.value))) problems.push(`${at}: a service date is answered with a YYYY-MM-DD date or "use_document"`);
        else if (item.fact !== 'service_date' && (item.value === 'use_document' || ISO_DATE.test(item.value))) problems.push(`${at}: only the service date is answered with a date or "use_document"`);
        else if (item.fact === 'service_date' && plan.context_edit !== undefined && plan.context_edit !== null) problems.push(`${at}: the service date is review_plan.context_edit's, never answered twice`);
        else if (seen.has(`${item.fact}|${item.code || ''}`)) problems.push(`${at}: ${item.fact}${item.code ? ` for ${item.code}` : ''} is answered twice`);
        if (item && typeof item === 'object') seen.add(`${item.fact}|${item.code || ''}`);
      }
    }
  }
  if (plan.modifiers !== undefined) {
    const modifiers = plan.modifiers;
    if (!modifiers || typeof modifiers !== 'object' || Array.isArray(modifiers) || !Object.keys(modifiers).length
      || Object.entries(modifiers).some(([code, value]) => !code.trim() || !MODIFIER_CHOICES.has(value))) {
      problems.push(`${id}: review_plan.modifiers must map each code to one modifier, "59" or "XS" (never both, never a list)`);
    }
  }
  if (plan.stop_and_resume !== undefined && typeof plan.stop_and_resume !== 'boolean') problems.push(`${id}: review_plan.stop_and_resume must be true or false`);
  if (plan.addendum !== undefined) {
    const add = plan.addendum;
    const where = `${id}: review_plan.addendum`;
    if (!add || typeof add !== 'object' || Array.isArray(add)) problems.push(`${where} must be an object`);
    else {
      if (typeof add.fact !== 'string' || !add.fact) problems.push(`${where}.fact must name the detail the addendum answers`);
      if (typeof add.text !== 'string' || !add.text.trim()) problems.push(`${where}.text must be the physician's addendum text`);
      if (add.code !== undefined && (typeof add.code !== 'string' || !/^\d{5}$/.test(add.code))) problems.push(`${where}.code must be a five-digit code`);
      if (add.expect_ready !== undefined && !(Array.isArray(add.expect_ready) && add.expect_ready.every(c => typeof c === 'string' && /^\d{5}$/.test(c)))) problems.push(`${where}.expect_ready must be a list of five-digit codes`);
      const unknown = Object.keys(add).filter(k => !['fact', 'code', 'text', 'expect_ready'].includes(k));
      if (unknown.length) problems.push(`${where} has an unknown key: ${unknown.join(', ')}`);
    }
  }
  if (doc?.expected_no_em_questions !== undefined && typeof doc.expected_no_em_questions !== 'boolean') problems.push(`${id}: expected_no_em_questions must be true or false`);
  if (doc?.expected_codes !== undefined) {
    const codes = doc.expected_codes;
    const where = `${id}: expected_codes`;
    const listOf = value => Array.isArray(value) && value.every(code => typeof code === 'string' && /^\d{5}$/.test(code)) && new Set(value).size === value.length;
    if (!codes || typeof codes !== 'object' || Array.isArray(codes)) problems.push(`${where} must be an object`);
    else {
      const unknown = Object.keys(codes).filter(key => !['ready', 'not_ready', 'units', 'complete'].includes(key));
      if (unknown.length) problems.push(`${where} has an unknown key: ${unknown.join(', ')}`);
      for (const key of ['ready', 'not_ready']) if (codes[key] !== undefined && !listOf(codes[key])) problems.push(`${where}.${key} must be a list of distinct five-digit codes`);
      const both = (codes.ready || []).filter(code => (codes.not_ready || []).includes(code));
      if (both.length) problems.push(`${where} names ${both.join(', ')} both ready and not_ready`);
      if (codes.units !== undefined && !(codes.units && typeof codes.units === 'object' && !Array.isArray(codes.units)
        && Object.entries(codes.units).every(([code, n]) => /^\d{5}$/.test(code) && Number.isInteger(n) && n > 0))) problems.push(`${where}.units must map five-digit codes to a whole number of units`);
      if (codes.complete !== undefined && !(Array.isArray(codes.complete) && codes.complete.every(f => typeof f === 'string' && /^gi\.[a-z_]+$/.test(f)))) problems.push(`${where}.complete must be a list of families`);
    }
  }
  if (doc?.expected_failure !== undefined) {
    if (!FAILED_STATES.has(doc.expected_failure)) problems.push(`${id}: expected_failure must be one of ${[...FAILED_STATES].join(', ')}`);
    // a document that must fail has nothing to decide, answer, stop or attach: a plan beside it would never be carried out
    if (Object.keys(plan).length) problems.push(`${id}: a document with expected_failure has no review_plan (it would never be carried out)`);
    if (doc.expected_no_em_questions !== undefined) problems.push(`${id}: a document with expected_failure has no questions to expect`);
    if (options.acceptanceReviewer) problems.push(`${id}: expected_failure is walked in agent mode only (an acceptance reviewer only approves)`);
    // the walk of a failed document checks none of these, so a manifest carrying one would read as checked when it is not
    const unwalked = ['expected_extraction', 'expected_context', 'expected_routing', 'must_not_code', 'expected_clarifications',
      'incomplete_services', 'author_expected_cpt', 'expected_codes'].filter(key => doc[key] !== undefined);
    if (unwalked.length) problems.push(`${id}: a document with expected_failure carries ${unwalked.join(', ')}, which its walk never checks`);
  }
  if (options.acceptanceReviewer) {
    if (!(typeof notes.approve === 'string' && ACCEPTANCE_NOTE_LABEL.test(notes.approve))) {
      problems.push(`review_notes approve must say "${ACCEPTANCE_LABEL}" (${id} would write it on every approval)`);
    } else if (noteNotVerbatim(notes.approve)) {
      // an approval cannot be taken back: one whose note the screen or the server would change is not made at all
      problems.push(`review_notes approve could not be kept verbatim through the review screen: ${noteNotVerbatim(notes.approve)}`);
    }
    return problems;
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
  out.push(check('context_edit.request', 'hard', saved(edit?.http_status),
    `the details save answered HTTP ${edit?.http_status ?? 'none'}${edit?.error ? `: ${edit.error}` : ''}; the page sent ${JSON.stringify(edit?.posted ?? null)}`));
  if (!saved(edit?.http_status) || !after) return out;

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
// processing settled, or null): nothing sent or held, every run unchanged (read from the operator view), and - soft -
// only a re-check; and - soft - the details panel shows the answer as saved once the page is reloaded, so it is not
// asked again (editContext sends the second save as a stale page or a repeated request would: straight to the API).
function identicalSaveChecks(after, settled, identical) {
  // --acceptance-reviewer answers the clarification once: the same save is not made again, so nothing is judged of it
  if (identical.skipped) return [skip('context_edit.identical_save', identical.skipped)];
  const out = [];
  let rechecked = null;
  if (!saved(identical.http_status) || !settled) {
    out.push(check('context_edit.identical_save', 'hard', false, `the identical save ${identical.http_status === null || identical.http_status === undefined
      ? 'was not made' : `answered HTTP ${identical.http_status}`}${identical.error ? `: ${identical.error}` : ''}${saved(identical.http_status) ? '; its processing was not seen to settle' : ''}`));
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
  out.push(check('context_edit.panel_shows_saved', 'soft', identical.panel_asks_again === false,
    identical.panel_asks_again === true ? 'after the save and a reload the details panel still asks the answered question, unsaved'
      : identical.panel_asks_again === false ? 'after the save and a reload the details panel does not ask the answered question again'
        : 'the details panel was not read after the save'));
  return out;
}

// A save the API accepted (the context endpoint answers 201; the details endpoint any 2xx).
function saved(status) {
  return Number.isInteger(status) && status >= 200 && status < 300;
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
  out.push(check('context_edit.request', 'hard', saved(edit?.http_status),
    `the details save answered HTTP ${edit?.http_status ?? 'none'}${edit?.error ? `: ${edit.error}` : ''}; the page sent ${JSON.stringify(edit?.posted ?? null)}`));
  if (!saved(edit?.http_status) || !after) return out;

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

// reviewerKind: the actor kind every decision this run made must be recorded with (human under --acceptance-reviewer).
function checkPersistence(decisions, before, after, reloaded, reviewerKind = 'agent') {
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
    const ok = p?.decision_state === want && p.decision?.reviewer_kind === reviewerKind && p.decision?.note === d.note && Boolean(entry);
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

// --- the customer contract (ops/verification/customer-contract.json) ---------------------------------------------------

const SCALARS = {
  string: value => typeof value === 'string', integer: value => Number.isInteger(value),
  number: value => typeof value === 'number' && Number.isFinite(value), boolean: value => typeof value === 'boolean',
  any: () => true, date: value => typeof value === 'string' && DATE_ONLY.test(value),
  iso: value => typeof value === 'string' && ISO_TIMESTAMP.test(value),
};

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function kindOf(value) {
  if (value === undefined) return 'nothing';
  return value === null ? 'null' : Array.isArray(value) ? 'a list' : typeof value === 'object' ? 'an object' : typeof value;
}

// The differences between a value and a contract node (customer-contract.json's node language), each as
// "<where>: <what>"; at most 60. ops/scan_customer.py shape_problems is the same function.
function shapeProblems(value, node, where = '$', out = [], types = CONTRACT.types) {
  if (out.length >= 60) return out;
  if (typeof node === 'string') {
    const nullable = node.endsWith('?');
    const base = nullable ? node.slice(0, -1) : node;
    const test = SCALARS[base];
    if (!test) out.push(`${where}: the contract names an unknown type ${base}`);
    else if (value === null && (nullable || base === 'any')) return out;
    else if (value === undefined || !test(value)) out.push(`${where}: ${kindOf(value)} where the contract has ${node}`);
    return out;
  }
  if (!isObject(node)) {
    out.push(`${where}: the contract node is not understood`);
    return out;
  }
  if (node.ref !== undefined) {
    if (value === null && node.nullable) return out;
    if (!types[node.ref]) {
      out.push(`${where}: the contract names an unknown type ${node.ref}`);
      return out;
    }
    return shapeProblems(value, types[node.ref], where, out, types);
  }
  if (value === null && node.nullable) return out;
  if (Array.isArray(node.enum)) {
    if (!node.enum.includes(value)) out.push(`${where}: ${JSON.stringify(value)} is not one of ${node.enum.join('|')}`);
    return out;
  }
  if (node.items !== undefined) {
    if (!Array.isArray(value)) out.push(`${where}: ${kindOf(value)} where the contract has a list`);
    else value.forEach((item, index) => shapeProblems(item, node.items, `${where}[${index}]`, out, types));
    return out;
  }
  if (node.map !== undefined) {
    if (!isObject(value)) out.push(`${where}: ${kindOf(value)} where the contract has an object`);
    else for (const [key, item] of Object.entries(value)) shapeProblems(item, node.map, `${where}.${key}`, out, types);
    return out;
  }
  if (isObject(node.keys)) {
    if (!isObject(value)) {
      out.push(`${where}: ${kindOf(value)} where the contract has an object`);
      return out;
    }
    for (const key of Object.keys(node.keys)) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) out.push(`${where}.${key}: missing (the contract lists it)`);
      else shapeProblems(value[key], node.keys[key], `${where}.${key}`, out, types);
    }
    for (const key of Object.keys(value)) {
      if (!Object.prototype.hasOwnProperty.call(node.keys, key)) out.push(`${where}.${key}: not in the customer contract`);
    }
    return out;
  }
  out.push(`${where}: the contract node is not understood`);
  return out;
}

// schema: 'encounter' (GET /api/encounters/<id>), 'session' (GET /api/session) or 'list' (GET /api/encounters).
function checkCustomerContract(value, schema = 'encounter', id = 'customer.contract') {
  const problems = shapeProblems(value, CONTRACT[schema]);
  return [check(id, 'hard', problems.length === 0, problems.length
    ? `${problems.length} difference(s) from the customer contract (CORE-UX-DESIGN 7): ${problems.slice(0, 10).join('; ')}`
    : `the ${schema} payload carries every key the contract lists and nothing else, each of its type`,
  problems.length ? { problems } : undefined)];
}

// The words the contract fixes: each state's label, each code status's label, the three checks in order, the four steps
// in order with their labels, and the details rows' controls.
function checkCustomerVocabulary(enc) {
  const problems = [];
  if (VOCAB.states[enc?.state] === undefined) problems.push(`state ${JSON.stringify(enc?.state)}`);
  else if (enc.state_label !== VOCAB.states[enc.state]) problems.push(`state ${enc.state} labelled ${JSON.stringify(enc.state_label)}, not "${VOCAB.states[enc.state]}"`);
  for (const code of Array.isArray(enc?.codes) ? enc.codes : []) {
    if (code?.status_label !== VOCAB.code_statuses[code?.status]) {
      problems.push(`${code?.code} ${code?.status} labelled ${JSON.stringify(code?.status_label)}, not "${VOCAB.code_statuses[code?.status]}"`);
    }
  }
  const checks = (Array.isArray(enc?.checks) ? enc.checks : []).map(item => [item?.key, item?.label]);
  const wantChecks = Object.entries(VOCAB.checks);
  if (JSON.stringify(checks) !== JSON.stringify(wantChecks)) problems.push(`checks ${JSON.stringify(checks)}, not ${JSON.stringify(wantChecks)}`);
  const steps = (Array.isArray(enc?.progress?.steps) ? enc.progress.steps : []).map(item => [item?.key, item?.label]);
  const wantSteps = Object.entries(VOCAB.steps);
  if (JSON.stringify(steps) !== JSON.stringify(wantSteps)) problems.push(`progress steps ${JSON.stringify(steps)}, not ${JSON.stringify(wantSteps)}`);
  for (const detail of Array.isArray(enc?.details_needed) ? enc.details_needed : []) {
    if (detail?.control === 'date' && detail?.fact !== 'service_date') problems.push(`detail ${detail?.id} has a date control for ${detail?.fact}`);
    if (detail?.control === 'confirm' && (detail?.choices || []).length) problems.push(`detail ${detail?.id} is a confirmation with choices: a member never supplies a clinical fact`);
    if (detail?.control === 'confirm' && !(detail?.allow || []).length) problems.push(`detail ${detail?.id} is a confirmation with neither "Not documented" nor "Cannot confirm"`);
  }
  return [check('customer.vocabulary', 'hard', problems.length === 0, problems.length ? problems.join('; ')
    : 'state, code statuses, checks, steps and details controls use the contract\'s words')];
}

// --- the denylist (ops/verification/customer-denylist.json) -------------------------------------------------------------

const PATTERNS = DENYLIST.patterns.map(p => ({ id: p.id, severity: p.severity, surfaces: new Set(p.surfaces), regex: new RegExp(p.source, 'gi') }));
const FORBIDDEN_KEYS = new Set(DENYLIST.forbidden_keys);
const DENY_SHAPE = new RegExp(DENYLIST.deny_value_shape);

// The strings at a dotted path of a value: "a.b[]" takes each element of a.b, a numeric part indexes a list.
function harvest(value, dotted) {
  let nodes = [value];
  for (const part of dotted.split('.')) {
    const each = part.endsWith('[]');
    const key = each ? part.slice(0, -2) : part;
    nodes = nodes.flatMap(node => {
      const next = Array.isArray(node) && /^\d+$/.test(key) ? node[Number(key)] : isObject(node) ? node[key] : undefined;
      if (each) return Array.isArray(next) ? next : [];
      return next === undefined ? [] : [next];
    });
  }
  return nodes.filter(item => typeof item === 'string');
}

// Every identifier the operator view (and its trace) holds for this encounter that a customer surface must never carry:
// run ids, request and response hashes, models, check ids and sources, revision and assessment ids ... - identifier-
// shaped (a digit or . : @ / - in it) and at least deny_value_min_length long, so no plain word is ever one.
function denyValuesFrom(encounter, trace = null) {
  const paths = DENYLIST.deny_value_paths;
  const values = [...paths.encounter.flatMap(p => harvest(encounter, p)), ...(trace ? paths.trace.flatMap(p => harvest(trace, p)) : [])];
  return [...new Set(values.filter(value => value.length >= DENYLIST.deny_value_min_length && DENY_SHAPE.test(value)))];
}

// documentText: the encounter's own text (a string that is a quotation of it is never scanned); denyValues: as above,
// less any the document itself contains; allowed: more strings removed before scanning (the site's own host).
function scanContext({ documentText = '', denyValues = [], allowed = [] } = {}) {
  const text = String(documentText || '');
  return { documentText: text, denyValues: [...new Set(denyValues)].filter(value => value && !text.includes(value)),
    allowed: [...new Set([...DENYLIST.allowed, ...allowed].filter(Boolean))].sort((a, b) => b.length - a.length) };
}

function excerpt(text, at, length) {
  const from = Math.max(0, at - 24);
  return `${from > 0 ? '…' : ''}${text.slice(from, at + length + 24).replace(/\s+/g, ' ')}${at + length + 24 < text.length ? '…' : ''}`;
}

// The hits of one string on one surface: {id, severity, surface, where, match}. A string that is a substring of the
// document text is a quotation of it and is not scanned (bundle text always is).
function scanText(text, ctx, surface, where = '', hits = []) {
  const raw = typeof text === 'string' ? text : String(text ?? '');
  if (!raw.trim()) return hits;
  if (surface !== 'bundle' && ctx.documentText && ctx.documentText.includes(raw)) return hits;
  let cleaned = raw;
  for (const allowed of ctx.allowed) cleaned = cleaned.split(allowed).join(' ');
  for (const pattern of PATTERNS) {
    if (!pattern.surfaces.has(surface)) continue;
    for (const match of cleaned.matchAll(pattern.regex)) {
      hits.push({ id: pattern.id, severity: pattern.severity, surface, where, match: excerpt(cleaned, match.index, match[0].length) });
    }
  }
  if (surface !== 'bundle') {
    for (const value of ctx.denyValues) {
      if (cleaned.includes(value)) hits.push({ id: 'deny_value', severity: 'hard', surface, where, match: `${value.slice(0, 14)}…` });
    }
  }
  return hits;
}

// A JSON value: every string value and every key (a forbidden key is a hit by itself).
function scanJson(value, ctx, where = '$', hits = [], surface = 'json') {
  if (typeof value === 'string') return scanText(value, ctx, surface, where, hits);
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanJson(item, ctx, `${where}[${index}]`, hits, surface));
  } else if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key)) hits.push({ id: 'forbidden_key', severity: 'hard', surface, where: `${where}.${key}`, match: key });
      scanText(key, ctx, surface, `${where}.${key} (key)`, hits);
      scanJson(item, ctx, `${where}.${key}`, hits, surface);
    }
  }
  return hits;
}

// RFC 4180 rows of a CSV text (quoted cells, doubled quotes, CR LF or LF), for the download scan.
function csvRows(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i += 1; } else if (ch === '"') quoted = false; else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i += 1;
      row.push(cell); rows.push(row); row = []; cell = '';
    } else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// A downloaded file, whole: a CSV cell by cell, a TXT line by line, with any quoted passage that is the document's own
// text set aside (a report quotes the document).
function scanFile(text, ctx, name, fmt, hits = []) {
  if (fmt === 'csv') {
    csvRows(text).forEach((row, r) => row.forEach((cell, c) => scanText(cell, ctx, 'file', `${name} row ${r + 1} cell ${c + 1}`, hits)));
    return hits;
  }
  String(text).split(/\r?\n/).forEach((line, index) => {
    let rest = line;
    for (const quoted of line.match(/"[^"]*"/g) || []) {
      if (ctx.documentText.includes(quoted.slice(1, -1))) rest = rest.replace(quoted, '""');
    }
    if (rest.trim() && ctx.documentText.includes(rest.trim())) return;
    scanText(rest, ctx, 'file', `${name} line ${index + 1}`, hits);
  });
  return hits;
}

// The response headers a customer surface carries wording in (security policy, cookies, caching and dates aside).
function scanHeaders(headers, ctx, where, hits = []) {
  for (const [name, value] of Object.entries(headers || {})) {
    if (UNSCANNED_HEADERS.has(name.toLowerCase())) continue;
    scanText(name, ctx, 'header', `${where} header ${name} (name)`, hits);
    scanText(String(value), ctx, 'header', `${where} header ${name}`, hits);
  }
  return hits;
}

function describeHits(hits) {
  const shown = hits.slice(0, 6).map(hit => `${hit.id} at ${hit.where}: ${JSON.stringify(hit.match)}`);
  return `${shown.join('; ')}${hits.length > shown.length ? `; and ${hits.length - shown.length} more` : ''}`;
}

// One surface's hits as checks: hard hits fail it, soft hits (wording a clinician may use) are a warning.
function checkScan(id, hits, what) {
  const hard = hits.filter(hit => hit.severity === 'hard');
  const soft = hits.filter(hit => hit.severity !== 'hard');
  const out = [check(id, 'hard', hard.length === 0, hard.length ? `${hard.length} hit(s) in ${what}: ${describeHits(hard)}`
    : `${what}: no provider, model, usage, id, hash, trace, rule-id or orchestration text`, hard.length ? { hits: hard.slice(0, 40) } : undefined)];
  if (soft.length) out.push(check(`${id}.wording`, 'soft', false, `${soft.length} soft hit(s) in ${what}: ${describeHits(soft)}`, { hits: soft.slice(0, 40) }));
  return out;
}

// --- the customer view against the operator view ------------------------------------------------------------------------

// The codes the customer list must show, in the contract's order (CORE-UX-DESIGN 7): selected and reinstated codes by
// stored position, then the excluded codes a reviewer can still decide (reinstatable, or a confirmed exclusion);
// alternatives only in other_codes. A reinstated code is an excluded one whose current decision is not a confirmation.
// A code the engine excluded by a member's answer (its support records the answer: questions.answered_away, mirrored
// here field for field) stays listed where its selected code was (customer_api.code_rows, completion repair U11). The walk
// round (2026-11-07, finding 6): the list check had predated that case and named the product's own listing a failure.
const UNAVAILABLE_ANSWERS = new Set(['not_documented', 'cannot_confirm']);
function answeredAway(p) {
  const marker = p && isObject(p.support) ? p.support.answered : null;
  return isObject(marker) && UNAVAILABLE_ANSWERS.has(marker.value) && typeof marker.fact === 'string' && marker.fact !== '';
}

function expectedCodeRows(op) {
  const proposals = proposalsOf(op);
  const first = proposals.filter(p => p.bucket === 'selected' || answeredAway(p)
    || (p.bucket === 'excluded' && p.decision && p.decision.action !== 'confirm'));
  const then = proposals.filter(p => p.bucket === 'excluded' && !first.includes(p) && (p.reinstatable === true || p.decision?.action === 'confirm'));
  return [...first, ...then];
}

// What the server shows for proposal p on the customer page, as the operator view states it: the proposal's "customer"
// (serializers.customer_codes - customer_api.code_rows over the review overlay, the very rows the page is served - with
// its status, sub label and reviewer_actions, the actions a member who may review is allowed), or null where the view
// states none, or none in the contract's shape: then nothing is judged against it (cannot verify). The walk judges the
// page against this statement and never re-derives the overlay's rules (refutation round 3, B-02 and B-03: the
// re-derivation read a reinstated code whose needed detail a member answered unavailable - Excluded, revoke only - as
// ready with approve accepted, and one still waiting on that detail - reject and revoke accepted - as revoke only).
function serverCustomer(p) {
  const row = p && typeof p === 'object' ? p.customer : null;
  if (!row || typeof row !== 'object' || !CODE_STATUSES.has(row.status) || typeof row.sub_label !== 'string'
    || !Array.isArray(row.reviewer_actions) || !row.reviewer_actions.every(action => typeof action === 'string')) return null;
  return row;
}

// The customer status of an operator proposal and the sub label it must carry - the server's (serverCustomer), which
// labels an approval agent review exactly when its approver is an agent (customer_api.agent_approval, refutation round
// 2, L3-6) - or null where the operator view does not say.
function expectedCustomerStatus(p) {
  const row = serverCustomer(p);
  return row ? { status: row.status, sub: row.sub_label } : null;
}

function sameInstant(a, b) {
  const x = Date.parse(a);
  const y = Date.parse(b);
  return Number.isFinite(x) && Number.isFinite(y) && Math.floor(x / 1000) === Math.floor(y / 1000);
}

function sameList(a, b) {
  return JSON.stringify(Array.isArray(a) ? a : []) === JSON.stringify(Array.isArray(b) ? b : []);
}

// CPT Studio's located acts by id, from the operator view's recorded reading (assessment.services).
function actIndex(op) {
  const out = new Map();
  const services = op?.assessment?.services?.services;
  for (const service of Array.isArray(services) ? services : []) {
    for (const act of service && Array.isArray(service.acts) ? service.acts : []) {
      if (act && typeof act.id === 'string') out.set(act.id, act);
    }
  }
  return out;
}

// The passages a quotation of the code may be, by the one rule the server quotes a code by - the page's "Why this code?"
// (customer_api._quotes) and the approved export's evidence alike (CORE-UX-DESIGN.md 7: CPT Studio's own located
// passages for the matched act first, then the provider's exact passages only when they support; never a passage that
// does not support, and none for an excluded code); ops/verify_downloads.py allowed_passages is the same rule:
// - support.source only where the support reading recorded it as showing the act (status 'warn': none of the provider's
//   passages does). A 'not_applicable' reading's source passages are the service's own and show no act (refutation
//   round 2, L3-7);
// - the evidence CPT Studio's reading recorded for each act the support record names, while that act is stored
//   'performed' or 'incomplete';
// - the provider's exact passages (context 0, exact) the support reading found supporting, never one it found unrelated.
// Nothing where no support reading was recorded (L3-10: every exact provider passage was accepted). status: the code's
// customer status; an excluded code quotes nothing.
function allowedPassages(p, points, acts = new Map(), status = null) {
  const sliced = span => Boolean(span) && cpSlice(points, span.start, span.end) === span.text;
  const exact = new Map();
  (Array.isArray(p?.evidence) ? p.evidence : []).forEach((span, index) => {
    if (span && span.context_index === 0 && span.exact === true && sliced(span)) exact.set(index, span);
  });
  const support = p?.support && typeof p.support === 'object' ? p.support : {};
  const unrelatedIds = new Set(Array.isArray(support.unrelated) ? support.unrelated.filter(Number.isInteger) : []);
  const unrelated = [...unrelatedIds].sort((a, b) => a - b).filter(index => exact.has(index)).map(index => exact.get(index));
  const reading = typeof support.status === 'string' ? support.status : null;
  // studio/review.py evidence_spans: nothing unless the support reading records the act as shown (SHOWN_SUPPORT)
  if (!['pass', 'warn'].includes(reading) || status === 'excluded') return { allowed: [], unrelated };
  const source = (Array.isArray(support.source) ? support.source : []).filter(sliced);
  const own = [];
  for (const act of Array.isArray(support.acts) ? support.acts : []) {
    const stored = act && typeof act === 'object' ? acts.get(act.id) : undefined;
    if (!stored || !['performed', 'incomplete'].includes(stored.status)) continue;
    for (const span of Array.isArray(stored.evidence) ? stored.evidence : []) if (sliced(span)) own.push(span);
  }
  const cited = (Array.isArray(support.supporting) ? support.supporting : [])
    .filter(index => Number.isInteger(index) && exact.has(index) && !unrelatedIds.has(index)).map(index => exact.get(index));
  return { allowed: [...source, ...own, ...cited], unrelated };
}

// The modifiers the operator view's decision records (none where none was chosen), or null where it does not say - a
// decision with no "modifiers" list (serializers._decision_json served none): never read as none, which passed a
// customer that dropped the reviewer's modifier and failed one that kept it (refutation round 2, L3-3).
function decidedModifiers(decision) {
  if (!decision) return [];
  return Array.isArray(decision.modifiers) ? decision.modifiers : null;
}

// The actions the server accepts from a member on proposal p: the actions the operator view states a member who may
// review is allowed (serverCustomer's reviewer_actions: review.allowed_actions, the rule record_decision enforces and the
// customer page offers by); none from a member who may not review; null where the view does not state them (cannot
// verify). Never the operator view's own allowed_actions, which are the operator's: an operator with no membership
// (ops-agent) is allowed none (studio.operator.ReadOnlyAccess; refutation round 2, L3-5). canReview: the member's own
// permissions.can_review.
function serverActions(p, canReview = true) {
  if (!canReview || !p) return [];
  const row = serverCustomer(p);
  return row ? [...row.reviewer_actions] : null;
}

function pageOf(pages, start, end) {
  const page = (Array.isArray(pages) ? pages : []).find(item => item && start >= item.start && end <= item.end);
  return page ? page.page : null;
}

function checkCustomerVsOperator(cust, op) {
  const out = [];
  const text = typeof op?.revision?.text === 'string' ? op.revision.text : '';
  const points = Array.from(text);
  const doc = cust?.document || {};
  const spans = pages => (Array.isArray(pages) ? pages : []).map(item => [item?.page, item?.start, item?.end]);
  const pagesSame = sameList(spans(doc.pages), spans(op?.revision?.pages));
  out.push(check('customer.document', 'hard', doc.text === text && doc.revision === op?.revision?.number && pagesSame,
    `the customer document is ${doc.text === text ? 'the operator view\'s revision text' : 'NOT the operator view\'s revision text'}; revision ${doc.revision} (operator ${op?.revision?.number}); pages ${pagesSame ? 'equal' : 'differ'}`));
  const codes = Array.isArray(cust?.codes) ? cust.codes : [];
  const wanted = expectedCodeRows(op);
  const byId = new Map(proposalsOf(op).map(p => [p.id, p]));
  const acts = actIndex(op);
  const ids = codes.map(code => code?.id);
  const numbers = codes.map(code => code?.number);
  out.push(check('customer.codes.listed', 'hard', sameList(ids, wanted.map(p => p.id)) && sameList(numbers, codes.map((_, i) => i + 1)),
    `the customer lists ${codes.map(code => `${code?.number}. ${code?.code}`).join(', ') || 'no code'}; the operator view implies ${wanted.map((p, i) => `${i + 1}. ${p.code}`).join(', ') || 'none'}`
      + (codes.some(code => byId.get(code?.id)?.bucket === 'alternative') ? ' (an alternative is listed as a code)' : '')
      + (codes.some(code => !byId.has(code?.id)) ? ' (a code the operator view does not hold)' : '')));
  const statusWrong = [];
  const statusUnknown = [];
  const actionsUnknown = [];
  const unitsWrong = [];
  const unverifiable = [];
  const decisionWrong = [];
  const actionsWrong = [];
  const quotesInexact = [];
  const quotesUnsupported = [];
  const canReview = cust?.permissions?.can_review === true;
  for (const code of codes) {
    const p = byId.get(code?.id);
    if (!p) continue;
    const want = expectedCustomerStatus(p);  // the server's statement of the page (null: the view does not say)
    if (!want) statusUnknown.push(p.code);
    else if (code.status !== want.status) statusWrong.push(`${p.code} ${code.status} (the server shows ${want.status})`);
    else if (code.sub_label !== want.sub) statusWrong.push(`${p.code} sub label ${JSON.stringify(code.sub_label)} (the server shows ${JSON.stringify(want.sub)})`);
    if (code.units !== p.units) unitsWrong.push(`${p.code} ${code.units} (operator ${p.units})`);
    const d = p.decision || null;
    const modifiers = decidedModifiers(d);
    if (modifiers === null) unverifiable.push(`${p.code} (the customer shows ${JSON.stringify(code.modifiers)})`);
    else if (!sameList(code.modifiers, modifiers)) unitsWrong.push(`${p.code} modifiers ${JSON.stringify(code.modifiers)} (operator ${JSON.stringify(modifiers)})`);
    if (!d) {
      if (code.decision !== null) decisionWrong.push(`${p.code} shows a decision the operator view does not hold`);
    } else {
      const shown = code.decision || {};
      const fine = shown.action === d.action && shown.by === d.reviewer && shown.by_kind === d.reviewer_kind && shown.note === d.note
        && (modifiers === null || sameList(shown.modifiers, modifiers)) && (sameInstant(shown.at, d.decided_at) || sameInstant(shown.at, d.created_at));
      if (!fine) decisionWrong.push(`${p.code} ${JSON.stringify({ action: shown.action, by: shown.by, by_kind: shown.by_kind, at: shown.at, modifiers: shown.modifiers })} (operator ${d.action} by ${d.reviewer} (${d.reviewer_kind}) at ${d.decided_at || d.created_at}${modifiers === null ? '' : `, modifiers ${JSON.stringify(modifiers)}`})`);
    }
    const stated = serverActions(p, canReview);
    if (stated === null) actionsUnknown.push(p.code);
    else {
      const accepted = new Set(stated);
      const extra = (code.allowed_actions || []).filter(action => !accepted.has(action));
      if (extra.length) actionsWrong.push(`${p.code} offers ${extra.join(', ')} (the server accepts ${[...accepted].join(', ') || 'none'} from this member)`);
    }
    const { allowed, unrelated } = allowedPassages(p, points, acts, want ? want.status : null);
    for (const q of code.why?.quotes || []) {
      const slice = cpSlice(points, q?.start, q?.end);
      if (q?.exact !== false && slice !== q?.text) quotesInexact.push(`${p.code}[${q?.start}:${q?.end}]`);
      else if (q?.exact !== false && q?.page !== null && q?.page !== undefined && pageOf(op?.revision?.pages, q.start, q.end) !== q.page) {
        quotesInexact.push(`${p.code}[${q.start}:${q.end}] page ${q.page} (the text there is on page ${pageOf(op?.revision?.pages, q.start, q.end)})`);
      }
      const same = span => span.start === q?.start && span.end === q?.end;
      if (unrelated.some(same)) quotesUnsupported.push(`${p.code}[${q?.start}:${q?.end}] is a passage CPT Studio found unrelated`);
      else if (!allowed.some(same)) quotesUnsupported.push(`${p.code}[${q?.start}:${q?.end}] is none of the passages CPT Studio holds as support`);
    }
  }
  const cannot = (codesOf, what) => (codesOf.length ? [`cannot verify: the operator view does not state ${what} for ${codesOf.join(', ')}`] : []);
  out.push(check('customer.codes.status', 'hard', statusWrong.length === 0 && statusUnknown.length === 0,
    [...statusWrong, ...cannot(statusUnknown, 'what the customer page shows (no "customer" status)')].join('; ')
      || `${codes.length} code(s) with the status and sub label the server gives them`));
  out.push(check('customer.codes.units_modifiers', 'hard', unitsWrong.length === 0 && unverifiable.length === 0,
    [...unitsWrong, ...(unverifiable.length ? [`cannot verify: the operator view's decision carries no "modifiers" list for ${unverifiable.join(', ')}`] : [])].join('; ')
      || 'units and decided modifiers as persisted'));
  out.push(check('customer.codes.decision', 'hard', decisionWrong.length === 0, decisionWrong.join('; ') || 'each decision as persisted (action, reviewer, kind, time, note, modifiers)'));
  out.push(check('customer.codes.actions', 'hard', actionsWrong.length === 0 && actionsUnknown.length === 0,
    [...actionsWrong, ...cannot(actionsUnknown, 'the actions the server accepts (no "customer" reviewer_actions)')].join('; ')
      || 'no action the server would not accept is offered'));
  out.push(check('customer.why.exact', 'hard', quotesInexact.length === 0, quotesInexact.length ? `quotations not exact at their offsets: ${quotesInexact.join(', ')}`
    : `${codes.reduce((n, code) => n + (code.why?.quotes || []).length, 0)} quotation(s), each an exact slice of the document on its page`));
  out.push(check('customer.why.supports', 'hard', quotesUnsupported.length === 0, quotesUnsupported.join('; ') || 'every quotation is a passage CPT Studio holds as support for its code'));
  const listedAlternatives = proposalsOf(op).filter(p => p.bucket === 'alternative').map(p => p.code);
  const others = new Set((cust?.other_codes || []).map(item => item?.code));
  out.push(check('customer.other_codes', 'soft', listedAlternatives.every(code => others.has(code)),
    `operator alternatives ${listedAlternatives.join(', ') || 'none'}; customer other codes ${[...others].join(', ') || 'none'}`));
  const fact = op?.context?.facts?.service_date || {};
  const member = op?.context?.user_values?.service_date || null;
  const date = cust?.service_date || {};
  const established = ['document', 'user'].includes(fact.origin) && isoDate(String(fact.value ?? '')) ? String(fact.value) : null;
  const dateOk = (date.value ?? null) === established && Boolean(date.conflict) === (fact.member_conflict === true)
    && (date.entered_value ?? null) === (member || null);
  out.push(check('customer.service_date', 'hard', dateOk,
    `customer value ${JSON.stringify(date.value ?? null)}, conflict ${date.conflict}, entered ${JSON.stringify(date.entered_value ?? null)}; operator ${JSON.stringify(fact.value ?? null)} (${fact.origin}), member conflict ${fact.member_conflict === true}, member value ${JSON.stringify(member)}`));
  // The approved export is the reviewed one, except where nothing is approved: it lists approved codes only, so with
  // none to list it is withheld although the review is complete, and the customer is told why (session decision (f),
  // customer_api.readiness). That difference, and only it, is accepted (refutation round 2, L3-9).
  const readiness = cust?.readiness || {};
  const reviewed = op?.readiness?.reviewed === true;
  const noneApproved = reviewed && !expectedCodeRows(op).some(p => p.decision?.action === 'approve');
  const toldWhy = !noneApproved || (Array.isArray(readiness.blockers) && readiness.blockers.includes(NONE_APPROVED_BLOCKER));
  out.push(check('customer.readiness', 'hard', readiness.draft === (op?.readiness?.draft === true) && readiness.approved === (reviewed && !noneApproved) && toldWhy,
    `customer draft ${readiness.draft}, approved ${readiness.approved}; operator draft ${op?.readiness?.draft}, reviewed ${op?.readiness?.reviewed}`
      + (noneApproved ? `; nothing is approved, so the approved export is withheld${toldWhy ? ' and the customer is told so' : ` but the customer's blockers do not say "${NONE_APPROVED_BLOCKER}"`}` : '')));
  const expectedState = CUSTOMER_STATE_OF[op?.state];
  out.push(check('customer.state_vs_operator', 'soft', !expectedState || cust?.state === expectedState || cust?.state === 'action_needed',
    `customer ${cust?.state}; operator ${op?.state}${expectedState ? ` (read as ${expectedState})` : ''}`));
  out.push(...checkDetailRows(cust, op));
  return out;
}

// Each material question once (directive section 4): no two rows of the same fact, family and codes; each row's codes
// are codes of this encounter; and - soft - every question the operator view holds open is asked.
function checkDetailRows(cust, op) {
  const rows = Array.isArray(cust?.details_needed) ? cust.details_needed : [];
  const seen = new Map();
  const twice = [];
  for (const row of rows) {
    const key = JSON.stringify([row?.fact, row?.family_label, [...(row?.affects || [])].sort()]);
    if (seen.has(key)) twice.push(`${row?.fact} (${row?.family_label}; affects ${(row?.affects || []).join(', ')})`);
    seen.set(key, row);
  }
  const codes = new Set(proposalsOf(op).map(p => p.code));
  const stray = rows.flatMap(row => (row?.affects || []).filter(code => !codes.has(code)).map(code => `${row?.fact} affects ${code}`));
  const open = (op?.clarifications || []).filter(c => c?.state === 'open');
  const asked = new Set(rows.map(row => row?.fact));
  const unasked = [...new Set(open.map(c => c.fact).filter(name => !asked.has(name)))];
  return [
    check('customer.details.asked_once', 'hard', twice.length === 0, twice.length ? `asked more than once: ${twice.join('; ')}` : `${rows.length} detail(s), each asked once`),
    check('customer.details.affects', 'hard', stray.length === 0, stray.join('; ') || 'every detail names codes of this encounter'),
    check('customer.details.covers_open_questions', 'soft', unasked.length === 0, unasked.length
      ? `open in the operator view but not asked: ${unasked.join(', ')}` : `${open.length} open question(s), each asked`),
  ];
}

// No office E/M question when no separate E/M service is documented (manifest expected_no_em_questions).
function checkNoEmQuestions(cust, op) {
  const open = (op?.clarifications || []).filter(c => c?.state === 'open' && c.family === 'gi.office_em');
  const rows = (cust?.details_needed || []).filter(row => EM_FACTS.has(row?.fact) || EM_WORDING.test(`${row?.family_label} ${row?.prompt}`));
  return [check('details.no_em_question', 'hard', open.length === 0 && rows.length === 0, open.length || rows.length
    ? `office E/M asked although no separate E/M service is documented: ${[...open.map(c => `operator ${c.fact} (${c.scope})`), ...rows.map(row => `details ${row.fact}: ${row.prompt}`)].join('; ')}`
    : 'no office E/M question, in the operator view or the details panel')];
}

// --- the customer page (CORE-UX-DESIGN 8) -----------------------------------------------------------------------------
//
// readCustomerDom runs IN THE PAGE (page.evaluate serializes it, so it closes over nothing) and, in the unit tests, over
// a small DOM of the same shape. It reads only the contract's hooks.
function readCustomerDom(root) {
  const doc = root || document;
  const text = el => (el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const attr = (el, name) => (el && typeof el.getAttribute === 'function' ? el.getAttribute(name) : null);
  const all = (el, selector) => (el ? Array.from(el.querySelectorAll(selector)) : []);
  const one = (el, selector) => (el ? el.querySelector(selector) : null);
  const disabled = el => Boolean(el && (el.disabled === true || attr(el, 'disabled') !== null || attr(el, 'aria-disabled') === 'true'));
  const list = one(doc, 'ol.result-list');
  const rows = all(doc, 'ol.result-list > li.result-row').map(li => {
    const status = one(li, '.status');
    const why = one(li, 'details.why-code');
    return {
      id: attr(li, 'id') || '', proposal: attr(li, 'data-proposal'), code: attr(li, 'data-code'), status: attr(li, 'data-status'),
      number: text(one(li, '.result-number')), code_text: text(one(li, '.result-code')), units: text(one(li, '.result-units')),
      modifiers: text(one(li, '.result-modifiers')), status_text: text(status), status_attr: attr(status, 'data-status'),
      sub: text(one(li, '.result-sub')), summary: text(one(li, '.result-summary')),
      why: why ? { summary: text(one(why, 'summary')), open: Boolean(why.open || attr(why, 'open') !== null),
        quotes: all(why, '.why-quote').map(q => ({ start: attr(q, 'data-start'), end: attr(q, 'data-end'), page: attr(q, 'data-page'), text: String(q.textContent || '') })),
        qualifications: all(why, '.why-qualification').map(text) } : null,
      actions: all(li, 'button[data-decision]').map(b => ({ action: attr(b, 'data-decision'), proposal: attr(b, 'data-proposal'), disabled: disabled(b) })),
    };
  });
  const panel = one(doc, 'section.details-panel');
  const details = panel ? {
    heading: text(one(panel, 'h1, h2, h3, h4')),
    rows: all(panel, '.detail-row').map(row => {
      const id = attr(row, 'data-detail');
      const date = one(row, 'input[type="date"][data-detail-input]');
      return {
        id, fact: attr(row, 'data-fact'), date_input: Boolean(date), date_value: date ? (date.value ?? attr(date, 'value')) : null,
        radios: all(row, 'input[type="radio"]').filter(input => attr(input, 'name') === `detail-${id}`).map(input => ({ value: attr(input, 'value'), checked: Boolean(input.checked) })),
        choices: all(row, 'button[data-detail-choice]').map(b => attr(b, 'data-detail-choice')),
        use_document: Boolean(one(row, 'button[data-action="use-document-date"]')),
        document_date: one(row, '.detail-document-date') ? text(one(row, '.detail-document-date')) : null,
        entered_date: one(row, '.detail-entered-date') ? text(one(row, '.detail-entered-date')) : null,
        saved: one(row, '.detail-saved') ? text(one(row, '.detail-saved')) : null, text: text(row),
        revoke: Boolean(one(row, 'button[data-action="revoke-detail"]')),  // a saved answer's "Change this answer"
      };
    }),
    save: Boolean(one(panel, 'button[data-action="save-details"]')),
  } : null;
  const pp = one(doc, 'section.progress-panel');
  const progress = pp ? {
    phase: attr(pp, 'data-phase'), card: String(attr(pp, 'class') || '').split(/\s+/).includes('progress-card'),
    compact: String(attr(pp, 'class') || '').split(/\s+/).includes('progress-done'), summary: text(one(pp, '.progress-summary')),
    steps: all(pp, '.progress-step').map(step => ({ key: attr(step, 'data-step'), state: attr(step, 'data-state'), text: text(step), classes: String(attr(step, 'class') || '') })),
    elapsed_present: Boolean(one(pp, '[data-elapsed]')), elapsed: text(one(pp, '[data-elapsed]')),
    message: text(one(pp, '.progress-message')), leave: text(one(pp, '.leave-note')),
    // the failed or stopped notice (app.js progressError): the error's own sentence, which the head does not repeat
    notice: text(one(pp, '.progress-error')),
    notice_action: one(pp, '.progress-error button[data-action]') ? attr(one(pp, '.progress-error button[data-action]'), 'data-action') : null,
    stop: Boolean(one(pp, 'button[data-action="stop"]')), resume: Boolean(one(pp, 'button[data-action="resume"]')),
    bars: all(pp, 'progress, [role="progressbar"]').length, text: text(pp),
  } : null;
  const checks = all(doc, 'ul.checks-panel > li.check-step').map(item => ({ key: attr(item, 'data-check'), state: attr(item, 'data-state'), text: text(item) }));
  const exportDialog = one(doc, '#exportDialog');
  const options = all(doc, '#exportDialog button.export-option').map(b => ({ kind: attr(b, 'data-export-kind'), fmt: attr(b, 'data-export-fmt'), disabled: disabled(b), text: text(b) }));
  const ack = one(doc, '.upload-ack');
  return {
    list: Boolean(list), rows, details, progress, checks, progress_cards: all(doc, '.progress-card').length,
    export: exportDialog ? { open: Boolean(exportDialog.open || attr(exportDialog, 'open') !== null), options, text: text(exportDialog) } : null,
    upload_ack: ack ? text(ack) : null,
  };
}

// The number a row's units or number element shows (the first integer in its text), or null.
function shownInteger(textValue) {
  const match = /\d+/.exec(String(textValue || ''));
  return match ? Number(match[0]) : null;
}

function stripQuoteMarks(value) {
  return collapse(String(value || '')).replace(/^["“”'‘’«»]+|["“”'‘’«»]+$/g, '').trim();
}

// The result list as the customer API serves it: a row per code in order, its number, code, units, modifiers, status
// word, sub label, summary, "Why this code?" (each quotation with its offsets and page, each qualification) and only the
// actions the API allows.
function checkResultList(cust, dom) {
  const codes = Array.isArray(cust?.codes) ? cust.codes : [];
  const rows = dom?.rows || [];
  const out = [check('dom.result_list', 'hard', codes.length === 0 ? rows.length === 0 : dom?.list === true && rows.length === codes.length,
    `${rows.length} row(s) in ${dom?.list ? 'ol.result-list' : 'no ol.result-list'}; the API serves ${codes.length} code(s)`)];
  rows.forEach((row, index) => {
    const code = codes[index];
    if (!code) return;
    const problems = [];
    if (row.proposal !== code.id || row.id !== `card-${code.id}`) problems.push(`row ${index + 1} is ${row.proposal} (id ${row.id}), not ${code.id}`);
    if (row.code !== code.code || row.code_text !== code.code) problems.push(`code ${row.code}/${JSON.stringify(row.code_text)}`);
    if (row.status !== code.status || row.status_attr !== code.status) problems.push(`status ${row.status}/${row.status_attr} (API ${code.status})`);
    if (row.status_text !== code.status_label) problems.push(`status word ${JSON.stringify(row.status_text)} (API ${JSON.stringify(code.status_label)})`);
    if (shownInteger(row.number) !== code.number) problems.push(`number ${JSON.stringify(row.number)}`);
    const units = shownInteger(row.units) ?? 1;
    if (units !== code.units) problems.push(`units ${JSON.stringify(row.units)} (API ${code.units})`);
    for (const modifier of code.modifiers || []) if (!new RegExp(`\\b${modifier}\\b`).test(row.modifiers)) problems.push(`modifier ${modifier} not shown`);
    if (collapse(row.sub) !== collapse(code.sub_label)) problems.push(`sub label ${JSON.stringify(row.sub)} (API ${JSON.stringify(code.sub_label)})`);
    if (collapse(row.summary) !== collapse(code.summary)) problems.push('the summary differs from the API\'s');
    const quotes = code.why?.quotes || [];
    const qualifications = code.why?.qualifications || [];
    if (quotes.length || qualifications.length) {
      if (!row.why) problems.push('no "Why this code?" disclosure');
      else {
        if (row.why.summary !== 'Why this code?') problems.push(`the disclosure says ${JSON.stringify(row.why.summary)}`);
        const shown = row.why.quotes.map(q => [Number(q.start), Number(q.end), q.page === null || q.page === '' ? null : Number(q.page), stripQuoteMarks(q.text)]);
        const want = quotes.map(q => [q.start, q.end, q.page ?? null, stripQuoteMarks(q.text)]);
        if (JSON.stringify(shown) !== JSON.stringify(want)) problems.push(`quotations ${JSON.stringify(shown.map(([s, e, p]) => [s, e, p]))} (API ${JSON.stringify(want.map(([s, e, p]) => [s, e, p]))}${JSON.stringify(shown.map(q => q[3])) !== JSON.stringify(want.map(q => q[3])) ? '; texts differ' : ''})`);
        if (!sameList(row.why.qualifications.map(collapse), qualifications.map(collapse))) problems.push('the qualifications differ from the API\'s');
      }
    }
    const offered = row.actions.map(action => action.action).sort();
    const allowed = [...(code.allowed_actions || [])].sort();
    if (!sameList(offered, allowed)) problems.push(`actions ${offered.join(', ') || 'none'} (API allows ${allowed.join(', ') || 'none'})`);
    if (row.actions.some(action => action.proposal !== code.id)) problems.push('an action names another proposal');
    out.push(check(`dom.row.${code.code}`, 'hard', problems.length === 0, problems.join('; ') || `row ${code.number}: ${code.code} · ${code.status_label}${code.modifiers?.length ? ` · ${code.modifiers.join(', ')}` : ''}`));
    if (!(code.modifiers || []).length && MODIFIER_TOKEN.test(row.modifiers)) {
      out.push(check(`dom.row.${code.code}.no_assigned_modifier`, 'soft', false, `the row shows ${JSON.stringify(row.modifiers)} although no modifier is assigned`));
    }
  });
  return out;
}

function checkChecksPanel(cust, dom) {
  const want = (cust?.checks || []).map(item => [item?.key, item?.state]);
  const shown = (dom?.checks || []).map(item => [item.key, item.state]);
  const labels = (cust?.checks || []).every((item, index) => (dom?.checks?.[index]?.text || '').includes(item?.label));
  return [check('dom.checks_panel', 'hard', JSON.stringify(want) === JSON.stringify(shown) && labels,
    `the page shows ${shown.map(([k, s]) => `${k}:${s}`).join(', ') || 'no check step'}; the API serves ${want.map(([k, s]) => `${k}:${s}`).join(', ')}${labels ? '' : ' (a label differs)'}`)];
}

// The details panel as the API serves details_needed: the heading, a row per detail in order with its control (a date
// field, the listed choices, "Not documented" / "Cannot confirm" where allowed, "Use document date" exactly where the API
// allows it, the document's date beside the entered one for a date conflict), a saved answer shown as saved, and Save.
function checkDetailsPanel(cust, dom) {
  const details = Array.isArray(cust?.details_needed) ? cust.details_needed : [];
  const panel = dom?.details || null;
  if (!details.length) return [check('dom.details_panel', 'hard', !panel || !panel.rows.length, panel ? `the page shows ${panel.rows.length} detail row(s); the API asks none` : 'no details asked, no panel')];
  if (!panel) return [check('dom.details_panel', 'hard', false, `the API asks ${details.length} detail(s); the page shows no section.details-panel`)];
  const problems = [];
  if (panel.heading !== DETAILS_HEADING) problems.push(`heading ${JSON.stringify(panel.heading)}`);
  if (panel.rows.length !== details.length) problems.push(`${panel.rows.length} row(s) for ${details.length} detail(s)`);
  details.forEach((detail, index) => {
    const row = panel.rows[index];
    if (!row) return;
    const where = `row ${index + 1} (${detail.fact})`;
    if (row.id !== detail.id || row.fact !== detail.fact) problems.push(`${where} is ${row.id}/${row.fact}`);
    if (detail.saved) {
      // a saved row shows its answer, and a way to change it (app.js savedAnswer: "Saved: ..." and "Change this answer"
      // where the API names the answer; a date entered at upload keeps its date field), never the open row's offers:
      // walk 2 (2026-11-05) held a saved row to an open row's answer buttons, and a correct page failed
      const editable = cust?.permissions?.can_review === true && cust?.progress?.busy !== true;
      if (row.saved === null) problems.push(`${where} does not show its saved answer`);
      const named = typeof detail.saved.answer_id === 'string' && Boolean(detail.saved.answer_id);
      if (editable && named && !row.revoke) problems.push(`${where} offers no way to change its saved answer`);
      if (editable && !named && detail.control === 'date' && !row.date_input) problems.push(`${where} offers no date field to change the entered date`);
      return;
    }
    if (detail.control === 'date') {
      if (!row.date_input) problems.push(`${where} has no date field`);
      // the page may write the date in words: the document's date and the entered one are each shown, side by side
      if (detail.document_value && !(row.document_date || '').trim()) problems.push(`${where} does not show the document's date`);
      if (detail.entered_value && row.entered_date === null) problems.push(`${where} does not show the entered date beside the document's`);
      const offered = detail.fact === 'service_date' && cust?.service_date?.can_use_document_date === true;
      if (row.use_document !== offered) problems.push(`${where} ${row.use_document ? 'offers' : 'does not offer'} "Use document date" (the API ${offered ? 'allows' : 'does not allow'} it)`);
    } else if (row.use_document) problems.push(`${where} offers "Use document date" on a ${detail.control} question`);
    if (detail.control === 'choice') {
      const values = row.radios.map(radio => radio.value);
      const missing = (detail.choices || []).map(choice => choice.value).filter(value => !values.includes(value));
      if (missing.length) problems.push(`${where} lacks the choice(s) ${missing.join(', ')}`);
    }
    if (detail.control === 'confirm' && row.radios.length) problems.push(`${where} offers a clinical fact to choose: a member never supplies one`);
    for (const allowed of detail.allow || []) {
      if (!row.choices.includes(allowed) && !row.radios.some(radio => radio.value === allowed)) problems.push(`${where} does not offer ${allowed}`);
    }
    for (const offered of row.choices) if (!(detail.allow || []).includes(offered)) problems.push(`${where} offers ${offered}, which the API does not allow`);
    if (row.saved !== null) problems.push(`${where} shows a saved answer the API does not hold`);
  });
  if (details.some(detail => !detail.saved) && !panel.save) problems.push('no Save (button[data-action="save-details"])');
  return [check('dom.details_panel', 'hard', problems.length === 0, problems.join('; ') || `${details.length} detail row(s) with the API's controls`)];
}

// --- progress (CORE-UX-DESIGN 6 and 8) -------------------------------------------------------------------------------------

// The page's progress panel against the encounter the page was served. A phase in PANEL_PHASES draws the whole panel: the
// phase, each step in order and state, elapsed time while busy, no percentage or ETA, the progress-card class only while
// busy, Stop and Resume where the API offers them, the server's message (in the head, or in the notice when it is the
// error's own sentence, which the head does not repeat: app.js progressPanel), the served error in the notice, the leave
// note; and once failed or stopped no step active and nothing animating (animating: the elements under the panel with a
// running CSS animation, read in the page). Any other phase is the compact line (checkCompactProgress).
function checkProgressDom(cust, dom, animating = []) {
  const progress = cust?.progress || {};
  const panel = dom?.progress || null;
  if (!panel) {
    // the review page always draws its panel (app.js reviewView); a waiting, stopped or failed document without one has
    // lost its steps, its notice and its leave note (refutation, 2026-11-05: it once passed whenever nothing was busy)
    const owed = progress.busy || PANEL_PHASES.has(progress.phase);
    return [check('progress.dom.panel', 'hard', !owed, progress.busy ? 'the encounter is processing and the page shows no section.progress-panel'
      : owed ? `the encounter is ${progress.phase} and the page shows no section.progress-panel` : 'results are ready; no progress panel drawn')];
  }
  if (!PANEL_PHASES.has(progress.phase)) return checkCompactProgress(progress, panel, dom, animating);
  const want = (progress.steps || []).map(step => [step.key, step.state]);
  const shown = panel.steps.map(step => [step.key, step.state]);
  const served = collapse(progress.message || '');
  const errorText = isObject(progress.error) ? collapse(progress.error.text || '') : '';
  const inNotice = Boolean(served) && served === errorText;
  const said = inNotice ? panel.notice : panel.message;
  const out = [
    check('progress.dom.phase', 'hard', panel.phase === progress.phase, `the panel shows ${panel.phase}; the page was served ${progress.phase}`),
    check('progress.dom.whole_panel', 'hard', !panel.compact, panel.compact ? `the page drew ${progress.phase} as the compact line, without its steps` : `${progress.phase}: the whole panel`),
    check('progress.dom.steps', 'hard', JSON.stringify(want) === JSON.stringify(shown) && (progress.steps || []).every((step, i) => (panel.steps[i]?.text || '').includes(step.label)),
      `the panel shows ${shown.map(([k, s]) => `${k}:${s}`).join(', ') || 'no step'}; served ${want.map(([k, s]) => `${k}:${s}`).join(', ')}`),
    check('progress.dom.no_percentage_or_eta', 'hard', !PERCENT_OR_ETA.test(panel.text) && panel.bars === 0,
      panel.bars ? `${panel.bars} progress bar element(s)` : PERCENT_OR_ETA.test(panel.text) ? `the panel says ${JSON.stringify(panel.text.match(PERCENT_OR_ETA)[0])}` : 'no percentage, ETA or progress bar'),
    check('progress.dom.card_while_busy', 'hard', progress.busy ? panel.card : dom.progress_cards === 0,
      progress.busy ? `busy: the panel ${panel.card ? 'carries' : 'lacks'} the progress-card class` : `not busy: ${dom.progress_cards} .progress-card element(s)`),
    check('progress.dom.message', 'hard', collapse(said).includes(served), `the panel ${inNotice ? 'notice' : 'head'} says ${JSON.stringify(said)}; served ${JSON.stringify(progress.message)}`),
  ];
  if (errorText) out.push(check('progress.dom.error', 'hard', collapse(panel.notice).includes(errorText), `the notice says ${JSON.stringify(panel.notice)}; served the error ${JSON.stringify(progress.error.text)}`));
  if (progress.busy && ELAPSED_PHASES.has(progress.phase)) out.push(check('progress.dom.elapsed', 'hard', panel.elapsed_present && /\d/.test(panel.elapsed), `elapsed ${panel.elapsed_present ? JSON.stringify(panel.elapsed) : 'not shown'}`));
  if (progress.can_stop) out.push(check('progress.dom.stop', 'hard', panel.stop, `Stop ${panel.stop ? 'offered' : 'not offered'} while the API allows it`));
  if (progress.can_resume) out.push(check('progress.dom.resume', 'hard', panel.resume, `Resume ${panel.resume ? 'offered' : 'not offered'} while the API allows it`));
  if (progress.can_leave) out.push(check('progress.dom.leave_note', 'hard', Boolean(panel.leave), `leave note ${panel.leave ? JSON.stringify(panel.leave) : 'not shown'}`));
  if (SETTLED_PHASES.has(progress.phase)) {
    out.push(check('progress.dom.settled_still', 'hard', animating.length === 0 && !panel.steps.some(step => step.state === 'active'),
      animating.length ? `${progress.phase}, and still animating: ${animating.slice(0, 5).join(', ')}` : panel.steps.some(step => step.state === 'active')
        ? `${progress.phase}, and a step still reads active` : `${progress.phase}: no step active, nothing animating`));
  }
  return out;
}

// A phase outside PANEL_PHASES (results are ready, a detail is asked, a limitation): one compact line - the phase's title
// and, once finished, the time it took; the server's message only where it adds to the title (COMPACT_MESSAGE_PHASES);
// no step, no Stop or Resume, no percentage or ETA, no progress card, nothing animating.
function checkCompactProgress(progress, panel, dom, animating = []) {
  const extra = [panel.steps.length ? `${panel.steps.length} step(s)` : '', panel.stop ? 'a Stop' : '', panel.resume ? 'a Resume' : ''].filter(Boolean);
  const title = COMPACT_TITLES[progress.phase] || '';
  const out = [
    check('progress.dom.phase', 'hard', panel.phase === progress.phase, `the panel shows ${panel.phase}; the page was served ${progress.phase}`),
    check('progress.dom.compact', 'hard', panel.compact && Boolean(title) && collapse(panel.summary).startsWith(title) && !extra.length,
      !panel.compact ? `${progress.phase} drawn as the whole panel, not the compact line` : !title ? `no compact title is known for the phase ${progress.phase}`
        : `${progress.phase}: one line ${JSON.stringify(panel.summary)} (its title "${title}")${extra.length ? `, with ${extra.join(' and ')}` : ''}`),
    check('progress.dom.no_percentage_or_eta', 'hard', !PERCENT_OR_ETA.test(panel.text) && panel.bars === 0,
      panel.bars ? `${panel.bars} progress bar element(s)` : PERCENT_OR_ETA.test(panel.text) ? `the line says ${JSON.stringify(panel.text.match(PERCENT_OR_ETA)[0])}` : 'no percentage, ETA or progress bar'),
    check('progress.dom.card_while_busy', 'hard', dom.progress_cards === 0, `${dom.progress_cards} .progress-card element(s)`),
    check('progress.dom.still', 'hard', animating.length === 0, animating.length ? `still animating: ${animating.slice(0, 5).join(', ')}` : 'nothing animating'),
  ];
  if (progress.started_at && progress.finished_at) out.push(check('progress.dom.took', 'hard', panel.elapsed_present && /\d/.test(panel.elapsed), `took ${panel.elapsed_present ? JSON.stringify(panel.elapsed) : 'not shown'}`));
  if (COMPACT_MESSAGE_PHASES.has(progress.phase) && progress.message) {
    out.push(check('progress.dom.message', 'hard', collapse(panel.message).includes(collapse(progress.message)), `the line says ${JSON.stringify(panel.message)}; served ${JSON.stringify(progress.message)}`));
  }
  return out;
}

// The customer steps the operator view's jobs imply (P5's fold): each step from the LAST job of each kind folded into it.
function foldedSteps(op) {
  const stages = Array.isArray(op?.pipeline?.stages) ? op.pipeline.stages : [];
  const keyOf = index => {
    const kind = stages[index].kind;
    if (kind !== 'assess') return STEP_OF_KIND[kind] || null;
    return stages.slice(index + 1).some(later => PEER_KINDS.has(later.kind)) ? 'checking' : 'preparing';
  };
  // A finished stage gives its step the outcome the operator view serves (step_outcome: the page's own rule,
  // progress._step_outcome - done, failed, stopped, or null when it did nothing for the step); an operator view that
  // serves none falls back to the job's own state. One step reads its stages as the page does: a stop or an outcome
  // still being confirmed outranks a failure, and a failure outranks done (refutation round 3, C-R3-5).
  const effective = stage => {
    if (stage.state === 'running' || stage.state === 'queued') return stage.state;
    if (!Object.prototype.hasOwnProperty.call(stage, 'step_outcome')) return stage.state;
    return stage.step_outcome;
  };
  const last = new Map();
  stages.forEach((stage, index) => {
    const key = keyOf(index);
    const state = effective(stage);
    if (key && state !== null && state !== undefined) last.set(`${key}|${stage.kind}|${stage.kind === 'assess' ? key : ''}`, { key, state });
  });
  const steps = {};
  for (const key of Object.keys(VOCAB.steps)) {
    const states = [...last.values()].filter(item => item.key === key).map(item => item.state);
    steps[key] = !states.length ? 'none' : states.some(s => s === 'running' || s === 'queued') ? 'active'
      : states.some(s => s === 'stopped' || s === 'cancelled') ? 'stopped' : states.some(s => s === 'unknown') ? 'unknown'
        : states.some(s => s === 'failed') ? 'failed' : 'done';
  }
  return steps;
}

function checkProgressFold(cust, op) {
  const folded = foldedSteps(op);
  const shown = Object.fromEntries((cust?.progress?.steps || []).map(step => [step.key, step.state]));
  const wrong = Object.entries(folded).filter(([key, state]) => !STEP_STATES_FOR[state].includes(shown[key]));
  return [check('progress.backend_stage', 'hard', wrong.length === 0, wrong.length
    ? `the steps served are not the jobs' state: ${wrong.map(([key, state]) => `${key} ${shown[key]} (jobs: ${state})`).join(', ')}`
    : `the steps served are the jobs' state: ${Object.entries(folded).map(([key, state]) => `${key} ${state}`).join(', ')}`)];
}

// The upload acknowledgement (CORE-UX-DESIGN 8: .upload-ack from the POST 201, before the first GET): watch is
// window.__cptVerify as pageWatch recorded it, id the new encounter's.
function checkUploadAck(watch, id) {
  const path = `/api/encounters/${id}`;
  const first = (watch?.gets || []).find(get => get.path === path) || null;
  const created = (watch?.requests || []).find(r => r.method === 'POST' && r.path === '/api/encounters' && r.status === 201) || null;
  const ack = watch?.ack || null;
  return [
    check('upload.acknowledged', 'hard', Boolean(first) && first.ack_present && first.ack_visible, !first
      ? `the page never asked for ${path}` : first.ack_visible ? `on screen when the page first asked for the encounter: ${JSON.stringify(first.ack_text)}`
        : `the page asked for the encounter while ${first.ack_present ? 'the acknowledgement was hidden' : 'no .upload-ack was on screen'}`),
    check('upload.ack_after_created', 'hard', Boolean(ack) && Boolean(created) && created.t_end !== null && ack.t >= created.t_end - 1,
      !ack ? 'no acknowledgement was seen' : !created ? 'the upload\'s 201 was not seen by the page' : `shown ${Math.round(ack.t - created.t_end)} ms after the 201 arrived`),
    check('upload.ack_wording', 'soft', Boolean(ack) && /\b(?:uploaded|received)\b/i.test(ack.text), `the acknowledgement says ${JSON.stringify(ack?.text ?? '')}`),
  ];
}

// --- no duplicate paid request (directive section 5), read from the operator view -------------------------------------------

function byCreated(a, b) {
  return String(a.created_at || '').localeCompare(String(b.created_at || ''));
}

// Each sent run whose request (provider, purpose, request hash) was already answered (succeeded) or left unknown and not
// reconciled by an earlier sent run: a duplicate paid request. A request sent again after a definite failure is a retry.
function duplicateSends(runs) {
  const groups = new Map();
  const duplicates = [];
  for (const run of [...(runs || [])].sort(byCreated)) {
    if (!sentRun(run) || !run.request_sha256) continue;
    const key = `${run.provider}|${run.purpose}|${run.request_sha256}`;
    const earlier = groups.get(key) || [];
    const blocking = earlier.filter(item => item.state === 'succeeded' || (item.state === 'unknown' && !item.reconciled));
    if (blocking.length) duplicates.push({ run, earlier: blocking });
    groups.set(key, [...earlier, run]);
  }
  return duplicates;
}

function checkNoDuplicateSends(op, id = 'pipeline.no_duplicate_send') {
  const runs = op?.provider_runs || [];
  const dupes = duplicateSends(runs);
  const sent = runs.filter(sentRun).length;
  return [check(id, 'hard', dupes.length === 0, dupes.length
    ? `sent again after an answer or an unreconciled unknown outcome: ${dupes.map(({ run, earlier }) => `${run.id} (${describeRun(run)}) after ${earlier.map(e => `${e.id} ${e.state}`).join(', ')}`).join('; ')}`
    : `${runs.length} run(s), ${sent} sent, no request sent twice`)];
}

// A job's identity across two reads of the operator view: its id where the view serves one, else its kind and place.
function stageIdentity(stage, index) {
  return typeof stage?.id === 'string' && stage.id ? stage.id : `${index}:${stage?.kind}`;
}

// The jobs of the earlier read kept in the later one: each at its place with its kind, and one that had finished keeping
// its state and finish time.
function jobsKept(before, after) {
  const earlier = before?.pipeline?.stages || [];
  const later = after?.pipeline?.stages || [];
  return earlier.map((stage, index) => {
    const same = later.find((item, i) => stageIdentity(item, i) === stageIdentity(stage, index));
    if (!same || same.kind !== stage.kind) return `${stageIdentity(stage, index)} (${stage.kind}) is gone`;
    if (stage.finished_at && (same.finished_at !== stage.finished_at || same.state !== stage.state)) return `${stage.kind} finished ${stage.state} at ${stage.finished_at}, now ${same.state} at ${same.finished_at}`;
    return null;
  }).filter(Boolean);
}

// Runs of the earlier read kept in the later one: each present, and one that had finished unchanged.
function runsKept(before, after) {
  const later = new Map((after?.provider_runs || []).map(run => [run.id, run]));
  return (before?.provider_runs || []).filter(run => {
    const same = later.get(run.id);
    if (!same) return true;
    return ['succeeded', 'failed', 'not_sent', 'cancelled'].includes(run.state) && runRecord(same) !== runRecord(run);
  }).map(run => `${run.id} (${describeRun(run)})`);
}

// before / after: {url, ids (the customer list's encounter ids), op (the operator view), dom (readCustomerDom), cust}.
function checkReloadIdentity(id, before, after, prefix = 'reload') {
  const hash = String(after?.url || '').split('#')[1] || '';
  const added = (after?.ids || []).filter(item => !(before?.ids || []).includes(item));
  const lostJobs = jobsKept(before?.op, after?.op);
  const lostRuns = runsKept(before?.op, after?.op);
  const dom = after?.dom || {};
  const shown = Boolean(dom.progress) || Boolean(dom.list) || Boolean(dom.details);
  const busy = after?.cust?.progress?.busy === true;
  return [
    check(`${prefix}.same_encounter`, 'hard', hash === `doc/${id}` && added.length === 0,
      `the page is at #${hash}${added.length ? `; new encounter(s) in the list: ${added.join(', ')}` : '; no new encounter in the list'}`),
    check(`${prefix}.jobs_kept`, 'hard', lostJobs.length === 0, lostJobs.join('; ') || `${(before?.op?.pipeline?.stages || []).length} job(s) kept, each with its state`),
    check(`${prefix}.runs_kept`, 'hard', lostRuns.length === 0, lostRuns.length ? `changed or missing: ${lostRuns.join(', ')}` : `${(before?.op?.provider_runs || []).length} run(s) kept`),
    ...checkNoDuplicateSends(after?.op, `${prefix}.no_duplicate_send`),
    check(`${prefix}.progress_restored`, 'hard', shown && (!busy || (dom.progress && dom.progress.phase === after?.cust?.progress?.phase)),
      !shown ? 'the encounter screen did not come back' : busy ? `processing: the panel shows ${dom.progress?.phase ?? 'nothing'}, served ${after?.cust?.progress?.phase}` : 'the result came back'),
  ];
}

// record: what stopAndResume did and read (stopped: the encounter once stopped; quiet: the operator view read
// QUIET_SECONDS_WHILE_STOPPED later; resumed: once processing settled again).
function checkStopResume(id, record) {
  const out = [check('stop.request', 'hard', saved(record?.stop_status), `Stop answered HTTP ${record?.stop_status ?? 'none'}${record?.error ? `: ${record.error}` : ''}`)];
  if (!saved(record?.stop_status)) return out;
  const stopped = record.stopped || {};
  out.push(check('stop.state', 'hard', stopped.cust?.state === 'stopped' && stopped.cust?.progress?.phase === 'stopped',
    `after Stop: state ${stopped.cust?.state}, phase ${stopped.cust?.progress?.phase}`));
  out.push(...checkProgressDom(stopped.cust, stopped.dom, stopped.animating || []).map(item => ({ ...item, id: item.id.replace(/^progress\.dom\./, 'stop.') })));
  const fresh = (record.quiet?.op?.provider_runs || []).filter(run => !(stopped.op?.provider_runs || []).some(item => item.id === run.id));
  out.push(check('stop.nothing_sent_while_stopped', 'hard', Boolean(record.quiet?.op) && fresh.length === 0,
    !record.quiet?.op ? 'the operator view was not read while stopped' : fresh.length ? `new run(s) while stopped: ${fresh.map(describeRun).join(', ')}` : `no new run in ${QUIET_SECONDS_WHILE_STOPPED} s while stopped`));
  if (record.resume_status === undefined || record.resume_status === null) {
    out.push(check('resume.request', 'hard', false, record.resume_error || 'Resume was not offered or not made'));
    return out;
  }
  out.push(check('resume.request', 'hard', saved(record.resume_status), `Resume answered HTTP ${record.resume_status}${record.resume_error ? `: ${record.resume_error}` : ''}`));
  if (!record.resumed) return out;
  out.push(...checkReloadIdentity(id, { ...record.before, url: record.resumed.url }, record.resumed, 'resume')
    .filter(item => item.id !== 'resume.progress_restored'));
  out.push(check('resume.finished', 'hard', record.resumed.cust?.progress?.busy === false && !['stopped', 'failed'].includes(record.resumed.cust?.state),
    `after Resume: state ${record.resumed.cust?.state}, phase ${record.resumed.cust?.progress?.phase}`));
  return out;
}

// --- provenance, read from the operator view (directive section 2: kept complete for platform operators) ------------------

const HARNESS_PARTICIPANTS = ['corti', 'astra', 'fable'];
// Participants whose service names no model. Corti's coding API answers codes, candidates and usageInfo only - no model,
// version or response id (its response, read key by key on run d24ae7b3 on 2026-11-05) - and review.HARNESS_PARTICIPANTS
// names it with model ''; so its runs are identified by endpoint, adapter version and run identity. Every other
// participant names the model it asked for and the model that answered.
const MODELLESS_PARTICIPANTS = new Set(['corti']);
const SHA256 = /^[0-9a-f]{64}$/;

function checkProvenance(op, trace, { expectHarness = false } = {}) {
  const out = [];
  const harness = op?.harness;
  if (!harness || !Array.isArray(harness.participants)) {
    out.push(expectHarness ? check('provenance.participants', 'hard', false, 'the operator view serves no harness for this encounter, and this walk expects it (--expect-harness)')
      : skip('provenance.participants', 'the operator view serves no harness for this encounter'));
  } else {
    const rows = harness.participants.filter(isObject);
    const names = rows.map(row => row.name);
    out.push(check('provenance.participants', 'hard', sameList(names, HARNESS_PARTICIPANTS), `participants ${names.join(', ') || 'none'} (expected ${HARNESS_PARTICIPANTS.join(', ')})`));
    const named = value => typeof value === 'string' && Boolean(value);
    const unnamed = rows.filter(row => !named(row.vendor) || (!MODELLESS_PARTICIPANTS.has(row.name) && !named(row.model))).map(row => row.name);
    out.push(check('provenance.models', 'hard', unnamed.length === 0, unnamed.length ? `no vendor or model named for ${unnamed.join(', ')}`
      : rows.map(row => `${row.name}: ${row.vendor} ${MODELLESS_PARTICIPANTS.has(row.name) ? '(its API names no model)' : row.model}${row.returned_model ? ` (answered ${row.returned_model})` : ''}`).join('; ')));
    const unanswered = rows.filter(row => row.state === 'done' && !MODELLESS_PARTICIPANTS.has(row.name) && !named(row.returned_model)).map(row => row.name);
    out.push(check('provenance.returned_models', 'soft', unanswered.length === 0, unanswered.length ? `no answering model recorded for ${unanswered.join(', ')}` : 'every participant that ran names the model that answered'));
    if (expectHarness) {
      const peers = rows.filter(row => row.name !== 'corti' && !(isObject(row.peer) && typeof row.peer.state === 'string'));
      out.push(check('provenance.peer_reviews', 'hard', peers.length === 0, peers.length ? `no peer review state for ${peers.map(row => row.name).join(', ')}` : 'Astra and Fable each with a peer review state'));
    }
  }
  const runs = Array.isArray(op?.provider_runs) ? op.provider_runs : [];
  const unhashed = runs.filter(run => sentRun(run) && (!SHA256.test(String(run.request_sha256 || '')) || (run.state === 'succeeded' && !SHA256.test(String(run.response_sha256 || '')))));
  out.push(check('provenance.request_hashes', 'hard', unhashed.length === 0, unhashed.length ? `sent run(s) without their request/response sha256: ${unhashed.map(describeRun).join(', ')}`
    : `${runs.filter(sentRun).length} sent run(s), each with its request and response sha256`));
  const unmetered = runs.filter(run => sentRun(run) && run.state === 'succeeded' && !(isObject(run.usage) && Object.keys(run.usage).length));
  out.push(check('provenance.usage', 'soft', unmetered.length === 0, unmetered.length ? `succeeded sent run(s) with no usage recorded: ${unmetered.map(describeRun).join(', ')}`
    : 'every succeeded sent run records its usage'));
  // a reuse sends nothing and bills nothing: jobs.py records it with usage {} ('reused_retained_result_no_new_usage')
  const reused = runs.filter(run => run.reused_from);
  const billed = reused.filter(run => isObject(run.usage) && Object.keys(run.usage).length);
  out.push(check('provenance.reuse', 'hard', billed.length === 0, billed.length ? `reused run(s) carrying usage of their own: ${billed.map(run => `${run.id} from ${run.reused_from}`).join(', ')}`
    : `${reused.length} run(s) reusing a retained answer${reused.length ? ` (${reused.map(run => `${run.id} from ${run.reused_from}`).join(', ')})` : ''}, none with usage of its own`));
  if (trace === undefined) return out;
  const traced = (trace?.participants || []).flatMap(item => (item?.runs || []).map(r => ({ ...r, participant: item.name })));
  // a participant whose API names no model is identified by its adapter version in the model's place
  const bare = traced.filter(r => r.sent && !(r.endpoint && r.run_identity && (MODELLESS_PARTICIPANTS.has(r.participant) ? r.adapter_version : r.requested_model)));
  out.push(check('provenance.trace', 'hard', Boolean(trace) && bare.length === 0, !trace ? 'the operator trace was not served'
    : bare.length ? `traced runs without endpoint, model (or, where the API names none, adapter version) or identity: ${bare.map(r => `${r.participant} ${r.id}`).join(', ')}`
      : `${traced.length} traced run(s), each with its endpoint, model or adapter version, and identity`));
  return out;
}

// --- direct-URL authorization (CORE-UX-DESIGN 5: every /ops/ URL answers 404 to anyone who is not an operator) ----------

// probes: [{who: 'customer'|'anonymous'|'operator', method, path, status, location}].
function checkAuthorization(probes) {
  const by = who => (probes || []).filter(p => p.who === who);
  const isOps = p => p.path.startsWith('/ops/');
  const customerOps = by('customer').filter(isOps);
  const customerWrong = customerOps.filter(p => p.status !== 404);
  const removed = (probes || []).filter(p => !isOps(p) && /\/trace$/.test(p.path));
  const removedWrong = removed.filter(p => p.status !== 404);
  const removedByCustomer = removed.some(p => p.who === 'customer');
  const anonymous = by('anonymous');
  const anonymousWrong = anonymous.filter(p => !([401, 403, 404].includes(p.status) || (p.status >= 300 && p.status < 400 && /^\/login\b/.test(pathnameOf(p.location || '') || p.location || ''))));
  const operator = by('operator').filter(isOps);
  const operatorWrong = operator.filter(p => p.status !== 200);
  const words = list => list.map(p => `${p.method} ${p.path} -> ${p.status}`).join(', ');
  return [
    check('authorization.customer_ops_404', 'hard', customerOps.length > 0 && customerWrong.length === 0, !customerOps.length ? 'no /ops/ URL was tried with the customer session'
      : customerWrong.length ? `not 404 to the customer: ${words(customerWrong)}` : `${customerOps.length} /ops/ URL(s), each 404 to the customer (${customerOps.filter(p => p.method === 'POST').length} POST)`),
    check('authorization.trace_removed', 'hard', removedByCustomer && removedWrong.length === 0, !removedByCustomer ? 'the old trace URL was not tried with the customer session'
      : removedWrong.length ? `the old trace URL answered: ${words(removedWrong)}` : `${words(removed)}`),
    check('authorization.anonymous', 'hard', anonymous.length > 0 && anonymousWrong.length === 0, !anonymous.length ? 'no URL was tried without a session'
      : anonymousWrong.length ? `answered without a session: ${words(anonymousWrong)}` : `${anonymous.length} URL(s) refused without a session`),
    check('authorization.operator_reads', 'hard', operator.length > 0 && operatorWrong.length === 0, !operator.length ? 'the operator read no /ops/ URL'
      : operatorWrong.length ? `the operator could not read: ${words(operatorWrong)}` : `${operator.length} /ops/ URL(s) read by the operator`),
  ];
}

// --- the two viewports (CORE-UX-DESIGN 8: no horizontal scroll at 390 px; touch targets of at least 44 px) ----------------

// Runs IN THE PAGE: the page's scroll width and what lies past the right edge, then each result row, decision button
// and details control - scrolled into view vertically only (a horizontal scroll would hide the overflow it measures),
// placed in page coordinates, and hit-tested at its centre (another element on top of it is not operable).
function measureViewport() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  const doc = document.documentElement;
  window.scrollTo(0, 0);
  const label = el => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.className && typeof el.className === 'string' && el.className.trim() ? `.${el.className.trim().split(/\s+/).join('.')}` : ''}`;
  const offenders = Array.from(document.body.querySelectorAll('*')).filter(el => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.right + window.scrollX > width + 1 && getComputedStyle(el).position !== 'fixed'
      && !(el.parentElement && el.parentElement.getBoundingClientRect().right + window.scrollX > width + 1);
  }).slice(0, 8).map(el => `${label(el)} (right ${Math.round(el.getBoundingClientRect().right + window.scrollX)})`);
  const info = el => {
    const first = el.getBoundingClientRect();
    window.scrollTo(window.scrollX, Math.max(0, window.scrollY + first.top + first.height / 2 - height / 2));
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const left = rect.left + window.scrollX;
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const top = rect.width && rect.height && y >= 0 && y < height && x >= 0 && x < width ? document.elementFromPoint(x, y) : null;
    return { left: Math.round(left), right: Math.round(left + rect.width), width: Math.round(rect.width), height: Math.round(rect.height),
      shown: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
      hit: Boolean(top) && (top === el || el.contains(top)),
      enabled: !(el.disabled === true || el.getAttribute('aria-disabled') === 'true') };
  };
  const rows = Array.from(document.querySelectorAll('ol.result-list > li.result-row')).map(li => ({ proposal: li.getAttribute('data-proposal'), ...info(li) }));
  const actions = Array.from(document.querySelectorAll('ol.result-list > li.result-row button[data-decision]'))
    .map(b => ({ action: b.getAttribute('data-decision'), proposal: b.getAttribute('data-proposal'), ...info(b) }));
  const controls = Array.from(document.querySelectorAll('section.details-panel input, section.details-panel button, section.details-panel select'))
    .filter(el => el.type !== 'hidden').map(el => ({ control: el.getAttribute('data-action') || el.getAttribute('data-detail-choice') || el.type || el.tagName.toLowerCase(), ...info(el) }));
  window.scrollTo(0, 0);
  return { width, height, scroll_width: Math.max(doc.scrollWidth, document.body ? document.body.scrollWidth : 0), rows, actions, controls, offenders };
}

function checkViewport(name, m) {
  const inside = item => item.shown && item.left >= -1 && item.right <= m.width + 1;
  const rowsOff = (m.rows || []).filter(item => !inside(item));
  const actionsOff = (m.actions || []).filter(item => !(inside(item) && item.hit && item.enabled));
  const controlsOff = (m.controls || []).filter(item => !(inside(item) && item.hit));
  const small = [...(m.actions || []), ...(m.controls || [])].filter(item => item.shown && (item.width < 44 || item.height < 44));
  const out = [
    check(`viewport.${name}.no_horizontal_scroll`, 'hard', m.scroll_width <= m.width + 1,
      `scroll width ${m.scroll_width} at ${m.width} px${m.offenders?.length ? `; past the edge: ${m.offenders.join(', ')}` : ''}`),
    check(`viewport.${name}.rows_visible`, 'hard', rowsOff.length === 0, rowsOff.length ? `rows off screen: ${rowsOff.map(item => item.proposal).join(', ')}` : `${(m.rows || []).length} row(s) on screen`),
    check(`viewport.${name}.actions_operable`, 'hard', actionsOff.length === 0, actionsOff.length
      ? `actions not operable: ${actionsOff.map(item => `${item.action} ${item.proposal} (${!item.shown ? 'hidden' : !item.hit ? 'covered' : !item.enabled ? 'disabled' : 'off screen'})`).join(', ')}`
      : `${(m.actions || []).length} action(s) on screen, enabled and on top`),
  ];
  if ((m.controls || []).length) {
    out.push(check(`viewport.${name}.details_operable`, 'hard', controlsOff.length === 0, controlsOff.length
      ? `details controls not operable: ${controlsOff.map(item => item.control).join(', ')}` : `${m.controls.length} details control(s) on screen and on top`));
  }
  out.push(check(`viewport.${name}.touch_targets`, 'soft', small.length === 0, small.length
    ? `under 44x44 px: ${small.slice(0, 6).map(item => `${item.action || item.control} ${item.width}x${item.height}`).join(', ')}` : 'every action and control at least 44x44 px'));
  return out;
}

// --- decisions as the customer sees them -------------------------------------------------------------------------------

// Each decision this run made, after the reload: its row shows the decided status (an approval Approved; a rejection or
// a confirmed exclusion Excluded), an agent's approval labelled agent-executed synthetic review (a human's - the
// acceptance reviewer's - never), a rejection "Rejected in review", and the modifier the walk chose.
function checkDecisionRows(decisions, cust, dom, options = {}) {
  return decisions.filter(d => d.http_status === 201).map(d => {
    const row = (dom?.rows || []).find(item => item.proposal === d.proposal_id);
    const want = d.action === 'approve' ? 'approved' : d.action === 'reinstate' ? ['ready', 'needs_detail'] : 'excluded';
    const statusOk = Boolean(row) && (Array.isArray(want) ? want.includes(row.status) : row.status === want);
    let labelOk = true;
    let label = '';
    if (row && d.action === 'approve') {
      labelOk = options.acceptance ? !/agent/i.test(`${row.sub} ${row.status_text}`) : row.sub.includes(AGENT_SUB_LABEL);
      label = options.acceptance ? 'not labelled as an agent\'s' : `labelled "${AGENT_SUB_LABEL}"`;
    } else if (row && d.action === 'reject') {
      labelOk = row.sub.includes(REJECTED_SUB_LABEL);
      label = `labelled "${REJECTED_SUB_LABEL}"`;
    }
    const modifierOk = !d.modifier || (Boolean(row) && new RegExp(`\\b${d.modifier}\\b`).test(row.modifiers));
    return check(`dom.decision.${d.code}`, 'hard', statusOk && labelOk && modifierOk, !row ? 'no row after the reload'
      : `row ${row.status} (${JSON.stringify(row.status_text)})${statusOk ? '' : ` (expected ${[].concat(want).join(' or ')})`}; ${label ? `${labelOk ? '' : 'NOT '}${label}` : 'no label owed'}`
        + (d.modifier ? `; modifier ${d.modifier} ${modifierOk ? 'shown' : 'NOT shown'}` : ''));
  });
}

// Each decision this run made as the customer API serves it after the reload: by the signed-in account, of its kind,
// with the walk's note and the modifier it chose (or none).
function checkCustomerDecisions(decisions, cust, account, kind = 'agent') {
  const codes = new Map((cust?.codes || []).map(code => [code.id, code]));
  return decisions.filter(d => d.http_status === 201 && d.action !== 'revoke').map(d => {
    const code = codes.get(d.proposal_id);
    const shown = code?.decision || null;
    const modifiers = d.modifier ? [d.modifier] : [];
    const problems = [];
    if (!code) problems.push('the code is not listed');
    else if (!shown) problems.push('no decision served');
    else {
      if (shown.action !== d.action) problems.push(`action ${shown.action}`);
      if (account?.label && shown.by !== account.label) problems.push(`by ${JSON.stringify(shown.by)} (signed in as ${JSON.stringify(account.label)})`);
      if (shown.by_kind !== kind) problems.push(`by_kind ${shown.by_kind} (expected ${kind})`);
      if (shown.note !== d.note) problems.push('the note changed');
      if (!sameList(shown.modifiers, modifiers) || (d.action === 'approve' && !sameList(code.modifiers, modifiers))) problems.push(`modifiers ${JSON.stringify(shown.modifiers)} / ${JSON.stringify(code.modifiers)} (chosen ${JSON.stringify(modifiers)})`);
    }
    return check(`customer.decision.${d.code}`, 'hard', problems.length === 0, problems.join('; ') || `${d.action} by ${shown.by} (${shown.by_kind}) with the walk's note${modifiers.length ? ` and modifier ${modifiers[0]}` : ''}`);
  });
}

// The review dialog as each decision found it: the modifier select shown exactly where the code has a modifier review,
// with the options "", "59" and "XS", never prefilled, and the page posting exactly the modifier the walk chose.
function checkModifierDialogs(decisions, cust) {
  const codes = new Map((cust?.codes || []).map(code => [code.id, code]));
  return decisions.filter(d => d.action === 'approve' && d.http_status !== null).map(d => {
    const reviewed = Boolean(codes.get(d.proposal_id)?.modifier_review);
    const posted = Array.isArray(d.posted?.modifiers) ? d.posted.modifiers : [];
    const problems = [];
    if (d.modifier_offered !== reviewed) problems.push(`the modifier choice is ${d.modifier_offered ? 'shown' : 'not shown'} where the code ${reviewed ? 'has' : 'has no'} modifier review`);
    if (d.modifier_offered && !sameList(d.modifier_options, MODIFIER_OPTIONS)) problems.push(`options ${JSON.stringify(d.modifier_options)}`);
    if (d.modifier_offered && d.modifier_prefilled !== '') problems.push(`prefilled with ${JSON.stringify(d.modifier_prefilled)}`);
    if (!sameList(posted, d.modifier ? [d.modifier] : [])) problems.push(`the page posted modifiers ${JSON.stringify(posted)} (chosen ${JSON.stringify(d.modifier || null)})`);
    return check(`decision.modifier.${d.code}`, 'hard', problems.length === 0, problems.join('; ') || (d.modifier ? `modifier ${d.modifier} chosen and posted; nothing prefilled` : 'no modifier chosen, none posted'));
  });
}

// --- the customer downloads (CORE-UX-DESIGN 5) -------------------------------------------------------------------------

function expectedCustomerDownloads(readiness) {
  return ['draft', 'approved'].filter(kind => readiness?.[kind] === true).flatMap(kind => ['txt', 'csv'].map(fmt => `${kind}.${fmt}`));
}

// Each download the customer readiness owes: made, re-fetched to the same bytes, with no X-Content-SHA256 on the
// customer download, the operator listing naming it a customer artifact with that sha256 and the operator's stored
// bytes (and their X-Content-SHA256) the same; one at least made at mobile width; and, while the approved export is not
// available, its option shown disabled with every blocker listed.
function checkCustomerDownloads(downloads, readiness, withheld) {
  const out = [];
  const wanted = expectedCustomerDownloads(readiness);
  for (const want of wanted) {
    const d = downloads.find(item => `${item.kind}.${item.fmt}` === want);
    if (!d || d.error) {
      out.push(check(`download.${want}`, 'hard', false, d ? d.error : 'not downloaded'));
      continue;
    }
    const problems = [];
    if (!saved(d.http_status)) problems.push(`HTTP ${d.http_status}`);
    if (!(d.size > 0)) problems.push('empty');
    if (d.refetch_sha256 !== d.sha256) problems.push(`re-fetch ${d.refetch_sha256}`);
    if (d.header_sha256) problems.push('the customer download carries X-Content-SHA256');
    if (d.operator_sha256 !== d.sha256) problems.push(`the operator listing says ${d.operator_sha256 ?? 'nothing'}`);
    if (d.operator_audience !== 'customer') problems.push(`the operator listing calls it ${JSON.stringify(d.operator_audience ?? null)}, not a customer artifact`);
    if (d.operator_download_sha256 !== d.sha256 || d.operator_header_sha256 !== d.sha256) problems.push(`the operator's stored bytes ${d.operator_download_sha256 ?? 'not read'} (header ${d.operator_header_sha256 ?? 'none'})`);
    out.push(check(`download.${want}`, 'hard', problems.length === 0, problems.join('; ') || `${d.size} bytes; ${d.sha256}, as re-fetched and as the operator holds it`));
  }
  if (wanted.length) {
    out.push(check('download.mobile', 'hard', downloads.some(d => d.viewport === 'mobile' && !d.error), downloads.some(d => d.viewport === 'mobile')
      ? `made at 390x844: ${downloads.filter(d => d.viewport === 'mobile').map(d => `${d.kind}.${d.fmt}${d.error ? ` (${d.error})` : ''}`).join(', ')}` : 'no download was made at mobile width'));
  }
  if (readiness?.approved !== true) {
    const options = (withheld?.options || []).filter(option => option.kind === 'approved');
    const blockers = readiness?.blockers || [];
    const listed = blockers.every(blocker => collapse(withheld?.text || '').includes(collapse(blocker)));
    out.push(check('download.approved_withheld', 'hard', options.length > 0 && options.every(option => option.disabled) && listed,
      !options.length ? 'the export dialog shows no approved option' : options.some(option => !option.disabled) ? 'the approved export is offered before the review is complete'
        : listed ? `offered disabled, with ${blockers.length} blocker(s) listed` : `offered disabled, but not every blocker is listed (${blockers.join('; ')})`));
  }
  return out;
}

// Each download listed on the encounter as current, by its id, kind and format.
function checkCustomerListing(downloads, cust) {
  const reports = cust?.reports || [];
  return downloads.filter(d => d.report_id).map(d => {
    const r = reports.find(item => item.id === d.report_id);
    return check(`listing.${d.kind}.${d.fmt}`, 'hard', Boolean(r) && r.kind === d.kind && r.fmt === d.fmt && r.current === true,
      r ? `listed ${r.kind}/${r.fmt}${r.current ? ', current' : ', NOT current'}` : 'not listed on the encounter');
  });
}

// --- the physician's addendum (review_plan.addendum; completion repair 2026-11-06, U11) ---------------------------------

// review_plan.addendum: {"fact": F, "code"?: C, "text": T, "expect_ready"?: [codes]} - the physician's own documentation,
// added through the details panel's control as a new revision. The panel offers the addendum only on an OPEN row, and a
// saved "Not documented" closes it, so a saved answer of the row is first withdrawn through the page's "Change this
// answer" (a recompute: nothing sent) and the addendum is then added from the reopened row. The new revision is read by
// the providers again (a paid stage), so this step runs only where a manifest names it.
async function addAddendum(page, ctx, op, id, plan, cust, deadlineAt, history) {
  const out = { record: { plan: { fact: plan.fact, code: plan.code || null, characters: Array.from(plan.text || '').length } }, error: null };
  const rowsOf = c => (c?.details_needed || []).filter(row => row.fact === plan.fact && (!plan.code || (row.affects || []).includes(plan.code)));
  out.before = { cust, op: await fetchOperator(op, ctx, id) };
  let current = cust;
  const saved = rowsOf(current).find(row => row.saved && row.saved.answer_id);
  if (saved) {
    const own = page.locator(`#detail-${attributeValue(saved.id)}-revoke`);
    const earlier = page.locator(`#earlier-${attributeValue(saved.saved.answer_id)}-revoke`);
    const button = (await own.count()) ? own : earlier;
    if (!(await button.count())) { out.error = `no "Change this answer" control for the saved ${plan.fact} answer`; return out; }
    await button.first().click({ timeout: UI_TIMEOUT_MS });
    out.record.withdrew = saved.saved.answer_id;
    const settled = await waitForProcessing(page, ctx, id, deadlineAt, history);
    if (settled.timedOut) { out.error = 'the recompute after withdrawing the answer did not finish'; return out; }
    current = await fetchCustomer(page, ctx, id);
    out.reopened = { cust: current, op: await fetchOperator(op, ctx, id) };
  }
  const open = rowsOf(current).filter(row => !row.saved && row.addendum_allowed === true);
  out.record.open_rows = open.length;
  if (open.length !== 1) { out.error = `expected one open ${plan.fact} row that offers the addendum, found ${open.length}`; return out; }
  const target = `/api/encounters/${id}/addenda`;
  const seen = [];
  const listen = request => { if (request.method() === 'POST' && pathnameOf(request.url()) === target) seen.push(request); };
  page.on('request', listen);
  try {
    await page.click(`section.details-panel button.detail-addendum[data-detail="${attributeValue(open[0].id)}"]`, { timeout: UI_TIMEOUT_MS });
    await page.fill('#addendumText', plan.text, { timeout: UI_TIMEOUT_MS });
    await page.check('#addendumAttestation', { timeout: UI_TIMEOUT_MS });
    const answered = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === target, { timeout: UI_TIMEOUT_MS }));
    await page.click('#saveAddendum', { timeout: UI_TIMEOUT_MS });
    const response = await answered.catch(() => null);
    await page.waitForTimeout(600);  // a second request the page made for the same addendum is counted too
    out.record.requests = seen.length;
    out.record.http_status = response ? response.status() : null;
  } finally {
    page.off('request', listen);
  }
  if (!out.record.http_status || out.record.http_status >= 300) { out.error = `the addendum was not accepted (HTTP ${out.record.http_status})`; return out; }
  const settled = await waitForProcessing(page, ctx, id, deadlineAt, history);
  if (settled.timedOut) { out.error = 'processing after the addendum did not finish'; return out; }
  out.after = { op: await fetchOperator(op, ctx, id), cust: await fetchCustomer(page, ctx, id) };
  const rev = r => r && { id: r.id, number: r.number, total: r.revisions_total, kind: r.kind };
  out.record.revision = { before: rev(out.before.op?.revision), after: rev(out.after.op?.revision) };
  return out;
}

function checkAddendum(plan, step) {
  const out = [];
  out.push(check('addendum.added', 'hard', !step.error && step.record.requests === 1 && step.record.http_status >= 200 && step.record.http_status < 300,
    step.error || `one POST /addenda for one addendum (HTTP ${step.record.http_status}${step.record.withdrew ? '; the saved answer was withdrawn first' : ''})`));
  if (step.error || !step.after) return out;
  const before = step.record.revision?.before;
  const after = step.record.revision?.after;
  out.push(check('addendum.new_revision', 'hard', Boolean(before && after) && after.kind === 'addendum' && after.id !== before.id
    && after.total === before.total + 1 && after.number === before.number + 1,
  `revision ${before?.number} of ${before?.total} -> ${after?.number} of ${after?.total} (${after?.kind})`));
  const rows = (step.after.cust?.details_needed || []).filter(row => row.fact === plan.fact && (!plan.code || (row.affects || []).includes(plan.code)));
  const applied = rows.filter(row => row.saved);
  out.push(check('addendum.earlier_answer_not_applied', 'hard', applied.length === 0,
    applied.length ? `${plan.fact} still shows a saved answer on the new revision` : `no answer of ${plan.fact} is applied to the new revision`));
  for (const code of plan.expect_ready || []) {
    const found = proposalsOf(step.after.op).filter(p => p.code === code && p.bucket === 'selected');
    out.push(check(`addendum.ready.${code}`, 'hard', found.length === 1 && found[0].status === 'ready',
      `${code} after the addendum: ${found.map(p => `${p.bucket}/${p.status}`).join(', ') || 'not proposed'}`));
  }
  return out;
}

// --- the details panel: answers as member context (directive section 4) ------------------------------------------------

// The answers a document's plan makes through the details panel: review_plan.details as written, and a context_edit
// (the member date conflict, or the open date question) as the date row's answer.
function detailsPlan(doc) {
  const plan = doc?.review_plan || {};
  const answers = Array.isArray(plan.details) ? plan.details.map(item => ({ fact: item.fact, value: item.value, ...(item.code ? { code: String(item.code) } : {}) })) : [];
  const edit = contextEditPlan(doc);
  if (edit) answers.unshift({ fact: 'service_date', value: edit.clear_member_date ? 'use_document' : edit.service_date, context_edit: true });
  return answers;
}

// The details row an answer is for: the row of its fact (and, given, the one whose affects lists its code).
function detailRowFor(cust, answer) {
  const rows = (cust?.details_needed || []).filter(row => row.fact === answer.fact && (!answer.code || (row.affects || []).includes(answer.code)));
  return rows.length === 1 ? rows[0] : null;
}

// before / after: {cust, op} once the save's processing settled (after) and before it (before); save: what saveDetails
// did; reloaded: {cust, op, dom} after a reload; account: the signed-in member.
function checkDetailsSave(answers, before, after, save, reloaded, account) {
  const out = [];
  // one request for the one save, carrying exactly the answers the walk made (a row left unanswered may be sent empty)
  const posted = Array.isArray(save?.posted?.answers) ? save.posted.answers : null;
  const planned = answers.map(answer => ({ id: save?.rows?.[answer.fact + (answer.code || '')], fact: answer.fact, value: answer.value }));
  const filled = (posted || []).filter(item => item && item.value !== '' && item.value !== null && item.value !== undefined);
  const same = (a, b) => a.id === b.id && a.fact === b.fact && a.value === b.value;
  const exact = Boolean(posted) && planned.every(p => filled.some(item => same(item, p))) && filled.every(item => planned.some(p => same(item, p)));
  out.push(check('details.request', 'hard', save?.requests === 1 && saved(save?.http_status) && exact,
    `${save?.requests ?? 0} POST /details request(s) for one save (HTTP ${save?.http_status ?? 'none'}${save?.error ? `: ${save.error}` : ''}); posted ${JSON.stringify(save?.posted ?? null)}`
      + (posted && !exact ? `; the answers made were ${JSON.stringify(planned)}` : '')));
  if (!saved(save?.http_status) || !after) return out;
  const rev = item => [item?.op?.revision?.id, item?.op?.revision?.number, item?.op?.revision?.revisions_total];
  out.push(check('details.not_a_revision', 'hard', JSON.stringify(rev(before)) === JSON.stringify(rev(after)) && (!reloaded || JSON.stringify(rev(before)) === JSON.stringify(rev(reloaded))),
    `revision ${before?.op?.revision?.number} (${before?.op?.revision?.revisions_total} in all) -> ${after?.op?.revision?.number} (${after?.op?.revision?.revisions_total})`));
  const member = answers.filter(answer => ['not_documented', 'cannot_confirm'].includes(answer.value));
  for (const [label, state] of [['after_save', after], ...(reloaded ? [['after_reload', reloaded]] : [])]) {
    const problems = [];
    for (const answer of answers) {
      const values = state?.op?.context?.user_values || {};
      if (answer.fact === 'service_date' && answer.value === 'use_document') {
        if (values.service_date) problems.push(`the member date ${values.service_date} is still held`);
        if (state?.cust?.service_date?.source !== 'document' || state?.cust?.service_date?.conflict) problems.push(`the date reads ${state?.cust?.service_date?.source}${state?.cust?.service_date?.conflict ? ', still in conflict' : ''}`);
      } else if (answer.fact === 'service_date' && isoDate(answer.value)) {
        if (values.service_date !== answer.value) problems.push(`the member date is ${JSON.stringify(values.service_date ?? null)}, not ${answer.value}`);
      } else if (['setting', 'billing_context'].includes(answer.fact) && !DETAIL_VALUES.has(answer.value)) {
        if (values[answer.fact] !== answer.value) problems.push(`the member's ${answer.fact} is ${JSON.stringify(values[answer.fact] ?? null)}, not ${answer.value}`);
      } else {
        const row = detailRowFor(state?.cust, answer);
        const shown = row?.saved;
        if (!shown) problems.push(`${answer.fact}${answer.code ? ` (${answer.code})` : ''} shows no saved answer`);
        else {
          if (shown.value !== answer.value) problems.push(`${answer.fact} saved as ${JSON.stringify(shown.value)}`);
          if (account?.label && shown.by !== account.label) problems.push(`${answer.fact} attributed to ${JSON.stringify(shown.by)}, not ${JSON.stringify(account.label)}`);
          if (!(typeof shown.at === 'string' && ISO_TIMESTAMP.test(shown.at))) problems.push(`${answer.fact} saved with no time`);
          if (!shown.answer_id) problems.push(`${answer.fact} saved with no answer id`);
          if (label === 'after_reload' && reloaded?.dom) {
            const domRow = (reloaded.dom.details?.rows || []).find(item => item.id === row.id);
            if (!domRow || domRow.saved === null) problems.push(`${answer.fact} is not shown as saved on the reloaded page`);
          }
        }
      }
    }
    out.push(check(label === 'after_save' ? 'details.member_context' : 'details.persist_after_reload', 'hard', problems.length === 0,
      problems.join('; ') || `${answers.length} answer(s) held as the member's context, attributed to ${account?.label ?? 'the member'}${label === 'after_reload' ? ', after a reload' : ''}`));
  }
  const asked = [];
  for (const answer of answers) {
    const again = ((reloaded || after)?.cust?.details_needed || []).filter(row => row.fact === answer.fact && (!answer.code || (row.affects || []).includes(answer.code)) && !row.saved);
    if (again.length) asked.push(`${answer.fact} asked again, unsaved`);
  }
  out.push(check('details.asked_once', 'hard', asked.length === 0, asked.join('; ') || 'no answered question is asked again'));
  if (member.length) {
    const fresh = (after?.op?.provider_runs || []).filter(run => !(before?.op?.provider_runs || []).some(item => item.id === run.id));
    const onlyMember = member.length === answers.length;
    out.push(check('details.member_answer_sends_nothing', onlyMember ? 'hard' : 'soft', !onlyMember || fresh.length === 0,
      `${fresh.length} new run(s) after a save of ${member.length} "not documented" / "cannot confirm" answer(s)${onlyMember ? '' : ' (with context answers beside them)'}`));
  }
  return out;
}

// Completion repair (2026-11-06, U11): a "Not documented" or "Cannot confirm" answer given for a code re-makes the
// assessment from the recorded runs (jobs.recompute_after_answers). Once that recompute settled, read from the operator
// view: every proposal of the code is excluded, with the 'member.answer' check naming the answer
// (engine._MemberAnswers._excluded), and no question of the answered fact is still open for it. state: {op} after the
// save's processing settled (the reloaded one, when the walk reloaded).
const MEMBER_ANSWER_LABELS = { not_documented: 'Not documented', cannot_confirm: 'Cannot confirm' };
function checkMemberAnswers(answers, state) {
  const op = state?.op;
  if (!op) return [];
  const proposals = proposalsOf(op);
  return (answers || []).filter(answer => MEMBER_ANSWER_LABELS[answer.value] && answer.code).flatMap(answer => {
    const label = MEMBER_ANSWER_LABELS[answer.value];
    const rows = proposals.filter(p => p.code === answer.code);
    const byAnswer = p => isExcluded(p) && (p.checks || []).some(c => c.id === 'member.answer' && c.status !== 'pass' && String(c.detail || '').includes(`"${label}"`));
    const left = rows.filter(p => !byAnswer(p));
    const ids = new Set(rows.map(p => p.id));
    const open = (op.clarifications || []).filter(c => c.state === 'open' && c.fact === answer.fact && ids.has(c.proposal_id));
    return [
      check(`details.member_answer.${answer.code}.excluded`, 'hard', rows.length > 0 && left.length === 0,
        !rows.length ? `no proposal of ${answer.code} in the recomputed assessment`
          : left.length ? `${left.map(p => `${p.code} ${p.bucket}/${p.status}`).join(', ')}: not excluded by the member's "${label}" answer`
            : `${rows.length} proposal(s) of ${answer.code} excluded by the member's "${label}" answer`),
      check(`details.member_answer.${answer.code}.question_closed`, 'hard', open.length === 0,
        open.length ? `${open.length} ${answer.fact} question(s) still open for ${answer.code}` : `no ${answer.fact} question open for ${answer.code}`),
    ];
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
    clarifications: (enc.clarifications || []).map(c => ({ fact: c.fact, scope: c.scope, family: c.family, state: c.state,
      // harness@2: the candidates (their values are CPT Studio's own words, never a passage) and the confirmation's id
      ...(Array.isArray(c.candidates) ? { candidates: c.candidates.map(x => ({ id: x?.id, value: x?.value, verified: x?.verified, located_by: x?.located_by, phase: x?.phase })),
        confirmation: c.confirmation && typeof c.confirmation === 'object' ? c.confirmation.id : null } : {}) })),
    ...(Array.isArray(enc.confirmations) ? { confirmations: enc.confirmations.map(c => ({ id: c?.id, fact: c?.fact, value: c?.value, located_by: c?.located_by,
      confirmed_by: c?.confirmed_by, confirmed_by_kind: c?.confirmed_by_kind, created_at: c?.created_at })) } : {}),
    provider_runs: (enc.provider_runs || []).map(r => ({ provider: r.provider, mode: r.mode, state: r.state, http_status: r.http_status, usage: r.usage, usage_basis: r.usage_basis, reused_from: r.reused_from, latency_ms: r.latency_ms, purpose: r.purpose, scope_items: r.scope_items, request_sha256: r.request_sha256, member_date_hold: isMemberDateHold(r) })),
    user_values: enc.context?.user_values || {},
    readiness: enc.readiness,
    // Which participants ran, with which models, and what reference validation retrieved (HARNESS.md 7): structured
    // fields only, never a participant's sentence, which can quote the document.
    harness: enc.harness && Array.isArray(enc.harness.participants) ? {
      participants: enc.harness.participants.map(p => ({ name: p?.name, state: p?.state, model: p?.model, returned_model: p?.returned_model,
        run_id: p?.run_id, reused: p?.reused, codes: p?.codes, unverified_quotes: p?.unverified_quotes, usage_basis: p?.usage_basis,
        estimated_cost_usd: p?.estimated_cost_usd,
        // harness@2: its peer review and its references by phase, counted - never a sentence or a reference's use
        ...('peer' in (p || {}) ? { peer: { state: p.peer?.state, run_id: p.peer?.run_id, codes_added: p.peer?.codes_added, unverified_quotes: p.peer?.unverified_quotes },
          references: referenceCounts(p.references), peer_references: referenceCounts(p.peer_references) } : {}) })),
      ...('phase' in enc.harness ? { phase: enc.harness.phase } : {}),
      reference_validation: { state: enc.harness.reference_validation?.state, codes_checked: enc.harness.reference_validation?.codes_checked,
        passages: enc.harness.reference_validation?.passages, sources: (enc.harness.reference_validation?.sources || []).map(s => s?.key) },
      final: enc.harness.final?.state,
    } : null,
  };
}

// What one participant run retrieved with its own tools and what it says it used (HARNESS.md 11.2), counted.
function referenceCounts(references) {
  const list = name => (references && Array.isArray(references[name]) ? references[name].filter(item => item && typeof item === 'object') : []);
  return { retrieved: list('retrieved').length, used: list('used').length, cited_not_retrieved: list('used').filter(item => item.retrieved !== true).length };
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

// ops/verify_login.py _read_private: the content and mode of a private regular file, checked on the descriptor that is
// read; a file a group or other user may read or write is refused before a byte of it is read.
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
      if (total > MAX_PASSWORD_FILE_BYTES) throw new UsageError(`the ${what} ${file} is over ${MAX_PASSWORD_FILE_BYTES} bytes`);
      chunks.push(chunk.subarray(0, read));
    }
    return { content: Buffer.concat(chunks), mode };
  } finally {
    fs.closeSync(fd);
  }
}

// ops/verify_login.py load_password_file: a private file holding only the password; one trailing line break (LF or
// CRLF) is not part of it. Its content is never quoted.
function loadPasswordFile(file, username) {
  const { content, mode } = readPrivate(file, 'password file');
  let password;
  try {
    password = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(content);
  } catch {
    throw new UsageError(`the password file ${file} is not UTF-8 text`);
  }
  if (password.endsWith('\n')) {
    password = password.slice(0, -1);
    if (password.endsWith('\r')) password = password.slice(0, -1);
  }
  if (!password || /[\r\n]/.test(password)) throw new UsageError(`the password file ${file} must hold one non-empty line`);
  return { username, password, source: 'password_file', mode };
}

// What the evidence keeps of the sign-in: the account, never its password (a credentials file's record is as before).
function credentialsRecord(creds) {
  if (creds.source === 'password_file') {
    return { username: creds.username, source: 'password_file', file_mode: creds.mode.toString(8).padStart(4, '0') };
  }
  return { username: creds.username, file_group_or_other_readable: creds.groupOrOtherReadable };
}

// Whether DEBUG could turn on a Playwright log that carries the password (PASSWORD_LOGS). The debug package reads DEBUG as
// names split by commas or whitespace, '*' matching anything; older releases read each name as a regular expression. A
// name is matched both ways, an unreadable one counts, and a '-' exclusion is never relied on.
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

// ops/verify_login.py Secret: every form in which a password could reach an output - as typed, percent- and
// form-encoded, HTML-escaped, inside a JSON string - longest first.
function secretForms(password) {
  const text = String(password);
  const html = quote => {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return quote ? escaped.replace(/"/g, '&quot;').replace(/'/g, '&#x27;') : escaped;
  };
  const json = JSON.stringify(text).slice(1, -1);
  const forms = new Set([text, html(true), html(false), json,
    json.replace(/[\u007f-\uffff]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`)]);
  try {
    const percent = encodeURIComponent(text);
    const strict = percent.replace(/[!'()*]/g, c => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
    for (const form of [percent, strict, strict.replace(/%20/g, '+'), new URLSearchParams([['p', text]]).toString().slice(2)]) forms.add(form);
  } catch {
    // a lone surrogate has no percent-encoded form, and a UTF-8 password file cannot hold one
  }
  return [...forms].filter(Boolean).sort((a, b) => b.length - a.length);
}

// ``value`` (text, or a JSON value: keys and strings) with every form of the password replaced.
function scrubSecret(value, forms) {
  if (typeof value === 'string') return forms.reduce((text, form) => text.split(form).join(WITHHELD), value);
  if (Array.isArray(value)) return value.map(item => scrubSecret(item, forms));
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [scrubSecret(key, forms), scrubSecret(item, forms)]));
  }
  return value;
}

// --acceptance-reviewer: the signed-in reviewer as the session serves them, which each decision must be recorded as.
function reviewerAccount(session) {
  const user = session?.user || {};
  return { username: user.username ?? null, label: user.label ?? null, actor_kind: user.actor_kind ?? null,
    acknowledgement: session?.acknowledgement ?? null };
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
  const problems = [...new Set(selected.flatMap(doc => planProblems(doc, manifest.review_notes || {}, { acceptanceReviewer: opts.acceptanceReviewer })))];
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

// Runs in the customer page before any of its own scripts (context.addInitScript), in the page's own clock: each
// request the page makes through fetch or XMLHttpRequest, whether the upload acknowledgement was on screen when the page
// first asked for an encounter, and every toast or alert text it showed (a toast is gone before any later read).
function pageWatch() {
  if (window.__cptVerify) return;
  const state = { requests: [], gets: [], ack: null, toasts: [] };
  window.__cptVerify = state;
  const shown = el => Boolean(el) && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const squash = text => String(text || '').replace(/\s+/g, ' ').trim().slice(0, 300);
  const begin = (method, address) => {
    let where = '';
    try {
      where = new URL(String(address), location.href).pathname;
    } catch (error) {
      where = '';
    }
    const entry = { method: String(method || 'GET').toUpperCase(), path: where, t: performance.now(), status: null, t_end: null };
    if (state.requests.length < 1000) state.requests.push(entry);
    if (entry.method === 'GET' && /^\/api\/encounters\/[0-9a-f-]{36}$/.test(where)) {
      const ack = document.querySelector('.upload-ack');
      state.gets.push({ path: where, t: entry.t, ack_present: Boolean(ack), ack_visible: shown(ack), ack_text: ack ? squash(ack.textContent) : '' });
    }
    return entry;
  };
  // the field names a form body carries (never a value): Playwright serves no multipart body that holds a file, so this is
  // where the walk sees whether an upload carried its client key (the 2026-11-05 walk read postData() and saw none)
  const formKeys = body => (typeof FormData === 'function' && body instanceof FormData ? Array.from(body.keys()) : null);
  // whether the form's client_key is a UUID, as api._client_key requires (an empty key is read as none): a boolean
  const keyShaped = body => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(body.get('client_key') || ''));
  const original = window.fetch;
  if (typeof original === 'function') {
    window.fetch = function watchedFetch(input, init) {
      const entry = begin((init && init.method) || (input && input.method) || 'GET', typeof input === 'string' || input instanceof URL ? input : input && input.url);
      const keys = formKeys(init && init.body);
      if (keys) Object.assign(entry, { form_keys: keys, client_key_uuid: keyShaped(init.body) });
      return original.apply(this, arguments).then(response => {
        entry.status = response.status;
        entry.t_end = performance.now();
        return response;
      });
    };
  }
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function watchedOpen(method, address) {
    this.__cptVerify = { method, address };
    return open.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function watchedSend(body) {
    const asked = this.__cptVerify || {};
    const entry = begin(asked.method, asked.address);
    const keys = formKeys(body);
    if (keys) Object.assign(entry, { form_keys: keys, client_key_uuid: keyShaped(body) });
    this.addEventListener('loadend', () => {
      entry.status = this.status;
      entry.t_end = performance.now();
    });
    return send.apply(this, arguments);
  };
  const seen = new Set();
  const observe = () => {
    const ack = document.querySelector('.upload-ack');
    if (!state.ack && shown(ack)) state.ack = { t: performance.now(), text: squash(ack.textContent) };
    for (const el of document.querySelectorAll('#toast, [role="alert"], .toast, .form-error, .error-message, [role="status"]:not(.progress-panel)')) {
      const text = squash(el.textContent);
      if (text && !seen.has(text) && state.toasts.length < 200) {
        seen.add(text);
        state.toasts.push(text);
      }
    }
  };
  new MutationObserver(observe).observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
}

// Runs in the page: each element under the progress panel with a running CSS or Web animation.
function readAnimations() {
  const panel = document.querySelector('section.progress-panel');
  if (!panel) return [];
  const name = el => `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? `.${el.className.trim().split(/\s+/).join('.')}` : ''}`;
  const out = [];
  for (const el of [panel, ...panel.querySelectorAll('*')]) {
    const style = getComputedStyle(el);
    const names = String(style.animationName || 'none').split(',').map(item => item.trim()).filter(item => item && item !== 'none');
    const running = String(style.animationPlayState || 'running').split(',').some(item => item.trim() === 'running');
    const lasting = String(style.animationDuration || '0s').split(',').some(item => parseFloat(item) > 0);
    if (names.length && running && lasting) out.push(`${name(el)} (${names.join(', ')})`);
  }
  if (typeof document.getAnimations === 'function') {
    for (const animation of document.getAnimations()) {
      const target = animation.effect && animation.effect.target;
      if (target && panel.contains(target) && animation.playState === 'running') out.push(`${name(target)} (running animation)`);
    }
  }
  return [...new Set(out)];
}

// Runs in the page: every text node and the wording attributes of every element (scripts, styles and templates aside;
// the CSRF field's token is no wording), for the negative scan.
function collectDomStrings() {
  const out = [];
  const keep = /^(?:aria-[\w-]+|data-[\w-]+|title|alt|placeholder|value|label|href|src|action|download|content)$/i;
  const ignore = el => Boolean(el && el.closest && el.closest('script, style, template, noscript'));
  const csrf = el => el.getAttribute && el.getAttribute('name') === 'csrfmiddlewaretoken';
  const describe = el => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.className && typeof el.className === 'string' && el.className.trim() ? `.${el.className.trim().split(/\s+/)[0]}` : ''}`;
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let node = walker.currentNode; node; node = walker.nextNode()) {
    if (node.nodeType === Node.TEXT_NODE) {
      const parent = node.parentElement;
      if (node.nodeValue && node.nodeValue.trim() && parent && !ignore(parent)) out.push(['text', describe(parent), node.nodeValue]);
    } else if (node.nodeType === Node.ELEMENT_NODE && !ignore(node) && !csrf(node)) {
      for (const attribute of Array.from(node.attributes)) if (keep.test(attribute.name)) out.push(['attr', `${describe(node)}@${attribute.name}`, attribute.value]);
      if (/^(?:INPUT|TEXTAREA|SELECT)$/.test(node.tagName) && node.type !== 'hidden' && node.value) out.push(['value', describe(node), String(node.value)]);
    }
    if (out.length >= 20000) break;
  }
  out.push(['title', 'document.title', document.title]);
  return out;
}

async function readToasts(page) {
  return page.evaluate(() => (window.__cptVerify ? window.__cptVerify.toasts.slice() : [])).catch(() => []);
}

// What the page shows now (readCustomerDom), and its strings kept for the negative scan.
async function readPage(page, ctx) {
  const dom = await page.evaluate(readCustomerDom);
  for (const [kind, where, value] of await page.evaluate(collectDomStrings)) if (!ctx.domStrings.has(value)) ctx.domStrings.set(value, `${kind} ${where}`);
  for (const toast of await readToasts(page)) ctx.toasts.add(toast);
  return dom;
}

// A reload of the page: its toasts are read first (a reload forgets them).
async function reloadPage(page, ctx) {
  for (const toast of await readToasts(page)) ctx.toasts.add(toast);
  await page.reload({ waitUntil: 'domcontentloaded' });
}

// Same-origin customer API responses the PAGE received, kept for the scans (a report download's bytes are scanned as the
// saved file; an original is the document itself, so only its headers are kept).
async function captureResponse(response, watch, base) {
  const ctx = watch.current;
  if (!ctx) return;
  let url;
  try {
    url = new URL(response.url());
  } catch {
    return;
  }
  if (url.origin !== base || !url.pathname.startsWith('/api/')) return;
  const entry = { via: 'page', method: response.request().method(), path: url.pathname, status: response.status(), headers: response.headers(), body: null };
  if (!/\/download$|\/original$/.test(url.pathname)) entry.body = await response.text().catch(() => null);
  if (ctx.bodies.length < 600) ctx.bodies.push(entry);
  if (entry.method === 'GET' && /^\/api\/encounters\/[0-9a-f-]{36}$/.test(url.pathname) && entry.body) {
    try {
      ctx.lastServed.set(url.pathname.split('/').pop(), { at: Date.now(), json: JSON.parse(entry.body) });
    } catch {
      // not JSON: the contract check of the walk's own read says so
    }
  }
}

async function remember(ctx, method, where, response, via = 'walk') {
  const body = await response.text().catch(() => '');
  if (ctx.bodies.length < 600) ctx.bodies.push({ via, method, path: where, status: response.status(), headers: response.headers(), body });
  return body;
}

async function fetchCustomer(page, ctx, id) {
  const where = `/api/encounters/${id}`;
  const response = await page.request.get(`${ctx.base}${where}`, { headers: { Accept: 'application/json', ...CLIENT_HEADERS }, timeout: UI_TIMEOUT_MS });
  const body = await remember(ctx, 'GET', where, response);
  if (!response.ok()) throw new Error(`GET ${where} answered HTTP ${response.status()}`);
  return JSON.parse(body);
}

// The encounter ids of the customer's list (GET /api/encounters).
async function customerListIds(page, ctx) {
  const response = await page.request.get(`${ctx.base}/api/encounters`, { headers: { Accept: 'application/json', ...CLIENT_HEADERS }, timeout: UI_TIMEOUT_MS });
  const body = await remember(ctx, 'GET', '/api/encounters', response);
  if (!response.ok()) throw new Error(`GET /api/encounters answered HTTP ${response.status()}`);
  const list = JSON.parse(body);
  if (!ctx.listChecked) {
    ctx.listChecked = true;
    ctx.listContract = checkCustomerContract(list, 'list', 'customer.list_contract');
  }
  return (Array.isArray(list?.encounters) ? list.encounters : []).map(row => row?.id);
}

async function fetchOperatorJson(op, base, where) {
  const response = await op.request.get(`${base}${where}`, { headers: { Accept: 'application/json' }, timeout: UI_TIMEOUT_MS });
  if (!response.ok()) throw new Error(`operator GET ${where} answered HTTP ${response.status()}`);
  return response.json();
}

async function fetchOperator(op, ctx, id) {
  return fetchOperatorJson(op, ctx.base, `/ops/api/encounters/${id}`);
}

async function fetchOperatorTrace(op, ctx, id) {
  return fetchOperatorJson(op, ctx.base, `/ops/api/encounters/${id}/trace`).catch(() => null);
}

// Every report artifact of the encounter, as the operator listing serves it (a list, or {reports: [...]}).
async function fetchOperatorReports(op, ctx, id) {
  const body = await fetchOperatorJson(op, ctx.base, `/ops/api/encounters/${id}/reports`);
  return Array.isArray(body) ? body : Array.isArray(body?.reports) ? body.reports : [];
}

// A JSON POST with the page's own session, as a stale page or a repeated request makes it (the CSRF token from the
// cookie the page reads).
async function postJson(page, ctx, where, json) {
  const cookies = await page.context().cookies(ctx.base);
  const token = (cookies.find(cookie => cookie.name === CSRF_COOKIE) || {}).value || '';
  const response = await page.request.post(`${ctx.base}${where}`, { data: json, timeout: UI_TIMEOUT_MS, maxRedirects: 0,
    headers: { Accept: 'application/json', ...CLIENT_HEADERS, 'X-CSRFToken': token, Origin: ctx.base, Referer: `${ctx.base}/` } });
  const body = await remember(ctx, 'POST', where, response);
  let parsed = {};
  try {
    parsed = JSON.parse(body);
  } catch {
    parsed = {};
  }
  return { status: response.status(), error: saved(response.status()) ? null : parsed.error || `HTTP ${response.status()}`, location: response.headers().location || null };
}

async function signIn(page, base, creds) {
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
  return pathnameOf(page.url());
}

async function login(page, base, creds) {
  await signIn(page, base, creds);
  const response = await page.request.get(`${base}/api/session`, { headers: { Accept: 'application/json', ...CLIENT_HEADERS } });
  if (!response.ok()) throw new Error(`GET /api/session answered HTTP ${response.status()}`);
  return response.json();
}

// The operator's sign-in, in its own browser context, and the positive control: /ops/api/encounters must answer 200
// before any zero the walk reads from it can mean anything.
async function operatorSignIn(context, base, creds) {
  const page = await context.newPage();
  page.setDefaultTimeout(UI_TIMEOUT_MS);
  const landed = await signIn(page, base, creds);
  const control = await context.request.get(`${base}/ops/api/encounters`, { headers: { Accept: 'application/json' }, timeout: UI_TIMEOUT_MS });
  return { page, request: context.request, landed, control: control.status() };
}

// opts.acceptanceReviewer: the account --username names, a HUMAN one, in an active reviewer membership (CPT Studio GI
// interpretation 63); otherwise an agent account, as before (and, signed in with a password file, the one named). The
// customer session serves no username (CORE-UX-DESIGN 7): the account is then the one this fresh context signed in as.
// It serves no provider mode either, so the walk cannot tell a live provider from a recorded one: --allow-live-provider
// must accept that each new document may make a request with real usage.
function sessionProblems(session, opts) {
  const problems = [];
  const named = opts.username;
  const served = isObject(session?.user) && Object.prototype.hasOwnProperty.call(session.user, 'username');
  const other = named !== undefined && served && session.user.username !== named
    ? `the session is ${JSON.stringify(session.user?.username ?? null)}'s, not the named account ${JSON.stringify(named)}'s` : null;
  if (opts.acceptanceReviewer) {
    if (typeof named !== 'string' || !named) problems.push('no account was named (--username)');
    else if (other) problems.push(other);
    if (session.user?.actor_kind !== 'human') {
      problems.push(`the account's actor kind is ${JSON.stringify(session.user?.actor_kind ?? null)}: the acceptance test is made through the ordinary (human) reviewer account`);
    }
    if (session.role !== 'reviewer') problems.push(`the account's role in this workspace is ${JSON.stringify(session.role ?? null)}: the acceptance test is made through a reviewer membership`);
  } else {
    if (session.user?.actor_kind !== 'agent') problems.push(`the account is a ${session.user?.actor_kind} account; decisions must be recorded as agent review`);
    if (other) problems.push(other);
  }
  if (session.can_review !== true) problems.push('the account cannot review in this workspace');
  if (session.synthetic_only !== true) problems.push('the workspace does not report synthetic_only');
  if (Object.prototype.hasOwnProperty.call(session || {}, 'provider_mode')) {
    if (session.provider_mode === 'disabled') problems.push('provider_mode is disabled, so no proposals would be produced');
    if (session.provider_mode === 'live' && !opts.allowLiveProvider) problems.push('provider_mode is live: each new document may make a provider request with real usage; re-run with --allow-live-provider to accept');
  } else if (!opts.allowLiveProvider) {
    problems.push('the session serves no provider mode (the customer contract keeps it from customers), so this walk cannot tell a live provider from a recorded one: each new document may make a provider request with real usage; re-run with --allow-live-provider to accept');
  }
  return problems;
}

async function shot(page, docDir, outDir, record, name, viewport) {
  const size = VIEWPORTS[viewport];
  const file = path.join(docDir, `${name}-${viewport}-${size.width}x${size.height}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => null);
  if (fs.existsSync(file)) record.screenshots.push({ name, viewport, ...size, path: path.relative(outDir, file) });
}

async function uploadDocument(page, ctx, item, timings) {
  const { doc, file, delivery } = item;
  await page.evaluate(() => {
    const state = window.__cptVerify;
    if (state) {
      state.requests.length = 0;
      state.gets.length = 0;
      state.ack = null;
    }
  });
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
  const sent = String(response.request().postData() || '');
  // the acknowledgement as the page drew it, read once the page first asked for the new encounter (or 15 s passed)
  await page.waitForFunction(id => (window.__cptVerify?.gets || []).some(get => get.path === `/api/encounters/${id}`), body.id, { timeout: 15000 }).catch(() => {});
  const watch = await page.evaluate(() => (window.__cptVerify ? JSON.parse(JSON.stringify({ requests: window.__cptVerify.requests,
    gets: window.__cptVerify.gets, ack: window.__cptVerify.ack })) : null));
  return { id: body.id, watch, client_key: uploadCarriedClientKey(watch, sent) };
}

// Whether the upload POST carried its client key: the field names the page's own request recorder read from the form it
// sent (pageWatch: a body holding a file is never served by Playwright's postData()), else the text body Playwright saw.
function uploadCarriedClientKey(watch, sent = '') {
  const post = (watch?.requests || []).find(entry => entry && entry.method === 'POST' && entry.path === '/api/encounters');
  if (post && Array.isArray(post.form_keys)) return post.form_keys.includes('client_key') && post.client_key_uuid === true;
  return /name="client_key"/.test(String(sent || ''));
}

function isBusy(enc) {
  return enc?.progress?.busy === true || enc?.state === 'processing';
}

// Read-only polling of the customer encounter (what the page reads): a failed GET is recorded and polled again (at most
// MAX_POLL_ERRORS in a row); nothing is ever re-submitted. sampler(enc) runs on each busy read.
async function waitForProcessing(page, ctx, id, deadlineAt, history, sampler = null) {
  let errors = 0;
  for (;;) {
    let enc;
    try {
      enc = await fetchCustomer(page, ctx, id);
      errors = 0;
    } catch (error) {
      errors += 1;
      history.push({ at: isoNow(), error: String(error.message || error) });
      if (errors >= MAX_POLL_ERRORS || Date.now() + POLL_MS > deadlineAt) throw error;
      await page.waitForTimeout(POLL_MS);
      continue;
    }
    const busy = isBusy(enc);
    const last = history.filter(h => !h.error).pop();
    if (!last || last.state !== enc.state || last.phase !== (enc.progress?.phase ?? null) || last.busy !== busy) {
      history.push({ at: isoNow(), state: enc.state, phase: enc.progress?.phase ?? null, busy });
    }
    if (busy && sampler) await sampler(enc);
    if (!busy) return { enc, timedOut: false };
    if (Date.now() + POLL_MS > deadlineAt) return { enc, timedOut: true };
    await page.waitForTimeout(POLL_MS);
  }
}

// The encounter's screen is drawn: its progress panel, its result list or its details panel.
async function waitForEncounterScreen(page) {
  await page.waitForFunction(() => Boolean(document.querySelector('section.progress-panel') || document.querySelector('ol.result-list')
    || document.querySelector('section.details-panel')), null, { timeout: UI_TIMEOUT_MS });
}

// The result screen: no .progress-card (the panel carries it only while busy), and the result or the details drawn.
async function waitForResults(page) {
  await page.waitForFunction(() => !document.querySelector('.progress-card') && Boolean(document.querySelector('ol.result-list')
    || document.querySelector('section.details-panel') || document.querySelector('section.progress-panel')), null, { timeout: UI_TIMEOUT_MS });
}

// One sample of the progress panel against the encounter the PAGE was last served (never the walk's own read, which can
// be newer than what the page drew); a mismatch is read once more, 900 ms later, before it counts.
async function sampleProgress(page, ctx, id) {
  const take = async () => ({ served: ctx.lastServed.get(id)?.json || null, dom: await readPage(page, ctx), animating: await page.evaluate(readAnimations) });
  const judge = item => (item.served ? checkProgressDom(item.served, item.dom, item.animating)
    : [check('progress.dom.served', 'hard', false, 'the page\'s own read of the encounter was not seen, so its panel could not be compared with it')]);
  let sample = await take();
  let results = judge(sample);
  if (results.some(r => r.status === 'fail')) {
    await page.waitForTimeout(900);
    sample = await take();
    results = judge(sample);
  }
  return { at: isoNow(), phase: sample.served?.progress?.phase ?? null, dom_phase: sample.dom.progress?.phase ?? null, served: Boolean(sample.served), results };
}

// The checks of every sample, one result per check id: failed if it failed on any sample (its first failure kept).
function mergeSamples(samples) {
  const merged = new Map();
  for (const sample of samples) {
    for (const result of sample.results) {
      const id = result.id.replace(/^progress\.dom\./, 'progress.sampled.');
      const seen = merged.get(id);
      if (!seen || (seen.status !== 'fail' && result.status === 'fail') || (seen.status === 'pass' && result.status === 'warn')) {
        merged.set(id, { ...result, id, reason: `${result.reason} (${samples.length} sample(s))` });
      }
    }
  }
  return [...merged.values()];
}

// One reload while the document processes: the same encounter, the same jobs, no duplicate request, and the screen back.
async function reloadWhileProcessing(page, ctx, op, id, cust) {
  const before = { url: page.url(), ids: await customerListIds(page, ctx), op: await fetchOperator(op, ctx, id), cust };
  await reloadPage(page, ctx);
  await waitForEncounterScreen(page).catch(() => {});
  const after = { url: page.url(), ids: await customerListIds(page, ctx), op: await fetchOperator(op, ctx, id),
    cust: await fetchCustomer(page, ctx, id), dom: await readPage(page, ctx) };
  const summary = state => ({ url_hash: String(state.url).split('#')[1] || '', encounters: state.ids.length,
    jobs: (state.op?.pipeline?.stages || []).map(stage => `${stage.kind}:${stage.state}`), runs: (state.op?.provider_runs || []).map(describeRun) });
  return { at: isoNow(), before: summary(before), after: { ...summary(after), phase: after.cust?.progress?.phase ?? null }, checks: checkReloadIdentity(id, before, after) };
}

// review_plan.stop_and_resume: the panel's Stop while the document processes, the stopped state read, nothing sent for
// QUIET_SECONDS_WHILE_STOPPED, then the panel's Resume and processing awaited. A confirmation the page asks for is
// accepted. Never a second Stop, never a retry.
async function stopAndResume(page, ctx, op, id, deadlineAt, history, outDir, docDir, record) {
  const out = { asked_at: isoNow(), stop_status: null, error: null, before: null, stopped: null, quiet: null, resume_status: null, resume_error: null, resumed: null };
  const stop = page.locator('section.progress-panel button[data-action="stop"]');
  const count = await stop.count();
  if (count !== 1) return { ...out, error: `expected one Stop in the progress panel, found ${count}` };
  out.before = { ids: await customerListIds(page, ctx), op: await fetchOperator(op, ctx, id) };
  page.once('dialog', dialog => dialog.accept().catch(() => {}));
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${id}/stop`, { timeout: UI_TIMEOUT_MS }));
  await stop.click({ timeout: UI_TIMEOUT_MS });
  const confirm = page.locator('dialog[open] button[data-action="confirm-stop"], dialog[open] button[value="confirm"]');
  if (await confirm.count()) await confirm.first().click().catch(() => {});
  const response = await posted.catch(() => null);
  out.stop_status = response ? response.status() : null;
  if (!saved(out.stop_status)) return { ...out, error: response ? `HTTP ${out.stop_status}` : 'no Stop request was made' };
  const until = Math.min(deadlineAt, Date.now() + 60000);
  let cust = await fetchCustomer(page, ctx, id);
  while (cust.state !== 'stopped' && isBusy(cust) && Date.now() + POLL_MS < until) {
    await page.waitForTimeout(POLL_MS);
    cust = await fetchCustomer(page, ctx, id);
  }
  history.push({ at: isoNow(), state: cust.state, phase: cust.progress?.phase ?? null, busy: isBusy(cust), after: 'stop' });
  await page.waitForFunction(() => document.querySelector('section.progress-panel')?.getAttribute('data-phase') === 'stopped', null, { timeout: 15000 }).catch(() => {});
  out.stopped = { cust, op: await fetchOperator(op, ctx, id), dom: await readPage(page, ctx), animating: await page.evaluate(readAnimations) };
  await shot(page, docDir, outDir, record, 'stopped', 'desktop');
  await page.waitForTimeout(QUIET_SECONDS_WHILE_STOPPED * 1000);
  out.quiet = { op: await fetchOperator(op, ctx, id) };
  if (stopRequested(outDir)) return { ...out, resume_error: 'not resumed: a STOP file is present' };
  const resume = page.locator('section.progress-panel button[data-action="resume"]');
  if (await resume.count() !== 1) return { ...out, resume_error: `expected one Resume in the progress panel, found ${await resume.count()}` };
  const resumed = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${id}/resume`, { timeout: UI_TIMEOUT_MS }));
  await resume.click({ timeout: UI_TIMEOUT_MS });
  const answer = await resumed.catch(() => null);
  out.resume_status = answer ? answer.status() : null;
  if (!saved(out.resume_status)) return { ...out, resume_error: answer ? `HTTP ${out.resume_status}` : 'no Resume request was made' };
  const { enc, timedOut } = await waitForProcessing(page, ctx, id, deadlineAt, history);
  out.resumed = { url: page.url(), ids: await customerListIds(page, ctx), op: await fetchOperator(op, ctx, id), cust: enc, dom: await readPage(page, ctx), timed_out: timedOut };
  return out;
}

function attributeValue(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

// The answers through the details panel, then its one Save (a choice the page saves at once is that save): every POST of
// the details endpoint the page made is counted.
async function saveDetails(page, ctx, id, cust, answers) {
  const out = { rows: {}, acts: [], requests: 0, posted: null, http_status: null, error: null };
  const target = `/api/encounters/${id}/details`;
  const seen = [];
  const listen = request => {
    if (request.method() === 'POST' && pathnameOf(request.url()) === target) seen.push(request);
  };
  page.on('request', listen);
  try {
    for (const answer of answers) {
      const row = detailRowFor(cust, answer);
      if (!row) {
        out.error = `no single details row asks ${answer.fact}${answer.code ? ` for ${answer.code}` : ''}`;
        return out;
      }
      out.rows[answer.fact + (answer.code || '')] = row.id;
      const scope = `section.details-panel .detail-row[data-detail="${attributeValue(row.id)}"]`;
      if (answer.value === 'use_document') {
        await page.click(`${scope} button[data-action="use-document-date"]`, { timeout: UI_TIMEOUT_MS });
      } else if (answer.value === 'not_documented' || answer.value === 'cannot_confirm') {
        const button = page.locator(`${scope} button[data-detail-choice="${answer.value}"]`);
        if (await button.count()) await button.first().click({ timeout: UI_TIMEOUT_MS });
        else await page.check(`${scope} input[type="radio"][value="${answer.value}"]`, { timeout: UI_TIMEOUT_MS });
      } else if (isoDate(String(answer.value)) && row.control === 'date') {
        await page.fill(`${scope} input[type="date"][data-detail-input]`, answer.value, { timeout: UI_TIMEOUT_MS });
      } else {
        await page.check(`${scope} input[type="radio"][name="detail-${attributeValue(row.id)}"][value="${attributeValue(answer.value)}"]`, { timeout: UI_TIMEOUT_MS });
      }
      out.acts.push(`${answer.fact}${answer.code ? ` (${answer.code})` : ''} = ${answer.value}`);
    }
    await page.waitForTimeout(400);
    if (!seen.length) {
      const save = page.locator('section.details-panel button[data-action="save-details"]');
      if (await save.count() === 0) {
        out.error = 'the details panel has no Save';
        return out;
      }
      const answered = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === target, { timeout: UI_TIMEOUT_MS }));
      await save.first().click({ timeout: UI_TIMEOUT_MS });
      await answered.catch(() => null);
    }
    await page.waitForTimeout(600);  // a second request the page makes for the same save is counted too
    out.requests = seen.length;
    if (!seen.length) {
      out.error = 'the details panel sent no request';
      return out;
    }
    try {
      out.posted = seen[0].postDataJSON();
    } catch {
      out.posted = null;
    }
    const response = await seen[0].response();
    out.http_status = response ? response.status() : null;
    if (!saved(out.http_status)) {
      const body = response ? await response.json().catch(() => ({})) : {};
      out.error = body.error || `HTTP ${out.http_status}`;
    }
    return out;
  } finally {
    page.off('request', listen);
  }
}

// review_plan.context_edit through the details panel's date row (the old proofs: one request, for the right date, the
// hold kept, the same save made again sending nothing - every run read from the operator view). repeat false
// (--acceptance-reviewer): the one save only.
async function editContext(page, ctx, op, id, plan, cust, deadlineAt, history, { repeat = true } = {}) {
  const answers = [{ fact: 'service_date', value: plan.clear_member_date ? 'use_document' : plan.service_date }];
  const out = { asked_at: isoNow(), form: null, posted: null, http_status: null, error: null, timed_out: false, after: null, after_customer: null,
    identical: { via: null, http_status: null, error: null, timed_out: false, panel_asks_again: null }, settled: null };
  const first = await saveDetails(page, ctx, id, cust, answers);
  out.form = { rows: first.rows, requests: first.requests, acts: first.acts };
  Object.assign(out, { posted: first.posted, http_status: first.http_status, error: first.error });
  if (!saved(first.http_status)) return out;
  const settled = await waitForProcessing(page, ctx, id, deadlineAt, history);
  out.after_customer = settled.enc;
  out.after = await fetchOperator(op, ctx, id);
  if (settled.timedOut) return { ...out, timed_out: true };
  await reloadPage(page, ctx);
  await waitForResults(page).catch(() => {});
  const now = await fetchCustomer(page, ctx, id);
  out.identical.panel_asks_again = (now.details_needed || []).some(row => row.fact === 'service_date' && !row.saved);
  if (!repeat) {
    out.identical.skipped = 'not made: the acceptance reviewer answers the clarification once, so the same save is not made again';
    return out;
  }
  const again = await postJson(page, ctx, `/api/encounters/${id}/details`, first.posted || { answers: answers.map(a => ({ id: first.rows.service_date, ...a })) });
  Object.assign(out.identical, { via: 'api', http_status: again.status, error: again.error });
  if (saved(again.status)) {
    const second = await waitForProcessing(page, ctx, id, deadlineAt, history);
    out.identical_view = await fetchOperator(op, ctx, id);
    out.settled = second.timedOut ? null : out.identical_view;
    out.identical.timed_out = second.timedOut;
  }
  await reloadPage(page, ctx);
  return out;
}

// A decision through the screen: its row's button -> the review dialog -> the acknowledgement for an approval -> the
// modifier (only one the plan names, and only where the dialog offers the choice) -> the note -> Save; then the row's
// status is awaited. onDialog(page) runs with the dialog open (a screenshot).
async function decide(page, encounterId, decision, { modifier = null, onDialog = null } = {}) {
  const record = { ...decision, modifier, http_status: null, decision_id: null, error: null, at: isoNow(), modifier_offered: false,
    modifier_options: null, modifier_prefilled: null, posted: null };
  const button = page.locator(`button[data-decision="${decision.action}"][data-proposal="${decision.proposal_id}"]`);
  if (await button.count() === 0) return { ...record, error: `no ${decision.action} button for ${decision.code}` };
  await button.first().click({ timeout: UI_TIMEOUT_MS });
  await page.locator('#reviewDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
  if (decision.action === 'approve') await page.check('#reviewAcknowledgement');
  const select = page.locator('#reviewDialog select#reviewModifier');
  record.modifier_offered = (await select.count()) > 0 && await select.first().isVisible();
  if (record.modifier_offered) {
    record.modifier_prefilled = await select.first().inputValue();
    record.modifier_options = await select.first().locator('option').evaluateAll(options => options.map(option => option.value));
  }
  if (modifier) {
    if (!record.modifier_offered) {
      await page.keyboard.press('Escape');
      return { ...record, error: `the review dialog offers no modifier for ${decision.code}` };
    }
    await select.first().selectOption(modifier);
  }
  await page.fill('#reviewNote', decision.note);
  if (onDialog) await onDialog(page);
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${encounterId}/decisions`, { timeout: UI_TIMEOUT_MS }));
  await page.click('#saveReview');
  const response = await posted;
  try {
    record.posted = response.request().postDataJSON();
  } catch {
    record.posted = null;
  }
  const body = await response.json().catch(() => ({}));
  record.http_status = response.status();
  record.decision_id = body.id || null;
  record.reviewer_kind = body.reviewer_kind || body.by_kind || null;
  if (record.http_status !== 201) return { ...record, error: body.error || `HTTP ${record.http_status}` };
  await page.locator('#reviewDialog').waitFor({ state: 'hidden', timeout: UI_TIMEOUT_MS });
  const wanted = decision.action === 'approve' ? ['approved'] : decision.action === 'reinstate' ? ['ready', 'needs_detail'] : ['excluded'];
  const shown = await page.waitForFunction(([id, states]) => {
    const row = document.querySelector(`ol.result-list > li.result-row[data-proposal="${id}"]`);
    return Boolean(row) && states.includes(row.getAttribute('data-status'));
  }, [decision.proposal_id, wanted], { timeout: UI_TIMEOUT_MS }).then(() => true, () => false);
  return { ...record, ui_updated: shown };
}

// The modifier review_plan.modifiers names for a decision: only for an approval, and only "59" or "XS".
function modifierFor(plan, decision) {
  const named = plan?.modifiers && typeof plan.modifiers === 'object' ? plan.modifiers[decision.code] : undefined;
  return decision.action === 'approve' && MODIFIER_CHOICES.has(named) ? named : null;
}

async function openExport(page) {
  if (await page.locator('#exportDialog[open]').count()) return;
  const openers = page.locator('[data-action="export"]');
  const count = await openers.count();
  for (let i = 0; i < count; i += 1) {
    if (await openers.nth(i).isVisible()) {
      await openers.nth(i).click({ timeout: UI_TIMEOUT_MS });
      break;
    }
  }
  await page.locator('#exportDialog').waitFor({ state: 'visible', timeout: UI_TIMEOUT_MS });
}

async function closeExport(page) {
  if (await page.locator('#exportDialog[open]').count()) await page.keyboard.press('Escape');
}

// One customer report through the export dialog as a real browser download, then: re-fetched with the customer session
// (no X-Content-SHA256 owed or allowed), found in the operator listing (its audience and sha256) and read back from the
// operator's stored bytes (and their X-Content-SHA256).
async function downloadReport(page, ctx, op, id, kind, fmt, docDir, outDir, viewport) {
  const record = { kind, fmt, audience: 'customer', viewport, offered: false, error: null };
  await openExport(page);
  const option = page.locator(`#exportDialog button.export-option[data-export-kind="${kind}"][data-export-fmt="${fmt}"]`);
  if (await option.count() === 0) return { ...record, error: 'the export dialog does not offer this report' };
  if (await option.first().isDisabled()) return { ...record, error: 'the export dialog offers this report disabled' };
  record.offered = true;
  const posted = settle(page.waitForResponse(r => r.request().method() === 'POST' && pathnameOf(r.url()) === `/api/encounters/${id}/reports`, { timeout: UI_TIMEOUT_MS }));
  const downloaded = settle(page.waitForEvent('download', { timeout: 60000 }));
  await option.first().click({ timeout: UI_TIMEOUT_MS });
  const response = await posted;
  const body = await response.json().catch(() => ({}));
  Object.assign(record, { http_status: response.status(), report_id: body.id || null, filename: body.filename || null, response_keys: Object.keys(body).sort() });
  if (!saved(record.http_status)) return { ...record, error: body.error || `HTTP ${record.http_status}` };
  const download = await downloaded;
  const failure = await download.failure();
  if (failure) return { ...record, error: `download failed: ${failure}` };
  const target = path.join(docDir, `${kind}-${fmt}-${safeName(download.suggestedFilename())}`);
  await download.saveAs(target);
  const bytes = fs.readFileSync(target);
  const again = await page.request.get(`${ctx.base}${body.download_url}`, { timeout: UI_TIMEOUT_MS });
  Object.assign(record, { suggested_filename: download.suggestedFilename(), path: path.relative(outDir, target), size: bytes.length,
    sha256: sha256(bytes), refetch_status: again.status(), refetch_sha256: sha256(await again.body()),
    header_sha256: again.headers()['x-content-sha256'] || null });
  ctx.bodies.push({ via: 'walk', method: 'GET', path: pathnameOf(`${ctx.base}${body.download_url}`), status: again.status(), headers: again.headers(), body: null });
  try {
    const listed = (await fetchOperatorReports(op, ctx, id)).find(item => item?.id === record.report_id) || null;
    Object.assign(record, { operator_sha256: listed?.sha256 ?? null, operator_audience: listed?.audience ?? null, operator_kind: listed?.kind ?? null });
    const stored = await op.request.get(`${ctx.base}/ops/api/reports/${record.report_id}/download`, { timeout: UI_TIMEOUT_MS });
    Object.assign(record, { operator_download_status: stored.status(), operator_download_sha256: stored.ok() ? sha256(await stored.body()) : null,
      operator_header_sha256: stored.headers()['x-content-sha256'] || null });
  } catch (error) {
    record.operator_error = String(error.message || error);
  }
  return record;
}

// The direct-URL authorization matrix of this encounter: the customer session against every /ops/ URL (GET, and POST
// with a body the operator views refuse), the old trace URL, and every operator-only artifact's customer download; no
// session at all against /ops/; and the operator reading what it must.
async function probeAuthorization(page, ctx, op, anonymous, id, reportIds, operatorArtifacts) {
  const probes = [];
  const base = ctx.base;
  const record = async (who, method, where, response, extra = {}) => {
    probes.push({ who, method, path: where, status: response ? response.status() : null, location: response ? response.headers().location || null : null, ...extra });
    if (response && who !== 'operator') {
      const body = await response.text().catch(() => '');
      if (ctx.bodies.length < 600) ctx.bodies.push({ via: `authorization:${who}`, method, path: where, status: response.status(), headers: response.headers(), body: body.slice(0, 200000) });
    }
  };
  const get = (request, where) => request.get(`${base}${where}`, { maxRedirects: 0, timeout: UI_TIMEOUT_MS, headers: { Accept: 'application/json', ...CLIENT_HEADERS } }).catch(() => null);
  for (const where of [...OPS_GET_PATHS(id), ...reportIds.map(report => `/ops/api/reports/${report}/download`), ...REMOVED_PATHS(id)]) await record('customer', 'GET', where, await get(page.request, where));
  const cookies = await page.context().cookies(base);
  const token = (cookies.find(cookie => cookie.name === CSRF_COOKIE) || {}).value || '';
  for (const where of OPS_POST_PATHS(id)) {
    const response = await page.request.post(`${base}${where}`, { data: OPS_POST_BODY, maxRedirects: 0, timeout: UI_TIMEOUT_MS,
      headers: { Accept: 'application/json', 'X-CSRFToken': token, Origin: base, Referer: `${base}/` } }).catch(() => null);
    await record('customer', 'POST', where, response);
  }
  for (const artifact of operatorArtifacts) {
    const where = `/api/reports/${artifact}/download`;
    await record('customer', 'GET', where, await get(page.request, where), { artifact: true });
  }
  for (const where of [`/ops/api/encounters/${id}`, '/ops/']) await record('anonymous', 'GET', where, await get(anonymous, where));
  for (const where of [...OPS_GET_PATHS(id), ...REMOVED_PATHS(id)]) await record('operator', 'GET', where, await get(op.request, where));
  return probes;
}

// Every operator-only artifact a customer download must 404 for (checkAuthorization's artifact rows).
function checkArtifactsHidden(probes) {
  const rows = (probes || []).filter(p => p.artifact);
  if (!rows.length) return [skip('authorization.operator_artifacts_hidden', 'the encounter holds no operator-only report artifact')];
  const wrong = rows.filter(p => p.status !== 404);
  return [check('authorization.operator_artifacts_hidden', 'hard', wrong.length === 0, wrong.length
    ? `operator-only artifacts a customer could download: ${wrong.map(p => `${p.path} -> ${p.status}`).join(', ')}` : `${rows.length} operator-only artifact(s), each 404 to the customer`)];
}

// The served customer page and its same-origin scripts and stylesheets, scanned whole (once per run); and the contract's
// one script on the customer page, with no inline script.
async function scanBundle(page, base, ctx) {
  const index = await page.request.get(`${base}/`, { timeout: UI_TIMEOUT_MS });
  const html = await index.text();
  const assets = await page.evaluate(() => Array.from(document.querySelectorAll('script[src], link[rel="stylesheet"][href], link[rel="modulepreload"][href], link[rel="preload"][href]'))
    .map(el => el.src || el.href));
  const files = [{ path: '/', status: index.status(), text: html }];
  for (const address of [...new Set(assets)]) {
    let url;
    try {
      url = new URL(address, base);
    } catch {
      continue;
    }
    if (url.origin !== base) {
      files.push({ path: url.href, status: null, text: '', foreign: true });
      continue;
    }
    const response = await page.request.get(url.href, { timeout: UI_TIMEOUT_MS });
    files.push({ path: url.pathname, status: response.status(), text: await response.text() });
  }
  const hits = files.flatMap(file => scanText(file.text, ctx, 'bundle', file.path));
  const scripts = (html.match(/<script\b[^>]*\bsrc\s*=/gi) || []).length;
  const inline = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)].filter(m => !/\bsrc\s*=/.test(m[1]) && m[2].trim()).length;
  return { files: files.map(file => ({ path: file.path, status: file.status, bytes: Buffer.byteLength(file.text), sha256: file.text ? sha256(Buffer.from(file.text)) : null, foreign: Boolean(file.foreign) })),
    hits, scripts, inline };
}

function checkBundle(bundle) {
  const foreign = bundle.files.filter(file => file.foreign);
  const unread = bundle.files.filter(file => !file.foreign && file.status !== 200);
  return [
    ...checkScan('scan.bundle', bundle.hits, `the served page and ${bundle.files.length - 1} asset(s)`),
    check('bundle.one_script', 'hard', bundle.scripts === 1 && bundle.inline === 0 && foreign.length === 0,
      `${bundle.scripts} script(s) loaded by the customer page, ${bundle.inline} inline${foreign.length ? `; from another origin: ${foreign.map(file => file.path).join(', ')}` : ''}`),
    check('bundle.read', 'hard', unread.length === 0, unread.length ? `not read: ${unread.map(file => `${file.path} (${file.status})`).join(', ')}` : `${bundle.files.length} file(s) read`),
  ];
}

// The "Why this code?" control works: the first row's disclosure opens and shows its first quotation.
async function openWhy(page) {
  const why = page.locator('ol.result-list > li.result-row details.why-code');
  if (await why.count() === 0) return skip('dom.why_opens', 'no "Why this code?" on the page');
  await why.first().locator('summary').click({ timeout: UI_TIMEOUT_MS });
  const open = await why.first().evaluate(el => el.open === true);
  const quote = why.first().locator('.why-quote');
  const visible = (await quote.count()) === 0 || await quote.first().isVisible();
  return check('dom.why_opens', 'hard', open && visible, `the first "Why this code?" ${open ? 'opened' : 'did not open'}${open && !visible ? ', its quotation not shown' : ''}`);
}

function saveSnapshot(record, docDir, outDir, name, enc, kind = 'customer') {
  const file = path.join(docDir, `${kind === 'operator' ? 'ops' : 'api'}-${name.replace(/_/g, '-')}.json`);
  fs.writeFileSync(file, `${JSON.stringify(enc, null, 2)}\n`);
  record[kind === 'operator' ? 'operator_snapshots' : 'customer_snapshots'][name] = path.relative(outDir, file);
}

async function checkOriginal(page, ctx, id, delivery, cust) {
  const where = `/api/encounters/${id}/original`;
  const response = await page.request.get(`${ctx.base}${where}`, { timeout: UI_TIMEOUT_MS });
  ctx.bodies.push({ via: 'walk', method: 'GET', path: where, status: response.status(), headers: response.headers(), body: null });
  const offered = cust?.document?.original_url ?? null;
  if (delivery.format === 'paste') {
    return check('original.preserved', 'hard', response.status() === 404 && offered === null, `pasted text: GET original answered ${response.status()} (404 expected); original_url ${JSON.stringify(offered)}`);
  }
  const digest = response.ok() ? sha256(await response.body()) : null;
  return check('original.preserved', 'hard', digest === delivery.sha256 && offered === where,
    `GET original answered ${response.status()}; sha256 ${digest} vs uploaded ${delivery.sha256}; original_url ${JSON.stringify(offered)}`);
}

// The customer surface of one document, scanned once its operator view is known: every body and header, the page's
// strings and toasts, and every downloaded file.
function scanDocument(ctx, sc, record, outDir) {
  const json = [];
  const headers = [];
  for (const entry of ctx.bodies) {
    scanHeaders(entry.headers, sc, `${entry.method} ${entry.path}`, headers);
    if (entry.body === null || entry.body === undefined || entry.body === '') continue;
    let parsed;
    try {
      parsed = JSON.parse(entry.body);
    } catch {
      parsed = undefined;
    }
    if (parsed === undefined) scanText(entry.body, sc, 'json', `${entry.method} ${entry.path} (${entry.status}, not JSON)`, json);
    else scanJson(parsed, sc, `${entry.method} ${entry.path}`, json);
  }
  const dom = [];
  for (const [value, where] of ctx.domStrings) scanText(value, sc, 'dom', where, dom);
  for (const toast of ctx.toasts) scanText(toast, sc, 'dom', 'toast', dom);
  const files = [];
  for (const d of record.downloads.filter(item => item.path)) {
    const file = path.join(outDir, d.path);
    if (fs.existsSync(file)) scanFile(fs.readFileSync(file, 'utf8'), sc, `${d.kind}.${d.fmt}`, d.fmt, files);
  }
  record.scans = { responses: ctx.bodies.length, dom_strings: ctx.domStrings.size, toasts: [...ctx.toasts].length, files: record.downloads.filter(item => item.path).length,
    hits: { json: json.length, header: headers.length, dom: dom.length, file: files.length } };
  const bodies = ctx.bodies.filter(entry => entry.body).length;
  const nothing = (id, what) => check(id, 'hard', false, `nothing to scan: no ${what} was read, so the scan proves nothing`);
  return [
    ...(bodies ? checkScan('scan.json', json, `${bodies} customer API body(ies)`) : [nothing('scan.json', 'customer API body')]),
    ...(ctx.bodies.length ? checkScan('scan.header', headers, `${ctx.bodies.length} customer response(s)' headers`) : [nothing('scan.header', 'customer response')]),
    ...(ctx.domStrings.size ? checkScan('scan.dom', dom, `${ctx.domStrings.size} page string(s) and ${ctx.toasts.size} toast(s)`) : [nothing('scan.dom', 'page string')]),
    ...checkScan('scan.file', files, `${record.downloads.filter(item => item.path).length} downloaded file(s)`),
  ];
}

// --- a document that must fail (manifest expected_failure) -------------------------------------------------------------

// Thrown by verifyDocument once a document that had to fail is walked: its main steps end there, with no error recorded.
const FAILURE_WALKED = Object.freeze({ walked: 'expected_failure' });

// A failed document against its manifest: the operator state it names, the customer's failed phase and nothing busy, no
// code, no provider request (it failed before anything was sent), the served error with the button its action offers in
// the notice (a resume may be the panel's own Resume), and the panel itself (checkProgressDom: its steps, stillness, the
// error in the notice, the leave note).
function checkFailure(cust, op, dom, expected, animating = []) {
  const progress = cust?.progress || {};
  const error = isObject(progress.error) ? progress.error : null;
  // a document that fails on reading has no provider run of any state (the operator view's runs carry no `sent` key:
  // serializers._provider_run_json; refutation, 2026-11-05: a filter on it passed five sent runs)
  const sent = (Array.isArray(op?.provider_runs) ? op.provider_runs : []).filter(isObject);
  const button = error ? ERROR_ACTION_BUTTONS[error.action] || null : null;
  const notice = dom?.progress?.notice_action ?? null;
  const offered = button === 'resume' ? Boolean(dom?.progress?.resume) : notice === button;
  const codes = Array.isArray(cust?.codes) ? cust.codes.length : 0;
  return [
    check('failure.state', 'hard', op?.state === expected, `operator state ${op?.state ?? 'not served'} (expected ${expected})`),
    check('failure.customer', 'hard', cust?.state === 'failed' && progress.phase === 'failed' && !isBusy(cust), `customer state ${cust?.state}, phase ${progress.phase}, busy ${isBusy(cust)}`),
    check('failure.no_codes', 'hard', codes === 0, `${codes} code(s) served`),
    check('failure.nothing_sent', 'hard', sent.length === 0, sent.length ? `${sent.length} provider run(s) recorded: ${sent.map(describeRun).join(', ')}` : 'no provider run was recorded, so nothing was sent'),
    check('failure.error', 'hard', Boolean(error && typeof error.text === 'string' && error.text), error ? `served the error ${JSON.stringify(error.text)} (action ${error.action})` : 'no error served for a failed document'),
    check('failure.action', 'hard', offered, `the notice offers ${notice ? `"${notice}"` : 'no action'}; the error's action ${error?.action ?? 'none'} offers ${button ? `"${button}"` : 'none'}`),
    ...checkProgressDom(cust, dom, animating),
  ];
}

// The failed document's walk, once processing ended: its panel as the page drew it (from the page's own last read), the
// customer contract and vocabulary, the original still served, both viewports measured and photographed, the final views
// (nothing sent since), and the direct-URL probes. Its scans run after, as for every document.
async function verifyFailure(page, ctx, { op, anonymous, id, doc, item, processed, opView, record, add, docDir, opts }) {
  // the page's own poll backs off to 15 s, so its first failed read can come later than the walk's
  await page.waitForFunction(() => document.querySelector('section.progress-panel')?.getAttribute('data-phase') === 'failed', null, { timeout: UI_TIMEOUT_MS }).catch(() => {});
  const served = ctx.lastServed.get(id)?.json || processed;
  const dom = await readPage(page, ctx);
  const animating = await page.evaluate(readAnimations);
  record.failure = { expected: doc.expected_failure, operator_state: opView?.state ?? null, phase: served?.progress?.phase ?? null,
    action: isObject(served?.progress?.error) ? served.progress.error.action ?? null : null,
    provider_runs: (opView?.provider_runs || []).filter(isObject).length };
  add(checkFailure(served, opView, dom, doc.expected_failure, animating));
  add(checkCustomerContract(served));
  add(checkCustomerVocabulary(served));
  add([await checkOriginal(page, ctx, id, item.delivery, served)]);
  await shot(page, docDir, opts.out, record, 'failed', 'desktop');
  record.viewports.desktop = await page.evaluate(measureViewport);
  add(checkViewport('desktop', record.viewports.desktop));
  await page.setViewportSize(VIEWPORTS.mobile);
  await page.waitForTimeout(300);
  record.viewports.mobile = await page.evaluate(measureViewport);
  add(checkViewport('mobile', record.viewports.mobile));
  await shot(page, docDir, opts.out, record, 'failed', 'mobile');
  await page.setViewportSize(VIEWPORTS.desktop);
  const final = await fetchCustomer(page, ctx, id);
  saveSnapshot(record, docDir, opts.out, 'final', final);
  const finalOp = await fetchOperator(op, ctx, id);
  saveSnapshot(record, docDir, opts.out, 'final', finalOp, 'operator');
  add(checkNoDuplicateSends(finalOp, 'final.no_duplicate_send'));
  record.authorization = await probeAuthorization(page, ctx, op, anonymous, id, [], []);
  add(checkAuthorization(record.authorization));
  add(checkArtifactsHidden(record.authorization));
  if (ctx.listContract.length) add(ctx.listContract);  // the document list, as every document's walk checks it
  record.summary = { operator: summarize(finalOp), customer: customerSummary(final) };
}

async function verifyDocument(page, opts, manifest, item, sink, sessions = {}) {
  const { doc } = item;
  const { op, anonymous, watch } = sessions;
  const docDir = path.join(opts.out, doc.id);
  fs.mkdirSync(docDir, { recursive: true });
  const started = Date.now();
  const record = {
    id: doc.id, title: doc.title, delivery: item.delivery, encounter_id: null, review_url: null,
    timings: { started_at: isoNow() }, state_history: [], upload_ack: null, progress_samples: [], reload: null, stop: null, details: null,
    decisions: [], designated_rejection: null, downloads: [], approved_withheld: null, screenshots: [], customer_snapshots: {}, operator_snapshots: {},
    authorization: [], viewports: {}, scans: null, summary: null, assertions: [], console_errors: sink.splice(0), error: null, result: null,
  };
  const add = items => record.assertions.push(...items);
  // --acceptance-reviewer: approvals only, and a details save only as the clarification the document needs (opts.account
  // is the signed-in reviewer each decision must be recorded as)
  const acceptance = Boolean(opts.acceptanceReviewer);
  const ctx = { base: opts.baseUrl, bodies: [], domStrings: new Map(), toasts: new Set(), lastServed: new Map(), listChecked: false, listContract: [] };
  if (watch) watch.current = ctx;
  const plan = doc.review_plan || {};
  let opView = null;
  let trace = null;
  try {
    if (!op) throw new Error('no operator session: the operator view is what this walk checks the customer surface against');
    await page.goto(`${opts.baseUrl}/`, { waitUntil: 'domcontentloaded' });
    await customerListIds(page, ctx);
    let id;
    if (opts.encounter) {  // attached: nothing is uploaded
      id = opts.encounter;
      record.attached = true;
      record.timings.encounter_created_at = record.timings.attached_at = isoNow();
      await page.goto(`${opts.baseUrl}/#doc/${id}`, { waitUntil: 'domcontentloaded' });
    } else {
      const upload = await uploadDocument(page, ctx, item, record.timings);
      id = upload.id;
      record.upload_ack = { ack: upload.watch?.ack ?? null, first_get: (upload.watch?.gets || []).find(get => get.path === `/api/encounters/${id}`) ?? null };
      add(checkUploadAck(upload.watch, id));
      add([check('upload.client_key', 'soft', upload.client_key, upload.client_key ? 'the upload carried a client key (a repeated upload returns the same encounter)'
        : 'the upload carried no client_key, so a retried upload could create a second encounter')]);
      if (record.upload_ack.ack) await shot(page, docDir, opts.out, record, 'upload-ack', 'desktop');
    }
    record.encounter_id = id;
    await page.waitForURL(url => new URL(url).hash === `#doc/${id}`, { timeout: UI_TIMEOUT_MS });
    record.review_url = page.url();
    const deadlineAt = started + opts.deadlineSeconds * 1000;
    const samples = [];
    let reloadDone = Boolean(opts.noReloadWhileProcessing);
    let stopDone = plan.stop_and_resume !== true;
    const sampler = async cust => {
      if (!samples.length) await shot(page, docDir, opts.out, record, 'progress', 'desktop');
      if (samples.length < MAX_PROGRESS_SAMPLES) {
        const sample = await sampleProgress(page, ctx, id);
        samples.push(sample);
        record.progress_samples.push({ at: sample.at, phase: sample.phase, dom_phase: sample.dom_phase, failed: sample.results.filter(r => r.status === 'fail').map(r => r.id) });
      }
      if (!reloadDone) {
        reloadDone = true;
        const reload = await reloadWhileProcessing(page, ctx, op, id, cust);
        record.reload = { at: reload.at, before: reload.before, after: reload.after };
        add(reload.checks);
      }
      if (!stopDone && cust.progress?.can_stop === true) {
        stopDone = true;
        if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; the document was not stopped');
        const stopped = await stopAndResume(page, ctx, op, id, deadlineAt, record.state_history, opts.out, docDir, record);
        record.stop = { asked_at: stopped.asked_at, stop_status: stopped.stop_status, error: stopped.error, resume_status: stopped.resume_status,
          resume_error: stopped.resume_error, stopped_phase: stopped.stopped?.cust?.progress?.phase ?? null, resumed_state: stopped.resumed?.cust?.state ?? null };
        add(checkStopResume(id, stopped));
      }
    };
    const { enc: processed, timedOut } = await waitForProcessing(page, ctx, id, deadlineAt, record.state_history, sampler);
    record.timings.processing_done_at = isoNow();
    record.timings.processing_seconds = (Date.parse(record.timings.processing_done_at) - Date.parse(record.timings.encounter_created_at)) / 1000;
    saveSnapshot(record, docDir, opts.out, 'after_processing', processed);
    if (timedOut) throw new Error(`processing did not finish within ${opts.deadlineSeconds}s (state ${processed.state}); no Stop was issued and nothing is retried`);
    add(samples.length ? mergeSamples(samples) : [skip('progress.sampled', 'processing had finished before the page was first sampled')]);
    if (!record.reload && !opts.noReloadWhileProcessing) add([skip('reload.same_encounter', 'processing had finished before the page could be reloaded while busy')]);
    if (plan.stop_and_resume === true && !record.stop) add([check('stop.request', 'hard', false, 'the document was never seen processing with Stop offered, so it was not stopped')]);
    opView = await fetchOperator(op, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'after_processing', opView, 'operator');
    trace = await fetchOperatorTrace(op, ctx, id);
    if (trace) saveSnapshot(record, docDir, opts.out, 'trace', trace, 'operator');
    // an attached encounter is proved to be the manifest's document first, a failed one included (an uploaded file by
    // its stored original; a failed paste has no text to prove it by, so it is refused: refutation, 2026-11-05)
    const foreign = record.attached ? attachedProblems(opView, item) : [];
    if (foreign.length) throw new Error(`refusing to act on encounter ${id}: ${foreign.join('; ')}`);
    if (doc.expected_failure !== undefined) {
      // manifest expected_failure: the failed state is walked, and nothing about codes - there are none to walk
      await verifyFailure(page, ctx, { op, anonymous, id, doc, item, processed, opView, record, add, docDir, opts });
      throw FAILURE_WALKED;
    }
    const editPlan = contextEditPlan(doc);
    // the edit is made only on a precondition seen to hold; until then nothing is requested, so coding is judged after it
    const unmet = editPlan ? contextEditPreconditions(opView, doc.upload?.service_date || null, editPlan).filter(a => a.status === 'fail') : [];
    const editing = Boolean(editPlan) && unmet.length === 0;
    add(checkPipeline(opView));
    add(checkExtraction(doc.expected_extraction || {}, opView, item.delivery, item.sourceText));
    if (!record.attached) add(checkUploadDate(doc.upload?.service_date, opView));
    add(checkContext(doc.expected_context, opView));
    add(checkRouting(doc.expected_routing || {}, opView));
    add(checkEvidenceExact(opView));
    if (editing) add([skip('must_not_code', 'judged after the context edit'), skip('incomplete', 'judged after the context edit')]);
    else add(checkMustNotCode(doc.must_not_code, opView));
    add(checkClarifications(doc.expected_clarifications, opView));
    if (!editing) add(checkIncomplete(doc.incomplete_services, opView));
    if (editing) { if (doc.expected_codes) add([skip('codes', 'judged after the context edit')]); } else add(checkExpectedCodes(doc.expected_codes, opView));
    add(checkProvenance(opView, trace, { expectHarness: opts.expectHarness }));
    add(checkNoDuplicateSends(opView));
    add([check('customer.processed', 'hard', CUSTOMER_DONE_STATES.has(processed.state) && !isBusy(processed), `state ${processed.state}, phase ${processed.progress?.phase}`)]);
    add(checkCustomerContract(processed));
    add(checkCustomerVocabulary(processed));
    add(checkCustomerVsOperator(processed, opView));
    add(checkProgressFold(processed, opView));
    if (doc.expected_no_em_questions === true) add(checkNoEmQuestions(processed, opView));
    add([await checkOriginal(page, ctx, id, item.delivery, processed)]);
    await waitForResults(page).catch(async () => {
      add([check('ui.refreshed_itself', 'soft', false, 'the page did not leave the processing view on its own within 30 s; reloaded')]);
      await reloadPage(page, ctx);
      await waitForResults(page);
    });
    let cust = await fetchCustomer(page, ctx, id);
    let dom = await readPage(page, ctx);
    add(checkResultList(cust, dom));
    add(checkChecksPanel(cust, dom));
    add(checkDetailsPanel(cust, dom));
    add(checkProgressDom(cust, dom, await page.evaluate(readAnimations)).map(a => ({ ...a, id: a.id.replace(/^progress\.dom\./, 'progress.idle.') })));
    add([await openWhy(page)]);
    await readPage(page, ctx);
    await shot(page, docDir, opts.out, record, 'why-open', 'desktop');
    record.viewports.desktop = await page.evaluate(measureViewport);
    add(checkViewport('desktop', record.viewports.desktop));
    await shot(page, docDir, opts.out, record, 'results', 'desktop');
    if (dom.details) await shot(page, docDir, opts.out, record, 'details', 'desktop');

    // the details panel: the date answer of a context_edit (its old proofs) and review_plan.details, in one save
    const answers = detailsPlan(doc);
    if (editPlan && !editing) {  // nothing is saved, so nothing is sent, on a precondition the walk did not see hold
      const edit = { http_status: null, error: `not made: ${unmet.map(a => a.id).join(' and ')} failed, so the edit has nothing verified to ${editPlan.answers_question ? 'answer' : 'settle'}` };
      record.context_edit = { plan: plan.context_edit, ...(editPlan.answers_question ? { answers_question: true } : {}), http_status: null, error: edit.error };
      add(checkContextEdit(opView, null, null, editPlan, edit, doc.upload?.service_date || null));
    } else if (answers.length) {
      if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; the details were not saved');
      const before = { cust, op: opView };
      if (editing && answers.length === 1) {
        const edit = await editContext(page, ctx, op, id, editPlan, cust, deadlineAt, record.state_history, { repeat: !acceptance });
        const wanted = edit.after ? (editPlan.clear_member_date ? documentedServiceDate(opView, editPlan).date : editPlan.service_date) : null;
        record.context_edit = {
          plan: plan.context_edit, ...(editPlan.answers_question ? { answers_question: true } : {}),
          asked_at: edit.asked_at, form: edit.form, posted: edit.posted, http_status: edit.http_status, error: edit.error, timed_out: edit.timed_out,
          identical: edit.identical, request_date: edit.after ? wanted : null,
          expected_request_sha256: edit.after ? primaryRequestSha256(edit.after.revision?.text || '', wanted) : null,
          ...(acceptance ? { clarification_answer: true, coding_decision: false } : {}),
        };
        if (edit.after) saveSnapshot(record, docDir, opts.out, 'after_context_edit', edit.after, 'operator');
        if (edit.identical_view) saveSnapshot(record, docDir, opts.out, 'after_identical_context_save', edit.identical_view, 'operator');
        add(checkContextEdit(opView, edit.timed_out ? null : edit.after, edit.settled, editPlan, edit, doc.upload?.service_date || null));
        if (edit.timed_out || edit.identical.timed_out) throw new Error(`processing after the details ${edit.timed_out ? 'save' : 'save made again'} did not finish within ${opts.deadlineSeconds}s; no Stop was issued, nothing is retried and no decision was recorded`);
        if (edit.after) {
          await waitForResults(page).catch(async () => { await reloadPage(page, ctx); await waitForResults(page); });
          const reloaded = { cust: await fetchCustomer(page, ctx, id), op: edit.settled || edit.after, dom: await readPage(page, ctx) };
          add(checkDetailsSave(answers, before, { cust: edit.after_customer, op: edit.after }, { requests: edit.form?.requests, posted: edit.posted, http_status: edit.http_status, error: edit.error, rows: edit.form?.rows }, reloaded, opts.account || sessions.account));
          opView = reloaded.op;
          add([...checkPipeline(opView), ...checkEvidenceExact(opView), ...checkMustNotCode(doc.must_not_code, opView), ...checkIncomplete(doc.incomplete_services, opView)]
            .map(a => ({ ...a, id: `after_context_edit.${a.id}` })));
        }
      } else {
        const save = await saveDetails(page, ctx, id, cust, answers);
        record.details = { answers, rows: save.rows, acts: save.acts, requests: save.requests, posted: save.posted, http_status: save.http_status, error: save.error };
        let after = null;
        let reloaded = null;
        if (saved(save.http_status)) {
          const settled = await waitForProcessing(page, ctx, id, deadlineAt, record.state_history);
          if (settled.timedOut) throw new Error(`processing after the details save did not finish within ${opts.deadlineSeconds}s`);
          after = { cust: settled.enc, op: await fetchOperator(op, ctx, id) };
          saveSnapshot(record, docDir, opts.out, 'after_details', after.op, 'operator');
          await reloadPage(page, ctx);
          await waitForResults(page).catch(() => {});
          reloaded = { cust: await fetchCustomer(page, ctx, id), op: await fetchOperator(op, ctx, id), dom: await readPage(page, ctx) };
          opView = reloaded.op;
        }
        add(checkDetailsSave(answers, before, after, save, reloaded, opts.account || sessions.account));
        add(checkMemberAnswers(answers, reloaded || after));
      }
      cust = await fetchCustomer(page, ctx, id);
      dom = await readPage(page, ctx);
      add([...checkCustomerVsOperator(cust, opView), ...checkResultList(cust, dom), ...checkDetailsPanel(cust, dom)].map(a => ({ ...a, id: `after_details.${a.id}` })));
    }

    if (plan.addendum) {
      if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; the addendum was not added');
      const step = await addAddendum(page, ctx, op, id, plan.addendum, cust, deadlineAt, record.state_history);
      record.addendum = step.record;
      add(checkAddendum(plan.addendum, step));
      if (step.after) {
        opView = step.after.op;
        cust = step.after.cust;
        saveSnapshot(record, docDir, opts.out, 'after_addendum', opView, 'operator');
        await reloadPage(page, ctx);
        await waitForResults(page).catch(() => {});
        dom = await readPage(page, ctx);
        add([...checkPipeline(opView), ...checkEvidenceExact(opView), ...checkMustNotCode(doc.must_not_code, opView), ...checkIncomplete(doc.incomplete_services, opView),
          ...checkCustomerVsOperator(cust, opView), ...checkResultList(cust, dom)].map(a => ({ ...a, id: `after_addendum.${a.id}` })));
        if (doc.expected_codes?.not_ready) {
          const wanted = new Set(plan.addendum.expect_ready || []);
          add(checkExpectedCodes({ not_ready: doc.expected_codes.not_ready.filter(code => !wanted.has(code)) }, opView, 'after_addendum.codes'));
        }
      }
    }

    const secondPlan = secondReviewPlan(doc);
    if (secondPlan) add([skip('second_review.asked', 'not asked: the customer contract offers no second review (CORE-UX-DESIGN 7)')]);
    const canReview = cust?.permissions?.can_review === true;  // the walking member's own, never the operator's
    const decisionPlan = planDecisions(opView, doc.review_plan, manifest.review_notes, { mustNotCode: doc.must_not_code, noAutoApprove: opts.noAutoApprove, acceptanceReviewer: acceptance, canReview });
    if (decisionPlan.second_review_held.length) add([check('decisions.second_review_held', 'soft', false, `left undecided (${acceptance ? 'the acceptance reviewer decides no code a second review added' : 'not in review_plan.second_review.approve_codes'}): ${decisionPlan.second_review_held.join(', ')}`)]);
    if (decisionPlan.must_not_code_held.length) add([check('decisions.must_not_code_held', 'soft', false, `left undecided, never approved (the manifest's must_not_code lists their family): ${decisionPlan.must_not_code_held.join(', ')}`)]);
    if (decisionPlan.plan_conflicts.length) add([check('decisions.plan_conflict', 'hard', false, `approve_codes names a code of a family must_not_code lists; not approved: ${decisionPlan.plan_conflicts.join(', ')}`)]);
    if (decisionPlan.not_in_approve_codes.length) add([check('decisions.not_in_approve_codes', 'soft', false, `left undecided (not named in review_plan.approve_codes${acceptance ? '; --acceptance-reviewer' : opts.noAutoApprove ? '; --no-auto-approve' : ''}): ${decisionPlan.not_in_approve_codes.join(', ')}`)]);
    if (decisionPlan.approve_codes_unmatched.length) add([check('decisions.approve_codes_unmatched', 'soft', false, `named in review_plan.approve_codes but not a ready selected code: ${decisionPlan.approve_codes_unmatched.join(', ')}`)]);
    record.designated_rejection = decisionPlan.decisions.find(d => d.designated)?.code || null;
    if (decisionPlan.designated_missing) add([check('decisions.designated_rejection', 'soft', false, `no ready selected proposal in ${plan.reject.family} to reject`)]);
    const confirmable = planConfirmations(opView, doc.must_not_code, manifest.review_notes, canReview);
    const confirmations = acceptance ? [] : confirmable;
    const deciding = [...decisionPlan.decisions, ...confirmations];
    if (acceptance) {  // what an agent walk would also do is recorded as not done; nothing but an approval is ever sent
      if (plan.reject) add([skip('decisions.rejection', 'not made: the acceptance reviewer makes no rejection (review_plan.reject is not carried out)')]);
      if (confirmable.length) add([skip('decisions.confirmations', `not made: the acceptance reviewer confirms no exclusion; left undecided: ${confirmable.map(d => d.code).join(', ')}`)]);
      // the planner makes approvals only; this is the last check before an act that cannot be taken back
      const other = deciding.filter(d => d.action !== 'approve');
      if (other.length) throw new Error(`refusing to decide: the acceptance reviewer makes approvals only, and the plan holds ${other.map(d => `${d.action} ${d.code}`).join(', ')}`);
    }
    // 390x844 first: the page measured and photographed there, and the first decision made there
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.waitForTimeout(300);
    record.viewports.mobile = await page.evaluate(measureViewport);
    add(checkViewport('mobile', record.viewports.mobile));
    await readPage(page, ctx);
    await shot(page, docDir, opts.out, record, 'results', 'mobile');
    if (dom.details) await shot(page, docDir, opts.out, record, 'details', 'mobile');
    for (const [index, decision] of deciding.entries()) {
      if (stopRequested(opts.out)) throw new Error('stopped: a STOP file is present; no further decision was made');
      const mobile = index === 0;
      if (!mobile) await page.setViewportSize(VIEWPORTS.desktop);
      const onDialog = mobile ? async p => { await readPage(p, ctx); await shot(p, docDir, opts.out, record, 'review-dialog', 'mobile'); } : null;
      record.decisions.push({ ...(await decide(page, id, decision, { modifier: modifierFor(plan, decision), onDialog })), viewport: mobile ? 'mobile' : 'desktop' });
    }
    await page.setViewportSize(VIEWPORTS.desktop);
    record.timings.decisions_done_at = isoNow();
    add(record.decisions.map(d => check(`decision.${d.action}.${d.code}`, 'hard', d.http_status === 201 && !d.error, d.error || `HTTP ${d.http_status}${d.ui_updated === false ? '; the row did not update within 30 s' : ''}`)));
    if (deciding.length) add([check('decision.mobile', 'hard', record.decisions.some(d => d.viewport === 'mobile' && d.http_status === 201), `the first decision was made at 390x844${record.decisions[0]?.http_status === 201 ? '' : ` and failed: ${record.decisions[0]?.error}`}`)]);
    add(checkModifierDialogs(record.decisions, cust));
    const afterDecisions = await fetchOperator(op, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'after_decisions', afterDecisions, 'operator');
    saveSnapshot(record, docDir, opts.out, 'after_decisions', await fetchCustomer(page, ctx, id));
    await readPage(page, ctx);

    await reloadPage(page, ctx);
    await waitForResults(page);
    record.timings.reload_done_at = isoNow();
    const reloaded = await fetchOperator(op, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'after_reload', reloaded, 'operator');
    cust = await fetchCustomer(page, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'after_reload', cust);
    dom = await readPage(page, ctx);
    const account = opts.account || sessions.account || {};
    add(checkPersistence(record.decisions, opView, afterDecisions, reloaded, acceptance ? 'human' : 'agent'));
    add(checkDecisionRows(record.decisions, cust, dom, { acceptance }));
    add(checkCustomerDecisions(record.decisions, cust, account, acceptance ? 'human' : 'agent'));
    const labels = acceptance
      ? checkAcceptanceDecisions(record.decisions, reloaded, doc.must_not_code, account, [])
      : checkDecisionLabels(record.decisions, reloaded, doc.must_not_code);
    record.decision_labels = labels.labels;
    add(labels.checks);
    add(checkReadiness(reloaded));
    add([...checkCustomerContract(cust), ...checkCustomerVsOperator(cust, reloaded), ...checkResultList(cust, dom)].map(a => ({ ...a, id: `after_reload.${a.id}` })));

    const readiness = cust.readiness || {};
    const owed = expectedCustomerDownloads(readiness);
    for (const [index, want] of owed.entries()) {
      const [kind, fmt] = want.split('.');
      const viewport = index === 0 ? 'mobile' : 'desktop';
      await page.setViewportSize(VIEWPORTS[viewport]);
      if (index === 0 || index === 1) {
        await openExport(page);
        await readPage(page, ctx);
        await shot(page, docDir, opts.out, record, 'export-dialog', viewport);
      }
      record.downloads.push(await downloadReport(page, ctx, op, id, kind, fmt, docDir, opts.out, viewport));
      await closeExport(page);
    }
    await page.setViewportSize(VIEWPORTS.desktop);
    if (readiness.approved !== true && cust.codes?.length) {
      await openExport(page);
      const shown = await readPage(page, ctx);
      record.approved_withheld = { options: shown.export?.options || [], text: shown.export?.text || '', blockers: readiness.blockers || [] };
      await closeExport(page);
    }
    record.timings.downloads_done_at = isoNow();
    add(checkCustomerDownloads(record.downloads, readiness, record.approved_withheld));
    const final = await fetchCustomer(page, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'final', final);
    const finalOp = await fetchOperator(op, ctx, id);
    saveSnapshot(record, docDir, opts.out, 'final', finalOp, 'operator');
    add(checkCustomerListing(record.downloads, final));
    add(checkNoDuplicateSends(finalOp, 'final.no_duplicate_send'));
    opView = finalOp;

    // direct-URL authorization, with this encounter's report ids and its operator-only artifacts
    const listing = await fetchOperatorReports(op, ctx, id).catch(() => []);
    const operatorOnly = listing.filter(item => item && item.audience !== 'customer').map(item => item.id).filter(Boolean);
    record.authorization = await probeAuthorization(page, ctx, op, anonymous, id, record.downloads.map(d => d.report_id).filter(Boolean), operatorOnly);
    add(checkAuthorization(record.authorization));
    add(checkArtifactsHidden(record.authorization));
    if (ctx.listContract.length) add(ctx.listContract);
    record.summary = { operator: summarize(finalOp), customer: customerSummary(final) };
    await shot(page, docDir, opts.out, record, 'review', 'desktop');
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.waitForTimeout(300);
    await shot(page, docDir, opts.out, record, 'review', 'mobile');
    await page.setViewportSize(VIEWPORTS.desktop);
  } catch (error) {
    if (error !== FAILURE_WALKED) {  // a document that had to fail ends its walk here, with nothing gone wrong
      record.error = String(error && error.message || error).split('\n')[0];
      await page.setViewportSize(VIEWPORTS.desktop).catch(() => {});
      await shot(page, docDir, opts.out, record, 'error', 'desktop').catch(() => {});
    }
  }
  // the negative scans, once the operator view (and so every identifier it holds) is known
  try {
    await readPage(page, ctx).catch(() => null);
    const sc = scanContext({ documentText: opView?.revision?.text || '', denyValues: opView ? denyValuesFrom(opView, trace) : [], allowed: [new URL(opts.baseUrl).host] });
    add(scanDocument(ctx, sc, record, opts.out));
  } catch (error) {
    add([check('scan.json', 'hard', false, `the scans could not run: ${String(error && error.message || error)}`)]);
  }
  if (watch) watch.current = null;
  record.console_errors.push(...sink.splice(0));
  record.assertions.push(check('console.errors', 'soft', record.console_errors.length === 0, `${record.console_errors.length} console/page error(s)`));
  record.timings.finished_at = isoNow();
  record.timings.total_seconds = (Date.now() - started) / 1000;
  record.result = documentResult(record);
  return record;
}

// The customer view of a document as the evidence keeps it: structured fields only, never a sentence of the document.
function customerSummary(enc) {
  return {
    state: enc?.state, phase: enc?.progress?.phase ?? null,
    codes: (enc?.codes || []).map(code => ({ number: code.number, code: code.code, units: code.units, modifiers: code.modifiers, status: code.status,
      decision: code.decision ? { action: code.decision.action, by_kind: code.decision.by_kind } : null, quotes: (code.why?.quotes || []).length })),
    other_codes: (enc?.other_codes || []).map(item => item.code), details: (enc?.details_needed || []).map(row => ({ fact: row.fact, control: row.control, saved: Boolean(row.saved) })),
    readiness: enc?.readiness ?? null, reports: (enc?.reports || []).map(r => ({ kind: r.kind, fmt: r.fmt, current: r.current })),
  };
}

// forms (secretForms of every password the run read): the evidence is scrubbed of them, and where a form survives the
// scrub (it spans the JSON's own syntax) nothing that holds it is written (ops/verify_login.py write_evidence).
function writeEvidence(file, evidence, forms = null) {
  if (!forms) {
    fs.writeFileSync(file, `${JSON.stringify(evidence, null, 2)}\n`);
    return;
  }
  let text = `${JSON.stringify(scrubSecret(evidence, forms), null, 2)}\n`;
  if (forms.some(form => text.includes(form))) {
    text = `${JSON.stringify({ schema: evidence.schema, run_id: evidence.run_id,
      run_error: 'the evidence would have held the password; it was not written' }, null, 2)}\n`;
  }
  fs.writeFileSync(file, text);
}

// --operator-credentials: a private JSON file (no group or other access, checked on the descriptor read) with a
// top-level "username" and "password"; its content is never quoted.
function loadOperatorCredentials(file) {
  const { content, mode } = readPrivate(file, 'operator credentials file');
  let data;
  try {
    data = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(content));
  } catch {
    throw new UsageError(`the operator credentials file ${file} is not a JSON object`);
  }
  if (!isObject(data) || typeof data.username !== 'string' || !data.username || typeof data.password !== 'string' || !data.password) {
    throw new UsageError(`the operator credentials file ${file} must hold a non-empty top-level "username" and "password"`);
  }
  return { username: data.username, password: data.password, source: 'operator_credentials', mode };
}

async function main(argv) {
  let opts;
  let inputs;
  let creds;
  let operator;
  try {
    opts = parseArgs(argv);
    if (/pw:(api|\*)|(^|,)\*($|,)/.test(process.env.DEBUG || '')) throw new UsageError('refusing to run with DEBUG=pw:api: Playwright would log the password');
    // every run types the operator's password into the sign-in form
    if (debugMayLog(process.env.DEBUG)) {
      throw new UsageError(`refusing to run with DEBUG=${process.env.DEBUG}: a Playwright call, channel or protocol log would carry the password`);
    }
    inputs = loadInputs(opts);
    creds = opts.passwordFile !== undefined ? loadPasswordFile(opts.passwordFile, opts.username) : loadCredentials(opts.credentials);
    operator = loadOperatorCredentials(opts.operatorCredentials);
    if (operator.username === creds.username) throw new UsageError('the operator account must not be the customer account: the two sessions are different accounts');
    if (fs.existsSync(path.join(opts.out, 'evidence.json'))) throw new UsageError(`${opts.out} already holds evidence.json; use a fresh --out directory`);
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    process.stderr.write(`verify_browser: ${error.message}\n${USAGE}\n`);
    return 2;
  }
  fs.mkdirSync(opts.out, { recursive: true });
  const evidenceFile = path.join(opts.out, 'evidence.json');
  const forms = [...new Set([...secretForms(creds.password), ...secretForms(operator.password)])].sort((a, b) => b.length - a.length);
  const print = text => process.stdout.write(scrubSecret(text, forms));
  const { chromium, request: playwrightRequest } = require(PLAYWRIGHT);
  const evidence = {
    schema: EVIDENCE_SCHEMA, ...(opts.acceptanceReviewer ? { mode: 'acceptance_reviewer' } : {}),
    run_id: `verify-${isoNow().replace(/[-:.]/g, '')}-${crypto.randomBytes(4).toString('hex')}`,
    started_at: isoNow(), finished_at: null, base_url: opts.baseUrl, synthetic_only: true,
    manifest: { path: path.resolve(opts.manifest), sha256: inputs.manifestSha }, docs_dir: path.resolve(opts.docs),
    options: { only: opts.only, deadline_seconds: opts.deadlineSeconds, stop_on_failure: opts.stopOnFailure, allow_live_provider: opts.allowLiveProvider,
               encounter: opts.encounter || null, no_auto_approve: opts.noAutoApprove, expect_harness: opts.expectHarness,
               reload_while_processing: !opts.noReloadWhileProcessing, ...(opts.acceptanceReviewer ? { acceptance_reviewer: true } : {}) },
    environment: { node: process.version, playwright: require(path.join(PLAYWRIGHT, 'package.json')).version, browser: null },
    credentials: credentialsRecord(creds), operator_credentials: { username: operator.username, file_mode: operator.mode.toString(8).padStart(4, '0') },
    session: null, operator: null, bundle: null, run_checks: [], documents: [], summary: null, run_error: null,
  };
  const browser = await chromium.launch({ headless: true });
  evidence.environment.browser = browser.version();
  const context = await browser.newContext({ acceptDownloads: true, viewport: VIEWPORTS.desktop });
  await context.addInitScript(pageWatch);
  const page = await context.newPage();
  page.setDefaultTimeout(UI_TIMEOUT_MS);
  const sink = [];
  const watch = { current: null };
  page.on('console', msg => { if (msg.type() === 'error') sink.push({ at: isoNow(), kind: 'console', text: msg.text().slice(0, 500) }); });
  page.on('pageerror', error => sink.push({ at: isoNow(), kind: 'pageerror', text: String(error.message).slice(0, 500) }));
  page.on('requestfailed', request => {
    const failure = request.failure()?.errorText || '';
    if (!/ERR_ABORTED/.test(failure)) sink.push({ at: isoNow(), kind: 'requestfailed', text: `${request.method()} ${pathnameOf(request.url())}: ${failure}` });
  });
  page.on('response', response => {
    if (response.status() >= 400 && pathnameOf(response.url()).startsWith('/api/')) sink.push({ at: isoNow(), kind: 'http', text: `${response.request().method()} ${pathnameOf(response.url())} -> ${response.status()}` });
    captureResponse(response, watch, opts.baseUrl).catch(() => {});
  });
  const operatorContext = await browser.newContext({ viewport: VIEWPORTS.desktop });
  const anonymous = await playwrightRequest.newContext();
  try {
    evidence.session = await login(page, opts.baseUrl, creds);
    const problems = sessionProblems(evidence.session, opts);
    if (problems.length) throw new Error(`refusing to upload: ${problems.join('; ')}`);
    const runScan = scanContext({ allowed: [new URL(opts.baseUrl).host] });
    evidence.run_checks.push(...checkCustomerContract(evidence.session, 'session', 'session.contract'),
      ...checkScan('scan.session', scanJson(evidence.session, runScan, 'GET /api/session'), 'the customer session'));
    const op = await operatorSignIn(operatorContext, opts.baseUrl, operator);
    evidence.operator = { landed: op.landed, control: op.control };
    if (op.control !== 200) throw new Error(`refusing to upload: the operator session cannot read /ops/api/encounters (HTTP ${op.control}), so nothing the walk reads there could be believed`);
    await page.goto(`${opts.baseUrl}/`, { waitUntil: 'domcontentloaded' });
    const bundle = await scanBundle(page, opts.baseUrl, runScan);
    evidence.bundle = { files: bundle.files, scripts: bundle.scripts, inline: bundle.inline, hits: bundle.hits.slice(0, 40) };
    evidence.run_checks.push(...checkBundle(bundle));
    const walk = { ...opts, account: reviewerAccount(evidence.session) };
    for (const item of inputs.documents) {
      if (stopRequested(opts.out)) {
        evidence.run_error = 'stopped: a STOP file is present in the evidence directory; no further upload was made';
        print(`${evidence.run_error}\n`);
        break;
      }
      print(`${item.doc.id} ${item.delivery.format} ... `);
      const record = await verifyDocument(page, walk, inputs.manifest, item, sink, { op, anonymous, watch, account: walk.account });
      evidence.documents.push(record);
      writeEvidence(evidenceFile, evidence, forms);
      const failed = record.assertions.filter(a => a.status === 'fail').map(a => a.id);
      print(`${record.result}${record.error ? ` (${record.error})` : ''}${failed.length ? ` [${failed.join(', ')}]` : ''}\n`);
      if (record.result === 'fail' && opts.stopOnFailure) break;
    }
  } catch (error) {
    evidence.run_error = String(error && error.message || error).split('\n')[0];
    print(`run stopped: ${evidence.run_error}\n`);
  } finally {
    await anonymous.dispose().catch(() => {});
    await browser.close();
    evidence.finished_at = isoNow();
    const passed = evidence.documents.filter(d => d.result === 'pass').length;
    evidence.summary = { selected: inputs.documents.length, verified: evidence.documents.length, passed, failed: evidence.documents.length - passed,
      run_checks_failed: evidence.run_checks.filter(a => a.status === 'fail').map(a => a.id) };
    writeEvidence(evidenceFile, evidence, forms);
  }
  print(`evidence: ${evidenceFile}\n${JSON.stringify(evidence.summary)}\n`);
  const complete = !evidence.run_error && evidence.summary.verified === evidence.summary.selected;
  return complete && evidence.summary.failed === 0 && evidence.summary.run_checks_failed.length === 0 ? 0 : 1;
}

function stopRequested(outDir) {
  return fs.existsSync(path.join(outDir, 'STOP'));
}

module.exports = {
  stopRequested, parseArgs, UsageError, cpSlice, safeName, sessionProblems, checkPipeline, checkExtraction, checkContext, checkRouting,
  checkEvidenceExact, checkMustNotCode, checkClarifications, checkIncomplete, planDecisions, planConfirmations, checkReadiness,
  checkPersistence, checkEvidenceMarks, summarize, documentResult, secondReviewPlan, checkSecondReview, attachedProblems, sentRun,
  contextEditPlan, isMemberDateHold, contextRequestDate, primaryRequestSha256, checkUploadDate, checkContextEdit, contextEditPreconditions,
  checkDecisionLabels, planProblems, MEMBER_DATE_HOLD_MESSAGE, PROVIDER_SYSTEMS,
  documentedServiceDate, quotedDates, USER_CONFLICT_NOTE, USER_ELSEWHERE_NOTE,
  checkQuestionEdit, questionEditPreconditions, openDateQuestions, identicalSaveChecks, verifyDocument,
  ACCEPTANCE_LABEL, REVIEW_NOTE_MAX, checkAcceptanceDecisions, loadPasswordFile, loadOperatorCredentials, credentialsRecord, debugMayLog,
  secretForms, scrubSecret, writeEvidence, reviewerAccount, main,
  // the customer surface (CORE-UX-DESIGN 5-8)
  answeredAway, CONTRACT, DENYLIST, shapeProblems, checkCustomerContract, checkCustomerVocabulary, harvest, denyValuesFrom, scanContext, scanText,
  scanJson, scanFile, scanHeaders, csvRows, checkScan, expectedCodeRows, expectedCustomerStatus, allowedPassages, actIndex, checkCustomerVsOperator,
  serverCustomer, decidedModifiers, serverActions, NONE_APPROVED_BLOCKER,
  checkDetailRows, checkNoEmQuestions, readCustomerDom, checkResultList, checkChecksPanel, checkDetailsPanel, checkProgressDom, foldedSteps,
  checkProgressFold, checkUploadAck, duplicateSends, checkNoDuplicateSends, jobsKept, checkReloadIdentity, checkStopResume, checkProvenance,
  checkAuthorization, checkArtifactsHidden, checkViewport, checkDecisionRows, checkCustomerDecisions, checkModifierDialogs,
  expectedCustomerDownloads, checkCustomerDownloads, checkCustomerListing, detailsPlan, detailRowFor, checkDetailsSave, checkMemberAnswers, checkExpectedCodes, modifierFor,
  mergeSamples, sampleProgress, scanDocument, checkBundle, customerSummary, isBusy, saved, OPS_GET_PATHS, OPS_POST_PATHS, REMOVED_PATHS,
  // the 2026-11-05 acceptance walk's corrections: the compact line, a model-less participant, the upload key, a failed document
  checkCompactProgress, PANEL_PHASES, MODELLESS_PARTICIPANTS, uploadCarriedClientKey, checkFailure, FAILED_STATES, FAILURE_WALKED,
  // the completion repair's physician addendum step (review_plan.addendum)
  checkAddendum,
};

if (require.main === module) {
  main(process.argv.slice(2)).then(code => { process.exitCode = code; }, error => {
    process.stderr.write(`verify_browser: ${error && error.stack || error}\n`);
    process.exitCode = 1;
  });
}
