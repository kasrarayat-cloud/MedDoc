'use strict';
// CPT Studio customer page, drawn from the customer encounter contract (client contract customer-2026-11-20: the build
// specification, sections 6 and 7). Rendering builds markup strings; every value that comes from the server passes
// through escapeHtml. Text the coding review wrote (reasons, questions, documentation notes, quoted passages) is shown
// as written and escaped like every other value. Everything above "browser wiring" is pure and unit-tested under node
// (tests/frontend/app.test.cjs).

const POLL_BASE_MS = 2500;
const POLL_MAX_MS = 15000;
const POLL_MAX_ERROR_MS = 30000;
const TICK_MS = 1000;
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;
const MAX_PASTE_CHARS = 400000;
const MAX_ANSWER_CHARS = 2000;
const UPLOAD_NAME = /\.(pdf|docx|txt)$/i;
const UUID_PART = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const UUID = new RegExp(`^${UUID_PART}$`, 'i');
const REPORT_URL = new RegExp(`^/api/reports/${UUID_PART}/download$`, 'i');
const ORIGINAL_URL = new RegExp(`^/api/encounters/${UUID_PART}/original$`, 'i');
// The in-page view of the original: the same path with view=1 among plain query parameters, nothing else.
const VIEW_URL = new RegExp(`^/api/encounters/${UUID_PART}/original\\?(?:[\\w.-]+=[\\w.-]*&)*view=1(?:&[\\w.-]+=[\\w.-]*)*$`, 'i');
// The page tells the server which build of this page is asking. A server that no longer serves this build refuses the
// call with a conflict status and {"error_code": "client_outdated"}, and the page asks the member to reload.
const CLIENT_HEADER = 'X-CPT-Studio-Client';
const CLIENT_VERSION = 'customer-2026-11-20';
const OUTDATED_TEXT = 'CPT Studio was updated — reload the page to continue.';
const OFFLINE_TEXT = 'The server could not be reached. Check the connection and try again.';
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#x60;' };

// The encounter states and their fixed labels (the build specification, section 5), and 'earlier': a document an
// earlier version of CPT Studio reviewed, with no coding review of this version and so no codes.
const STATE_LABELS = {
  processing: 'Processing', stopped: 'Stopped', failed: 'Could not finish', awaiting_answer: 'Questions for you',
  needs_review: 'Needs your review', ready: 'Ready for approval', reviewed: 'Reviewed', no_codes: 'No codes found',
  earlier: 'Earlier review',
};
const STATE_TONES = { ready: 'green', reviewed: 'green', awaiting_answer: 'amber', needs_review: 'amber', failed: 'amber' };
// The states that wait on a member: questions to answer, codes to review or to approve.
const QUEUE_STATES = new Set(['awaiting_answer', 'needs_review', 'ready']);
// code status -> [label, badge tone, badge icon]
const CODE_STATUSES = {
  ready: ['Ready for approval', 'green', ''],
  needs_answer: ['Needs your answer', 'amber', 'help'],
  needs_review: ['Needs your review', 'amber-outline', 'info'],
  not_supported: ['Not supported', 'gray', ''],
};
// a current decision -> [shown status, label, badge tone, badge icon]
const DECISIONS = { approve: ['approved', 'Approved', 'green', 'check'], reject: ['rejected', 'Rejected', 'gray', 'close'] };
// [action, button kind, label, icon]: the only decision buttons the page draws, each only when the server allows it.
const ACTION_BUTTONS = [['approve', 'primary', 'Approve', 'check'], ['reject', 'secondary', 'Reject', ''], ['revoke', 'secondary', 'Undo', '']];
const REVIEW_COPY = {
  approve: { eyebrow: 'APPROVE', title: 'Make the decision visible.', button: 'Approve code' },
  reject: { eyebrow: 'REJECT', title: 'Leave a clear record.', button: 'Reject code' },
};
const TALLY = [
  ['approved', 'approved', 'approved'], ['rejected', 'rejected', 'rejected'], ['ready', 'ready for approval', 'ready for approval'],
  ['needs_review', 'needs your review', 'need your review'], ['needs_answer', 'needs your answer', 'need your answer'],
  ['not_supported', 'not supported', 'not supported'],
];
const PHASES = ['queued', 'reading', 'checking', 'done', 'failed', 'stopped', 'earlier'];
const BUSY_PHASES = new Set(['queued', 'reading', 'checking']);
const PHASE_TITLES = {
  queued: 'Waiting to start', reading: 'Reading your document', checking: 'Checking the codes a second time',
  done: 'Coding review finished', failed: 'The coding review could not finish', stopped: 'The coding review was stopped',
  earlier: 'Earlier review',
};
const STEP_KEYS = ['reading', 'checking', 'finished'];
const STEP_LABELS = { reading: 'Reading', checking: 'Checking', finished: 'Finished' };
const STEP_STATES = { done: 'Done', active: 'In progress', waiting: 'Waiting', failed: 'Did not finish', stopped: 'Stopped', unknown: '' };
const STEP_ICONS = { done: 'check', active: 'clock', failed: 'close', stopped: 'stop' };
// phase -> the state of each step. A review that failed or was stopped does not say how far it got, so the earlier
// steps claim nothing. An earlier review has no coding review of this version, so it has no steps at all.
const PHASE_STEPS = {
  queued: ['waiting', 'waiting', 'waiting'], reading: ['active', 'waiting', 'waiting'], checking: ['done', 'active', 'waiting'],
  done: ['done', 'done', 'done'], failed: ['unknown', 'unknown', 'failed'], stopped: ['unknown', 'unknown', 'stopped'],
  earlier: [],
};
const LEAVE_NOTE = 'You can leave this page. The coding review keeps running, and the document stays in Documents.';
// [action, progress flag, address, button kind, label, icon, what the page says once the server accepts it]
const PROGRESS_ACTIONS = [
  ['stop', 'can_stop', 'stop', 'secondary', 'Stop', 'stop', 'Stopping. A step that is already running finishes; nothing after it starts.'],
  ['resume', 'can_resume', 'resume', 'primary', 'Resume', 'arrow', 'Resumed. The coding review continues.'],
  ['retry', 'can_retry', 'retry', 'primary', 'Retry', 'arrow', 'The coding review starts again.'],
];
// An earlier review's retry: the same act (POST retry), which codes the document with the current version.
const REVIEW_AGAIN = 'Review again';
// document.view_media_type -> the in-page viewer: the PDF (opened at a quoted page) or the text; anything else, none.
const VIEW_KINDS = { 'application/pdf': 'pdf', 'text/plain': 'text' };
const CONVERTED_NOTE = 'Shown as the PDF the coding review read (converted from the Word file).';
const INSURANCE_CHOICES = [['medicare', 'Medicare'], ['medicaid', 'Medicaid'], ['commercial', 'Commercial or other'], ['unknown', 'Not sure']];
const INSURANCE_VALUES = new Set(INSURANCE_CHOICES.map(([value]) => value));
const INSURANCE_SHOWN = { medicare: 'Medicare', medicaid: 'Medicaid', commercial: 'Commercial or other' };
const KIND_LABELS = { upload: 'Uploaded file', paste: 'Pasted text' };
const TRIGGER_TEXT = { answers: 'after your answers', retry: 'after a retry' };
const ROUTE_TITLES = { workspace: 'Overview', documents: 'Documents', queue: 'Review queue', 'how-it-works': 'How it works', doc: 'Document review' };
const LIST_HEADER = '<div class="list-header"><span>DOCUMENT</span><span>STATUS</span><span class="date-header">SERVICE DATE</span><span></span></div>';

// --- pure helpers ----------------------------------------------------------------

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"'`]/g, ch => HTML_ESCAPES[ch]);
}

function lookup(map, key, fallback) {
  return typeof key === 'string' && Object.hasOwn(map, key) ? map[key] : fallback;
}

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

function strings(value) {
  return list(value).map(text).filter(Boolean);
}

function objects(value) {
  return list(value).filter(item => item && typeof item === 'object' && !Array.isArray(item));
}

