'use strict';
// CPT Studio customer page, drawn from the customer encounter contract (client contract customer-2026-11-26: the build
// specification, sections 6 and 7, with the fix passes' line identity). Every code row is named by its line ("L1".."Ln",
// "M1".."Mk"), never by its code alone: one code may stand on two lines. The review dialog, the reason it shows, the
// buttons and every decision use the row's line and the number of the coding review the page shows; an Undo names the
// decision it undoes (the id the page shows for it), and a download names the coding review the export dialog was
// opened on. What a dialog's act names - the document, the coding review, the line, its code - is fixed when the dialog
// opens (an export dialog opened while the page loads the latest offers nothing until it has, and is then drawn as opened
// on it), and leaving the document closes it. An act the server refuses because what the page shows changed reads the
// document again and says so. Rendering builds markup strings; every
// value that comes from the server passes through escapeHtml. Text the coding review wrote (reasons, questions,
// documentation notes, quoted passages) is shown as written and escaped like every other value. Everything above
// "browser wiring" is pure and unit-tested under node (tests/frontend/app.test.cjs).

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
const CLIENT_VERSION = 'customer-2026-11-26';
const OUTDATED_TEXT = 'CPT Studio was updated — reload the page to continue.';
// What the page says when the server refuses a decision with a conflict status (the coding review the page shows, or a
// line of it, is no longer the latest): nothing was recorded, and the page has read the document again.
const CHANGED_TEXT = 'This coding review has changed, so nothing was recorded. The page now shows the latest.';
const OFFLINE_TEXT = 'The server could not be reached. Check the connection and try again.';
// Release 1 (RELEASE-1-SPEC B4 to B6, C4 to C6): the sign-in state the page keeps up with, the practice's team, the plain
// sentence of a limit and the download of a Word document.
const POLL_HEADER = 'X-CPT-Poll';  // the document poll and the refresh on return carry it: neither is the member's activity
const ACTIVITY_URL = '/session/activity';
const ACTIVITY_EVERY_MS = 60000;  // the activity ping goes at most once a minute, while there is input
const ACTIVITY_INPUTS = ['pointerdown', 'keydown', 'wheel', 'scroll', 'touchstart'];
const SESSION_CHANNEL = 'cpt-studio-session';  // the tabs of this browser share one idle timer
const ACCOUNT_REQUIRED_URL = '/account/?required=1';
const WORD_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const WORD_ORIGINAL_TEXT = 'The original Word file can contain links and embedded content. Download it anyway?';
const DOWNLOAD_ADDRESS_MS = 60000;  // how long the address of a file saved from the page's own bytes is kept
const FRAME_LIMIT_TEXT = 'The document could not be shown: too many requests in a short time. Wait a minute, then open it again.';
const FRAME_REFUSED_TEXT = 'The document could not be shown. Open it again to try once more.';
const ROLE_LABELS = { owner: 'Owner', reviewer: 'Reviewer', viewer: 'Viewer' };
// a code the server answers for the page to act on (signed_out, password_change_required, rate_limited), never a
// sentence to show
const MACHINE_WORD = /^[a-z][a-z0-9_]*$/;
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
// A line of a coding review: "L1".."Ln" for the codes it listed, in its order, then "M1".."Mk" for the codes the second
// check added. A decision names one; a row without one is shown and never decided.
const LINE = /^[LM][1-9][0-9]{0,2}$/;
// The id the server gives a line's current decision (the CodeDecision's own id): what an Undo names, so the server can
// refuse to undo a decision the member never saw. A decision without one the page can send back is shown, never undone.
const DECISION_ID = /^[A-Za-z0-9-]{1,64}$/;
// Units or modifiers the coding review did not give (the contract's null): said so - never a number, never nothing, and
// never "No modifier", which is the coding review saying there is none. Units are a whole number as the coding review
// wrote them, 0 included (it writes 0 on a code it does not support), and shown as that number: "0 units".
const UNITS_NOT_GIVEN = 'Units not given';
const MODIFIERS_NOT_GIVEN = 'Modifiers not given';
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
const ROUTE_TITLES = { workspace: 'Overview', documents: 'Documents', queue: 'Review queue', 'how-it-works': 'How it works', doc: 'Document review', team: 'Team' };
const LIST_HEADER = '<div class="list-header"><span>DOCUMENT</span><span>STATUS</span><span class="date-header">SERVICE DATE</span><span></span></div>';
// R2-22: the lists a page at a time (R2-19), the search's POST (R2-20), automatic pages (C7), a search in the page (C2).
const LIST_ADDRESS = { workspace: '/api/encounters?list=recent', documents: '/api/encounters?list=documents', queue: '/api/encounters?list=queue' };
const SEARCH_URL = '/api/encounters/search';
const SEARCH_PAUSE_MS = 300;
const AUTO_PAGES = 3;
const LOCAL_SEARCH_MAX = 200;
const MORE_TEXT = 'Show more documents';

// --- pure helpers ----------------------------------------------------------------

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"'`]/g, ch => HTML_ESCAPES[ch]);
}

// (Object.prototype.hasOwnProperty: the page script asks no more of a browser than it needs; the PDF viewer's own needs
// are pdfCapable's)
function lookup(map, key, fallback) {
  return typeof key === 'string' && Object.prototype.hasOwnProperty.call(map, key) ? map[key] : fallback;
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
  if (status === 429) return served && !MACHINE_WORD.test(served) ? served : rateLimitText(data);
  if (served && !MACHINE_WORD.test(served)) return served;
  if (status === 400) return 'This could not be saved. Check the form and try again.';
  if (status === 403) return 'This action is not allowed for your account, or the page is out of date. Reload the page and try again.';
  if (status === 404) return 'Not found, or not in your workspace.';
  if (status === 409) return 'This action is not available right now. Reload the page to see the latest state.';
  if (status === 413) return 'The file is too large. Choose a file up to 15 MB.';
  if (status === 429) return 'Too many attempts in a short time. Wait a moment and try again.';
  return 'Something went wrong on our side. Nothing was changed by this attempt; try again in a moment.';
}

// C5: a limit the server counts (429 {"error": "rate_limited", "retry_after": seconds}) in plain words.
function rateLimitText(data) {
  const seconds = Number(data?.retry_after);
  if (!Number.isFinite(seconds) || seconds <= 0) return 'Too many requests in a short time. Wait a moment and try again.';
  if (seconds <= 60) return 'Too many requests in a short time. Wait a minute and try again.';
  return `Too many requests in a short time. Wait ${Math.ceil(seconds / 60)} minutes and try again.`;
}

// B6: under HTTPS the site's cookies carry the __Host- prefix (cptstudio/settings.py) and only that name is read, so a
// cookie of the name before release 1, left in this browser, never wins; without HTTPS, the plain name.
function csrfCookieName(protocol) {
  return protocol === 'https:' ? '__Host-cptstudio_csrf' : 'cptstudio_csrf';
}

// B5: why the server signed the member out ({"error": "signed_out", "reason": "idle" | "expired"}): idle when it says
// so, else expired - a session that ended for any other reason is simply over.
function signedOutReason(data) {
  return data?.error === 'signed_out' && data.reason === 'idle' ? 'idle' : 'expired';
}

// The sign-in page, saying why, and coming back to the page the member was on.
function loginAddress(reason, hash) {
  return `/login/?${new URLSearchParams({ reason, next: `/${hash || ''}` })}`;
}

// B5: the shared idle timer's next step at `now` (ms): 'out' at or after the deadline the tabs share, 'warn' inside the
// warning's lead before it, 'wait' until then; `in` is how long until the step after it, `left` how long until the end.
function idleStep(deadline, warningMs, now) {
  if (!Number.isFinite(deadline) || deadline <= 0) return { step: 'wait', in: null, left: null };
  if (now >= deadline) return { step: 'out', in: 0, left: 0 };
  if (now >= deadline - warningMs) return { step: 'warn', in: deadline - now, left: deadline - now };
  return { step: 'wait', in: deadline - warningMs - now, left: deadline - now };
}

function idleWarningText(ms) {
  const minutes = Math.max(1, Math.ceil(ms / 60000));
  return `You will be signed out in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
}

// C4: the practice's team as GET /api/members serves it to an owner: {"members": [{id, label, username, role, active,
// actor_kind, last_sign_in, password_change_required}]}; a row without an id of its own is never drawn.
function teamMembers(data) {
  return objects(data?.members).filter(member => typeof member.id === 'string' && UUID.test(member.id));
}

function memberRow(member, selfId) {
  const self = member.id === selfId;
  const label = text(member.label) || text(member.username) || 'Unnamed account';
  const detail = [lookup(ROLE_LABELS, member.role, 'Member'), member.actor_kind === 'agent' ? 'Automated account' : 'Person', text(member.username)]
    .filter(Boolean).join(' · ');
  const access = member.active === true ? badge('green', 'Access on') : badge('gray', 'Access off');
  const password = member.password_change_required === true ? badge('amber', 'Must choose a password') : '';
  const signIn = formatTimestamp(member.last_sign_in) || 'Never signed in';
  const id = escapeHtml(member.id);
  const action = self ? '<span class="card-empty">You</span>'
    : member.active === true ? `<button type="button" class="button secondary" data-member-access="off" data-member="${id}" data-label="${escapeHtml(label)}">Turn off</button>`
      : `<button type="button" class="button secondary" data-member-access="on" data-member="${id}" data-label="${escapeHtml(label)}">Turn on</button>`;
  return `<div class="document-row team-row" data-member-row="${id}"><span class="doc-row-main"><span class="doc-file-icon">${icon('shield')}</span><span><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></span></span><span>${access}${password}</span><span class="doc-row-date">${escapeHtml(signIn)}</span><span>${action}</span></div>`;
}

const TEAM_HEADER = '<div class="list-header"><span>PERSON</span><span>ACCESS</span><span class="date-header">LAST SIGN-IN</span><span></span></div>';

function teamList(members, selfId) {
  if (members === null) return `${TEAM_HEADER}<p class="empty-state">Loading the team…</p>`;
  return TEAM_HEADER + (members.length ? members.map(member => memberRow(member, selfId)).join('') : '<p class="empty-state">Nobody else has access to this practice.</p>');
}

function teamView() {
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">YOUR PRACTICE</span><h1>Team.</h1><p>Everyone with access to this practice's documents. Turning a person off ends their access to this practice only, at their next step; their other practices are not changed. Adding people and changing roles is done by CPT Studio on the practice's request.</p></div></div><div class="document-list" id="teamList">${teamList(null, '')}</div></section>`;
}

// C6: a Word document downloads as the PDF the coding review read; the Word file itself only after a warning, as
// ?format=original, and so does the original of a Word document not yet converted. A PDF or a text downloads as before.
function downloadLinks(part) {
  const original = safeOriginalUrl(part?.original_url);
  if (!original) return '';
  const plain = label => `<a class="viewer-download" id="downloadOriginal" href="${escapeHtml(original)}" download>${icon('download')}${label}</a>`;
  if (part.media_type !== WORD_MEDIA_TYPE) return plain('Download original');
  const word = `<button type="button" class="viewer-download meta-link" id="downloadWord" data-word-original="${escapeHtml(`${original}?format=original`)}">${icon('download')}Download the Word file</button>`;
  return part.converted === true ? plain('Download PDF') + word : word;
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
  return findPassages(source, passage)[0] || null;
}

// Each UTF-16 unit lower-cased where that keeps it one unit (a letter whose lower case is longer is compared as written),
// so the offsets of a case-blind search stay those of the text.
function lowerUnits(value) {
  return value.replace(/[\s\S]/g, unit => {
    const lower = unit.toLowerCase();
    return lower.length === 1 ? lower : unit;
  });
}

// Every place a quoted passage occurs in a text, left to right and without overlap, as [start, end] in the text's own
// offsets: the text document's rule (findPassage), counted.
function findPassages(source, passage) {
  const hay = collapseSpace(String(source ?? ''));
  const want = collapseSpace(String(passage ?? '')).flat.trim();
  if (!want) return [];
  const places = (flat, needle) => {
    const found = [];
    for (let at = flat.indexOf(needle); at >= 0; at = flat.indexOf(needle, at + needle.length)) found.push(at);
    return found;
  };
  let found = places(hay.flat, want);
  if (!found.length) found = places(lowerUnits(hay.flat), lowerUnits(want));
  return found.map(at => [hay.map[at], hay.map[at + want.length - 1] + 1]);
}

// --- the quoted words, marked on a page of a PDF (the owner's direction of 2026-11-20, DECISIONS D368) --------------
// The rule's one statement is CORE-UX-DESIGN.md, "Marking a quoted passage": a page's text (pageText, overprintCopies),
// a quote located by its own characters, its word edges (keepsEdge) and its pages (locateQuote). Nothing here reads
// what the words mean: Unicode character classes, NFKC and the items' geometry only.

// One character with the marks that follow it (or marks with nothing before them): how a text is cut into characters
// where the browser cannot cut it into the characters a person sees (Intl.Segmenter). The PDF viewer never runs there
// (pdfCapable).
const TEXT_UNIT = /\P{M}\p{M}*|\p{M}+/gu;
// What a folded text never holds: white space and format characters.
const UNFOLDED = /[\s\p{Cf}]+/gu;
const FORMAT_CHARACTER = /\p{Cf}/u;
// A character that belongs to a word (a letter, a digit or a combining mark), and one a quote's word edge is kept for (a
// letter or a digit) - unless it is a Han ideograph or a hiragana character, each a word of its own as Unicode's default
// word boundaries (UAX #29) have it (R2c); katakana stays a word part.
const WORD_PART = /^[\p{L}\p{N}\p{M}]$/u;
const WORD_EDGE = /^[\p{L}\p{N}]/u;
const OWN_WORD = /^[\p{Ideographic}\p{Script=Hiragana}]/u;
// R2a: a digit, and the code points that keep two digits in one word when a digit stands on each side (UAX #29 WB11 and
// WB12: MidNum, MidNumLet and Single_Quote in Unicode 16.0, the 21 that Node 22's ICU 77.1 joins between two digits only).
const DIGIT = /^\p{Nd}/u;
const NUMBER_SEPARATORS = new Set([0x0027, 0x002c, 0x002e, 0x003b, 0x037e, 0x0589, 0x060c, 0x060d, 0x066c, 0x07f8, 0x2018,
  0x2019, 0x2024, 0x2044, 0xfe50, 0xfe52, 0xfe54, 0xff07, 0xff0c, 0xff0e, 0xff1b]);
// R1: two drawings' font heights agree within this share to be one overprint. R2b: one drawing continues another where
// their font heights agree within CONTINUED.heights and the next begins at the first one's end, within CONTINUED.along of
// its font height along its text and CONTINUED.across of it across.
const OVERPRINT_HEIGHTS = 0.01;
// Heights within OVERPRINT_HEIGHTS of each other differ by at most -ln(0.99) = 0.01005 in logarithm, so they fall in the same
// band of this width or in neighbouring ones (overprintCopies looks in three).
const OVERPRINT_BAND = 0.0101;
const CONTINUED = { heights: 0.05, along: 0.25, across: 0.1 };
let characterCutter;

// Where each character of a text begins and ends, as [start, end] offsets covering the whole text: its extended grapheme
// clusters (a letter with its accents, a Hangul syllable written as jamo, an emoji sequence, a flag).
function characterSpans(value) {
  if (characterCutter === undefined) {
    characterCutter = typeof Intl === 'object' && typeof Intl.Segmenter === 'function'
      ? new Intl.Segmenter('en', { granularity: 'grapheme' }) : null;
  }
  const spans = [];
  if (characterCutter) {
    for (const { index, segment } of characterCutter.segment(value)) spans.push([index, index + segment.length]);
  } else {
    for (const match of value.matchAll(TEXT_UNIT)) spans.push([match.index, match.index + match[0].length]);
  }
  return spans;
}

// The items of one page that are overprint copies (R1), as a Set of their indexes: an item whose string, after NFKC, holds
// a character that is not white space and is the string (after NFKC) of an earlier item of the page - any earlier item -
// whose font height h, hypot(transform[2], transform[3]), agrees with its own within 1% (|h1 - h2| <= 0.01 x the larger),
// and whose origin (transform[4], transform[5]) lies at most max(1, 0.2 x h) PDF units from its own in a straight line, h
// being its own height: the same words drawn again a fraction of a point away, to look bold. An item without that
// geometry (a bare string) is never one, nor the earlier item of one. The cost is linear in the page's items: each looks
// only at the earlier items of its own string in 27 cells about its origin - its height's band (OVERPRINT_BAND) and the
// two beside it, each a 3 x 3 square of cells as wide as the page's largest reach, so every item within its own reach is
// in one of them. Known limit: a copy the library joins to the text beside it, or splits otherwise than its original, is
// no item of its own, and is not found.
function overprintCopies(items) {
  const entries = list(items);
  const drawn = [];
  let cell = 1;
  entries.forEach((item, index) => {
    const t = item && typeof item === 'object' && Array.isArray(item.transform) ? item.transform : null;
    if (!t || typeof item.str !== 'string' || ![t[2], t[3], t[4], t[5]].every(Number.isFinite)) return;
    const value = item.str.normalize('NFKC');
    const height = Math.hypot(t[2], t[3]);
    const reach = Math.max(1, 0.2 * height);
    if (!/\S/u.test(value) || !Number.isFinite(reach)) return;
    cell = Math.max(cell, reach);
    drawn.push({ index, value, x: t[4], y: t[5], height, reach });
  });
  const copies = new Set();
  // the earlier items of each string: string -> band -> column -> row -> items (a height of 0 is its own band, -Infinity)
  const byString = new Map();
  const into = (map, key) => {
    if (!map.has(key)) map.set(key, new Map());
    return map.get(key);
  };
  for (const item of drawn) {
    const bands = into(byString, item.value);
    const band = item.height > 0 ? Math.floor(Math.log(item.height) / OVERPRINT_BAND) : -Infinity;
    const column = Math.floor(item.x / cell);
    const row = Math.floor(item.y / cell);
    const near = other => Math.abs(item.height - other.height) <= OVERPRINT_HEIGHTS * Math.max(item.height, other.height)
      && Math.hypot(item.x - other.x, item.y - other.y) <= item.reach;
    let copy = false;
    for (const each of band === -Infinity ? [band] : [band - 1, band, band + 1]) {
      const columns = bands.get(each);
      for (let across = -1; columns && across <= 1 && !copy; across += 1) {
        const rows = columns.get(column + across);
        for (let down = -1; rows && down <= 1 && !copy; down += 1) copy = list(rows.get(row + down)).some(near);
      }
      if (copy) break;
    }
    if (copy) copies.add(item.index);
    const rows = into(into(bands, band), column);
    if (!rows.has(row)) rows.set(row, []);
    rows.get(row).push(item);
  }
  return copies;
}

// What R2b reads of an item's geometry: its transform (six finite numbers), its width (finite, above 0) and the lengths of
// its text direction (transform[0], transform[1]) and its up direction (transform[2], transform[3], its font height), or
// null where it has none of that (a bare string, as in tests).
function itemDrawing(item) {
  const t = item && typeof item === 'object' && Array.isArray(item.transform) ? item.transform : null;
  if (!t || t.length < 6 || !t.slice(0, 6).every(Number.isFinite) || !(Number.isFinite(item.width) && item.width > 0)) return null;
  const scale = Math.hypot(t[0], t[1]);
  const height = Math.hypot(t[2], t[3]);
  return scale > 0 && height > 0 && Number.isFinite(scale) && Number.isFinite(height) ? { t, width: item.width, scale, height } : null;
}

// Whether drawing `next` visibly continues drawing `first` (R2b): both have that geometry, their font heights agree within
// 5%, and the next one's origin, measured from the first one's, lies at the first one's end: along the first one's text
// direction (transform[0], transform[1], normalised) within 0.25 x its font height of its width, which the library gives
// as the advance along the text, rotated or not; across it (transform[2], transform[3], normalised) within 0.1 x its
// height. So a word drawn in two fonts ("pain" then a bold "less") stays one word, while a raised or smaller footnote
// marker, the jump back of fake bold and an overstrike glued after a line's end are not continuations.
function continuesDrawing(first, next) {
  const a = itemDrawing(first);
  const b = itemDrawing(next);
  if (!a || !b || Math.abs(a.height - b.height) > CONTINUED.heights * Math.max(a.height, b.height)) return false;
  const dx = b.t[4] - a.t[4];
  const dy = b.t[5] - a.t[5];
  const along = (dx * a.t[0] + dy * a.t[1]) / a.scale;
  const across = (dx * a.t[2] + dy * a.t[3]) / a.height;
  return Math.abs(along - a.width) <= CONTINUED.along * a.height && Math.abs(across) <= CONTINUED.across * a.height;
}

// One page's text, made ready to search. `items` are its text items in order: {str, transform, width, hasEOL} as the
// library reads them, or bare strings (an item that is neither counts as none). `joined` is their strings in order,
// overprint copies left out and format characters dropped, with a line break after every item marked hasEOL; for each
// UTF-16 unit of it, `itemOf` and `offsetOf` name the item and the offset in that item's own string it came from (-1 for
// a line break). `edges[p]` is 1 where place p of `joined` lies between the last character of one item and the first of
// the next item that gives a character, with nothing between them, and the next does not visibly continue the first
// (continuesDrawing): a word edge (R2b). It is cut into characters (characterSpans) and joined again wherever NFKC would
// combine two of them, so that NFKC of the text is exactly its characters' NFKC, in order; a character that folds to
// nothing (white space) is left out. `starts` and `ends` are each character's place in `joined`; `exact` and `blind` are
// the characters' folded text (NFKC, white space and format characters dropped) as written and lower-cased, character by
// character, each with the character every UTF-16 unit of it came from (`owner`); `copies` lists the overprint copies'
// item indexes.
function pageText(items) {
  const entries = list(items);
  const copies = overprintCopies(entries);
  const parts = [];
  const itemOf = [];
  const offsetOf = [];
  const take = (value, item, offset) => {
    parts.push(value);
    for (let unit = 0; unit < value.length; unit += 1) {
      itemOf.push(item);
      offsetOf.push(offset + unit);
    }
  };
  entries.forEach((entry, index) => {
    const value = typeof entry === 'string' ? entry : entry && typeof entry.str === 'string' ? entry.str : '';
    if (value && !copies.has(index)) {
      if (!FORMAT_CHARACTER.test(value)) {
        take(value, index, 0);
      } else {
        for (let at = 0; at < value.length;) {
          const size = value.codePointAt(at) > 0xffff ? 2 : 1;
          const point = value.slice(at, at + size);
          if (!FORMAT_CHARACTER.test(point)) take(point, index, at);
          at += size;
        }
      }
    }
    if (entry && typeof entry === 'object' && entry.hasEOL === true) take('\n', -1, -1);
  });
  const joined = parts.join('');
  const edges = new Uint8Array(joined.length + 1);
  for (let at = 1; at < joined.length; at += 1) {
    const before = itemOf[at - 1];
    const after = itemOf[at];
    if (before >= 0 && after >= 0 && before !== after && !continuesDrawing(entries[before], entries[after])) edges[at] = 1;
  }
  const nfkc = value => value.normalize('NFKC');
  const cuts = [];
  for (const span of characterSpans(joined)) {
    const last = cuts[cuts.length - 1];
    // nothing below U+0300 is combined by NFKC with what comes before it
    if (last && joined.codePointAt(span[0]) >= 0x300) {
      const before = joined.slice(last[0], last[1]);
      const after = joined.slice(span[0], span[1]);
      if (nfkc(before + after) !== nfkc(before) + nfkc(after)) {
        last[1] = span[1];
        continue;
      }
    }
    cuts.push([span[0], span[1]]);
  }
  // Until NFKC of the characters, in order, is NFKC of the whole text, the characters around the first place they differ
  // are joined into one; the text as one character always agrees.
  const whole = nfkc(joined);
  const folded = cuts.map(([start, end]) => nfkc(joined.slice(start, end)));
  while (cuts.length > 1 && folded.join('') !== whole) {
    let at = 0;
    let index = 0;
    while (index < folded.length - 1 && whole.startsWith(folded[index], at)) {
      at += folded[index].length;
      index += 1;
    }
    const from = Math.max(0, index - 1);
    const to = Math.min(cuts.length - 1, index + 1);
    cuts.splice(from, to - from + 1, [cuts[from][0], cuts[to][1]]);
    folded.splice(from, to - from + 1, nfkc(joined.slice(cuts[from][0], cuts[from][1])));
  }
  const starts = [];
  const ends = [];
  const exact = [];
  const blind = [];
  cuts.forEach(([start, end], index) => {
    const value = folded[index].replace(UNFOLDED, '');
    if (!value) return;
    starts.push(start);
    ends.push(end);
    exact.push(value);
    blind.push(value.toLowerCase());
  });
  const owned = values => {
    const text = values.join('');
    const owner = new Int32Array(text.length);
    let at = 0;
    values.forEach((value, index) => {
      owner.fill(index, at, at + value.length);
      at += value.length;
    });
    return { text, owner };
  };
  return { joined, itemOf: Int32Array.from(itemOf), offsetOf: Int32Array.from(offsetOf), edges, starts: Int32Array.from(starts),
    ends: Int32Array.from(ends), exact: owned(exact), blind: owned(blind), copies: [...copies].sort((a, b) => a - b) };
}

