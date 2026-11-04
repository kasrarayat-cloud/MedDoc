'use strict';
// CPT Studio customer page, drawn from the customer encounter contract (API.md, "Core repair and customer
// interface"). Rendering builds markup strings; every value that comes from the server passes through escapeHtml.
// Everything above "browser wiring" is pure and unit-tested under node (tests/frontend/app.test.cjs).

const POLL_BASE_MS = 2500;
const POLL_MAX_MS = 15000;
const POLL_MAX_ERROR_MS = 30000;
const TICK_MS = 1000;
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;
const MAX_PASTE_CHARS = 400000;
const MAX_ADDENDUM_CHARS = 20000;
const UPLOAD_NAME = /\.(pdf|docx|txt)$/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REPORT_URL = /^\/api\/reports\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/download$/i;
const ORIGINAL_URL = /^\/api\/encounters\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/original$/i;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const PARAGRAPH_BREAK = /\n(?:[^\S\n]*\n)+/g;
// The page tells the server which build of this page is asking. A server that no longer serves this build answers
// HTTP 409 with {"error_code": "client_outdated"}, and the page asks the member to reload (updateNotice).
const CLIENT_HEADER = 'X-CPT-Studio-Client';
const CLIENT_VERSION = 'customer-2026-11-03';
const OUTDATED_TEXT = 'CPT Studio was updated — reload the page to continue.';
const OFFLINE_TEXT = 'The server could not be reached. Check the connection and try again.';
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#x60;' };

const AGENT_REVIEW = 'Agent-executed synthetic review — not clinical approval';
const STATE_LABELS = {
  processing: 'Processing', action_needed: 'Action needed', awaiting_detail: 'A few details needed', ready: 'Ready for review',
  reviewed: 'Reviewed', no_codes: 'No codes suggested', stopped: 'Stopped', failed: 'Could not finish', being_confirmed: 'Being confirmed',
};
const STATE_TONES = { ready: 'green', reviewed: 'green', action_needed: 'amber', awaiting_detail: 'amber', being_confirmed: 'amber', failed: 'amber' };
// The review queue: documents that wait on a member (a date to choose, a detail to answer, codes to review).
const QUEUE_STATES = new Set(['action_needed', 'awaiting_detail', 'ready']);
// status -> [label, badge tone, badge icon]
const CODE_STATUSES = {
  ready: ['Ready for review', 'green', ''],
  needs_detail: ['Needs a detail', 'amber', 'info'],
  approved: ['Approved', 'green', 'check'],
  excluded: ['Excluded', 'gray', ''],
};
const STEP_KEYS = ['reading', 'identifying', 'checking', 'preparing'];
const STEP_LABELS = { reading: 'Reading your document', identifying: 'Identifying procedures', checking: 'Checking suggested codes', preparing: 'Preparing your results' };
const STEP_STATES = { done: 'Done', active: 'In progress', waiting: 'Waiting to start', not_started: 'Not started', failed: 'Did not finish', stopped: 'Stopped', skipped: 'Not needed' };
const STEP_ICONS = { done: 'check', active: 'clock', failed: 'close', stopped: 'stop' };
const CHECK_KEYS = ['document_review', 'independent_checks', 'coding_validation'];
const CHECK_LABELS = { document_review: 'Document review', independent_checks: 'Independent checks', coding_validation: 'Coding validation' };
const CHECK_STATES = { done: 'Done', running: 'In progress', waiting: 'Waiting', unavailable: 'Unavailable', not_run: 'Not run' };
const CHECK_ICONS = { done: 'circle-check', running: 'clock', waiting: 'clock', unavailable: 'info', not_run: 'info' };
const PHASES = ['uploading', 'queued', 'processing', 'action_needed', 'awaiting_detail', 'completed', 'partial', 'failed', 'stopped', 'being_confirmed'];
const PHASE_TITLES = {
  uploading: 'Uploading your document', queued: 'Waiting to start', processing: 'Processing your document', action_needed: 'Action needed',
  awaiting_detail: 'Results ready', completed: 'Results ready', partial: 'Results ready, with a limitation', failed: 'Processing could not finish',
  stopped: 'Processing stopped', being_confirmed: 'An earlier check is being confirmed',
};
// Only these phases draw an animated step, and only while the server says the document is busy.
const ANIMATED_PHASES = new Set(['uploading', 'queued', 'processing']);
// These phases draw the whole progress panel; the others (results are ready) draw one compact line.
const PANEL_PHASES = new Set(['uploading', 'queued', 'processing', 'action_needed', 'failed', 'stopped', 'being_confirmed']);
// The page polls the document while it is busy, and while an earlier check is being confirmed.
const POLL_PHASES = new Set(['queued', 'processing', 'being_confirmed']);
const STATE_PHASES = { processing: 'processing', action_needed: 'action_needed', awaiting_detail: 'awaiting_detail', failed: 'failed', stopped: 'stopped', being_confirmed: 'being_confirmed' };
const LEAVE_NOTES = {
  uploading: 'Keep this page open until the upload finishes.',
  queued: 'You can leave this page — processing continues, and the document stays in Documents.',
  processing: 'You can leave this page — processing continues, and the document stays in Documents.',
  action_needed: 'You can leave this page — the document waits in the Review queue until you choose.',
  being_confirmed: 'You can leave this page — the document stays in Documents while this is settled.',
};
const DETAIL_ANSWERS = { not_documented: 'Not documented', cannot_confirm: 'Cannot confirm' };
const USE_DOCUMENT = 'use_document';
const KIND_LABELS = { upload: 'Uploaded file', paste: 'Pasted text', addendum: 'Document with addendum' };
const ERROR_ACTIONS = { resume: ['resume', 'Resume processing'], new_document: ['upload', 'Upload a new document'] };
const ACKNOWLEDGEMENTS = {
  human: 'I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This synthetic review is not clinical approval or billing advice.',
  agent: 'I am an automated agent. I read the whole source document, not only the cited passages, and it supports this code as a service performed at this encounter. The documentation checks can miss wording they do not recognise. This agent-executed synthetic review is not clinical approval or billing advice.',
};
const ACTION_BUTTONS = [['approve', 'primary', 'Approve', 'check'], ['reject', 'secondary', 'Reject', ''], ['reinstate', 'secondary', 'Reinstate for review', ''], ['confirm', 'secondary', 'Confirm exclusion', ''], ['revoke', 'secondary', 'Undo decision', '']];
const DECISION_TITLES = { approve: 'Approved', reject: 'Rejected', reinstate: 'Reinstated for review', confirm: 'Exclusion confirmed' };
const REVIEW_COPY = {
  approve: { eyebrow: 'APPROVE', title: 'Make the decision visible.', button: 'Approve code' },
  reject: { eyebrow: 'REJECT', title: 'Leave a clear record.', button: 'Reject code' },
  reinstate: { eyebrow: 'REINSTATE', title: 'Bring it back for review.', button: 'Reinstate for review' },
  confirm: { eyebrow: 'CONFIRM EXCLUSION', title: 'Agree with the exclusion, on the record.', button: 'Confirm exclusion' },
};
const MODIFIER_CHOICES = ['59', 'XS'];
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

function pollDelay(count, errors) {
  if (errors > 0) return Math.min(POLL_MAX_ERROR_MS, POLL_BASE_MS * 2 ** errors);
  return Math.min(POLL_MAX_MS, Math.round(POLL_BASE_MS * 1.25 ** count));
}