function record(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function icon(name, className = '') {
  return `<svg class="${className}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function parseIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value ?? ''));
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number);
  const check = new Date(Date.UTC(year, month - 1, day));
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null;
  return { year, month, day };
}

function formatDate(value, long = false) {
  const date = parseIsoDate(value);
  if (!date) return '';
  const month = MONTHS[date.month - 1];
  return `${date.day} ${long ? month : month.slice(0, 3)} ${date.year}`;
}

function formatTimestamp(value) {
  const time = typeof value === 'string' ? Date.parse(value) : NaN;
  if (Number.isNaN(time)) return '';
  const date = new Date(time);
  const clock = `${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}`;
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()].slice(0, 3)} ${date.getUTCFullYear()}, ${clock} UTC`;
}

function formatSize(bytes) {
  return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function pad(number) {
  return String(number).padStart(2, '0');
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function joinWords(items) {
  return items.length <= 2 ? items.join(' and ') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

function readCookie(cookies, name) {
  for (const part of String(cookies || '').split(';')) {
    const index = part.indexOf('=');
    if (index < 0 || part.slice(0, index).trim() !== name) continue;
    try {
      return decodeURIComponent(part.slice(index + 1).trim());
    } catch {
      return '';
    }
  }
  return '';
}

function safeDownloadUrl(url) {
  return typeof url === 'string' && REPORT_URL.test(url) ? url : '';
}

function safeOriginalUrl(url) {
  return typeof url === 'string' && ORIGINAL_URL.test(url) ? url : '';
}

function safeViewUrl(url) {
  return typeof url === 'string' && VIEW_URL.test(url) ? url : '';
}

function pollDelay(count, errors) {
  if (errors > 0) return Math.min(POLL_MAX_ERROR_MS, POLL_BASE_MS * 2 ** errors);
  return Math.min(POLL_MAX_MS, Math.round(POLL_BASE_MS * 1.25 ** count));
}

function parseRoute(hash) {
  const path = String(hash || '').replace(/^#/, '');
  if (path.startsWith('doc/')) return { name: 'doc', id: path.slice(4) };
  return { name: lookup(ROUTE_TITLES, path, null) && path !== 'doc' ? path : 'workspace' };
}

// A conflict status with {"error_code": "client_outdated"}: this build of the page is no longer served.
function isClientOutdated(status, data) {
  return status === 409 && Boolean(data) && typeof data === 'object' && data.error_code === 'client_outdated';
}

// The sentence a failed call shows: the server's own customer sentence when it sends one, else a plain one for the
// status. Never the status code or a technical payload.
function errorText(status, data) {
  const served = typeof data?.error === 'string' ? data.error.trim() : '';
  if (served) return served;
  if (status === 400) return 'This could not be saved. Check the form and try again.';
  if (status === 403) return 'This action is not allowed for your account, or the page is out of date. Reload the page and try again.';
  if (status === 404) return 'Not found, or not in your workspace.';
  if (status === 409) return 'This action is not available right now. Reload the page to see the latest state.';
  if (status === 413) return 'The file is too large. Choose a file up to 15 MB.';
  if (status === 429) return 'Too many attempts in a short time. Wait a moment and try again.';
  return 'Something went wrong on our side. Nothing was changed by this attempt; try again in a moment.';
}

// A version-4 UUID from 16 random bytes: the key one upload attempt carries, so a retried attempt whose answer was
// lost reaches the same document instead of creating a second one.
function newClientKey(randomBytes) {
  const bytes = randomBytes(16);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

// '45 s', '4 min 05 s', '1 h 02 min'. A negative or unreadable span reads as 0 s. Never a percentage or a forecast.
function durationText(ms) {
  const total = Number.isFinite(ms) && ms > 0 ? Math.floor(ms / 1000) : 0;
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} min ${pad(total % 60)} s`;
  return `${Math.floor(minutes / 60)} h ${pad(minutes % 60)} min`;
}

// The server clock minus this browser's, measured when a document arrived, so elapsed time is the server's.
function clockOffset(serverIso, receivedMs) {
  const server = typeof serverIso === 'string' ? Date.parse(serverIso) : NaN;
  return Number.isFinite(server) && Number.isFinite(receivedMs) ? server - receivedMs : 0;
}

function elapsedText(sinceIso, nowMs) {
  const since = typeof sinceIso === 'string' ? Date.parse(sinceIso) : NaN;
  return durationText(Number.isFinite(since) ? nowMs - since : 0);
}

function codePoints(value) {
  return [...String(value)].length;
}

function isoTime(value) {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value)) ? value : '';
}

// A quoted passage inside a text: [start, end] in the text's own offsets, or null. Runs of white space count as one
// space on both sides (a line break in the document may be a space in the quote), and a case-blind match is the
// fallback.
function collapseSpace(source) {
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

function findPassage(source, passage) {
  const hay = collapseSpace(String(source ?? ''));
  const want = collapseSpace(String(passage ?? '')).flat.trim();
  if (!want) return null;
  let at = hay.flat.indexOf(want);
  if (at < 0) at = hay.flat.toLowerCase().indexOf(want.toLowerCase());
  if (at < 0) return null;
  return [hay.map[at], hay.map[at + want.length - 1] + 1];
}

// --- the customer contract, read defensively ---------------------------------------

function canReview(doc) {
  return doc?.permissions?.can_review === true;
}

function stateLabel(stateName, label) {
  return lookup(STATE_LABELS, stateName, text(label) || 'Unknown');
}

// Every code the page can show: a code is named by its CPT code, one row per code.
function codesOf(doc) {
  return objects(doc?.codes).filter(code => text(code.code));
}

function questionsOf(doc) {
  return objects(doc?.questions).filter(question => typeof question.id === 'string' && question.id && text(question.text));
}

function answersOf(doc) {
  return objects(doc?.answers).filter(item => text(item.question) || text(item.answer));
}

function notesOf(doc) {
  return strings(doc?.notes);
}

// The progress phase: the server's, else read from the state. 'earlier' is never 'done': it has no codes to show.
function progressPhase(doc) {
  const phase = doc?.progress?.phase;
  if (PHASES.includes(phase)) return phase;
  return lookup({ processing: 'queued', failed: 'failed', stopped: 'stopped', earlier: 'earlier' }, doc?.state, 'done');
}

function isBusy(doc) {
  return doc?.progress?.busy === true || BUSY_PHASES.has(progressPhase(doc));
}

// The page polls a document while its coding review is queued or running.
function shouldPoll(doc) {
  return Boolean(doc) && isBusy(doc);
}

// One code's status, with its fixed label; a status this page does not know is never shown as reviewable.
function codeStatus(code) {
  const key = typeof code?.status === 'string' ? code.status : '';
  const known = lookup(CODE_STATUSES, key, null);
  if (known) return { key, label: known[0], tone: known[1], icon: known[2] };
  return { key: key || 'unknown', label: text(code?.status_label) || 'Not reviewable', tone: 'gray', icon: '' };
}

function currentDecision(code) {
  const decision = code?.decision;
  return decision && typeof decision === 'object' && lookup(DECISIONS, decision.action, null) ? decision : null;
}

// What the badge says: the decision once one stands (Approved, Rejected), else the code's status.
function shownStatus(code) {
  const decision = currentDecision(code);
  if (!decision) return codeStatus(code);
  const [key, label, tone, iconName] = DECISIONS[decision.action];
  return { key, label, tone, icon: iconName };
}

function unitsLabel(units) {
  return Number.isInteger(units) && units > 0 ? plural(units, 'unit', 'units') : '';
}

function modifiersOf(code) {
  return strings(code?.modifiers);
}

function modifiersLabel(code) {
  const modifiers = modifiersOf(code);
  if (!modifiers.length) return 'No modifier';
  return `${modifiers.length === 1 ? 'Modifier' : 'Modifiers'} ${modifiers.join(', ')}`;
}

// The second check's verdict on one code, and its reason as written. Without a verdict the server's reason is its own
// fixed sentence ("The second check did not review this code."), which is then the whole line, shown as given.
function secondCheck(code) {
  const check = record(code?.second_check);
  const verdict = check.agrees === true ? 'agrees' : check.agrees === false ? 'disagrees' : 'none';
  const reason = text(check.reason);
  if (verdict === 'none' && reason) return { verdict, label: reason, reason: '' };
  const label = { agrees: 'Second check: agrees.', disagrees: 'Second check: disagrees.', none: 'Second check: no verdict.' }[verdict];
  return { verdict, label, reason };
}

function quotePage(quote) {
  return Number.isInteger(quote?.page) && quote.page > 0 ? quote.page : null;
}

function quotesOf(code) {
  return objects(code?.quotes).filter(quote => text(quote.text)).map(quote => ({ text: text(quote.text), page: quotePage(quote) }));
}

function quoteKey(code, index) {
  return `${text(code?.code)}#${index}`;
}

// The viewer's address for one page of the original (a PDF opens at #page=N), or the plain view address.
function viewerUrl(viewUrl, page) {
  const base = safeViewUrl(viewUrl);
  if (!base) return '';
  return Number.isInteger(page) && page > 0 ? `${base}#page=${page}` : base;
}

// What the in-page viewer shows, as the server says in document.view_media_type (never read from media_type, the type
// of the original): 'pdf' (an iframe of view_url, opened at #page=N for a quoted page; for a Word document the PDF the
// coding review read), 'text' (the text, where a quoted passage is found) or 'none' (no viewer, only the download).
function viewerKind(documentPart) {
  const part = record(documentPart);
  if (!safeViewUrl(part.view_url)) return 'none';
  return lookup(VIEW_KINDS, part.view_media_type, 'none');
}

// The decision buttons one code gets: those the server allows, for a member who may review, in a fixed order.
function allowedActions(code, doc) {
  if (!canReview(doc)) return [];
  const allowed = list(code?.allowed_actions);
  return ACTION_BUTTONS.filter(([name]) => allowed.includes(name)).map(([name]) => name);
}

function decisionBody(code, action, acknowledgement = '', note = '') {
  return {
    code: String(code ?? ''), action,
    acknowledgement: action === 'approve' && typeof acknowledgement === 'string' ? acknowledgement : '',
    note: action === 'revoke' ? '' : text(note),
  };
}

// The answers one send carries: every question answered on this page, trimmed, in the order asked - or the sentence
// that says what is missing.
function answersPayload(doc, drafts) {
  const typed = drafts instanceof Map ? drafts : new Map();
  const answers = [];
  for (const question of questionsOf(doc)) {
    const value = text(typed.get(question.id));
    if (!value) continue;
    if (codePoints(value) > MAX_ANSWER_CHARS) return 'An answer can be at most 2,000 characters. Shorten it, then send.';
    answers.push({ question_id: question.id, text: value });
  }
  if (!answers.length) return 'Write an answer to at least one question, then send.';
  return { answers };
}

function insuranceLabel(value) {
  return INSURANCE_CHOICES.find(([key]) => key === value)?.[1] || 'Not sure';
}

// The insurance as the review page states it: a named insurance, else that none was given.
function insuranceText(value) {
  return lookup(INSURANCE_SHOWN, value, 'Insurance not given');
}

function tallyText(doc) {
  const counts = new Map();
  for (const code of codesOf(doc)) {
    const key = shownStatus(code).key;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const parts = TALLY.filter(([key]) => counts.get(key)).map(([key, one, many]) => `${counts.get(key)} ${counts.get(key) === 1 ? one : many}`);
  return parts.length ? parts.join(' · ') : 'No codes yet';
}

function readinessText(doc) {
  const readiness = record(doc?.readiness);
  if (readiness.approved === true) return 'The approved download is available. It lists only approved codes.';
  if (readiness.draft === true) return 'You can download the codes as a draft. Approve codes to download them as approved.';
  return 'Downloads become available when the coding review finishes.';
}

function exportStatusText(doc) {
  const readiness = record(doc?.readiness);
  const blockers = strings(readiness.blockers);
  if (readiness.approved === true) return 'At least one code is approved. The approved download lists only approved codes, with who approved them.';
  const head = readiness.draft === true ? 'Draft only: the codes are the coding review\'s, not approvals.' : 'Nothing can be downloaded yet.';
  return blockers.length ? `${head} Before the approved download: ${blockers.join(' ')}` : head;
}

function emptyCodesText(doc) {
  if (isBusy(doc)) return 'Codes appear here when the coding review finishes.';
  const phase = progressPhase(doc);
  if (phase === 'failed') return 'No codes: the coding review could not finish.';
  if (phase === 'stopped') return 'No codes: the coding review was stopped before it finished.';
  if (phase === 'earlier') return 'Codes appear here once the document is reviewed again with the current version.';
  return 'The coding review found no CPT code to report for this document.';
}

function rowKey(code) {
  return String(code ?? '').replace(/[^A-Za-z0-9]/g, '_');
}

// --- rendering (pure string builders) ----------------------------------------------

const state = {
  session: null, route: null, routeSerial: 0, doc: null, docKey: '', viewerKey: '', selectedQuote: '',
  poll: { timer: 0, count: 0, errors: 0 }, tickTimer: 0, clock: 0, reconnecting: false, outdated: false,
  upload: { file: null, paste: false, busy: false, key: '' }, ack: null, review: null,
  open: new Set(), answers: new Map(), pending: new Set(), toastTimer: 0, leaving: false,
};

function uiState(overrides = {}) {
  return { open: state.open, answers: state.answers, ack: state.ack, reconnecting: state.reconnecting, nowMs: Date.now(), clock: state.clock, entrance: false, ...overrides };
}

function badge(tone, label, iconName = '', attributes = '') {
  return `<span class="status ${tone}"${attributes}>${iconName ? icon(iconName) : ''}${escapeHtml(label)}</span>`;
}

function stateBadge(stateName, label) {
  const iconName = stateName === 'reviewed' ? 'check' : stateName === 'processing' ? 'clock' : '';
  return badge(lookup(STATE_TONES, stateName, 'gray'), stateLabel(stateName, label), iconName);
}

function documentRow(row) {
  const tone = lookup(STATE_TONES, row.state, 'gray');
  const meta = [lookup(KIND_LABELS, row.kind, ''), lookup(INSURANCE_SHOWN, row.insurance, '')].filter(Boolean).join(' · ');
  return `<a class="document-row" href="#doc/${escapeHtml(encodeURIComponent(row.id))}"><span class="doc-row-main"><span class="doc-file-icon${tone === 'amber' ? ' amber' : ''}">${icon('file')}</span><span><strong>${escapeHtml(text(row.title) || 'Untitled document')}</strong><small>${escapeHtml(meta)}</small></span></span><span>${stateBadge(row.state, row.state_label)}</span><span class="doc-row-date">${escapeHtml(formatDate(row.service_date) || 'Not entered')}</span>${icon('chevron', 'row-arrow')}</a>`;
}

function inQueue(row) {
  return QUEUE_STATES.has(row?.state);
}

function listRows(name, rows) {
  if (name === 'queue') return rows.filter(inQueue);
  return name === 'workspace' ? rows.slice(0, 5) : rows;
}

function listBody(name, rows) {
  const shown = listRows(name, rows);
  const empty = { workspace: 'No documents yet. Start with a synthetic GI document.', documents: 'No documents yet. Use New document to upload a synthetic GI document or paste its text.', queue: 'Nothing is waiting for you.' }[name];
  return LIST_HEADER + (shown.length ? shown.map(row => documentRow(row)).join('') : `<p class="empty-state">${escapeHtml(empty)}</p>`);
}

function listDescription(name, rows) {
  if (name === 'queue') {
    const count = listRows('queue', rows).length;
    return count ? `${count === 1 ? 'One document waits' : `${count} documents wait`} on you: questions to answer, or codes to review or approve.` : 'No document waits on you for an answer or a decision.';
  }
  return `${plural(rows.length, 'synthetic document', 'synthetic documents')} in this workspace.`;
}

function inviteMarkup(rows) {
  const recent = rows?.[0];
  if (rows === null) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>Loading recent documents…</strong><p>One moment.</p></span>`;
  if (!recent) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>No documents yet</strong><p>Upload a synthetic GI document to see its CPT codes beside the source.</p></span><button type="button" class="button secondary" data-action="upload">New document ${icon('plus')}</button>`;
  const detail = ['Most recent', stateLabel(recent.state, recent.state_label), formatDate(recent.service_date) || 'service date not entered'].join(' · ');
  return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>${escapeHtml(text(recent.title) || 'Untitled document')}</strong><p>${escapeHtml(detail)}</p></span><button type="button" class="button secondary" data-open="${escapeHtml(recent.id)}">Open review ${icon('arrow')}</button>`;
}

function overviewView() {
  return `<section class="view-entrance"><div class="heading-row home-heading"><div><span class="eyebrow">A CLEARER VIEW OF EVERY CODE</span><h1>Precision starts<br>with the <em>evidence.</em></h1><p>A focused workspace that reads clinical documentation and suggests CPT codes, each with its reason and the passages it rests on.</p></div><div class="heading-actions"><span class="only-tag">CPT ONLY</span><button type="button" class="button primary" data-action="upload" aria-label="New document">${icon('plus')}<span class="desktop-label">New document</span></button></div></div>
  <div class="home-grid"><section class="upload-panel"><div class="panel-heading">${icon('file')}<h2>Start a coding review</h2><span class="small-badge">One encounter at a time</span></div><button type="button" class="drop-zone" id="overviewDrop" data-action="upload"><span class="upload-icon">${icon('upload')}</span><strong>Bring the original document.</strong><span>Choose a file, drop it here or paste the text</span><span>PDF, DOCX or TXT</span></button><div class="upload-footnote">${icon('info')}<span>Synthetic documents only. Do not upload real patient information.</span></div><div class="sample-invite" id="recentInvite">${inviteMarkup(null)}</div></section>
  <aside class="story-panel"><span class="eyebrow">BUILT AROUND THE CLINICAL STORY</span><h2>A clearer path.<br>From note to code.</h2><ol class="workflow-list"><li><span class="workflow-number">01</span><span><strong>Bring the original document</strong><p>The coding review reads the whole document, every page of it.</p></span></li><li><span class="workflow-number">02</span><span><strong>See why each code is there</strong><p>Every code comes with its reason, the passages it rests on and a second check.</p></span></li><li><span class="workflow-number">03</span><span><strong>Answer, then decide</strong><p>Answer any questions about the document, then approve or reject each code.</p></span></li></ol><div class="story-bottom">${icon('link')}Evidence beside the decision. Always.</div></aside></div>
  <div class="section-heading"><h2>Recent documents</h2><a href="#documents">View all ${icon('arrow')}</a></div><div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div></section>`;
}

function documentsView(name) {
  const queue = name === 'queue';
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">${queue ? 'WHAT WAITS ON YOU' : 'THE ORIGINAL, ALWAYS IN VIEW'}</span><h1>${queue ? 'Review queue.' : 'Your documents.'}</h1><p>${queue ? 'Questions to answer and codes to review or approve: each document shows its next step.' : 'Keep source notes, supporting evidence and coding decisions together.'}</p></div><div class="heading-actions"><button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button></div></div><p class="section-description" id="listDescription">Loading…</p>${queue ? '' : `<label class="search-field list-search">${icon('search')}<input id="documentSearch" aria-label="Search documents" placeholder="Search documents…" autocomplete="off"></label>`}<div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div><p class="checks-disclaimer">${queue ? 'A document that is still being processed is not listed here; it appears once it needs you.' : 'Synthetic documents only. Each decision is tied to the coding review it was made on.'}</p></section>`;
}

function howItWorksView() {
  return `<section class="view-entrance"><div class="heading-row how-heading"><div><span class="eyebrow">A FOCUSED PRODUCT, BY DESIGN</span><h1>A reason behind<br><em>every suggestion.</em></h1><p>A standalone CPT workspace that keeps the original clinical story and the coding review connected.</p></div><button type="button" class="button primary" data-action="upload">Start a coding review ${icon('arrow')}</button></div><div class="flow-overview"><article class="flow-card"><span class="step">01</span><h2>The source<br>comes first.</h2><p>Upload the original PDF, Word document or text file, or paste the note. The coding review reads the whole document as it is, and you can open it beside the codes.</p></article><article class="flow-card"><span class="step">02</span><h2>Read, then<br>checked again.</h2><p>The coding review suggests each code with its reason and the passages it rests on. A second check then reviews every code on its own. Where the two disagree, the code needs your review.</p></article><article class="flow-card"><span class="step">03</span><h2>Review makes<br>the difference.</h2><p>Answer any questions about the document; your answers start a new coding review. Then approve or reject each code, and download the codes as a draft or the approved codes alone.</p></article></div><div class="how-note"><strong>This is a synthetic demonstration.</strong><br>Licensed CPT descriptors are not shown in this release. The coding review reads the wording of the document and can be wrong, so every code needs a reviewer who reads the whole document. Accuracy has not been independently evaluated; no accuracy percentage or payment guarantee is claimed.</div><button type="button" class="button secondary" data-action="about">${icon('info')}About CPT Studio</button></section>`;
}

function messageView(title, detail, retry = false) {
  return `<section class="view-entrance"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="check-list-card"><p class="empty-state"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</p>${retry ? '<p class="empty-state"><button type="button" class="button secondary" data-action="reload-view">Try again</button></p>' : ''}</div></section>`;
}

// The upload is acknowledged from the server's answer, before the document is first read back.
function uploadAck(ack, extra = '') {
  if (!ack) return '';
  const at = formatTimestamp(new Date(ack.at).toISOString());
  return `<div class="upload-ack" role="status">${icon('circle-check')}<div><strong>Uploaded. The coding review starts shortly.</strong><p>${escapeHtml(`Received ${at}.`)}${extra ? ` ${escapeHtml(extra)}` : ''}</p></div></div>`;
}

function ackView(ack) {
  return `<section class="view-entrance review-view"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="review-column ack-column">${uploadAck(ack, 'You can leave this page; the document stays in Documents.')}</div></section>`;
}

// --- the review page: the heading ---

function reviewMeta(doc) {
  const context = record(doc?.context);
  const date = formatDate(context.service_date);
  const items = [date ? `Date of service ${date}` : 'Date of service not entered', insuranceText(context.insurance)];
  const round = record(doc?.round);
  if (Number.isInteger(round.number) && round.number > 0) {
    const trigger = lookup(TRIGGER_TEXT, round.trigger, '');
    items.push(`Coding review ${round.number}${trigger ? `, ${trigger}` : ''}`);
  }
  return [`<span>${stateBadge(doc?.state, doc?.state_label)}</span>`, ...items.map(item => `<span>${escapeHtml(item)}</span>`)].join('');
}

function reviewHeading(doc) {
  const download = codesOf(doc).length || objects(doc?.reports).length ? `<button type="button" class="button secondary" data-action="export">${icon('download')}<span>Download</span></button>` : '';
  return `<div class="heading-row review-heading"><div><span class="eyebrow">CODING REVIEW · GASTROENTEROLOGY</span><h1>${escapeHtml(text(doc?.title) || 'Untitled document')}</h1><div class="review-meta">${reviewMeta(doc)}</div></div><div class="heading-actions"><button type="button" class="button secondary" data-action="upload">${icon('plus')}<span>New document</span></button>${download}</div></div>`;
}

// --- the original document and its quoted passages (left) ---

function documentName(part) {
  return text(part.name) || (part.kind === 'paste' ? 'Pasted text' : 'Original document');
}

// The viewer of the original: an iframe of view_url for a PDF or a text, with a note under it when the PDF is the one a
// Word document was converted to; with no view, no viewer at all and only the "Download original" link.
function viewerPanel(doc) {
  const part = record(doc?.document);
  const kind = viewerKind(part);
  const name = documentName(part);
  const original = safeOriginalUrl(part.original_url);
  const frame = kind === 'none' ? ''
    : `<iframe id="documentViewer" class="viewer-frame" src="${escapeHtml(viewerUrl(part.view_url, null))}" title="${escapeHtml(`Original document: ${name}`)}" referrerpolicy="same-origin"></iframe>`;
  const note = kind === 'pdf' && part.converted === true ? `<p class="viewer-note">${icon('info')}<span>${escapeHtml(CONVERTED_NOTE)}</span></p>` : '';
  const meta = [lookup(KIND_LABELS, part.kind, ''), Number.isInteger(part.size) && part.size > 0 ? formatSize(part.size) : ''].filter(Boolean).join(' · ');
  const download = original ? `<a class="viewer-download" id="downloadOriginal" href="${escapeHtml(original)}" download>${icon('download')}Download original</a>` : '';
  return `<section class="viewer-panel${kind === 'none' ? ' no-view' : ''}" aria-labelledby="viewerTitle"><div class="viewer-toolbar">${icon('file')}<h2 id="viewerTitle">Original document</h2><span class="viewer-name">${escapeHtml(name)}</span></div>${frame}${note}<div class="viewer-bottom"><span>${escapeHtml(meta || 'Original as received')}</span>${download}</div></section>`;
}

function quoteBody(quote) {
  return `<q class="quote-text">${escapeHtml(quote.text)}</q><span class="quote-page">${quote.page ? escapeHtml(`Page ${quote.page}`) : ''}</span>`;
}

function quotesLead(doc) {
  const kind = viewerKind(doc?.document);
  if (kind === 'pdf') return 'Each code rests on these passages. Choose one to open its page in the document.';
  if (kind === 'text') return 'Each code rests on these passages. Choose one to find it in the document.';
  return 'Each code rests on these passages of the original document.';
}

// The hint a quoted passage carries, where the viewer can show it.
function quoteTitle(doc) {
  return ['pdf', 'text'].includes(viewerKind(doc?.document)) ? ' title="Show this passage in the document"' : '';
}

function quotesPanel(doc) {
  const entries = codesOf(doc).flatMap(code => quotesOf(code).map((quote, index) => ({ code, quote, index })));
  const items = entries.map(({ code, quote, index }) => `<li><button type="button" class="quote" data-code="${escapeHtml(code.code)}" data-page="${quote.page ?? ''}" data-quote="${escapeHtml(quoteKey(code, index))}"${quoteTitle(doc)}><span class="quote-code">${escapeHtml(code.code)}</span>${quoteBody(quote)}</button></li>`).join('');
  const empty = isBusy(doc) ? 'Quoted passages appear here when the coding review finishes.'
    : progressPhase(doc) === 'earlier' ? 'Quoted passages appear here once the document is reviewed again.' : 'No passage of the document is quoted.';
  return `<section class="quotes-panel" id="quotesPanel" aria-labelledby="quotesTitle"><div class="quotes-head"><h2 id="quotesTitle">Quoted passages</h2>${entries.length ? `<span class="small-badge">${entries.length}</span>` : ''}</div>`
    + (entries.length ? `<p class="quotes-lead">${escapeHtml(quotesLead(doc))}</p><ol class="quote-list">${items}</ol>` : `<p class="quotes-empty">${escapeHtml(empty)}</p>`)
    + '</section>';
}

// --- the progress panel ---

function progressSteps(phase) {
  const states = lookup(PHASE_STEPS, phase, PHASE_STEPS.queued);
  return states.map((stepState, index) => ({ key: STEP_KEYS[index], label: STEP_LABELS[STEP_KEYS[index]], state: stepState }));
}

function progressStep(step, animate) {
  const stateText = lookup(STEP_STATES, step.state, '');
  const iconName = lookup(STEP_ICONS, step.state, '');
  return `<li class="progress-step${step.state === 'active' && animate ? ' is-animated' : ''}" data-step="${step.key}" data-state="${step.state}"><span class="step-mark" aria-hidden="true">${iconName ? icon(iconName) : ''}</span><span class="step-text"><strong>${escapeHtml(step.label)}</strong>${stateText ? `<small>${escapeHtml(stateText)}</small>` : ''}</span></li>`;
}

// [label, markup] of the time the panel states: elapsed, ticking, while busy; the total once ended; else null.
function progressTime(progress, phase, busy, ui) {
  const started = isoTime(progress?.started_at);
  if (!started) return null;
  if (busy) {
    const now = (ui.nowMs ?? Date.now()) + (ui.clock || 0);
    return ['Elapsed', `<span data-elapsed data-since="${escapeHtml(started)}">${escapeHtml(elapsedText(started, now))}</span>`];
  }
  const finished = isoTime(progress?.finished_at);
  if (!finished) return null;
  return [phase === 'done' ? 'Finished in' : 'Ran for', `<span data-elapsed data-since="${escapeHtml(started)}" data-until="${escapeHtml(finished)}">${escapeHtml(durationText(Date.parse(finished) - Date.parse(started)))}</span>`];
}

// Stop, Resume and Retry, each only when the server offers it and the member may review: Stop while the review runs,
// the other two once it does not. An earlier review's retry is "Review again".
function progressButtons(doc, busy, phase) {
  if (!canReview(doc)) return '';
  const progress = record(doc?.progress);
  return PROGRESS_ACTIONS.filter(([action, flag]) => progress[flag] === true && (action === 'stop' ? busy : !busy))
    .map(([action, , , kind, label, iconName]) => {
      const shown = action === 'retry' && phase === 'earlier' ? REVIEW_AGAIN : label;
      return `<button type="button" class="button ${kind}" data-action="${action}">${action === 'stop' ? `${icon(iconName)}${shown}` : `${shown} ${icon(iconName)}`}</button>`;
    }).join('');
}

function progressPanel(doc, ui = {}) {
  const progress = record(doc?.progress);
  const phase = progressPhase(doc);
  const busy = isBusy(doc);
  const animate = busy && (phase === 'reading' || phase === 'checking' || phase === 'queued');
  const steps = progressSteps(phase).map(step => progressStep(step, animate)).join('');
  const time = progressTime(progress, phase, busy, ui);
  const message = text(progress.message);
  const failure = text(record(progress.error).text);
  if (phase === 'done' && !busy) {
    const took = time ? ` · ${time[0].toLowerCase()} ${time[1]}` : '';
    return `<section class="progress-panel progress-compact" data-phase="done" aria-labelledby="progressTitle"><div class="progress-head">${icon('circle-check')}<div class="progress-status"><p class="progress-summary"><strong id="progressTitle">${escapeHtml(PHASE_TITLES.done)}</strong>${took}</p>${message ? `<p class="progress-message">${escapeHtml(message)}</p>` : ''}</div></div><ol class="progress-steps">${steps}</ol></section>`;
  }
  const headIcon = lookup({ failed: 'close', stopped: 'stop', earlier: 'info' }, phase, 'clock');
  const showAck = ui.ack && ui.ack.id === doc?.id && busy;
  const said = message && message !== failure ? message : '';
  const buttons = progressButtons(doc, busy, phase);
  return `<section class="progress-panel${busy ? ' progress-card' : ''}" data-phase="${phase}" aria-labelledby="progressTitle">`
    + `<div class="progress-head"><span class="progress-icon${animate ? ' is-animated' : ''}">${icon(headIcon)}</span><div class="progress-status" aria-live="polite"><h2 id="progressTitle">${escapeHtml(PHASE_TITLES[phase])}</h2>${said ? `<p class="progress-message">${escapeHtml(said)}</p>` : ''}</div></div>`
    + (showAck ? uploadAck(ui.ack) : '')
    + (steps ? `<ol class="progress-steps">${steps}</ol>` : '')
    + (time ? `<p class="progress-time">${time[0]} ${time[1]}</p>` : '')
    + `<p class="progress-reconnecting" role="status"${ui.reconnecting && busy ? '' : ' hidden'}>Reconnecting…</p>`
    + (failure ? `<div class="progress-error" role="alert">${icon('info')}<div><p>${escapeHtml(failure)}</p></div></div>` : '')
    + (busy ? `<p class="leave-note">${escapeHtml(LEAVE_NOTE)}</p>` : '')
    + (buttons ? `<div class="progress-actions">${buttons}</div>` : '')
    + '</section>';
}

// --- questions for you, and the answers given earlier ---

function questionsLead(count, editable, busy) {
  if (busy) return 'You can answer once the coding review has finished.';
  if (!editable) return 'A reviewer can answer these questions.';
  return `${count === 1 ? 'The coding review has one question' : `The coding review has ${count} questions`} about this document. Answer what you can, then send all answers at once.`;
}

function questionsPanel(doc, ui = {}) {
  const questions = questionsOf(doc);
  if (!questions.length) return '';
  const busy = isBusy(doc);
  const editable = canReview(doc) && !busy;
  const drafts = ui.answers instanceof Map ? ui.answers : new Map();
  const rows = questions.map((question, index) => {
    const field = `answer-${index + 1}`;
    const codes = strings(question.codes);
    const lead = `<span class="question-number">${escapeHtml(`Question ${index + 1}`)}</span><span class="question-text">${escapeHtml(text(question.text))}</span>`;
    const draft = typeof drafts.get(question.id) === 'string' ? drafts.get(question.id) : '';
    return `<li class="question-row" data-question="${escapeHtml(question.id)}">${editable ? `<label class="question-label" for="${field}">${lead}</label>` : `<p class="question-label">${lead}</p>`}`
      + (codes.length ? `<p class="question-codes">${escapeHtml(`About ${joinWords(codes)}`)}</p>` : '')
      + (editable ? `<textarea id="${field}" class="question-answer" data-answer="${escapeHtml(question.id)}" rows="3" maxlength="${MAX_ANSWER_CHARS}" placeholder="Your answer">${escapeHtml(draft)}</textarea>` : '')
      + '</li>';
  }).join('');
  const send = editable ? `<p class="form-error" id="answersError" role="alert" hidden></p><div class="questions-actions"><button type="button" class="button primary" id="sendAnswers" data-action="send-answers">Send answers ${icon('arrow')}</button><p>Your answers start a new coding review of the whole document. Its codes replace these when it finishes, and decisions on these codes do not carry over.</p></div>` : '';
  return `<section class="questions-panel" id="questionsPanel" aria-labelledby="questionsTitle"><div class="questions-head">${icon('help')}<div><h2 id="questionsTitle">Questions for you</h2><p>${escapeHtml(questionsLead(questions.length, editable, busy))}</p></div></div><ol class="question-list">${rows}</ol>${send}</section>`;
}

function answersPanel(doc) {
  const items = answersOf(doc);
  if (!items.length) return '';
  const rows = items.map(item => {
    const by = [text(item.by), formatTimestamp(item.at)].filter(Boolean).join(', ');
    return `<li class="answer-item"><p class="answer-question">${escapeHtml(text(item.question))}</p><p class="answer-text">${escapeHtml(text(item.answer))}</p>${by ? `<small>${escapeHtml(by)}</small>` : ''}</li>`;
  }).join('');
  return `<section class="answers-panel" id="answersPanel" aria-labelledby="answersTitle"><h2 id="answersTitle">Earlier answers</h2><p>The coding review reads these with the document.</p><ol class="answer-list">${rows}</ol></section>`;
}

// --- the codes ---

function decisionButton(action, code) {
  const [, kind, label, iconName] = ACTION_BUTTONS.find(([name]) => name === action);
  return `<button type="button" class="button ${kind}" id="act-${rowKey(code.code)}-${action}" data-decision="${action}" data-code="${escapeHtml(code.code)}">${label}${iconName ? ` ${icon(iconName)}` : ''}</button>`;
}

function codeQuotes(code, doc) {
  const quotes = quotesOf(code);
  if (!quotes.length) return '<p class="code-quotes code-quotes-empty">No passage of the document is quoted for this code.</p>';
  return `<ul class="code-quotes" aria-label="${escapeHtml(`Passages quoted for ${code.code}`)}">${quotes.map((quote, index) => `<li><button type="button" class="code-quote" data-quote="${escapeHtml(quoteKey(code, index))}" data-view-page="${quote.page ?? ''}"${quoteTitle(doc)}>${quoteBody(quote)}</button></li>`).join('')}</ul>`;
}

function decisionLine(code) {
  const decision = currentDecision(code);
  if (!decision) return '';
  const title = `${DECISIONS[decision.action][1]} by ${text(decision.by) || 'a reviewer whose name was not recorded'}`;
  const when = formatTimestamp(decision.at);
  const note = text(decision.note);
  return `<div class="code-decision">${icon('shield')}<div><strong>${escapeHtml(title)}</strong>${when ? `<p>${escapeHtml(`${when} · synthetic review, not clinical approval`)}</p>` : ''}${note ? `<p>${escapeHtml(`Note: ${note}`)}</p>` : ''}</div></div>`;
}

function codeHint(code) {
  if (currentDecision(code)) return '';
  const key = codeStatus(code).key;
  if (key === 'needs_answer') return '<p class="code-hint">Answer the question above to finish this code.</p>';
  if (key === 'not_supported') return '<p class="code-hint">The document does not support this code, so it cannot be approved.</p>';
  return '';
}

function codeRow(code, doc) {
  const status = shownStatus(code);
  const decision = currentDecision(code);
  const check = secondCheck(code);
  const question = text(code.question);
  const actions = allowedActions(code, doc);
  return `<li class="code-row" id="code-${rowKey(code.code)}" tabindex="-1" data-code="${escapeHtml(code.code)}" data-status="${escapeHtml(codeStatus(code).key)}"${decision ? ` data-decision="${escapeHtml(decision.action)}"` : ''} data-units="${escapeHtml(Number.isInteger(code.units) ? code.units : '')}" data-modifiers="${escapeHtml(modifiersOf(code).join(' '))}">`
    + `<div class="code-head"><span class="code-number">${escapeHtml(code.code)}</span><span class="code-units">${escapeHtml(unitsLabel(code.units))}</span><span class="code-modifiers">${escapeHtml(modifiersLabel(code))}</span>${badge(status.tone, status.label, status.icon, ` data-status="${escapeHtml(status.key)}"`)}</div>`
    + `<p class="code-reason">${escapeHtml(text(code.reason) || 'No reason was given for this code.')}</p>`
    + `<p class="code-check" data-check="${check.verdict}">${icon(check.verdict === 'agrees' ? 'circle-check' : 'info')}<span><strong>${escapeHtml(check.label)}</strong>${check.reason ? ` ${escapeHtml(check.reason)}` : ''}</span></p>`
    + (question ? `<p class="code-question">${icon('help')}<span>${escapeHtml(question)}</span></p>` : '')
    + codeQuotes(code, doc)
    + decisionLine(code)
    + codeHint(code)
    + (actions.length ? `<div class="code-actions">${actions.map(action => decisionButton(action, code)).join('')}</div>` : '')
    + '</li>';
}

function reviewBar(doc) {
  return `<div class="review-bar"><div><p class="review-tally">${escapeHtml(tallyText(doc))}</p><p class="review-readiness">${escapeHtml(readinessText(doc))}</p></div><button type="button" class="button secondary" data-action="export">${icon('download')}Review and download</button></div>`;
}

function codesSection(doc) {
  const codes = codesOf(doc);
  const bar = codes.length || objects(doc?.reports).length ? reviewBar(doc) : '';
  return `<section class="codes-section" aria-labelledby="codesTitle"><div class="results-topline"><h2 id="codesTitle">CPT codes</h2>${codes.length ? `<span class="small-badge">${codes.length}</span>` : ''}</div>`
    + `<ol id="codesList" class="codes-list" aria-label="CPT codes"${codes.length ? '' : ' hidden'}>${codes.map(code => codeRow(code, doc)).join('')}</ol>`
    + (codes.length ? '' : `<p class="results-empty">${escapeHtml(emptyCodesText(doc))}</p>`)
    + `${bar}</section>`;
}

// Documentation notes: what the coding review noticed about the documentation itself, as written. Shown once a review
// has finished, so "no notes" is never said of a review still running.
function notesPanel(doc) {
  const notes = notesOf(doc);
  if (!notes.length && !(progressPhase(doc) === 'done' && !isBusy(doc))) return '';
  const body = notes.length ? `<p>What the coding review noticed about the documentation itself.</p><ul class="notes-list">${notes.map(note => `<li>${escapeHtml(note)}</li>`).join('')}</ul>` : '<p class="notes-empty">The coding review made no notes about the documentation.</p>';
  return `<section class="notes-panel" id="notesPanel" aria-labelledby="notesTitle"><h2 id="notesTitle">Documentation notes</h2>${body}</section>`;
}

function activityLog(doc, ui = {}) {
  const items = objects(doc?.activity).filter(item => text(item.text));
  if (!items.length) return '';
  const key = 'activity';
  return `<details class="activity-log" data-key="${key}"${ui.open?.has?.(key) ? ' open' : ''}><summary>History</summary><ol>${items.map(item => {
    const at = formatTimestamp(item.at);
    return `<li><strong>${escapeHtml(text(item.text))}</strong>${at ? `<small>${escapeHtml(at)}</small>` : ''}</li>`;
  }).join('')}</ol></details>`;
}

function reviewColumn(doc, ui = {}) {
  return `${progressPanel(doc, ui)}${questionsPanel(doc, ui)}${answersPanel(doc)}${codesSection(doc)}${notesPanel(doc)}${activityLog(doc, ui)}`;
}

// The whole review page. The right column, the heading and the quoted passages are redrawn on their own after a read
// that changes them (renderDocument), so the original document's viewer is never reloaded under the member.
function reviewView(doc, ui = {}) {
  return `<section class="${ui.entrance ? 'view-entrance ' : ''}review-view"><a class="back-link" href="#documents">${icon('arrow')}All documents</a>`
    + `<div id="reviewHead">${reviewHeading(doc)}</div>`
    + `<div class="review-layout"><div class="review-column" id="reviewColumn">${reviewColumn(doc, ui)}</div><div class="viewer-column">${viewerPanel(doc)}<div id="quotesBox">${quotesPanel(doc)}</div></div></div></section>`;
}

// --- the export dialog ---

function exportOption(kind, fmt, enabled, title, detail) {
  return `<button type="button" class="export-option" data-export-kind="${kind}" data-export-fmt="${fmt}"${enabled ? '' : ' disabled'}><span class="export-format">${fmt.toUpperCase()}</span><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></span>${icon('download')}</button>`;
}

// An export made from an earlier coding review is still listed and linked, and says so.
function reportItem(report) {
  const url = safeDownloadUrl(report.download_url);
  const name = text(report.filename) || 'Download';
  const kind = report.kind === 'approved' ? 'Approved codes' : 'Codes (draft)';
  const meta = [kind, formatTimestamp(report.generated_at)].filter(Boolean).join(' · ');
  const link = url ? `<a href="${escapeHtml(url)}" download>${escapeHtml(name)}</a>` : `<span>${escapeHtml(name)}</span>`;
  if (report.current !== true) return `<li class="report-item earlier">${link}<small>${escapeHtml(`${meta} · Earlier: made from an earlier coding review; it may not show the current codes`)}</small></li>`;
  return `<li class="report-item">${link}<small>${escapeHtml(meta)}</small></li>`;
}

function exportOptions(doc) {
  const readiness = record(doc?.readiness);
  const draft = readiness.draft === true;
  const approved = readiness.approved === true;
  const blockers = strings(readiness.blockers);
  const reports = objects(doc?.reports);
  const draftDetail = 'Every code with its status, units, modifiers, reason and quoted passages. Nothing in it is approved.';
  const approvedDetail = 'Only approved codes, with who approved them and when.';
  const why = !approved && blockers.length ? `<div class="export-blockers"><p>Not available yet:</p><ul>${blockers.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '';
  return `<div class="export-group"><div class="evidence-label">Codes — not approved</div>${exportOption('draft', 'txt', draft, 'Codes as text (draft)', draftDetail)}${exportOption('draft', 'csv', draft, 'Codes as a spreadsheet (CSV, draft)', draftDetail)}</div>`
    + `<div class="export-group"><div class="evidence-label">Approved codes</div>${exportOption('approved', 'txt', approved, 'Approved codes as text', approvedDetail)}${exportOption('approved', 'csv', approved, 'Approved codes as a spreadsheet (CSV)', approvedDetail)}${why}</div>`
    + (reports.length ? `<div class="export-group"><div class="evidence-label">Earlier downloads</div><ul class="report-list">${reports.map(reportItem).join('')}</ul></div>` : '');
}

// The multipart body of one upload attempt, or the sentence that says what is missing.
function uploadForm(fields, key) {
  const form = new FormData();
  if (fields.paste) {
    if (!text(fields.text)) return 'Paste the clinical text, or switch back to uploading a file.';
    if (codePoints(fields.text) > MAX_PASTE_CHARS) return 'The pasted text is longer than 400,000 characters. Upload it as a file instead.';
    form.append('text', fields.text);
  } else {
    if (!fields.file) return 'Choose a PDF, DOCX or TXT document, or paste the text instead.';
    form.append('file', fields.file, fields.file.name);
  }
  if (fields.serviceDate && !parseIsoDate(fields.serviceDate)) return 'Enter the service date as a valid date, or leave it blank.';
  const insurance = fields.insurance ?? 'unknown';
  if (!INSURANCE_VALUES.has(insurance)) return 'Choose the insurance, or Not sure.';
  if (!fields.attested) return 'Confirm that the document is synthetic and contains no real patient information.';
  if (fields.serviceDate) form.append('service_date', fields.serviceDate);
  form.append('insurance', insurance);
  form.append('synthetic_attestation', 'yes');
  form.append('client_key', key);
  return form;
}

// --- browser wiring ------------------------------------------------------------------

class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.status = status;
    this.details = data && typeof data === 'object' && data.details && typeof data.details === 'object' ? data.details : null;
  }
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function csrfValue() {
  return readCookie(document.cookie, 'cptstudio_csrf') || $('input[name="csrfmiddlewaretoken"]')?.value || '';
}

function goToLogin() {
  if (state.leaving) return;
  state.leaving = true;
  location.assign(`/login/?next=${encodeURIComponent(`/${location.hash}`)}`);
}

function showUpdateNotice() {
  state.outdated = true;
  stopPolling();
  const notice = $('#updateNotice');
  if (notice) notice.hidden = false;
}

// One call to the customer API. A change the server accepts with no body reads as an empty answer; a read must be JSON.
async function api(path, { method = 'GET', json, form } = {}) {
  const headers = { Accept: 'application/json', [CLIENT_HEADER]: CLIENT_VERSION };
  let body;
  if (method !== 'GET') headers['X-CSRFToken'] = csrfValue();
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let response;
  try {
    response = await fetch(path, { method, headers, body, credentials: 'same-origin', cache: 'no-store' });
  } catch {
    throw new ApiError(OFFLINE_TEXT);
  }
  if (response.status === 401 || (response.redirected && new URL(response.url).pathname.startsWith('/login'))) {
    goToLogin();
    throw new ApiError('Your session has ended. Sign in again.', 401);
  }
  const isJson = (response.headers.get('Content-Type') || '').includes('application/json');
  const data = isJson ? await response.json().catch(() => null) : null;
  if (isClientOutdated(response.status, data)) {
    showUpdateNotice();
    throw new ApiError(OUTDATED_TEXT, 409, data);
  }
  if (!response.ok) throw new ApiError(errorText(response.status, data), response.status, data);
  if (data && typeof data === 'object') return data;
  if (method !== 'GET') return {};
  throw new ApiError('The server answered in a way this page cannot read. Reload the page and try again.', response.status);
}

function toast(message) {
  clearTimeout(state.toastTimer);
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('visible');
  state.toastTimer = setTimeout(() => element.classList.remove('visible'), 4200);
}

function showError(id, message) {
  const element = $(`#${id}`);
  if (!element) return;
  element.textContent = message;
  element.hidden = false;
}

function hideError(id) {
  const element = $(`#${id}`);
  if (element) element.hidden = true;
}

function setBusy(button, busy) {
  if (!button) return;
  button.disabled = busy;
  button.toggleAttribute('aria-busy', busy);
}

function openDialog(id) {
  const dialog = $(`#${id}`);
  if (!dialog.open) dialog.showModal();
}

function closeDialog(id) {
  const dialog = $(`#${id}`);
  if (dialog.open) dialog.close();
}

function closeNavigation() {
  const wasOpen = $('#sidebar').classList.contains('open');
  $('#sidebar').classList.remove('open');
  $('#sidebarBackdrop').hidden = true;
  $('#menuButton').setAttribute('aria-expanded', 'false');
  $('#sidebar').inert = window.matchMedia('(max-width:760px)').matches;
  if (wasOpen) $('#menuButton').focus({ preventScroll: true });
}

function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function isAgent() {
  return state.session?.user?.actor_kind === 'agent';
}

function setCount(selector, value) {
  const element = $(selector);
  const valid = Number.isInteger(value) && value >= 0;
  element.textContent = valid ? String(value) : '';
  element.hidden = !valid;
}

function renderSession(session) {
  const name = text(session.workspace?.name) || 'Workspace';
  $('#workspaceName').textContent = name;
  $('#workspaceSubtitle').textContent = 'Synthetic demonstration workspace';
  $('#workspaceAvatar').textContent = ([...name][0] || '').toUpperCase();
  const label = text(session.user?.label) || 'Signed in';
  const initials = text(session.user?.initials) || label.split(/\s+/).filter(Boolean).slice(0, 2).map(word => [...word][0]).join('').toUpperCase();
  $('#profileAvatar').textContent = initials;
  $('#topAvatar').textContent = initials;
  $('#profileName').textContent = label;
  $('#profileRole').textContent = lookup({ owner: 'Owner', reviewer: 'Reviewer', viewer: 'Viewer' }, session.role, 'Member');
  setCount('#documentsCount', session.counts?.documents);
  setCount('#queueCount', session.counts?.queue);
}

async function loadSession() {
  try {
    state.session = await api('/api/session');
    renderSession(state.session);
  } catch (error) {
    if (error.status !== 401) toast(`The workspace could not be loaded. ${error.message}`);
  }
  return state.session;
}

function setActiveNav(name) {
  const active = name === 'doc' ? 'documents' : name;
  $$('[data-nav]').forEach(link => {
    link.classList.toggle('active', link.dataset.nav === active);
    if (link.dataset.nav === active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
}

function stopPolling() {
  clearTimeout(state.poll.timer);
  state.poll = { timer: 0, count: 0, errors: 0 };
}

function stopTicker() {
  clearTimeout(state.tickTimer);
  state.tickTimer = 0;
}

function route() {
  const next = parseRoute(location.hash);
  const serial = ++state.routeSerial;
  stopPolling();
  stopTicker();
  if (next.name !== 'doc' || next.id !== state.doc?.id) {
    state.doc = null;
    state.docKey = '';
    state.viewerKey = '';
    state.selectedQuote = '';
    state.open = new Set();
    state.answers = new Map();
    state.reconnecting = false;
  }
  state.route = next;
  $('#breadcrumbCurrent').textContent = ROUTE_TITLES[next.name];
  setActiveNav(next.name);
  closeNavigation();
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (next.name === 'doc') return showDocument(next.id, serial);
  if (next.name === 'how-it-works') {
    $('#main').innerHTML = howItWorksView();
    return undefined;
  }
  return showList(next.name, serial);
}

async function showList(name, serial) {
  $('#main').innerHTML = name === 'workspace' ? overviewView() : documentsView(name);
  let rows;
  try {
    const data = await api('/api/encounters');
    rows = Array.isArray(data) ? data : data.encounters;
    if (!Array.isArray(rows)) throw new ApiError('The server answered with a document list this page cannot read.');
    rows = objects(rows);
  } catch (error) {
    if (serial !== state.routeSerial) return;
    $('#documentsTable').innerHTML = `${LIST_HEADER}<p class="empty-state">${escapeHtml(`Documents could not be loaded. ${error.message}`)}</p>`;
    if ($('#listDescription')) $('#listDescription').textContent = 'Documents could not be loaded.';
    if ($('#recentInvite')) $('#recentInvite').innerHTML = '';
    return;
  }
  if (serial !== state.routeSerial) return;
  $('#documentsTable').innerHTML = listBody(name, rows);
  if ($('#listDescription')) $('#listDescription').textContent = listDescription(name, rows);
  if ($('#recentInvite')) $('#recentInvite').innerHTML = inviteMarkup(rows);
  applySearch();
}

function applySearch() {
  const input = $('#documentSearch');
  if (!input) return;
  const query = input.value.toLowerCase().trim();
  const rows = $$('#documentsTable .document-row');
  rows.forEach(row => { row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query); });
  let empty = $('#searchEmpty');
  if (rows.length && rows.every(row => row.hidden)) {
    if (!empty) {
      empty = document.createElement('p');
      empty.id = 'searchEmpty';
      empty.className = 'empty-state';
      empty.textContent = 'No documents match your search.';
      $('#documentsTable').appendChild(empty);
    }
  } else {
    empty?.remove();
  }
}

function showDocument(id, serial) {
  if (!UUID.test(id)) {
    $('#main').innerHTML = messageView('This document is not available.', 'The address does not name a document in this workspace.');
    return undefined;
  }
  $('#main').innerHTML = state.ack?.id === id ? ackView(state.ack) : '<section class="view-entrance"><p class="empty-state">Loading the review…</p></section>';
  return loadDocument(id, serial, false);
}

function setReconnecting(on) {
  state.reconnecting = on;
  const line = $('.progress-reconnecting');
  if (line) line.hidden = !(on && shouldPoll(state.doc));
}

async function loadDocument(id, serial, silent) {
  clearTimeout(state.poll.timer);
  let doc;
  try {
    doc = await api(`/api/encounters/${encodeURIComponent(id)}`);
  } catch (error) {
    if (serial !== state.routeSerial || state.outdated) return;
    if (silent && state.doc) {
      if (shouldPoll(state.doc)) {
        state.poll.errors += 1;
        setReconnecting(true);
        schedulePoll(serial);
      } else {
        toast(`The review could not be refreshed. ${error.message}`);
      }
      return;
    }
    $('#main').innerHTML = error.status === 404
      ? messageView('This document is not available.', 'It does not exist, or it is not in your workspace.')
      : messageView('The review could not be loaded.', error.message, true);
    return;
  }
  if (serial !== state.routeSerial) return;
  state.poll.errors = 0;
  state.reconnecting = false;
  state.clock = clockOffset(doc.progress?.server_time, Date.now());
  if (state.ack?.id === doc.id && !isBusy(doc)) state.ack = null;
  renderDocument(doc, !silent);
  schedulePoll(serial);
}

function schedulePoll(serial) {
  clearTimeout(state.poll.timer);
  if (!shouldPoll(state.doc) || state.outdated) {
    state.poll.count = 0;
    return;
  }
  const delay = pollDelay(state.poll.count, state.poll.errors);
  state.poll.count += 1;
  const id = state.doc.id;
  state.poll.timer = setTimeout(() => loadDocument(id, serial, true), delay);
}

async function refreshDocument() {
  if (state.route?.name !== 'doc') return;
  state.poll.count = 0;
  state.poll.errors = 0;
  await loadDocument(state.route.id, state.routeSerial, true);
}

function refreshIfWaiting() {
  if (state.route?.name === 'doc' && shouldPoll(state.doc) && !document.hidden) refreshDocument();
}

// Where the focus was, so a redraw can put it back: the element's id, the code row it sits in, and the caret of an
// answer being typed.
function focusTarget() {
  const element = document.activeElement;
  if (!element || !$('#main').contains(element)) return null;
  const target = { id: element.id || '', code: element.closest?.('.code-row')?.dataset.code || '' };
  if (element.tagName === 'TEXTAREA' && typeof element.selectionStart === 'number') target.selection = [element.selectionStart, element.selectionEnd];
  return target.id || target.code ? target : null;
}

function restoreFocus(target) {
  if (!target) return;
  let element = target.id ? document.getElementById(target.id) : null;
  if (!element && target.code) element = document.getElementById(`code-${rowKey(target.code)}`);
  if (!element) return;
  element.focus({ preventScroll: true });
  if (target.selection && element.tagName === 'TEXTAREA') {
    try {
      element.setSelectionRange(target.selection[0], target.selection[1]);
    } catch {
      // the field is no longer the one the caret was in
    }
  }
}

// What decides whether a read of the document redraws the page: everything served but the server's clock, which moves
// on every read and changes nothing drawn (the elapsed time follows state.clock).
function renderKey(doc) {
  const progress = doc && typeof doc === 'object' ? doc.progress : null;
  if (!progress || typeof progress !== 'object' || Array.isArray(progress)) return JSON.stringify(doc);
  return JSON.stringify({ ...doc, progress: { ...progress, server_time: null } });
}

// What the viewer shows: the page redraws it only when this changes, so a poll never reloads the original.
function viewerKey(doc) {
  const part = record(doc?.document);
  return `${doc?.id || ''} ${viewerKind(part)} ${part.converted === true} ${safeViewUrl(part.view_url)} ${safeOriginalUrl(part.original_url)} ${documentName(part)}`;
}

function renderDocument(doc, fresh, force = false) {
  const key = renderKey(doc);
  if (!fresh && !force && key === state.docKey) {
    state.doc = doc;  // the same page: only the server's clock moved
    return;
  }
  const keep = fresh ? null : { window: window.scrollY, focus: focusTarget() };
  const frame = viewerKey(doc);
  const partial = !fresh && frame === state.viewerKey && $('#reviewHead') && $('#reviewColumn') && $('#quotesBox');
  state.doc = doc;
  state.docKey = key;
  const ui = uiState({ entrance: fresh });
  if (partial) {
    $('#reviewHead').innerHTML = reviewHeading(doc);
    $('#quotesBox').innerHTML = quotesPanel(doc);
    $('#reviewColumn').innerHTML = reviewColumn(doc, ui);
  } else {
    state.viewerKey = frame;
    state.selectedQuote = '';
    $('#main').innerHTML = reviewView(doc, ui);
  }
  if (keep) {
    window.scrollTo({ top: keep.window, behavior: 'instant' });
    restoreFocus(keep.focus);
  }
  markSelectedQuote();
  tick();
}

// Elapsed time on the page: one timer that rewrites only the [data-elapsed] text, while the document is busy.
function tick() {
  stopTicker();
  if (state.route?.name !== 'doc' || !isBusy(state.doc)) return;
  const nodes = $$('[data-elapsed][data-since]:not([data-until])');
  if (!nodes.length) return;
  const now = Date.now() + state.clock;
  for (const node of nodes) node.textContent = elapsedText(node.dataset.since, now);
  state.tickTimer = setTimeout(tick, TICK_MS);
}

// --- quoted passages: open the page, or find the passage in a text document ---

function findQuote(key) {
  for (const code of codesOf(state.doc)) {
    const quotes = quotesOf(code);
    for (let index = 0; index < quotes.length; index += 1) if (quoteKey(code, index) === key) return { code, quote: quotes[index] };
  }
  return null;
}

function markSelectedQuote() {
  $$('[data-quote]').forEach(element => {
    const selected = Boolean(state.selectedQuote) && element.dataset.quote === state.selectedQuote;
    element.classList.toggle('selected', selected);
    if (selected) element.setAttribute('aria-current', 'true');
    else element.removeAttribute('aria-current');
  });
}

// Selects the passage inside the viewer of a text document and scrolls it into view. Best effort: a viewer this page
// cannot read (another origin, a PDF, not loaded yet) is left as it is.
function revealInFrame(frame, passage) {
  try {
    const view = frame.contentWindow;
    const page = frame.contentDocument;
    if (!view || !page?.body) return false;
    const walker = page.createTreeWalker(page.body, 4);
    const nodes = [];
    let source = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      nodes.push([node, source.length]);
      source += node.nodeValue;
    }
    const found = findPassage(source, passage);
    if (!found) return false;
    const place = offset => {
      let index = nodes.length - 1;
      while (index > 0 && nodes[index][1] > offset) index -= 1;
      return [nodes[index][0], offset - nodes[index][1]];
    };
    const range = page.createRange();
    range.setStart(...place(found[0]));
    range.setEnd(...place(found[1]));
    const selection = view.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    const box = range.getBoundingClientRect();
    view.scrollBy(0, box.top - view.innerHeight / 3);
    return true;
  } catch {
    return false;
  }
}

// The PDF viewer opens the quoted page (#page=N); the text viewer finds the passage, since a text has no pages.
function showQuote(key) {
  const found = findQuote(key);
  if (!found) return;
  state.selectedQuote = key;
  markSelectedQuote();
  const frame = $('#documentViewer');
  if (!frame) return;
  if (found.quote.page && viewerKind(state.doc?.document) === 'pdf') {
    const url = viewerUrl(state.doc?.document?.view_url, found.quote.page);
    if (url) frame.src = url;
  } else {
    revealInFrame(frame, found.quote.text);
  }
  frame.scrollIntoView({ behavior: reducedMotion() ? 'instant' : 'smooth', block: 'nearest' });
}

// --- decisions ---

function findCode(value) {
  return codesOf(state.doc).find(code => code.code === value) || null;
}

function reviewCopyText(action, agent) {
  if (action === 'reject') return 'A rejected code is left out of the approved download. Add a note so the next reviewer knows why.';
  return agent
    ? 'This approval is recorded as an agent-executed synthetic review, with the agent\'s name and the time. It applies to these codes only; a new coding review starts without it.'
    : 'Your approval is recorded with your name and the time. It applies to these codes only; a new coding review starts without it.';
}

async function openReview(value, action) {
  const code = findCode(value);
  if (!code || !REVIEW_COPY[action] || !allowedActions(code, state.doc).includes(action)) return;
  if (!state.session && !(await loadSession())) {
    toast('Your identity could not be confirmed, so no decision can be recorded. Reload the page and try again.');
    return;
  }
  const acknowledgement = typeof state.session?.acknowledgement === 'string' ? state.session.acknowledgement : '';
  if (action === 'approve' && !acknowledgement.trim()) {
    toast('The approval statement could not be loaded, so no approval can be recorded. Reload the page and try again.');
    return;
  }
  const copy = REVIEW_COPY[action];
  state.review = { code: code.code, action };
  $('#reviewEyebrow').textContent = copy.eyebrow;
  $('#reviewTitle').textContent = copy.title;
  $('#reviewCopy').textContent = reviewCopyText(action, isAgent());
  $('#reviewCode').textContent = code.code;
  $('#reviewStatus').textContent = codeStatus(code).label;
  $('#reviewSummary').textContent = text(code.reason);
  $('#reviewAcknowledgement').hidden = action !== 'approve';
  $('#reviewAckBox').checked = false;
  $('#reviewAckText').textContent = action === 'approve' ? acknowledgement : '';
  $('#reviewNote').value = '';
  $('#reviewNotice').textContent = 'A review decision records a judgement; it is not billing advice.';
  $('#saveReviewLabel').textContent = copy.button;
  $('#saveReview').disabled = action === 'approve';
  hideError('reviewError');
  openDialog('reviewDialog');
}

async function guarded(key, task) {
  if (state.pending.has(key)) return;
  state.pending.add(key);
  try {
    await task();
  } finally {
    state.pending.delete(key);
  }
}

function postDecision(body) {
  return api(`/api/encounters/${encodeURIComponent(state.doc.id)}/decisions`, { method: 'POST', json: body });
}

async function afterChange(message) {
  toast(message);
  loadSession();
  await refreshDocument();
}

function submitReview(event) {
  event.preventDefault();
  const review = state.review;
  if (!review || !state.doc) return undefined;
  const approve = review.action === 'approve';
  if (approve && !$('#reviewAckBox').checked) {
    showError('reviewError', 'Confirm the statement above to approve this code.');
    return undefined;
  }
  return guarded('review', async () => {
    const button = $('#saveReview');
    setBusy(button, true);
    hideError('reviewError');
    const body = decisionBody(review.code, review.action, approve ? state.session?.acknowledgement : '', $('#reviewNote').value);
    try {
      await postDecision(body);
      closeDialog('reviewDialog');
      await afterChange(approve ? `Approval recorded for ${review.code}.` : `Rejection recorded for ${review.code}.`);
    } catch (error) {
      showError('reviewError', error.message);
    } finally {
      setBusy(button, approve && !$('#reviewAckBox').checked);
    }
  });
}

function revokeDecision(value, button) {
  return guarded(`revoke:${value}`, async () => {
    setBusy(button, true);
    try {
      await postDecision(decisionBody(value, 'revoke'));
      await afterChange(`Decision undone for ${value}.`);
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function handleDecision(action, value, button) {
  const code = findCode(value);
  if (!code || !allowedActions(code, state.doc).includes(action)) return undefined;
  if (action === 'revoke') return revokeDecision(code.code, button);
  return openReview(code.code, action);
}

// --- answers: typed on the page, sent together ---

function sendAnswers(button) {
  if (!state.doc) return undefined;
  const payload = answersPayload(state.doc, state.answers);
  if (typeof payload === 'string') {
    showError('answersError', payload);
    return undefined;
  }
  return guarded('answers', async () => {
    setBusy(button, true);
    hideError('answersError');
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/answers`, { method: 'POST', json: payload });
      for (const item of payload.answers) state.answers.delete(item.question_id);
      await afterChange(payload.answers.length === 1 ? 'Answer sent. A new coding review has started.' : `${payload.answers.length} answers sent. A new coding review has started.`);
    } catch (error) {
      showError('answersError', error.message);
      setBusy(button, false);
    }
  });
}

// --- upload ---

function randomBytes(count) {
  return crypto.getRandomValues(new Uint8Array(count));
}

// Any change to what is being uploaded makes it a new attempt with a new key; a retry of the same attempt keeps it.
function forgetAttemptKey() {
  state.upload.key = '';
}

function resetUpload() {
  state.upload = { file: null, paste: false, busy: false, key: '' };
  $('#uploadForm').reset();
  setUploadFile(null);
  setPasteMode(false);
  hideError('uploadError');
  setUploadStatus('');
}

function openUpload(file) {
  if (state.upload.busy) return openDialog('uploadDialog');
  resetUpload();
  if (file) setUploadFile(file);
  return openDialog('uploadDialog');
}

function setUploadStatus(message) {
  const element = $('#uploadStatus');
  element.textContent = message;
  element.hidden = !message;
}

function setUploadFile(file) {
  hideError('uploadError');
  forgetAttemptKey();
  let accepted = file || null;
  if (accepted && !UPLOAD_NAME.test(accepted.name)) {
    showError('uploadError', 'Choose a PDF, DOCX or TXT file.');
    accepted = null;
  } else if (accepted && accepted.size > MAX_UPLOAD_BYTES) {
    showError('uploadError', 'This file is larger than 15 MB. Choose a smaller file.');
    accepted = null;
  } else if (accepted && accepted.size === 0) {
    showError('uploadError', 'This file is empty. Choose a document with content.');
    accepted = null;
  }
  state.upload.file = accepted;
  $('#selectedFile').hidden = !accepted;
  $('#selectedFileName').textContent = accepted ? `${accepted.name} · ${formatSize(accepted.size)}` : '';
  if (!accepted) $('#uploadFile').value = '';
}

function setPasteMode(paste) {
  state.upload.paste = paste;
  forgetAttemptKey();
  $('#fileFields').hidden = paste;
  $('#pasteField').hidden = !paste;
  $('#pasteToggle').textContent = paste ? 'Upload a file instead' : 'Paste text instead';
  $('#pasteToggle').setAttribute('aria-expanded', String(paste));
  hideError('uploadError');
}

async function submitUpload(event) {
  event.preventDefault();
  if (state.upload.busy) return;
  if (!state.upload.key) state.upload.key = newClientKey(randomBytes);
  const form = uploadForm({ paste: state.upload.paste, text: $('#pasteText').value, file: state.upload.file, serviceDate: $('#serviceDate').value, insurance: $('#insurance').value, attested: $('#syntheticAttestation').checked }, state.upload.key);
  if (typeof form === 'string') {
    showError('uploadError', form);
    return;
  }
  const button = $('#startReview');
  state.upload.busy = true;
  setBusy(button, true);
  hideError('uploadError');
  setUploadStatus('Uploading your document… Keep this page open until the upload finishes.');
  try {
    const created = await api('/api/encounters', { method: 'POST', form });
    if (!UUID.test(String(created.id || ''))) throw new ApiError('The server did not confirm the upload. Try again; the same upload is never added twice.');
    state.upload.busy = false;
    state.ack = { id: created.id, at: Date.now() };
    closeDialog('uploadDialog');
    loadSession();
    if (location.hash === `#doc/${created.id}`) route();
    else location.hash = `doc/${created.id}`;
  } catch (error) {
    setUploadStatus('');
    showError('uploadError', error.message);
  } finally {
    state.upload.busy = false;
    setBusy(button, false);
  }
}

// --- stop, resume, retry, export ---

function progressAction(action, button) {
  const entry = PROGRESS_ACTIONS.find(([name]) => name === action);
  if (!state.doc || !entry) return undefined;
  const [, , address, , , , done] = entry;
  return guarded(action, async () => {
    setBusy(button, true);
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/${address}`, { method: 'POST', json: {} });
      await afterChange(done);
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function openExport() {
  if (!state.doc) return;
  const readiness = record(state.doc.readiness);
  $('#exportStatus').classList.toggle('reviewed', readiness.approved === true);
  $('#exportStatus').textContent = exportStatusText(state.doc);
  $('#exportOptions').innerHTML = exportOptions(state.doc);
  hideError('exportError');
  openDialog('exportDialog');
}

function startDownload(url, filename) {
  const link = document.createElement('a');
  link.href = url;
  link.download = typeof filename === 'string' ? filename : '';
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function generateReport(kind, fmt) {
  if (!state.doc) return undefined;
  return guarded('export', async () => {
    const options = $$('#exportOptions .export-option');
    const enabled = options.filter(option => !option.disabled);
    enabled.forEach(option => setBusy(option, true));
    hideError('exportError');
    try {
      const report = await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/reports`, { method: 'POST', json: { kind, fmt } });
      const url = safeDownloadUrl(report.download_url);
      if (!url) throw new ApiError('The download could not be started. Try again.');
      startDownload(url, report.filename);
      $('#exportStatus').textContent = `${exportStatusText(state.doc)} Downloading ${text(report.filename) || 'the file'}.`;
      refreshDocument();
    } catch (error) {
      const blockers = strings(error.details?.blockers);
      showError('exportError', blockers.length ? `${error.message} ${blockers.join(' ')}` : error.message);
    } finally {
      enabled.forEach(option => setBusy(option, false));
    }
  });
}

function hasFiles(event) {
  return [...(event.dataTransfer?.types || [])].includes('Files');
}

function setDragTarget(zone) {
  $$('.drop-zone.dragover').forEach(element => { if (element !== zone) element.classList.remove('dragover'); });
  zone?.classList.add('dragover');
}

function onClick(event) {
  const target = event.target;
  if (target.closest('.skip-link')) {
    event.preventDefault();
    $('#main').focus();
    return;
  }
  const close = target.closest('[data-close]');
  if (close) {
    const dialog = close.closest('dialog');
    if (!(dialog.id === 'uploadDialog' && state.upload.busy)) dialog.close();
    return;
  }
  const open = target.closest('[data-open]');
  if (open) {
    location.hash = `doc/${open.dataset.open}`;
    return;
  }
  const quote = target.closest('[data-quote]');
  if (quote) {
    showQuote(quote.dataset.quote);
    return;
  }
  const decision = target.closest('[data-decision]');
  if (decision) {
    handleDecision(decision.dataset.decision, decision.dataset.code, decision);
    return;
  }
  const report = target.closest('[data-export-kind]');
  if (report) {
    generateReport(report.dataset.exportKind, report.dataset.exportFmt);
    return;
  }
  const action = target.closest('[data-action]');
  if (!action) return;
  ({
    upload: () => openUpload(),
    about: () => openDialog('aboutDialog'),
    export: openExport,
    'send-answers': () => sendAnswers(action),
    stop: () => progressAction('stop', action),
    resume: () => progressAction('resume', action),
    retry: () => progressAction('retry', action),
    reload: () => location.reload(),
    'reload-view': route,
  })[action.dataset.action]?.();
}

function onInput(event) {
  const input = event.target;
  if (input.id === 'documentSearch') applySearch();
  else if (input.matches?.('textarea[data-answer]')) {
    state.answers.set(input.dataset.answer, input.value);
    hideError('answersError');
  } else if (['pasteText', 'serviceDate', 'insurance'].includes(input.id)) forgetAttemptKey();
}

// The open History disclosure survives a refresh of the page's data.
function onToggle(event) {
  const element = event.target;
  if (!(element instanceof HTMLDetailsElement) || !element.dataset.key) return;
  if (element.open) state.open.add(element.dataset.key);
  else state.open.delete(element.dataset.key);
}

function onKeydown(event) {
  if (event.key === 'Escape') closeNavigation();
}

function bindDialogs() {
  $('#uploadForm').addEventListener('submit', submitUpload);
  $('#reviewForm').addEventListener('submit', submitReview);
  $('#uploadFile').addEventListener('change', event => setUploadFile(event.target.files?.[0]));
  $('#insurance').addEventListener('change', forgetAttemptKey);
  $('#clearFile').addEventListener('click', () => setUploadFile(null));
  $('#pasteToggle').addEventListener('click', () => {
    setPasteMode(!state.upload.paste);
    (state.upload.paste ? $('#pasteText') : $('#uploadFile')).focus();
  });
  $('#reviewAckBox').addEventListener('change', event => { $('#saveReview').disabled = !event.target.checked; });
  $('#uploadDialog').addEventListener('cancel', event => { if (state.upload.busy) event.preventDefault(); });
}

function bindDragAndDrop() {
  document.addEventListener('dragover', event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    setDragTarget(event.target.closest?.('.drop-zone') || null);
  });
  document.addEventListener('dragleave', event => {
    if (event.target.closest?.('.drop-zone') && !event.target.closest('.drop-zone').contains(event.relatedTarget)) setDragTarget(null);
  });
  document.addEventListener('drop', event => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    const zone = event.target.closest?.('.drop-zone');
    setDragTarget(null);
    const file = event.dataTransfer.files?.[0];
    if (!zone || !file) return;
    if (zone.id === 'dialogDrop') setUploadFile(file);
    else if (zone.id === 'overviewDrop') openUpload(file);
  });
}

function boot() {
  document.addEventListener('click', onClick);
  document.addEventListener('input', onInput);
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('toggle', onToggle, true);
  bindDialogs();
  bindDragAndDrop();
  $('#menuButton').addEventListener('click', () => {
    const open = !$('#sidebar').classList.contains('open');
    $('#sidebar').classList.toggle('open', open);
    $('#sidebarBackdrop').hidden = !open;
    $('#menuButton').setAttribute('aria-expanded', String(open));
    $('#sidebar').inert = !open && window.matchMedia('(max-width:760px)').matches;
    if (open) $('.brand').focus();
  });
  $('#sidebarBackdrop').addEventListener('click', closeNavigation);
  window.addEventListener('hashchange', route);
  window.addEventListener('online', () => refreshIfWaiting());
  window.addEventListener('offline', () => { if (shouldPoll(state.doc)) setReconnecting(true); });
  document.addEventListener('visibilitychange', refreshIfWaiting);
  window.matchMedia('(max-width:760px)').addEventListener('change', closeNavigation);
  loadSession().then(route);
}

if (typeof module === 'object' && module.exports) {
  module.exports = {
    escapeHtml, lookup, parseIsoDate, formatDate, formatTimestamp, readCookie, safeDownloadUrl, safeOriginalUrl, safeViewUrl,
    pollDelay, parseRoute, isClientOutdated, errorText, newClientKey, durationText, clockOffset, elapsedText, findPassage,
    canReview, stateLabel, codesOf, questionsOf, answersOf, notesOf, progressPhase, isBusy, shouldPoll, codeStatus,
    currentDecision, shownStatus, unitsLabel, modifiersLabel, secondCheck, quotesOf, quoteKey, viewerUrl, viewerKind,
    allowedActions, decisionBody, answersPayload, insuranceLabel, insuranceText, tallyText, readinessText, exportStatusText,
    emptyCodesText, documentRow, inQueue, listBody, listDescription, inviteMarkup, overviewView, documentsView, howItWorksView,
    messageView, uploadAck, ackView, reviewMeta, reviewHeading, viewerPanel, quotesPanel, progressSteps, progressPanel,
    questionsPanel, answersPanel, codeRow, codesSection, notesPanel, activityLog, reviewColumn, reviewView, reportItem,
    exportOptions, uploadForm, renderKey, viewerKey, api, sendAnswers, submitReview, handleDecision, progressAction, onClick,
    onInput, showQuote, state, STATE_LABELS, CODE_STATUSES, DECISIONS, ACTION_BUTTONS, PHASES, PHASE_TITLES, STEP_KEYS,
    STEP_LABELS, PROGRESS_ACTIONS, INSURANCE_CHOICES, QUEUE_STATES, OUTDATED_TEXT, CLIENT_HEADER, CLIENT_VERSION,
    MAX_ANSWER_CHARS, CONVERTED_NOTE, REVIEW_AGAIN,
  };
}
if (typeof document !== 'undefined') boot();