// The pieces of the items' strings that character `index` of a page's text (pageText) is made of: [{item, start, end}]
// in each item's own offsets (an accent the PDF draws in another font is an item of its own, and a piece of the letter
// before it).
function characterPieces(text, index) {
  const pieces = [];
  for (let unit = text.starts[index]; unit < text.ends[index]; unit += 1) {
    const item = text.itemOf[unit];
    if (item < 0) continue;
    const last = pieces[pieces.length - 1];
    if (last && last.item === item) last.end = text.offsetOf[unit] + 1;
    else pieces.push({ item, start: text.offsetOf[unit], end: text.offsetOf[unit] + 1 });
  }
  return pieces;
}

// One page's characters, one by one: {pieces, folded} (pageText, characterPieces).
function pageCharacters(items) {
  const text = pageText(items);
  const folded = Array.from(text.starts, () => '');
  for (let at = 0; at < text.exact.text.length; at += 1) folded[text.exact.owner[at]] += text.exact.text[at];
  return folded.map((value, index) => ({ pieces: characterPieces(text, index), folded: value }));
}

// The code point of a text that ends at UTF-16 offset `at` ({point, size}), or null at the text's start.
function pointBefore(value, at) {
  if (at <= 0) return null;
  const unit = value.charCodeAt(at - 1);
  const high = at >= 2 ? value.charCodeAt(at - 2) : 0;
  return unit >= 0xdc00 && unit <= 0xdfff && high >= 0xd800 && high <= 0xdbff ? { point: value.codePointAt(at - 2), size: 2 } : { point: unit, size: 1 };
}

// The code point of a text that begins at UTF-16 offset `at` ({point, size}), or null at the text's end.
function pointAt(value, at) {
  if (at >= value.length) return null;
  const point = value.codePointAt(at);
  return { point, size: point > 0xffff ? 2 : 1 };
}

// R2 with R2c: a code point that joins a word on the page (a letter, a digit or a mark, but not a Han ideograph or a
// hiragana character).
function wordPart(point) {
  const character = String.fromCodePoint(point);
  return WORD_PART.test(character) && !OWN_WORD.test(character);
}

function isDigit(point) {
  return DIGIT.test(String.fromCodePoint(point));
}

// What a quote asks of the page at its two ends (its folded characters as R2 reads them - NFKC, white space and format
// characters dropped - each asked by its first code point): `start` and `end`, a word edge where that character is a
// letter or a digit other than a Han ideograph or a hiragana character (R2, R2c); `startDigit` and `endDigit`, where it is
// a digit, and `startSeparated` and `endSeparated`, where it is a number separator with a digit inside the quote next to
// it (R2a).
function quoteEdges(wanted) {
  const { text, owner } = wanted.exact;
  const ends = { start: false, end: false, startDigit: false, endDigit: false, startSeparated: false, endSeparated: false };
  if (!text) return ends;
  const firsts = [];
  for (let at = 0; at < text.length; at += 1) {
    if (at === 0 || owner[at] !== owner[at - 1]) firsts.push(text.codePointAt(at));
  }
  const edge = point => WORD_EDGE.test(String.fromCodePoint(point)) && !OWN_WORD.test(String.fromCodePoint(point));
  const [first, second] = firsts;
  const last = firsts[firsts.length - 1];
  const beforeLast = firsts.length > 1 ? firsts[firsts.length - 2] : undefined;
  return { start: edge(first), end: edge(last), startDigit: isDigit(first), endDigit: isDigit(last),
    startSeparated: NUMBER_SEPARATORS.has(first) && second !== undefined && isDigit(second),
    endSeparated: NUMBER_SEPARATORS.has(last) && beforeLast !== undefined && isDigit(beforeLast) };
}

// Whether an occurrence whose first character is character `index` of a page's text (side 'before'), or whose last is
// ('after'), meets a word edge there, as the quote asks (`edges`, quoteEdges), read in the page's joined text as the page
// writes it (not after NFKC): R2b first - two drawings that do not continue each other meet at an edge; else R2 (with
// R2c) - where the quote's end asks for an edge, the code point beside the occurrence may not join a word (the page's
// start and end are edges); then R2a - a digit with a number separator and another digit beyond it, or a separator ending
// the quote with a digit beyond it, means the occurrence sits inside a number. Reading stops at an R2b edge: a code point
// on its far side counts as none.
function keepsEdge(text, index, side, edges) {
  const { joined } = text;
  if (side === 'before') {
    const at = text.starts[index];
    if (text.edges[at]) return true;
    const one = pointBefore(joined, at);
    if (!one) return true;
    if (edges.start && wordPart(one.point)) return false;
    if (edges.startDigit && NUMBER_SEPARATORS.has(one.point)) {
      const two = text.edges[at - one.size] ? null : pointBefore(joined, at - one.size);
      if (two && isDigit(two.point)) return false;
    }
    return !(edges.startSeparated && isDigit(one.point));
  }
  const at = text.ends[index];
  if (text.edges[at]) return true;
  const one = pointAt(joined, at);
  if (!one) return true;
  if (edges.end && wordPart(one.point)) return false;
  if (edges.endDigit && NUMBER_SEPARATORS.has(one.point)) {
    const two = text.edges[at + one.size] ? null : pointAt(joined, at + one.size);
    if (two && isDigit(two.point)) return false;
  }
  return !(edges.endSeparated && isDigit(one.point));
}

// Where `needle` occurs in the folded text of runs of pages ([{number, text}], their texts joined in order), left to
// right without overlap, as [{first, last}], each [run, character]. A place that would begin or end inside a character is
// none; so is one that does not meet a word edge at both ends as its quote asks (`edges`: quoteEdges, keepsEdge; each end
// read in the text of its own page). Past a place that is none, the search goes on from its next unit.
function foldedOccurrences(runs, needle, caseBlind, edges) {
  const found = [];
  if (!needle || !runs.length) return found;
  const parts = runs.map(run => (caseBlind ? run.text.blind : run.text.exact));
  const hay = parts.map(part => part.text).join('');
  const offsets = [];
  let total = 0;
  for (const part of parts) {
    offsets.push(total);
    total += part.text.length;
  }
  const ownerAt = at => {
    let low = 0;
    let high = offsets.length - 1;
    while (low < high) {
      const middle = (low + high + 1) >> 1;
      if (offsets[middle] <= at) low = middle;
      else high = middle - 1;
    }
    return [low, parts[low].owner[at - offsets[low]]];
  };
  const same = (a, b) => a[0] === b[0] && a[1] === b[1];
  let from = 0;
  for (let at = hay.indexOf(needle); at >= 0; at = hay.indexOf(needle, from)) {
    const end = at + needle.length;
    const first = ownerAt(at);
    const last = ownerAt(end - 1);
    const whole = (at === 0 || !same(ownerAt(at - 1), first)) && (end === hay.length || !same(ownerAt(end), last));
    if (whole && (!edges || (keepsEdge(runs[first[0]].text, first[1], 'before', edges) && keepsEdge(runs[last[0]].text, last[1], 'after', edges)))) {
      found.push({ first, last });
      from = end;
    } else {
      from = at + 1;
    }
  }
  return found;
}

// Where one quote is marked: {page, pageCount, status, scope, caseBlind, count, pages, marks, textless}. `texts` holds the
// text items of every page (texts[p - 1] for page p, as pageText takes them; null for a page not read), and its length is
// the document's page count; `prepared`, a Map from page number to pageText, keeps each page's prepared text for the next
// quote (one per document). status: 'marked', 'not_found', 'missing_page' (the quote names a page the document does not
// have) or 'empty' (no character to look for); scope: 'page', 'continued' (from the quote's page onto the next) or
// 'document' (a quote with no page); textless (not found only): the quote's page - for a quote with no page, every page -
// was read and has no character to search (a scanned page). marks[p] lists, in reading order, {item, start, end,
// occurrence}: what of item `item`'s own string is marked on page p, and which occurrence (0, 1, ...) it is part of;
// pages lists the pages that hold a mark.
function locateQuote(quote, texts, prepared = null) {
  const pages = list(texts);
  const page = quotePage(quote);
  const result = { page, pageCount: pages.length, status: 'not_found', scope: page ? 'page' : 'document', caseBlind: false,
    count: 0, pages: [], marks: {}, textless: false };
  const wanted = pageText([typeof quote?.text === 'string' ? quote.text : '']);
  if (!wanted.exact.text) return { ...result, status: 'empty' };
  if (page && page > pages.length) return { ...result, status: 'missing_page' };
  const kept = prepared instanceof Map ? prepared : new Map();
  const read = number => {
    if (!kept.has(number)) {
      const items = pages[number - 1];
      if (!Array.isArray(items)) return null;
      kept.set(number, pageText(items));
    }
    return kept.get(number);
  };
  const edges = quoteEdges(wanted);
  const search = (numbers, keep) => {
    const runs = numbers.map(number => ({ number, text: read(number) })).filter(run => run.text);
    for (const caseBlind of [false, true]) {
      const found = foldedOccurrences(runs, caseBlind ? wanted.blind.text : wanted.exact.text, caseBlind, edges)
        .filter(({ first, last }) => keep(runs[first[0]].number, runs[last[0]].number));
      if (found.length) return { runs, found, caseBlind };
    }
    return null;
  };
  let hit;
  if (!page) {
    hit = search(pages.map((_, index) => index + 1), () => true);
  } else {
    hit = search([page], () => true);
    if (!hit && page < pages.length) {
      hit = search([page, page + 1], (first, last) => first === page && last === page + 1);
      if (hit) result.scope = 'continued';
    }
  }
  if (!hit) {
    const searched = (page ? [page] : pages.map((_, index) => index + 1)).map(read);
    return { ...result, textless: searched.length > 0 && searched.every(text => text !== null && !text.exact.text) };
  }
  const marks = {};
  hit.found.forEach(({ first, last }, occurrence) => {
    let open = null;
    for (let run = first[0]; run <= last[0]; run += 1) {
      const { number, text } = hit.runs[run];
      const to = run === last[0] ? last[1] : text.starts.length - 1;
      for (let index = run === first[0] ? first[1] : 0; index <= to; index += 1) {
        for (const piece of characterPieces(text, index)) {
          if (open && open.page === number && open.item === piece.item) {
            open.end = piece.end;
          } else {
            open = { page: number, item: piece.item, start: piece.start, end: piece.end, occurrence };
            (marks[number] ||= []).push(open);
          }
        }
      }
    }
  });
  const marked = Object.keys(marks).map(Number).sort((a, b) => a - b);
  for (const number of marked) marks[number] = marks[number].map(({ item, start, end, occurrence }) => ({ item, start, end, occurrence }));
  return { ...result, status: 'marked', caseBlind: hit.caseBlind, count: hit.found.length, pages: marked, marks };
}

function pagesText(numbers) {
  return numbers.length === 1 ? `page ${numbers[0]}` : `pages ${joinWords(numbers.map(String))}`;
}

// What the note under the viewer says of one quote chosen in a PDF. Where nothing is found, it says what was searched:
// the searchable text of the page (or the document), or - where the page has none - that it has none.
function markNote(result) {
  const { page, status, scope, count, pages, textless } = record(result);
  if (status === 'marked') {
    if (scope === 'continued') {
      return count === 1 ? `Marked on page ${page}, continuing onto page ${page + 1}.`
        : `These words appear ${count} times, starting on page ${page} and continuing onto page ${page + 1}. Each is marked.`;
    }
    if (scope === 'page') return count === 1 ? `Marked on page ${page}.` : `These words appear ${count} times on page ${page}. Each is marked.`;
    return count === 1 ? `Marked on ${pagesText(list(pages))}.` : `These words appear ${count} times, on ${pagesText(list(pages))}. Each is marked.`;
  }
  if (status === 'missing_page') return `This passage names page ${page}, but the document has ${plural(record(result).pageCount, 'page', 'pages')}. Nothing is marked.`;
  if (status === 'empty') return 'This passage has no words to mark.';
  if (textless === true) {
    return page ? `Page ${page} has no text the viewer can search (it may be a scanned image), so nothing is marked. Page ${page} is shown.`
      : 'This document has no text the viewer can search (it may be a scanned image), so nothing is marked.';
  }
  return page ? `The exact words were not found in the searchable text of page ${page}, so nothing is marked. Page ${page} is shown.`
    : 'The exact words were not found in the searchable text of this document, so nothing is marked.';
}

// The note when the PDF is shown by the browser's own viewer, which can open a page but not mark words on it: why, then
// the quote's page (never what the frame shows). 'browser' - this browser lacks what marking needs (pdfCapable);
// 'library' - the PDF library or its worker did not load or start, or not within the time limit, or its worker failed,
// or, once the document had opened, the library has not answered for 20 seconds while the viewer waited on it (its
// watchdog); 'document' - the library refuses the document, finds no page in it, or fails on a page's drawing or text;
// 'slow' - the download stopped moving before the document opened; 'download' - the download failed (an answer that is
// not 2xx, a fetch that failed, a body that broke off).
const FRAME_REASONS = {
  browser: 'Marking needs a newer browser.',
  library: 'The marking tool did not work here, so nothing is marked.',
  document: 'This document cannot be drawn here, so nothing is marked.',
  slow: 'The document took too long to load here, so nothing is marked.',
  download: 'The document could not be downloaded for marking, so nothing is marked.',
};

function frameNote(page, reason) {
  const said = lookup(FRAME_REASONS, reason, FRAME_REASONS.document);
  return page ? `${said} The quote is on page ${page}.` : said;
}

// The note for a passage of a text document, found by the text rule (findPassages).
function textMarkNote(count) {
  if (!count) return 'The exact words could not be found in the document, so nothing is marked.';
  return count === 1 ? 'Marked in the document.' : `These words appear ${count} times in the document. Each is marked.`;
}

// --- the customer contract, read defensively ---------------------------------------

function canReview(doc) {
  return doc?.permissions?.can_review === true;
}

function stateLabel(stateName, label) {
  return lookup(STATE_LABELS, stateName, text(label) || 'Unknown');
}

// Every code the page can show, one row per line of the coding review, in the served order.
function codesOf(doc) {
  return objects(doc?.codes).filter(code => text(code.code));
}

// The line a code row stands on, or '' when the server named none the page can use. Given the document, also '' when
// the same line is named on two of its rows: the page cannot tell which one a decision is about, so it decides neither.
function lineOf(code, doc) {
  const line = typeof code?.line === 'string' && LINE.test(code.line) ? code.line : '';
  if (!line || doc === undefined) return line;
  return codesOf(doc).filter(item => item.line === line).length === 1 ? line : '';
}

// The number of the coding review the page shows: what every decision names, so the server can refuse one made on a
// coding review that is no longer the latest.
function roundNumber(doc) {
  const number = doc?.round?.number;
  return Number.isInteger(number) && number > 0 ? number : null;
}

// What names a row on the page (its ids, its quotes): its line; only a row without one falls back to its place.
function rowRef(code, position, doc) {
  return lineOf(code, doc) || `row-${position + 1}`;
}