function parseRoute(hash) {
  const path = String(hash || '').replace(/^#/, '');
  if (path.startsWith('doc/')) return { name: 'doc', id: path.slice(4) };
  return { name: lookup(ROUTE_TITLES, path, null) && path !== 'doc' ? path : 'workspace' };
}

// HTTP 409 {"error_code": "client_outdated"}: this build of the page is no longer served.
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

// API offsets are Python code points; JavaScript strings index UTF-16 units.
// Returns null when the two coincide (no surrogates), else point -> unit offsets.
function codeUnitOffsets(source) {
  if (!/[\uD800-\uDFFF]/.test(source)) return null;
  const offsets = [0];
  let unit = 0;
  for (const ch of source) {
    unit += ch.length;
    offsets.push(unit);
  }
  return offsets;
}

function isExactSpan(source, span, length, unit) {
  return Boolean(span) && span.exact !== false && Number.isInteger(span.start) && Number.isInteger(span.end)
    && span.start >= 0 && span.start < span.end && span.end <= length && typeof span.text === 'string'
    && source.slice(unit(span.start), unit(span.end)) === span.text;
}

// Overlapping spans become one mark carrying every key; touching spans stay separate.
function mergeSpans(spans) {
  const sorted = [...spans].sort((a, b) => a.start - b.start || a.end - b.end || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  const merged = [];
  for (const span of sorted) {
    const last = merged[merged.length - 1];
    if (last && span.start < last.end) {
      last.end = Math.max(last.end, span.end);
      if (!last.keys.includes(span.key)) last.keys.push(span.key);
    } else {
      merged.push({ start: span.start, end: span.end, keys: [span.key] });
    }
  }
  return merged;
}

// Page k runs from its recorded start to the next page's start (the last to the end
// of the text), so separators and any unpaged text are never dropped.
function pageRanges(pages, length, unit, unitLength) {
  const valid = Array.isArray(pages) && pages.length > 0 && pages.every((page, i) => page
    && Number.isInteger(page.page) && Number.isInteger(page.start) && Number.isInteger(page.end)
    && page.start >= 0 && page.start <= page.end && page.end <= length && (i === 0 || page.start >= pages[i - 1].end));
  if (!valid) return [{ page: 1, start: 0, end: unitLength }];
  return pages.map((page, i) => ({
    page: page.page,
    start: i === 0 ? 0 : unit(page.start),
    end: i === pages.length - 1 ? unitLength : unit(pages[i + 1].start),
  }));
}

function paragraphRanges(source, start, end) {
  const part = source.slice(start, end);
  const ranges = [];
  const add = (from, to) => {
    while (from < to && part[from] === '\n') from += 1;
    while (to > from && part[to - 1] === '\n') to -= 1;
    if (part.slice(from, to).trim()) ranges.push([start + from, start + to]);
  };
  let cursor = 0;
  for (const match of part.matchAll(PARAGRAPH_BREAK)) {
    add(cursor, match.index);
    cursor = match.index + match[0].length;
  }
  add(cursor, part.length);
  return ranges;
}

function paragraphPieces(source, start, end, marks) {
  const pieces = [];
  let cursor = start;
  for (const mark of marks) {
    if (mark.end <= start || mark.start >= end) continue;
    const from = Math.max(mark.start, start);
    const to = Math.min(mark.end, end);
    if (from > cursor) pieces.push({ text: source.slice(cursor, from), keys: null });
    pieces.push({ text: source.slice(from, to), keys: mark.keys });
    cursor = to;
  }
  if (cursor < end) pieces.push({ text: source.slice(cursor, end), keys: null });
  return pieces;
}

// spans: [{key, start, end, text, exact}] in code points. A span is marked only when
// text[start:end] equals its text; anything else is reported as unlocated.
function layoutDocument(source, pages, spans) {
  const body = String(source || '');
  const offsets = codeUnitOffsets(body);
  const length = offsets ? offsets.length - 1 : body.length;
  const unit = point => (offsets ? offsets[point] : point);
  const located = [];
  const unlocated = [];
  for (const span of spans) {
    if (isExactSpan(body, span, length, unit)) located.push({ key: span.key, start: unit(span.start), end: unit(span.end) });
    else unlocated.push(span.key);
  }
  const marks = mergeSpans(located);
  return {
    pages: pageRanges(pages, length, unit, body.length).map(page => ({
      page: page.page,
      paragraphs: paragraphRanges(body, page.start, page.end).map(([from, to]) => paragraphPieces(body, from, to, marks)),
    })),
    unlocated,
  };
}

function excerpt(value, limit = 80) {
  const flat = String(value ?? '').split(/\s+/).filter(Boolean).join(' ');
  const points = [...flat];
  return points.length <= limit ? flat : `${points.slice(0, limit - 1).join('').trimEnd()}…`;
}

// --- the customer contract, read defensively ---------------------------------------

function codesOf(doc) {
  return objects(doc?.codes);
}

function detailsOf(doc) {
  return objects(doc?.details_needed);
}

function openDetails(doc) {
  return detailsOf(doc).filter(row => !row.saved);
}

function canReview(doc) {
  return doc?.permissions?.can_review === true;
}

function stateLabel(stateName, label) {
  return lookup(STATE_LABELS, stateName, text(label) || 'Unknown');
}

// The phase the progress panel shows: the upload in flight (client only), else the server's, else read from the state.
function progressPhase(doc, ui = {}) {
  if (ui.uploading) return 'uploading';
  const phase = doc?.progress?.phase;
  if (PHASES.includes(phase)) return phase;
  return lookup(STATE_PHASES, doc?.state, 'completed');
}

function shouldPoll(doc) {
  const progress = doc?.progress;
  return Boolean(progress) && (progress.busy === true || POLL_PHASES.has(progress.phase));
}

// One code's status as the list shows it: the contract's four statuses, each with its own fixed label.
function codeStatus(code) {
  const key = typeof code?.status === 'string' ? code.status : '';
  const known = lookup(CODE_STATUSES, key, null);
  if (known) return { key, label: known[0], tone: known[1], icon: known[2] };
  return { key: key || 'unknown', label: text(code?.status_label) || 'Not reviewable', tone: 'gray', icon: '' };
}

function isAgentDecision(code) {
  return code?.decision?.by_kind === 'agent';
}

// The line under a code: an agent approval always says it is an agent-executed synthetic review, whatever else the
// server sends; a rejection says so when the server sends nothing.
function rowSubLabel(code) {
  if (codeStatus(code).key === 'approved' && isAgentDecision(code)) return AGENT_REVIEW;
  const served = text(code?.sub_label);
  if (served) return served;
  return code?.decision?.action === 'reject' ? 'Rejected in review' : '';
}

function unitsLabel(units) {
  return Number.isInteger(units) && units > 0 ? plural(units, 'unit', 'units') : '';
}

function modifierLabel(code) {
  const chosen = strings(code?.modifiers);
  if (chosen.length) return `Modifier ${chosen.join(', ')}`;
  if (!code?.modifier_review) return '';
  return codeStatus(code).key === 'approved' ? 'No modifier' : 'Modifier review';
}

// The modifier choices of one approval: none, 59 or XS - never both, never prefilled, never a free list.
function reviewModifierOptions(code) {
  const review = code?.modifier_review;
  if (!review || typeof review !== 'object') return [];
  const offered = MODIFIER_CHOICES.filter(choice => list(review.options).includes(choice));
  return offered.length ? [['', 'No modifier'], ...offered.map(choice => [choice, choice])] : [];
}

function hasAgentDecision(doc) {
  return codesOf(doc).some(code => code.decision && isAgentDecision(code));
}

function attestationText(session) {
  return session?.acknowledgement || (session?.user?.actor_kind === 'agent' ? ACKNOWLEDGEMENTS.agent : ACKNOWLEDGEMENTS.human);
}

function tallyText(doc) {
  const counts = { approved: 0, ready: 0, needs_detail: 0, excluded: 0 };
  for (const code of codesOf(doc)) {
    const key = codeStatus(code).key;
    if (Object.hasOwn(counts, key)) counts[key] += 1;
  }
  const parts = [
    counts.approved ? `${counts.approved} approved` : '',
    counts.ready ? `${counts.ready} ready for review` : '',
    counts.needs_detail ? `${plural(counts.needs_detail, 'needs', 'need')} a detail` : '',
    counts.excluded ? `${counts.excluded} excluded` : '',
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'No codes yet';
}

function exportStatusText(doc) {
  const readiness = doc?.readiness || {};
  const blockers = strings(readiness.blockers);
  if (readiness.approved === true) {
    return `Every suggested code has a decision. The approved download lists only approved codes.${hasAgentDecision(doc) ? ` Includes ${AGENT_REVIEW.charAt(0).toLowerCase()}${AGENT_REVIEW.slice(1)}.` : ''}`;
  }
  const head = readiness.draft === true ? 'Draft only: the codes are suggestions, not approvals.' : 'Nothing can be downloaded yet.';
  return blockers.length ? `${head} Before the approved download: ${blockers.join(' ')}` : head;
}

function serviceDateText(date, long = true) {
  const value = date || {};
  if (value.conflict === true || value.source === 'conflict') {
    const documented = formatDate(value.document_value, long);
    const entered = formatDate(value.entered_value, long);
    return documented && entered ? `Two dates: the document says ${documented}, you entered ${entered}` : 'Two different dates';
  }
  const shown = formatDate(value.value, long);
  if (!shown) return 'Not documented';
  return value.source === 'member' ? `${shown} (entered)` : shown;
}

// --- rendering (pure string builders) ----------------------------------------------

const state = {
  session: null, route: null, routeSerial: 0, doc: null, docKey: '', layout: null, selectedEvidence: [],
  poll: { timer: 0, count: 0, errors: 0 }, tickTimer: 0, clock: 0, reconnecting: false, outdated: false,
  upload: { file: null, paste: false, busy: false, key: '' }, ack: null, review: null, addendum: null,
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

function rowDate(row) {
  return formatDate(row?.service_date) || (row?.date_conflict === true ? 'Date to choose' : 'Not documented');
}

function documentRow(row) {
  const tone = lookup(STATE_TONES, row.state, 'gray');
  const open = Number.isInteger(row.open_details) && row.open_details > 0 ? plural(row.open_details, 'detail needed', 'details needed') : '';
  const meta = [lookup(KIND_LABELS, row.kind, ''), open].filter(Boolean).join(' · ');
  return `<a class="document-row" href="#doc/${escapeHtml(encodeURIComponent(row.id))}"><span class="doc-row-main"><span class="doc-file-icon${tone === 'amber' ? ' amber' : ''}">${icon('file')}</span><span><strong>${escapeHtml(row.title || 'Untitled document')}</strong><small>${escapeHtml(meta)}</small></span></span><span>${stateBadge(row.state, row.state_label)}</span><span class="doc-row-date">${escapeHtml(rowDate(row))}</span>${icon('chevron', 'row-arrow')}</a>`;
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
    return count ? `${count === 1 ? 'One document waits' : `${count} documents wait`} on you: a date to choose, a detail to answer, or codes to review.` : 'No document waits on you for a date, a detail or a review decision.';
  }
  return `${plural(rows.length, 'synthetic document', 'synthetic documents')} in this workspace.`;
}

function inviteMarkup(rows) {
  const recent = rows?.[0];
  if (rows === null) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>Loading recent documents…</strong><p>One moment.</p></span>`;
  if (!recent) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>No documents yet</strong><p>Upload a synthetic GI document to see suggested codes beside the source.</p></span><button type="button" class="button secondary" data-action="upload">New document ${icon('plus')}</button>`;
  const detail = ['Most recent', stateLabel(recent.state, recent.state_label), formatDate(recent.service_date) || (recent.date_conflict === true ? 'date to choose' : 'service date not documented')].join(' · ');
  return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>${escapeHtml(recent.title || 'Untitled document')}</strong><p>${escapeHtml(detail)}</p></span><button type="button" class="button secondary" data-open="${escapeHtml(recent.id)}">Open review ${icon('arrow')}</button>`;
}

function overviewView() {
  return `<section class="view-entrance"><div class="heading-row home-heading"><div><span class="eyebrow">A CLEARER VIEW OF EVERY CODE</span><h1>Precision starts<br>with the <em>evidence.</em></h1><p>A focused workspace to turn clinical documentation into evidence-backed CPT suggestions.</p></div><div class="heading-actions"><span class="only-tag">CPT ONLY</span><button type="button" class="button primary" data-action="upload" aria-label="New document">${icon('plus')}<span class="desktop-label">New document</span></button></div></div>
  <div class="home-grid"><section class="upload-panel"><div class="panel-heading">${icon('file')}<h2>Start a coding review</h2><span class="small-badge">One encounter at a time</span></div><button type="button" class="drop-zone" id="overviewDrop" data-action="upload"><span class="upload-icon">${icon('upload')}</span><strong>Bring the original document.</strong><span>Choose a file, drop it here or paste the text</span><span>PDF, DOCX or TXT</span></button><div class="upload-footnote">${icon('info')}<span>Synthetic documents only. Do not upload real patient information.</span></div><div class="sample-invite" id="recentInvite">${inviteMarkup(null)}</div></section>
  <aside class="story-panel"><span class="eyebrow">BUILT AROUND THE CLINICAL STORY</span><h2>A clearer path.<br>From note to code.</h2><ol class="workflow-list"><li><span class="workflow-number">01</span><span><strong>Read the whole note</strong><p>Begin with the original documentation and encounter context.</p></span></li><li><span class="workflow-number">02</span><span><strong>See why each code is there</strong><p>Every suggested code links to the passages of the document that support it.</p></span></li><li><span class="workflow-number">03</span><span><strong>Make a clear decision</strong><p>Answer the few details that are missing, then approve or exclude each code.</p></span></li></ol><div class="story-bottom">${icon('link')}Evidence beside the decision. Always.</div></aside></div>
  <div class="section-heading"><h2>Recent documents</h2><a href="#documents">View all ${icon('arrow')}</a></div><div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div></section>`;
}

function documentsView(name) {
  const queue = name === 'queue';
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">${queue ? 'WHAT WAITS ON YOU' : 'THE ORIGINAL, ALWAYS IN VIEW'}</span><h1>${queue ? 'Review queue.' : 'Your documents.'}</h1><p>${queue ? 'A date to choose, a detail to answer, or codes to review: each document shows its next step.' : 'Keep source notes, supporting evidence and coding decisions together.'}</p></div><div class="heading-actions"><button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button></div></div><p class="section-description" id="listDescription">Loading…</p>${queue ? '' : `<label class="search-field list-search">${icon('search')}<input id="documentSearch" aria-label="Search documents" placeholder="Search documents…" autocomplete="off"></label>`}<div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div><p class="checks-disclaimer">${queue ? 'A document that is still being processed is not listed here; it appears once it needs you.' : 'Synthetic documents only. Each review decision is tied to the revision it was made on.'}</p></section>`;
}

function howItWorksView() {
  return `<section class="view-entrance"><div class="heading-row how-heading"><div><span class="eyebrow">A FOCUSED PRODUCT, BY DESIGN</span><h1>A reason behind<br><em>every suggestion.</em></h1><p>A standalone CPT workspace that keeps the original clinical story and the coding review connected.</p></div><button type="button" class="button primary" data-action="upload">Start a coding review ${icon('arrow')}</button></div><div class="flow-overview"><article class="flow-card"><span class="step">01</span><h2>The source<br>comes first.</h2><p>Upload the original PDF or Word document, or paste the note. The text is kept exactly as read, and anything that could not be read is listed.</p></article><article class="flow-card"><span class="step">02</span><h2>Four plain<br>stages.</h2><p>Reading your document, identifying procedures, checking suggested codes and preparing your results. The checks are a document review, independent checks and coding validation. A code is kept only with passages quoted exactly from the document.</p></article><article class="flow-card"><span class="step">03</span><h2>Review makes<br>the difference.</h2><p>Answer the few details that are missing, approve or exclude each code, and download the suggested codes as a draft or the approved codes alone. A changed document invalidates earlier decisions.</p></article></div><div class="how-note"><strong>This is a synthetic demonstration.</strong><br>Licensed CPT descriptors and NCCI procedure-to-procedure edits are not connected in this release, so descriptors are not shown and those edits are not checked. The checks read the wording of the document and can miss wording they do not recognise, so every code needs a reviewer who reads the whole document. Accuracy has not been independently evaluated; no accuracy percentage or payment guarantee is claimed.</div><button type="button" class="button secondary" data-action="about">${icon('info')}About CPT Studio</button></section>`;
}

function messageView(title, detail, retry = false) {
  return `<section class="view-entrance"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="check-list-card"><p class="empty-state"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</p>${retry ? '<p class="empty-state"><button type="button" class="button secondary" data-action="retry">Try again</button></p>' : ''}</div></section>`;
}

// The upload is acknowledged from the server's 201, before the document is first read back; once the reading stage is
// past, the stages below it say what is happening and the acknowledgement says only that the upload arrived.
function uploadAck(ack, extra = '', reading = true) {
  if (!ack) return '';
  const at = formatTimestamp(new Date(ack.at).toISOString());
  return `<div class="upload-ack" role="status">${icon('circle-check')}<div><strong>${reading ? 'Uploaded. Reading your document…' : 'Uploaded.'}</strong><p>${escapeHtml(`Received ${at}.`)}${extra ? ` ${escapeHtml(extra)}` : ''}</p></div></div>`;
}

function ackView(ack) {
  return `<section class="view-entrance review-view"><a class="back-link" href="#documents">${icon('arrow')}All documents</a><div class="review-column ack-column">${uploadAck(ack, 'You can leave this page; the document stays in Documents.')}</div></section>`;
}

// Every key that marks a passage in the source: each code's quotes ('<code id>:q<n>') and the document's date.
function documentLayout(doc) {
  const spans = [];
  const codes = new Map();
  for (const code of codesOf(doc)) {
    objects(code.why?.quotes).forEach((quote, index) => {
      const key = `${code.id}:q${index}`;
      spans.push({ ...quote, key });
      codes.set(key, String(code.code ?? ''));
    });
  }
  const dateQuote = doc?.service_date?.document_quote;
  if (dateQuote && typeof dateQuote === 'object') spans.push({ ...dateQuote, exact: true, key: 'date:document' });
  const documentPart = doc?.document || {};
  const layout = layoutDocument(documentPart.text || '', documentPart.pages, spans);
  return { pages: layout.pages, unlocated: new Set(layout.unlocated), codes };
}

function renderPieces(pieces, layout) {
  return pieces.map(piece => {
    if (!piece.keys) return escapeHtml(piece.text);
    const cited = [...new Set(piece.keys.map(key => layout.codes.get(key)).filter(Boolean))];
    const title = [cited.length ? `Cited for ${joinWords(cited)}` : '', piece.keys.includes('date:document') ? 'Date of service in the document' : ''].filter(Boolean).join('; ');
    return `<button type="button" class="evidence-mark" data-evidence="${escapeHtml(piece.keys[0])}" data-keys="${escapeHtml(piece.keys.join(' '))}" title="${escapeHtml(title)}">${escapeHtml(piece.text)}</button>`;
  }).join('');
}

function sourceName(documentPart) {
  return text(documentPart.name) || lookup({ paste: 'Pasted clinical text', addendum: 'Document with addendum' }, documentPart.kind, 'Original document');
}

function sourcePanel(doc, layout) {
  const documentPart = doc.document || {};
  const reading = documentPart.reading || {};
  const hasText = Boolean(documentPart.text);
  const total = Math.max(Number.isInteger(documentPart.page_count) ? documentPart.page_count : 0, layout.pages.length);
  const subtitle = ['Gastroenterology', text(reading.label), Number.isInteger(documentPart.revision) ? `Revision ${documentPart.revision}` : ''].filter(Boolean).join(' · ');
  const notes = strings(reading.messages);
  if (documentPart.kind === 'addendum') notes.unshift('This revision adds an addendum to the earlier text; decisions made on earlier revisions no longer apply.');
  if (reading.status === 'pending') notes.push('The text appears here once the document has been read.');
  const metadata = [['SERVICE DATE', serviceDateText(doc.service_date)], ['DOCUMENT', [lookup(KIND_LABELS, documentPart.kind, ''), Number.isInteger(documentPart.size) && documentPart.kind !== 'paste' ? formatSize(documentPart.size) : ''].filter(Boolean).join(' · ') || 'Not recorded'], ['PAGES', total ? String(total) : 'Not recorded']]
    .map(([label, value]) => `<span><b>${label}</b>${escapeHtml(value)}</span>`).join('');
  const header = `<span class="paper-eyebrow">${escapeHtml(`${state.session?.workspace?.name || 'CPT Studio'} · synthetic document`.toUpperCase())}</span><h3>${escapeHtml(sourceName(documentPart))}</h3><p class="paper-subtitle">${escapeHtml(subtitle)}</p><div class="paper-metadata">${metadata}</div>`;
  const emptyText = reading.status === 'failed' ? 'No text could be read from this document.' : 'The document text appears here once it has been read.';
  const papers = layout.pages.map((page, index) => {
    const body = page.paragraphs.map(pieces => `<p class="source-text">${renderPieces(pieces, layout)}</p>`).join('');
    return `<article class="source-paper" data-page="${escapeHtml(page.page)}" aria-label="${escapeHtml(`Page ${page.page}`)}">${index === 0 ? header : ''}${body || (index === 0 && !hasText ? `<p class="card-empty">${emptyText}</p>` : '')}<div class="paper-footer"><span>SYNTHETIC DOCUMENT · NOT FOR BILLING</span><span>${hasText ? escapeHtml(`${pad(page.page)} / ${pad(total)}`) : ''}</span></div></article>`;
  }).join('');
  const pageLabel = hasText ? `Page ${layout.pages[0].page} of ${total}` : 'No text yet';
  const originalUrl = safeOriginalUrl(documentPart.original_url);
  const original = originalUrl ? `<a href="${escapeHtml(originalUrl)}" download>${icon('download')}Download original</a>` : '';
  return `<section class="source-panel" aria-label="Source document"><div class="source-toolbar">${icon('file')}<h2>Original document</h2><span class="page-number" id="pageNumber" data-total="${escapeHtml(total)}">${escapeHtml(pageLabel)}</span></div><div class="source-paper-wrap" id="sourceScroll">${notes.map(note => `<div class="reference-note">${icon('info')}<span>${escapeHtml(note)}</span></div>`).join('')}${papers}</div><div class="source-bottom"><span></span>Original text as read${original}</div></section>`;
}

function reviewMeta(doc) {
  const date = doc.service_date || {};
  const dateItem = date.conflict === true ? 'Service date: two dates to choose from' : formatDate(date.value) ? `Service date ${formatDate(date.value)}` : 'Service date not documented';
  const revision = Number.isInteger(doc.document?.revision) ? `Revision ${doc.document.revision}` : '';
  return [`<span>${stateBadge(doc.state, doc.state_label)}</span>`, ...[dateItem, revision].filter(Boolean).map(item => `<span>${escapeHtml(item)}</span>`)].join('');
}

// --- the progress panel ---

function normalizedSteps(progress) {
  const served = new Map(objects(progress?.steps).map(step => [step.key, step]));
  return STEP_KEYS.map(key => {
    const step = served.get(key) || {};
    return { key, label: STEP_LABELS[key], state: lookup(STEP_STATES, step.state, null) ? step.state : 'not_started', started_at: step.started_at, finished_at: step.finished_at };
  });
}

function isoTime(value) {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value)) ? value : '';
}

// [label, markup] of the time the panel states: elapsed, ticking, while busy; the total once finished; else null.
function progressTime(progress, phase, ui) {
  const started = isoTime(progress?.started_at);
  if (!started) return null;
  if (progress.busy === true && ANIMATED_PHASES.has(phase)) {
    const now = (ui.nowMs ?? Date.now()) + (ui.clock || 0);
    return ['Elapsed', `<span data-elapsed data-since="${escapeHtml(started)}">${escapeHtml(elapsedText(started, now))}</span>`];
  }
  const finished = isoTime(progress.finished_at);
  if (!finished) return null;
  return [phase === 'failed' || phase === 'stopped' ? 'Ran for' : 'Finished in', `<span data-elapsed data-since="${escapeHtml(started)}" data-until="${escapeHtml(finished)}">${escapeHtml(durationText(Date.parse(finished) - Date.parse(started)))}</span>`];
}

function progressStep(step, active, animate, detail) {
  const stateText = lookup(STEP_STATES, step.state, 'Not started');
  const iconName = lookup(STEP_ICONS, step.state, '');
  const showDetail = active && detail;
  return `<li class="progress-step${active && animate ? ' is-animated' : ''}" data-step="${step.key}" data-state="${step.state}"><span class="step-mark" aria-hidden="true">${iconName ? icon(iconName) : ''}</span><span class="step-text"><strong>${escapeHtml(step.label)}</strong><small>${escapeHtml(stateText)}${showDetail ? ` · ${escapeHtml(detail)}` : ''}</small></span></li>`;
}

// The error's action is offered only to a member who may take it, and Resume only once (the panel's own Resume button
// may already offer it).
function progressError(error, { canAct = false, resumeShown = false } = {}) {
  if (!error || typeof error !== 'object' || !text(error.text)) return '';
  const offered = lookup(ERROR_ACTIONS, error.action, null);
  const action = canAct && offered && !(offered[0] === 'resume' && resumeShown) ? offered : null;
  return `<div class="progress-error" role="alert">${icon('info')}<div><p>${escapeHtml(error.text)}</p>${action ? `<button type="button" class="button secondary" data-action="${action[0]}">${escapeHtml(action[1])}</button>` : ''}</div></div>`;
}

function progressPanel(doc, ui = {}) {
  const progress = doc?.progress || {};
  const phase = progressPhase(doc, ui);
  const busy = progress.busy === true || phase === 'uploading';
  const message = text(progress.message);
  const time = progressTime(progress, phase, ui);
  if (!PANEL_PHASES.has(phase)) {
    const took = time ? ` · ${time[0].toLowerCase()} ${time[1]}` : '';
    return `<section class="progress-panel progress-done" data-phase="${phase}" aria-label="Processing">${icon(phase === 'partial' ? 'info' : 'circle-check')}<div><p class="progress-summary"><strong>${escapeHtml(PHASE_TITLES[phase])}</strong>${took}</p>${(phase === 'partial' || phase === 'awaiting_detail') && message ? `<p class="progress-message">${escapeHtml(message)}</p>` : ''}</div></section>`;
  }
  const animate = busy && ANIMATED_PHASES.has(phase);
  const steps = normalizedSteps(progress);
  const activeIndex = steps.findIndex(step => step.state === 'active');
  const detail = text(progress.active_detail);
  const showAck = ui.ack && ui.ack.id === doc?.id && ANIMATED_PHASES.has(phase);
  const canAct = canReview(doc);
  const stop = canAct && progress.can_stop === true && busy ? `<button type="button" class="button secondary" data-action="stop">${icon('stop')}Stop processing</button>` : '';
  const resume = canAct && progress.can_resume === true && !busy ? `<button type="button" class="button primary" data-action="resume">Resume processing ${icon('arrow')}</button>` : '';
  const leave = progress.can_leave !== false ? lookup(LEAVE_NOTES, phase, '') : '';
  const slow = progress.slow === true && busy;
  const headIcon = phase === 'action_needed' ? 'info' : phase === 'failed' ? 'close' : phase === 'stopped' ? 'stop' : 'clock';
  // the error says its own sentence below; the head does not repeat it
  const said = message && !(progress.error && typeof progress.error === 'object' && text(progress.error.text) === message) ? message : '';
  return `<section class="progress-panel${busy ? ' progress-card' : ''}" data-phase="${phase}" aria-labelledby="progressTitle">`
    + `<div class="progress-head"><span class="progress-icon${animate ? ' is-animated' : ''}">${icon(headIcon)}</span><div class="progress-status" aria-live="polite"><h2 id="progressTitle">${escapeHtml(PHASE_TITLES[phase])}</h2>${said ? `<p class="progress-message${slow ? ' slow' : ''}">${escapeHtml(said)}</p>` : ''}</div></div>`
    + (showAck ? uploadAck(ui.ack, '', ['waiting', 'active', 'not_started'].includes(steps[0].state)) : '')
    + `<ol class="progress-steps">${steps.map((step, index) => progressStep(step, index === activeIndex, animate, detail)).join('')}</ol>`
    + (time ? `<p class="progress-time">${time[0]} ${time[1]}</p>` : '')
    + `<p class="progress-reconnecting" role="status"${ui.reconnecting && shouldPoll(doc) ? '' : ' hidden'}>Reconnecting…</p>`
    + progressError(progress.error, { canAct, resumeShown: Boolean(resume) })
    + (leave ? `<p class="leave-note">${escapeHtml(leave)}</p>` : '')
    + (stop || resume ? `<div class="progress-actions">${stop}${resume}</div>` : '')
    + '</section>';
}

function checksPanel(doc) {
  const served = new Map(objects(doc?.checks).map(check => [check.key, check]));
  if (!served.size) return '';
  const items = CHECK_KEYS.filter(key => served.has(key)).map(key => {
    const check = served.get(key);
    const checkState = lookup(CHECK_STATES, check.state, null) ? check.state : 'not_run';
    return `<li class="check-step" data-check="${key}" data-state="${checkState}">${icon(CHECK_ICONS[checkState])}<span><strong>${escapeHtml(CHECK_LABELS[key])}</strong><small>${escapeHtml(CHECK_STATES[checkState])}</small></span></li>`;
  });
  return `<ul class="checks-panel" aria-label="Checks">${items.join('')}</ul>`;
}

// --- the "A few details needed" panel ---

function detailAnswer(row, ui) {
  const answer = ui.answers?.get?.(row.id);
  return answer && typeof answer.value === 'string' ? answer.value : '';
}

function answerButton(row, value, label, pending, action = '') {
  const pressed = pending === value;
  const hook = action ? `data-action="${action}"` : `data-detail-choice="${value}"`;
  return `<button type="button" class="button secondary detail-choice" id="detail-${escapeHtml(row.id)}-${value}" ${hook} data-detail="${escapeHtml(row.id)}" aria-pressed="${pressed}">${escapeHtml(label)}</button>`;
}

function allowedAnswers(row, pending) {
  return Object.keys(DETAIL_ANSWERS).filter(value => list(row.allow).includes(value)).map(value => answerButton(row, value, DETAIL_ANSWERS[value], pending)).join('');
}

function quoteLine(quote) {
  return quote && typeof quote.text === 'string' && quote.text ? `<q class="detail-quote">${escapeHtml(excerpt(quote.text, 120))}</q>` : '';
}

function dateControl(row, ui) {
  const pending = detailAnswer(row, ui);
  const documented = formatDate(row.document_value, true);
  const entered = formatDate(row.entered_value, true);
  // offered exactly where the server offers it (a choice of the row: the document states one date, and the member's
  // entry contradicts it), so the save the button makes is one the server accepts; never for a date only asked
  const offered = objects(row.choices).some(choice => choice.value === USE_DOCUMENT);
  const useDocument = documented && offered ? answerButton(row, USE_DOCUMENT, 'Use document date', pending, 'use-document-date') : '';
  const typed = parseIsoDate(pending) ? pending : '';
  return `<div class="detail-dates"><div class="detail-document-date"><span class="detail-date-label">Document</span><strong>${escapeHtml(documented || 'Not stated')}</strong>${quoteLine(row.quote)}</div><div class="detail-entered-date"><span class="detail-date-label">You entered</span><strong>${escapeHtml(entered || 'Nothing entered')}</strong></div></div>`
    + `<div class="detail-controls">${useDocument}<label class="detail-date-input">Or enter the date of service<input type="date" id="detail-${escapeHtml(row.id)}-date" data-detail-input data-detail="${escapeHtml(row.id)}"${typed ? ` value="${escapeHtml(typed)}"` : ''}></label>${allowedAnswers(row, pending)}</div>`;
}

function choiceControl(row, ui) {
  const pending = detailAnswer(row, ui);
  const radios = objects(row.choices).filter(choice => typeof choice.value === 'string' && choice.value).map(choice => {
    const checked = pending === choice.value;
    return `<label class="detail-radio"><input type="radio" name="detail-${escapeHtml(row.id)}" id="detail-${escapeHtml(row.id)}-${escapeHtml(choice.value)}" value="${escapeHtml(choice.value)}" data-detail="${escapeHtml(row.id)}"${checked ? ' checked' : ''}><span>${escapeHtml(choice.label || choice.value)}</span></label>`;
  }).join('');
  return `<div class="detail-controls">${radios}${allowedAnswers(row, pending)}</div>`;
}

function confirmControl(row, ui) {
  const pending = detailAnswer(row, ui);
  const addendum = row.addendum_allowed === true ? `<button type="button" class="button subtle detail-addendum" data-action="addendum" data-detail="${escapeHtml(row.id)}">Add to the documentation (physician)</button>` : '';
  return `<div class="detail-controls">${allowedAnswers(row, pending)}${addendum}</div>`;
}

function savedAnswer(row, editable) {
  const saved = row.saved;
  const value = text(saved.label) || lookup(DETAIL_ANSWERS, saved.value, saved.value === USE_DOCUMENT ? 'Use document date' : formatDate(saved.value, true) || text(saved.value));
  const by = [text(saved.by), formatTimestamp(saved.at)].filter(Boolean).join(', ');
  const change = editable && typeof saved.answer_id === 'string' && saved.answer_id ? `<button type="button" class="meta-link" data-action="revoke-detail" data-answer="${escapeHtml(saved.answer_id)}" id="detail-${escapeHtml(row.id)}-revoke">Change this answer</button>` : '';
  return `<p class="detail-saved">${icon('check')}<span>Saved: <strong>${escapeHtml(value)}</strong>${by ? ` — ${escapeHtml(by)}` : ''}</span>${change}</p>`;
}

function detailRow(row, doc, ui) {
  const editable = canReview(doc) && doc?.progress?.busy !== true;
  const affects = strings(row.affects);
  const control = row.saved ? savedAnswer(row, editable)
    : !editable ? '<p class="detail-wait">Answers can be saved once processing has finished.</p>'
      : row.control === 'date' ? dateControl(row, ui) : row.control === 'choice' ? choiceControl(row, ui) : confirmControl(row, ui);
  // a choice is a radio group, named by its legend; the legend comes first, holding the family and the prompt
  const tag = row.control === 'choice' && !row.saved && editable ? 'fieldset' : 'div';
  const lead = tag === 'fieldset' ? 'legend' : 'div';
  return `<${tag} class="detail-row${row.saved ? ' is-saved' : ''}" data-detail="${escapeHtml(row.id)}" data-fact="${escapeHtml(row.fact)}"><${lead} class="detail-lead"><span class="detail-family">${escapeHtml(text(row.family_label) || 'Detail')}</span><span class="detail-prompt">${escapeHtml(row.prompt)}</span></${lead}>${affects.length ? `<p class="detail-affects">Affects ${escapeHtml(joinWords(affects))}</p>` : ''}${control}</${tag}>`;
}

function detailsPanel(doc, ui = {}) {
  const rows = detailsOf(doc);
  if (!rows.length) return '';
  const open = rows.filter(row => !row.saved).length;
  const editable = canReview(doc) && doc?.progress?.busy !== true;
  const dateOnly = open && rows.filter(row => !row.saved).every(row => row.control === 'date');
  const lead = !open ? 'Every detail has an answer. You can change an answer below.'
    : dateOnly ? 'Choose the date of service. Nothing is checked until you do.'
      : `${plural(open, 'detail is', 'details are')} needed. Answer what you can; codes that do not depend on them stay reviewable.`;
  const save = open && editable ? `<div class="details-actions"><button type="button" class="button primary" data-action="save-details" id="saveDetails">Save answers ${icon('check')}</button><p>One save records every answer above. Nothing here changes the document itself.</p></div>` : '';
  return `<section class="details-panel" aria-labelledby="detailsTitle"><div class="details-head">${icon('info')}<div><h2 id="detailsTitle">A few details needed</h2><p>${escapeHtml(lead)}</p></div></div>${rows.map(row => detailRow(row, doc, ui)).join('')}<p class="form-error" id="detailsError" role="alert" hidden></p>${save}</section>`;
}

// --- the codes-first result list ---

function decisionButton(action, code) {
  const [, kind, label, iconName] = ACTION_BUTTONS.find(([name]) => name === action);
  return `<button type="button" class="button ${kind}" id="act-${escapeHtml(code.id)}-${action}" data-decision="${action}" data-proposal="${escapeHtml(code.id)}">${label}${iconName ? ` ${icon(iconName)}` : ''}</button>`;
}

function rowActions(code) {
  const allowed = list(code.allowed_actions);
  const buttons = ACTION_BUTTONS.filter(([name]) => allowed.includes(name)).map(([name]) => decisionButton(name, code));
  return buttons.length ? `<div class="result-actions">${buttons.join('')}</div>` : '';
}

// The agent label is stated once per row: here, unless the row's own line under the code already says it.
function decisionLine(code) {
  const decision = code.decision;
  if (!decision || typeof decision !== 'object') return '';
  const labelled = rowSubLabel(code) === AGENT_REVIEW;
  const title = `${lookup(DECISION_TITLES, decision.action, 'Decision recorded')} by ${text(decision.by) || 'a reviewer whose name was not recorded'}`;
  const modifiers = strings(decision.modifiers);
  const kind = decision.by_kind === 'agent' ? (labelled ? '' : 'agent-executed synthetic review — not clinical approval') : 'synthetic review — not clinical approval';
  const detail = [formatTimestamp(decision.at), modifiers.length ? `modifier ${modifiers.join(', ')}` : '', kind].filter(Boolean).join(' · ');
  const note = text(decision.note);
  return `<div class="result-decision">${icon('shield')}<div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p>${note ? `<p>${escapeHtml(`Note: ${note}`)}</p>` : ''}</div></div>`;
}

function whyQuote(code, quote, index, layout) {
  const key = `${code.id}:q${index}`;
  const attributes = `data-start="${escapeHtml(quote.start)}" data-end="${escapeHtml(quote.end)}" data-page="${escapeHtml(quote.page)}"`;
  if (layout.unlocated.has(key)) {
    return `<li><span class="why-quote unlocated" ${attributes}>${escapeHtml(quote.text)}</span><small class="why-unlocated">Not found at this place in the document.</small></li>`;
  }
  return `<li><button type="button" class="why-quote" data-evidence="${escapeHtml(key)}" ${attributes} title="Show this passage in the document">${escapeHtml(quote.text)}</button></li>`;
}

function modifierReview(code) {
  const review = code.modifier_review;
  if (!review || typeof review !== 'object') return '';
  const sources = strings(review.sources);
  return `<div class="why-modifier"><strong>Modifier review</strong>${text(review.text) ? `<p>${escapeHtml(review.text)}</p>` : ''}${sources.length ? `<p class="why-sources">${escapeHtml(`Source: ${sources.join('; ')}`)}</p>` : ''}<p class="why-sources">No modifier is added automatically; the reviewer may choose one when approving.</p></div>`;
}

function whyThisCode(code, layout, ui = {}) {
  const quotes = objects(code.why?.quotes).filter(quote => typeof quote.text === 'string' && quote.text);
  const qualifications = strings(code.why?.qualifications);
  const key = `why:${code.id}`;
  const body = [
    quotes.length ? `<p class="why-label">From the document</p><ul class="why-quotes">${objects(code.why?.quotes).map((quote, index) => (typeof quote.text === 'string' && quote.text ? whyQuote(code, quote, index, layout) : '')).join('')}</ul>` : '<p class="why-label">No passage of the document is quoted for this code.</p>',
    qualifications.length ? `<ul class="why-qualifications">${qualifications.map(item => `<li class="why-qualification">${escapeHtml(item)}</li>`).join('')}</ul>` : '',
    modifierReview(code),
  ].join('');
  return `<details class="why-code" data-key="${escapeHtml(key)}"${ui.open?.has?.(key) ? ' open' : ''}><summary>Why this code?</summary><div class="why-body">${body}</div></details>`;
}

function resultRow(code, index, doc, layout, ui = {}) {
  const status = codeStatus(code);
  const number = Number.isInteger(code.number) && code.number > 0 ? code.number : index + 1;
  const modifiers = strings(code.modifiers);
  const units = unitsLabel(code.units);
  return `<li class="result-row" id="card-${escapeHtml(code.id)}" tabindex="-1" data-proposal="${escapeHtml(code.id)}" data-code="${escapeHtml(code.code)}" data-status="${escapeHtml(status.key)}" data-units="${escapeHtml(Number.isInteger(code.units) ? code.units : '')}" data-modifiers="${escapeHtml(modifiers.join(' '))}">`
    + `<div class="result-head"><span class="result-number">${escapeHtml(number)}</span><span class="result-code">${escapeHtml(code.code)}</span><span class="result-units">${escapeHtml(units)}</span><span class="result-modifiers">${escapeHtml(modifierLabel(code))}</span>${badge(status.tone, status.label, status.icon, ` data-status="${escapeHtml(status.key)}"`)}</div>`
    + `<p class="result-sub">${escapeHtml(rowSubLabel(code))}</p>`
    + `<p class="result-summary">${escapeHtml(text(code.summary) || 'No explanation was recorded for this code.')}</p>`
    + decisionLine(code)
    + `<div class="result-foot">${whyThisCode(code, layout, ui)}${rowActions(code)}</div>`
    + '</li>';
}

function emptyResults(doc, ui) {
  const phase = progressPhase(doc, ui);
  return lookup({
    uploading: 'Suggested codes appear here when processing finishes.', queued: 'Suggested codes appear here when processing finishes.', processing: 'Suggested codes appear here when processing finishes.',
    action_needed: 'Nothing has been checked yet. Choose the date of service to continue.', failed: 'No codes were suggested.', stopped: 'Processing stopped before codes were suggested.',
    being_confirmed: 'Suggested codes appear here once the earlier check is confirmed.',
  }, phase, 'No CPT codes were suggested for this document.');
}

function reviewBar(doc) {
  const readiness = doc.readiness || {};
  const line = readiness.approved === true ? 'Every code has a decision. The approved download is available.' : readiness.draft === true ? 'You can download the suggested codes as a draft. The approved download waits for every decision.' : 'Downloads become available when results are ready.';
  return `<div class="review-bar"><div><p class="review-tally">${escapeHtml(tallyText(doc))}</p><p class="review-readiness">${escapeHtml(line)}</p></div><button type="button" class="button secondary" data-action="export">${icon('download')}Review and download</button></div>`;
}

function resultList(doc, layout, ui = {}) {
  const codes = codesOf(doc);
  if (!codes.length) return `<p class="results-empty">${escapeHtml(emptyResults(doc, ui))}</p>`;
  return `<ol class="result-list" aria-label="Suggested CPT codes">${codes.map((code, index) => resultRow(code, index, doc, layout, ui)).join('')}</ol>`;
}

function resultsSection(doc, layout, ui = {}) {
  const codes = codesOf(doc);
  const bar = codes.length || objects(doc.reports).length ? reviewBar(doc) : '';
  return `<section class="results-section" aria-labelledby="resultsTitle"><div class="results-topline"><h2 id="resultsTitle">Suggested codes</h2>${codes.length ? `<span class="small-badge">${escapeHtml(codes.length)}</span>` : ''}</div>${checksPanel(doc)}${resultList(doc, layout, ui)}${bar}</section>`;
}

function notSeparatelyCoded(doc) {
  const items = objects(doc.not_separately_coded).filter(item => text(item.label));
  if (!items.length) return '';
  return `<section class="result-notes not-coded"><h3>Not separately coded</h3><ul>${items.map(item => `<li><strong>${escapeHtml(item.label)}</strong>${text(item.reason) ? `<span>${escapeHtml(item.reason)}</span>` : ''}</li>`).join('')}</ul></section>`;
}

function otherCodes(doc, ui = {}) {
  const items = objects(doc.other_codes).filter(item => text(item.code));
  if (!items.length) return '';
  const key = 'other-codes';
  return `<details class="other-codes" data-key="${key}"${ui.open?.has?.(key) ? ' open' : ''}><summary>Other codes considered (not suggested)</summary><ul>${items.map(item => `<li><span class="other-code">${escapeHtml(item.code)}</span><span>${escapeHtml(text(item.reason) || 'Not supported by the document.')}</span></li>`).join('')}</ul></details>`;
}

function notesSection(doc) {
  const unresolved = strings(doc.unresolved);
  const limitations = strings(doc.limitations);
  if (!unresolved.length && !limitations.length) return '';
  return `<section class="result-notes limitations">${unresolved.length ? `<h3>Still open</h3><ul class="unresolved-list">${unresolved.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}${limitations.length ? `<h3>Limitations</h3><ul class="limitation-list">${limitations.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}</section>`;
}

function activityLog(doc, ui = {}) {
  const items = objects(doc.activity).filter(item => text(item.summary));
  if (!items.length) return '';
  const key = 'activity';
  return `<details class="activity-log" data-key="${key}"${ui.open?.has?.(key) ? ' open' : ''}><summary>History</summary><ol>${items.map(item => {
    const actor = text(item.actor);
    const by = [actor ? `${actor}${item.actor_kind === 'agent' && !/automated agent/i.test(actor) ? ' (automated agent)' : ''}` : '', formatTimestamp(item.at)].filter(Boolean).join(' · ');
    return `<li><strong>${escapeHtml(item.summary)}</strong>${by ? `<small>${escapeHtml(by)}</small>` : ''}</li>`;
  }).join('')}</ol></details>`;
}

function reviewView(doc, layout, ui = {}) {
  const codes = codesOf(doc);
  const download = codes.length || objects(doc.reports).length ? `<button type="button" class="button secondary" data-action="export">${icon('download')}<span>Download</span></button>` : '';
  return `<section class="${ui.entrance ? 'view-entrance ' : ''}review-view"><a class="back-link" href="#documents">${icon('arrow')}All documents</a>`
    + `<div class="heading-row review-heading"><div><span class="eyebrow">CODING REVIEW · GASTROENTEROLOGY</span><h1>${escapeHtml(doc.title || 'Untitled document')}</h1><div class="review-meta">${reviewMeta(doc)}</div></div><div class="heading-actions"><button type="button" class="button secondary" data-action="upload">${icon('plus')}<span>New document</span></button>${download}</div></div>`
    + `<div class="review-layout"><div class="review-column">${progressPanel(doc, ui)}${detailsPanel(doc, ui)}${resultsSection(doc, layout, ui)}${notSeparatelyCoded(doc)}${otherCodes(doc, ui)}${notesSection(doc)}${activityLog(doc, ui)}</div>${sourcePanel(doc, layout)}</div></section>`;
}

// --- the export dialog ---

function exportOption(kind, fmt, enabled, title, detail) {
  return `<button type="button" class="export-option" data-export-kind="${kind}" data-export-fmt="${fmt}"${enabled ? '' : ' disabled'}><span class="export-format">${fmt.toUpperCase()}</span><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></span>${icon('download')}</button>`;
}

function reportItem(report) {
  const url = safeDownloadUrl(report.download_url);
  const name = text(report.filename) || 'Download';
  const kind = report.kind === 'approved' ? 'Approved codes' : 'Suggested codes (draft)';
  const meta = [kind, formatTimestamp(report.generated_at), text(report.generated_by)].filter(Boolean).join(' · ');
  if (report.current !== true) {
    return `<li class="report-item stale"><span>${escapeHtml(name)}</span><small>${escapeHtml(`${meta} · No longer matches the saved decisions; create a new download.`)}</small></li>`;
  }
  return `<li class="report-item">${url ? `<a href="${escapeHtml(url)}" download>${escapeHtml(name)}</a>` : `<span>${escapeHtml(name)}</span>`}<small>${escapeHtml(meta)}</small></li>`;
}

function exportOptions(doc) {
  const readiness = doc?.readiness || {};
  const draft = readiness.draft === true;
  const approved = readiness.approved === true;
  const blockers = strings(readiness.blockers);
  const reports = objects(doc?.reports);
  const draftDetail = 'Every suggested code with its status. Nothing in it is approved.';
  const approvedDetail = 'Only approved codes, with who approved them and when.';
  return `<div class="export-group"><div class="evidence-label">Suggested codes — not approved</div>${exportOption('draft', 'txt', draft, 'Suggested codes as text', draftDetail)}${exportOption('draft', 'csv', draft, 'Suggested codes as a spreadsheet (CSV)', draftDetail)}</div>`
    + `<div class="export-group"><div class="evidence-label">Approved codes</div>${exportOption('approved', 'txt', approved, 'Approved codes as text', approvedDetail)}${exportOption('approved', 'csv', approved, 'Approved codes as a spreadsheet (CSV)', approvedDetail)}${!approved && blockers.length ? `<div class="export-blockers"><p>Not available yet:</p><ul>${blockers.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : ''}</div>`
    + (reports.length ? `<div class="export-group"><div class="evidence-label">Earlier downloads</div><ul class="report-list">${reports.map(reportItem).join('')}</ul></div>` : '');
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
  if (!data || typeof data !== 'object') throw new ApiError('The server answered in a way this page cannot read. Reload the page and try again.', response.status);
  return data;
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
    state.layout = null;
    state.selectedEvidence = [];
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
    ({ encounters: rows } = await api('/api/encounters'));
    if (!Array.isArray(rows)) throw new ApiError('The server answered with a document list this page cannot read.');
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
  if (state.ack?.id === doc.id && !(doc.progress?.busy === true)) state.ack = null;
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

function focusTarget() {
  const element = document.activeElement;
  if (!element || !$('#main').contains(element)) return null;
  if (element.id) return { id: element.id };
  if (element.dataset.proposal) return { proposal: element.dataset.proposal };
  return null;
}

function restoreFocus(target) {
  if (!target) return;
  const element = target.id ? document.getElementById(target.id) : document.getElementById(`card-${target.proposal}`);
  element?.focus({ preventScroll: true });
}

function renderDocument(doc, fresh, force = false) {
  const key = JSON.stringify(doc);
  if (!fresh && !force && key === state.docKey) return;
  const keep = fresh ? null : { source: $('#sourceScroll')?.scrollTop || 0, window: window.scrollY, focus: focusTarget() };
  state.doc = doc;
  state.docKey = key;
  state.layout = documentLayout(doc);
  $('#main').innerHTML = reviewView(doc, state.layout, uiState({ entrance: fresh }));
  if (keep) {
    if ($('#sourceScroll')) $('#sourceScroll').scrollTop = keep.source;
    window.scrollTo({ top: keep.window, behavior: 'instant' });
    restoreFocus(keep.focus);
  }
  if (state.selectedEvidence.length) applyHighlight(state.selectedEvidence);
  updatePageNumber();
  tick();
}

// Elapsed time on the page: one timer that rewrites only the [data-elapsed] text, while the document is busy.
function tick() {
  stopTicker();
  if (state.route?.name !== 'doc' || state.doc?.progress?.busy !== true) return;
  const nodes = $$('[data-elapsed][data-since]:not([data-until])');
  if (!nodes.length) return;
  const now = Date.now() + state.clock;
  for (const node of nodes) node.textContent = elapsedText(node.dataset.since, now);
  state.tickTimer = setTimeout(tick, TICK_MS);
}

function evidenceKeys(element) {
  return (element.dataset.keys || element.dataset.evidence || '').split(' ').filter(Boolean);
}

function applyHighlight(keys) {
  const wanted = new Set(keys);
  let first = null;
  $$('.evidence-mark').forEach(mark => {
    const selected = evidenceKeys(mark).some(key => wanted.has(key));
    mark.classList.toggle('selected', selected);
    if (selected && !first) first = mark;
  });
  $$('.why-quote[data-evidence]').forEach(quote => quote.classList.toggle('selected', wanted.has(quote.dataset.evidence)));
  return first;
}

function highlightEvidence(keys, scroll = true) {
  state.selectedEvidence = keys;
  const first = applyHighlight(keys);
  if (!scroll || !first) return;
  first.scrollIntoView({ behavior: reducedMotion() ? 'instant' : 'smooth', block: 'center' });
  updatePageNumber();
}

function updatePageNumber() {
  const box = $('#sourceScroll');
  const label = $('#pageNumber');
  const papers = box ? $$('.source-paper', box) : [];
  if (!label || papers.length < 2) return;
  const view = box.getBoundingClientRect();
  const middle = view.top + view.height / 2;
  let current = papers[0];
  for (const paper of papers) if (paper.getBoundingClientRect().top <= middle) current = paper;
  label.textContent = `Page ${current.dataset.page} of ${label.dataset.total}`;
}

function findCode(id) {
  return codesOf(state.doc).find(code => code.id === id) || null;
}

function setModifierField(code, action) {
  const options = action === 'approve' ? reviewModifierOptions(code) : [];
  const field = $('#reviewModifierField');
  const select = $('#reviewModifier');
  select.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    return option;
  }));
  select.value = '';
  field.hidden = !options.length;
  const review = code?.modifier_review;
  $('#reviewModifierHelp').textContent = options.length ? [text(review?.text), strings(review?.sources).length ? `Source: ${strings(review.sources).join('; ')}.` : ''].filter(Boolean).join(' ') : '';
}

async function openReview(proposalId, action) {
  const code = findCode(proposalId);
  if (!code || !REVIEW_COPY[action]) return;
  if (!state.session && !(await loadSession())) {
    toast('Your identity could not be confirmed, so no decision can be recorded. Reload the page and try again.');
    return;
  }
  const agent = isAgent();
  const copy = REVIEW_COPY[action];
  const revision = Number.isInteger(state.doc.document?.revision) ? state.doc.document.revision : 1;
  const body = {
    approve: agent ? `This approval is recorded as an agent-executed synthetic review, with the agent's identity and the time, against revision ${revision} of this document. A changed document invalidates it.` : `Your approval is recorded with your identity and the time, against revision ${revision} of this document. A changed document invalidates it.`,
    reject: 'A rejected code is excluded from the approved download. Add a note so the next reviewer knows why.',
    reinstate: 'This code was excluded when the document was checked. Reinstating records your judgement and makes it reviewable; it does not approve it.',
    confirm: 'This code was excluded when the document was checked. Confirming records your judgement that the exclusion is right.',
  }[action];
  state.review = { proposalId, action };
  $('#reviewEyebrow').textContent = copy.eyebrow;
  $('#reviewTitle').textContent = copy.title;
  $('#reviewCopy').textContent = body;
  $('#reviewCode').textContent = code.code;
  $('#reviewStatus').textContent = codeStatus(code).label;
  $('#reviewSummary').textContent = text(code.summary);
  $('#reviewAckLabel').hidden = action !== 'approve';
  $('#reviewAcknowledgement').checked = false;
  $('#reviewAckText').textContent = attestationText(state.session);
  setModifierField(code, action);
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
  if (review.action === 'approve' && !$('#reviewAcknowledgement').checked) {
    showError('reviewError', 'Confirm that you reviewed the document for this code.');
    return undefined;
  }
  return guarded('review', async () => {
    const button = $('#saveReview');
    setBusy(button, true);
    hideError('reviewError');
    const body = { proposal_id: review.proposalId, action: review.action, note: $('#reviewNote').value.trim(), acknowledgement: review.action === 'approve' ? $('#reviewAckText').textContent : '' };
    if (review.action === 'approve' && !$('#reviewModifierField').hidden) {
      const chosen = $('#reviewModifier').value;
      body.modifiers = MODIFIER_CHOICES.includes(chosen) ? [chosen] : [];
    }
    try {
      await postDecision(body);
      const code = findCode(review.proposalId)?.code || 'the code';
      closeDialog('reviewDialog');
      await afterChange({ approve: `Approval recorded for ${code}.`, reject: `Rejection recorded for ${code}.`, reinstate: `${code} reinstated for review.`, confirm: `Exclusion of ${code} confirmed.` }[review.action]);
    } catch (error) {
      showError('reviewError', error.message);
    } finally {
      setBusy(button, review.action === 'approve' && !$('#reviewAcknowledgement').checked);
    }
  });
}

function revokeDecision(proposalId, button) {
  return guarded(`revoke:${proposalId}`, async () => {
    setBusy(button, true);
    try {
      await postDecision({ proposal_id: proposalId, action: 'revoke', note: '', acknowledgement: '' });
      await afterChange(`Decision undone for ${findCode(proposalId)?.code || 'the code'}.`);
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function handleDecision(action, proposalId, button) {
  if (action === 'revoke') return revokeDecision(proposalId, button);
  return openReview(proposalId, action);
}

// --- details: every answer is a selection until the one save sends them all ---

function findDetail(id) {
  return detailsOf(state.doc).find(row => row.id === id) || null;
}

function syncDetailRow(id) {
  const row = $$('.detail-row').find(element => element.dataset.detail === id);
  if (!row) return;
  const value = state.answers.get(id)?.value || '';
  $$('[data-detail-choice], [data-action="use-document-date"]', row).forEach(button => {
    const own = button.dataset.detailChoice || USE_DOCUMENT;
    button.setAttribute('aria-pressed', String(own === value));
  });
  $$('input[type="radio"]', row).forEach(input => { input.checked = input.value === value; });
  const date = $('input[data-detail-input]', row);
  if (date && !parseIsoDate(value) && date.value) date.value = '';
}

function chooseDetail(id, value) {
  const row = findDetail(id);
  if (!row || row.saved) return;
  if (state.answers.get(id)?.value === value) state.answers.delete(id);
  else state.answers.set(id, { fact: row.fact, value });
  hideError('detailsError');
  syncDetailRow(id);
}

function enterDetailDate(input) {
  const row = findDetail(input.dataset.detail);
  if (!row || row.saved) return;
  if (parseIsoDate(input.value)) state.answers.set(row.id, { fact: row.fact, value: input.value });
  else if (parseIsoDate(state.answers.get(row.id)?.value || '')) state.answers.delete(row.id);
  hideError('detailsError');
  syncDetailRow(row.id);
}

function detailAnswers(doc) {
  return openDetails(doc).filter(row => state.answers.has(row.id)).map(row => ({ id: row.id, fact: row.fact, value: state.answers.get(row.id).value }));
}

function saveDetails(button) {
  if (!state.doc) return undefined;
  const answers = detailAnswers(state.doc);
  if (!answers.length) {
    showError('detailsError', 'Choose an answer for at least one detail, then save.');
    return undefined;
  }
  return guarded('details', async () => {
    setBusy(button, true);
    hideError('detailsError');
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/details`, { method: 'POST', json: { answers } });
      for (const answer of answers) state.answers.delete(answer.id);
      await afterChange(answers.length === 1 ? 'Answer saved.' : `${answers.length} answers saved.`);
    } catch (error) {
      showError('detailsError', error.message);
      setBusy(button, false);
    }
  });
}

function revokeDetail(button) {
  if (!state.doc) return undefined;
  const answerId = button.dataset.answer;
  return guarded(`revoke-detail:${answerId}`, async () => {
    setBusy(button, true);
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/details/${encodeURIComponent(answerId)}/revoke`, { method: 'POST', json: {} });
      await afterChange('The answer was withdrawn. You can answer again.');
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

// --- addendum: the physician's own documentation, as a new revision ---

function openAddendum(detailId) {
  const row = findDetail(detailId);
  state.addendum = { detailId: row?.id || null };
  $('#addendumQuestion').textContent = row ? text(row.prompt) : '';
  $('#addendumQuestion').hidden = !row;
  $('#addendumText').value = '';
  $('#addendumAttestation').checked = false;
  hideError('addendumError');
  openDialog('addendumDialog');
}

function submitAddendum(event) {
  event.preventDefault();
  if (!state.doc || !state.addendum) return undefined;
  const body = $('#addendumText').value;
  if (!body.trim()) {
    showError('addendumError', 'Write the addendum text.');
    return undefined;
  }
  if (codePoints(body.trim()) > MAX_ADDENDUM_CHARS) {
    showError('addendumError', 'An addendum can be at most 20,000 characters.');
    return undefined;
  }
  if (!$('#addendumAttestation').checked) {
    showError('addendumError', 'Confirm that the addendum is synthetic and contains no real patient information.');
    return undefined;
  }
  return guarded('addendum', async () => {
    const button = $('#saveAddendum');
    setBusy(button, true);
    hideError('addendumError');
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/addenda`, { method: 'POST', json: { text: body, clarification_id: state.addendum.detailId, synthetic_attestation: 'yes' } });
      closeDialog('addendumDialog');
      await afterChange('Addendum added as a new revision. Processing has started.');
    } catch (error) {
      showError('addendumError', error.message);
    } finally {
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

// The multipart body of one upload attempt, or the sentence that says what is missing.
function uploadForm(fields, key) {
  const form = new FormData();
  if (fields.paste) {
    if (!fields.text.trim()) return 'Paste the clinical text, or switch back to uploading a file.';
    if (codePoints(fields.text) > MAX_PASTE_CHARS) return 'The pasted text is longer than 400,000 characters. Upload it as a file instead.';
    form.append('text', fields.text);
  } else {
    if (!fields.file) return 'Choose a PDF, DOCX or TXT document, or paste the text instead.';
    form.append('file', fields.file, fields.file.name);
  }
  if (fields.serviceDate && !parseIsoDate(fields.serviceDate)) return 'Enter the service date as a valid date, or leave it blank.';
  if (!fields.attested) return 'Confirm that the document is synthetic and contains no real patient information.';
  if (fields.serviceDate) form.append('service_date', fields.serviceDate);
  form.append('synthetic_attestation', 'yes');
  form.append('client_key', key);
  return form;
}

async function submitUpload(event) {
  event.preventDefault();
  if (state.upload.busy) return;
  if (!state.upload.key) state.upload.key = newClientKey(randomBytes);
  const form = uploadForm({ paste: state.upload.paste, text: $('#pasteText').value, file: state.upload.file, serviceDate: $('#serviceDate').value, attested: $('#syntheticAttestation').checked }, state.upload.key);
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

// --- stop, resume, export ---

function stopProcessing(button) {
  if (!state.doc) return undefined;
  return guarded('stop', async () => {
    setBusy(button, true);
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/stop`, { method: 'POST', json: {} });
      await afterChange('Stopping. Steps that have not started will not run.');
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function resumeProcessing(button) {
  if (!state.doc) return undefined;
  return guarded('resume', async () => {
    setBusy(button, true);
    try {
      await api(`/api/encounters/${encodeURIComponent(state.doc.id)}/resume`, { method: 'POST', json: {} });
      await afterChange('Processing resumed.');
    } catch (error) {
      toast(error.message);
      setBusy(button, false);
    }
  });
}

function openExport() {
  if (!state.doc) return;
  const readiness = state.doc.readiness || {};
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
  const evidence = target.closest('[data-evidence]');
  if (evidence) {
    highlightEvidence(evidenceKeys(evidence));
    return;
  }
  const decision = target.closest('[data-decision]');
  if (decision) {
    handleDecision(decision.dataset.decision, decision.dataset.proposal, decision);
    return;
  }
  const choice = target.closest('[data-detail-choice]');
  if (choice) {
    chooseDetail(choice.dataset.detail, choice.dataset.detailChoice);
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
    addendum: () => openAddendum(action.dataset.detail),
    'use-document-date': () => chooseDetail(action.dataset.detail, USE_DOCUMENT),
    'save-details': () => saveDetails(action),
    'revoke-detail': () => revokeDetail(action),
    stop: () => stopProcessing(action),
    resume: () => resumeProcessing(action),
    reload: () => location.reload(),
    retry: route,
  })[action.dataset.action]?.();
}

function onChange(event) {
  const input = event.target;
  if (input.matches?.('.detail-row input[type="radio"]')) chooseDetail(input.dataset.detail, input.value);
  else if (input.matches?.('input[data-detail-input]')) enterDetailDate(input);
}

function onInput(event) {
  const input = event.target;
  if (input.id === 'documentSearch') applySearch();
  else if (input.matches?.('input[data-detail-input]')) enterDetailDate(input);
  else if (['pasteText', 'serviceDate'].includes(input.id)) forgetAttemptKey();
}

// The open "Why this code?" and other disclosures survive a refresh of the page's data.
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
  $('#addendumForm').addEventListener('submit', submitAddendum);
  $('#uploadFile').addEventListener('change', event => setUploadFile(event.target.files?.[0]));
  $('#clearFile').addEventListener('click', () => setUploadFile(null));
  $('#pasteToggle').addEventListener('click', () => {
    setPasteMode(!state.upload.paste);
    (state.upload.paste ? $('#pasteText') : $('#uploadFile')).focus();
  });
  $('#reviewAcknowledgement').addEventListener('change', event => { $('#saveReview').disabled = !event.target.checked; });
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
  document.addEventListener('change', onChange);
  document.addEventListener('input', onInput);
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('toggle', onToggle, true);
  let pageFrame = 0;
  document.addEventListener('scroll', event => {
    if (event.target.id !== 'sourceScroll' || pageFrame) return;
    pageFrame = requestAnimationFrame(() => { pageFrame = 0; updatePageNumber(); });
  }, true);
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
    escapeHtml, lookup, parseIsoDate, formatDate, formatTimestamp, readCookie, safeDownloadUrl, safeOriginalUrl, pollDelay,
    parseRoute, isClientOutdated, errorText, newClientKey, durationText, clockOffset, elapsedText, codeUnitOffsets, mergeSpans,
    pageRanges, paragraphRanges, paragraphPieces, layoutDocument, progressPhase, shouldPoll, codeStatus, rowSubLabel, unitsLabel,
    modifierLabel, reviewModifierOptions, hasAgentDecision, attestationText, tallyText, exportStatusText, serviceDateText,
    documentRow, listBody, listDescription, inviteMarkup, overviewView, documentsView, howItWorksView, inQueue, uploadAck, ackView,
    documentLayout, sourcePanel, reviewMeta, progressPanel, checksPanel, detailsPanel, detailRow, resultRow, resultList,
    resultsSection, whyThisCode, decisionLine, reviewBar, notSeparatelyCoded, otherCodes, notesSection, activityLog, reviewView,
    exportOptions, uploadForm, state, ACKNOWLEDGEMENTS, AGENT_REVIEW, OUTDATED_TEXT, CLIENT_HEADER, CLIENT_VERSION, QUEUE_STATES,
    STEP_KEYS, CHECK_KEYS, MODIFIER_CHOICES,
  };
}
if (typeof document !== 'undefined') boot();