// The one row on `line` of the coding review the page shows, or null (no row, or more than one).
function findLine(doc, line) {
  const wanted = typeof line === 'string' && LINE.test(line) ? line : '';
  const rows = wanted ? codesOf(doc).filter(code => lineOf(code) === wanted) : [];
  return rows.length === 1 ? rows[0] : null;
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

// The id of the decision that stands on a row, exactly as served, or '' when there is none the page can name.
function decisionId(code) {
  const id = currentDecision(code)?.id;
  return typeof id === 'string' && DECISION_ID.test(id) ? id : '';
}

// What the badge says: the decision once one stands (Approved, Rejected), else the code's status.
function shownStatus(code) {
  const decision = currentDecision(code);
  if (!decision) return codeStatus(code);
  const [key, label, tone, iconName] = DECISIONS[decision.action];
  return { key, label, tone, icon: iconName };
}

function unitsLabel(units) {
  return Number.isInteger(units) && units >= 0 ? plural(units, 'unit', 'units') : UNITS_NOT_GIVEN;
}

// A row's modifiers as served: a list of strings ([] when the coding review says there is none), or null when it gave
// none the page can state - the contract's null, or anything that is not a list of modifiers, which is shown as not
// given and never read as "none".
function modifiersOf(code) {
  const modifiers = code?.modifiers;
  if (!Array.isArray(modifiers) || modifiers.some(item => typeof item !== 'string' || !item.trim())) return null;
  return modifiers.map(item => item.trim());
}

function modifiersLabel(code) {
  const modifiers = modifiersOf(code);
  if (modifiers === null) return MODIFIERS_NOT_GIVEN;
  if (!modifiers.length) return 'No modifier';
  return `${modifiers.length === 1 ? 'Modifier' : 'Modifiers'} ${modifiers.join(', ')}`;
}

// The line as the review dialog states it: its units and its modifiers, so two lines of one code read apart.
function lineDetail(code) {
  return `${unitsLabel(code?.units)} · ${modifiersLabel(code)}`;
}

// The second check's verdict on one code, and its reason as written. Without a verdict the server's reason opens with
// its own sentence ("The second check did not review this code.", or "The second check did not give a clear verdict."
// before the review's own reason), which is then the whole line, shown as given.
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

// One quoted passage of one row: the row's line (its place, for a row without one) and the passage's place in it.
function quoteKey(code, index, position, doc) {
  return `${rowRef(code, position, doc)}#${index}`;
}

// The viewer's address for one page of the original (the browser's own PDF viewer, where the page cannot draw the PDF
// itself, opens at #page=N), or the plain view address.
function viewerUrl(viewUrl, page) {
  const base = safeViewUrl(viewUrl);
  if (!base) return '';
  return Number.isInteger(page) && page > 0 ? `${base}#page=${page}` : base;
}

// What the in-page viewer shows, as the server says in document.view_media_type (never read from media_type, the type
// of the original): 'pdf' (the PDF of view_url drawn in the page, a quoted passage marked on its page; for a Word
// document the PDF the coding review read), 'text' (the text, where a quoted passage is marked) or 'none' (no viewer,
// only the download).
function viewerKind(documentPart) {
  const part = record(documentPart);
  if (!safeViewUrl(part.view_url)) return 'none';
  return lookup(VIEW_KINDS, part.view_media_type, 'none');
}

// The decision buttons one row gets: those the server allows, for a member who may review, in a fixed order - and none
// for a row the page cannot name by its line, or on a page that does not know which coding review it shows; no Undo of
// a decision the page cannot name by its id.
function allowedActions(code, doc) {
  if (!canReview(doc) || !lineOf(code, doc) || roundNumber(doc) === null) return [];
  const allowed = list(code?.allowed_actions);
  return ACTION_BUTTONS.filter(([name]) => allowed.includes(name) && (name !== 'revoke' || decisionId(code)))
    .map(([name]) => name);
}

// What a decision on one row names: the coding review the page shows, the row's line and its code as served, and the
// decision that stands on it (its id: what an Undo undoes).
function decisionTarget(code, doc) {
  return { round: roundNumber(doc), line: lineOf(code, doc), code: typeof code?.code === 'string' ? code.code : '',
    decision: decisionId(code) };
}

// The body of POST decisions: {round, line, code, action, acknowledgement, note}, and for an Undo the decision it undoes
// ({..., decision}).
function decisionBody(target, action, acknowledgement = '', note = '') {
  const named = record(target);
  return {
    round: named.round, line: named.line, code: named.code, action,
    acknowledgement: action === 'approve' && typeof acknowledgement === 'string' ? acknowledgement : '',
    note: action === 'revoke' ? '' : text(note),
    ...(action === 'revoke' ? { decision: typeof named.decision === 'string' ? named.decision : '' } : {}),
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
  if (parts.length) return parts.join(' · ');
  return progressPhase(doc) === 'done' && !isBusy(doc) ? 'No codes found' : 'No codes yet';
}

// Whether the page offers the export dialog: whenever the server allows a download (a draft once the coding review has
// finished, codes or none; the approved download once a code is approved), or there are downloads made earlier to list.
function exportOffered(doc) {
  const readiness = record(doc?.readiness);
  return readiness.draft === true || readiness.approved === true || objects(doc?.reports).length > 0;
}

// The PDF is the report for the doctor, and the only one made (the export dialog).
function readinessText(doc) {
  const readiness = record(doc?.readiness);
  if (readiness.approved === true) return 'The approved report can be downloaded as a PDF. It lists only approved codes.';
  if (readiness.draft === true) return 'You can download the draft report as a PDF. Approve codes to download the approved report.';
  return 'Downloads become available when the coding review finishes.';
}

function exportStatusText(doc) {
  const readiness = record(doc?.readiness);
  const blockers = strings(readiness.blockers);
  if (readiness.approved === true) return 'At least one code is approved. The approved report lists only approved codes, with who approved them and when.';
  const head = readiness.draft === true ? 'Draft only: the codes are the coding review\'s, not approvals.' : 'Nothing can be downloaded yet.';
  return blockers.length ? `${head} Before the approved report: ${blockers.join(' ')}` : head;
}

function emptyCodesText(doc) {
  if (isBusy(doc)) return 'Codes appear here when the coding review finishes.';
  const phase = progressPhase(doc);
  if (phase === 'failed') return 'No codes: the coding review could not finish.';
  if (phase === 'stopped') return 'No codes: the coding review was stopped before it finished.';
  if (phase === 'earlier') return 'Codes appear here once the document is reviewed again with the current version.';
  return 'The coding review found no CPT code to report for this document.';
}

// A row's name as the part of an element id: letters and digits only.
function rowKey(value) {
  return String(value ?? '').replace(/[^A-Za-z0-9]/g, '_');
}

// --- rendering (pure string builders) ----------------------------------------------

const state = {
  session: null, route: null, routeSerial: 0, doc: null, docKey: '', viewerKey: '', selectedQuote: '',
  poll: { timer: 0, count: 0, errors: 0 }, tickTimer: 0, clock: 0, reconnecting: false, outdated: false,
  // exporting: what the export dialog was opened on (the document, its coding review and that read of it); making: the
  // file being made ({encounter, kind, fmt}) while its request runs; made: the file just made, whose option waits a moment
  // (madeTimer), and madeRead the read that releases it; rereading: the document the page reads again after a download
  // of it was refused because it changed, and rereadAfter the number of the last read asked before that refusal
  upload: { file: null, paste: false, busy: false, key: '' }, ack: null, review: null, exporting: null, making: null,
  made: null, madeTimer: 0, madeRead: null, rereading: null, rereadAfter: 0,
  // the reads of the document, numbered in the order the page asked for them, and the number of the latest one shown
  reads: { asked: 0, applied: 0 },
  open: new Set(), answers: new Map(), pending: new Set(), toastTimer: 0, leaving: false,
  // the PDF viewer of the document shown (browser wiring), the PDF library once it is asked for and how many times it has
  // been asked for (a failed load is tried again at fresh addresses), and the passage of a text document being marked
  viewer: null, pdfLibrary: null, pdfAttempt: 0, framePassage: null,
  // release 1: what the confirmation dialog runs on Continue (askConfirm), and the object addresses the page made, which
  // it lets go of when it signs out (clearScreen)
  confirming: null, objectUrls: new Set(),
  // release 2: the session's last read (R2-17); the worker made ready ahead (R2-10); whether a worker started (R2-12)
  sessionReadAt: 0, standbyOn: false, standbyFails: 0, pdfStandby: null, standbyTimer: 0, standbyFrame: 0, standbyIdle: 0, pdfStarted: false,
  // the PDFs kept for a re-open, oldest view first (R2-15); the click's early view and the list's hints (R2-16); the
  // ends that spare no view (forgetMemory, R2-18): a document opening across one keeps no copy
  keptViews: new Map(), early: null, viewHints: new Map(), wipes: 0,
  // the list on the page (R2-22)
  list: null,
};

function uiState(overrides = {}) {
  return { open: state.open, answers: state.answers, ack: state.ack, reconnecting: state.reconnecting, nowMs: Date.now(), clock: state.clock, ...overrides };
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
  const empty = { workspace: 'No documents yet. Start with a synthetic document.', documents: 'No documents yet. Use New document to upload a synthetic document or paste its text.', queue: 'Nothing is waiting for you.' }[name];
  return LIST_HEADER + (shown.length ? shown.map(row => documentRow(row)).join('') : `<p class="empty-state">${escapeHtml(empty)}</p>`);
}

// R2-22: a page of a list - its rows, the next page's place (null on the last), the list's size (a first page's) - or
// release 1's whole list; anything else is refused.
function listPage(data) {
  const whole = Array.isArray(data);
  const rows = whole ? data : data?.encounters;
  const next = whole ? null : data?.next ?? null;
  const total = whole ? null : data?.total ?? null;
  const workspace = whole ? null : data?.workspace ?? null;
  if (!Array.isArray(rows) || (next !== null && typeof next !== 'string') || (total !== null && !(Number.isInteger(total) && total >= 0))
    || (workspace !== null && typeof workspace !== 'string')) {
    throw new ApiError('The server answered with a document list this page cannot read.');
  }
  return { rows: objects(rows), next: next || null, total, workspace };
}

// The list's description for `count` documents.
function listDescription(name, count) {
  if (name === 'queue') {
    return count ? `${count === 1 ? 'One document waits' : `${count} documents wait`} on you: questions to answer, or codes to review or approve.` : 'No document waits on you for an answer or a decision.';
  }
  return `${plural(count, 'synthetic document', 'synthetic documents')} in this workspace.`;
}

function inviteMarkup(rows) {
  const recent = rows?.[0];
  if (rows === null) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>Loading recent documents…</strong><p>One moment.</p></span>`;
  if (!recent) return `<span class="sample-icon">${icon('file')}</span><span class="sample-text"><strong>No documents yet</strong><p>Upload a synthetic document to see its CPT codes beside the source.</p></span><button type="button" class="button secondary" data-action="upload">New document ${icon('plus')}</button>`;
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
  return `<section class="view-entrance"><div class="heading-row documents-heading"><div><span class="eyebrow">${queue ? 'WHAT WAITS ON YOU' : 'THE ORIGINAL, ALWAYS IN VIEW'}</span><h1>${queue ? 'Review queue.' : 'Your documents.'}</h1><p>${queue ? 'Questions to answer and codes to review or approve: each document shows its next step.' : 'Keep source notes, supporting evidence and coding decisions together.'}</p></div><div class="heading-actions"><button type="button" class="button primary" data-action="upload">${icon('plus')}New document</button></div></div><p class="section-description" id="listDescription">Loading…</p>${queue ? '' : `<label class="search-field list-search">${icon('search')}<input id="documentSearch" aria-label="Search documents" placeholder="Search documents…" autocomplete="off"></label>`}<div class="document-list" id="documentsTable">${LIST_HEADER}<p class="empty-state">Loading documents…</p></div><div class="list-more" id="listMore" hidden></div><p class="checks-disclaimer">${queue ? 'A document that is still being processed is not listed here; it appears once it needs you.' : 'Synthetic documents only. Each decision is tied to the coding review it was made on.'}</p></section>`;
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
  const download = exportOffered(doc) ? `<button type="button" class="button secondary" data-action="export">${icon('download')}<span>Download</span></button>` : '';
  return `<div class="heading-row review-heading"><div><span class="eyebrow">${escapeHtml(specialtyEyebrow())}</span><h1>${escapeHtml(text(doc?.title) || 'Untitled document')}</h1><div class="review-meta">${reviewMeta(doc)}</div></div><div class="heading-actions"><button type="button" class="button secondary" data-action="upload">${icon('plus')}<span>New document</span></button>${download}</div></div>`;
}

// --- the original document and its quoted passages (left) ---

function documentName(part) {
  return text(part.name) || (part.kind === 'paste' ? 'Pasted text' : 'Original document');
}

// The viewer of the original, #documentViewer, which keeps the view address in data-view-url: for a PDF (or the PDF a Word
// document was converted to) a scrolling region the page draws the PDF's pages in (the browser wiring below; where that
// cannot run, the browser's own viewer in a frame), with the page shown in the toolbar and the zoom beside it (shown once
// the pages are drawn); for a text an iframe of the text. The toolbar's file name carries its full text as its title too
// (it is cut short where the toolbar is narrow).
// Under it, the note that says what choosing a quote marked (a polite live region), then the note when the PDF is the one
// a Word document was converted to. With no view, no viewer at all and only the "Download original" link.
function viewerPanel(doc) {
  const part = record(doc?.document);
  const kind = viewerKind(part);
  const name = documentName(part);
  const view = viewerUrl(part.view_url, null);
  const original = safeOriginalUrl(part.original_url);
  const label = escapeHtml(`Original document: ${name}`);
  let frame = '';
  if (kind === 'pdf') {
    frame = `<div id="documentViewer" class="viewer-frame pdf-viewer" data-view-url="${escapeHtml(view)}" role="region" aria-label="${label}" tabindex="0"><p class="pdf-status">Opening the document…</p></div>`;
  } else if (kind === 'text') {
    frame = `<iframe id="documentViewer" class="viewer-frame" src="${escapeHtml(view)}" data-view-url="${escapeHtml(view)}" title="${label}" referrerpolicy="same-origin"></iframe>`;
  }
  const marked = kind === 'none' ? '' : '<p class="viewer-mark" id="viewerMark" role="status" aria-live="polite"></p>';
  const page = kind === 'pdf' ? '<span class="viewer-page" id="viewerPage"></span>' : '';
  const zoom = kind === 'pdf' ? '<span class="viewer-zoom" id="viewerZoom" role="group" aria-label="Zoom" hidden>'
    + '<button type="button" class="zoom-button" data-zoom="out" aria-label="Zoom out" title="Zoom out">−</button>'
    + '<span class="zoom-level" id="zoomLevel" aria-live="polite">100%</span>'
    + '<button type="button" class="zoom-button" data-zoom="in" aria-label="Zoom in" title="Zoom in">+</button>'
    + '<button type="button" class="zoom-button zoom-fit" data-zoom="fit">Fit width</button></span>' : '';
  const note = kind === 'pdf' && part.converted === true ? `<p class="viewer-note">${icon('info')}<span>${escapeHtml(CONVERTED_NOTE)}</span></p>` : '';
  const meta = [lookup(KIND_LABELS, part.kind, ''), Number.isInteger(part.size) && part.size > 0 ? formatSize(part.size) : ''].filter(Boolean).join(' · ');
  const download = original ? downloadLinks(part) : '';
  return `<section class="viewer-panel${kind === 'none' ? ' no-view' : ''}" aria-labelledby="viewerTitle"><div class="viewer-toolbar">${icon('file')}<h2 id="viewerTitle">Original document</h2><span class="viewer-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>${page}${zoom}</div>${frame}${marked}${note}<div class="viewer-bottom"><span>${escapeHtml(meta || 'Original as received')}</span>${download}</div></section>`;
}

function quoteBody(quote) {
  return `<q class="quote-text">${escapeHtml(quote.text)}</q><span class="quote-page">${quote.page ? escapeHtml(`Page ${quote.page}`) : ''}</span>`;
}

function quotesLead(doc) {
  const kind = viewerKind(doc?.document);
  if (kind === 'pdf') return 'Each code rests on these passages. Choose one to open its page and mark its words there.';
  if (kind === 'text') return 'Each code rests on these passages. Choose one to mark it in the document.';
  return 'Each code rests on these passages of the original document.';
}

// The hint a quoted passage carries, where the viewer can show it.
function quoteTitle(doc) {
  return ['pdf', 'text'].includes(viewerKind(doc?.document)) ? ' title="Show this passage in the document"' : '';
}

function quotesPanel(doc) {
  const entries = codesOf(doc).flatMap((code, position) => quotesOf(code).map((quote, index) => ({ code, quote, index, position })));
  const items = entries.map(({ code, quote, index, position }) => `<li><button type="button" class="quote" data-code="${escapeHtml(code.code)}" data-line="${escapeHtml(lineOf(code, doc))}" data-page="${quote.page ?? ''}" data-quote="${escapeHtml(quoteKey(code, index, position, doc))}"${quoteTitle(doc)}><span class="quote-code">${escapeHtml(code.code)}</span>${quoteBody(quote)}</button></li>`).join('');
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

// One decision button of one row: named by the row's line (its id and data-line), with the code it decides.
function decisionButton(action, code, position, doc) {
  const [, kind, label, iconName] = ACTION_BUTTONS.find(([name]) => name === action);
  return `<button type="button" class="button ${kind}" id="act-${rowKey(rowRef(code, position, doc))}-${action}" data-decision="${action}" data-code="${escapeHtml(code.code)}" data-line="${escapeHtml(lineOf(code, doc))}">${label}${iconName ? ` ${icon(iconName)}` : ''}</button>`;
}

function codeQuotes(code, doc, position) {
  const quotes = quotesOf(code);
  if (!quotes.length) return '<p class="code-quotes code-quotes-empty">No passage of the document is quoted for this code.</p>';
  return `<ul class="code-quotes" aria-label="${escapeHtml(`Passages quoted for ${code.code}`)}">${quotes.map((quote, index) => `<li><button type="button" class="code-quote" data-quote="${escapeHtml(quoteKey(code, index, position, doc))}" data-view-page="${quote.page ?? ''}"${quoteTitle(doc)}>${quoteBody(quote)}</button></li>`).join('')}</ul>`;
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

// One row: one line of the coding review (`position` is its place in the served list, which names only a row the server
// gave no line).
function codeRow(code, doc, position = 0) {
  const status = shownStatus(code);
  const decision = currentDecision(code);
  const check = secondCheck(code);
  const question = text(code.question);
  const actions = allowedActions(code, doc);
  return `<li class="code-row" id="code-${rowKey(rowRef(code, position, doc))}" tabindex="-1" data-code="${escapeHtml(code.code)}" data-line="${escapeHtml(lineOf(code, doc))}" data-status="${escapeHtml(codeStatus(code).key)}"${decision ? ` data-decision="${escapeHtml(decision.action)}"` : ''} data-units="${escapeHtml(Number.isInteger(code.units) && code.units >= 0 ? code.units : '')}" data-modifiers="${escapeHtml((modifiersOf(code) || []).join(' '))}">`
    + `<div class="code-head"><span class="code-number">${escapeHtml(code.code)}</span><span class="code-units">${escapeHtml(unitsLabel(code.units))}</span><span class="code-modifiers">${escapeHtml(modifiersLabel(code))}</span>${badge(status.tone, status.label, status.icon, ` data-status="${escapeHtml(status.key)}"`)}</div>`
    + `<p class="code-reason">${escapeHtml(text(code.reason) || 'No reason was given for this code.')}</p>`
    + `<p class="code-check" data-check="${check.verdict}">${icon(check.verdict === 'agrees' ? 'circle-check' : 'info')}<span><strong>${escapeHtml(check.label)}</strong>${check.reason ? ` ${escapeHtml(check.reason)}` : ''}</span></p>`
    + (question ? `<p class="code-question">${icon('help')}<span>${escapeHtml(question)}</span></p>` : '')
    + codeQuotes(code, doc, position)
    + decisionLine(code)
    + codeHint(code)
    + (actions.length ? `<div class="code-actions">${actions.map(action => decisionButton(action, code, position, doc)).join('')}</div>` : '')
    + '</li>';
}

function reviewBar(doc) {
  return `<div class="review-bar"><div><p class="review-tally">${escapeHtml(tallyText(doc))}</p><p class="review-readiness">${escapeHtml(readinessText(doc))}</p></div><button type="button" class="button secondary" data-action="export">${icon('download')}Review and download</button></div>`;
}

function codesSection(doc) {
  const codes = codesOf(doc);
  const bar = codes.length || exportOffered(doc) ? reviewBar(doc) : '';
  return `<section class="codes-section" aria-labelledby="codesTitle"><div class="results-topline"><h2 id="codesTitle">CPT codes</h2>${codes.length ? `<span class="small-badge">${codes.length}</span>` : ''}</div>`
    + `<ol id="codesList" class="codes-list" aria-label="CPT codes"${codes.length ? '' : ' hidden'}>${codes.map((code, position) => codeRow(code, doc, position)).join('')}</ol>`
    + (codes.length ? '' : `<p class="results-empty">${escapeHtml(emptyCodesText(doc))}</p>`)
    + `${bar}</section>`;
}

// Documentation notes: what the coding review noticed about the documentation itself, as written, then each comment of
// the second check that could not be tied to one line (the server's sentence with its reason as written). Shown once a
// review has finished, so "no notes" is never said of a review still running.
function notesPanel(doc) {
  const notes = notesOf(doc);
  if (!notes.length && !(progressPhase(doc) === 'done' && !isBusy(doc))) return '';
  const body = notes.length ? `<p>What the coding review noticed about the documentation itself, and any comment of the second check that could not be tied to one line.</p><ul class="notes-list">${notes.map(note => `<li>${escapeHtml(note)}</li>`).join('')}</ul>` : '<p class="notes-empty">The coding review made no notes about the documentation.</p>';
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
// that changes them (renderDocument), so the original document's viewer is never reloaded under the member. It never
// fades in (R2-14).
function reviewView(doc, ui = {}) {
  return `<section class="review-view"><a class="back-link" href="#documents">${icon('arrow')}All documents</a>`
    + `<div id="reviewHead">${reviewHeading(doc)}</div>`
    + `<div class="review-layout"><div class="review-column" id="reviewColumn">${reviewColumn(doc, ui)}</div><div class="viewer-column">${viewerPanel(doc)}<div id="quotesBox">${quotesPanel(doc)}</div></div></div></section>`;
}

// --- the export dialog ---

// Each group of the dialog (the draft, the approved codes) holds its PDF, the report for the doctor and the only one CPT
// Studio makes (owner direction 2026-11-21: no more TXT or CSV), as the primary button, with a line on what it holds.
// Each group is named by its label. While a file is made every option waits (disabled), and the one chosen says it is
// being prepared. A draft holds the decisions saved so far, approvals among them: its line says so. Files made earlier,
// the TXT and CSV of earlier releases among them, stay listed under Earlier downloads.
const EXPORT_GROUPS = [['draft', 'Draft report'], ['approved', 'Approved report']];
const PDF_NOTES = {
  draft: 'Every code with its status, any saved decision, the evidence and what still needs a decision.',
  approved: 'Only approved codes, with who approved them and when.',
};
const PDF_NOTE_IDS = { draft: 'exportPdfDraftNote', approved: 'exportPdfApprovedNote' };
// The two PDF buttons show the same words; each one's name adds which report it is, after the words shown, so the two are
// told apart by name alone (a list of the page's buttons, a spoken command).
const PDF_NAMES = { draft: 'draft report', approved: 'approved report' };
// the ids of the groups' labels, which name the groups
const GROUP_LABEL_IDS = { draft: 'exportDraftLabel', approved: 'exportApprovedLabel', earlier: 'exportEarlierLabel' };
// a download's format as the list of earlier downloads names it (earlier releases also made CSV and TXT), and as the
// dialog's sentences name the file being made
const FORMAT_LABELS = { pdf: 'PDF', csv: 'CSV', txt: 'TXT' };
const FILE_WORDS = { pdf: 'PDF' };
const PREPARING_PDF = 'Preparing PDF…';
// One gesture makes one file: once a file is made its option waits (unavailable) at least this long, and until the
// dialog has been drawn from the document read again; a double click's second click is not a choice at all (onClick).
const MADE_HOLD_MS = 1000;

function pdfOption(kind, enabled, busy = false) {
  const words = busy ? PREPARING_PDF : 'Download PDF';
  return `<button type="button" class="button primary export-pdf" data-export-kind="${kind}" data-export-fmt="pdf" aria-label="${escapeHtml(`${words} (${PDF_NAMES[kind]})`)}" aria-describedby="${PDF_NOTE_IDS[kind]}"${enabled ? '' : ' disabled'}${busy ? ' aria-busy="true"' : ''}>${icon('download')}<span>${words}</span></button>`
    + `<p class="export-pdf-note" id="${PDF_NOTE_IDS[kind]}">${escapeHtml(PDF_NOTES[kind])}</p>`;
}

// An export the server no longer lists as current is still listed and linked, and says so: it was made from an earlier
// coding review, or before a decision recorded after it on the same one. Its format is named when the server names one
// of the three.
function reportItem(report) {
  const url = safeDownloadUrl(report.download_url);
  const name = text(report.filename) || 'Download';
  const kind = report.kind === 'approved' ? 'Approved codes' : 'Codes (draft)';
  const meta = [kind, lookup(FORMAT_LABELS, report.fmt, ''), formatTimestamp(report.generated_at)].filter(Boolean).join(' · ');
  const link = url ? `<a href="${escapeHtml(url)}" download>${escapeHtml(name)}</a>` : `<span>${escapeHtml(name)}</span>`;
  if (report.current !== true) return `<li class="report-item earlier">${link}<small>${escapeHtml(`${meta} · Earlier: made before a later decision or coding review; it may not show the current codes`)}</small></li>`;
  return `<li class="report-item">${link}<small>${escapeHtml(meta)}</small></li>`;
}

// The dialog's options for `doc`. `making` ({kind, fmt}) is the file being made: then every option is disabled, and the
// one with that kind and format says it is being prepared (none does for {kind: null, fmt: null}). `made` ({kind, fmt})
// is a file just made: its option alone waits a moment, disabled, saying nothing more.
function exportOptions(doc, making = null, made = null) {
  const readiness = record(doc?.readiness);
  const allowed = { draft: readiness.draft === true, approved: readiness.approved === true };
  const blockers = strings(readiness.blockers);
  const reports = objects(doc?.reports);
  const waiting = Boolean(making);
  const busy = (kind, fmt) => waiting && making.kind === kind && making.fmt === fmt;
  const free = (kind, fmt) => allowed[kind] && !waiting && !(made && made.kind === kind && made.fmt === fmt);
  const label = (key, words) => `<div class="evidence-label" id="${GROUP_LABEL_IDS[key]}">${words}</div>`;
  const opening = key => `<div class="export-group" role="group" aria-labelledby="${GROUP_LABEL_IDS[key]}">`;
  const why = !allowed.approved && blockers.length ? `<div class="export-blockers"><p>Not available yet:</p><ul>${blockers.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : '';
  const group = ([kind, words]) => `${opening(kind)}${label(kind, words)}${pdfOption(kind, free(kind, 'pdf'), busy(kind, 'pdf'))}${kind === 'approved' ? why : ''}</div>`;
  return EXPORT_GROUPS.map(group).join('')
    + (reports.length ? `${opening('earlier')}${label('earlier', 'Earlier downloads')}<ul class="report-list">${reports.map(reportItem).join('')}</ul></div>` : '');
}

// What the export dialog's status says while a file is made, and once the server has made it.
function preparingText(fmt) {
  return `Your ${lookup(FILE_WORDS, fmt, 'file')} is being prepared. The download starts when it is ready.`;
}

function readyText(fmt, filename) {
  return `Your ${lookup(FILE_WORDS, fmt, 'file')} is ready. Downloading ${text(filename) || 'the file'}.`;
}

const ANOTHER_FILE = 'Another download is still being prepared. Wait a moment, then choose again.';
// What an export dialog says, offering nothing, while the page reads the document again after a download was refused
// because its coding review changed.
const LOADING_LATEST_TEXT = 'This coding review has changed. The page is loading the latest; what it allows can be downloaded once it has.';

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
    this.code = data && typeof data === 'object' && typeof data.error_code === 'string' ? data.error_code : '';
    this.details = data && typeof data === 'object' && data.details && typeof data.details === 'object' ? data.details : null;
  }
}

// A decision the server refused because what the page shows is no longer the latest: a conflict status that is not the
// stale-build notice (which asks for a reload of the whole page instead).
function changedUnderPage(error) {
  return error instanceof ApiError && error.status === 409 && error.code !== 'client_outdated';
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function csrfValue() {
  const cookieName = csrfCookieName(globalThis.location?.protocol);
  return readCookie(document.cookie, cookieName) || $('input[name="csrfmiddlewaretoken"]')?.value || '';
}

function goToLogin(reason = 'expired') {
  if (state.leaving) return;
  state.leaving = true;
  clearScreen();
  location.assign(loginAddress(reason, location.hash));
}

// B4: a password staff set must be replaced before anything else opens (403 {"error": "password_change_required"}).
function goToAccount() {
  if (state.leaving) return;
  state.leaving = true;
  clearScreen();
  location.assign(ACCOUNT_REQUIRED_URL);
}

function showUpdateNotice() {
  state.outdated = true;
  stopPolling();
  const notice = $('#updateNotice');
  if (notice) notice.hidden = false;
}

// One call to the customer API. A change the server accepts with no body reads as an empty answer; a read must be JSON.
async function api(path, { method = 'GET', json, form, poll = false } = {}) {
  const headers = { Accept: 'application/json', [CLIENT_HEADER]: CLIENT_VERSION };
  let body;
  if (poll) headers[POLL_HEADER] = '1';
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
  const isJson = (response.headers.get('Content-Type') || '').includes('application/json');
  if (response.status === 401 || (response.redirected && new URL(response.url).pathname.startsWith('/login'))) {
    const answer = isJson ? await response.json().catch(() => null) : null;
    sessionEnded(signedOutReason(answer));  // every tab of the session is told (B5)
    throw new ApiError('Your session has ended. Sign in again.', 401);
  }
  const data = isJson ? await response.json().catch(() => null) : null;
  if (response.status === 403 && data?.error === 'password_change_required') {
    goToAccount();
    throw new ApiError('Choose a new password to continue.', 403, data);
  }
  // a 404 to the search that is no JSON is release 1's web after a switch-back, which has no search (I1-3)
  if (isClientOutdated(response.status, data) || (response.status === 404 && !isJson && path === SEARCH_URL)) {
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

// The review and export dialogs belong to the document they were opened on: a route (a link, browser Back) closes them,
// so nothing one showed is saved while the page shows another. A route reads the document afresh, so a read asked for
// after a refused download is no longer awaited by an export dialog opened after it.
function closeDocumentDialogs() {
  state.review = null;
  state.exporting = null;
  state.rereading = null;
  closeDialog('reviewDialog');
  closeDialog('exportDialog');
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

// The workspace's specialty, as the session names it (GET /api/session, workspace.specialty) and, before the session is
// read, as the page shell names it (data-specialty on <body>; owner direction 2026-11-22, D390): a label only - nothing
// on the page or the server codes from it.
function specialtyEyebrow() {
  const shell = typeof document === 'undefined' ? '' : text(document.body?.dataset?.specialty);
  const specialty = text(state.session?.workspace?.specialty) || shell;
  return specialty ? `CODING REVIEW · ${specialty.toUpperCase()}` : 'CODING REVIEW';
}

function renderSession(session) {
  const name = text(session.workspace?.name) || 'Workspace';
  $('#workspaceName').textContent = name;
  // the specialty follows the session, as the workspace name does: a page left open while the same browser signs in to
  // another workspace names the workspace it now works in (refutation N1-3-1)
  const specialty = text(session.workspace?.specialty);
  const specialtyOption = $('#specialty option');
  if (specialty && specialtyOption) specialtyOption.textContent = specialty;
  const eyebrow = $('.review-heading .eyebrow');
  if (eyebrow) eyebrow.textContent = specialtyEyebrow();
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
  const team = $('#teamNav');
  if (team) team.hidden = session.can_manage_team !== true;
}

async function loadSession() {
  try {
    state.session = await api('/api/session');
    state.sessionReadAt = Date.now();
    renderSession(state.session);
  } catch (error) {
    if (error.status !== 401) toast(`The workspace could not be loaded. ${error.message}`);
  }
  return state.session;
}

// R2-17: the session the shell carries (<body data-session-json>: GET /api/session's payload), or null.
function shellSession() {
  try {
    const data = JSON.parse(text(document.body?.dataset?.sessionJson) || 'null');
    const part = value => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
    return part(data) && part(data.user) && part(data.workspace) ? data : null;
  } catch {
    return null;
  }
}

const SESSION_FRESH_MS = 60000;

// R2-17: a document's route reads the session again only when the page has none or read it a minute ago or more.
function refreshSession() {
  if (!state.session || Math.abs(Date.now() - state.sessionReadAt) >= SESSION_FRESH_MS) {
    loadSession();  // the review heading's specialty follows the session (refutation N2-2-2), at most once a minute
  }
}

// R2-14: the entrance fade (main[data-entrance]) is a page load's first view's alone.
function endEntrance() {
  $('#main')?.removeAttribute('data-entrance');
}

// Boot's first route: at once from the shell's session (R2-17), else after reading it, as release 1; the worker made
// ready ahead is asked for `first` ms after the next frame, the one that draws the route (R2-10, D-R2-54), and an end
// before that frame cancels it (endStandby).
function firstRoute() {
  const carried = shellSession();
  const begin = () => {
    route();
    state.standbyOn = true;
    if (typeof requestAnimationFrame !== 'function') scheduleStandby(PDF_STANDBY.first);
    else state.standbyFrame = requestAnimationFrame(() => { state.standbyFrame = 0; scheduleStandby(PDF_STANDBY.first); });
  };
  if (!carried) return loadSession().then(begin);
  state.session = carried;
  state.sessionReadAt = Date.now();
  renderSession(carried);
  begin();
  return Promise.resolve();
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
  const before = state.route;
  if (before) endEntrance();
  dropEarly();
  closeList();
  stopPolling();
  stopTicker();
  closeDocumentDialogs();
  closeViewer();  // every route redraws #main, and with it the viewer
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
  if (next.name === 'doc') {
    refreshSession();
    return showDocument(next.id, serial, Boolean(before) && LIST_ROUTES.has(before.name));
  }
  window.scrollTo({ top: 0, behavior: 'instant' });
  if (next.name === 'how-it-works') {
    $('#main').innerHTML = howItWorksView();
    return undefined;
  }
  if (next.name === 'team') return showTeam(serial);
  return showList(next.name, serial);
}

// C4: the owners' Team panel. A reviewer or viewer who opens it is told it is the owners'; any change reads the team again.
async function showTeam(serial) {
  $('#main').innerHTML = teamView();
  let data;
  try {
    data = await api('/api/members');
  } catch (error) {
    if (serial !== state.routeSerial) return;
    const sentence = error.status === 403 || error.status === 404 ? 'Only the practice\'s owners see the team.' : `The team could not be loaded. ${error.message}`;
    $('#teamList').innerHTML = `${TEAM_HEADER}<p class="empty-state">${escapeHtml(sentence)}</p>`;
    return;
  }
  if (serial !== state.routeSerial) return;
  $('#teamList').innerHTML = teamList(teamMembers(data), state.session?.user?.id || '');
}

async function setMemberAccess(id, active, button) {
  if (!UUID.test(String(id))) return;
  setBusy(button, true);
  try {
    await api(`/api/members/${encodeURIComponent(id)}/access`, { method: 'POST', json: { active } });
    toast(active ? 'Access turned on.' : 'Access turned off.');
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(button, false);
  }
  if (state.route?.name === 'team') await showTeam(state.routeSerial);
}

// One confirmation at a time (#confirmDialog): its Continue runs `run`, its Cancel or Close runs nothing.
function askConfirm({ title, text: body, action, run }) {
  state.confirming = run;
  $('#confirmTitle').textContent = title;
  $('#confirmText').textContent = body;
  $('#confirmGo').textContent = action;
  openDialog('confirmDialog');
}

function confirmChosen() {
  const run = state.confirming;
  state.confirming = null;
  closeDialog('confirmDialog');
  if (typeof run === 'function') run();
}

function askMemberAccess(button) {
  const active = button.dataset.memberAccess === 'on';
  const id = button.dataset.member;
  if (active) return setMemberAccess(id, true, button);
  askConfirm({ title: `Turn off ${button.dataset.label || 'this person'}'s access?`,
    text: 'They can no longer open this practice\'s documents, from their next step. Their other practices are not changed, and you can turn their access on again here.',
    action: 'Turn off', run: () => setMemberAccess(id, false, button) });
  return undefined;
}

// C6: the Word file itself is downloaded only once the member has read why it is not the default.
function askWordOriginal(address) {
  if (!/^\/api\/encounters\/[0-9a-f-]{36}\/original\?format=original$/i.test(String(address))) return;
  askConfirm({ title: 'Download the Word file?', text: WORD_ORIGINAL_TEXT, action: 'Download it anyway',
    run: () => saveDownload(address, '').catch(error => toast(error.message)) });
}

// R2-22: a list view asks for its first page, its rows and words release 1's; its total sets the counts (page memory).
async function showList(name, serial) {
  $('#main').innerHTML = name === 'workspace' ? overviewView() : documentsView(name);
  const list = { name, loaded: false, total: null, local: true, browse: null, found: null, query: '', words: '',
    all: false, loading: false, searching: false, again: false, timer: 0, observer: null, near: false, refused: '' };
  state.list = list;
  let page;
  try {
    page = listPage(await api(LIST_ADDRESS[name]));
  } catch (error) {
    if (serial !== state.routeSerial || list !== state.list) return;
    $('#documentsTable').innerHTML = `${LIST_HEADER}<p class="empty-state">${escapeHtml(`Documents could not be loaded. ${error.message}`)}</p>`;
    if ($('#listDescription')) $('#listDescription').textContent = 'Documents could not be loaded.';
    if ($('#recentInvite')) $('#recentInvite').innerHTML = '';
    return;
  }
  if (serial !== state.routeSerial || list !== state.list) return;
  // exact-1: a first page of another practice than the page shows is never drawn either
  if (page.workspace && state.session?.workspace?.id && otherPractice({ workspace: state.session.workspace.id }, page)) return;
  const next = name === 'workspace' ? null : page.next;
  Object.assign(list, { loaded: true, total: page.total, workspace: page.workspace,
    browse: { rows: page.rows, next, auto: 0, failed: false, problem: '',
      button: next !== null && typeof IntersectionObserver !== 'function' } });
  // C2: the search runs in the page up to LOCAL_SEARCH_MAX documents, else on the server
  list.local = next === null || (page.total !== null && page.total <= LOCAL_SEARCH_MAX);
  state.viewHints = new Map();
  hintRows(page.rows);
  $('#documentsTable').innerHTML = listBody(name, page.rows);
  if ($('#listDescription')) $('#listDescription').textContent = listDescription(name, page.total ?? listRows(name, page.rows).length);
  if ($('#recentInvite')) $('#recentInvite').innerHTML = inviteMarkup(page.rows);
  if (page.total !== null && name !== 'workspace') setCount(name === 'queue' ? '#queueCount' : '#documentsCount', page.total);
  watchListEnd(list);
  drawListMore();
  applySearch();
}

// I1-2, exact-1: a page of another practice than the one shown (the member's access changed meanwhile) - a later page
// or a search against the list's first page, a first page against the session - is never drawn: the session is read
// again, then the route drawn afresh once it names another practice.
function otherPractice(list, page) {
  if (page.workspace === list.workspace) return false;
  const serial = state.routeSerial;
  loadSession().then(session => { if (serial === state.routeSerial && session?.workspace?.id !== list.workspace) route(); });
  return true;
}

function closeList() {
  const list = state.list;
  state.list = null;
  if (!list) return;
  clearTimeout(list.timer);
  list.observer?.disconnect();
}

// R2-16: the rows that open as a PDF of at most 1 MiB (opens_pdf).
function hintRows(rows) {
  for (const row of rows) if (row.opens_pdf === true) state.viewHints.set(row.id, true);
}

// The list's end (#listMore), watched 600 px ahead, loads the next page itself, AUTO_PAGES times (C7).
function watchListEnd(list) {
  const more = $('#listMore');
  if (!more || !list.browse.next || typeof IntersectionObserver !== 'function') return;
  list.observer = new IntersectionObserver(entries => {
    if (list !== state.list) return;
    list.near = entries[entries.length - 1]?.isIntersecting === true;
    pumpList(list);
  }, { rootMargin: '600px 0px' });
  list.observer.observe(more);
}

// Rows drawn again or added: the end is observed afresh, for a new answer.
function relook(list) {
  const more = $('#listMore');
  if (!list.observer || !more) return;
  list.near = false;
  list.observer.unobserve(more);
  list.observer.observe(more);
}

// One load at a time: for the page's own search (C2) every page not yet loaded; else, the end near and an automatic
// load left (the budget counted as the load starts), the next page.
function pumpList(list) {
  if (list !== state.list || list.loading) return;
  const source = list.found || list.browse;
  if (!source?.next || source.failed) return;
  if (list.local && list.all) {
    loadMore(list, 'search');
    return;
  }
  // above LOCAL_SEARCH_MAX, words in the box are the server's to search: the list's rows they hide load nothing more
  if (!list.near || source.button || source.auto >= AUTO_PAGES || (!list.local && list.query && !list.found)) return;
  source.auto += 1;
  loadMore(list, 'auto');
}

// One more page of the rows shown, appended in order; with the automatic loads used up or one failed, the button
// alone loads more (C7).
async function loadMore(list, why) {
  const source = list.found || list.browse;
  if (list.loading || !source?.next) return;
  list.loading = true;
  source.problem = '';
  drawListMore();
  let page = null;
  let failure = '';
  try {
    page = listPage(source === list.browse ? await api(`${LIST_ADDRESS[list.name]}&before=${encodeURIComponent(source.next)}`)
      : await api(SEARCH_URL, { method: 'POST', json: { text: source.words, before: source.next } }));
  } catch (error) {
    failure = error.message;
  }
  list.loading = false;
  if (list !== state.list || (page && otherPractice(list, page))) return;
  const shown = source === (list.found || list.browse);
  if (page) {
    // a page with no rows, or naming the same place again, is the end
    source.next = page.rows.length && page.next !== source.next ? page.next : null;
    source.rows.push(...page.rows);
    hintRows(page.rows);
    if (shown) appendRows(list, page.rows);
    if (source.next && source.auto >= AUTO_PAGES) source.button = true;
    // the list's last page: the whole list, searched here (C2); an answer's rows, asked later, stay, its new ones first
    if (source === list.browse && !source.next) {
      list.refused = '';
      if (list.found) {
        const newer = new Map(list.found.rows.map(row => [row.id, row]));
        source.rows = source.rows.map(row => newer.get(row.id) || row);
        source.rows.unshift(...list.found.rows.filter(row => !source.rows.includes(row)));
        list.found = null;
        $('#documentsTable').innerHTML = listBody(list.name, source.rows);
      }
    }
  } else {
    source.problem = `Documents could not be loaded. ${failure}`;  // said while its own list is shown
    if (why !== 'button') Object.assign(source, { failed: true, button: true });
  }
  filterRows();
  drawListMore();
  relook(list);
  pumpList(list);
}

function moreDocuments() {
  const list = state.list;
  if ((list?.found || list?.browse)?.button) loadMore(list, 'button');
}

// New rows go in through a template element, so the rows already shown are never drawn again.
function appendRows(list, rows) {
  const table = $('#documentsTable');
  if (!table) return;
  $('#searchEmpty')?.remove();
  const template = document.createElement('template');
  template.innerHTML = listRows(list.name, rows).map(row => documentRow(row)).join('');
  table.append(template.content);
}

// #listMore: empty while automatic loads remain; the button after them or a failed one (C7); a refusal's sentence.
function drawListMore() {
  const list = state.list;
  const more = $('#listMore');
  if (!more || !list?.loaded) return;
  const source = list.found || list.browse;
  const said = [source.problem, list.refused].filter(Boolean);
  more.hidden = !source.next && !said.length;
  more.innerHTML = said.map(words => `<p class="empty-state" role="status">${escapeHtml(words)}</p>`).join('')
    + (source.next && source.button ? `<button type="button" class="button secondary" data-action="more-documents"${list.loading ? ' disabled aria-busy="true"' : ''}>${MORE_TEXT}</button>` : '');
}

// Whether nothing beyond the page can match: the whole list is on it, or every match of words the words typed hold.
function nothingBeyond(list) {
  return !list.browse.next || (Boolean(list.found) && !list.found.next && list.query.includes(list.found.query));
}

// Release 1's rule, inside the keystroke. "No documents match your search." only when nothing more can match; else
// the loading line while a load or a search is under way.
function filterRows() {
  const list = state.list;
  const table = $('#documentsTable');
  if (!list?.loaded || !table) return;
  const query = list.query;
  const rows = $$('#documentsTable .document-row');
  rows.forEach(row => { row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query); });
  const none = Boolean(query) && (rows.length ? rows.every(row => row.hidden) : Boolean(list.found));
  const waiting = list.loading || list.searching || Boolean(list.timer) || (list.local && list.all && !list.browse.failed);
  const words = !none ? '' : nothingBeyond(list) ? 'No documents match your search.' : waiting ? 'Loading documents…' : '';
  let empty = $('#searchEmpty');
  if (words) {
    if (!empty) {
      empty = document.createElement('p');
      empty.id = 'searchEmpty';
      empty.className = 'empty-state';
      table.appendChild(empty);
    }
    empty.textContent = words;
  } else {
    empty?.remove();
  }
}

// The search box (C2): up to LOCAL_SEARCH_MAX documents it loads the rest and runs in the page; above, it filters the rows
// shown and asks the server after SEARCH_PAUSE_MS while matches may lie beyond. Clearing it shows the list again.
function applySearch() {
  const input = $('#documentSearch');
  const list = state.list;
  if (!input || !list?.loaded) return;
  list.words = input.value.trim();  // sent as typed (R2-20); lower-cased for the page's own rule
  list.query = list.words.toLowerCase();
  clearTimeout(list.timer);
  list.timer = 0;
  if (list.local) {
    if (list.query && list.browse.next) list.all = true;
  } else {
    list.refused = '';
    if (list.found && !(list.query && list.query.includes(list.found.query))) {
      list.found = null;
      $('#documentsTable').innerHTML = listBody(list.name, list.browse.rows);
      relook(list);
    }
    if (list.query && !nothingBeyond(list)) list.timer = setTimeout(() => searchDocuments(list), SEARCH_PAUSE_MS);
  }
  filterRows();
  drawListMore();
  pumpList(list);
}

// R2-20: one server search at a time, its words in a POST body; an answer to older words is dropped, a refusal said.
async function searchDocuments(list) {
  list.timer = 0;
  if (list !== state.list || !list.query || nothingBeyond(list)) return;
  // words whose answer is on the page already are never asked again: its own pages reach the rest
  if (list.query === list.found?.query) return filterRows();
  if (list.searching) {
    list.again = true;
    return;
  }
  const query = list.query;
  const words = list.words;
  list.searching = true;
  list.again = false;
  let page = null;
  let failure = '';
  try {
    page = listPage(await api(SEARCH_URL, { method: 'POST', json: { text: words, before: null } }));
  } catch (error) {
    failure = error.message;
  }
  list.searching = false;
  if (list !== state.list || (page && otherPractice(list, page))) return;
  const due = list.again;
  list.again = false;
  if (list.query !== query) {
    if (due && !list.timer) searchDocuments(list);  // a pause still running asks in its own time
    else filterRows();
    return;
  }
  if (!list.browse.next) return filterRows();  // the list's last page came meanwhile: searched in the page (C2)
  if (page) {
    list.refused = '';
    list.found = { query, words, rows: page.rows, next: page.next, auto: 0, failed: false, problem: '',
      button: page.next !== null && typeof IntersectionObserver !== 'function' };
    hintRows(page.rows);
    $('#documentsTable').innerHTML = LIST_HEADER + page.rows.map(row => documentRow(row)).join('');
    relook(list);
  } else {
    list.refused = failure;
  }
  filterRows();
  drawListMore();
}

// R2-14: how long a list stays shown while the document chosen in it is read.
const LOADING_AFTER_MS = 150;
const LIST_ROUTES = new Set(['workspace', 'documents', 'queue']);

// R2-14: chosen in a list, the document is read with the list in view until the review is drawn or LOADING_AFTER_MS
// has passed; from anywhere else the loading line (or an upload's acknowledgement) shows at once.
function showDocument(id, serial, fromList = false) {
  if (!UUID.test(id)) {
    window.scrollTo({ top: 0, behavior: 'instant' });
    $('#main').innerHTML = messageView('This document is not available.', 'The address does not name a document in this workspace.');
    return undefined;
  }
  startEarly(id);
  const loading = () => {
    if (serial !== state.routeSerial) return;
    window.scrollTo({ top: 0, behavior: 'instant' });
    $('#main').innerHTML = state.ack?.id === id ? ackView(state.ack) : '<section class="view-entrance"><p class="empty-state">Loading the review…</p></section>';
  };
  const wait = fromList && state.ack?.id !== id;
  if (!wait) loading();
  const timer = wait ? setTimeout(loading, LOADING_AFTER_MS) : 0;
  return loadDocument(id, serial, false).finally(() => clearTimeout(timer));
}

function setReconnecting(on) {
  state.reconnecting = on;
  const line = $('.progress-reconnecting');
  if (line) line.hidden = !(on && shouldPoll(state.doc));
}

// Reads can answer out of order (a poll, the read after an act, the read after a download): one that answers after a
// read asked later than it was shown is older than what the page shows, and changes nothing - nor does its failure.
// Each read shown draws an open export dialog again (redrawExportDialog).
async function loadDocument(id, serial, silent, poll = false) {
  clearTimeout(state.poll.timer);
  const read = ++state.reads.asked;
  const older = () => read < state.reads.applied;
  let doc;
  try {
    doc = await api(`/api/encounters/${encodeURIComponent(id)}`, { poll });
  } catch (error) {
    // a 404 (another practice's document, access ended) is an end (R2-18); to a route left it spares the view the
    // route shown is opening (an older read, or a route back to it, is the document's own)
    if (serial !== state.routeSerial || older()) {
      if (error.status === 404) forgetMemory(serial === state.routeSerial || state.route?.id === id ? '' : state.viewer?.view || state.early?.view
        || (state.route?.name === 'doc' ? `/api/encounters/${state.route.id}/original?view=1` : ''));
      return;
    }
    if (error.status === 404) forgetMemory();
    if (state.outdated) {
      dropEarly();  // R2-16: a first read refused as outdated drops the click's early view too
      return;
    }
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
    dropEarly();
    window.scrollTo({ top: 0, behavior: 'instant' });
    $('#main').innerHTML = error.status === 404
      ? messageView('This document is not available.', 'It does not exist, or it is not in your workspace.')
      : messageView('The review could not be loaded.', error.message, true);
    return;
  }
  if (serial !== state.routeSerial || older()) {
    if (state.route?.id !== doc?.id) dropRefused(doc);  // I1-16: left before its answers; the route's abort kept it
    return;
  }
  state.reads.applied = read;
  state.poll.errors = 0;
  state.reconnecting = false;
  state.clock = clockOffset(doc.progress?.server_time, Date.now());
  if (state.ack?.id === doc.id && !isBusy(doc)) state.ack = null;
  renderDocument(doc, !silent);
  // any read asked after a refused download (or after a file was made) shows what the server had since: the dialog
  // waiting for the latest, or the option waiting for the page's read, waits no longer for its own read, which may stall
  if (state.rereading === doc.id && read > state.rereadAfter) state.rereading = null;
  if (state.madeRead && read > state.madeRead.after) state.madeRead.done();
  redrawExportDialog();
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
  state.poll.timer = setTimeout(() => loadDocument(id, serial, true, true), delay);
}

async function refreshDocument({ poll = false } = {}) {
  if (state.route?.name !== 'doc') return;
  state.poll.count = 0;
  state.poll.errors = 0;
  await loadDocument(state.route.id, state.routeSerial, true, poll);
}

// the refresh on return to the tab or on reconnecting is a poll: it never counts as the member's activity (B5)
function refreshIfWaiting() {
  if (state.route?.name === 'doc' && shouldPoll(state.doc) && !document.hidden) refreshDocument({ poll: true });
}

// Where the focus was, so a redraw can put it back: the element's id, the code row it sits in (its line and its code),
// and the caret of an answer being typed.
function focusTarget() {
  const element = document.activeElement;
  if (!element || !$('#main').contains(element)) return null;
  const row = element.closest?.('.code-row');
  const target = { id: element.id || '', line: row?.dataset.line || '', code: row?.dataset.code || '' };
  if (element.tagName === 'TEXTAREA' && typeof element.selectionStart === 'number') target.selection = [element.selectionStart, element.selectionEnd];
  return target.id || target.line ? target : null;
}

// Focus goes back to the same element, or to its row; never onto another code that a new coding review put on that line.
function restoreFocus(target) {
  if (!target) return;
  let element = target.id ? document.getElementById(target.id) : null;
  if (!element && target.line) element = document.getElementById(`code-${rowKey(target.line)}`);
  if (!element) return;
  const row = element.closest?.('.code-row');
  if (target.code && row && row.dataset.code !== target.code) return;
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

// The stored conversion a Word document's view serves, as the server names it (a UUID), or none (I2-2).
const conversionOf = value => (typeof value === 'string' && UUID.test(value) ? value : '');

// What the viewer shows (the Word conversion served included: I1-12, I2-2): the page redraws it only when this
// changes, so neither a poll nor a later round reading back the same conversion reloads the original.
function viewerKey(doc) {
  const part = record(doc?.document);
  return `${doc?.id || ''} ${viewerKind(part)} ${part.converted === true} ${conversionOf(part.view_conversion)} ${safeViewUrl(part.view_url)} ${safeOriginalUrl(part.original_url)} ${documentName(part)}`;
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
  // a passage chosen on one coding review names a line of it: another coding review's same line is another passage, so
  // the passage chosen and its mark go
  const another = roundNumber(doc) !== roundNumber(state.doc);
  if (another) state.selectedQuote = '';
  state.doc = doc;
  state.docKey = key;
  const ui = uiState();
  if (partial) {
    $('#reviewHead').innerHTML = reviewHeading(doc);
    $('#quotesBox').innerHTML = quotesPanel(doc);
    $('#reviewColumn').innerHTML = reviewColumn(doc, ui);
    if (another) clearViewerMark();
  } else {
    state.viewerKey = frame;
    state.selectedQuote = '';
    closeViewer();
    state.framePassage = null;
    endEntrance();
    $('#main').innerHTML = reviewView(doc, ui);
    if (!keep) window.scrollTo({ top: 0, behavior: 'instant' });
    mountViewer(doc);
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
  const codes = codesOf(state.doc);
  for (let position = 0; position < codes.length; position += 1) {
    const quotes = quotesOf(codes[position]);
    for (let index = 0; index < quotes.length; index += 1) if (quoteKey(codes[position], index, position, state.doc) === key) return { code: codes[position], quote: quotes[index] };
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

// Choosing a quote: the PDF viewer opens the quoted page and marks the quote's words there (locateQuote); the text viewer
// marks the passage in the text (findPassages), since a text has no pages. The note under the viewer says what was
// marked. The mark stays until another quote is chosen or the document changes.
function showQuote(key) {
  const found = findQuote(key);
  if (!found) return undefined;
  state.selectedQuote = key;
  markSelectedQuote();
  const element = $('#documentViewer');
  if (!element) return undefined;
  const kind = viewerKind(state.doc?.document);
  let shown;
  if (kind === 'pdf' && state.viewer && state.viewer.element === element) shown = showPdfQuote(state.viewer, found.quote, key);
  else if (kind === 'text') markInFrame(element, found.quote.text, key);
  element.scrollIntoView?.({ behavior: reducedMotion() ? 'instant' : 'smooth', block: 'nearest' });
  return shown;
}

// A new coding review names other passages: the mark of one chosen on the earlier one, and its note, go.
function clearViewerMark() {
  const viewer = state.viewer;
  if (viewer) {
    viewer.mark = null;
    viewer.pending = null;
    viewer.chosen = null;
    viewer.markSerial += 1;
    dropQuoteScroll(viewer);
    for (const page of viewer.pages) paintPage(viewer, page);
    setMarkState(viewer.element, '', null);
  }
  const frame = $('#documentViewer');
  if (state.framePassage !== null && frame?.tagName === 'IFRAME') {
    state.framePassage = null;
    paintFrame(frame);
  }
  setMarkNote('');
}

function setMarkNote(message, missing = false) {
  const note = $('#viewerMark');
  if (!note) return;
  note.textContent = message;
  note.classList.toggle('is-missing', Boolean(message) && missing);
}

// What the viewer marked, on the viewer element, for the walk to check against the page: the quote, what was found, on
// which pages and how many times.
function setMarkState(element, key, result) {
  if (!element?.dataset) return;
  element.dataset.marked = key || '';
  element.dataset.markStatus = result ? result.status : '';
  element.dataset.markPages = result ? result.pages.join(' ') : '';
  element.dataset.markCount = result ? String(result.count) : '';
}

function scrollBehavior() {
  return reducedMotion() ? 'instant' : 'smooth';
}

// --- the PDF viewer: the original's pages drawn in the page, near the visible area only, fitted to its width --------
// The PDF library (pdf.js; a pinned copy of its legacy build this site serves, listed with its licences and a checksum
// of every file in studio/static/studio/lib/pdfjs-6.5.438/MANIFEST.json) is loaded for the worker made ready ahead,
// once the page has routed (startStandby, R2-10), or when a document is first viewed as a PDF; the page shell names its
// module and worker (data-pdf-module and data-pdf-worker on <body>, in legacy/build/; the image decoders and standard
// fonts it fetches are the package's own wasm/ and standard_fonts/, two folders up). It reads only the same-origin view
// address, runs with no WebAssembly, no document scripting, no XFA and no layer of links or form fields (form fields'
// appearances are drawn on the page), and the PDF's text reaches the page as text only, in its text layer. The viewer
// starts the library's worker itself, or takes the one made ready ahead (takeWorker), and hands it to the library, and
// downloads the document itself (downloadDocument: beside the library once a worker has started here, R2-12; a re-open
// answered 304 is drawn from the bytes kept in page memory, R2-15). Where it cannot run or cannot draw the document,
// the browser's own viewer is framed instead, as before: a quote opens its page there (a new frame at #page=N, since
// that viewer opens the page only as its frame loads), nothing is marked, and the note says why and names the quote's
// page (frameNote). No wait on the library is endless: loading it and starting its worker have a time limit
// (withinLimit); the download has one while it stops moving; and once the document has opened, the viewer's watchdog
// gives up its waits on the library only when the library has not answered for 20 seconds (libraryWatchdog), so a
// library that is busy - a worker decoding other pages' images - is not taken for a broken one.

// gap: around the pages and a mark scrolled to; settleMs: how often a quote's scroll is looked at to see whether it has
// stopped; closeMs: how long a closed document's worker is given to let go of it before it is ended.
const PDF_VIEW = { gap: 12, near: '100% 0px', resizeMs: 150, stallMs: 20000, limitMs: 20000, sliceMs: 40, settleMs: 150, closeMs: 3000,
  maxCanvasPixels: 16777216 };
// The zoom steps, relative to the page fitted to the viewer's width (ZOOM_FIT: 100%).
const ZOOM_STEPS = [0.75, 1, 1.25, 1.5, 2, 3];
const ZOOM_FIT = 1;
// The keys that scroll the viewer when it has the focus.
const SCROLL_KEYS = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', ' ', 'Spacebar']);
// How the page loads the library's module (a test stands in for it).
const PDF_IMPORT = { load: specifier => import(specifier) };
// R2-10: the worker made ready ahead, `first` ms after the first route and `next` ms after a viewer closes or draws a
// page, when idle (within `idle` ms); after `fails` failures, none.
const PDF_STANDBY = { first: 500, next: 600, idle: 2000, fails: 2 };
// R2-15: the bounds of the PDFs kept for a re-open; a view's tag, a quoted UUID (anything else is no tag).
const KEPT_VIEWS = { documents: 6, bytes: 24 * 1024 * 1024 };
const VIEW_TAG = new RegExp(`^(?:W/)?"(${UUID_PART})"$`, 'i');
const CONVERSION_HEADER = 'X-CPT-View-Conversion';  // I2-1: the stored conversion a view's 200 or 304 served

// A wait on the library that went past its time limit (withinLimit).
class TimeLimit extends Error {}

// Settles as `promise` does, or rejects with TimeLimit once it has waited `ms` of the time the page was visible: a hidden
// tab draws nothing (the browser stops the animation frames the library draws in), so its time does not count.
function withinLimit(promise, ms) {
  return new Promise((resolve, reject) => {
    const page = typeof document === 'object' && document ? document : null;
    const hidden = () => page?.hidden === true;
    let left = ms;
    let since = 0;
    let timer = 0;
    const run = () => {
      since = Date.now();
      timer = setTimeout(() => {
        stop();
        reject(new TimeLimit('The PDF library did not answer in time.'));
      }, Math.max(0, left));
    };
    const watch = () => {
      if (hidden()) {
        if (timer) {
          clearTimeout(timer);
          timer = 0;
          left -= Date.now() - since;
        }
      } else if (!timer) {
        run();
      }
    };
    const stop = () => {
      clearTimeout(timer);
      timer = 0;
      if (typeof page?.removeEventListener === 'function') page.removeEventListener('visibilitychange', watch);
    };
    if (typeof page?.addEventListener === 'function') page.addEventListener('visibilitychange', watch);
    if (!hidden()) run();
    Promise.resolve(promise).then(value => {
      stop();
      resolve(value);
    }, error => {
      stop();
      reject(error);
    });
  });
}

// A clock of the time the page has been visible: a hidden tab draws nothing, so its time does not count for a limit.
// `changed` is called when the page is hidden or shown again.
function visibleClock(changed = null) {
  const page = typeof document === 'object' && document ? document : null;
  let total = 0;
  let since = page?.hidden === true ? null : Date.now();
  const watch = () => {
    if (page?.hidden === true) {
      if (since !== null) {
        total += Date.now() - since;
        since = null;
      }
    } else if (since === null) {
      since = Date.now();
    }
    changed?.();
  };
  if (typeof page?.addEventListener === 'function') page.addEventListener('visibilitychange', watch);
  return {
    now: () => total + (since === null ? 0 : Date.now() - since),
    hidden: () => since === null,
    stop: () => { if (typeof page?.removeEventListener === 'function') page.removeEventListener('visibilitychange', watch); },
  };
}

// The viewer's one watchdog on the library once its document has opened (A3): every wait on the library (wait: the pages
// fetched, a page drawn, a page's text read, a text layer rendered) is given up only when the library has not answered
// for PDF_VIEW.limitMs of visible time, counted from the later of its last answer and the start of the wait. An answer
// is any message from the viewer's own worker (answer) or any of these waits settling. When it fires, every wait still
// pending rejects with TimeLimit and the frame is shown, as the library not working. A page released or drawn again is no
// longer waited on: its waits are let go (forget) - what the worker still finishes for it is messages, so answers.
// Known limit: one page whose images take longer than that to decode, with no other answer meanwhile, is taken as the
// library not working.
function libraryWatchdog(viewer) {
  if (viewer.watchdog) return viewer.watchdog;
  const waits = new Map();
  let timer = 0;
  let anchor = 0;
  let clock = null;
  const arm = () => {
    clearTimeout(timer);
    timer = 0;
    if (waits.size && clock && !clock.hidden()) timer = setTimeout(check, Math.max(0, anchor + PDF_VIEW.limitMs - clock.now()));
  };
  const check = () => {
    timer = 0;
    if (!waits.size) return;
    if (clock.now() - anchor < PDF_VIEW.limitMs) {
      arm();
      return;
    }
    const given = [...waits.keys()];
    waits.clear();
    for (const reject of given) reject(new TimeLimit('The PDF library did not answer in time.'));
    fallbackViewer(viewer, 'library');
  };
  clock = visibleClock(arm);
  anchor = clock.now();
  viewer.watchdog = {
    answer() {
      anchor = clock.now();
    },
    wait(promise, owner = null) {
      return new Promise((resolve, reject) => {
        if (!waits.size) anchor = clock.now();
        waits.set(reject, owner);
        if (!timer) arm();
        const settled = finish => value => {
          if (!waits.delete(reject)) return;
          anchor = clock.now();
          if (!waits.size) arm();
          finish(value);
        };
        Promise.resolve(promise).then(settled(resolve), settled(reject));
      });
    },
    forget(owner) {
      for (const [reject, of] of [...waits]) {
        if (of !== owner) continue;
        waits.delete(reject);
        reject(Object.assign(new Error('The page is no longer drawn.'), { name: 'AbortException' }));
      }
      if (!waits.size) arm();
    },
    stop() {
      clearTimeout(timer);
      timer = 0;
      const given = [...waits.keys()];
      waits.clear();
      for (const reject of given) reject(Object.assign(new Error('The document is no longer shown.'), { name: 'AbortException' }));
      clock.stop();
    },
  };
  return viewer.watchdog;
}

// A wait on the library once the document has opened, under the viewer's watchdog; `page`, where it is that page's draw.
// A viewer framed or closed has no watchdog any more, and nothing it still waits on is watched.
function watched(viewer, promise, page = null) {
  return viewer.mode === 'frame' || viewer.mode === 'closed' ? Promise.resolve(promise) : libraryWatchdog(viewer).wait(promise, page);
}

// Settles once `promise` has, or after `ms` at most, whichever comes first (never rejects).
function settleWithin(promise, ms) {
  return new Promise(resolve => {
    const timer = setTimeout(resolve, ms);
    Promise.resolve(promise).catch(() => {}).then(() => {
      clearTimeout(timer);
      resolve();
    });
  });
}

// Starts the library's worker as the viewer's own (A4): a module worker at the worker's address (viewer.thread), ready
// once it says so - the message {sourceName: 'worker', targetName: 'main', action: 'ready'} that the library's worker
// sends when it has set itself up (pdf.js 6.5.438 WorkerMessageHandler.initializeFromPort through its MessageHandler) -
// and then handed to the library as its port (openPdf), so the library never starts a worker of its own, nor its stand-in
// on the page's own thread. An 'error' or 'messageerror' event before ready rejects; the caller's time limit covers a
// worker that never says it is ready.
function startWorker(viewer, address, loading) {
  return new Promise((resolve, reject) => {
    const thread = new Worker(address, { type: 'module' });
    viewer.thread = thread;
    const done = (finish, value) => {
      thread.removeEventListener('message', ready);
      thread.removeEventListener('error', failed);
      thread.removeEventListener('messageerror', failed);
      finish(value);
    };
    const ready = event => {
      const data = event?.data;
      if (data && typeof data === 'object' && data.sourceName === 'worker' && data.targetName === 'main' && data.action === 'ready') {
        if (state.pdfLibrary === loading) state.pdfStarted = true;  // R2-12; a forgotten library's worker says nothing
        done(resolve, thread);
      }
    };
    const failed = () => done(reject, new Error('The PDF library\'s worker did not start.'));
    thread.addEventListener('message', ready);
    thread.addEventListener('error', failed);
    thread.addEventListener('messageerror', failed);
  });
}

// The viewer's download of its view (A5, R2-15: CORE-UX-DESIGN.md, "The viewer's own worker, download and watchdog" and
// "A re-open from page memory"), marked a poll; each chunk calls `moved`; a failure or an abort rejects. It answers
// {data, tag, held, conversion}: the conversion the answer names (I2-1).
async function downloadDocument(view, signal, moved) {
  const held = state.keptViews.get(view) || null;
  const headers = { [POLL_HEADER]: '1' };
  if (held) headers['If-None-Match'] = `"${held.tag}"`;
  let response;
  try {
    response = await fetch(view, { credentials: 'same-origin', cache: 'no-store', signal, headers });
  } catch (error) {
    if (!signal?.aborted) dropView(view, held);
    throw error;
  }
  const conversion = conversionOf(response.headers?.get?.(CONVERSION_HEADER));
  if (held && response.status === 304) {
    try {
      await response.arrayBuffer?.();  // its empty body read, so the browser counts the request done, not cancelled
    } catch {
      // nothing to read
    }
    // a copy wiped or replaced while its answer came, or while that answer's empty body was read, is never drawn
    if (state.keptViews.get(view) !== held) throw new Error('The copy was let go of.');
    moved();
    keepView(view, held.tag, held.data);
    return { data: held.data.slice(0), tag: held.tag, held: true, conversion };
  }
  dropView(view, held);
  // a 401 (the session ended) or a 403 (its password must change) is an end (R2-18)
  if (response.status === 401 || response.status === 403) forgetMemory();
  if (!response.ok) throw new Error(`The document's download was answered ${response.status}.`);
  const tag = VIEW_TAG.exec(response.headers?.get?.('ETag') || '')?.[1] || '';
  const chunks = [];
  let size = 0;
  if (response.body && typeof response.body.getReader === 'function') {
    const body = response.body.getReader();
    for (let read = await body.read(); !read.done; read = await body.read()) {
      chunks.push(read.value);
      size += read.value.byteLength;
      moved();
    }
  } else {
    const whole = new Uint8Array(await response.arrayBuffer());
    chunks.push(whole);
    size = whole.byteLength;
    moved();
  }
  const data = new Uint8Array(size);
  let at = 0;
  for (const chunk of chunks) {
    data.set(chunk, at);
    at += chunk.byteLength;
  }
  return { data, tag, held: false, conversion };
}

// R2-15: an opened PDF's bytes, kept in page memory under their tag - never a Blob, the Cache API, IndexedDB or Web
// Storage - within KEPT_VIEWS, the least recently viewed going first; every copy that goes is overwritten.
function keepView(view, tag, data) {
  const kept = state.keptViews;
  const old = kept.get(view);
  kept.delete(view);
  if (old && old.data !== data) old.data.fill(0);
  if (!UUID.test(String(tag)) || !(data instanceof Uint8Array) || data.byteLength > KEPT_VIEWS.bytes) return;
  kept.set(view, { tag, data });
  let bytes = 0;
  for (const item of kept.values()) bytes += item.data.byteLength;
  for (const [key, item] of kept) {
    if (kept.size <= KEPT_VIEWS.documents && bytes <= KEPT_VIEWS.bytes) break;
    kept.delete(key);
    bytes -= item.data.byteLength;
    item.data.fill(0);
  }
}

function dropView(view, held) {
  if (!held || state.keptViews.get(view) !== held) return;
  state.keptViews.delete(view);
  held.data.fill(0);
}

// R2-16: the view chosen, asked with the click once a worker has started, on a live page that can draw a PDF, for a
// kept copy or an opens_pdf row only - never on a hover or a list.
function startEarly(id) {
  dropEarly();
  const view = `/api/encounters/${id}/original?view=1`;
  if (!state.pdfStarted || state.outdated || state.leaving || idle.gone || typeof AbortController !== 'function' || !pdfCapable()) return;
  if (!state.keptViews.has(view) && state.viewHints.get(id) !== true) return;
  const early = { view, abort: new AbortController(), moved: null, result: null };
  early.result = downloadDocument(view, early.abort.signal, () => early.moved?.());
  early.result.catch(() => {});
  state.early = early;
}

function takeEarly(view) {
  const early = state.early;
  if (!early || early.view !== view) return null;
  state.early = null;
  return early;
}

function dropEarly() {
  state.early?.abort.abort();
  state.early = null;
}

function pdfAssets() {
  const data = (typeof document === 'object' && document.body?.dataset) || {};
  const asset = value => (typeof value === 'string' && /^\/static\/[\w./-]+\.mjs$/.test(value) ? value : '');
  return { module: asset(data.pdfModule), worker: asset(data.pdfWorker) };
}

// What this browser must have natively for the viewer to draw a PDF and mark its words. A browser without any of it is
// not offered the viewer (the library is not even downloaded): the browser's own viewer is framed and the note says
// marking needs a newer browser. Measured (DECISIONS D368, fix round 2) in Chromium only, each candidate deleted in the
// page and in the library's worker (typeof read before and after), then the preview's PDFs and the walk's gi-02 opened and
// every quote chosen: asked for here is what our own code calls, what broke the drawing or the marking when deleted, and
// what the library calls with no stand-in on a path the viewer can take. What the legacy build puts back
// itself, and what it does not that the documents never needed, are listed in CORE-UX-DESIGN.md ("Browsers that mark");
// Iterator take and drop are put back in the page only. OffscreenCanvas, ImageDecoder, CompressionStream and
// DecompressionStream are used only where they exist. Dynamic import() is this script's own syntax, so a browser running
// the script has it; the library's own syntax (class static blocks: Chrome 94, Firefox 93, Safari 16.4) is older than the
// newest built-in asked for here. A worker has its page's built-ins, so the page answers for the worker.
function pdfCapable() {
  return typeof IntersectionObserver === 'function'  // our code: pages are drawn only near the visible area
    && typeof ResizeObserver === 'function'  // our code: pages are refitted when the panel's width changes
    && typeof Intl === 'object' && typeof Intl.Segmenter === 'function'  // our code: the matcher's characters
    && typeof Promise.withResolvers === 'function'  // measured: the library cannot start its worker, nor the worker read a PDF
    && typeof ArrayBuffer.prototype.transferToFixedLength === 'function'  // measured: the worker sends no font; pages draw blank
    && typeof Array.prototype.at === 'function'  // measured: the library's worker does not start
    && typeof structuredClone === 'function'  // read: an image shared by pages; the library's stand-in for its worker
    && typeof Object.hasOwn === 'function';  // read: the library's cleanup of a closed document (its fonts, its download)
}

// The library's module, with its worker's address set (GlobalWorkerOptions.workerSrc, where the viewer starts its own
// worker: startWorker): one load for every document while it works. A load that fails or is given up, or whose worker
// failed (forgetPdfLibrary), is not kept, and the next document tries again at fresh addresses (?attempt=2, 3, ..., for
// the module and the worker): the browser remembers a module that failed to load for the life of the page, by its
// address.
function loadPdfLibrary() {
  if (!state.pdfLibrary) {
    const { module, worker } = pdfAssets();
    state.pdfAttempt += 1;
    const attempt = state.pdfAttempt;
    const address = value => (attempt > 1 ? `${value}?attempt=${attempt}` : value);
    const loading = module && worker
      ? Promise.resolve().then(() => PDF_IMPORT.load(address(module))).then(library => {
        library.GlobalWorkerOptions.workerSrc = address(worker);
        return library;
      })
      : Promise.reject(new Error('The page names no PDF library.'));
    state.pdfLibrary = loading;
    // a failed load is forgotten at once (R2-11); one past its time limit, by its viewer (openPdf)
    loading.catch(() => forgetPdfLibrary(loading));
  }
  return state.pdfLibrary;
}

function forgetPdfLibrary(loading) {
  if (state.pdfLibrary !== loading) return;
  state.pdfLibrary = null;
  state.pdfStarted = false;  // tried again at fresh addresses, so fetched again (R2-12)
}

// R2-10: the worker made ready ahead, asked for in `ms`, when the browser is idle (one idle callback waits at a time).
function scheduleStandby(ms) {
  clearTimeout(state.standbyTimer);
  state.standbyTimer = 0;
  if (!state.standbyOn) return;
  state.standbyTimer = setTimeout(() => {
    state.standbyTimer = 0;
    if (typeof requestIdleCallback === 'function') state.standbyIdle ||= requestIdleCallback(() => { state.standbyIdle = 0; startStandby(); }, { timeout: PDF_STANDBY.idle });
    else startStandby();
  }, ms);
}

// Starts the one worker made ready ahead (and the library) on a page that has routed, holds none, is not leaving or
// signed out, saves no data and can draw a PDF. It holds no document: the next one takes it as its own (takeWorker;
// D368, A4). A failed one is ended; after PDF_STANDBY.fails failures, none is made.
function startStandby() {
  if (!state.standbyOn || state.pdfStandby || state.leaving || idle.gone || globalThis.navigator?.connection?.saveData === true || !pdfCapable()) return;
  const standby = { thread: null, address: '', ready: null, taken: false, failed: null, end: null };
  state.pdfStandby = standby;
  standby.failed = () => {
    if (standby.taken) return;
    if (state.pdfStandby === standby) {
      state.pdfStandby = null;
      state.standbyFails += 1;
      if (state.standbyFails >= PDF_STANDBY.fails) state.standbyOn = false;
    }
    standby.thread?.terminate();
  };
  const loading = loadPdfLibrary();
  // ended before it is ready, its wait settles at once
  const ended = new Promise((resolve, reject) => { standby.end = () => reject(new Error('The worker made ready ahead was ended.')); });
  standby.ready = withinLimit(Promise.race([ended, (async () => {
    const library = await loading;
    if (state.pdfStandby !== standby) throw new Error('The worker made ready ahead is no longer wanted.');
    standby.address = library.GlobalWorkerOptions.workerSrc;
    const thread = await startWorker(standby, standby.address, loading);
    thread.addEventListener('error', standby.failed);
    return thread;
  })()]), PDF_VIEW.limitMs);
  standby.ready.catch(standby.failed);
}

function endStandby() {
  clearTimeout(state.standbyTimer);
  state.standbyTimer = 0;
  if (state.standbyFrame) cancelAnimationFrame(state.standbyFrame);
  state.standbyFrame = 0;
  if (state.standbyIdle && typeof cancelIdleCallback === 'function') cancelIdleCallback(state.standbyIdle);
  state.standbyIdle = 0;
  const standby = state.pdfStandby;
  state.pdfStandby = null;
  standby?.end?.();
  standby?.thread?.terminate();
}

// The viewer's own worker: the one made ready ahead for this address, the viewer's at once, else a new one; one made
// ready for another address (?attempt=n) is ended.
function takeWorker(viewer, address, loading) {
  const standby = state.pdfStandby;
  if (!standby || standby.address !== address || !standby.thread) {
    if (standby?.address && standby.address !== address) endStandby();
    return startWorker(viewer, address, loading);
  }
  state.pdfStandby = null;
  standby.taken = true;
  viewer.thread = standby.thread;
  return standby.ready.then(thread => {
    thread.removeEventListener('error', standby.failed);
    return thread;
  });
}

// R2-18: at every end - sign-out, idle, cap, a 401, another tab, a forced password change, a refused document,
// pagehide - the early view, the kept copies (overwritten), the hints and the worker made ready ahead go; the view
// `opening` keeps its early view, its copy and its own opening (pagehide's Event is no view).
function forgetMemory(opening = '') {
  const spared = typeof opening === 'string' ? opening : '';
  if (!spared) state.wipes += 1;
  if (!spared || state.early?.view !== spared) dropEarly();
  for (const [view, { data }] of state.keptViews) {
    if (view === spared) continue;
    data.fill(0);
    state.keptViews.delete(view);
  }
  state.viewHints.clear();
  endStandby();
}

// I1-16: a document whose detail names no PDF view keeps no copy, whichever of its answers came first.
function dropRefused(doc) {
  const own = `/api/encounters/${doc?.id}/original?view=1`;
  if (viewerKind(doc?.document) !== 'pdf') dropView(own, state.keptViews.get(own));
}

// Draws the PDF of a document viewed as one into #documentViewer (after a full redraw of the review page).
function mountViewer(doc) {
  closeViewer();
  const element = $('#documentViewer');
  const view = safeViewUrl(element?.dataset?.viewUrl);
  if (!element || !view || viewerKind(doc?.document) !== 'pdf') {
    dropEarly();
    dropRefused(doc);
    return;
  }
  // thread: the viewer's own worker; worker: the library's handle on it; download: the download's abort; watchdog: the
  // waits on the library (libraryWatchdog); quoteScroll: the quote's page while the scroll to it is under way; inputs: the
  // listeners that see the member scroll the viewer; queue and busy: the pages asked to be drawn, and the one drawing
  const viewer = {
    element, view, conversion: conversionOf(record(doc?.document).view_conversion), name: documentName(record(doc?.document)), mode: 'loading', library: null, thread: null, worker: null, task: null,
    download: null, watchdog: null, pages: [], texts: new Map(), prepared: new Map(), mark: null, pending: null, chosen: null,
    markSerial: 0, reveal: 0, quoteScroll: null, frame: null, framePage: null, fallback: '', zoom: ZOOM_FIT, watch: null,
    resize: null, onScroll: null, inputs: [], unwatchRatio: null, width: 0, ratio: 1, stallTimer: 0, resizeTimer: 0,
    settleTimer: 0, labelFrame: 0, queue: [], busy: null, drawTimer: 0, scrolledAt: 0,
  };
  state.viewer = viewer;
  openPdf(viewer);
}

function closeViewer() {
  const viewer = state.viewer;
  state.viewer = null;
  if (!viewer) return;
  stopPdf(viewer);
  viewer.mode = 'closed';
  scheduleStandby(PDF_STANDBY.next);
}

async function openPdf(viewer) {
  const opening = () => state.viewer === viewer && viewer.mode === 'loading';
  const wipes = state.wipes;
  // a browser without what marking needs is not given the library at all
  if (!pdfCapable()) {
    fallbackViewer(viewer, 'browser');
    return;
  }
  // R2-12: once a worker has started in this page, the document is asked for beside the library; else after it
  const early = takeEarly(viewer.view);
  if (!early) dropEarly();
  let downloading = early || state.pdfStarted ? downloadFor(viewer, early) : null;
  // the library and the viewer's worker, within the time limit: one that does not start is the library's failure, and
  // the next document tries it afresh; a viewer closed meanwhile concludes nothing (R2-11)
  const loading = loadPdfLibrary();
  try {
    await withinLimit((async () => {
      const library = await loading;
      if (!opening()) return;
      viewer.library = library;
      const thread = await takeWorker(viewer, library.GlobalWorkerOptions.workerSrc, loading);
      if (!opening()) return;
      viewer.worker = new library.PDFWorker({ port: thread, verbosity: library.VerbosityLevel.ERRORS });
    })(), PDF_VIEW.limitMs);
  } catch {
    if (!opening()) return;
    forgetPdfLibrary(loading);
    fallbackViewer(viewer, 'library');
    return;
  }
  if (!opening()) return;
  const { library, thread } = viewer;
  // every message of the worker is the library answering (the watchdog); the worker failing once it has started is the
  // library not working, and the next document tries it again
  thread.addEventListener('message', () => {
    if (viewer.thread === thread) libraryWatchdog(viewer).answer();
  });
  thread.addEventListener('error', () => {
    if (state.viewer !== viewer || viewer.thread !== thread) return;
    forgetPdfLibrary(loading);
    fallbackViewer(viewer, 'library');
  });
  downloading = downloading || downloadFor(viewer, null);
  let got = await downloading;
  // I2-1: drawn only as the conversion the detail names. The click's early answer, read before the detail, is asked
  // again; any other is newer than the detail, which is read again (its redraw asks afresh)
  if (got && early && got.conversion !== viewer.conversion && opening()) got = await downloadFor(viewer, null);
  if (!got || !opening()) return;
  if (got.conversion !== viewer.conversion) {
    startStall(viewer);
    refreshDocument({ poll: true });
    return;
  }
  const { data, tag, held } = got;
  // R2-15: the copy kept (a tagged 200's, once opened) is made first: the library takes the array it is given
  const copy = tag && !held && data.byteLength <= KEPT_VIEWS.bytes ? data.slice(0) : null;
  startStall(viewer);  // the library's parse, under the download's limit
  let pdf;
  try {
    const worker = new URL(library.GlobalWorkerOptions.workerSrc, location.href);
    viewer.task = library.getDocument({
      data, isEvalSupported: false, enableXfa: false, useWasm: false,
      wasmUrl: new URL('../../wasm/', worker).href, standardFontDataUrl: new URL('../../standard_fonts/', worker).href,
      useSystemFonts: true, disableWorkerRendering: true, stopAtErrors: false, verbosity: library.VerbosityLevel.ERRORS,
      worker: viewer.worker,
    });
    pdf = await viewer.task.promise;
  } catch {
    stopStall(viewer);
    fallbackViewer(viewer, 'document');
    return;
  }
  // once the document has opened, the download's timer stops; the watchdog watches the waits on the library from here
  stopStall(viewer);
  if (!opening()) return;
  if (!(Number.isInteger(pdf?.numPages) && pdf.numPages >= 1)) {
    fallbackViewer(viewer, 'document');
    return;
  }
  if (copy && state.wipes === wipes) keepView(viewer.view, tag, copy);
  else copy?.fill(0);  // an end came while it opened (R2-18)
  let proxies;
  try {
    proxies = await watched(viewer, Promise.all(Array.from({ length: pdf.numPages }, (_, index) => pdf.getPage(index + 1))));
  } catch (error) {
    fallbackViewer(viewer, error instanceof TimeLimit ? 'library' : 'document');
    return;
  }
  if (!opening()) return;
  buildPages(viewer, proxies);
}

function startStall(viewer) {
  clearTimeout(viewer.stallTimer);
  viewer.stallTimer = setTimeout(() => {
    if (viewer.mode === 'loading') fallbackViewer(viewer, 'slow');
  }, PDF_VIEW.stallMs);
}

function stopStall(viewer) {
  clearTimeout(viewer.stallTimer);
  viewer.stallTimer = 0;
}

// R2-12: the viewer's download of its document: what it got, or null once said not to have come or the viewer left
// loading; a stalled one is 'slow', a failed one 'download', at once.
function downloadFor(viewer, early) {
  const opening = () => state.viewer === viewer && viewer.mode === 'loading';
  const moved = () => { if (opening()) startStall(viewer); };
  viewer.download = early ? early.abort : typeof AbortController === 'function' ? new AbortController() : null;
  startStall(viewer);
  if (early) early.moved = moved;
  const fetching = early ? early.result : downloadDocument(viewer.view, viewer.download?.signal, moved);
  return fetching.then(got => {
    if (!opening()) return null;
    stopStall(viewer);
    return got;
  }, () => {
    if (!opening()) return null;
    stopStall(viewer);
    fallbackViewer(viewer, 'download');
    return null;
  });
}

// Every page as a placeholder of its size; pages near the visible area are drawn (IntersectionObserver), the others
// released, and a new width (ResizeObserver, debounced) or pixel ratio (watchRatio) re-fits and redraws them.
function buildPages(viewer, proxies) {
  const holder = document.createElement('div');
  holder.className = 'pdf-pages';
  viewer.pages = proxies.map((proxy, index) => {
    const element = document.createElement('div');
    element.className = 'pdf-page';
    element.dataset.page = String(index + 1);
    element.setAttribute('role', 'group');
    element.setAttribute('aria-label', `Page ${index + 1} of ${proxies.length}`);
    holder.append(element);
    return { number: index + 1, proxy, element, viewport: null, near: false, drawn: '', drawing: '', serial: 0, render: null,
      layer: null, painted: [] };
  });
  viewer.element.replaceChildren(holder);
  viewer.element.dataset.mode = 'pdf';
  viewer.mode = 'pdf';
  layoutPages(viewer);
  viewer.watch = new IntersectionObserver(entries => nearPages(viewer, entries), { root: viewer.element, rootMargin: PDF_VIEW.near });
  for (const page of viewer.pages) viewer.watch.observe(page.element);
  viewer.resize = new ResizeObserver(() => {
    clearTimeout(viewer.resizeTimer);
    viewer.resizeTimer = setTimeout(() => relayoutPages(viewer), PDF_VIEW.resizeMs);
  });
  viewer.resize.observe(viewer.element);
  watchRatio(viewer);
  // R2-13: page 1 at once, unless a quote waits to be shown on its own page
  if (!viewer.pending) {
    viewer.pages[0].near = true;
    drawPage(viewer, viewer.pages[0]);
  }
  viewer.onScroll = () => {
    viewer.scrolledAt = Date.now();
    if (!viewer.labelFrame) viewer.labelFrame = requestAnimationFrame(() => { viewer.labelFrame = 0; showPageLabel(viewer); });
  };
  viewer.element.addEventListener('scroll', viewer.onScroll, { passive: true });
  // the member's own scrolling (a wheel, a touch, a scroll key, a pointer on the viewer) ends the scroll to a quote and
  // its reveal, so nothing moves the view later unasked (A7)
  const own = () => dropQuoteScroll(viewer);
  viewer.inputs = [['wheel', own], ['touchstart', own], ['pointerdown', own], ['keydown', event => { if (SCROLL_KEYS.has(event?.key)) own(); }]];
  for (const [type, listener] of viewer.inputs) viewer.element.addEventListener(type, listener, { passive: true });
  showPageLabel(viewer);
  showZoom(viewer);
  if (viewer.pending) {
    const { quote, key } = viewer.pending;
    viewer.pending = null;
    showPdfQuote(viewer, quote, key);
  }
}

// A change of the screen's pixel ratio with no change of size (the window moved to another screen) redraws the pages:
// a query for the ratio now, asked again after every change.
function watchRatio(viewer) {
  viewer.unwatchRatio?.();
  if (typeof window.matchMedia !== 'function') return;
  const query = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
  const changed = () => {
    viewer.unwatchRatio?.();
    if (state.viewer !== viewer || viewer.mode !== 'pdf') return;
    relayoutPages(viewer);
    watchRatio(viewer);
  };
  query.addEventListener?.('change', changed);
  viewer.unwatchRatio = () => {
    query.removeEventListener?.('change', changed);
    viewer.unwatchRatio = null;
  };
}

// (not named innerWidth: a function declared here is a property of window, and window.innerWidth is read)
function viewerWidth(element) {
  const style = getComputedStyle(element);
  return Math.max(1, element.clientWidth - parseFloat(style.paddingLeft || '0') - parseFloat(style.paddingRight || '0'));
}

// Each page fitted to the viewer's width at the zoom chosen: its placeholder takes the page's size, and the text layer its
// scale.
function layoutPages(viewer) {
  viewer.width = viewerWidth(viewer.element);
  viewer.ratio = window.devicePixelRatio || 1;
  const zoom = ZOOM_STEPS[viewer.zoom] || 1;
  for (const page of viewer.pages) {
    const natural = page.proxy.getViewport({ scale: 1 });
    page.viewport = page.proxy.getViewport({ scale: (viewer.width / natural.width) * zoom });
    const { style } = page.element;
    style.width = `${Math.floor(page.viewport.width)}px`;
    style.height = `${Math.floor(page.viewport.height)}px`;
    style.setProperty('--total-scale-factor', String(page.viewport.scale * (page.viewport.userUnit || 1)));
    style.setProperty('--scale-round-x', '1px');
    style.setProperty('--scale-round-y', '1px');
  }
}

// After a new width, pixel ratio or zoom (`zoomed`): the pages laid out again, the page at the top of the view kept there
// at the same place in it (and the middle of what shows across kept in the middle), and the pages near the view redrawn.
// While a quote's scroll is under way or its reveal is armed, the relayout keeps the quote (A7): it is scrolled to again,
// to its first mark where its page is drawn, else to its page's top with the reveal kept.
function relayoutPages(viewer, zoomed = false) {
  if (state.viewer !== viewer || viewer.mode !== 'pdf') return;
  if (!zoomed && Math.abs(viewerWidth(viewer.element) - viewer.width) < 1 && (window.devicePixelRatio || 1) === viewer.ratio) return;
  const { element } = viewer;
  const quote = viewer.pages[(viewer.quoteScroll?.page || viewer.reveal || 0) - 1] || null;
  const top = element.scrollTop;
  const anchor = pageAtOffset(viewer, top);
  const within = anchor ? (top - anchor.element.offsetTop) / Math.max(1, anchor.element.offsetHeight) : 0;
  const across = (element.scrollLeft + element.clientWidth / 2) / Math.max(1, element.scrollWidth);
  layoutPages(viewer);
  if (anchor) element.scrollTop = anchor.element.offsetTop + within * anchor.element.offsetHeight;
  element.scrollLeft = Math.max(0, across * element.scrollWidth - element.clientWidth / 2);
  for (const page of viewer.pages) if (page.near) drawPage(viewer, page);
  if (quote) scrollToQuote(viewer, quote);
}

// The toolbar's zoom: "Zoom out", "Zoom in" (one step of ZOOM_STEPS) and "Fit width" (100%).
function zoomViewer(action) {
  const viewer = state.viewer;
  if (!viewer || viewer.mode !== 'pdf') return;
  const step = { in: 1, out: -1 }[action] || 0;
  const next = action === 'fit' ? ZOOM_FIT : Math.min(ZOOM_STEPS.length - 1, Math.max(0, viewer.zoom + step));
  if (next === viewer.zoom) return;
  viewer.zoom = next;
  relayoutPages(viewer, true);
  showZoom(viewer);
}

// The zoom controls, shown with the drawn pages only: the level, and a button that can do nothing is said to be off
// (aria-disabled, so it keeps the focus).
function showZoom(viewer) {
  const group = $('#viewerZoom');
  if (!group) return;
  const drawn = Boolean(viewer) && viewer.mode === 'pdf';
  group.hidden = !drawn;
  if (!drawn) return;
  const level = $('#zoomLevel');
  if (level) level.textContent = `${Math.round(ZOOM_STEPS[viewer.zoom] * 100)}%`;
  for (const [action, off] of [['out', viewer.zoom === 0], ['in', viewer.zoom === ZOOM_STEPS.length - 1], ['fit', viewer.zoom === ZOOM_FIT]]) {
    const button = $(`#viewerZoom [data-zoom="${action}"]`);
    if (button) button.setAttribute('aria-disabled', String(off));
  }
}

// The last page whose top is at or above `offset` in the viewer, else the first page.
function pageAtOffset(viewer, offset) {
  let found = viewer.pages[0];
  for (const page of viewer.pages) if (page.element.offsetTop <= offset) found = page;
  return found;
}

function nearPages(viewer, entries) {
  if (state.viewer !== viewer || viewer.mode !== 'pdf') return;
  for (const entry of entries) {
    const page = viewer.pages[Number(entry.target.dataset.page) - 1];
    if (!page) continue;
    page.near = entry.isIntersecting;
    if (page.near) drawPage(viewer, page);
    else releasePage(page);
  }
}

// The canvas's pixels per CSS pixel: the screen's, unless a page would need more pixels than one canvas should hold.
function outputRatio(viewport, ratio) {
  const area = viewport.width * viewport.height;
  return area * ratio * ratio > PDF_VIEW.maxCanvasPixels ? Math.sqrt(PDF_VIEW.maxCanvasPixels / area) : ratio;
}

function pageContent(viewer, number) {
  if (!viewer.texts.has(number)) viewer.texts.set(number, viewer.pages[number - 1].proxy.getTextContent());
  return viewer.texts.get(number);
}

// A page's text, prepared to be searched (pageText), once per document: the quotes chosen and the pages drawn share it.
function preparedPage(viewer, number, content) {
  if (!viewer.prepared.has(number)) viewer.prepared.set(number, pageText(list(content?.items).filter(item => typeof item?.str === 'string')));
  return viewer.prepared.get(number);
}

// Asks for one page to be drawn at the current size (`drawPage`). The pages are drawn one at a time, in the order asked,
// the page a quote is waiting to be shown on first (viewer.reveal): the library's worker decodes one page's images at a
// time and answers as each is done, so a busy scan keeps answering the watchdog (several pages asked for at once have
// their images decoded as one batch before any is sent), and a page that leaves the view before its turn is never
// decoded at all.
// A page asked for at a new size while it is being drawn is not cancelled: its drawing finishes and is shown, and the
// page is drawn again at the new size from what the library has already decoded for it (a cancelled drawing would have
// its images decoded again).
function drawPage(viewer, page) {
  const key = `${page.viewport.scale} ${viewer.ratio}`;
  if (page.drawn === key || page.drawing === key) return;
  if (!Array.isArray(viewer.queue)) viewer.queue = [];
  if (viewer.busy !== page) cancelPage(page);
  page.drawing = key;
  if (!viewer.queue.includes(page)) viewer.queue.push(page);
  drawNext(viewer);
}

// Starts the next page asked for, once the page being drawn is done (or given up) and the view has stopped scrolling for
// PDF_VIEW.settleMs: a page the view only passes (a scroll to a quote, the member's own scrolling) is let go before its
// turn, so the library never decodes it.
function drawNext(viewer) {
  if (viewer.busy || state.viewer !== viewer || viewer.mode !== 'pdf' || !Array.isArray(viewer.queue)) return;
  const still = Date.now() - (viewer.scrolledAt || 0);
  if (viewer.queue.length && still < PDF_VIEW.settleMs) {
    if (!viewer.drawTimer) viewer.drawTimer = setTimeout(() => { viewer.drawTimer = 0; drawNext(viewer); }, PDF_VIEW.settleMs - still);
    return;
  }
  while (viewer.queue.length) {
    const first = viewer.queue.findIndex(item => item.number === viewer.reveal);
    const [page] = viewer.queue.splice(Math.max(0, first), 1);
    if (!page.drawing) continue;  // released while it waited
    viewer.busy = page;
    renderPage(viewer, page).catch(() => {}).finally(() => {
      if (viewer.busy === page) viewer.busy = null;
      drawNext(viewer);
    });
    return;
  }
}

// Draws one page: its canvas (annotation appearances drawn on it), then its text layer from the same text content the
// quotes are located in (an overprint copy's span says so, data-overprint), then the marks of the chosen quote on that
// page. A page redrawn keeps its old drawing until the new one is ready. Each wait is the watchdog's (watched): one given
// up because the library has not answered gives the frame, as the library not working; one that fails, as a document it
// cannot draw.
async function renderPage(viewer, page) {
  const key = `${page.viewport.scale} ${viewer.ratio}`;
  const { serial, viewport } = page;
  const { library } = viewer;
  const live = () => state.viewer === viewer && viewer.mode === 'pdf' && page.serial === serial;
  const ratio = outputRatio(viewport, viewer.ratio);
  const canvas = document.createElement('canvas');
  canvas.width = Math.floor(viewport.width * ratio);
  canvas.height = Math.floor(viewport.height * ratio);
  canvas.setAttribute('aria-hidden', 'true');
  try {
    page.render = page.proxy.render({ canvas, viewport, annotationMode: library.AnnotationMode.ENABLE,
      transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] });
    // R2-13: the text is read beside the drawing; both are shown together
    const reading = watched(viewer, pageContent(viewer, page.number), page);
    reading.catch(() => {});
    await watched(viewer, page.render.promise, page);
    const content = await reading;
    // D-R2-54: the frame that ends a page's drawing is not one long task with all the rest: a later page (another is
    // drawn) is shown in the next task; the first page shown, at once (R2-13), and its text, unless already prepared to
    // be searched (a redraw, whose marks are then painted with it), prepared in the next task
    const later = viewer.pages.some(other => other !== page && other.drawn);
    if (later) await nextTask();
    if (!live()) return;
    const text = document.createElement('div');
    text.className = 'pdf-text';
    page.drawn = '';  // no mark is painted on a text layer still being built
    page.element.replaceChildren(canvas, text);
    page.layer = new library.TextLayer({ textContentSource: content, container: text, viewport });
    page.painted = [];
    await watched(viewer, page.layer.render(), page);
    if (!later && !viewer.prepared.has(page.number)) await nextTask();
    if (!live()) return;
    for (const item of preparedPage(viewer, page.number, content).copies) page.layer.textDivs[item]?.setAttribute('data-overprint', '1');
    page.drawn = key;
    scheduleStandby(PDF_STANDBY.next);
    if (page.drawing === key) page.drawing = '';  // else asked for at another size meanwhile: it is queued again
    paintPage(viewer, page);
    if (viewer.reveal === page.number) {
      viewer.reveal = 0;
      scrollToQuote(viewer, page);
    }
  } catch (error) {
    if (!live() || ['RenderingCancelledException', 'AbortException'].includes(error?.name)) return;
    fallbackViewer(viewer, error instanceof TimeLimit ? 'library' : 'document');
  }
}

// A page's drawing given up (it left the view, or is drawn again): the drawing is cancelled and its waits let go.
function cancelPage(page) {
  page.serial += 1;
  page.drawing = '';
  page.render?.cancel();
  page.render = null;
  state.viewer?.watchdog?.forget(page);
}

// A page away from the view goes back to its placeholder, and the library lets go of what it decoded to draw it (its
// images); drawn again, it is decoded again.
function releasePage(page) {
  cancelPage(page);
  page.layer?.cancel();
  page.layer = null;
  page.painted = [];
  page.drawn = '';
  page.element.replaceChildren();
  page.proxy?.cleanup?.();
}

// The chosen quote's marks on one drawn page: the text layer's spans of the marked items, each split into its unmarked
// text and mark.pdf-mark[data-occurrence] around exactly the marked characters. Text only, never markup.
function paintPage(viewer, page) {
  if (!page.layer || !page.drawn) return;
  const divs = page.layer.textDivs;
  const strings = page.layer.textContentItemsStr;
  for (const item of page.painted) if (divs[item]) divs[item].textContent = strings[item];
  page.painted = [];
  const byItem = new Map();
  for (const mark of list(viewer.mark?.result?.marks?.[page.number])) {
    if (!byItem.has(mark.item)) byItem.set(mark.item, []);
    byItem.get(mark.item).push(mark);
  }
  for (const [item, parts] of byItem) {
    const div = divs[item];
    const value = strings[item];
    if (!div || typeof value !== 'string') continue;
    div.textContent = '';
    let at = 0;
    for (const part of parts) {
      if (part.start > at) div.append(value.slice(at, part.start));
      const mark = document.createElement('mark');
      mark.className = 'pdf-mark';
      mark.dataset.occurrence = String(part.occurrence);
      mark.textContent = value.slice(part.start, part.end);
      div.append(mark);
      at = part.end;
    }
    if (at < value.length) div.append(value.slice(at));
    page.painted.push(item);
  }
}

// Scrolls the viewer to a page: to its first mark when the page is drawn and marked, else to its top. Where the pages are
// wider than the viewer (a zoom above fit width), the first mark is brought into view across too (A6): if it fits within
// the viewer's width with PDF_VIEW.gap on each side, by the least distance that shows all of it; if not, with its start
// PDF_VIEW.gap from the viewer's start. The scroll is the quote's until the view stops moving (followQuoteScroll).
function scrollToQuote(viewer, page) {
  const { element } = viewer;
  let top = page.element.offsetTop - PDF_VIEW.gap;
  let left = null;
  const mark = page.drawn ? page.element.querySelector('.pdf-mark') : null;
  if (mark) {
    const box = mark.getBoundingClientRect();
    const frame = page.element.getBoundingClientRect();
    top = page.element.offsetTop + (box.top - frame.top) - element.clientHeight / 3;
    if (element.scrollWidth > element.clientWidth + 1) {
      const start = page.element.offsetLeft + (box.left - frame.left);
      const end = start + box.width;
      const shown = element.scrollLeft;
      if (end - start + 2 * PDF_VIEW.gap <= element.clientWidth) {
        if (start - PDF_VIEW.gap < shown) left = start - PDF_VIEW.gap;
        else if (end + PDF_VIEW.gap > shown + element.clientWidth) left = end + PDF_VIEW.gap - element.clientWidth;
      } else {
        left = start - PDF_VIEW.gap;
      }
    }
  }
  const target = { top: Math.max(0, top), behavior: scrollBehavior() };
  if (left !== null) target.left = Math.max(0, Math.min(left, element.scrollWidth - element.clientWidth));
  element.scrollTo(target);
  followQuoteScroll(viewer, page.number);
}

// A quote's scroll is under way (viewer.quoteScroll) from scrollToQuote until the view stops moving: looked at every
// PDF_VIEW.settleMs, it ends at the first look that finds the view where the last one did.
function followQuoteScroll(viewer, number) {
  clearTimeout(viewer.settleTimer);
  const { element } = viewer;
  const place = () => `${element.scrollTop} ${element.scrollLeft}`;
  const scroll = { page: number };
  viewer.quoteScroll = scroll;
  let last = place();
  const look = () => {
    viewer.settleTimer = 0;
    if (viewer.quoteScroll !== scroll) return;
    const now = place();
    if (now === last || state.viewer !== viewer || viewer.mode !== 'pdf') {
      viewer.quoteScroll = null;
      return;
    }
    last = now;
    viewer.settleTimer = setTimeout(look, PDF_VIEW.settleMs);
  };
  viewer.settleTimer = setTimeout(look, PDF_VIEW.settleMs);
}

// The scroll to a quote and its reveal end: the member scrolled the viewer, or another quote or coding review came.
function dropQuoteScroll(viewer) {
  clearTimeout(viewer.settleTimer);
  viewer.settleTimer = 0;
  viewer.quoteScroll = null;
  viewer.reveal = 0;
}

function showPageLabel(viewer) {
  const label = $('#viewerPage');
  if (!label || viewer.mode !== 'pdf' || !viewer.pages.length) return;
  const middle = viewer.element.scrollTop + viewer.element.clientHeight / 2;
  const current = pageAtOffset(viewer, middle);
  label.textContent = `Page ${current.number} of ${viewer.pages.length}`;
}

// Lets the page's own work run between slices of a long one.
function nextTask() {
  return new Promise(resolve => setTimeout(resolve, 0));
}

// One quote chosen in a PDF. First, before anything is waited on, what was shown of the quote chosen before goes (A2): its
// mark (so nothing of it is painted on a page drawn meanwhile), its marks on every drawn page, the mark state kept on
// #documentViewer and the note. Then the text of its page (and the next) or of every page is read, one page at a time,
// each read under the watchdog, and prepared once per document (preparedPage), in slices that let the page breathe; then
// the quote is located (locateQuote), its marks painted on every drawn page, the note and the mark state set and the page
// scrolled to. A quote whose pages are prepared already is shown in the same task as the clearing, so nothing flickers.
// The quote being chosen is kept (viewer.chosen), so a frame shown meanwhile names its page.
async function showPdfQuote(viewer, quote, key) {
  if (viewer.mode === 'frame') return frameQuote(viewer, quote);
  viewer.chosen = { quote, key };
  viewer.mark = null;
  dropQuoteScroll(viewer);
  for (const item of viewer.pages) paintPage(viewer, item);
  setMarkState(viewer.element, '', null);
  setMarkNote('');
  if (viewer.mode !== 'pdf') {
    viewer.pending = { quote, key };
    return undefined;
  }
  const serial = ++viewer.markSerial;
  const live = () => state.viewer === viewer && viewer.mode === 'pdf' && viewer.markSerial === serial;
  const count = viewer.pages.length;
  const page = quotePage(quote);
  const wanted = page ? [page, page + 1].filter(number => number <= count) : viewer.pages.map(item => item.number);
  let slice = Date.now();
  try {
    for (const number of wanted) {
      if (viewer.prepared.has(number)) continue;
      const content = await watched(viewer, pageContent(viewer, number));
      if (!live()) return undefined;
      preparedPage(viewer, number, content);
      if (Date.now() - slice > PDF_VIEW.sliceMs) {
        await nextTask();
        if (!live()) return undefined;
        slice = Date.now();
      }
    }
  } catch (error) {
    if (!live()) return undefined;
    viewer.pending = { quote, key };
    fallbackViewer(viewer, error instanceof TimeLimit ? 'library' : 'document');
    return undefined;
  }
  const result = locateQuote(quote, Array.from({ length: count }, () => null), viewer.prepared);
  viewer.mark = { key, quote, result };
  for (const item of viewer.pages) paintPage(viewer, item);
  setMarkState(viewer.element, key, result);
  setMarkNote(markNote(result), result.status !== 'marked');
  const target = viewer.pages[(result.pages[0] || (page && page <= count ? page : 0)) - 1];
  if (target) {
    viewer.reveal = result.status === 'marked' && !target.drawn ? target.number : 0;
    scrollToQuote(viewer, target);
  }
  return result;
}

// The frame (the browser's own viewer) and a quote chosen in it: a quote on another page than the frame was opened at
// gets a new frame at its page (the browser's viewer opens #page=N only as its frame loads; changing the address of a
// loaded frame moves nothing); its own page, or no page, leaves the frame as it is. Nothing is marked, and the note says
// why and names the quote's page.
function frameQuote(viewer, quote) {
  const page = quotePage(quote);
  if (page && page !== viewer.framePage) showFrame(viewer, page);
  setMarkState(viewer.element, '', null);
  setMarkNote(frameNote(page, viewer.fallback), true);
  return undefined;
}

function showFrame(viewer, page) {
  const frame = document.createElement('iframe');
  frame.className = 'viewer-fallback';
  frame.title = `Original document: ${viewer.name}`;
  frame.setAttribute('referrerpolicy', 'same-origin');
  frame.src = viewerUrl(viewer.view, page);
  viewer.element.replaceChildren(frame);
  viewer.frame = frame;
  viewer.framePage = page || null;
}

// Where the library cannot run or cannot draw the document, or the document cannot be downloaded, the browser's own
// viewer is framed in its place (today's viewer), at the page of the quote being chosen, if any. `reason` is why, as
// frameNote says it: 'browser', 'library', 'document', 'slow' or 'download'; the viewer element keeps it
// (data-fallback) for the walk.
function fallbackViewer(viewer, reason) {
  if (state.viewer !== viewer || viewer.mode === 'frame' || viewer.mode === 'closed') return;
  stopPdf(viewer);
  const chosen = viewer.pending?.quote || viewer.chosen?.quote || null;
  const page = quotePage(chosen);
  viewer.mode = 'frame';
  viewer.fallback = lookup(FRAME_REASONS, reason, null) ? reason : 'document';
  viewer.pending = null;
  viewer.mark = null;
  showFrame(viewer, page);
  viewer.element.dataset.mode = 'frame';
  viewer.element.dataset.fallback = viewer.fallback;
  const label = $('#viewerPage');
  if (label) label.textContent = '';
  showZoom(viewer);
  setMarkState(viewer.element, '', null);
  if (chosen) setMarkNote(frameNote(page, viewer.fallback), true);
}

function stopPdf(viewer) {
  clearTimeout(viewer.stallTimer);
  clearTimeout(viewer.resizeTimer);
  clearTimeout(viewer.settleTimer);
  clearTimeout(viewer.drawTimer);
  if (viewer.labelFrame) cancelAnimationFrame(viewer.labelFrame);
  viewer.download?.abort();
  viewer.watchdog?.stop();
  viewer.watch?.disconnect();
  viewer.resize?.disconnect();
  viewer.unwatchRatio?.();
  if (viewer.onScroll) viewer.element.removeEventListener('scroll', viewer.onScroll);
  for (const [type, listener] of list(viewer.inputs)) viewer.element.removeEventListener(type, listener);
  for (const page of viewer.pages) {
    cancelPage(page);
    page.layer?.cancel();
  }
  // the worker is the viewer's own (A4): the library lets go of the document (within PDF_VIEW.closeMs - a worker that has
  // stopped never answers), then its handle on the worker goes, and the worker itself is ended (the library never ends a
  // worker it was handed)
  const { task, worker, thread } = viewer;
  settleWithin(task?.destroy(), PDF_VIEW.closeMs).then(() => {
    worker?.destroy();
    thread?.terminate();
  });
  Object.assign(viewer, { watch: null, resize: null, onScroll: null, inputs: [], unwatchRatio: null, task: null, worker: null,
    thread: null, download: null, watchdog: null, pages: [], texts: new Map(), prepared: new Map(), labelFrame: 0, stallTimer: 0,
    settleTimer: 0, quoteScroll: null, queue: [], busy: null, drawTimer: 0 });
}

// --- a passage of a text document, marked inside its frame (the text rule: findPassages) ---------------------------

// The document each frame's own load last brought (noteFrameLoad, from boot), or UNREADABLE when this page could not
// read what it brought. A document whose own load has not come (still loading, or a load the browser stopped or that
// broke off: no load event ever comes for those) is not taken as loaded.
const loadedPages = new WeakMap();
const UNREADABLE = {};

function frameDocument(frame) {
  try {
    const page = frame.contentDocument;
    return page && page.body && page.URL !== 'about:blank' && page.readyState === 'complete' ? page : null;
  } catch {
    return null;
  }
}

// A frame's load, heard on the way down to it (boot listens in the capture phase, since load does not bubble). Each
// load of the text viewer's frame paints the quote chosen in it again, so the marks and the note follow what the frame
// now holds (a reload from the frame's own menu, or a first load after a choice). A frame's first, empty document
// (about:blank) is recorded like any other and is never taken as the document (frameDocument).
function noteFrameLoad(event) {
  const frame = event?.target;
  if (frame?.tagName !== 'IFRAME') return;
  let page = null;
  try {
    page = frame.contentDocument;
  } catch {
    page = null;
  }
  loadedPages.set(frame, page || UNREADABLE);
  watchFrameInput(page);
  // the PDF viewer's own frame, and the text viewer's (#documentViewer, the frame itself)
  if (state.viewer?.frame === frame || frame.id === 'documentViewer') noteRefusedFrame(frame);
  if (state.framePassage?.frame === frame) paintFrame(frame);
}

// The browser's own viewer of a PDF, framed where the page cannot draw it, shows whatever the server answered - the front
// door's refusal (429) too, which reads as a broken document. Its own load says the answer, and anything but 200 is said
// under the viewer in plain words (refutation r2, finding 21).
function noteRefusedFrame(frame) {
  let status;
  try {
    status = frame.contentWindow.performance.getEntriesByType('navigation')[0]?.responseStatus;
  } catch {
    // the site's refusals forbid framing, so theirs cannot be read: the session is asked, as a poll, and a 401 or a
    // forced password change's 403 is the end it is (api; R2-18)
    api('/api/session', { poll: true }).catch(() => {});
    return;
  }
  if (!Number.isInteger(status) || status === 0 || status === 200) return;
  if (status === 401 || status === 403) forgetMemory();  // an end (R2-18), as at the viewer's own download
  if (frame.id === 'documentViewer') return;  // the text viewer's frame: paintFrame says what it holds, as in release 1
  frame.dataset.refused = String(status);
  setMarkNote(status === 429 ? FRAME_LIMIT_TEXT : FRAME_REFUSED_TEXT, true);
}

// Input inside a frame of the page - a wheel, a key, a touch in the viewer's framed text - is the member's input as much
// as on the page itself (B5; refutation r2, finding 15): each document a frame loads gets the page's own listeners. A
// document this page cannot read (another origin, the browser's own viewer of a PDF) has none to give.
function watchFrameInput(page) {
  if (!page || typeof page.addEventListener !== 'function') return;
  try {
    for (const type of ACTIVITY_INPUTS) page.addEventListener(type, noteInput, { capture: true, passive: true });
  } catch {
    // a document that refuses listeners: the page's own input still counts
  }
}

// Whether the text frame holds the document this page asked for: 'waiting' until the frame's current document has had
// its own load; 'failed' when what loaded is not the document - something this page cannot read (an answer the frame
// refused to show), an answer other than 200, or a body whose positive size is not the document's (`size`,
// document.size: the view's exact bytes; the edge's own "temporarily unavailable" page, sent while the app restarts, is
// shown in the frame and readable); else 'document'. Where the browser does not tell the answer or a positive size, the
// frame is taken as the document.
function frameHolds(frame, size) {
  let page = null;
  try {
    page = frame.contentDocument;
  } catch {
    page = null;
  }
  const loaded = loadedPages.get(frame);
  if (!page) return loaded === UNREADABLE ? 'failed' : 'waiting';
  if (loaded !== page || !frameDocument(frame)) return 'waiting';
  let entry = null;
  try {
    entry = frame.contentWindow.performance.getEntriesByType('navigation')[0] || null;
  } catch {
    entry = null;
  }
  const status = entry ? entry.responseStatus : undefined;
  if (Number.isInteger(status) && status > 0 && status !== 200) return 'failed';
  const body = entry ? entry.decodedBodySize : undefined;
  if (Number.isInteger(size) && size >= 0 && Number.isInteger(body) && body > 0 && body !== size) return 'failed';
  return 'document';
}

function documentSize() {
  return record(state.doc?.document).size;
}

// Marks every occurrence of the passage in the text frame; a frame still waiting for its load is painted by that load.
function markInFrame(frame, passage, key) {
  state.framePassage = { passage, key, frame };
  paintFrame(frame);
}

// The marks of the passage chosen (state.framePassage) in the text frame: mark[data-quote-mark] elements around each
// occurrence, in the page's lime, and the note. A frame still waiting for its load shows nothing of an earlier choice
// meanwhile. A frame that does not hold the document (frameHolds) is never searched: nothing is marked and the note
// says the document could not be downloaded, as a PDF's does. A frame whose text cannot be marked falls back to
// selecting the passage, as before.
function paintFrame(frame) {
  const chosen = state.framePassage;
  const held = frameHolds(frame, documentSize());
  if (held === 'waiting') {
    // nothing is answered yet: data-marked names a quote only once the viewer has answered for it (the walk waits
    // on it)
    delete frame.dataset.fallback;
    frame.dataset.marked = '';
    frame.dataset.markStatus = '';
    frame.dataset.markCount = '';
    setMarkNote('');
    return;
  }
  if (held === 'failed') {
    frame.dataset.fallback = 'download';
    frame.dataset.marked = chosen ? chosen.key || '' : '';
    frame.dataset.markStatus = chosen ? 'unavailable' : '';
    frame.dataset.markCount = chosen ? '0' : '';
    if (chosen) setMarkNote(FRAME_REASONS.download, true);
    return;
  }
  const page = frameDocument(frame);
  if (!page) return;
  delete frame.dataset.fallback;
  try {
    for (const old of page.querySelectorAll('mark[data-quote-mark]')) old.replaceWith(...old.childNodes);
    page.body.normalize();
    if (!chosen) {
      setMarkState(frame, '', null);
      return;
    }
    const walker = page.createTreeWalker(page.body, 4);
    const nodes = [];
    let source = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      nodes.push([node, source.length]);
      source += node.nodeValue;
    }
    const found = findPassages(source, chosen.passage);
    const place = offset => {
      let index = nodes.length - 1;
      while (index > 0 && nodes[index][1] > offset) index -= 1;
      return [nodes[index][0], offset - nodes[index][1]];
    };
    const lime = getComputedStyle(document.documentElement).getPropertyValue('--lime').trim();
    let first = null;
    for (const [start, end] of [...found].reverse()) {
      const range = page.createRange();
      range.setStart(...place(start));
      range.setEnd(...place(end));
      const mark = page.createElement('mark');
      mark.setAttribute('data-quote-mark', '');
      mark.style.backgroundColor = lime || 'Mark';
      mark.style.color = 'inherit';
      mark.append(range.extractContents());
      range.insertNode(mark);
      first = mark;
    }
    frame.dataset.marked = chosen.key || '';
    frame.dataset.markStatus = found.length ? 'marked' : 'not_found';
    frame.dataset.markCount = String(found.length);
    setMarkNote(textMarkNote(found.length), !found.length);
    // only the frame's own window scrolls (scrollIntoView would move the review page too)
    if (first) frame.contentWindow.scrollBy({ top: first.getBoundingClientRect().top - frame.contentWindow.innerHeight / 3, behavior: scrollBehavior() });
  } catch {
    // nothing is claimed of a frame whose text could not be marked
    frame.dataset.markStatus = '';
    frame.dataset.markCount = '';
    setMarkNote('');
    revealInFrame(frame, chosen?.passage || '');
  }
}

// --- decisions: each names the row's line and the coding review the page shows ---

function reviewCopyText(action, agent) {
  if (action === 'reject') return 'A rejected code is left out of the approved download. Add a note so the next reviewer knows why.';
  return agent
    ? 'This approval is recorded as an agent-executed synthetic review, with the agent\'s name and the time. It applies to this code in this coding review only; a new coding review starts without it.'
    : 'Your approval is recorded with your name and the time. It applies to this code in this coding review only; a new coding review starts without it.';
}

// The review dialog of one line: what the decision will name (the document, the coding review shown, the line, its
// code) is fixed when the dialog opens, so a redraw while it is open never moves the decision to another row, another
// coding review or another document.
async function openReview(line, action) {
  const code = findLine(state.doc, line);
  if (!code || !REVIEW_COPY[action] || !allowedActions(code, state.doc).includes(action)) return;
  const target = { ...decisionTarget(code, state.doc), encounter: state.doc.id };
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
  state.review = { ...target, action };
  $('#reviewEyebrow').textContent = copy.eyebrow;
  $('#reviewTitle').textContent = copy.title;
  $('#reviewCopy').textContent = reviewCopyText(action, isAgent());
  $('#reviewCode').textContent = code.code;
  $('#reviewLine').textContent = lineDetail(code);
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

function postDecision(encounter, body) {
  return api(`/api/encounters/${encodeURIComponent(encounter)}/decisions`, { method: 'POST', json: body });
}

async function afterChange(message) {
  toast(message);
  loadSession();
  await refreshDocument();
}

// A decision refused because the coding review changed under the page: nothing was recorded, so the page says so and
// reads the document again. Nothing is sent again; the member decides on what the page now shows.
async function afterConflict() {
  toast(CHANGED_TEXT);
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
    const body = decisionBody(review, review.action, approve ? state.session?.acknowledgement : '', $('#reviewNote').value);
    try {
      await postDecision(review.encounter, body);
      closeDialog('reviewDialog');
      await afterChange(approve ? `Approval recorded for ${review.code}.` : `Rejection recorded for ${review.code}.`);
    } catch (error) {
      if (changedUnderPage(error)) {
        closeDialog('reviewDialog');
        await afterConflict();
      } else {
        showError('reviewError', error.message);
      }
    } finally {
      setBusy(button, approve && !$('#reviewAckBox').checked);
    }
  });
}

// Undo posts at once, naming the decision the row shows (the server refuses it when that is no longer the one standing).
function revokeDecision(code, button) {
  const target = decisionTarget(code, state.doc);
  const encounter = state.doc.id;
  return guarded(`revoke:${target.line}`, async () => {
    setBusy(button, true);
    try {
      await postDecision(encounter, decisionBody(target, 'revoke'));
      await afterChange(`Decision undone for ${target.code}.`);
    } catch (error) {
      setBusy(button, false);
      if (changedUnderPage(error)) await afterConflict();
      else toast(error.message);
    }
  });
}

// A decision button's click: the row is found by the button's line, never by its code.
function handleDecision(action, line, button) {
  const code = findLine(state.doc, line);
  if (!code || !allowedActions(code, state.doc).includes(action)) return undefined;
  if (action === 'revoke') return revokeDecision(code, button);
  return openReview(lineOf(code, state.doc), action);
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
  // the session read again, so the Specialty field names the workspace the upload goes to (refutation N2-2-2)
  loadSession();
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

// The export dialog names the document and the coding review it was opened on: its options are built from them, and a
// download names that coding review, so one that changed under the dialog is refused rather than made from another.
// Opened again while a file is still being made, it says so and its options wait. Opened while the page reads the
// document again after a download of it was refused as changed, it says the page is loading the latest and offers
// nothing; once that read has ended it is drawn as opened on the read the page then has (redrawExportDialog).
function openExport() {
  if (!state.doc) return;
  const doc = state.doc;
  const loading = state.rereading === doc.id;
  state.exporting = { encounter: doc.id, round: roundNumber(doc), doc, loading, ready: false };
  const status = $('#exportStatus');
  status.classList.toggle('reviewed', !loading && record(doc.readiness).approved === true);
  status.textContent = loading ? LOADING_LATEST_TEXT : makingText(doc.id) || exportStatusText(doc);
  drawExportOptions();
  hideError('exportError');
  openDialog('exportDialog');
}

// What the export dialog's status says of a file being made, for a dialog on document `encounter` ('' when none is).
function makingText(encounter) {
  const making = state.making;
  return !making ? '' : making.encounter === encounter ? preparingText(making.fmt) : ANOTHER_FILE;
}

// An open export dialog's status drawn again: `sentence` when there is one (a file being made or just made), else what
// can be downloaded from `doc`; marked reviewed while `doc` allows the approved report. The status is announced, so the
// same words are not written again: a read that changes nothing in it says nothing.
function showExportStatus(doc, sentence = '') {
  const status = $('#exportStatus');
  const words = sentence || exportStatusText(doc);
  status.classList.toggle('reviewed', record(doc?.readiness).approved === true);
  if (status.textContent !== words) status.textContent = words;
}

// The read of the document an export dialog shows: the page's latest while it is still of the coding review the dialog
// was opened on (so a download just made is listed), else the read it was opened on.
function dialogDoc(exporting) {
  return state.doc?.id === exporting.encounter && roundNumber(state.doc) === exporting.round ? state.doc : exporting.doc;
}

// Draws the export dialog's options from the read it shows (dialogDoc), with the file being made, if any; on another
// document's dialog, that file makes every option wait without naming one. `focus` ([kind, fmt]) is the option to give
// the focus once drawn when the focus was lost meanwhile (a disabled button cannot hold it); else an option that held
// the focus keeps it, as drawn again.
// While the page loads the latest, every option waits without naming one; a file just made of this document makes its
// option wait (state.made). Markup the same as drawn is not drawn again, so a read that changes nothing in the dialog
// takes no option from under the focus.
function drawExportOptions(focus = null) {
  const exporting = state.exporting;
  if (!exporting) return;
  const box = $('#exportOptions');
  if (!box) return;
  const active = document.activeElement;
  const held = active?.dataset?.exportKind && box.contains?.(active) ? [active.dataset.exportKind, active.dataset.exportFmt] : null;
  const lost = !active || active === document.body;
  const making = state.making;
  const waits = exporting.loading || (making && making.encounter !== exporting.encounter) ? { kind: null, fmt: null } : making;
  const made = state.made?.encounter === exporting.encounter ? state.made : null;
  const html = exportOptions(dialogDoc(exporting), waits, made);
  if (html !== exporting.drawn) {
    box.innerHTML = html;
    exporting.drawn = html;
  }
  const target = held || (lost ? focus : null);
  if (target) $$('#exportOptions [data-export-kind]').find(item => item.dataset.exportKind === target[0] && item.dataset.exportFmt === target[1] && !item.disabled)?.focus({ preventScroll: true });
}

// Every read of the document the page shows draws an open export dialog again, from that read while it is of the coding
// review the dialog was opened on (dialogDoc): an approval recorded, or the coding review finishing, while the dialog is
// open shows at once, in its options and its status - unless a file is being made, when the dialog stays as it is (its
// options wait, its status says so) until the file is made, or its status says a file was just made, which it keeps
// saying. A dialog opened while the page loaded the latest after a refused download is drawn, once that read has ended,
// as opened on the read the page then has.
function redrawExportDialog() {
  const exporting = state.exporting;
  if (!exporting) return;
  if (exporting.loading) {
    if (state.rereading === exporting.encounter) return;
    const doc = state.doc?.id === exporting.encounter ? state.doc : exporting.doc;
    state.exporting = { encounter: exporting.encounter, round: roundNumber(doc), doc, loading: false, ready: false };
    showExportStatus(doc, makingText(doc.id));
    drawExportOptions();
    return;
  }
  if (state.making || !$('#exportDialog')?.open) return;
  const doc = dialogDoc(exporting);
  showExportStatus(doc, exporting.ready ? $('#exportStatus').textContent : '');
  drawExportOptions();
}

// One gesture makes one file: the option of a file just made waits until MADE_HOLD_MS have passed and the page has read
// the document again - its own read, or any read asked after it, whichever is shown first (the dialog drawn from that
// read) - then is offered again, the focus going back to it when nothing else holds it. A later file makes its own option
// wait instead.
function holdMade(made) {
  state.made = made;
  clearTimeout(state.madeTimer);
  let waiting = 2;
  let read = false;
  const release = () => {
    waiting -= 1;
    if (waiting > 0 || state.made !== made) return;
    state.made = null;
    state.madeRead = null;
    drawExportOptions([made.kind, made.fmt]);
  };
  const done = () => {
    if (read) return;
    read = true;
    release();
  };
  state.madeRead = { after: state.reads.asked, done };
  state.madeTimer = setTimeout(release, MADE_HOLD_MS);
  refreshDocument().then(done, done);
}

// After a download refused because its coding review changed, the page reads the document again (afterConflict), with
// the download's guard already released, so no other choice is held up meanwhile; an export dialog opened on the
// document in the meantime says the page is loading the latest until that read has ended, or until any read asked after
// the refusal is shown (loadDocument), whichever comes first.
async function rereadAfterRefusal(encounter) {
  try {
    await afterConflict();
  } finally {
    if (state.rereading === encounter) state.rereading = null;
    redrawExportDialog();
  }
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

// A file the page downloads for the member - an export just made, an earlier one, the original - is fetched first, so a
// refusal (the front door's limit, 429; a session that ended; any answer but 2xx) is seen and said in plain words instead
// of going unread to the browser's downloads while the page says the file is downloading (refutation r2, finding 21).
// It is then saved from the answer's bytes, a Blob - which the browser may keep on disk, so a file up to the bundle limit
// is not held in the page twice - under its own name. The address goes a minute later, or when the page leaves
// (releaseObjectUrls). Resolves once the browser has the file; rejects with an ApiError that says why it has not.
async function saveDownload(url, filename) {
  let response;
  try {
    response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
  } catch {
    throw new ApiError(OFFLINE_TEXT);
  }
  if (response.status === 401 || (response.redirected && new URL(response.url).pathname.startsWith('/login'))) {
    sessionEnded('expired');
    throw new ApiError('Your session has ended. Sign in again.', 401);
  }
  if (response.status === 403) {
    forgetMemory();  // a forced password change: an end (R2-18), as at the view's download
    state.standbyOn = false;  // it holds: no worker made ready ahead again (R2-10)
  }
  if (!response.ok) throw new ApiError(await downloadRefusal(response), response.status);
  const address = URL.createObjectURL(await response.blob());
  if (!(state.objectUrls instanceof Set)) state.objectUrls = new Set();
  state.objectUrls.add(address);
  startDownload(address, typeof filename === 'string' && filename ? filename : savedName(response));
  const timer = setTimeout(() => {
    if (!state.objectUrls?.delete(address)) return;
    try {
      URL.revokeObjectURL(address);
    } catch {
      // already gone
    }
  }, DOWNLOAD_ADDRESS_MS);
  timer?.unref?.();  // (a timer of the page in a browser; under Node's tests it keeps nothing waiting)
}

// What a refused download says: the server's own sentence where it answered one, the wait at the front door's limit
// (429, from its Retry-After), else a plain sentence of the answer.
async function downloadRefusal(response) {
  const data = (response.headers.get('Content-Type') || '').includes('application/json') ? await response.json().catch(() => null) : null;
  if (response.status === 429 && !data) return rateLimitText({ retry_after: Number(response.headers.get('Retry-After')) });
  return errorText(response.status, data);
}

// The name the server gave the file (Content-Disposition), else 'download'.
function savedName(response) {
  const header = response.headers.get('Content-Disposition') || '';
  const encoded = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      // fall back to the plain name
    }
  }
  const plain = /filename\s*=\s*"([^"]+)"/i.exec(header) || /filename\s*=\s*([^;]+)/i.exec(header);
  return plain ? plain[1].trim() : 'download';
}

// A download link the member clicks (an earlier export, the original) goes the same way: fetched first, a refusal said.
function saveLinked(link) {
  const address = link.getAttribute('href') || '';
  saveDownload(address, link.getAttribute('download') || '').catch(error => {
    if (link.closest?.('#exportDialog') && $('#exportDialog')?.open) showError('exportError', error.message);
    else toast(error.message);
  });
}

// POST reports {kind, fmt, round}: the round the export dialog was opened on. While it runs every option waits and the
// one chosen says it is being prepared, as the status does; the file is said to be ready, and downloaded, only once the
// server has made it (201). The options then come back - the one just used a moment later (holdMade) - and the dialog
// lists the new file once the page has read the document again. A refusal that says what is missing (its readiness
// blockers), or that the file could not be made, is shown in the dialog with the options back, so the member can try
// again (as a notice when the dialog was closed meanwhile); any other conflict means the coding review changed under the
// dialog, so the dialog closes and the page reads the document again and says so (rereadAfterRefusal). A dialog opened
// meanwhile on another document is drawn again for its own. The option of a file just made, and a dialog waiting for the
// latest, make nothing.
function generateReport(kind, fmt) {
  const exporting = state.exporting;
  if (!exporting || exporting.round === null || exporting.loading) return undefined;
  const made = state.made;
  if (made && made.encounter === exporting.encounter && made.kind === kind && made.fmt === fmt) return undefined;
  let refused = false;
  return guarded('export', async () => {
    state.making = { encounter: exporting.encounter, kind, fmt };
    exporting.ready = false;
    drawExportOptions();
    $('#exportStatus').textContent = preparingText(fmt);
    hideError('exportError');
    // whether the dialog is still on this document when the request ends, and whether it is open
    const same = () => state.exporting?.encounter === exporting.encounter;
    const shown = () => same() && $('#exportDialog').open;
    let report;
    try {
      report = await api(`/api/encounters/${encodeURIComponent(exporting.encounter)}/reports`, { method: 'POST', json: { kind, fmt, round: exporting.round } });
      if (!safeDownloadUrl(report.download_url)) throw new ApiError('The download could not be started. Try again.');
    } catch (error) {
      state.making = null;
      const blockers = strings(error.details?.blockers);
      const sentence = blockers.length ? `${error.message} ${blockers.join(' ')}` : error.message;
      if (changedUnderPage(error) && !blockers.length && state.doc?.id === exporting.encounter) {
        const onThis = same();
        if (state.exporting === exporting) state.exporting = null;
        if (onThis) closeDialog('exportDialog');
        state.rereading = exporting.encounter;
        state.rereadAfter = state.reads.asked;
        refused = true;
        return;
      }
      if (state.exporting) $('#exportStatus').textContent = exportStatusText(dialogDoc(state.exporting));
      if (shown()) {
        showError('exportError', sentence);
        $('#exportError').scrollIntoView?.({ block: 'nearest' });  // under the options, which may be scrolled past
      } else {
        toast(state.doc?.id === exporting.encounter ? sentence : `${text(exporting.doc?.title) || 'Another document'}: ${sentence}`);
      }
      drawExportOptions([kind, fmt]);
      return;
    }
    state.making = null;
    if (state.exporting) {
      state.exporting.ready = same();
      $('#exportStatus').textContent = same() ? readyText(fmt, report.filename) : exportStatusText(dialogDoc(state.exporting));
    }
    holdMade({ encounter: exporting.encounter, kind, fmt });
    drawExportOptions([kind, fmt]);
    try {
      await saveDownload(safeDownloadUrl(report.download_url), report.filename);
    } catch (error) {
      // made, but not downloaded (refutation r2, finding 21): the dialog never says it is; the file is listed among the
      // downloads once the page has read the document again, to try again
      if (state.exporting?.encounter === exporting.encounter) {
        state.exporting.ready = false;
        $('#exportStatus').textContent = exportStatusText(dialogDoc(state.exporting));
      }
      if (shown()) showError('exportError', error.message);
      else if (error.status !== 401) toast(error.message);
    }
  }).then(() => (refused ? rereadAfterRefusal(exporting.encounter) : undefined));
}

// --- automatic sign-out after inactivity, and at the session's cap (B5) -------------------------------------------
// The server ends a session idle longer than its limit, or older than its cap (studio.sessions); the page keeps one timer
// with it, shared by the tabs of this browser that show the same session (BroadcastChannel, else localStorage events;
// every access in try/catch), so an idle tab never signs out a tab in use. The timer is armed the moment the page loads,
// from the seconds the server put on the page (data-idle-seconds, data-cap-seconds, data-warning-seconds;
// studio.sessions.page_config), so it never waits on a ping that may fail (refutation r2, finding 13). Input sends the
// activity ping at most once a minute - one that failed is tried again on input after RETRY_MS, the deadline standing
// meanwhile - and the ping's answer is the server's own remaining time, so the timer never drifts from the session. The
// deadline is the earlier of the idle end and the session's cap (finding 16). A warning comes SESSION_IDLE_WARNING_SECONDS
// before it: before the idle end with a button that sends the ping, before the cap with a sentence to send or copy what
// is typed, since the cap cannot be moved. When the warning closes the focus goes back where it was, into the viewer's
// frame too (finding 15). At the end the page closes the viewer, wipes what it keeps for speed (forgetMemory, R2-18),
// lets go of its object addresses, empties #main and every dialog, and submits the sign-out form. Answers typed and not
// sent are lost then: the warning is their protection (no drafts are kept, because a draft would put a document's text
// in the browser's storage).
// Every message between tabs names its session (data-session: a per-sign-in value, which the ping answers too), and a
// tab acts on its own session's news only. A message of another session - the browser was signed in again, or the
// message is stale - makes the tab ask the server which session it is in (the ping marked a poll: no activity), and a
// tab whose session is no longer the browser's leaves. A 401, in whichever tab meets it, is told to every tab of the
// session, and each clears its screen (finding 14).
const DEFAULT_IDLE_SECONDS = 900;  // the doctors' limit, for a page the server gave no seconds (it always gives them)
const RETRY_MS = 15000;  // a ping that failed is tried again on the next input after this
const IDLE_TEXT = 'CPT Studio signs you out after a while without activity, and clears the screen. Answers you have typed and not sent are lost when it does.';
const CAP_TEXT = 'This session has reached its time limit. CPT Studio clears the screen and signs you out when it ends. Send or copy anything you are typing now: you will need to sign in again.';
const idle = {
  deadline: 0, idleEnd: 0, capEnd: 0, warningMs: 120000, lastPing: 0, pinging: null, checking: null, timer: 0,
  channel: null, gone: false, started: false, session: '', capClosed: 0, returnFocus: null,
};

function seconds(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

// The seconds the server put on the page (studio.sessions.page_config), each null when it is absent or no number, and
// the page's session tag ('' when absent).
function pageSession(dataset) {
  const data = dataset || {};
  const number = value => (typeof value === 'string' && value.trim() !== '' ? seconds(value) : null);
  return { idle: number(data.idleSeconds), cap: number(data.capSeconds), warning: number(data.warningSeconds),
    session: typeof data.session === 'string' ? data.session : '' };
}

// The timer armed from the page's own seconds, before any ping answers: it is never unarmed.
function armFromPage(now = Date.now()) {
  const config = pageSession(typeof document === 'object' ? document.body?.dataset : null);
  idle.session = config.session;
  adoptDeadline(now + (config.idle ?? DEFAULT_IDLE_SECONDS) * 1000, config.warning === null ? null : config.warning * 1000,
    false, config.cap === null ? null : now + config.cap * 1000);
}

function releaseObjectUrls() {
  for (const address of state.objectUrls || []) {
    try {
      URL.revokeObjectURL(address);
    } catch {
      // already gone
    }
  }
  state.objectUrls = new Set();
}

// Everything the page shows of the workspace goes: the viewer, its addresses, #main, every dialog, the notices.
function clearScreen() {
  stopPolling();
  stopTicker();
  closeViewer();
  forgetMemory();
  closeList();
  releaseObjectUrls();
  closeDocumentDialogs();
  state.doc = null;
  state.docKey = '';
  state.viewerKey = '';
  const main = $('#main');
  if (main) main.innerHTML = '';
  for (const dialog of $$('dialog')) {
    if (dialog.open) dialog.close();
    dialog.replaceChildren?.();
  }
  const notice = $('#toast');
  if (notice) notice.textContent = '';
}

// Every message names this tab's session.
function shareSession(message) {
  const data = { ...message, session: idle.session, at: Date.now() };
  try {
    if (idle.channel) {
      idle.channel.postMessage(data);
      return;
    }
  } catch {
    // fall through to the storage events
  }
  try {
    localStorage.setItem(SESSION_CHANNEL, JSON.stringify(data));
  } catch {
    // no storage here: this tab keeps its own timer
  }
}

// A tab's news: acted on when it is of this tab's session; any other makes this tab ask the server which session it is
// in, never adopt it.
function receiveSession(message) {
  if (!message || typeof message !== 'object' || idle.gone) return;
  if (message.session !== idle.session) {
    checkSession();
    return;
  }
  if (message.type === 'deadline') adoptDeadline(Number(message.deadline), Number(message.warningMs), false, Number(message.cap));
  else if (message.type === 'signed-out') leaveSignedOut(message.reason === 'idle' ? 'idle' : 'expired');
}

function openSessionChannel() {
  try {
    idle.channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel(SESSION_CHANNEL) : null;
    if (idle.channel) idle.channel.onmessage = event => receiveSession(event.data);
  } catch {
    idle.channel = null;
  }
  try {
    window.addEventListener('storage', event => {
      if (event.key !== SESSION_CHANNEL || !event.newValue) return;
      try {
        receiveSession(JSON.parse(event.newValue));
      } catch {
        // not a message of this page
      }
    });
  } catch {
    // no storage events here
  }
}

// The idle end only moves later (the server's last activity only moves forward) and the cap only comes closer; the
// deadline is the earlier of the two. Another tab's news never shortens this one's idle time.
function adoptDeadline(deadline, warningMs, share = true, cap = null) {
  if (Number.isFinite(warningMs) && warningMs > 0) idle.warningMs = warningMs;
  let moved = false;
  if (Number.isFinite(deadline) && deadline > idle.idleEnd) {
    idle.idleEnd = deadline;
    moved = true;
  }
  if (Number.isFinite(cap) && cap > 0 && (!idle.capEnd || cap < idle.capEnd)) {
    idle.capEnd = cap;
    moved = true;
  }
  if (!moved) return;
  idle.deadline = idle.capEnd ? Math.min(idle.idleEnd, idle.capEnd) : idle.idleEnd;
  if (share) shareSession({ type: 'deadline', deadline: idle.idleEnd, cap: idle.capEnd, warningMs: idle.warningMs });
  scheduleIdle();
}

// The answer of the ping, or of a re-check: a tab of another session than the browser's leaves; else the server's own
// remaining time moves the timer.
function applySessionAnswer(data, share) {
  const tag = typeof data?.session === 'string' ? data.session : '';
  if (tag && idle.session && tag !== idle.session) {
    leaveSignedOut('expired');
    return;
  }
  const left = seconds(data?.idle_seconds);
  const cap = seconds(data?.cap_seconds);
  const lead = seconds(data?.warning_seconds);
  const now = Date.now();
  if (left !== null) adoptDeadline(now + left * 1000, lead === null ? null : lead * 1000, share, cap === null ? null : now + cap * 1000);
}

function sendActivity() {
  if (idle.gone) return Promise.resolve();
  if (idle.pinging) return idle.pinging;
  idle.lastPing = Date.now();
  idle.pinging = (async () => {
    try {
      applySessionAnswer(await api(ACTIVITY_URL, { method: 'POST', json: {} }), true);
    } catch (error) {
      // a 401 has already signed the page out; any other failure keeps the deadline this page has, and the next input
      // after RETRY_MS tries again
      if (error?.status !== 401) idle.lastPing = Date.now() - ACTIVITY_EVERY_MS + RETRY_MS;
    } finally {
      idle.pinging = null;
    }
  })();
  return idle.pinging;
}

// Which session this tab is in, asked of the server without counting as activity: the ping marked a poll.
function checkSession() {
  if (idle.gone) return Promise.resolve();
  if (idle.checking) return idle.checking;
  idle.checking = (async () => {
    try {
      applySessionAnswer(await api(ACTIVITY_URL, { method: 'POST', json: {}, poll: true }), false);
    } catch {
      // a 401 has already signed the page out; offline, the timer stands
    } finally {
      idle.checking = null;
    }
  })();
  return idle.checking;
}

function noteInput() {
  if (idle.gone || idle.pinging) return;
  if (Date.now() - idle.lastPing >= ACTIVITY_EVERY_MS) sendActivity();
}

// Whether the session's cap comes before its idle end: the warning then says so, and the page signs out as expired.
function capFirst() {
  return Boolean(idle.capEnd) && idle.capEnd <= idle.idleEnd;
}

function capWarningText(ms) {
  const minutes = Math.max(1, Math.ceil(ms / 60000));
  return `Your session ends in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
}

function showIdleWarning(left) {
  const dialog = $('#idleDialog');
  if (!dialog) return;
  const cap = capFirst();
  const title = $('#idleTitle');
  if (title) title.textContent = cap ? capWarningText(left) : idleWarningText(left);
  const copy = $('#idleText');
  if (copy) copy.textContent = cap ? CAP_TEXT : IDLE_TEXT;
  const stay = $('#idleStay');
  if (stay) stay.hidden = cap;
  const close = $('#idleClose');
  if (close) close.hidden = !cap;
  if (dialog.open) return;
  const active = document.activeElement;
  idle.returnFocus = active && active !== document.body ? active : null;
  dialog.showModal();
}

// The warning closes, and the focus goes back where it was - into the viewer's frame too, so the next key scrolls it.
function hideIdleWarning() {
  const dialog = $('#idleDialog');
  if (!dialog?.open) return;
  dialog.close();
  const back = idle.returnFocus;
  idle.returnFocus = null;
  if (!back || back.isConnected === false || typeof back.focus !== 'function') return;
  try {
    back.focus({ preventScroll: true });
    if (back.tagName === 'IFRAME') back.contentWindow?.focus();
  } catch {
    // gone meanwhile
  }
}

// The cap's warning, read: closed until the end, which no ping moves.
function closeCapWarning() {
  idle.capClosed = idle.capEnd;
  hideIdleWarning();
}

function scheduleIdle() {
  clearTimeout(idle.timer);
  if (idle.gone) return;
  const next = idleStep(idle.deadline, idle.warningMs, Date.now());
  if (next.step === 'out') {
    signOutIdle(capFirst() ? 'expired' : 'idle');
    return;
  }
  if (next.step === 'warn' && !(capFirst() && idle.capClosed === idle.capEnd)) showIdleWarning(next.left);
  else hideIdleWarning();
  if (next.in === null) return;
  idle.timer = setTimeout(scheduleIdle, next.step === 'warn' ? Math.min(1000, next.in) : Math.max(1000, next.in));
}

// Another tab of this session signed out, or the server said the session is over: this one clears its screen and goes to
// the sign-in page too.
function leaveSignedOut(reason) {
  if (idle.gone) return;
  idle.gone = true;
  clearTimeout(idle.timer);
  goToLogin(reason);
}

// The server answered this tab 401: every tab of the session is told, and this one leaves, whatever its timer did.
function sessionEnded(reason) {
  if (!idle.gone) shareSession({ type: 'signed-out', reason });
  idle.gone = true;
  clearTimeout(idle.timer);
  goToLogin(reason);
}

function signOutIdle(reason = 'idle') {
  if (idle.gone) return;
  idle.gone = true;
  clearTimeout(idle.timer);
  shareSession({ type: 'signed-out', reason });
  state.leaving = true;
  clearScreen();
  const form = $('#signoutForm');
  if (!form) return;
  form.setAttribute('action', `/logout/?reason=${reason === 'expired' ? 'expired' : 'idle'}`);
  form.submit?.();
}

function startIdleWatch() {
  if (idle.started) return;
  idle.started = true;
  armFromPage();
  openSessionChannel();
  for (const type of ACTIVITY_INPUTS) document.addEventListener(type, noteInput, { capture: true, passive: true });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) scheduleIdle(); });
  $('#signoutForm')?.addEventListener('submit', () => {
    if (!idle.gone) shareSession({ type: 'signed-out', reason: 'expired' });
    idle.gone = true;
    forgetMemory();
  });
  sendActivity();
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
  const zoom = target.closest('[data-zoom]');
  if (zoom) {
    zoomViewer(zoom.dataset.zoom);
    return;
  }
  const quote = target.closest('[data-quote]');
  if (quote) {
    showQuote(quote.dataset.quote);
    return;
  }
  const decision = target.closest('[data-decision]');
  if (decision) {
    handleDecision(decision.dataset.decision, decision.dataset.line, decision);
    return;
  }
  const access = target.closest('[data-member-access]');
  if (access) {
    askMemberAccess(access);
    return;
  }
  const word = target.closest('[data-word-original]');
  if (word) {
    askWordOriginal(word.dataset.wordOriginal);
    return;
  }
  const linked = target.closest('a[download]');
  if (linked && !(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)) {
    const href = linked.getAttribute('href') || '';
    if (safeDownloadUrl(href) || safeOriginalUrl(href)) {
      event.preventDefault();
      saveLinked(linked);
      return;
    }
  }
  const report = target.closest('[data-export-kind]');
  if (report) {
    // the second (or third) click of one gesture - a double click - is not a choice of its own
    if (event.detail > 1) return;
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
    confirm: confirmChosen,
    'more-documents': () => moreDocuments(),
    'stay-signed-in': () => sendActivity(),
    'idle-close': () => closeCapWarning(),
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
  document.addEventListener('load', noteFrameLoad, true);
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
  window.addEventListener('pagehide', forgetMemory);
  window.addEventListener('pageshow', event => { if (event.persisted) scheduleStandby(PDF_STANDBY.next); });
  startIdleWatch();
  firstRoute();
}

if (typeof module === 'object' && module.exports) {
  module.exports = {
    escapeHtml, lookup, parseIsoDate, formatDate, formatTimestamp, readCookie, safeDownloadUrl, safeOriginalUrl, safeViewUrl,
    pollDelay, parseRoute, isClientOutdated, errorText, newClientKey, durationText, clockOffset, elapsedText, findPassage,
    canReview, stateLabel, codesOf, lineOf, roundNumber, findLine, questionsOf, answersOf, notesOf, progressPhase, isBusy,
    shouldPoll, codeStatus, currentDecision, shownStatus, unitsLabel, modifiersLabel, lineDetail, secondCheck, quotesOf,
    quoteKey, viewerUrl, viewerKind, allowedActions, decisionTarget, decisionBody, answersPayload, insuranceLabel,
    insuranceText, tallyText, exportOffered, readinessText, exportStatusText, emptyCodesText, documentRow, inQueue, listBody,
    listDescription, inviteMarkup, overviewView, documentsView, howItWorksView, messageView, uploadAck, ackView, reviewMeta,
    reviewHeading, viewerPanel, quotesPanel, progressSteps, progressPanel, questionsPanel, answersPanel, codeRow,
    codesSection, notesPanel, activityLog, reviewColumn, reviewView, reportItem, exportOptions, uploadForm, renderKey,
    viewerKey, api, sendAnswers, submitReview, handleDecision, progressAction, onClick, onInput, showQuote, state,
    STATE_LABELS, CODE_STATUSES, DECISIONS, ACTION_BUTTONS, PHASES, PHASE_TITLES, STEP_KEYS, STEP_LABELS, PROGRESS_ACTIONS,
    INSURANCE_CHOICES, QUEUE_STATES, OUTDATED_TEXT, CHANGED_TEXT, UNITS_NOT_GIVEN, MODIFIERS_NOT_GIVEN, CLIENT_HEADER,
    CLIENT_VERSION, MAX_ANSWER_CHARS, CONVERTED_NOTE, REVIEW_AGAIN, MADE_HOLD_MS, LOADING_LATEST_TEXT, loadDocument, refreshDocument,
    findPassages, characterSpans, pageCharacters, pageText, overprintCopies, characterPieces, quoteEdges, foldedOccurrences,
    locateQuote, markNote, frameNote, textMarkNote, FRAME_REASONS, pdfAssets, pdfCapable, loadPdfLibrary, withinLimit, TimeLimit,
    PDF_IMPORT, mountViewer, closeViewer, showPdfQuote, frameQuote, fallbackViewer, clearViewerMark, drawPage, releasePage,
    paintPage, layoutPages, zoomViewer, renderDocument, PDF_VIEW, ZOOM_STEPS, ZOOM_FIT,
    continuesDrawing, keepsEdge, NUMBER_SEPARATORS, libraryWatchdog, startWorker, downloadDocument, scrollToQuote, relayoutPages,
    buildPages, frameHolds, noteFrameLoad, watchFrameInput, markInFrame, paintFrame,
    csrfCookieName, csrfValue, signedOutReason, loginAddress, idleStep, idleWarningText, rateLimitText, teamMembers, memberRow,
    teamList, teamView, downloadLinks, showTeam, setMemberAccess, askConfirm, confirmChosen, askWordOriginal, clearScreen,
    saveDownload, downloadRefusal, savedName, saveLinked, noteRefusedFrame, FRAME_LIMIT_TEXT, FRAME_REFUSED_TEXT,
    generateReport, readyText, startDownload,
    goToLogin, goToAccount, sendActivity, adoptDeadline, scheduleIdle, signOutIdle, receiveSession, shareSession, noteInput,
    pageSession, armFromPage, applySessionAnswer, checkSession, sessionEnded, leaveSignedOut, capFirst, capWarningText,
    showIdleWarning, hideIdleWarning, closeCapWarning, startIdleWatch, IDLE_TEXT, CAP_TEXT, RETRY_MS, DEFAULT_IDLE_SECONDS,
    idle, POLL_HEADER, ACTIVITY_URL, ACTIVITY_EVERY_MS, ACTIVITY_INPUTS, WORD_ORIGINAL_TEXT, SESSION_CHANNEL, ROUTE_TITLES, schedulePoll,
    refreshIfWaiting, renderSession,
    route, showDocument, shellSession, refreshSession, endEntrance, firstRoute, loadSession, SESSION_FRESH_MS, LOADING_AFTER_MS,
    scheduleStandby, startStandby, endStandby, takeWorker, forgetMemory, downloadFor, forgetPdfLibrary, PDF_STANDBY,
    keepView, startEarly, takeEarly, dropEarly, KEPT_VIEWS,
    showList, closeList, listPage, applySearch, moreDocuments, LIST_ADDRESS, SEARCH_URL, SEARCH_PAUSE_MS, AUTO_PAGES, LOCAL_SEARCH_MAX, MORE_TEXT,
  };
}
if (typeof document !== 'undefined') boot();
